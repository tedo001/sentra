"""Dashboard, as the revamp lays it out.

Five figures; SIF exposure by IOGP rule (navy bars), failed barrier controls
(violet bars) and the latest reports side by side; then the risk trend up to
now - today by the hour, the last week or month by the day, the last year by
the month, or every dated report - line or bar, SIF potential, critical and
total reports, an average line, with the peaks and totals beneath it; and
beside it the risk profile, a spider chart of the same reports by IOGP rule,
energy source or failed barrier. High-energy sources and flagged activities
follow, so nothing the two-workspace dashboard shows is lost.

Same interface as :class:`ui4.dashboard.DashboardPage`, plus
:meth:`set_trend_range` and :meth:`set_profile`, so the same wiring fills it.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Dict, Sequence, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton

from ui4.dashboard import RECENT_COLUMNS
from ui4.kit import Card, Col, DesignTable, Page, Segmented, StatStrip, link_button
from ui4.present import PROFILES, TREND_SPANS, fmt_date, fmt_week, received

from .charts import AxisBarChart, RadarChart, TrendChart

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
    def __init__(self, total: str = "┄") -> None:
        super().__init__(
            "<span style='color:#1E3A5F'>━</span> SIF potential&nbsp;&nbsp;&nbsp;"
            "<span style='color:#DC2626'>━</span> Critical risk&nbsp;&nbsp;&nbsp;"
            f"<span style='color:#9CA3AF'>{total}</span> Total reports")
        self.setObjectName("CardCaption")


#: How each range's buckets are named on the axis and in the summary.
UNIT_WORDS = {"hour": ("Hour of day", "hour"), "day": ("Day", "day"),
              "week": ("Week commencing", "week"), "month": ("Month", "month")}


class SentraDashboard(Page):
    period_changed = pyqtSignal(str)
    filter_changed = pyqtSignal()
    #: The trend's range (today/week/month/year/all) or the spider's view changed.
    trend_changed = pyqtSignal()
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

        self.trend = Card("Risk Trend — SIF & Critical incidents", "")
        self.trend_range = Segmented(tuple((key, button) for key, button, _unit, _caption
                                           in TREND_SPANS), "month")
        self.trend_range.setToolTip("Up to now: today by the hour, the last 7 or 30 days by "
                                    "the day, the last 12 months by the month")
        self.trend_range.changed.connect(lambda _key: self.trend_changed.emit())
        self.trend.add_head(self.trend_range)
        self.chart_mode = Segmented((("line", "↗ Line"), ("bar", "▄ Bar")), "line")
        self.chart_mode.changed.connect(lambda mode: self.trend_chart.set_mode(mode))
        self.trend.add_head(self.chart_mode)
        under = QHBoxLayout()
        self.trend_span = QLabel("")
        self.trend_span.setObjectName("PageCaption")
        under.addWidget(self.trend_span)
        under.addStretch(1)
        under.addWidget(_Legend())
        self.trend.body.addLayout(under)
        self.trend_chart = TrendChart()
        self.trend_chart.setMinimumHeight(300)
        self.trend.add(self.trend_chart)
        self.summary = StatStrip(("Peak SIF / day", "Average SIF / day",
                                  "Peak critical / day", "Total reports in period"))
        self.summary.setObjectName("SummaryStrip")
        self.trend.add(self.summary)

        self.profile = Card("Risk profile", "")
        self.profile_view = Segmented(tuple((key, button) for key, button, _axes in PROFILES),
                                      "rule")
        self.profile_view.changed.connect(lambda _key: self.trend_changed.emit())
        self.profile.add_head(self.profile_view)
        self.profile_span = QLabel("")
        self.profile_span.setObjectName("PageCaption")
        self.profile.add(self.profile_span)
        self.radar = RadarChart()
        self.radar.setMinimumHeight(340)
        self.profile.add(self.radar, 1)
        legend = _Legend("▨")
        legend.setWordWrap(True)
        self.profile.add(legend)
        trend_row = QHBoxLayout()
        trend_row.setSpacing(16)
        trend_row.addWidget(self.trend, 2)
        trend_row.addWidget(self.profile, 1)
        self.body.addLayout(trend_row)

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

    @property
    def trend_span_key(self) -> str:
        return self.trend_range.current

    @property
    def profile_key(self) -> str:
        return self.profile_view.current

    def set_trend_range(self, table: Dict[str, object]) -> None:
        """Draw :func:`ui4.present.trend_table`'s buckets: up to now, per hour, day or month."""
        buckets = list(table.get("buckets") or [])
        axis, unit = UNIT_WORDS.get(str(table.get("unit") or "day"), UNIT_WORDS["day"])
        sif = [float(bucket["sif"]) for bucket in buckets]
        critical = [float(bucket["critical"]) for bucket in buckets]
        reports = [float(bucket["reports"]) for bucket in buckets]
        average = sum(sif) / len(sif) if sif else 0.0
        self.trend_chart.axis_caption = axis
        # Hours and days are counts, not a continuous flow: straight lines.
        self.trend_chart.smooth = unit in ("week", "month")
        self.trend_chart.set_data([str(bucket["label"]) for bucket in buckets], sif, critical,
                                  reports, (average, "Average") if buckets else None,
                                  titles=[str(bucket["title"]) for bucket in buckets])
        caption = str(table.get("caption") or "")
        if table.get("untimed"):
            caption += f" · {table['untimed']} dated today without a time"
        self.trend_span.setText(caption or "no dated reports")
        for cell, text in zip(self.summary.cells, (f"Peak SIF / {unit}", f"Average SIF / {unit}",
                                                   f"Peak critical / {unit}",
                                                   "Total reports in period")):
            cell.label.setText(text)
        in_range = int(table.get("reports") or sum(reports))
        if buckets and in_range:
            peak = max(buckets, key=lambda bucket: bucket["sif"])
            peak_critical = max(buckets, key=lambda bucket: bucket["critical"])
            over = {"today": "each hour today", "week": "each day, last 7 days",
                    "month": "each day, last 30 days", "year": "each month, last 12 months",
                    }.get(str(table.get("span")), f"each {unit} in range")
            values = ((f"{peak['sif']:g}", str(peak["title"]) if peak["sif"] else "none"),
                      (f"{average:.1f}", over),
                      (f"{peak_critical['critical']:g}",
                       str(peak_critical["title"]) if peak_critical["critical"] else "none"),
                      (f"{in_range:g}", "dated in this range" + (
                          f" · {table['untimed']} without a time" if table.get("untimed")
                          else "")))
        else:
            values = (("0", "no reports in this range"), ("0.0", ""), ("0", ""),
                      ("0", "dated in this range"))
        for cell, (value, note) in zip(self.summary.cells, values):
            cell.set(value, note)

    def set_profile(self, axes: Sequence[Tuple[str, str, int, int, int]], caption: str,
                    reports: int = 0) -> None:
        """The spider chart: per category (full name, short, SIF, critical, all)."""
        self.radar.set_axes(axes)
        placed = sum(1 for axis in axes if axis[4])
        self.profile_span.setText(
            f"{caption} · {reports} report(s), {placed} of {len(axes)} categories"
            if reports else f"{caption} · no reports in this range")

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
