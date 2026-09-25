"""Activity and access: who is using the console, and what each of them did.

The audit trail already recorded everything; what it could not do was say
*who*, and it could not be read person by person. This page is that reading:

* **People** - every account, with what the trail says each has done: how many
  times they signed in, how many reports they analysed, how many cases they
  decided. An administrator manages the accounts from here.
* **Activity** - the trail itself, filterable to one person.
* **Integrity** - whether the chain of entries is still intact, and the head
  hash an auditor can note down to prove later that nothing has been removed.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QScrollArea,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sif.accounts import ROLE_LABELS, ROLES
from ui.components import DataTable, Panel

__all__ = ["ActivityView", "AccountDialog", "PEOPLE_COLUMNS", "ACTIVITY_COLUMNS"]

PEOPLE_COLUMNS = (
    ("User", "username", 130),
    ("Name", "full_name", 180),
    ("Role", "role_label", 120),
    ("Last sign-in", "last_login", 150),
    ("Sign-ins", "sign_ins", 76),
    ("Reports analysed", "analysed", 132),
    ("Decisions", "decisions", 86),
    ("Status", "status", 90),
)
PEOPLE_FLEX = ("full_name",)

ACTIVITY_COLUMNS = (
    ("Time", "when", 150),
    ("User", "user", 120),
    ("Role", "role", 90),
    ("Action", "action", 180),
    ("Detail", "summary", 420),
)
ACTIVITY_FLEX = ("summary",)

#: The actions that count toward a person's tally on the People table.
SIGN_IN = "signed in"
ANALYSED = "reports analysed"
DECIDED = "review decision"


def tally(rows: Sequence[Dict[str, object]]) -> Dict[str, Dict[str, int]]:
    """Per user: sign-ins, reports analysed, decisions - read off the trail."""
    people: Dict[str, Dict[str, int]] = {}
    for row in rows:
        user = str(row.get("user") or "")
        if not user:
            continue
        counts = people.setdefault(user, {"sign_ins": 0, "analysed": 0, "decisions": 0})
        action = row.get("action")
        detail = row.get("detail") if isinstance(row.get("detail"), dict) else {}
        if action == SIGN_IN:
            counts["sign_ins"] += 1
        elif action == ANALYSED:
            try:
                counts["analysed"] += int(detail.get("count", 0) or 0)
            except (TypeError, ValueError):
                pass
        elif action == DECIDED:
            counts["decisions"] += 1
    return people


class AccountDialog(QDialog):
    """Name, username and role for a new account. The password is issued."""

    def __init__(self, stylesheet: str = "", parent: Optional[QWidget] = None,
                 roles: Optional[Sequence[str]] = None,
                 labels: Optional[Dict[str, str]] = None) -> None:
        """``roles`` and ``labels`` narrow and rename the choice for a build
        whose role model is simpler than the account store's."""
        super().__init__(parent)
        self.setWindowTitle("Add an account")
        if stylesheet:
            self.setStyleSheet(stylesheet)
        self.full_name = QLineEdit()
        self.full_name.setPlaceholderText("Full name")
        self.username = QLineEdit()
        self.username.setPlaceholderText("Username - e.g. r.sharma")
        self.role = QComboBox()
        choices = list(roles or ROLES)
        for role in choices:
            self.role.addItem((labels or ROLE_LABELS).get(role, role), role)
        self.role.setCurrentIndex(choices.index("analyst") if "analyst" in choices else 0)
        note = QLabel("A one-time password is issued when you press OK. The person "
                      "chooses their own the first time they sign in.")
        note.setObjectName("Faint")
        note.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for widget in (self.full_name, self.username, self.role, note, buttons):
            layout.addWidget(widget)

    def values(self):
        return (self.username.text().strip(), self.full_name.text().strip(),
                str(self.role.currentData()))


