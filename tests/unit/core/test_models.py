"""Tests for clipforge.core.models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError


def test_effect_settings_defaults() -> None:
    from clipforge.core.models import EffectSettings

    s = EffectSettings(enabled=True)
    assert s.intensity == 1.0
    assert s.probability == 1.0


def test_effect_settings_bounds() -> None:
    from clipforge.core.models import EffectSettings

    with pytest.raises(PydanticValidationError):
        EffectSettings(enabled=True, intensity=1.5)
    with pytest.raises(PydanticValidationError):
        EffectSettings(enabled=True, intensity=-0.1)
    with pytest.raises(PydanticValidationError):
        EffectSettings(enabled=True, probability=1.5)


def test_slicing_config_valid() -> None:
    from clipforge.core.models import SlicingConfig

    cfg = SlicingConfig(min_length_sec=3.0, max_length_sec=5.0)
    assert cfg.strategy == "sequential"
    assert cfg.skip_start_sec == 0.0


def test_slicing_config_min_gt_max_rejected() -> None:
    from clipforge.core.models import SlicingConfig

    with pytest.raises(PydanticValidationError):
        SlicingConfig(min_length_sec=5.0, max_length_sec=3.0)


def test_slicing_config_random_sample_count_zero_rejected() -> None:
    """random_sample_count=0 is rejected by the ge=1 field constraint."""
    from clipforge.core.models import SlicingConfig

    with pytest.raises(PydanticValidationError):
        SlicingConfig(
            strategy="random_sample",
            min_length_sec=3.0,
            max_length_sec=5.0,
            random_sample_count=0,
        )


def test_slicing_config_random_sample_count_default_none_rejected() -> None:
    """The model_validator rejects random_sample with no count supplied."""
    from clipforge.core.models import SlicingConfig

    with pytest.raises(PydanticValidationError):
        SlicingConfig(
            strategy="random_sample",
            min_length_sec=3.0,
            max_length_sec=5.0,
            # random_sample_count defaults to None → validator should reject
        )


def test_effects_config_defaults() -> None:
    from clipforge.core.models import EffectsConfig, EffectSettings

    disabled = EffectSettings(enabled=False, intensity=0.0, probability=0.0)
    cfg = EffectsConfig(
        global_intensity=1.0,
        mirror=disabled,
        zoom=disabled,
        speed=disabled,
        color=disabled,
        rotation=disabled,
        edge_crop=disabled,
        noise=disabled,
        vignette=disabled,
        pixel_shift=disabled,
        film_grain=disabled,
    )
    assert cfg.pitch_preservation is False


def test_output_config_aspect_choices() -> None:
    from clipforge.core.models import OutputConfig

    cfg = OutputConfig(
        aspect="9:16",
        codec="libx264",
        quality="balanced",
        audio_mode="keep",
    )
    assert cfg.target_fps == 30


def test_models_are_frozen() -> None:
    from clipforge.core.models import EffectSettings

    s = EffectSettings(enabled=True)
    with pytest.raises(PydanticValidationError):
        s.intensity = 0.5  # type: ignore[misc]


def test_models_reject_unknown_keys() -> None:
    from clipforge.core.models import EffectSettings

    with pytest.raises(PydanticValidationError):
        EffectSettings.model_validate({"enabled": True, "what": "ever"})


def test_video_metadata() -> None:
    from clipforge.core.models import VideoMetadata

    vm = VideoMetadata(
        duration_sec=60.0,
        width=1920,
        height=1080,
        fps=30.0,
        has_audio=True,
    )
    assert vm.duration_sec == 60.0


def test_job_spec_round_trip() -> None:
    from clipforge.core.models import (
        EffectsConfig,
        EffectSettings,
        JobSpec,
        OutputConfig,
        SlicingConfig,
    )

    disabled = EffectSettings(enabled=False, intensity=0.0, probability=0.0)
    enabled = EffectSettings(enabled=True, intensity=0.5, probability=1.0)

    job = JobSpec(
        source_path=Path("source.mp4"),
        output_root=Path("/tmp/out"),
        slicing=SlicingConfig(min_length_sec=3.0, max_length_sec=5.0),
        effects=EffectsConfig(
            global_intensity=1.0,
            mirror=enabled,
            zoom=enabled,
            speed=disabled,
            color=disabled,
            rotation=disabled,
            edge_crop=disabled,
            noise=disabled,
            vignette=disabled,
            pixel_shift=disabled,
            film_grain=disabled,
        ),
        output=OutputConfig(
            aspect="9:16",
            codec="libx264",
            quality="balanced",
            audio_mode="keep",
        ),
        mode="clips",
    )
    text = job.model_dump_json()
    restored = JobSpec.model_validate_json(text)
    assert restored == job


def test_resolved_effects_optional_fields() -> None:
    from clipforge.core.models import ResolvedEffects

    re = ResolvedEffects(
        mirror_applied=False,
        zoom_factor=None,
        speed_factor=None,
        color_brightness=None,
        color_contrast=None,
        color_saturation=None,
        rotation_deg=None,
        edge_crop_pct=None,
        noise_level=None,
        vignette_angle=None,
        pixel_shift_x=None,
        pixel_shift_y=None,
        film_grain_level=None,
        pitch_preservation=False,
    )
    assert re.mirror_applied is False


def test_clip_plan_fields() -> None:
    from clipforge.core.models import ClipPlan, ResolvedEffects

    re = ResolvedEffects(
        mirror_applied=True,
        zoom_factor=None,
        speed_factor=None,
        color_brightness=None,
        color_contrast=None,
        color_saturation=None,
        rotation_deg=None,
        edge_crop_pct=None,
        noise_level=None,
        vignette_angle=None,
        pixel_shift_x=None,
        pixel_shift_y=None,
        film_grain_level=None,
        pitch_preservation=False,
    )
    cp = ClipPlan(
        index=0,
        start_sec=0.0,
        length_sec=4.5,
        effects=re,
        output_path=Path("/tmp/out/clip_0001.mp4"),
    )
    assert cp.index == 0


def test_preset_round_trip() -> None:
    import json

    from clipforge.core.models import (
        EffectsConfig,
        EffectSettings,
        OutputConfig,
        Preset,
        SlicingConfig,
    )

    off = EffectSettings(enabled=False, intensity=0.0, probability=0.0)
    enabled = EffectSettings(enabled=True, intensity=0.8, probability=0.5)

    p = Preset(
        name="Test Preset",
        description="hello",
        builtin=False,
        slicing=SlicingConfig(min_length_sec=3.0, max_length_sec=5.0),
        effects=EffectsConfig(
            global_intensity=0.9,
            mirror=enabled,
            zoom=off,
            speed=off,
            color=off,
            rotation=off,
            edge_crop=off,
            noise=off,
            vignette=off,
            pixel_shift=off,
            film_grain=off,
        ),
        output=OutputConfig(
            aspect="9:16",
            codec="libx264",
            quality="balanced",
            audio_mode="keep",
        ),
        mode="clips",
    )
    text = p.model_dump_json()
    parsed = json.loads(text)
    assert parsed["schema_version"] == 1
    restored = Preset.model_validate_json(text)
    assert restored == p


def test_preset_name_whitespace_only_rejected() -> None:
    from clipforge.core.models import (
        EffectsConfig,
        EffectSettings,
        OutputConfig,
        Preset,
        SlicingConfig,
    )

    off = EffectSettings(enabled=False, intensity=0.0, probability=0.0)
    with pytest.raises(PydanticValidationError):
        Preset(
            name="   ",
            slicing=SlicingConfig(min_length_sec=3.0, max_length_sec=5.0),
            effects=EffectsConfig(
                global_intensity=1.0,
                mirror=off,
                zoom=off,
                speed=off,
                color=off,
                rotation=off,
                edge_crop=off,
                noise=off,
                vignette=off,
                pixel_shift=off,
                film_grain=off,
            ),
            output=OutputConfig(
                aspect="9:16",
                codec="libx264",
                quality="balanced",
                audio_mode="keep",
            ),
            mode="clips",
        )
