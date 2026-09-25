"""Dashboard - the corpus at a glance, for a period, a site and an activity.

From the design: the period (last 30 days, 90 days, 12 months), a site and
an activity filter and a CSV export; five figures; SIF exposure by IOGP
life-saving rule, high-energy sources and the weekly risk trend; failed
barrier controls, frequently flagged activities and the latest reports.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QWidget

from .kit import (BarList, Card, Col, DesignTable, LineChart, Page, Segmented, StatStrip,
                  link_button)

__all__ = ["DashboardPage", "PERIODS", "RECENT_COLUMNS"]

PERIODS = (("30", "Last 30\ndays"), ("90", "Last 90\ndays"), ("365", "12\nmonths"))

def _critical(row: Dict[str, object]) -> bool:
    return float(row.get("risk_score") or 0) >= 85


RECENT_COLUMNS = (
    Col("reference", "Ref", 118, "mono", style=lambda row: ("", _critical(row))),
    Col("site", "Location", 0, value=lambda row: row.get("site") or row.get("location", "")),
    Col("risk_text", "Risk", 62, align="right",
        style=lambda row: ("#B3261E" if _critical(row) else "", False)),
    Col("status", "Status", 104, "pill"),
)


class Legend(QWidget):
    """'— SIF potential  - - Critical' in the trend card's head."""

    def __init__(self) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        for mark, name, css in (("—", "SIF potential", "color:#1F2328;"),
                                ("- -", "Critical", "color:#B3261E;")):
            glyph = QLabel(mark)
            glyph.setStyleSheet(css + "font-weight:700;")
            label = QLabel(name)
            label.setObjectName("LegendText")
            row.addWidget(glyph)
            row.addWidget(label)
            row.addSpacing(6)


class DashboardPage(Page):
    period_changed = pyqtSignal(str)
    filter_changed = pyqtSignal()
    export_requested = pyqtSignal()
    queue_requested = pyqtSignal()
    report_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__("Dashboard", "", scroll=True)
        self.period = Segmented(PERIODS, "90")
        self.period.changed.connect(self.period_changed.emit)
        self.site = QComboBox()
        self.site.setFixedWidth(150)
        self.activity = QComboBox()
        self.activity.setFixedWidth(176)
        for box in (self.site, self.activity):
            box.currentIndexChanged.connect(lambda _index: self.filter_changed.emit())
        export = QPushButton("Export CSV")
        export.clicked.connect(self.export_requested.emit)
        for widget in (self.period, self.site, self.activity, export):
            self.head.add(widget)

        self.stats = StatStrip(("Total reports", "SIF potential", "Mean risk score",
                                "Critical risk", "Awaiting review"))
        self.body.addWidget(self.stats)

        self.rules = Card("SIF exposure by IOGP life-saving rule", "")
        self.rules_caption = self._right(self.rules, "reports")
        self.rule_bars = BarList()
        self.rules.add(self.rule_bars)
        self.rules.body.addStretch(1)
        self.energy = Card("High-energy source", "")
        self._right(self.energy, "high-energy reports")
        self.energy_bars = BarList()
        self.energy.add(self.energy_bars)
        self.energy.body.addStretch(1)
        self.trend = Card("Risk trend", "")
        self.trend.add_head(Legend())
        self.trend_chart = LineChart()
        self.trend.add(self.trend_chart, 1)
        self.barriers = Card("Failed barrier controls", "")
        self.barrier_bars = BarList()
        self.barriers.add(self.barrier_bars)
        self.barriers.body.addStretch(1)
        self.activities = Card("Frequently flagged activities", "")
        self._right(self.activities, "SIF potential")
        self.activity_bars = BarList()
        self.activities.add(self.activity_bars)
        self.activities.body.addStretch(1)
        self.recent = Card("Recent reports", "", flush=True)
        queue = link_button("Review queue")
        queue.clicked.connect(self.queue_requested.emit)
        self.recent.add_head(queue)
        self.recent_table = DesignTable(RECENT_COLUMNS, row_height=30)
        self.recent_table.row_activated.connect(self._open)
        self.recent.add(self.recent_table, 1)

        grid = QGridLayout()
        grid.setSpacing(12)
        for index, card in enumerate((self.rules, self.energy, self.trend,
                                      self.barriers, self.activities, self.recent)):
            grid.addWidget(card, index // 3, index % 3)
            card.setMinimumHeight(290)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        self.body.addLayout(grid, 1)

    @staticmethod
    def _right(card: Card, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("CardCaption")
        card.add_head(label)
        return label

    def _open(self, row: int) -> None:
        if 0 <= row < len(self.recent_table.rows):
            self.report_requested.emit(str(self.recent_table.rows[row].get("reference", "")))

    # -- filters ------------------------------------------------------------------

    def set_choices(self, sites: Sequence[str], activities: Sequence[str]) -> None:
        for box, everything, values in ((self.site, "All sites", sites),
                                        (self.activity, "All activities", activities)):
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
    def filters(self) -> Tuple[str, str, str]:
        return (self.period.current, str(self.site.currentData() or ""),
                str(self.activity.currentData() or ""))

    # -- state from the window --------------------------------------------------------

    def set_caption(self, text: str) -> None:
        self.head.caption.setText(text)

    def set_stats(self, values: Sequence[Tuple[object, str, bool]]) -> None:
        for cell, (value, note, alert) in zip(self.stats.cells, values):
            cell.set(value, note, alert=alert)

    def set_charts(self, rules, energies, barriers, activities) -> None:
        self.rule_bars.set_items(rules)
        self.energy_bars.set_items(energies)
        self.barrier_bars.set_items(barriers)
        self.activity_bars.set_items(activities)

    def set_trend(self, sif, critical, labels) -> None:
        self.trend_chart.set_series(((sif, "#1F2328", False), (critical, "#B3261E", True)),
                                    labels)

    def set_recent(self, rows: Sequence[Dict[str, object]]) -> None:
        self.recent_table.set_rows(rows)
