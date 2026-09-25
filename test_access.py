"""Sign-in, roles, attribution and the tamper-evident trail.

Run:  QT_QPA_PLATFORM=offscreen SIF_ENCODER=hashing python -m unittest test_access -v

The questions these tests hold the console to are the ones an auditor asks:
who got in, who was refused, who analysed this report, who decided it, could
they have done it under someone else's name, and has anyone altered the record
since.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from typing import List

from sif import audit as audit_module
from sif.accounts import (ANALYSE, CLEAR, DECIDE, MANAGE_USERS, PERMISSIONS, ROLES,
                          TRAIN, AccountStore, AuthError, Session)
from sif.audit import AuditLog

try:
    import PyQt6  # noqa: F401
    HAS_PYQT = True
except ImportError:  # pragma: no cover
    HAS_PYQT = False

#: Far below the production count: these tests hash hundreds of passwords.
FAST = 1_000


def _folder(test: unittest.TestCase) -> str:
    folder = tempfile.mkdtemp(prefix="sif-access-")
    test.addCleanup(shutil.rmtree, folder, True)
    return folder


class TestAccounts(unittest.TestCase):
    """The accounts file: what is stored, and what is refused."""

    def setUp(self) -> None:
        self.path = os.path.join(_folder(self), "users.json")
        self.store = AccountStore(self.path, iterations=FAST)
        self.store.create("d.manikandan", "D. Manikandan", "admin", "correct horse")

    def test_the_password_itself_is_never_written(self) -> None:
        with open(self.path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn("correct horse", text)
        record = json.loads(text)["accounts"][0]
        self.assertEqual(len(bytes.fromhex(record["salt"])), 16)
        self.assertEqual(len(record["password_hash"]), 64)      # SHA-256 hex

    def test_two_accounts_with_one_password_store_different_digests(self) -> None:
        self.store.create("r.sharma", "R. Sharma", "analyst", "correct horse")
        first, second = self.store.get("d.manikandan"), self.store.get("r.sharma")
        self.assertNotEqual(first.password_hash, second.password_hash, "salt missing")

    def test_a_right_password_signs_in_and_names_the_person(self) -> None:
        session = self.store.authenticate("D.Manikandan", "correct horse")
        self.assertEqual(session.username, "d.manikandan")
        self.assertEqual(session.signature, "D. Manikandan (d.manikandan)")
        self.assertTrue(session.authenticated)
        self.assertTrue(self.store.get("d.manikandan").last_login)

    def test_a_wrong_password_and_an_unknown_user_read_the_same(self) -> None:
        """Different messages would tell a stranger which usernames exist."""
        with self.assertRaises(AuthError) as wrong:
            self.store.authenticate("d.manikandan", "not it at all")
        with self.assertRaises(AuthError) as unknown:
            self.store.authenticate("nobody.here", "not it at all")
        self.assertEqual(str(wrong.exception), str(unknown.exception))
        self.assertEqual(wrong.exception.reason, "wrong password")
        self.assertEqual(unknown.exception.reason, "unknown user")

    def test_five_wrong_passwords_lock_the_account(self) -> None:
        for _ in range(4):
            with self.assertRaises(AuthError):
                self.store.authenticate("d.manikandan", "guess")
        with self.assertRaises(AuthError) as fifth:
            self.store.authenticate("d.manikandan", "guess")
        self.assertEqual(fifth.exception.reason, "locked out")
        with self.assertRaises(AuthError) as locked:
            self.store.authenticate("d.manikandan", "correct horse")
        self.assertEqual(locked.exception.reason, "locked",
                         "the right password must not work during a lockout")

    def test_a_lockout_ends_by_itself(self) -> None:
        account = self.store.get("d.manikandan")
        account.locked_until = (datetime.now() - timedelta(minutes=1)).isoformat()
        account.failed_attempts = 5
        self.assertTrue(self.store.authenticate("d.manikandan", "correct horse"))
        self.assertEqual(self.store.get("d.manikandan").failed_attempts, 0)

    def test_a_disabled_account_cannot_sign_in(self) -> None:
        self.store.create("x.admin", "X Admin", "admin", "another pass")
        self.store.set_active("d.manikandan", False)
        with self.assertRaises(AuthError) as refused:
            self.store.authenticate("d.manikandan", "correct horse")
        self.assertEqual(refused.exception.reason, "disabled")

    def test_what_is_refused_at_creation(self) -> None:
        cases = [("ab", "Name", "analyst", "long enough", "bad username"),
                 ("Has Space", "Name", "analyst", "long enough", "bad username"),
                 ("good.name", "", "analyst", "long enough", "no name"),
                 ("good.name", "Name", "superuser", "long enough", "bad role"),
                 ("good.name", "Name", "analyst", "short", "short password"),
                 ("good.name", "Name", "analyst", "good.name", "password is username"),
                 ("d.manikandan", "Name", "analyst", "long enough", "duplicate")]
        for username, name, role, password, reason in cases:
            with self.subTest(reason=reason):
                with self.assertRaises(AuthError) as refused:
                    self.store.create(username, name, role, password)
                self.assertEqual(refused.exception.reason, reason)

    def test_a_one_time_password_works_once_then_must_be_replaced(self) -> None:
        self.store.create("r.sharma", "R. Sharma", "analyst", "first pass",
                          must_change=True)
        temporary = self.store.reset_password("r.sharma", by="d.manikandan")
        self.assertTrue(self.store.get("r.sharma").must_change)
        self.store.authenticate("r.sharma", temporary)
        self.store.change_password("r.sharma", temporary, "my own choice")
        self.assertFalse(self.store.get("r.sharma").must_change)
        with self.assertRaises(AuthError):
            self.store.authenticate("r.sharma", temporary)
        self.assertTrue(self.store.authenticate("r.sharma", "my own choice"))

    def test_the_last_administrator_cannot_be_removed(self) -> None:
        with self.assertRaises(AuthError) as demote:
            self.store.set_role("d.manikandan", "analyst")
        self.assertEqual(demote.exception.reason, "last admin")
        with self.assertRaises(AuthError):
            self.store.set_active("d.manikandan", False)
        self.store.create("x.admin", "X Admin", "admin", "another pass")
        self.store.set_role("d.manikandan", "reviewer")            # now allowed

    def test_an_unreadable_file_is_an_error_not_an_empty_store(self) -> None:
        """Reading it as empty would offer to create an administrator over it."""
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        with self.assertRaises(AuthError):
            AccountStore(self.path, iterations=FAST)

    def test_saving_leaves_no_half_written_file(self) -> None:
        self.store.create("r.sharma", "R. Sharma", "analyst", "long enough")
        self.assertFalse(os.path.exists(self.path + ".tmp"))
        reloaded = AccountStore(self.path, iterations=FAST)
        self.assertEqual([a.username for a in reloaded.accounts()],
                         ["d.manikandan", "r.sharma"])

    def test_each_role_can_do_everything_the_one_before_can(self) -> None:
        for lower, higher in zip(ROLES, ROLES[1:]):
            self.assertLess(PERMISSIONS[lower], PERMISSIONS[higher], (lower, higher))
        viewer = Session("v", "V", "viewer", "now")
        self.assertFalse(viewer.can(ANALYSE))
        self.assertTrue(Session("r", "R", "reviewer", "now").can(DECIDE))
        self.assertFalse(Session("r", "R", "reviewer", "now").can(CLEAR))
        self.assertTrue(Session("a", "A", "admin", "now").can(MANAGE_USERS))


class TestTamperEvidentTrail(unittest.TestCase):
    """The audit chain: every edit, insertion and deletion is caught."""

    def setUp(self) -> None:
        self.path = os.path.join(_folder(self), "audit.jsonl")
        self.log = AuditLog(self.path, version="test")
        self.log.sign_in("d.manikandan", "admin")
        for index in range(6):
            self.log.functionality("reports analysed", count=index + 1)

    def _lines(self) -> List[str]:
        with open(self.path, encoding="utf-8") as handle:
            return handle.read().splitlines()

    def _write(self, lines: List[str]) -> None:
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    def test_an_untouched_trail_verifies(self) -> None:
        report = self.log.verify()
        self.assertTrue(report.intact, report.summary)
        self.assertEqual((report.entries, report.chained), (6, 6))
        self.assertEqual(report.head, self.log.head)

    def test_every_entry_names_the_signed_in_account(self) -> None:
        entry = self.log.entries(limit=1)[0]
        self.assertEqual((entry.user, entry.role), ("d.manikandan", "admin"))
        self.log.sign_out()
        self.assertEqual(self.log.system("idle").user, "")

    def test_an_edited_entry_is_caught_where_it_was_edited(self) -> None:
        lines = self._lines()
        tampered = json.loads(lines[2])
        tampered["user"] = "someone.else"
        lines[2] = json.dumps(tampered)
        self._write(lines)
        report = AuditLog(self.path).verify()
        self.assertFalse(report.intact)
        self.assertEqual(report.broken_at, 3)

    def test_a_deleted_entry_is_caught(self) -> None:
        lines = self._lines()
        del lines[3]
        self._write(lines)
        report = AuditLog(self.path).verify()
        self.assertFalse(report.intact)
        self.assertEqual(report.broken_at, 4)

    def test_an_inserted_entry_is_caught(self) -> None:
        lines = self._lines()
        forged = {"at": "2026-01-01T00:00:00", "category": "functionality",
                  "action": "review decision", "user": "d.manikandan"}
        lines.insert(2, json.dumps(forged))
        self._write(lines)
        self.assertFalse(AuditLog(self.path).verify().intact)

    def test_entries_from_before_chaining_are_accepted_as_history(self) -> None:
        legacy = json.dumps({"at": "2025-01-01T00:00:00", "category": "system",
                             "action": "console started"})
        self._write([legacy, legacy] + self._lines())
        report = AuditLog(self.path).verify()
        self.assertTrue(report.intact, report.summary)
        self.assertEqual((report.entries, report.chained), (8, 6))

    def test_two_holders_of_the_file_keep_one_chain(self) -> None:
        """The sign-in page and the window each hold a log on the same file."""
        other = AuditLog(self.path)
        other.functionality("signed in")
        self.log.functionality("review decision")
        other.functionality("signed out")
        self.assertTrue(AuditLog(self.path).verify().intact)


@unittest.skipUnless(HAS_PYQT, "PyQt6 is not installed")
class TestSignInAndAttribution(unittest.TestCase):
    """The dialog, the window's roles, and who is named on each record."""

    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        import main2

        folder = _folder(self)
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

    def _window(self, role: str, username: str = ""):
        import main2
        from sif.review import DecisionLog

        username = username or f"{role}.person"
        if self.store.get(username) is None:
            self.store.create(username, f"{role.title()} Person", role, "long enough")
        session = self.store.authenticate(username, "long enough")
        window = main2.MainWindow(session, self.store)
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

    # -- the dialog --------------------------------------------------------

    def test_first_run_creates_the_administrator_and_signs_them_in(self) -> None:
        from ui2.login import LoginDialog

        dialog = LoginDialog(self.store, AuditLog(self.audit_path))
        self.assertEqual(dialog.page, "setup", "no accounts: there is no default password")
        dialog.setup_name.setText("D. Manikandan")
        dialog.setup_user.setText("d.manikandan")
        dialog.setup_password.setText("correct horse")
        dialog.setup_confirm.setText("correct horse")
        dialog.create_administrator()

        self.assertIsNotNone(dialog.session)
        self.assertEqual(dialog.session.role, "admin")
        signed = [e for e in self._actions() if e["action"] == "signed in"]
        self.assertEqual(signed[-1]["user"], "d.manikandan")
        self.assertIn("administrator created", [e["action"] for e in self._actions()])

    def test_a_refused_sign_in_is_recorded_with_the_name_that_was_tried(self) -> None:
        from ui2.login import LoginDialog

        self.store.create("d.manikandan", "D. Manikandan", "admin", "correct horse")
        dialog = LoginDialog(self.store, AuditLog(self.audit_path))
        self.assertEqual(dialog.page, "sign in")
        dialog.username.setText("d.manikandan")
        dialog.password.setText("wrong guess")
        dialog.sign_in()

        self.assertIsNone(dialog.session)
        self.assertFalse(dialog.error.isHidden())
        self.assertEqual(dialog.password.text(), "", "a refused password is cleared")
        refused = [e for e in self._actions() if e["action"] == "sign-in refused"]
        self.assertEqual(refused[-1]["detail"]["attempted"], "d.manikandan")
        self.assertEqual(refused[-1]["user"], "", "nobody is signed in yet")

    def test_a_one_time_password_leads_to_choosing_a_real_one(self) -> None:
        from ui2.login import LoginDialog

        self.store.create("d.manikandan", "D. Manikandan", "admin", "correct horse")
        self.store.create("r.sharma", "R. Sharma", "analyst", "temporary1",
                          must_change=True)
        dialog = LoginDialog(self.store, AuditLog(self.audit_path))
        dialog.username.setText("r.sharma")
        dialog.password.setText("temporary1")
        dialog.sign_in()
        self.assertEqual(dialog.page, "change")
        self.assertIsNone(dialog.session, "not signed in until the password is chosen")
        dialog.new_password.setText("my own choice")
        dialog.new_confirm.setText("my own choice")
        dialog.change_password()
        self.assertEqual(dialog.session.username, "r.sharma")
        self.assertFalse(self.store.get("r.sharma").must_change)

    # -- attribution -------------------------------------------------------

    def test_every_analysed_report_names_who_analysed_it(self) -> None:
        window = self._window("analyst", "r.sharma")
        self._analyse(window)
        self.assertTrue(window.rows)
        for row in window.rows:
            self.assertEqual(row["analysed_by"], "Analyst Person (r.sharma)")
            self.assertTrue(row["analysed_at"])
        batch = [e for e in self._actions() if e["action"] == "reports analysed"][-1]
        self.assertEqual(batch["user"], "r.sharma")
        self.assertIn(window.rows[0]["reference"], batch["detail"]["references"])

    def test_a_decision_is_recorded_under_the_signed_in_person_only(self) -> None:
        window = self._window("reviewer", "d.expert")
        self._analyse(window)
        self.assertTrue(window.review_view.reviewer.isReadOnly())
        window.review_view.reviewer.setText("Someone Else")      # cannot be read
        window.navigate("review")
        window.select_review_row(0)
        window.record_decision("confirmed", "")
        self.assertEqual(window.decisions.entries[-1].reviewer,
                         "Reviewer Person (d.expert)")

    # -- roles ---------------------------------------------------------------

    def test_a_viewer_is_refused_and_the_refusal_is_recorded(self) -> None:
        window = self._window("viewer")
        window.load_seed_data()
        self.assertIsNone(window.worker, "a viewer must not start an analysis")
        refused = [e for e in self._actions() if e["action"] == "permission refused"]
        self.assertEqual(refused[-1]["detail"]["attempted"], "load_seed_data")
        self.assertEqual(refused[-1]["user"], "viewer.person")

    def test_an_analyst_can_analyse_but_not_decide_or_clear(self) -> None:
        window = self._window("analyst")
        self._analyse(window)
        before = len(window.decisions.entries)
        window.navigate("review")
        window.select_review_row(0)
        window.record_decision("confirmed", "")
        self.assertEqual(len(window.decisions.entries), before)
        self.assertFalse(window.review_view.can_decide)
        rows = len(window.rows)
        window.confirm_clear_queue()
        self.assertEqual(len(window.rows), rows, "an analyst cannot clear the corpus")
        self.assertFalse(window.engines_view.train_button.isEnabled())

    def test_a_guarded_action_still_accepts_a_signal_argument(self) -> None:
        """clicked(bool) hands a slot an extra argument; the guard must drop it."""
        window = self._window("admin")
        window.load_seed_data(False)                 # as a clicked() signal would
        self.assertIsNotNone(window.worker)
        window.worker.wait(120_000)

    # -- the activity page -------------------------------------------------

    def test_the_activity_page_tallies_each_person(self) -> None:
        window = self._window("admin", "d.manikandan")
        self._analyse(window)
        window.navigate("activity")
        people = {row["username"]: row for row in window.activity_view._people}
        self.assertEqual(people["d.manikandan"]["analysed"], len(window.rows))
        self.assertIn("Chain intact", window.activity_view.chain_label.text())
        self.assertFalse(window.activity_view.add_button.isHidden())

    def test_only_an_administrator_manages_accounts(self) -> None:
        admin = self._window("admin", "d.manikandan")
        password = admin.create_account("r.sharma", "R. Sharma", "analyst")
        self.assertEqual(len(password), 12)
        self.assertTrue(self.store.get("r.sharma").must_change)
        self.assertIn("account created", [e["action"] for e in self._actions()])

        analyst = self._window("analyst", "someone")
        self.assertTrue(analyst.activity_view.add_button.isHidden())
        self.assertEqual(analyst.create_account("x.y", "X Y", "admin"), None)
        self.assertIsNone(self.store.get("x.y"))

    def test_signing_out_is_recorded_and_hands_back_to_sign_in(self) -> None:
        window = self._window("analyst", "r.sharma")
        window.sign_out()
        self.assertTrue(window.sign_out_requested)
        self.assertEqual(self._actions()[-1]["action"], "console closed")
        self.assertIn("signed out", [e["action"] for e in self._actions()])

    def test_the_entry_point_will_not_open_without_a_sign_in(self) -> None:
        """run_signed_in returns without a window when the sign-in is abandoned."""
        import main2
        from ui2 import login

        class Abandoned:
            DialogCode = login.LoginDialog.DialogCode

            def __init__(self, *args, **kwargs):
                self.session = None

            def exec(self):
                return self.DialogCode.Rejected

        built = []
        original = login.LoginDialog
        login.LoginDialog = Abandoned
        self.addCleanup(setattr, login, "LoginDialog", original)
        original_store = main2.AccountStore
        main2.AccountStore = lambda: self.store
        self.addCleanup(setattr, main2, "AccountStore", original_store)
        code = main2.run_signed_in(self.app, lambda *a: built.append(a))
        self.assertEqual((code, built), (0, []))


if __name__ == "__main__":
    unittest.main(verbosity=2)
