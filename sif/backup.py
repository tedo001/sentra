"""Backups: one encrypted archive of everything the console keeps, sent off-site.

What goes in
    The SQL database's contents (reports, decisions, action items, audit
    mirror, vectors) as portable JSON, so a backup taken from SQLite restores
    into PostgreSQL and back; and the files beside it - the accounts, the
    hash-chained audit trail, the review decisions, the compliance calendar,
    the preferences and the trained model. A ``manifest.json`` lists every
    member with its SHA-256.

How it is sealed
    The zip is encrypted with Fernet (AES-128-CBC + HMAC-SHA256) under a key
    derived from the administrator's passphrase with PBKDF2-SHA256. Without
    the passphrase the archive is noise, so a cloud provider holds only
    ciphertext. Lose the passphrase and the backup is lost with it - the
    Data & Backup page says so where the passphrase is set.

Where it goes (a *target*)
    * a folder - a network share, or a OneDrive / Google Drive / Dropbox
      folder the desktop client syncs to the cloud;
    * S3-compatible object storage - AWS S3, MinIO, Cloudflare R2, Wasabi,
      Backblaze B2 - signed with AWS Signature V4, written out here so no SDK
      is needed;
    * WebDAV - Nextcloud, ownCloud, most NAS boxes.

Restore never deletes: the database contents are merged back by content key
(see :mod:`sif.datastore`), and the files are unpacked into a dated folder for
an administrator to put in place, so a mistaken restore costs nothing.
"""

from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import hmac
import io
import json
import os
import socket
import zipfile
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote, unquote, urlencode, urlsplit
from xml.etree import ElementTree

from .version import __version__

__all__ = ["MAGIC", "BackupError", "BackupInfo", "build_archive", "seal", "unseal",
           "read_archive", "archive_name", "sign_v4", "FolderTarget", "S3Target",
           "WebDAVTarget", "make_target", "TARGET_KINDS", "SCHEDULES", "due", "unpack"]

MAGIC = b"SENTRA-BACKUP-1\n"
SUFFIX = ".sentra"
ITERATIONS = 390_000
TIMEOUT = 30

TARGET_KINDS = (("folder", "Folder / synced drive"), ("s3", "S3-compatible storage"),
                ("webdav", "WebDAV (Nextcloud, NAS)"))
SCHEDULES = (("off", "Off"), ("daily", "Every day"), ("weekly", "Every week"))


class BackupError(RuntimeError):
    """A backup could not be written, read, sent or fetched - with the reason."""


# -- the archive ---------------------------------------------------------------------


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_name(when: Optional[_dt.datetime] = None, host: str = "") -> str:
    when = when or _dt.datetime.now()
    host = "".join(ch if ch.isalnum() or ch in "-_" else "-"
                   for ch in (host or socket.gethostname()))[:40] or "host"
    return f"SENTRA-{host}-{when.strftime('%Y%m%d-%H%M%S')}{SUFFIX}"


