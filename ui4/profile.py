"""Profile - the signed-in person's own account.

From the design: a head card (initials, name, role and organisation, site,
department, last sign-in) over four tabs. For an HSE Analyst: Profile,
Security, Preferences, Activity - with what the role can and cannot do. For
an administrator: Profile, Security, Sessions, Activity - with the
separation-of-duties note in place of the role list.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .kit import Col, DesignTable, KeyValues, Page, TabbedCard

__all__ = ["ACTIVITY_COLUMNS", "ProfilePage", "ROLE_CAN", "ROLE_CANNOT"]

ROLE_CAN = {
    "hse": ("Upload and ingest reports", "Read all reports, evidence and dashboards",
            "Record review decisions", "Investigate hotspots", "Keep the action-item calendar"),
    "viewer": ("Read all reports, evidence and dashboards", "Read the action-item calendar"),
}
ROLE_CANNOT = {
    "hse": ("Engines, settings, system log, audit log", "Creating or changing accounts"),
    "viewer": ("Uploading, analysing or deciding", "Engines, settings, logs and accounts"),
}
SEPARATION = ("This account manages the platform. It cannot record review decisions, so no "
              "one both configures the engine and signs off its results.")

ACTIVITY_COLUMNS = (
    Col("when", "Time", 170, "mono"),
    Col("action", "Action", 200),
    Col("summary", "Detail", 0, "muted"),
)
SESSION_COLUMNS = (
    Col("when", "Signed in", 170, "mono"),
    Col("workstation", "Workstation", 170, "mono"),
    Col("role", "Role", 150),
    Col("state", "Session", 0),
)


def _l(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    return label


class ProfilePage(Page):
    password_change_requested = pyqtSignal(str, str)
    preference_changed = pyqtSignal(str, object)

    def __init__(self, workspace: str) -> None:
        super().__init__("Profile", "Your account on SENTRA")
        self.workspace = workspace

        head = QFrame()
        head.setObjectName("Card")
        row = QHBoxLayout(head)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(16)
        self.avatar = _l("", "BigAvatar")
        self.avatar.setFixedSize(50, 50)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        words = QVBoxLayout()
        words.setSpacing(2)
        self.name = _l("", "ProfileName")
        self.role = _l("", "CardCaption")
        words.addWidget(self.name)
        words.addWidget(self.role)
        row.addWidget(self.avatar)
        row.addLayout(words)
        row.addSpacing(40)
        self.inline: Dict[str, QLabel] = {}
        for key, label in (("site", "Site"), ("department", "Department"),
                           ("last", "Last sign-in")):
            row.addWidget(_l(label, "KvKey"))
            value = _l("", "InlineMono" if key == "last" else "InlineValue")
            self.inline[key] = value
            row.addWidget(value)
            row.addSpacing(8)
        row.addStretch(1)
        self.body.addWidget(head)

        tabs = ("Profile", "Security",
                "Sessions" if workspace == "admin" else "Preferences", "Activity")
        self.tabs = TabbedCard(tabs)

        # -- Profile ----------------------------------------------------------------
        details = QWidget()
        detail_row = QHBoxLayout(details)
        detail_row.setContentsMargins(18, 20, 18, 18)
        detail_row.setSpacing(24)
        self.fields = KeyValues(1, label_width=170)
        detail_row.addWidget(self.fields, 7)
        self.side = QVBoxLayout()
        self.side.setSpacing(8)
        side_box = QWidget()
        side_box.setLayout(self.side)
        detail_row.addWidget(side_box, 4)
        wrapper = QWidget()
        wrap = QVBoxLayout(wrapper)
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.addWidget(details)
        wrap.addStretch(1)
        self.tabs.add_page(wrapper)

        # -- Security -----------------------------------------------------------------
        security = QWidget()
        form = QVBoxLayout(security)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(10)
        form.addWidget(_l("Change your password", "SubTitle"))
        self.current = QLineEdit()
        self.current.setPlaceholderText("Current password")
        self.new = QLineEdit()
        self.new.setPlaceholderText("New password - at least 8 characters")
        self.confirm = QLineEdit()
        self.confirm.setPlaceholderText("New password again")
        for field in (self.current, self.new, self.confirm):
            field.setEchoMode(QLineEdit.EchoMode.Password)
            field.setMaximumWidth(420)
            form.addWidget(field)
        self.change = QPushButton("Change password")
        self.change.setObjectName("Primary")
        self.change.setMaximumWidth(420)
        self.change.clicked.connect(self._request_change)
        self.clear_password = QPushButton("Clear")
        self.clear_password.setToolTip("Empty the three password fields")
        self.clear_password.clicked.connect(self.clear_password_fields)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self.change, 1)
        buttons.addWidget(self.clear_password)
        holder = QWidget()
        holder.setMaximumWidth(420)
        holder.setLayout(buttons)
        buttons.setContentsMargins(0, 0, 0, 0)
        form.addWidget(holder)
        self.security_note = _l("", "CardCaption")
        self.security_note.setWordWrap(True)
        form.addWidget(self.security_note)
        policy = _l("After 5 failed attempts an account is locked for 5 minutes. Every "
                    "sign-in, refusal and password change is written to the audit log.",
                    "CardCaption")
        policy.setWordWrap(True)
        form.addSpacing(8)
        form.addWidget(policy)
        form.addStretch(1)
        self.tabs.add_page(security)

        # -- Preferences or Sessions -------------------------------------------------------
        if workspace == "admin":
            sessions = QWidget()
            box = QVBoxLayout(sessions)
            box.setContentsMargins(0, 0, 0, 0)
            self.sessions = DesignTable(SESSION_COLUMNS)
            box.addWidget(self.sessions)
            self.tabs.add_page(sessions)
            self.check_updates = QCheckBox()
            self.check_updates.hide()
        else:
            preferences = QWidget()
            box = QVBoxLayout(preferences)
            box.setContentsMargins(18, 18, 18, 18)
            box.setSpacing(10)
            self.check_updates = QCheckBox("Check for a new release when the console starts")
            self.check_updates.toggled.connect(
                lambda on: self.preference_changed.emit("check_updates", on))
            self.auto_refresh = QCheckBox("Refresh my pages every 5 minutes")
            self.auto_refresh.toggled.connect(
                lambda on: self.preference_changed.emit("auto_refresh", on))
            box.addWidget(self.check_updates)
            box.addWidget(self.auto_refresh)
            box.addStretch(1)
            self.tabs.add_page(preferences)
            self.sessions = None

        # -- Activity -----------------------------------------------------------------------
        activity = QWidget()
        box = QVBoxLayout(activity)
        box.setContentsMargins(0, 0, 0, 0)
        self.activity = DesignTable(ACTIVITY_COLUMNS)
        box.addWidget(self.activity)
        self.tabs.add_page(activity)
        self.body.addWidget(self.tabs, 1)

    def _request_change(self) -> None:
        if self.new.text() != self.confirm.text():
            self.set_security_note("The two new passwords do not match.", False)
            return
        self.password_change_requested.emit(self.current.text(), self.new.text())

    def clear_password_fields(self) -> None:
        for field in (self.current, self.new, self.confirm):
            field.clear()
        self.security_note.clear()

    def set_security_note(self, text: str, ok: bool) -> None:
        self.security_note.setText(text)
        self.security_note.setProperty("ok", ok)
        self.security_note.setStyleSheet("color: #1E7B34;" if ok else "color: #B3261E;")

    def clear_passwords(self) -> None:
        for field in (self.current, self.new, self.confirm):
            field.clear()

    def set_person(self, person: Dict[str, str], fields: Sequence[Tuple[str, str]],
                   can_change_password: bool) -> None:
        self.avatar.setText(person.get("initials", ""))
        self.name.setText(person.get("full_name", ""))
        self.role.setText(f"{person.get('role', '')} · Oil India Limited")
        self.inline["site"].setText(person.get("site") or "-")
        self.inline["department"].setText(person.get("department") or "-")
        self.inline["last"].setText(person.get("last") or "-")
        self.fields.set_pairs(fields, mono=("Email", "Employee no.", "Project",
                                            "Account created", "Session"))
        for field in (self.current, self.new, self.confirm, self.change):
            field.setEnabled(can_change_password)
        if not can_change_password:
            self.set_security_note("This session was not signed in with an account, so there "
                                   "is no password to change.", False)
        while self.side.count():
            item = self.side.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)
        key = person.get("workspace_key", "hse")
        if key == "admin":
            self.side.addWidget(_l("Separation of duties", "SideTitle"))
            text = _l(SEPARATION, "SideText")
            text.setWordWrap(True)
            self.side.addWidget(text)
        else:
            self.side.addWidget(_l("What this role can do", "SideTitle"))
            for line in ROLE_CAN.get(key, ()):
                self.side.addWidget(_l(f"•  {line}", "SideText"))
            self.side.addSpacing(8)
            self.side.addWidget(_l("Not available to this role", "SideTitle"))
            for line in ROLE_CANNOT.get(key, ()):
                self.side.addWidget(_l(f"•  {line}", "SideFaint"))
            self.side.addSpacing(8)
            note = _l("Name, role and site are managed by your administrator.", "SideFaint")
            note.setWordWrap(True)
            self.side.addWidget(note)
        self.side.addStretch(1)

    def set_activity(self, rows: Sequence[Dict[str, object]]) -> None:
        self.activity.set_rows(rows)

    def set_sessions(self, rows: Sequence[Dict[str, object]]) -> None:
        if self.sessions is not None:
            self.sessions.set_rows(rows)
