"""ClipForge main window and application bootstrap (v1.0.3).

Layout: slim drop bar (top), preset tabs (header), 2-column body
(config | output+log), status bar with language toggle and Start/Cancel.

UX rules:
- All 10 effect rows always render; effects disabled by the active preset
  are shown greyed but visible.
- Numeric inputs are authoritative; sliders are companions and ignore
  mouse wheel.
- Editing any value while a built-in preset tab is active flips the
  active tab to Custom, preserving the edit.
- Users can save the current configuration as a named preset; saved
  presets appear as additional tabs between built-ins and Custom on
  next launch.
"""

from __future__ import annotations

import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
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
from clipforge.core.presets import (
    discover_builtins,
    discover_user_presets,
    save_preset_to_file,
)
from clipforge.i18n import manager as i18n_manager
from clipforge.i18n import tr
from clipforge.infra.paths import (
    app_data_dir,
    default_output_dir,
    ffmpeg_path,
    resources_dir,
)
from clipforge.job_runner import JobRunner
from clipforge.version import __version__
from clipforge.widgets import (
    EffectRow,
    NoWheelDoubleSpinBox,
    NoWheelSlider,
    NoWheelSpinBox,
)

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

# Only these three built-ins surface as tabs. The other JSON files in
# resources/presets/ are kept on disk for users who copy them out.
ACTIVE_BUILTIN_PRESETS: tuple[str, ...] = (
    "TikTok Soft",
    "Instagram Reels",
    "YouTube Shorts",
)

EFFECT_ORDER: tuple[tuple[str, str], ...] = (
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


def _flag_icon(code: str) -> QIcon | None:
    """Real flag PNG icon (CC0 from flagcdn.com), bundled in resources/icons/flags/."""
    name = {"en": "gb.png", "uk": "ua.png"}.get(code)
    if name is None:
        return None
    candidates = [
        resources_dir() / "icons" / "flags" / name,
        Path(__file__).resolve().parents[2] / "resources" / "icons" / "flags" / name,
    ]
    for c in candidates:
        if c.is_file():
            return QIcon(str(c))
    return None


def _user_presets_dir() -> Path:
    """Where user-saved `.cfp.json` presets live."""
    return app_data_dir() / "presets"


def _slugify(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in nfkd)
    return safe.strip().replace(" ", "_").lower() or "preset"


class ClipForgeApp(QApplication):
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        # Force the Fusion style — the Windows native style ignores some
        # QSS rules (notably QComboBox text colour), which made our cyan
        # combos render as blank boxes on Windows.
        from PySide6.QtWidgets import QStyleFactory

        fusion = QStyleFactory.create("Fusion")
        if fusion is not None:
            self.setStyle(fusion)
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


class DropBar(QFrame):
    """Slim full-width drop target — collapses to filename once loaded."""

    def __init__(
        self, on_file_chosen: Callable[[Path], None], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._on_file_chosen = on_file_chosen
        self.setObjectName("dropBar")
        self.setAcceptDrops(True)
        self.setProperty("dragOver", False)
        self.setProperty("loaded", False)
        self.setMinimumHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 12, 8)
        layout.setSpacing(10)

        self._icon = QLabel("✂", self)
        self._icon.setStyleSheet("color: #22D3EE; font-size: 22px; font-weight: 700;")
        layout.addWidget(self._icon)

        self._title = QLabel(tr("Drop a video here, or click to browse"), self)
        self._title.setProperty("role", "subtitle")
        self._title.setStyleSheet("color: #ECFEFF; font-size: 14px;")
        layout.addWidget(self._title, 1)

        self._sub = QLabel("", self)
        self._sub.setProperty("role", "caption")
        layout.addWidget(self._sub)

        self._change_btn = QPushButton(tr("Change…"), self)
        self._change_btn.setProperty("role", "secondary")
        self._change_btn.setVisible(False)
        self._change_btn.clicked.connect(self._open_dialog)
        layout.addWidget(self._change_btn)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def retranslate(self, loaded: bool) -> None:
        if not loaded:
            self._title.setText(tr("Drop a video here, or click to browse"))
        self._change_btn.setText(tr("Change…"))

    def set_loaded(self, path: Path) -> None:
        self._icon.setText("🎬")
        self._title.setText(path.name)
        self._sub.setText(str(path.parent))
        self._change_btn.setVisible(True)
        self.setProperty("loaded", True)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event: object) -> None:  # noqa: N802
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent

        if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
            self._open_dialog()
        if isinstance(event, QEvent):
            super().mousePressEvent(event)  # type: ignore[arg-type]

    def _open_dialog(self) -> None:
        filters = (
            tr("Choose a source video")
            + " ("
            + " ".join(f"*{ext}" for ext in sorted(VIDEO_EXTENSIONS))
            + ");;All files (*.*)"
        )
        path_str, _ = QFileDialog.getOpenFileName(self, tr("Choose a source video"), "", filters)
        if path_str:
            self._on_file_chosen(Path(path_str))

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
                p = Path(url.toLocalFile())
                if p.suffix.lower() in VIDEO_EXTENSIONS:
                    self._on_file_chosen(p)
                    event.acceptProposedAction()
                    return
        event.ignore()