def build_archive(database: Dict[str, List[Dict[str, object]]],
                  files: Sequence[Tuple[str, str]]) -> Tuple[bytes, Dict[str, object]]:
    """A zip of the database export and ``files`` [(name in archive, path)] + manifest."""
    members: Dict[str, bytes] = {
        "database.json": json.dumps(database, ensure_ascii=False, default=str).encode("utf-8")}
    for name, path in files:
        if path and os.path.isfile(path):
            with open(path, "rb") as handle:
                members[name] = handle.read()
        elif path and os.path.isdir(path):
            for root, _dirs, names in os.walk(path):
                for item in names:
                    full = os.path.join(root, item)
                    relative = os.path.relpath(full, path).replace(os.sep, "/")
                    with open(full, "rb") as handle:
                        members[f"{name}/{relative}"] = handle.read()
    manifest = {
        "format": 1, "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "host": socket.gethostname(), "version": __version__,
        "counts": {table: len(rows) for table, rows in database.items()},
        "files": {name: {"sha256": _sha256(data), "bytes": len(data)}
                  for name, data in sorted(members.items())},
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue(), manifest


def _key(passphrase: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def seal(data: bytes, passphrase: str) -> bytes:
    from cryptography.fernet import Fernet

    if not passphrase:
        raise BackupError("A backup passphrase is required - archives are never "
                          "written unencrypted.")
    salt = os.urandom(16)
    return MAGIC + salt + Fernet(_key(passphrase, salt)).encrypt(data)


def unseal(blob: bytes, passphrase: str) -> bytes:
    from cryptography.fernet import Fernet, InvalidToken

    if not blob.startswith(MAGIC):
        raise BackupError("This is not a SENTRA backup archive.")
    salt = blob[len(MAGIC):len(MAGIC) + 16]
    try:
        return Fernet(_key(passphrase, salt)).decrypt(blob[len(MAGIC) + 16:])
    except InvalidToken:
        raise BackupError("Wrong passphrase, or the archive was damaged in transit.") from None


def read_archive(blob: bytes, passphrase: str) -> Tuple[Dict[str, object], Dict[str, bytes]]:
    """Open and check an archive: (manifest, members). Any mismatch is an error."""
    data = unseal(blob, passphrase)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            members = {name: archive.read(name) for name in archive.namelist()
                       if name != "manifest.json"}
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise BackupError(f"The archive is unreadable ({exc}).") from None
    for name, entry in manifest.get("files", {}).items():
        if name not in members:
            raise BackupError(f"{name} is listed in the manifest but missing.")
        if _sha256(members[name]) != entry.get("sha256"):
            raise BackupError(f"{name} does not match its checksum.")
    return manifest, members


@dataclass
class BackupInfo:
    name: str
    size: int = 0
    modified: str = ""
    extra: Dict[str, str] = field(default_factory=dict)


# -- AWS Signature Version 4 ------------------------------------------------------------

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def _hmac(key: bytes, text: str) -> bytes:
    return hmac.new(key, text.encode("utf-8"), hashlib.sha256).digest()


def sign_v4(method: str, url: str, headers: Dict[str, str], payload_hash: str,
            access_key: str, secret_key: str, region: str, service: str,
            amz_date: str) -> str:
    """The ``Authorization`` header for a request. ``headers`` must hold host and x-amz-date."""
    parts = urlsplit(url)
    path = quote(parts.path or "/", safe="/~")
    pairs = []
    for item in parts.query.split("&") if parts.query else []:
        key, _, value = item.partition("=")
        pairs.append((quote(key, safe="-_.~"), quote(value, safe="-_.~")))
    canonical_query = "&".join(f"{k}={v}" for k, v in sorted(pairs))
    lowered = {name.lower().strip(): " ".join(str(value).strip().split())
               for name, value in headers.items()}
    signed = ";".join(sorted(lowered))
    canonical_headers = "".join(f"{name}:{lowered[name]}\n" for name in sorted(lowered))
    canonical = "\n".join((method.upper(), path, canonical_query, canonical_headers, signed,
                           payload_hash))
    day = amz_date[:8]
    scope = f"{day}/{region}/{service}/aws4_request"
    to_sign = "\n".join(("AWS4-HMAC-SHA256", amz_date, scope,
                         hashlib.sha256(canonical.encode("utf-8")).hexdigest()))
    key = _hmac(_hmac(_hmac(_hmac(f"AWS4{secret_key}".encode("utf-8"), day), region),
                      service), "aws4_request")
    signature = hmac.new(key, to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return (f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, SignedHeaders={signed}, "
            f"Signature={signature}")


# -- targets --------------------------------------------------------------------------


class Target:
    kind = ""

    def describe(self) -> str:
        raise NotImplementedError

    def upload(self, name: str, blob: bytes) -> None:
        raise NotImplementedError

    def list(self) -> List[BackupInfo]:
        raise NotImplementedError

    def download(self, name: str) -> bytes:
        raise NotImplementedError

    def delete(self, name: str) -> None:
        raise NotImplementedError

    def test(self) -> Tuple[bool, str]:
        """Write, list and delete a small probe: can a backup really land here?"""
        probe = f"SENTRA-probe-{socket.gethostname()}{SUFFIX}.probe"
        try:
            self.upload(probe, b"probe")
            count = len(self.list())
            self.delete(probe)
            return True, f"Writable · {count} backup(s) there"
        except Exception as exc:  # noqa: BLE001 - reported to the administrator
            return False, _reason(exc)

    def prune(self, keep: int) -> List[str]:
        """Delete all but the newest ``keep`` backups; returns what went."""
        if keep <= 0:
            return []
        backups = sorted(self.list(), key=lambda item: item.name, reverse=True)
        gone = []
        for item in backups[keep:]:
            self.delete(item.name)
            gone.append(item.name)
        return gone


def _reason(exc: Exception) -> str:
    text = str(exc) or type(exc).__name__
    return text if isinstance(exc, BackupError) else f"{type(exc).__name__}: {text}"


class FolderTarget(Target):
    kind = "folder"

    def __init__(self, path: str) -> None:
        if not path:
            raise BackupError("Choose a folder for the backups.")
        self.path = os.path.abspath(os.path.expanduser(path))

    def describe(self) -> str:
        return f"Folder · {self.path}"

    def upload(self, name: str, blob: bytes) -> None:
        os.makedirs(self.path, exist_ok=True)
        temporary = os.path.join(self.path, name + ".part")
        with open(temporary, "wb") as handle:
            handle.write(blob)
        os.replace(temporary, os.path.join(self.path, name))

    def list(self) -> List[BackupInfo]:
        if not os.path.isdir(self.path):
            return []
        found = []
        for name in os.listdir(self.path):
            full = os.path.join(self.path, name)
            if name.endswith(SUFFIX) and os.path.isfile(full):
                stat = os.stat(full)
                found.append(BackupInfo(name, stat.st_size, _dt.datetime.fromtimestamp(
                    stat.st_mtime).isoformat(timespec="seconds")))
        return sorted(found, key=lambda item: item.name, reverse=True)

    def download(self, name: str) -> bytes:
        with open(os.path.join(self.path, os.path.basename(name)), "rb") as handle:
            return handle.read()

    def delete(self, name: str) -> None:
        full = os.path.join(self.path, os.path.basename(name))
        if os.path.exists(full):
            os.remove(full)


class _HTTPTarget(Target):
    def _session(self):
        import requests

        return requests

    @staticmethod
    def _check(response, action: str) -> None:
        if response.status_code >= 300:
            detail = " ".join(response.text.split())[:200]
            raise BackupError(f"{action} refused: HTTP {response.status_code} {detail}".strip())


class S3Target(_HTTPTarget):
    """Any S3-compatible store, path-style addressing (bucket in the path)."""

    kind = "s3"

    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str,
                 region: str = "us-east-1", prefix: str = "sentra/",
                 clock: Callable[[], _dt.datetime] = None) -> None:
        if not (endpoint and bucket and access_key and secret_key):
            raise BackupError("S3 needs an endpoint, a bucket, an access key and a secret key.")
        endpoint = endpoint.strip().rstrip("/")
        if "://" not in endpoint:
            endpoint = "https://" + endpoint
        self.endpoint = endpoint
        self.bucket = bucket.strip()
        self.access_key = access_key.strip()
        self.secret_key = secret_key
        self.region = (region or "us-east-1").strip()
        self.prefix = (prefix or "").strip().lstrip("/")
        if self.prefix and not self.prefix.endswith("/"):
            self.prefix += "/"
        self.clock = clock or (lambda: _dt.datetime.now(_dt.timezone.utc))

    def describe(self) -> str:
        return f"S3 · {self.endpoint}/{self.bucket}/{self.prefix}"

    def _url(self, key: str = "", query: Optional[Dict[str, str]] = None) -> str:
        url = f"{self.endpoint}/{quote(self.bucket)}"
        if key:
            url += "/" + quote(key, safe="/~")
        if query:
            url += "?" + urlencode(sorted(query.items()), quote_via=quote)
        return url

    def _request(self, method: str, key: str = "", body: bytes = b"",
                 query: Optional[Dict[str, str]] = None):
        url = self._url(key, query)
        amz_date = self.clock().strftime("%Y%m%dT%H%M%SZ")
        payload_hash = hashlib.sha256(body).hexdigest()
        headers = {"host": urlsplit(url).netloc, "x-amz-date": amz_date,
                   "x-amz-content-sha256": payload_hash}
        headers["Authorization"] = sign_v4(method, url, headers, payload_hash,
                                           self.access_key, self.secret_key, self.region,
                                           "s3", amz_date)
        return self._session().request(method, url, data=body or None, headers=headers,
                                       timeout=TIMEOUT)

    def upload(self, name: str, blob: bytes) -> None:
        self._check(self._request("PUT", self.prefix + name, blob), "Upload")

    def list(self) -> List[BackupInfo]:
        response = self._request("GET", query={"list-type": "2", "prefix": self.prefix})
        self._check(response, "Listing")
        root = ElementTree.fromstring(response.content)
        namespace = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
        found = []
        for item in root.iter(f"{namespace}Contents"):
            key = item.findtext(f"{namespace}Key") or ""
            name = key[len(self.prefix):] if key.startswith(self.prefix) else key
            if name.endswith(SUFFIX) and "/" not in name:
                found.append(BackupInfo(name, int(item.findtext(f"{namespace}Size") or 0),
                                        (item.findtext(f"{namespace}LastModified") or "")[:19]))
        return sorted(found, key=lambda entry: entry.name, reverse=True)

    def download(self, name: str) -> bytes:
        response = self._request("GET", self.prefix + name)
        self._check(response, "Download")
        return response.content

    def delete(self, name: str) -> None:
        self._check(self._request("DELETE", self.prefix + name), "Delete")


class WebDAVTarget(_HTTPTarget):
    kind = "webdav"

    def __init__(self, url: str, username: str = "", password: str = "") -> None:
        if not url:
            raise BackupError("WebDAV needs the folder's URL.")
        self.url = url.strip().rstrip("/") + "/"
        self.auth = (username, password) if username else None

    def describe(self) -> str:
        return f"WebDAV · {self.url}"

    def _call(self, method: str, name: str = "", **kwargs):
        return self._session().request(method, self.url + quote(name), auth=self.auth,
                                       timeout=TIMEOUT, **kwargs)

    def upload(self, name: str, blob: bytes) -> None:
        response = self._call("PUT", name, data=blob)
        if response.status_code == 409:  # the folder is not there yet
            self._check(self._session().request("MKCOL", self.url, auth=self.auth,
                                                timeout=TIMEOUT), "Creating the folder")
            response = self._call("PUT", name, data=blob)
        self._check(response, "Upload")

    def list(self) -> List[BackupInfo]:
        response = self._call("PROPFIND", headers={"Depth": "1"})
        if response.status_code == 404:
            return []
        self._check(response, "Listing")
        root = ElementTree.fromstring(response.content)
        found = []
        for item in root.iter("{DAV:}response"):
            href = item.findtext("{DAV:}href") or ""
            name = unquote(os.path.basename(href.rstrip("/")))
            if not name.endswith(SUFFIX):
                continue
            size = item.findtext(".//{DAV:}getcontentlength") or "0"
            modified = item.findtext(".//{DAV:}getlastmodified") or ""
            found.append(BackupInfo(name, int(size), modified))
        return sorted(found, key=lambda entry: entry.name, reverse=True)

    def download(self, name: str) -> bytes:
        response = self._call("GET", name)
        self._check(response, "Download")
        return response.content

    def delete(self, name: str) -> None:
        response = self._call("DELETE", name)
        if response.status_code != 404:
            self._check(response, "Delete")


def make_target(config: Dict[str, str], secrets: Dict[str, str]) -> Target:
    """The target a saved configuration describes; secrets come from the vault."""
    kind = config.get("kind", "folder")
    if kind == "s3":
        return S3Target(config.get("endpoint", ""), config.get("bucket", ""),
                        config.get("access_key", ""), secrets.get("s3_secret", ""),
                        config.get("region", "") or "us-east-1", config.get("prefix", "sentra/"))
    if kind == "webdav":
        return WebDAVTarget(config.get("url", ""), config.get("username", ""),
                            secrets.get("webdav_password", ""))
    return FolderTarget(config.get("folder", ""))


def due(schedule: str, last: str, now: Optional[_dt.datetime] = None) -> bool:
    """Is a scheduled backup owed, given the last successful one (ISO time or '')?"""
    days = {"daily": 1, "weekly": 7}.get(schedule)
    if not days:
        return False
    if not last:
        return True
    try:
        then = _dt.datetime.fromisoformat(str(last)[:19])
    except ValueError:
        return True
    return (now or _dt.datetime.now()) - then >= _dt.timedelta(days=days)


def unpack(members: Dict[str, bytes], directory: str) -> str:
    """Write the archive's files (not the database) under ``directory``; returns it."""
    os.makedirs(directory, exist_ok=True)
    for name, data in members.items():
        if name == "database.json":
            continue
        target = os.path.abspath(os.path.join(directory, name))
        if not target.startswith(os.path.abspath(directory) + os.sep):
            continue  # a crafted archive does not write outside the folder
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(data)
    return directory
