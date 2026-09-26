"""The sign-in screen, as the revamp draws it.

White on the left - the Oil India mark, SENTRA and its tagline, the form with
an icon in each field, remember me, sign in - and on the right a navy
gradient under a faint grid: SENTRA, "Safer Operations / Smarter Decisions /
Compliance Always", and whether the system is up.

All the behaviour is :class:`ui4.login.WorkspaceLogin`'s, which is
:class:`ui2.login.LoginDialog`'s: first-run setup with no default password,
lockout, one-time passwords, audit entries. The design's "prototype
accounts (any password)" box is left out on purpose - an any-password door
would undo all of that.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen,
                         QPixmap)
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QVBoxLayout,
                             QWidget)

from sif import prefs
from ui.theme import ASSETS
from ui4.login import WorkspaceLogin

__all__ = ["SentraLogin", "field_icon"]

TAGLINES = ("Safer Operations", "Smarter Decisions", "Compliance Always")


def field_icon(kind: str) -> QIcon:
    """The revamp's grey person and padlock, drawn."""
    pixmap = QPixmap(32, 32)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#9CA3AF"), 1.3))
    if kind == "user":
        painter.drawEllipse(QRectF(5.2, 2.5, 5.6, 5.6))
        path = QPainterPath()
        path.moveTo(2.5, 14)
        path.cubicTo(3, 9.5, 13, 9.5, 13.5, 14)
        painter.drawPath(path)
    else:
        painter.drawRoundedRect(QRectF(3, 7, 10, 7), 1.5, 1.5)
        path = QPainterPath()
        path.moveTo(5.2, 7)
        path.lineTo(5.2, 5)
        path.cubicTo(5.2, 1.5, 10.8, 1.5, 10.8, 5)
        path.lineTo(10.8, 7)
        painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def _l(text: str, name: str, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


class GradientPanel(QFrame):
    """Navy to teal-black, a faint grid, SENTRA and three lines."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("LoginGradient")
        column = QVBoxLayout(self)
        column.setContentsMargins(40, 40, 40, 40)
        column.addStretch(1)
        word = _l("SENTRA", "GradientWordmark")
        word.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(word)
        tag = _l("Safety · Intelligence · Compliance", "GradientTag")
        tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(tag)
        column.addSpacing(56)
        for line in TAGLINES:
            label = _l(line, "GradientLine")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(label)
            column.addSpacing(10)
        column.addSpacing(48)
        self.status = _l("", "GradientStatus")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row = QHBoxLayout()
        status_row.addStretch(1)
        status_row.addWidget(self.status)
        status_row.addStretch(1)
        column.addLayout(status_row)
        column.addStretch(1)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        gradient = QLinearGradient(QPointF(0, 0), QPointF(self.width(), self.height()))
        gradient.setColorAt(0.0, QColor("#0D1F35"))
        gradient.setColorAt(0.5, QColor("#1A3A5C"))
        gradient.setColorAt(1.0, QColor("#0D2A1A"))
        painter.fillRect(self.rect(), gradient)
        painter.setPen(QPen(QColor(255, 255, 255, 8), 1))
        for x in range(0, self.width(), 60):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 60):
            painter.drawLine(0, y, self.width(), y)
        super().paintEvent(event)


#: The sign-in block's width: wordmark, form and notes.
FORM_WIDTH = 340


class SentraLogin(WorkspaceLogin):
    def _arrange(self, form: QWidget):
        left = QFrame()
        left.setObjectName("LoginForm")
        column = QVBoxLayout(left)
        column.setContentsMargins(40, 40, 40, 40)
        column.setSpacing(0)

        brand = QHBoxLayout()
        brand.setSpacing(12)
        mark = QLabel()
        logo = os.path.join(ASSETS, "oil_logo.png")
        if os.path.isfile(logo):
            mark.setPixmap(QPixmap(logo).scaledToHeight(
                44, Qt.TransformationMode.SmoothTransformation))
        brand.addWidget(mark)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(_l(str(prefs.get("organisation", "Oil India Limited")), "FormOrg"))
        names.addWidget(_l("Health, Safety and Environment", "FormDept"))
        brand.addLayout(names)
        brand.addStretch(1)
        column.addLayout(brand)
        column.addStretch(1)

        # The wordmark, the tagline, every label, field, button and note share
        # one left edge, and the block sits in the middle of the white half.
        if form.layout() is not None:
            form.layout().setContentsMargins(0, 0, 0, 0)
        form.setFixedWidth(FORM_WIDTH)
        block = QWidget()
        block.setObjectName("LoginBlock")
        block.setFixedWidth(FORM_WIDTH)
        block.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)
        form.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)
        body = QVBoxLayout(block)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(2)
        body.addWidget(_l("SENTRA", "FormWordmark"))
        body.addWidget(_l("Safety · Intelligence · Compliance", "FormTag"))
        body.addSpacing(28)
        body.addWidget(form)
        body.addStretch(1)
        centred = QHBoxLayout()
        centred.setContentsMargins(0, 0, 0, 0)
        centred.addStretch(1)
        centred.addWidget(block)
        centred.addStretch(1)
        column.addLayout(centred)
        column.addStretch(1)
        column.addWidget(_l(f"Oil India Limited  |  {prefs.get('project_code', 'PS 26165')}",
                            "FormFoot"))

        self.gradient = GradientPanel()
        split = QHBoxLayout()
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(0)
        split.addWidget(left, 44)
        split.addWidget(self.gradient, 56)
        return split

    def __init__(self, store, audit, stylesheet: str = "", parent=None,
                 last_run: str = "") -> None:
        super().__init__(store, audit, stylesheet, parent)
        for field, kind in ((self.username, "user"), (self.password, "lock"),
                            (self.forgot_name, "user"),
                            (getattr(self, "setup_user", None), "user"),
                            (getattr(self, "setup_password", None), "lock")):
            if isinstance(field, QLineEdit):
                field.addAction(field_icon(kind), QLineEdit.ActionPosition.LeadingPosition)
        self.username.setPlaceholderText("Username or email")
        self.password.setPlaceholderText("Password")
        self.remember.setText("Remember Me")
        # The application's display name is added by the system: "Sign in - SENTRA".
        self.setWindowTitle("Sign in")
        self.forgot_name.setPlaceholderText("Username or email")
        for field in (self.username, self.forgot_name):
            field.setClearButtonEnabled(True)
        # Each page as tall as its own content: labels sit on their fields, and
        # the block centres on what is shown rather than on the tallest page.
        for index in range(self.pages.count()):
            self.pages.widget(index).layout().addStretch(1)
        self.pages.currentChanged.connect(self._fit_page)
        self._fit_page(self.pages.currentIndex())
        if not prefs.get("remember_username"):
            self.remember.setChecked(True)
        self.gradient.status.setText("●  System operational" + (
            f" · last run {last_run}" if last_run else ""))

    def _fit_page(self, _current: int = -1) -> None:
        """The page stack as tall as the page on show (a stack keeps its tallest)."""
        page = self.pages.currentWidget()
        if page is None:
            return
        layout = page.layout()
        height = (layout.heightForWidth(FORM_WIDTH) if layout.hasHeightForWidth()
                  else layout.sizeHint().height())
        self.pages.setFixedHeight(max(height, layout.minimumSize().height()
                                      if not layout.hasHeightForWidth() else 0))

    def request_reset(self) -> bool:
        sent = super().request_reset()
        self._fit_page()
        return sent

    def _heading(self, layout, title: str, why: str) -> None:
        # The revamp's sign-in page has no heading over the form; the setup and
        # change-password pages keep theirs, they need the explanation.
        if title != "Sign in":
            super()._heading(layout, title, why)
