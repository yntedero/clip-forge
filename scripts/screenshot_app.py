"""Headless screenshot helper: builds MainWindow, grabs PNGs, and exits.

Usage:
    uv run python scripts/screenshot_app.py [output_dir]

Skips drag/drop and FFmpeg execution — purely UI snapshot.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Force offscreen so this works on CI / no-display environments.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

OUT_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "screenshots").resolve()
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QApplication

    from clipforge.app import ClipForgeApp, MainWindow

    app = QApplication.instance() or ClipForgeApp([])

    window = MainWindow()
    window.resize(QSize(1280, 800))
    window.show()
    # Process events twice so Qt completes the show / layout pass.
    app.processEvents()
    app.processEvents()

    initial = OUT_DIR / "app-initial.png"
    pix = window.grab()
    pix.save(str(initial), "PNG")
    print(f"saved {initial}")

    # Simulate selecting a source: populate the drop zone display.
    test_video = Path(__file__).resolve().parents[1] / "test-video" / "test-video.mp4"
    if test_video.is_file():
        window.set_source(test_video)
        app.processEvents()
        loaded = OUT_DIR / "app-source-loaded.png"
        window.grab().save(str(loaded), "PNG")
        print(f"saved {loaded}")

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
