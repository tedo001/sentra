"""Background jobs for the data features, beside the console's one worker slot.

The console runs one analysis or training job at a time (``MainWindow._start``).
Syncing, backing up, embedding and asking the LLM host whether it is up are
different kinds of work - network and disk, not the model - and must not be
refused because an import is running, nor block one. Each gets a :class:`Task`
of its own; the window keeps a reference until it finishes.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QThread, pyqtSignal

__all__ = ["Task"]


class Task(QThread):
    """Run ``job()`` off the GUI thread; ``done(ok, result_or_message)`` on the GUI thread."""

    done = pyqtSignal(bool, object)
    progress = pyqtSignal(str)

    def __init__(self, name: str, job: Callable[["Task"], object], parent=None) -> None:
        super().__init__(parent)
        self.name = name
        self.job = job

    def run(self) -> None:  # noqa: D401 - QThread entry point
        try:
            result = self.job(self)
        except Exception as exc:  # noqa: BLE001 - reported on screen and in the log
            text = str(exc) or type(exc).__name__
            self.done.emit(False, text if type(exc).__name__ == "BackupError"
                           else f"{type(exc).__name__}: {text}")
            return
        self.done.emit(True, result)
