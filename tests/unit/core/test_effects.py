"""Tests for clipforge.core.effects."""

from __future__ import annotations

import math
import random

import pytest


def _all_disabled():
    from clipforge.core.models import EffectsConfig, EffectSettings

    off = EffectSettings(enabled=False, intensity=0.0, probability=0.0)
    return EffectsConfig(
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
    )


def _with(name: str, intensity: float = 1.0, probability: float = 1.0):
    from clipforge.core.models import EffectSettings

    cfg = _all_disabled()
    on = EffectSettings(enabled=True, intensity=intensity, probability=probability)
    return cfg.model_copy(update={name: on})


def test_all_disabled_resolves_to_no_effects() -> None:
    from clipforge.core.effects import resolve_effects

    rng = random.Random(0)
    re = resolve_effects(_all_disabled(), clip_index=0, rng=rng)
    assert re.mirror_applied is False
    assert re.zoom_factor is None
    assert re.speed_factor is None
    assert re.color_brightness is None
    assert re.rotation_deg is None
    assert re.edge_crop_pct is None
    assert re.noise_level is None
    assert re.vignette_angle is None
    assert re.pixel_shift_x is None
    assert re.pixel_shift_y is None
    assert re.film_grain_level is None


def test_mirror_probability_zero_never_applies() -> None:
    from clipforge.core.effects import resolve_effects

    cfg = _with("mirror", intensity=1.0, probability=0.0)
    rng = random.Random(42)
    for i in range(50):
        re = resolve_effects(cfg, clip_index=i, rng=rng)
        assert re.mirror_applied is False


def test_mirror_probability_one_always_applies() -> None:
    from clipforge.core.effects import resolve_effects

    cfg = _with("mirror", intensity=1.0, probability=1.0)
    rng = random.Random(42)
    for i in range(20):
        re = resolve_effects(cfg, clip_index=i, rng=rng)
        assert re.mirror_applied is True


def test_zoom_intensity_zero_skips() -> None:
    from clipforge.core.effects import resolve_effects

    cfg = _with("zoom", intensity=0.0, probability=1.0)
    rng = random.Random(0)
    re = resolve_effects(cfg, clip_index=0, rng=rng)
    assert re.zoom_factor is None


def test_zoom_intensity_one_in_range() -> None:
    from clipforge.core.effects import resolve_effects

    cfg = _with("zoom", intensity=1.0, probability=1.0)
    rng = random.Random(7)
    for i in range(20):
        re = resolve_effects(cfg, clip_index=i, rng=rng)
        assert re.zoom_factor is not None
        assert 1.0 <= re.zoom_factor <= 1.20 + 1e-9


def test_speed_intensity_one_in_range() -> None:
    from clipforge.core.effects import resolve_effects

    cfg = _with("speed", intensity=1.0, probability=1.0)
    rng = random.Random(7)
    for i in range(20):
        re = resolve_effects(cfg, clip_index=i, rng=rng)
        assert re.speed_factor is not None
        assert 0.85 - 1e-9 <= re.speed_factor <= 1.15 + 1e-9


def test_rotation_intensity_one_in_range() -> None:
    from clipforge.core.effects import resolve_effects

    cfg = _with("rotation", intensity=1.0, probability=1.0)
    rng = random.Random(7)
    for i in range(20):
        re = resolve_effects(cfg, clip_index=i, rng=rng)
        assert re.rotation_deg is not None
        assert -3.0 - 1e-9 <= re.rotation_deg <= 3.0 + 1e-9


def test_noise_intensity_full_is_12() -> None:
    from clipforge.core.effects import resolve_effects

    cfg = _with("noise", intensity=1.0, probability=1.0)
    rng = random.Random(0)
    re = resolve_effects(cfg, clip_index=0, rng=rng)
    assert re.noise_level == pytest.approx(12.0)


def test_vignette_intensity_full_is_pi_over_3_5() -> None:
    from clipforge.core.effects import resolve_effects

    cfg = _with("vignette", intensity=1.0, probability=1.0)
    rng = random.Random(0)
    re = resolve_effects(cfg, clip_index=0, rng=rng)
    assert re.vignette_angle == pytest.approx(math.pi / 3.5)


def test_global_intensity_scales_zoom() -> None:
    from clipforge.core.effects import resolve_effects
    from clipforge.core.models import EffectsConfig, EffectSettings

    on = EffectSettings(enabled=True, intensity=1.0, probability=1.0)
    off = EffectSettings(enabled=False, intensity=0.0, probability=0.0)
    cfg = EffectsConfig(
        global_intensity=0.5,
        mirror=off,
        zoom=on,
        speed=off,
        color=off,
        rotation=off,
        edge_crop=off,
        noise=off,
        vignette=off,
        pixel_shift=off,
        film_grain=off,
    )
    rng = random.Random(0)
    re = resolve_effects(cfg, clip_index=0, rng=rng)
    # effective intensity = 1.0 * 0.5 = 0.5 → zoom in [1.0, 1.10]
    assert re.zoom_factor is not None
    assert 1.0 <= re.zoom_factor <= 1.10 + 1e-9


