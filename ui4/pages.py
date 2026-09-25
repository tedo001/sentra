"""The two pages build 4 adds: Home and Profile.

Home answers "what needs me now" for an HSE analyst: the counts that matter,
the cases waiting for a person in the order they should be taken, the latest
reports, and what the analyst did most recently.

Profile is the person's own page: who they are signed in as, their password,
one preference, and their own actions - only theirs.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.components import DataTable, KpiTile, Panel
from ui.theme import C

__all__ = ["HomeView", "ProfileView"]

ATTENTION_COLUMNS = (
    ("Trigger", "trigger", 140),
    ("Ref", "reference", 84),
    ("Risk", "risk_score", 60),
    ("Why a person is needed", "reason", 380),
)
RECENT_COLUMNS = (
    ("Ref", "reference", 84),
    ("Risk", "risk_score", 60),
    ("SIF", "sif_potential", 52),
    ("IOGP rule", "iogp_rule", 170),
    ("Location", "location", 190),
    ("Analysed by", "analysed_by", 200),
)
OWN_ACTIVITY_COLUMNS = (
    ("Time", "when", 150),
    ("Action", "action", 180),
    ("Detail", "summary", 420),
)


def _scroll(content: QWidget, minimum: int) -> QScrollArea:
    content.setMinimumHeight(minimum)
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(content)
    return area


class HomeView(QWidget):
    """What needs me now."""

    review_requested = pyqtSignal()
    ingest_requested = pyqtSignal()
    report_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.kpis = {
            "reports": KpiTile("REPORTS ANALYSED", "0", C.TEXT, note="in this session"),
            "sif": KpiTile("SIF POTENTIAL", "0", C.DANGER, note="high energy + failed barrier"),
            "waiting": KpiTile("WAITING FOR A PERSON", "0", C.ACCENT, note="the HSE review queue"),
            "critical": KpiTile("CRITICAL", "0", C.WARN, note="risk 70 and above"),
        }
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        for tile in self.kpis.values():
            tiles.addWidget(tile)

        open_review = QPushButton("Open HSE review")
        open_review.setObjectName("Primary")
        open_review.clicked.connect(self.review_requested.emit)
        add = QPushButton("Bring reports in")
        add.clicked.connect(self.ingest_requested.emit)
        self.attention = DataTable(ATTENTION_COLUMNS, flex_keys=("reason",))
        self.attention_note = QLabel("Nothing is waiting for a person.")
        self.attention_note.setObjectName("Muted")
        attention = Panel("Needs attention", action=open_review)
        attention.add(self.attention_note)
        attention.add(self.attention, stretch=1)

        self.recent = DataTable(RECENT_COLUMNS, flex_keys=("location", "analysed_by"))
        self.recent.itemDoubleClicked.connect(self._open_recent)
        self._recent_refs: List[str] = []
        recent = Panel("Recent reports", action=add)
        hint = QLabel("Double-click a report to open it with its evidence.")
        hint.setObjectName("Faint")
        recent.add(hint)
        recent.add(self.recent, stretch=1)

        self.own = DataTable(OWN_ACTIVITY_COLUMNS, flex_keys=("summary",))
        mine = Panel("Your recent activity")
        mine.add(self.own, stretch=1)

        grid = QGridLayout()
        grid.setSpacing(12)
        grid.addWidget(attention, 0, 0, 1, 2)
        grid.addWidget(recent, 1, 0)
        grid.addWidget(mine, 1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addLayout(tiles)
        layout.addLayout(grid, stretch=1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_scroll(content, 700))

    def show_state(self, rows: Sequence[Dict[str, object]], queue: Sequence[Dict[str, object]],
               outstanding: int, own: Sequence[Dict[str, object]]) -> None:
        self.kpis["reports"].set_value(str(len(rows)))
        self.kpis["sif"].set_value(str(sum(1 for row in rows if row.get("sif_potential"))))
        self.kpis["waiting"].set_value(str(outstanding))
        self.kpis["critical"].set_value(
            str(sum(1 for row in rows if float(row.get("risk_score") or 0) >= 70)))
        waiting = [row for row in queue if not row.get("decided")][:8]
        self.attention.set_rows(waiting)
        self.attention.setVisible(bool(waiting))
        self.attention_note.setVisible(not waiting)
        latest = list(reversed(list(rows)))[:8]
        self._recent_refs = [str(row.get("reference", "")) for row in latest]
        self.recent.set_rows(latest)
        self.own.set_rows(list(own)[:8])

    def _open_recent(self, item) -> None:
        row = item.row()
        if 0 <= row < len(self._recent_refs):
            self.report_requested.emit(self._recent_refs[row])


class ProfileView(QWidget):
    """The signed-in person's own page."""

    password_change_requested = pyqtSignal(str, str)
    preference_changed = pyqtSignal(str, bool)

    def __init__(self) -> None:
        super().__init__()
        self.fields: Dict[str, QLabel] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)
        for row, (key, label) in enumerate((
                ("full_name", "Name"), ("username", "Username"), ("role", "Role"),
                ("workspace", "Workspace"), ("signed_in", "Signed in at"),
                ("session", "Session"))):
            caption = QLabel(label)
            caption.setObjectName("Muted")
            value = QLabel("-")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(caption, row, 0)
            grid.addWidget(value, row, 1)
            self.fields[key] = value
        grid.setColumnStretch(1, 1)
        profile = Panel("Profile")
        profile.body.addLayout(grid)

        self.current = QLineEdit()
        self.current.setPlaceholderText("Current password")
        self.current.setEchoMode(QLineEdit.EchoMode.Password)
        self.new = QLineEdit()
        self.new.setPlaceholderText("New password - at least 8 characters")
        self.new.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm = QLineEdit()
        self.confirm.setPlaceholderText("New password again")
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.change = QPushButton("Change password")
        self.change.setObjectName("Primary")
        self.change.clicked.connect(self._request_change)
        self.security_note = QLabel("")
        self.security_note.setWordWrap(True)
        self.security_note.setObjectName("Muted")
        security = Panel("Security")
        for widget in (self.current, self.new, self.confirm, self.change, self.security_note):
            security.add(widget)

        self.check_updates = QCheckBox("Check for a new release when the console starts")
        self.check_updates.toggled.connect(
            lambda on: self.preference_changed.emit("check_updates", on))
        preferences = Panel("Preferences")
        preferences.add(self.check_updates)

        self.activity = DataTable(OWN_ACTIVITY_COLUMNS, flex_keys=("summary",))
        activity = Panel("Your activity")
        note = QLabel("Your own actions only. An administrator reads everyone's in the "
                      "Audit Log.")
        note.setObjectName("Faint")
        activity.add(note)
        activity.add(self.activity, stretch=1)

        top = QHBoxLayout()
        top.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(12)
        left.addWidget(profile)
        left.addWidget(preferences)
        left.addStretch(1)
        top.addLayout(left, stretch=1)
        top.addWidget(security, stretch=1)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addLayout(top)
        layout.addWidget(activity, stretch=1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_scroll(content, 720))

    def set_person(self, values: Dict[str, str], can_change_password: bool) -> None:
        for key, value in values.items():
            if key in self.fields:
                self.fields[key].setText(value or "-")
        for widget in (self.current, self.new, self.confirm, self.change):
            widget.setEnabled(can_change_password)
        if not can_change_password:
            self.security_note.setText("This session is not signed in to an account.")

    def set_activity(self, rows: Sequence[Dict[str, object]]) -> None:
        self.activity.set_rows(list(rows))

    def set_security_note(self, text: str, ok: bool) -> None:
        self.security_note.setText(text)
        self.security_note.setStyleSheet("" if ok else f"color: {C.DANGER};")

    def _request_change(self) -> None:
        if self.new.text() != self.confirm.text():
            self.set_security_note("The two new passwords are not the same.", False)
            return
        self.password_change_requested.emit(self.current.text(), self.new.text())
