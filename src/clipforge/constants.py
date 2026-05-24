"""Application-wide constants.

Values that are configuration (e.g. window dimensions, app identity) and
need to be referenced from multiple places. Anything that might become
user-configurable lives in settings, not here.
"""

from __future__ import annotations

from typing import Final

APP_NAME: Final[str] = "ClipForge"
APP_ORG: Final[str] = "ClipForge"
APP_ORG_DOMAIN: Final[str] = "clipforge.app"

WINDOW_TITLE: Final[str] = "ClipForge"
WINDOW_DEFAULT_WIDTH: Final[int] = 1280
WINDOW_DEFAULT_HEIGHT: Final[int] = 800
WINDOW_MIN_WIDTH: Final[int] = 1024
WINDOW_MIN_HEIGHT: Final[int] = 700
