"""sentra.py: the revamp's console, its database, its backups and its LLM button.

Run:  QT_QPA_PLATFORM=offscreen SIF_ENCODER=hashing python -m unittest test_sentra -v

The SENTRA build is build 4's controller in the revamp's design, so the
two-workspace rules are tested in test_app4; what is tested here is what
SENTRA adds - the Data & Backup tab, the SQL store the console reads and
writes, the vector index, encrypted backup and restore, and ``gemma2:latest``
switched on from the start - and that none of it leaks into app4.
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

FAST = 1_000
PASSWORD = "long enough"
PASSPHRASE = "correct horse battery"


@unittest.skipUnless(HAS_PYQT, "PyQt6 is not installed")
class TestSentra(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        os.environ.setdefault("SIF_ENCODER", "hashing")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        import main2
        from ui.theme import C, LOOK

        palette = {name: getattr(C, name) for name in vars(C)
                   if name.isupper() and isinstance(getattr(C, name), str)}
        look = {name: getattr(LOOK, name) for name in vars(LOOK) if name.isupper()}
        self.addCleanup(self._restore, palette, look)

        self.folder = tempfile.mkdtemp(prefix="sentra-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.audit_path = os.path.join(self.folder, "audit.jsonl")
        original = audit_module.audit_file_path
        audit_module.audit_file_path = lambda: self.audit_path
        self.addCleanup(setattr, audit_module, "audit_file_path", original)
        from sif import actions as actions_module
        from sif import prefs

        original_actions = actions_module.default_action_path
        actions_module.default_action_path = lambda: os.path.join(self.folder, "actions.json")
        self.addCleanup(setattr, actions_module, "default_action_path", original_actions)
        original_config = prefs.config_directory
        prefs.config_directory = lambda: self.folder
        self.addCleanup(setattr, prefs, "config_directory", original_config)
        original_prefs = prefs._path
        prefs._path = lambda: os.path.join(self.folder, "prefs.json")
        self.addCleanup(setattr, prefs, "_path", original_prefs)

        self.dialogs: List[str] = []
        boxes = (main2.QMessageBox.information, main2.QMessageBox.warning)
        main2.QMessageBox.information = lambda *a, **k: self.dialogs.append(str(a[2]))
        main2.QMessageBox.warning = lambda *a, **k: self.dialogs.append(str(a[2]))
        self.addCleanup(lambda: setattr(main2.QMessageBox, "information", boxes[0]))
        self.addCleanup(lambda: setattr(main2.QMessageBox, "warning", boxes[1]))
        self.store = AccountStore(os.path.join(self.folder, "users.json"), iterations=FAST)
        self.db_url = "sqlite:///" + os.path.join(self.folder, "sentra.db")

    @staticmethod
    def _restore(palette, look) -> None:
        from ui import workspace_theme
        from ui.theme import LOOK, apply_palette

        apply_palette(palette)
        for name, value in look.items():
            setattr(LOOK, name, value)
        workspace_theme.prepare()

    def _window(self, role: str, username: str = "", **options):
        import sentra
        from sif.datastore import DataStore
        from sif.review import DecisionLog
        from sif.vault import Vault

        username = username or f"{role}.person"
        if self.store.get(username) is None:
            self.store.create(username, f"{role.title()} Person", role, PASSWORD)
        session = self.store.authenticate(username, PASSWORD)
        options.setdefault("probe_llm", False)
        datastore = DataStore(self.db_url)
        window = sentra.build_window(session, self.store, datastore=datastore,
                                     vault=Vault(self.folder), **options)
        window.decisions = DecisionLog(os.path.join(self.folder, "decisions.json")).load()
        window.wait_for_tasks()
        self.addCleanup(self._close, window)
        return window

    def _close(self, window) -> None:
        window.wait_for_tasks()
        window.close()
        self.app.processEvents()

    def _analyse(self, window) -> None:
        from sif import SEED_REPORTS

        window._start(window._analysis_worker(texts=list(SEED_REPORTS)))
        self.assertTrue(window.worker.wait(120_000))
        self.app.processEvents()
        window.wait_for_tasks()

    def _actions(self) -> List[str]:
        with open(self.audit_path, encoding="utf-8") as handle:
            return [json.loads(line)["action"] for line in handle if line.strip()]

    # -- the shell ------------------------------------------------------------------

    def test_the_hse_workspace_has_its_tabs_and_asset_memory_in_the_revamp_pages(self) -> None:
        from ui5.actions import SentraActions
        from ui5.dashboard import SentraDashboard
        from ui5.review import SentraReview

        window = self._window("reviewer")
        self.assertEqual(window.tab_row.keys, ["home", "ingest", "dashboard", "review",
                                               "actions", "hotspots", "assets", "profile"])
        self.assertIsInstance(window.dashboard_page, SentraDashboard)
        self.assertIsInstance(window.review_page, SentraReview)
        self.assertIsInstance(window.actions_view, SentraActions)
        self.assertEqual(window.windowTitle(), "SENTRA")
        self.assertFalse(hasattr(window, "data_page"))
        window.navigate("data")
        self.assertNotEqual(window.pages.currentIndex(), window._page_index.get("data", -1))

    def test_an_administrator_gets_data_and_backup_before_profile(self) -> None:
        window = self._window("admin")
        self.assertEqual(window.tab_row.keys, ["engines", "settings", "syslog", "audit",
                                               "accounts", "data", "profile"])
        window.navigate("data")
        self.assertEqual(window.pages.currentIndex(), window._page_index["data"])
        self.assertIn("SQLite", window.data_page.db_where.text())

    def test_the_dashboard_draws_the_weekly_trend(self) -> None:
        window = self._window("reviewer")
        self._analyse(window)
        window.navigate("dashboard")
        chart = window.dashboard_page.trend_chart
        self.assertEqual(len(chart.weeks), 13)
        self.assertIn("weekly counts", window.dashboard_page.trend_span.text())
        window.dashboard_page.period.buttons["30"].click()
        self.assertEqual(len(window.dashboard_page.trend_chart.weeks), 5)

    # -- gemma2:latest, always on ------------------------------------------------------------

    def test_gemma2_is_the_model_and_is_switched_on_from_the_start(self) -> None:
        window = self._window("reviewer")
        self.assertEqual(window.llm.model, "gemma2:latest")
        self.assertTrue(window.llm_enabled)
        self.assertEqual(window.llm_button.text(), "gemma2:latest")
        # Not attached until the host has answered: no per-report timeouts.
        self.assertFalse(window.pipeline.has_llm)

    def test_the_button_reports_what_the_host_said(self) -> None:
        window = self._window("reviewer")
        window._llm_checked(window.llm, False, True, (True, True, "Ollama ready"))
        self.assertEqual(window.llm_button.state, "ready")
        self.assertTrue(window.pipeline.has_llm)
        window._llm_checked(window.llm, False, True, (True, False, "model not pulled"))
        self.assertEqual(window.llm_button.state, "missing")
        self.assertIn("ollama pull gemma2:latest", window.llm_button.toolTip())
        self.assertFalse(window.pipeline.has_llm)
        window._llm_checked(window.llm, True, True, (False, False, "refused"))
        self.assertEqual(window.llm_button.state, "offline")

    def test_a_real_probe_of_an_absent_host_says_offline(self) -> None:
        from sif.llm import OllamaEngine

        window = self._window("reviewer")
        window.llm = OllamaEngine(host="http://127.0.0.1:9", model="gemma2:latest")
        window.check_llm()
        window.wait_for_tasks()
        self.assertEqual(window.llm_button.state, "offline")
        self.assertFalse(window.llm_online)

    def test_only_an_administrator_switches_it_off_and_the_choice_is_kept(self) -> None:
        from sif import prefs

        analyst = self._window("reviewer")
        self.assertFalse(analyst.llm_button.can_configure)
        analyst.set_llm_enabled(False)
        self.assertTrue(analyst.llm_enabled)
        self.assertIn("permission refused", self._actions())

        admin = self._window("admin")
        self.assertTrue(admin.llm_button.can_configure)
        admin.set_llm_enabled(False)
        admin.wait_for_tasks()
        self.assertFalse(admin.llm_enabled)
        self.assertEqual(admin.llm_button.state, "off")
        self.assertFalse(prefs.get("llm_always_on", True))
        self.assertIn("LLM analyser switched off", self._actions())
        self.assertFalse(self._window("reviewer", "second").llm_enabled)

    # -- the SQL database and the vector index --------------------------------------------------

    def test_an_analysis_run_is_written_and_the_next_session_loads_it(self) -> None:
        first = self._window("reviewer")
        self._analyse(first)
        self.assertEqual(first.datastore.counts()["reports"], len(first.rows))
        self.assertEqual(first.vectors.count(), len(first.rows))
        references = sorted(str(row["reference"]) for row in first.rows)
        self._close(first)

        second = self._window("reviewer", "someone.else")
        self.assertEqual(sorted(str(row["reference"]) for row in second.rows), references)
        self.assertEqual(second.outstanding_reviews, first.outstanding_reviews)

    def test_a_decision_reaches_the_database_and_undo_withdraws_it(self) -> None:
        window = self._window("reviewer")
        self._analyse(window)
        window.navigate("review")
        window.review_view.select(0)
        window.record_decision("confirmed", "")
        window.wait_for_tasks()
        self.assertEqual(window.datastore.counts()["decisions"], 1)
        window.undo_decision()
        self.assertEqual(window.datastore.counts()["decisions"], 0)

    def test_sync_now_is_an_administrator_action_and_is_audited(self) -> None:
        self._analyse(self._window("reviewer"))
        analyst = self._window("reviewer", "second.analyst")
        self.assertIsNone(analyst.request_sync())
        admin = self._window("admin")
        admin.request_sync()
        admin.wait_for_tasks()
        self.assertIn("data synced", self._actions())
        self.assertTrue(admin.datastore.last("sync")["ok"])

    def test_similar_reports_are_found_through_the_index(self) -> None:
        analyst = self._window("reviewer")
        self._analyse(analyst)
        self._close(analyst)
        admin = self._window("admin")
        admin.navigate("data")
        admin.find_similar(str(admin.rows[0]["raw_text"]))
        admin.wait_for_tasks()
        rows = admin.data_page.similar.rows
        self.assertTrue(rows)
        self.assertEqual(rows[0]["reference"], admin.rows[0]["reference"])

    def test_switching_to_another_database_carries_the_session_across(self) -> None:
        analyst = self._window("reviewer")
        self._analyse(analyst)
        self._close(analyst)
        admin = self._window("admin")
        other = "sqlite:///" + os.path.join(self.folder, "shared.db")
        admin.apply_database(other)
        admin.wait_for_tasks()
        self.assertEqual(admin.datastore.url, other)
        self.assertEqual(admin.datastore.counts()["reports"], len(admin.rows))
        self.assertIn("database changed", self._actions())
        admin.apply_database("postgresql+nodriver://x@nowhere/db")
        admin.wait_for_tasks()
        self.assertEqual(admin.datastore.url, other)

    # -- backup ---------------------------------------------------------------------------------

    def test_backup_verify_and_restore_through_a_synced_folder(self) -> None:
        from sif import backup, prefs

        analyst = self._window("reviewer")
        self._analyse(analyst)
        self._close(analyst)
        admin = self._window("admin")
        admin.navigate("data")
        cloud = os.path.join(self.folder, "OneDrive", "SENTRA")
        config = {"kind": "folder", "folder": cloud, "schedule": "daily", "keep": 5}
        self.assertFalse(admin.save_backup_settings(config, {"passphrase": "short",
                                                             "passphrase_again": "short"}))
        self.assertTrue(admin.save_backup_settings(
            config, {"passphrase": PASSPHRASE, "passphrase_again": PASSPHRASE}))
        with open(prefs._path(), encoding="utf-8") as handle:
            self.assertNotIn(PASSPHRASE, handle.read())
        admin.backup_now()
        admin.wait_for_tasks()
        names = os.listdir(cloud)
        self.assertEqual(len(names), 1)
        with open(os.path.join(cloud, names[0]), "rb") as handle:
            manifest, members = backup.read_archive(handle.read(), PASSPHRASE)
        self.assertEqual(manifest["counts"]["reports"], len(admin.rows))
        self.assertIn("users.json", members)
        self.assertIn("audit.jsonl", members)
        self.assertEqual(len(admin.data_page.backups.rows), 1)

        admin.verify_backup(names[0])
        admin.wait_for_tasks()
        self.assertIn("intact", admin.data_page.backups_note.text())

        admin.restore_backup(names[0])
        admin.wait_for_tasks()
        self.assertIn("Restored", admin.data_page.backups_note.text())
        restored = os.path.join(self.folder, "restored")
        self.assertEqual(len(os.listdir(restored)), 1)
        actions = self._actions()
        for action in ("backup settings changed", "backup made", "backup verified",
                       "backup restored"):
            self.assertIn(action, actions)

    def test_a_scheduled_backup_runs_when_owed(self) -> None:
        from sif import prefs

        admin = self._window("admin")
        cloud = os.path.join(self.folder, "share")
        admin.save_backup_settings({"kind": "folder", "folder": cloud, "schedule": "daily"},
                                   {"passphrase": PASSPHRASE, "passphrase_again": PASSPHRASE})
        analyst = self._window("reviewer")
        analyst._scheduled_backup()
        analyst.wait_for_tasks()
        self.assertEqual(len(os.listdir(cloud)), 1)
        self.assertTrue(prefs.get("last_backup"))
        analyst._scheduled_backup()
        analyst.wait_for_tasks()
        self.assertEqual(len(os.listdir(cloud)), 1)

    def test_a_backup_is_refused_without_a_passphrase(self) -> None:
        admin = self._window("admin")
        admin.navigate("data")
        self.assertFalse(admin.backup_now())
        self.assertFalse(admin.save_backup_settings({"kind": "folder", "folder": self.folder},
                                                    {}))

    # -- Asset Safety Memory and Work-Hold Recommendation ---------------------------------

    def _analyse_samples(self, window) -> None:
        window._start(window._analysis_worker(csv_path=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "samples", "near_miss_reports.csv")))
        self.assertTrue(window.worker.wait(120_000))
        self.app.processEvents()
        window.wait_for_tasks()

    def test_asset_memory_is_a_tab_and_ranks_the_assets(self) -> None:
        window = self._window("reviewer")
        self.assertIn("assets", window.tab_row.keys)
        self.assertEqual(window.tab_row.keys[-2:], ["assets", "profile"])
        self._analyse_samples(window)
        window.navigate("assets")
        page = window.assets_page
        names = [row["asset"] for row in page.table.rows]
        self.assertIn("Duliajan OCS-4", names[:3])
        self.assertEqual(page.title.text(), names[0])
        page.select("Duliajan OCS-4")
        self.assertEqual([row["reference"] for row in page.timeline.rows],
                         ["NM-2607", "NM-2601"])
        self.assertTrue(page.signal_box.count())

    def test_work_holds_lead_home_and_review_and_are_audited_once(self) -> None:
        window = self._window("reviewer")
        self._analyse_samples(window)
        holds = window.holds()
        self.assertIn("NM-2607", holds)
        self.assertEqual(window.recommendation("NM-2607").level, "hold")
        self.assertEqual(window.recommendation("NM-2609").level, "continue")
        window.navigate("home")
        first = window.home_page.attention.body.itemAt(0).widget()
        self.assertIn("Work-Hold Recommended", " ".join(
            label.text() for label in first.findChildren(__import__(
                "PyQt6.QtWidgets", fromlist=["QLabel"]).QLabel)))
        window.navigate("review")
        page = window.review_page
        self.assertEqual(page.filters[1], ("hold", "Work-hold"))
        self.assertTrue(page.rows[0]["trigger"].startswith("Work-hold"))
        raised = [line for line in self._actions() if line == "work-hold recommended"]
        self.assertEqual(len(raised), len(holds))
        window._memory_dirty = True
        window.memory()
        self.assertEqual(len([line for line in self._actions()
                              if line == "work-hold recommended"]), len(holds))

    def test_a_case_shows_its_recommendation_and_its_asset_history(self) -> None:
        window = self._window("reviewer")
        self._analyse_samples(window)
        window.show()
        window.navigate("review")
        window.review_page.select("NM-2607")
        self.app.processEvents()
        panel = window.review_page.recommendation
        self.assertTrue(panel.isVisible())
        self.assertEqual(panel.level.text(), "Work-Hold Recommended")
        memory = window.review_page.memory
        self.assertTrue(memory.isVisible())
        self.assertEqual(memory.name.text(), "Duliajan OCS-4")
        self.assertIn("NM-2601", [memory.earlier.itemAt(i).widget().text().split(" ")[0]
                                  for i in range(memory.earlier.count())
                                  if memory.earlier.itemAt(i).widget()])
        window.close()

    def test_a_reviewer_who_rejects_a_hold_releases_it(self) -> None:
        window = self._window("reviewer")
        self._analyse_samples(window)
        window.navigate("review")
        window.review_page.select("NM-2607")
        self.assertTrue(window.decide_case("NM-2607", "rejected"))
        self.assertNotIn("NM-2607", window.holds())
        self.assertEqual(window.recommendation("NM-2607").level, "continue")

    def test_the_memory_and_the_holds_are_kept_in_the_database(self) -> None:
        window = self._window("reviewer")
        self._analyse_samples(window)
        window.wait_for_tasks()
        store = window.datastore
        self.assertGreaterEqual(store.counts()["asset_memory"], 10)
        stored = {item["reference"]: item["level"] for item in store.holds()}
        self.assertEqual(stored["NM-2607"], "hold")
        ocs4 = next(item for item in store.assets() if item["asset"] == "Duliajan OCS-4")
        self.assertTrue(ocs4["signal_list"])

    # -- the sign-in -----------------------------------------------------------------------------

    def test_the_sign_in_page_signs_in_by_email(self) -> None:
        from sif.audit import AuditLog
        from ui import sentra_theme
        from ui5.login import SentraLogin

        sentra_theme.prepare()
        self.store.create("a.baruah", "Anupam Baruah", "reviewer", PASSWORD)
        self.store.set_profile("a.baruah", email="a.baruah@oilindia.in")
        dialog = SentraLogin(self.store, AuditLog(self.audit_path), sentra_theme.STYLESHEET)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.remember.text(), "Remember Me")
        self.assertTrue(dialog.remember.isChecked())
        dialog.username.setText("a.baruah@oilindia.in")
        dialog.password.setText(PASSWORD)
        dialog.sign_in()
        self.assertIsNotNone(dialog.session)
        self.assertEqual(dialog.session.username, "a.baruah")

    def _login(self):
        from sif.audit import AuditLog
        from ui import sentra_theme
        from ui5.login import SentraLogin

        sentra_theme.prepare()
        dialog = SentraLogin(self.store, AuditLog(self.audit_path), sentra_theme.STYLESHEET)
        self.addCleanup(dialog.close)
        dialog.resize(1440, 900)
        dialog.show()
        self.app.processEvents()
        return dialog

    def test_the_sign_in_block_is_centred_on_one_left_edge(self) -> None:
        from PyQt6.QtCore import QPoint
        from PyQt6.QtWidgets import QFrame, QLabel

        self.store.create("a.baruah", "Anupam Baruah", "reviewer", PASSWORD)
        dialog = self._login()
        left = dialog.findChild(QFrame, "LoginForm")
        wordmark = dialog.findChild(QLabel, "FormWordmark")
        edges = {widget.mapTo(left, QPoint(0, 0)).x()
                 for widget in (wordmark, dialog.username, dialog.password.parentWidget(),
                                dialog.remember, dialog.sign_in_button)}
        self.assertEqual(len(edges), 1, edges)
        block = wordmark.parentWidget()
        centre = block.mapTo(left, QPoint(0, 0)).x() + block.width() / 2
        self.assertAlmostEqual(centre, left.width() / 2, delta=2)
        forgot = dialog.forgot_link.mapTo(left, QPoint(dialog.forgot_link.width(), 0)).x()
        right = dialog.sign_in_button.mapTo(left, QPoint(dialog.sign_in_button.width(), 0)).x()
        self.assertAlmostEqual(forgot, right, delta=2)

    def test_forgot_password_asks_the_administrator_without_saying_who_exists(self) -> None:
        self.store.create("a.baruah", "Anupam Baruah", "reviewer", PASSWORD)
        self.store.set_profile("a.baruah", email="a.baruah@oilindia.in")
        dialog = self._login()
        dialog.username.setText("a.baruah@oilindia.in")
        dialog.forgot_link.click()
        self.assertEqual(dialog.page, "forgot")
        self.assertEqual(dialog.forgot_name.text(), "a.baruah@oilindia.in")
        self.assertTrue(dialog.request_reset())
        known = dialog.forgot_note.text()
        dialog.forgot_name.setText("nobody@oilindia.in")
        self.assertTrue(dialog.request_reset())
        self.assertEqual(dialog.forgot_note.text(), known)
        with open(self.audit_path, encoding="utf-8") as handle:
            requests = [json.loads(line)["detail"] for line in handle
                        if '"password reset requested"' in line]
        self.assertEqual([(item["username"], item["known"]) for item in requests],
                         [("a.baruah", True), ("nobody@oilindia.in", False)])
        dialog.show_page("sign in")
        self.assertEqual(dialog.page, "sign in")

        admin = self._window("admin")
        self.assertEqual(list(admin.reset_requests()), ["a.baruah"])
        admin.navigate("accounts")
        row = next(row for row in admin.accounts_page.table.rows
                   if row["username"] == "a.baruah")
        self.assertEqual(row["status"], ("↻ Reset requested", "warn"))
        self.assertEqual(admin.shell_header.bell_badge.text(), "1")
        admin.shell_header.bell_clicked.emit()
        self.assertEqual(admin.pages.currentIndex(), admin._page_index["accounts"])
        self.assertTrue(admin.reset_account_password("a.baruah"))
        self.assertEqual(admin.reset_requests(), {})
        self.assertFalse(admin.shell_header.bell_badge.isVisible())

    # -- pop-ups ---------------------------------------------------------------------------------

    def _menu_is_opaque_white(self, menu) -> None:
        from PyQt6.QtCore import QPoint

        menu.popup(QPoint(100, 100))
        self.app.processEvents()
        image = menu.grab().toImage()
        menu.hide()
        colour = image.pixelColor(image.width() // 2, image.height() - 6)
        self.assertEqual((colour.name(), colour.alpha()), ("#ffffff", 255))

    def test_menus_from_the_dark_title_row_are_white_not_transparent(self) -> None:
        # The title row's "transparent, white text" rule used to reach its own
        # menus, which Windows then drew black with dark items on them.
        import app4

        window = self._window("admin")
        window.show()
        self._menu_is_opaque_white(window.shell_header.menu)
        self._menu_is_opaque_white(window.llm_button.menu_)
        window.close()
        session = self.store.authenticate("admin.person", PASSWORD)
        other = app4.build_window(session, self.store)
        self.addCleanup(other.close)
        other.show()
        self._menu_is_opaque_white(other.shell_header.menu)

    # -- nothing leaks ---------------------------------------------------------------------------

    def test_app4_keeps_its_own_look_after_sentra_ran(self) -> None:
        import app4
        from ui4 import kit

        self._window("reviewer")
        self.assertTrue(kit.HEAD_STACKED)
        session = self.store.authenticate("reviewer.person", PASSWORD)
        window = app4.build_window(session, self.store)
        self.addCleanup(window.close)
        self.assertFalse(kit.HEAD_STACKED)
        self.assertEqual(kit.MONO_FAMILY, "IBM Plex Mono")
        self.assertFalse(hasattr(window, "llm_button"))
        self.assertNotIn("data", window.tab_row.keys)


if __name__ == "__main__":
    unittest.main()
