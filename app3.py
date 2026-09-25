"""SENTRA - build 3, in the Flowbite admin dashboard design.

Oil India Limited - Problem Statement 26165.

    python app3.py

The same console as ``app.py`` and ``app2.py`` - the same controller
(``main2.py``), the same pages, the same sign-in, roles and audit trail - in
the design of ``tedo001/sample-ui-1``, the Flowbite admin dashboard: a grey-50
page, a white sidebar with grey icons, white bordered cards, primary-700 blue
buttons and uppercase table headings. See :mod:`ui.flowbite_theme` for where
each value comes from in the template.

Nothing in ``app.py`` or ``app2.py`` changes. A skin is a palette applied
before the window is built and a style sheet applied after, and each entry
point applies its own; the three windows differ in appearance and in nothing
else, so a fix to any capability lands in all of them.
"""

from __future__ import annotations

import sys

#: Shown in the title bar, so an operator running several builds side by side
#: can tell which window is which.
WINDOW_TITLE = "SENTRA - build 3"


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
    """Construct the console in the Flowbite design, for ``session``.

    The palette goes on first and the window is built second: every widget that
    styles itself reads the palette in its constructor. Without a session the
    window runs unattended - which :func:`main` never does; it signs someone in
    first.
    """
    from ui import flowbite_theme

    flowbite_theme.prepare()

    from main2 import MainWindow

    window = MainWindow(session, accounts)
    flowbite_theme.dress(window)
    window.setWindowTitle(WINDOW_TITLE)
    return window


def main(argv: list[str] | None = None) -> int:
    """Sign in, then launch build 3; return the Qt exit code."""
    _require_pyqt6()

    from main2 import create_application, run_signed_in
    from ui import flowbite_theme

    application = create_application(argv if argv is not None else sys.argv)
    flowbite_theme.prepare()
    return run_signed_in(application, build_window, flowbite_theme.STYLESHEET)


if __name__ == "__main__":
    raise SystemExit(main())
