# Mock PDF reports

Fourteen one-page UA/UC report forms: a **SIF precursor** and a **non-SIF**
report in each of English, Assamese, Hindi, Bengali, Tamil, Marathi and
Kannada. Every form says *MOCK REPORT - SENTRA TEST DATA - NOT A REAL RECORD*
at the top; none describes a real person, event or record.

| File | Language | Expected | What happened |
| --- | --- | --- | --- |
| `english_sif_flowline_pressure.pdf` | English | **SIF precursor** | Flange opened on a live 18 bar flow line, no permit |
| `english_non_sif_housekeeping.pdf` | English | non-SIF | Cartons and cable ties on a store walkway, cleared |
| `assamese_sif_feeder_no_loto.pdf` | Assamese | **SIF precursor** | 11 kV feeder left unearthed, cable jointing without LOTO |
| `assamese_non_sif_wet_walkway.pdf` | Assamese | non-SIF | Rainwater on an office walkway, mopped and signed |
| `hindi_sif_hot_work_expired_permit.pdf` | Hindi | **SIF precursor** | Welding beside a condensate tank on an expired permit, no gas test, no fire watch |
| `hindi_non_sif_controlled_lift.pdf` | Hindi | non-SIF | Crane lift done to plan; a worn tag line replaced |
| `bengali_sif_under_suspended_load.pdf` | Bengali | **SIF precursor** | Two workers under a 4 t module on the crane, no lift plan |
| `bengali_non_sif_store_walkway.pdf` | Bengali | non-SIF | Packing material on a warehouse walkway, cleared |
| `tamil_sif_confined_space.pdf` | Tamil | **SIF precursor** | Separator tank entry with no gas test or ventilation, expired permit, H2S |
| `tamil_non_sif_parking_water.pdf` | Tamil | non-SIF | Standing rainwater in an office car park, cleared |
| `marathi_sif_work_at_height.pdf` | Marathi | **SIF precursor** | Harness clipped to a railing at 9 m, scaffold tag expired |
| `marathi_non_sif_controlled_hot_work.pdf` | Marathi | non-SIF | Welding on a valid permit, gas test done, fire watch present |
| `kannada_sif_tanker_fatigue_fog.pdf` | Kannada | **SIF precursor** | Crude tanker driver 11 hours at the wheel, overtook in fog |
| `kannada_non_sif_first_aid_box.pdf` | Kannada | non-SIF | First-aid box short of bandages, refilled |

## Try them

**Ingest** → **Choose files...** → select all fourteen → **Start processing**.
Then:

* **Ingest** - each file is one report. The Language column names its
  language; after analysis it reads `→ English` (Ollama translated it),
  `· keyword gloss` (no LLM: the engines read an English gloss of the safety
  terms) or `· not translated` (nothing the gloss knows - the non-SIF
  housekeeping reports).
* **HSE Review** - the seven precursors are queued as SIF potential, each with
  its site (Duliajan, Naharkatiya, Moran) read off the form. A non-English case
  shows `ORIGINAL · HINDI` with **Show the keyword gloss** (or the translation).
* **Dashboard** - the reports sit on the dates written on the forms
  (14-27 Sep 2026) in the risk trend's *Month* view; the spider chart shows
  which rules, energies and barriers they touch.

The non-SIF set is deliberately mixed: some are housekeeping with no energy at
all, and two describe **high-energy work with every barrier in place** (a crane
lift to plan in Hindi, welding on a valid permit with a gas test and a fire
watch in Marathi) - they must *not* be flagged, and they are not.

## How they are made

`python tools/make_mock_reports.py` (PyQt6 and PyMuPDF; the FreeSerif font from
GNU FreeFont). English forms are ordinary text PDFs. The Indian-language forms
are drawn by Qt, which shapes the scripts correctly, into a page image with an
invisible text layer holding the exact Unicode - as a searchable scan does -
because a PDF's own text of shaped Indic glyphs comes back scrambled from every
PDF reader. `test_languages.py` reads all fourteen and checks the language and
the verdict of each.
