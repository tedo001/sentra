"""Work-Hold Recommendation: Continue, HSE Review Required, or Work-Hold Recommended.

An explainable recommendation for one report, from six things the console
already knows about it:

1. **Hazards** - the high-energy sources in the report;
2. **SIF-precursor information** - the engine's fatal-potential verdict, its
   risk score, and whether the learned model or the local LLM agrees;
3. **Failed or absent controls** - the barriers found missing;
4. **Exposure severity** - the risk score's band, and whether people were at
   work with the hazard present (from the report's wording);
5. **Activity context** - work the IOGP Life-Saving Rules single out:
   isolation, confined space, work at height, lifting, hot work, excavation,
   live electrical work, well operations;
6. **Asset history** - the Asset Safety Memory's signals: a control that has
   failed here before, a corrective action that did not hold, an emerging
   SIF-precursor pattern.

Every factor that contributed is listed with its evidence and its weight, so
the recommendation can be read, checked and argued with. The rules are fixed
and simple enough to state in one paragraph:

* **Work-Hold Recommended** when the report has fatal potential *and* a
  control has failed or is absent *and* the exposure is critical (risk 85 or
  more), or the asset's history shows the same control failing again, a
  corrective action that did not hold, or an emerging precursor pattern - or
  when the weighted evidence reaches the hold threshold.
* **HSE Review Required** when the report has fatal potential, a high risk
  score, a high-energy source with a failed control, a high-severity history
  signal, or the evidence reaches the review threshold.
* **Continue** otherwise.

A recommendation is advice to a person, never an order: a hold or a review
is routed to an HSE expert, and a reviewer's decision is shown beside it (a
reviewer who judged the report not SIF brings it back to Continue, with that
decision recorded as the reason).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .assets import AssetContext, report_kind

__all__ = ["CONTINUE", "REVIEW", "HOLD", "LEVELS", "LABELS", "Factor", "Recommendation",
           "recommend", "HOLD_SCORE", "REVIEW_SCORE"]

CONTINUE, REVIEW, HOLD = "continue", "review", "hold"
LEVELS = (CONTINUE, REVIEW, HOLD)
LABELS = {CONTINUE: "Continue", REVIEW: "HSE Review Required", HOLD: "Work-Hold Recommended"}
TONES = {CONTINUE: "ok", REVIEW: "warn", HOLD: "fail"}

#: Weighted evidence at or above which the level is raised regardless of the rules.
HOLD_SCORE = 12
REVIEW_SCORE = 4
CRITICAL = 85.0
HIGH = 50.0

#: Work the IOGP Life-Saving Rules single out, as the engine names it.
HIGH_RISK_WORK = re.compile(
    r"energy isolation|confined space|working at height|work at height|lifting|hot work|"
    r"welding|excavation|ground disturbance|live|electrical|well control|drilling|tripping|"
    r"pressure|line of fire|bypassing", re.I)
WORK_STOPPED = re.compile(
    r"\b(?:work|job|task|operation|lift|entry)s? (?:was|were|has been|had been) "
    r"(?:stopped|halted|suspended)|stopped the (?:job|work|task|lift)|"
    r"\b(?:work|job) stopped\b", re.I)


@dataclass
class Factor:
    """One reason, with the evidence behind it and how much it weighed."""

    name: str
    evidence: str
    weight: int
    group: str                   # hazard / precursor / control / exposure / activity / history

    def to_dict(self) -> Dict[str, object]:
        return {"name": self.name, "evidence": self.evidence, "weight": self.weight,
                "group": self.group}


@dataclass
class Recommendation:
    level: str
    score: int
    factors: List[Factor] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)     # which rule decided the level
    work_stopped: bool = False
    decision: str = ""

    @property
    def label(self) -> str:
        return LABELS[self.level]

    @property
    def tone(self) -> str:
        return TONES[self.level]

    @property
    def routed(self) -> bool:
        """Goes to an HSE expert: every hold and every review."""
        return self.level != CONTINUE

    @property
    def summary(self) -> str:
        lead = self.reasons[0] if self.reasons else "no factor reached a threshold"
        if self.level == HOLD:
            action = ("The report says the work was stopped: keep it stopped until the "
                      "controls are restored and an HSE expert releases it."
                      if self.work_stopped else
                      "Stop or keep the work on hold until the failed controls are restored "
                      "and an HSE expert releases it.")
        elif self.level == REVIEW:
            action = "An HSE expert should review the report before the work goes on."
        else:
            action = "No hold indicated; the report stays on record for the asset's memory."
        return f"{self.label}: {lead}. {action}"

    @property
    def advice(self) -> str:
        """The summary without the level's name, for beside a label that shows it."""
        text = self.summary.split(": ", 1)[1]
        return text[:1].upper() + text[1:]

    def to_dict(self) -> Dict[str, object]:
        return {"level": self.level, "label": self.label, "score": self.score,
                "summary": self.summary, "reasons": list(self.reasons),
                "factors": [factor.to_dict() for factor in self.factors],
                "work_stopped": self.work_stopped, "decision": self.decision,
                "routed": self.routed}


