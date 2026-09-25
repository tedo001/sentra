"""Reports - every analysed report, and the evidence behind each verdict.

Where a reference on Home, the Dashboard or Risk Hotspots leads: the list on
the left, the report on the right in the same form as a review case (without
the decision bar - a report that is not queued is not a case), with a way to
its case when it has one and a way to raise a corrective action against it.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout

from .kit import Card, Col, DesignTable, Page
from .present import received
from .review import CaseView

__all__ = ["REPORT_COLUMNS", "ReportsPage"]

REPORT_COLUMNS = (
    Col("reference", "Ref", 88, "mono", style=lambda row: ("", float(row.get("risk_score") or 0) >= 85)),
    Col("received", "Received", 124, "mono", value=received),
    Col("site", "Location", 0, value=lambda row: row.get("site") or row.get("location", "")),
    Col("risk_score", "Risk", 82, "risk"),
    Col("status", "Review", 148, "pill"),
)


class ReportsPage(Page):
    report_selected = pyqtSignal(str)
    case_requested = pyqtSignal(str)
    action_requested = pyqtSignal(str)
    export_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__("Reports", "")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search ref, location, activity, rule")
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(lambda _text: self._apply())
        export = QPushButton("Export CSV")
        export.clicked.connect(self.export_requested.emit)
        self.head.add(self.search)
        self.head.add(export)

        self.rows: List[Dict[str, object]] = []
        self.current = ""
        self.list_card = Card(flush=True)
        self.table = DesignTable(REPORT_COLUMNS)
        self.table.row_clicked.connect(self._clicked)
        self.list_card.add(self.table, 1)
        self.list_card.setFixedWidth(560)

        case_card = QFrame()
        case_card.setObjectName("Card")
        layout = QVBoxLayout(case_card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.case = CaseView()
        layout.addWidget(self.case, 1)
        actions = QFrame()
        actions.setObjectName("DecisionBar")
        row = QHBoxLayout(actions)
        row.setContentsMargins(16, 10, 16, 12)
        self.to_case = QPushButton("Open its case in HSE Review")
        self.to_case.clicked.connect(lambda: self.case_requested.emit(self.current))
        self.raise_action = QPushButton("Raise a corrective action")
        self.raise_action.clicked.connect(lambda: self.action_requested.emit(self.current))
        row.addWidget(self.to_case)
        row.addWidget(self.raise_action)
        row.addStretch(1)
        layout.addWidget(actions)

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self.list_card)
        body.addWidget(case_card, 1)
        self.body.addLayout(body, 1)

    def set_rows(self, rows: Sequence[Dict[str, object]]) -> None:
        self.rows = list(rows)
        self.head.caption.setText(f"{len(self.rows)} analysed · the evidence behind "
                                  "each verdict")
        self._apply()

    def _apply(self) -> None:
        needle = self.search.text().strip().lower()
        shown = [row for row in self.rows if not needle or needle in " ".join(
            str(row.get(key, "")) for key in ("reference", "site", "location", "activity",
                                              "iogp_rule")).lower()]
        self.table.set_rows(shown)
        refs = [str(row.get("reference")) for row in shown]
        if self.current in refs:
            self.table.selectRow(refs.index(self.current))
        elif shown:
            self.table.selectRow(0)
            self._clicked(0)

    def _clicked(self, index: int) -> None:
        if 0 <= index < len(self.table.rows):
            self.current = str(self.table.rows[index].get("reference", ""))
            self.report_selected.emit(self.current)

    def select(self, reference: str) -> None:
        self.current = reference
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self._apply()
        self.report_selected.emit(reference)