class PresetTabs(QWidget):
    """Horizontal row of preset selector buttons + 'Custom' at the end."""

    selected = Signal(str)  # emits the active name

    def __init__(
        self, builtin_names: list[str], user_names: list[str], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        for name in builtin_names:
            btn = self._mk(name)
            layout.addWidget(btn)
        if user_names:
            sep = QLabel("·", self)
            sep.setStyleSheet("color: #5E8290; padding: 0 4px;")
            layout.addWidget(sep)
            for name in user_names:
                btn = self._mk(name)
                layout.addWidget(btn)
        custom_btn = self._mk("Custom")
        layout.addWidget(custom_btn)
        layout.addStretch(1)

        self._active: str | None = None

    def _mk(self, name: str) -> QPushButton:
        btn = QPushButton(tr(name), self)
        btn.setProperty("role", "tab")
        btn.setProperty("active", False)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _checked=False, n=name: self.set_active(n, emit=True))
        self._buttons[name] = btn
        return btn

    def names(self) -> list[str]:
        return list(self._buttons.keys())

    def retranslate(self) -> None:
        for name, btn in self._buttons.items():
            btn.setText(tr(name))

    def active(self) -> str | None:
        return self._active

    def set_active(self, name: str, *, emit: bool = False) -> None:
        if name not in self._buttons:
            return
        self._active = name
        for n, b in self._buttons.items():
            b.setProperty("active", n == name)
            b.style().unpolish(b)
            b.style().polish(b)
        if emit:
            self.selected.emit(name)

    def add_button(self, name: str) -> None:
        if name in self._buttons:
            return
        # Insert before Custom (always last user-visible button).
        layout = self.layout()
        custom_btn = self._buttons.get("Custom")
        btn = self._mk(name)
        if custom_btn is not None and layout is not None:
            idx = layout.indexOf(custom_btn)
            layout.insertWidget(idx, btn)
        else:
            assert layout is not None
            layout.addWidget(btn)


