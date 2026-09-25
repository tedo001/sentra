"""SENTRA: the two-workspace console in the revamp's design, with its data kept.

Everything :mod:`main4` does, laid out as the revamp draws it, plus three
things the console did not have:

* **A local SQL database** (:mod:`sif.datastore`) - every analysed report,
  review decision, compliance action and audit entry is kept in SQLite on
  this workstation, or in a PostgreSQL / MySQL server the site shares. It is
  loaded when SENTRA starts, written after every analysis run and decision,
  and synced both ways on demand.
* **A vector database** (:mod:`sif.vectorstore`) - each report's embedding,
  so an administrator can find past reports like a new one in plain words.
* **Encrypted off-site backup** (:mod:`sif.backup`) - to a synced cloud
  folder, S3-compatible storage or WebDAV, on demand or on a schedule, with
  verify and a non-destructive restore. On the administrator's new
  *Data & Backup* tab.

Two contextual-intelligence features sit on top of the analysis:

* **Asset Safety Memory** (:mod:`sif.assets`) - every asset's incidents, near
  misses, hazards, control failures, SIF precursors and corrective actions;
  each new report is read against it for recurring hazards, repeated control
  failures and emerging precursor patterns. An *Asset Memory* tab in the HSE
  workspace, and a panel in every review case.
* **Work-Hold Recommendation** (:mod:`sif.workhold`) - Continue, HSE Review
  Required or Work-Hold Recommended for every report, with the factors behind
  it; holds lead Home, have their own review filter, and are written to the
  audit log when first raised.

And the local LLM is always on: ``gemma2:latest`` through Ollama, attached at
start-up, shown as a button in the title row that says whether it answers.
"""

from __future__ import annotations

import os
from datetime import datetime
from types import SimpleNamespace
from typing import Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from main2 import requires
from main4 import ADMIN_TABS, HSE_TABS, WorkspaceWindow
from sif import backup, prefs
from sif.accounts import ANALYSE, CONFIGURE, AccountStore, Session
from sif.actions import ComplianceAction
from sif.assets import AssetMemory
from sif.workhold import HOLD, Recommendation, recommend
from sif.datastore import DataStore, default_url, describe_url
from sif.llm import DEFAULT_HOST, OllamaEngine
from sif.review import ReviewDecision, fingerprint
from sif.vault import Vault
from sif.vectorstore import VectorStore
from ui4.admin_wiring import setting
from ui4.present import stamp, weekly_table
from ui5.actions import SentraActions
from ui5.assets import KIND_LABEL, LEVEL_TONE, AssetMemoryPage
from ui5.dashboard import VIOLET, SentraDashboard
from ui5.data import DataPage
from ui5.llm import LLMButton
from ui5.review import SentraReview
from ui5.tasks import Task

__all__ = ["SentraWindow", "SENTRA_ADMIN_TABS", "SENTRA_HSE_TABS", "LLM_MODEL", "row_fingerprint"]

#: The model SENTRA keeps switched on.
LLM_MODEL = "gemma2:latest"
#: Seconds between quiet re-checks of the LLM host.
LLM_RECHECK_S = 120
#: Minutes between looks at whether a scheduled backup is owed.
BACKUP_CHECK_MIN = 15

SENTRA_HSE_TABS = tuple(tab for tab in HSE_TABS if tab[0] != "profile") + (
    ("assets", "Asset Memory"), ("profile", "Profile"))
SENTRA_ADMIN_TABS = tuple(tab for tab in ADMIN_TABS if tab[0] != "profile") + (
    ("data", "Data && Backup"), ("profile", "Profile"))

#: Where the database URL's password is kept, apart from the URL.
DB_SECRET = "database_password"
BACKUP_SECRETS = ("s3_secret", "webdav_password", "passphrase")
DEFAULT_PLACE = "Field HQ Duliajan · Assam"


def short_time(value: object) -> str:
    """'14:06' today, '24 Sep 14:06' before - what fits in a figure cell."""
    try:
        when = datetime.fromisoformat(str(value)[:19])
    except ValueError:
        return str(value or "-")
    if when.date() == datetime.now().date():
        return when.strftime("%H:%M")
    return when.strftime("%d %b %H:%M").lstrip("0")


def row_fingerprint(row: Dict[str, object]) -> str:
    """The same identity :func:`sif.review.fingerprint` gives the row's result."""
    return fingerprint(SimpleNamespace(reference=row.get("reference", ""),
                                       raw_text=row.get("raw_text", "")))


def split_url(url: str) -> Tuple[str, str]:
    """(URL without its password, the password) - the password goes to the vault."""
    from sqlalchemy.engine import make_url

    try:
        parsed = make_url(url)
    except Exception:  # noqa: BLE001 - kept as typed; the test will say what is wrong
        return url, ""
    if not parsed.password:
        return url, ""
    return (parsed.set(password=None).render_as_string(hide_password=False),
            str(parsed.password))


def join_url(url: str, password: str) -> str:
    from sqlalchemy.engine import make_url

    if not (url and password):
        return url
    try:
        return make_url(url).set(password=password).render_as_string(hide_password=False)
    except Exception:  # noqa: BLE001
        return url


