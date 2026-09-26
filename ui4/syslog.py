"""SysLog - what the software did, service by service.

From the design: a search, a time range, a service and a level filter, a live
tail; every event with its time, service, level, message, machine and
outcome; and the chosen event in full beside it. No human action appears
here - those are the Audit Log's.
"""

from __future__ import annotations

from typing import Dict, Sequence

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from .kit import Card, Col, DesignTable, KeyValues, Page, Segmented

__all__ = ["LEVEL_COLOURS", "SERVICES", "SysLogPage", "service_of"]

#: Logger name -> the service the design names.
SERVICES = {"sif.ocr": "OCR", "sif.encoders": "ENCODER", "sif.llm": "LLM",
            "sif.pipeline": "PIPELINE", "sif.mlops": "TRAIN", "sif.app2": "CONSOLE",
            "sif.audit": "AUDIT", "sif.updater": "UPDATER", "sif.accounts": "ACCOUNTS",
            "sif.actions": "ACTIONS", "sif.review": "REVIEW"}
LEVEL_COLOURS = {"INFO": "#1E4F7A", "WARNING": "#8A5A00", "ERROR": "#B3261E",
                 "CRITICAL": "#B3261E", "DEBUG": "#5F6368"}


def service_of(logger: str) -> str:
    return SERVICES.get(logger, logger.split(".")[-1].upper() or "SYSTEM")


def outcome_of(level: str) -> tuple:
    if level in ("ERROR", "CRITICAL"):
        return ("✕ Failed", "#B3261E")
    if level == "WARNING":
        return ("◆ Warn", "#8A5A00")
    return ("✓ OK", "#1E7B34")


COLUMNS = (
    Col("timestamp", "Timestamp", 196, "mono"),
    Col("service", "Service", 96, "mono"),
    Col("level_text", "Level", 76, "mono",
        style=lambda row: (LEVEL_COLOURS.get(str(row.get("level")), ""), True)),
    Col("message", "Event", 0, "mono"),
    Col("machine", "Machine", 120, "mono", style=lambda row: ("#6B6F74", False)),
    Col("outcome", "Status", 96, style=lambda row: (outcome_of(str(row.get("level")))[1], True)),
)


class SysLogPage(Page):
    filters_changed = pyqtSignal()
    export_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__("SysLog", "System events written by SENTRA services. No human "
                                   "actions appear here — see Audit Log.")
        export = QPushButton("Export .log")
        export.clicked.connect(self.export_requested.emit)
        self.head.add(export)

        bar = QFrame()
        bar.setObjectName("Card")
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search events")
        self.search.setFixedWidth(270)
        self.search.textChanged.connect(lambda _t: self.filters_changed.emit())
        self.span = QComboBox()
        for hours, label in ((1, "Last hour"), (24, "Last 24 hours"), (0, "This session")):
            self.span.addItem(label, hours)
        self.span.setCurrentIndex(1)
        self.service = QComboBox()
        self.service.addItem("All services", "")
        for name in sorted(set(SERVICES.values())):
            self.service.addItem(name, name)
        for box in (self.span, self.service):
            box.currentIndexChanged.connect(lambda _i: self.filters_changed.emit())
        self.levels = Segmented((("", "All levels"), ("ERROR", "ERROR"), ("WARNING", "WARN"),
                                 ("INFO", "INFO"), ("DEBUG", "DEBUG")))
        self.levels.changed.connect(lambda _k: self.filters_changed.emit())
        self.live = QCheckBox("Live tail")
        self.live.setChecked(True)
        self.count = QLabel("")
        self.count.setObjectName("MonoFaint")
        self.clear_button = QPushButton("Clear filters")
        self.clear_button.clicked.connect(self.clear_filters)
        for widget in (self.search, self.span, self.service, self.levels, self.clear_button):
            row.addWidget(widget)
        row.addStretch(1)
        row.addWidget(self.live)
        row.addWidget(self.count)
        self.body.addWidget(bar)

        self.table_card = Card(flush=True)
        self.table = DesignTable(COLUMNS, row_height=40, wrap=True)
        self.table.row_clicked.connect(self._pick)
        self.table_card.add(self.table, 1)
        self.detail = Card("Event detail", "")
        self.detail.setFixedWidth(372)
        self.facts = KeyValues(1, label_width=110)
        self.detail.add(self.facts)
        self.message = QLabel("")
        self.message.setObjectName("KvValue")
        self.message.setWordWrap(True)
        self.detail.add(self.message)
        self.note = QLabel("")
        self.note.setObjectName("CardCaption")
        self.note.setWordWrap(True)
        self.detail.add(self.note)
        self.detail.body.addStretch(1)
        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self.table_card, 1)
        body.addWidget(self.detail)
        self.body.addLayout(body, 1)
        self.log_file = ""
        self._selected = -1

    def clear_filters(self) -> None:
        """Every service and level, the last 24 hours, no search."""
        for widget in (self.search, self.span, self.service):
            widget.blockSignals(True)
        self.search.clear()
        self.span.setCurrentIndex(1)
        self.service.setCurrentIndex(0)
        for widget in (self.search, self.span, self.service):
            widget.blockSignals(False)
        self.levels.select("")
        self.filters_changed.emit()

    @property
    def filters(self) -> Dict[str, object]:
        return {"needle": self.search.text().strip().lower(), "hours": self.span.currentData(),
                "service": self.service.currentData() or "", "level": self.levels.current}

    def set_rows(self, rows: Sequence[Dict[str, object]], total: int) -> None:
        keep = self.table.rows[self._selected] if 0 <= self._selected < len(self.table.rows) else None
        shown = [{**row, "level_text": "WARN" if row["level"] == "WARNING" else row["level"],
                  "outcome": outcome_of(str(row["level"]))[0]} for row in rows]
        self.table.set_rows(shown)
        self.count.setText(f"{len(shown)} of {total}")
        index = next((i for i, row in enumerate(shown) if keep and row["timestamp"] ==
                      keep["timestamp"] and row["message"] == keep["message"]), 0 if shown else -1)
        if index >= 0:
            self.table.selectRow(index)
            self._pick(index)
        else:
            self._pick(-1)

    def _pick(self, index: int) -> None:
        self._selected = index
        if not 0 <= index < len(self.table.rows):
            self.facts.set_pairs(())
            self.message.setText("No event matches the filters.")
            self.note.setText("")
            return
        row = self.table.rows[index]
        self.facts.set_pairs((("Timestamp", str(row["timestamp"])), ("Service", str(row["service"])),
                              ("Level", str(row["level_text"])), ("Machine", str(row["machine"])),
                              ("Status", str(row["outcome"]))),
                             mono=("Timestamp", "Level", "Machine"))
        self.message.setText(str(row["message"]))
        self.note.setText(f"Written by {row['logger']}." + (
            f" Kept in {self.log_file}." if self.log_file else ""))
