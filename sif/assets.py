"""Asset Safety Memory: each asset's safety history, and what it says about a new report.

An *asset* is the installation a report is about - an oil collecting station,
a rig, a gas compressor station, a substation - named by the report's site
(the export's ``site`` column) or, failing that, the location the engine read
from the text. Its memory is everything SENTRA holds about it:

* every report - classified from its wording as an **incident** (someone was
  hurt or something was damaged or released), a **near miss** (it could have
  been, and the report says so or says it was stopped) or a **hazard
  observation** (an unsafe act or condition seen before anything happened);
* the **hazards** - the high-energy sources the engine found;
* the **control failures** - the barriers found failed or absent;
* the **SIF precursors** - reports with fatal potential, and which of them an
  HSE reviewer confirmed;
* the **corrective actions** raised against its reports, and whether they
  are open, overdue or done;
* the equipment tags named in its reports (``P-3B``, ``GGS-5``, ``K-101``).

The memory is derived, not typed in: it is rebuilt from the reports,
decisions and actions the console keeps (and SENTRA's SQL database keeps
between sessions), so it can never disagree with them.

For a new report, :meth:`AssetMemory.context` compares it with what came
before at the same asset and returns *signals* an HSE professional should
read before deciding: a recurring hazard, a control that has failed there
before, an emerging SIF-precursor pattern, a corrective action that did not
hold, a confirmed precursor on record, actions still open.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = ["AssetRecord", "AssetAction", "Signal", "AssetHistory", "AssetContext",
           "AssetMemory", "asset_name", "report_kind", "equipment_tags", "WINDOW_DAYS"]

#: How far back "recurring" and "repeated" look from the report in hand.
WINDOW_DAYS = 90
#: How far back "emerging" looks, and the period it is compared with.
EMERGING_DAYS = 30

NO_HAZARD = "No high-energy source identified"
NO_FAILURE = "No barrier failure identified"
NOT_STATED = ("location not stated", "not stated", "unknown", "")

_INCIDENT = re.compile(
    r"\b(injur(?:ed|y|ies)|fractur\w*|hospital\w*|first[- ]aid|burn(?:ed|t|s)\b|lost[- ]time|"
    r"fatal\w*|killed|amputat\w*|unconscious|damag(?:ed|e to)|caught fire|fire broke out|"
    r"strain(?:ed)?|sprain(?:ed)?|bruis\w*|lacerat\w*|was hurt|hurt (?:his|her)|"
    r"explo(?:ded|sion occurred)|was released|leak(?:ed)? (?:of|and)|spill(?:ed|age))", re.I)
_NO_HARM = re.compile(r"\bno (?:one was )?(?:injur\w*|harm|damage)|nobody was (?:hurt|injured)|"
                      r"without injury|no one was hurt", re.I)
_NEAR_MISS = re.compile(
    r"\b(near[- ]miss|narrowly|could have|would have|nearly|missed (?:the|him|her)|"
    r"(?:work|job|task|operation)s? (?:was |were )?(?:stopped|halted|suspended)|"
    r"stopped the (?:job|work|task)|landed|fell|dropped|slipped)", re.I)
#: Someone was at work with the hazard present - a near miss, not an observation.
_EXPOSED = re.compile(
    r"\b(workers?|crew|fitter|technician|operator|electrician|rigger|driver|driller|welder|"
    r"helper|contractor|storekeeper|mechanic|lineman|linemen|team|gang|he|she|they|"
    r"people|persons|personnel|staff|men|"
    r"excavator|crane|bus|tanker|work (?:was|is) (?:being )?(?:done|carried out|underway)|"
    r"live[- ]line work|(?:was|were) (?:working|carrying|lifting|welding|cutting|entering))\b", re.I)
_NOT_EXPOSED = re.compile(r"\b(?:no one|nobody|no person(?:nel)?|no worker)s? (?:was|were) "
                          r"(?:working|present|in the area|exposed)|area was (?:unoccupied|empty)",
                          re.I)
_TAG = re.compile(r"\b(?!PTW\b|JSA\b|LOTO\b|PPE\b|H2S\b)([A-Z]{1,4}-\d{1,4}[A-Z]?)\b")


def asset_name(row: Dict[str, object]) -> str:
    """The asset a report is about: its site, else the location the engine read."""
    for key in ("site", "location"):
        name = " ".join(str(row.get(key) or "").split())
        if name.lower() not in NOT_STATED:
            return name
    return ""


def report_kind(text: str) -> str:
    """'incident', 'near miss' or 'hazard' - read from the report's own words."""
    text = str(text or "")
    harmed = bool(_INCIDENT.search(text))
    if harmed and _NO_HARM.search(text) and not re.search(r"\b(was|were) (injured|burned|burnt)\b",
                                                          text, re.I):
        harmed = False
    if harmed:
        return "incident"
    exposed = bool(_EXPOSED.search(text)) and not _NOT_EXPOSED.search(text)
    if _NEAR_MISS.search(text) or _NO_HARM.search(text) or exposed:
        return "near miss"
    return "hazard"


