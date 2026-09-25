# SENTRA

*Sense the Risk · Stop the Incident*

> Workers report near-misses every day. SENTRA reads each report the moment it is
> written, finds the ones that could have killed someone, shows why, and asks a
> person to confirm.

Prototype for **Oil India Limited — Problem Statement 26165**: turning raw
Unsafe Act / Unsafe Condition (UA/UC) and near-miss reports into structured,
decision-grade **SIF (Serious Injury & Fatality) intelligence**.
The engine is SENTRA; `sif/` remains the package name, and the settings folder
keeps its old name so an existing operator's review decisions are not orphaned.

![The reports page](docs/ui-reports.png)

*Every analysed report, the verdict, and the cues behind it. The console ships
in this design; `app2.py` runs the same window in a deep-navy one.*

| | |
| --- | --- |
| ![Workflow map](docs/ui-workflow.png) | ![Dashboard](docs/ui-dashboard.png) |
| **Workflow map** — every capability, its live status on this machine, and its own control. | **Dashboard** — headline metrics and the exposure charts for the whole corpus. |
| ![Risk hotspots](docs/ui-hotspots.png) | ![Human review](docs/ui-review.png) |
| **Risk hotspots** — repeats ranked by SIF-precursor density, not by volume. | **Human review** — the queue on the left, the whole case and three keys on the right. |
| ![Ingest and OCR](docs/ui-ingest.png) | ![Engines](docs/ui-engines.png) |
| **Ingest** — text, CSV, PDFs, scans and photographs, in twelve languages. | **Engines** — what is installed on this machine and what each one is doing. |

> **Start here:** [USING_SENTRA.md](USING_SENTRA.md) — the click-by-click flow,
> from first launch to working the review queue.
>
> **Operating manual:** [INSTRUCTION.md](INSTRUCTION.md) — the rules the system
> must be used under, step-by-step install and daily process, how to train the
> model on reviewed labels, and what has to change before it is trusted on live
> safety data.
>
> **Building the installer:** [packaging/INNO_SETUP.md](packaging/INNO_SETUP.md)
> — PyInstaller and Inno Setup, step by step, and how to publish a release.
>
> **Architecture, test and gap report:** [reports/report.pdf](reports/report.pdf)
> — how the engine decides, the models and data, every test result, and what is
> still missing.

## Sign-in and a record of who did what

Every session begins with a sign-in, and everything the console records carries
the account that did it: each analysed report says who analysed it, each review
decision is recorded under the signed-in person, and the audit trail names the
user on every entry.

| | |
| --- | --- |
| ![Sign in](docs/access-signin.png) | ![Activity](docs/access-activity.png) |

* **No default password.** The first start on a machine creates the administrator.
* **Four roles** — Viewer, HSE Analyst, HSE Expert, Administrator — each able to do
  everything the one before can. The check is on the action, not the button.
* **Passwords are never stored** — a salted PBKDF2-HMAC-SHA256 digest at 600,000
  iterations. Five wrong attempts lock an account for five minutes.
* **A tamper-evident trail.** Each audit entry carries the hash of the one before
  it; the Activity page shows whether the chain is intact and where it broke.


## Run it

### Installed, on Windows

