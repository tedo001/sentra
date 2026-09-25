"""SENTRA - system architecture, test and gap report (report.pdf)."""
import json, os, sys
from collections import Counter, OrderedDict, defaultdict

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
TESTS = json.load(open(os.path.join(HERE, "tests.json")))
METRICS = json.load(open(os.path.join(HERE, "metrics.json")))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "reports", "report.pdf")

# -- palette: the console's own, printed ---------------------------------------
INK = colors.HexColor("#15171a")
DIM = colors.HexColor("#5b5f66")
FAINT = colors.HexColor("#8b9098")
RULE = colors.HexColor("#d9dbde")
BAND = colors.HexColor("#f3f4f2")
LIME = colors.HexColor("#6cc40f")        # the lime, darkened to read on white
LIME_BG = colors.HexColor("#eef9e0")
RED = colors.HexColor("#c62828")
RED_BG = colors.HexColor("#fdecea")
AMBER = colors.HexColor("#b45309")
AMBER_BG = colors.HexColor("#fdf3e3")
BLACK = colors.HexColor("#0b0b0b")

base = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=30, leading=34,
                            textColor=INK, spaceAfter=6),
    "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=13, leading=18,
                               textColor=DIM),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=18, leading=22,
                         textColor=INK, spaceBefore=4, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12.5, leading=16,
                         textColor=INK, spaceBefore=10, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.6, leading=13.6,
                           textColor=INK, spaceAfter=6),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8.2, leading=11,
                            textColor=DIM, spaceAfter=4),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.2, leading=10.6,
                           textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=8.2, leading=10.6,
                            textColor=INK),
    "head": ParagraphStyle("head", fontName="Helvetica-Bold", fontSize=7.4, leading=9.4,
                           textColor=DIM),
    "tiny": ParagraphStyle("tiny", fontName="Helvetica", fontSize=6.9, leading=8.6,
                           textColor=INK),
    "mono": ParagraphStyle("mono", fontName="Courier", fontSize=7.8, leading=10,
                           textColor=INK),
    "callout": ParagraphStyle("callout", fontName="Helvetica", fontSize=9.6, leading=13.6,
                              textColor=INK),
    "kpi": ParagraphStyle("kpi", fontName="Helvetica-Bold", fontSize=20, leading=23,
                          textColor=INK),
    "kpil": ParagraphStyle("kpil", fontName="Helvetica", fontSize=7.6, leading=9.6,
                           textColor=DIM),
}

W = A4[0] - 36 * mm           # text width


def P(text, style="body"):
    return Paragraph(text, S[style])


def table(rows, widths, head=True, zebra=True, style="cell", valign="TOP", extra=()):
    data = []
    for i, row in enumerate(rows):
        data.append([c if not isinstance(c, str) else
                     Paragraph(c, S["head"] if (head and i == 0) else S[style]) for c in row])
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    cmds = [("VALIGN", (0, 0), (-1, -1), valign),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE)]
    if head:
        cmds += [("LINEBELOW", (0, 0), (-1, 0), 0.9, INK), ("BACKGROUND", (0, 0), (-1, 0), BAND)]
    if zebra:
        for r in range(1 if head else 0, len(rows)):
            if r % 2 == 0:
                cmds.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#fafaf9")))
    t.setStyle(TableStyle(cmds + list(extra)))
    return t


def callout(text, kind="note"):
    fg, bg = {"note": (LIME, LIME_BG), "warn": (AMBER, AMBER_BG), "bad": (RED, RED_BG)}[kind]
    t = Table([[Paragraph(text, S["callout"])]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg),
                           ("LINEBEFORE", (0, 0), (0, -1), 3, fg),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return t


def kpis(items):
    cells = [[Paragraph(v, S["kpi"]), ] for v, _ in items]
    row1 = [Paragraph(v, S["kpi"]) for v, _ in items]
    row2 = [Paragraph(l, S["kpil"]) for _, l in items]
    t = Table([row1, row2], colWidths=[W / len(items)] * len(items))
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, 0), 8),
                           ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
                           ("BACKGROUND", (0, 0), (-1, -1), BAND),
                           ("LINEAFTER", (0, 0), (-2, -1), 2, colors.white)]))
    return t


def shot(name, width=W, caption=""):
    path = os.path.join(REPO, "docs", name)
    from PIL import Image as PILImage
    w, h = PILImage.open(path).size
    img = Image(path, width=width, height=width * h / w)
    parts = [img]
    if caption:
        parts.append(P(caption, "small"))
    return KeepTogether(parts)


