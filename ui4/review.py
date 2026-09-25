"""HSE Review - the case list and one case, with the human decision beneath it.

From the design: the queue filtered by Open, Critical, Disagreement, Needs
info, Reviewed and Over 7 days; one case with the engine's assessment boxed
and labelled "not a decision", the report as written (or as translated, with
the original a click away), the cues the engine found, its reasoning step by
step and the state of each model; and a decision bar that says whose name
the decision is recorded under.

:class:`CaseView` is the right-hand side on its own, so the report drill-down
shows a report exactly as a case is shown, less the decision bar.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from .kit import Card, Col, DesignTable, Page, Pill, clear_layout, scrolling

__all__ = ["CASE_COLUMNS", "CaseView", "FILTERS", "ReviewPage", "reasoning", "evidence_rows"]

FILTERS = (("open", "Open"), ("critical", "Critical"), ("disagreement", "Disagreement"),
           ("info", "Needs info"), ("reviewed", "Reviewed"), ("old", "Over 7 days"))

CASE_COLUMNS = (
    Col("reference", "Ref", 90, "mono", style=lambda row: ("", True)),
    Col("risk_score", "Risk", 84, "risk"),
    Col("sif", "SIF", 74, value=lambda row: "Potential" if row.get("sif_potential") else "No"),
    Col("trigger", "Trigger", 0),
    Col("status", "Status", 128, "pill"),
    Col("date", "Date", 74, "mono"),
)


def _l(text: str, name: str, wrap: bool = True) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(wrap)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def evidence_rows(row: Dict[str, object]) -> List[Tuple[str, str]]:
    """The cues the engine matched, as (quote, what it is evidence of)."""
    evidence = row.get("evidence") or {}
    found: List[Tuple[str, str]] = []
    energy = str(row.get("energy_source") or "").split(" + ")[0].split(" / ")[0].lower()
    barrier = str(row.get("barrier_failure") or "").split(";")[0].split(" / ")[0]
    kinds = {"energy": f"Energy · {energy or 'source'}",
             "barrier": f"Barrier · {barrier.lower() or 'control'}",
             "rule": f"Rule · {str(row.get('iogp_rule') or '').lower()}",
             "activity": "Activity", "exposure": "Exposure · point of work"}
    for line in evidence.get("lexical_cues") or []:
        head, _, cues = str(line).partition(":")
        kind = head.replace("cues", "").strip().lower()
        for cue in cues.split(","):
            cue = cue.strip()
            if cue and len(found) < 12 and all(cue != quote.strip("\u201c\u201d")
                                               for quote, _kind in found):
                found.append((f"“{cue}”", kinds.get(kind, kind.title() or "Cue")))
    for kind, match in (evidence.get("semantic_matches") or {}).items():
        if isinstance(match, (list, tuple)) and len(match) == 2:
            found.append((f"close to “{match[0]}”",
                          f"Semantic · {kind} ({float(match[1]):.2f})"))
    return found


def reasoning(row: Dict[str, object]) -> List[str]:
    """How the engine got to its call, one step a line."""
    steps: List[str] = []
    energy = str(row.get("energy_source") or "no energy").split(" + ")[0].lower()
    barrier = str(row.get("barrier_failure") or "no failed barrier").split(";")[0]
    lexical = "SIF" if row.get("lexical_flag") else "not SIF"
    steps.append(f"Lexical: {energy} + {barrier.lower()} → {lexical}")
    if row.get("semantic_active"):
        steps.append("Semantic encoder " + ("agrees" if row.get("semantic_flag")
                                            == row.get("lexical_flag") else "differs")
                     + (" → SIF" if row.get("semantic_flag") else " → not SIF"))
    else:
        steps.append("Semantic encoder inactive (offline encoder) - lexical rules decide")
    if row.get("ml_active") and row.get("ml_probability") is not None:
        probability = float(row["ml_probability"])
        steps.append(f"Learned model (XGBoost) {probability:.2f} → "
                     + ("SIF" if row.get("ml_flag") else "not SIF"))
    else:
        steps.append("Learned model not attached - no third opinion")
    if row.get("llm_active"):
        steps.append("Local LLM " + ("flags SIF" if row.get("llm_flag") else "does not flag SIF")
                     + (f": {row.get('llm_rationale')}" if row.get("llm_rationale") else ""))
    risk = (row.get("evidence") or {}).get("risk") or {}
    drivers = risk.get("drivers") or {}
    if drivers:
        steps.append(
            f"Score {float(row.get('risk_score') or 0):.0f} = 100 × P(SIF) "
            f"{float(drivers.get('p_sif', 0)):.2f} × severity "
            f"{float(drivers.get('energy_severity', 0)):.2f} × barrier "
            f"{float(drivers.get('barrier_criticality', 0)):.2f} × evidence "
            f"{float(drivers.get('evidence_factor', 0)):.2f}")
    return steps


class CaseView(QWidget):
    """One report: head, engine assessment, text, evidence, reasoning."""

    def __init__(self) -> None:
        super().__init__()
        self.reference = _l("", "CaseRef", wrap=False)
        self.meta = _l("", "CaseMeta")
        self.pills = QHBoxLayout()
        self.pills.setSpacing(6)
        head = QFrame()
        head.setObjectName("CaseHead")
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(16, 12, 16, 12)
        head_layout.setSpacing(12)
        words = QVBoxLayout()
        words.setSpacing(2)
        words.addWidget(self.reference)
        words.addWidget(self.meta)
        head_layout.addLayout(words, 1)
        head_layout.addLayout(self.pills)

        body = QWidget()
        content = QVBoxLayout(body)
        content.setContentsMargins(16, 14, 16, 16)
        content.setSpacing(12)

        self.assessment = QFrame()
        self.assessment.setObjectName("Assessment")
        box = QVBoxLayout(self.assessment)
        box.setContentsMargins(14, 12, 14, 14)
        box.setSpacing(10)
        top = QHBoxLayout()
        top.addWidget(_l("ENGINE ASSESSMENT — NOT A DECISION", "MonoTitle", wrap=False))
        top.addStretch(1)
        self.trigger = _l("", "CaseMeta", wrap=False)
        top.addWidget(self.trigger)
        box.addLayout(top)
        self.explanation = _l("", "Explanation")
        box.addWidget(self.explanation)
        self.facts = QGridLayout()
        self.facts.setHorizontalSpacing(20)
        self.facts.setVerticalSpacing(10)
        box.addLayout(self.facts)
        content.addWidget(self.assessment)

        text_head = QHBoxLayout()
        text_head.setSpacing(10)
        text_head.addWidget(_l("Report text", "SubTitle", wrap=False))
        self.text_tag = _l("", "MonoTag", wrap=False)
        text_head.addWidget(self.text_tag)
        text_head.addStretch(1)
        self.original_button = QPushButton("Show the original")
        self.original_button.setCheckable(True)
        self.original_button.toggled.connect(self._toggle_original)
        text_head.addWidget(self.original_button)
        content.addLayout(text_head)
        self.text = _l("", "ReportText")
        content.addWidget(self.text)

        lower = QHBoxLayout()
        lower.setSpacing(24)
        cues = QVBoxLayout()
        cues.setSpacing(8)
        cues.addWidget(_l("Evidence — cues found in the text", "SubTitle", wrap=False))
        self.cues = QGridLayout()
        self.cues.setSpacing(0)
        cue_frame = QFrame()
        cue_frame.setObjectName("CueTable")
        cue_frame.setLayout(self.cues)
        cues.addWidget(cue_frame)
        cues.addStretch(1)
        steps = QVBoxLayout()
        steps.setSpacing(8)
        steps.addWidget(_l("Engine reasoning", "SubTitle", wrap=False))
        self.steps = _l("", "Steps")
        self.steps.setTextFormat(Qt.TextFormat.RichText)
        steps.addWidget(self.steps)
        steps.addWidget(_l("Model status", "SubTitle", wrap=False))
        self.model_status = _l("", "CaseMeta")
        steps.addWidget(self.model_status)
        steps.addStretch(1)
        lower.addLayout(cues, 11)
        lower.addLayout(steps, 10)
        content.addLayout(lower)
        content.addStretch(1)

        self.empty = _l("Choose a case on the left to read it.", "Faint")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll = scrolling(body)
        self.scroll.setObjectName("CaseScroll")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(head)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(self.empty, 1)
        self._head = head
        self._row: Dict[str, object] = {}
        self.show_case(None)

    def _toggle_original(self, original: bool) -> None:
        row = self._row
        translated = str(row.get("translated_text") or "")
        self.text.setText(str(row.get("raw_text") or "") if original or not translated
                          else translated)
        self.original_button.setText("Show the translation" if original else "Show the original")
        language = str(row.get("source_language") or "the original").split(" /")[0]
        self.text_tag.setText(f"ORIGINAL · {language.upper()}" if original else
                              f"ENGLISH — TRANSLATED FROM {language.upper()}")

    def show_case(self, row: Optional[Dict[str, object]], *, status: Tuple[str, str] = ("", ""),
                  meta: str = "", waiting: str = "") -> None:
        has = row is not None
        self._head.setVisible(has)
        self.scroll.setVisible(has)
        self.empty.setVisible(not has)
        if row is None:
            self._row = {}
            return
        self._row = row
        self.reference.setText(str(row.get("reference") or ""))
        self.meta.setText(meta)
        clear_layout(self.pills)
        risk = float(row.get("risk_score") or 0)
        band = str(row.get("risk_band") or "")
        self.pills.addWidget(Pill(f"ENGINE · {'▲ ' if risk >= 85 else ''}{band} {risk:.0f}",
                                  "engine"))
        self.pills.addWidget(Pill("ENGINE · " + ("SIF potential" if row.get("sif_potential")
                                                      else "not SIF"), "engine"))
        if status[0]:
            self.pills.addWidget(Pill(*status))
        trigger = str(row.get("review_trigger") or "")
        self.trigger.setText(" · ".join(part for part in (
            f"Trigger: {trigger}" if trigger else "Not queued for review",
            f"waiting {waiting}" if waiting else "") if part))
        explanation = str(row.get("explanation") or "")
        lead = "Fatal potential. " if row.get("sif_potential") else ""
        self.explanation.setText(lead + explanation[:1].upper() + explanation[1:])
        clear_layout(self.facts)
        facts = (("IOGP rule", row.get("iogp_rule")), ("Energy source", row.get("energy_source")),
                 ("Failed barrier", row.get("barrier_failure")), ("Activity", row.get("activity")),
                 ("Location", row.get("site") or row.get("location")),
                 ("Source", row.get("source") or "pasted or seeded"))
        for index, (name, value) in enumerate(facts):
            cell = QVBoxLayout()
            cell.setSpacing(2)
            cell.addWidget(_l(name, "FactName", wrap=False))
            cell.addWidget(_l(str(value or "-"), "FactMono" if name == "Source" else "FactValue"))
            self.facts.addLayout(cell, index // 3, index % 3, Qt.AlignmentFlag.AlignTop)
        for column in range(3):
            self.facts.setColumnStretch(column, 1)

        translated = bool(row.get("translated_text"))
        self.original_button.setVisible(translated)
        self.original_button.blockSignals(True)
        self.original_button.setChecked(False)
        self.original_button.blockSignals(False)
        if translated:
            self._toggle_original(False)
        else:
            self.text.setText(str(row.get("raw_text") or ""))
            self.text_tag.setText("ENGLISH AS WRITTEN")

        clear_layout(self.cues)
        cues = evidence_rows(row) or [("No cue matched", "the engine found nothing to quote")]
        for index, (quote, kind) in enumerate(cues):
            self.cues.addWidget(_l(quote, "CueQuote"), index, 0)
            self.cues.addWidget(_l(kind, "CueKind"), index, 1)
        self.cues.setColumnStretch(0, 11)
        self.cues.setColumnStretch(1, 10)
        items = "".join(f"<li style='margin-bottom:4px'>{step}</li>" for step in reasoning(row))
        self.steps.setText(f"<ol style='margin-left:-22px'>{items}</ol>")
        evidence = row.get("evidence") or {}
        self.model_status.setText(str(evidence.get("decision_path") or "-")
                                  + (f"\nEncoder: {row.get('encoder')}" if row.get("encoder") else ""))
        self.scroll.verticalScrollBar().setValue(0)


class DecisionBar(QFrame):
    """HUMAN DECISION - three calls, and whose name they go under."""

    decided = pyqtSignal(str)
    undo_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("DecisionBar")
        self.recorded = _l("", "CaseMeta", wrap=False)
        self.confirm = QPushButton("▲ Confirm SIF")
        self.confirm.setObjectName("Danger")
        self.reject = QPushButton("Not SIF")
        self.unclear = QPushButton("? Need more information")
        for button, decision in ((self.confirm, "confirmed"), (self.reject, "rejected"),
                                 (self.unclear, "unclear")):
            button.setObjectName(button.objectName() or "DecisionButton")
            button.clicked.connect(lambda _checked, d=decision: self.decided.emit(d))
        self.undo = QPushButton("Undo the last decision")
        self.undo.setObjectName("Link")
        self.undo.clicked.connect(self.undo_requested.emit)
        hint = _l("Read the report and evidence first. The engine result above is not a "
                  "decision.", "Hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        hint.setMaximumWidth(330)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(_l("HUMAN DECISION", "MonoTitle", wrap=False))
        top.addWidget(self.recorded)
        top.addStretch(1)
        top.addWidget(self.undo)
        row = QHBoxLayout()
        row.setSpacing(10)
        for button in (self.confirm, self.reject, self.unclear):
            row.addWidget(button)
        row.addStretch(1)
        row.addWidget(hint)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 12)
        layout.setSpacing(8)
        layout.addLayout(top)
        layout.addLayout(row)

    def set_enabled(self, allowed: bool, reason: str = "") -> None:
        for button in (self.confirm, self.reject, self.unclear):
            button.setEnabled(allowed)
            button.setToolTip("" if allowed else reason)


class ReviewPage(Page):
    case_selected = pyqtSignal(str)
    decided = pyqtSignal(str, str)            # reference, decision
    undo_requested = pyqtSignal()
    export_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__("HSE Review", "")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search ref, location, activity")
        self.search.setFixedWidth(236)
        self.search.textChanged.connect(lambda _text: self._apply())
        export = QPushButton("Export decision trail")
        export.clicked.connect(self.export_requested.emit)
        self.head.add(self.search)
        self.head.add(export)

        self.filter_key = "open"
        self.rows: List[Dict[str, object]] = []
        self.tabs = QTabBar()
        self.tabs.setObjectName("Filters")
        self.tabs.setUsesScrollButtons(False)
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        for _key, label in FILTERS:
            self.tabs.addTab(label)
        self.tabs.currentChanged.connect(self._tab)
        self.list_card = Card(flush=True)
        tab_head = QFrame()
        tab_head.setObjectName("TabHead")
        tab_row = QHBoxLayout(tab_head)
        tab_row.setContentsMargins(6, 0, 6, 0)
        tab_row.addWidget(self.tabs)
        tab_row.addStretch(1)
        self.list_card.body.addWidget(tab_head)
        self.table = DesignTable(CASE_COLUMNS, row_height=52, wrap=True)
        self.table.row_clicked.connect(self._clicked)
        self.list_card.add(self.table, 1)
        self.list_card.setFixedWidth(530)

        self.case_card = QFrame()
        self.case_card.setObjectName("Card")
        case_layout = QVBoxLayout(self.case_card)
        case_layout.setContentsMargins(0, 0, 0, 0)
        case_layout.setSpacing(0)
        self.case = CaseView()
        self.bar = DecisionBar()
        self.bar.decided.connect(self._decide)
        self.bar.undo_requested.connect(self.undo_requested.emit)
        case_layout.addWidget(self.case, 1)
        case_layout.addWidget(self.bar)

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self.list_card)
        row.addWidget(self.case_card, 1)
        self.body.addLayout(row, 1)
        self.current = ""

    # -- the list -------------------------------------------------------------------

    def _tab(self, index: int) -> None:
        self.filter_key = FILTERS[index][0]
        self._apply()

    def set_counts(self, counts: Dict[str, int]) -> None:
        for index, (key, label) in enumerate(FILTERS):
            self.tabs.setTabText(index, f"{label}  {counts.get(key, 0)}")

    def set_rows(self, rows: Sequence[Dict[str, object]]) -> None:
        """Every case, each carrying the filter keys it belongs to in ``_in``."""
        self.rows = list(rows)
        self._apply()

    def _apply(self) -> None:
        needle = self.search.text().strip().lower()
        shown = [row for row in self.rows if self.filter_key in row.get("_in", ())
                 and (not needle or needle in " ".join(
                     str(row.get(key, "")) for key in ("reference", "site", "location",
                                                       "activity", "trigger")).lower())]
        self.table.set_rows(shown)
        references = [str(row.get("reference")) for row in shown]
        if self.current in references:
            self.table.selectRow(references.index(self.current))
        elif shown:
            self.table.selectRow(0)
            self._clicked(0)
        else:
            self.current = ""
            self.case_selected.emit("")

    def _clicked(self, index: int) -> None:
        if 0 <= index < len(self.table.rows):
            self.current = str(self.table.rows[index].get("reference", ""))
            self.case_selected.emit(self.current)

    def select(self, reference: str) -> None:
        """Show ``reference``'s case, switching to a tab that holds it."""
        for tab_index, (key, _label) in enumerate(FILTERS):
            if any(str(row.get("reference")) == reference and key in row.get("_in", ())
                   for row in self.rows):
                self.current = reference
                if self.tabs.currentIndex() != tab_index and self.filter_key not in next(
                        (row.get("_in", ()) for row in self.rows
                         if str(row.get("reference")) == reference), ()):
                    self.tabs.setCurrentIndex(tab_index)
                else:
                    self._apply()
                self.case_selected.emit(reference)
                return

    def _decide(self, decision: str) -> None:
        if self.current:
            self.decided.emit(self.current, decision)
