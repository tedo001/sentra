"""SENTRA's data layer: SQL store, vector index, vault and encrypted backups.

Run:  python -m unittest test_sentra_data -v

No network is needed: the S3 and WebDAV targets are exercised against small
servers on 127.0.0.1 that check the requests the way the real services do -
the S3 one recomputes every AWS Signature V4 and refuses a wrong one.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
import unittest
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

import numpy as np

from sif import backup
from sif.datastore import DataStore, describe_url
from sif.vault import Vault
from sif.vectorstore import VectorStore

PASSPHRASE = "correct horse battery"
ACCESS, SECRET = "AKIDTEST", "secret/key+example"


def _row(reference: str, text: str, risk: float = 50.0, sif: bool = False) -> dict:
    return {"reference": reference, "raw_text": text, "risk_score": risk,
            "sif_potential": sif, "reported_on": "2026-09-01", "site": "Duliajan",
            "_timestamp": "12:00:00"}


class TempDir(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.mkdtemp(prefix="sentra-data-")
        self.addCleanup(shutil.rmtree, self.folder, True)

    def store(self, name: str = "s.db") -> DataStore:
        store = DataStore("sqlite:///" + os.path.join(self.folder, name))
        self.addCleanup(store.dispose)
        return store


class TestDataStore(TempDir):
    def test_pushing_twice_changes_nothing_and_a_change_is_an_update(self) -> None:
        store = self.store()
        reports = [("fp1", _row("NM-1", "a fall")), ("fp2", _row("NM-2", "a spill"))]
        self.assertEqual(store.push(reports=reports)["reports"], (2, 0))
        self.assertEqual(store.push(reports=reports)["reports"], (0, 0))
        changed = [("fp1", {**reports[0][1], "risk_score": 90.0})]
        self.assertEqual(store.push(reports=changed)["reports"], (0, 1))

    def test_private_keys_are_not_stored(self) -> None:
        store = self.store()
        store.push(reports=[("fp1", _row("NM-1", "a fall"))])
        self.assertNotIn("_timestamp", store.report("fp1"))

    def test_pull_brings_only_what_this_machine_lacks(self) -> None:
        store = self.store()
        store.push(reports=[("fp1", _row("NM-1", "a")), ("fp2", _row("NM-2", "b"))],
                   decisions=[{"fingerprint": "fp1", "decided_at": "2026-09-01T10:00:00",
                               "decision": "confirmed", "reference": "NM-1"}],
                   actions=[{"id": "a1", "title": "Gas test"}])
        self.assertEqual([fp for fp, _row in store.pull_reports({"fp1"})], ["fp2"])
        self.assertEqual(store.pull_decisions(set()), [
            {"fingerprint": "fp1", "decided_at": "2026-09-01T10:00:00",
             "decision": "confirmed", "reference": "NM-1"}])
        self.assertEqual(store.pull_decisions({"fp1@2026-09-01T10:00:00"}), [])
        self.assertEqual(store.pull_actions({"a1"}), [])
        store.remove_action("a1")
        store.remove_decision("fp1", "2026-09-01T10:00:00")
        self.assertEqual(store.counts()["actions"], 0)
        self.assertEqual(store.counts()["decisions"], 0)

    def test_export_then_import_into_an_empty_database_restores_everything(self) -> None:
        first = self.store("a.db")
        first.push(reports=[("fp1", _row("NM-1", "a"))],
                   audit=[{"hash": "h1", "at": "2026-09-01T10:00:00", "action": "signed in",
                           "user": "a", "summary": "x", "when": "y"}])
        VectorStore(first).upsert([("fp1", "NM-1", np.ones(4, dtype=np.float32))], "enc")
        data = json.loads(json.dumps(first.export()))
        second = self.store("b.db")
        counts = second.import_(data)
        self.assertEqual(counts["reports"], (1, 0))
        self.assertEqual(counts["vectors"], (1, 0))
        self.assertEqual(second.import_(data)["reports"], (0, 0))
        self.assertEqual(second.counts(), first.counts())
        hits = VectorStore(second).search(np.ones(4), "enc")
        self.assertEqual(hits[0][0], "fp1")

    def test_the_sync_log_keeps_outcomes(self) -> None:
        store = self.store()
        store.log("sync", "here", True, "pushed 1")
        store.log("backup", "there", False, "refused")
        self.assertEqual(store.last("sync")["detail"], "pushed 1")
        self.assertIsNone(store.last("backup"))
        self.assertEqual([row["kind"] for row in store.history()], ["backup", "sync"])

    def test_a_server_url_is_described_without_its_password(self) -> None:
        text = describe_url("postgresql://hse:s3cret@db.oil.local/sentra")
        self.assertNotIn("s3cret", text)
        self.assertIn("db.oil.local", text)


class TestVectorStore(TempDir):
    def test_search_ranks_by_cosine_and_keeps_encoders_apart(self) -> None:
        vectors = VectorStore(self.store())
        vectors.upsert([("a", "NM-1", np.array([1, 0, 0], dtype=np.float32)),
                        ("b", "NM-2", np.array([0.6, 0.8, 0], dtype=np.float32)),
                        ("c", "NM-3", np.array([0, 0, 1], dtype=np.float32))], "hash")
        vectors.upsert([("a", "NM-1", np.ones(5, dtype=np.float32))], "other")
        hits = vectors.search(np.array([1, 0.1, 0]), "hash", k=2)
        self.assertEqual([hit[1] for hit in hits], ["NM-1", "NM-2"])
        self.assertEqual(vectors.search(np.array([1, 0, 0]), "hash", exclude=["a"])[0][0], "b")
        self.assertEqual(vectors.missing(["a", "z"], "hash"), ["z"])
        self.assertEqual(vectors.count("hash"), 3)
        self.assertEqual(vectors.encoders(), ["hash", "other"])
        self.assertEqual(vectors.search(np.ones(3), "nothing"), [])


class TestVault(TempDir):
    def test_secrets_are_sealed_at_rest_and_read_back(self) -> None:
        vault = Vault(self.folder)
        vault.put("passphrase", PASSPHRASE)
        self.assertEqual(vault.get("passphrase"), PASSPHRASE)
        self.assertTrue(vault.has("passphrase"))
        with open(vault.path, encoding="utf-8") as handle:
            self.assertNotIn(PASSPHRASE, handle.read())
        vault.clear("passphrase")
        self.assertIsNone(vault.get("passphrase"))
        if os.name == "posix":
            self.assertEqual(os.stat(os.path.join(self.folder, "vault.key")).st_mode & 0o077, 0)


class TestArchive(TempDir):
    def _archive(self):
        path = os.path.join(self.folder, "users.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('{"users": []}')
        model = os.path.join(self.folder, "model")
        os.makedirs(model)
        with open(os.path.join(model, "m.json"), "w", encoding="utf-8") as handle:
            handle.write("{}")
        return backup.build_archive({"reports": [{"fingerprint": "fp1"}]},
                                    [("users.json", path), ("model", model),
                                     ("missing.json", os.path.join(self.folder, "nope"))])

    def test_an_archive_round_trips_and_lists_every_file_with_its_checksum(self) -> None:
        archive, manifest = self._archive()
        self.assertEqual(sorted(manifest["files"]), ["database.json", "model/m.json",
                                                     "users.json"])
        blob = backup.seal(archive, PASSPHRASE)
        self.assertTrue(blob.startswith(backup.MAGIC))
        self.assertNotIn(b"fingerprint", blob)
        opened, members = backup.read_archive(blob, PASSPHRASE)
        self.assertEqual(opened["counts"], {"reports": 1})
        self.assertEqual(members["users.json"], b'{"users": []}')

    def test_a_wrong_passphrase_or_a_damaged_archive_is_refused(self) -> None:
        blob = backup.seal(self._archive()[0], PASSPHRASE)
        with self.assertRaises(backup.BackupError):
            backup.read_archive(blob, "not the passphrase")
        damaged = blob[:-10] + bytes(10)
        with self.assertRaises(backup.BackupError):
            backup.read_archive(damaged, PASSPHRASE)
        with self.assertRaises(backup.BackupError):
            backup.seal(b"x", "")

    def test_unpack_writes_the_files_but_never_outside_its_folder(self) -> None:
        target = os.path.join(self.folder, "out")
        backup.unpack({"a/b.txt": b"1", "../escape.txt": b"2", "database.json": b"{}"},
                      target)
        self.assertTrue(os.path.exists(os.path.join(target, "a", "b.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.folder, "escape.txt")))
        self.assertFalse(os.path.exists(os.path.join(target, "database.json")))

    def test_a_schedule_is_due_after_its_interval(self) -> None:
        now = datetime(2026, 9, 25, 12, 0)
        self.assertTrue(backup.due("daily", "", now))
        self.assertTrue(backup.due("daily", "2026-09-24T11:00:00", now))
        self.assertFalse(backup.due("daily", "2026-09-25T01:00:00", now))
        self.assertFalse(backup.due("weekly", "2026-09-20T12:00:00", now))
        self.assertFalse(backup.due("off", "", now))


class TestSignatureV4(unittest.TestCase):
    """The AWS SigV4 test suite's own cases."""

    def _sign(self, url: str) -> str:
        headers = {"host": "example.amazonaws.com", "x-amz-date": "20150830T123600Z"}
        return backup.sign_v4("GET", url, headers, backup.EMPTY_SHA256, "AKIDEXAMPLE",
                              "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY", "us-east-1",
                              "service", "20150830T123600Z")

    def test_get_vanilla(self) -> None:
        self.assertEqual(
            self._sign("https://example.amazonaws.com/"),
            "AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20150830/us-east-1/service/aws4_request, "
            "SignedHeaders=host;x-amz-date, "
            "Signature=5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31")

    def test_get_vanilla_query_order_key_case(self) -> None:
        self.assertTrue(self._sign("https://example.amazonaws.com/?Param2=value2&Param1=value1")
                        .endswith("b97d918cfa904a5beff61c982a1b6f458b799221646efd99d3219ec94cdf2500"))