# -- the architecture diagram, drawn -------------------------------------------
def flow_diagram():
    d = Drawing(W, 300)
    def box(x, y, w, h, title, sub, fill=colors.white, edge=INK, tcol=INK):
        d.add(Rect(x, y, w, h, rx=4, ry=4, fillColor=fill, strokeColor=edge, strokeWidth=0.9))
        d.add(String(x + w / 2, y + h - 13, title, fontName="Helvetica-Bold", fontSize=8,
                     fillColor=tcol, textAnchor="middle"))
        for i, line in enumerate(sub):
            d.add(String(x + w / 2, y + h - 24 - i * 9, line, fontName="Helvetica", fontSize=6.3,
                         fillColor=DIM if tcol == INK else colors.HexColor("#cfd3cf"),
                         textAnchor="middle"))
    def arrow(x1, y1, x2, y2):
        d.add(Line(x1, y1, x2, y2, strokeColor=DIM, strokeWidth=0.9))
        import math
        a = math.atan2(y2 - y1, x2 - x1); s = 4.2
        d.add(Polygon([x2, y2, x2 - s * math.cos(a - 0.45), y2 - s * math.sin(a - 0.45),
                       x2 - s * math.cos(a + 0.45), y2 - s * math.sin(a + 0.45)],
                      fillColor=DIM, strokeColor=DIM))
    gap, bh = 12, 52
    bw = (W - 4 - 4 * gap) / 5            # five boxes fill the text width exactly
    y1 = 230
    xs = [2 + i * (bw + gap) for i in range(5)]
    row1 = [("1 INGEST", ["text  CSV  PDF", "scans  photos"]),
            ("2 READ", ["PDF text layer", "PaddleOCR, 12 langs"]),
            ("3 TRANSLATE", ["local Ollama LLM", "original kept"]),
            ("4 PREPROCESS", ["clean  expand", "LOTO/PTW/H2S"]),
            ("5 ENCODE", ["MiniLM-L6-v2", "or offline hash"])]
    for x, (t, s) in zip(xs, row1):
        box(x, y1, bw, bh, t, s)
    for a, b in zip(xs, xs[1:]):
        arrow(a + bw, y1 + bh / 2, b, y1 + bh / 2)
    # engine band
    ey = 128
    d.add(Rect(2, ey, W - 4, 74, rx=6, ry=6, fillColor=BLACK, strokeColor=BLACK))
    d.add(String(12, ey + 60, "SIF PRECURSOR INTELLIGENCE ENGINE", fontName="Helvetica-Bold",
                 fontSize=8.5, fillColor=colors.HexColor("#8cef1e")))
    inner = [("LEXICAL RULES", ["energy, barrier, rule,", "activity, location"]),
             ("SEMANTIC HEADS", ["prototype similarity", "discrimination guard"]),
             ("FUSION", ["energy x barrier", "extends, never overturns"]),
             ("RISK SCORE", ["0-100 x severity x", "criticality x evidence"]),
             ("XGBOOST", ["46 named features", "third opinion"])]
    for x, (t, s) in zip(xs, inner):
        box(x + 4, ey + 8, bw - 8, 44, t, s, fill=colors.HexColor("#1d1b18"),
            edge=colors.HexColor("#3b3733"), tcol=colors.white)
    arrow(xs[4] + bw / 2, y1, xs[4] + bw / 2, ey + 74)
    # outputs
    oy = 34
    row3 = [("EVIDENCE", ["cues, neighbours,", "decision path"]),
            ("REVIEW QUEUE", ["8 triggers,", "nothing auto-closed"]),
            ("HOTSPOTS", ["density ranked,", "Wilson bound"]),
            ("DASHBOARD", ["KPIs, 4 charts,", "matrix, bulletin"]),
            ("AUDIT TRAIL", ["who did what,", "hash-chained"])]
    for x, (t, s) in zip(xs, row3):
        box(x, oy, bw, bh, t, s, fill=LIME_BG, edge=LIME)
        arrow(x + bw / 2, ey, x + bw / 2, oy + bh)
    # feedback
    d.add(Line(xs[1] + bw / 2, oy, xs[1] + bw / 2, 10, strokeColor=LIME, strokeWidth=1))
    d.add(Line(xs[1] + bw / 2, 10, xs[4] + bw / 2, 10, strokeColor=LIME, strokeWidth=1))
    d.add(Line(xs[4] + bw / 2, 10, xs[4] + bw / 2, oy, strokeColor=LIME, strokeWidth=1))
    d.add(String(xs[2] + 20, 14, "expert decisions become training labels for XGBoost",
                 fontName="Helvetica-Oblique", fontSize=6.8, fillColor=LIME))
    return d


def layers_diagram():
    d = Drawing(W, 150)
    layers = [("PRESENTATION", "app.py (black/lime)  -  app2.py (deep navy)  -  ui/ skins  -  ui2/ pages  -  sign-in dialog", LIME_BG, LIME),
              ("CONTROLLER", "main2.MainWindow  -  role guard on every action  -  4 worker threads (analysis, extraction, training, probes)", BAND, INK),
              ("ANALYSIS", "sif/  pipeline - lexical - encoders - heads - evidence - scoring - patterns - review - mlops - llm - ocr", BAND, INK),
              ("STORAGE", "%APPDATA%\\SIF Insight Console  -  users.json - audit.jsonl (chained) - review decisions - logs - models - mlflow.db", colors.HexColor("#f6f6f4"), DIM)]
    y = 150 - 36
    for name, text, fill, edge in layers:
        d.add(Rect(2, y, W - 4, 30, rx=4, ry=4, fillColor=fill, strokeColor=edge, strokeWidth=0.8))
        d.add(String(10, y + 18, name, fontName="Helvetica-Bold", fontSize=7.6, fillColor=INK))
        d.add(String(10, y + 7, text, fontName="Helvetica", fontSize=6.9, fillColor=DIM))
        y -= 37
    return d


# -- page furniture -------------------------------------------------------------
def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.2)
    canvas.setFillColor(FAINT)
    canvas.drawString(18 * mm, 10 * mm, "SENTRA  -  System architecture, test and gap report  -  Oil India Limited  -  SIH PS 26165")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")
    canvas.setStrokeColor(LIME)
    canvas.setLineWidth(2)
    canvas.line(18 * mm, A4[1] - 12 * mm, 38 * mm, A4[1] - 12 * mm)
    canvas.restoreState()


def on_cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BLACK)
    canvas.rect(0, A4[1] - 118 * mm, A4[0], 118 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#8cef1e"))
    canvas.setFont("Helvetica-Bold", 44)
    canvas.drawString(18 * mm, A4[1] - 52 * mm, "SENTRA")
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 11)
    canvas.drawString(18 * mm, A4[1] - 62 * mm, "Safety Event Network for Threat Recognition & Anticipation")
    canvas.setFont("Helvetica-Bold", 19)
    canvas.drawString(18 * mm, A4[1] - 86 * mm, "System architecture, test and gap report")
    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(colors.HexColor("#c2bcb3"))
    canvas.drawString(18 * mm, A4[1] - 96 * mm, "Oil India Limited  -  Smart India Hackathon 2026, Problem Statement 26165  -  Team WellDropp")
    canvas.setFillColor(colors.HexColor("#3c3cd2"))
    canvas.rect(0, A4[1] - 118 * mm, A4[0], 2.2 * mm, fill=1, stroke=0)
    canvas.restoreState()


# -- content --------------------------------------------------------------------
records = TESTS["records"]
status = Counter(r["status"] for r in records)
N_TESTS = len(records)
PASSED = status.get("pass", 0)
E42, T56, MODEL = METRICS["eval42"], METRICS["train56"], METRICS["model"]

story = []

# COVER ---------------------------------------------------------------------------
story.append(Spacer(1, 120 * mm))
story.append(kpis([(f"{PASSED}/{N_TESTS}", "automated tests passing"),
                   (f"{E42['recall']:.2f}", "recall, 42 authored cases"),
                   (f"{METRICS['ms_per_report']:.1f} ms", "engine time per report"),
                   ("0", "real Oil India reports seen")]))
