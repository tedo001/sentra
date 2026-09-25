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
from typing import Dict, List, Optional, Tuple

from PyQt6.QtWidgets import QMessageBox, QVBoxLayout, QWidget

from main2 import APP_NAME, MainWindow, requires
from sif import prefs
from sif.accounts import (ANALYSE, CLEAR, CONFIGURE, DECIDE, MANAGE_USERS, TRAIN, VIEW,
                          AccountStore, AuthError, Session)
from sif.version import __version__
from ui2.activity import AccountDialog, ActivityView
from ui2.components import titled
from ui4.pages import HomeView, ProfileView
from ui4.shell import TabRow, WorkspaceHeader

__all__ = ["WorkspaceSession", "WorkspaceWindow", "HSE_TABS", "ADMIN_TABS",
           "workspace_session"]

HSE_TABS: Tuple[Tuple[str, str], ...] = (
    ("home", "Home"), ("ingest", "Ingest"), ("dashboard", "Dashboard"),
    ("review", "HSE Review"), ("hotspots", "Risk Hotspots"), ("profile", "Profile"))
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


class WorkspaceWindow(MainWindow):
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

        self.home_view = HomeView()
        self.profile_view = ProfileView()
        self._add_page("home", self.home_view, "Home",
                       "What needs you now: the counts, the cases waiting for a person, "
                       "the latest reports and your own recent work.")
        self._add_page("profile", self.profile_view, "Profile",
                       "Who you are signed in as, your password, your preferences and "
                       "your own activity.")

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
        self.home_view.review_requested.connect(lambda: self.navigate("review"))
        self.home_view.ingest_requested.connect(lambda: self.navigate("ingest"))
        self.home_view.report_requested.connect(self.open_report)
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
        elif key == "profile":
            self._refresh_profile()
        elif key == "syslog":
            self._refresh_logs()
        elif key in ("audit", "accounts"):
            self._refresh_activity()
        # A report opened from Home is part of the corpus view.
        self.tab_row.select("dashboard" if key == "reports" else key)

    def open_report(self, reference: str) -> None:
        """Open one report with its evidence - the drill-down from Home."""
        for index, row in enumerate(self.rows):
            if str(row.get("reference")) == reference:
                self.navigate("reports")
                self.select_row(index)
                return

    # -- refreshing ----------------------------------------------------------

    def _refresh(self, *args, **kwargs):
        result = super()._refresh(*args, **kwargs)
        if getattr(self, "_shell_ready", False):
            self._refresh_shell()
            if self.pages.currentIndex() == self._page_index.get("home"):
                self._refresh_home()
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

    def _refresh_home(self) -> None:
        self.home_view.show_state(self.rows, self.queue_rows, self.outstanding_reviews,
                                  self._own_activity())

    def _refresh_profile(self) -> None:
        account = self.accounts.get(self.session.username) if self.accounts else None
        self.profile_view.set_person({
            "full_name": self.session.full_name,
            "username": self.session.username,
            "role": self.session.role_label,
            "workspace": "Administration" if self.workspace == "admin" else "HSE workspace",
            "signed_in": self.session.started_at.replace("T", " "),
            "session": self.session.session_id,
        }, can_change_password=self.session.authenticated and account is not None)
        self.profile_view.check_updates.blockSignals(True)
        self.profile_view.check_updates.setChecked(bool(prefs.get("check_updates", True)))
        self.profile_view.check_updates.blockSignals(False)
        self.profile_view.set_activity(self._own_activity())

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
