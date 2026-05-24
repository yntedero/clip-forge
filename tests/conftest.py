"""Shared pytest configuration.

Sets ``QT_QPA_PLATFORM=offscreen`` before any Qt import so the test suite can
run in CI / headless environments.
"""

from __future__ import annotations

import os

# Must be set BEFORE PySide6 is imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


import pytest


@pytest.fixture(scope="session")
def qapp(qapp_args):  # type: ignore[no-untyped-def]
    """Session-scoped QApplication using ClipForgeApp so stylesheet is loaded."""
    from PySide6.QtWidgets import QApplication

    from clipforge.app import ClipForgeApp

    existing = QApplication.instance()
    if isinstance(existing, ClipForgeApp):
        yield existing
    else:
        app = ClipForgeApp(qapp_args)
        yield app
        app.quit()