class ActivityView(QWidget):
    """People, their activity, and the integrity of the record."""

    #: Below this the page scrolls instead of squeezing its tables flat.
    MIN_CONTENT_HEIGHT = 760

    add_requested = pyqtSignal()
    reset_requested = pyqtSignal(str)
    role_requested = pyqtSignal(str)
    toggle_requested = pyqtSignal(str)
    verify_requested = pyqtSignal()
    filter_changed = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._people: List[Dict[str, object]] = []

        # -- people ----------------------------------------------------------
        self.people_table = DataTable(PEOPLE_COLUMNS, flex_keys=PEOPLE_FLEX)
        self.add_button = QPushButton("Add an account")
        self.add_button.setObjectName("Primary")
        self.add_button.clicked.connect(self.add_requested.emit)
        self.reset_button = QPushButton("Issue a new password")
        self.reset_button.clicked.connect(lambda: self._with_selected(self.reset_requested))
        self.role_button = QPushButton("Change role")
        self.role_button.clicked.connect(lambda: self._with_selected(self.role_requested))
        self.toggle_button = QPushButton("Disable / enable")
        self.toggle_button.clicked.connect(lambda: self._with_selected(self.toggle_requested))
        self.admin_note = QLabel("")
        self.admin_note.setObjectName("Faint")
        self.admin_note.setWordWrap(True)

        people_buttons = QHBoxLayout()
        people_buttons.setSpacing(8)
        for button in (self.add_button, self.reset_button, self.role_button,
                       self.toggle_button):
            people_buttons.addWidget(button)
        people_buttons.addStretch(1)

        people = Panel("People")
        self.people_panel = people
        # The actions sit above the list, so a long list never pushes them
        # below the fold.
        people.body.addLayout(people_buttons)
        people.add(self.admin_note)
        people.add(self.people_table, stretch=1)

        # -- activity --------------------------------------------------------
        self.filter = QComboBox()
        self.filter.addItem("Everyone", "")
        self.filter.currentIndexChanged.connect(
            lambda: self.filter_changed.emit(str(self.filter.currentData() or "")))
        self.activity_table = DataTable(ACTIVITY_COLUMNS, flex_keys=ACTIVITY_FLEX)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        show = QLabel("Show")
        show.setObjectName("Muted")
        filter_row.addWidget(show)
        filter_row.addWidget(self.filter, stretch=1)

        activity = Panel("Activity")
        self.activity_panel = activity
        activity.body.addLayout(filter_row)
        activity.add(self.activity_table, stretch=1)

        # -- integrity -------------------------------------------------------
        self.chain_label = QLabel("The trail has not been checked yet.")
        self.chain_label.setWordWrap(True)
        self.head_label = QLabel("")
        self.head_label.setObjectName("Faint")
        self.head_label.setWordWrap(True)
        self.head_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.verify_button = QPushButton("Verify the trail")
        self.verify_button.clicked.connect(self.verify_requested.emit)

        integrity_row = QHBoxLayout()
        integrity_row.setSpacing(12)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(self.chain_label)
        text.addWidget(self.head_label)
        integrity_row.addLayout(text, stretch=1)
        integrity_row.addWidget(self.verify_button)
        integrity = Panel("Integrity of the record")
        self.integrity_panel = integrity
        integrity.body.addLayout(integrity_row)

        # Scrolls rather than squeezes: on a 1366x768 plant laptop two tables
        # and a status panel do not fit, and a squeezed table is unusable.
        content = QWidget()
        content.setMinimumHeight(self.MIN_CONTENT_HEIGHT)
        inner = QVBoxLayout(content)
        inner.setContentsMargins(18, 16, 18, 16)
        inner.setSpacing(12)
        inner.addWidget(people, stretch=3)
        inner.addWidget(activity, stretch=4)
        inner.addWidget(integrity)

        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(QFrame.Shape.NoFrame)
        scroller.setWidget(content)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroller)

    # -- controller interface ----------------------------------------------

    def set_admin(self, allowed: bool) -> None:
        """Account management is for administrators; everyone may read."""
        for button in (self.add_button, self.reset_button, self.role_button,
                       self.toggle_button):
            button.setVisible(allowed)
        self.admin_note.setText(
            "" if allowed else "Accounts are managed by an administrator.")
        self.admin_note.setVisible(not allowed)

    def set_people(self, rows: Sequence[Dict[str, object]]) -> None:
        self._people = list(rows)
        self.people_table.set_rows(self._people)
        current = str(self.filter.currentData() or "")
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.addItem("Everyone", "")
        for row in self._people:
            self.filter.addItem(f"{row.get('full_name')} ({row.get('username')})",
                                row.get("username"))
        index = max(0, self.filter.findData(current))
        self.filter.setCurrentIndex(index)
        self.filter.blockSignals(False)

    def set_activity(self, rows: Sequence[Dict[str, object]]) -> None:
        self.activity_table.set_rows(list(rows))

    def set_chain(self, summary: str, head: str, intact: bool) -> None:
        self.chain_label.setText(summary)
        self.chain_label.setStyleSheet("" if intact else "color: #ff5c52; font-weight: 700;")
        self.head_label.setText(
            f"Head of the chain: {head}" if head else "No chained entries yet.")

    def selected_username(self) -> str:
        row = self.people_table.currentRow()
        if 0 <= row < len(self._people):
            return str(self._people[row].get("username", ""))
        return ""

    def _with_selected(self, signal) -> None:
        username = self.selected_username()
        if username:
            signal.emit(username)
