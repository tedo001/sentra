"""app4.py: the two-workspace build - HSE workspace and Administration.

Run:  QT_QPA_PLATFORM=offscreen SIF_ENCODER=hashing python -m unittest test_app4 -v

The fourth build keeps every engine of app.py but reorganises the console
around who is signed in: an HSE Analyst works in Home, Ingest, Dashboard,
HSE Review, Risk Hotspots and Profile; an administrator runs Engines,
Settings, SysLog, Audit Log and accounts. Safety judgement and platform
control live in separate accounts, so an administrator decides no review
case and an HSE Analyst trains no model. None of this may leak into the
other builds.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from typing import List

from sif import audit as audit_module
from sif.accounts import AccountStore

try:
    import PyQt6  # noqa: F401
    HAS_PYQT = True
except ImportError:  # pragma: no cover
    HAS_PYQT = False

#: Far below the production count: these tests hash many passwords.
FAST = 1_000
PASSWORD = "long enough"


@unittest.skipUnless(HAS_PYQT, "PyQt6 is not installed")
class TestBuildFour(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        import main2
        from ui.theme import C, LOOK

        palette = {name: getattr(C, name) for name in vars(C)
                   if name.isupper() and isinstance(getattr(C, name), str)}
        look = {name: getattr(LOOK, name) for name in vars(LOOK) if name.isupper()}
        self.addCleanup(self._restore, palette, look)

        folder = tempfile.mkdtemp(prefix="sif-app4-")
        self.addCleanup(shutil.rmtree, folder, True)
        self.audit_path = os.path.join(folder, "audit.jsonl")
        original = audit_module.audit_file_path
        audit_module.audit_file_path = lambda: self.audit_path
        self.addCleanup(setattr, audit_module, "audit_file_path", original)
        from sif import actions as actions_module

        self.actions_path = os.path.join(folder, "actions.json")
        original_actions = actions_module.default_action_path
        actions_module.default_action_path = lambda: self.actions_path
        self.addCleanup(setattr, actions_module, "default_action_path", original_actions)

        self.dialogs: List[str] = []
        boxes = (main2.QMessageBox.information, main2.QMessageBox.warning)
        main2.QMessageBox.information = lambda *a, **k: self.dialogs.append(str(a[2]))
        main2.QMessageBox.warning = lambda *a, **k: self.dialogs.append(str(a[2]))
        self.addCleanup(lambda: setattr(main2.QMessageBox, "information", boxes[0]))
        self.addCleanup(lambda: setattr(main2.QMessageBox, "warning", boxes[1]))

        self.store = AccountStore(os.path.join(folder, "users.json"), iterations=FAST)
        self.decisions_path = os.path.join(folder, "decisions.json")
        # Settings and "remember me" write preferences; never into a real profile.
        from sif import prefs

        original_prefs = prefs._path
        prefs._path = lambda: os.path.join(folder, "prefs.json")
        self.addCleanup(setattr, prefs, "_path", original_prefs)

    @staticmethod
    def _restore(palette, look) -> None:
        from ui.theme import LOOK, apply_palette

        apply_palette(palette)
        for name, value in look.items():
            setattr(LOOK, name, value)

    def _window(self, role: str, username: str = ""):
        import app4
        from sif.review import DecisionLog

        username = username or f"{role}.person"
        if self.store.get(username) is None:
            self.store.create(username, f"{role.title()} Person", role, PASSWORD)
        session = self.store.authenticate(username, PASSWORD)
        window = app4.build_window(session, self.store)
        self.addCleanup(window.close)
        window.decisions = DecisionLog(self.decisions_path)
        return window

    def _analyse(self, window) -> None:
        from sif import SEED_REPORTS

        window._start(window._analysis_worker(texts=list(SEED_REPORTS)))
        self.assertTrue(window.worker.wait(120_000))
        self.app.processEvents()

    def _actions(self) -> List[dict]:
        with open(self.audit_path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def _current(self, window) -> str:
        index = window.pages.currentIndex()
        names = [key for key, value in window._page_index.items() if value == index]
        return names[0] if names else ""

    # -- the two workspaces ------------------------------------------------

    def test_an_hse_analyst_lands_on_home_with_the_six_hse_tabs(self) -> None:
        import main4

        window = self._window("reviewer", "a.baruah")
        self.assertEqual(window.workspace, "hse")
        self.assertEqual(self._current(window), "home")
        self.assertEqual(window.tab_row.keys, [key for key, _ in main4.HSE_TABS])
        self.assertEqual(window.tab_row.keys,
                         ["home", "ingest", "dashboard", "review", "actions", "hotspots",
                          "profile"])
        self.assertEqual(window.shell_header.tag.text(), "HSE WORKSPACE")
        self.assertEqual(window.session.role_label, "HSE Analyst")

    def test_an_administrator_lands_on_engines_with_the_admin_tabs(self) -> None:
        window = self._window("admin", "d.manikandan")
        self.assertEqual(window.workspace, "admin")
        self.assertEqual(self._current(window), "engines")
        self.assertEqual(window.tab_row.keys,
                         ["engines", "settings", "syslog", "audit", "accounts", "profile"])
        self.assertEqual(window.shell_header.tag.text(), "ADMINISTRATION")
        self.assertEqual(window.tab_row.buttons["accounts"].text(), "New HSE Login")

    def test_a_page_of_the_other_workspace_stays_shut(self) -> None:
        hse = self._window("reviewer", "a.baruah")
        hse.navigate("engines")
        self.assertEqual(self._current(hse), "home")
        admin = self._window("admin", "d.manikandan")
        admin.navigate("review")
        self.assertEqual(self._current(admin), "engines")

    def test_the_window_holds_to_the_design_minimum(self) -> None:
        window = self._window("reviewer", "a.baruah")
        self.assertGreaterEqual(window.minimumWidth(), 1366)
        self.assertGreaterEqual(window.minimumHeight(), 768)

    # -- separation of duties ------------------------------------------------

    def test_an_administrator_decides_no_case_and_starts_no_analysis(self) -> None:
        analyst = self._window("reviewer", "a.baruah")
        self._analyse(analyst)

        admin = self._window("admin", "d.manikandan")
        admin.load_seed_data()
        self.assertIsNone(admin.worker, "an administrator does not analyse reports")
        admin.rows = list(analyst.rows)
        admin._refresh()
        before = len(admin.decisions.entries)
        admin.record_decision("confirmed", "")
        self.assertEqual(len(admin.decisions.entries), before)
        refused = [e["detail"]["attempted"] for e in self._actions()
                   if e["action"] == "permission refused" and e["user"] == "d.manikandan"]
        self.assertIn("load_seed_data", refused)
        self.assertIn("record_decision", refused)
        self.assertTrue(admin.engines_view.train_button.isEnabled())

    def test_an_hse_analyst_decides_here_but_trains_nothing(self) -> None:
        window = self._window("analyst", "r.sharma")
        self._analyse(window)
        window.navigate("review")
        window.select_review_row(0)
        window.record_decision("confirmed", "")
        self.assertEqual(window.decisions.entries[-1].reviewer, "Analyst Person (r.sharma)")
        self.assertFalse(window.engines_view.train_button.isEnabled())
        window.train_model()
        window.add_account()
        refused = [e["detail"]["attempted"] for e in self._actions()
                   if e["action"] == "permission refused"]
        self.assertIn("train_model", refused)
        self.assertIn("add_account", refused)

    def test_the_two_roles_stay_inside_this_build(self) -> None:
        """In app.py an analyst still cannot decide - app4's rights do not leak."""
        import main2
        from sif.review import DecisionLog

        self._window("analyst", "r.sharma")
        session = self.store.authenticate("r.sharma", PASSWORD)
        plain = main2.MainWindow(session, self.store)
        self.addCleanup(plain.close)
        plain.decisions = DecisionLog(self.decisions_path)
        self.assertFalse(plain.session.can("decide"))
        self.assertEqual(main2.MainWindow.role_label_for("reviewer"), "HSE Expert")

    # -- the pages -----------------------------------------------------------

    def test_home_shows_what_needs_a_person_and_opens_a_report(self) -> None:
        window = self._window("reviewer", "a.baruah")
        self._analyse(window)
        window.navigate("home")
        self.assertGreater(window.outstanding_reviews, 0)
        self.assertEqual(window.tab_row.badge.text(), str(window.outstanding_reviews))
        self.assertTrue(window.tab_row.note.text().startswith("Last analysis run"))
        reference = str(window.rows[-1]["reference"])
        window.open_report(reference)
        self.assertEqual(self._current(window), "reports")
        self.assertTrue(window.tab_row.buttons["dashboard"].isChecked())

    def test_syslog_audit_log_and_accounts_are_the_design_s_pages(self) -> None:
        import logging

        window = self._window("admin", "d.manikandan")
        logging.getLogger("sif.ocr").warning("low confidence 0.61 on a test photo")
        window.navigate("syslog")
        page = window.syslog_page
        self.assertTrue(page.table.rows, "the service log is listed")
        page.levels.select("WARNING")
        page.levels.changed.emit("WARNING")
        self.assertTrue(all(row["level"] == "WARNING" for row in page.table.rows))
        self.assertIn("OCR", [row["service"] for row in page.table.rows])

        window.navigate("audit")
        window.verify_audit_trail()
        self.assertIn("Chain intact", window.audit_page.banner.text())
        self.assertTrue(all(row.get("category") == "functionality"
                            for row in window.audit_page.table.rows), "human actions only")

        window.navigate("accounts")
        self.assertEqual(self._current(window), "accounts")
        self.assertIn("d.manikandan", [row["username"] for row in window.accounts_page.accounts])

    def test_the_account_menu_signs_out(self) -> None:
        window = self._window("reviewer", "a.baruah")
        window.shell_header.sign_out_requested.emit()
        self.assertTrue(window.sign_out_requested)
        self.assertIn("signed out", [e["action"] for e in self._actions()])

    def test_a_person_changes_their_own_password_from_profile(self) -> None:
        window = self._window("reviewer", "a.baruah")
        self.assertFalse(window.change_own_password("wrong one", "a new long one"))
        self.assertTrue(window.change_own_password(PASSWORD, "a new long one"))
        self.assertIsNotNone(self.store.authenticate("a.baruah", "a new long one"))
        changed = [e for e in self._actions() if e["action"] == "password changed"]
        self.assertEqual(changed[-1]["user"], "a.baruah")

    # -- compliance action items -------------------------------------------------

    def test_an_hse_analyst_adds_an_action_and_closes_one_date_of_it(self) -> None:
        from datetime import date

        window = self._window("reviewer", "a.baruah")
        window.navigate("actions")
        self.assertEqual(self._current(window), "actions")
        today = date.today()
        action = window.create_action("Gas test before hot work", today, "daily",
                                      category="Permit to work", owner="a.baruah")
        self.assertIsNotNone(action)
        cell = window.actions_view.cells[today]
        self.assertEqual([chip.item.action.id for chip in cell.chips], [action.id])
        self.assertIn("\u27f3", cell.chips[0].label.text(), "a repeating item is marked")

        self.assertTrue(window.complete_action(action.id, today.isoformat()))
        self.assertTrue(window.actions.get(action.id).is_done(today))
        chip = window.actions_view.cells[today].chips[0]
        self.assertEqual(chip.property("state"), "done")
        actions = [(e["action"], e["user"]) for e in self._actions()]
        self.assertIn(("compliance action added", "a.baruah"), actions)
        self.assertIn(("compliance action done", "a.baruah"), actions)

        self.assertTrue(window.delete_action(action.id))
        self.assertIsNone(window.actions.get(action.id))
        self.assertIn("compliance action deleted", [e["action"] for e in self._actions()])

    def test_a_crowded_day_shows_n_more_which_opens_its_week(self) -> None:
        from datetime import date

        from ui4.calendar import MONTH_LIMIT

        window = self._window("reviewer", "a.baruah")
        window.navigate("actions")
        today = date.today()
        for number in range(MONTH_LIMIT + 2):
            window.create_action(f"Check {number}", today)
        cell = window.actions_view.cells[today]
        self.assertEqual(len(cell.chips), MONTH_LIMIT)
        self.assertEqual(cell.more.text(), "2 more")
        cell.more.click()
        self.assertEqual(window.actions_view.mode, "week")
        self.assertEqual(len(window.actions_view.cells), 7)
        self.assertEqual(len(window.actions_view.cells[today].chips), MONTH_LIMIT + 2)

    def test_the_view_filter_narrows_the_calendar(self) -> None:
        from datetime import date

        window = self._window("reviewer", "a.baruah")
        self._window("analyst", "r.sharma")
        window.navigate("actions")
        today = date.today()
        window.create_action("Mine", today, owner="a.baruah")
        window.create_action("Theirs", today, owner="r.sharma")
        window.create_action("Re-test feeder", today, reference="NM-2601",
                             category="Corrective action")
        view = window.actions_view

        def titles(key):
            view.filter.setCurrentIndex(view.filter.findData(key))
            return sorted(item.action.title for item in view.visible_items())

        self.assertEqual(titles("all"), ["Mine", "Re-test feeder", "Theirs"])
        self.assertEqual(titles("mine"), ["Mine"])
        self.assertEqual(titles("corrective"), ["Re-test feeder"])
        self.assertEqual(titles("done"), [])

    def test_the_example_schedule_is_offered_only_on_an_empty_calendar(self) -> None:
        window = self._window("reviewer", "a.baruah")
        window.navigate("actions")
        self.assertFalse(window.actions_view.samples_button.isHidden())
        self.assertGreater(window.load_sample_actions(), 0)
        self.assertTrue(window.actions_view.samples_button.isHidden())

    def test_a_viewer_reads_the_calendar_but_changes_nothing(self) -> None:
        from datetime import date

        window = self._window("viewer", "v.person")
        window.navigate("actions")
        self.assertEqual(self._current(window), "actions")
        self.assertFalse(window.actions_view.add_button.isEnabled())
        self.assertIsNone(window.create_action("Anything", date.today()))
        self.assertEqual(window.actions.actions, [])
        refused = [e["detail"]["attempted"] for e in self._actions()
                   if e["action"] == "permission refused"]
        self.assertIn("create_action", refused)

    def test_the_calendar_belongs_to_the_hse_workspace(self) -> None:
        admin = self._window("admin", "d.manikandan")
        self.assertNotIn("actions", admin.tab_row.keys)
        admin.navigate("actions")
        self.assertEqual(self._current(admin), "engines")

    # -- the organisation's logo ---------------------------------------------------

    def _logo(self, folder: str, width: int, height: int) -> None:
        from PyQt6.QtGui import QColor, QImage

        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(QColor("#C8102E"))
        self.assertTrue(image.save(os.path.join(folder, "oil_logo.png")))

    def _header(self, folder: str):
        from ui4 import shell

        original = shell.LOGO_DIRECTORY
        shell.LOGO_DIRECTORY = folder
        self.addCleanup(setattr, shell, "LOGO_DIRECTORY", original)
        return shell.WorkspaceHeader("hse", "A. Baruah", "HSE Analyst", "a.baruah")

    def test_without_a_logo_file_the_header_keeps_the_drawn_badge(self) -> None:
        folder = tempfile.mkdtemp(prefix="sif-logo-")
        self.addCleanup(shutil.rmtree, folder, True)
        header = self._header(folder)
        self.assertEqual(header.mark.objectName(), "OilMark")
        self.assertEqual(header.mark.text(), "OIL")
        self.assertFalse(header.organisation.isHidden())

    def test_a_logo_file_replaces_the_badge(self) -> None:
        folder = tempfile.mkdtemp(prefix="sif-logo-")
        self.addCleanup(shutil.rmtree, folder, True)
        self._logo(folder, 200, 200)                      # an emblem: the name stays
        header = self._header(folder)
        self.assertEqual(header.mark.objectName(), "OilLogo")
        self.assertFalse(header.mark.pixmap().isNull())
        self.assertEqual(round(header.mark.pixmap().deviceIndependentSize().height()), 34)
        self.assertFalse(header.organisation.isHidden())

    def test_a_logo_with_the_name_in_it_is_not_captioned_twice(self) -> None:
        folder = tempfile.mkdtemp(prefix="sif-logo-")
        self.addCleanup(shutil.rmtree, folder, True)
        self._logo(folder, 600, 150)                      # a lockup: emblem and name
        header = self._header(folder)
        self.assertEqual(header.mark.objectName(), "OilLogo")
        self.assertTrue(header.organisation.isHidden())

    # -- the design's pages ----------------------------------------------------------

    def test_home_asks_for_the_critical_cases_first(self) -> None:
        window = self._window("reviewer", "a.baruah")
        self._analyse(window)
        window.navigate("home")
        page = window.home_page
        self.assertEqual(page.stats.cells[0].value.text(), str(len(window.rows)))
        alerts = [page.attention.body.itemAt(i).widget()
                  for i in range(page.attention.body.count())]
        alerts = [alert for alert in alerts if alert is not None and alert.objectName() == "Alert"]
        self.assertTrue(alerts, "a critical case needs someone")
        self.assertEqual(alerts[0].property("tone"), "critical")
        critical = [row for row in window.rows if float(row["risk_score"]) >= 85]
        top = max(critical, key=lambda row: float(row["risk_score"]))
        alerts[0].button.click()
        self.assertEqual(self._current(window), "review")
        self.assertEqual(window.review_page.current, str(top["reference"]))

    def test_ingest_works_a_csv_through_the_queue(self) -> None:
        window = self._window("reviewer", "a.baruah")
        sample = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples",
                              "near_miss_reports.csv")
        self.assertEqual(window.stage_files([sample]), 1)
        self.assertEqual(window.ingest_items[0]["state"], "queued")
        self.assertTrue(window.ingest_page.start.isEnabled())
        window.start_processing()
        self.assertIsNotNone(window.worker)
        self.assertTrue(window.worker.wait(120_000))
        for _ in range(5):
            self.app.processEvents()
        item = window.ingest_items[0]
        self.assertEqual((item["state"], item["stage"]), ("done", "Review"))
        self.assertEqual(item["reports"], len(window.rows))
        self.assertTrue(all(row.get("source") == "near_miss_reports.csv" for row in window.rows))
        self.assertTrue(window.rows[0].get("site"), "the export's site is kept")
        self.assertTrue(window.rows[0].get("reported_on"), "and its date")
        window.navigate("ingest")
        self.assertTrue(window.ingest_page.pipeline.cells[0].value.text().startswith("1 "))

    def test_a_viewer_cannot_stage_files(self) -> None:
        window = self._window("viewer", "v.person")
        self.assertIsNone(window.stage_files(["whatever.csv"]))
        self.assertEqual(window.ingest_items, [])

    def test_hse_review_decides_under_the_signed_in_person(self) -> None:
        window = self._window("reviewer", "a.baruah")
        self._analyse(window)
        window.navigate("review")
        page = window.review_page
        opened = int(page.tabs.tabText(0).split()[-1])
        self.assertEqual(opened, window.outstanding_reviews)
        reference = page.current
        self.assertTrue(reference)
        self.assertTrue(window.decide_case(reference, "confirmed"))
        entry = window.decisions.entries[-1]
        self.assertEqual((entry.reference, entry.decision), (reference, "confirmed"))
        self.assertEqual(entry.reviewer, "Reviewer Person (a.baruah)")
        self.assertEqual(int(page.tabs.tabText(0).split()[-1]), opened - 1)
        self.assertIn("reviewed", next(row["_in"] for row in page.rows
                                       if row["reference"] == reference))

    def test_a_viewer_reads_cases_but_the_decision_bar_is_shut(self) -> None:
        window = self._window("viewer", "v.person")
        self.assertFalse(window.review_page.bar.confirm.isEnabled())
        self.assertFalse(window.decide_case("SEED-01", "confirmed"))

    def test_the_dashboard_filters_by_site(self) -> None:
        window = self._window("reviewer", "a.baruah")
        sample = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples",
                              "near_miss_reports.csv")
        window._start(window._analysis_worker(csv_path=sample))
        self.assertTrue(window.worker.wait(120_000))
        self.app.processEvents()
        window.navigate("dashboard")
        page = window.dashboard_page
        page.period.select("365")
        page.period.changed.emit("365")
        self.assertEqual(page.stats.cells[0].value.text(), str(len(window.rows)))
        site = str(window.rows[0]["site"])
        page.site.setCurrentIndex(page.site.findData(site))
        expected = sum(1 for row in window.rows if row.get("site") == site)
        self.assertEqual(page.stats.cells[0].value.text(), str(expected))

    def test_hotspots_rank_by_the_wilson_lower_bound(self) -> None:
        from sif.patterns import wilson_lower_bound

        window = self._window("reviewer", "a.baruah")
        sample = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples",
                              "near_miss_reports.csv")
        window._start(window._analysis_worker(csv_path=sample))
        self.assertTrue(window.worker.wait(120_000))
        self.app.processEvents()
        window.navigate("hotspots")
        spots = window.hotspots_page.table.rows
        self.assertTrue(spots)
        densities = [spot["density"] for spot in spots]
        self.assertEqual(densities, sorted(densities, reverse=True))
        top = spots[0]
        self.assertAlmostEqual(top["density"],
                               wilson_lower_bound(top["sif_reports"], top["reports"]))
        self.assertEqual(len(window.hotspots_page.incident_table.rows), top["reports"])

    def test_a_reference_opens_the_report_page(self) -> None:
        window = self._window("reviewer", "a.baruah")
        self._analyse(window)
        reference = str(window.rows[2]["reference"])
        window.open_report(reference)
        self.assertEqual(self._current(window), "reports")
        self.assertEqual(window.reports_page.current, reference)
        self.assertEqual(window.reports_page.case.reference.text(), reference)

    def test_engines_show_real_state_and_training_is_guarded(self) -> None:
        admin = self._window("admin", "d.manikandan")
        admin.navigate("engines")
        cards = admin.engines_page.cards
        self.assertEqual(set(cards), {"encoder", "ocr", "llm", "risk", "model", "tracking"})
        self.assertIn(admin.llm.host, cards["llm"].facts.values["Host"].text())
        self.assertIn("No reviewed decisions", admin.run_evaluation())
        analyst = self._window("reviewer", "a.baruah")
        self.assertIsNone(analyst.toggle_model())
        refused = [e["detail"]["attempted"] for e in self._actions()
                   if e["action"] == "permission refused"]
        self.assertIn("toggle_model", refused)

    def test_a_setting_change_records_what_it_replaced(self) -> None:
        admin = self._window("admin", "d.manikandan")
        admin.navigate("settings")
        self.assertTrue(admin.change_setting("project_code", "PS 26165-B"))
        self.assertEqual(admin.shell_header.project.text(), "PS 26165-B")
        entry = [e for e in self._actions() if e["action"] == "setting changed"][-1]
        self.assertEqual((entry["detail"]["previous"], entry["detail"]["new"]),
                         ("PS 26165", "PS 26165-B"))
        self.assertFalse(admin.change_setting("no_such_setting", 1))
        analyst = self._window("reviewer", "a.baruah")
        self.assertIsNone(analyst.change_setting("project_code", "X"))

    def test_an_administrator_creates_an_hse_login_that_signs_in_by_email(self) -> None:
        admin = self._window("admin", "d.manikandan")
        password = admin.create_hse_account({
            "full_name": "Priyanka Saikia", "email": "p.saikia@oilindia.in",
            "username": "p.saikia", "role": "reviewer", "site": "Rig S-12 Moran",
            "department": "HSE — Field Operations", "active": True})
        self.assertEqual(len(password), 12)
        account = self.store.get("p.saikia")
        self.assertEqual((account.email, account.site), ("p.saikia@oilindia.in", "Rig S-12 Moran"))
        session = self.store.authenticate("p.saikia@oilindia.in", password)
        self.assertEqual(session.username, "p.saikia")
        self.assertTrue(admin.change_account_role("p.saikia", "viewer"))
        change = [e for e in self._actions() if e["action"] == "role changed"][-1]
        self.assertEqual((change["detail"]["previous"], change["detail"]["role"]),
                         ("reviewer", "viewer"))
        from ui4.auditlog import describe_entry

        row = describe_entry(change)
        self.assertEqual((row["previous"], row["new"]), ("HSE Analyst", "Viewer"))

    def test_the_sign_in_screen_keeps_the_login_logic(self) -> None:
        from sif.audit import AuditLog
        from ui4.login import WorkspaceLogin

        empty = AccountStore(os.path.join(os.path.dirname(self.audit_path), "none.json"),
                             iterations=FAST)
        self.assertEqual(WorkspaceLogin(empty, AuditLog(self.audit_path)).page, "setup")
        self.store.create("a.baruah", "Anupam Baruah", "reviewer", PASSWORD)
        self.store.set_profile("a.baruah", email="a.baruah@oilindia.in")
        dialog = WorkspaceLogin(self.store, AuditLog(self.audit_path))
        self.assertEqual(dialog.page, "sign in")
        dialog.username.setText("a.baruah@oilindia.in")
        dialog.password.setText("wrong password")
        dialog.sign_in()
        self.assertIsNone(dialog.session)
        self.assertEqual(self._actions()[-1]["action"], "sign-in refused")
        dialog.password.setText(PASSWORD)
        dialog.remember.setChecked(True)
        dialog.sign_in()
        self.assertEqual(dialog.session.username, "a.baruah")
        again = WorkspaceLogin(self.store, AuditLog(self.audit_path))
        self.assertEqual(again.username.text(), "a.baruah@oilindia.in")

    def test_the_profile_shows_the_account_s_particulars(self) -> None:
        window = self._window("reviewer", "a.baruah")
        self.store.set_profile("a.baruah", email="a.baruah@oilindia.in",
                               site="Duliajan Field HQ", department="HSE — Field Operations")
        window.navigate("profile")
        values = window.profile_view.fields.values
        self.assertEqual(values["Email"].text(), "a.baruah@oilindia.in")
        self.assertEqual(window.profile_view.inline["site"].text(), "Duliajan Field HQ")

    def test_the_bundled_fonts_load(self) -> None:
        from PyQt6.QtGui import QFontDatabase

        from ui import workspace_theme

        self.assertTrue(workspace_theme.load_fonts())
        self.assertIn("IBM Plex Sans", QFontDatabase.families())
        self.assertIn("IBM Plex Mono", QFontDatabase.families())

    # -- the entry point -------------------------------------------------------

    def test_the_entry_point_signs_in_and_wears_the_workspace_design(self) -> None:
        import inspect

        import app4
        from ui import workspace_theme

        self.assertIn("run_signed_in", inspect.getsource(app4.main))
        window = self._window("reviewer", "a.baruah")
        self.assertEqual(window.styleSheet(), workspace_theme.STYLESHEET)
        self.assertEqual(window.windowTitle(), "SENTRA")

    def test_presentation_mode_scales_the_interface_before_qt_starts(self) -> None:
        import app4

        saved = {key: os.environ.pop(key, None)
                 for key in ("QT_SCALE_FACTOR", "SENTRA_SCALE", "SENTRA_PRESENT")}
        self.addCleanup(self._restore_environment, saved)
        self.addCleanup(setattr, app4, "_presenting", app4._presenting)

        self.assertFalse(app4.presentation_requested(["app4.py"]))
        self.assertTrue(app4.presentation_requested(["app4.py", "--present"]))
        argv = app4.enter_presentation(["app4.py", "--present"])
        self.assertEqual(argv, ["app4.py"], "Qt must not see the flag")
        self.assertEqual(os.environ["QT_SCALE_FACTOR"], app4.PRESENT_SCALE)

        os.environ.pop("QT_SCALE_FACTOR")
        os.environ["SENTRA_SCALE"] = "2"
        app4.enter_presentation(["app4.py"])
        self.assertEqual(os.environ["QT_SCALE_FACTOR"], "2")

    @staticmethod
    def _restore_environment(saved) -> None:
        for key, value in saved.items():
            os.environ.pop(key, None)
            if value is not None:
                os.environ[key] = value

    def test_building_it_leaves_the_other_builds_as_they_were(self) -> None:
        import app
        from ui import green_theme
        from ui.theme import LOOK

        self._window("reviewer", "a.baruah")
        one = app.build_window()
        self.addCleanup(one.close)
        self.assertEqual(one.styleSheet(), green_theme.STYLESHEET)
        self.assertFalse(hasattr(one, "tab_row"))
        self.assertFalse(one.sidebar.isHidden())
        self.assertFalse(LOOK.NAV_NUMBERED)


if __name__ == "__main__":
    unittest.main()