Go to the **[releases page](https://github.com/tedo001/sentra/releases)** and,
under **Assets**, **click `SENTRA-2.0.0-setup.exe`** to download it. The two
"Source code" entries beneath it are the code, not the application. Run the
installer and start SENTRA from the Start menu — Windows 10 or newer, 64-bit,
and no Python needed.

| | |
| --- | --- |
| ![Select additional tasks](docs/install-1-tasks.png) | ![Ready to install](docs/install-2-ready.png) |
| ![Installing](docs/install-3-installing.png) | ![Information](docs/install-4-information.png) |

The build carries the sentence encoder, the learned model and the OCR engine, so
nothing is fetched afterwards — which is why the download is large. The last
page of the wizard names the one thing no installer can carry: the local Ollama
model that performs translation.

[INSTRUCTION.md §3A](INSTRUCTION.md) walks through it screen by screen.

The installed console keeps its data in `%APPDATA%\SIF Insight Console` —
preferences, the audit trail, the decision trail, logs, the trained model and
the training history — never in its own installation folder, which a standard
user cannot write to. Uninstalling leaves that folder alone.

### From source

```bash
pip install -r requirements.txt
python app.py        # the console
python app2.py       # the same console, deep-navy design
python app3.py       # the same console, Flowbite admin design
python app4.py       # two workspaces: HSE workspace and Administration
python app4.py --present   # everything 1.5x larger - for screenshots on slides
```

**Organisation logo (app4).** Save the official Oil India Limited logo as
`ui/assets/oil_logo.png` (`.svg`, `.webp` or `.jpg` also work) and the header
shows it in place of the drawn OIL badge; a wide logo that already includes the
name replaces the name text too. The file is bundled into the installer.

For slides, `--present` scales the whole interface (text, tables, buttons) and
fills the screen, so a screenshot stays readable when projected.
`SENTRA_SCALE=1.25` suits a laptop screen and `SENTRA_SCALE=2` a 4K one
(PowerShell: `$env:SENTRA_SCALE="1.25"; python app4.py --present`).

Click **Load 5 seed incidents** for an instant demo, or **Import CSV export**
and pick `samples/near_miss_reports.csv`. The first run downloads the
sentence-transformer (~90 MB); the status bar reports progress and the window
stays responsive. To run with no model and no network, pick **Offline — lexical
rules only** on the Engines page, or export `SIF_ENCODER=hashing`.

### Two entry points, one console

`app.py` and `app2.py` build the *same* window from the same controller
(`main2.py`) and differ only by a palette and a style sheet — so a fix to any
capability lands in both, and neither can drift into being a stale copy of the
other.

| | |
| --- | --- |
| `app.py` | Black cards on a warm charcoal ground, lime for everything pressable, the rail in capitals. This is what the installer ships. |
| `app2.py` | The same console in near-black navy with a teal accent, icons in the rail. |
| `app3.py` | The same console in the Flowbite admin design: white cards, grey ground, blue accent. |
| `app4.py` | Two workspaces behind one sign-in, tabs instead of a rail. An HSE Analyst gets Home, Ingest, Dashboard, HSE Review, Action Items (a month/week calendar of recurring and corrective compliance actions, each date marked done by a person), Risk Hotspots and Profile; an administrator gets Engines, Settings, SysLog, Audit Log and New HSE Login. Safety decisions and platform control are separate roles in this build only. |

A third skin, white and grey with a blue accent, lives in `ui/light_theme.py`
and is one line away in `build_window()`.

### What is optional

Everything except PyQt6 is detected at run time, and the **Engines** page says
which of them this machine has:

These are what an installed build carries by default; a source install carries
whatever you `pip install`.

| Missing | What still works |
| --- | --- |
| `sentence-transformers` | Everything, on the deterministic lexical engine — it ranks and enriches but never raises a flag of its own. |
| `xgboost` / `mlflow` | Everything but the learned third opinion and the run history. |
| `paddleocr` | Everything but scanned pages; PDFs with a text layer are still read exactly. |
| Ollama | Everything but translation and the optional fourth opinion. A non-English report is analysed in its original wording, and that fact is recorded on the report rather than silently skipped. |

Ollama is a separate service and is not bundled by any build: install it from
ollama.com, then `ollama pull llama3.2` (or `gemma2`), and point the Engines
page at it.

### The pages

| Page | What it is for |
| --- | --- |
| **Workflow map** | Every capability in one picture — ingest, OCR, translate, analyse, dashboard, hotspots, review, learn — each with a live status and its own control, so the path from a scanned report to a trained model is visible rather than implied. |
| **Ingest and OCR** | Paste text, import a CSV export, or add PDFs, scans and photographs; shows which backend read each file, its OCR confidence and the extracted text, with per-document preview, analyse and remove. |
| **Dashboard** | KPI tiles and the four exposure charts for the whole corpus. |
| **Reports and evidence** | Every analysed report, and for the selected one: the plain-English brief, the report as filed, the extracted fields and the cues behind the verdict. |
| **Risk hotspots** | Sites, activities, rule-at-location repeats and repeat barrier failures above the repeat threshold, ranked by SIF-precursor density. |
| **Human review** | The queue, the case, and three keys to decide it — plus the decision trail, exportable as CSV. |
| **Analytics** | Corpus-level charts, the learned model's summary and its feature importances. |
| **Engines** | The encoder, the local LLM, the learned model and MLOps: what is installed, what is running, and the controls for each. |
| **Settings** | Preferences, the live log view and the audit trail. |

### Settings — system logging and MLOps

* **System logging** — every component logs through `logging`; the tab shows a
  live, level-filtered view of the ring buffer, names the rotating file under
  `logs/`, and lets you change level or clear the buffer at runtime.
* **MLflow** — set the tracking URI and experiment (default
  `sqlite:///mlflow.db`, since MLflow 3 put the file store into maintenance
  mode). Recent runs are listed with their metrics.
* **XGBoost** — train on the analysed corpus in one click. The run logs params,
  metrics, feature importances and the model artifact to MLflow, saves the
  booster to `models/`, and attaches it to the pipeline as a third opinion.
* **PaddleOCR** — enable/disable OCR, pick a language, and *actually load* the
  engine with "Download / verify OCR models" (it reports the real outcome,
  including a failed model download, rather than guessing from the import). The
  models are fetched **once per machine** and kept in `~/.paddlex`; the console
  reads that directory, so a machine that already has them is told so at every
  start-up rather than asked to check again. `python -m sif.ocr en hi ta` does
  the download deliberately, and `--list` shows what is already there.

## Architecture

```
                    REPORT (text · CSV · PDF · scan · photo)
                             │
                    ┌────────▼────────┐
                    │ DOCUMENT INGEST │  sif/ocr.py
                    │ text · pdf-text │  PaddleOCR for scanned pages
                    │ · paddleocr     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ NLP PREPROCESSOR│  sif/preprocessing.py
                    └────────┬────────┘  clean · expand LOTO/PTW/GGS · segment
                             │
                  ┌──────────▼───────────┐
                  │ Semantic NLP Engine  │  sif/encoders.py
                  │ Transformer Encoder  │  all-MiniLM-L6-v2 · offline fallback
                  └──────────┬───────────┘
                             │
        ┌────────────────────┼─────────────────────┐
        ▼                    ▼                     ▼
  SIF Classifier      Rule Classifier        NER / Extraction     sif/heads.py
  P(SIF)=energy×      IOGP Life-Saving       ┌──────┼───────┐
  barrier             Rule                   ▼      ▼       ▼
        │                    │           Activity Location Barrier
        └────────────────────┼─────────────────────┘
                             ▼
                    ┌─────────────────┐
                    │ Evidence Engine │  sif/evidence.py
                    └────────┬────────┘  cues · neighbours · decision path
                             ▼
                     ┌───────────────┐
                     │ SIF Risk Score│  sif/scoring.py   0–100 + band
                     └───────┬───────┘
                             │  ◄── XGBoost model as a third opinion
                             │      (sif/mlops.py, tracked in MLflow)
                  ┌──────────┴──────────┐
                  ▼                     ▼
          Pattern Detection        Human Review        sif/patterns.py
          (sif/patterns.py)        (sif/review.py)
                  │                     │
                  ▼                     │
           ┌───────────────┐            │
           │ Risk Hotspots │◄───────────┘
           └───────┬───────┘
                   ▼
            HSE Intelligence          sif/pipeline.py → Intelligence
                   ▼
               Dashboard              main.py (PyQt6)
```

### Stage by stage

| Stage | Module | What it does |
| --- | --- | --- |
| 1. Preprocessor | `sif/preprocessing.py` | Cleans the text, expands upstream shorthand (LOTO, PTW, GGS, H2S…) for the encoder while preserving the reporter's surface wording for the patterns, and segments sentences. |
| 2. Semantic encoder | `sif/encoders.py` | `all-MiniLM-L6-v2` sentence embeddings via `sentence-transformers`, behind a small interface. A deterministic hashing encoder is the offline fallback; resolution is eager, so a missing model degrades before the batch starts, not halfway through. |
| 3a. SIF classifier | `sif/heads.py` | `P(SIF) = energy_score × barrier_score` — the "high energy **AND** failed barrier" rule expressed continuously. Each factor is the max of the lexical determination and the calibrated similarity to the energy / barrier prototypes. |
| 3b. Rule classifier | `sif/heads.py` | Fuses per-rule lexical scores with cosine similarity to the IOGP rule prototypes (0.55/0.45 with a model, 0.8/0.2 without), and returns `Unclassified` below a floor rather than guessing. |
| 3c. NER / extraction | `sif/heads.py` | Activity, location and barrier: gazetteer and pattern hits first, semantic nearest-prototype only where the lexical layer fell back, and an explicit "not stated" below the similarity floor. |
| 4. Evidence engine | `sif/evidence.py` | Collects lexical cues, nearest semantic prototypes with scores, per-field provenance and the decision path, then writes the one-line explanation shown in the UI. |
| 5. Risk score | `sif/scoring.py` | `100 × P(SIF) × energy severity × barrier criticality × evidence factor`, banded Critical / High / Medium / Low. Ordinal, for ranking a queue — not an actuarial probability. |
| 6a. Pattern detection | `sif/patterns.py` | Location, activity, rule-at-location and repeat-barrier clusters (≥2 reports), ranked by **SIF-precursor density** — the share of a group's reports carrying fatal potential — discounted by a Wilson lower bound so a 2-of-2 group cannot outrank a well-evidenced one. |
| 6b. Human review | `sif/review.py` | Queues what a person must verify: model/rule **disagreement**, **critical risk**, **thin evidence**, **high energy with no rule match**, **energy with no barrier found**, or, as a catch-all, **any other confirmed finding** — no report the engine calls SIF-potential is ever closed without a person, whatever band it scored in. Flags dismissive wording ("nothing serious") that undersells a real finding. Records the expert's decision, persists it, and hands it back as the labels training uses. |
| 6c. Narrative generation | `sif/narrative.py` | Turns the same structured facts back into prose: a one-paragraph brief per report, or a multi-section bulletin over a corpus — headline numbers, what is driving risk, repeat exposures, language coverage, and exactly what still needs a person. Templated from verified fields, not model-generated, so every sentence traces back to a report. |
| 7. Dashboard | `main.py` + `ui/` | Sidebar navigation, KPI tiles, painted charts, the three result tables, evidence panel and Settings. |

### The learned layer (MLOps)

`sif/mlops.py` turns each result into a **named, interpretable feature vector**
(46 columns: the two SIF factors, energy and barrier families as multi-hot flags,
severity weights, the rule one-hot, text statistics) and fits an
`XGBClassifier` with stratified cross-validation. Feature importance therefore
reads as safety language — `p_sif`, `barrier_criticality`, `energy::Electrical
energy` — not as `f37`.

Two things are deliberate and worth knowing:

* **Labels.** With no reviewed corpus, training defaults to the pipeline's own
  verdicts. That is *distillation*: the model learns to reproduce the rules and
  adds no knowledge until real labels replace them, which is what the review
  queue exists to produce. The label source is recorded on every run.
* **Small corpora.** XGBoost's default `min_child_weight` silently forbids any
  split that isolates fewer than ~4 reports, so a pilot corpus yields split-less
  trees and a constant probability — a model that looks trained and predicts
  nothing. `adapt_params` relaxes it for small runs and records a warning on the
  report.

Where the model contradicts the pipeline, the report is queued as a **model
disagreement** — the highest-value row to label, since one of the two is wrong.

### Why fusion, not replacement

The semantic layer **extends** the deterministic rules; it never overturns them.
A report the patterns flag stays flagged, and the model can add a flag the
patterns missed — so recall only grows. Two guards keep that honest:

* the offline fallback is explicitly non-semantic: it can rank and enrich, but it
  never raises a flag of its own, so offline mode is exactly as precise as the
  rules; and
* a **discrimination guard** — if an encoder scores every prototype alike (an
  untrained, mis-loaded or otherwise degenerate model), the ranking is treated as
  uninformative and the decision falls back to the lexical rules.

Every result records which path decided it (`evidence.decision_path`), and any
disagreement between the two goes to the human review queue.

## Releases and updates

Pushing a version tag builds installers for Windows, macOS and Linux and
publishes a GitHub Release; the app checks for it and offers the update. See
[RELEASING.md](RELEASING.md).

```bash
git tag -a v2.1.0 -m "..." && git push origin v2.1.0
```

## Module map

| File | Responsibility |
| --- | --- |
| `sif/pipeline.py` | `SIFPipeline` — orchestration, `PipelineResult`, corpus `Intelligence`. |
| `sif/ocr.py` | `DocumentExtractor` — plain text, PDF text layer, PaddleOCR for scans; per-line OCR confidence. Also the model cache: one engine per language for the life of the process, a disk check so a downloaded model is never re-announced as pending, and `python -m sif.ocr` to fetch them once. |
| `sif/mlops.py` | Features, `SIFModel` (XGBoost), `MLflowTracker`, `MLOpsService`. |
| `sif/logging_setup.py` | Rotating file + in-memory ring buffer behind the Settings log view. |
| `sif/audit.py` | The audit trail: append-only JSONL, `system` and `functionality` entries, CSV export. Separate from the log, because the log rotates away. |
| `ui/` | `theme` (palette, style sheet, scroll-control assets), `charts` (painted bar/donut), `components`, `views`. |
| `ui/assets/` | Scrollbar stepper arrows - Qt cannot draw a triangle reliably from a style sheet alone. |
| `sif/lexical.py` | `LexicalEngine` — IOGP, energy, barrier, activity and location knowledge as patterns; the deterministic backbone. Holds the 5 seed narratives. |
| `sif/prototypes.py` | Natural-language label descriptions for zero-shot semantic classification. |
| `main2.py` | The controller both entry points build on: `MainWindow`, the workers, every page's wiring. |
| `main.py` | The first console, kept as a single-window reference build. |
| `app.py`, `app2.py` | Launchers — dependency check, palette, `QApplication` bootstrap, event loop. They differ by which theme module they call. |
| `ui/theme.py` | The shared colour table and the typographic switches a skin sets before a window is built - a Qt style sheet can change neither letter case nor an icon. |
| `ui/green_theme.py`, `ui/gov_theme.py`, `ui/light_theme.py` | The three skins: black and lime, deep navy and teal, white and grey. Each is a palette plus a style sheet, applied either side of construction. |
| `sif/paths.py` | Where a build may write: beside the code from a checkout, under the per-user data directory when frozen. An installed application cannot write into its own Program Files folder. |
| `train_model.py` | Command-line trainer: analyse a CSV, train on reviewed labels, log the run to MLflow. |
| `sif/updater.py` | Checks GitHub Releases, verifies the download's checksum, launches the installer. |
| `sif/version.py` | The one place the version lives; CI stamps it from the git tag. |
| `packaging/`, `.github/workflows/release.yml` | PyInstaller spec, Inno Setup script, the step-by-step build guide, tag-driven release pipeline. |
| `test_sif.py` | 102 unit tests across every stage, the fusion guards, MLOps, document extraction, where a frozen build writes, and the Qt widgets. |
| `test_app2.py` | 103 tests: language handling, the local LLM and its model names, the workflow map, the review bench, the decision log and the OCR model cache. |
| `test_release.py` | 25 tests for versioning, the update checker and the release pipeline. |
| `test_functional.py` | 60 end-to-end tests: both windows driven against the real `samples/` files, from import through review to a trained model, plus the skins measured off the rendered pixels. |
| `sample_reports.csv` | Six mock rows for the batch-import demo. |
| `samples/` | Test material for every ingestion path - an 18-report CSV, a shift log, a text-layer PDF, a scan with no text layer, and reports in five Indian languages. See `samples/README.md`. |
| `reports/` | Generated analysis report (PDF). |

## Result fields

`SIFPipeline.analyze(text)` returns a `PipelineResult`. The five fields the
problem statement asks for keep their names: `sif_potential`, `iogp_rule`,
`activity`, `location`, `barrier_failure`. Alongside them:

`p_sif`, `risk_score`, `risk_band`, `energy_source`, `high_energy`,
`barrier_failed`, `lexical_flag`, `semantic_flag`, `semantic_active`,
`rule_confidence`, `confidence`, `severity_hint`, `needs_review`,
`review_trigger`, `review_reason`, `explanation`, `evidence`, `encoder`,
`elapsed_ms`, and — when a model is attached — `ml_probability`, `ml_flag`,
`ml_active`.

Every extractor degrades to an explicit fallback (`Unclassified / General HSE`,
`Unspecified activity`, `Location not stated`, `No barrier failure identified`)
rather than raising, so a malformed row never breaks a batch.

## How good is the engine?

A number, not an adjective. `evaluation/` holds 42 hand-labelled reports and a
scorer:

```bash
python evaluation/evaluate.py            # the offline rule engine
python evaluation/evaluate.py --errors   # every miss, with its text
```

| Metric | Before the barrier work | Now |
| --- | --- | --- |
| **Recall** (of 25 real precursors) | 0.292 | **1.000** |
| **Precision** (17 negative controls) | 1.000 | **1.000** |
| Barrier recall | 0.292 | **1.000** |
| Energy recall | 0.917 | **1.000** |
| Rule accuracy (on true positives) | 0.792 | **0.960** |
| Confirmed findings never queued | 5 | **0** |

Recall was the problem, and the cause was specific: `P(SIF) = energy x barrier`,
so a barrier the vocabulary could not name scored zero however obvious the
hazard. The engine was reading explicit negatives ("no LOTO was applied") and
missing implicit ones - "clipped to the handrail **instead of** the anchor
point", "car-sealed open with no tag", "no test for dead", "the trip tank had not
been monitored". Those are now in the knowledge base.

**Read those numbers honestly.** The labelled set is 42 cases written for this
repository, and the vocabulary was extended after seeing which of them missed -
that is fitting to the test. Two things make it more than that:

* **17 negative controls.** Every positive case has a twin describing the same
  incident with the barrier *holding* ("LOTO was applied and verified", "the
  exclusion zone was barricaded and the banksman kept the area clear"). Chasing
  recall by loosening patterns fails those immediately, and they include two
  counterfactual traps using the exact "would have been struck" phrasing that the
  near-miss pattern looks for, and one that pairs dismissive wording ("nothing
  serious to report") with a barrier that genuinely held.
* **A held-out corpus.** The 18 reports in `samples/near_miss_reports.csv` were
  written before this work and were not tuned against. Flags there went from 5 to
  13, and the five that still do not flag are the five low-consequence ones.

A third check is not a recall number at all: **every confirmed finding must
reach a person**, independent of whether the label agrees. Measuring that
against the labelled set and the sample corpus both found five confirmed
findings - outside the Critical band, with clean extraction and no
disagreement - that matched none of the queue's triggers and reached nobody.
The queue's own contract (see `sif/review.py`) says that must never happen; a
catch-all trigger now closes it, and `confirmed_unqueued` is asserted at 0
alongside recall and precision.

The real number comes from OIL's own reports, and the review queue is what
produces it: `test_sif.py::TestEngineQuality` holds the floor at 0.90 recall and
0.90 precision, and asserts `confirmed_unqueued == 0`, so a future change cannot
quietly undo either.

## Review happens in English

A reviewer confirms or overturns a fatal-potential call. They cannot do that on
words they do not read, so wherever a report is put to a person - the review
bench and the report detail - the **English rendering is what is shown**, and the
bar above it says which text is on screen:

| The report | What the bench shows | What the bar says |
| --- | --- | --- |
| Translated from Tamil | The English | `ENGLISH - TRANSLATED FROM TAMIL FOR REVIEW`, with **Show the original** beside it |
| Not in English, not translated | The original, because there is nothing else | `NOT TRANSLATED - ... START OLLAMA AND RE-ANALYSE BEFORE DECIDING` in red |
| Written in English | The report | `ENGLISH AS WRITTEN` |

The original is never hidden and never replaced: it is one button away on the
bench, it sits under EVIDENCE AND REASONING on the report page, and it is what
the decision log and the audit trail keep. The translation is for reading; the
original is the record.

## The audit trail

Settings carries two records, and they are not the same thing.

* **System logging** is diagnostics. Verbose, full of third-party chatter, and it
  rotates away after a few megabytes - right for finding out why something failed
  this morning, wrong for anything else.
* **The audit trail** (`sif/audit.py`) is append-only JSONL beside the settings
  file, one line per event, and nothing rotates it. **SYSTEM** entries are what
  the software did by itself - started, attached a model, fetched OCR models,
  checked for a release. **FUNCTIONALITY** entries are what an operator asked for
  and what came back - reports analysed (with how many were repeats), documents
  read, a model trained and on whose labels, every review decision, every export.

Every entry carries the operating-system user, the reviewer name when one is set,
the version, and its own detail. Filter by kind, and export to CSV for an
auditor. If the location cannot be written the trail says **MEMORY ONLY** rather
than letting anyone believe it reached disk.

## Desktop behaviour

Both builds are desktop applications rather than mock-ups of one:

* **No pictographs anywhere.** Every label is words or a typographic mark, so the
  interface renders identically on a plant workstation with no emoji font. A test
  in each suite fails if one creeps back in.
* **Nothing decorative that does nothing.** The notification bell was a label
  with no signal behind it; an indicator that never indicates anything teaches an
  operator to ignore indicators, so it was removed rather than given a meaning.
* **The window remembers itself.** Size, position and maximised state are saved
  on close and restored on start - clamped to the screen actually attached, so a
  geometry saved on a docked 4K monitor cannot open off-screen on a laptop.
* **Draggable columns.** Build 1's dashboard workspace is a splitter: an operator
  reading long narratives widens the middle, one entering reports widens the
  left. Neither column can be collapsed to nothing.
* **Minimum window size** of 1024x640, below which the layout is not honest about
  what it can show.

## Scrolling

Every page that can outgrow the window scrolls rather than compressing. Each
sits in a scroll area with a minimum content height below which the bar appears
instead of the content shrinking; the sidebar nav scrolls on short screens; and
all tables scroll per pixel in both directions. Verified at **1280 x 720** - a
plant laptop, not a desk monitor - with every page reachable:

| Build 2 page | How it scrolls |
| --- | --- |
| Workflow map | The eight stage cards and the legend, below 720 px |
| Ingest and OCR, Dashboard, Engines, Settings | Whole page, below their own floors |
| Reports and evidence | Matrix scrolls itself; the detail column has its own area |
| Risk hotspots | The table, in both directions |
| Human review | Queue table scrolls; the case detail scrolls; **the three decision buttons never do** - they stay pinned where the reviewer's eye expects them |
| Analytics | Whole page, below 900 px |

The scrollbars themselves - track, thumb and the stepper arrows from
`ui/assets/` - are styled once, globally, so anything wrapped in a scroll area
picks them up without asking.

The controls themselves are styled to match the rest of the console - a sunken
track, a light rounded thumb, and stepper arrows at both ends drawn from the PNGs
in `ui/assets/`, since a Qt style sheet cannot reliably draw the triangles
itself. A unit test asserts every asset the style sheet references exists, so a
rename cannot silently leave the arrows blank.

## Concurrency

Four worker threads, no blocking work on the GUI thread:

| Worker | Runs |
| --- | --- |
| `AnalysisWorker` | Encoder load and every pipeline stage; streams one row at a time. |
| `ExtractionWorker` | PDF reading and OCR, including PaddleOCR's first-run model download. |
| `TrainingWorker` | XGBoost training and the MLflow run. |
| `OCRProbeWorker` | The "Check OCR availability" probe. |

Results come back over `pyqtSignal` — `row_ready(dict)`, `progress(int, int)`,
`status(str)`, `failed(str)`, `completed(int)` — so the event loop is never
blocked, including during a model download. A running worker is interrupted
cleanly on window close.

## Tests

```bash
python -m unittest discover -p "test_*.py"
```

On a headless machine prefix with `QT_QPA_PLATFORM=offscreen`, and with
`SIF_ENCODER=hashing` to pin the offline encoder so the run needs no model
download and is deterministic.

**322 tests.** They cover every pipeline stage and the fusion guards, the MLOps
round-trip, document extraction and the OCR model cache, the local LLM's
readiness and model-name handling, the review bench and its decision trail, the
update checker and the release pipeline, sign-in, roles and the audit chain — and the interface itself, driven
headless against the real `samples/` files from import through review to a
trained model.

Some of them measure rendered pixels rather than state, because a few classes of
interface bug are invisible to any other kind of test: a widget painting the
page's background over a coloured rail, a checkbox indicator that draws nothing,
a table wider than the page it sits on, a field long enough to push a panel past
its pane.
