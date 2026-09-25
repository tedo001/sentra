"""Data & Backup: the administrator's page for where SENTRA's records live.

Four things, top to bottom:

* **Local SQL database** - SQLite on this workstation by default, or a
  PostgreSQL / MySQL server the site shares. Test a URL, switch to it, sync
  now, and choose whether every analysis run syncs by itself.
* **Vector database** - every report's embedding, for "find reports like
  this one". Build or top up the index, and search it in plain words.
* **Cloud backup** - an encrypted archive of everything, to a synced folder,
  S3-compatible storage or WebDAV; on demand or on a schedule; with the
  backups already there listed for verifying or restoring.
* **Sync & backup log** - every sync, backup, restore and test, with its
  outcome.

The page only shows and asks; :mod:`main5` does the work, off the GUI thread,
behind the CONFIGURE permission, and writes each step to the Audit Log.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QGridLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
                             QStackedWidget, QWidget)

from sif.backup import SCHEDULES, TARGET_KINDS
from ui4.kit import Card, Col, DesignTable, KeyValues, Page, Pill, StatStrip

__all__ = ["DataPage", "SIMILAR_COLUMNS", "BACKUP_COLUMNS", "LOG_COLUMNS"]

SIMILAR_COLUMNS = (
    Col("reference", "Ref", 110, "link"),
    Col("similarity", "Similarity", 110, "bar"),
    Col("risk_score", "Risk", 90, "risk"),
    Col("iogp_rule", "IOGP rule", 0),
)
BACKUP_COLUMNS = (
    Col("name", "Archive", 0, "mono"),
    Col("size", "Size", 90, "num", align="right"),
    Col("modified", "Stored", 160, "muted"),
)
LOG_COLUMNS = (
    Col("at", "When", 150, "mono", value=lambda row: str(row.get("at", "")).replace("T", " ")),
    Col("kind", "What", 110, "strong"),
    Col("state", "Result", 90, "pill"),
    Col("target", "Where", 260, "muted"),
    Col("detail", "Detail", 0),
)


def _label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


def _secret(placeholder: str = "") -> QLineEdit:
    field = QLineEdit()
    field.setEchoMode(QLineEdit.EchoMode.Password)
    field.setPlaceholderText(placeholder)
    return field


def _form() -> QFormLayout:
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(8)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return form


def _row(*widgets) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    for widget in widgets:
        if widget is None:
            row.addStretch(1)
        else:
            row.addWidget(widget)
    return row


class DataPage(Page):
    test_database = pyqtSignal(str)
    apply_database = pyqtSignal(str)
    sync_requested = pyqtSignal()
    auto_sync_changed = pyqtSignal(bool)
    index_requested = pyqtSignal()
    search_requested = pyqtSignal(str)
    report_requested = pyqtSignal(str)
    save_target = pyqtSignal(dict, dict)
    test_target = pyqtSignal(dict, dict)
    backup_requested = pyqtSignal()
    list_requested = pyqtSignal()
    verify_requested = pyqtSignal(str)
    restore_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__("Data & Backup",
                         "Local SQL database · vector index · encrypted off-site backup",
                         scroll=True)
        self.sync_button = QPushButton("Sync now")
        self.sync_button.clicked.connect(self.sync_requested.emit)
        self.backup_button = QPushButton("Back up now")
        self.backup_button.setObjectName("Primary")
        self.backup_button.clicked.connect(self.backup_requested.emit)
        self.head.add(self.sync_button)
        self.head.add(self.backup_button)

        self.stats = StatStrip(("SQL database", "Vector index", "Last sync", "Last backup"))
        self.body.addWidget(self.stats)

        top = QGridLayout()
        top.setSpacing(16)
        top.addWidget(self._database_card(), 0, 0)
        top.addWidget(self._vector_card(), 0, 1)
        top.setColumnStretch(0, 1)
        top.setColumnStretch(1, 1)
        self.body.addLayout(top)

        middle = QGridLayout()
        middle.setSpacing(16)
        middle.addWidget(self._cloud_card(), 0, 0)
        middle.addWidget(self._backups_card(), 0, 1)
        middle.setColumnStretch(0, 1)
        middle.setColumnStretch(1, 1)
        self.body.addLayout(middle)

        self.log_card = Card("Sync & backup log", "newest first", flush=True)
        self.log_table = DesignTable(LOG_COLUMNS, row_height=32)
        self.log_table.setMinimumHeight(240)
        self.log_card.add(self.log_table, 1)
        self.body.addWidget(self.log_card)
        self.set_busy("")

    # -- the cards ------------------------------------------------------------------

    def _database_card(self) -> Card:
        card = Card("Local SQL database", "")
        self.db_state = card.add_head(Pill("", "grey"))
        self.db_where = card.add(_label("", "KvValue"))
        self.db_url = QLineEdit()
        self.db_url.setPlaceholderText("sqlite:///C:/SENTRA/sentra.db  ·  "
                                       "postgresql://user:password@server/sentra")
        test = QPushButton("Test")
        test.clicked.connect(lambda: self.test_database.emit(self.db_url.text().strip()))
        use = QPushButton("Use this database")
        use.clicked.connect(lambda: self.apply_database.emit(self.db_url.text().strip()))
        card.body.addWidget(_label("Database URL", "FieldLabel"))
        card.body.addLayout(_row(self.db_url, test, use))
        self.db_note = card.add(_label("", "Hint"))
        self.db_counts = KeyValues(2, label_width=110)
        card.add(self.db_counts)
        self.auto_sync = QCheckBox("Sync to this database after every analysis run and "
                                   "review decision")
        self.auto_sync.toggled.connect(self.auto_sync_changed.emit)
        card.add(self.auto_sync)
        card.add(_label("Sync pushes this workstation's reports, decisions, action items and "
                        "audit entries, then pulls what other workstations stored. It is "
                        "keyed on content, so running it twice changes nothing.", "Hint"))
        card.body.addStretch(1)
        return card

    def _vector_card(self) -> Card:
        card = Card("Vector database", "similar-report search")
        self.vector_state = card.add_head(Pill("", "grey"))
        self.vector_facts = KeyValues(1, label_width=130)
        card.add(self.vector_facts)
        self.index_button = QPushButton("Build / top up the index")
        self.index_button.clicked.connect(self.index_requested.emit)
        self.vector_note = _label("", "Hint")
        card.body.addLayout(_row(self.index_button, None))
        card.add(self.vector_note)
        card.body.addWidget(_label("Find reports like…", "FieldLabel"))
        self.query = QLineEdit()
        self.query.setPlaceholderText("e.g. scaffold board gave way, harness not clipped")
        self.query.returnPressed.connect(self._search)
        find = QPushButton("Search")
        find.clicked.connect(self._search)
        card.body.addLayout(_row(self.query, find))
        self.similar = DesignTable(SIMILAR_COLUMNS, row_height=30)
        self.similar.setMinimumHeight(170)
        self.similar.link_clicked.connect(self._open)
        self.similar.row_activated.connect(self._open)
        card.add(self.similar, 1)
        return card

    def _cloud_card(self) -> Card:
        card = Card("Cloud backup", "encrypted before it leaves this machine")
        self.target_state = card.add_head(Pill("", "grey"))
        self.kind = QComboBox()
        for key, label in TARGET_KINDS:
            self.kind.addItem(label, key)
        self.forms = QStackedWidget()

        folder = QWidget()
        folder_form = _form()
        folder.setLayout(folder_form)
        self.folder = QLineEdit()
        self.folder.setPlaceholderText("OneDrive, Google Drive or Dropbox folder, or \\\\server\\share")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        holder = QWidget()
        holder.setLayout(_row(self.folder, browse))
        holder.layout().setContentsMargins(0, 0, 0, 0)
        folder_form.addRow("Folder", holder)
        folder_form.addRow(_label("A folder the OneDrive, Google Drive or Dropbox client "
                                  "syncs is uploaded by that client; a network share is "
                                  "written directly.", "Hint"))
        self.forms.addWidget(folder)

        s3 = QWidget()
        s3_form = _form()
        s3.setLayout(s3_form)
        self.s3_endpoint = QLineEdit()
        self.s3_endpoint.setPlaceholderText("https://s3.ap-south-1.amazonaws.com")
        self.s3_bucket = QLineEdit()
        self.s3_region = QLineEdit()
        self.s3_region.setPlaceholderText("ap-south-1")
        self.s3_prefix = QLineEdit()
        self.s3_prefix.setPlaceholderText("sentra/")
        self.s3_access = QLineEdit()
        self.s3_secret = _secret()
        for label, widget in (("Endpoint", self.s3_endpoint), ("Bucket", self.s3_bucket),
                              ("Region", self.s3_region), ("Folder prefix", self.s3_prefix),
                              ("Access key", self.s3_access), ("Secret key", self.s3_secret)):
            s3_form.addRow(label, widget)
        s3_form.addRow(_label("AWS S3, MinIO, Cloudflare R2, Wasabi or Backblaze B2.", "Hint"))
        self.forms.addWidget(s3)

        dav = QWidget()
        dav_form = _form()
        dav.setLayout(dav_form)
        self.dav_url = QLineEdit()
        self.dav_url.setPlaceholderText("https://cloud.example.org/remote.php/dav/files/hse/sentra/")
        self.dav_user = QLineEdit()
        self.dav_password = _secret()
        for label, widget in (("Folder URL", self.dav_url), ("Username", self.dav_user),
                              ("Password", self.dav_password)):
            dav_form.addRow(label, widget)
        self.forms.addWidget(dav)
        self.kind.currentIndexChanged.connect(self.forms.setCurrentIndex)

        common = _form()
        common.addRow("Store backups in", self.kind)
        card.body.addLayout(common)
        card.add(self.forms)

        after = _form()
        self.passphrase = _secret()
        self.passphrase_again = _secret()
        after.addRow("Passphrase", self.passphrase)
        after.addRow("Repeat", self.passphrase_again)
        self.schedule = QComboBox()
        for key, label in SCHEDULES:
            self.schedule.addItem(label, key)
        self.keep = QSpinBox()
        self.keep.setRange(0, 365)
        self.keep.setSpecialValueText("all")
        self.keep.setSuffix(" newest")
        after.addRow("Schedule", self.schedule)
        after.addRow("Keep", self.keep)
        card.body.addLayout(after)
        card.add(_label("The passphrase is the only way to open a backup. It is kept sealed "
                        "on this machine so scheduled backups can run; write it down "
                        "somewhere safe as well.", "Hint"))
        save = QPushButton("Save")
        save.setObjectName("Primary")
        save.clicked.connect(lambda: self._emit_target(self.save_target))
        test = QPushButton("Test connection")
        test.clicked.connect(lambda: self._emit_target(self.test_target))
        card.body.addLayout(_row(save, test, None))
        self.target_note = card.add(_label("", "Hint"))
        card.body.addStretch(1)
        return card

    def _backups_card(self) -> Card:
        card = Card("Backups at the target", "")
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.list_requested.emit)
        card.add_head(refresh)
        self.backups = DesignTable(BACKUP_COLUMNS, row_height=30)
        self.backups.setMinimumHeight(260)
        card.add(self.backups, 1)
        self.verify_button = QPushButton("Verify")
        self.verify_button.clicked.connect(lambda: self._emit_selected(self.verify_requested))
        self.restore_button = QPushButton("Restore…")
        self.restore_button.setObjectName("Danger")
        self.restore_button.clicked.connect(lambda: self._emit_selected(self.restore_requested))
        card.body.addLayout(_row(self.verify_button, self.restore_button, None))
        card.add(_label("Verify downloads an archive, decrypts it and checks every file "
                        "against its SHA-256. Restore merges the database back - nothing on "
                        "this machine is deleted - and unpacks the files into a dated "
                        "folder to put in place by hand.", "Hint"))
        self.backups_note = card.add(_label("", "Hint"))
        return card

    # -- page events -------------------------------------------------------------------

    def _search(self) -> None:
        if self.query.text().strip():
            self.search_requested.emit(self.query.text().strip())

    def _open(self, row: int) -> None:
        if 0 <= row < len(self.similar.rows):
            self.report_requested.emit(str(self.similar.rows[row].get("reference", "")))

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Folder for the backups",
                                                  self.folder.text())
        if chosen:
            self.folder.setText(chosen)

    def _emit_selected(self, signal) -> None:
        row = self.backups.currentRow()
        if 0 <= row < len(self.backups.rows):
            signal.emit(str(self.backups.rows[row]["name"]))
        else:
            self.backups_note.setText("Choose a backup in the list first.")

    def target_values(self) -> Tuple[Dict[str, object], Dict[str, str]]:
        """(settings kept in the preferences, secrets for the vault - blank = keep)."""
        config = {"kind": self.kind.currentData(), "folder": self.folder.text().strip(),
                  "endpoint": self.s3_endpoint.text().strip(),
                  "bucket": self.s3_bucket.text().strip(),
                  "region": self.s3_region.text().strip(),
                  "prefix": self.s3_prefix.text().strip() or "sentra/",
                  "access_key": self.s3_access.text().strip(),
                  "url": self.dav_url.text().strip(), "username": self.dav_user.text().strip(),
                  "schedule": self.schedule.currentData(), "keep": self.keep.value()}
        secrets = {"s3_secret": self.s3_secret.text(),
                   "webdav_password": self.dav_password.text(),
                   "passphrase": self.passphrase.text(),
                   "passphrase_again": self.passphrase_again.text()}
        return config, secrets

    def _emit_target(self, signal) -> None:
        config, secrets = self.target_values()
        signal.emit(config, secrets)

    # -- filling -------------------------------------------------------------------------

    def set_busy(self, what: str) -> None:
        """Disable what cannot run twice; ``what`` names the running job or is ''."""
        for button in (self.sync_button, self.backup_button, self.index_button,
                       self.verify_button, self.restore_button):
            button.setEnabled(not what)
        self.head.caption.setText(
            f"Working: {what}…" if what
            else "Local SQL database · vector index · encrypted off-site backup")

    def set_database(self, where: str, url: str, ok: bool, message: str,
                     counts: Dict[str, int], auto_sync: bool) -> None:
        self.db_state.set("Connected" if ok else "Unavailable", "ok" if ok else "fail")
        self.db_where.setText(where)
        if not self.db_url.hasFocus() and not self.db_url.text():
            self.db_url.setText(url)
        self.db_note.setText(message)
        self.db_counts.set_pairs([("Reports", str(counts.get("reports", 0))),
                                  ("Decisions", str(counts.get("decisions", 0))),
                                  ("Action items", str(counts.get("actions", 0))),
                                  ("Audit entries", str(counts.get("audit", 0)))])
        self.auto_sync.blockSignals(True)
        self.auto_sync.setChecked(auto_sync)
        self.auto_sync.blockSignals(False)

    def set_database_note(self, text: str, ok: bool = True) -> None:
        self.db_note.setText(text)
        self.db_note.setObjectName("Hint" if ok else "ErrorText")
        self.db_note.style().unpolish(self.db_note)
        self.db_note.style().polish(self.db_note)

    def set_vectors(self, encoder: str, stored: int, missing: int, corpus: int,
                    others: Sequence[str]) -> None:
        tone = "ok" if stored and not missing else ("warn" if corpus else "grey")
        self.vector_state.set(f"{stored} indexed" if stored else "Empty", tone)
        pairs = [("Encoder", encoder or "loads on first use"),
                 ("Reports indexed", f"{stored} of {corpus} in this session"),
                 ("Not yet indexed", str(missing))]
        if others:
            pairs.append(("Other encoders", ", ".join(others)))
        self.vector_facts.set_pairs(pairs)

    def set_vector_note(self, text: str) -> None:
        self.vector_note.setText(text)

    def set_similar(self, rows: Sequence[Dict[str, object]]) -> None:
        self.similar.set_rows(rows)

    def set_target(self, config: Dict[str, object], stored: Dict[str, bool],
                   describe: str) -> None:
        index = self.kind.findData(config.get("kind", "folder"))
        self.kind.setCurrentIndex(max(0, index))
        self.folder.setText(str(config.get("folder", "")))
        self.s3_endpoint.setText(str(config.get("endpoint", "")))
        self.s3_bucket.setText(str(config.get("bucket", "")))
        self.s3_region.setText(str(config.get("region", "")))
        self.s3_prefix.setText(str(config.get("prefix", "") or "sentra/"))
        self.s3_access.setText(str(config.get("access_key", "")))
        self.dav_url.setText(str(config.get("url", "")))
        self.dav_user.setText(str(config.get("username", "")))
        for field, key in ((self.s3_secret, "s3_secret"), (self.dav_password, "webdav_password"),
                           (self.passphrase, "passphrase"),
                           (self.passphrase_again, "passphrase")):
            field.clear()
            field.setPlaceholderText("stored - leave blank to keep" if stored.get(key)
                                     else "not set")
        self.schedule.setCurrentIndex(max(0, self.schedule.findData(
            config.get("schedule", "off"))))
        self.keep.setValue(int(config.get("keep", 14) or 0))
        configured = bool(describe)
        self.target_state.set("Configured" if configured and stored.get("passphrase")
                              else "Not set up", "ok" if configured and stored.get("passphrase")
                              else "warn")
        self.target_note.setText(describe or "Choose where backups go, set a passphrase, "
                                 "then Save.")

    def set_target_note(self, text: str, ok: bool = True) -> None:
        self.target_note.setText(text)
        self.target_note.setObjectName("Hint" if ok else "ErrorText")
        self.target_note.style().unpolish(self.target_note)
        self.target_note.style().polish(self.target_note)

    def set_backups(self, rows: Sequence[Dict[str, object]], note: str = "") -> None:
        self.backups.set_rows(rows)
        self.backups_note.setText(note)

    def set_stats(self, values: Sequence[Tuple[object, str, bool]]) -> None:
        for cell, (value, note, alert) in zip(self.stats.cells, values):
            cell.set(value, note, alert=alert)

    def set_log(self, rows: Sequence[Dict[str, object]]) -> None:
        self.log_table.set_rows([{**row, "state": ("OK", "ok") if row.get("ok")
                                  else ("Failed", "fail")} for row in rows])
