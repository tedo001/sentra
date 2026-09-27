"""What the design's pages say, worked out from the console's own state.

Pure functions: rows, queue entries, decisions and audit entries in; the
strings, pills and lists the pages show out. Kept apart from the widgets so
each wording can be tested without a window, and so every page words the
same thing the same way - a report "Awaiting review" on Home is "Awaiting
review" in HSE Review.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = ["ACTION_WORDS", "age", "case_line", "clock", "day_month", "describe_action",
           "initials", "queued_at", "received", "review_status", "row_when", "stamp",
           "trigger_counts", "weekly_series", "weekly_table", "fmt_date", "fmt_time",
           "TREND_SPANS", "trend_table", "trend_rows", "PROFILES", "risk_profile",
           "fmt_datetime", "fmt_week", "in_zone", "zone", "date_format", "ZONES"]

#: Audit actions as a sentence about a person, for timelines.
ACTION_WORDS = {
    "reports analysed": "Reports analysed",
    "review decision": "Review decision",
    "decision withdrawn": "Decision withdrawn",
    "signed in": "Signed in",
    "signed out": "Signed out",
    "sign-in refused": "Sign-in failed",
    "account locked": "Account locked",
    "password changed": "Password changed",
    "account created": "User created",
    "administrator created": "Administrator created",
    "password reset": "Password reset",
    "role changed": "Role changed",
    "account disabled": "Account disabled",
    "account enabled": "Account enabled",
    "document read": "Document read",
    "model trained": "Model trained",
    "permission refused": "Permission refused",
    "compliance action added": "Action item added",
    "compliance action done": "Action item done",
    "compliance action reopened": "Action item reopened",
    "compliance action deleted": "Action item deleted",
    "compliance actions loaded": "Example schedule loaded",
    "decision trail exported": "Decision trail exported",
    "audit trail exported": "Audit trail exported",
    "results exported": "Report exported",
    "setting changed": "Setting changed",
    "console started": "Console started",
    "console closed": "Console closed",
}

DECISION_WORDS = {"confirmed": "confirmed SIF on", "rejected": "marked not SIF",
                  "unclear": "asked for more information on"}


def _parse(value: object) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "")[:19])
    except ValueError:
        try:
            return datetime.fromisoformat(text[:10])
        except ValueError:
            return None


def row_when(row: Dict[str, object]) -> Optional[datetime]:
    """When a report happened: the export's own date, or when it was analysed."""
    return _parse(row.get("reported_on")) or _parse(row.get("analysed_at"))


def queued_at(row: Dict[str, object]) -> Optional[datetime]:
    """When a report reached the console - what "waiting" is measured from."""
    return _parse(row.get("analysed_at"))


def case_line(row: Dict[str, object]) -> str:
    """One sentence for a case: the first failed barrier, the energy, and where.

    The engine's full explanation is a paragraph; an alert has a line.
    """
    barrier = str(row.get("barrier_failure") or "").split(";")[0].strip()
    energy = str(row.get("energy_source") or "").split(" + ")[0].strip()
    where = str(row.get("site") or row.get("location") or "").strip()
    parts = []
    if barrier and barrier.lower() != "none identified":
        parts.append(barrier[0].upper() + barrier[1:])
    if energy and energy.lower() not in ("none identified", "unknown"):
        parts.append(energy.lower())
    text = " \u2014 ".join(parts) or str(row.get("review_reason") or "Needs a person")
    return f"{text} at {where}." if where else f"{text}."


def day_month(value: Optional[datetime]) -> str:
    return value.strftime("%d %b").lstrip("0") if value else "-"


# -- dates and times, one way everywhere ---------------------------------------------
#
# Settings chooses the date format and the time zone; every page asks these
# functions rather than calling strftime itself. Times are stored as this
# workstation's local clock, so they are converted to the chosen zone and the
# zone is named. A report's own date ("the export said 7 Jan") is a calendar
# date, not an instant, and is never shifted.

