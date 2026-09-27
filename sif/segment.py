"""Where one report ends and the next begins in a text document.

A blank line is not a report boundary. A field report form has a heading
(company, site, date, report number), the narrative, and an "Immediate
action:" paragraph - three paragraphs, one report. A shift log has a heading
and then one entry per paragraph - many reports. A file of reports in several
languages marks each one with a separator line (``--- HINDI ---``). Cutting
every one of them on blank lines turned a Hindi report form into three
"reports", one of them just the letterhead.

:func:`split_reports` reads the layout instead:

1. **Separator lines** (``---``, ``===``, ``***``, a form feed) divide the
   document into sections. When the separators carry labels, the text before
   the first one is the document's own heading and is dropped.
2. **Leading headings** - short lines with no sentence ending - are the
   letterhead. They stay with the report when the document holds one report,
   and are dropped when it holds several (a log's title is not an incident).
3. **Follow-on paragraphs** - one that opens with a short label and a colon,
   such as "Immediate action:" or "तत्काल कार्रवाई:" - belong to the report
   above them.
4. **Fragments** too short to be a report join the report above them.

Works for every script SENTRA reads: the sentence endings include the danda
(।) and the Urdu full stop (۔).
"""

from __future__ import annotations

import re
from typing import List

__all__ = ["split_reports", "is_heading", "is_follow_on", "report_date"]

#: Anything shorter is a fragment, not a report.
MINIMUM_REPORT = 25

_SEPARATOR = re.compile(r"^[ \t]*(?:[-=*_#~]{3,})(?P<label>[^\n]*?)(?:[-=*_#~]{3,})?[ \t]*$",
                        re.MULTILINE)
_SENTENCE_END = re.compile(r"[.!?।॥۔](?:\s|$)")
#: "Immediate action:", "तत्काल कार्रवाई:", "فوری کارروائی:" - up to four words, then a colon.
_LABEL = re.compile(r"^\s*(?P<label>[^\s:：\d][^:：\n]{0,38}?)\s*[:：]")
#: A label that starts a report of its own rather than continuing one.
_STARTS_REPORT = re.compile(r"\d|\b(?:report|incident|entry|case|observation|near[- ]miss)\b",
                            re.IGNORECASE)


def _paragraphs(text: str) -> List[str]:
    return [block.strip() for block in re.split(r"\n[ \t]*\n", text) if block.strip()]


def is_heading(paragraph: str) -> bool:
    """A letterhead or title: at most three short lines and not a sentence."""
    lines = [line for line in paragraph.splitlines() if line.strip()]
    if not lines or len(lines) > 3:
        return False
    if max(len(line.strip()) for line in lines) > 110:
        return False
    return not _SENTENCE_END.search(paragraph)


def is_follow_on(paragraph: str) -> bool:
    """A paragraph that continues the report above it ("Immediate action: ...")."""
    match = _LABEL.match(paragraph)
    if not match:
        return False
    label = match.group("label")
    return len(label.split()) <= 4 and not _STARTS_REPORT.search(label)


def _split_section(section: str) -> List[str]:
    paragraphs = _paragraphs(section)
    headings: List[str] = []
    while paragraphs and is_heading(paragraphs[0]) and len(paragraphs) > 1:
        headings.append(paragraphs.pop(0))
    reports: List[str] = []
    for paragraph in paragraphs:
        if reports and (is_follow_on(paragraph) or len(paragraph) <= MINIMUM_REPORT):
            reports[-1] = reports[-1] + "\n\n" + paragraph
        else:
            reports.append(paragraph)
    if len(reports) == 1 and headings:
        # One report: the letterhead carries its site, date and number.
        return ["\n\n".join(headings + reports)]
    return reports


def split_reports(text: str) -> List[str]:
    """The reports in ``text``, each as its own string, in order.

    Never empty for a non-empty text: a document that cannot be divided is
    one report.
    """
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n---\n")
    if not text.strip():
        return []
    separators = list(_SEPARATOR.finditer(text))
    if separators:
        pieces = []
        start = 0
        for match in separators:
            pieces.append(text[start:match.start()])
            start = match.end()
        pieces.append(text[start:])
        labelled = any(match.group("label").strip() for match in separators)
        if labelled and len(pieces) > 1:
            pieces = pieces[1:]
        sections = [piece for piece in pieces if piece.strip()]
    else:
        sections = [text]
    reports = [report for section in sections for report in _split_section(section)]
    reports = [report for report in reports if len(report) > MINIMUM_REPORT] or reports
    return reports or [text.strip()]


#: "Date:" on a report form, in the languages SENTRA reads.
_DATE_LABEL = (r"(?:\bDate|\bDated|दिनांक|तारीख|तारीख़|तिथि|তাৰিখ|তারিখ|நாள்|தேதி|తేదీ|ದಿನಾಂಕ|"
               r"તારીખ|ਮਿਤੀ|ତାରିଖ|തീയതി|تاریخ)")
_DATE = re.compile(_DATE_LABEL + r"\s*[:：.-]?\s*(?P<a>\d{1,4})[-/.](?P<b>\d{1,2})[-/.](?P<c>\d{2,4})")


def report_date(text: str) -> str:
    """The date a report form gives itself - 'दिनांक: 18-09-2026' - as '2026-09-18'.

    Day first, as Indian forms write it; a four-digit first part is read as
    year-month-day. Indian digits are read too. Empty when the report names no
    date, or names one that cannot be a real day or lies in the future.
    """
    from datetime import date, timedelta

    match = _DATE.search(str(text or ""))
    if not match:
        return ""
    try:
        a, b, c = (int(match.group(name)) for name in "abc")
    except ValueError:
        return ""
    year, month, day = (a, b, c) if a > 31 else (c, b, a)
    if year < 100:
        year += 2000
    try:
        found = date(year, month, day)
    except ValueError:
        return ""
    if not date(1990, 1, 1) <= found <= date.today() + timedelta(days=1):
        return ""
    return found.isoformat()
