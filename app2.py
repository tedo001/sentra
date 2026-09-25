"""Entry point for SENTRA, build 2.

Oil India Limited - Problem Statement 26165.

    python app2.py

``app.py`` runs the same console in the white-and-grey design; this one is the
deep navy. The two differ in appearance only - one controller, one set of
pages, one copy of every rule. This build carries:

* a **workflow map** - every capability in one picture, each with a live status
  and its own control, so the path from a scanned report to a trained model is
  visible rather than implied;
* **Indian-language ingestion** - PaddleOCR in Hindi, Marathi, Tamil, Telugu,
  Kannada, Urdu and the wider Devanagari family, with optional translation to
  English so the analysers can read the report;
* an **optional local LLM analyser** (Ollama) that reads each narrative as a
  fourth opinion and never overrides the pipeline - where it disagrees, the
  report is queued for a human;
* a **dashboard of its own**, separate from ingestion and from the report matrix;
* an interface with **no pictographic icons**, which renders identically on a
  plant workstation with no emoji font.

Optional components are all detected at run time. Without Ollama, without a
trained model, without OCR models, the console still starts and the workflow map
says exactly which stage is unavailable and why.

Environment
-----------
    SIF_ENCODER=auto|transformer|hashing     encoder backend (default: auto)
    SIF_ENCODER_MODEL=<hub id or local dir>  sentence-transformer to load
    OLLAMA_HOST=http://localhost:11434       where the local LLM listens
    SIF_LLM_MODEL=llama3.2                   which model to ask
"""

from __future__ import annotations

import sys


def _require_pyqt6() -> None:
    """Fail fast with an actionable message if PyQt6 is not installed."""
    try:
        import PyQt6  # noqa: F401  (import is the check)
    except ImportError:
        sys.stderr.write(
            "PyQt6 is required to run SENTRA.\n"
            "Install it with:\n\n    pip install -r requirements.txt\n\n"
            "or:\n\n    pip install PyQt6\n"
        )
        raise SystemExit(1)


def build_window(session=None, accounts=None):
    """Construct the console in the deep-navy design.

    The palette goes on before the window is built and the style sheet after -
    that order is the mechanism, because every widget that styles itself reads
    the palette in its constructor. ``app.py`` performs the same two steps with
    :mod:`ui.light_theme`, so the two builds differ by a palette and a style
    sheet and by nothing else.
    """
    from ui import gov_theme

    gov_theme.prepare()

    from main2 import MainWindow

    window = MainWindow(session, accounts)
    gov_theme.dress(window)
    return window


def main(argv: list[str] | None = None) -> int:
    """Launch build 2 and return the Qt exit code."""
    _require_pyqt6()

    from main2 import create_application

    from ui import gov_theme
    from main2 import run_signed_in

    app = create_application(argv if argv is not None else sys.argv)
    gov_theme.prepare()
    return run_signed_in(app, build_window, gov_theme.STYLESHEET)


if __name__ == "__main__":
    raise SystemExit(main())
