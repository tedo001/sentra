"""Asset Safety Memory and Work-Hold Recommendation.

Run:  python -m unittest test_asset_memory -v

The memory is built from analysed rows, review decisions and corrective
actions; the recommendation from a row and its asset context. Both are
deterministic, so each rule is pinned by a small, hand-made history.
"""

from __future__ import annotations

import unittest
from datetime import date

from sif.assets import AssetMemory, asset_name, equipment_tags, report_kind
from sif.workhold import CONTINUE, HOLD, LABELS, REVIEW, recommend

LOTO = "Energy isolation / LOTO not applied or verified"
FALL = "Fall protection not used / not anchored"


def row(reference, day, site="Duliajan OCS-4", energy="Electrical energy", failure=LOTO,
        sif=True, risk=95.0, text="The technician started work on the feeder without LOTO.",
        **extra):
    return {"reference": reference, "reported_on": day, "site": site, "raw_text": text,
            "energy_source": energy, "high_energy": energy != "No high-energy source identified",
            "barrier_failure": failure, "barrier_failed": failure != "No barrier failure identified",
            "sif_potential": sif, "risk_score": risk, "p_sif": 0.9 if sif else 0.1,
            "activity": "Equipment maintenance", "iogp_rule": "Energy Isolation", **extra}


class TestReading(unittest.TestCase):
    def test_the_asset_is_the_site_else_the_location_read_from_the_text(self) -> None:
        self.assertEqual(asset_name({"site": " Duliajan  OCS-4 "}), "Duliajan OCS-4")
        self.assertEqual(asset_name({"location": "Moran Gas Compressor Station"}),
                         "Moran Gas Compressor Station")
        self.assertEqual(asset_name({"location": "Location not stated"}), "")

    def test_report_kinds_come_from_the_words(self) -> None:
        self.assertEqual(report_kind("The rigger was injured when the sling parted."), "incident")
        self.assertEqual(report_kind("Minor oil spillage on the canteen floor."), "incident")
        self.assertEqual(report_kind("The load swung past the crew; no one was hurt."),
                         "near miss")
        self.assertEqual(report_kind("Two workers entered the sump without a gas test."),
                         "near miss")
        self.assertEqual(report_kind("Loose plate found at the entrance; no one was working "
                                     "in the area."), "hazard")
        self.assertEqual(report_kind("Unattended open excavation found near the road."),
                         "hazard")

    def test_equipment_tags_leave_the_acronyms_out(self) -> None:
        self.assertEqual(equipment_tags("Pump P-3B at GGS-5 under PTW 4471, H2S and LOTO "
                                        "checked, K-101 tripped, P-3B again"),
                         ["P-3B", "GGS-5", "K-101"])


class TestMemory(unittest.TestCase):
    def test_a_repeated_control_failure_and_a_named_precursor_scenario(self) -> None:
        memory = AssetMemory().build([row("NM-1", "2026-01-04"), row("NM-2", "2026-01-20")])
        kinds = {signal.kind: signal for signal in memory.context("NM-2").signals}
        self.assertIn("recurring hazard", kinds)
        self.assertIn("repeated control failure", kinds)
        self.assertEqual(kinds["repeated control failure"].references, ["NM-1"])
        self.assertEqual(kinds["emerging SIF precursor"].severity, "high")
        self.assertEqual([record.reference for record in memory.context("NM-2").prior],
                         ["NM-1"])
        self.assertEqual([signal.kind for signal in memory.context("NM-1").signals],
                         ["first report"])

    def test_history_outside_the_window_does_not_recur(self) -> None:
        memory = AssetMemory().build([row("NM-1", "2025-06-01"), row("NM-2", "2026-01-20")])
        kinds = [signal.kind for signal in memory.context("NM-2").signals]
        self.assertNotIn("repeated control failure", kinds)

    def test_other_assets_are_not_history(self) -> None:
        memory = AssetMemory().build([row("NM-1", "2026-01-04", site="Rig-12"),
                                      row("NM-2", "2026-01-20")])
        self.assertEqual(memory.context("NM-2").prior, [])
        self.assertEqual(len(memory.assets()), 2)

    def test_a_corrective_action_that_did_not_hold(self) -> None:
        actions = [{"title": "Lock out the booster feeder", "reference": "NM-1",
                    "start": "2026-01-05", "recurrence": "once", "done": {"2026-01-06": "a"}}]
        memory = AssetMemory(today=date(2026, 2, 1)).build(
            [row("NM-1", "2026-01-04"), row("NM-2", "2026-01-20")], actions=actions)
        failed = [signal for signal in memory.context("NM-2").signals
                  if signal.kind == "corrective action did not hold"]
        self.assertEqual(len(failed), 1)
        self.assertIn("Lock out the booster feeder", failed[0].text)
        self.assertEqual(memory.get("Duliajan OCS-4").actions[0].state, "done")

    def test_open_and_overdue_actions_and_confirmed_precursors(self) -> None:
        actions = [{"title": "Retrain the crew", "reference": "NM-1", "start": "2026-01-10"}]
        memory = AssetMemory(today=date(2026, 2, 1)).build(
            [row("NM-1", "2026-01-04"), row("NM-2", "2026-01-20", energy="Gravity",
                                            failure=FALL)],
            decisions={"NM-1": "confirmed"}, actions=actions)
        kinds = {signal.kind: signal for signal in memory.context("NM-2").signals}
        self.assertIn("1 overdue", kinds["open corrective action"].text)
        self.assertIn("NM-1", kinds["confirmed precursor on record"].text)
        summary = memory.get("Duliajan OCS-4").summary()
        self.assertEqual((summary["precursors"], summary["confirmed"], summary["open_actions"]),
                         (2, 1, 1))

    def test_a_rejected_report_is_not_a_precursor(self) -> None:
        memory = AssetMemory().build([row("NM-1", "2026-01-04")], decisions={"NM-1": "rejected"})
        self.assertEqual(memory.get("Duliajan OCS-4").precursors, [])


