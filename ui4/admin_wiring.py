"""The Administration workspace's pages, fed from the console's state.

A mixin for :class:`main4.WorkspaceWindow`, as :mod:`ui4.hse_wiring` is for
the HSE side: Engines, Settings, SysLog, Audit Log and New HSE Login, built
as the design draws them and driven through the controller's own methods, so
every permission check and audit entry is the one the other builds make.
"""

from __future__ import annotations

import os
import socket
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMenu

from main2 import requires
from sif import prefs
from sif.accounts import CONFIGURE, MANAGE_USERS, TRAIN, AuthError
from sif.mlops import MODEL_FILE
from sif.version import __version__

from .accounts import AccountsPage
from .auditlog import AuditPage, describe_entry
from .engines import EnginesPage
from .settings import SettingsPage
from .syslog import SysLogPage, service_of

__all__ = ["AdminPages", "SETTING_DEFAULTS"]

#: Every setting the Settings page holds, with the value it has until changed.
SETTING_DEFAULTS: Dict[str, object] = {
    "project_code": "PS 26165",
    "application_name": "SENTRA",
    "timezone": "Asia/Kolkata (IST, UTC+5:30)",
    "interface_language": "English",
    "date_format": "%d %b %Y",
    "auto_refresh": True,
    "require_overturn_reason": True,
    "allow_uploads": True,
    "translate": True,
    "viewer_scores": False,
    "organisation": "Oil India Limited",
    "place": "Field HQ Duliajan · Assam",
    "sites": ["Duliajan Field HQ", "GGS-5 Duliajan", "OCS-2 Naharkatia", "Rig S-12 Moran",
              "CTF Makum", "Tank farm Duliajan", "Pipeline ROW Jorajan"],
    "departments": ["HSE — Field Operations", "HSE — Drilling", "Production",
                    "Maintenance", "IT — Applications"],
    "notify_critical": True,
    "notify_security": True,
    "notify_overdue": True,
    "check_updates": True,
}


def setting(key: str) -> object:
    """A setting's current value: what was saved, else its default."""
    return prefs.get(key, SETTING_DEFAULTS.get(key))


def _version(package: str) -> str:
    try:
        from importlib.metadata import version

        return version(package)
    except Exception:  # noqa: BLE001 - not installed, or no metadata
        return ""


def _short_time(value: object) -> str:
    """'2026-09-10 15:37:34' -> '10 Sep 15:37'."""
    try:
        return datetime.fromisoformat(str(value)[:19]).strftime("%d %b %H:%M")
    except ValueError:
        return str(value or "")


