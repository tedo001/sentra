"""Home - what needs the analyst now.

From the design: the date line and a refresh; four figures (reports, SIF
potential, critical risk still open, awaiting review); what requires
attention, worst first; open cases by trigger; the latest incidents with
their review status; and today's activity.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QLabel, QPushButton, QWidget

from .kit import (AlertRow, Card, Col, DesignTable, Page, StatStrip, Timeline, clear_layout,
                  link_button)
from .present import received

__all__ = ["HomePage", "INCIDENT_COLUMNS"]

INCIDENT_COLUMNS = (
    Col("reference", "Ref", 104, "link"),
    Col("received", "Received", 128, "mono", value=received),
    Col("site", "Location", 176, value=lambda row: row.get("site") or row.get("location", "")),
    Col("activity", "Activity", 178),
    Col("iogp_rule", "IOGP rule", 0),
    Col("risk_score", "Risk", 86, "risk"),
    Col("status", "Review", 176, "pill"),
)


class TriggerList(QWidget):
    """Trigger name and count, one per line."""

    def __init__(self) -> None:
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(12)

    def set_counts(self, counts: Sequence[Tuple[str, int]]) -> None:
        clear_layout(self.grid)
        if not counts:
            none = QLabel("No open cases.")
            none.setObjectName("Faint")
            self.grid.addWidget(none, 0, 0)
        for row, (name, count) in enumerate(counts):
            label = QLabel(name)
            label.setObjectName("KvValue")
            value = QLabel(str(count))
            value.setObjectName("TriggerCount")
            self.grid.addWidget(label, row, 0)
            self.grid.addWidget(value, row, 1)
        self.grid.setColumnStretch(0, 1)


class HomePage(Page):
    refresh_requested = pyqtSignal()
    review_requested = pyqtSignal(str)            # a reference, "" for the queue
    report_requested = pyqtSignal(str)
    reports_requested = pyqtSignal()
    alert_action = pyqtSignal(str, str)           # action key, payload

    def __init__(self) -> None:
        super().__init__("Home", "", scroll=True)
        self.updated = QLabel("")
        self.updated.setObjectName("PageNote")
        self.head.add(self.updated)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_requested.emit)
        self.head.add(refresh)

        self.stats = StatStrip(("Reports analysed", "SIF potential (engine)",
                                "Critical risk, open", "Awaiting your review"))
        self.body.addWidget(self.stats)

        self.attention = Card("Requires your attention", "worst first, then oldest")
        self.attention.body.setSpacing(8)
        self.triggers = Card("Open cases by trigger")
        queue = link_button("Queue")
        queue.clicked.connect(lambda: self.review_requested.emit(""))
        self.triggers.add_head(queue)
        self.trigger_list = TriggerList()
        self.triggers.add(self.trigger_list)
        self.triggers.body.addStretch(1)

        self.incidents = Card("Recent incidents", flush=True)
        everything = link_button("All reports")
        everything.clicked.connect(self.reports_requested.emit)
        self.incidents.add_head(everything)
        self.table = DesignTable(INCIDENT_COLUMNS)
        self.table.setMinimumHeight(250)
        self.table.link_clicked.connect(self._open)
        self.table.row_activated.connect(self._open)
        self.incidents.add(self.table, 1)

        self.activity = Card("Recent activity", "today")
        self.timeline = Timeline()
        self.activity.add(self.timeline, 1)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.addWidget(self.attention, 0, 0)
        grid.addWidget(self.triggers, 0, 1)
        grid.addWidget(self.incidents, 1, 0)
        grid.addWidget(self.activity, 1, 1)
        grid.setColumnStretch(0, 29)
        grid.setColumnStretch(1, 10)
        grid.setRowStretch(1, 1)
        self.body.addLayout(grid, 1)

    def _open(self, row: int) -> None:
        if 0 <= row < len(self.table.rows):
            self.report_requested.emit(str(self.table.rows[row].get("reference", "")))

    # -- state from the window -------------------------------------------------

    def set_heading(self, date_line: str, updated: str) -> None:
        self.head.caption.setText(date_line)
        self.updated.setText(updated)

    def set_stats(self, values: Sequence[Tuple[object, str, bool]]) -> None:
        for cell, (value, note, alert) in zip(self.stats.cells, values):
            cell.set(value, note, alert=alert)

    def set_attention(self, items: Sequence[Tuple[str, str, str, str, str, str]]) -> None:
        """``(tone, lead, text, action label, action key, payload)`` per line."""
        clear_layout(self.attention.body)
        if not items:
            calm = QLabel("Nothing needs you right now. New reports that do will "
                          "appear here, worst first.")
            calm.setObjectName("Faint")
            calm.setWordWrap(True)
            self.attention.add(calm)
        for tone, lead, text, label, key, payload in items:
            row = AlertRow(tone, lead, text, label)
            row.clicked.connect(lambda k=key, p=payload: self.alert_action.emit(k, p))
            self.attention.add(row)

    def set_triggers(self, counts: Sequence[Tuple[str, int]]) -> None:
        self.trigger_list.set_counts(counts)

    def set_incidents(self, rows: Sequence[Dict[str, object]]) -> None:
        self.table.set_rows(rows)

    def set_activity(self, items: Sequence[Tuple[str, str, str]]) -> None:
        self.timeline.set_items(items)
