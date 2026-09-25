"""Engines - the six engines behind the console, each with its state and control.

From the design: one card per engine (semantic encoder, OCR, local LLM, the
risk/SIF pipeline, the learned model, experiment tracking) with its status,
model, version, host, connection and last run, a note and one action; then
the training panel, the recent runs and what the model leans on.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
)

from .kit import BarList, Card, Col, DesignTable, KeyValues, Page, Pill

__all__ = ["ENGINE_KEYS", "EngineCard", "EnginesPage", "RUN_COLUMNS"]

ENGINE_KEYS = (("encoder", "Semantic encoder"), ("ocr", "OCR engine"), ("llm", "Local LLM"),
               ("risk", "Risk / SIF analysis"), ("model", "Learned model"),
               ("tracking", "Experiment tracking"))

RUN_COLUMNS = (
    Col("run_id", "Run", 72, "mono"),
    Col("started", "Started", 118, "mono"),
    Col("labels", "Labels", 0),
    Col("samples", "Samples", 70, align="right"),
    Col("f1", "F1", 54, align="right"),
    Col("roc_auc", "AUC", 54, align="right"),
    Col("state", "Status", 150, "pill"),
)


class EngineCard(Card):
    """One engine: status pill, five facts, a note and an action."""

    action = pyqtSignal()

    def __init__(self, title: str, action: str) -> None:
        super().__init__(title, "")
        self.pill = Pill("", "grey")
        self.add_head(self.pill)
        self.facts = KeyValues(1, label_width=96)
        self.body.setContentsMargins(14, 12, 14, 0)
        self.add(self.facts)
        self.body.addStretch(1)
        foot = QFrame()
        foot.setObjectName("CardFoot")
        row = QHBoxLayout(foot)
        row.setContentsMargins(14, 8, 12, 10)
        self.note = QLabel("")
        self.note.setObjectName("CardCaption")
        self.note.setWordWrap(True)
        row.addWidget(self.note, 1)
        self.button = QPushButton(action)
        self.button.clicked.connect(self.action.emit)
        self.button.setVisible(bool(action))
        row.addWidget(self.button)
        self.layout().addWidget(foot)

    def show_state(self, pill: Tuple[str, str], facts: Sequence[Tuple[str, str]],
                   note: str, action: str = "") -> None:
        self.pill.set(*pill)
        self.facts.set_pairs(facts, mono=("Version", "Host", "Connection", "Last run"))
        self.note.setText(note)
        if action:
            self.button.setText(action)


class EnginesPage(Page):
    check_all_requested = pyqtSignal()
    engine_action = pyqtSignal(str)
    train_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__("Engines", "", scroll=True)
        check = QPushButton("Check all connections")
        check.clicked.connect(self.check_all_requested.emit)
        self.head.add(check)

        actions = {"encoder": "Switch encoder", "ocr": "Verify OCR models",
                   "llm": "Test connection", "risk": "Run evaluation",
                   "model": "Detach model", "tracking": "Open run history"}
        self.cards: Dict[str, EngineCard] = {}
        grid = QGridLayout()
        grid.setSpacing(12)
        for index, (key, title) in enumerate(ENGINE_KEYS):
            card = EngineCard(title, actions[key])
            card.action.connect(lambda k=key: self.engine_action.emit(k))
            card.setMinimumHeight(232)
            self.cards[key] = card
            grid.addWidget(card, index // 3, index % 3)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        self.body.addLayout(grid)

        # -- training ------------------------------------------------------------------
        self.train = Card("Train learned model (XGBoost)", "")
        self.train.add(self._field("Label source"))
        self.reviewed = QRadioButton("Reviewed human decisions")
        self.reviewed_count = QLabel("")
        self.reviewed_count.setObjectName("MonoFaint")
        self.pipeline = QRadioButton("Pipeline verdicts")
        distil = QLabel("(distillation)")
        distil.setObjectName("CardCaption")
        group = QButtonGroup(self)
        for button in (self.reviewed, self.pipeline):
            group.addButton(button)
        self.reviewed.setChecked(True)
        for button, extra in ((self.reviewed, self.reviewed_count), (self.pipeline, distil)):
            line = QHBoxLayout()
            line.setSpacing(8)
            line.addWidget(button)
            line.addWidget(extra)
            line.addStretch(1)
            self.train.body.addLayout(line)
        params = QGridLayout()
        params.setHorizontalSpacing(12)
        self.trees = QSpinBox()
        self.trees.setRange(20, 1000)
        self.trees.setSingleStep(20)
        self.trees.setValue(220)
        self.trees.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.depth = QSpinBox()
        self.depth.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.depth.setRange(2, 10)
        self.depth.setValue(4)
        params.addWidget(self._field("n_estimators"), 0, 0)
        params.addWidget(self._field("max_depth"), 0, 1)
        params.addWidget(self.trees, 1, 0)
        params.addWidget(self.depth, 1, 1)
        self.train.body.addLayout(params)
        self.train_button = QPushButton("Train model")
        self.train_button.setObjectName("Primary")
        self.train_button.clicked.connect(self.train_requested.emit)
        self.train.add(self.train_button)
        self.train_note = QLabel("")
        self.train_note.setObjectName("CardCaption")
        self.train_note.setWordWrap(True)
        self.train.add(self.train_note)
        self.train.body.addStretch(1)

        self.runs = Card("Recent training runs", "", flush=True)
        self.runs_caption = QLabel("")
        self.runs_caption.setObjectName("CardCaption")
        self.runs.add_head(self.runs_caption)
        self.run_table = DesignTable(RUN_COLUMNS, row_height=34)
        self.runs.add(self.run_table, 1)

        self.importance = Card("Feature importance", "")
        self.importance_caption = QLabel("")
        self.importance_caption.setObjectName("CardCaption")
        self.importance.add_head(self.importance_caption)
        self.importance_bars = BarList(label_ratio=0.52)
        self.importance_bars.empty = "Train a model to see what it leans on."
        self.importance.add(self.importance_bars)
        self.importance.body.addStretch(1)

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self.train, 30)
        row.addWidget(self.runs, 43)
        row.addWidget(self.importance, 25)
        for card in (self.train, self.runs, self.importance):
            card.setMinimumHeight(330)
        self.body.addLayout(row)

    @staticmethod
    def _field(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    @property
    def label_choice(self) -> str:
        return "pipeline" if self.pipeline.isChecked() else "reviewed"

    def show_runs(self, rows, caption: str) -> None:
        self.run_table.set_rows(rows)
        self.runs_caption.setText(caption)

    def show_importance(self, items, caption: str) -> None:
        self.importance_bars.set_items(items)
        self.importance_caption.setText(caption)
