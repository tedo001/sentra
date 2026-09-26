"""New HSE Login - create and manage accounts.

From the design: every account with its email, role, site, status and last
sign-in, and its three actions in the row (change role, reset password,
disable or enable); and the form that creates one - name, email, role, site,
department, the permissions the role carries, and whether it starts active.

The design's "email a first sign-in link" needs a mail service SENTRA does
not have, so the form issues a one-time password instead: shown once to the
administrator, changed by the person at their first sign-in.
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QRadioButton,
    QWidget,
)

from .kit import Card, Col, DesignTable, Page

__all__ = ["ACCOUNT_COLUMNS", "AccountsPage", "ROLE_CHOICES", "username_for"]

#: What an administrator can create here, as stored and as shown.
ROLE_CHOICES = (("viewer", "Viewer"), ("reviewer", "HSE Analyst"), ("admin", "Administrator"))
PERMISSIONS = {
    "viewer": (("View reports, evidence and dashboards", True),
               ("Upload and ingest documents", False), ("Record review decisions", False),
               ("Engines, settings, logs and accounts", False)),
    "reviewer": (("View reports, evidence and dashboards", True),
                 ("Upload and ingest documents", True), ("Record review decisions", True),
                 ("Engines, settings, logs and accounts", False)),
    "admin": (("View reports, evidence and dashboards", True),
              ("Upload and ingest documents", False), ("Record review decisions", False),
              ("Engines, settings, logs and accounts", True)),
}

ACCOUNT_COLUMNS = (
    Col("full_name", "Name", 110, "strong"),
    Col("email", "Email", 0, "mono"),
    Col("role_label", "Role", 106),
    Col("site", "Site", 98),
    Col("status", "Status", 94, "pill"),
    Col("last", "Last sign-in", 98, "mono"),
    Col("actions", "Actions", 300),
)


def username_for(email: str, full_name: str) -> str:
    """A username from the email's local part, else from the name."""
    base = email.split("@")[0] if "@" in email else full_name
    base = re.sub(r"[^a-z0-9._-]+", ".", base.strip().lower()).strip("._-")
    return (base or "user")[:32]


