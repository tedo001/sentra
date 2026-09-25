"""The sign-in screen, as the design draws it.

Dark on the left - the organisation, SENTRA, what it does and the five steps
from report to a person confirming; light on the right - the form. The
logic is :class:`ui2.login.LoginDialog`'s, untouched: the same first-run
setup with no default password, the same lockout, the same one-time
password that must be replaced, the same audit entries. Only the pages are
laid out differently, the username field also takes an email address, the
password can be shown, and the username can be remembered on this machine.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPen
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

from sif import prefs
from sif.version import __version__
from ui2.login import LoginDialog

__all__ = ["WorkspaceLogin", "STEPS"]

STEPS = ("Report", "Read", "Flag", "Explain", "Person confirms")


def _l(text: str, name: str, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


def _edit(placeholder: str = "", secret: bool = False, name: str = "") -> QLineEdit:
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    edit.setMinimumHeight(40)
    if secret:
        edit.setEchoMode(QLineEdit.EchoMode.Password)
    if name:
        edit.setObjectName(name)
    return edit


class BrandPanel(QFrame):
    """The dark half: a faint grid behind the organisation and the product."""

    def __init__(self, organisation: str, project: str) -> None:
        super().__init__()
        self.setObjectName("LoginBrand")
        mark = _l("OIL", "LoginMark")
        mark.setFixedSize(38, 38)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        org = QVBoxLayout()
        org.setSpacing(0)
        org.addWidget(_l(organisation, "LoginOrg"))
        org.addWidget(_l("Health, Safety and Environment", "LoginDept"))
        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(mark)
        top.addLayout(org)
        top.addStretch(1)

        chips = QHBoxLayout()
        chips.setSpacing(0)
        for index, step in enumerate(STEPS):
            chip = _l(step, "LoginStep")
            chip.setProperty("last", index == len(STEPS) - 1)
            chips.addWidget(chip)
        chips.addStretch(1)

        foot = QHBoxLayout()
        foot.addWidget(_l(f"{project} · SENTRA {__version__}", "LoginFoot"))
        foot.addStretch(1)
        foot.addWidget(_l("Restricted system · authorised personnel only", "LoginFoot"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(58, 48, 58, 44)
        layout.setSpacing(0)
        layout.addLayout(top)
        layout.addStretch(3)
        layout.addWidget(_l("SENTRA", "LoginWordmark"))
        layout.addSpacing(10)
        layout.addWidget(_l("SAFETY · INTELLIGENCE · COMPLIANCE", "LoginTagline"))
        layout.addSpacing(26)
        about = _l("Reads each near-miss and UA/UC report as it arrives, finds the ones that "
                   "could have killed someone, shows why, and asks a person to confirm.",
                   "LoginAbout", wrap=True)
        about.setMaximumWidth(500)
        layout.addWidget(about)
        layout.addSpacing(26)
        layout.addLayout(chips)
        layout.addStretch(5)
        layout.addLayout(foot)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#22272B"))
        painter.setPen(QPen(QColor(255, 255, 255, 10), 1))
        step = 36
        for x in range(0, self.width(), step):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), step):
            painter.drawLine(0, y, self.width(), y)
        super().paintEvent(event)


class WorkspaceLogin(LoginDialog):
    """:class:`LoginDialog`'s behaviour in the design's split layout."""

    def __init__(self, store, audit, stylesheet: str = "",
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(store, audit, stylesheet, parent)
        self.setWindowTitle("SENTRA - sign in")
        self.setMinimumSize(1100, 680)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            room = screen.availableGeometry()
            self.resize(min(1440, room.width()), min(900, room.height()))

        # The parent's single card gives way to the two halves; its pages and
        # its error line are kept and re-seated on the right.
        outer = self.layout()
        while outer.count():
            item = outer.takeAt(0)
            if item.widget() is not None and item.widget() is not self.pages:
                old = item.widget()
                self.pages.setParent(None)
                self.error.setParent(None)
                old.setParent(None)
                old.deleteLater()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.error.setObjectName("ErrorText")
        self.error.setStyleSheet("")
        column = QVBoxLayout()
        column.setSpacing(10)
        column.addWidget(self.pages)
        column.addWidget(self.error)
        holder = QWidget()
        holder.setFixedWidth(420)
        holder.setLayout(column)
        outer.addLayout(self._arrange(holder))

        remembered = str(prefs.get("remember_username", "") or "")
        if remembered and hasattr(self, "remember"):
            self.username.setText(remembered)
            self.remember.setChecked(True)
            self.password.setFocus()

    def _arrange(self, form: QWidget):
        """The two halves: the brand on the left, ``form`` centred on the right."""
        brand = BrandPanel(str(prefs.get("organisation", "Oil India Limited")),
                           str(prefs.get("project_code", "PS 26165")))
        side = QFrame()
        side.setObjectName("LoginSide")
        right = QHBoxLayout(side)
        right.setContentsMargins(40, 40, 40, 40)
        right.addStretch(1)
        right.addWidget(form, 0, Qt.AlignmentFlag.AlignVCenter)
        right.addStretch(1)
        split = QHBoxLayout()
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(0)
        split.addWidget(brand, 53)
        split.addWidget(side, 47)
        return split

    # -- pages, laid out as designed ---------------------------------------------------

    def _heading(self, layout, title: str, why: str) -> None:
        layout.addWidget(_l(title, "LoginTitle"))
        layout.addWidget(_l(why, "LoginWhy", wrap=True))
        layout.addSpacing(10)

    @staticmethod
    def _labelled(layout, label: str, widget: QWidget) -> None:
        layout.addWidget(_l(label, "FieldLabel"))
        layout.addWidget(widget)
        layout.addSpacing(6)

    def _password_row(self, edit: QLineEdit) -> QWidget:
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(0)
        show = QPushButton("Show")
        show.setObjectName("ShowPassword")
        show.setCheckable(True)
        show.setFixedHeight(40)
        show.toggled.connect(lambda on: (edit.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password),
            show.setText("Hide" if on else "Show")))
        edit.setObjectName("PasswordField")
        line.addWidget(edit, 1)
        line.addWidget(show)
        return row

    def _sign_in_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._heading(layout, "Sign in",
                      "Use your Oil India account. Your role is set by your administrator.")
        self.username = _edit("name@oilindia.in or username", name="username")
        self.password = _edit("", True, "password")
        self._labelled(layout, "Username or email", self.username)
        self._labelled(layout, "Password", self._password_row(self.password))
        self.remember = QCheckBox("Remember me on this workstation")
        layout.addWidget(self.remember)
        layout.addSpacing(10)
        self.sign_in_button = QPushButton("Sign in")
        self.sign_in_button.setObjectName("LoginPrimary")
        self.sign_in_button.clicked.connect(self.sign_in)
        self.password.returnPressed.connect(self.sign_in)
        self.username.returnPressed.connect(self.password.setFocus)
        layout.addWidget(self.sign_in_button)
        layout.addSpacing(12)
        rule = QFrame()
        rule.setObjectName("LoginRule")
        rule.setFixedHeight(1)
        layout.addWidget(rule)
        layout.addSpacing(8)
        layout.addWidget(_l("After 5 failed attempts the account is locked for 5 minutes. "
                            "Every sign-in is written to the audit log.", "LoginNote", wrap=True))
        layout.addWidget(_l("Forgotten password or locked out: ask your SENTRA administrator "
                            "for a one-time password.", "LoginNote", wrap=True))
        return page

    def _setup_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._heading(layout, "Create the administrator",
                      "No account exists on this machine yet. The first one manages everyone "
                      "else's. There is no default password.")
        self.setup_name = _edit("As on employee record", name="setup_name")
        self.setup_user = _edit("e.g. d.manikandan", name="setup_user")
        self.setup_password = _edit("At least 8 characters", True, "setup_password")
        self.setup_confirm = _edit("Password again", True, "setup_confirm")
        self._labelled(layout, "Full name", self.setup_name)
        self._labelled(layout, "Username", self.setup_user)
        self._labelled(layout, "Password", self.setup_password)
        layout.addWidget(self.setup_confirm)
        layout.addSpacing(10)
        self.setup_button = QPushButton("Create and sign in")
        self.setup_button.setObjectName("LoginPrimary")
        self.setup_button.clicked.connect(self.create_administrator)
        self.setup_confirm.returnPressed.connect(self.create_administrator)
        layout.addWidget(self.setup_button)
        return page

    def _change_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._heading(layout, "Choose your own password",
                      "You signed in with a one-time password from an administrator. Choose "
                      "one only you know before going on.")
        self.new_password = _edit("At least 8 characters", True, "new_password")
        self.new_confirm = _edit("New password again", True, "new_confirm")
        self._labelled(layout, "New password", self.new_password)
        layout.addWidget(self.new_confirm)
        layout.addSpacing(10)
        self.change_button = QPushButton("Save and continue")
        self.change_button.setObjectName("LoginPrimary")
        self.change_button.clicked.connect(self.change_password)
        self.new_confirm.returnPressed.connect(self.change_password)
        layout.addWidget(self.change_button)
        return page

    # -- remembering the username ------------------------------------------------------

    def _accept(self, session) -> None:
        if hasattr(self, "remember"):
            prefs.set_value("remember_username",
                            self.username.text().strip() if self.remember.isChecked() else "")
        super()._accept(session)