class SentraWindow(WorkspaceWindow):
    """The revamp's console: build 4's controller, its data kept and backed up."""

    header_logo = ("oil_logo_dark.png",)
    actions_view_class = SentraActions
    dashboard_page_class = SentraDashboard
    review_page_class = SentraReview

    def __init__(self, session: Optional[Session] = None,
                 accounts: Optional[AccountStore] = None, *,
                 datastore: Optional[DataStore] = None, vault: Optional[Vault] = None,
                 load_on_start: Optional[bool] = None, probe_llm: bool = True) -> None:
        self._tasks: Dict[str, Task] = {}
        self.asset_memory = AssetMemory()
        self.recommendations: Dict[str, Recommendation] = {}
        self._memory_dirty = True
        self._holds_raised: Optional[set] = None
        self._llm_state = "checking"
        self.vault = vault or Vault()
        self._db_error = ""
        self.datastore = datastore or self._open_database()
        self.vectors = VectorStore(self.datastore)
        super().__init__(session, accounts)

        # The local LLM, always on unless an administrator switched it off. It
        # is attached to the pipeline once the host has answered, so a machine
        # without Ollama analyses at full speed instead of timing out per report.
        self.llm = OllamaEngine(host=str(prefs.get("llm_host", "") or DEFAULT_HOST),
                                model=str(prefs.get("llm_model", "") or LLM_MODEL))
        self.llm_enabled = bool(prefs.get("llm_always_on", True))
        self.llm_online = False
        self.llm_message = "not checked yet"
        self.pipeline.attach_llm(None)
        self.llm_button.set_model(self.llm.model)
        self.llm_button.set_state("checking" if self.llm_enabled else "off")
        self.llm_timer = QTimer(self)
        self.llm_timer.timeout.connect(lambda: self.check_llm(silent=True))
        self.backup_timer = QTimer(self)
        self.backup_timer.timeout.connect(self._scheduled_backup)
        if probe_llm:
            self.check_llm()
            self.llm_timer.start(LLM_RECHECK_S * 1000)
            self.backup_timer.start(BACKUP_CHECK_MIN * 60 * 1000)
            # A backup owed since the machine was last on runs a minute after start.
            self.first_backup_check = QTimer(self)
            self.first_backup_check.setSingleShot(True)
            self.first_backup_check.timeout.connect(self._scheduled_backup)
            self.first_backup_check.start(60_000)

        if load_on_start if load_on_start is not None else bool(prefs.get("load_on_start", True)):
            self.sync_now(pull_only=True, quiet=True)

    # -- the shell -------------------------------------------------------------------

    @property
    def tabs(self):
        return SENTRA_ADMIN_TABS if self.workspace == "admin" else SENTRA_HSE_TABS

    def _build_shell(self) -> None:
        super()._build_shell()
        self.shell_header.setFixedHeight(52)
        self.llm_button = LLMButton(LLM_MODEL, can_configure=self.session.can(CONFIGURE))
        self.llm_button.check_requested.connect(self.check_llm)
        self.llm_button.enable_requested.connect(self.set_llm_enabled)
        self.llm_button.settings_requested.connect(lambda: self.navigate("engines"))
        self.shell_header.right.insertWidget(1, self.llm_button)

        # Action Items: the legend, filters, view and add button in the page head.
        page = self.pages.widget(self._page_index["actions"])
        for widget in self.actions_view.head_widgets():
            page.head.add(widget)
        self.hotspots_page.barrier_bars.tone = VIOLET

        if self.workspace == "admin":
            self.data_page = self._build_data_page()
            self._page_index["data"] = self.pages.addWidget(self.data_page)
        else:
            self.assets_page = self._build_assets_page()
            self._page_index["assets"] = self.pages.addWidget(self.assets_page)
        review = self.review_page
        review.recommendation.action_requested.connect(
            lambda reference: self.add_action(reference=reference))
        review.memory.asset_requested.connect(self.open_asset)
        review.memory.report_requested.connect(self.open_case)

    def _apply_identity(self) -> None:
        super()._apply_identity()
        if hasattr(self, "shell_header"):
            place = str(setting("place"))
            self.shell_header.place.setText("Health, Safety and Environment"
                                            if place in ("", DEFAULT_PLACE) else place)

    def navigate(self, key: str) -> None:
        super().navigate(key)
        if key == "data" and self.workspace == "admin" and self._shell_ready:
            self._refresh_data_page()
        elif key == "assets" and self._shell_ready and hasattr(self, "assets_page"):
            self._refresh_assets_page()

    def _refresh_dashboard(self) -> None:
        super()._refresh_dashboard()
        period = self.dashboard_page.filters[0]
        weeks = {"30": 5, "90": 13, "365": 52}.get(period, 13)
        label = {"30": "last 30 days", "90": "last 90 days", "365": "last 12 months"}[period]
        self.dashboard_page.set_weekly(weekly_table(getattr(self, "_dashboard_rows", []),
                                                    weeks=weeks), label)

    # -- background jobs --------------------------------------------------------------

    def _run(self, key: str, label: str, job: Callable[[Task], object],
             done: Callable[[bool, object], None]) -> bool:
        if key in self._tasks:
            self._set_status(f"{label} is already running.")
            return False
        task = Task(label, job, self)
        self._tasks[key] = task
        task.done.connect(lambda ok, result: self._finished(key, ok, result, done))
        self._show_busy()
        task.start()
        return True

    def _finished(self, key: str, ok: bool, result: object,
                  done: Callable[[bool, object], None]) -> None:
        task = self._tasks.pop(key, None)
        if task is not None:
            task.wait(5000)
            task.deleteLater()
        try:
            done(ok, result)
        finally:
            self._show_busy()

    def _show_busy(self) -> None:
        if hasattr(self, "data_page"):
            running = [task.name for key, task in self._tasks.items() if key != "llm"]
            self.data_page.set_busy(", ".join(running))

    def busy(self) -> bool:
        return bool(self._tasks)

    def wait_for_tasks(self, timeout_ms: int = 60_000) -> bool:
        """Let every background job finish (for tests and for closing)."""
        from time import monotonic

        deadline = monotonic() + timeout_ms / 1000
        while self._tasks and monotonic() < deadline:
            QApplication.processEvents()
            for task in list(self._tasks.values()):
                task.wait(20)
        QApplication.processEvents()
        return not self._tasks

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        for timer in (self.llm_timer, self.backup_timer):
            timer.stop()
        for task in list(self._tasks.values()):
            task.wait(10_000)
        super().closeEvent(event)
        try:
            self.datastore.dispose()
        except Exception:  # noqa: BLE001 - closing regardless
            pass

    # -- the local LLM, always on -------------------------------------------------------

    def _gate_llm(self) -> None:
        self.pipeline.attach_llm(self.llm if self.llm_enabled and self.llm_online else None)

    def check_llm(self, silent: bool = False) -> None:
        """Ask the Ollama host whether it answers and has the model - off the GUI thread."""
        if "llm" in self._tasks or not hasattr(self, "llm_button"):
            return
        engine = self.llm
        if not silent:
            self.engines_view.set_llm_status("Checking the local LLM host")
            if self.llm_enabled:
                self.llm_button.set_state("checking")

        def job(_task):
            up = engine.available()
            has = up and engine.has_model()
            return up, has, engine.status()

        self._run("llm", "LLM check",
                  job, lambda ok, result: self._llm_checked(engine, silent, ok, result))

    def _llm_checked(self, engine: OllamaEngine, silent: bool, ok: bool, result) -> None:
        if engine is not self.llm:
            return  # the host or model changed while this was asked
        up, has, message = result if ok else (False, False, str(result))
        state = "ready" if has else ("missing" if up else "offline")
        changed = state != self._llm_state
        self._llm_state = state
        if not silent or changed:
            self.on_probed("Ollama", has, message)
        else:
            self.llm_online = has
            self.llm_message = message
        self._gate_llm()
        self.llm_button.set_state(state if self.llm_enabled else "off", message)

    def on_translation_state(self, ready: bool, reason: str) -> None:
        super().on_translation_state(ready, reason)
        self._gate_llm()

    @requires(CONFIGURE)
    def set_llm_enabled(self, enabled: bool) -> None:
        super().set_llm_enabled(enabled)
        prefs.set_value("llm_always_on", bool(enabled))
        self.audit.functionality("LLM analyser switched " + ("on" if enabled else "off"),
                                 model=self.llm.model, host=self.llm.host)
        self._gate_llm()
        self.llm_button.set_state(self._llm_state if enabled else "off", self.llm_message)
        if enabled:
            self.check_llm()

    @requires(CONFIGURE)
    def configure_llm(self, host: str, model: str) -> None:
        super().configure_llm(host, model)
        prefs.set_value("llm_host", self.llm.host)
        prefs.set_value("llm_model", self.llm.model)
        self.llm_button.set_model(self.llm.model)
        self._gate_llm()

    def change_encoder(self, backend: str) -> None:
        super().change_encoder(backend)
        self._gate_llm()

    # -- Asset Safety Memory and Work-Hold Recommendation ---------------------------------

    def _refresh(self, *args, **kwargs):
        # Reports, decisions and actions may have changed: the memory is rebuilt
        # the next time anything reads it.
        self._memory_dirty = True
        return super()._refresh(*args, **kwargs)

    def _decision_by_reference(self) -> Dict[str, str]:
        standing = self.decisions.current()
        found = {}
        for row in self.rows:
            entry = standing.get(row_fingerprint(row))
            if entry is not None:
                found[str(row.get("reference") or "")] = entry.decision
        return found

    def memory(self) -> AssetMemory:
        """Every asset's history, with a recommendation for every report."""
        if self._memory_dirty:
            self._memory_dirty = False
            decisions = self._decision_by_reference()
            actions = getattr(self, "actions", None)
            self.asset_memory = AssetMemory().build(
                self.rows, decisions, actions.actions if actions is not None else ())
            self.recommendations = {}
            for row in self.rows:
                reference = str(row.get("reference") or "")
                if reference:
                    self.recommendations[reference] = recommend(
                        row, self.asset_memory.context(reference), decisions.get(reference, ""))
            self._raise_holds()
        return self.asset_memory

    def recommendation(self, reference: str) -> Optional[Recommendation]:
        self.memory()
        return self.recommendations.get(str(reference))

    def _raise_holds(self) -> None:
        """Write each new work-hold recommendation to the audit log, once."""
        if self._holds_raised is None:
            self._holds_raised = {str((row.get("detail") or {}).get("reference", ""))
                                  for row in self.audit.rows(limit=0)
                                  if row.get("action") == "work-hold recommended"}
        for reference, rec in self.recommendations.items():
            if rec.level == HOLD and not rec.decision and reference not in self._holds_raised:
                self._holds_raised.add(reference)
                self.audit.system("work-hold recommended", reference=reference,
                                  asset=self.asset_memory.context(reference).asset or None,
                                  reason=(rec.reasons[0] if rec.reasons else "")[:200],
                                  score=rec.score, routed_to="HSE review")

    def holds(self) -> List[str]:
        """References with a work-hold recommendation no person has decided yet."""
        self.memory()
        rows = {str(row.get("reference")): row for row in self.rows}
        return sorted((reference for reference, rec in self.recommendations.items()
                       if rec.level == HOLD and not rec.decision),
                      key=lambda reference: (-self.recommendations[reference].score,
                                             -float(rows.get(reference, {}).get("risk_score")
                                                    or 0)))

    def asset_snapshot(self) -> List[Dict[str, object]]:
        memory = self.memory()
        holds = set(self.holds())
        snapshot = []
        for history in memory.assets():
            summary = history.summary()
            summary["signal_list"] = [signal.to_dict() for signal in history.signals]
            summary["equipment"] = list(history.equipment)
            summary["holds"] = sum(1 for record in history.records
                                   if record.reference in holds)
            snapshot.append(summary)
        return snapshot

    def hold_snapshot(self) -> List[Dict[str, object]]:
        memory = self.memory()
        return [{**rec.to_dict(), "reference": reference,
                 "asset": memory.context(reference).asset}
                for reference, rec in self.recommendations.items()]

    def open_asset(self, name: str) -> None:
        if not hasattr(self, "assets_page"):
            return
        self.navigate("assets")
        if name:
            self.assets_page.select(name)

    def _case_rows(self) -> List[Dict[str, object]]:
        cases = super()._case_rows()
        self.memory()
        for case in cases:
            rec = self.recommendations.get(str(case.get("reference")))
            case["recommendation"] = rec.level if rec else ""
            if rec is not None and rec.level == HOLD and "open" in case["_in"]:
                case["_in"] = tuple(case["_in"]) + ("hold",)
                case["trigger"] = f"Work-hold · {case.get('trigger', '')}"
        # Holds first, in the order the queue had them.
        cases.sort(key=lambda case: 0 if "hold" in case["_in"] else 1)
        return cases

    def _refresh_review_page(self) -> None:
        super()._refresh_review_page()
        page = self.review_page
        page.set_counts({key: sum(1 for case in page.rows if key in case.get("_in", ()))
                         for key, _label in page.filters})

    def _show_case(self, reference: str) -> None:
        super()._show_case(reference)
        page = self.review_page
        rec = self.recommendation(reference) if reference else None
        page.recommendation.show_recommendation(reference, rec,
                                                can_act=self.session.can(ANALYSE))
        memory = self.memory()
        context = memory.context(reference) if reference else None
        page.memory.show_context(context, memory.get(context.asset) if context else None)

    def _attention(self, critical, by_ref, now):
        items = super()._attention(critical, by_ref, now)
        holds = self.holds()
        if not holds:
            return items
        memory = self.memory()
        lead = []
        for reference in holds[:4]:
            rec = self.recommendations[reference]
            asset = memory.context(reference).asset
            lead.append(("critical", f"{reference} · Work-Hold Recommended.",
                         (rec.reasons[0][:1].upper() + rec.reasons[0][1:] if rec.reasons
                          else "") + (f" at {asset}" if asset else "") + "."
                         + (" The report says the work was stopped." if rec.work_stopped
                            else ""),
                         "Review case", "review", reference))
        if len(holds) > 4:
            lead.append(("critical", f"{len(holds) - 4} more work holds.",
                         "Each is waiting in HSE Review under the Work-hold filter.",
                         "Open work holds", "review", holds[4]))
        shown = set(holds)
        rest = [item for item in items if not (item[4] == "review" and item[5] in shown)]
        return lead + rest

    def _build_assets_page(self) -> AssetMemoryPage:
        page = AssetMemoryPage()
        page.asset_selected.connect(self._show_asset)
        page.report_requested.connect(self.open_case)
        return page

    def _refresh_assets_page(self) -> None:
        memory = self.memory()
        holds = set(self.holds())
        rows = []
        for history in memory.assets():
            summary = history.summary()
            high = summary["high_signals"]
            rows.append({
                "asset": history.name, "reports": summary["reports"],
                "precursors": summary["precursors"],
                "signal": (f"{high} high · {summary['signals']}", "fail") if high
                else ((f"{summary['signals']} signal(s)", "warn") if summary["signals"]
                      and any(signal.severity != "low" for signal in history.signals)
                      else ("Quiet", "grey")),
                "signals": sum(1 for signal in history.signals if signal.severity != "low"),
                "holds": sum(1 for record in history.records if record.reference in holds),
                "open_actions": summary["open_actions"], "last": summary["last"]})
        page = self.assets_page
        page.set_assets(rows)
        kinds = {"recurring hazard": 0, "repeated control failure": 0,
                 "emerging SIF precursor": 0}
        for history in memory.assets():
            for kind in kinds:
                kinds[kind] += int(any(signal.kind == kind for signal in history.signals))
        page.set_stats((
            (len(rows), f"{len(self.rows)} report(s) placed", False),
            (kinds["recurring hazard"], "assets, last 90 days", False),
            (kinds["repeated control failure"], "assets, last 90 days",
             bool(kinds["repeated control failure"])),
            (kinds["emerging SIF precursor"], "assets", bool(kinds["emerging SIF precursor"])),
            (len(holds), "awaiting an HSE decision", bool(holds))))

    def _show_asset(self, name: str) -> None:
        memory = self.memory()
        history = memory.get(name) if name else None
        timeline = []
        if history is not None:
            for record in reversed(history.records):
                rec = self.recommendations.get(record.reference)
                timeline.append({
                    "when": record.when.strftime("%d %b %y") if record.when else "-",
                    "reference": record.reference,
                    "kind_label": KIND_LABEL.get(record.kind, record.kind),
                    "risk_score": record.risk,
                    "failure": record.failures[0] if record.failures else "-",
                    "recommendation": (rec.label, LEVEL_TONE[rec.level]) if rec else ("", "grey")})
        self.assets_page.show_asset(history, timeline)

    def open_case(self, reference: str = "") -> None:
        """A reference from the memory: its case if it is queued, else its report."""
        queued = {str(row.get("reference")) for row in self._case_rows()} if reference else set()
        if reference and reference not in queued:
            self.open_report(reference)
            return
        super().open_case(reference)

    # -- the SQL database ----------------------------------------------------------------

    def _database_url(self) -> str:
        url = str(prefs.get("database_url", "") or "")
        return join_url(url, self.vault.get(DB_SECRET) or "") if url else default_url()

    def _open_database(self) -> DataStore:
        url = self._database_url()
        try:
            return DataStore(url)
        except Exception as exc:  # noqa: BLE001 - never stop the console over it
            self._db_error = (f"{describe_url(url)} could not be opened "
                              f"({type(exc).__name__}: {exc}); using this workstation's "
                              "SQLite file instead.")
            return DataStore(default_url())

    def _snapshot(self) -> Dict[str, object]:
        """What the console holds, copied on the GUI thread for a job to write."""
        rows = [dict(row) for row in self.rows]
        return {
            "reports": [(row_fingerprint(row), row) for row in rows],
            "decisions": [entry.to_dict() for entry in self.decisions.entries],
            "actions": [action.to_dict() for action in self.actions.actions],
            "audit": self.audit.rows(limit=0),
            "assets": self.asset_snapshot(),
            "holds": self.hold_snapshot(),
        }

    def _known(self) -> Dict[str, set]:
        return {"reports": {row_fingerprint(row) for row in self.rows},
                "decisions": {f"{entry.fingerprint}@{entry.decided_at}"
                              for entry in self.decisions.entries},
                "actions": {action.id for action in self.actions.actions}}

    def _index_job(self, store: VectorStore, rows: List[Dict[str, object]]):
        """Embed the reports the index lacks, with the pipeline's own encoder."""
        encoder = self.pipeline.encoder
        label = encoder.info.label()
        by_fp = {row_fingerprint(row): row for row in rows if row.get("raw_text")}
        missing = store.missing(by_fp, label)
        for start in range(0, len(missing), 64):
            chunk = missing[start:start + 64]
            vectors = encoder.encode([str(by_fp[fp].get("raw_text", "")) for fp in chunk])
            store.upsert([(fp, str(by_fp[fp].get("reference", "")), vectors[i])
                          for i, fp in enumerate(chunk)], label)
        return label, len(missing)

    def sync_now(self, pull_only: bool = False, quiet: bool = False,
                 push_only: bool = False) -> bool:
        """Push what this workstation holds, pull what it does not, top up the index.

        ``pull_only`` is the load at start-up; ``push_only`` is the automatic
        write after an analysis run or a decision (pulling then would bring back
        reports someone just cleared from the session).
        """
        snapshot = {} if pull_only else self._snapshot()
        known = self._known()
        store = self.datastore
        vectors = self.vectors
        rows = [dict(row) for row in self.rows]
        index = self.pipeline._encoder is not None and not pull_only

        def job(_task):
            pushed = store.push(**snapshot) if snapshot else {}
            pulled = {"reports": [], "decisions": [], "actions": []}
            if not push_only:
                pulled = {"reports": store.pull_reports(known["reports"]),
                          "decisions": store.pull_decisions(known["decisions"]),
                          "actions": store.pull_actions(known["actions"])}
            indexed = self._index_job(vectors, rows + [row for _fp, row in pulled["reports"]]) \
                if index else ("", 0)
            return pushed, pulled, indexed

        kind = "load" if pull_only else ("sync" if not push_only else "auto-sync")
        return self._run("sync", "Loading the database" if pull_only else "Syncing", job,
                         lambda ok, result: self._synced(store, kind, quiet, ok, result))

    def _synced(self, store: DataStore, kind: str, quiet: bool, ok: bool, result) -> None:
        if not ok:
            store_note = f"{kind} failed: {result}"
            self._log_data(store, kind, False, str(result))
            self._set_status(store_note)
            if hasattr(self, "data_page"):
                self.data_page.set_database_note(store_note, False)
            return
        pushed, pulled, (encoder, indexed) = result
        added = self._merge_pulled(pulled)
        new = sum(inserted for inserted, _updated in pushed.values())
        changed = sum(updated for _inserted, updated in pushed.values())
        detail = (f"pushed {new} new, {changed} changed · pulled {added['reports']} report(s), "
                  f"{added['decisions']} decision(s), {added['actions']} action item(s)"
                  + (f" · indexed {indexed}" if indexed else ""))
        self._log_data(store, kind, True, detail)
        if not quiet or any(added.values()):
            self.audit.functionality("data synced" if kind != "load" else "data loaded",
                                     database=store.describe(), detail=detail)
        self._set_status(f"Database {kind}: {detail}")
        if hasattr(self, "data_page") and \
                self.pages.currentIndex() == self._page_index.get("data"):
            self._refresh_data_page()

    def _merge_pulled(self, pulled: Dict[str, list]) -> Dict[str, int]:
        added = {"reports": 0, "decisions": 0, "actions": 0}
        index = self._narrative_index()
        for _fp, row in pulled.get("reports", []):
            key = self._narrative_key(row.get("raw_text", ""))
            if key in index:
                continue
            index[key] = len(self.rows)
            self.rows.append(row)
            added["reports"] += 1
        for payload in pulled.get("decisions", []):
            try:
                self.decisions.entries.append(ReviewDecision.from_dict(payload))
                added["decisions"] += 1
            except Exception:  # noqa: BLE001 - a malformed row is skipped
                continue
        if added["decisions"]:
            self.decisions.entries.sort(key=lambda entry: entry.decided_at)
            self.decisions.save()
        for payload in pulled.get("actions", []):
            try:
                self.actions.actions.append(ComplianceAction.from_dict(payload))
                added["actions"] += 1
            except Exception:  # noqa: BLE001
                continue
        if added["actions"]:
            self.actions.save()
        if added["reports"] or added["decisions"]:
            self.report_view.table.set_rows(self.rows)
            self._refresh()
        if added["actions"] and self._shell_ready:
            self._refresh_actions()
        return added

    def _log_data(self, store: DataStore, kind: str, ok: bool, detail: str,
                  target: str = "") -> None:
        try:
            store.log(kind, target or store.describe(), ok, detail)
        except Exception:  # noqa: BLE001 - the log is a convenience, not the record
            pass

    def _auto_sync(self) -> None:
        if bool(prefs.get("auto_sync", True)) and "sync" not in self._tasks:
            self.sync_now(push_only=True, quiet=True)

    def on_analysis_completed(self, *args, **kwargs):
        result = super().on_analysis_completed(*args, **kwargs)
        self._auto_sync()
        return result

    def record_decision(self, *args, **kwargs):
        before = len(self.decisions.entries)
        result = super().record_decision(*args, **kwargs)
        if len(self.decisions.entries) != before:
            self._auto_sync()
        return result

    def undo_decision(self) -> None:
        last = self.decisions.entries[-1] if self.decisions.entries else None
        super().undo_decision()
        if last is not None and last not in self.decisions.entries:
            try:
                self.datastore.remove_decision(last.fingerprint, last.decided_at)
            except Exception:  # noqa: BLE001 - the local undo stands
                pass

    def create_action(self, *args, **kwargs):
        action = super().create_action(*args, **kwargs)
        self._memory_dirty = True
        if action is not None:
            self._auto_sync()
        return action

    def complete_action(self, *args, **kwargs):
        changed = super().complete_action(*args, **kwargs)
        self._memory_dirty = True
        if changed:
            self._auto_sync()
        return changed

    def delete_action(self, action_id: str) -> bool:
        removed = super().delete_action(action_id)
        self._memory_dirty = True
        if removed:
            try:
                self.datastore.remove_action(action_id)
            except Exception:  # noqa: BLE001
                pass
        return removed

    @requires(CONFIGURE)
    def request_sync(self) -> bool:
        """The Sync now button."""
        return self.sync_now()

    @requires(CONFIGURE)
    def set_auto_sync(self, enabled: bool) -> None:
        prefs.set_value("auto_sync", bool(enabled))
        self.audit.functionality("automatic sync " + ("on" if enabled else "off"))

    @requires(CONFIGURE)
    def test_database(self, url: str) -> bool:
        url = url or default_url()

        def job(_task):
            store = DataStore(url)
            try:
                return store.test()
            finally:
                store.dispose()

        def done(ok, result):
            good, message = result if ok else (False, str(result))
            self.data_page.set_database_note(f"{describe_url(url)}: {message}", good)

        return self._run("dbtest", "Testing the database", job, done)

    @requires(CONFIGURE)
    def apply_database(self, url: str) -> bool:
        """Switch to another database, then push this session into it."""
        url = url or default_url()

        def job(_task):
            store = DataStore(url)
            good, message = store.test()
            if not good:
                store.dispose()
                raise RuntimeError(message)
            return store

        def done(ok, result):
            if not ok:
                self.data_page.set_database_note(f"Not switched: {result}", False)
                return
            old = self.datastore
            self.datastore = result
            self.vectors = VectorStore(result)
            plain, password = split_url(url)
            prefs.set_value("database_url", "" if url == default_url() else plain)
            self.vault.put(DB_SECRET, password)
            old.dispose()
            self.audit.functionality("database changed", previous=old.describe(),
                                     database=result.describe())
            self.data_page.db_url.clear()
            self._refresh_data_page()
            self.data_page.set_database_note(f"Now using {result.describe()}.", True)
            self.sync_now()

        return self._run("dbapply", "Switching the database", job, done)

    # -- the vector database -------------------------------------------------------------

    @requires(CONFIGURE)
    def build_index(self) -> bool:
        rows = [dict(row) for row in self.rows]
        store = self.vectors

        def done(ok, result):
            if not ok:
                self.data_page.set_vector_note(f"Indexing failed: {result}")
                return
            encoder, count = result
            self._log_data(self.datastore, "index", True, f"{count} report(s) embedded",
                           target=encoder)
            self.audit.functionality("vector index built", encoder=encoder, added=count)
            self._refresh_data_page()
            self.data_page.set_vector_note(
                f"{count} report(s) added with {encoder}." if count
                else "Every report in this session is already indexed.")

        self.data_page.set_vector_note("Embedding reports - the encoder may take a moment "
                                       "to load the first time.")
        return self._run("index", "Indexing", lambda _task: self._index_job(store, rows), done)

    def find_similar(self, text: str, k: int = 10) -> bool:
        store = self.vectors

        def job(_task):
            encoder = self.pipeline.encoder
            label = encoder.info.label()
            return label, store.search(encoder.encode([text])[0], label, k=k)

        def done(ok, result):
            if not ok:
                self.data_page.set_vector_note(f"Search failed: {result}")
                return
            label, hits = result
            by_fp = {row_fingerprint(row): row for row in self.rows}
            rows = []
            for fp, reference, score in hits:
                row = by_fp.get(fp) or self.datastore.report(fp) or {}
                rows.append({"reference": reference or row.get("reference", ""),
                             "similarity": (f"{score:.2f}", max(0.0, score)),
                             "risk_score": float(row.get("risk_score") or 0.0),
                             "iogp_rule": row.get("iogp_rule") or "-"})
            self.data_page.set_similar(rows)
            self.data_page.set_vector_note(
                f"{len(rows)} closest report(s) by {label}." if rows
                else "The index is empty for this encoder - build it first.")

        return self._run("search", "Searching", job, done)

    # -- backup --------------------------------------------------------------------------

    def _backup_config(self) -> Dict[str, object]:
        config = prefs.get("backup_target", {})
        return dict(config) if isinstance(config, dict) else {}

    def _secrets(self) -> Dict[str, str]:
        return {name: self.vault.get(name) or "" for name in BACKUP_SECRETS}

    def _target(self, config: Optional[Dict[str, object]] = None,
                secrets: Optional[Dict[str, str]] = None) -> backup.Target:
        return backup.make_target(config if config is not None else self._backup_config(),
                                  secrets if secrets is not None else self._secrets())

    def _describe_target(self) -> str:
        config = self._backup_config()
        if not config:
            return ""
        try:
            return self._target(config).describe()
        except backup.BackupError:
            return ""

    @requires(CONFIGURE)
    def save_backup_settings(self, config: Dict[str, object], secrets: Dict[str, str]) -> bool:
        if secrets.get("passphrase") != secrets.get("passphrase_again"):
            self.data_page.set_target_note("The two passphrases differ.", False)
            return False
        if secrets.get("passphrase") and len(secrets["passphrase"]) < 10:
            self.data_page.set_target_note("Use a passphrase of at least 10 characters.", False)
            return False
        if not secrets.get("passphrase") and not self.vault.has("passphrase"):
            self.data_page.set_target_note("Set a passphrase - backups are always "
                                           "encrypted.", False)
            return False
        merged = {name: secrets.get(name) or self.vault.get(name) or ""
                  for name in BACKUP_SECRETS}
        try:
            target = self._target(config, merged)
        except backup.BackupError as exc:
            self.data_page.set_target_note(str(exc), False)
            return False
        for name in BACKUP_SECRETS:
            if secrets.get(name):
                self.vault.put(name, secrets[name])
        prefs.set_value("backup_target", dict(config))
        self.audit.functionality("backup settings changed", target=target.describe(),
                                 schedule=config.get("schedule"), keep=config.get("keep"),
                                 passphrase_changed=bool(secrets.get("passphrase")) or None)
        self._refresh_data_page()
        self.data_page.set_target_note(f"Saved · {target.describe()}", True)
        return True

    @requires(CONFIGURE)
    def test_backup_target(self, config: Dict[str, object], secrets: Dict[str, str]) -> bool:
        merged = {name: secrets.get(name) or self.vault.get(name) or ""
                  for name in BACKUP_SECRETS}
        try:
            target = self._target(config, merged)
        except backup.BackupError as exc:
            self.data_page.set_target_note(str(exc), False)
            return False

        def done(ok, result):
            good, message = result if ok else (False, str(result))
            self._log_data(self.datastore, "test", good, message, target=target.describe())
            self.data_page.set_target_note(f"{target.describe()}: {message}", good)
            self._refresh_data_log()

        self.data_page.set_target_note(f"Testing {target.describe()}…", True)
        return self._run("target", "Testing the target", lambda _task: target.test(), done)

    def _backup_files(self) -> List[Tuple[str, str]]:
        from sif.accounts import accounts_file_path

        return [("users.json", self.accounts.path if self.accounts else accounts_file_path()),
                ("audit.jsonl", self.audit.path),
                ("review_decisions.json", self.decisions.path),
                ("compliance_actions.json", self.actions.path),
                ("settings.json", prefs._path()),
                ("model", self.mlops.model_directory)]

    @requires(CONFIGURE)
    def backup_now(self) -> bool:
        return self._backup(scheduled=False)

    def _backup(self, scheduled: bool) -> bool:
        config = self._backup_config()
        secrets = self._secrets()
        if not secrets.get("passphrase"):
            if hasattr(self, "data_page"):
                self.data_page.set_target_note("Set up the backup and its passphrase first.",
                                               False)
            return False
        try:
            target = self._target(config, secrets)
        except backup.BackupError as exc:
            if hasattr(self, "data_page"):
                self.data_page.set_target_note(str(exc), False)
            return False
        snapshot = self._snapshot()
        store = self.datastore
        files = self._backup_files()
        keep = int(config.get("keep", 14) or 0)

        def job(_task):
            store.push(**snapshot)
            archive, manifest = backup.build_archive(store.export(), files)
            blob = backup.seal(archive, secrets["passphrase"])
            name = backup.archive_name()
            target.upload(name, blob)
            pruned = target.prune(keep)
            return name, len(blob), manifest, pruned

        def done(ok, result):
            if not ok:
                self._log_data(store, "backup", False, str(result), target=target.describe())
                self.audit.system("backup failed", target=target.describe(),
                                  reason=str(result)[:200], scheduled=scheduled or None)
                if hasattr(self, "data_page"):
                    self.data_page.set_target_note(f"Backup failed: {result}", False)
                self._set_status(f"Backup failed: {result}")
                return
            name, size, manifest, pruned = result
            detail = (f"{name} · {size / 1024:.0f} KB · {len(manifest['files'])} file(s)"
                      + (f" · {len(pruned)} old removed" if pruned else ""))
            self._log_data(store, "backup", True, detail, target=target.describe())
            prefs.set_value("last_backup", datetime.now().isoformat(timespec="seconds"))
            (self.audit.system if scheduled else self.audit.functionality)(
                "backup made", archive=name, bytes=size, target=target.describe(),
                reports=manifest["counts"].get("reports"), scheduled=scheduled or None)
            self._set_status(f"Backed up: {detail}")
            if hasattr(self, "data_page"):
                self._refresh_data_page()
                self.data_page.set_target_note(f"Backed up · {detail}", True)
                self.list_backups()

        return self._run("backup", "Backing up", job, done)

    def _scheduled_backup(self) -> None:
        config = self._backup_config()
        schedule = str(config.get("schedule", "off"))
        if schedule == "off" or "backup" in self._tasks or not self.vault.has("passphrase"):
            return
        if backup.due(schedule, str(prefs.get("last_backup", "") or "")):
            self._backup(scheduled=True)

    @requires(CONFIGURE)
    def list_backups(self) -> bool:
        try:
            target = self._target()
        except backup.BackupError as exc:
            self.data_page.set_backups([], str(exc))
            return False

        def done(ok, result):
            if not ok:
                self.data_page.set_backups([], f"Could not list: {result}")
                return
            self.data_page.set_backups([
                {"name": item.name, "size": f"{item.size / 1024:,.0f} KB",
                 "modified": stamp(item.modified) if item.modified[:4].isdigit()
                 else item.modified} for item in result],
                f"{len(result)} backup(s) at {target.describe()}")

        return self._run("list", "Listing backups", lambda _task: target.list(), done)

    def _fetch(self, name: str):
        target = self._target()
        passphrase = self._secrets()["passphrase"]
        return lambda: backup.read_archive(target.download(name), passphrase)

    @requires(CONFIGURE)
    def verify_backup(self, name: str) -> bool:
        try:
            fetch = self._fetch(name)
        except backup.BackupError as exc:
            self.data_page.set_backups(self.data_page.backups.rows, str(exc))
            return False

        def done(ok, result):
            if not ok:
                self._log_data(self.datastore, "verify", False, str(result), target=name)
                self.data_page.set_backups(self.data_page.backups.rows,
                                           f"{name}: {result}")
                return
            manifest, _members = result
            counts = manifest.get("counts", {})
            note = (f"{name}: intact · {len(manifest.get('files', {}))} file(s) match their "
                    f"SHA-256 · {counts.get('reports', 0)} report(s) · made "
                    f"{str(manifest.get('created_at', ''))[:16].replace('T', ' ')} on "
                    f"{manifest.get('host', '?')}")
            self._log_data(self.datastore, "verify", True, note, target=name)
            self.audit.functionality("backup verified", archive=name)
            self.data_page.set_backups(self.data_page.backups.rows, note)
            self._refresh_data_log()

        return self._run("verify", "Verifying", lambda _task: fetch(), done)

    @requires(CONFIGURE)
    def restore_backup(self, name: str) -> bool:
        if not self._confirm(
                f"Restore {name}?\n\nIts reports, decisions, action items and vectors are "
                "merged into the database and this session - nothing here is deleted. Its "
                "files (accounts, audit trail, settings, model) are unpacked into a dated "
                "folder for you to put in place."):
            return False
        try:
            fetch = self._fetch(name)
        except backup.BackupError as exc:
            self.data_page.set_backups(self.data_page.backups.rows, str(exc))
            return False
        store = self.datastore
        folder = os.path.join(prefs.config_directory(), "restored",
                              datetime.now().strftime("%Y%m%d-%H%M%S"))

        def job(_task):
            import json

            manifest, members = fetch()
            counts = store.import_(json.loads(members["database.json"]))
            backup.unpack(members, folder)
            return manifest, counts

        def done(ok, result):
            if not ok:
                self._log_data(store, "restore", False, str(result), target=name)
                self.data_page.set_backups(self.data_page.backups.rows,
                                           f"Restore failed: {result}")
                return
            manifest, counts = result
            added = ", ".join(f"{table} +{inserted}" for table, (inserted, _u) in counts.items())
            self._log_data(store, "restore", True, f"{added} · files in {folder}", target=name)
            self.audit.functionality("backup restored", archive=name,
                                     created=manifest.get("created_at"),
                                     host=manifest.get("host"), merged=added, folder=folder)
            self.data_page.set_backups(self.data_page.backups.rows,
                                       f"Restored {name}: {added}. Files unpacked to {folder}.")
            self.sync_now(pull_only=True)

        return self._run("restore", "Restoring", job, done)

    # -- the page ----------------------------------------------------------------------------

    def _build_data_page(self) -> DataPage:
        page = DataPage()
        page.sync_requested.connect(self.request_sync)
        page.auto_sync_changed.connect(self.set_auto_sync)
        page.test_database.connect(self.test_database)
        page.apply_database.connect(self.apply_database)
        page.index_requested.connect(self.build_index)
        page.search_requested.connect(self.find_similar)
        page.report_requested.connect(self.open_report)
        page.save_target.connect(self.save_backup_settings)
        page.test_target.connect(self.test_backup_target)
        page.backup_requested.connect(self.backup_now)
        page.list_requested.connect(self.list_backups)
        page.verify_requested.connect(self.verify_backup)
        page.restore_requested.connect(self.restore_backup)
        return page

    def open_report(self, reference: str) -> None:
        if self.workspace == "admin":
            # The report view belongs to the HSE workspace; say where it is instead.
            self._set_status(f"{reference} is opened from the HSE workspace.")
            return
        super().open_report(reference)

    def _encoder_label(self) -> str:
        if self.pipeline._encoder is not None:
            return self.pipeline.encoder.info.label()
        labels = [str(row.get("encoder") or "") for row in self.rows if row.get("encoder")]
        return labels[-1] if labels else ""

    def _refresh_data_log(self) -> None:
        try:
            self.data_page.set_log(self.datastore.history(60))
        except Exception:  # noqa: BLE001
            self.data_page.set_log([])

    def _refresh_data_page(self) -> None:
        page = self.data_page
        store = self.datastore
        try:
            counts = store.counts()
            ok, message = True, self._db_error or "Every analysis run and decision is kept here."
        except Exception as exc:  # noqa: BLE001
            counts, ok, message = {}, False, f"{type(exc).__name__}: {exc}"
        page.set_database(store.describe(), split_url(store.url)[0], ok, message, counts,
                          bool(prefs.get("auto_sync", True)))
        label = self._encoder_label()
        fps = [row_fingerprint(row) for row in self.rows]
        try:
            stored = self.vectors.count(label) if label else 0
            missing = len(self.vectors.missing(fps, label)) if label else len(fps)
            others = [name for name in self.vectors.encoders() if name != label]
        except Exception:  # noqa: BLE001
            stored, missing, others = 0, len(fps), []
        page.set_vectors(label, stored, missing, len(fps), others)
        stored_secrets = {name: self.vault.has(name) for name in BACKUP_SECRETS}
        page.set_target(self._backup_config(), stored_secrets, self._describe_target())
        last_sync = store.last("sync") or store.last("auto-sync") or store.last("load")
        last_backup = store.last("backup")
        schedule = dict(backup.SCHEDULES).get(str(self._backup_config().get("schedule", "off")))
        page.set_stats((
            (counts.get("reports", 0), store.describe().split(" · ")[0] + " · reports", not ok),
            (stored, label.split(":")[0] if label else "no encoder loaded yet", False),
            (short_time(last_sync["at"]) if last_sync else "never",
             "automatic after each run" if prefs.get("auto_sync", True) else "manual only",
             False),
            (short_time(last_backup["at"]) if last_backup else "never",
             f"schedule: {(schedule or 'off').lower()}",
             not last_backup and bool(self._backup_config()))))
        self._refresh_data_log()
