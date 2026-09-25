"""The local SQL database: every analysed report, decision, action item and
audit entry, kept past the end of a session and shareable between machines.

The console holds its analysed corpus in memory; this is where it is kept.
SQLite on the workstation by default (``sentra.db`` beside the other
records), or any SQLAlchemy URL - a PostgreSQL or MySQL server several
workstations share - when the site has one and its driver is installed.

Sync is keyed on content, not on row numbers: a report by its fingerprint
(reference plus normalised narrative, :func:`sif.review.fingerprint`), a
decision by its fingerprint and time, an action item by its id, an audit
entry by its hash. So pushing twice changes nothing, two workstations
pushing the same report store it once, and pulling brings back only what
this machine does not already have.
"""

from __future__ import annotations

import json
import logging
import os
import socket
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from . import prefs

__all__ = ["DB_FILE", "DataStore", "default_url", "describe_url"]

LOGGER = logging.getLogger("sif.datastore")

DB_FILE = "sentra.db"


def default_url() -> str:
    """SQLite beside the accounts and the audit trail, in the per-user folder."""
    path = os.path.join(prefs.config_directory(), DB_FILE)
    return "sqlite:///" + os.path.abspath(path).replace("\\", "/")


def describe_url(url: str) -> str:
    """The URL without its password, for a screen or a log line."""
    from sqlalchemy.engine import make_url

    try:
        parsed = make_url(url)
    except Exception:  # noqa: BLE001
        return url
    if parsed.drivername.startswith("sqlite"):
        return f"SQLite · {parsed.database}"
    return parsed.render_as_string(hide_password=True)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