def equipment_tags(text: str) -> List[str]:
    """Equipment and unit tags named in the text (P-3B, GGS-5, K-101)."""
    seen: List[str] = []
    for tag in _TAG.findall(str(text or "")):
        if tag not in seen:
            seen.append(tag)
    return seen


def _parts(value: object, separator: str) -> List[str]:
    return [part.strip() for part in str(value or "").split(separator) if part.strip()]


def _when(row: Dict[str, object]) -> Optional[date]:
    for key in ("reported_on", "date", "analysed_at"):
        text = str(row.get(key) or "").strip()
        if text:
            try:
                return datetime.fromisoformat(text.replace("Z", "")[:19]).date()
            except ValueError:
                try:
                    return date.fromisoformat(text[:10])
                except ValueError:
                    continue
    return None


def _fmt(day: Optional[date]) -> str:
    return day.strftime("%d %b %Y").lstrip("0") if day else "undated"


@dataclass
class AssetRecord:
    """One report, as the asset's memory keeps it."""

    reference: str
    when: Optional[date]
    kind: str
    sif: bool
    risk: float
    hazards: List[str]
    failures: List[str]
    rule: str
    activity: str
    decision: str = ""           # confirmed / rejected / unclear / "" (not decided)
    fingerprint: str = ""
    order: int = 0               # arrival order, for undated reports

    @property
    def precursor(self) -> bool:
        """Fatal potential, unless a reviewer judged otherwise."""
        return self.decision == "confirmed" or (self.sif and self.decision != "rejected")

    def before(self, other: "AssetRecord") -> bool:
        if self.when and other.when and self.when != other.when:
            return self.when < other.when
        return self.order < other.order


@dataclass
class AssetAction:
    """A corrective action raised against one of the asset's reports."""

    title: str
    reference: str
    state: str                   # open / overdue / done
    start: Optional[date] = None
    done_on: Optional[date] = None


@dataclass
class Signal:
    """Something the history says about a report, in one line, with its evidence."""

    kind: str                    # recurring hazard / repeated control failure / ...
    text: str
    severity: str = "medium"     # high / medium / low
    references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {"kind": self.kind, "text": self.text, "severity": self.severity,
                "references": list(self.references)}


SIGNAL_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class AssetHistory:
    name: str
    records: List[AssetRecord] = field(default_factory=list)
    actions: List[AssetAction] = field(default_factory=list)
    equipment: List[str] = field(default_factory=list)
    signals: List[Signal] = field(default_factory=list)

    @property
    def kinds(self) -> Counter:
        return Counter(record.kind for record in self.records)

    @property
    def precursors(self) -> List[AssetRecord]:
        return [record for record in self.records if record.precursor]

    @property
    def confirmed(self) -> List[AssetRecord]:
        return [record for record in self.records if record.decision == "confirmed"]

    @property
    def hazards(self) -> Counter:
        return Counter(hazard for record in self.records for hazard in record.hazards)

    @property
    def failures(self) -> Counter:
        return Counter(failure for record in self.records for failure in record.failures)

    @property
    def open_actions(self) -> List[AssetAction]:
        return [action for action in self.actions if action.state != "done"]

    @property
    def last(self) -> Optional[AssetRecord]:
        return self.records[-1] if self.records else None

    @property
    def peak_risk(self) -> float:
        return max((record.risk for record in self.records), default=0.0)

    def summary(self) -> Dict[str, object]:
        kinds = self.kinds
        return {
            "asset": self.name, "reports": len(self.records),
            "incidents": kinds.get("incident", 0), "near_misses": kinds.get("near miss", 0),
            "hazards_seen": kinds.get("hazard", 0), "precursors": len(self.precursors),
            "confirmed": len(self.confirmed), "open_actions": len(self.open_actions),
            "overdue_actions": sum(1 for action in self.actions if action.state == "overdue"),
            "top_hazard": self.hazards.most_common(1)[0][0] if self.hazards else "",
            "top_failure": self.failures.most_common(1)[0][0] if self.failures else "",
            "signals": len(self.signals),
            "high_signals": sum(1 for signal in self.signals if signal.severity == "high"),
            "last": _fmt(self.last.when) if self.last else "",
            "peak_risk": self.peak_risk,
        }


