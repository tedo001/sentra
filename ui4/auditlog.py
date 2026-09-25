"""Audit Log - what people did, and whether the record still holds.

From the design: the chain's state in a banner (intact, how many entries
since when, where it is kept); filters by user, role, action and period;
every human action with its object, the value it replaced and the value it
set, and its result; and the chosen entry in full, with its own hash and
the hash of the entry before it.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from .kit import Card, Col, DesignTable, KeyValues, Page

__all__ = ["AuditPage", "COLUMNS", "describe_entry"]

ROLE_WORDS = {"admin": "Administrator", "reviewer": "HSE Analyst", "analyst": "HSE Analyst",
              "viewer": "Viewer"}
DECISIONS = {"confirmed": "Confirmed SIF", "rejected": "Not SIF", "unclear": "Needs info"}
DENIED = ("sign-in refused", "permission refused", "account locked")

COLUMNS = (
    Col("when", "Timestamp", 186, "mono", value=lambda row: str(row.get("when", ""))[:19]),
    Col("user", "User", 132, "mono"),
    Col("role_label", "Role", 112),
    Col("title", "Action", 146, "strong"),
    Col("object", "Object", 0, "mono"),
    Col("previous", "Previous value", 132,
        style=lambda row: ("#8A8F95", False, row.get("previous") not in ("\u2014", ""))),
    Col("new", "New value", 150),
    Col("result", "Result", 100, "pill"),
)


def describe_entry(entry: Dict[str, object], workstation: str = "") -> Dict[str, object]:
    """An audit entry as the design's row: object, previous value, new value, result."""
    from .present import ACTION_WORDS

    action = str(entry.get("action", ""))
    detail = dict(entry.get("detail") or {})
    obj, previous, new = "—", "—", str(entry.get("summary", ""))
    if action == "reports analysed":
        obj = f"{detail.get('count', '?')} report(s)"
        new = f"{detail.get('count', '?')} analysed · {detail.get('awaiting_review', 0)} queued"
    elif action == "review decision":
        obj = str(detail.get("reference", ""))
        previous = "Awaiting review"
        new = DECISIONS.get(str(detail.get("decision")), str(detail.get("decision")))
    elif action == "decision withdrawn":
        obj = str(detail.get("reference", ""))
        previous = DECISIONS.get(str(detail.get("decision")), str(detail.get("decision")))
        new = "Awaiting review"
    elif action == "setting changed":
        obj = str(detail.get("setting", ""))
        previous, new = str(detail.get("previous", "—")), str(detail.get("new", ""))
    elif action == "role changed":
        obj = str(detail.get("username", ""))
        previous = ROLE_WORDS.get(str(detail.get("previous")), str(detail.get("previous") or "—"))
        new = ROLE_WORDS.get(str(detail.get("role")), str(detail.get("role")))
    elif action == "account created":
        obj = str(detail.get("username", ""))
        new = ROLE_WORDS.get(str(detail.get("role")), str(detail.get("role"))) + (
            f" · {detail['site']}" if detail.get("site") else "")
    elif action in ("account disabled", "account enabled"):
        obj = str(detail.get("username", ""))
        previous, new = (("Active", "Disabled") if action == "account disabled"
                         else ("Disabled", "Active"))
    elif action == "password reset":
        obj, new = str(detail.get("username", "")), "One-time password issued"
    elif action == "password changed":
        obj, new = str(detail.get("username", "")), "Password changed"
    elif action == "signed in":
        obj, new = workstation or "—", "Session opened"
    elif action == "signed out":
        obj, new = workstation or "—", "Session closed"
    elif action == "sign-in refused":
        obj = str(detail.get("attempted", ""))
        new = {"wrong password": "Wrong password", "unknown user": "Unknown user",
               "locked out": "Locked out", "locked": "Account locked",
               "disabled": "Account disabled"}.get(str(detail.get("reason")),
                                                   str(detail.get("reason", "")))
    elif action == "account locked":
        obj, new = str(detail.get("username", "")), "Locked for 5 minutes"
    elif action == "permission refused":
        obj, new = str(detail.get("attempted", "")), f"needs {detail.get('needs', '')}"
    elif action == "model trained":
        obj = f"run {str(detail.get('run_id', ''))[:6]}"
        new = str(detail.get("metrics", ""))[:40]
    elif action.startswith("compliance action"):
        obj = str(detail.get("title", ""))[:40]
        new = str(detail.get("date") or detail.get("start") or "")
    elif action in ("decision trail exported", "audit trail exported", "results exported",
                    "system log exported"):
        obj = "export"
        new = str(detail.get("path", "")).replace("\\", "/").split("/")[-1]
    elif action == "document read":
        obj = str(detail.get("name", ""))
        new = f"{detail.get('characters', '?')} characters"
    denied = action in DENIED
    return {**entry, "title": ACTION_WORDS.get(action, action.capitalize()),
            "role_label": ROLE_WORDS.get(str(entry.get("role")), str(entry.get("role") or "—")),
            "object": obj, "previous": previous, "new": new,
            "result": ("✕ Denied", "fail") if denied else ("✓ Success", "ok"),
            "user": entry.get("user") or "—"}


