"""Compliance action items: the recurring and one-off HSE work on a calendar.

A SIF precursor is only half the job; the other half is the work that keeps
the barrier in place - a gas test before hot work every shift, a LOTO audit
every week, a permit renewed every month - and the corrective action a
confirmed report calls for. Each is an :class:`ComplianceAction`: a title, a
first date, a recurrence, an owner, and optionally the report it answers.

An action is stored once; its *occurrences* are worked out for whatever range
the calendar shows, so a daily task costs one record, not one per day. Done is
recorded per occurrence - the Tuesday gas test being done says nothing about
Wednesday's - with who closed it and when.

Stored as JSON, written atomically, next to the decision log.
"""

from __future__ import annotations

import calendar
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, NamedTuple, Optional

from .paths import writable

__all__ = ["ACTION_FILE", "CATEGORIES", "RECURRENCES", "RECURRENCE_LABELS", "SAMPLE_ACTIONS",
           "ActionStore", "ComplianceAction", "Occurrence", "default_action_path"]

LOGGER = logging.getLogger("sif.actions")

ACTION_FILE = "compliance_actions.json"
SCHEMA = 1

RECURRENCES = ("once", "daily", "weekdays", "weekly", "monthly")
RECURRENCE_LABELS = {
    "once": "Does not repeat",
    "daily": "Every day",
    "weekdays": "Every weekday (Mon-Fri)",
    "weekly": "Every week on the same day",
    "monthly": "Every month on the same date",
}
CATEGORIES = ("Inspection", "Permit to work", "Energy isolation", "Training",
              "Environmental", "Maintenance", "Corrective action")

#: How far back an unfinished occurrence still counts as overdue. A daily task
#: missed a year ago is a finding for an audit, not a red chip today.
OVERDUE_WINDOW_DAYS = 14


def default_action_path() -> str:
    return writable(ACTION_FILE)


