"""Smoke tests proving the package imports and a window can be built."""

from __future__ import annotations

import pytest


def test_package_imports() -> None:
    import clipforge

    assert isinstance(clipforge.__version__, str)
    assert clipforge.__version__ == "0.0.1-dev"


def test_constants_present() -> None:
    from clipforge import constants

    assert constants.APP_NAME == "ClipForge"
    assert constants.WINDOW_TITLE == "ClipForge"
    assert isinstance(constants.WINDOW_DEFAULT_WIDTH, int)
    assert isinstance(constants.WINDOW_DEFAULT_HEIGHT, int)
    assert constants.WINDOW_DEFAULT_WIDTH >= constants.WINDOW_MIN_WIDTH
    assert constants.WINDOW_DEFAULT_HEIGHT >= constants.WINDOW_MIN_HEIGHT


@pytest.mark.qt
def test_app_window_opens(qtbot) -> None:  # type: ignore[no-untyped-def]
    """build_main_window returns a configured QMainWindow without crashing."""
    from clipforge.app import build_main_window

    window = build_main_window()
    qtbot.addWidget(window)

    assert window.windowTitle() == "ClipForge"
    assert window.minimumWidth() == 1024
    assert window.minimumHeight() == 700
    assert window.width() == 1280
    assert window.height() == 800


@pytest.mark.qt
def test_app_loads_stylesheet(qapp) -> None:  # type: ignore[no-untyped-def]
    """ClipForgeApp loads the M0 stylesheet on construction."""
    from clipforge.app import ClipForgeApp

    assert isinstance(qapp, ClipForgeApp), (
        f"Expected ClipForgeApp from the conftest qapp fixture, got {type(qapp).__name__}"
    )
    stylesheet = qapp.styleSheet()
    assert "QMainWindow" in stylesheet
    assert "#0A0612" in stylesheet


def test_load_m0_stylesheet_raises_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If neither candidate path resolves, _load_m0_stylesheet raises FileNotFoundError."""
    from clipforge import app

    monkeypatch.setattr("clipforge.app.Path.is_file", lambda self: False)

    with pytest.raises(FileNotFoundError, match="M0 stylesheet not found"):
        app._load_m0_stylesheet()