# -- small local services ---------------------------------------------------------------


class _S3(BaseHTTPRequestHandler):
    objects: dict = {}

    def log_message(self, *args) -> None:  # quiet
        pass

    def _authorised(self, body: bytes) -> bool:
        given = self.headers.get("Authorization", "")
        payload = hashlib.sha256(body).hexdigest()
        if self.headers.get("x-amz-content-sha256") != payload:
            return False
        headers = {"host": self.headers["Host"], "x-amz-date": self.headers["x-amz-date"],
                   "x-amz-content-sha256": payload}
        url = f"http://{self.headers['Host']}{self.path}"
        expected = backup.sign_v4(self.command, url, headers, payload, ACCESS, SECRET,
                                  "us-east-1", "s3", self.headers["x-amz-date"])
        return given == expected

    def _reply(self, code: int, body: bytes = b"") -> None:
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if not self._authorised(body):
            return self._reply(403, b"<Error><Code>SignatureDoesNotMatch</Code></Error>")
        parts = urlsplit(self.path)
        key = unquote(parts.path).split("/", 2)[2] if parts.path.count("/") >= 2 else ""
        if self.command == "PUT":
            self.objects[key] = body
            return self._reply(200)
        if self.command == "DELETE":
            self.objects.pop(key, None)
            return self._reply(204)
        if not key:
            prefix = parse_qs(parts.query).get("prefix", [""])[0]
            items = "".join(f"<Contents><Key>{name}</Key><Size>{len(data)}</Size>"
                            f"<LastModified>2026-09-25T10:00:00.000Z</LastModified></Contents>"
                            for name, data in sorted(self.objects.items())
                            if name.startswith(prefix))
            return self._reply(200, ('<ListBucketResult xmlns="http://s3.amazonaws.com/doc/'
                                     f'2006-03-01/">{items}</ListBucketResult>').encode())
        if key in self.objects:
            return self._reply(200, self.objects[key])
        return self._reply(404)

    do_GET = do_PUT = do_DELETE = _handle


