"""Compliance Action Items: the HSE calendar.

A month or a week of action items, one cell per day. A cell shows the first
few items and "N more"; "N more" opens that week, where every item shows.
Recurring items carry the repeat mark. An item that is done is struck through
in grey, one missed in the last fortnight is edged in red, and a corrective
action raised against a report is edged in navy.

Clicking an item opens it - what it is, who owns it, which report it answers
- with done / reopen / delete. Double-clicking a day adds an action on that
day. The view filter narrows the calendar to one person's items, the open or
overdue ones, the done ones, or the corrective actions.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sif.actions import CATEGORIES, RECURRENCE_LABELS, RECURRENCES, Occurrence

__all__ = ["ActionDetailDialog", "ActionDialog", "ActionsView", "FILTERS", "REPEAT_MARK"]

REPEAT_MARK = "⟳"          # ⟳ - the item repeats
DONE_MARK = "✓"            # ✓
WEEKDAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
FILTERS = (("all", "All"), ("mine", "Mine"), ("open", "Open"), ("overdue", "Overdue"),
           ("done", "Done"), ("corrective", "Corrective actions"))

#: Items a month cell shows before "N more".
MONTH_LIMIT = 3
MONTH_CELL_HEIGHT = 235
WEEK_CELL_HEIGHT = 480
HEADER_HEIGHT = 30


def week_start(day: date) -> date:
    """The Sunday on or before ``day`` - the calendar's weeks run Sun to Sat."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def keep(item: Occurrence, key: str, username: str) -> bool:
    if key == "mine":
        return item.action.owner == username
    if key == "open":
        return not item.done
    if key == "overdue":
        return item.overdue
    if key == "done":
        return item.done
    if key == "corrective":
        return bool(item.action.reference) or item.action.category == "Corrective action"
    return True


class ActionChip(QFrame):
    """One occurrence in a day cell; click to open it."""

    clicked = pyqtSignal(str, str)

    def __init__(self, item: Occurrence) -> None:
        super().__init__()
        self.item = item
        self.setObjectName("ActionChip")
        state = "done" if item.done else "overdue" if item.overdue else "open"
        self.setProperty("state", state)
        self.setProperty("kind", "corrective" if item.action.reference else "")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        text = item.action.title
        if item.done:
            text = f"{DONE_MARK} {text}"
        if item.action.recurring:
            text = f"{text}  {REPEAT_MARK}"
        self.label = QLabel(text)
        self.label.setObjectName("ChipText")
        self.label.setWordWrap(True)
        font = self.label.font()
        font.setStrikeOut(item.done)
        self.label.setFont(font)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.addWidget(self.label)
        tip = [item.action.title, RECURRENCE_LABELS.get(item.action.recurrence, ""),
               item.action.category]
        if item.action.owner:
            tip.append(f"Owner: {item.action.owner}")
        if item.action.reference:
            tip.append(f"Answers report {item.action.reference}")
        tip.append("Done" if item.done else "Overdue" if item.overdue else "Open")
        self.setToolTip("\n".join(part for part in tip if part))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt's name
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item.action.id, self.item.day.isoformat())
        super().mouseReleaseEvent(event)


