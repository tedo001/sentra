"""SENTRA - Serious-injury and fatality precursor detection for Oil India Limited.

Problem Statement 26165.

    python sentra.py
    python sentra.py --present      # everything 1.5x larger, for screenshots and slides

One sign-in; the account decides the workspace.

* **HSE workspace** - Home, Ingest, Dashboard, HSE Review, Action Items, Risk
  Hotspots, Profile.
* **Administration** - Engines, Settings, SysLog, Audit Log, New HSE Login,
  Data & Backup, Profile.

Every capability of the console (analysis, review bench, hash-chained audit
trail, compliance calendar, training) plus a local SQL database, a vector
index for similar-report search, encrypted cloud backup, and the local LLM
``gemma2:latest`` switched on from the start. See :mod:`main5`.
"""

from __future__ import annotations

import sys

import app4

WINDOW_TITLE = "SENTRA"


def build_window(session=None, accounts=None, **options):
    """The SENTRA console for ``session`` - theme first, then the window."""
    from ui import sentra_theme

    sentra_theme.prepare()

    from main5 import SentraWindow

    window = SentraWindow(session, accounts, **options)
    sentra_theme.dress(window)
    window.setWindowTitle(WINDOW_TITLE)
    if app4._presenting:
        app4._fit_to_screen(window)
    return window


def main(argv: list[str] | None = None) -> int:
    """Sign in, open the workspace the account belongs to; return Qt's exit code."""
    app4._require_pyqt6()

    from main2 import create_application, run_signed_in
    from ui import sentra_theme

    argv = list(argv if argv is not None else sys.argv)
    if app4.presentation_requested(argv):
        argv = app4.enter_presentation(argv)
    application = create_application(argv)
    application.setApplicationDisplayName(WINDOW_TITLE)
    sentra_theme.prepare()
    from ui5.login import SentraLogin

    return run_signed_in(application, build_window, sentra_theme.STYLESHEET,
                         dialog_class=SentraLogin)


if __name__ == "__main__":
    raise SystemExit(main())
