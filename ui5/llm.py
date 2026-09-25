"""The local LLM, always on: one button in the title row that says whether it is.

SENTRA runs ``gemma2:latest`` through Ollama as a fourth opinion on every
report and as the translator for narratives not written in English. It is
switched on at start-up; this button is where anyone can see, at a glance,
whether it is actually answering:

* **green** - the host answered and the model is installed;
* **amber** - checking, or the host is up but the model has not been pulled
  (the tooltip gives the one command that fixes it);
* **red** - the host did not answer, so reports are being analysed without it;
* **grey** - an administrator switched it off.

Pressing it checks again. The arrow beside it, for an administrator, turns it
off or on; nobody else can switch the analyser off from here.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QToolButton

__all__ = ["LLMButton", "STATE_COLOURS"]

STATE_COLOURS = {"ready": "#22C55E", "checking": "#F59E0B", "missing": "#F59E0B",
                 "offline": "#EF4444", "off": "#71717A"}
STATE_WORDS = {"ready": "ready", "checking": "checking…", "missing": "model not pulled",
               "offline": "offline", "off": "off"}


def _dot(colour: str) -> QIcon:
    scale = 2
    pixmap = QPixmap(10 * scale, 10 * scale)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    halo = QColor(colour)
    halo.setAlpha(70)
    painter.setBrush(halo)
    painter.drawEllipse(QRectF(0, 0, 10, 10))
    painter.setBrush(QColor(colour))
    painter.drawEllipse(QRectF(2, 2, 6, 6))
    painter.end()
    return QIcon(pixmap)


class LLMButton(QToolButton):
    """``● gemma2:latest`` - press to check; administrators get an on/off menu."""

    check_requested = pyqtSignal()
    enable_requested = pyqtSignal(bool)
    settings_requested = pyqtSignal()

    def __init__(self, model: str, can_configure: bool = False) -> None:
        super().__init__()
        self.setObjectName("LLMButton")
        self.model = model
        self.state = "checking"
        self.detail = ""
        self.can_configure = can_configure
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(10, 10))
        self.setFixedHeight(28)
        self.clicked.connect(self.check_requested.emit)
        if can_configure:
            self.menu_ = QMenu(self)
            self.menu_.addAction("Check the connection now").triggered.connect(
                self.check_requested.emit)
            self.toggle_action = self.menu_.addAction("Turn the LLM analyser off")
            self.toggle_action.triggered.connect(
                lambda: self.enable_requested.emit(self.state == "off"))
            self.menu_.addSeparator()
            self.menu_.addAction("Host and model settings…").triggered.connect(
                self.settings_requested.emit)
            self.setMenu(self.menu_)
            self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.set_state("checking")

    def set_model(self, model: str) -> None:
        self.model = model
        self.set_state(self.state, self.detail)

    def set_state(self, state: str, detail: str = "") -> None:
        self.state = state if state in STATE_COLOURS else "offline"
        self.detail = detail
        self.setProperty("state", self.state)
        self.setIcon(_dot(STATE_COLOURS[self.state]))
        self.setText(self.model)
        lines = [f"Local LLM · {self.model} · {STATE_WORDS[self.state]}"]
        if detail:
            lines.append(detail)
        if self.state == "missing":
            lines.append(f"On the LLM host run:  ollama pull {self.model}")
        elif self.state == "offline":
            lines.append("Reports are still analysed by the three engines; the LLM "
                         "opinion and translation are skipped until the host answers.")
        elif self.state == "off":
            lines.append("Switched off by an administrator.")
        lines.append("Press to check again." if self.state != "off" or not self.can_configure
                     else "Use the arrow to turn it back on.")
        self.setToolTip("\n".join(lines))
        if self.can_configure:
            self.toggle_action.setText("Turn the LLM analyser on" if self.state == "off"
                                       else "Turn the LLM analyser off")
        self.style().unpolish(self)
        self.style().polish(self)