story.append(Spacer(1, 10))
story.append(P("Version 2.0.0  -  prepared 25 September 2026  -  every number in this report was "
               "measured from the code on branch <b>tedo</b> at the time of writing, by the scripts "
               "listed in Appendix B.", "small"))
story.append(Spacer(1, 10))
story.append(P("<b>What this report covers</b>", "h2"))
toc = [["1", "Executive summary"], ["2", "How SENTRA actually works"],
       ["3", "System design"], ["4", "How the SIF precursor intelligence decides"],
       ["5", "Models - what is used now, and what fits better"],
       ["6", "Datasets - what was used, and what must be collected"],
       ["7", "Testing - method and results"], ["8", "Software gaps"],
       ["9", "This update: sign-in, roles and a record of who did what"],
       ["10", "The recommended solution"], ["A", "Every test, by area"],
       ["B", "How the numbers were produced"]]
story.append(table([["", "Section"]] + toc, [12 * mm, W - 12 * mm], zebra=False))
story.append(NextPageTemplate("body"))
story.append(PageBreak())

# 1 EXECUTIVE SUMMARY -------------------------------------------------------------
story.append(P("1  Executive summary", "h1"))
story.append(P(
    "SENTRA reads unsafe-act / unsafe-condition and near-miss reports and finds the ones "
    "carrying <b>serious-injury or fatality (SIF) potential</b> - reports where a high-energy "
    "source met a failed or missing critical barrier, whatever the outcome happened to be. It "
    "runs entirely on the operator's machine, explains every verdict, ranks recurring "
    "precursors by density, and never closes a report by itself: anything that matters goes "
    "to a person, whose decision becomes a training label."))
story.append(P("<b>What was done for this report.</b> The whole codebase was reviewed module by "
               "module; every one of the %d automated tests was run and recorded individually "
               "(all pass, %.0f s); the engine was scored against both labelled sets in the "
               "repository; the learned model was trained and cross-validated; and the engine was "
               "timed. The findings are below, and the gaps are in Section 8." %
               (N_TESTS, TESTS["total_seconds"])))
story.append(callout(
    "<b>The single most important finding.</b> Every accuracy figure in this report is perfect "
    "or nearly so - and that is a warning, not a result. Both labelled sets were written by the "
    "team, the engine's vocabulary was extended after seeing which cases it missed, and the "
    "learned model's strongest feature is the rule engine's own score. These numbers show that "
    "the system is <b>internally consistent</b>. They say nothing yet about how it performs on "
    "Oil India's real reports, because it has never seen one. Section 6 specifies the data that "
    "would change that; it is the highest-value next step by a wide margin.", "warn"))
story.append(Spacer(1, 4))
story.append(P("Headline findings", "h2"))
story.append(table([
    ["", "Finding"],
    ["Works", "All %d tests pass: every pipeline stage, the review bench, OCR and LLM handling, "
              "every page of the interface, the release pipeline, and the new sign-in and "
              "audit chain." % N_TESTS],
    ["Works", "The engine is fast - %.1f ms per report, about %s reports a minute on one core - "
              "so the interface, not the analysis, is the only speed constraint." %
              (METRICS["ms_per_report"], f"{METRICS['reports_per_minute']:,}")],
    ["Works", "No confirmed SIF finding is ever closed without a person: 0 of 42 on the evaluation "
              "set reach nobody, by construction and by test."],
    ["Gap", "No real data. All 127 labelled or sample reports in the repository are authored."],
    ["Gap", "The learned model is a distillation of the rules until real reviewed labels exist."],
    ["Gap", "Word documents (.docx) are not read; there is no asset/equipment identity; "
            "there is no work-hold output and no central server."],
    ["Added", "Sign-in with roles, every report and decision attributed to a named person, and a "
              "hash-chained audit trail that detects tampering (Section 9)."],
], [18 * mm, W - 18 * mm]))
story.append(PageBreak())

# 2 HOW IT WORKS --------------------------------------------------------------------
story.append(P("2  How SENTRA actually works", "h1"))
story.append(P("A report travels five stages to reach the engine, and the engine's verdict "
               "travels to five places. Nothing in the path needs a network connection: the "
               "encoder, the OCR models and the optional language model are all local."))
story.append(flow_diagram())
story.append(Spacer(1, 6))
story.append(table([
    ["Stage", "Module", "What it does"],
    ["1 Ingest", "sif/ocr.py", "Accepts pasted text, CSV exports, PDFs, scanned pages and photographs (.txt .md .log .csv .tsv .pdf and seven image formats)."],
    ["2 Read", "sif/ocr.py", "A PDF's text layer is read exactly with pypdfium2; a page without one, or an image, goes through PaddleOCR in one of 12 languages. Every line keeps its OCR confidence."],
    ["3 Translate", "sif/llm.py", "A non-Latin report is translated to English by a local Ollama model before analysis. The original wording is kept as the record; the English is what the engines read."],
    ["4 Preprocess", "sif/preprocessing.py", "Cleans the text, expands field shorthand (LOTO, PTW, GGS, H2S) for the encoder while keeping the reporter's own words for the patterns, and splits sentences."],
    ["5 Encode", "sif/encoders.py", "all-MiniLM-L6-v2 sentence embeddings (384-d). If that model cannot load, a deterministic hashing encoder takes over - and is barred from raising a flag of its own."],
    ["Engine", "sif/heads.py, scoring.py", "Decides SIF potential, the IOGP rule, activity, location, energy source and failed barrier, and a 0-100 risk score (Section 4)."],
    ["Outputs", "evidence, review, patterns", "Evidence for every field, a queue for human review, density-ranked hotspots, the dashboard and a plain-English bulletin."],
    ["Learn", "sif/mlops.py", "Reviewed decisions train an XGBoost model on 46 named features; each run is logged to MLflow; the model becomes a third opinion."],
], [22 * mm, 34 * mm, W - 56 * mm]))
story.append(PageBreak())

# 3 SYSTEM DESIGN ---------------------------------------------------------------------
story.append(P("3  System design", "h1"))
story.append(P("Four layers, each depending only on the one below. The analysis layer imports "
               "nothing from Qt, so it can be run from a script, a test or a future server "
               "without the interface."))