def _first(value: object, separator: str) -> str:
    parts = [part.strip() for part in str(value or "").split(separator) if part.strip()]
    return parts[0] if parts else ""


def recommend(row: Dict[str, object], context: Optional[AssetContext] = None,
              decision: str = "") -> Recommendation:
    """The recommendation for one analysed report, with every factor that counted."""
    factors: List[Factor] = []
    text = str(row.get("translated_text") or row.get("raw_text") or "")
    risk = float(row.get("risk_score") or 0.0)
    sif = bool(row.get("sif_potential"))
    high_energy = bool(row.get("high_energy"))
    energy = str(row.get("energy_source") or "")
    failed = bool(row.get("barrier_failed"))
    failure = str(row.get("barrier_failure") or "")
    activity = str(row.get("activity") or "")
    rule = str(row.get("iogp_rule") or "")

    # 1-2. hazards and SIF-precursor information
    if high_energy:
        factors.append(Factor("High-energy hazard", energy, 2, "hazard"))
    if sif:
        factors.append(Factor("SIF precursor (engine)",
                              f"fatal potential, P(SIF) {float(row.get('p_sif') or 0):.2f}",
                              3, "precursor"))
    agreeing = [name for name, key in (("learned model", "ml_flag"), ("local LLM", "llm_flag"))
                if row.get(key.replace("flag", "active")) and bool(row.get(key)) == sif and sif]
    if agreeing:
        factors.append(Factor("Second opinion agrees", " and ".join(agreeing) + " also flag it",
                              1, "precursor"))

    # 3. failed or absent controls
    if failed and failure:
        factors.append(Factor("Control failed or absent", failure, 2, "control"))

    # 4. exposure severity
    if risk >= CRITICAL:
        factors.append(Factor("Critical exposure", f"risk score {risk:.0f} of 100", 3,
                              "exposure"))
    elif risk >= HIGH:
        factors.append(Factor("High exposure", f"risk score {risk:.0f} of 100", 1, "exposure"))
    kind = report_kind(text)
    if kind in ("incident", "near miss") and (sif or high_energy):
        factors.append(Factor("People exposed",
                              "the report describes " + ("harm" if kind == "incident" else
                                                         "people at work with the hazard present"),
                              1, "exposure"))

    # 5. activity context
    matched = HIGH_RISK_WORK.search(f"{activity} {rule}")
    if matched and (sif or high_energy):
        factors.append(Factor("High-risk activity",
                              f"{activity or 'activity not stated'} · IOGP {rule}", 1,
                              "activity"))

    # 6. asset history
    history_hold = []
    if context is not None and context.known:
        for signal in context.signals:
            weight = {"repeated control failure": 3, "corrective action did not hold": 3,
                      "emerging SIF precursor": 3 if signal.severity == "high" else 2,
                      "recurring hazard": 2 if signal.severity == "high" else 1,
                      "confirmed precursor on record": 1,
                      "open corrective action": 1 if signal.severity != "low" else 0}.get(
                signal.kind, 0)
            if weight:
                factors.append(Factor(f"Asset history: {signal.kind}", signal.text, weight,
                                      "history"))
            if signal.kind in ("repeated control failure", "corrective action did not hold") \
                    or (signal.kind == "emerging SIF precursor" and signal.severity == "high"):
                history_hold.append(signal.kind)

    score = sum(factor.weight for factor in factors)
    reasons: List[str] = []
    level = CONTINUE
    if sif and failed and (risk >= CRITICAL or history_hold):
        level = HOLD
        why = f"fatal potential with a failed control ({_first(failure, ';') or 'control'})"
        reasons.append(why + (f" at critical risk {risk:.0f}" if risk >= CRITICAL
                              else f" and {history_hold[0]} at this asset"))
    elif score >= HOLD_SCORE:
        level = HOLD
        reasons.append(f"the weighted evidence ({score}) reached the hold threshold "
                       f"({HOLD_SCORE})")
    elif sif:
        level = REVIEW
        reasons.append("the engine found fatal potential")
    elif risk >= HIGH:
        level = REVIEW
        reasons.append(f"risk score {risk:.0f}")
    elif high_energy and failed:
        level = REVIEW
        reasons.append(f"{_first(energy, ' + ')} with a failed control")
    elif any(factor.group == "history" and factor.weight >= 2 for factor in factors):
        level = REVIEW
        reasons.append("the asset's history")
    elif score >= REVIEW_SCORE:
        level = REVIEW
        reasons.append(f"the weighted evidence ({score}) reached the review threshold "
                       f"({REVIEW_SCORE})")

    # A person's decision stands beside the engine's; it can bring a report back.
    if decision == "rejected":
        reasons.insert(0, "an HSE reviewer judged it not SIF potential")
        level = CONTINUE
    elif decision == "confirmed" and level == CONTINUE:
        level = REVIEW
        reasons.insert(0, "an HSE reviewer confirmed SIF potential")
    elif decision == "confirmed":
        reasons.append("an HSE reviewer confirmed SIF potential")

    factors.sort(key=lambda factor: -factor.weight)
    return Recommendation(level, score, factors, reasons,
                          bool(WORK_STOPPED.search(text)), decision)
