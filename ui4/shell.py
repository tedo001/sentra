"""The two-workspace shell: a dark title row and a tab row beneath it.

Taken from the Stage 2 sheet, left to right: the OIL mark and organisation,
SENTRA with a workspace tag, then the project code, notifications, settings or
preferences, and the signed-in person with their role, which opens the account
menu. The tab row carries one workspace's destinations and nothing else, with
one count - the cases waiting for a person - and a machine-facing note on the
right: the last analysis run for an analyst, the host and build for an
administrator.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath,
                         QPen, QPixmap)
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
)

__all__ = ["WorkspaceHeader", "TabRow", "header_icon", "find_logo", "LOGO_NAMES"]

#: The organisation's logo, when its file has been placed in ui/assets. The
#: first name found is used; with none, the header keeps the drawn OIL badge.
LOGO_NAMES = ("oil_logo.png", "oil_logo.svg", "oil_logo.webp", "oil_logo.jpg", "oil_logo.jpeg")
LOGO_DIRECTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "ui", "assets")
#: Wider than this, the file is a lockup that already spells the name out.
LOCKUP_RATIO = 2.2


def find_logo(directory: str = "") -> str:
    directory = directory or LOGO_DIRECTORY
    for name in LOGO_NAMES:
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            return path
    return ""


def logo_pixmap(path: str, height: int) -> Optional[QPixmap]:
    """``path`` scaled to ``height`` logical pixels, sharp on a high-DPI screen."""
    from PyQt6.QtGui import QGuiApplication

    source = QPixmap(path)
    if source.isNull():
        return None
    screen = QGuiApplication.primaryScreen()
    ratio = screen.devicePixelRatio() if screen is not None else 1.0
    scaled = source.scaledToHeight(int(round(height * ratio)),
                                   Qt.TransformationMode.SmoothTransformation)
    scaled.setDevicePixelRatio(ratio)
    return scaled


def header_icon(kind: str, colour: str = "#E6E8EB") -> QIcon:
    """A bell or a gear, drawn - no icon font to go missing on a workstation."""
    scale = 2
    pixmap = QPixmap(20 * scale, 20 * scale)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    paint = QPainter(pixmap)
    paint.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(colour), 1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    paint.setPen(pen)
    if kind == "bell":
        path = QPainterPath()
        path.moveTo(5.0, 14.0)
        path.lineTo(15.0, 14.0)
        path.lineTo(13.8, 12.2)
        path.lineTo(13.8, 8.6)
        path.cubicTo(13.8, 5.9, 12.1, 4.2, 10.0, 4.2)
        path.cubicTo(7.9, 4.2, 6.2, 5.9, 6.2, 8.6)
        path.lineTo(6.2, 12.2)
        path.closeSubpath()
        paint.drawPath(path)
        paint.drawLine(QPointF(8.6, 16.2), QPointF(11.4, 16.2))
    else:
        paint.drawEllipse(QRectF(7.4, 7.4, 5.2, 5.2))
        import math
        for step in range(8):
            angle = step * math.pi / 4
            inner, outer = 5.0, 7.4
            paint.drawLine(QPointF(10 + inner * math.cos(angle), 10 + inner * math.sin(angle)),
                           QPointF(10 + outer * math.cos(angle), 10 + outer * math.sin(angle)))
        paint.drawEllipse(QRectF(5.0, 5.0, 10.0, 10.0))
    paint.end()
    return QIcon(pixmap)


def _label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    return label


class WorkspaceHeader(QFrame):
    """The dark title row."""

    bell_clicked = pyqtSignal()
    gear_clicked = pyqtSignal()
    profile_requested = pyqtSignal()
    preferences_requested = pyqtSignal()
    sign_out_requested = pyqtSignal()

    def __init__(self, workspace: str, full_name: str, role_label: str,
                 username: str, project: str = "PS 26165",
                 organisation: str = "Oil India Limited",
                 place: str = "Field HQ Duliajan · Assam") -> None:
        super().__init__()
        self.setObjectName("WorkspaceHeader")
        self.setProperty("workspace", workspace)
        self.setFixedHeight(48 if workspace == "hse" else 51)

        self.logo_path = find_logo()
        picture = logo_pixmap(self.logo_path, 34) if self.logo_path else None
        self.organisation = _label(organisation, "OrgName")
        if picture is not None:
            # On a white tile: a logo drawn for paper disappears on the dark row.
            mark = _label("", "OilLogo")
            mark.setPixmap(picture)
            mark.setToolTip(organisation)
            mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
            mark.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            # A lockup already carries the name; the words would say it twice.
            self.organisation.setVisible(
                picture.width() / max(1, picture.height()) < LOCKUP_RATIO)
        else:
            mark = _label("OIL", "OilMark")
            mark.setFixedSize(30, 30)
            mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mark = mark
        org = QVBoxLayout()
        org.setSpacing(0)
        org.addWidget(self.organisation)
        self.place = _label(place, "OrgPlace")
        org.addWidget(self.place)
        left = QHBoxLayout()
        left.setSpacing(10)
        left.addWidget(mark)
        left.addLayout(org)

        self.wordmark = _label("SENTRA", "Wordmark")
        self.tag = _label("ADMINISTRATION" if workspace == "admin" else "HSE WORKSPACE",
                          "WorkspaceTag")
        self.tag.setProperty("workspace", workspace)
        self.tag.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        centre = QHBoxLayout()
        centre.setSpacing(12)
        centre.addWidget(self.wordmark, alignment=Qt.AlignmentFlag.AlignVCenter)
        centre.addWidget(self.tag, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.project = _label(project, "ProjectCode")
        self.bell = QToolButton()
        self.bell.setObjectName("HeaderIcon")
        self.bell.setFixedSize(32, 32)
        self.bell.setIcon(header_icon("bell"))
        self.bell.setIconSize(QSize(20, 20))
        self.bell.setToolTip("Cases waiting for a person" if workspace == "hse"
                             else "Security events today")
        self.bell.clicked.connect(self.bell_clicked.emit)
        self.bell_badge = _label("", "Badge")
        self.bell_badge.setParent(self.bell)
        self.bell_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bell_badge.setFixedHeight(14)
        self.bell_badge.setMinimumWidth(14)
        self.bell_badge.hide()
        self.gear = QToolButton()
        self.gear.setObjectName("HeaderIcon")
        self.gear.setIcon(header_icon("gear"))
        self.gear.setIconSize(QSize(20, 20))
        self.gear.setToolTip("System settings" if workspace == "admin" else "Preferences")
        self.gear.clicked.connect(self.gear_clicked.emit)

        initials = "".join(part[0] for part in full_name.replace(".", " ").split()[:2]).upper()
        avatar = _label(initials or "?", "Avatar")
        avatar.setFixedSize(28, 28)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.user_name = _label(full_name, "UserName")
        self.user_role = _label(role_label, "UserRole")
        who = QVBoxLayout()
        who.setSpacing(0)
        who.addWidget(self.user_name)
        who.addWidget(self.user_role)
        chevron = _label("▾", "UserRole")
        self.account = QPushButton()
        self.account.setObjectName("AccountButton")
        self.account.setCursor(Qt.CursorShape.PointingHandCursor)
        inside = QHBoxLayout(self.account)
        inside.setContentsMargins(6, 2, 6, 2)
        inside.setSpacing(8)
        inside.addWidget(avatar)
        inside.addLayout(who)
        inside.addWidget(chevron)
        self.account.setMinimumWidth(170)
        self.account.setMinimumHeight(38)
        self.menu = self._account_menu(full_name, username, role_label, project, workspace)
        self.account.clicked.connect(
            lambda: self.menu.exec(self.account.mapToGlobal(self.account.rect().bottomLeft())))

        right = QHBoxLayout()
        right.setSpacing(14)
        right.addWidget(self.project)
        right.addWidget(self.bell)
        right.addWidget(self.gear)
        right.addWidget(self.account)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.addLayout(left)
        layout.addStretch(1)
        layout.addLayout(centre)
        layout.addStretch(1)
        layout.addLayout(right)

    def _account_menu(self, full_name: str, username: str, role_label: str,
                      project: str, workspace: str) -> QMenu:
        """Name, role and project, then My profile, Preferences, Sign out."""
        menu = QMenu(self)
        for text in (full_name, f"{username}  ·  {role_label}  ·  {project}"):
            item = menu.addAction(text)
            item.setEnabled(False)
        menu.addSeparator()
        menu.addAction("My profile").triggered.connect(self.profile_requested.emit)
        menu.addAction("System settings" if workspace == "admin" else "Preferences") \
            .triggered.connect(self.preferences_requested.emit)
        menu.addSeparator()
        menu.addAction("Sign out").triggered.connect(self.sign_out_requested.emit)
        return menu

    def set_identity(self, organisation: str, place: str, project: str) -> None:
        """Organisation, field HQ and project code, as Settings has them."""
        self.organisation.setText(organisation)
        self.place.setText(place)
        self.project.setText(project)

    def set_bell(self, count: int) -> None:
        self.bell_badge.setText(str(count) if count < 100 else "99+")
        self.bell_badge.adjustSize()
        # Top-right of the bell, however wide the number made it.
        self.bell_badge.move(self.bell.width() - self.bell_badge.width(), 0)
        self.bell_badge.setVisible(count > 0)


class TabRow(QFrame):
    """One workspace's destinations, with one count and one note."""

    navigated = pyqtSignal(str)

    def __init__(self, workspace: str, tabs: Sequence[Tuple[str, str]],
                 badge_key: str = "") -> None:
        super().__init__()
        self.setObjectName("TabRow")
        self.setProperty("workspace", workspace)
        self.buttons: Dict[str, QPushButton] = {}
        self.badge = _label("", "TabBadge")
        self.badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.badge.hide()
        self.note = _label("", "TabNote")

        group = QButtonGroup(self)
        group.setExclusive(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 16, 0)
        layout.setSpacing(2)
        # Measured bold: the selected tab is set in bold, and a button sized for
        # the regular weight clips its own label the moment it is selected.
        bold = QFont()
        bold.setPixelSize(14)
        bold.setWeight(QFont.Weight.DemiBold)
        metrics = QFontMetrics(bold)
        for key, label in tabs:
            button = QPushButton(label)
            button.setObjectName("WorkspaceTab")
            button.setMinimumWidth(metrics.horizontalAdvance(label) + 34)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked, name=key: self.navigated.emit(name))
            group.addButton(button)
            self.buttons[key] = button
            layout.addWidget(button)
            if key == badge_key:
                layout.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)
                layout.addSpacing(8)
        layout.addStretch(1)
        layout.addWidget(self.note)

    @property
    def keys(self) -> List[str]:
        return list(self.buttons)

    def select(self, key: str) -> None:
        button = self.buttons.get(key)
        if button is not None:
            button.setChecked(True)

    def set_badge(self, count: int) -> None:
        self.badge.setText(str(count))
        self.badge.setVisible(count > 0)

    def set_note(self, text: str) -> None:
        self.note.setText(text)