class AuditPage(Page):
    verify_requested = pyqtSignal()
    export_requested = pyqtSignal()
    filters_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__("Audit Log", "Human actions only · append-only · each entry "
                                      "carries the hash of the one before")
        verify = QPushButton("Verify chain")
        verify.clicked.connect(self.verify_requested.emit)
        export = QPushButton("Export CSV for auditor")
        export.clicked.connect(self.export_requested.emit)
        self.head.add(verify)
        self.head.add(export)

        self.banner = QLabel("")
        self.banner.setObjectName("ChainBanner")
        self.banner.setWordWrap(True)
        self.body.addWidget(self.banner)

        bar = QFrame()
        bar.setObjectName("Card")
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(8)
        self.user = QComboBox()
        self.role = QComboBox()
        self.action = QComboBox()
        self.period = QComboBox()
        for days, label in ((1, "Today"), (7, "Last 7 days"), (30, "Last 30 days"), (0, "All time")):
            self.period.addItem(label, days)
        self.period.setCurrentIndex(1)
        for box, width in ((self.user, 150), (self.role, 150), (self.action, 180),
                           (self.period, 140)):
            box.setFixedWidth(width)
            box.currentIndexChanged.connect(lambda _i: self.filters_changed.emit())
            row.addWidget(box)
        row.addStretch(1)
        self.count = QLabel("")
        self.count.setObjectName("MonoFaint")
        row.addWidget(self.count)
        self.body.addWidget(bar)

        self.table_card = Card(flush=True)
        self.table = DesignTable(COLUMNS, row_height=42, wrap=True)
        self.table.row_clicked.connect(self._pick)
        self.table_card.add(self.table, 1)

        self.entry = Card("Entry", "")
        self.number = QLabel("")
        self.number.setObjectName("MonoFaint")
        self.entry.add_head(self.number)
        self.entry.setFixedWidth(336)
        self.facts = KeyValues(1, label_width=86)
        self.entry.add(self.facts)
        boxes = QHBoxLayout()
        boxes.setSpacing(6)
        self.before = QLabel("")
        self.before.setObjectName("ValueBox")
        self.after = QLabel("")
        self.after.setObjectName("ValueBoxNew")
        for box in (self.before, self.after):
            box.setWordWrap(True)
            boxes.addWidget(box, 1)
        self.entry.body.addLayout(boxes)
        self.chain = KeyValues(1, label_width=96)
        self.entry.add(self.chain)
        note = QLabel("Entries cannot be edited or deleted from SENTRA. A correction is a "
                      "new entry that references this one.")
        note.setObjectName("CardCaption")
        note.setWordWrap(True)
        self.entry.add(note)
        self.entry.body.addStretch(1)

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self.table_card, 1)
        body.addWidget(self.entry)
        self.body.addLayout(body, 1)

    # -- filters ------------------------------------------------------------------------

    def set_choices(self, users: Sequence[str], roles: Sequence[str],
                    actions: Sequence[str]) -> None:
        for box, everything, values in ((self.user, "All users", users),
                                        (self.role, "All roles", roles),
                                        (self.action, "All actions", actions)):
            current = box.currentData()
            box.blockSignals(True)
            box.clear()
            box.addItem(everything, "")
            for value in values:
                box.addItem(value, value)
            index = box.findData(current)
            box.setCurrentIndex(index if index >= 0 else 0)
            box.blockSignals(False)

    @property
    def filters(self) -> Tuple[str, str, str, int]:
        return (str(self.user.currentData() or ""), str(self.role.currentData() or ""),
                str(self.action.currentData() or ""), int(self.period.currentData()))

    # -- state ---------------------------------------------------------------------------

    def set_banner(self, text: str, ok: bool) -> None:
        self.banner.setText(text)
        self.banner.setProperty("ok", ok)
        self.banner.style().unpolish(self.banner)
        self.banner.style().polish(self.banner)

    def set_rows(self, rows: Sequence[Dict[str, object]], total: int) -> None:
        self.table.set_rows(rows)
        self.count.setText(f"{len(rows)} entries")
        if rows:
            self.table.selectRow(0)
            self._pick(0)
        else:
            self._pick(-1)

    def _pick(self, index: int) -> None:
        if not 0 <= index < len(self.table.rows):
            self.facts.set_pairs(())
            self.chain.set_pairs(())
            self.before.setText("")
            self.after.setText("")
            self.number.setText("")
            return
        row = self.table.rows[index]
        self.number.setText(f"# {row.get('_number', '')}")
        self.facts.set_pairs((("When", str(row.get("when", ""))[:19]),
                              ("Who", f"{row.get('user')} · {row.get('role_label')}"),
                              ("Action", str(row.get("title"))),
                              ("Object", str(row.get("object")))),
                             mono=("When", "Object"))
        self.before.setText(f"<span style='color:#5F6368'>Previous</span><br>{row.get('previous')}")
        self.after.setText(f"<span style='color:#5F6368'>New</span><br>{row.get('new')}")

        def short(value: object) -> str:
            text = str(value or "")
            return f"{text[:4]}…{text[-4:]}" if len(text) > 12 else (text or "—")

        self.chain.set_pairs((("Entry hash", short(row.get("hash"))),
                              ("Prev. hash", short(row.get("prev"))),
                              ("Workstation", str(row.get("_workstation", "—"))),
                              ("Build", str(row.get("version") or "—"))),
                             mono=("Entry hash", "Prev. hash", "Workstation", "Build"))
