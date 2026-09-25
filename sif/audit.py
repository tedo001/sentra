"""The audit trail - what the console did, and who asked for it.

This is not the debug log. :mod:`sif.logging_setup` writes diagnostics: it is
verbose, it carries third-party chatter, and it rotates away after a few
megabytes, which is exactly right for finding out why something failed this
morning and exactly wrong for answering "who cleared that report, and when?"
six months later.

So the audit trail is separate, and deliberately dull:

* **Append-only, one JSON object per line.** A line is written and never
  rewritten, so a corrupt or truncated tail costs at most the last entry rather
  than the file. Nothing here rotates on its own.
* **Two kinds of entry.** ``system`` records what the software did on this
  machine - started, loaded a model, fetched OCR models, checked for an update.
  ``functionality`` records what the console was *asked* to do and what came
  back - reports analysed, documents read, a model trained, a decision recorded,
  something exported. An auditor reads the second kind; support reads the first.
* **Every entry names its actor.** The signed-in account and its role, plus
  the operating-system user underneath it. A trail that cannot say who did
  something is not a trail.
* **Every entry is chained to the one before it.** Each carries the SHA-256 of
  its predecessor and of itself, so an edited, inserted or deleted line breaks
  the chain at that point and :meth:`AuditLog.verify` says where. Removing lines
  from the *end* leaves a shorter chain that is still consistent, which is why
  the head hash is shown on screen: an auditor who notes it can tell later
  whether anything has been taken off since.
* **Never fatal.** An unwritable location degrades to in-memory only and says so
  once; recording an event must not be able to interrupt the work being audited.

The file lives beside the settings, so it follows the operator's profile rather
than the installation directory: ``%APPDATA%\\SIF Insight Console\\audit.jsonl``
on Windows, ``~/.config/SIF Insight Console/audit.jsonl`` elsewhere.
"""

from __future__ import annotations

import csv
import getpass
import hashlib
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence

from . import prefs

__all__ = ["AuditEntry", "AuditLog", "ChainReport", "SYSTEM", "FUNCTIONALITY",
           "CATEGORIES", "audit_file_path"]

LOGGER = logging.getLogger(__name__)

#: What the software did by itself.
SYSTEM = "system"
#: What an operator asked for, and what came back.
FUNCTIONALITY = "functionality"
CATEGORIES = (SYSTEM, FUNCTIONALITY)

FILE_NAME = "audit.jsonl"
#: Read back at most this many entries for the interface; the file keeps them all.
DEFAULT_LIMIT = 500


def audit_file_path() -> str:
    """Where the trail is written for this operator."""
    return os.path.join(prefs.config_directory(), FILE_NAME)


def _actor() -> str:
    """The operating-system user, as far as it can be determined."""
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - no controlling terminal, odd container
        return os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"


@dataclass
class AuditEntry:
    """One line of the trail."""

    at: str
    category: str
    action: str
    actor: str = ""
    reviewer: str = ""
    version: str = ""
    detail: Dict[str, object] = field(default_factory=dict)
    #: The signed-in account and its role. Empty on entries written before
    #: sign-in existed, and on the unattended session scripts run under.
    user: str = ""
    role: str = ""
    #: The chain: the previous entry's hash, and this entry's own.
    prev: str = ""
    hash: str = ""

    def to_dict(self) -> Dict[str, object]:
        payload = {"at": self.at, "category": self.category, "action": self.action,
                   "actor": self.actor, "user": self.user, "role": self.role,
                   "reviewer": self.reviewer, "version": self.version,
                   "detail": dict(self.detail)}
        if self.hash:
            payload["prev"] = self.prev
            payload["hash"] = self.hash
        return payload

    def digest(self) -> str:
        """SHA-256 over everything but the hash itself, in a fixed form."""
        payload = self.to_dict()
        payload.pop("hash", None)
        payload["prev"] = self.prev
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                               separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "AuditEntry":
        detail = payload.get("detail")
        return cls(
            at=str(payload.get("at", "")),
            category=str(payload.get("category", SYSTEM)),
            action=str(payload.get("action", "")),
            actor=str(payload.get("actor", "")),
            reviewer=str(payload.get("reviewer", "")),
            version=str(payload.get("version", "")),
            detail=dict(detail) if isinstance(detail, dict) else {},
            user=str(payload.get("user", "")),
            role=str(payload.get("role", "")),
            prev=str(payload.get("prev", "")),
            hash=str(payload.get("hash", "")),
        )

    @property
    def summary(self) -> str:
        """The detail as one readable line, for the table."""
        return "  ·  ".join(f"{key}: {value}" for key, value in self.detail.items())


