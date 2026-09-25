"""Ingest - documents and narratives in, reports out.

From the design: the engines' readiness beside the title; the six stages of
the pipeline with what is in each; on the left, upload (drop zone, OCR
language, translate, analyse-after-extraction, CSV rows as reports) or a
pasted narrative; on the right, every document with its type, pages,
language, OCR outcome, stage and status, and beneath it the selected
document's extracted text, its source and its processing log.
"""

from __future__ import annotations

import os
from typing import Dict, Sequence

from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .kit import Card, Col, DesignTable, Page, Pill, StatStrip, TabbedCard, link_button

__all__ = ["DOCUMENT_COLUMNS", "IngestPage", "STAGES", "UPLOAD_FILTER"]

STAGES = ("1. Upload", "2. OCR", "3. Extract", "4. Translate", "5. Analyse", "6. Review")
UPLOAD_FILTER = ("Reports (*.pdf *.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp *.txt *.md *.csv);;"
                 "All files (*)")
ACCEPTED = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".txt", ".md",
            ".csv", ".tsv", ".log")

DOCUMENT_COLUMNS = (
    Col("name", "File / source", 0, "mono"),
    Col("type", "Type", 62),
    Col("pages", "Pages", 84, align="right"),
    Col("language", "Language", 150),
    Col("ocr", "OCR", 160),
    Col("stage", "Stage", 86),
    Col("status", "Status", 190, "pill"),
)