class DataStore:
    """Reports, decisions, action items, audit entries, vectors and the sync log."""

    def __init__(self, url: str = "") -> None:
        from sqlalchemy import (Boolean, Column, Float, Integer, LargeBinary, MetaData,
                                String, Table, Text, create_engine)

        self.url = url or default_url()
        if self.url.startswith("sqlite:///"):
            folder = os.path.dirname(self.url[len("sqlite:///"):])
            if folder:
                os.makedirs(folder, exist_ok=True)
        self.engine = create_engine(self.url, future=True)
        metadata = MetaData()
        self.reports = Table(
            "reports", metadata,
            Column("fingerprint", String(64), primary_key=True),
            Column("reference", String(120), index=True),
            Column("reported_on", String(32)),
            Column("site", String(200)),
            Column("risk_score", Float),
            Column("sif_potential", Boolean),
            Column("analysed_at", String(32)),
            Column("analysed_by", String(200)),
            Column("origin", String(120)),
            Column("updated_at", String(32)),
            Column("payload", Text))
        self.decisions = Table(
            "decisions", metadata,
            Column("key", String(120), primary_key=True),
            Column("fingerprint", String(64), index=True),
            Column("reference", String(120)),
            Column("decision", String(20)),
            Column("reviewer", String(200)),
            Column("decided_at", String(32)),
            Column("payload", Text))
        self.actions = Table(
            "actions", metadata,
            Column("id", String(40), primary_key=True),
            Column("title", String(300)),
            Column("updated_at", String(32)),
            Column("payload", Text))
        self.audit = Table(
            "audit", metadata,
            Column("key", String(80), primary_key=True),
            Column("at", String(32), index=True),
            Column("action", String(120)),
            Column("user", String(120)),
            Column("payload", Text))
        self.vectors = Table(
            "vectors", metadata,
            Column("fingerprint", String(64), primary_key=True),
            Column("encoder", String(160), primary_key=True),
            Column("reference", String(120)),
            Column("dim", Integer),
            Column("vector", LargeBinary),
            Column("updated_at", String(32)))
        #: Asset Safety Memory, as last computed: one row per asset.
        self.asset_memory = Table(
            "asset_memory", metadata,
            Column("asset", String(200), primary_key=True),
            Column("reports", Integer),
            Column("precursors", Integer),
            Column("signals", Integer),
            Column("updated_at", String(32)),
            Column("payload", Text))
        #: Work-hold recommendations, one row per report.
        self.work_holds = Table(
            "work_holds", metadata,
            Column("reference", String(120), primary_key=True),
            Column("asset", String(200), index=True),
            Column("level", String(20), index=True),
            Column("score", Integer),
            Column("updated_at", String(32)),
            Column("payload", Text))
        self.sync_log = Table(
            "sync_log", metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("at", String(32)),
            Column("kind", String(40)),
            Column("target", String(300)),
            Column("ok", Boolean),
            Column("detail", Text))
        metadata.create_all(self.engine)

    # -- writing ---------------------------------------------------------------------

    def _merge(self, connection, table, key_columns: Sequence[str],
               rows: Sequence[Dict[str, object]]) -> Tuple[int, int]:
        """Insert rows that are new, update rows whose payload changed."""
        from sqlalchemy import and_, select

        inserted = updated = 0
        for row in rows:
            condition = and_(*(table.c[name] == row[name] for name in key_columns))
            existing = connection.execute(select(table.c.payload).where(condition)).first()
            if existing is None:
                connection.execute(table.insert().values(**row))
                inserted += 1
            elif existing[0] != row.get("payload"):
                connection.execute(table.update().where(condition).values(**row))
                updated += 1
        return inserted, updated

    def push(self, reports: Iterable[Tuple[str, Dict[str, object]]] = (),
             decisions: Iterable[Dict[str, object]] = (),
             actions: Iterable[Dict[str, object]] = (),
             audit: Iterable[Dict[str, object]] = (),
             assets: Iterable[Dict[str, object]] = (),
             holds: Iterable[Dict[str, object]] = ()) -> Dict[str, Tuple[int, int]]:
        """Write what the console holds; returns (inserted, updated) per table."""
        origin = socket.gethostname()
        stamp = _now()
        report_rows = [{
            "fingerprint": fingerprint, "reference": str(row.get("reference", "")),
            "reported_on": str(row.get("reported_on") or ""), "site": str(row.get("site") or
                                                                           row.get("location") or ""),
            "risk_score": float(row.get("risk_score") or 0.0),
            "sif_potential": bool(row.get("sif_potential")),
            "analysed_at": str(row.get("analysed_at") or ""),
            "analysed_by": str(row.get("analysed_by") or ""), "origin": origin,
            "updated_at": stamp,
            "payload": _dump({k: v for k, v in row.items() if not str(k).startswith("_")}),
        } for fingerprint, row in reports]
        decision_rows = [{
            "key": f"{entry.get('fingerprint')}@{entry.get('decided_at')}",
            "fingerprint": str(entry.get("fingerprint", "")),
            "reference": str(entry.get("reference", "")),
            "decision": str(entry.get("decision", "")),
            "reviewer": str(entry.get("reviewer", "")),
            "decided_at": str(entry.get("decided_at", "")), "payload": _dump(entry),
        } for entry in decisions]
        action_rows = [{"id": str(item.get("id")), "title": str(item.get("title", ""))[:300],
                        "updated_at": stamp, "payload": _dump(item)} for item in actions]
        audit_rows = [{
            "key": str(entry.get("hash") or f"{entry.get('at')}|{entry.get('action')}|"
                                                f"{entry.get('user')}")[:80],
            "at": str(entry.get("at", "")), "action": str(entry.get("action", "")),
            "user": str(entry.get("user", "")),
            "payload": _dump({k: v for k, v in entry.items() if k not in ("summary", "when")}),
        } for entry in audit]
        asset_rows = [{
            "asset": str(item.get("asset", ""))[:200], "reports": int(item.get("reports") or 0),
            "precursors": int(item.get("precursors") or 0),
            "signals": int(item.get("signals") or 0), "updated_at": stamp,
            "payload": _dump(item)} for item in assets if item.get("asset")]
        hold_rows = [{
            "reference": str(item.get("reference", "")), "asset": str(item.get("asset", ""))[:200],
            "level": str(item.get("level", "")), "score": int(item.get("score") or 0),
            "updated_at": stamp, "payload": _dump(item)} for item in holds
            if item.get("reference")]
        with self.engine.begin() as connection:
            counts = {
                "reports": self._merge(connection, self.reports, ("fingerprint",), report_rows),
                "decisions": self._merge(connection, self.decisions, ("key",), decision_rows),
                "actions": self._merge(connection, self.actions, ("id",), action_rows),
                "audit": self._merge(connection, self.audit, ("key",), audit_rows),
                "asset_memory": self._merge(connection, self.asset_memory, ("asset",),
                                            asset_rows),
                "work_holds": self._merge(connection, self.work_holds, ("reference",),
                                          hold_rows),
            }
        return counts

    def holds(self, level: str = "") -> List[Dict[str, object]]:
        """Stored work-hold recommendations, highest score first."""
        from sqlalchemy import select

        query = select(self.work_holds.c.payload).order_by(self.work_holds.c.score.desc())
        if level:
            query = query.where(self.work_holds.c.level == level)
        with self.engine.connect() as connection:
            return [json.loads(row[0]) for row in connection.execute(query)]

    def assets(self) -> List[Dict[str, object]]:
        from sqlalchemy import select

        with self.engine.connect() as connection:
            return [json.loads(row[0]) for row in connection.execute(
                select(self.asset_memory.c.payload).order_by(
                    self.asset_memory.c.signals.desc(), self.asset_memory.c.asset))]

    def remove_action(self, action_id: str) -> None:
        """An action item deleted on purpose goes from the shared database too."""
        with self.engine.begin() as connection:
            connection.execute(self.actions.delete().where(self.actions.c.id == action_id))

    def remove_decision(self, fingerprint: str, decided_at: str) -> None:
        """A withdrawn decision (the misclick undo) is withdrawn everywhere."""
        with self.engine.begin() as connection:
            connection.execute(self.decisions.delete().where(
                self.decisions.c.key == f"{fingerprint}@{decided_at}"))

    # -- reading ---------------------------------------------------------------------

    def pull_reports(self, known: Set[str]) -> List[Tuple[str, Dict[str, object]]]:
        """Reports this machine does not hold yet, as (fingerprint, analysed row)."""
        from sqlalchemy import select

        found = []
        with self.engine.connect() as connection:
            for fingerprint, payload in connection.execute(
                    select(self.reports.c.fingerprint, self.reports.c.payload)
                    .order_by(self.reports.c.reported_on, self.reports.c.analysed_at)):
                if fingerprint not in known:
                    try:
                        found.append((fingerprint, json.loads(payload)))
                    except (TypeError, ValueError):
                        LOGGER.warning("Unreadable report %s in the database", fingerprint)
        return found

    def pull_decisions(self, known_keys: Set[str]) -> List[Dict[str, object]]:
        from sqlalchemy import select

        found = []
        with self.engine.connect() as connection:
            for key, payload in connection.execute(
                    select(self.decisions.c.key, self.decisions.c.payload)
                    .order_by(self.decisions.c.decided_at)):
                if key not in known_keys:
                    found.append(json.loads(payload))
        return found

    def pull_actions(self, known_ids: Set[str]) -> List[Dict[str, object]]:
        from sqlalchemy import select

        with self.engine.connect() as connection:
            return [json.loads(payload) for key, payload in connection.execute(
                select(self.actions.c.id, self.actions.c.payload)) if key not in known_ids]

    def report(self, fingerprint: str) -> Optional[Dict[str, object]]:
        from sqlalchemy import select

        with self.engine.connect() as connection:
            row = connection.execute(select(self.reports.c.payload).where(
                self.reports.c.fingerprint == fingerprint)).first()
        return json.loads(row[0]) if row else None

    # -- whole-database export, for a backup archive ------------------------------------

    TABLES = ("reports", "decisions", "actions", "audit", "vectors", "asset_memory",
              "work_holds")

    def export(self) -> Dict[str, List[Dict[str, object]]]:
        """Every row of every table, as JSON-ready dicts (vectors base64-encoded)."""
        import base64

        from sqlalchemy import select

        data: Dict[str, List[Dict[str, object]]] = {}
        with self.engine.connect() as connection:
            for name in self.TABLES:
                rows = [dict(row) for row in connection.execute(
                    select(getattr(self, name))).mappings()]
                if name == "vectors":
                    for row in rows:
                        row["vector"] = base64.b64encode(row["vector"] or b"").decode("ascii")
                data[name] = rows
        return data

    def import_(self, data: Dict[str, List[Dict[str, object]]]) -> Dict[str, Tuple[int, int]]:
        """Merge an export back in: new rows added, changed rows updated, none deleted."""
        import base64

        from sqlalchemy import and_, select

        keys = {"reports": ("fingerprint",), "decisions": ("key",), "actions": ("id",),
                "audit": ("key",), "asset_memory": ("asset",), "work_holds": ("reference",)}
        counts: Dict[str, Tuple[int, int]] = {}
        with self.engine.begin() as connection:
            for name, key_columns in keys.items():
                table = getattr(self, name)
                columns = set(table.c.keys())
                rows = [{k: v for k, v in row.items() if k in columns}
                        for row in data.get(name, [])]
                counts[name] = self._merge(connection, table, key_columns, rows)
            added = 0
            table = self.vectors
            for row in data.get("vectors", []):
                condition = and_(table.c.fingerprint == row["fingerprint"],
                                 table.c.encoder == row["encoder"])
                if connection.execute(select(table.c.dim).where(condition)).first() is None:
                    connection.execute(table.insert().values(
                        **{**{k: v for k, v in row.items() if k in table.c.keys()},
                           "vector": base64.b64decode(row.get("vector") or "")}))
                    added += 1
            counts["vectors"] = (added, 0)
        return counts

    def counts(self) -> Dict[str, int]:
        from sqlalchemy import func, select

        with self.engine.connect() as connection:
            return {name: int(connection.execute(select(func.count()).select_from(table)).scalar()
                              or 0)
                    for name, table in (("reports", self.reports), ("decisions", self.decisions),
                                        ("actions", self.actions), ("audit", self.audit),
                                        ("vectors", self.vectors),
                                        ("asset_memory", self.asset_memory),
                                        ("work_holds", self.work_holds))}

    def describe(self) -> str:
        return describe_url(self.url)

    def test(self) -> Tuple[bool, str]:
        """Can this database be written to right now?"""
        try:
            counts = self.counts()
            self.log("test", self.describe(), True, "connection checked")
            return True, f"Connected · {counts['reports']} report(s) stored"
        except Exception as exc:  # noqa: BLE001 - shown to the administrator
            return False, f"{type(exc).__name__}: {exc}"

    # -- the sync log ---------------------------------------------------------------------

    def log(self, kind: str, target: str, ok: bool, detail: str = "") -> None:
        with self.engine.begin() as connection:
            connection.execute(self.sync_log.insert().values(
                at=_now(), kind=kind, target=target[:300], ok=ok, detail=detail[:2000]))

    def history(self, limit: int = 50) -> List[Dict[str, object]]:
        from sqlalchemy import select

        with self.engine.connect() as connection:
            rows = connection.execute(select(self.sync_log).order_by(
                self.sync_log.c.id.desc()).limit(limit)).mappings().all()
        return [dict(row) for row in rows]

    def last(self, kind: str) -> Optional[Dict[str, object]]:
        from sqlalchemy import select

        with self.engine.connect() as connection:
            row = connection.execute(select(self.sync_log).where(
                self.sync_log.c.kind == kind, self.sync_log.c.ok.is_(True)).order_by(
                self.sync_log.c.id.desc()).limit(1)).mappings().first()
        return dict(row) if row else None

    def dispose(self) -> None:
        self.engine.dispose()
