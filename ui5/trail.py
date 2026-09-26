"""The decision trail, on the HSE Review page.

Every review decision ever recorded on this workstation's decision log -
newest first, including the ones a later decision on the same report
superseded - with who decided, when, what the engine had said, whether the
decision overturned it, and the note. It can be filtered by person, by
decision and by text, and exported as CSV for an auditor.

Each case also carries its own history (:class:`CaseHistory`): the decisions
on that one report, in order, so a reviewer sees what was decided before.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, \
    QVBoxLayout, QWidget

from sif.review import DECISION_LABELS
from ui4.kit import Card, Col, DesignTable, clear_layout
from ui4.present import fmt_datetime

__all__ = ["DecisionTrail", "CaseHistory", "TRAIL_COLUMNS", "DECISION_TONES"]

DECISION_TONES = {"confirmed": "fail", "rejected": "ok", "unclear": "warn"}
SHORT = {"confirmed": "SIF confirmed", "rejected": "Not SIF", "unclear": "Needs info"}

TRAIL_COLUMNS = (
    Col("when", "Decided", 196, "mono"),
    Col("reference", "Ref", 96, "link"),
    Col("decision_pill", "Decision", 120, "pill"),
    Col("reviewer", "Reviewer", 190),
    Col("engine", "Engine said", 96, "muted"),
    Col("overturn_pill", "Overturns", 96, "pill"),
    Col("trigger", "Trigger", 150, "muted"),
    Col("note", "Note", 0),
    Col("standing_pill", "Standing", 104, "pill"),
)


def trail_rows(entries: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    """Decision payloads (oldest first) as table rows, newest first. The last
    decision on each report stands; the ones before it were superseded."""
    entries = list(entries)
    last = {str(entry.get("fingerprint")): index for index, entry in enumerate(entries)}
    rows = []
    for index in range(len(entries) - 1, -1, -1):
        entry = entries[index]
        decision = str(entry.get("decision", ""))
        is_standing = last.get(str(entry.get("fingerprint"))) == index
        rows.append({
            **entry, "when": fmt_datetime(entry.get("decided_at")),
            "decision_pill": (SHORT.get(decision, decision), DECISION_TONES.get(decision, "grey")),
            "engine": "SIF" if entry.get("engine_verdict") else "Not SIF",
            "overturn_pill": ("Overturned", "warn") if entry.get("overturns_engine")
            else ("Agrees", "grey"),
            "standing_pill": ("Standing", "info") if is_standing else ("Superseded", "grey"),
            "standing": is_standing,
        })
    return rows


class DecisionTrail(QWidget):
    """Every decision, filterable, exportable."""

    reference_requested = pyqtSignal(str)
    export_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.rows: List[Dict[str, object]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.card = Card("Decision trail", "every decision recorded, newest first", flush=True)
        self.summary = QLabel("")
        self.summary.setObjectName("CardCaption")
        self.card.add_head(self.summary)

        filters = QFrame()
        filters.setObjectName("TrailFilters")
        row = QHBoxLayout(filters)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search ref, reviewer, trigger, note")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(280)
        self.reviewer = QComboBox()
        self.reviewer.setFixedWidth(220)
        self.decision = QComboBox()
        self.decision.setFixedWidth(170)
        self.decision.addItem("All decisions", "")
        for key, label in DECISION_LABELS.items():
            self.decision.addItem(label, key)
        self.decision.addItem("Overturned the engine", "overturned")
        self.standing = QComboBox()
        self.standing.setFixedWidth(170)
        for key, label in (("", "Standing and superseded"), ("standing", "Standing only"),
                           ("superseded", "Superseded only")):
            self.standing.addItem(label, key)
        self.clear_button = QPushButton("Clear filters")
        self.clear_button.clicked.connect(self.clear_filters)
        for widget in (self.search, self.reviewer, self.decision, self.standing):
            row.addWidget(widget)
        row.addWidget(self.clear_button)
        row.addStretch(1)
        self.search.textChanged.connect(lambda _text: self._apply())
        for box in (self.reviewer, self.decision, self.standing):
            box.currentIndexChanged.connect(lambda _index: self._apply())
        self.card.body.addWidget(filters)

        self.table = DesignTable(TRAIL_COLUMNS, row_height=40, wrap=True)
        self.table.link_clicked.connect(self._open)
        self.table.row_activated.connect(self._open)
        self.card.add(self.table, 1)
        self.empty = QLabel("No decision recorded yet. Decisions made on HSE Review appear "
                            "here with who made them and when.")
        self.empty.setObjectName("Hint")
        self.empty.setContentsMargins(14, 10, 14, 14)
        self.card.add(self.empty)
        layout.addWidget(self.card, 1)

    def set_rows(self, rows: Sequence[Dict[str, object]]) -> None:
        self.rows = list(rows)
        current = self.reviewer.currentData()
        self.reviewer.blockSignals(True)
        self.reviewer.clear()
        self.reviewer.addItem("All reviewers", "")
        for name in sorted({str(row.get("reviewer") or "") for row in self.rows} - {""}):
            self.reviewer.addItem(name, name)
        index = self.reviewer.findData(current)
        self.reviewer.setCurrentIndex(max(0, index))
        self.reviewer.blockSignals(False)
        self._apply()

    def clear_filters(self) -> None:
        for box in (self.reviewer, self.decision, self.standing):
            box.blockSignals(True)
            box.setCurrentIndex(0)
            box.blockSignals(False)
        self.search.clear()
        self._apply()

    def _apply(self) -> None:
        needle = self.search.text().strip().lower()
        reviewer = self.reviewer.currentData() or ""
        decision = self.decision.currentData() or ""
        standing = self.standing.currentData() or ""
        shown = []
        for row in self.rows:
            if reviewer and row.get("reviewer") != reviewer:
                continue
            if decision == "overturned" and not row.get("overturns_engine"):
                continue
            if decision and decision != "overturned" and row.get("decision") != decision:
                continue
            if standing and (standing == "standing") != bool(row.get("standing")):
                continue
            if needle and needle not in " ".join(str(row.get(key, "")) for key in (
                    "reference", "reviewer", "trigger", "note")).lower():
                continue
            shown.append(row)
        self.table.set_rows(shown)
        self.table.setVisible(bool(self.rows))
        self.empty.setVisible(not self.rows)
        standing_rows = [row for row in self.rows if row.get("standing")]
        self.summary.setText(
            f"{len(shown)} of {len(self.rows)} shown · "
            f"{sum(1 for row in standing_rows if row.get('decision') == 'confirmed')} confirmed, "
            f"{sum(1 for row in standing_rows if row.get('decision') == 'rejected')} not SIF, "
            f"{sum(1 for row in standing_rows if row.get('decision') == 'unclear')} need info · "
            f"{sum(1 for row in standing_rows if row.get('overturns_engine'))} overturned "
            "the engine")

    def _open(self, index: int) -> None:
        if 0 <= index < len(self.table.rows):
            self.reference_requested.emit(str(self.table.rows[index].get("reference", "")))


class CaseHistory(QFrame):
    """The decisions on one report, oldest first, in the case."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("HistoryPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(4)
        title = QLabel("DECISION HISTORY FOR THIS REPORT")
        title.setObjectName("MonoTitle")
        layout.addWidget(title)
        self.lines = QVBoxLayout()
        self.lines.setSpacing(4)
        layout.addLayout(self.lines)

    def set_entries(self, entries: Sequence[Dict[str, object]]) -> None:
        clear_layout(self.lines)
        if not entries:
            note = QLabel("No decision yet on this report.")
            note.setObjectName("Hint")
            self.lines.addWidget(note)
            return
        last = len(entries) - 1
        for index, entry in enumerate(entries):
            decision = str(entry.get("decision", ""))
            text = (f"<b>{SHORT.get(decision, decision)}</b> · {entry.get('reviewer') or 'unattended'}"
                    f" · {fmt_datetime(entry.get('decided_at'))}"
                    + (" · overturned the engine" if entry.get("overturns_engine") else "")
                    + (f" — “{entry.get('note')}”" if entry.get("note") else "")
                    + ("" if index == last else " <span style='color:#9CA3AF'>(superseded)</span>"))
            line = QLabel(text)
            line.setObjectName("HistoryLine")
            line.setWordWrap(True)
            self.lines.addWidget(line)