class ProcessingBadge(QWidget):
    """The "N processing" pill, its ring turning while anything is in flight."""

    def __init__(self) -> None:
        super().__init__()
        self.count = 0
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self._turn)
        self.setFixedHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set_count(0)

    def set_count(self, count: int) -> None:
        self.count = count
        self.setFixedWidth(self.fontMetrics().horizontalAdvance(f"{count} processing") + 40)
        if count and not self.timer.isActive():
            self.timer.start()
        elif not count:
            self.timer.stop()
        self.update()

    def _turn(self) -> None:
        self.angle = (self.angle + 30) % 360
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        box = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setPen(QPen(QColor("#A9C1D9"), 1))
        painter.setBrush(QColor("#E8EFF7"))
        painter.drawRoundedRect(box, 2, 2)
        ring = QRectF(8, 6, 12, 12)
        painter.setPen(QPen(QColor("#A9C1D9"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(ring)
        painter.setPen(QPen(QColor("#1E4F7A"), 2))
        painter.drawArc(ring, -self.angle * 16, 90 * 16)
        font = self.font()
        font.setPixelSize(12)
        font.setWeight(font.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(QRectF(26, 0, self.width() - 30, self.height()),
                         Qt.AlignmentFlag.AlignVCenter, f"{self.count} processing")


class DropZone(QFrame):
    """The dashed box: drop files on it or press Choose files."""

    files_dropped = pyqtSignal(list)
    choose_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        title = QLabel("Drop files here")
        title.setObjectName("DropTitle")
        kinds = QLabel("PDF · PNG · JPG · TIFF · TXT · CSV\nup to 50 MB each")
        kinds.setObjectName("DropNote")
        kinds.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.choose = QPushButton("Choose files…")
        self.choose.clicked.connect(self.choose_requested.emit)
        self.staged = QLabel("")
        self.staged.setObjectName("DropNote")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 14)
        layout.setSpacing(6)
        for widget in (title, kinds):
            layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.choose, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.staged, 0, Qt.AlignmentFlag.AlignHCenter)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            self.setProperty("hover", True)
            self.style().polish(self)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self.setProperty("hover", False)
        self.style().polish(self)

    def dropEvent(self, event) -> None:  # noqa: N802
        self.setProperty("hover", False)
        self.style().polish(self)
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        paths = [path for path in paths if os.path.splitext(path)[1].lower() in ACCEPTED]
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()


class IngestPage(Page):
    files_chosen = pyqtSignal(list)
    process_requested = pyqtSignal()
    narrative_submitted = pyqtSignal(str, str)
    seed_requested = pyqtSignal()
    language_changed = pyqtSignal(str)
    translate_toggled = pyqtSignal(bool)
    analyse_after_toggled = pyqtSignal(bool)
    csv_rows_toggled = pyqtSignal(bool)
    document_selected = pyqtSignal(int)
    retry_requested = pyqtSignal(int)
    remove_requested = pyqtSignal(int)
    analyse_requested = pyqtSignal(int)

    def __init__(self, languages: Sequence[str]) -> None:
        super().__init__("Ingest", "Documents and narratives in · reports out")
        self.engines = QLabel("")
        self.engines.setObjectName("PageNote")
        self.head.add(self.engines)

        self.pipeline = StatStrip(STAGES, mono=True)
        self.body.addWidget(self.pipeline)

        # -- left: upload or paste ------------------------------------------------
        self.inputs = TabbedCard(("Upload files", "Paste narrative"))
        self.inputs.setFixedWidth(342)
        upload = QWidget()
        form = QVBoxLayout(upload)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)
        self.drop = DropZone()
        self.drop.choose_requested.connect(self._choose)
        self.drop.files_dropped.connect(self.files_chosen.emit)
        form.addWidget(self.drop)
        language_label = QLabel("OCR language")
        language_label.setObjectName("FieldLabel")
        self.language = QComboBox()
        for name in languages:
            self.language.addItem(name)
        self.language.currentTextChanged.connect(self.language_changed.emit)
        form.addWidget(language_label)
        form.addWidget(self.language)
        self.translate = QCheckBox("Translate non-English for review")
        self.translate.setChecked(True)
        self.translate.toggled.connect(self.translate_toggled.emit)
        local = QLabel("(local LLM)")
        local.setObjectName("CardCaption")
        translate_row = QHBoxLayout()
        translate_row.setSpacing(6)
        translate_row.addWidget(self.translate)
        translate_row.addWidget(local)
        translate_row.addStretch(1)
        form.addLayout(translate_row)
        self.analyse_after = QCheckBox("Analyse after extraction")
        self.analyse_after.setChecked(True)
        self.analyse_after.toggled.connect(self.analyse_after_toggled.emit)
        form.addWidget(self.analyse_after)
        self.csv_rows = QCheckBox("Treat CSV rows as separate reports")
        self.csv_rows.setChecked(True)
        self.csv_rows.toggled.connect(self.csv_rows_toggled.emit)
        form.addWidget(self.csv_rows)
        self.start = QPushButton("Start processing")
        self.start.setObjectName("Primary")
        self.start.setEnabled(False)
        self.start.clicked.connect(self.process_requested.emit)
        form.addWidget(self.start)
        note = QLabel("Originals are kept as the record. Translation is only for reading.")
        note.setObjectName("CardCaption")
        note.setWordWrap(True)
        form.addWidget(note)
        form.addStretch(1)
        self.inputs.add_page(upload)

        paste = QWidget()
        paste_form = QVBoxLayout(paste)
        paste_form.setContentsMargins(12, 12, 12, 12)
        paste_form.setSpacing(10)
        reference_label = QLabel("Reference (optional)")
        reference_label.setObjectName("FieldLabel")
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("e.g. NM-26-0420")
        narrative_label = QLabel("Narrative")
        narrative_label.setObjectName("FieldLabel")
        self.narrative = QPlainTextEdit()
        self.narrative.setPlaceholderText("Paste one report, or several separated by a blank "
                                          "line. Any language - it is translated for reading.")
        self.submit = QPushButton("Analyse narrative")
        self.submit.setObjectName("Primary")
        self.submit.clicked.connect(self._submit)
        seed = link_button("Load the five seed incidents")
        seed.clicked.connect(self.seed_requested.emit)
        for widget in (reference_label, self.reference, narrative_label):
            paste_form.addWidget(widget)
        paste_form.addWidget(self.narrative, 1)
        paste_form.addWidget(self.submit)
        paste_form.addWidget(seed, 0, Qt.AlignmentFlag.AlignLeft)
        self.inputs.add_page(paste)

        # -- right: documents and the selected one's text -----------------------------
        self.documents = Card("Documents", "")
        badges = QWidget()
        badge_row = QHBoxLayout(badges)
        badge_row.setContentsMargins(0, 0, 0, 0)
        badge_row.setSpacing(6)
        self.processing = ProcessingBadge()
        self.failed = Pill("✕ 0 failed", "fail")
        self.attention = Pill("◆ 0 need attention", "warn")
        for widget in (self.processing, self.failed, self.attention):
            badge_row.addWidget(widget)
        self.documents.add_head(badges)
        self.documents.body.setContentsMargins(0, 0, 0, 0)
        self.table = DesignTable(DOCUMENT_COLUMNS)
        self.table.row_clicked.connect(self.document_selected.emit)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        self.documents.add(self.table, 1)

        self.detail_name = QLabel("")
        self.detail_name.setObjectName("DetailName")
        self.detail = TabbedCard(("Extracted text", "Source", "Processing log"), self.detail_name)
        self.text_caption = QLabel("")
        self.text_caption.setObjectName("MonoCaption")
        self.text_view = QPlainTextEdit()
        self.text_view.setObjectName("Reader")
        self.text_view.setReadOnly(True)
        self.source_view = QPlainTextEdit()
        self.source_view.setObjectName("Reader")
        self.source_view.setReadOnly(True)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("ReaderMono")
        self.log_view.setReadOnly(True)
        text_page = QWidget()
        text_layout = QVBoxLayout(text_page)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        text_layout.addWidget(self.text_caption)
        text_layout.addWidget(self.text_view, 1)
        self.detail.add_page(text_page)
        self.detail.add_page(self.source_view)
        self.detail.add_page(self.log_view)

        right = QVBoxLayout()
        right.setSpacing(12)
        right.addWidget(self.documents, 11)
        right.addWidget(self.detail, 13)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self.inputs)
        row.addLayout(right, 1)
        self.body.addLayout(row, 1)
        self.set_detail("", "", "", "", "")

    # -- the left side -------------------------------------------------------------

    def _choose(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose report files", os.getcwd(),
                                                UPLOAD_FILTER)
        if paths:
            self.files_chosen.emit(paths)

    def _submit(self) -> None:
        text = self.narrative.toPlainText().strip()
        if text:
            self.narrative_submitted.emit(text, self.reference.text().strip())

    def clear_narrative(self) -> None:
        self.narrative.clear()
        self.reference.clear()

    def _menu(self, point) -> None:
        row = self.table.rowAt(point.y())
        if row < 0:
            return
        menu = QMenu(self)
        analyse = menu.addAction("Analyse this document")
        retry = menu.addAction("Read it again")
        menu.addSeparator()
        remove = menu.addAction("Remove from the list")
        chosen = menu.exec(self.table.viewport().mapToGlobal(point))
        if chosen is analyse:
            self.analyse_requested.emit(row)
        elif chosen is retry:
            self.retry_requested.emit(row)
        elif chosen is remove:
            self.remove_requested.emit(row)

    # -- state from the window -------------------------------------------------------

    def set_engines(self, text: str) -> None:
        self.engines.setText(text)

    def set_pipeline(self, values: Sequence[str]) -> None:
        for cell, value in zip(self.pipeline.cells, values):
            cell.set(value)

    def set_staged(self, count: int, busy: bool) -> None:
        self.drop.staged.setText(f"{count} file(s) ready to process" if count else "")
        self.start.setEnabled(bool(count) and not busy)
        self.start.setText("Processing…" if busy else "Start processing")

    def set_documents(self, rows: Sequence[Dict[str, object]], caption: str,
                      processing: int, failed: int, attention: int) -> None:
        self.documents.caption.setText(caption)
        self.processing.set_count(processing)
        self.failed.set(f"✕ {failed} failed", "fail")
        self.attention.set(f"◆ {attention} need attention", "warn")
        selected = self.table.currentRow()
        self.table.set_rows(rows)
        if 0 <= selected < len(rows):
            self.table.selectRow(selected)

    def set_detail(self, name: str, caption: str, text: str, source: str, log: str) -> None:
        self.detail_name.setText(name)
        self.text_caption.setText(caption)
        self.text_caption.setVisible(bool(caption))
        self.text_view.setPlainText(text or ("Select a document to read what was extracted "
                                             "from it." if not name else "No text was extracted."))
        self.source_view.setPlainText(source)
        self.log_view.setPlainText(log)
