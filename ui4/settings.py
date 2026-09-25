"""Settings - the administrator's configuration, a section at a time.

From the design: sections down the left (General, Organization, Users &
Roles, Models, Security, Storage, Notifications) and the chosen section's
fields on the right. Every change is emitted as ``(key, value)`` and written
to the audit log with its previous and new value by the window.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .kit import Col, DesignTable, KeyValues, Page, scrolling

__all__ = ["SECTIONS", "SettingsPage"]

SECTIONS = ("General", "Organization", "Users & Roles", "Models", "Security", "Storage",
            "Notifications")

TIMEZONES = ("Asia/Kolkata (IST, UTC+5:30)", "UTC")
DATE_FORMATS = (("%d %b %Y", "25 Sep 2026"), ("%Y-%m-%d", "2026-09-25"),
                ("%d/%m/%Y", "25/09/2026"))
ENCODERS = (("auto", "Auto - transformer, fall back offline"),
            ("transformer", "Transformer (all-MiniLM-L6-v2)"),
            ("hashing", "Offline - deterministic rules only"))
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

ROLE_COLUMNS = (
    Col("role", "Role", 150, "strong"),
    Col("can", "Can", 0),
    Col("cannot", "Cannot", 300, "muted"),
)


def _l(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


class SettingsPage(Page):
    setting_changed = pyqtSignal(str, object)
    encoder_changed = pyqtSignal(str)
    llm_toggled = pyqtSignal(bool)
    llm_configured = pyqtSignal(str, str)
    tracking_changed = pyqtSignal(str, str)
    log_level_changed = pyqtSignal(str)
    accounts_requested = pyqtSignal()
    verify_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__("Settings", "Changes are written to the audit log with the value "
                                     "they replaced")
        self.nav = QListWidget()
        self.nav.setObjectName("SettingsNav")
        self.nav.addItems(SECTIONS)
        self.nav.setFixedWidth(208)
        self.stack = QStackedWidget()
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.fields: Dict[str, object] = {}
        self._loading = False

        for builder in (self._general, self._organization, self._roles, self._models,
                        self._security, self._storage, self._notifications):
            content = QWidget()
            layout = QVBoxLayout(content)
            layout.setContentsMargins(18, 18, 18, 18)
            layout.setSpacing(12)
            builder(layout)
            layout.addStretch(1)
            area = scrolling(content)
            area.setObjectName("CardScroll")
            self.stack.addWidget(area)

        nav_card = QFrame()
        nav_card.setObjectName("Card")
        nav_layout = QVBoxLayout(nav_card)
        nav_layout.setContentsMargins(0, 6, 0, 6)
        nav_layout.addWidget(self.nav)
        form_card = QFrame()
        form_card.setObjectName("Card")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.addWidget(self.stack)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(nav_card)
        row.addWidget(form_card, 1)
        self.body.addLayout(row, 1)
        self.nav.setCurrentRow(0)

    # -- builders --------------------------------------------------------------------------

    def _title(self, layout, text: str) -> None:
        layout.addWidget(_l(text, "SubTitle"))

    def _text(self, grid: QGridLayout, row: int, column: int, key: str, label: str) -> QLineEdit:
        grid.addWidget(_l(label, "FieldLabel"), row * 2, column)
        field = QLineEdit()
        field.setFixedWidth(386)
        field.editingFinished.connect(lambda k=key, f=field: self._emit(k, f.text().strip()))
        grid.addWidget(field, row * 2 + 1, column)
        self.fields[key] = field
        return field

    def _combo(self, grid: QGridLayout, row: int, column: int, key: str, label: str,
               choices: Sequence[Tuple[str, str]]) -> QComboBox:
        grid.addWidget(_l(label, "FieldLabel"), row * 2, column)
        box = QComboBox()
        box.setFixedWidth(386)
        for value, text in choices:
            box.addItem(text, value)
        box.currentIndexChanged.connect(lambda _i, k=key, b=box: self._emit(k, b.currentData()))
        grid.addWidget(box, row * 2 + 1, column)
        self.fields[key] = box
        return box

    def _check(self, layout, key: str, text: str) -> QCheckBox:
        box = QCheckBox(text)
        box.toggled.connect(lambda on, k=key: self._emit(k, on))
        layout.addWidget(box)
        self.fields[key] = box
        return box

    @staticmethod
    def _grid(layout) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(2, 1)
        layout.addLayout(grid)
        return grid

    def _general(self, layout) -> None:
        self._title(layout, "Project information")
        grid = self._grid(layout)
        self._text(grid, 0, 0, "project_code", "Project code")
        self._text(grid, 0, 1, "application_name", "Application name")
        self._combo(grid, 1, 0, "timezone", "Timezone", [(zone, zone) for zone in TIMEZONES])
        self._combo(grid, 1, 1, "interface_language", "Interface language",
                    [("English", "English")])
        self._combo(grid, 2, 0, "date_format", "Date format",
                    [(fmt, text) for fmt, text in DATE_FORMATS])
        layout.addSpacing(8)
        self._title(layout, "Application")
        self._check(layout, "auto_refresh", "Auto-refresh HSE pages every 5 minutes")
        self._check(layout, "require_overturn_reason",
                    "Require a reason when a reviewer overturns an engine SIF call")
        self._check(layout, "allow_uploads", "Allow file uploads (PDF, images, TXT, CSV)")
        self._check(layout, "translate", "Translate non-English reports for review")
        self._check(layout, "viewer_scores", "Show engine risk scores to Viewer role")

    def _organization(self, layout) -> None:
        self._title(layout, "Organisation")
        grid = self._grid(layout)
        self._text(grid, 0, 0, "organisation", "Organisation name")
        self._text(grid, 0, 1, "place", "Field HQ, as the header shows it")
        layout.addSpacing(8)
        self._title(layout, "Sites and departments")
        layout.addWidget(_l("One per line. They are the choices offered when an account "
                            "is created.", "CardCaption"))
        lists = QHBoxLayout()
        lists.setSpacing(20)
        for key, label in (("sites", "Sites"), ("departments", "Departments")):
            column = QVBoxLayout()
            column.addWidget(_l(label, "FieldLabel"))
            box = QPlainTextEdit()
            box.setFixedSize(386, 180)
            column.addWidget(box)
            save = QPushButton(f"Save {label.lower()}")
            save.clicked.connect(lambda _c, k=key, b=box: self._emit(
                k, [line.strip() for line in b.toPlainText().splitlines() if line.strip()]))
            column.addWidget(save, 0, Qt.AlignmentFlag.AlignLeft)
            lists.addLayout(column)
            self.fields[key] = box
        lists.addStretch(1)
        layout.addLayout(lists)

    def _roles(self, layout) -> None:
        self._title(layout, "Roles in this build")
        layout.addWidget(_l("Two roles, kept apart: whoever configures the engine cannot sign "
                            "off its results. Permissions follow the role; to change what a "
                            "person may do, change their role.", "CardCaption"))
        self.roles = DesignTable(ROLE_COLUMNS, row_height=56, wrap=True)
        self.roles.setMinimumHeight(220)
        self.roles.set_rows([
            {"role": "HSE Analyst", "can": "Ingest and analyse reports, record review "
             "decisions, investigate hotspots, keep action items",
             "cannot": "Engines, settings, logs, accounts"},
            {"role": "Administrator", "can": "Engines and training, settings, SysLog, "
             "Audit Log, accounts", "cannot": "Analyse reports or decide review cases"},
            {"role": "Viewer", "can": "Read reports, evidence, dashboards and action items",
             "cannot": "Change anything"}])
        layout.addWidget(self.roles)
        manage = QPushButton("Manage accounts in New HSE Login")
        manage.clicked.connect(self.accounts_requested.emit)
        layout.addWidget(manage, 0, Qt.AlignmentFlag.AlignLeft)

    def _models(self, layout) -> None:
        self._title(layout, "Semantic encoder")
        grid = self._grid(layout)
        encoder = self._combo(grid, 0, 0, "encoder", "Encoder", ENCODERS)
        encoder.currentIndexChanged.connect(
            lambda _i: None if self._loading else self.encoder_changed.emit(encoder.currentData()))
        layout.addSpacing(8)
        self._title(layout, "Local LLM (Ollama)")
        self.llm_enabled = QCheckBox("Ask the local LLM for a fourth opinion on every report")
        self.llm_enabled.toggled.connect(
            lambda on: None if self._loading else self.llm_toggled.emit(on))
        layout.addWidget(self.llm_enabled)
        grid = self._grid(layout)
        host = self._text(grid, 0, 0, "llm_host", "Host")
        model = self._text(grid, 0, 1, "llm_model", "Model")
        apply = QPushButton("Apply and test")
        apply.clicked.connect(lambda: self.llm_configured.emit(host.text().strip(),
                                                               model.text().strip()))
        layout.addWidget(apply, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(8)
        self._title(layout, "Experiment tracking (MLflow)")
        grid = self._grid(layout)
        uri = self._text(grid, 0, 0, "tracking_uri", "Tracking URI")
        experiment = self._text(grid, 0, 1, "experiment", "Experiment")
        save = QPushButton("Apply")
        save.clicked.connect(lambda: self.tracking_changed.emit(uri.text().strip(),
                                                                experiment.text().strip()))
        layout.addWidget(save, 0, Qt.AlignmentFlag.AlignLeft)

    def _security(self, layout) -> None:
        self._title(layout, "Sign-in")
        facts = KeyValues(1, label_width=260)
        facts.set_pairs((("Failed attempts before lock", "5"), ("Lock lasts", "5 minutes"),
                         ("Password storage", "PBKDF2-HMAC-SHA256, 600,000 iterations"),
                         ("New and reset accounts", "one-time password, changed at first "
                                                    "sign-in"),
                         ("Default password", "none - the first run creates the "
                                              "administrator")), mono=("Password storage",))
        layout.addWidget(facts)
        layout.addSpacing(8)
        self._title(layout, "Audit trail")
        layout.addWidget(_l("Every entry carries the hash of the one before it, so an altered, "
                            "removed or inserted entry shows where it happened.", "CardCaption"))
        verify = QPushButton("Verify the chain now")
        verify.clicked.connect(self.verify_requested.emit)
        layout.addWidget(verify, 0, Qt.AlignmentFlag.AlignLeft)

    def _storage(self, layout) -> None:
        self._title(layout, "Where SENTRA keeps its records")
        self.paths = KeyValues(1, label_width=200)
        layout.addWidget(self.paths)
        layout.addSpacing(8)
        self._title(layout, "Logging")
        grid = self._grid(layout)
        level = self._combo(grid, 0, 0, "log_level", "Minimum level written",
                            [(name, name) for name in LOG_LEVELS])
        level.currentIndexChanged.connect(
            lambda _i: None if self._loading else self.log_level_changed.emit(level.currentData()))

    def _notifications(self, layout) -> None:
        self._title(layout, "What rings the bell")
        self._check(layout, "notify_critical", "A critical case waits for a person (HSE)")
        self._check(layout, "notify_security",
                    "A sign-in is refused, an account locks or a permission is refused (admin)")
        self._check(layout, "notify_overdue", "An action item is overdue (HSE)")
        layout.addSpacing(8)
        self._title(layout, "Releases")
        self._check(layout, "check_updates", "Check for a new release when the console starts")

    # -- values ---------------------------------------------------------------------------------

    def _emit(self, key: str, value: object) -> None:
        if not self._loading:
            self.setting_changed.emit(key, value)

    def load(self, values: Dict[str, object], paths: Sequence[Tuple[str, str]]) -> None:
        """Show the current values without emitting a single change."""
        self._loading = True
        try:
            for key, field in self.fields.items():
                value = values.get(key)
                if value is None:
                    continue
                if isinstance(field, QCheckBox):
                    field.setChecked(bool(value))
                elif isinstance(field, QComboBox):
                    index = field.findData(value)
                    if index >= 0:
                        field.setCurrentIndex(index)
                elif isinstance(field, QPlainTextEdit):
                    field.setPlainText("\n".join(value) if isinstance(value, (list, tuple))
                                       else str(value))
                elif isinstance(field, QLineEdit):
                    field.setText(str(value))
            self.llm_enabled.setChecked(bool(values.get("llm_enabled")))
            self.paths.set_pairs(paths, mono=[name for name, _ in paths])
        finally:
            self._loading = False