@dataclass(frozen=True)
class ChainReport:
    """What :meth:`AuditLog.verify` found."""

    intact: bool
    entries: int
    chained: int
    head: str = ""
    broken_at: int = 0          # 1-based line number of the first bad entry
    reason: str = ""

    @property
    def summary(self) -> str:
        if not self.entries:
            return "The trail is empty."
        if not self.intact:
            return f"Chain BROKEN at entry {self.broken_at}: {self.reason}"
        legacy = self.entries - self.chained
        return (f"Chain intact - {self.chained} entr(ies) verified"
                + (f", {legacy} older unchained" if legacy else "")
                + (f" - head {self.head[:12]}" if self.head else ""))


class AuditLog:
    """Append-only record of everything worth answering for later."""

    def __init__(self, path: str = "", version: str = "") -> None:
        self.path = path or audit_file_path()
        self.version = version
        self.reviewer = ""
        #: The signed-in account, stamped on every entry from here on.
        self.user = ""
        self.role = ""
        #: The hash of the last entry written, read from the file on first use.
        self._head: Optional[str] = None
        self._lock = threading.Lock()
        self._memory: List[AuditEntry] = []
        #: False once a write has failed, so the interface can say the trail is
        #: only in memory rather than letting anyone believe it reached disk.
        self.writable = True

    # -- recording ---------------------------------------------------------

    def record(self, category: str, action: str, **detail: object) -> AuditEntry:
        """Append one entry. Never raises - auditing must not break the work."""
        entry = AuditEntry(
            at=datetime.now().isoformat(timespec="seconds"),
            category=category if category in CATEGORIES else SYSTEM,
            action=action,
            actor=_actor(),
            reviewer=self.reviewer,
            version=self.version,
            detail={key: value for key, value in detail.items() if value is not None},
            user=self.user,
            role=self.role,
        )
        with self._lock:
            # Re-read the tail before every write while the file is reachable:
            # the sign-in page and the console window each hold an AuditLog on
            # the same file, and a cached head would fork the chain the moment
            # the other one had written.
            if self.writable or self._head is None:
                self._head = self._tail_hash()
            entry.prev = self._head
            entry.hash = entry.digest()
            self._head = entry.hash
            self._memory.append(entry)
            self._append(entry)
        return entry

    def sign_in(self, user: str, role: str) -> None:
        """Attribute everything recorded from now on to this account."""
        self.user, self.role = user, role

    def sign_out(self) -> None:
        self.user, self.role = "", ""

    @property
    def head(self) -> str:
        """The hash of the newest entry - what an auditor notes down."""
        with self._lock:
            if self._head is None:
                self._head = self._tail_hash()
            return self._head

    def _tail_hash(self) -> str:
        """The hash on the last line of the file, or "" to start a chain.

        Read from the end, so the cost does not grow with the trail: only the
        last block is read, and the whole file only if one line outgrew it.
        """
        try:
            with open(self.path, "rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                block = min(size, 65536)
                handle.seek(size - block)
                tail = handle.read()
                if block < size and b"\n" not in tail.rstrip(b"\n"):
                    handle.seek(0)
                    tail = handle.read()
        except Exception:  # noqa: BLE001 - no file, no permission, a bad path:
            return ""      # start a new chain rather than fail the work being audited
        lines = [line for line in tail.splitlines() if line.strip()]
        if not lines:
            return ""
        try:
            return str(json.loads(lines[-1].decode("utf-8")).get("hash", ""))
        except Exception:  # noqa: BLE001 - a torn last line starts a new link
            return ""

    def verify(self) -> ChainReport:
        """Walk the file and check every link.

        Entries written before chaining existed carry no hash and are counted
        but not checked. Once the first hashed entry appears, every entry after
        it must be hashed and must name its predecessor - an unhashed line in
        the middle of the chain is an insertion, and is reported as one.
        """
        entries = chained = 0
        previous = ""
        started = False
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                lines = [line for line in handle if line.strip()]
        except FileNotFoundError:
            return ChainReport(True, 0, 0)
        except Exception as exc:  # noqa: BLE001
            return ChainReport(False, 0, 0, reason=f"the trail could not be read: {exc}")
        for number, line in enumerate(lines, start=1):
            entries += 1
            try:
                payload = json.loads(line)
                entry = AuditEntry.from_dict(payload)
            except Exception:  # noqa: BLE001
                if started:
                    return ChainReport(False, entries, chained, previous, number,
                                       "the line is not a readable entry")
                continue
            if not entry.hash:
                if started:
                    return ChainReport(False, entries, chained, previous, number,
                                       "an unchained entry inside the chain")
                continue
            if started and entry.prev != previous:
                return ChainReport(False, entries, chained, previous, number,
                                   "it does not follow the entry before it")
            if entry.digest() != entry.hash:
                return ChainReport(False, entries, chained, previous, number,
                                   "its content no longer matches its hash")
            started = True
            chained += 1
            previous = entry.hash
        return ChainReport(True, entries, chained, previous)

    def system(self, action: str, **detail: object) -> AuditEntry:
        """Record something the software did on this machine."""
        return self.record(SYSTEM, action, **detail)

    def functionality(self, action: str, **detail: object) -> AuditEntry:
        """Record something an operator asked for, and what came back."""
        return self.record(FUNCTIONALITY, action, **detail)

    def _append(self, entry: AuditEntry) -> None:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())     # a crash must not lose the last entry
            self.writable = True
        except Exception as exc:  # noqa: BLE001 - a read-only profile is not fatal
            if self.writable:                 # complain once, not once per event
                LOGGER.warning("Audit trail is memory-only (%s): %s", self.path, exc)
            self.writable = False

    # -- reading -----------------------------------------------------------

    def entries(self, category: str = "", limit: int = DEFAULT_LIMIT) -> List[AuditEntry]:
        """The most recent entries, newest first, optionally by category."""
        rows = self._read()
        if category in CATEGORIES:
            rows = [entry for entry in rows if entry.category == category]
        rows.reverse()
        return rows[:limit] if limit else rows

    def rows(self, category: str = "", limit: int = DEFAULT_LIMIT) -> List[Dict[str, object]]:
        """The same, as table payloads.

        ``when`` is the same instant as ``at``, with the ISO ``T`` replaced by a
        space so it reads like the log beside it. ``at`` stays machine-readable.
        """
        return [{**entry.to_dict(), "summary": entry.summary,
                 "when": entry.at.replace("T", " ")}
                for entry in self.entries(category, limit)]

    def _read(self) -> List[AuditEntry]:
        """Everything on disk, plus anything that never reached it."""
        found: List[AuditEntry] = []
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        found.append(AuditEntry.from_dict(json.loads(line)))
                    except Exception:  # noqa: BLE001 - one bad line, not the file
                        continue
        except FileNotFoundError:
            pass
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Could not read the audit trail (%s)", exc)
        if not self.writable:
            found.extend(self._memory)
        return found

    def counts(self) -> Dict[str, int]:
        """How much of each kind the trail holds."""
        rows = self._read()
        return {
            "total": len(rows),
            SYSTEM: sum(1 for entry in rows if entry.category == SYSTEM),
            FUNCTIONALITY: sum(1 for entry in rows if entry.category == FUNCTIONALITY),
        }

    def export_csv(self, path: str, category: str = "") -> str:
        """Write the trail out for an auditor; returns the path."""
        columns = ["at", "category", "action", "user", "role", "actor", "reviewer",
                   "version", "summary", "hash"]
        entries = self.entries(category, limit=0)
        entries.reverse()                      # oldest first reads as a history
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for entry in entries:
                payload = entry.to_dict()
                payload["summary"] = entry.summary
                writer.writerow({key: payload.get(key, "") for key in columns})
        LOGGER.info("Exported %d audit entr(ies) to %s", len(entries), path)
        return path


def summarise(entries: Sequence[AuditEntry]) -> Dict[str, int]:
    """Count entries by action - what this machine actually spends its time on."""
    tally: Dict[str, int] = {}
    for entry in entries:
        tally[entry.action] = tally.get(entry.action, 0) + 1
    return dict(sorted(tally.items(), key=lambda item: item[1], reverse=True))


_ACTIVE: Optional[AuditLog] = None


def active(version: str = "") -> AuditLog:
    """The process-wide trail, created on first use."""
    global _ACTIVE
    if _ACTIVE is None:
        _ACTIVE = AuditLog(version=version)
    return _ACTIVE
