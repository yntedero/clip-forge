"""Cross-platform path resolution for bundled and dev layouts."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _bundle_root() -> Path | None:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        return Path(meipass)
    return None


def repo_root() -> Path:
    """Path to the project root in dev layout."""
    return Path(__file__).resolve().parents[3]


def resources_dir() -> Path:
    """Where bundled resources (themes, presets, ffmpeg) live."""
    bundle = _bundle_root()
    if bundle is not None:
        candidate = bundle / "resources"
        if candidate.is_dir():
            return candidate
    return repo_root() / "resources"


def ffmpeg_path() -> Path:
    """Locate the bundled FFmpeg binary."""
    name = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
    return resources_dir() / "ffmpeg" / name


def ffprobe_path() -> Path:
    """Locate the bundled ffprobe binary."""
    name = "ffprobe.exe" if sys.platform.startswith("win") else "ffprobe"
    return resources_dir() / "ffmpeg" / name


def default_output_dir() -> Path:
    """Where output clips go by default."""
    home = Path.home()
    return home / "ClipForge Output"


def app_data_dir() -> Path:
    """Persistent user data: settings, user presets, cache."""
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "ClipForge"
