"""Build 4: two workspaces behind one sign-in.

The controller is build 2's - :class:`main2.MainWindow` - so every capability,
worker, audit entry and permission check is the same code as ``app.py`` runs.
What this module changes is who sees what, and the chrome around it:

* **Two workspaces, one sign-in.** The account decides which one opens;
  nothing on screen lets a person choose. An administrator lands on Engines,
  everyone else on Home.
* **Two roles, as the Stage 1 sheet draws them.** An HSE Analyst ingests,
  analyses, decides review cases and investigates hotspots. An Administrator
  configures and trains the engines, changes settings, reads the SysLog and the
  Audit Log, and manages accounts - and does *not* record review decisions, so
  platform control and safety judgement stay in separate accounts. This
  applies in build 4 only; the other builds keep their four roles.
* **A title row and a tab row** in place of the sidebar, per the Stage 2 sheet.

The account store's four roles map onto the two: ``admin`` is an
Administrator; ``analyst`` and ``reviewer`` are HSE Analysts; ``viewer`` opens
the HSE workspace read-only.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, fields
from datetime import date
from typing import Dict, List, Optional, Tuple

from PyQt6.QtWidgets import QMessageBox, QVBoxLayout, QWidget

from main2 import APP_NAME, MainWindow, requires
from sif import prefs
from sif.actions import ActionStore
from sif.accounts import (ANALYSE, CLEAR, CONFIGURE, DECIDE, MANAGE_USERS, TRAIN, VIEW,
                          AccountStore, AuthError, Session)
from sif.version import __version__
from ui2.activity import AccountDialog, ActivityView
from ui2.components import titled
from ui4.calendar import ActionDetailDialog, ActionDialog, ActionsView
from ui4.hse_wiring import HSEPages, IngestFlow
from ui4.present import initials, stamp
from ui4.kit import Page
from ui4.profile import ProfilePage
from ui4.shell import TabRow, WorkspaceHeader

__all__ = ["WorkspaceSession", "WorkspaceWindow", "HSE_TABS", "ADMIN_TABS",
           "workspace_session"]

HSE_TABS: Tuple[Tuple[str, str], ...] = (
    ("home", "Home"), ("ingest", "Ingest"), ("dashboard", "Dashboard"),
    ("review", "HSE Review"), ("actions", "Action Items"), ("hotspots", "Risk Hotspots"),
    ("profile", "Profile"))
ADMIN_TABS: Tuple[Tuple[str, str], ...] = (
    ("engines", "Engines"), ("settings", "Settings"), ("syslog", "SysLog"),
    ("audit", "Audit Log"), ("accounts", "New HSE Login"), ("profile", "Profile"))

#: What each workspace may do - the Stage 1 permission table.
HSE_ANALYST = frozenset({VIEW, ANALYSE, DECIDE})
READ_ONLY = frozenset({VIEW})
ADMINISTRATOR = frozenset({VIEW, TRAIN, CLEAR, CONFIGURE, MANAGE_USERS})

#: How build 4 names the account store's roles.
ROLE_NAMES = {"admin": "Administrator", "reviewer": "HSE Analyst",
              "analyst": "HSE Analyst", "viewer": "Viewer"}
#: What an administrator can create here: the two roles the sheets draw. An HSE
#: Analyst is stored as ``reviewer`` so the same account can decide cases in the
#: other builds too.
CREATABLE = ("reviewer", "admin")


@dataclass(frozen=True)
class WorkspaceSession(Session):
    """A session judged by build 4's two-role table instead of the store's four."""

    @property
    def workspace(self) -> str:
        return "admin" if self.role == "admin" else "hse"

    @property
    def role_label(self) -> str:
        return ROLE_NAMES.get(self.role, self.role)

    def can(self, permission: str) -> bool:
        if self.role == "admin":
            return permission in ADMINISTRATOR
        if self.role == "viewer":
            return permission in READ_ONLY
        return permission in HSE_ANALYST


def workspace_session(session: Optional[Session]) -> WorkspaceSession:
    """Re-read any session under build 4's rules; an absent one runs unattended."""
    session = session or Session.unattended()
    return WorkspaceSession(**{item.name: getattr(session, item.name)
                               for item in fields(Session)})


