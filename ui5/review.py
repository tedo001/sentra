"""HSE Review, as the revamp lays it out.

A narrow case list - reference and date, risk, trigger - beside the case,
whose engine pills are filled and whose decision buttons sit under the
report. The two-workspace page's filters (open, critical, disagreement,
needs info, reviewed, over 7 days) move from tabs to a list in the head, and
the evidence and reasoning stay beneath the report, so nothing is lost.
"""

from __future__ import annotations

from typing import Dict

from PyQt6.QtWidgets import QComboBox

from ui4.kit import Col
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
    def __init__(self) -> None:
        super().__init__()
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
        for _key, label in FILTERS:
            self.show_box.addItem(label)
        self.show_box.currentIndexChanged.connect(self.tabs.setCurrentIndex)
        self.head.actions.insertWidget(0, self.show_box)

    def set_counts(self, counts: Dict[str, int]) -> None:
        super().set_counts(counts)
        for index, (key, label) in enumerate(FILTERS):
            self.show_box.setItemText(index, f"{label} ({counts.get(key, 0)})")
