"""Dashboard, as the revamp lays it out.

Five figures; SIF exposure by IOGP rule (navy bars), failed barrier controls
(violet bars) and the latest reports side by side; then the weekly risk trend
across the page - line or bar, SIF potential, critical and total reports, an
average line - with the week's peaks and totals beneath it. High-energy
sources and flagged activities follow, so nothing the two-workspace
dashboard shows is lost.

Same interface as :class:`ui4.dashboard.DashboardPage`, plus
:meth:`set_weekly`, so the same wiring fills it.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Dict, Sequence, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton

from ui4.dashboard import RECENT_COLUMNS
from ui4.kit import Card, Col, DesignTable, Page, Segmented, StatStrip, link_button
from ui4.present import fmt_date, fmt_week, received

from .charts import AxisBarChart, TrendChart

__all__ = ["SentraDashboard"]

PERIODS = (("30", "Last 30 days"), ("90", "Last 90 days"), ("365", "12 months"))
#: The latest reports with when each happened, as the report states it.
SENTRA_RECENT_COLUMNS = (
    Col("reference", "Ref", 84, "mono", style=RECENT_COLUMNS[0].style),
    Col("reported", "Reported", 104, "muted", value=received),
    RECENT_COLUMNS[1],
    Col("risk_text", "Risk", 50, align="right", style=RECENT_COLUMNS[2].style),
    Col("status", "Status", 92, "pill"),
)
VIOLET = "#7C3AED"


class _Legend(QLabel):
    def __init__(self) -> None:
        super().__init__(
            "<span style='color:#1E3A5F'>━</span> SIF potential&nbsp;&nbsp;&nbsp;"
            "<span style='color:#DC2626'>━</span> Critical risk&nbsp;&nbsp;&nbsp;"
            "<span style='color:#9CA3AF'>┄</span> Total reports")
        self.setObjectName("CardCaption")


class SentraDashboard(Page):
    period_changed = pyqtSignal(str)
    filter_changed = pyqtSignal()
    export_requested = pyqtSignal()
    queue_requested = pyqtSignal()
    report_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__("Dashboard", "", scroll=True)
        self.period = Segmented(PERIODS, "90")
        self.period.layout().setSpacing(6)
        self.period.changed.connect(self.period_changed.emit)
        self.site = QComboBox()
        self.site.setFixedWidth(150)
        self.activity = QComboBox()
        self.activity.setFixedWidth(184)
        for box in (self.site, self.activity):
            box.currentIndexChanged.connect(lambda _index: self.filter_changed.emit())
        export = QPushButton("Export CSV")
        export.clicked.connect(self.export_requested.emit)
        self.clear_button = QPushButton("Clear filters")
        self.clear_button.setToolTip("Last 90 days, every site, every activity")
        self.clear_button.clicked.connect(self.clear_filters)
        for widget in (self.period, self.site, self.activity, self.clear_button, export):
            self.head.add(widget)
        self.updated = QLabel("")
        self.updated.setObjectName("PageCaption")
        self.head.actions.insertWidget(0, self.updated)

        self.stats = StatStrip(("Total reports", "SIF potential", "Mean risk score",
                                "Critical risk", "Awaiting review"))
        self.body.addWidget(self.stats)

        self.rules = Card("SIF exposure by IOGP rule", "")
        self.rules_period = self._right(self.rules)
        self.rule_bars = AxisBarChart("#1E3A5F")
        self.rules.add(self.rule_bars)
        self.rules.body.addStretch(1)
        self.barriers = Card("Failed barrier controls", "")
        self.barriers_period = self._right(self.barriers)
        self.barrier_bars = AxisBarChart(VIOLET)
        self.barriers.add(self.barrier_bars)
        self.barriers.body.addStretch(1)
        self.recent = Card("Recent reports", "", flush=True)
        queue = link_button("Review queue")
        queue.clicked.connect(self.queue_requested.emit)
        self.recent.add_head(queue)
        self.recent_table = DesignTable(SENTRA_RECENT_COLUMNS, row_height=30)
        self.recent_table.row_activated.connect(self._open)
        self.recent.add(self.recent_table, 1)
        top = QGridLayout()
        top.setSpacing(16)
        for column, card in enumerate((self.rules, self.barriers, self.recent)):
            card.setMinimumHeight(300)
            top.addWidget(card, 0, column)
            top.setColumnStretch(column, 1)
        self.body.addLayout(top)

        self.trend = Card("Risk Trend — Weekly SIF & Critical incidents", "")
        self.trend_span = QLabel("")
        self.trend_span.setObjectName("PageCaption")
        self.trend.head_actions.insertWidget(2, self.trend_span)
        self.chart_mode = Segmented((("line", "↗ Line"), ("bar", "▄ Bar")), "line")
        self.chart_mode.changed.connect(lambda mode: self.trend_chart.set_mode(mode))
        self.trend.add_head(self.chart_mode)
        self.trend.add_head(_Legend())
        self.trend_chart = TrendChart()
        self.trend_chart.setMinimumHeight(300)
        self.trend.add(self.trend_chart)
        self.summary = StatStrip(("Peak SIF / week", "Average SIF / week",
                                  "Peak critical / week", "Total reports in period"))
        self.summary.setObjectName("SummaryStrip")
        self.trend.add(self.summary)
        self.body.addWidget(self.trend)

        self.energy = Card("High-energy source", "")
        self._right(self.energy).setText("high-energy reports")
        self.energy_bars = AxisBarChart("#1E3A5F")
        self.energy.add(self.energy_bars)
        self.energy.body.addStretch(1)
        self.activities = Card("Frequently flagged activities", "")
        self._right(self.activities).setText("SIF potential")
        self.activity_bars = AxisBarChart(VIOLET)
        self.activities.add(self.activity_bars)
        self.activities.body.addStretch(1)
        more = QHBoxLayout()
        more.setSpacing(16)
        more.addWidget(self.energy, 1)
        more.addWidget(self.activities, 1)
        self.body.addLayout(more)

    @staticmethod
    def _right(card: Card) -> QLabel:
        label = QLabel("")
        label.setObjectName("CardCaption")
        card.add_head(label)
        return label

    def _open(self, row: int) -> None:
        if 0 <= row < len(self.recent_table.rows):
            self.report_requested.emit(str(self.recent_table.rows[row].get("reference", "")))

    # -- the same interface as the two-workspace dashboard ------------------------------

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

    def set_caption(self, text: str) -> None:
        self.head.caption.setText(text.replace(
            "all figures are engine assessments unless marked reviewed", "engine assessments"))
        label = dict(PERIODS).get(self.period.current, "")
        for caption in (self.rules_period, self.barriers_period):
            caption.setText(label)

    def set_stats(self, values: Sequence[Tuple[object, str, bool]]) -> None:
        for cell, (value, note, alert) in zip(self.stats.cells, values):
            cell.set(value, note, alert=alert)

    def set_charts(self, rules, energies, barriers, activities) -> None:
        self.rule_bars.set_items(rules)
        self.energy_bars.set_items(energies)
        self.barrier_bars.set_items(barriers)
        self.activity_bars.set_items(activities)

    def set_trend(self, sif, critical, labels) -> None:
        """The two-workspace call; the weekly table (set_weekly) is what draws here."""

    def set_weekly(self, weeks: Sequence[Dict[str, object]], period_label: str) -> None:
        labels = [str(week["label"]) for week in weeks]
        sif = [float(week["sif"]) for week in weeks]
        critical = [float(week["critical"]) for week in weeks]
        reports = [float(week["reports"]) for week in weeks]
        average = sum(sif) / len(sif) if sif else 0.0
        self.trend_chart.set_data(labels, sif, critical, reports,
                                  (average, "Average") if weeks else None,
                                  titles=[f"Week {week.get('week') or fmt_week(week['start'])}"
                                          for week in weeks])
        self.trend_span.setText(
            f"{fmt_date(weeks[0]['start'])} → "
            f"{fmt_date(weeks[-1]['start'] + timedelta(days=6))} · weekly counts"
            if weeks else "no dated reports")
        if weeks:
            peak = max(weeks, key=lambda week: week["sif"])
            peak_critical = max(weeks, key=lambda week: week["critical"])
            values = ((f"{peak['sif']:g}", f"week of {fmt_week(peak['start'])}"),
                      (f"{average:.1f}", period_label),
                      (f"{peak_critical['critical']:g}",
                       f"week of {fmt_week(peak_critical['start'])}"),
                      (f"{sum(reports):g}", "all documents"))
        else:
            values = (("-", ""),) * 4
        for cell, (value, note) in zip(self.summary.cells, values):
            cell.set(value, note)

    def clear_filters(self) -> None:
        for box in (self.site, self.activity):
            box.blockSignals(True)
            box.setCurrentIndex(0)
            box.blockSignals(False)
        self.period.select("90")
        self.period_changed.emit("90")

    def set_updated(self, text: str) -> None:
        self.updated.setText(text)

    def set_recent(self, rows: Sequence[Dict[str, object]]) -> None:
        self.recent_table.set_rows(rows)