class WorkspaceWindow(IngestFlow, HSEPages, MainWindow):
    """Build 2's console behind build 4's two workspaces."""

    MIN_WIDTH, MIN_HEIGHT = 1366, 768

    def __init__(self, session: Optional[Session] = None,
                 accounts: Optional[AccountStore] = None) -> None:
        self._shell_ready = False
        super().__init__(workspace_session(session), accounts)
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self._build_shell()
        self._shell_ready = True
        self.navigate(self.landing)
        self._set_status(f"Signed in as {self.session.full_name} - "
                         + ("Administration" if self.workspace == "admin" else "HSE workspace")
                         if self.session.authenticated else "Ready.")

    # -- construction ------------------------------------------------------

    @property
    def workspace(self) -> str:
        return self.session.workspace

    @property
    def landing(self) -> str:
        return "engines" if self.workspace == "admin" else "home"

    @property
    def tabs(self) -> Tuple[Tuple[str, str], ...]:
        return ADMIN_TABS if self.workspace == "admin" else HSE_TABS

    def _build_shell(self) -> None:
        """Swap the sidebar and header for the title row and the tab row."""
        self.header.hide()
        self.sidebar.hide()
        self.shell_header = WorkspaceHeader(self.workspace, self.session.full_name,
                                            self.session.role_label, self.session.username)
        self.tab_row = TabRow(self.workspace, self.tabs,
                              badge_key="review" if self.workspace == "hse" else "")
        layout = self.centralWidget().layout()
        layout.insertWidget(0, self.shell_header)
        layout.insertWidget(1, self.tab_row)

        # The design has neither a menu bar nor a status footer; the menu's
        # shortcuts stay on the window so Ctrl+O and the rest still work.
        for menu_action in self.menuBar().actions():
            menu = menu_action.menu()
            for action in (menu.actions() if menu is not None else ()):
                if not action.isSeparator():
                    self.addAction(action)
        self.menuBar().hide()
        self.status_label.parentWidget().hide()

        self.home_page = self._build_home()
        self._page_index["home"] = self.pages.addWidget(self.home_page)
        self.ingest_page = self._build_ingest()
        self._page_index["ingest"] = self.pages.addWidget(self.ingest_page)
        self.dashboard_page = self._build_dashboard()
        self._page_index["dashboard"] = self.pages.addWidget(self.dashboard_page)
        self.review_page = self._build_review()
        self._page_index["review"] = self.pages.addWidget(self.review_page)
        self.hotspots_page = self._build_hotspots()
        self._page_index["hotspots"] = self.pages.addWidget(self.hotspots_page)
        self.profile_view = ProfilePage(self.workspace)
        self._page_index["profile"] = self.pages.addWidget(self.profile_view)

        # Compliance Action Items: the HSE calendar of recurring and corrective work.
        self.actions = ActionStore()
        self.actions_view = ActionsView()
        self.actions_view.set_user(self.session.username)
        self.actions_view.set_editable(self.session.can(ANALYSE))
        self.actions_view.period_changed.connect(self._refresh_actions)
        self.actions_view.add_requested.connect(self.add_action)
        self.actions_view.action_requested.connect(self.open_action)
        self.actions_view.samples_requested.connect(self.load_sample_actions)
        actions_page = Page("Compliance Action Items",
                            "Recurring and corrective HSE work \u00b7 a person marks each "
                            "date done")
        actions_page.body.addWidget(self.actions_view, 1)
        self._page_index["actions"] = self.pages.addWidget(actions_page)
        self.reports_page = self._build_reports()
        self._page_index["reports"] = self.pages.addWidget(self.reports_page)

        # SysLog: what the software did - the log panel from Settings.
        syslog = QWidget()
        syslog_layout = QVBoxLayout(syslog)
        syslog_layout.setContentsMargins(18, 16, 18, 16)
        syslog_layout.addWidget(self.settings_view.logging_panel)
        self._add_page("syslog", syslog, "SysLog",
                       "What the software did: service events and their levels. No human "
                       "actions - those are in the Audit Log.")
        # Settings keeps its tracking panel; the audit panel's work is the
        # Audit Log's here, with the chain and a filter by person.
        self.settings_view.audit_panel.hide()

        # Audit Log: what people did, hash-chained - a second reading of the trail.
        self.audit_view = ActivityView()
        self.audit_view.people_panel.hide()
        self.audit_view.set_admin(False)
        self.audit_view.filter_changed.connect(lambda _: self._refresh_activity())
        self.audit_view.verify_requested.connect(self.verify_audit_trail)
        self._add_page("audit", self.audit_view, "Audit Log",
                       "What people did: user, role, action and result, hash-chained so an "
                       "altered record shows where it was altered.")
        # New HSE Login: the account half of the Activity page.
        self.activity_view.activity_panel.hide()
        self.activity_view.integrity_panel.hide()
        self._page_index["accounts"] = self._page_index["activity"]
        self._retitle("activity", "New HSE Login",
                      "Create, disable, reset and re-role accounts. Privileged changes "
                      "ask for confirmation.")

        self.tab_row.navigated.connect(self.navigate)
        self.shell_header.bell_clicked.connect(
            lambda: self.navigate("audit" if self.workspace == "admin" else "review"))
        self.shell_header.gear_clicked.connect(self._open_preferences)
        self.shell_header.preferences_requested.connect(self._open_preferences)
        self.shell_header.profile_requested.connect(lambda: self.navigate("profile"))
        self.shell_header.sign_out_requested.connect(self.sign_out)
        self.profile_view.password_change_requested.connect(self.change_own_password)
        self.profile_view.preference_changed.connect(prefs.set_value)
        if self.workspace == "admin":
            self.tab_row.set_note(f"{socket.gethostname()}  ·  v{__version__}")
        self._refresh_shell()

    def _add_page(self, key: str, widget: QWidget, title: str, caption: str) -> None:
        self._page_index[key] = self.pages.addWidget(titled(widget, title, caption))

    def _retitle(self, key: str, title: str, caption: str) -> None:
        from PyQt6.QtWidgets import QLabel

        page = self.pages.widget(self._page_index[key])
        for label in page.findChildren(QLabel):
            if label.objectName() == "PageTitle":
                label.setText(title)
            elif label.objectName() == "Muted" and label.parent() is not None \
                    and label.parent().objectName() == "PageHead":
                label.setText(caption)

    def _open_preferences(self) -> None:
        self.navigate("settings" if self.workspace == "admin" else "profile")

    # -- navigation --------------------------------------------------------

    def navigate(self, key: str) -> None:
        """Go to a page of this workspace; a page of the other one stays shut."""
        allowed = {name for name, _ in self.tabs} | {"reports"}
        if self._shell_ready and key not in allowed:
            self._set_status("That page belongs to the other workspace.")
            return
        super().navigate(key)
        if not self._shell_ready:
            return
        if key == "home":
            self._refresh_home()
        elif key == "ingest":
            self._refresh_ingest()
        elif key == "dashboard":
            self._refresh_dashboard()
        elif key == "review":
            self._refresh_review_page()
        elif key == "hotspots":
            self._refresh_hotspots()
        elif key == "reports":
            self._refresh_reports()
        elif key == "profile":
            self._refresh_profile()
        elif key == "syslog":
            self._refresh_logs()
        elif key in ("audit", "accounts"):
            self._refresh_activity()
        elif key == "actions":
            self._refresh_actions()
        # A report opened from Home is part of the corpus view.
        self.tab_row.select("dashboard" if key == "reports" else key)

    def open_report(self, reference: str) -> None:
        """Open one report with its evidence - the drill-down from anywhere."""
        self.navigate("reports")
        if reference:
            self.reports_page.select(reference)

    # -- refreshing ----------------------------------------------------------

    def _refresh(self, *args, **kwargs):
        result = super()._refresh(*args, **kwargs)
        self._intelligence = result
        if getattr(self, "_shell_ready", False):
            self._refresh_shell()
            current = self.pages.currentIndex()
            if current == self._page_index.get("home"):
                self._refresh_home()
            elif current == self._page_index.get("dashboard"):
                self._refresh_dashboard()
            elif current == self._page_index.get("review"):
                self._refresh_review_page()
            elif current == self._page_index.get("hotspots"):
                self._refresh_hotspots()
            elif current == self._page_index.get("reports"):
                self._refresh_reports()
            self._refresh_ingest()
        return result

    def _refresh_shell(self) -> None:
        if self.workspace == "hse":
            self.tab_row.set_badge(self.outstanding_reviews)
            self.shell_header.set_bell(self.outstanding_reviews)
            runs = [row for row in self.audit.rows(limit=200)
                    if row.get("action") == "reports analysed"]
            self.tab_row.set_note(
                f"Last analysis run {runs[0]['at'][11:16]}" if runs else "No analysis run yet")
        else:
            today = self._today()
            alarms = [row for row in self.audit.rows(limit=500)
                      if str(row.get("at", "")).startswith(today)
                      and row.get("action") in ("sign-in refused", "account locked",
                                                "permission refused")]
            self.shell_header.set_bell(len(alarms))

    @staticmethod
    def _today() -> str:
        from datetime import date

        return date.today().isoformat()

    def _own_activity(self) -> List[Dict[str, object]]:
        return [row for row in self.audit.rows(limit=500)
                if row.get("user") == self.session.username]

    @staticmethod
    def _long_date(value: str) -> str:
        from datetime import datetime

        try:
            return datetime.fromisoformat(str(value)[:19]).strftime("%d %b %Y %H:%M")
        except ValueError:
            return str(value or "-")

    def _refresh_profile(self) -> None:
        account = self.accounts.get(self.session.username) if self.accounts else None
        key = "admin" if self.workspace == "admin" else (
            "viewer" if self.session.role == "viewer" else "hse")
        created = "-"
        if account is not None and account.created_at:
            creator = self.accounts.get(account.created_by) if account.created_by else None
            created = self._long_date(account.created_at)[:11] + (
                f" by {creator.full_name}" if creator is not None
                else " \u00b7 first administrator on this machine" if account.role == "admin"
                and not account.created_by else "")
        site = account.site if account is not None else ""
        department = account.department if account is not None else ""
        fields = [("Full name", self.session.full_name),
                  ("Email", (account.email if account is not None else "") or "-"),
                  ("Employee no.", (account.employee_no if account is not None else "") or "-"),
                  ("Role", self.session.role_label),
                  ("Organisation", "Oil India Limited"),
                  ("Site", site or "-"),
                  ("Department", department or "-")]
        if key != "admin":
            fields.append(("Project", "PS 26165"))
        fields += [("Account created", created), ("Session", self.session.session_id)]
        self.profile_view.set_person({
            "full_name": self.session.full_name, "initials": initials(self.session.full_name),
            "role": self.session.role_label, "site": site, "department": department,
            "last": self._long_date(self.session.started_at) if self.session.authenticated
            else "-", "workspace_key": key,
        }, fields, can_change_password=self.session.authenticated and account is not None)
        self.profile_view.check_updates.blockSignals(True)
        self.profile_view.check_updates.setChecked(bool(prefs.get("check_updates", True)))
        self.profile_view.check_updates.blockSignals(False)
        if hasattr(self.profile_view, "auto_refresh"):
            self.profile_view.auto_refresh.blockSignals(True)
            self.profile_view.auto_refresh.setChecked(bool(prefs.get("auto_refresh", True)))
            self.profile_view.auto_refresh.blockSignals(False)
        self.profile_view.set_activity([
            {"when": stamp(row.get("at")), "action": row.get("action", ""),
             "summary": row.get("summary", "")} for row in self._own_activity()])
        me = self.session.username
        self.profile_view.set_sessions([
            {"when": stamp(row.get("at")),
             "workstation": (row.get("detail") or {}).get("workstation") or socket.gethostname(),
             "role": ROLE_NAMES.get(str(row.get("role")), str(row.get("role") or "")),
             "state": "this session" if index == 0 else "ended"}
            for index, row in enumerate(entry for entry in self.audit.rows(limit=500)
                                        if entry.get("user") == me
                                        and entry.get("action") == "signed in")])

    def _refresh_logs(self) -> None:
        if self.pages.currentIndex() == self._page_index.get("syslog"):
            level = self.settings_view.level_box.currentText()
            self.settings_view.set_log_rows(
                [{"timestamp": entry.timestamp, "level": entry.level,
                  "logger": entry.logger, "message": entry.message}
                 for entry in self.ring.entries(level, limit=400)])
            return
        super()._refresh_logs()

    def _refresh_activity(self, view=None) -> None:
        super()._refresh_activity(view)
        if view is None and hasattr(self, "audit_view"):
            super()._refresh_activity(self.audit_view)

    @staticmethod
    def role_label_for(role: str) -> str:
        return ROLE_NAMES.get(role, role)

    def on_analysis_completed(self, *args, **kwargs):
        # The run is written to the trail after the base refresh, so the "last
        # analysis run" note is read again once it is there.
        result = super().on_analysis_completed(*args, **kwargs)
        self._refresh_shell()
        return result

    def _apply_role(self) -> None:
        super()._apply_role()
        # An HSE Analyst trains nothing here; an administrator decides nothing.
        self.engines_view.train_button.setEnabled(self.session.can(TRAIN))
        if hasattr(self, "actions_view"):
            self.actions_view.set_editable(self.session.can(ANALYSE))

    # -- compliance action items -------------------------------------------

    def _refresh_actions(self) -> None:
        first, last = self.actions_view.period()
        today = date.today()
        self.actions_view.show_occurrences(self.actions.occurrences(first, last, today),
                                           today=today,
                                           total_actions=len(self.actions.actions))

    def _owner_choices(self) -> List[Tuple[str, str]]:
        people = [(self.session.username, self.session.full_name)]
        if self.accounts is not None:
            people += [(account.username, account.full_name)
                       for account in self.accounts.accounts()
                       if account.active and account.role != "admin"
                       and account.username != self.session.username]
        return [(username, f"{name} ({username})") for username, name in people]

    def _reference_choices(self) -> List[Tuple[str, str]]:
        rows = sorted(self.rows, key=lambda row: (not row.get("sif_potential"),
                                                 -float(row.get("risk_score") or 0)))
        return [(str(row.get("reference")),
                 f"{row.get('reference')} - {row.get('iogp_rule') or 'no rule'}"
                 + ("  (SIF)" if row.get("sif_potential") else ""))
                for row in rows if row.get("reference")]

    @requires(ANALYSE)
    def add_action(self, day: str = "", reference: str = "") -> None:
        """Ask for a new action on ``day``; ``reference`` pre-links a report."""
        start = date.fromisoformat(day) if day else self.actions_view.selected
        dialog = ActionDialog(self.styleSheet(), self, day=start,
                              owners=self._owner_choices(), owner=self.session.username,
                              references=self._reference_choices(), reference=reference)
        if dialog.exec() != ActionDialog.DialogCode.Accepted:
            return
        self.create_action(**dialog.values())

    @requires(ANALYSE)
    def create_action(self, title: str, start, recurrence: str = "once", **details):
        try:
            action = self.actions.add(title, start, recurrence,
                                      created_by=self.session.username, **details)
        except ValueError as exc:
            self._set_status(str(exc))
            return None
        self.audit.functionality("compliance action added", title=action.title,
                                 start=action.start, recurrence=action.recurrence,
                                 owner=action.owner, reference=action.reference)
        self._set_status(f"Action added: {action.title}")
        self._refresh_actions()
        return action

    def open_action(self, action_id: str, day: str) -> None:
        item = next((entry for entry in self.actions.due(day)
                     if entry.action.id == action_id), None)
        if item is None:
            return
        owner = self.accounts.get(item.action.owner) if self.accounts else None
        dialog = ActionDetailDialog(item, self.styleSheet(), self,
                                    editable=self.session.can(ANALYSE),
                                    owner_label=f"{owner.full_name} ({owner.username})"
                                    if owner else item.action.owner)
        if dialog.exec() != ActionDetailDialog.DialogCode.Accepted:
            return
        if dialog.choice == "delete":
            self.delete_action(action_id)
        elif dialog.choice in ("done", "reopen"):
            self.complete_action(action_id, day, dialog.choice == "done")

    @requires(ANALYSE)
    def complete_action(self, action_id: str, day: str, done: bool = True) -> bool:
        action = self.actions.get(action_id)
        if action is None or not self.actions.set_done(action_id, day, self.session.username,
                                                       done):
            return False
        self.audit.functionality("compliance action done" if done
                                 else "compliance action reopened",
                                 title=action.title, date=day, reference=action.reference)
        self._set_status(f"{action.title} - {day}: {'done' if done else 'reopened'}")
        self._refresh_actions()
        return True

    @requires(ANALYSE)
    def delete_action(self, action_id: str) -> bool:
        action = self.actions.get(action_id)
        if action is None:
            return False
        if not self._confirm(f"Delete \"{action.title}\"" + (" and every date it repeats on"
                                                             if action.recurring else "")
                             + "?\n\nWhat was already marked done stays in the Audit Log."):
            return False
        self.actions.remove(action_id)
        self.audit.functionality("compliance action deleted", title=action.title,
                                 recurrence=action.recurrence, reference=action.reference)
        self._set_status(f"Action deleted: {action.title}")
        self._refresh_actions()
        return True

    @requires(ANALYSE)
    def load_sample_actions(self) -> int:
        count = self.actions.add_samples(date.today(), created_by=self.session.username)
        self.audit.functionality("compliance actions loaded", count=count,
                                 source="example field schedule")
        self._refresh_actions()
        return count

    # -- the person's own account -----------------------------------------

    def change_own_password(self, current: str, new: str) -> bool:
        store = self.accounts
        if store is None or not self.session.authenticated:
            return False
        try:
            store.change_password(self.session.username, current, new)
        except AuthError as exc:
            self.profile_view.set_security_note(str(exc), False)
            return False
        self.audit.functionality("password changed", username=self.session.username,
                                 reason="changed by the owner")
        self.profile_view.set_security_note("Password changed.", True)
        for field in (self.profile_view.current, self.profile_view.new,
                      self.profile_view.confirm):
            field.clear()
        return True

    # -- account management, with the two roles and a confirmation --------

    @requires(MANAGE_USERS)
    def add_account(self) -> None:
        dialog = AccountDialog(self.styleSheet(), self, roles=CREATABLE, labels=ROLE_NAMES)
        dialog.setWindowTitle("New HSE login")
        if dialog.exec() != AccountDialog.DialogCode.Accepted:
            return
        username, full_name, role = dialog.values()
        if role == "admin" and not self._confirm(
                f"Make {full_name or username} an Administrator?\n\nAn administrator "
                "manages accounts and engines, and cannot decide review cases."):
            return
        password = self.create_account(username, full_name, role)
        if password:
            self._show_one_time_password(username, password)

    @requires(MANAGE_USERS)
    def change_account_role(self, username: str, role: str = "") -> bool:
        if not role:
            account = self.accounts.get(username) if self.accounts else None
            if account is None:
                return False
            role = "reviewer" if account.role == "admin" else "admin"
            if not self._confirm(f"Change {account.full_name} to "
                                 f"{ROLE_NAMES[role]}?"):
                return False
        return MainWindow.change_account_role.__wrapped__(self, username, role)

    @requires(MANAGE_USERS)
    def toggle_account(self, username: str) -> bool:
        account = self.accounts.get(username) if self.accounts else None
        if account is not None and account.active and not self._confirm(
                f"Disable {account.full_name}'s account?\n\nThey will not be able to "
                "sign in until it is enabled again."):
            return False
        return MainWindow.toggle_account.__wrapped__(self, username)

    def _confirm(self, question: str) -> bool:
        """The confirmation step for a privileged change - when a person is there."""
        if not self.isVisible():
            return True
        answer = QMessageBox.question(self, APP_NAME, question)
        return answer == QMessageBox.StandardButton.Yes
