"""Compliance Action Items, as the revamp lays them out.

The two-workspace calendar - the same store, recurrences, done-per-date and
dialogs - with the revamp's look: chips filled in their category's colour,
today's date in a navy circle, two items a cell then "+N more", and a column
beside the calendar with what is coming up and the categories, each of which
filters the calendar when clicked.
"""

from __future__ import annotations

from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sif.actions import CATEGORIES
from ui.sentra_theme import CATEGORY_COLOURS
from ui4.calendar import ActionsView, Occurrence
from ui4.kit import clear_layout

__all__ = ["SentraActions"]


class SentraActions(ActionsView):
    month_limit = 2
    month_cell_height = 104
    week_cell_height = 420

    def __init__(self) -> None:
        super().__init__()
        self.category = ""
        self.grid.setHorizontalSpacing(0)
        self.grid.setVerticalSpacing(0)

        # Category filter and the page-level controls the revamp puts in the head.
        self.category_box = QComboBox()
        self.category_box.addItem("All categories", "")
        for name in CATEGORIES:
            self.category_box.addItem(name, name)
        self.category_box.setFixedWidth(170)
        self.category_box.currentIndexChanged.connect(
            lambda _i: self.set_category(str(self.category_box.currentData() or "")))
        self.add_top = QPushButton("+  Add New")
        self.add_top.setObjectName("Primary")
        self.add_top.clicked.connect(lambda: self.add_requested.emit(self.selected.isoformat()))
        self.legend.setText("⟳ repeats  ·  ✓ done  ·  "
                            "<span style='color:#EF4444'>red edge</span>: overdue")
        self.legend.setObjectName("PageCaption")

        # The column beside the calendar.
        self.upcoming = QFrame()
        self.upcoming.setObjectName("Card")
        up = QVBoxLayout(self.upcoming)
        up.setContentsMargins(0, 0, 0, 0)
        up.setSpacing(0)
        head = QFrame()
        head.setObjectName("CardHead")
        head_row = QHBoxLayout(head)
        head_row.setContentsMargins(16, 10, 16, 10)
        self.upcoming_title = QLabel("Upcoming")
        self.upcoming_title.setObjectName("CardTitle")
        head_row.addWidget(self.upcoming_title)
        up.addWidget(head)
        self.upcoming_list = QVBoxLayout()
        self.upcoming_list.setContentsMargins(0, 0, 0, 0)
        self.upcoming_list.setSpacing(0)
        up.addLayout(self.upcoming_list)

        legend = QFrame()
        legend.setObjectName("Card")
        cats = QVBoxLayout(legend)
        cats.setContentsMargins(16, 14, 16, 14)
        cats.setSpacing(4)
        title = QLabel("Categories")
        title.setObjectName("LegendTitle")
        cats.addWidget(title)
        self.category_buttons = {}
        for name in CATEGORIES:
            button = QPushButton(f"  {name}")
            button.setObjectName("CategoryButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton#CategoryButton { text-align: left; border: none; padding: 4px 8px;"
                " background: transparent; }"
                "QPushButton#CategoryButton:checked { background: #F3F4F6; }")
            button.setIcon(self._swatch(CATEGORY_COLOURS.get(name, "#6B7280")))
            button.clicked.connect(lambda _c, n=name: self.set_category(
                "" if self.category == n else n))
            self.category_buttons[name] = button
            cats.addWidget(button)

        side = QVBoxLayout()
        side.setSpacing(12)
        side.addWidget(self.upcoming)
        side.addWidget(legend)
        side.addStretch(1)
        side_box = QWidget()
        side_box.setFixedWidth(260)
        side_box.setLayout(side)

        outer = self.layout()
        outer.removeWidget(self.board)
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(self.board, 1)
        row.addWidget(side_box)
        outer.addLayout(row)

    @staticmethod
    def _swatch(colour: str):
        from PyQt6.QtGui import QColor, QIcon, QPixmap

        pixmap = QPixmap(12, 12)
        pixmap.fill(QColor(colour))
        return QIcon(pixmap)

    def head_widgets(self) -> List[QWidget]:
        """What the page head carries in the revamp: legend, filters, view, add."""
        return [self.legend, self.category_box, self.filter, self.week_button,
                self.month_button, self.add_top]

    def set_category(self, name: str) -> None:
        self.category = name
        index = self.category_box.findData(name)
        self.category_box.blockSignals(True)
        self.category_box.setCurrentIndex(max(0, index))
        self.category_box.blockSignals(False)
        for key, button in self.category_buttons.items():
            button.setChecked(key == name)
        self._render()

    def visible_items(self) -> List[Occurrence]:
        items = super().visible_items()
        return [item for item in items if not self.category or item.action.category == self.category]

    def _render(self) -> None:
        super()._render()
        for day, cell in self.cells.items():
            number = cell.findChild(QLabel, "DayNumber")
            if number is not None:
                number.setText(str(day.day))
                number.setFixedSize(24, 22)
                number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            width = max(60, self.grid_host.width() // 7 - 18)
            for chip in cell.chips:
                chip.label.setWordWrap(False)
                chip.layout().setContentsMargins(6, 1, 6, 1)
                metrics = chip.label.fontMetrics()
                chip.label.setText(metrics.elidedText(chip.item.action.title,
                                                      Qt.TextElideMode.ElideRight, width))
            if cell.more is not None and not cell.more.text().startswith("+"):
                cell.more.setText("+" + cell.more.text())
        self._render_upcoming()

    def _render_upcoming(self) -> None:
        clear_layout(self.upcoming_list)
        today = self.today
        self.upcoming_title.setText(f"Upcoming · {self.anchor.strftime('%b %Y')}")
        coming = [item for item in self.visible_items() if item.day >= today and not item.done]
        coming.sort(key=lambda item: (item.day, item.action.title.lower()))
        if not coming:
            note = QLabel("Nothing coming up in this view.")
            note.setObjectName("CardCaption")
            note.setContentsMargins(16, 12, 16, 12)
            self.upcoming_list.addWidget(note)
        for item in coming[:6]:
            row = QFrame()
            row.setObjectName("UpcomingRow")
            line = QHBoxLayout(row)
            line.setContentsMargins(16, 8, 16, 8)
            line.setSpacing(12)
            when = QVBoxLayout()
            when.setSpacing(0)
            month = QLabel(item.day.strftime("%b"))
            month.setObjectName("UpcomingMonth")
            day = QLabel(str(item.day.day))
            day.setObjectName("UpcomingDayToday" if item.day == today else "UpcomingDay")
            for label in (month, day):
                label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                when.addWidget(label)
            line.addLayout(when)
            words = QVBoxLayout()
            words.setSpacing(1)
            colour = CATEGORY_COLOURS.get(item.action.category, "#6B7280")
            title = QLabel(f"<span style='color:{colour}'>●</span>&nbsp; {item.action.title}")
            title.setObjectName("UpcomingTitle")
            title.setWordWrap(True)
            words.addWidget(title)
            sub = QLabel(item.action.category + ("  ·  overdue" if item.overdue else ""))
            sub.setObjectName("UpcomingSub")
            words.addWidget(sub)
            line.addLayout(words, 1)
            self.upcoming_list.addWidget(row)