#: Settings' time zones, as fixed offsets: zoneinfo needs a time zone database
#: that a Windows build does not carry.
ZONES: Dict[str, Tuple[tzinfo, str]] = {
    "Asia/Kolkata (IST, UTC+5:30)": (timezone(timedelta(hours=5, minutes=30)), "IST"),
    "UTC": (timezone.utc, "UTC"),
}
DEFAULT_ZONE = "Asia/Kolkata (IST, UTC+5:30)"
DEFAULT_DATE_FORMAT = "%d %b %Y"


def _setting(key: str, default: str) -> str:
    try:
        from sif import prefs

        return str(prefs.get(key, default) or default)
    except Exception:  # noqa: BLE001 - formatting must never fail
        return default


def date_format() -> str:
    return _setting("date_format", DEFAULT_DATE_FORMAT)


def zone() -> Tuple[tzinfo, str]:
    return ZONES.get(_setting("timezone", DEFAULT_ZONE), ZONES[DEFAULT_ZONE])


def in_zone(when: datetime) -> datetime:
    """A stored local time as it reads in the chosen zone."""
    target, _name = zone()
    if when.tzinfo is None:
        when = when.astimezone()          # this workstation's clock
    return when.astimezone(target)


def fmt_date(value: object) -> str:
    """'25 Sep 2026' (or the format Settings chose); a calendar date is not shifted."""
    if isinstance(value, datetime):
        when = value
    elif isinstance(value, date):
        return value.strftime(date_format()).lstrip("0") if date_format().startswith("%d") \
            else value.strftime(date_format())
    else:
        text = str(value or "").strip()
        when = _parse(text)
        if when is None:
            return "-"
        if len(text) > 10:
            when = in_zone(when)
    out = when.strftime(date_format())
    return out.lstrip("0") if date_format().startswith("%d %b") else out


def fmt_time(value: object, seconds: bool = False) -> str:
    """'14:06 IST' - in the chosen zone, named."""
    when = value if isinstance(value, datetime) else _parse(value)
    if when is None:
        return "-"
    local = in_zone(when)
    return local.strftime("%H:%M:%S" if seconds else "%H:%M") + " " + zone()[1]


def fmt_datetime(value: object, seconds: bool = False) -> str:
    """'25 Sep 2026, 14:06 IST' - date, time and zone."""
    when = value if isinstance(value, datetime) else _parse(value)
    if when is None:
        return "-"
    local = in_zone(when)
    day = local.strftime(date_format())
    if date_format().startswith("%d %b"):
        day = day.lstrip("0")
    return f"{day}, {local.strftime('%H:%M:%S' if seconds else '%H:%M')} {zone()[1]}"


def fmt_week(start: date, days: int = 7) -> str:
    """'27 Oct – 2 Nov 2025' - one week, for a chart's tooltip."""
    end = start + timedelta(days=days - 1)
    first = start.strftime("%d %b").lstrip("0") + (
        start.strftime(" %Y") if start.year != end.year else "")
    return f"{first} – {end.strftime('%d %b %Y').lstrip('0')}"


def received(row: Dict[str, object]) -> str:
    """When the report says it happened: its date, with the time only when the
    source had one ('7 Jan 2026' or '25 Sep 2026, 11:42 IST')."""
    reported = str(row.get("reported_on") or "")
    if reported:
        return fmt_date(reported) if len(reported) <= 10 else fmt_datetime(reported)
    analysed = row.get("analysed_at")
    return fmt_datetime(analysed) if analysed else "-"


def clock(value: object) -> str:
    when = _parse(value)
    return in_zone(when).strftime("%H:%M") if when else ""


def stamp(value: object) -> str:
    """'25 Sep 2026, 13:52:41 IST' - the audit and log tables' full timestamp."""
    return fmt_datetime(value, seconds=True) if _parse(value) else str(value or "")