class _DAV(BaseHTTPRequestHandler):
    files: dict = {}

    def log_message(self, *args) -> None:
        pass

    def _reply(self, code: int, body: bytes = b"") -> None:
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle(self) -> None:
        if self.headers.get("Authorization") is None:
            return self._reply(401)
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        name = unquote(self.path.rsplit("/", 1)[-1])
        if self.command == "PUT":
            self.files[name] = body
            return self._reply(201)
        if self.command == "DELETE":
            return self._reply(204 if self.files.pop(name, None) is not None else 404)
        if self.command == "GET":
            return self._reply(200, self.files[name]) if name in self.files else self._reply(404)
        if self.command == "MKCOL":
            return self._reply(201)
        rows = "".join(f"<d:response><d:href>/dav/{item}</d:href><d:propstat><d:prop>"
                       f"<d:getcontentlength>{len(data)}</d:getcontentlength>"
                       f"<d:getlastmodified>Fri, 25 Sep 2026 10:00:00 GMT</d:getlastmodified>"
                       f"</d:prop></d:propstat></d:response>" for item, data in self.files.items())
        return self._reply(207, f'<d:multistatus xmlns:d="DAV:">{rows}</d:multistatus>'.encode())

    do_GET = do_PUT = do_DELETE = do_MKCOL = do_PROPFIND = _handle