class AdminPages:
    """Engines, Settings, SysLog, Audit Log, New HSE Login - the design's."""

    # -- Engines --------------------------------------------------------------------------

    def _build_engines(self) -> EnginesPage:
        page = EnginesPage()
        page.check_all_requested.connect(self.check_all_connections)
        page.engine_action.connect(self._engine_action)
        page.train_requested.connect(self.train_model)
        self._evaluation = ""
        return page

    def _last_audit(self, *actions: str) -> Optional[Dict[str, object]]:
        return next((entry for entry in self.audit.rows(limit=400)
                     if entry.get("action") in actions), None)

    def check_all_connections(self) -> None:
        """The local LLM first, then the OCR models - one at a time, as workers run."""
        self._checks_pending = ["ocr"]
        self._engines_checked = datetime.now()
        self.check_llm()
        if self.worker is not None:
            self.worker.finished.connect(self._next_check)
        else:
            self._next_check()

    def _next_check(self) -> None:
        pending = getattr(self, "_checks_pending", [])
        if pending:
            pending.pop(0)
            QTimer.singleShot(0, self.check_ocr)

    def _engine_action(self, key: str) -> None:
        if key == "encoder":
            menu = QMenu(self)
            for backend, label in (("auto", "Auto - transformer, fall back offline"),
                                   ("transformer", "Transformer (all-MiniLM-L6-v2)"),
                                   ("hashing", "Offline - deterministic rules only")):
                menu.addAction(label, lambda b=backend: self._switch_encoder(b))
            button = self.engines_page.cards["encoder"].button
            menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
        elif key == "ocr":
            self.check_ocr()
        elif key == "llm":
            self.check_llm()
        elif key == "risk":
            self.run_evaluation()
        elif key == "model":
            self.toggle_model()
        elif key == "tracking":
            scroll = self.engines_page.scroll
            if scroll is not None:
                scroll.ensureWidgetVisible(self.engines_page.runs)

    def _switch_encoder(self, backend: str) -> None:
        self.change_encoder(backend)
        self._refresh_engines_page()

    @requires(TRAIN)
    def toggle_model(self) -> bool:
        """Detach the learned model from the pipeline, or attach it again."""
        if self.pipeline.has_model:
            self.pipeline.attach_model(None)
            self.audit.functionality("model detached", reason="administrator")
        elif self.mlops.model.is_trained:
            self.pipeline.attach_model(self.mlops)
            self.audit.functionality("model attached", reason="administrator")
        else:
            self._set_status("There is no trained model to attach.")
            return False
        self._refresh_engines_page()
        return True

    def run_evaluation(self) -> str:
        """How the engine's calls compare with what reviewers decided."""
        results = self._as_results()
        reviewed, labels = self.decisions.labels_for(results)
        if not labels:
            self._evaluation = "No reviewed decisions yet - nothing to evaluate against."
        else:
            predicted = [int(result.sif_potential) for result in reviewed]
            tp = sum(1 for p, y in zip(predicted, labels) if p and y)
            fp = sum(1 for p, y in zip(predicted, labels) if p and not y)
            fn = sum(1 for p, y in zip(predicted, labels) if not p and y)
            recall = tp / (tp + fn) if tp + fn else 0.0
            precision = tp / (tp + fp) if tp + fp else 0.0
            self._evaluation = (f"Reviewed set: recall {recall:.2f} · precision "
                                f"{precision:.2f} ({len(labels)})")
        self.audit.functionality("engine evaluated", outcome=self._evaluation)
        self._refresh_engines_page()
        return self._evaluation

    def _refresh_engines_page(self) -> None:
        if not hasattr(self, "engines_page"):
            return
        page = self.engines_page
        checked = getattr(self, "_engines_checked", None)
        page.head.caption.setText(f"host {socket.gethostname()}" + (
            f" · checked {checked.strftime('%H:%M')}" if checked else ""))
        analysed = self._last_audit("reports analysed")
        last_run = "-"
        if analysed is not None:
            detail = analysed.get("detail") or {}
            last_run = (f"{str(analysed.get('at'))[11:16]} · {detail.get('count', 0)} reports")
        kpis = self._intelligence.kpis if self._intelligence is not None else {}
        encoder = str(kpis.get("encoder") or "")

        # Semantic encoder
        offline = encoder.startswith("hashing") or os.environ.get("SIF_ENCODER") == "hashing"
        page.cards["encoder"].show_state(
            ("✓ Ready", "ok") if encoder else ("Loads on first run", "grey"),
            (("Model", "Hashing encoder (lexical only)" if offline
              else "all-MiniLM-L6-v2 (sentence-transformers)"),
             ("Version", (encoder.split(":", 1)[-1].strip() if encoder else "")
              or ("-" if offline else _version("sentence-transformers") or "-")),
             ("Host", "In-process · CPU"),
             ("Connection", "Loaded" if encoder else "Not loaded yet"),
             ("Last run", last_run)),
            "Offline fallback: hashing encoder (lexical only)")

        # OCR
        status = self.extractor.status()
        if "disabled" in status:
            ocr_pill, connection = ("Off", "grey"), "Text layer only"
        elif "unavailable" in status or "not usable" in status:
            ocr_pill, connection = ("✕ Unavailable", "fail"), "Not usable - see Verify"
        elif "download" in status:
            ocr_pill, connection = ("◆ Models not fetched", "warn"), "Models download on first use"
        else:
            ocr_pill, connection = ("✓ Ready", "ok"), "Models cached on this machine"
        read = self._last_audit("document read")
        failures = sum(1 for item in getattr(self, "ingest_items", [])
                       if item.get("state") == "failed")
        page.cards["ocr"].show_state(
            ocr_pill,
            (("Model", "PaddleOCR" + (f" · {self.language.split(' /')[0]}"
                                      if self.language else "")),
             ("Version", _version("paddleocr") or "not installed"),
             ("Host", "In-process · CPU"),
             ("Connection", connection),
             ("Last run", f"{str(read.get('at'))[11:16]} · "
                          f"{(read.get('detail') or {}).get('name', '')}" if read else "-")),
            f"Confidence floor 0.70 · {failures} failure(s) this session")

        # Local LLM
        if self.llm_online:
            llm_pill = ("✓ Running", "ok")
        elif self.llm_enabled or self.translate_enabled:
            llm_pill = ("◆ Not reached", "warn")
        else:
            llm_pill = ("Off", "grey")
        probe = self._last_audit("Ollama check", "translation readiness")
        page.cards["llm"].show_state(
            llm_pill,
            (("Model", f"{self.llm.model} via Ollama"),
             ("Version", "Ollama"),
             ("Host", self.llm.host),
             ("Connection", str(self.llm_message)[:60]),
             ("Last run", str(probe.get("at"))[11:16] if probe else "-")),
            ("Used to translate non-English reports for reading"
             + (" and as a fourth opinion" if self.llm_enabled else "")))

        # Risk / SIF pipeline
        queued = self.outstanding_reviews
        page.cards["risk"].show_state(
            ("✓ Ready", "ok"),
            (("Model", "SENTRA pipeline · lexical KB"),
             ("Version", __version__),
             ("Host", "In-process"),
             ("Connection", "—"),
             ("Last run", f"{last_run} · {queued} queued" if analysed else "-")),
            self._evaluation or "Compare the engine with reviewers' decisions.")

        # Learned model
        model = self.mlops.model
        metadata = getattr(model, "metadata", {}) or {}
        attached = self.pipeline.has_model
        disagreements = sum(1 for item in self.queue_rows
                            if "disagree" in str(item.get("trigger", "")).lower()
                            and not item.get("decided"))
        page.cards["model"].show_state(
            ("✓ Attached · third opinion", "ok") if attached else
            (("Trained · detached", "warn") if model.is_trained else ("Not trained", "grey")),
            (("Model", "XGBoost classifier" + (f" · run {self.mlops.last_report.run_id[:6]}"
                                               if self.mlops.last_report and
                                               self.mlops.last_report.run_id else "")),
             ("Version", f"xgboost {_version('xgboost') or '-'} · "
                         f"{len(metadata.get('features') or []) or 46} features"),
             ("Host", os.path.relpath(os.path.join(self.mlops.model_directory, MODEL_FILE))
              if model.is_trained else "-"),
             ("Connection", "—"),
             ("Last run", f"Trained {str(metadata.get('trained_at', ''))[:16].replace('T', ' ')} "
                          f"· {metadata.get('samples', '?')} "
                          f"{'reviewed labels' if 'review' in str(metadata.get('label_source')) else 'pipeline labels'}"
              if model.is_trained else "-")),
            f"Disagreements queued now: {disagreements}",
            "Detach model" if attached else "Attach model")
        page.cards["model"].button.setEnabled(model.is_trained and self.session.can(TRAIN))

        # Experiment tracking
        tracker = self.mlops.tracker
        runs = []
        try:
            runs = tracker.recent_runs(10)
        except Exception:  # noqa: BLE001 - a broken store must not stop the page
            runs = []
        installed = tracker.installed()
        page.cards["tracking"].show_state(
            ("✓ Connected", "ok") if installed else ("Not installed", "grey"),
            (("Model", f"MLflow · experiment {tracker.experiment}"),
             ("Version", f"mlflow {_version('mlflow')}" if installed else "-"),
             ("Host", str(tracker.tracking_uri)[:48]),
             ("Connection", f"{len(runs)} run(s)" if installed else "-"),
             ("Last run", f"{_short_time(runs[0]['started'])} · run {runs[0]['run_id'][:6]}"
              if runs else "-")),
            f"Model files: {os.path.relpath(self.mlops.model_directory)}")

        # Training panel, runs, importance
        results = self._as_results()
        _reviewed, labels = self.decisions.labels_for(results)
        page.reviewed_count.setText(f"{len(labels)} available")
        page.train_button.setEnabled(self.session.can(TRAIN) and self.worker is None)
        latest = runs[0]["run_id"] if runs else ""
        page.show_runs([{**run, "labels": str(run.get("labels", "")).split(" (")[0],
                         "run_id": str(run.get("run_id", ""))[:6],
                         "started": _short_time(run.get("started")),
                         "state": ("✓ Finished · attached", "ok")
                         if run["run_id"] == latest and attached else
                         ("Finished", "grey") if run.get("status") == "FINISHED" else
                         (str(run.get("status", "")).title(), "fail")} for run in runs],
                       f"MLflow · {tracker.experiment}" if installed else "MLflow not installed")
        importances = list(self.mlops.last_report.importances) if self.mlops.last_report else []
        if not importances and model.is_trained:
            try:
                from sif.mlops import FEATURE_NAMES

                values = model._booster.feature_importances_
                importances = sorted(((name, float(value)) for name, value
                                      in zip(FEATURE_NAMES, values) if value > 0),
                                     key=lambda item: item[1], reverse=True)
            except Exception:  # noqa: BLE001
                importances = []
        page.show_importance([(name, round(value, 2)) for name, value in importances[:8]],
                             f"run {latest[:6]}" if latest else "")

    # -- Settings ------------------------------------------------------------------------

    def _build_settings(self) -> SettingsPage:
        page = SettingsPage()
        page.setting_changed.connect(self.change_setting)
        page.encoder_changed.connect(self._switch_encoder)
        page.llm_toggled.connect(self.set_llm_enabled)
        page.llm_configured.connect(self.configure_llm)
        page.tracking_changed.connect(self.change_tracking)
        page.log_level_changed.connect(self.change_log_level)
        page.accounts_requested.connect(lambda: self.navigate("accounts"))
        page.verify_requested.connect(self.verify_audit_trail)
        return page

    def _refresh_settings_page(self) -> None:
        from sif.logging_setup import active_log_file, log_file_path
        from sif.review import DECISION_FILE

        from sif import audit as audit_module

        values = {key: setting(key) for key in SETTING_DEFAULTS}
        values.update(encoder=os.environ.get("SIF_ENCODER") or prefs.get("encoder", "auto"),
                      llm_enabled=self.llm_enabled, llm_host=self.llm.host,
                      llm_model=self.llm.model, tracking_uri=self.mlops.tracker.tracking_uri,
                      experiment=self.mlops.tracker.experiment,
                      log_level=prefs.get("log_level", "INFO"),
                      translate=self.translate_enabled)
        paths = (("Audit trail", audit_module.audit_file_path()),
                 ("Review decisions", getattr(self.decisions, "path", DECISION_FILE)),
                 ("Action items", self.actions.path if hasattr(self, "actions") else "-"),
                 ("Accounts", self.accounts.path if self.accounts else "-"),
                 ("Learned model", os.path.abspath(self.mlops.model_directory)),
                 ("Service log", active_log_file() or log_file_path()),
                 ("Preferences", prefs._path()))
        self.settings_page.load(values, paths)

    @requires(CONFIGURE)
    def change_setting(self, key: str, value: object) -> bool:
        """Save one setting, apply it, and write old and new to the audit log."""
        if key not in SETTING_DEFAULTS:
            return False
        previous = setting(key)
        if previous == value:
            return False
        prefs.set_value(key, value)
        self.audit.functionality("setting changed", setting=key,
                                 previous=str(previous)[:120], new=str(value)[:120])
        if key == "translate":
            self.set_translation(bool(value))
        elif key in ("organisation", "place", "project_code"):
            self._apply_identity()
        self._set_status(f"Setting changed: {key}")
        return True

    def _apply_identity(self) -> None:
        if hasattr(self, "shell_header"):
            self.shell_header.set_identity(str(setting("organisation")), str(setting("place")),
                                           str(setting("project_code")))

    # -- New HSE Login -------------------------------------------------------------------

    def _build_accounts(self) -> AccountsPage:
        page = AccountsPage()
        page.create_requested.connect(self.create_hse_account)
        page.role_requested.connect(self.change_account_role)
        page.reset_requested.connect(self.reset_account_password)
        page.toggle_requested.connect(self.toggle_account)
        return page

    def _refresh_accounts_page(self) -> None:
        if not hasattr(self, "accounts_page"):
            return
        from main4 import ROLE_NAMES

        page = self.accounts_page
        page.set_choices([str(site) for site in setting("sites") or []],
                         [str(dept) for dept in setting("departments") or []])
        rows = []
        for account in (self.accounts.accounts() if self.accounts else []):
            last = "now" if account.username == self.session.username else (
                _short_time(account.last_login).replace(" ", "\n", 1).replace(" ", "\n")
                if account.last_login else "never")
            rows.append({"username": account.username, "full_name": account.full_name,
                         "email": account.email or account.username,
                         "role": account.role,
                         "role_label": ROLE_NAMES.get(account.role, account.role),
                         "site": account.site or "\u2014",
                         "status": ("\u2713 Active", "ok") if account.active
                         else ("\u25a0 Disabled", "grey"),
                         "active": account.active, "last": last})
        page.set_accounts(rows, self.session.username)

    @requires(MANAGE_USERS)
    def create_hse_account(self, values: Dict[str, object]) -> str:
        """Create an account from the form; returns the one-time password, or ''."""
        page = getattr(self, "accounts_page", None)
        role = str(values.get("role"))
        name = str(values.get("full_name", "")).strip()
        if role == "admin" and not self._confirm(
                f"Make {name} an Administrator?\n\nAn administrator manages accounts and "
                "engines, and cannot decide review cases."):
            return ""
        username = str(values.get("username", ""))
        store = self.accounts
        if store is not None and values.get("email") and store.resolve(
                str(values["email"])) != str(values["email"]).strip().lower():
            if page is not None:
                page.set_error("Another account already uses that email.")
            return ""
        password = self.create_account(username, name, role)
        if not password:
            if page is not None:
                page.set_error("The account could not be created - see the message shown.")
            return ""
        try:
            store.set_profile(username, email=str(values.get("email") or ""),
                              site=str(values.get("site") or ""),
                              department=str(values.get("department") or ""))
        except AuthError as exc:
            if page is not None:
                page.set_error(str(exc))
        if not values.get("active", True):
            from main2 import MainWindow

            MainWindow.toggle_account.__wrapped__(self, username)
        if page is not None:
            page.clear_form()
        self._refresh_accounts_page()
        if self.isVisible():
            self._show_one_time_password(username, password)
        return password

    # -- Audit Log ------------------------------------------------------------------------

    def _build_audit(self) -> AuditPage:
        page = AuditPage()
        page.verify_requested.connect(self.verify_audit_trail)
        page.export_requested.connect(self.export_audit)
        page.filters_changed.connect(self._refresh_audit_page)
        self._chain_report = None
        self._chain_checked = None
        return page

    def verify_audit_trail(self) -> None:
        super().verify_audit_trail()
        self._chain_report = self.audit.verify()
        self._chain_checked = datetime.now()
        if hasattr(self, "audit_page"):
            self._refresh_audit_page()

    def _refresh_audit_page(self) -> None:
        from datetime import timedelta

        from sif import audit as audit_module

        page = self.audit_page
        report = self._chain_report or self.audit.verify()
        self._chain_report = report
        everything = self.audit.rows(limit=100000)
        total = len(everything)
        first = everything[-1].get("at", "") if everything else ""
        checked = self._chain_checked
        if report.intact:
            page.set_banner(
                f"\u2713  <b>Chain intact.</b> {report.entries:,} entries"
                + (f" since {_short_time(first)[:6]}" if first else "")
                + (f" \u00b7 last verified today {checked.strftime('%H:%M')}" if checked else
                   " \u00b7 checked when this page opened")
                + f" \u00b7 stored at {audit_module.audit_file_path()}", True)
        else:
            page.set_banner(f"\u2715  <b>Chain broken</b> at entry {report.broken_at}: "
                            f"{report.reason}. The record from that entry on cannot be relied on.",
                            False)
        machine = socket.gethostname()
        human = []
        for position, entry in enumerate(everything):
            if entry.get("category") != "functionality":
                continue
            row = describe_entry(entry, machine)
            row["_number"] = total - position
            row["_workstation"] = machine
            human.append(row)
        users = sorted({str(row["user"]) for row in human} - {"\u2014"})
        roles = sorted({str(row["role_label"]) for row in human} - {"\u2014"})
        actions = sorted({str(row["title"]) for row in human})
        page.set_choices(users, roles, actions)
        user, role, action, days = page.filters
        now = datetime.now()
        shown = []
        for row in human:
            if user and row["user"] != user:
                continue
            if role and row["role_label"] != role:
                continue
            if action and row["title"] != action:
                continue
            if days:
                try:
                    when = datetime.fromisoformat(str(row.get("at"))[:19])
                    if now - when > timedelta(days=days):
                        continue
                except ValueError:
                    pass
            shown.append(row)
        page.set_rows(shown[:1000], len(human))

    # -- SysLog ---------------------------------------------------------------------------

    def _build_syslog(self) -> SysLogPage:
        page = SysLogPage()
        page.filters_changed.connect(self._refresh_syslog)
        page.export_requested.connect(self.export_syslog)
        return page

    def _syslog_rows(self) -> Tuple[List[Dict[str, object]], int]:
        from datetime import timedelta

        page = self.syslog_page
        wanted = page.filters
        entries = self.ring.entries("DEBUG")
        machine = socket.gethostname()
        now = datetime.now()
        rows = []
        for entry in reversed(entries):
            if wanted["level"] and entry.level != wanted["level"] and not (
                    wanted["level"] == "ERROR" and entry.level == "CRITICAL"):
                continue
            service = service_of(entry.logger)
            if wanted["service"] and service != wanted["service"]:
                continue
            if wanted["hours"]:
                try:
                    when = datetime.strptime(entry.timestamp, "%Y-%m-%d %H:%M:%S")
                    if now - when > timedelta(hours=int(wanted["hours"])):
                        continue
                except ValueError:
                    pass
            if wanted["needle"] and wanted["needle"] not in (
                    f"{entry.message} {entry.logger} {service}".lower()):
                continue
            rows.append({"timestamp": entry.timestamp, "service": service, "level": entry.level,
                         "message": entry.message, "machine": machine, "logger": entry.logger})
        return rows[:500], len(entries)

    def _refresh_syslog(self) -> None:
        from sif.logging_setup import active_log_file, log_file_path

        page = self.syslog_page
        page.log_file = active_log_file() or log_file_path()
        rows, total = self._syslog_rows()
        page.set_rows(rows, total)

    @requires(CONFIGURE)
    def export_syslog(self) -> str:
        """Write the events the filters show to a .log file."""
        from PyQt6.QtWidgets import QFileDialog

        rows, _total = self._syslog_rows()
        path, _ = QFileDialog.getSaveFileName(self, "Export the system log", "sentra_syslog.log",
                                              "Log files (*.log);;All files (*)")
        if not path:
            return ""
        with open(path, "w", encoding="utf-8") as handle:
            for row in reversed(rows):
                handle.write(f"{row['timestamp']} | {row['level']:<8} | {row['service']:<8} | "
                             f"{row['machine']} | {row['message']}\n")
        self.audit.functionality("system log exported", events=len(rows), path=path)
        return path

    @requires(TRAIN)
    def train_model(self) -> None:
        """Train as the panel says: its label source, trees and depth."""
        from main2 import MainWindow, TrainingWorker

        page = getattr(self, "engines_page", None)
        if page is not None:
            self.mlops.model.params.update(n_estimators=page.trees.value(),
                                           max_depth=page.depth.value())
            if page.label_choice == "pipeline":
                results = self._as_results()
                if len(results) < 4:
                    MainWindow.train_model.__wrapped__(self)   # says why it cannot
                    return
                worker = TrainingWorker(self.mlops, results,
                                        label_source="pipeline verdicts (distillation)",
                                        parent=self)
                worker.trained.connect(self.on_trained)
                worker.failed.connect(self.on_failed)
                self._start(worker, f"Training on {len(results)} pipeline verdict(s)")
                return
        MainWindow.train_model.__wrapped__(self)