def age(since: Optional[datetime], now: Optional[datetime] = None) -> str:
    """'2 h 24 m', '3 d 4 h' - how long something has waited."""
    if since is None:
        return ""
    delta = (now or datetime.now()) - since
    minutes = max(0, int(delta.total_seconds() // 60))
    days, rest = divmod(minutes, 1440)
    hours, minutes = divmod(rest, 60)
    if days:
        return f"{days} d {hours} h"
    if hours:
        return f"{hours} h {minutes} m"
    return f"{minutes} m" if minutes else "just now"


def initials(name: str) -> str:
    words = [word for word in str(name or "").replace(".", " ").split() if word[:1].isalpha()]
    return "".join(word[0] for word in words[:2]).upper() or "?"


def review_status(row: Dict[str, object], decision: Optional[Dict[str, object]]
                  ) -> Tuple[str, str]:
    """The review column's pill for one report: text and tone."""
    if decision:
        kind = decision.get("decision")
        if kind == "confirmed":
            who = initials(str(decision.get("reviewer", "")).split("(")[0])
            return (f"✓ Confirmed SIF · {who}", "dark")
        if kind == "rejected":
            return ("Not SIF", "grey")
        return ("? Needs info", "warn")
    if row.get("needs_review"):
        return ("Awaiting review", "info")
    return ("Closed · not queued", "grey")


def trigger_counts(queue: Iterable[Dict[str, object]]) -> List[Tuple[str, int]]:
    """Open cases per review trigger, most first."""
    counts = Counter(str(item.get("trigger") or "Other") for item in queue
                     if not item.get("decided"))
    return counts.most_common()


def describe_action(entry: Dict[str, object], me: str = "") -> Tuple[str, str, str]:
    """An audit entry as a timeline line: time, sentence, and what it was."""
    action = str(entry.get("action", ""))
    detail = entry.get("detail") or {}
    user = str(entry.get("user") or "")
    who = "You" if me and user == me else (user or "System")
    when = clock(entry.get("at"))
    if action == "reports analysed":
        count = detail.get("count", "")
        queued = detail.get("awaiting_review")
        text = f"{count} report(s) analysed" + (f" · {queued} queued" if queued else "")
        return when, text, ("Analysis run by you" if who == "You" else f"Analysis run by {who}")
    if action == "review decision":
        verb = DECISION_WORDS.get(str(detail.get("decision")), "decided")
        return when, f"{who} {verb} {detail.get('reference', '')}".strip(), "Decision"
    if action == "decision withdrawn":
        return when, f"{who} withdrew the decision on {detail.get('reference', '')}", "Decision"
    if action == "document read":
        return when, f"{who} read {detail.get('name', 'a document')}", "Ingest"
    if action.startswith("compliance action"):
        title = detail.get("title", "")
        return when, f"{ACTION_WORDS.get(action, action)}: {title}", "Action items"
    return when, f"{ACTION_WORDS.get(action, action.capitalize())}" + (
        "" if who in ("You", "System") else f" · {who}"), str(entry.get("category", "")).title()


def weekly_series(rows: Sequence[Dict[str, object]], weeks: int = 13,
                  today: Optional[date] = None) -> Tuple[List[float], List[float], Tuple[str, str, str]]:
    """SIF-potential and critical reports per week, oldest first, with axis labels.

    The span ends at the latest dated report, so a historic export draws its own
    quarter rather than thirteen empty weeks before today.
    """
    dated = [(row_when(row), row) for row in rows]
    dated = [(when.date(), row) for when, row in dated if when is not None]
    if not dated:
        return [], [], ("", "", "")
    end = max(day for day, _row in dated) if today is None else today
    end_week = end - timedelta(days=end.weekday())
    start_week = end_week - timedelta(weeks=weeks - 1)
    sif = [0.0] * weeks
    critical = [0.0] * weeks
    for day, row in dated:
        index = (day - timedelta(days=day.weekday()) - start_week).days // 7
        if 0 <= index < weeks:
            if row.get("sif_potential"):
                sif[index] += 1
            if float(row.get("risk_score") or 0) >= 85:
                critical[index] += 1
    peak = int(max(sif)) if sif else 0
    labels = (f"w/c {start_week.strftime('%d %b').lstrip('0')}",
              f"weekly · peak {peak} SIF / week",
              f"w/c {end_week.strftime('%d %b').lstrip('0')}")
    return sif, critical, labels


def weekly_table(rows: Sequence[Dict[str, object]], weeks: int = 13,
                 end: Optional[date] = None) -> List[Dict[str, object]]:
    """Week by week, oldest first: SIF potential, critical (score >= 85) and all reports.

    The span ends at the latest dated report unless ``end`` is given, for the
    same reason :func:`weekly_series` does.
    """
    dated = [(when.date(), row) for when, row in ((row_when(row), row) for row in rows)
             if when is not None]
    if not dated:
        return []
    last = end or max(day for day, _row in dated)
    last_week = last - timedelta(days=last.weekday())
    first_week = last_week - timedelta(weeks=weeks - 1)
    table = [{"start": first_week + timedelta(weeks=i),
              "label": (first_week + timedelta(weeks=i)).strftime("%d %b").lstrip("0"),
              "week": fmt_week(first_week + timedelta(weeks=i)),
              "sif": 0, "critical": 0, "reports": 0} for i in range(weeks)]
    for day, row in dated:
        index = (day - timedelta(days=day.weekday()) - first_week).days // 7
        if 0 <= index < weeks:
            table[index]["reports"] += 1
            if row.get("sif_potential"):
                table[index]["sif"] += 1
            if float(row.get("risk_score") or 0) >= 85:
                table[index]["critical"] += 1
    return table


# -- the risk trend up to now, and the risk profile ------------------------------------

#: The risk trend's ranges, each ending now: (key, button, unit, caption).
TREND_SPANS: Tuple[Tuple[str, str, str, str], ...] = (
    ("today", "Today", "hour", "hourly"),
    ("week", "Week", "day", "daily · last 7 days"),
    ("month", "Month", "day", "daily · last 30 days"),
    ("year", "Year", "month", "monthly · last 12 months"),
    ("all", "All", "", "every dated report"),
)
CRITICAL_SCORE = 85


def _moment(row: Dict[str, object]) -> Tuple[Optional[datetime], bool]:
    """When a report happened, in the chosen zone, and whether a time was given.

    A date alone ("2026-09-10") is a calendar day and is not shifted; it has
    no hour, so the Today view counts it apart instead of at midnight.
    """
    reported = str(row.get("reported_on") or "").strip()
    when = _parse(reported) if reported else None
    if when is not None:
        timed = len(reported) > 10
        return ((in_zone(when).replace(tzinfo=None) if timed else when), timed)
    analysed = _parse(row.get("analysed_at"))
    if analysed is None:
        return None, False
    return in_zone(analysed).replace(tzinfo=None), True


def _month_start(day: date, back: int = 0) -> date:
    month = day.year * 12 + day.month - 1 - back
    return date(month // 12, month % 12 + 1, 1)


def _bucket(start: object, label: str, title: str) -> Dict[str, object]:
    return {"start": start, "label": label, "title": title,
            "sif": 0, "critical": 0, "reports": 0}


def _count(bucket: Dict[str, object], row: Dict[str, object]) -> None:
    bucket["reports"] += 1
    if row.get("sif_potential"):
        bucket["sif"] += 1
    if float(row.get("risk_score") or 0) >= CRITICAL_SCORE:
        bucket["critical"] += 1


def _day_label(day: date) -> str:
    return day.strftime("%d %b").lstrip("0")


def trend_table(rows: Sequence[Dict[str, object]], span: str = "month",
                now: Optional[datetime] = None) -> Dict[str, object]:
    """SIF potential, critical and all reports per hour, day or month, up to now.

    ``span`` is one of :data:`TREND_SPANS`: today by hour, the last 7 or 30
    days by day, the last 12 months by month, or every dated report (by day,
    week or month, whichever keeps the chart readable). Every range ends at
    the present moment - "up to date" - not at the latest report, so a quiet
    week shows as quiet.

    Returns ``{"span", "unit", "caption", "buckets", "untimed", "first", "last"}``;
    each bucket has ``start``, ``label``, ``title``, ``sif``, ``critical`` and
    ``reports``. ``untimed`` counts today's reports that give a date and no
    time - they have no hour to go in and get a bucket of their own.
    """
    now = in_zone(now or datetime.now()).replace(tzinfo=None)
    today = now.date()
    keys = {key: (unit, caption) for key, _button, unit, caption in TREND_SPANS}
    span = span if span in keys else "month"
    unit, caption = keys[span]
    moments = [(_moment(row), row) for row in rows]
    moments = [(when, timed, row) for (when, timed), row in moments if when is not None]
    untimed = 0

    if span == "today":
        buckets = [_bucket(datetime.combine(today, datetime.min.time()) + timedelta(hours=hour),
                           f"{hour:02d}:00",
                           f"{fmt_date(today)}, {hour:02d}:00\u2013{(hour + 1) % 24:02d}:00 "
                           f"{zone()[1]}") for hour in range(24)]
        # A report dated today with no time has no hour: it is counted in the
        # range's total and named in the caption, not drawn at midnight.
        loose = _bucket(None, "No time", f"{fmt_date(today)} - date given, no time")
        for when, timed, row in moments:
            if when.date() != today:
                continue
            if timed:
                _count(buckets[when.hour], row)
            else:
                _count(loose, row)
                untimed += 1
        caption = f"{fmt_date(today)} · hourly"
    elif span in ("week", "month"):
        days = 7 if span == "week" else 30
        first = today - timedelta(days=days - 1)
        buckets = [_bucket(first + timedelta(days=i),
                           ((first + timedelta(days=i)).strftime("%a ") if span == "week" else "")
                           + _day_label(first + timedelta(days=i)),
                           (first + timedelta(days=i)).strftime("%A ") +
                           fmt_date(first + timedelta(days=i)))
                   for i in range(days)]
        for when, _timed, row in moments:
            index = (when.date() - first).days
            if 0 <= index < days:
                _count(buckets[index], row)
        caption = f"{fmt_date(first)} \u2192 {fmt_date(today)} · daily"
    elif span == "year":
        months = [_month_start(today, back) for back in range(11, -1, -1)]
        buckets = [_bucket(month, month.strftime("%b") + (month.strftime(" %y")
                                                          if month.month == 1 or i == 0 else ""),
                           month.strftime("%B %Y")) for i, month in enumerate(months)]
        for when, _timed, row in moments:
            key = date(when.year, when.month, 1)
            if months[0] <= key <= months[-1]:
                index = (key.year - months[0].year) * 12 + key.month - months[0].month
                _count(buckets[index], row)
        caption = (f"{months[0].strftime('%b %Y')} \u2192 {months[-1].strftime('%b %Y')}"
                   " · monthly")
    else:
        if not moments:
            return {"span": span, "unit": "day", "caption": "no dated reports", "buckets": [],
                    "untimed": 0, "first": None, "last": None}
        first_day = min(when.date() for when, _timed, _row in moments)
        last_day = max(max(when.date() for when, _timed, _row in moments), today)
        length = (last_day - first_day).days + 1
        if length <= 31:
            unit = "day"
            buckets = [_bucket(first_day + timedelta(days=i), _day_label(first_day + timedelta(days=i)),
                               fmt_date(first_day + timedelta(days=i))) for i in range(length)]
            for when, _timed, row in moments:
                _count(buckets[(when.date() - first_day).days], row)
        elif length <= 26 * 7:
            unit = "week"
            start = first_day - timedelta(days=first_day.weekday())
            weeks = ((last_day - start).days // 7) + 1
            buckets = [_bucket(start + timedelta(weeks=i), _day_label(start + timedelta(weeks=i)),
                               "Week " + fmt_week(start + timedelta(weeks=i))) for i in range(weeks)]
            for when, _timed, row in moments:
                _count(buckets[(when.date() - start).days // 7], row)
        else:
            unit = "month"
            start = date(first_day.year, first_day.month, 1)
            count = (last_day.year - start.year) * 12 + last_day.month - start.month + 1
            months = [_month_start(start, -i) for i in range(count)]
            buckets = [_bucket(month, month.strftime("%b %y"), month.strftime("%B %Y"))
                       for month in months]
            for when, _timed, row in moments:
                index = (when.year - start.year) * 12 + when.month - start.month
                _count(buckets[index], row)
        caption = (f"{fmt_date(first_day)} \u2192 {fmt_date(last_day)} · "
                   f"{ {'day': 'daily', 'week': 'weekly', 'month': 'monthly'}[unit] }")
    in_range = sum(bucket["reports"] for bucket in buckets) + untimed
    return {"span": span, "unit": unit, "caption": caption, "buckets": buckets,
            "untimed": untimed, "reports": in_range,
            "untimed_counts": loose if span == "today" else None,
            "first": buckets[0]["start"] if buckets else None,
            "last": buckets[-1]["start"] if buckets else None}


def trend_rows(rows: Sequence[Dict[str, object]], span: str = "month",
               now: Optional[datetime] = None) -> List[Dict[str, object]]:
    """The reports inside the trend's range - what the spider chart beside it draws."""
    now = in_zone(now or datetime.now()).replace(tzinfo=None)
    today = now.date()
    first = {"today": today, "week": today - timedelta(days=6),
             "month": today - timedelta(days=29),
             "year": _month_start(today, 11)}.get(span)
    kept = []
    for row in rows:
        when, _timed = _moment(row)
        if when is None:
            continue
        if first is None or first <= when.date() <= today:
            kept.append(row)
    return kept


#: The spider chart's views: (key, button, axes as (full name, short label)).
PROFILES: Tuple[Tuple[str, str, Tuple[Tuple[str, str], ...]], ...] = (
    ("rule", "IOGP rule", (
        ("Working at Height", "Height"), ("Energy Isolation", "Isolation"),
        ("Line of Fire", "Line of fire"), ("Confined Space", "Confined space"),
        ("Safe Mechanical Lifting", "Lifting"), ("Hot Work", "Hot work"),
        ("Driving", "Driving"), ("Bypassing Safety Controls", "Bypass"),
        ("Work Authorisation", "Permit"), ("Excavation & Ground Disturbance", "Excavation"),
        ("Well Control & Process Containment", "Well control"))),
    ("energy", "Energy", (
        ("Gravity / Fall from height", "Fall"), ("Electrical energy", "Electrical"),
        ("Suspended load / Mechanical", "Load"), ("Pressure / Stored energy", "Pressure"),
        ("Fire / Explosion", "Fire"), ("Toxic / Asphyxiant atmosphere", "Toxic"),
        ("Vehicle / Traffic motion", "Traffic"), ("Excavation / Ground collapse", "Ground"),
        ("Thermal energy", "Thermal"))),
    ("barrier", "Barrier", (
        ("Fall protection not used / not anchored", "Fall protection"),
        ("Energy isolation / LOTO not applied or verified", "LOTO"),
        ("Permit to work / JSA absent, expired or not followed", "Permit / JSA"),
        ("Gas testing / ventilation / atmospheric control missing", "Gas test"),
        ("Exclusion zone / barricading absent", "Exclusion zone"),
        ("Safety device bypassed, inhibited or removed", "Bypass"),
        ("Fire prevention controls not in place", "Fire prevention"),
        ("Mandatory PPE not worn", "PPE"),
        ("Competence / supervision inadequate", "Supervision"),
        ("Traffic / journey management control breached", "Journey"),
        ("Equipment integrity / inspection lapse", "Integrity"),
        ("Well monitoring / containment control lapsed", "Well"))),
)


def risk_profile(rows: Sequence[Dict[str, object]], by: str = "rule"
                 ) -> List[Tuple[str, str, int, int, int]]:
    """Per axis of the spider chart: (full name, short label, SIF, critical, all).

    A report counts on every axis it names - an energy source of "Electrical
    energy + Fire / Explosion" is on both - and the axes are fixed, so the
    shape can be compared between one period and the next.
    """
    axes = dict((key, axes) for key, _button, axes in PROFILES).get(by) or PROFILES[0][2]
    field, split = {"rule": ("iogp_rule", None), "energy": ("energy_source", "+"),
                    "barrier": ("barrier_failure", ";")}.get(by, ("iogp_rule", None))
    counts = {name: [0, 0, 0] for name, _short in axes}
    for row in rows:
        value = str(row.get(field) or "")
        names = [part.strip() for part in value.split(split)] if split else [value.strip()]
        for name in set(names):
            if name in counts:
                slot = counts[name]
                slot[2] += 1
                if row.get("sif_potential"):
                    slot[0] += 1
                if float(row.get("risk_score") or 0) >= CRITICAL_SCORE:
                    slot[1] += 1
    return [(name, short, *counts[name]) for name, short in axes]
