"""The HSE workspace's pages, fed from the console's state.

A mixin for :class:`main4.WorkspaceWindow`: it builds the design's HSE pages
and fills them from what the controller already holds - the analysed rows,
the review queue, the decision log, the audit trail, the documents and the
action items. It holds no state of its own beyond the pages.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QTimer

from main2 import ExtractionWorker, requires
from sif import SEED_REPORTS
from sif import prefs
from sif.accounts import ANALYSE, DECIDE
from sif.llm import looks_non_latin
from sif.ocr import IMAGE_SUFFIXES, PDF_SUFFIXES, PaddleOCRBackend
from sif.review import fingerprint

from .dashboard import DashboardPage
from .home import HomePage
from .hotspots import HotspotsPage
from .ingest import IngestPage
from .reports import ReportsPage
from .review import ReviewPage
from .present import (age, case_line, describe_action, initials, queued_at, received,
                      review_status, row_when, trigger_counts, weekly_series)

__all__ = ["HSEPages"]

#: Critical, by the design's cut: a score at or above this is "Critical".
CRITICAL = 85.0


class HSEPages:
    """Home, Ingest, Dashboard, HSE Review, Risk Hotspots, Profile - the design's."""

    _intelligence = None

    # -- shared reading of the corpus --------------------------------------------

    def _decisions_by_row(self) -> List[Optional[Dict[str, object]]]:
        """The standing decision on each analysed row, or None."""
        standing = self.decisions.current()
        found: List[Optional[Dict[str, object]]] = []
        for position in range(1, len(self.rows) + 1):
            result = self._result_at(position)
            entry = standing.get(fingerprint(result)) if result is not None else None
            found.append(entry.to_dict() if entry is not None else None)
        return found

    def _row_for(self, reference: str) -> Tuple[int, Optional[Dict[str, object]]]:
        for index, row in enumerate(self.rows):
            if str(row.get("reference")) == reference:
                return index, row
        return -1, None

    def _open_queue(self) -> List[Dict[str, object]]:
        return [item for item in self.queue_rows if not item.get("decided")]

    # -- Home -------------------------------------------------------------------------

    def _build_home(self) -> HomePage:
        page = HomePage()
        page.refresh_requested.connect(self._refresh_home)
        page.review_requested.connect(self.open_case)
        page.report_requested.connect(self.open_report)
        page.reports_requested.connect(lambda: self.open_report(""))
        page.alert_action.connect(self._home_alert)
        return page

    def _home_alert(self, key: str, payload: str) -> None:
        if key == "review":
            self.open_case(payload)
        elif key == "hotspot":
            self.navigate("hotspots")
        elif key == "actions":
            self.navigate("actions")
        elif key == "ingest":
            self.navigate("ingest")
        elif key == "report":
            self.open_report(payload)

    def _refresh_home(self) -> None:
        page = self.home_page
        now = datetime.now()
        page.set_heading(now.strftime("%a %d %b %Y · %H:%M"),
                         f"Updated {now.strftime('%H:%M:%S')}")
        rows = self.rows
        decisions = self._decisions_by_row()
        by_ref = {str(row.get("reference")): row for row in rows}

        open_items = self._open_queue()
        critical = sorted((item for item in open_items
                           if float(item.get("risk_score") or 0) >= CRITICAL),
                          key=lambda item: (-float(item.get("risk_score") or 0),
                                            str(by_ref.get(str(item.get("reference")), {})
                                                .get("analysed_at", ""))))
        oldest = min((queued_at(by_ref.get(str(item.get("reference")), {}))
                      or now for item in critical), default=None)
        needs_info = sum(1 for entry in decisions if entry and entry.get("decision") == "unclear")
        over_two_days = sum(
            1 for item in open_items
            if (queued_at(by_ref.get(str(item.get("reference")), {})) or now)
            < now - timedelta(hours=48))
        sif = sum(1 for row in rows if row.get("sif_potential"))
        today = now.date().isoformat()
        analysed_today = sum(1 for row in rows
                             if str(row.get("analysed_at", "")).startswith(today))
        page.set_stats((
            (len(rows), f"{analysed_today} analysed today" if rows else "none yet", False),
            (sif, f"{sif * 100 // len(rows)}% of reports" if rows else "", False),
            (len(critical), f"oldest waiting {age(oldest, now)}" if critical else "none open",
             bool(critical)),
            (self.outstanding_reviews,
             f"+{needs_info} needs info · {over_two_days} over 48 h", False),
        ))
        page.set_attention(self._attention(critical[:3], by_ref, now))
        page.set_triggers(trigger_counts(self.queue_rows))

        order = sorted(range(len(rows)), key=lambda i: (
            str(rows[i].get("reported_on") or rows[i].get("analysed_at") or ""), i),
            reverse=True)
        incidents = []
        for index in order[:40]:
            row = dict(rows[index])
            row["status"] = review_status(row, decisions[index])
            incidents.append(row)
        page.set_incidents(incidents)

        me = self.session.username
        entries = [entry for entry in self.audit.rows(limit=300)
                   if str(entry.get("at", "")).startswith(today)
                   and entry.get("action") not in ("console started", "console closed",
                                                   "signed in", "signed out")
                   and (entry.get("user") in (me, "") or not me)]
        page.set_activity([describe_action(entry, me) for entry in entries[:30]])

    # -- HSE Review ----------------------------------------------------------------------

    def _build_review(self) -> ReviewPage:
        # Decided cases stay in the controller's queue list here, so the Needs
        # info and Reviewed tabs have something to show.
        self.review_view.show_decided.blockSignals(True)
        self.review_view.show_decided.setChecked(True)
        self.review_view.show_decided.blockSignals(False)
        page = ReviewPage()
        page.case_selected.connect(self._show_case)
        page.decided.connect(self.decide_case)
        page.undo_requested.connect(self.undo_decision)
        page.export_requested.connect(self.export_decisions)
        allowed = self.session.can(DECIDE)
        page.bar.set_enabled(allowed, "Your role can read cases but not decide them.")
        page.bar.undo.setVisible(allowed)
        page.bar.recorded.setText(
            f"recorded under {self.session.full_name} ({self.session.role_label}) "
            "\u00b7 written to the audit log" if self.session.authenticated
            else "unattended \u00b7 written to the audit log")
        return page

    def _case_rows(self) -> List[Dict[str, object]]:
        decisions = self._decisions_by_row()
        now = datetime.now()
        cases = []
        for item in self.queue_rows:
            position = int(item.get("index", 0) or 0)
            if not 1 <= position <= len(self.rows):
                continue
            row = self.rows[position - 1]
            decision = decisions[position - 1]
            when = row_when(row)
            keys = []
            if decision is None:
                keys.append("open")
                if float(row.get("risk_score") or 0) >= CRITICAL:
                    keys.append("critical")
                if "disagree" in str(item.get("trigger", "")).lower():
                    keys.append("disagreement")
                queued = queued_at(row)
                if queued is not None and now - queued > timedelta(days=7):
                    keys.append("old")
            elif decision.get("decision") == "unclear":
                keys.append("info")
            else:
                keys.append("reviewed")
            cases.append({**row, "trigger": item.get("trigger", ""),
                          "status": review_status(row, decision),
                          "date": when.strftime("%d %b\n%H:%M") if when and row.get(
                              "analysed_at") and not row.get("reported_on")
                          else when.strftime("%d %b\n%Y") if when else "-",
                          "_in": tuple(keys)})
        return cases

    def _refresh_review_page(self) -> None:
        page = self.review_page
        cases = self._case_rows()
        counts = {key: sum(1 for case in cases if key in case["_in"])
                  for key in ("open", "critical", "disagreement", "info", "reviewed", "old")}
        page.set_counts(counts)
        page.head.caption.setText(
            f"{counts['open']} open \u00b7 decisions are recorded under "
            f"{self.session.full_name if self.session.authenticated else 'no one (unattended)'}")
        page.set_rows(cases)

    def _show_case(self, reference: str) -> None:
        page = self.review_page
        index, row = self._row_for(reference) if reference else (-1, None)
        if row is None:
            page.case.show_case(None)
            return
        decision = self._decisions_by_row()[index]
        meta = " \u00b7 ".join(str(part) for part in (
            row.get("site") or row.get("location"), row.get("activity"), received(row),
            f"reported by {row['reported_by']}" if row.get("reported_by") else "") if part)
        waiting = age(queued_at(row)) if decision is None else ""
        page.case.show_case(row, status=review_status(row, decision), meta=meta,
                            waiting=waiting)

    def open_case(self, reference: str = "") -> None:
        """HSE Review, on ``reference``'s case when it has one."""
        self.navigate("review")
        if reference:
            self.review_page.select(reference)

    def decide_case(self, reference: str, decision: str) -> bool:
        """Record ``decision`` on ``reference``'s case under the signed-in person."""
        if not self.permitted(DECIDE, "record_decision"):
            return False
        position = next((i for i, item in enumerate(self.queue_rows)
                         if str(item.get("reference")) == reference), -1)
        if position < 0:
            return False
        _index, row = self._row_for(reference)
        note = ""
        overturns = row is not None and ((decision == "rejected" and row.get("sif_potential"))
                                         or (decision == "confirmed"
                                             and not row.get("sif_potential")))
        if overturns and prefs.get("require_overturn_reason", True) and self.isVisible():
            from PyQt6.QtWidgets import QInputDialog

            note, ok = QInputDialog.getText(
                self, "Reason required",
                "This overturns the engine's call. Say why - it is kept with the decision:")
            if not ok or not note.strip():
                return False
        self.review_view.select(position)
        if self.review_view.current_row() != position:
            return False
        before = len(self.decisions.entries)
        self.record_decision(decision, note.strip())
        if len(self.decisions.entries) == before:
            return False
        # On to the next case still open in this list.
        shown = [str(case.get("reference")) for case in self.review_page.table.rows]
        after = shown[shown.index(reference) + 1:] if reference in shown else []
        self._refresh_review_page()
        remaining = [str(case.get("reference")) for case in self.review_page.table.rows]
        following = next((ref for ref in after if ref in remaining), None)
        if following:
            self.review_page.select(following)
        return True

    # -- Reports ---------------------------------------------------------------------------

    def _build_reports(self) -> ReportsPage:
        page = ReportsPage()
        page.report_selected.connect(self._show_report)
        page.case_requested.connect(self.open_case)
        page.action_requested.connect(self._raise_action)
        page.export_requested.connect(self.export_csv)
        page.raise_action.setVisible(self.session.can(ANALYSE))
        return page

    def _raise_action(self, reference: str) -> None:
        self.navigate("actions")
        self.add_action("", reference)

    def _refresh_reports(self) -> None:
        decisions = self._decisions_by_row()
        rows = []
        order = sorted(range(len(self.rows)), key=lambda i: (
            str(self.rows[i].get("reported_on") or self.rows[i].get("analysed_at") or ""), i),
            reverse=True)
        for index in order:
            row = dict(self.rows[index])
            row["status"] = review_status(row, decisions[index])
            rows.append(row)
        self.reports_page.set_rows(rows)

    def _show_report(self, reference: str) -> None:
        page = self.reports_page
        index, row = self._row_for(reference) if reference else (-1, None)
        if row is None:
            page.case.show_case(None)
            page.to_case.setEnabled(False)
            page.raise_action.setEnabled(False)
            return
        decision = self._decisions_by_row()[index]
        meta = " \u00b7 ".join(str(part) for part in (
            row.get("site") or row.get("location"), row.get("activity"), received(row),
            f"reported by {row['reported_by']}" if row.get("reported_by") else "") if part)
        queued = any(str(item.get("reference")) == reference for item in self.queue_rows)
        page.case.show_case(row, status=review_status(row, decision), meta=meta,
                            waiting=age(queued_at(row)) if queued and decision is None else "")
        page.to_case.setEnabled(queued)
        page.raise_action.setEnabled(True)

    # -- Risk Hotspots ------------------------------------------------------------------

    def _build_hotspots(self) -> HotspotsPage:
        page = HotspotsPage()
        self._hotspot_site = ""
        page.filters_changed.connect(self._refresh_hotspots)
        page.site_chosen.connect(self._choose_site)
        page.review_requested.connect(self.open_case)
        page.report_requested.connect(self.open_report)
        return page

    def _choose_site(self, label: str) -> None:
        self._hotspot_site = label
        self._refresh_hotspots()

    def _refresh_hotspots(self) -> None:
        from collections import Counter

        from sif.patterns import wilson_lower_bound

        page = self.hotspots_page
        period, minimum, rank = page.filters
        rows = self.rows
        dated = [row_when(row) for row in rows]
        latest = max((when for when in dated if when is not None), default=None)
        groups: Dict[str, List[int]] = {}
        for index, row in enumerate(rows):
            when = dated[index]
            if period and latest is not None and when is not None and (latest - when).days >= period:
                continue
            site = str(row.get("site") or row.get("location") or "").strip()
            if site and site.lower() not in ("unknown", "unspecified location"):
                groups.setdefault(site, []).append(index)
        spots = []
        for label, members in groups.items():
            if len(members) < minimum:
                continue
            picked = [rows[i] for i in members]
            sif = sum(1 for row in picked if row.get("sif_potential"))
            rules = Counter(self._sentence(row.get("iogp_rule") or "Unclassified")
                            for row in picked if row.get("sif_potential")) or Counter(
                self._sentence(row.get("iogp_rule") or "Unclassified") for row in picked)
            barriers = Counter(str(row.get("barrier_failure") or "").split(";")[0].strip()
                               for row in picked if row.get("barrier_failed"))
            top_barrier, repeats = (barriers.most_common(1)[0] if barriers else ("-", 0))
            days = [dated[i] for i in members if dated[i] is not None]
            span = (max(days) - min(days)).days + 1 if days else 0
            spots.append({"label": label, "reports": len(picked), "sif_reports": sif,
                          "density": wilson_lower_bound(sif, len(picked)),
                          "top_rule": rules.most_common(1)[0][0] if rules else "-",
                          "top_barrier": top_barrier or "-",
                          "repeats": f"{repeats} in {span} days" if repeats and span else "-",
                          "_members": members})
        key = (lambda spot: (-spot["density"], -spot["reports"])) if rank == "density" else \
            (lambda spot: (-spot["reports"], -spot["density"]))
        spots.sort(key=key)
        for number, spot in enumerate(spots, start=1):
            spot["rank"] = number
        labels = [spot["label"] for spot in spots]
        if self._hotspot_site not in labels:
            self._hotspot_site = labels[0] if labels else ""

        insight = ""
        if len(spots) > 2:
            busiest = max(spots, key=lambda spot: spot["reports"])
            if busiest["rank"] > 1:
                insight = (f"{busiest['label']} has the most reports ({busiest['reports']}) but "
                           f"ranks {busiest['rank']} of {len(spots)}: {busiest['sif_reports']} of "
                           f"{busiest['reports']} carry fatal potential. Volume is not risk.")
        chosen = next((spot for spot in spots if spot["label"] == self._hotspot_site), None)
        incidents, activities, barrier_counts, dominant = [], [], [], ""
        if chosen is not None:
            members = sorted(chosen["_members"], key=lambda i: str(
                rows[i].get("reported_on") or rows[i].get("analysed_at") or ""), reverse=True)
            for i in members:
                row = rows[i]
                text = " ".join(str(row.get("raw_text") or "").split())
                first = text.split(". ")[0]
                incidents.append({"reference": row.get("reference"),
                                  "date": (row_when(row).strftime("%d %b") if row_when(row) else "-"),
                                  "what": first if len(first) <= 56 else first[:55] + "\u2026",
                                  "risk": f"{float(row.get('risk_score') or 0):.0f}"})
            activities = Counter(str(rows[i].get("activity") or "Unspecified")
                                 for i in chosen["_members"]).most_common(6)
            barrier_counts = Counter(
                part.strip()[0].upper() + part.strip()[1:]
                for i in chosen["_members"] if rows[i].get("barrier_failed")
                for part in str(rows[i].get("barrier_failure") or "").split(";")
                if part.strip()).most_common(6)
            if barrier_counts:
                dominant = (f"Dominant: {barrier_counts[0][0]} under {chosen['top_rule']}.")
        page.show_state(spots, self._hotspot_site, insight, incidents, activities,
                        barrier_counts, dominant)

    # -- Dashboard ---------------------------------------------------------------------

    def _build_dashboard(self) -> DashboardPage:
        page = DashboardPage()
        page.period_changed.connect(lambda _key: self._refresh_dashboard())
        page.filter_changed.connect(self._refresh_dashboard)
        page.export_requested.connect(self.export_csv)
        page.queue_requested.connect(lambda: self.open_case(""))
        page.report_requested.connect(self.open_report)
        return page

    @staticmethod
    def _sentence(label: str) -> str:
        """'Energy Isolation' -> 'Energy isolation', as the design sets rule names."""
        words = str(label).split(" ")
        return " ".join([words[0]] + [word if word.isupper() and len(word) > 1 else word.lower()
                                      for word in words[1:]]) if words else ""

    def _refresh_dashboard(self) -> None:
        from collections import Counter

        page = self.dashboard_page
        rows = self.rows
        sites = sorted({str(row.get("site") or row.get("location") or "") for row in rows} - {""})
        activities = sorted({str(row.get("activity") or "") for row in rows} - {""})
        page.set_choices(sites, activities)
        period, site, activity = page.filters
        decisions = self._decisions_by_row()

        dated = [row_when(row) for row in rows]
        latest = max((when for when in dated if when is not None), default=None)
        chosen = []
        for index, row in enumerate(rows):
            if site and (row.get("site") or row.get("location")) != site:
                continue
            if activity and row.get("activity") != activity:
                continue
            when = dated[index]
            if latest is not None and when is not None and \
                    (latest - when).days >= int(period):
                continue
            chosen.append(index)
        span = {"30": "Last 30 days", "90": "Last 90 days", "365": "Last 12 months"}[period]
        if latest is not None:
            start = latest - timedelta(days=int(period) - 1)
            span += (f" ({start.strftime('%d %b').lstrip('0')} \u2013 "
                     f"{latest.strftime('%d %b %Y').lstrip('0')})")
        page.set_caption(f"{span} \u00b7 all figures are engine assessments unless "
                         "marked reviewed")
        page.head.caption.setToolTip("The period runs back from the latest dated report, so "
                                     "an imported history reads as it was, not as empty weeks.")

        picked = [rows[index] for index in chosen]
        total = len(picked)
        sif = sum(1 for row in picked if row.get("sif_potential"))
        risks = [float(row.get("risk_score") or 0) for row in picked]
        critical = sum(1 for risk in risks if risk >= CRITICAL)
        needs_info = sum(1 for index in chosen
                         if decisions[index] and decisions[index].get("decision") == "unclear")
        page.set_stats((
            (total, "analysed", False),
            (sif, f"{sif * 1000 // total / 10 if total else 0}% \u00b7 engine", False),
            (f"{sum(risks) / total:.1f}" if total else "-", "0\u2013100, ordinal", False),
            (critical, "score \u2265 85", bool(critical)),
            (self.outstanding_reviews, f"+{needs_info} needs info \u00b7 now", False),
        ))

        rules = Counter(self._sentence(row.get("iogp_rule") or "Unclassified")
                        for row in picked if row.get("sif_potential"))
        energies: Counter = Counter()
        barriers: Counter = Counter()
        flagged: Counter = Counter()
        for row in picked:
            if row.get("high_energy"):
                for part in str(row.get("energy_source") or "").split(" + "):
                    if part.strip():
                        energies[part.strip()] += 1
            if row.get("barrier_failed"):
                for part in str(row.get("barrier_failure") or "").split(";"):
                    if part.strip():
                        barriers[part.strip()[0].upper() + part.strip()[1:]] += 1
            if row.get("sif_potential"):
                flagged[str(row.get("activity") or "Unspecified activity")] += 1
        page.set_charts(rules.most_common(9), energies.most_common(8),
                        barriers.most_common(8), flagged.most_common(8))
        sif_series, critical_series, labels = weekly_series(picked)
        page.set_trend(sif_series, critical_series, labels)

        order = sorted(chosen, key=lambda i: (str(rows[i].get("reported_on")
                                                  or rows[i].get("analysed_at") or ""), i),
                       reverse=True)
        recent = []
        for index in order[:30]:
            row = dict(rows[index])
            risk = float(row.get("risk_score") or 0)
            row["risk_text"] = f"\u25b2 {risk:.0f}" if risk >= CRITICAL else f"{risk:.0f}"
            text, tone = review_status(row, decisions[index])
            short = {"Awaiting review": "Awaiting", "Closed \u00b7 not queued": "Not queued",
                     "? Needs info": "Needs info"}.get(text, text)
            if text.startswith("\u2713"):
                short = f"\u2713 SIF \u00b7 {text.rsplit(' ', 1)[-1]}"
            row["status"] = (short, tone)
            recent.append(row)
        page.set_recent(recent)

    def _attention(self, critical, by_ref, now) -> List[Tuple[str, str, str, str, str, str]]:
        items: List[Tuple[str, str, str, str, str, str]] = []
        for item in critical:
            reference = str(item.get("reference", ""))
            row = by_ref.get(reference, {})
            waited = age(queued_at(row), now)
            items.append(("critical",
                          f"{reference} · Critical {float(item.get('risk_score') or 0):.0f}.",
                          case_line(row) + (f" Waiting {waited}." if waited else ""),
                          "Review case", "review", reference))
        intelligence = self._intelligence
        for spot in (intelligence.hotspots if intelligence is not None else [])[:40]:
            data = spot.to_dict()
            if data.get("kind") != "barrier" or int(data.get("reports") or 0) < 3:
                continue
            items.append(("warn", "Repeat barrier failure.",
                          f"{data.get('label')} — {data.get('reports')} reports, "
                          f"{float(data.get('sif_rate') or 0):.0f}% with fatal potential.",
                          "Open hotspot", "hotspot", str(data.get("label"))))
            break
        for row in self.rows:
            if looks_non_latin(str(row.get("raw_text", ""))) and not row.get("translated_text"):
                items.append(("warn", "Not translated.",
                              f"{row.get('reference')} was analysed in its original wording; "
                              "the local LLM was not available to translate it.",
                              "Open report", "report", str(row.get("reference"))))
                break
        failed = [doc for doc in self.documents if doc.get("backend") == "failed"]
        if failed:
            items.append(("fail", "Extraction failed.",
                          f"{failed[-1].get('name')} — {failed[-1].get('note')}",
                          "Open in Ingest", "ingest", ""))
        overdue = self.actions.overdue() if hasattr(self, "actions") else []
        if overdue:
            first = overdue[0]
            items.append(("warn", "Overdue action items.",
                          f"{len(overdue)} open from the last fortnight, the oldest "
                          f"“{first.action.title}” on "
                          f"{first.day.strftime('%d %b').lstrip('0')}.",
                          "Open action items", "actions", ""))
        return items