class AccountsPage(Page):
    create_requested = pyqtSignal(dict)
    role_requested = pyqtSignal(str, str)
    reset_requested = pyqtSignal(str)
    toggle_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__("New HSE Login", "Create and manage HSE accounts · every change is "
                                          "written to the audit log")
        self.me = ""
        self.list = Card("Accounts", "", flush=True)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter by name or email")
        self.filter.setFixedWidth(208)
        self.filter.textChanged.connect(lambda _t: self._apply())
        self.list.add_head(self.filter)
        self.table = DesignTable(ACCOUNT_COLUMNS, row_height=50, wrap=True)
        self.list.add(self.table, 1)
        self.accounts: List[Dict[str, object]] = []

        self.form = Card("Create HSE account", "")
        self.form.setFixedWidth(392)
        self.full_name = self._field("Full name", QLineEdit(), "As on employee record")
        self.email = self._field("Email", QLineEdit(), "name@oilindia.in")
        pair = QGridLayout()
        pair.setHorizontalSpacing(8)
        pair.setVerticalSpacing(4)
        self.role = QComboBox()
        for value, label in ROLE_CHOICES:
            self.role.addItem(label, value)
        self.site = QComboBox()
        pair.addWidget(self._label("Role"), 0, 0)
        pair.addWidget(self._label("Site"), 0, 1)
        pair.addWidget(self.role, 1, 0)
        pair.addWidget(self.site, 1, 1)
        self.form.body.addLayout(pair)
        self.department = self._field("Department", QComboBox())
        self.form.add(self._label("Permissions from role"))
        self.permissions = QLabel("")
        self.permissions.setObjectName("PermissionBox")
        self.permissions.setTextFormat(Qt.TextFormat.RichText)
        self.form.add(self.permissions)
        follow = QLabel("Permissions follow the role. To change them, change the role.")
        follow.setObjectName("CardCaption")
        self.form.add(follow)
        self.form.add(self._label("Account status"))
        status = QHBoxLayout()
        self.active = QRadioButton("Active")
        self.inactive = QRadioButton("Disabled until enabled here")
        group = QButtonGroup(self)
        group.addButton(self.active)
        group.addButton(self.inactive)
        self.active.setChecked(True)
        status.addWidget(self.active)
        status.addWidget(self.inactive)
        status.addStretch(1)
        self.form.body.addLayout(status)
        self.one_time = QCheckBox("Issue a one-time password (changed at first sign-in)")
        self.one_time.setChecked(True)
        self.one_time.setEnabled(False)
        self.form.add(self.one_time)
        self.username_hint = QLabel("")
        self.username_hint.setObjectName("MonoFaint")
        self.form.add(self.username_hint)
        self.create = QPushButton("Create account…")
        self.create.setObjectName("Primary")
        self.create.setEnabled(False)
        self.create.clicked.connect(self._create)
        self.clear_form_button = QPushButton("Clear form")
        self.clear_form_button.setToolTip("Empty the form and start again")
        self.clear_form_button.clicked.connect(self.reset_form)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self.create, 1)
        buttons.addWidget(self.clear_form_button)
        self.form.body.addLayout(buttons)
        self.error = QLabel("")
        self.error.setObjectName("ErrorText")
        self.error.setWordWrap(True)
        self.form.add(self.error)
        self.form.body.addStretch(1)
        for field in (self.full_name, self.email):
            field.textChanged.connect(self._validate)
        self.role.currentIndexChanged.connect(self._validate)
        self._validate()

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self.list, 1)
        row.addWidget(self.form)
        self.body.addLayout(row, 1)

    # -- the form -------------------------------------------------------------------------

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    def _field(self, label: str, widget, placeholder: str = ""):
        self.form.add(self._label(label))
        if placeholder:
            widget.setPlaceholderText(placeholder)
        self.form.add(widget)
        return widget

    def reset_form(self) -> None:
        """The Clear form button: every field back to its starting value."""
        for field in (self.full_name, self.email):
            field.clear()
        for box in (self.role, self.site, self.department):
            box.setCurrentIndex(0)
        self.active.setChecked(True)
        self.error.clear()
        self._validate()

    def _validate(self) -> None:
        role = str(self.role.currentData())
        lines = "".join(
            f"<div style='margin:3px 0;color:{'#1F2328' if ok else '#8A8F95'}'>"
            f"{'&#10003;' if ok else '&mdash;'}&nbsp;&nbsp;{text}</div>"
            for text, ok in PERMISSIONS.get(role, ()))
        self.permissions.setText(lines)
        name, email = self.full_name.text().strip(), self.email.text().strip()
        valid_email = not email or re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email)
        self.username_hint.setText(f"username: {username_for(email, name)}" if name else "")
        self.error.setText("" if valid_email else "That does not look like an email address.")
        self.create.setEnabled(bool(name) and bool(valid_email))

    def _create(self) -> None:
        name, email = self.full_name.text().strip(), self.email.text().strip()
        self.create_requested.emit({
            "full_name": name, "email": email, "username": username_for(email, name),
            "role": str(self.role.currentData()), "site": self.site.currentText(),
            "department": self.department.currentText(), "active": self.active.isChecked()})

    def clear_form(self) -> None:
        self.full_name.clear()
        self.email.clear()
        self.active.setChecked(True)
        self.error.setText("")

    def set_error(self, text: str) -> None:
        self.error.setText(text)

    def set_choices(self, sites: Sequence[str], departments: Sequence[str]) -> None:
        for box, values in ((self.site, sites), (self.department, departments)):
            current = box.currentText()
            box.clear()
            box.addItems(list(values))
            if current in values:
                box.setCurrentText(current)

    # -- the list ------------------------------------------------------------------------

    def set_accounts(self, rows: Sequence[Dict[str, object]], me: str) -> None:
        self.me = me
        self.accounts = list(rows)
        active = sum(1 for row in rows if row.get("active"))
        self.list.caption.setText(f"{active} active · {len(rows) - active} disabled")
        self._apply()

    def _apply(self) -> None:
        needle = self.filter.text().strip().lower()
        shown = [row for row in self.accounts if not needle or needle in
                 f"{row.get('full_name')} {row.get('email')} {row.get('username')}".lower()]
        self.table.set_rows(shown)
        for index, row in enumerate(shown):
            self.table.setCellWidget(index, len(ACCOUNT_COLUMNS) - 1, self._actions(row))

    def _actions(self, row: Dict[str, object]) -> QWidget:
        holder = QWidget()
        line = QHBoxLayout(holder)
        line.setContentsMargins(4, 6, 4, 6)
        line.setSpacing(5)
        username = str(row.get("username"))
        if username == self.me:
            you = QLabel("You")
            you.setObjectName("CardCaption")
            line.addWidget(you)
            line.addStretch(1)
            return holder
        role = QPushButton("Change role")
        role.setObjectName("Small")
        role.clicked.connect(lambda _c, u=username, b=role, r=row: self._role_menu(u, b, r))
        reset = QPushButton("Reset password")
        reset.setObjectName("Small")
        reset.clicked.connect(lambda _c, u=username: self.reset_requested.emit(u))
        toggle = QPushButton("Disable" if row.get("active") else "Enable")
        toggle.setObjectName("SmallDanger" if row.get("active") else "Small")
        toggle.clicked.connect(lambda _c, u=username: self.toggle_requested.emit(u))
        for button in (role, reset, toggle):
            line.addWidget(button)
        line.addStretch(1)
        return holder

    def _role_menu(self, username: str, button: QPushButton, row: Dict[str, object]) -> None:
        menu = QMenu(self)
        for value, label in ROLE_CHOICES:
            action = menu.addAction(label)
            action.setEnabled(value != row.get("role"))
            action.triggered.connect(lambda _c=False, v=value: self.role_requested.emit(username, v))
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
