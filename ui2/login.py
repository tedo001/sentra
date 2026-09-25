"""The sign-in page: who is about to use the console.

Three states in one dialog, because they are one moment from the operator's
side - "let me in":

``setup``     No account exists on this machine yet. Create the administrator.
              There is no default password to fall back on, on purpose.
``sign in``   The ordinary case.
``change``    The account was created or reset by an administrator with a
              one-time password. Choose a real one before going further.

Everything the dialog decides is written to the audit trail - successful
sign-ins under the account, refused ones with the name that was tried - so the
trail answers "who tried to get in" as well as "who got in".
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sif.accounts import AccountStore, AuthError, Session
from sif.audit import AuditLog

__all__ = ["LoginDialog"]


def _field(placeholder: str, secret: bool = False, name: str = "") -> QLineEdit:
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    edit.setMinimumHeight(38)
    if secret:
        edit.setEchoMode(QLineEdit.EchoMode.Password)
    if name:
        edit.setObjectName(name)
    return edit


def _caption(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Caption")
    return label


class LoginDialog(QDialog):
    """Sign in, first-run setup, or a forced password change."""

    def __init__(self, store: AccountStore, audit: AuditLog,
                 stylesheet: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.store = store
        self.audit = audit
        self.session: Optional[Session] = None
        self._pending: Optional[Session] = None      # signed in, must change password
        self._pending_password = ""

        self.setWindowTitle("SENTRA - sign in")
        self.setModal(True)
        self.setMinimumWidth(440)
        # The pages are plain widgets, and a plain widget paints the
        # application background - here, a charcoal block inside the card.
        self.setStyleSheet(stylesheet + "\nQStackedWidget#LoginPages, "
                           "QStackedWidget#LoginPages > QWidget "
                           "{ background: transparent; }")

        card = QFrame()
        card.setObjectName("Panel")
        body = QVBoxLayout(card)
        body.setContentsMargins(28, 26, 28, 24)
        body.setSpacing(10)

        brand = QLabel("SENTRA")
        brand.setObjectName("BrandName")
        brand.setStyleSheet("font-size: 26px;")
        organisation = QLabel("Oil India Limited  ·  PS 26165")
        organisation.setObjectName("Muted")
        body.addWidget(brand)
        body.addWidget(organisation)
        body.addSpacing(8)

        self.pages = QStackedWidget()
        self.pages.setObjectName("LoginPages")
        self.pages.addWidget(self._setup_page())
        self.pages.addWidget(self._sign_in_page())
        self.pages.addWidget(self._change_page())
        body.addWidget(self.pages)

        self.error = QLabel("")
        self.error.setObjectName("LoginError")
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #ff5c52;")
        self.error.hide()
        body.addWidget(self.error)

        note = QLabel("Everything you do in the console is recorded under this "
                      "account - what you analyse, what you decide, what you export.")
        note.setObjectName("Faint")
        note.setWordWrap(True)
        body.addSpacing(4)
        body.addWidget(note)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.addWidget(card)

        self.show_page("sign in" if store.has_accounts() else "setup")

    # -- pages -------------------------------------------------------------

    def _setup_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        title = QLabel("Create the administrator")
        title.setObjectName("SectionTitle")
        why = QLabel("No account exists on this machine yet. The first one manages "
                     "everyone else's. There is no default password.")
        why.setObjectName("Muted")
        why.setWordWrap(True)
        self.setup_name = _field("Full name", name="setup_name")
        self.setup_user = _field("Username - e.g. d.manikandan", name="setup_user")
        self.setup_password = _field("Password - at least 8 characters", True,
                                     "setup_password")
        self.setup_confirm = _field("Password again", True, "setup_confirm")
        self.setup_button = QPushButton("Create and sign in")
        self.setup_button.setObjectName("Primary")
        self.setup_button.clicked.connect(self.create_administrator)
        self.setup_confirm.returnPressed.connect(self.create_administrator)
        for widget in (title, why, _caption("FULL NAME"), self.setup_name,
                       _caption("USERNAME"), self.setup_user, _caption("PASSWORD"),
                       self.setup_password, self.setup_confirm, self.setup_button):
            layout.addWidget(widget)
        return page

    def _sign_in_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        title = QLabel("Sign in")
        title.setObjectName("SectionTitle")
        self.username = _field("Username", name="username")
        self.password = _field("Password", True, "password")
        self.sign_in_button = QPushButton("Sign in")
        self.sign_in_button.setObjectName("Primary")
        self.sign_in_button.clicked.connect(self.sign_in)
        self.password.returnPressed.connect(self.sign_in)
        self.username.returnPressed.connect(self.password.setFocus)
        for widget in (title, _caption("USERNAME"), self.username,
                       _caption("PASSWORD"), self.password, self.sign_in_button):
            layout.addWidget(widget)
        return page

    def _change_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        title = QLabel("Choose your own password")
        title.setObjectName("SectionTitle")
        why = QLabel("You signed in with a one-time password from an administrator. "
                     "Choose one only you know before going on.")
        why.setObjectName("Muted")
        why.setWordWrap(True)
        self.new_password = _field("New password - at least 8 characters", True,
                                   "new_password")
        self.new_confirm = _field("New password again", True, "new_confirm")
        self.change_button = QPushButton("Save and continue")
        self.change_button.setObjectName("Primary")
        self.change_button.clicked.connect(self.change_password)
        self.new_confirm.returnPressed.connect(self.change_password)
        for widget in (title, why, self.new_password, self.new_confirm,
                       self.change_button):
            layout.addWidget(widget)
        return page

    def show_page(self, name: str) -> None:
        index = {"setup": 0, "sign in": 1, "change": 2}[name]
        self.pages.setCurrentIndex(index)
        self._clear_error()
        focus = {0: self.setup_name, 1: self.username, 2: self.new_password}[index]
        focus.setFocus()

    @property
    def page(self) -> str:
        return ("setup", "sign in", "change")[self.pages.currentIndex()]

    # -- actions -----------------------------------------------------------

    def create_administrator(self) -> None:
        if self.setup_password.text() != self.setup_confirm.text():
            self._fail("The two passwords are not the same.")
            return
        try:
            account = self.store.create(
                self.setup_user.text(), self.setup_name.text(), "admin",
                self.setup_password.text(), created_by="first-run setup")
            session = self.store.authenticate(account.username,
                                              self.setup_password.text())
        except AuthError as exc:
            self._fail(str(exc))
            return
        self.audit.sign_in(session.username, session.role)
        self.audit.functionality("administrator created", username=session.username)
        self._accept(session)

    def sign_in(self) -> None:
        username = self.username.text().strip()
        password = self.password.text()
        if not username or not password:
            self._fail("Enter your username and password.")
            return
        try:
            session = self.store.authenticate(username, password)
        except AuthError as exc:
            self.audit.functionality("sign-in refused", attempted=username.lower(),
                                     reason=exc.reason)
            if exc.reason == "locked out":
                self.audit.functionality("account locked", username=username.lower())
            self.password.clear()
            self._fail(str(exc))
            return
        account = self.store.get(session.username)
        if account is not None and account.must_change:
            self._pending, self._pending_password = session, password
            self.show_page("change")
            return
        self.audit.sign_in(session.username, session.role)
        self._accept(session)

    def change_password(self) -> None:
        if self._pending is None:
            return
        if self.new_password.text() != self.new_confirm.text():
            self._fail("The two passwords are not the same.")
            return
        try:
            self.store.change_password(self._pending.username, self._pending_password,
                                       self.new_password.text())
        except AuthError as exc:
            self._fail(str(exc))
            return
        session, self._pending, self._pending_password = self._pending, None, ""
        self.audit.sign_in(session.username, session.role)
        self.audit.functionality("password changed", username=session.username,
                                 reason="one-time password replaced")
        self._accept(session)

    def _accept(self, session: Session) -> None:
        self.session = session
        self.audit.functionality("signed in", username=session.username,
                                 role=session.role, session=session.session_id)
        self.accept()

    def _fail(self, message: str) -> None:
        self.error.setText(message)
        self.error.show()

    def _clear_error(self) -> None:
        self.error.clear()
        self.error.hide()
