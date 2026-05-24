"""Real-window screenshot capture for v1.0.3 verification.

Uses the native Windows Qt platform plugin (NOT offscreen) so the
captures reflect real Segoe UI rendering, real cyan, real layout. Runs
the event loop briefly, takes the snapshot, switches states, repeats.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# IMPORTANT: do not force offscreen — we want the real Windows backend.
os.environ.pop("QT_QPA_PLATFORM", None)

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from clipforge.app import ClipForgeApp, MainWindow
from clipforge.i18n import manager as i18n_manager

OUT = Path(__file__).resolve().parents[1] / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def _flush(app: QApplication, ms: int = 200) -> None:
    """Pump the event loop for ``ms`` milliseconds so Qt finishes painting."""
    timer = QTimer()
    timer.setSingleShot(True)
    timer.start(ms)
    while timer.isActive():
        app.processEvents()


def main() -> int:
    existing = QApplication.instance()
    app = existing if isinstance(existing, ClipForgeApp) else ClipForgeApp(sys.argv)

    window = MainWindow()
    window.resize(1280, 800)
    window.show()
    _flush(app, 400)
    window.grab().save(str(OUT / "v1.0.3-real-initial.png"), "PNG")
    print(f"saved {OUT / 'v1.0.3-real-initial.png'}")

    # Load the test video so we see the populated drop bar.
    test_video = Path(__file__).resolve().parents[1] / "test-video" / "test-video.mp4"
    if test_video.is_file():
        window.set_source(test_video)
        _flush(app, 300)
        window.grab().save(str(OUT / "v1.0.3-real-source-loaded.png"), "PNG")
        print(f"saved {OUT / 'v1.0.3-real-source-loaded.png'}")

    # Switch to Instagram Reels tab.
    window._tabs.set_active("Instagram Reels", emit=True)
    _flush(app, 300)
    window.grab().save(str(OUT / "v1.0.3-real-instagram.png"), "PNG")
    print(f"saved {OUT / 'v1.0.3-real-instagram.png'}")

    # Switch language to Ukrainian.
    i18n_manager().set_locale("uk")
    _flush(app, 300)
    window.grab().save(str(OUT / "v1.0.3-real-ukrainian.png"), "PNG")
    print(f"saved {OUT / 'v1.0.3-real-ukrainian.png'}")

    # Custom tab — switch back to English, click Custom.
    i18n_manager().set_locale("en")
    window._tabs.set_active("Custom", emit=True)
    _flush(app, 300)
    window.grab().save(str(OUT / "v1.0.3-real-custom.png"), "PNG")
    print(f"saved {OUT / 'v1.0.3-real-custom.png'}")

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