def test_pitch_preservation_passthrough() -> None:
    from clipforge.core.effects import resolve_effects

    cfg = _all_disabled().model_copy(update={"pitch_preservation": True})
    rng = random.Random(0)
    re = resolve_effects(cfg, clip_index=0, rng=rng)
    assert re.pitch_preservation is True


def test_determinism_same_seed_same_output() -> None:
    """Two calls with identical inputs and same RNG state produce identical results."""
    from clipforge.core.effects import resolve_effects
    from clipforge.core.models import EffectsConfig, EffectSettings

    on = EffectSettings(enabled=True, intensity=0.5, probability=0.5)
    cfg = EffectsConfig(
        global_intensity=1.0,
        mirror=on,
        zoom=on,
        speed=on,
        color=on,
        rotation=on,
        edge_crop=on,
        noise=on,
        vignette=on,
        pixel_shift=on,
        film_grain=on,
    )
    rng_a = random.Random(123)
    rng_b = random.Random(123)
    out_a = resolve_effects(cfg, clip_index=5, rng=rng_a)
    out_b = resolve_effects(cfg, clip_index=5, rng=rng_b)
    assert out_a == out_b


def test_effect_toggle_stability() -> None:
    """Toggling one effect off must not shift the resolved values of other effects.

    Achieved by always drawing all RNG values regardless of which effects are enabled.
    """
    from clipforge.core.effects import resolve_effects
    from clipforge.core.models import EffectsConfig, EffectSettings

    on = EffectSettings(enabled=True, intensity=1.0, probability=1.0)
    off = EffectSettings(enabled=False, intensity=0.0, probability=0.0)
    cfg_all = EffectsConfig(
        global_intensity=1.0,
        mirror=on,
        zoom=on,
        speed=on,
        color=on,
        rotation=on,
        edge_crop=on,
        noise=on,
        vignette=on,
        pixel_shift=on,
        film_grain=on,
    )
    cfg_no_mirror = cfg_all.model_copy(update={"mirror": off})

    rng_a = random.Random(99)
    out_a = resolve_effects(cfg_all, clip_index=0, rng=rng_a)
    rng_b = random.Random(99)
    out_b = resolve_effects(cfg_no_mirror, clip_index=0, rng=rng_b)

    # Mirror differs by design (one is on, the other off).
    assert out_a.zoom_factor == out_b.zoom_factor
    assert out_a.speed_factor == out_b.speed_factor
    assert out_a.rotation_deg == out_b.rotation_deg
    assert out_a.noise_level == out_b.noise_level


def test_pixel_shift_int_range() -> None:
    from clipforge.core.effects import resolve_effects

    cfg = _with("pixel_shift", intensity=1.0, probability=1.0)
    rng = random.Random(7)
    seen_x: set[int] = set()
    seen_y: set[int] = set()
    for i in range(30):
        re = resolve_effects(cfg, clip_index=i, rng=rng)
        assert re.pixel_shift_x is not None
        assert re.pixel_shift_y is not None
        assert isinstance(re.pixel_shift_x, int)
        assert isinstance(re.pixel_shift_y, int)
        assert -8 <= re.pixel_shift_x <= 8
        assert -8 <= re.pixel_shift_y <= 8
        seen_x.add(re.pixel_shift_x)
        seen_y.add(re.pixel_shift_y)
    assert len(seen_x) > 1  # actually varying


class _ZeroRng(random.Random):
    """RNG whose random() always returns 0.0 and randint() always returns 0.

    Used to force pixel_shift into the (0,0) safety-guard branch.
    """

    def random(self) -> float:  # type: ignore[override]
        return 0.0

    def randint(self, a: int, b: int) -> int:  # type: ignore[override]
        return 0

    def uniform(self, a: float, b: float) -> float:  # type: ignore[override]
        return a  # lower bound — keeps other effects deterministic


def test_pixel_shift_zero_zero_safety_branch() -> None:
    """When both raw shifts round to 0, x is forced to 1 to keep the effect visible."""
    from clipforge.core.effects import resolve_effects

    cfg = _with("pixel_shift", intensity=1.0, probability=1.0)
    rng = _ZeroRng()
    re = resolve_effects(cfg, clip_index=0, rng=rng)
    assert re.pixel_shift_x == 1
    assert re.pixel_shift_y == 0