class IngestFlow:
    """Staged files, a queue of jobs, and what each document went through.

    The controller runs one background task at a time, so the page's files are
    worked through as a queue: a document is read (text layer, then OCR), then -
    when "analyse after extraction" is on - its blocks are analysed; a CSV is
    analysed row by row. Every file keeps its own record: stage, status, how
    many reports it produced, its text and a processing log.
    """

    def _build_ingest(self) -> IngestPage:
        from sif.ocr import LANGUAGE_CHOICES

        self.ingest_items: List[Dict[str, object]] = []
        self._ingest_jobs: List[Tuple] = []
        self._ingest_selected = -1
        self.analyse_after_extraction = True
        self.csv_rows_as_reports = True
        page = IngestPage(LANGUAGE_CHOICES)
        page.files_chosen.connect(self.stage_files)
        page.process_requested.connect(self.start_processing)
        page.narrative_submitted.connect(self.submit_narrative)
        page.seed_requested.connect(self.load_seed_data)
        page.language_changed.connect(self.change_language)
        page.translate_toggled.connect(self.set_translation)
        page.analyse_after_toggled.connect(lambda on: setattr(self, "analyse_after_extraction", on))
        page.csv_rows_toggled.connect(lambda on: setattr(self, "csv_rows_as_reports", on))
        page.document_selected.connect(self._select_ingest)
        page.retry_requested.connect(self.retry_item)
        page.remove_requested.connect(self.remove_item)
        page.analyse_requested.connect(self.analyse_item)
        return page

    # -- staging and the queue ---------------------------------------------------

    def _new_item(self, name: str, kind: str, path: str = "") -> Dict[str, object]:
        suffix = os.path.splitext(name)[1].lower().lstrip(".")
        item = {"name": name, "path": path, "kind": kind,
                "type": {"jpeg": "JPG", "tif": "TIFF", "md": "TXT"}.get(suffix, suffix.upper())
                or "TXT",
                "pages": "", "language": "", "ocr": "", "stage": "Upload", "state": "queued",
                "reports": 0, "blocks": 0, "text": "", "source": "", "log": [],
                "note": "", "document": None, "references": []}
        self._log(item, f"received {name}")
        return item

    @staticmethod
    def _log(item: Dict[str, object], message: str) -> None:
        item["log"].append(f"{datetime.now().strftime('%H:%M:%S')}  {message}")

    @requires(ANALYSE)
    def stage_files(self, paths: List[str]) -> int:
        """Add files to the list; they wait for Start processing."""
        from main import read_csv_records

        known = {item.get("path") for item in self.ingest_items}
        added = 0
        for path in paths:
            if not path or path in known or not os.path.isfile(path):
                continue
            name = os.path.basename(path)
            csv = name.lower().endswith((".csv", ".tsv"))
            item = self._new_item(name, "csv" if csv else "doc", path)
            if csv:
                try:
                    count = len(read_csv_records(path)[0])
                    item["pages"] = f"{count} rows"
                    item["ocr"] = "Not needed"
                except Exception as exc:  # noqa: BLE001 - shown on the row
                    item["state"], item["note"] = "failed", str(exc)
            self.ingest_items.append(item)
            added += 1
        self.audit.functionality("files staged", count=added)
        self._refresh_ingest()
        return added

    @requires(ANALYSE)
    def start_processing(self) -> int:
        """Queue every staged file and start on the first."""
        queued = [item for item in self.ingest_items if item["state"] == "queued"]
        for item in queued:
            item["state"] = "waiting"
            if item["kind"] == "csv" and self.csv_rows_as_reports:
                self._ingest_jobs.append(("csv", item))
            else:
                self._ingest_jobs.append(("extract", item))
        self._ingest_next()
        self._refresh_ingest()
        return len(queued)

    @requires(ANALYSE)
    def submit_narrative(self, text: str, reference: str = "") -> None:
        blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
        if not blocks:
            return
        item = self._new_item("Pasted narrative", "paste")
        item.update(type="TXT", pages=str(len(blocks)), ocr="Not needed", text=text,
                    source=text, state="waiting")
        self.ingest_items.append(item)
        references = [reference] if reference and len(blocks) == 1 else []
        self._ingest_jobs.append(("analyse", item, blocks, references))
        self.ingest_page.clear_narrative()
        self._ingest_next()
        self._refresh_ingest()

    def load_seed_data(self) -> None:
        """The five seed incidents, as one pasted item - so they show in the list."""
        if not self.permitted(ANALYSE, "load_seed_data"):
            return
        item = self._new_item("Seed incidents", "paste")
        item.update(type="TXT", pages=str(len(SEED_REPORTS)), ocr="Not needed",
                    text="\n\n".join(SEED_REPORTS), source="\n\n".join(SEED_REPORTS),
                    state="waiting")
        self.ingest_items.append(item)
        references = [f"SEED-{number:02d}" for number in range(1, len(SEED_REPORTS) + 1)]
        self._ingest_jobs.append(("analyse", item, list(SEED_REPORTS), references))
        self._ingest_next()
        if getattr(self, "_shell_ready", False):
            self._refresh_ingest()

    @requires(ANALYSE)
    def retry_item(self, index: int) -> None:
        if 0 <= index < len(self.ingest_items):
            item = self.ingest_items[index]
            if item["kind"] == "paste" or self.worker is not None and item["state"] == "processing":
                return
            item["state"] = "waiting"
            self._log(item, "read again on request")
            self._ingest_jobs.append(("csv" if item["kind"] == "csv" and self.csv_rows_as_reports
                                      else "extract", item))
            self._ingest_next()
            self._refresh_ingest()

    @requires(ANALYSE)
    def analyse_item(self, index: int) -> None:
        if not 0 <= index < len(self.ingest_items):
            return
        item = self.ingest_items[index]
        document = item.get("document") or {}
        blocks = list(document.get("_blocks") or [])
        if not blocks:
            self._set_status(f"No text is waiting to be analysed from {item['name']}.")
            return
        self._queue_blocks(item, blocks)
        self._ingest_next()
        self._refresh_ingest()

    @requires(ANALYSE)
    def remove_item(self, index: int) -> None:
        if 0 <= index < len(self.ingest_items):
            item = self.ingest_items[index]
            if item["state"] in ("processing", "waiting"):
                return
            self.ingest_items.pop(index)
            if item.get("document") in self.documents:
                self.documents.remove(item["document"])
                self._sync_pending_blocks()
            self._refresh_ingest()

    def _queue_blocks(self, item: Dict[str, object], blocks: List[str]) -> None:
        stem = os.path.splitext(str(item["name"]))[0][:18] or "DOC"
        references = [f"{stem}-{number:02d}" for number in range(1, len(blocks) + 1)]
        document = item.get("document")
        if document is not None:
            document["_blocks"] = []
            self._sync_pending_blocks()
        item["state"] = "waiting"
        self._ingest_jobs.insert(0, ("analyse", item, blocks, references))

    def _ingest_next(self) -> None:
        if self.worker is not None or not self._ingest_jobs:
            return
        job = self._ingest_jobs.pop(0)
        kind, item = job[0], job[1]
        item["state"] = "processing"
        self._current_item = item
        if kind == "extract":
            suffix = os.path.splitext(str(item["name"]))[1].lower()
            item["stage"] = "OCR" if suffix in IMAGE_SUFFIXES + PDF_SUFFIXES else "Extract"
            self._log(item, "reading the text layer" if suffix in PDF_SUFFIXES
                      else "running OCR" if suffix in IMAGE_SUFFIXES else "reading the file")
            worker = ExtractionWorker(self.extractor, [str(item["path"])], parent=self)
            worker.document_ready.connect(lambda payload, it=item: self._document_read(it, payload))
            worker.failed.connect(self.on_failed)
            self._start(worker, f"Reading {item['name']}")
        else:
            item["stage"] = "Analyse"
            if kind == "csv":
                self._log(item, f"analysing {item['pages']} as separate reports")
                worker = self._analysis_worker(csv_path=str(item["path"]))
            else:
                blocks, references = job[2], job[3]
                self._log(item, f"analysing {len(blocks)} block(s)")
                worker = self._analysis_worker(texts=blocks, references=references)
            worker.completed.connect(lambda count, it=item: self._item_analysed(it, count))
            self._start(worker, f"Analysing {item['name']}")
        if self.worker is not None:
            self.worker.finished.connect(self._ingest_after)
        else:  # refused to start - put it back as it was
            item["state"] = "queued"
        self._refresh_ingest()

    def _ingest_after(self) -> None:
        item = getattr(self, "_current_item", None)
        if item is not None and item["state"] == "processing":
            item["state"] = "failed"
            self._log(item, "stopped before it finished")
        self._current_item = None
        QTimer.singleShot(0, self._after_job)

    def _after_job(self) -> None:
        self._ingest_next()
        self._refresh_ingest()

    def _document_read(self, item: Dict[str, object], payload: Dict[str, object]) -> None:
        self.on_document_ready(payload)
        item["document"] = payload
        text = str(payload.get("_text", ""))
        blocks = list(payload.get("_blocks") or [])
        item["text"] = item["source"] = text
        item["blocks"] = len(blocks)
        pages = payload.get("pages") or 1
        item["pages"] = str(pages)
        backend = str(payload.get("backend", ""))
        confidence = payload.get("confidence")
        if backend == "failed":
            item["state"], item["stage"] = "failed", "OCR"
            item["ocr"] = "Could not read"
            item["note"] = str(payload.get("note", ""))
            self._log(item, f"failed: {item['note']}")
            return
        item["ocr"] = ("Not needed" if backend in ("text", "plain text") else
                       f"{backend}" + (f" \u00b7 conf {float(confidence) * 100:.0f}%"
                                       if isinstance(confidence, (int, float)) and confidence else ""))
        non_english = looks_non_latin(text)
        item["language"] = (f"{self.language.split(' /')[0]} \u2192 English"
                            if non_english and self.translate_enabled
                            else self.language.split(" /")[0] if non_english else "English")
        self._log(item, f"read via {backend}: {len(text)} characters, {len(blocks)} block(s)")
        if not blocks:
            item["state"], item["stage"] = "attention", "Extract"
            item["note"] = "no readable text"
            return
        if isinstance(confidence, (int, float)) and 0 < confidence < 0.70:
            item["state"], item["stage"] = "attention", "Extract"
            item["note"] = f"low OCR confidence {confidence:.2f} - check the text"
            self._log(item, "held for a text check (confidence below 0.70)")
            return
        if self.analyse_after_extraction:
            self._queue_blocks(item, blocks)
        else:
            item["state"], item["stage"] = "extracted", "Extract"

    def _item_analysed(self, item: Dict[str, object], count: int) -> None:
        references = list(self._batch_refs)
        item["references"] = references
        item["reports"] = count
        item["state"], item["stage"] = "done", "Review"
        for reference in references:
            index, row = self._row_for(reference)
            if row is not None and not row.get("source"):
                row["source"] = item["name"]
        translated = [row for row in self.rows if str(row.get("reference")) in references
                      and row.get("translated_text")]
        if translated:
            item["translated"] = "\n\n".join(str(row["translated_text"]) for row in translated)
        if not item.get("language"):
            produced = [row for row in self.rows if str(row.get("reference")) in references]
            foreign = any(looks_non_latin(str(row.get("raw_text", ""))) for row in produced)
            name = self.language.split(" /")[0]
            item["language"] = ((f"{name} \u2192 English" if translated else name)
                                if foreign else "English")
        self._log(item, f"analysed: {count} report(s)")

    # -- the page ------------------------------------------------------------------------

    def _select_ingest(self, index: int) -> None:
        self._ingest_selected = index
        self._show_ingest_detail()

    def _show_ingest_detail(self) -> None:
        page = self.ingest_page
        if not 0 <= self._ingest_selected < len(self.ingest_items):
            page.set_detail("", "", "", "", "")
            return
        item = self.ingest_items[self._ingest_selected]
        caption, text = "", str(item.get("text") or "")
        if item.get("translated"):
            caption = (f"ENGLISH \u2014 TRANSLATED FROM {self.language.split(' /')[0].upper()} "
                       "FOR REVIEW \u00b7 original kept as the record")
            text = str(item["translated"])
        elif item["kind"] == "csv":
            caption = f"CSV EXPORT \u00b7 {item.get('pages')} \u00b7 each row analysed as a report"
            refs = item.get("references") or []
            text = ("Reports produced: " + ", ".join(refs)) if refs else "Not analysed yet."
        page.set_detail(str(item["name"]), caption, text, str(item.get("source") or ""),
                        "\n".join(item["log"]))

    STATUS = {
        "queued": ("Queued", "grey"),
        "waiting": ("Waiting", "grey"),
        "processing": ("\u25cc Processing", "info"),
        "done": ("\u2713 Completed", "ok"),
        "failed": ("\u2715 Failed", "fail"),
        "attention": ("\u25c6 Needs attention", "warn"),
        "extracted": ("Extracted", "info"),
    }

    def _refresh_ingest(self) -> None:
        if not hasattr(self, "ingest_page"):
            return
        page = self.ingest_page
        rows = []
        for item in self.ingest_items:
            text, tone = self.STATUS[str(item["state"])]
            extra = ""
            if item["state"] == "done":
                extra = f"{item['reports']} report{'s' if item['reports'] != 1 else ''}"
            elif item["state"] == "failed":
                extra = "see the log"
            elif item["state"] == "attention":
                note = str(item.get("note", ""))
                extra = note if len(note) <= 16 else note[:15] + "…"
            elif item["state"] == "extracted":
                extra = f"{item['blocks']} block(s)"
            rows.append({**item, "language": item.get("language") or "\u2014",
                         "status": (text, tone, extra)})
        processing = sum(1 for item in self.ingest_items if item["state"] in ("processing", "waiting"))
        failed = sum(1 for item in self.ingest_items if item["state"] == "failed")
        attention = sum(1 for item in self.ingest_items if item["state"] == "attention")
        page.set_documents(rows, f"this session \u00b7 {len(rows)} item{'s' if len(rows) != 1 else ''}",
                           processing, failed, attention)
        staged = sum(1 for item in self.ingest_items if item["state"] == "queued")
        page.set_staged(staged, self.worker is not None)
        ocr_active = sum(1 for item in self.ingest_items
                         if item["state"] == "processing" and item["stage"] == "OCR")
        held = attention + sum(1 for item in self.ingest_items if item["state"] == "extracted")
        untranslated = sum(1 for row in self.rows if looks_non_latin(str(row.get("raw_text", "")))
                           and not row.get("translated_text"))
        running = sum(1 for item in self.ingest_items
                      if item["state"] == "processing" and item["stage"] == "Analyse")
        page.set_pipeline((f"{len(self.ingest_items)} received",
                           f"{ocr_active} active / {failed} failed",
                           f"{held} held", f"{untranslated} pending", f"{running} running",
                           f"{self.outstanding_reviews} awaiting a person"))
        page.set_engines(self._engine_line())
        self._show_ingest_detail()

    def _engine_line(self) -> str:
        status = self.extractor.status()
        if "disabled" in status:
            ocr = "off (text layer only)"
        elif "unavailable" in status or "not usable" in status:
            ocr = "PaddleOCR unavailable"
        else:
            ocr = "PaddleOCR ready"
        if self.llm_online:
            llm = f"{self.llm.model} running"
        elif self.llm_enabled or self.translate_enabled:
            llm = f"{self.llm.model} not reached"
        else:
            llm = "off"
        intelligence = self._intelligence
        encoder = (str(intelligence.kpis.get("encoder", "")).split(":")[0]
                   if intelligence is not None and intelligence.kpis.get("encoder") else "ready")
        return f"OCR: {ocr} \u00b7 LLM: {llm} \u00b7 Encoder: {encoder}"
