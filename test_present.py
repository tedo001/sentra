"""The wording the design's pages use, worked out without a window.

Run:  python -m unittest test_present -v
"""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timedelta

from main import read_csv_records, read_csv_reports
from ui4.present import (age, case_line, describe_action, initials, received, review_status,
                         trigger_counts, weekly_series)

SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples",
                      "near_miss_reports.csv")


class TestPresent(unittest.TestCase):

    def test_waiting_times_read_as_people_say_them(self) -> None:
        now = datetime(2026, 9, 25, 14, 6)
        self.assertEqual(age(now - timedelta(hours=2, minutes=24), now), "2 h 24 m")
        self.assertEqual(age(now - timedelta(days=3, hours=4), now), "3 d 4 h")
        self.assertEqual(age(now - timedelta(seconds=20), now), "just now")
        self.assertEqual(age(None, now), "")

    def test_a_case_is_one_line_barrier_energy_and_where(self) -> None:
        row = {"barrier_failure": "Energy isolation / LOTO not applied or verified; Permit",
               "energy_source": "Electrical energy + Pressure", "site": "GGS-5 Duliajan"}
        self.assertEqual(case_line(row), "Energy isolation / LOTO not applied or verified "
                                         "— electrical energy at GGS-5 Duliajan.")

    def test_the_review_pill_follows_the_decision(self) -> None:
        self.assertEqual(review_status({"needs_review": True}, None), ("Awaiting review", "info"))
        self.assertEqual(review_status({}, None), ("Closed · not queued", "grey"))
        confirmed = review_status({}, {"decision": "confirmed",
                                       "reviewer": "Anupam Baruah (a.baruah)"})
        self.assertEqual(confirmed, ("✓ Confirmed SIF · AB", "dark"))
        self.assertEqual(review_status({}, {"decision": "unclear"}), ("? Needs info", "warn"))
        self.assertEqual(initials("D. Manikandan"), "DM")

    def test_open_cases_are_counted_by_trigger(self) -> None:
        queue = [{"trigger": "Critical risk"}, {"trigger": "Critical risk"},
                 {"trigger": "Thin evidence"}, {"trigger": "Critical risk", "decided": True}]
        self.assertEqual(trigger_counts(queue), [("Critical risk", 2), ("Thin evidence", 1)])

    def test_the_timeline_speaks_of_you(self) -> None:
        # Shown in the workstation's own zone, so the stored clock time reads back.
        from datetime import datetime
        from unittest import mock

        import ui4.present as present

        local = datetime.now().astimezone().tzinfo
        patcher = mock.patch.object(present, "zone", lambda: (local, "LOCAL"))
        patcher.start()
        self.addCleanup(patcher.stop)
        entry = {"action": "review decision", "user": "a.baruah", "at": "2026-09-25T13:40:07",
                 "detail": {"decision": "confirmed", "reference": "NM-26-0409"}}
        self.assertEqual(describe_action(entry, "a.baruah"),
                         ("13:40", "You confirmed SIF on NM-26-0409", "Decision"))

    def test_the_trend_ends_at_the_latest_report(self) -> None:
        rows = [{"reported_on": "2026-01-05", "sif_potential": True, "risk_score": 96},
                {"reported_on": "2026-01-06", "sif_potential": True, "risk_score": 40},
                {"reported_on": "2025-12-01", "sif_potential": False, "risk_score": 10}]
        sif, critical, labels = weekly_series(rows)
        self.assertEqual(len(sif), 13)
        self.assertEqual(sif[-1], 2)
        self.assertEqual(critical[-1], 1)
        self.assertTrue(labels[2].startswith("w/c 5 Jan"))

    def test_a_date_only_export_shows_its_date(self) -> None:
        self.assertEqual(received({"reported_on": "2026-01-04"}), "4 Jan 2026")

    def test_the_csv_keeps_date_site_and_reporter(self) -> None:
        narratives, references, metadata = read_csv_records(SAMPLE)
        self.assertEqual((narratives, references), read_csv_reports(SAMPLE))
        self.assertEqual(len(metadata), len(narratives))
        self.assertEqual(metadata[0], {"reported_on": "2026-01-04", "site": "Duliajan OCS-4",
                                       "reported_by": "Shift Supervisor"})


if __name__ == "__main__":
    unittest.main()


class TestDatesAndTimes(unittest.TestCase):
    def test_one_format_and_the_zone_named(self) -> None:
        from datetime import date, datetime, timedelta, timezone
        from unittest import mock

        import ui4.present as present

        ist = timezone(timedelta(hours=5, minutes=30))
        with mock.patch.object(present, "zone", lambda: (ist, "IST")), \
                mock.patch.object(present, "date_format", lambda: "%d %b %Y"):
            stored = datetime(2026, 9, 25, 8, 38, tzinfo=timezone.utc)
            self.assertEqual(present.fmt_datetime(stored), "25 Sep 2026, 14:08 IST")
            self.assertEqual(present.fmt_time(stored), "14:08 IST")
            # A report's own date is a calendar date and is never shifted.
            self.assertEqual(present.fmt_date("2026-01-07"), "7 Jan 2026")
            self.assertEqual(present.received({"reported_on": "2026-01-07"}), "7 Jan 2026")
            self.assertEqual(present.fmt_week(date(2025, 12, 29)), "29 Dec 2025 – 4 Jan 2026")
        with mock.patch.object(present, "date_format", lambda: "%Y-%m-%d"):
            self.assertEqual(present.fmt_date("2026-01-07"), "2026-01-07")
