"""Application bootstrap.

Exposes :class:`ClipForgeApp` (a :class:`QApplication` subclass), the
:func:`build_main_window` factory used by both tests and the runtime, and
:func:`run` which is the entry point for ``python -m clipforge``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow

from clipforge import constants
from clipforge.version import __version__


def _load_m0_stylesheet() -> str:
    """Read the M0 stylesheet from the packaged ``resources/themes/`` dir.

    Works both in a dev checkout and (eventually) under PyInstaller's
    ``sys._MEIPASS`` layout.
    """
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        candidates.append(Path(meipass) / "resources" / "themes" / "m0.qss")
    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / "resources" / "themes" / "m0.qss")

    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8")

    raise FileNotFoundError(f"M0 stylesheet not found in any of: {[str(p) for p in candidates]}")


class ClipForgeApp(QApplication):
    """QApplication subclass for ClipForge.

    Provides a hook point for future bootstrap concerns (font loading,
    theme registry, signal wiring). At M0 it just sets app identity and
    applies the minimal stylesheet.
    """

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setOrganizationName(constants.APP_ORG)
        self.setOrganizationDomain(constants.APP_ORG_DOMAIN)
        self.setApplicationName(constants.APP_NAME)
        self.setApplicationVersion(__version__)
        self.setStyleSheet(_load_m0_stylesheet())


def build_main_window() -> QMainWindow:
    """Construct the main window without showing it.

    Kept separate from :func:`run` so tests can build the window without
    starting the Qt event loop.
    """
    window = QMainWindow()
    window.setWindowTitle(constants.WINDOW_TITLE)
    window.setMinimumSize(constants.WINDOW_MIN_WIDTH, constants.WINDOW_MIN_HEIGHT)
    window.resize(constants.WINDOW_DEFAULT_WIDTH, constants.WINDOW_DEFAULT_HEIGHT)
    return window


def run() -> int:
    """Run the application: build the app, show the window, enter the loop."""
    app = ClipForgeApp(sys.argv)
    window = build_main_window()
    window.show()
    return app.exec()