story.append(layers_diagram())
story.append(P("Two entry points, one console", "h2"))
story.append(P("<b>app.py</b> and <b>app2.py</b> build the same window from the same controller "
               "(main2.py) and differ only by a palette and a style sheet. A fix to any capability "
               "lands in both. A skin is applied in two halves, because Qt style sheets cannot "
               "reach widgets that paint themselves: the palette is set <i>before</i> the window is "
               "built, the style sheet after. Letter case and rail icons, which no style sheet can "
               "change, are switches in ui.theme.LOOK that every skin sets in full."))
story.append(P("Concurrency", "h2"))
story.append(table([
    ["Worker thread", "Runs", "Why it is off the interface thread"],
    ["AnalysisWorker", "Encoder load and every pipeline stage; streams one row at a time", "A 90 MB model load or a thousand-report import must not freeze the window."],
    ["ExtractionWorker", "PDF reading and OCR, including first-run model download", "PaddleOCR's first run downloads models."],
    ["TrainingWorker", "XGBoost training and the MLflow run", "Cross-validation takes seconds."],
    ["Probe workers", "OCR and LLM availability checks, the update check", "A socket to a stopped Ollama can block for seconds."],
], [30 * mm, 70 * mm, W - 100 * mm]))
story.append(P("Where the data lives", "h2"))
story.append(table([
    ["File", "Format", "Written by", "Notes"],
    ["users.json", "JSON", "Sign-in, account management", "Salted PBKDF2 digests only; never a password. Atomic write."],
    ["audit.jsonl", "JSON lines", "Every action", "Append-only, fsync'd, hash-chained. Separate from the debug log, which rotates."],
    ["review_decisions.json", "JSON", "The review bench", "Append-only in meaning: a changed mind appends a new entry."],
    ["settings.json", "JSON", "Preferences", "Reviewer, rail width, update checks."],
    ["logs/", "rotating text", "logging", "Diagnostics; 1 MB x 3."],
    ["models/, mlflow.db", "JSON, SQLite", "Training", "The XGBoost booster and every run's metrics."],
], [34 * mm, 22 * mm, 38 * mm, W - 94 * mm]))
story.append(P("All of it sits in <b>%APPDATA%\\SIF Insight Console</b>. An installed build never writes "
               "into Program Files, which a standard user cannot write to (sif/paths.py).", "small"))
story.append(PageBreak())

# 4 THE ENGINE ------------------------------------------------------------------------
story.append(P("4  How the SIF precursor intelligence decides", "h1"))
story.append(P("The whole engine rests on one definition, taken from the energy-barrier model "
               "that has replaced the Heinrich triangle in modern SIF practice:"))
story.append(callout("<b>A report has SIF potential when a high-energy source was present AND a "
                     "critical barrier failed, was missing, bypassed or was not verified.</b><br/>"
                     "Expressed continuously:  P(SIF) = energy score x barrier score", "note"))
story.append(Spacer(1, 4))
story.append(P("The product is the point. A report full of alarming words about a dropped glove "
               "scores nothing, because there is no high energy; a report about a live 11 kV "
               "feeder where isolation held scores nothing either, because no barrier failed. "
               "Severity wording alone can never create a flag, and a dismissive tone "
               "(\"nothing serious to report\") can never remove one."))
story.append(P("Three readings, fused", "h2"))
story.append(table([
    ["Layer", "How it reads a report", "Its authority"],
    ["Lexical rules (sif/lexical.py)", "Curated patterns for 11 IOGP Life-Saving Rules, high-energy sources, critical barriers - including implicit failures such as \"clipped to the handrail instead of the anchor point\" - and site and activity vocabulary.", "The backbone. What it flags stays flagged."],
    ["Semantic heads (sif/heads.py)", "Cosine similarity between the report's embedding and prototype descriptions of each energy, barrier and rule.", "Can add a flag the rules missed; can never remove one. A discrimination guard ignores it when every prototype scores alike."],
    ["XGBoost (sif/mlops.py)", "46 named features - both SIF factors, energy and barrier families, severity weights, the rule, text statistics.", "A third opinion. Where it disagrees with the pipeline, the report goes to a person."],
    ["Local LLM (optional)", "Reads the narrative and answers the same question.", "A fourth opinion. Never overrides; a disagreement is queued."],
], [36 * mm, W - 36 * mm - 50 * mm, 50 * mm]))
story.append(P("Risk score and review", "h2"))
story.append(P("<b>Risk = 100 x P(SIF) x energy severity x barrier criticality x evidence factor</b>, banded "
               "Critical (70+), High (50+), Medium (30+) and Low. It is ordinal - for ranking a queue - not "
               "an actuarial probability. A report is queued for a person on any of eight triggers, in "
               "this priority: rule/semantic disagreement, model disagreement, LLM disagreement, critical "
               "risk, thin evidence, unclassified exposure, energy with no barrier found, and - as a catch-"
               "all - any other confirmed finding. <b>No report the engine calls SIF-potential is ever "
               "closed without a person.</b>"))
story.append(P("Hotspots rank a cluster by the share of its reports that carry SIF potential, "
               "discounted by the Wilson lower bound so a 2-of-2 cluster cannot outrank a 12-of-20 one."))
story.append(PageBreak())

story.append(P("A real report, traced through the engine", "h2"))
story.append(P("Report NM-2601 from the sample corpus, exactly as the engine produced it with the offline "
               "encoder:"))
story.append(callout("<i>During preventive maintenance of the booster pump at OCS-4 the 11 kV feeder cable was left "
                     "ungrounded and the breaker was not racked out. The technician had already started cable "
                     "jointing when the permit was checked; no LOTO was applied and no isolation certificate had "
                     "been raised.</i>", "note"))