@dataclass
class AssetContext:
    """What an asset's history says about one report."""

    asset: str
    record: Optional[AssetRecord]
    prior: List[AssetRecord] = field(default_factory=list)
    signals: List[Signal] = field(default_factory=list)
    actions: List[AssetAction] = field(default_factory=list)

    def has(self, kind: str) -> bool:
        return any(signal.kind == kind for signal in self.signals)

    @property
    def known(self) -> bool:
        return bool(self.asset)


class AssetMemory:
    """Every asset's history, built from the reports, decisions and actions held."""

    def __init__(self, window_days: int = WINDOW_DAYS, emerging_days: int = EMERGING_DAYS,
                 today: Optional[date] = None) -> None:
        self.window = timedelta(days=window_days)
        self.emerging = timedelta(days=emerging_days)
        self.today = today or date.today()
        self.histories: Dict[str, AssetHistory] = {}
        self._by_reference: Dict[str, Tuple[str, AssetRecord]] = {}

    # -- building --------------------------------------------------------------------

    def build(self, rows: Sequence[Dict[str, object]],
              decisions: Optional[Dict[str, str]] = None,
              actions: Iterable[object] = ()) -> "AssetMemory":
        """``decisions`` maps a report reference to its standing decision;
        ``actions`` are :class:`sif.actions.ComplianceAction` objects or dicts."""
        decisions = decisions or {}
        self.histories = {}
        self._by_reference = {}
        for order, row in enumerate(rows):
            name = asset_name(row)
            if not name:
                continue
            reference = str(row.get("reference") or "")
            text = str(row.get("translated_text") or row.get("raw_text") or "")
            record = AssetRecord(
                reference=reference, when=_when(row), kind=report_kind(text),
                sif=bool(row.get("sif_potential")), risk=float(row.get("risk_score") or 0.0),
                hazards=[part for part in _parts(row.get("energy_source"), " + ")
                         if part != NO_HAZARD],
                failures=[part for part in _parts(row.get("barrier_failure"), ";")
                          if part != NO_FAILURE] if row.get("barrier_failed", True) else [],
                rule=str(row.get("iogp_rule") or ""), activity=str(row.get("activity") or ""),
                decision=str(decisions.get(reference, "")), order=order)
            history = self.histories.setdefault(name.lower(), AssetHistory(name))
            history.records.append(record)
            for tag in equipment_tags(str(row.get("raw_text") or "")):
                if tag not in history.equipment:
                    history.equipment.append(tag)
            if reference:
                self._by_reference[reference] = (name.lower(), record)
        for history in self.histories.values():
            history.records.sort(key=lambda record: (record.when or date.max, record.order))
        for action in actions:
            self._attach(action)
        for history in self.histories.values():
            history.signals = self._asset_signals(history)
        return self

    def _asset_signals(self, history: AssetHistory) -> List[Signal]:
        """What the asset's recent history adds up to: each report's signals within
        the window of its latest report, the latest of each kind and subject kept."""
        latest = history.last
        if latest is None:
            return []
        recent = self._in_window(latest, history.records, self.window)
        merged: Dict[Tuple[str, str], Signal] = {}
        for record in recent:
            for signal in self._signals(history, record):
                if signal.kind == "first report" and len(history.records) > 1:
                    continue
                merged[(signal.kind, signal.text.split(":")[0])] = signal
        signals = list(merged.values())
        if any(signal.kind == "emerging SIF precursor" and signal.severity == "high"
               for signal in signals):
            # A named scenario says more than a count of the same reports.
            signals = [signal for signal in signals if signal.kind != "emerging SIF precursor"
                       or signal.severity == "high"]
        signals.sort(key=lambda signal: SIGNAL_ORDER.get(signal.severity, 3))
        return signals

    def _attach(self, action: object) -> None:
        data = action if isinstance(action, dict) else getattr(action, "__dict__", {})
        reference = str(data.get("reference") or "")
        if reference not in self._by_reference:
            return
        key, _record = self._by_reference[reference]
        start = _when({"date": data.get("start")})
        done = data.get("done") or {}
        recurring = str(data.get("recurrence") or "once") != "once"
        if done and not recurring:
            state = "done"
        elif start and start < self.today and not done:
            state = "overdue"
        else:
            state = "open"
        done_on = max((_when({"date": day}) for day in done), default=None) if done else None
        self.histories[key].actions.append(AssetAction(
            str(data.get("title") or ""), reference, state, start, done_on))

    # -- reading -----------------------------------------------------------------------

    def assets(self) -> List[AssetHistory]:
        """Worst first: high signals, then SIF precursors, then reports."""
        return sorted(self.histories.values(), key=lambda history: (
            -sum(1 for signal in history.signals if signal.severity == "high"),
            -len(history.precursors), -len(history.records), history.name))

    def get(self, name: str) -> Optional[AssetHistory]:
        return self.histories.get(str(name).lower())

    def context(self, reference_or_row) -> AssetContext:
        """The asset's history as it bears on one report."""
        if isinstance(reference_or_row, dict):
            reference = str(reference_or_row.get("reference") or "")
        else:
            reference = str(reference_or_row)
        found = self._by_reference.get(reference)
        if found is None:
            return AssetContext("", None)
        key, record = found
        history = self.histories[key]
        prior = [other for other in history.records
                 if other is not record and other.before(record)]
        related = {action.reference for action in history.actions}
        return AssetContext(history.name, record, prior, self._signals(history, record),
                            [action for action in history.actions
                             if action.reference in related])

    # -- the signals ---------------------------------------------------------------------

    def _in_window(self, record: AssetRecord, others: List[AssetRecord],
                   span: timedelta) -> List[AssetRecord]:
        if record.when is None:
            return others
        return [other for other in others
                if other.when is None or record.when - other.when <= span]

    def _signals(self, history: AssetHistory, record: AssetRecord) -> List[Signal]:
        prior = [other for other in history.records
                 if other is not record and other.before(record)]
        recent = self._in_window(record, prior, self.window)
        signals: List[Signal] = []
        days = self.window.days
        place = history.name

        for hazard in record.hazards:
            same = [other for other in recent if hazard in other.hazards]
            if same:
                fatal = any(other.precursor for other in same)
                signals.append(Signal(
                    "recurring hazard",
                    f"{hazard}: report {len(same) + 1} at {place} in {days} days"
                    + (" - earlier ones had fatal potential" if fatal else ""),
                    "high" if fatal and record.sif else "medium",
                    [other.reference for other in same]))

        for failure in record.failures:
            same = [other for other in recent if failure in other.failures]
            if same:
                signals.append(Signal(
                    "repeated control failure",
                    f"{failure}: failed {len(same)} time(s) before at {place}, first "
                    f"{_fmt(same[0].when)}",
                    "high" if len(same) >= 2 or record.sif else "medium",
                    [other.reference for other in same]))
                fixed = [action for action in history.actions
                         if action.state == "done" and action.reference in
                         {other.reference for other in same}
                         and (not record.when or not action.done_on
                              or action.done_on <= record.when)]
                if fixed:
                    signals.append(Signal(
                        "corrective action did not hold",
                        f"“{fixed[-1].title}” was closed for {fixed[-1].reference}, and "
                        f"the same control failed again: {failure}",
                        "high", [fixed[-1].reference]))

        if record.precursor:
            window = self._in_window(record, prior, self.emerging)
            current = [other for other in window if other.precursor]
            earlier = [other for other in self._in_window(record, prior, self.emerging * 2)
                       if other.precursor and other not in window]
            pairs = {(hazard, failure) for hazard in record.hazards
                     for failure in record.failures}
            same_scenario = [other for other in recent if other.precursor and pairs & {
                (hazard, failure) for hazard in other.hazards for failure in other.failures}]
            if same_scenario:
                hazard, failure = sorted(pairs & {
                    (h, f) for other in same_scenario for h in other.hazards
                    for f in other.failures})[0]
                signals.append(Signal(
                    "emerging SIF precursor",
                    f"{hazard} with “{failure}”: {len(same_scenario) + 1} reports with "
                    f"fatal potential at {place} in {days} days",
                    "high", [other.reference for other in same_scenario]))
            elif len(current) >= 1 and len(current) + 1 > len(earlier):
                signals.append(Signal(
                    "emerging SIF precursor",
                    f"{len(current) + 1} reports with fatal potential at {place} in the last "
                    f"{self.emerging.days} days, {len(earlier)} in the {self.emerging.days} "
                    "before",
                    "medium", [other.reference for other in current]))

        confirmed = [other for other in prior if other.decision == "confirmed"]
        if confirmed:
            signals.append(Signal(
                "confirmed precursor on record",
                f"{len(confirmed)} earlier report(s) at {place} confirmed as SIF potential by an "
                f"HSE reviewer, the latest {confirmed[-1].reference}",
                "medium", [other.reference for other in confirmed]))

        waiting = [action for action in history.actions if action.state != "done"]
        if waiting:
            overdue = [action for action in waiting if action.state == "overdue"]
            first = (overdue or waiting)[0]
            signals.append(Signal(
                "open corrective action",
                f"{len(waiting)} corrective action(s) open at {place}"
                + (f", {len(overdue)} overdue" if overdue else "")
                + f" - “{first.title}” ({first.reference})",
                "medium" if overdue else "low", [action.reference for action in waiting]))

        if not signals and not prior:
            signals.append(Signal("first report", f"The first report on record for {place}.",
                                  "low"))
        signals.sort(key=lambda signal: SIGNAL_ORDER.get(signal.severity, 3))
        return signals
