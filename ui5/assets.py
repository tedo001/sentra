"""Asset Safety Memory and Work-Hold Recommendation, on screen.

* :class:`RecommendationPanel` - the recommendation at the top of a review
  case: Continue / HSE Review Required / Work-Hold Recommended, why, what to
  do, and every factor that counted with its weight.
* :class:`AssetMemoryPanel` - the asset's history beside the case: what kind
  of reports it has had, the signals the history raises about this one, and
  the earlier reports.
* :class:`AssetMemoryPage` - the HSE workspace's *Asset Memory* tab: every
  asset, worst first, and for the chosen one its signals, hazards, control
  failures, reports with their recommendations, and corrective actions.

The pages show; :mod:`main5` builds the memory (:mod:`sif.assets`) and the
recommendations (:mod:`sif.workhold`).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from sif.assets import AssetContext, AssetHistory, Signal
from sif.workhold import Recommendation
from ui4.kit import (Card, Col, DesignTable, KeyValues, Page, Pill, StatStrip, clear_layout,
                     link_button)

from .charts import AxisBarChart

__all__ = ["RecommendationPanel", "AssetMemoryPanel", "AssetMemoryPage", "signal_mark",
           "ASSET_COLUMNS", "TIMELINE_COLUMNS", "ACTION_COLUMNS"]

SEVERITY = {"high": ("▲", "#DC2626"), "medium": ("◆", "#D97706"), "low": ("·", "#6B7280")}
LEVEL_TONE = {"continue": "ok", "review": "warn", "hold": "fail"}
KIND_LABEL = {"incident": "Incident", "near miss": "Near miss", "hazard": "Hazard observation"}


def _l(text: str, name: str, wrap: bool = True) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


def signal_mark(severity: str) -> str:
    mark, colour = SEVERITY.get(severity, SEVERITY["low"])
    return f"<span style='color:{colour}'>{mark}</span>"


def _signal_rows(layout: QVBoxLayout, signals: Sequence[Signal], limit: int = 8,
                 on_reference=None) -> None:
    for signal in list(signals)[:limit]:
        row = QHBoxLayout()
        row.setSpacing(8)
        mark = _l(signal_mark(signal.severity), "SignalMark", wrap=False)
        mark.setTextFormat(Qt.TextFormat.RichText)
        mark.setFixedWidth(12)
        mark.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        row.addWidget(mark)
        words = QVBoxLayout()
        words.setSpacing(0)
        words.addWidget(_l(signal.kind[:1].upper() + signal.kind[1:], "SignalKind", wrap=False))
        words.addWidget(_l(signal.text, "SignalText"))
        row.addLayout(words, 1)
        layout.addLayout(row)


class RecommendationPanel(QFrame):
    """The work-hold recommendation for one case, with its evidence."""

    action_requested = pyqtSignal(str)          # reference

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("HoldPanel")
        self.reference = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(_l("WORK-HOLD RECOMMENDATION", "MonoTitle", wrap=False))
        self.level = Pill("", "grey")
        top.addWidget(self.level)
        top.addStretch(1)
        self.route = _l("", "CaseMeta", wrap=False)
        top.addWidget(self.route)
        layout.addLayout(top)
        self.summary = _l("", "HoldSummary")
        layout.addWidget(self.summary)
        self.factors = QGridLayout()
        self.factors.setHorizontalSpacing(10)
        self.factors.setVerticalSpacing(3)
        layout.addLayout(self.factors)
        bottom = QHBoxLayout()
        self.score = _l("", "Hint", wrap=False)
        bottom.addWidget(self.score)
        bottom.addStretch(1)
        self.action = QPushButton("Raise a corrective action")
        self.action.clicked.connect(lambda: self.action_requested.emit(self.reference))
        bottom.addWidget(self.action)
        layout.addLayout(bottom)

    def show_recommendation(self, reference: str, rec: Optional[Recommendation],
                            can_act: bool = True) -> None:
        self.reference = reference
        self.setVisible(rec is not None)
        if rec is None:
            return
        self.setProperty("level", rec.level)
        self.style().unpolish(self)
        self.style().polish(self)
        self.level.set(rec.label, LEVEL_TONE[rec.level])
        self.route.setText("routed to an HSE expert" if rec.routed else "no routing needed")
        self.summary.setText(rec.advice)
        clear_layout(self.factors)
        for index, factor in enumerate(rec.factors[:9]):
            weight = _l(f"+{factor.weight}", "FactorWeight", wrap=False)
            weight.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            self.factors.addWidget(weight, index, 0)
            self.factors.addWidget(_l(factor.name, "FactorName", wrap=False), index, 1,
                                   Qt.AlignmentFlag.AlignTop)
            self.factors.addWidget(_l(factor.evidence, "FactorEvidence"), index, 2)
        self.factors.setColumnStretch(2, 1)
        more = len(rec.factors) - 9
        self.score.setText(f"Weighted evidence {rec.score} · hold at 12, review at 4"
                           + (f" · {more} more factor(s)" if more > 0 else ""))
        self.action.setVisible(rec.level != "continue")
        self.action.setEnabled(can_act)


class AssetMemoryPanel(QFrame):
    """What the asset's history says about the case in hand."""

    asset_requested = pyqtSignal(str)
    report_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("MemoryPanel")
        self.asset = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        top = QHBoxLayout()
        top.addWidget(_l("ASSET SAFETY MEMORY", "MonoTitle", wrap=False))
        self.name = _l("", "SubTitle", wrap=False)
        top.addWidget(self.name)
        top.addStretch(1)
        self.open = link_button("Open asset")
        self.open.clicked.connect(lambda: self.asset_requested.emit(self.asset))
        top.addWidget(self.open)
        layout.addLayout(top)
        self.counts = _l("", "CaseMeta")
        layout.addWidget(self.counts)
        self.signals = QVBoxLayout()
        self.signals.setSpacing(6)
        layout.addLayout(self.signals)
        self.earlier_title = _l("Earlier reports here", "FieldLabel", wrap=False)
        layout.addWidget(self.earlier_title)
        self.earlier = QHBoxLayout()
        self.earlier.setSpacing(6)
        layout.addLayout(self.earlier)

    def show_context(self, context: Optional[AssetContext],
                     history: Optional[AssetHistory]) -> None:
        self.setVisible(context is not None and context.known and history is not None)
        if not self.isVisible():
            return
        self.asset = context.asset
        self.name.setText(context.asset)
        summary = history.summary()
        self.counts.setText(
            f"{summary['reports']} report(s): {summary['incidents']} incident(s), "
            f"{summary['near_misses']} near miss(es), {summary['hazards_seen']} hazard "
            f"observation(s) · {summary['precursors']} SIF precursor(s), "
            f"{summary['confirmed']} confirmed · {summary['open_actions']} open action(s)"
            + (f" · equipment named: {', '.join(history.equipment[:6])}"
               if history.equipment else ""))
        clear_layout(self.signals)
        _signal_rows(self.signals, context.signals, limit=6)
        clear_layout(self.earlier)
        prior = list(reversed(context.prior))[:6]
        self.earlier_title.setVisible(bool(prior))
        for record in prior:
            button = link_button(f"{record.reference}"
                                 + (f" · {record.when.strftime('%d %b')}" if record.when else ""))
            button.setToolTip(f"{KIND_LABEL.get(record.kind, record.kind)} · risk "
                              f"{record.risk:.0f} · {record.rule}")
            button.clicked.connect(lambda _c=False, ref=record.reference:
                                   self.report_requested.emit(ref))
            self.earlier.addWidget(button)
        self.earlier.addStretch(1)