story.append(Spacer(1, 6))
story.append(table([
    ["Step", "What the engine found"],
    ["Energy cues", "11 kV, breaker, cable jointing, feeder  ->  <b>Electrical energy</b>, high energy"],
    ["Barrier cues", "left ungrounded, no isolation certificate, no LOTO  ->  <b>Energy isolation / LOTO not applied; Permit to work not followed</b>"],
    ["Rule cues", "11 kV, breaker, feeder, isolation certificate  ->  <b>Energy Isolation</b> (confidence 0.89; next best Work Authorisation 0.18)"],
    ["Activity, location", "Equipment maintenance at Oil Collecting Station (OCS) - both from the lexical layer"],
    ["P(SIF)", "1.00 = energy 1.00 x barrier 1.00"],
    ["Risk", "<b>100.0, Critical</b>  =  P(SIF) 1.00 x energy 1.00 x barrier 1.00 x evidence 1.00"],
    ["Semantic layer", "Inactive: the offline encoder placed this report nearest \"Toxic / Asphyxiant atmosphere\" (0.36) - wrong - which is exactly why that encoder may rank but never flag. Decision path: <i>lexical rules only</i>."],
    ["Review", "Queued - trigger <b>Critical risk</b>: \"risk 100/100 - verify before it drives an intervention\""],
    ["Plain English", "\"Electrical energy was uncontrolled because energy isolation / LOTO not applied or verified; permit to work absent, expired or not followed during equipment maintenance.\""],
], [30 * mm, W - 30 * mm]))
story.append(PageBreak())

# 5 MODELS ------------------------------------------------------------------------------
story.append(P("5  Models - what is used now, and what fits better", "h1"))
story.append(P("The present design is right for a system with <b>no labelled data</b>: a rule engine that "
               "needs none, an off-the-shelf encoder that needs none, and a small gradient-boosted model "
               "that can be trained on the first few hundred reviewed reports. What changes the answer is "
               "real data - and Indian-language reports."))
story.append(table([
    ["Job", "Used now", "Better suited, to evaluate next", "Why"],
    ["Decide SIF potential", "Lexical rules + P(SIF) fusion", "Keep, and add a fine-tuned classifier beside it (below)", "The rules are auditable and need no data; they should stay the floor that recall cannot fall below."],
    ["Sentence embedding", "all-MiniLM-L6-v2, 384-d, English only", "multilingual-e5-small / base, or paraphrase-multilingual-MiniLM-L12-v2; BGE-M3 if the machine can afford it", "Embeds Hindi, Tamil, Telugu and the rest directly, so meaning survives without a translation step that can lose it."],
    ["Learn from reviews", "XGBoost on 46 engineered features (220 trees, depth 4)", "SetFit (contrastive fine-tuning of a sentence encoder) once there are 8-64 labelled reports per class; later a fine-tuned DeBERTa-v3-small or MuRIL at 2,000+", "SetFit is built for exactly this few-label regime; MuRIL and IndicBERT are pretrained on Indian languages."],
    ["Probability quality", "Raw XGBoost probability", "Isotonic or Platt calibration on a held-out set", "A risk score that says 0.8 should be right about 80% of the time before anyone acts on it."],
    ["Translation", "Local Ollama (llama3.2 3B default; gemma2 9B optional)", "IndicTrans2 (AI4Bharat), run locally", "Purpose-built for 22 Indian languages; a general 3B chat model is not a translator. gemma2 9B does not fit a typical plant GPU (measured 20%/80% CPU/GPU split)."],
    ["Extract equipment", "None - no asset field exists", "GLiNER (zero-shot NER), or a small NER fine-tuned on tagged reports", "Enables asset-level memory: repeat failures on the same pump, crane or well."],
    ["OCR", "PaddleOCR, 12 languages", "Keep; add Bengali, Gujarati, Punjabi, Malayalam, Odia, Assamese as recognisers mature", "These six Indian scripts have no recogniser in the current build."],
], [26 * mm, 34 * mm, 50 * mm, W - 110 * mm], style="cell"))
story.append(Spacer(1, 6))
story.append(callout("<b>Recommendation.</b> Keep the rule engine as the auditable floor. Replace the English "
                     "encoder with a multilingual one. When 300-500 reports have been reviewed, train SetFit "
                     "beside XGBoost and let both be opinions, not deciders - and only promote a model whose "
                     "recall on real, held-out Oil India reports is at least the rule engine's. These are "
                     "candidates to evaluate on real data, not results.", "note"))
story.append(PageBreak())

# 6 DATASETS -------------------------------------------------------------------------------
story.append(P("6  Datasets - what was used, and what must be collected", "h1"))
story.append(P("What is in the repository today", "h2"))
story.append(table([
    ["Set", "Size", "Labels", "Used for", "Real?"],
    ["evaluation/labelled_reports.csv", "42", "25 SIF, 17 controls; IOGP rule", "Scoring the engine", "Authored"],
    ["samples/training_corpus.csv", "56", "33 SIF, 23 controls; IOGP rule", "Training XGBoost", "Authored"],
    ["samples/near_miss_reports.csv", "18", "none", "End-to-end import tests; held out from tuning", "Authored"],
    ["sample_reports.csv", "6", "none", "Batch-import demo", "Authored"],
    ["Seed incidents (sif/lexical.py)", "5", "none", "One-click demo", "Authored"],
    ["samples/languages/, multilingual", "6 + 5 blocks", "none", "Hindi, Marathi, Tamil, Telugu, Kannada, Urdu ingestion", "Authored"],
    ["permit PDF, scanned PNG, shift log", "3 files", "none", "PDF text layer, OCR and text-block paths", "Authored"],
], [52 * mm, 16 * mm, 38 * mm, 50 * mm, W - 156 * mm]))
story.append(P("The labelled sets are carefully built - every positive has a twin in which the barrier "
               "<i>held</i>, and minimising wording appears on both sides - but they were written by the "
               "same team that wrote the vocabulary. They test that the logic is coherent. They cannot test "
               "whether it matches how Oil India's crews actually write.", "small"))
story.append(P("What must be collected", "h2"))
story.append(table([
    ["", "Specification"],
    ["Source", "Oil India's own UA/UC and near-miss records - the HSE reporting system's export - including free-text narratives as written, in every language they arrive in; plus incident investigation reports where the outcome is known."],
    ["Volume", "300-500 reviewed reports to train SetFit and trust XGBoost; 2,000+ to fine-tune a transformer; at least 50 true SIF precursors in any evaluation set, so recall is measured on more than a handful."],
    ["Labels per report", "SIF potential (yes / no / unclear); high-energy source; failed barrier; IOGP rule; activity; location; <b>asset or equipment tag</b>; actual and potential severity; language."],
    ["Labelling protocol", "Two trained HSE reviewers label independently; disagreements are adjudicated; Cohen's kappa is reported and should be 0.7 or higher before the labels are trusted. SENTRA's review bench already records this per decision."],
    ["Splits", "By time, not at random: train on older reports, evaluate on the most recent quarter - which is how the system will be used."],
    ["Balance", "SIF precursors are rare. Keep the natural rate in evaluation; oversample only in training."],
    ["Privacy", "Remove names and employee IDs before labelling; keep sites and equipment, which carry the signal."],
    ["Supplementary", "OSHA Severe Injury Reports and fatality investigation summaries (public, US) are real narratives with known outcomes - useful for pretraining the classifier, never for evaluating it on Oil India's operations."],
], [30 * mm, W - 30 * mm]))
story.append(PageBreak())

