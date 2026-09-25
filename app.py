"""SENTRA - black-and-lime build. Oil India Limited, Problem Statement 26165.

Run with::

    python app.py

The same console as ``app2.py``, in the supplied design: black cards and a
black navigation rail on a warm charcoal ground, everything in capitals with
the rail numbered 01, 02, 03, and one vivid lime carrying the wordmark, every
control and the page you are on. Every capability is the one implementation -
the
workflow map, multilingual OCR, translation, the dashboard, hotspots, the human
review bench, analytics, training and the audit trail - so a fix to any of them
lands in both builds at once and neither can drift into being a stale copy of
the other.

Why a skin rather than a second application: duplicating the controller and its
pages to restyle them would mean two copies of every rule about when a report
reaches a person, and the copies would disagree within a week. The re-skin is
delivered in two halves instead, because a Qt style sheet alone cannot reach a
widget that paints itself:

1. :func:`ui.theme.apply_palette` repoints the shared colours *before* the
   window is built, which catches the badges, KPI values, chart series and the
   brand mark.
2. :data:`ui.green_theme.STYLESHEET` is set on the window afterwards, and
   carries the structure - square black cards, pill-shaped buttons, the page
   heading on its own raised band, and the rule that clears the plain widgets
   inside the rail so none of them lays a block of the charcoal over the black.

On a light ground the first half is what keeps the console readable rather than
merely consistent: a badge, a chart series or a nav icon left on a dark skin's
colour is not off-key here, it is invisible. That is why the palette carries
``ICON_ON`` and the three ``RAIL_*`` names as well as the surfaces - the
selected navigation icon and the rail's safety card are painted in code, not in
the style sheet. Column headings in capitals come from ``prepare()`` too, for a
related reason: Qt style sheets have no ``text-transform``.

``app2.py`` launches the same console in the deep-navy design.

Module map
----------
``sif/``
    The analysis stack, independent of Qt: ``ocr`` -> ``preprocessing`` ->
    ``encoders`` -> ``heads`` -> ``evidence`` -> ``scoring`` -> ``patterns`` /
    ``review``, orchestrated by ``pipeline.SIFPipeline``. ``lexical`` holds the
    deterministic rule layer, ``llm`` the optional local model, ``narrative``
    the generated briefs and bulletins, ``mlops`` the XGBoost model and
    ``audit`` the append-only trail.
``ui/``
    Shared presentation: ``theme`` (the console's own look, the shared colour
    table and the typographic switches), ``green_theme`` (this one),
    ``light_theme`` (white, grey and blue), ``gov_theme`` (the deep navy of
    ``app2.py``), ``charts``, ``components``.
``ui2/``
    The pages: navigation, workflow map, review bench, dashboards, settings.
``main2.py``
    The controller both builds run on.

Encoder selection
-----------------
    SIF_ENCODER=transformer|hashing|auto     # default: auto
    SIF_ENCODER_MODEL=<hub id or local dir>  # default: all-MiniLM-L6-v2

``auto`` uses the transformer when it loads and falls back to the offline
lexical engine otherwise, so the application always starts. XGBoost, MLflow,
PaddleOCR and Ollama are all detected at run time and the console runs without
any of them.
"""

from __future__ import annotations

import sys

#: Shown in the title bar, so an operator running both builds side by side can
#: tell which window is which.
WINDOW_TITLE = "SENTRA - black and lime"


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
    """Construct the console wearing the black-and-lime skin, for ``session``.

    The palette is applied first and the window built second: that order is the
    whole mechanism, because every widget that styles itself reads the palette
    in its constructor. Without a session the window runs unattended - which
    :func:`main` never does; it signs someone in first.
    """
    from ui import green_theme

    green_theme.prepare()

    from main2 import MainWindow

    window = MainWindow(session, accounts)
    green_theme.dress(window)
    window.setWindowTitle(WINDOW_TITLE)
    return window


def main(argv: list[str] | None = None) -> int:
    """Launch the desktop application and return the Qt exit code."""
    _require_pyqt6()

    from main2 import create_application

    from ui import green_theme
    from main2 import run_signed_in

    application = create_application(argv if argv is not None else sys.argv)
    green_theme.prepare()
    return run_signed_in(application, build_window, green_theme.STYLESHEET)


if __name__ == "__main__":
    raise SystemExit(main())
