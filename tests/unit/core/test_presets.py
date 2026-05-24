"""Tests for clipforge.core.presets."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_load_preset_from_json_valid() -> None:
    from clipforge.core.presets import load_preset_from_json

    text = """
{
  "schema_version": 1,
  "name": "X",
  "description": null,
  "builtin": false,
  "mode": "clips",
  "slicing": {"strategy": "sequential", "min_length_sec": 3, "max_length_sec": 5,
              "skip_start_sec": 0, "skip_end_sec": 0, "random_sample_count": null},
  "effects": {
    "global_intensity": 1.0,
    "mirror": {"enabled": false, "intensity": 0, "probability": 0},
    "zoom": {"enabled": false, "intensity": 0, "probability": 0},
    "speed": {"enabled": false, "intensity": 0, "probability": 0},
    "color": {"enabled": false, "intensity": 0, "probability": 0},
    "rotation": {"enabled": false, "intensity": 0, "probability": 0},
    "edge_crop": {"enabled": false, "intensity": 0, "probability": 0},
    "noise": {"enabled": false, "intensity": 0, "probability": 0},
    "vignette": {"enabled": false, "intensity": 0, "probability": 0},
    "pixel_shift": {"enabled": false, "intensity": 0, "probability": 0},
    "film_grain": {"enabled": false, "intensity": 0, "probability": 0},
    "pitch_preservation": false
  },
  "output": {
    "aspect": "9:16", "codec": "libx264", "quality": "balanced", "audio_mode": "keep",
    "audio_overlay_path": null, "audio_overlay_volume": 0.6, "source_audio_volume": 1.0,
    "target_fps": 30, "shuffle_assembled": false, "transition": "none"
  }
}
"""
    p = load_preset_from_json(text)
    assert p.name == "X"
    assert p.schema_version == 1


def test_load_preset_bad_schema_version() -> None:
    from clipforge.core.exceptions import PresetError
    from clipforge.core.presets import load_preset_from_json

    bad = '{"schema_version": 99, "name": "x"}'
    with pytest.raises(PresetError):
        load_preset_from_json(bad)


def test_load_preset_malformed_json() -> None:
    from clipforge.core.exceptions import PresetError
    from clipforge.core.presets import load_preset_from_json

    with pytest.raises(PresetError):
        load_preset_from_json("{not json")


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    from clipforge.core.models import (
        EffectsConfig,
        EffectSettings,
        OutputConfig,
        Preset,
        SlicingConfig,
    )
    from clipforge.core.presets import (
        load_preset_from_file,
        save_preset_to_file,
    )

    off = EffectSettings(enabled=False, intensity=0.0, probability=0.0)
    p = Preset(
        name="Round-trip",
        slicing=SlicingConfig(min_length_sec=3, max_length_sec=5),
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
    target = tmp_path / "rt.cfp.json"
    save_preset_to_file(p, target)
    restored = load_preset_from_file(target)
    assert restored == p


def test_discover_builtins_returns_five() -> None:
    from clipforge.core.presets import discover_builtins

    presets = discover_builtins()
    names = sorted(p.name for p in presets)
    assert set(names) == {
        "TikTok Soft",
        "TikTok Hard Uniq",
        "YouTube Shorts",
        "Instagram Reels",
        "Plain Slice",
    }
    for p in presets:
        assert p.builtin is True


def test_builtin_tiktok_soft_matches_spec_appendix_b() -> None:
    """The TikTok Soft preset matches spec Appendix B's values."""
    from clipforge.core.presets import discover_builtins

    by_name = {p.name: p for p in discover_builtins()}
    tt = by_name["TikTok Soft"]
    assert tt.slicing.min_length_sec == 3.0
    assert tt.slicing.max_length_sec == 6.0
    assert tt.effects.global_intensity == 0.8
    assert tt.effects.mirror.enabled is True
    assert tt.effects.mirror.probability == 0.5
    assert tt.effects.rotation.enabled is False
    assert tt.output.aspect == "9:16"


def test_plain_slice_has_no_effects() -> None:
    from clipforge.core.presets import discover_builtins

    by_name = {p.name: p for p in discover_builtins()}
    ps = by_name["Plain Slice"]
    assert ps.effects.global_intensity == 0.0
    for name in (
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
    ):
        assert getattr(ps.effects, name).enabled is False