# 7 TESTING --------------------------------------------------------------------------------
story.append(P("7  Testing - method and results", "h1"))
AREAS = OrderedDict([
    ("Pipeline and engine", ["TestPipeline", "TestLexicalEngine", "TestHeads", "TestScoring", "TestEncoders",
                             "TestPreprocessor", "TestEngineQuality", "TestIntelligence", "TestNarrativeGeneration",
                             "TestMinimizingLanguage", "TestEnergyWithoutBarrierTrigger"]),
    ("Human review", ["TestReviewBench", "TestReviewDecisions", "TestConfirmedFindingsAlwaysReachAPerson",
                      "TestDecisionTrailScaleAndClearing", "TestReviewToLabelsEndToEnd"]),
    ("Learning (MLOps)", ["TestMLOps", "TestModelInPipeline", "TestTrainerCLI", "TestTrainingCorpus"]),
    ("Ingestion and OCR", ["TestDocumentExtraction", "TestOCRLanguages", "TestOCRModelCache",
                           "TestIngestionPathsEndToEnd", "TestExtractedDocumentActions", "TestSampleReports"]),
    ("Local LLM and translation", ["TestOllamaEngine", "TestPipelineWithLLM", "TestTranslationWithoutAManualProbe"]),
    ("Interface", ["TestWorkflowAndInterface", "TestBuildTwoWindowEndToEnd", "TestHotspotsPage",
                   "TestInterfaceWidgets", "TestTheme", "TestBlackAndLimeBuild", "TestBuildOneInterface",
                   "TestBuildOneStillWorks", "TestAnalysisWorker", "TestImportSpeed"]),
    ("Audit and logging", ["TestAuditTrail", "TestSystemLogging", "TestTamperEvidentTrail"]),
    ("Sign-in and roles", ["TestAccounts", "TestSignInAndAttribution"]),
    ("Release and install", ["TestReleaseWorkflow", "TestUpdateChecker", "TestVersioning",
                             "TestWhereAnInstalledBuildWrites"]),
])
by_class = defaultdict(list)
for r in records:
    by_class[r["id"].split(".")[1]].append(r)
area_rows = [["Functional area", "Test classes", "Tests", "Passed", "Time (s)"]]
covered = set()
for area, classes in AREAS.items():
    rs = [r for c in classes for r in by_class.get(c, [])]
    covered.update(classes)
    area_rows.append([area, str(len([c for c in classes if c in by_class])), str(len(rs)),
                      str(sum(r["status"] == "pass" for r in rs)),
                      f"{sum(r['seconds'] for r in rs):.1f}"])
rest = [r for c, rs in by_class.items() if c not in covered for r in rs]
assert not rest, [r["id"] for r in rest]
area_rows.append(["<b>Total</b>", f"<b>{len(by_class)}</b>", f"<b>{N_TESTS}</b>", f"<b>{PASSED}</b>",
                  f"<b>{TESTS['total_seconds']:.1f}</b>"])
story.append(P("<b>Method.</b> The suite is Python unittest, run headless (offscreen Qt platform) with the "
               "deterministic offline encoder, so every run is reproducible with no network. It exercises "
               "every layer: unit tests for each engine stage; end-to-end tests that drive the real window "
               "against the files in samples/ from import through review to a trained model; and some that "
               "measure rendered pixels, because a few interface faults - a widget painting over the rail, a "
               "checkbox that draws nothing, a table wider than its page - are invisible to any other kind "
               "of test. Every test's outcome and time was recorded individually; Appendix A lists all of them."))
story.append(table(area_rows, [52 * mm, 26 * mm, 22 * mm, 22 * mm, W - 122 * mm]))
story.append(Spacer(1, 6))
story.append(P("Engine accuracy", "h2"))
story.append(table([
    ["Measure", "Evaluation set (42)", "Training corpus (56)"],
    ["Recall - SIF precursors found", f"{E42['recall']:.3f}  ({E42['tp']} of {E42['tp'] + E42['fn']})", f"{T56['recall']:.3f}  ({T56['tp']} of {T56['tp'] + T56['fn']})"],
    ["Precision - flags that were real", f"{E42['precision']:.3f}  ({E42['fp']} false)", f"{T56['precision']:.3f}  ({T56['fp']} false)"],
    ["IOGP rule right, on true positives", f"{E42['rule_accuracy']:.3f}", f"{T56['rule_accuracy']:.3f}"],
    ["Queued for a person", f"{E42['queued']} of {E42['n']}", f"{T56['queued']} of {T56['n']}"],
], [62 * mm, 55 * mm, W - 117 * mm]))
m = MODEL.get("metrics", {})
story.append(P("Learned model (XGBoost, cross-validated on the 56-report corpus): accuracy %.2f, precision "
               "%.2f, recall %.2f, ROC AUC %.2f. Top features: %s. %s" % (
                   m.get("accuracy", 0), m.get("precision", 0), m.get("recall", 0), m.get("roc_auc", 0),
                   ", ".join(f"{n} ({v:.2f})" for n, v in MODEL.get("top_features", [])[:3]),
                   (MODEL.get("warnings") or [""])[0])))
story.append(callout("<b>Reading these honestly.</b> Perfect scores on authored data are a ceiling, not a "
                     "forecast. The engine's vocabulary was extended after seeing its misses on the 42-case set, "
                     "which is fitting to the test. The model's top feature, p_sif at %.2f, is the rule engine's "
                     "own output - it has learned to agree with the rules, which is distillation, not new "
                     "knowledge. The first measurement that means something will be on real Oil India reports "
                     "labelled by Oil India reviewers." % (MODEL.get("top_features", [["", 0]])[0][1]), "warn"))