def _day(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


@dataclass
class ComplianceAction:
    title: str
    start: str                                   # ISO date of the first occurrence
    recurrence: str = "once"
    until: str = ""                              # ISO date of the last, "" = open-ended
    category: str = "Inspection"
    owner: str = ""                              # username responsible
    reference: str = ""                          # report reference it answers, if any
    notes: str = ""
    created_by: str = ""
    created_at: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    #: occurrence date -> "username at ISO time" for each closed occurrence.
    done: Dict[str, str] = field(default_factory=dict)

    @property
    def recurring(self) -> bool:
        return self.recurrence != "once"

    def occurs_on(self, day: date) -> bool:
        first = _day(self.start)
        if day < first:
            return False
        if self.until and day > _day(self.until):
            return False
        if self.recurrence == "once":
            return day == first
        if self.recurrence == "daily":
            return True
        if self.recurrence == "weekdays":
            return day.weekday() < 5
        if self.recurrence == "weekly":
            return day.weekday() == first.weekday()
        if self.recurrence == "monthly":
            # The 31st falls on the last day of a shorter month rather than
            # skipping it: a monthly permit renewal does not take February off.
            last = calendar.monthrange(day.year, day.month)[1]
            return day.day == min(first.day, last)
        return False

    def is_done(self, day: date) -> bool:
        return day.isoformat() in self.done

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "ComplianceAction":
        known = {item.name for item in fields(cls)}
        values = {key: value for key, value in data.items() if key in known}
        values["done"] = dict(values.get("done") or {})
        return cls(**values)


class Occurrence(NamedTuple):
    action: ComplianceAction
    day: date
    done: bool
    overdue: bool

    @property
    def key(self) -> str:
        return f"{self.action.id}@{self.day.isoformat()}"


class ActionStore:
    """The action items, their occurrences, and who closed each one."""

    def __init__(self, path: str = "") -> None:
        self.path = path or default_action_path()
        self.actions: List[ComplianceAction] = []
        self.saved = True
        self._load()

    # -- persistence -----------------------------------------------------------

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as handle:
                payload = json.load(handle)
            self.actions = [ComplianceAction.from_dict(item)
                            for item in payload.get("actions", [])]
        except Exception as exc:  # noqa: BLE001 - a damaged file must not stop the console
            LOGGER.warning("Could not read compliance actions from %s (%s)", self.path, exc)
            self.actions = []

    def save(self) -> bool:
        payload = {"schema": SCHEMA, "saved_at": datetime.now().isoformat(timespec="seconds"),
                   "actions": [action.to_dict() for action in self.actions]}
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            temporary = f"{self.path}.tmp"
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False)
            os.replace(temporary, self.path)
            self.saved = True
        except Exception as exc:  # noqa: BLE001 - a read-only home is not fatal
            LOGGER.warning("Could not save compliance actions (%s)", exc)
            self.saved = False
        return self.saved

    # -- changes -----------------------------------------------------------------

    def add(self, title: str, start: object, recurrence: str = "once", *, until: object = "",
            category: str = "Inspection", owner: str = "", reference: str = "",
            notes: str = "", created_by: str = "") -> ComplianceAction:
        title = " ".join(str(title).split())
        if not title:
            raise ValueError("An action needs a title.")
        if recurrence not in RECURRENCES:
            raise ValueError(f"Unknown recurrence {recurrence!r}.")
        first = _day(start)
        last = _day(until).isoformat() if until else ""
        if last and _day(last) < first:
            raise ValueError("The last date is before the first.")
        action = ComplianceAction(
            title=title, start=first.isoformat(), recurrence=recurrence, until=last,
            category=category or "Inspection", owner=owner, reference=reference,
            notes=notes.strip(), created_by=created_by,
            created_at=datetime.now().isoformat(timespec="seconds"))
        self.actions.append(action)
        self.save()
        return action

    def get(self, action_id: str) -> Optional[ComplianceAction]:
        return next((action for action in self.actions if action.id == action_id), None)

    def remove(self, action_id: str) -> Optional[ComplianceAction]:
        action = self.get(action_id)
        if action is not None:
            self.actions.remove(action)
            self.save()
        return action

    def set_done(self, action_id: str, day: object, by: str, done: bool = True) -> bool:
        """Close (or reopen) one occurrence; False when it is not an occurrence."""
        action = self.get(action_id)
        when = _day(day)
        if action is None or not action.occurs_on(when):
            return False
        if done:
            action.done[when.isoformat()] = f"{by} at {datetime.now().isoformat(timespec='seconds')}"
        else:
            action.done.pop(when.isoformat(), None)
        self.save()
        return True

    def add_samples(self, anchor: date, created_by: str = "") -> int:
        """Load the example schedule, anchored on ``anchor``'s month."""
        first = anchor.replace(day=1)
        for title, offset, recurrence, category in SAMPLE_ACTIONS:
            self.add(title, first + timedelta(days=offset), recurrence, category=category,
                     owner=created_by, created_by=created_by)
        return len(SAMPLE_ACTIONS)

    # -- reading -------------------------------------------------------------------

    def occurrences(self, start: object, end: object,
                    today: Optional[date] = None) -> List[Occurrence]:
        """Every occurrence from ``start`` to ``end`` inclusive, by day then title."""
        first, last = _day(start), _day(end)
        today = today or date.today()
        horizon = today - timedelta(days=OVERDUE_WINDOW_DAYS)
        found: List[Occurrence] = []
        day = first
        while day <= last:
            for action in self.actions:
                if action.occurs_on(day):
                    done = action.is_done(day)
                    overdue = not done and horizon <= day < today
                    found.append(Occurrence(action, day, done, overdue))
            day += timedelta(days=1)
        found.sort(key=lambda item: (item.day, item.done, item.action.title.lower()))
        return found

    def due(self, day: object, today: Optional[date] = None) -> List[Occurrence]:
        return self.occurrences(day, day, today)

    def overdue(self, today: Optional[date] = None) -> List[Occurrence]:
        today = today or date.today()
        start = today - timedelta(days=OVERDUE_WINDOW_DAYS)
        return [item for item in self.occurrences(start, today - timedelta(days=1), today)
                if item.overdue]

    def for_reference(self, reference: str) -> List[ComplianceAction]:
        return [action for action in self.actions if action.reference == reference]


#: An example schedule for an upstream field - title, day offset in the month,
#: recurrence, category. Loaded on request only; nothing is invented otherwise.
SAMPLE_ACTIONS = (
    ("Gas test before hot work", 0, "weekdays", "Permit to work"),
    ("Toolbox talk - start of shift", 0, "weekdays", "Training"),
    ("LOTO audit - substation", 1, "weekly", "Energy isolation"),
    ("Scaffolding inspection before use", 2, "weekly", "Inspection"),
    ("H2S detector bump test", 3, "weekly", "Inspection"),
    ("Measure and document weekly emissions", 4, "weekly", "Environmental"),
    ("Renew cold-work permits", 5, "monthly", "Permit to work"),
    ("Fire extinguisher inspection", 6, "monthly", "Inspection"),
    ("Well control drill", 9, "monthly", "Training"),
    ("Pressure relief valve test - separator", 12, "monthly", "Maintenance"),
    ("Dispose oily waste", 4, "weekly", "Environmental"),
    ("Confined space rescue drill", 17, "once", "Training"),
)
