"""Pydantic v2 data models for the ClipForge domain.

Every model is frozen and forbids extra fields.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

type EffectName = Literal[
    "mirror",
    "zoom",
    "speed",
    "color",
    "rotation",
    "edge_crop",
    "noise",
    "vignette",
    "pixel_shift",
    "film_grain",
]

type Aspect = Literal["original", "9:16", "16:9", "1:1", "4:5"]
type Codec = Literal["libx264", "libx265", "h264_nvenc", "h264_qsv", "h264_amf"]
type Quality = Literal["fast", "balanced", "high"]
type AudioMode = Literal["keep", "mute", "remove"]
type Mode = Literal["clips", "assembled", "both"]
type Strategy = Literal["sequential", "random_sample"]
type Transition = Literal["none", "fade", "crossfade"]


class _Frozen(BaseModel):
    """Base for all frozen, extra-forbidding models."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class EffectSettings(_Frozen):
    enabled: bool
    intensity: float = Field(default=1.0, ge=0.0, le=1.0)
    probability: float = Field(default=1.0, ge=0.0, le=1.0)


class SlicingConfig(_Frozen):
    strategy: Strategy = "sequential"
    min_length_sec: float = Field(default=3.0, ge=0.5, le=600.0)
    max_length_sec: float = Field(default=5.0, ge=0.5, le=600.0)
    skip_start_sec: float = Field(default=0.0, ge=0.0)
    skip_end_sec: float = Field(default=0.0, ge=0.0)
    random_sample_count: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validate_lengths(self) -> SlicingConfig:
        if self.min_length_sec > self.max_length_sec:
            raise ValueError("min_length_sec must be <= max_length_sec")
        if self.strategy == "random_sample" and self.random_sample_count is None:
            raise ValueError("random_sample strategy requires random_sample_count")
        return self


class EffectsConfig(_Frozen):
    global_intensity: float = Field(default=1.0, ge=0.0, le=1.5)
    mirror: EffectSettings
    zoom: EffectSettings
    speed: EffectSettings
    color: EffectSettings
    rotation: EffectSettings
    edge_crop: EffectSettings
    noise: EffectSettings
    vignette: EffectSettings
    pixel_shift: EffectSettings
    film_grain: EffectSettings
    pitch_preservation: bool = False


class OutputConfig(_Frozen):
    aspect: Aspect
    codec: Codec
    quality: Quality
    audio_mode: AudioMode
    audio_overlay_path: Path | None = None
    audio_overlay_volume: float = Field(default=0.6, ge=0.0, le=2.0)
    source_audio_volume: float = Field(default=1.0, ge=0.0, le=2.0)
    target_fps: int | None = Field(default=30, ge=1)
    shuffle_assembled: bool = False
    transition: Transition = "none"


class JobSpec(_Frozen):
    source_path: Path
    output_root: Path
    slicing: SlicingConfig
    effects: EffectsConfig
    output: OutputConfig
    mode: Mode
    seed: int | None = None


class ResolvedEffects(_Frozen):
    """Concrete per-clip parameters produced by the effects resolver.

    A field of ``None`` (or ``False`` for ``mirror_applied`` /
    ``pitch_preservation``) means "do not apply".
    """

    mirror_applied: bool
    zoom_factor: float | None
    speed_factor: float | None
    color_brightness: float | None
    color_contrast: float | None
    color_saturation: float | None
    rotation_deg: float | None
    edge_crop_pct: float | None
    noise_level: float | None
    vignette_angle: float | None
    pixel_shift_x: int | None
    pixel_shift_y: int | None
    film_grain_level: float | None
    pitch_preservation: bool


class ClipPlan(_Frozen):
    index: int = Field(ge=0)
    start_sec: float = Field(ge=0.0)
    length_sec: float = Field(gt=0.0)
    effects: ResolvedEffects
    output_path: Path


class Preset(_Frozen):
    schema_version: int = 1
    name: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
    description: str | None = None
    builtin: bool = False
    slicing: SlicingConfig
    effects: EffectsConfig
    output: OutputConfig
    mode: Mode


class VideoMetadata(_Frozen):
    duration_sec: float = Field(gt=0.0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: float = Field(gt=0.0)
    has_audio: bool