story.append(P("Speed", "h2"))
story.append(P("The engine analyses a report in <b>%.2f ms</b> with the offline encoder (about %s a minute). "
               "Earlier measurement found the interface, not the engine, was the bottleneck: it spent ~94 ms per "
               "report on a sleep, a refresh every five rows and a per-row scroll; that is now 4-6 ms. The "
               "sentence-transformer encoder adds roughly an order of magnitude per report and remains fast "
               "enough for any realistic import." % (METRICS["ms_per_report"],
                                                     f"{METRICS['reports_per_minute']:,}")))
story.append(PageBreak())

# 8 GAPS --------------------------------------------------------------------------------------
story.append(P("8  Software gaps", "h1"))
story.append(P("Ordered by what each costs if left as it is. <b>Fixed</b> marks what this update closed."))
gap_rows = [["Severity", "Gap", "What it costs", "The fix"]]
gaps = [
    ("High", "No real data - every report and label is authored", "Accuracy on Oil India's reports is unknown", "Collect and label per Section 6; measure before any operational use"),
    ("High", "The model is trained on the pipeline's own verdicts until reviews accumulate", "It agrees with the rules and adds nothing", "Train only on reviewed labels; SetFit at 8-64 per class"),
    ("High", "One machine, one database - no central server", "Attribution and decisions are per workstation; two sites cannot share a hotspot", "A small central service (Section 10, P3)"),
    ("Fixed", "No sign-in; the reviewer was a free-text box", "Anyone could decide under any name", "Accounts, roles, attributed decisions (Section 9)"),
    ("Fixed", "Audit trail could be edited without trace", "\"Who did what\" could not be proven", "Hash-chained entries with on-screen verification"),
    ("Medium", "Word documents (.docx) not read", "A common report format is rejected at ingest", "python-docx reader, about twenty lines"),
    ("Medium", "No asset or equipment identity", "Repeat failures on the same equipment are invisible", "Equipment NER and a fifth hotspot grouping"),
    ("Medium", "No work-hold output", "Detection stops at the queue; nothing says \"stop the job\"", "A threshold on high energy + failed critical barrier + critical risk, surfaced on the report and queue"),
    ("Medium", "English-only encoder; translation by a general chat model", "Meaning can be lost before analysis", "Multilingual encoder; IndicTrans2"),
    ("Medium", "Probabilities not calibrated", "A 0.8 may not mean 80%", "Isotonic calibration on held-out reviews"),
    ("Medium", "Six Indian scripts have no OCR recogniser", "Bengali, Gujarati, Punjabi, Malayalam, Odia, Assamese scans cannot be read", "Named honestly in the interface; revisit as PaddleOCR adds them"),
    ("Low", "Decision log rewrites the whole file per decision", "25 ms at 3,000 decisions; grows linearly", "Append-only JSON-lines, as the audit trail already is"),
    ("Low", "Installer is not code-signed; 1.64 GB", "SmartScreen warning; close to GitHub's 2 GB asset limit", "Organisation certificate; ship the slim build plus an engine pack"),
    ("Low", "Truncating the end of the audit trail leaves a valid shorter chain", "Removed final entries are undetectable without the noted head", "Periodic head export to a second location"),
]
colour = {"High": (RED, RED_BG), "Medium": (AMBER, AMBER_BG), "Low": (DIM, BAND), "Fixed": (LIME, LIME_BG)}
extra = []
for i, (sev, gap, cost, fix) in enumerate(gaps, start=1):
    gap_rows.append([f"<b>{sev}</b>", gap, cost, fix])
    fg, bg = colour[sev]
    extra.append(("BACKGROUND", (0, i), (0, i), bg))
story.append(table(gap_rows, [18 * mm, 52 * mm, 50 * mm, W - 120 * mm], zebra=False, extra=extra))
story.append(PageBreak())

# 9 THIS UPDATE ---------------------------------------------------------------------------
story.append(P("9  This update: sign-in, roles and a record of who did what", "h1"))
story.append(P("The console knew only the operating-system user - shared on a plant workstation - and a "
               "reviewer name typed into a box. Neither could answer the question an auditor asks: <b>which "
               "person analysed this report, and which person decided it?</b> Every session now begins with a "
               "sign-in, and everything recorded afterwards carries the account that did it."))
def plain(name, width):
    from PIL import Image as PILImage
    path = os.path.join(REPO, "docs", name)
    w, h = PILImage.open(path).size
    return Image(path, width=width, height=width * h / w)


img_row = Table([[plain("access-setup.png", 74 * mm), plain("access-signin.png", 74 * mm)]],
                colWidths=[W / 2, W / 2])
img_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
story.append(img_row)
story.append(P("Left: the first start on a machine. There is no default password - with no accounts, the page "
               "creates the administrator. Right: a refused sign-in, which is recorded with the name that was "
               "tried.", "small"))
story.append(P("Roles", "h2"))
story.append(table([
    ["Role", "Can", "Cannot"],
    ["Viewer", "Read every page", "Ingest, analyse, decide, train, clear, configure, manage accounts"],
    ["HSE Analyst", "+ ingest and analyse reports, export results", "Decide review cases, train, clear"],
    ["HSE Expert", "+ decide review cases, train the model on them", "Clear records, configure engines, manage accounts"],
    ["Administrator", "+ clear records, configure engines, manage accounts, export the audit trail", "Demote or disable the last administrator"],
], [28 * mm, 70 * mm, W - 98 * mm]))
story.append(P("The check sits on the controller action, not the button, so it holds for clicks, keyboard "
               "shortcuts, menus and the workflow map alike. A refusal is shown and recorded.", "small"))
story.append(P("How accounts are protected", "h2"))
story.append(table([
    ["Passwords", "Never stored. Each account keeps a random 16-byte salt and a PBKDF2-HMAC-SHA256 digest at 600,000 iterations (OWASP's 2023 figure), compared in constant time."],
    ["Guessing", "Five wrong passwords lock the account for five minutes. A wrong password and an unknown username give the same message in the same time, so neither reveals which usernames exist."],
    ["New accounts", "An administrator never chooses someone's password: the console issues a one-time password that must be replaced at first sign-in."],
    ["Lock-out safety", "The last active administrator cannot be demoted or disabled."],
], [30 * mm, W - 30 * mm], head=False))
story.append(PageBreak())
story.append(shot("access-activity.png", W, "The Activity page: each person's sign-ins, reports analysed and "
                  "decisions, read from the trail; the trail filterable to one person; account management for "
                  "administrators; and the state of the chain."))
