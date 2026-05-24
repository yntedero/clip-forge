"""Application bootstrap and main window.

Wires the core domain to a functional PySide6 UI: drop or browse for a
video, pick a preset, choose an output folder, hit Start, watch clips
appear in the output folder.

The full Neon Cut design system arrives in later releases; this is the
minimum viable UI for v1.0.1.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from clipforge import constants
from clipforge.core.models import JobSpec, Preset
from clipforge.core.presets import discover_builtins
from clipforge.infra.paths import default_output_dir, ffmpeg_path, resources_dir
from clipforge.job_runner import JobRunner
from clipforge.version import __version__

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".m4v",
    ".flv",
    ".mts",
    ".m2ts",
    ".wmv",
    ".ts",
}


def _load_stylesheet() -> str:
    """Read the bundled stylesheet from ``resources/themes/m0.qss``."""
    path = resources_dir() / "themes" / "m0.qss"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    repo_fallback = Path(__file__).resolve().parents[2] / "resources" / "themes" / "m0.qss"
    if repo_fallback.is_file():
        return repo_fallback.read_text(encoding="utf-8")
    return ""


class ClipForgeApp(QApplication):
    """QApplication subclass that sets identity and loads the stylesheet."""

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setOrganizationName(constants.APP_ORG)
        self.setOrganizationDomain(constants.APP_ORG_DOMAIN)
        self.setApplicationName(constants.APP_NAME)
        self.setApplicationVersion(__version__)
        self.setStyleSheet(_load_stylesheet())


def _load_m0_stylesheet() -> str:  # pragma: no cover — back-compat shim
    text = _load_stylesheet()
    if not text:
        raise FileNotFoundError("M0 stylesheet not found in any of: [resources/themes/m0.qss]")
    return text


class DropZone(QFrame):
    """Clickable drop target that hands the chosen path to the parent window."""

    def __init__(self, parent: MainWindow) -> None:
        super().__init__(parent)
        self._main = parent
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setProperty("dragOver", False)
        self.setMinimumHeight(180)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon = QLabel("✂", self)
        self._icon.setStyleSheet("color: #D946EF; font-size: 48px;")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon)

        self._title = QLabel("Drop a video here, or click to browse", self)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setProperty("role", "subtitle")
        layout.addWidget(self._title)

        self._hint = QLabel(
            "Supported: " + ", ".join(sorted(VIDEO_EXTENSIONS)),
            self,
        )
        self._hint.setProperty("role", "caption")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: object) -> None:  # noqa: N802
        # Qt requires PascalCase names; we accept QMouseEvent but type as object
        # to dodge mypy on Qt's untyped event class.
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent

        if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
            self._main.open_file_dialog()
        if isinstance(event, QEvent):
            super().mousePressEvent(event)  # type: ignore[arg-type]

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in VIDEO_EXTENSIONS:
                    event.acceptProposedAction()
                    self.setProperty("dragOver", True)
                    self.style().unpolish(self)
                    self.style().polish(self)
                    return
        event.ignore()

    def dragLeaveEvent(self, event: object) -> None:  # noqa: N802
        self.setProperty("dragOver", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        self.setProperty("dragOver", False)
        self.style().unpolish(self)
        self.style().polish(self)
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.suffix.lower() in VIDEO_EXTENSIONS:
                    self._main.set_source(path)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def set_loaded(self, path: Path) -> None:
        self._icon.setText("🎬")
        self._title.setText(path.name)
        self._hint.setText(f"{path.parent}")


class MainWindow(QMainWindow):
    """The single primary window for v1.0.1."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(constants.WINDOW_TITLE)
        self.setMinimumSize(constants.WINDOW_MIN_WIDTH, constants.WINDOW_MIN_HEIGHT)
        self.resize(constants.WINDOW_DEFAULT_WIDTH, constants.WINDOW_DEFAULT_HEIGHT)

        self._source_path: Path | None = None
        self._presets: list[Preset] = []
        self._runner = JobRunner(self)
        self._runner.progress.connect(self._on_progress)
        self._runner.clip_finished.connect(self._on_clip_finished)
        self._runner.job_finished.connect(self._on_job_finished)
        self._runner.job_failed.connect(self._on_job_failed)
        self._runner.log.connect(self._on_log)

        central = QWidget(self)
        central.setObjectName("central")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(32, 28, 32, 24)
        outer.setSpacing(20)

        heading = QLabel("ClipForge", central)
        heading.setProperty("role", "heading")
        outer.addWidget(heading)

        tagline = QLabel(
            "Slice long videos into short clips with subtle randomized effects.",
            central,
        )
        tagline.setProperty("role", "subtitle")
        outer.addWidget(tagline)

        self._drop = DropZone(self)
        outer.addWidget(self._drop)

        config_row = QHBoxLayout()
        config_row.setSpacing(16)

        preset_card = QFrame(central)
        preset_card.setObjectName("card")
        preset_layout = QVBoxLayout(preset_card)
        preset_layout.setContentsMargins(16, 14, 16, 14)
        pl = QLabel("Preset", preset_card)
        pl.setProperty("role", "subtitle")
        preset_layout.addWidget(pl)
        self._preset_combo = QComboBox(preset_card)
        preset_layout.addWidget(self._preset_combo)
        config_row.addWidget(preset_card, 1)

        out_card = QFrame(central)
        out_card.setObjectName("card")
        out_layout = QVBoxLayout(out_card)
        out_layout.setContentsMargins(16, 14, 16, 14)
        ol = QLabel("Output folder", out_card)
        ol.setProperty("role", "subtitle")
        out_layout.addWidget(ol)
        out_row = QHBoxLayout()
        self._out_field = QLineEdit(str(default_output_dir()), out_card)
        out_row.addWidget(self._out_field, 1)
        self._out_browse = QPushButton("Browse…", out_card)
        self._out_browse.setProperty("role", "secondary")
        self._out_browse.clicked.connect(self._choose_output_dir)
        out_row.addWidget(self._out_browse)
        self._out_open = QPushButton("Open", out_card)
        self._out_open.setProperty("role", "secondary")
        self._out_open.clicked.connect(self._open_output_dir)
        out_row.addWidget(self._out_open)
        out_layout.addLayout(out_row)
        config_row.addWidget(out_card, 2)

        outer.addLayout(config_row)

        self._progress = QProgressBar(central)
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setFormat("Idle")
        outer.addWidget(self._progress)

        self._log = QPlainTextEdit(central)
        self._log.setObjectName("logView")
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(120)
        outer.addWidget(self._log, 1)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self._cancel_btn = QPushButton("Cancel", central)
        self._cancel_btn.setProperty("role", "secondary")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel)
        action_row.addWidget(self._cancel_btn)
        self._start_btn = QPushButton("Start", central)
        self._start_btn.setObjectName("startButton")
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._start_job)
        action_row.addWidget(self._start_btn)
        outer.addLayout(action_row)

        sb = QStatusBar(self)
        self.setStatusBar(sb)
        ffmpeg_present = ffmpeg_path().is_file()
        ffmpeg_status = (
            "FFmpeg ready" if ffmpeg_present else "⚠ FFmpeg missing — run scripts/fetch_ffmpeg.py"
        )
        sb.showMessage(f"v{__version__}  •  {ffmpeg_status}")
        if not ffmpeg_present:
            self._append_log(
                "WARNING: FFmpeg binaries not found in resources/ffmpeg/. "
                "Run `uv run python scripts/fetch_ffmpeg.py` once before "
                "starting a job."
            )

        self._load_presets()

    def open_file_dialog(self) -> None:
        filters = (
            "Videos ("
            + " ".join(f"*{ext}" for ext in sorted(VIDEO_EXTENSIONS))
            + ");;All files (*.*)"
        )
        path_str, _ = QFileDialog.getOpenFileName(self, "Choose a source video", "", filters)
        if path_str:
            self.set_source(Path(path_str))

    def set_source(self, path: Path) -> None:
        self._source_path = path
        self._drop.set_loaded(path)
        self._update_start_enabled()
        self._append_log(f"Selected source: {path}")

    def _load_presets(self) -> None:
        try:
            self._presets = list(discover_builtins())
        except Exception as exc:
            QMessageBox.critical(
                self, "Preset load failed", f"Could not load built-in presets:\n{exc}"
            )
            self._presets = []
        self._preset_combo.clear()
        for p in self._presets:
            label = f"{p.name}  —  {p.description or ''}".strip(" -")
            self._preset_combo.addItem(label, p)
        self._update_start_enabled()

    def _update_start_enabled(self) -> None:
        ready = (
            self._source_path is not None
            and self._preset_combo.count() > 0
            and ffmpeg_path().is_file()
        )
        self._start_btn.setEnabled(ready)

    def _choose_output_dir(self) -> None:
        current = self._out_field.text() or str(default_output_dir())
        path_str = QFileDialog.getExistingDirectory(self, "Choose output folder", current)
        if path_str:
            self._out_field.setText(path_str)

    def _open_output_dir(self) -> None:
        path = Path(self._out_field.text())
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _start_job(self) -> None:
        if self._source_path is None or self._preset_combo.currentData() is None:
            return
        preset: Preset = self._preset_combo.currentData()
        out_root = Path(self._out_field.text()).expanduser()
        try:
            out_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Cannot create output folder", str(exc))
            return
        job = JobSpec(
            source_path=self._source_path,
            output_root=out_root,
            slicing=preset.slicing,
            effects=preset.effects,
            output=preset.output,
            mode=preset.mode,
            seed=None,
        )
        self._set_running(True)
        self._progress.setRange(0, 0)
        self._progress.setFormat("Preparing…")
        self._append_log(f"Starting job with preset “{preset.name}”")
        self._runner.run_async(job)

    def _cancel(self) -> None:
        self._runner.cancel()
        self._append_log("Cancellation requested.")

    def _set_running(self, running: bool) -> None:
        self._start_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)
        self._preset_combo.setEnabled(not running)
        self._drop.setEnabled(not running)
        self._out_field.setEnabled(not running)
        self._out_browse.setEnabled(not running)

    def _on_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)
        self._progress.setFormat(f"Clip {done} of {total}  •  %p%")

    def _on_clip_finished(self, path: str) -> None:
        self._append_log(f"✓ {path}")

    def _on_job_finished(self) -> None:
        self._set_running(False)
        if self._progress.maximum() == 0:
            self._progress.setRange(0, 1)
        self._progress.setValue(self._progress.maximum())
        self._progress.setFormat("Done")
        self._append_log("Job finished.")
        QMessageBox.information(
            self,
            "Job finished",
            "Your clips are ready in the output folder.",
        )

    def _on_job_failed(self, msg: str) -> None:
        self._set_running(False)
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setFormat("Failed")
        self._append_log(f"ERROR: {msg}")
        QMessageBox.critical(self, "Job failed", msg)

    def _on_log(self, line: str) -> None:
        self._append_log(line)

    def _append_log(self, line: str) -> None:
        self._log.appendPlainText(line)


def build_main_window() -> QMainWindow:
    """Construct (but do not show) the main window — handy for tests."""
    return MainWindow()


def run() -> int:  # pragma: no cover
    """Run the application: build the app, show the window, enter the loop."""
    app = ClipForgeApp(sys.argv)
    window = build_main_window()
    window.show()
    return app.exec()
