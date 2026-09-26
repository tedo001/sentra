"""Stage 5 - SIF risk score.

The classifier answers *whether* a report is a precursor; a queue of a thousand
"yes" answers still needs an order of work. The score turns the verdict into a
0-100 number by weighting three things a reviewer would weigh by hand:

* how confident the classifier is that both SIF conditions hold;
* how lethal the energy involved is if it is released (a fall from height and a
  slippery walkway are not the same exposure); and
* how close to the last line of defence the failed barrier sits.

The result is ordinal, not actuarial: it ranks a queue, it does not predict a
probability of death. For the same reason it never reads 100, and P(SIF) never
reads 1.00: a free-text report read by a machine is never certain, so the
score is capped at :data:`MAX_SCORE` (95) and the probability at
:data:`MAX_PROBABILITY` (0.95). The critical band starts at 85, so the cap
changes no report's band, queue or recommendation - only the claim of
certainty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .heads import SIFVerdict

__all__ = ["RiskScore", "RiskScorer", "ENERGY_SEVERITY", "BARRIER_CRITICALITY", "MAX_SCORE",
           "MAX_PROBABILITY", "cap_probability"]

#: The highest risk score a report can have: below 96, never "100%".
MAX_SCORE = 95.0
#: The highest P(SIF) a report can have.
MAX_PROBABILITY = 0.95


def cap_probability(value: float) -> float:
    return round(max(0.0, min(float(value), MAX_PROBABILITY)), 3)

#: How lethal an uncontrolled release of each energy typically is.
ENERGY_SEVERITY: Dict[str, float] = {
    "Gravity / Fall from height": 1.00,
    "Electrical energy": 1.00,
    "Toxic / Asphyxiant atmosphere": 1.00,
    "Suspended load / Mechanical": 0.95,
    "Pressure / Stored energy": 0.95,
    "Fire / Explosion": 0.95,
    "Excavation / Ground collapse": 0.90,
    "Vehicle / Traffic motion": 0.85,
    "Thermal energy": 0.80,
}

#: How close to the last line of defence each barrier sits.
BARRIER_CRITICALITY: Dict[str, float] = {
    "Fall protection not used / not anchored": 1.00,
    "Energy isolation / LOTO not applied or verified": 1.00,
    "Gas testing / ventilation / atmospheric control missing": 1.00,
    "Safety device bypassed, inhibited or removed": 0.95,
    "Exclusion zone / barricading absent": 0.90,
    "Fire prevention controls not in place": 0.90,
    "Equipment integrity / inspection lapse": 0.85,
    "Permit to work / JSA absent, expired or not followed": 0.85,
    "Competence / supervision inadequate": 0.80,
    "Traffic / journey management control breached": 0.80,
    "Mandatory PPE not worn": 0.70,
    "Housekeeping / walkway integrity lapse": 0.55,
}

DEFAULT_WEIGHT = 0.75


@dataclass
class RiskScore:
    """A 0-100 score with the factors that produced it."""

    value: float
    band: str
    drivers: Dict[str, float] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {"value": self.value, "band": self.band,
                "drivers": dict(self.drivers), "rationale": self.rationale}


class RiskScorer:
    """Turns a :class:`~sif.heads.SIFVerdict` into a ranked risk score."""

    BANDS = ((70.0, "Critical"), (50.0, "High"), (30.0, "Medium"), (0.0, "Low"))

    def score(self, verdict: SIFVerdict, extraction_confidence: float) -> RiskScore:
        energy_weight = self._weight(ENERGY_SEVERITY, verdict.energy_label)
        barrier_weight = self._weight(BARRIER_CRITICALITY, verdict.barrier_label)
        # A thin narrative should rank below an identical, well-evidenced one.
        evidence_factor = 0.85 + 0.15 * max(0.0, min(extraction_confidence, 1.0))

        probability = cap_probability(verdict.probability)
        value = 100.0 * probability * energy_weight * barrier_weight * evidence_factor
        value = round(max(0.0, min(value, MAX_SCORE)), 1)
        band = next(name for floor, name in self.BANDS if value >= floor)

        return RiskScore(
            value=value,
            band=band,
            drivers={
                "p_sif": probability,
                "energy_severity": round(energy_weight, 2),
                "barrier_criticality": round(barrier_weight, 2),
                "evidence_factor": round(evidence_factor, 2),
            },
            rationale=(f"P(SIF) {probability:.2f} x energy {energy_weight:.2f} "
                       f"x barrier {barrier_weight:.2f} x evidence {evidence_factor:.2f}"),
        )

    @staticmethod
    def _weight(table: Dict[str, float], label: str) -> float:
        """Look up a weight, taking the highest match in a compound label."""
        weights = [weight for key, weight in table.items() if key in label]
        return max(weights) if weights else DEFAULT_WEIGHT