class DayCell(QFrame):
    """One day: its number, its items, and "N more"."""

    chosen = pyqtSignal(str)
    add_requested = pyqtSignal(str)
    more_requested = pyqtSignal(str)
    action_requested = pyqtSignal(str, str)

    def __init__(self, day: date, items: Sequence[Occurrence], *, limit: Optional[int],
                 today: date, selected: bool, in_period: bool) -> None:
        super().__init__()
        self.day = day
        self.chips: List[ActionChip] = []
        self.setObjectName("DayCell")
        self.setProperty("today", day == today)
        self.setProperty("selected", selected)
        self.setProperty("outside", not in_period)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 4, 5, 6)
        layout.setSpacing(4)
        number = QLabel(str(day.day) if day.day != 1 else day.strftime("%d %b").lstrip("0"))
        number.setObjectName("DayNumber")
        layout.addWidget(number)

        shown = list(items) if limit is None else list(items)[:limit]
        for item in shown:
            chip = ActionChip(item)
            chip.clicked.connect(self.action_requested.emit)
            self.chips.append(chip)
            layout.addWidget(chip)
        hidden = len(items) - len(shown)
        self.more = None
        if hidden > 0:
            self.more = QPushButton(f"{hidden} more")
            self.more.setObjectName("MoreLink")
            self.more.setCursor(Qt.CursorShape.PointingHandCursor)
            self.more.clicked.connect(lambda: self.more_requested.emit(self.day.isoformat()))
            layout.addWidget(self.more, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.chosen.emit(self.day.isoformat())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.add_requested.emit(self.day.isoformat())
        super().mouseDoubleClickEvent(event)


class ActionsView(QWidget):
    """The calendar page. The window supplies the occurrences for :meth:`period`."""

    add_requested = pyqtSignal(str)            # ISO date the new action starts on
    action_requested = pyqtSignal(str, str)    # action id, ISO date of the occurrence
    period_changed = pyqtSignal()
    samples_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.mode = "month"
        self.anchor = date.today()
        self.selected = date.today()
        self.today = date.today()
        self.username = ""
        self.cells: Dict[date, DayCell] = {}
        self._items: List[Occurrence] = []

        self.add_button = QPushButton("Add New")
        self.add_button.setObjectName("Primary")
        self.add_button.clicked.connect(
            lambda: self.add_requested.emit(self.selected.isoformat()))
        self.today_button = QPushButton("Today")
        self.today_button.clicked.connect(self.go_today)
        self.back_button = QPushButton("<")
        self.back_button.setObjectName("CalendarStep")
        self.back_button.setToolTip("Previous")
        self.back_button.clicked.connect(lambda: self.step(-1))
        self.next_button = QPushButton(">")
        self.next_button.setObjectName("CalendarStep")
        self.next_button.setToolTip("Next")
        self.next_button.clicked.connect(lambda: self.step(1))
        self.period_label = QLabel("")
        self.period_label.setObjectName("CalendarPeriod")
        self.period_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        view_label = QLabel("View")
        view_label.setObjectName("Muted")
        self.filter = QComboBox()
        for key, label in FILTERS:
            self.filter.addItem(label, key)
        self.filter.currentIndexChanged.connect(lambda _: self._render())

        self.week_button = QPushButton("Week")
        self.month_button = QPushButton("Month")
        modes = QButtonGroup(self)
        modes.setExclusive(True)
        for button, mode in ((self.week_button, "week"), (self.month_button, "month")):
            button.setObjectName("ModeButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked, name=mode: self.set_mode(name))
            modes.addButton(button)
        self.month_button.setChecked(True)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.addWidget(self.add_button)
        toolbar.addSpacing(10)
        toolbar.addWidget(self.today_button)
        toolbar.addWidget(self.back_button)
        toolbar.addWidget(self.next_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.period_label)
        toolbar.addStretch(1)
        toolbar.addWidget(view_label)
        toolbar.addWidget(self.filter)
        toolbar.addSpacing(10)
        toolbar.addWidget(self.week_button)
        toolbar.addWidget(self.month_button)

        self.summary = QLabel("")
        self.summary.setObjectName("Muted")
        self.empty_note = QLabel("No action items yet. Add one with Add New, double-click a "
                                 "day, or start from an example field schedule.")
        self.empty_note.setObjectName("Faint")
        self.samples_button = QPushButton("Load an example schedule")
        self.samples_button.clicked.connect(self.samples_requested.emit)
        legend = QLabel(f"{REPEAT_MARK} repeats   ·   {DONE_MARK} done   ·   red edge: "
                        "overdue   ·   navy edge: answers a report")
        legend.setObjectName("Faint")

        status = QHBoxLayout()
        status.setSpacing(12)
        status.addWidget(self.summary)
        status.addWidget(self.empty_note)
        status.addWidget(self.samples_button)
        status.addStretch(1)
        status.addWidget(legend)

        self.grid_host = QWidget()
        self.grid_host.setObjectName("CalendarGrid")
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(6)
        self.grid.setVerticalSpacing(6)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(self.grid_host)

        board = QFrame()
        board.setObjectName("Panel")
        board_layout = QVBoxLayout(board)
        board_layout.setContentsMargins(14, 12, 14, 14)
        board_layout.setSpacing(10)
        board_layout.addLayout(toolbar)
        board_layout.addLayout(status)
        board_layout.addWidget(self.scroll, stretch=1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.addWidget(board)

    # -- the period shown --------------------------------------------------

    def period(self) -> Tuple[date, date]:
        """First and last day on screen: six whole weeks, or one."""
        if self.mode == "week":
            first = week_start(self.anchor)
            return first, first + timedelta(days=6)
        first = week_start(self.anchor.replace(day=1))
        return first, first + timedelta(days=41)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        (self.week_button if mode == "week" else self.month_button).setChecked(True)
        self.period_changed.emit()

    def step(self, direction: int) -> None:
        if self.mode == "week":
            self.anchor += timedelta(days=7 * direction)
        else:
            month = self.anchor.month - 1 + direction
            self.anchor = date(self.anchor.year + month // 12, month % 12 + 1, 1)
        self.period_changed.emit()

    def go_today(self) -> None:
        self.anchor = self.selected = date.today()
        self.period_changed.emit()

    def open_week(self, iso: str) -> None:
        """"N more": the week holding that day, where every item shows."""
        self.anchor = self.selected = date.fromisoformat(iso)
        self.set_mode("week")

    def select_day(self, iso: str) -> None:
        self.selected = date.fromisoformat(iso)
        for day, cell in self.cells.items():
            cell.setProperty("selected", day == self.selected)
            cell.style().unpolish(cell)
            cell.style().polish(cell)

    # -- state from the window -----------------------------------------------

    def set_user(self, username: str) -> None:
        self.username = username

    def set_editable(self, allowed: bool) -> None:
        self.add_button.setEnabled(allowed)
        self.samples_button.setEnabled(allowed)
        self.add_button.setToolTip("" if allowed else "Your role can view action items only.")

    @property
    def filter_key(self) -> str:
        return str(self.filter.currentData() or "all")

    def show_occurrences(self, items: Sequence[Occurrence], *, today: Optional[date] = None,
                         total_actions: int = 0) -> None:
        self.today = today or date.today()
        self._items = list(items)
        self.empty_note.setVisible(total_actions == 0)
        self.samples_button.setVisible(total_actions == 0)
        self.summary.setVisible(total_actions > 0)
        self._render()

    def visible_items(self) -> List[Occurrence]:
        return [item for item in self._items if keep(item, self.filter_key, self.username)]

    def _render(self) -> None:
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()
            if widget is not None:
                # Off the screen now, not whenever the deferred delete runs:
                # several renders in one burst would otherwise stack up.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.cells = {}
        first, last = self.period()
        if self.mode == "week":
            self.period_label.setText(
                f"{first.strftime('%d %b').lstrip('0')} - {last.strftime('%d %b %Y').lstrip('0')}")
        else:
            self.period_label.setText(self.anchor.strftime("%B %Y"))

        by_day: Dict[date, List[Occurrence]] = {}
        for item in self.visible_items():
            by_day.setdefault(item.day, []).append(item)

        for column, name in enumerate(WEEKDAYS):
            label = QLabel(name)
            label.setObjectName("WeekdayName")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.addWidget(label, 0, column)
            self.grid.setColumnStretch(column, 1)

        limit = None if self.mode == "week" else MONTH_LIMIT
        cell_height = WEEK_CELL_HEIGHT if self.mode == "week" else MONTH_CELL_HEIGHT
        day = first
        while day <= last:
            index = (day - first).days
            in_period = self.mode == "week" or day.month == self.anchor.month
            cell = DayCell(day, by_day.get(day, []), limit=limit, today=self.today,
                           selected=day == self.selected, in_period=in_period)
            cell.setMinimumHeight(cell_height)
            cell.chosen.connect(self.select_day)
            cell.add_requested.connect(self.add_requested.emit)
            cell.more_requested.connect(self.open_week)
            cell.action_requested.connect(self.action_requested.emit)
            self.grid.addWidget(cell, 1 + index // 7, index % 7)
            self.cells[day] = cell
            day += timedelta(days=1)
        # New cells are not shown yet, so the layout would measure them as
        # nothing and the scroll area would squeeze the rows flat; the height
        # the rows need is set outright.
        rows = ((last - first).days + 1) // 7
        spacing = self.grid.verticalSpacing()
        self.grid_host.setMinimumHeight(HEADER_HEIGHT + rows * (cell_height + spacing))

        shown = self.visible_items()
        due_today = [item for item in self._items if item.day == self.today]
        overdue = [item for item in self._items if item.overdue]
        done = sum(1 for item in shown if item.done)
        self.summary.setText(
            f"{len(shown)} on screen  ·  {done} done  ·  today: "
            f"{sum(1 for item in due_today if not item.done)} due  ·  "
            f"{len(overdue)} overdue")


class ActionDialog(QDialog):
    """A new compliance action: what, when, how often, whose, and for which report."""

    def __init__(self, stylesheet: str = "", parent: Optional[QWidget] = None, *,
                 day: Optional[date] = None, owners: Sequence[Tuple[str, str]] = (),
                 owner: str = "", references: Sequence[Tuple[str, str]] = (),
                 reference: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Add a compliance action")
        self.setMinimumWidth(520)
        if stylesheet:
            self.setStyleSheet(stylesheet)
        self.title = QLineEdit()
        self.title.setPlaceholderText("What has to be done - e.g. Gas test before hot work")
        self.start = QDateEdit()
        self.start.setCalendarPopup(True)
        self.start.setDisplayFormat("dd MMM yyyy")
        start = day or date.today()
        self.start.setDate(QDate(start.year, start.month, start.day))
        self.recurrence = QComboBox()
        for key in RECURRENCES:
            self.recurrence.addItem(RECURRENCE_LABELS[key], key)
        self.ends = QCheckBox("Stops repeating on")
        self.until = QDateEdit()
        self.until.setCalendarPopup(True)
        self.until.setDisplayFormat("dd MMM yyyy")
        self.until.setDate(self.start.date().addMonths(3))
        self.until.setEnabled(False)
        self.ends.toggled.connect(self.until.setEnabled)
        ends_row = QHBoxLayout()
        ends_row.addWidget(self.ends)
        ends_row.addWidget(self.until, stretch=1)
        self.recurrence.currentIndexChanged.connect(self._sync_repeat)
        self.category = QComboBox()
        self.category.addItems(CATEGORIES)
        self.owner = QComboBox()
        for username, label in owners:
            self.owner.addItem(label, username)
        if owner:
            self.owner.setCurrentIndex(max(0, self.owner.findData(owner)))
        self.reference = QComboBox()
        self.reference.addItem("None", "")
        for ref, label in references:
            self.reference.addItem(label, ref)
        if reference:
            self.reference.setCurrentIndex(max(0, self.reference.findData(reference)))
            self.category.setCurrentText("Corrective action")
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Optional: how, where, what counts as done.")
        self.notes.setFixedHeight(70)
        self.error = QLabel("")
        self.error.setObjectName("Faint")

        form = QFormLayout()
        form.setSpacing(8)
        form.addRow("Title", self.title)
        form.addRow("First date", self.start)
        form.addRow("Repeats", self.recurrence)
        form.addRow("", ends_row)
        form.addRow("Category", self.category)
        form.addRow("Owner", self.owner)
        form.addRow("Answers report", self.reference)
        form.addRow("Notes", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addWidget(buttons)
        self._sync_repeat()

    def _sync_repeat(self) -> None:
        repeats = self.recurrence.currentData() != "once"
        self.ends.setEnabled(repeats)
        self.until.setEnabled(repeats and self.ends.isChecked())

    def _accept(self) -> None:
        if not self.title.text().strip():
            self.error.setText("An action needs a title.")
            return
        self.accept()

    def values(self) -> Dict[str, object]:
        until = ""
        if self.recurrence.currentData() != "once" and self.ends.isChecked():
            until = self.until.date().toPyDate()
        return {"title": self.title.text().strip(),
                "start": self.start.date().toPyDate(),
                "recurrence": str(self.recurrence.currentData()),
                "until": until,
                "category": self.category.currentText(),
                "owner": str(self.owner.currentData() or ""),
                "reference": str(self.reference.currentData() or ""),
                "notes": self.notes.toPlainText().strip()}


class ActionDetailDialog(QDialog):
    """One occurrence: what it is, and done / reopen / delete."""

    def __init__(self, item: Occurrence, stylesheet: str = "",
                 parent: Optional[QWidget] = None, *, editable: bool = True,
                 owner_label: str = "") -> None:
        super().__init__(parent)
        self.choice = ""
        action = item.action
        self.setWindowTitle(action.title)
        self.setMinimumWidth(460)
        if stylesheet:
            self.setStyleSheet(stylesheet)
        heading = QLabel(action.title)
        heading.setObjectName("SectionTitle")
        heading.setWordWrap(True)
        form = QFormLayout()
        form.setSpacing(6)
        state = "Done" if item.done else "Overdue" if item.overdue else "Open"
        rows = [("Date", item.day.strftime("%A %d %B %Y")),
                ("Status", state + (f" - {action.done[item.day.isoformat()]}" if item.done else "")),
                ("Repeats", RECURRENCE_LABELS.get(action.recurrence, action.recurrence)
                 + (f", until {action.until}" if action.until else "")),
                ("Category", action.category),
                ("Owner", owner_label or action.owner or "-"),
                ("Answers report", action.reference or "-"),
                ("Added by", f"{action.created_by or '-'}  {action.created_at.replace('T', ' ')}")]
        if action.notes:
            rows.append(("Notes", action.notes))
        for name, value in rows:
            label = QLabel(value)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(name, label)

        self.done_button = QPushButton("Reopen" if item.done else "Mark done")
        self.done_button.setObjectName("" if item.done else "Primary")
        self.done_button.clicked.connect(lambda: self._choose("reopen" if item.done else "done"))
        self.delete_button = QPushButton("Delete the action" + (" (every date)"
                                                                if action.recurring else ""))
        self.delete_button.clicked.connect(lambda: self._choose("delete"))
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        for button in (self.done_button, self.delete_button):
            button.setEnabled(editable)
        buttons = QHBoxLayout()
        buttons.addWidget(self.done_button)
        buttons.addWidget(self.delete_button)
        buttons.addStretch(1)
        buttons.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addLayout(form)
        layout.addSpacing(6)
        layout.addLayout(buttons)

    def _choose(self, choice: str) -> None:
        self.choice = choice
        self.accept()
