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

        self.dialogs: List[str] = []
        boxes = (main2.QMessageBox.information, main2.QMessageBox.warning)
        main2.QMessageBox.information = lambda *a, **k: self.dialogs.append(str(a[2]))
        main2.QMessageBox.warning = lambda *a, **k: self.dialogs.append(str(a[2]))
        self.addCleanup(lambda: setattr(main2.QMessageBox, "information", boxes[0]))
        self.addCleanup(lambda: setattr(main2.QMessageBox, "warning", boxes[1]))

        self.store = AccountStore(os.path.join(folder, "users.json"), iterations=FAST)
        self.decisions_path = os.path.join(folder, "decisions.json")

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
                         ["home", "ingest", "dashboard", "review", "hotspots", "profile"])
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

    def test_syslog_holds_the_service_log_and_audit_the_chain(self) -> None:
        window = self._window("admin", "d.manikandan")
        window.navigate("syslog")
        self.assertIs(window.settings_view.logging_panel.window(), window)
        self.assertTrue(window.settings_view.audit_panel.isHidden())
        window.navigate("audit")
        window.verify_audit_trail()
        self.assertIn("Chain intact", window.audit_view.chain_label.text())
        self.assertTrue(window.audit_view.people_panel.isHidden())
        window.navigate("accounts")
        self.assertFalse(window.activity_view.add_button.isHidden())
        self.assertTrue(window.activity_view.activity_panel.isHidden())

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
