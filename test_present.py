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


class TestTrendUpToNow(unittest.TestCase):
    """The dashboard's risk trend: today, week, month, year, all - ending now."""

    NOW = datetime(2026, 9, 27, 14, 0)

    def setUp(self) -> None:
        from ui4 import present

        # Times read as written, whatever zone this machine and Settings are in.
        original = present.in_zone
        present.in_zone = lambda when: when.replace(tzinfo=None)
        self.addCleanup(setattr, present, "in_zone", original)
        self.rows = [
            {"reported_on": "2026-09-27T09:15:00", "sif_potential": True, "risk_score": 90,
             "iogp_rule": "Hot Work", "energy_source": "Fire / Explosion",
             "barrier_failure": "Fire prevention controls not in place; Mandatory PPE not worn"},
            {"reported_on": "2026-09-27", "sif_potential": False, "risk_score": 20,
             "iogp_rule": "Driving"},
            {"reported_on": "2026-09-21", "sif_potential": True, "risk_score": 70,
             "iogp_rule": "Hot Work"},
            {"reported_on": "2025-12-02", "sif_potential": True, "risk_score": 88,
             "iogp_rule": "Driving", "energy_source": "Vehicle / Traffic motion"},
            {"reported_on": "", "analysed_at": ""},
        ]

    def test_today_is_by_the_hour_and_a_date_alone_is_counted_apart(self) -> None:
        from ui4.present import trend_table

        table = trend_table(self.rows, "today", self.NOW)
        self.assertEqual((table["unit"], len(table["buckets"])), ("hour", 24))
        hours = [bucket["label"] for bucket in table["buckets"] if bucket["reports"]]
        self.assertEqual(hours, ["09:00"])
        self.assertEqual(table["untimed"], 1)
        self.assertEqual(table["reports"], 2)

    def test_week_and_month_are_day_by_day_ending_today(self) -> None:
        from ui4.present import trend_table

        week = trend_table(self.rows, "week", self.NOW)
        self.assertEqual(len(week["buckets"]), 7)
        self.assertEqual(week["buckets"][-1]["start"], date(2026, 9, 27))
        self.assertEqual(week["buckets"][0]["label"], "Mon 21 Sep")
        self.assertEqual([bucket["sif"] for bucket in week["buckets"]], [1, 0, 0, 0, 0, 0, 1])
        month = trend_table(self.rows, "month", self.NOW)
        self.assertEqual(len(month["buckets"]), 30)
        self.assertEqual(month["reports"], 3)

    def test_the_year_is_month_by_month_with_critical_counted(self) -> None:
        from ui4.present import trend_table

        year = trend_table(self.rows, "year", self.NOW)
        self.assertEqual(len(year["buckets"]), 12)
        self.assertEqual(year["buckets"][0]["start"], date(2025, 10, 1))
        self.assertEqual(year["buckets"][0]["label"], "Oct 25")
        december = next(bucket for bucket in year["buckets"] if bucket["start"].month == 12)
        self.assertEqual((december["sif"], december["critical"], december["reports"]), (1, 1, 1))
        self.assertEqual(year["buckets"][-1]["critical"], 1)

    def test_all_picks_a_readable_unit(self) -> None:
        from ui4.present import trend_table

        self.assertEqual(trend_table(self.rows, "all", self.NOW)["unit"], "month")
        recent = [row for row in self.rows if str(row.get("reported_on")).startswith("2026-09")]
        self.assertEqual(trend_table(recent, "all", self.NOW)["unit"], "day")
        self.assertEqual(trend_table([], "all", self.NOW)["buckets"], [])

    def test_the_spider_chart_counts_a_report_on_every_axis_it_names(self) -> None:
        from ui4.present import risk_profile, trend_rows

        this_month = trend_rows(self.rows, "month", self.NOW)
        self.assertEqual(len(this_month), 3)
        rules = {short: (sif, critical, total)
                 for _name, short, sif, critical, total in risk_profile(this_month, "rule")}
        self.assertEqual(rules["Hot work"], (2, 1, 2))
        self.assertEqual(rules["Driving"], (0, 0, 1))
        barriers = {short: total for _name, short, _s, _c, total
                    in risk_profile(self.rows, "barrier")}
        self.assertEqual((barriers["Fire prevention"], barriers["PPE"]), (1, 1))
        energy = {short: total for _name, short, _s, _c, total in risk_profile(self.rows, "energy")}
        self.assertEqual((energy["Fire"], energy["Traffic"]), (1, 1))
