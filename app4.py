"""SENTRA - build 4: two workspaces behind one sign-in.

Oil India Limited - Problem Statement 26165.

    python app4.py
    python app4.py --present      # everything 1.5x larger, for screenshots and slides

The design in the Stage 1 and Stage 2 sheets. One sign-in for everyone; the
account decides which workspace opens:

* **HSE workspace** - Home, Ingest, Dashboard, HSE Review, Risk Hotspots,
  Profile. For the people who analyse reports and decide cases.
* **Administration** - Engines, Settings, SysLog, Audit Log, New HSE Login,
  Profile. For the people who run the platform. An administrator does not
  decide review cases here: platform control and safety judgement stay in
  separate accounts.

The analysis, the review bench, the audit trail and every other capability are
the same code the other builds run (see :mod:`main4`). Nothing in app.py,
app2.py or app3.py changes, and the two-role model applies to this build only.
"""

from __future__ import annotations

import os
import sys

WINDOW_TITLE = "SENTRA"

#: ``--present`` (or SENTRA_PRESENT=1) scales the whole console - text, tables,
#: buttons, icons - so a screenshot of it stays readable on a projected slide.
PRESENT_FLAG = "--present"
#: How much larger; SENTRA_SCALE overrides it (1.25 for a smaller screen, 2 for 4K).
PRESENT_SCALE = "1.5"

_presenting = False


def presentation_requested(argv: list[str]) -> bool:
    return PRESENT_FLAG in argv or os.environ.get("SENTRA_PRESENT", "") not in ("", "0")


def enter_presentation(argv: list[str]) -> list[str]:
    """Scale the interface for slides; must run before the QApplication exists."""
    global _presenting
    _presenting = True
    os.environ.setdefault("QT_SCALE_FACTOR", os.environ.get("SENTRA_SCALE", PRESENT_SCALE))
    return [arg for arg in argv if arg != PRESENT_FLAG]


def _require_pyqt6() -> None:
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
    """The two-workspace console for ``session`` - palette first, then the window."""
    from ui import workspace_theme

    workspace_theme.prepare()

    from main4 import WorkspaceWindow

    window = WorkspaceWindow(session, accounts)
    workspace_theme.dress(window)
    window.setWindowTitle(WINDOW_TITLE)
    if _presenting:
        _fit_to_screen(window)
    return window


def _fit_to_screen(window) -> None:
    """Scaled up, the design minimum can outgrow the screen: shrink it, then fill it."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QGuiApplication

    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        room = screen.availableGeometry()
        window.setMinimumSize(min(window.MIN_WIDTH, room.width() - 16),
                              min(window.MIN_HEIGHT, room.height() - 48))
    window.setWindowState(window.windowState() | Qt.WindowState.WindowMaximized)


def main(argv: list[str] | None = None) -> int:
    """Sign in, open the workspace the account belongs to; return Qt's exit code."""
    _require_pyqt6()

    from main2 import create_application, run_signed_in
    from ui import workspace_theme

    argv = list(argv if argv is not None else sys.argv)
    if presentation_requested(argv):
        argv = enter_presentation(argv)
    application = create_application(argv)
    workspace_theme.prepare()
    return run_signed_in(application, build_window, workspace_theme.STYLESHEET)


if __name__ == "__main__":
    raise SystemExit(main())