class TestRecommendation(unittest.TestCase):
    def test_fatal_potential_with_a_failed_control_at_critical_risk_is_a_hold(self) -> None:
        rec = recommend(row("NM-1", "2026-01-04"))
        self.assertEqual(rec.level, HOLD)
        self.assertEqual(rec.label, LABELS[HOLD])
        self.assertTrue(rec.routed)
        self.assertIn(LOTO, rec.reasons[0])
        names = [factor.name for factor in rec.factors]
        for name in ("SIF precursor (engine)", "Control failed or absent", "Critical exposure",
                     "High-energy hazard"):
            self.assertIn(name, names)
        self.assertEqual(rec.score, sum(factor.weight for factor in rec.factors))

    def test_the_asset_history_turns_a_review_into_a_hold(self) -> None:
        rows = [row("NM-1", "2026-01-04", risk=70), row("NM-2", "2026-01-20", risk=70)]
        memory = AssetMemory().build(rows)
        self.assertEqual(recommend(rows[0], memory.context("NM-1")).level, REVIEW)
        rec = recommend(rows[1], memory.context("NM-2"))
        self.assertEqual(rec.level, HOLD)
        self.assertIn("repeated control failure", rec.reasons[0])
        self.assertTrue(any(factor.group == "history" for factor in rec.factors))

    def test_high_energy_with_a_failed_control_is_reviewed(self) -> None:
        rec = recommend(row("NM-1", "2026-01-04", sif=False, risk=30))
        self.assertEqual(rec.level, REVIEW)

    def test_nothing_in_it_continues(self) -> None:
        rec = recommend(row("NM-1", "2026-01-04", energy="No high-energy source identified",
                            failure="No barrier failure identified", sif=False, risk=0,
                            text="Loose plate found; refitted the same morning."))
        self.assertEqual(rec.level, CONTINUE)
        self.assertFalse(rec.routed)

    def test_a_reviewer_decision_stands_beside_the_engine(self) -> None:
        rec = recommend(row("NM-1", "2026-01-04"), decision="rejected")
        self.assertEqual(rec.level, CONTINUE)
        self.assertIn("not SIF", rec.reasons[0])
        low = row("NM-2", "2026-01-04", energy="No high-energy source identified",
                  failure="No barrier failure identified", sif=False, risk=0)
        self.assertEqual(recommend(low, decision="confirmed").level, REVIEW)

    def test_a_stopped_job_is_said_so(self) -> None:
        rec = recommend(row("NM-1", "2026-01-04",
                            text="LOTO was not applied. Work was stopped by the supervisor."))
        self.assertTrue(rec.work_stopped)
        self.assertIn("keep it stopped", rec.summary)
        self.assertNotIn(rec.label, rec.advice)


if __name__ == "__main__":
    unittest.main()


class TestGazetteer(unittest.TestCase):
    def test_sites_are_placed_by_their_locality_and_spread_apart(self) -> None:
        from sif.geo import LOCALITIES, locate, place_sites

        self.assertEqual(locate("Duliajan OCS-4")[0], "duliajan")
        self.assertEqual(locate("NAHARKATIYA Rig-12")[0], "naharkatiya")
        self.assertIsNone(locate("Head office"))
        placed, unplaced = place_sites(["Duliajan OCS-4", "Duliajan OCS-2", "Moran Field",
                                        "Head office"])
        self.assertEqual(unplaced, ["Head office"])
        self.assertEqual(placed["Moran Field"][:2], LOCALITIES["moran"])
        self.assertNotEqual(placed["Duliajan OCS-4"][:2], placed["Duliajan OCS-2"][:2])
        self.assertEqual(place_sites(["Duliajan OCS-2", "Duliajan OCS-4"])[0]["Duliajan OCS-4"],
                         placed["Duliajan OCS-4"])
