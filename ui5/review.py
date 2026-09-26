"""HSE Review, as the revamp lays it out.

A narrow case list - reference and date, risk, trigger - beside the case,
whose engine pills are filled and whose decision buttons sit under the
report. The two-workspace page's filters (open, critical, disagreement,
needs info, reviewed, over 7 days) move from tabs to a list in the head, and
the evidence and reasoning stay beneath the report, so nothing is lost.
"""

from __future__ import annotations

from typing import Dict

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox

from ui4.kit import Col, Segmented
from ui4.review import FILTERS, ReviewPage

__all__ = ["SentraReview", "SENTRA_CASE_COLUMNS"]


def _ref_and_date(row: Dict[str, object]) -> str:
    return f"{row.get('reference', '')}\n{str(row.get('date', '')).replace(chr(10), ' ')}"


SENTRA_CASE_COLUMNS = (
    Col("reference", "Ref", 116, "mono", value=_ref_and_date,
        style=lambda row: ("#1E3A5F", True)),
    Col("risk_score", "Risk", 86, "risk"),
    Col("trigger", "Trigger", 0),
)


class SentraReview(ReviewPage):
    #: Work-hold cases get a filter of their own, after Open.
    filters = FILTERS[:1] + (("hold", "Work-hold"),) + FILTERS[1:]
    mode_changed = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        from .trail import CaseHistory, DecisionTrail
        # The recommendation heads the case; the asset's memory follows the report.
        from .assets import AssetMemoryPanel, RecommendationPanel

        content = self.case.content
        self.recommendation = RecommendationPanel()
        content.insertWidget(0, self.recommendation)
        self.memory = AssetMemoryPanel()
        content.insertWidget(content.indexOf(self.case.text) + 1, self.memory)
        self.recommendation.hide()
        self.memory.hide()
        # What was decided on this report before, under the report and its memory.
        self.history = CaseHistory()
        content.insertWidget(content.indexOf(self.memory) + 1, self.history)
        # Cases, or the whole decision trail.
        self.trail = DecisionTrail()
        self.trail.export_requested.connect(self.export_requested.emit)
        self.trail.hide()
        self.body.addWidget(self.trail, 1)
        self.mode = Segmented((("cases", "Cases"), ("trail", "Decision trail")), "cases")
        self.mode.changed.connect(self.show_mode)
        self.head.actions.insertWidget(0, self.mode)
        from PyQt6.QtWidgets import QPushButton

        self.clear_button = QPushButton("Clear")
        self.clear_button.setToolTip("Clear the search and show every open case")
        self.clear_button.clicked.connect(self.clear_filters)
        self.head.actions.insertWidget(self.head.actions.indexOf(self.search) + 1,
                                       self.clear_button)
        self.search.setClearButtonEnabled(True)
        # The list: three columns, as narrow as the revamp draws it.
        from ui4.kit import DesignTable

        layout = self.list_card.body
        layout.removeWidget(self.table)
        self.table.setParent(None)
        self.table = DesignTable(SENTRA_CASE_COLUMNS, row_height=52, wrap=True)
        self.table.row_clicked.connect(self._clicked)
        self.list_card.add(self.table, 1)
        self.list_card.setFixedWidth(312)
        # Filters: the tabs stay (they hold the state) but hide behind a list.
        self.tabs.parentWidget().hide()
        self.show_box = QComboBox()
        self.show_box.setFixedWidth(170)
        for _key, label in self.filters:
            self.show_box.addItem(label)
        self.show_box.currentIndexChanged.connect(self.tabs.setCurrentIndex)
        # A case opened from elsewhere may switch the filter; the list says so.
        self.tabs.currentChanged.connect(self.show_box.setCurrentIndex)
        self.head.actions.insertWidget(0, self.show_box)

    def clear_filters(self) -> None:
        self.search.clear()
        self.show_box.setCurrentIndex(0)

    def show_mode(self, mode: str) -> None:
        cases = mode != "trail"
        if self.mode.current != mode:
            self.mode.select(mode)
        for widget in (self.list_card, self.case_card, self.show_box, self.search,
                       self.clear_button):
            widget.setVisible(cases)
        self.trail.setVisible(not cases)
        # The hidden half gives up its share of the page to the shown one.
        for index in range(self.body.count()):
            item = self.body.itemAt(index)
            if item.layout() is not None and item.layout().indexOf(self.case_card) >= 0:
                self.body.setStretch(index, 1 if cases else 0)
            elif item.widget() is self.trail:
                self.body.setStretch(index, 0 if cases else 1)
        self.mode_changed.emit(mode)

    def set_counts(self, counts: Dict[str, int]) -> None:
        super().set_counts(counts)
        for index, (key, label) in enumerate(self.filters):
            self.show_box.setItemText(index, f"{label} ({counts.get(key, 0)})")
