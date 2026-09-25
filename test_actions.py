"""Compliance action items: recurrence, per-date completion, storage.

Run:  python -m unittest test_actions -v
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from datetime import date, timedelta

from sif.actions import OVERDUE_WINDOW_DAYS, SAMPLE_ACTIONS, ActionStore


class TestActionStore(unittest.TestCase):

    def setUp(self) -> None:
        folder = tempfile.mkdtemp(prefix="sif-actions-")
        self.addCleanup(shutil.rmtree, folder, True)
        self.path = os.path.join(folder, "actions.json")
        self.store = ActionStore(self.path)

    def _days(self, action, start, end):
        return [item.day for item in self.store.occurrences(start, end)
                if item.action.id == action.id]

    # -- recurrence ------------------------------------------------------------

    def test_a_one_off_action_occurs_once(self) -> None:
        action = self.store.add("Confined space rescue drill", date(2026, 3, 18))
        self.assertEqual(self._days(action, date(2026, 3, 1), date(2026, 3, 31)),
                         [date(2026, 3, 18)])
        self.assertFalse(action.recurring)

    def test_weekday_actions_skip_the_weekend(self) -> None:
        action = self.store.add("Gas test before hot work", date(2026, 3, 2), "weekdays")
        days = self._days(action, date(2026, 3, 2), date(2026, 3, 15))
        self.assertEqual(len(days), 10)
        self.assertTrue(all(day.weekday() < 5 for day in days))

    def test_weekly_actions_keep_their_weekday(self) -> None:
        action = self.store.add("LOTO audit", date(2026, 3, 3), "weekly")     # a Tuesday
        days = self._days(action, date(2026, 3, 1), date(2026, 3, 31))
        self.assertEqual(days, [date(2026, 3, 3), date(2026, 3, 10), date(2026, 3, 17),
                                date(2026, 3, 24), date(2026, 3, 31)])

    def test_a_monthly_action_on_the_31st_lands_on_a_short_month_s_last_day(self) -> None:
        action = self.store.add("Renew permits", date(2026, 1, 31), "monthly")
        days = self._days(action, date(2026, 1, 1), date(2026, 4, 30))
        self.assertEqual(days, [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31),
                                date(2026, 4, 30)])

    def test_nothing_occurs_before_the_start_or_after_the_end(self) -> None:
        action = self.store.add("Daily walk", date(2026, 3, 10), "daily", until=date(2026, 3, 12))
        self.assertEqual(self._days(action, date(2026, 3, 1), date(2026, 3, 31)),
                         [date(2026, 3, 10), date(2026, 3, 11), date(2026, 3, 12)])

    def test_what_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.store.add("   ", date(2026, 3, 1))
        with self.assertRaises(ValueError):
            self.store.add("x", date(2026, 3, 1), "hourly")
        with self.assertRaises(ValueError):
            self.store.add("x", date(2026, 3, 10), "daily", until=date(2026, 3, 1))
        self.assertEqual(self.store.actions, [])

    # -- done, open and overdue ---------------------------------------------------

    def test_done_is_recorded_per_date_with_who_closed_it(self) -> None:
        action = self.store.add("Gas test", date(2026, 3, 2), "daily")
        self.assertTrue(self.store.set_done(action.id, date(2026, 3, 3), "a.baruah"))
        self.assertTrue(action.is_done(date(2026, 3, 3)))
        self.assertFalse(action.is_done(date(2026, 3, 4)), "one date says nothing of the next")
        self.assertTrue(action.done["2026-03-03"].startswith("a.baruah at "))
        self.assertTrue(self.store.set_done(action.id, date(2026, 3, 3), "a.baruah", False))
        self.assertFalse(action.is_done(date(2026, 3, 3)))

    def test_a_date_the_action_does_not_fall_on_cannot_be_closed(self) -> None:
        action = self.store.add("LOTO audit", date(2026, 3, 3), "weekly")
        self.assertFalse(self.store.set_done(action.id, date(2026, 3, 4), "a.baruah"))
        self.assertFalse(self.store.set_done("no-such-id", date(2026, 3, 3), "a.baruah"))

    def test_overdue_is_an_open_occurrence_in_the_recent_past(self) -> None:
        today = date(2026, 3, 20)
        action = self.store.add("Gas test", date(2026, 1, 1), "daily")
        self.store.set_done(action.id, date(2026, 3, 19), "a.baruah")
        overdue = self.store.overdue(today)
        self.assertEqual(len(overdue), OVERDUE_WINDOW_DAYS - 1)
        days = {item.day for item in overdue}
        self.assertNotIn(date(2026, 3, 19), days, "done is not overdue")
        self.assertNotIn(today, days, "today is due, not overdue")
        self.assertNotIn(today - timedelta(days=OVERDUE_WINDOW_DAYS + 1), days)

    # -- storage ---------------------------------------------------------------------

    def test_the_store_survives_a_restart(self) -> None:
        action = self.store.add("LOTO audit", date(2026, 3, 3), "weekly", owner="a.baruah",
                                reference="NM-2601", category="Corrective action")
        self.store.set_done(action.id, date(2026, 3, 10), "a.baruah")
        again = ActionStore(self.path)
        loaded = again.get(action.id)
        self.assertEqual((loaded.title, loaded.recurrence, loaded.owner, loaded.reference),
                         ("LOTO audit", "weekly", "a.baruah", "NM-2601"))
        self.assertTrue(loaded.is_done(date(2026, 3, 10)))
        self.assertEqual([a.id for a in again.for_reference("NM-2601")], [action.id])

    def test_a_damaged_file_opens_empty_rather_than_failing(self) -> None:
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        self.assertEqual(ActionStore(self.path).actions, [])

    def test_removing_an_action_removes_every_date(self) -> None:
        action = self.store.add("Gas test", date(2026, 3, 2), "daily")
        self.store.remove(action.id)
        self.assertEqual(self.store.occurrences(date(2026, 3, 1), date(2026, 3, 31)), [])
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["actions"], [])

    def test_the_example_schedule_loads_on_request_only(self) -> None:
        self.assertEqual(self.store.actions, [], "nothing is invented unasked")
        count = self.store.add_samples(date(2026, 3, 15), created_by="a.baruah")
        self.assertEqual(count, len(SAMPLE_ACTIONS))
        self.assertTrue(all(action.start.startswith("2026-03") for action in self.store.actions))


if __name__ == "__main__":
    unittest.main()