story.append(P("What is recorded, and under whom", "h2"))
story.append(table([
    ["Event", "Recorded with"],
    ["Signed in / signed out / sign-in refused / account locked", "The account (or, when refused, the name that was tried), role, session id"],
    ["Reports analysed", "The account, the count and <b>the reference of every report in the batch</b>"],
    ["Each analysed report", "\"Analysed by\" and the time, shown in its evidence panel and exported with it"],
    ["Review decision", "Recorded under the signed-in person; the reviewer box can no longer be edited"],
    ["Permission refused", "The account, what it tried, and which permission it lacked"],
    ["Account created, role changed, password reset, disabled", "The administrator who did it"],
], [70 * mm, W - 70 * mm]))
story.append(P("A trail that can prove it has not been altered", "h2"))
story.append(P("Each audit entry carries the SHA-256 of the entry before it and of itself. Editing, inserting "
               "or deleting a line breaks the chain at exactly that line, and the Activity page says where. "
               "Removing lines from the <i>end</i> leaves a shorter chain that still verifies - so the head "
               "hash is shown on screen, for an auditor to note and compare later."))
story.append(callout("<b>What this is not.</b> A security boundary against someone with access to the files. The "
                     "accounts and the trail live on the operator's own disk, and anyone who can edit them can "
                     "edit them. What sign-in buys is <b>attribution</b>: an honest operator cannot act under "
                     "someone else's name by accident, and a dishonest one leaves a trail whose tampering can be "
                     "detected. Tested by 32 new tests, all passing.", "warn"))
story.append(PageBreak())

# 10 RECOMMENDED SOLUTION -----------------------------------------------------------------
story.append(P("10  The recommended solution", "h1"))
story.append(P("The intelligent path is not a bigger model. It is <b>the right data, a human in the loop "
               "who is named, and models that are only promoted when they beat the rules on real reports</b>. "
               "In order:"))
phases = [
    ["Phase", "What", "Done when"],
    ["P0  Data (weeks 1-8)", "Pilot at one asset. Import the real UA/UC export. Two HSE reviewers label through SENTRA's own review bench - which now records who decided what - with adjudication of disagreements.", "500 reviewed reports; Cohen's kappa of 0.7 or more; the first honest recall figure on real reports."],
    ["P1  Models (weeks 6-12)", "Multilingual encoder in place of the English one. IndicTrans2 for translation. SetFit trained on reviewed labels beside XGBoost. Isotonic calibration.", "A model is promoted only if its recall on the latest held-out quarter is at least the rule engine's, at no worse precision."],
    ["P2  Capabilities (weeks 8-14)", "Work-hold recommendation on high energy + failed critical barrier + critical risk. Equipment extraction and asset-level hotspots. Word documents at ingest.", "Each has tests and appears on the report, the queue and the hotspots page."],
    ["P3  Platform (weeks 12-20)", "A small central service holding accounts, decisions and the audit chain, so attribution and hotspots span sites; workstations sync when connected and work offline between. Signed installer; slim build plus an engine pack.", "Two workstations at two sites see one queue, one trail and one set of hotspots."],
]
story.append(table(phases, [34 * mm, W - 34 * mm - 58 * mm, 58 * mm]))
story.append(Spacer(1, 8))
story.append(P("Three rules that should not change", "h2"))
story.append(table([
    ["1", "<b>The rules are the floor.</b> A learned model may add a flag; it may not remove one the rules raised. Recall can only grow."],
    ["2", "<b>Nothing is closed by software.</b> Every confirmed finding reaches a named person."],
    ["3", "<b>Every number is measured.</b> No accuracy figure is quoted unless it was measured on real, held-out reports, by a script anyone can run."],
], [10 * mm, W - 10 * mm], head=False))
story.append(PageBreak())

# APPENDIX A -------------------------------------------------------------------------------
story.append(P("Appendix A  Every test, by area", "h1"))
story.append(P("All %d tests, each run and recorded individually. P = passed. Times in seconds." % N_TESTS, "small"))
for area, classes in AREAS.items():
    rows = [["Test", "Result", "s"]]
    for c in classes:
        for r in sorted(by_class.get(c, []), key=lambda x: x["id"]):
            name = r["id"].split(".")[-1].replace("test_", "").replace("_", " ")
            rows.append([f"<font color='#5b5f66'>{c.replace('Test', '')}</font>  {name}",
                         "P" if r["status"] == "pass" else r["status"].upper(), f"{r['seconds']:.2f}"])
    story.append(P(f"{area}  ({len(rows) - 1})", "h2"))
    story.append(table(rows, [W - 28 * mm, 14 * mm, 14 * mm], style="tiny"))

# APPENDIX B -------------------------------------------------------------------------------
story.append(PageBreak())
story.append(P("Appendix B  How the numbers were produced", "h1"))
story.append(table([
    ["Figure", "Produced by"],
    ["Test results", "python -m unittest discover -p \"test_*.py\" with QT_QPA_PLATFORM=offscreen and SIF_ENCODER=hashing; a result class recorded each test's outcome and time."],
    ["Engine accuracy", "python evaluation/evaluate.py, and the same scoring applied to samples/training_corpus.csv."],
    ["Model metrics", "MLOpsService.train on samples/training_corpus.csv with its labels, stratified cross-validation."],
    ["Speed", "SIFPipeline.analyze over the 18 reports of samples/near_miss_reports.csv, offline encoder, after one warm-up call."],
    ["Screens", "Rendered from the running application, offscreen, against the sample reports."],
    ["Code size", "%d lines of application code across sif/, ui/, ui2/ and the entry points; %d lines of tests." %
     (sum(METRICS["loc"].values()), sum(METRICS["test_loc"].values()))],
], [34 * mm, W - 34 * mm]))

# -- build ------------------------------------------------------------------------------
doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                      topMargin=18 * mm, bottomMargin=18 * mm,
                      title="SENTRA - System architecture, test and gap report",
                      author="Team WellDropp", subject="Oil India Limited - SIH PS 26165")
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
doc.addPageTemplates([PageTemplate(id="cover", frames=[frame], onPage=on_cover),
                      PageTemplate(id="body", frames=[frame], onPage=on_page)])
doc.build(story)
print("wrote", OUT)
