"""FFmpeg argument generation.

Converts a :class:`ClipPlan` plus :class:`OutputConfig` into the input,
filter, and output argument lists needed by FFmpeg.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from clipforge.core.models import ClipPlan, OutputConfig, ResolvedEffects

_X264_QUALITY: Final[dict[str, tuple[str, str]]] = {
    "fast": ("veryfast", "23"),
    "balanced": ("medium", "20"),
    "high": ("slow", "17"),
}
_X265_QUALITY: Final[dict[str, tuple[str, str]]] = {
    "fast": ("fast", "26"),
    "balanced": ("medium", "23"),
    "high": ("slow", "20"),
}
_NVENC_QUALITY: Final[dict[str, tuple[str, str]]] = {
    "fast": ("p1", "28"),
    "balanced": ("p4", "23"),
    "high": ("p7", "20"),
}
_QSV_QUALITY: Final[dict[str, tuple[str, str]]] = {
    "fast": ("veryfast", "28"),
    "balanced": ("medium", "23"),
    "high": ("slow", "20"),
}
_AMF_QUALITY: Final[dict[str, tuple[str, str]]] = {
    "fast": ("speed", "28"),
    "balanced": ("balanced", "23"),
    "high": ("quality", "20"),
}


@dataclass(frozen=True, slots=True)
class FFmpegArgs:
    input_args: list[str]
    video_filter: str | None
    audio_filter: str | None
    output_args: list[str]


def _chain_atempo(factor: float) -> str:
    """atempo only accepts [0.5, 2.0]; chain stages to reach factors outside it."""
    stages: list[float] = []
    remaining = factor
    while remaining < 0.5:
        stages.append(0.5)
        remaining /= 0.5
    while remaining > 2.0:
        stages.append(2.0)
        remaining /= 2.0
    stages.append(remaining)
    return ",".join(f"atempo={s:.3f}" for s in stages)


def _build_video_filter(
    re: ResolvedEffects,
    target_dimensions: tuple[int, int],
    aspect: str,
) -> str | None:
    parts: list[str] = []

    if re.mirror_applied:
        parts.append("hflip")

    if re.rotation_deg is not None:
        parts.append(f"rotate={re.rotation_deg:.3f}*PI/180:fillcolor=black")
        parts.append("crop=iw*0.96:ih*0.96")

    if re.edge_crop_pct is not None:
        scale = 1.0 - 2.0 * re.edge_crop_pct
        parts.append(f"crop=iw*{scale:.2f}:ih*{scale:.2f}")

    if re.zoom_factor is not None and abs(re.zoom_factor - 1.0) > 1e-9:
        parts.append(f"crop=iw/{re.zoom_factor:.2f}:ih/{re.zoom_factor:.2f}")

    if (
        re.color_brightness is not None
        or re.color_contrast is not None
        or re.color_saturation is not None
    ):
        b = re.color_brightness or 0.0
        c = re.color_contrast if re.color_contrast is not None else 1.0
        s = re.color_saturation if re.color_saturation is not None else 1.0
        parts.append(f"eq=brightness={b:.3f}:contrast={c:.3f}:saturation={s:.3f}")

    if re.noise_level is not None:
        parts.append(f"noise=alls={round(re.noise_level)}:allf=t")

    if re.film_grain_level is not None:
        parts.append(f"noise=c0s={round(re.film_grain_level)}:allf=t")

    if re.vignette_angle is not None:
        parts.append(f"vignette=angle={re.vignette_angle:.3f}")

    if re.speed_factor is not None and abs(re.speed_factor - 1.0) > 1e-9:
        parts.append(f"setpts=PTS/{re.speed_factor:.2f}")

    width, height = target_dimensions
    if aspect != "original":
        parts.append(f"scale={width}:{height}:force_original_aspect_ratio=increase")
        if re.pixel_shift_x is not None or re.pixel_shift_y is not None:
            x = re.pixel_shift_x or 0
            y = re.pixel_shift_y or 0
            parts.append(f"crop={width}:{height}:{x}:{y}")
        else:
            parts.append(f"crop={width}:{height}")

    parts.append("setsar=1")
    return ",".join(parts) if parts else None


def _build_audio_filter(re: ResolvedEffects) -> str | None:
    if re.speed_factor is None or abs(re.speed_factor - 1.0) < 1e-9:
        return None
    if re.pitch_preservation:
        return f"rubberband=tempo={re.speed_factor:.2f}"
    return _chain_atempo(re.speed_factor)


def _quality_table(codec: str) -> dict[str, tuple[str, str]]:
    return {
        "libx264": _X264_QUALITY,
        "libx265": _X265_QUALITY,
        "h264_nvenc": _NVENC_QUALITY,
        "h264_qsv": _QSV_QUALITY,
        "h264_amf": _AMF_QUALITY,
    }[codec]


def _quality_flag(codec: str) -> str:
    return "-cq" if codec == "h264_nvenc" else "-crf"


def _build_output_args(clip: ClipPlan, output: OutputConfig) -> list[str]:
    preset, value = _quality_table(output.codec)[output.quality]
    args: list[str] = [
        "-c:v",
        output.codec,
        "-preset",
        preset,
        _quality_flag(output.codec),
        value,
        "-pix_fmt",
        "yuv420p",
    ]
    if output.audio_mode == "keep":
        args.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"])
    elif output.audio_mode == "mute":
        args.extend(["-c:a", "aac", "-af", "volume=0"])
    elif output.audio_mode == "remove":
        args.append("-an")
    args.append("-movflags")
    args.append("+faststart")
    if output.target_fps is not None:
        args.extend(["-r", str(output.target_fps)])
    args.append(str(clip.output_path))
    return args


def build_clip_args(
    clip: ClipPlan,
    source_path: Path,
    output: OutputConfig,
    target_dimensions: tuple[int, int],
) -> FFmpegArgs:
    input_args = [
        "-ss",
        f"{clip.start_sec:.3f}",
        "-i",
        str(source_path),
        "-t",
        f"{clip.length_sec:.3f}",
    ]
    video_filter = _build_video_filter(clip.effects, target_dimensions, output.aspect)
    audio_filter = _build_audio_filter(clip.effects)
    output_args = _build_output_args(clip, output)
    return FFmpegArgs(
        input_args=input_args,
        video_filter=video_filter,
        audio_filter=audio_filter,
        output_args=output_args,
    )
