"""Per-clip effect resolution.

Given an :class:`EffectsConfig` and a clip index, deterministically (given
an RNG) produce a :class:`ResolvedEffects` containing the concrete per-clip
parameters that the filter builder will turn into FFmpeg arguments.

The resolver uses a "draw, then decide" discipline: it pulls every RNG
value before checking whether to use it. This way, toggling one effect on
or off doesn't shift the RNG sequence seen by other effects, so per-clip
output stays stable under config tweaks.
"""

from __future__ import annotations

import math
import random

from clipforge.core.models import (
    EffectsConfig,
    EffectSettings,
    ResolvedEffects,
)


def _effective_intensity(effect: EffectSettings, global_intensity: float) -> float:
    return max(0.0, min(1.5, effect.intensity * global_intensity))


def _apply(effect: EffectSettings, rng: random.Random) -> bool:
    """Return True iff the effect's probability roll says to apply it.

    Always consumes one RNG value regardless of probability, so the RNG
    sequence is stable across config tweaks.
    """
    roll = rng.random()
    if not effect.enabled:
        return False
    return roll < effect.probability


def resolve_effects(
    config: EffectsConfig,
    clip_index: int,  # reserved for future per-clip biasing
    rng: random.Random,
) -> ResolvedEffects:
    g = config.global_intensity

    # 1. Mirror
    mirror_applied = _apply(config.mirror, rng)

    # 2. Zoom
    zoom_apply = _apply(config.zoom, rng)
    zoom_intensity = _effective_intensity(config.zoom, g)
    zoom_raw = rng.uniform(1.0, 1.0 + 0.20 * zoom_intensity)
    zoom_factor = zoom_raw if (zoom_apply and zoom_intensity > 0.0) else None

    # 3. Speed
    speed_apply = _apply(config.speed, rng)
    speed_intensity = _effective_intensity(config.speed, g)
    speed_delta = rng.uniform(-0.15, 0.15) * speed_intensity
    speed_factor = 1.0 + speed_delta if (speed_apply and speed_intensity > 0.0) else None

    # 4. Color
    color_apply = _apply(config.color, rng)
    color_intensity = _effective_intensity(config.color, g)
    color_b_raw = rng.uniform(-0.08, 0.08) * color_intensity
    color_c_raw = 1.0 + rng.uniform(-0.10, 0.10) * color_intensity
    color_s_raw = 1.0 + rng.uniform(-0.10, 0.15) * color_intensity
    if color_apply and color_intensity > 0.0:
        color_brightness: float | None = color_b_raw
        color_contrast: float | None = color_c_raw
        color_saturation: float | None = color_s_raw
    else:
        color_brightness = color_contrast = color_saturation = None

    # 5. Rotation
    rotation_apply = _apply(config.rotation, rng)
    rotation_intensity = _effective_intensity(config.rotation, g)
    rotation_raw = rng.uniform(-3.0, 3.0) * rotation_intensity
    rotation_deg = rotation_raw if (rotation_apply and rotation_intensity > 0.0) else None

    # 6. Edge crop
    edge_apply = _apply(config.edge_crop, rng)
    edge_intensity = _effective_intensity(config.edge_crop, g)
    edge_raw = rng.uniform(0.01, 0.06) * edge_intensity
    edge_crop_pct = edge_raw if (edge_apply and edge_intensity > 0.0) else None

    # 7. Noise
    noise_apply = _apply(config.noise, rng)
    noise_intensity = _effective_intensity(config.noise, g)
    noise_level = 12.0 * noise_intensity if (noise_apply and noise_intensity > 0.0) else None

    # 8. Vignette
    vignette_apply = _apply(config.vignette, rng)
    vignette_intensity = _effective_intensity(config.vignette, g)
    vignette_angle = (
        (math.pi / 3.5) * vignette_intensity
        if (vignette_apply and vignette_intensity > 0.0)
        else None
    )

    # 9. Pixel shift
    px_apply = _apply(config.pixel_shift, rng)
    px_intensity = _effective_intensity(config.pixel_shift, g)
    px_x_raw = rng.randint(-8, 8)
    px_y_raw = rng.randint(-8, 8)
    if px_apply and px_intensity > 0.0:
        px_x = round(px_x_raw * px_intensity)
        px_y = round(px_y_raw * px_intensity)
        # Guarantee non-zero magnitude when applied
        if px_x == 0 and px_y == 0:
            px_x = 1
        pixel_shift_x: int | None = px_x
        pixel_shift_y: int | None = px_y
    else:
        pixel_shift_x = pixel_shift_y = None

    # 10. Film grain
    grain_apply = _apply(config.film_grain, rng)
    grain_intensity = _effective_intensity(config.film_grain, g)
    film_grain_level = 12.0 * grain_intensity if (grain_apply and grain_intensity > 0.0) else None

    return ResolvedEffects(
        mirror_applied=mirror_applied,
        zoom_factor=zoom_factor,
        speed_factor=speed_factor,
        color_brightness=color_brightness,
        color_contrast=color_contrast,
        color_saturation=color_saturation,
        rotation_deg=rotation_deg,
        edge_crop_pct=edge_crop_pct,
        noise_level=noise_level,
        vignette_angle=vignette_angle,
        pixel_shift_x=pixel_shift_x,
        pixel_shift_y=pixel_shift_y,
        film_grain_level=film_grain_level,
        pitch_preservation=config.pitch_preservation,
    )