def _serve(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class TestTargets(TempDir):
    def _round_trip(self, target: backup.Target) -> None:
        blob = backup.seal(b"archive bytes", PASSPHRASE)
        for index in range(3):
            target.upload(f"SENTRA-host-2026092{index}-100000.sentra", blob)
        names = [item.name for item in target.list()]
        self.assertEqual(names, [f"SENTRA-host-2026092{index}-100000.sentra"
                                 for index in (2, 1, 0)])
        self.assertEqual(target.download(names[0]), blob)
        self.assertEqual(target.prune(2), ["SENTRA-host-20260920-100000.sentra"])
        self.assertEqual(len(target.list()), 2)
        ok, message = target.test()
        self.assertTrue(ok, message)
        self.assertEqual(len(target.list()), 2)  # the probe is gone

    def test_a_folder(self) -> None:
        self._round_trip(backup.FolderTarget(os.path.join(self.folder, "cloud")))

    def test_s3_compatible_storage_with_signed_requests(self) -> None:
        _S3.objects = {}
        server = _serve(_S3)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        endpoint = f"http://127.0.0.1:{server.server_address[1]}"
        self._round_trip(backup.S3Target(endpoint, "hse-backups", ACCESS, SECRET,
                                         prefix="sentra"))
        self.assertTrue(all(key.startswith("sentra/") for key in _S3.objects))
        wrong = backup.S3Target(endpoint, "hse-backups", ACCESS, "not the secret")
        ok, message = wrong.test()
        self.assertFalse(ok)
        self.assertIn("403", message)

    def test_webdav(self) -> None:
        _DAV.files = {}
        server = _serve(_DAV)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self._round_trip(backup.WebDAVTarget(
            f"http://127.0.0.1:{server.server_address[1]}/dav", "hse", "pw"))

    def test_make_target_reads_secrets_from_the_vault_side(self) -> None:
        target = backup.make_target({"kind": "s3", "endpoint": "s3.example.org",
                                     "bucket": "b", "access_key": "A"}, {"s3_secret": "S"})
        self.assertEqual(target.endpoint, "https://s3.example.org")
        with self.assertRaises(backup.BackupError):
            backup.make_target({"kind": "s3"}, {})
        with self.assertRaises(backup.BackupError):
            backup.make_target({"kind": "folder"}, {})


if __name__ == "__main__":
    unittest.main()
