"""Reusable widgets for the ClipForge UI.

- ``NoWheelSlider`` / ``NoWheelSpinBox`` / ``NoWheelDoubleSpinBox``:
  pass-through subclasses that ignore wheel events so values don't change
  when the user scrolls the page.
- ``EffectRow``: a single effects-panel row (checkbox + name + percent
  input + companion slider). Emits ``changed`` when the user edits any
  sub-control. Use ``set_values()`` for programmatic fills — it does
  NOT emit the change signal.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QSlider,
    QSpinBox,
    QWidget,
)


class NoWheelSlider(QSlider):
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        event.ignore()


class EffectRow(QWidget):
    """One row of the Effects section: [checkbox] name [%] [slider]."""

    changed = Signal()

    def __init__(self, field: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.field = field
        self._suppress = False
        self._label_source = label

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self.checkbox = QCheckBox(label, self)
        self.checkbox.setMinimumWidth(140)
        self.checkbox.toggled.connect(self._on_toggled)
        layout.addWidget(self.checkbox)

        self.percent = NoWheelSpinBox(self)
        self.percent.setRange(0, 100)
        self.percent.setSuffix(" %")
        self.percent.setFixedWidth(72)
        self.percent.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.percent.valueChanged.connect(self._on_percent_changed)
        layout.addWidget(self.percent)

        self.slider = NoWheelSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, 100)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider, 1)

        self.set_disabled_look(False)

    def retranslate(self, label: str) -> None:
        self._label_source = label
        self.checkbox.setText(label)

    def label_source(self) -> str:
        return self._label_source

    def set_values(self, enabled: bool, intensity_pct: int) -> None:
        """Programmatic set — does NOT emit ``changed``."""
        self._suppress = True
        self.checkbox.setChecked(enabled)
        self.percent.setValue(intensity_pct)
        self.slider.setValue(intensity_pct)
        self.set_disabled_look(not enabled)
        self._suppress = False

    def values(self) -> tuple[bool, int]:
        return self.checkbox.isChecked(), self.percent.value()

    def set_disabled_look(self, disabled: bool) -> None:
        self.percent.setEnabled(not disabled)
        self.slider.setEnabled(not disabled)

    def _on_toggled(self, checked: bool) -> None:
        self.set_disabled_look(not checked)
        if not self._suppress:
            self.changed.emit()

    def _on_percent_changed(self, value: int) -> None:
        if self._suppress:
            return
        self._suppress = True
        self.slider.setValue(value)
        self._suppress = False
        self.changed.emit()

    def _on_slider_changed(self, value: int) -> None:
        if self._suppress:
            return
        self._suppress = True
        self.percent.setValue(value)
        self._suppress = False
        self.changed.emit()
