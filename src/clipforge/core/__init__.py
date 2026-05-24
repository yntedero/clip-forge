"""ClipForge core domain — pure Python, no Qt."""

from __future__ import annotations

from clipforge.core.exceptions import (
    ClipForgeError,
    FilterBuildError,
    PlanningError,
    PresetError,
    ValidationError,
)
from clipforge.core.filters import FFmpegArgs, build_clip_args
from clipforge.core.models import (
    ClipPlan,
    EffectName,
    EffectsConfig,
    EffectSettings,
    JobSpec,
    OutputConfig,
    Preset,
    ResolvedEffects,
    SlicingConfig,
    VideoMetadata,
)
from clipforge.core.planner import plan_job
from clipforge.core.presets import (
    BUILTIN_PRESET_NAMES,
    CURRENT_SCHEMA_VERSION,
    discover_builtins,
    discover_user_presets,
    load_preset_from_file,
    load_preset_from_json,
    save_preset_to_file,
)

__all__ = [
    "BUILTIN_PRESET_NAMES",
    "CURRENT_SCHEMA_VERSION",
    "ClipForgeError",
    "ClipPlan",
    "EffectName",
    "EffectSettings",
    "EffectsConfig",
    "FFmpegArgs",
    "FilterBuildError",
    "JobSpec",
    "OutputConfig",
    "PlanningError",
    "Preset",
    "PresetError",
    "ResolvedEffects",
    "SlicingConfig",
    "ValidationError",
    "VideoMetadata",
    "build_clip_args",
    "discover_builtins",
    "discover_user_presets",
    "load_preset_from_file",
    "load_preset_from_json",
    "plan_job",
    "save_preset_to_file",
]
