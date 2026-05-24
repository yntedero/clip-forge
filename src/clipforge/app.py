"""Application bootstrap and main window.

UI: drop or browse for a video, pick a preset (card grid; Custom expands
into a configurator), pick an output folder, hit Start, watch clips
appear in the output folder. Footer flag toggles between English and
Ukrainian.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from clipforge import constants
from clipforge.core.models import (
    EffectsConfig,
    EffectSettings,
    JobSpec,
    OutputConfig,
    Preset,
    SlicingConfig,
)
from clipforge.core.presets import discover_builtins
from clipforge.i18n import manager as i18n_manager
from clipforge.i18n import tr
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

EFFECT_ORDER = (
    ("mirror", "Mirror"),
    ("zoom", "Zoom"),
    ("speed", "Speed"),
    ("color", "Color"),
    ("rotation", "Rotation"),
    ("edge_crop", "Edge crop"),
    ("noise", "Noise"),
    ("vignette", "Vignette"),
    ("pixel_shift", "Pixel shift"),
    ("film_grain", "Film grain"),
)


def _load_stylesheet() -> str:
    path = resources_dir() / "themes" / "m0.qss"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    repo_fallback = Path(__file__).resolve().parents[2] / "resources" / "themes" / "m0.qss"
    if repo_fallback.is_file():
        return repo_fallback.read_text(encoding="utf-8")
    return ""


def _icon_path() -> Path | None:
    """Find the app icon (.ico preferred, .png fallback)."""
    candidates = [
        resources_dir() / "icons" / "app.ico",
        resources_dir() / "icons" / "app.png",
        Path(__file__).resolve().parents[2] / "resources" / "icons" / "app.ico",
        Path(__file__).resolve().parents[2] / "resources" / "icons" / "app.png",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _app_icon() -> QIcon:
    p = _icon_path()
    if p is None:
        return QIcon()
    return QIcon(str(p))


class ClipForgeApp(QApplication):
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setOrganizationName(constants.APP_ORG)
        self.setOrganizationDomain(constants.APP_ORG_DOMAIN)
        self.setApplicationName(constants.APP_NAME)
        self.setApplicationVersion(__version__)
        self.setStyleSheet(_load_stylesheet())
        icon = _app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)


def _load_m0_stylesheet() -> str:  # pragma: no cover - back-compat shim
    text = _load_stylesheet()
    if not text:
        raise FileNotFoundError("M0 stylesheet not found in any of: [resources/themes/m0.qss]")
    return text


class DropZone(QFrame):
    def __init__(self, parent: MainWindow) -> None:
        super().__init__(parent)
        self._main = parent
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setProperty("dragOver", False)
        self.setMinimumHeight(180)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_path = _icon_path()
        if icon_path is not None and icon_path.suffix == ".png":
            self._icon = QLabel(self)
            pix = QPixmap(str(icon_path)).scaledToHeight(
                72, Qt.TransformationMode.SmoothTransformation
            )
            self._icon.setPixmap(pix)
        else:
            self._icon = QLabel("✂", self)  # scissors codepoint
            self._icon.setStyleSheet("color: #22D3EE; font-size: 52px; font-weight: 700;")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon)

        self._title = QLabel(tr("Drop a video here, or click to browse"), self)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setProperty("role", "subtitle")
        layout.addWidget(self._title)

        self._hint = QLabel(
            tr("Supported:") + " " + ", ".join(sorted(VIDEO_EXTENSIONS)),
            self,
        )
        self._hint.setProperty("role", "caption")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def retranslate(self) -> None:
        if self._main.source_path is None:
            self._title.setText(tr("Drop a video here, or click to browse"))
            self._hint.setText(tr("Supported:") + " " + ", ".join(sorted(VIDEO_EXTENSIONS)))

    def mousePressEvent(self, event: object) -> None:  # noqa: N802
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
        self._icon.setText("▶")  # play triangle
        self._icon.setStyleSheet("color: #22D3EE; font-size: 52px; font-weight: 700;")
        self._title.setText(path.name)
        self._hint.setText(str(path.parent))


class PresetCard(QFrame):
    """Single selectable preset tile."""

    def __init__(
        self,
        preset_or_name: Preset | str,
        description: str,
        parent: QWidget,
        on_click: Callable[[PresetCard], None],
    ) -> None:
        super().__init__(parent)
        self.setObjectName("presetCard")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(72)
        self._on_click = on_click
        self.preset: Preset | str = preset_or_name

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)
        name = preset_or_name.name if isinstance(preset_or_name, Preset) else preset_or_name
        self._name = QLabel(tr(name), self)
        self._name.setStyleSheet("color: #ECFEFF; font-weight: 600; font-size: 14px;")
        layout.addWidget(self._name)
        self._desc = QLabel(tr(description), self)
        self._desc.setProperty("role", "caption")
        self._desc.setWordWrap(True)
        layout.addWidget(self._desc)

        self._source_name = name
        self._source_desc = description

    def retranslate(self) -> None:
        self._name.setText(tr(self._source_name))
        self._desc.setText(tr(self._source_desc))

    def set_selected(self, value: bool) -> None:
        self.setProperty("selected", value)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event: object) -> None:  # noqa: N802
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent

        if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self)
        if isinstance(event, QEvent):
            super().mousePressEvent(event)  # type: ignore[arg-type]


class CustomConfigPanel(QFrame):
    """Configurator for the Custom preset - every dial exposed."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)

        self._title = QLabel(tr("Custom") + " - " + tr("Configure everything yourself"), self)
        self._title.setStyleSheet("color: #ECFEFF; font-weight: 600;")
        outer.addWidget(self._title)

        # Length range
        len_row = QHBoxLayout()
        self._min_label = QLabel(tr("min"), self)
        self._min_label.setProperty("role", "caption")
        len_row.addWidget(self._min_label)
        self._min_value = QLabel("3.0s", self)
        len_row.addWidget(self._min_value)
        self._min_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._min_slider.setRange(5, 600)
        self._min_slider.setValue(30)
        self._min_slider.valueChanged.connect(self._on_min_changed)
        len_row.addWidget(self._min_slider, 1)
        outer.addLayout(len_row)

        max_row = QHBoxLayout()
        self._max_label = QLabel(tr("max"), self)
        self._max_label.setProperty("role", "caption")
        max_row.addWidget(self._max_label)
        self._max_value = QLabel("8.0s", self)
        max_row.addWidget(self._max_value)
        self._max_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._max_slider.setRange(5, 600)
        self._max_slider.setValue(80)
        self._max_slider.valueChanged.connect(self._on_max_changed)
        max_row.addWidget(self._max_slider, 1)
        outer.addLayout(max_row)

        # Output config row
        out_row = QHBoxLayout()
        out_row.setSpacing(10)
        self._aspect_label = QLabel(tr("Aspect ratio"), self)
        self._aspect_label.setProperty("role", "caption")
        out_row.addWidget(self._aspect_label)
        self._aspect = QComboBox(self)
        for value, label in (
            ("original", "Original"),
            ("9:16", "9:16"),
            ("16:9", "16:9"),
            ("1:1", "1:1"),
            ("4:5", "4:5"),
        ):
            self._aspect.addItem(tr(label) if label == "Original" else label, value)
        self._aspect.setCurrentIndex(1)
        out_row.addWidget(self._aspect, 1)

        self._codec_label = QLabel(tr("Codec"), self)
        self._codec_label.setProperty("role", "caption")
        out_row.addWidget(self._codec_label)
        self._codec = QComboBox(self)
        for value, label in (
            ("libx264", "H.264 (libx264)"),
            ("libx265", "H.265 (libx265)"),
            ("h264_nvenc", "H.264 NVENC"),
            ("h264_qsv", "H.264 QSV"),
            ("h264_amf", "H.264 AMF"),
        ):
            self._codec.addItem(label, value)
        out_row.addWidget(self._codec, 1)

        self._quality_label = QLabel(tr("Quality"), self)
        self._quality_label.setProperty("role", "caption")
        out_row.addWidget(self._quality_label)
        self._quality = QComboBox(self)
        for value, label in (
            ("fast", "Fast"),
            ("balanced", "Balanced"),
            ("high", "High Quality"),
        ):
            self._quality.addItem(tr(label), value)
        self._quality.setCurrentIndex(1)
        out_row.addWidget(self._quality, 1)
        outer.addLayout(out_row)

        # Audio mode
        audio_row = QHBoxLayout()
        self._audio_label = QLabel(tr("Audio"), self)
        self._audio_label.setProperty("role", "caption")
        audio_row.addWidget(self._audio_label)
        self._audio = QComboBox(self)
        for value, label in (
            ("keep", "Keep audio"),
            ("mute", "Mute"),
            ("remove", "Remove track"),
        ):
            self._audio.addItem(tr(label), value)
        audio_row.addWidget(self._audio, 1)
        self._pitch = QCheckBox(tr("Pitch preservation"), self)
        audio_row.addWidget(self._pitch)
        outer.addLayout(audio_row)

        # Global intensity
        gi_row = QHBoxLayout()
        self._gi_label = QLabel(tr("Global intensity"), self)
        self._gi_label.setProperty("role", "caption")
        gi_row.addWidget(self._gi_label)
        self._gi_value = QLabel("100%", self)
        gi_row.addWidget(self._gi_value)
        self._gi_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._gi_slider.setRange(0, 150)
        self._gi_slider.setValue(100)
        self._gi_slider.valueChanged.connect(lambda v: self._gi_value.setText(f"{v}%"))
        gi_row.addWidget(self._gi_slider, 1)
        outer.addLayout(gi_row)

        # Effects grid
        self._effects_heading = QLabel(tr("Effects"), self)
        self._effects_heading.setProperty("role", "subtitle")
        outer.addWidget(self._effects_heading)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        self._effect_checks: dict[str, QCheckBox] = {}
        self._effect_sliders: dict[str, QSlider] = {}
        self._effect_value_labels: dict[str, QLabel] = {}
        self._effect_label_sources: dict[str, str] = {}

        for row, (field, label) in enumerate(EFFECT_ORDER):
            cb = QCheckBox(tr(label), self)
            cb.setChecked(True)
            grid.addWidget(cb, row, 0)
            slider = QSlider(Qt.Orientation.Horizontal, self)
            slider.setRange(0, 100)
            slider.setValue(60)
            grid.addWidget(slider, row, 1)
            val = QLabel("60%", self)
            val.setProperty("role", "caption")
            slider.valueChanged.connect(lambda v, lbl=val: lbl.setText(f"{v}%"))
            grid.addWidget(val, row, 2)
            self._effect_checks[field] = cb
            self._effect_sliders[field] = slider
            self._effect_value_labels[field] = val
            self._effect_label_sources[field] = label
        outer.addLayout(grid)

    def retranslate(self) -> None:
        self._title.setText(tr("Custom") + " - " + tr("Configure everything yourself"))
        self._min_label.setText(tr("min"))
        self._max_label.setText(tr("max"))
        self._aspect_label.setText(tr("Aspect ratio"))
        self._codec_label.setText(tr("Codec"))
        self._quality_label.setText(tr("Quality"))
        self._audio_label.setText(tr("Audio"))
        self._gi_label.setText(tr("Global intensity"))
        self._effects_heading.setText(tr("Effects"))
        self._pitch.setText(tr("Pitch preservation"))
        idx = self._aspect.findData("original")
        if idx >= 0:
            self._aspect.setItemText(idx, tr("Original"))
        label_map_q = {"fast": "Fast", "balanced": "Balanced", "high": "High Quality"}
        for i in range(self._quality.count()):
            data = self._quality.itemData(i)
            if data in label_map_q:
                self._quality.setItemText(i, tr(label_map_q[data]))
        label_map_a = {"keep": "Keep audio", "mute": "Mute", "remove": "Remove track"}
        for i in range(self._audio.count()):
            data = self._audio.itemData(i)
            if data in label_map_a:
                self._audio.setItemText(i, tr(label_map_a[data]))
        for field, label_src in self._effect_label_sources.items():
            self._effect_checks[field].setText(tr(label_src))

    def _on_min_changed(self, value: int) -> None:
        seconds = value / 10.0
        self._min_value.setText(f"{seconds:.1f}s")
        if value > self._max_slider.value():
            self._max_slider.setValue(value)

    def _on_max_changed(self, value: int) -> None:
        seconds = value / 10.0
        self._max_value.setText(f"{seconds:.1f}s")
        if value < self._min_slider.value():
            self._min_slider.setValue(value)

    def build_preset(self) -> Preset:
        min_len = self._min_slider.value() / 10.0
        max_len = self._max_slider.value() / 10.0
        slicing = SlicingConfig(
            strategy="sequential",
            min_length_sec=min_len,
            max_length_sec=max_len,
        )
        effects_kwargs: dict[str, EffectSettings] = {}
        for field, _ in EFFECT_ORDER:
            checked = self._effect_checks[field].isChecked()
            intensity = self._effect_sliders[field].value() / 100.0
            effects_kwargs[field] = EffectSettings(
                enabled=checked,
                intensity=intensity,
                probability=1.0,
            )
        effects = EffectsConfig(
            global_intensity=self._gi_slider.value() / 100.0,
            mirror=effects_kwargs["mirror"],
            zoom=effects_kwargs["zoom"],
            speed=effects_kwargs["speed"],
            color=effects_kwargs["color"],
            rotation=effects_kwargs["rotation"],
            edge_crop=effects_kwargs["edge_crop"],
            noise=effects_kwargs["noise"],
            vignette=effects_kwargs["vignette"],
            pixel_shift=effects_kwargs["pixel_shift"],
            film_grain=effects_kwargs["film_grain"],
            pitch_preservation=self._pitch.isChecked(),
        )
        output = OutputConfig(
            aspect=self._aspect.currentData(),
            codec=self._codec.currentData(),
            quality=self._quality.currentData(),
            audio_mode=self._audio.currentData(),
        )
        return Preset(
            name="Custom",
            description="Configure everything yourself",
            builtin=False,
            slicing=slicing,
            effects=effects,
            output=output,
            mode="clips",
        )