ASSET_COLUMNS = (
    Col("asset", "Asset", 0, "strong"),
    Col("reports", "Reports", 76, "num", align="right"),
    Col("precursors", "SIF", 44, "num", align="right",
        style=lambda row: ("#DC2626" if row.get("precursors") else "", True)),
    Col("signal", "History", 120, "pill"),
    Col("holds", "Holds", 64, "num", align="right",
        style=lambda row: ("#DC2626" if row.get("holds") else "#9CA3AF", bool(row.get("holds")))),
    Col("last", "Last report", 104, "muted"),
)
TIMELINE_COLUMNS = (
    Col("when", "Date", 104, "mono"),
    Col("reference", "Ref", 92, "link"),
    Col("kind_label", "Kind", 118),
    Col("risk_score", "Risk", 86, "risk"),
    Col("failure", "Control failure", 0),
    Col("recommendation", "Recommendation", 196, "pill"),
)
ACTION_COLUMNS = (
    Col("title", "Corrective action", 0),
    Col("reference", "Ref", 90, "mono"),
    Col("state_pill", "State", 90, "pill"),
)


class AssetMemoryPage(Page):
    """Every asset's safety history, worst first."""

    asset_selected = pyqtSignal(str)
    report_requested = pyqtSignal(str)
    filter_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__("Asset Memory",
                         "Each asset's incidents, near misses, hazards, control failures and "
                         "corrective actions", scroll=True)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find an asset")
        self.search.setFixedWidth(200)
        self.search.textChanged.connect(lambda _text: self._apply())
        self.show_box = QComboBox()
        for key, label in (("all", "All assets"), ("signals", "With history signals"),
                           ("holds", "With work holds"), ("actions", "With open actions")):
            self.show_box.addItem(label, key)
        self.show_box.setFixedWidth(180)
        self.show_box.currentIndexChanged.connect(lambda _index: self._apply())
        self.clear_button = QPushButton("Clear")
        self.clear_button.setToolTip("Every asset, no search")
        self.clear_button.clicked.connect(self.clear_filters)
        self.search.setClearButtonEnabled(True)
        self.head.add(self.search)
        self.head.add(self.show_box)
        self.head.add(self.clear_button)

        self.stats = StatStrip(("Assets on record", "Recurring hazards",
                                "Repeated control failures", "Emerging SIF precursors",
                                "Work holds recommended"))
        self.body.addWidget(self.stats)

        row = QHBoxLayout()
        row.setSpacing(16)
        self.list_card = Card("Assets", "worst first", flush=True)
        self.table = DesignTable(ASSET_COLUMNS, row_height=40)
        self.table.row_clicked.connect(self._clicked)
        self.table.setMinimumHeight(560)
        self.list_card.add(self.table, 1)
        self.list_card.setFixedWidth(580)
        row.addWidget(self.list_card, 0, Qt.AlignmentFlag.AlignTop)

        detail = QVBoxLayout()
        detail.setSpacing(16)
        self.detail_card = Card("", "")
        self.title = _l("", "PageTitle", wrap=False)
        self.detail_card.add(self.title)
        self.facts = KeyValues(5)
        self.detail_card.add(self.facts)
        self.detail_card.add(_l("What the history says", "SubTitle", wrap=False))
        self.signal_box = QVBoxLayout()
        self.signal_box.setSpacing(8)
        self.detail_card.body.addLayout(self.signal_box)
        charts = QHBoxLayout()
        charts.setSpacing(16)
        left = QVBoxLayout()
        left.addWidget(_l("Hazards (energy sources)", "FieldLabel", wrap=False))
        self.hazard_bars = AxisBarChart("#1E3A5F", label_width=170)
        left.addWidget(self.hazard_bars)
        right = QVBoxLayout()
        right.addWidget(_l("Control failures", "FieldLabel", wrap=False))
        self.failure_bars = AxisBarChart("#7C3AED", label_width=190)
        right.addWidget(self.failure_bars)
        charts.addLayout(left, 1)
        charts.addLayout(right, 1)
        self.detail_card.body.addLayout(charts)
        detail.addWidget(self.detail_card)

        self.timeline_card = Card("Reports at this asset", "newest first", flush=True)
        self.timeline = DesignTable(TIMELINE_COLUMNS, row_height=34)
        self.timeline.setMinimumHeight(220)
        self.timeline.link_clicked.connect(self._open_report)
        self.timeline.row_activated.connect(self._open_report)
        self.timeline_card.add(self.timeline, 1)
        detail.addWidget(self.timeline_card)

        self.actions_card = Card("Corrective actions", "raised against its reports",
                                 flush=True)
        self.actions_table = DesignTable(ACTION_COLUMNS, row_height=32)
        self.actions_table.setMinimumHeight(120)
        self.actions_card.add(self.actions_table, 1)
        detail.addWidget(self.actions_card)
        detail.addStretch(1)
        holder = QWidget()
        holder.setLayout(detail)
        holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(holder, 1)
        self.body.addLayout(row)
        self.rows: List[Dict[str, object]] = []
        self.current = ""
        self.empty_note = "Analyse reports with a site or location to build the memory."

    # -- the list ---------------------------------------------------------------------

    def set_assets(self, rows: Sequence[Dict[str, object]]) -> None:
        self.rows = list(rows)
        self._apply()

    def _apply(self) -> None:
        needle = self.search.text().strip().lower()
        key = self.show_box.currentData()
        shown = [row for row in self.rows
                 if (not needle or needle in str(row.get("asset", "")).lower())
                 and (key == "all" or (key == "signals" and row.get("signals"))
                      or (key == "holds" and row.get("holds"))
                      or (key == "actions" and row.get("open_actions")))]
        self.table.set_rows(shown)
        names = [str(row.get("asset")) for row in shown]
        if self.current in names:
            self.table.selectRow(names.index(self.current))
            self.asset_selected.emit(self.current)
        elif shown:
            self.table.selectRow(0)
            self._clicked(0)
        else:
            self.current = ""
            self.asset_selected.emit("")

    def _clicked(self, index: int) -> None:
        if 0 <= index < len(self.table.rows):
            self.current = str(self.table.rows[index].get("asset", ""))
            self.asset_selected.emit(self.current)

    def select(self, name: str) -> None:
        self.current = name
        self.search.clear()
        self.show_box.setCurrentIndex(0)
        self._apply()

    def clear_filters(self) -> None:
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.show_box.setCurrentIndex(0)
        self._apply()

    def _open_report(self, row: int) -> None:
        if 0 <= row < len(self.timeline.rows):
            self.report_requested.emit(str(self.timeline.rows[row].get("reference", "")))

    # -- the chosen asset -------------------------------------------------------------------

    def set_stats(self, values) -> None:
        for cell, (value, note, alert) in zip(self.stats.cells, values):
            cell.set(value, note, alert=alert)

    def show_asset(self, history: Optional[AssetHistory],
                   timeline: Sequence[Dict[str, object]] = ()) -> None:
        clear_layout(self.signal_box)
        if history is None:
            self.title.setText("No asset chosen")
            self.facts.set_pairs([])
            self.signal_box.addWidget(_l(self.empty_note, "Hint"))
            self.hazard_bars.set_items([])
            self.failure_bars.set_items([])
            self.timeline.set_rows([])
            self.actions_table.set_rows([])
            return
        summary = history.summary()
        self.title.setText(history.name)
        self.facts.set_pairs([
            ("Reports", str(summary["reports"])),
            ("Incidents", str(summary["incidents"])),
            ("Near misses", str(summary["near_misses"])),
            ("Hazard observations", str(summary["hazards_seen"])),
            ("SIF precursors", f"{summary['precursors']} ({summary['confirmed']} confirmed)"),
            ("Peak risk", f"{summary['peak_risk']:.0f}"),
            ("Last report", str(summary["last"] or "-")),
            ("Open actions", f"{summary['open_actions']}"
             + (f" ({summary['overdue_actions']} overdue)" if summary["overdue_actions"] else "")),
            ("Equipment named", ", ".join(history.equipment[:8]) or "-"),
        ], stacked=True)
        if history.signals:
            _signal_rows(self.signal_box, history.signals, limit=10)
        else:
            self.signal_box.addWidget(_l("Nothing recurring in the last 90 days.", "Hint"))
        self.hazard_bars.set_items(history.hazards.most_common(6))
        self.failure_bars.set_items(history.failures.most_common(6))
        self.timeline.set_rows(list(timeline))
        self.actions_table.set_rows([
            {"title": action.title, "reference": action.reference,
             "state_pill": {"done": ("Done", "ok"), "overdue": ("Overdue", "fail")}.get(
                 action.state, ("Open", "warn"))} for action in history.actions])
