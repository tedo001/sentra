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

    def test_the_hse_workspace_keeps_its_seven_tabs_in_the_revamp_pages(self) -> None:
        from ui5.actions import SentraActions
        from ui5.dashboard import SentraDashboard
        from ui5.review import SentraReview

        window = self._window("reviewer")
        self.assertEqual(window.tab_row.keys, ["home", "ingest", "dashboard", "review",
                                               "actions", "hotspots", "profile"])
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