class MainWindow(QMainWindow):
    """The single primary window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(constants.WINDOW_TITLE)
        self.setMinimumSize(constants.WINDOW_MIN_WIDTH, constants.WINDOW_MIN_HEIGHT)
        self.resize(constants.WINDOW_DEFAULT_WIDTH, constants.WINDOW_DEFAULT_HEIGHT + 60)
        icon = _app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self.source_path: Path | None = None
        self._presets: list[Preset] = []
        self._preset_cards: list[PresetCard] = []
        self._selected_card: PresetCard | None = None

        self._runner = JobRunner(self)
        self._runner.progress.connect(self._on_progress)
        self._runner.clip_finished.connect(self._on_clip_finished)
        self._runner.job_finished.connect(self._on_job_finished)
        self._runner.job_failed.connect(self._on_job_failed)
        self._runner.log.connect(self._on_log)

        i18n_manager().locale_changed.connect(lambda _code: self._retranslate())

        central = QWidget(self)
        central.setObjectName("central")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        scroll = QScrollArea(central)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_inner = QWidget()
        scroll.setWidget(scroll_inner)
        root.addWidget(scroll, 1)

        outer = QVBoxLayout(scroll_inner)
        outer.setContentsMargins(32, 28, 32, 24)
        outer.setSpacing(20)

        self._heading = QLabel(tr("ClipForge"), scroll_inner)
        self._heading.setProperty("role", "heading")
        outer.addWidget(self._heading)

        self._tagline = QLabel(
            tr("Slice long videos into short clips with subtle randomized effects."),
            scroll_inner,
        )
        self._tagline.setProperty("role", "subtitle")
        outer.addWidget(self._tagline)

        self._drop = DropZone(self)
        outer.addWidget(self._drop)

        self._preset_heading = QLabel(tr("Preset"), scroll_inner)
        self._preset_heading.setProperty("role", "subtitle")
        outer.addWidget(self._preset_heading)
        self._preset_grid_container = QWidget(scroll_inner)
        self._preset_grid = QGridLayout(self._preset_grid_container)
        self._preset_grid.setHorizontalSpacing(12)
        self._preset_grid.setVerticalSpacing(12)
        outer.addWidget(self._preset_grid_container)

        self._custom_panel = CustomConfigPanel(scroll_inner)
        self._custom_panel.setVisible(False)
        outer.addWidget(self._custom_panel)

        # Output folder card
        out_card = QFrame(scroll_inner)
        out_card.setObjectName("card")
        out_layout = QVBoxLayout(out_card)
        out_layout.setContentsMargins(16, 14, 16, 14)
        self._out_card_label = QLabel(tr("Output folder"), out_card)
        self._out_card_label.setProperty("role", "subtitle")
        out_layout.addWidget(self._out_card_label)
        out_row = QHBoxLayout()
        self._out_field = QLineEdit(str(default_output_dir()), out_card)
        out_row.addWidget(self._out_field, 1)
        self._out_browse = QPushButton(tr("Browse…"), out_card)
        self._out_browse.setProperty("role", "secondary")
        self._out_browse.clicked.connect(self._choose_output_dir)
        out_row.addWidget(self._out_browse)
        self._out_open = QPushButton(tr("Open"), out_card)
        self._out_open.setProperty("role", "secondary")
        self._out_open.clicked.connect(self._open_output_dir)
        out_row.addWidget(self._out_open)
        out_layout.addLayout(out_row)
        outer.addWidget(out_card)

        self._progress = QProgressBar(scroll_inner)
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setFormat(tr("Idle"))
        outer.addWidget(self._progress)

        self._log = QPlainTextEdit(scroll_inner)
        self._log.setObjectName("logView")
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(120)
        outer.addWidget(self._log, 1)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self._cancel_btn = QPushButton(tr("Cancel"), scroll_inner)
        self._cancel_btn.setProperty("role", "secondary")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel)
        action_row.addWidget(self._cancel_btn)
        self._start_btn = QPushButton(tr("Start"), scroll_inner)
        self._start_btn.setObjectName("startButton")
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._start_job)
        action_row.addWidget(self._start_btn)
        outer.addLayout(action_row)

        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self._lang_en_btn = QPushButton(self._flag_for("en") + "  EN", self)
        self._lang_en_btn.setProperty("role", "ghost")
        self._lang_en_btn.setFlat(True)
        self._lang_en_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lang_en_btn.clicked.connect(lambda: i18n_manager().set_locale("en"))
        sb.addWidget(self._lang_en_btn)
        self._lang_uk_btn = QPushButton(self._flag_for("uk") + "  UK", self)
        self._lang_uk_btn.setProperty("role", "ghost")
        self._lang_uk_btn.setFlat(True)
        self._lang_uk_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lang_uk_btn.clicked.connect(lambda: i18n_manager().set_locale("uk"))
        sb.addWidget(self._lang_uk_btn)

        self._status_msg = QLabel("", self)
        sb.addPermanentWidget(self._status_msg)

        self._refresh_status_bar()
        self._refresh_lang_buttons()

        self._load_presets()

    def _flag_for(self, code: str) -> str:
        if code == "en":
            return "\U0001f1ec\U0001f1e7"  # GB
        if code == "uk":
            return "\U0001f1fa\U0001f1e6"  # UA
        return ""

    def _refresh_lang_buttons(self) -> None:
        active = i18n_manager().locale
        for code, btn in (
            ("en", self._lang_en_btn),
            ("uk", self._lang_uk_btn),
        ):
            btn.setProperty("selected", code == active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _refresh_status_bar(self) -> None:
        ready = ffmpeg_path().is_file()
        msg = tr("FFmpeg ready") if ready else tr("FFmpeg missing — run scripts/fetch_ffmpeg.py")
        self._status_msg.setText(f"v{__version__}  ·  {msg}")
        if not ready:
            self._append_log("WARNING: " + msg)

    def open_file_dialog(self) -> None:
        filters = (
            tr("Choose a source video")
            + " ("
            + " ".join(f"*{ext}" for ext in sorted(VIDEO_EXTENSIONS))
            + ");;All files (*.*)"
        )
        path_str, _ = QFileDialog.getOpenFileName(self, tr("Choose a source video"), "", filters)
        if path_str:
            self.set_source(Path(path_str))

    def set_source(self, path: Path) -> None:
        self.source_path = path
        self._drop.set_loaded(path)
        self._update_start_enabled()
        self._append_log(tr("Selected source:") + " " + str(path))

    def _load_presets(self) -> None:
        try:
            self._presets = list(discover_builtins())
        except Exception as exc:
            QMessageBox.critical(
                self,
                tr("Preset load failed"),
                tr("Could not load built-in presets:") + f"\n{exc}",
            )
            self._presets = []

        while self._preset_grid.count():
            item = self._preset_grid.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.setParent(None)  # type: ignore[call-arg]
                w.deleteLater()
        self._preset_cards.clear()
        self._selected_card = None

        descriptions = {
            "TikTok Soft": "Gentle effects, 9:16, 3-6s",
            "TikTok Hard Uniq": "Aggressive effects, 9:16, 4-7s",
            "YouTube Shorts": "Balanced, 9:16, 5-10s",
            "Instagram Reels": "Mid intensity, 9:16, 3-8s",
            "Plain Slice": "No effects, original aspect, 5-10s",
        }
        cols = 3
        for idx, p in enumerate(self._presets):
            card = PresetCard(
                p,
                p.description or descriptions.get(p.name, ""),
                self._preset_grid_container,
                self._on_card_clicked,
            )
            self._preset_grid.addWidget(card, idx // cols, idx % cols)
            self._preset_cards.append(card)

        custom_card = PresetCard(
            "Custom",
            "Configure everything yourself",
            self._preset_grid_container,
            self._on_card_clicked,
        )
        custom_card.preset = "Custom"
        n = len(self._presets)
        self._preset_grid.addWidget(custom_card, n // cols, n % cols)
        self._preset_cards.append(custom_card)

        if self._preset_cards:
            self._on_card_clicked(self._preset_cards[0])

    def _on_card_clicked(self, card: PresetCard) -> None:
        for c in self._preset_cards:
            c.set_selected(False)
        card.set_selected(True)
        self._selected_card = card
        self._custom_panel.setVisible(card.preset == "Custom")
        self._update_start_enabled()

    def _update_start_enabled(self) -> None:
        ready = (
            self.source_path is not None
            and self._selected_card is not None
            and ffmpeg_path().is_file()
        )
        self._start_btn.setEnabled(ready)

    def _choose_output_dir(self) -> None:
        current = self._out_field.text() or str(default_output_dir())
        path_str = QFileDialog.getExistingDirectory(self, tr("Choose output folder"), current)
        if path_str:
            self._out_field.setText(path_str)

    def _open_output_dir(self) -> None:
        path = Path(self._out_field.text())
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _resolved_preset(self) -> Preset | None:
        if self._selected_card is None:
            return None
        if self._selected_card.preset == "Custom":
            return self._custom_panel.build_preset()
        return self._selected_card.preset  # type: ignore[return-value]

    def _start_job(self) -> None:
        preset = self._resolved_preset()
        if self.source_path is None or preset is None:
            return
        out_root = Path(self._out_field.text()).expanduser()
        try:
            out_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, tr("Cannot create output folder"), str(exc))
            return
        job = JobSpec(
            source_path=self.source_path,
            output_root=out_root,
            slicing=preset.slicing,
            effects=preset.effects,
            output=preset.output,
            mode=preset.mode,
            seed=None,
        )
        self._set_running(True)
        self._progress.setRange(0, 0)
        self._progress.setFormat(tr("Preparing…"))
        self._append_log(tr("Starting job with preset") + f" “{preset.name}”")
        self._runner.run_async(job)

    def _cancel(self) -> None:
        self._runner.cancel()
        self._append_log(tr("Cancellation requested."))

    def _set_running(self, running: bool) -> None:
        self._start_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)
        self._drop.setEnabled(not running)
        self._out_field.setEnabled(not running)
        self._out_browse.setEnabled(not running)
        for c in self._preset_cards:
            c.setEnabled(not running)
        self._custom_panel.setEnabled(not running)

    def _on_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)
        self._progress.setFormat(f"{done} / {total}  ·  %p%")

    def _on_clip_finished(self, path: str) -> None:
        self._append_log("✓ " + path)

    def _on_job_finished(self) -> None:
        self._set_running(False)
        if self._progress.maximum() == 0:
            self._progress.setRange(0, 1)
        self._progress.setValue(self._progress.maximum())
        self._progress.setFormat(tr("Done"))
        self._append_log(tr("Job finished."))
        QMessageBox.information(
            self,
            tr("Job finished"),
            tr("Your clips are ready in the output folder."),
        )

    def _on_job_failed(self, msg: str) -> None:
        self._set_running(False)
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setFormat(tr("Failed"))
        self._append_log(f"ERROR: {msg}")
        QMessageBox.critical(self, tr("Job failed"), msg)

    def _on_log(self, line: str) -> None:
        self._append_log(line)

    def _append_log(self, line: str) -> None:
        self._log.appendPlainText(line)

    def _retranslate(self) -> None:
        self._heading.setText(tr("ClipForge"))
        self._tagline.setText(
            tr("Slice long videos into short clips with subtle randomized effects.")
        )
        self._preset_heading.setText(tr("Preset"))
        self._out_card_label.setText(tr("Output folder"))
        self._out_browse.setText(tr("Browse…"))
        self._out_open.setText(tr("Open"))
        self._start_btn.setText(tr("Start"))
        self._cancel_btn.setText(tr("Cancel"))
        self._progress.setFormat(tr("Idle"))
        self._drop.retranslate()
        for c in self._preset_cards:
            c.retranslate()
        self._custom_panel.retranslate()
        self._refresh_status_bar()
        self._refresh_lang_buttons()


def build_main_window() -> QMainWindow:
    return MainWindow()


def run() -> int:  # pragma: no cover
    app = ClipForgeApp(sys.argv)
    window = build_main_window()
    window.show()
    return app.exec()