class MainWindow(QMainWindow):
    """Primary window for v1.0.3."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(constants.WINDOW_TITLE)
        self.setMinimumSize(constants.WINDOW_MIN_WIDTH, constants.WINDOW_MIN_HEIGHT)
        # Default a touch taller so the whole effects list fits without scroll
        # on a typical 1080p display.
        self.resize(constants.WINDOW_DEFAULT_WIDTH, max(900, constants.WINDOW_DEFAULT_HEIGHT))
        icon = _app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self.source_path: Path | None = None
        self._filling_from_preset = False  # suppresses Custom-flip while we fill
        # Combo-section labels are populated dynamically by ``col()`` but
        # declared here so mypy can see them.
        self._aspect_label: QLabel | None = None
        self._codec_label: QLabel | None = None
        self._quality_label: QLabel | None = None
        self._audio_label: QLabel | None = None

        # Preset catalogue
        all_builtins = {p.name: p for p in discover_builtins()}
        self._builtins: dict[str, Preset] = {
            n: all_builtins[n] for n in ACTIVE_BUILTIN_PRESETS if n in all_builtins
        }
        self._user_presets: dict[str, Preset] = {
            p.name: p for p in discover_user_presets(_user_presets_dir())
        }

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
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 16, 20, 8)
        outer.setSpacing(12)

        # Drop bar
        self._drop = DropBar(self.set_source, central)
        outer.addWidget(self._drop)

        # Preset tabs
        self._tabs = PresetTabs(
            list(self._builtins.keys()),
            list(self._user_presets.keys()),
            central,
        )
        self._tabs.selected.connect(self._on_tab_selected)
        outer.addWidget(self._tabs)

        # Body splitter
        splitter = QSplitter(Qt.Orientation.Horizontal, central)
        splitter.setHandleWidth(8)
        splitter.setChildrenCollapsible(False)
        outer.addWidget(splitter, 1)

        # Left: config card wrapped in a vertical scroll area so the long
        # effects list never gets clipped on smaller windows.
        self._config_card = self._build_config_card()
        config_scroll = QScrollArea()
        config_scroll.setWidgetResizable(True)
        config_scroll.setFrameShape(QFrame.Shape.NoFrame)
        config_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        config_scroll.setWidget(self._config_card)
        splitter.addWidget(config_scroll)

        # Right: output card
        self._output_card = self._build_output_card()
        splitter.addWidget(self._output_card)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([720, 460])

        # Status bar
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self._lang_en_btn = self._make_lang_button("en", "EN")
        self._lang_en_btn.clicked.connect(lambda: i18n_manager().set_locale("en"))
        sb.addWidget(self._lang_en_btn)
        self._lang_uk_btn = self._make_lang_button("uk", "UK")
        self._lang_uk_btn.clicked.connect(lambda: i18n_manager().set_locale("uk"))
        sb.addWidget(self._lang_uk_btn)

        self._status_msg = QLabel("", self)
        sb.addPermanentWidget(self._status_msg)

        self._cancel_btn = QPushButton(tr("Cancel"), self)
        self._cancel_btn.setProperty("role", "secondary")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel)
        sb.addPermanentWidget(self._cancel_btn)

        self._start_btn = QPushButton(tr("Start"), self)
        self._start_btn.setObjectName("startButton")
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._start_job)
        sb.addPermanentWidget(self._start_btn)

        self._refresh_status_bar()
        self._refresh_lang_buttons()

        # Initial tab — pick first built-in if any.
        if self._builtins:
            first = next(iter(self._builtins.keys()))
            self._tabs.set_active(first, emit=True)
        else:
            self._tabs.set_active("Custom", emit=True)

    # ----- card builders -----

    def _build_config_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)

        # Clip length row
        len_row = QHBoxLayout()
        len_row.setSpacing(8)
        self._len_label = QLabel(tr("Length"), card)
        self._len_label.setProperty("role", "subtitle")
        self._len_label.setFixedWidth(140)
        len_row.addWidget(self._len_label)
        self._from_label = QLabel(tr("From"), card)
        self._from_label.setProperty("role", "caption")
        len_row.addWidget(self._from_label)
        self._min_spin = NoWheelDoubleSpinBox(card)
        self._min_spin.setRange(0.5, 600.0)
        self._min_spin.setDecimals(1)
        self._min_spin.setSingleStep(0.5)
        self._min_spin.setSuffix(" s")
        self._min_spin.setFixedWidth(96)
        self._min_spin.valueChanged.connect(self._on_value_changed)
        self._min_spin.valueChanged.connect(self._enforce_min_le_max)
        len_row.addWidget(self._min_spin)
        self._to_label = QLabel(tr("To"), card)
        self._to_label.setProperty("role", "caption")
        len_row.addWidget(self._to_label)
        self._max_spin = NoWheelDoubleSpinBox(card)
        self._max_spin.setRange(0.5, 600.0)
        self._max_spin.setDecimals(1)
        self._max_spin.setSingleStep(0.5)
        self._max_spin.setSuffix(" s")
        self._max_spin.setFixedWidth(96)
        self._max_spin.valueChanged.connect(self._on_value_changed)
        self._max_spin.valueChanged.connect(self._enforce_min_le_max)
        len_row.addWidget(self._max_spin)
        len_row.addStretch(1)
        v.addLayout(len_row)

        # Global intensity row
        gi_row = QHBoxLayout()
        gi_row.setSpacing(8)
        self._gi_label = QLabel(tr("Global intensity"), card)
        self._gi_label.setProperty("role", "subtitle")
        self._gi_label.setFixedWidth(140)
        gi_row.addWidget(self._gi_label)
        self._gi_spin = NoWheelSpinBox(card)
        self._gi_spin.setRange(0, 150)
        self._gi_spin.setSuffix(" %")
        self._gi_spin.setFixedWidth(80)
        self._gi_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._gi_spin.valueChanged.connect(self._on_global_intensity_spin)
        gi_row.addWidget(self._gi_spin)
        self._gi_slider = NoWheelSlider(Qt.Orientation.Horizontal, card)
        self._gi_slider.setRange(0, 150)
        self._gi_slider.valueChanged.connect(self._on_global_intensity_slider)
        gi_row.addWidget(self._gi_slider, 1)
        v.addLayout(gi_row)

        # Output configuration: 2x2 grid so each combo has room for its text.
        out_grid = QGridLayout()
        out_grid.setHorizontalSpacing(14)
        out_grid.setVerticalSpacing(8)

        def col(label_src: str, combo: QComboBox, label_attr: str) -> QWidget:
            wrap = QWidget(card)
            wl = QVBoxLayout(wrap)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setSpacing(3)
            lbl = QLabel(tr(label_src), wrap)
            lbl.setProperty("role", "caption")
            wl.addWidget(lbl)
            combo.setMinimumWidth(180)
            combo.setMinimumHeight(28)
            wl.addWidget(combo)
            setattr(self, label_attr, lbl)
            return wrap

        self._aspect = QComboBox(card)
        for value, label in (
            ("original", "Original"),
            ("9:16", "9:16"),
            ("16:9", "16:9"),
            ("1:1", "1:1"),
            ("4:5", "4:5"),
        ):
            self._aspect.addItem(tr(label) if label == "Original" else label, value)
        self._aspect.currentIndexChanged.connect(self._on_value_changed)
        out_grid.addWidget(col("Aspect ratio", self._aspect, "_aspect_label"), 0, 0)

        self._codec = QComboBox(card)
        for value, label in (
            ("libx264", "H.264 (libx264)"),
            ("libx265", "H.265 (libx265)"),
            ("h264_nvenc", "H.264 NVENC"),
            ("h264_qsv", "H.264 QSV"),
            ("h264_amf", "H.264 AMF"),
        ):
            self._codec.addItem(label, value)
        self._codec.currentIndexChanged.connect(self._on_value_changed)
        out_grid.addWidget(col("Codec", self._codec, "_codec_label"), 0, 1)

        self._quality = QComboBox(card)
        for value, label in (
            ("fast", "Fast"),
            ("balanced", "Balanced"),
            ("high", "High Quality"),
        ):
            self._quality.addItem(tr(label), value)
        self._quality.currentIndexChanged.connect(self._on_value_changed)
        out_grid.addWidget(col("Quality", self._quality, "_quality_label"), 1, 0)

        self._audio = QComboBox(card)
        for value, label in (
            ("keep", "Keep audio"),
            ("mute", "Mute"),
            ("remove", "Remove track"),
        ):
            self._audio.addItem(tr(label), value)
        self._audio.currentIndexChanged.connect(self._on_value_changed)
        out_grid.addWidget(col("Audio", self._audio, "_audio_label"), 1, 1)
        out_grid.setColumnStretch(0, 1)
        out_grid.setColumnStretch(1, 1)
        v.addLayout(out_grid)

        # Pitch preservation
        self._pitch = QCheckBox(tr("Pitch preservation"), card)
        self._pitch.toggled.connect(self._on_value_changed)
        v.addWidget(self._pitch)

        # Effects header + rows
        self._effects_header = QLabel(tr("Effects"), card)
        self._effects_header.setProperty("role", "subtitle")
        v.addWidget(self._effects_header)

        self._effect_rows: dict[str, EffectRow] = {}
        for field, label in EFFECT_ORDER:
            row = EffectRow(field, tr(label), card)
            row.changed.connect(self._on_value_changed)
            self._effect_rows[field] = row
            v.addWidget(row)

        v.addStretch(1)
        return card

    def _build_output_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)

        self._out_label = QLabel(tr("Output folder"), card)
        self._out_label.setProperty("role", "subtitle")
        v.addWidget(self._out_label)

        out_row = QHBoxLayout()
        self._out_field = QLineEdit(str(default_output_dir()), card)
        out_row.addWidget(self._out_field, 1)
        self._browse_btn = QPushButton(tr("Browse…"), card)
        self._browse_btn.setProperty("role", "secondary")
        self._browse_btn.clicked.connect(self._choose_output_dir)
        out_row.addWidget(self._browse_btn)
        self._open_out_btn = QPushButton(tr("Open"), card)
        self._open_out_btn.setProperty("role", "secondary")
        self._open_out_btn.clicked.connect(self._open_output_dir)
        out_row.addWidget(self._open_out_btn)
        v.addLayout(out_row)

        self._save_preset_btn = QPushButton(tr("Save current as preset…"), card)
        self._save_preset_btn.setProperty("role", "secondary")
        self._save_preset_btn.clicked.connect(self._save_as_preset)
        v.addWidget(self._save_preset_btn)

        self._progress = QProgressBar(card)
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._progress.setFormat(tr("Idle"))
        v.addWidget(self._progress)

        self._log_label = QLabel(tr("Log"), card)
        self._log_label.setProperty("role", "subtitle")
        v.addWidget(self._log_label)
        self._log = QPlainTextEdit(card)
        self._log.setObjectName("logView")
        self._log.setReadOnly(True)
        v.addWidget(self._log, 1)
        return card

    # ----- preset I/O -----

    def _fill_from_preset(self, preset: Preset) -> None:
        self._filling_from_preset = True
        try:
            self._min_spin.setValue(preset.slicing.min_length_sec)
            self._max_spin.setValue(preset.slicing.max_length_sec)
            gi_pct = round(preset.effects.global_intensity * 100)
            self._gi_spin.setValue(gi_pct)
            self._gi_slider.setValue(gi_pct)

            def _set_combo(combo: QComboBox, value: str) -> None:
                idx = combo.findData(value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

            _set_combo(self._aspect, preset.output.aspect)
            _set_combo(self._codec, preset.output.codec)
            _set_combo(self._quality, preset.output.quality)
            _set_combo(self._audio, preset.output.audio_mode)
            self._pitch.setChecked(preset.effects.pitch_preservation)

            for field, _ in EFFECT_ORDER:
                eff: EffectSettings = getattr(preset.effects, field)
                self._effect_rows[field].set_values(
                    enabled=eff.enabled,
                    intensity_pct=round(eff.intensity * 100),
                )
        finally:
            self._filling_from_preset = False

    def _build_current_preset(self, name: str, *, builtin: bool) -> Preset:
        slicing = SlicingConfig(
            strategy="sequential",
            min_length_sec=float(self._min_spin.value()),
            max_length_sec=float(self._max_spin.value()),
        )
        effects_kwargs: dict[str, EffectSettings] = {}
        for field, _ in EFFECT_ORDER:
            enabled, pct = self._effect_rows[field].values()
            effects_kwargs[field] = EffectSettings(
                enabled=enabled,
                intensity=pct / 100.0,
                probability=1.0,
            )
        effects = EffectsConfig(
            global_intensity=self._gi_spin.value() / 100.0,
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
            name=name,
            description=None,
            builtin=builtin,
            slicing=slicing,
            effects=effects,
            output=output,
            mode="clips",
        )

    # ----- signal handlers -----

    def set_source(self, path: Path) -> None:
        self.source_path = path
        self._drop.set_loaded(path)
        self._update_start_enabled()
        self._append_log(tr("Selected source:") + " " + str(path))

    def _on_tab_selected(self, name: str) -> None:
        if name == "Custom":
            return  # Don't overwrite current config
        preset = self._builtins.get(name) or self._user_presets.get(name)
        if preset is not None:
            self._fill_from_preset(preset)

    def _on_value_changed(self, *_args: object) -> None:
        if self._filling_from_preset:
            return
        if self._tabs.active() != "Custom":
            self._tabs.set_active("Custom", emit=False)
        self._update_start_enabled()

    def _on_global_intensity_spin(self, value: int) -> None:
        if self._gi_slider.value() != value:
            self._gi_slider.blockSignals(True)
            self._gi_slider.setValue(value)
            self._gi_slider.blockSignals(False)
        self._on_value_changed()

    def _on_global_intensity_slider(self, value: int) -> None:
        if self._gi_spin.value() != value:
            self._gi_spin.blockSignals(True)
            self._gi_spin.setValue(value)
            self._gi_spin.blockSignals(False)
        self._on_value_changed()

    def _enforce_min_le_max(self, _value: float) -> None:
        if self._min_spin.value() > self._max_spin.value():
            sender = self.sender()
            if sender is self._min_spin:
                self._max_spin.blockSignals(True)
                self._max_spin.setValue(self._min_spin.value())
                self._max_spin.blockSignals(False)
            else:
                self._min_spin.blockSignals(True)
                self._min_spin.setValue(self._max_spin.value())
                self._min_spin.blockSignals(False)

    def _choose_output_dir(self) -> None:
        current = self._out_field.text() or str(default_output_dir())
        path_str = QFileDialog.getExistingDirectory(self, tr("Choose output folder"), current)
        if path_str:
            self._out_field.setText(path_str)

    def _open_output_dir(self) -> None:
        path = Path(self._out_field.text())
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _save_as_preset(self) -> None:
        name, ok = QInputDialog.getText(
            self,
            tr("Save current as preset…"),
            tr("Name your preset"),
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self._builtins or name in self._user_presets or name == "Custom":
            QMessageBox.warning(
                self,
                tr("Preset name"),
                tr("A preset with that name already exists."),
            )
            return
        preset = self._build_current_preset(name, builtin=False)
        target_dir = _user_presets_dir()
        target = target_dir / f"{_slugify(name)}.cfp.json"
        try:
            save_preset_to_file(preset, target)
        except Exception as exc:
            QMessageBox.critical(self, tr("Preset saved"), f"{exc}")
            return
        self._user_presets[name] = preset
        self._tabs.add_button(name)
        self._tabs.set_active(name, emit=False)
        self._append_log(tr("Preset saved") + ": " + str(target))

    def _start_job(self) -> None:
        if self.source_path is None:
            return
        active = self._tabs.active() or "Custom"
        preset = self._build_current_preset(active, builtin=False)
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
            mode="clips",
            seed=None,
        )
        self._set_running(True)
        self._progress.setRange(0, 0)
        self._progress.setFormat(tr("Preparing…"))
        self._append_log(tr("Starting job with preset") + f" '{active}'")
        self._runner.run_async(job)

    def _cancel(self) -> None:
        self._runner.cancel()
        self._append_log(tr("Cancellation requested."))

    def _set_running(self, running: bool) -> None:
        self._start_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)
        self._drop.setEnabled(not running)
        self._out_field.setEnabled(not running)
        self._browse_btn.setEnabled(not running)
        self._save_preset_btn.setEnabled(not running)
        self._config_card.setEnabled(not running)
        self._tabs.setEnabled(not running)

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

    def _update_start_enabled(self) -> None:
        self._start_btn.setEnabled(self.source_path is not None and ffmpeg_path().is_file())

    # ----- footer / status -----

    def _make_lang_button(self, code: str, label: str) -> QPushButton:
        btn = QPushButton(label, self)
        btn.setProperty("role", "ghost")
        btn.setProperty("lang", code)
        btn.setFlat(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        icon = _flag_icon(code)
        if icon is not None:
            btn.setIcon(icon)
            btn.setIconSize(QSize(20, 14))
        return btn

    def _refresh_lang_buttons(self) -> None:
        active = i18n_manager().locale
        for code, btn in (("en", self._lang_en_btn), ("uk", self._lang_uk_btn)):
            btn.setProperty("selected", code == active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _refresh_status_bar(self) -> None:
        ready = ffmpeg_path().is_file()
        msg = tr("FFmpeg ready") if ready else tr("FFmpeg missing — run scripts/fetch_ffmpeg.py")
        self._status_msg.setText(f"v{__version__}  ·  {msg}")

    # ----- retranslate -----

    def _retranslate(self) -> None:
        loaded = self.source_path is not None
        self._drop.retranslate(loaded)
        self._tabs.retranslate()
        self._len_label.setText(tr("Length"))
        self._from_label.setText(tr("From"))
        self._to_label.setText(tr("To"))
        self._gi_label.setText(tr("Global intensity"))
        self._aspect_label.setText(tr("Aspect ratio"))
        self._codec_label.setText(tr("Codec"))
        self._quality_label.setText(tr("Quality"))
        self._audio_label.setText(tr("Audio"))
        self._pitch.setText(tr("Pitch preservation"))
        self._effects_header.setText(tr("Effects"))
        self._out_label.setText(tr("Output folder"))
        self._log_label.setText(tr("Log"))
        self._browse_btn.setText(tr("Browse…"))
        self._open_out_btn.setText(tr("Open"))
        self._save_preset_btn.setText(tr("Save current as preset…"))
        self._cancel_btn.setText(tr("Cancel"))
        self._start_btn.setText(tr("Start"))
        # Combo display strings that we own
        idx = self._aspect.findData("original")
        if idx >= 0:
            self._aspect.setItemText(idx, tr("Original"))
        for i in range(self._quality.count()):
            data = self._quality.itemData(i)
            label_map = {"fast": "Fast", "balanced": "Balanced", "high": "High Quality"}
            if data in label_map:
                self._quality.setItemText(i, tr(label_map[data]))
        for i in range(self._audio.count()):
            data = self._audio.itemData(i)
            audio_label_map = {"keep": "Keep audio", "mute": "Mute", "remove": "Remove track"}
            if data in audio_label_map:
                self._audio.setItemText(i, tr(audio_label_map[data]))
        # Combo-section labels (assigned dynamically via ``col()``):
        for lbl_attr, src in (
            ("_aspect_label", "Aspect ratio"),
            ("_codec_label", "Codec"),
            ("_quality_label", "Quality"),
            ("_audio_label", "Audio"),
        ):
            lbl = getattr(self, lbl_attr, None)
            if lbl is not None:
                lbl.setText(tr(src))
        for field, label_src in EFFECT_ORDER:
            self._effect_rows[field].retranslate(tr(label_src))
        self._refresh_status_bar()
        self._refresh_lang_buttons()


def build_main_window() -> QMainWindow:
    return MainWindow()


def run() -> int:  # pragma: no cover
    app = ClipForgeApp(sys.argv)
    window = build_main_window()
    window.show()
    return app.exec()
