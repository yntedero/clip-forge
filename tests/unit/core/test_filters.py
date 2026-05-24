"""Tests for clipforge.core.filters.

Uses exact-string golden assertions to lock the filter graph format.
"""

from __future__ import annotations

from pathlib import Path


def _empty_effects():
    from clipforge.core.models import ResolvedEffects

    return ResolvedEffects(
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


def _output(aspect: str = "9:16", codec: str = "libx264", quality: str = "balanced"):
    from clipforge.core.models import OutputConfig

    return OutputConfig(
        aspect=aspect,  # type: ignore[arg-type]
        codec=codec,  # type: ignore[arg-type]
        quality=quality,  # type: ignore[arg-type]
        audio_mode="keep",
    )


def _clip(effects, start: float = 0.0, length: float = 5.0):
    from clipforge.core.models import ClipPlan

    return ClipPlan(
        index=0,
        start_sec=start,
        length_sec=length,
        effects=effects,
        output_path=Path("/tmp/out/clip_0001.mp4"),
    )


def test_no_effects_filter_chain() -> None:
    from clipforge.core.filters import build_clip_args

    args = build_clip_args(
        clip=_clip(_empty_effects()),
        source_path=Path("src.mp4"),
        output=_output(),
        target_dimensions=(1080, 1920),
    )
    assert args.video_filter == (
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    )
    assert args.audio_filter is None


def test_input_args_use_fast_seek() -> None:
    from clipforge.core.filters import build_clip_args

    args = build_clip_args(
        clip=_clip(_empty_effects(), start=42.5, length=4.23),
        source_path=Path("src.mp4"),
        output=_output(),
        target_dimensions=(1080, 1920),
    )
    assert args.input_args == ["-ss", "42.500", "-i", "src.mp4", "-t", "4.230"]


def test_mirror_only() -> None:
    from clipforge.core.filters import build_clip_args

    re = _empty_effects().model_copy(update={"mirror_applied": True})
    args = build_clip_args(
        clip=_clip(re),
        source_path=Path("src.mp4"),
        output=_output(),
        target_dimensions=(1080, 1920),
    )
    assert args.video_filter == (
        "hflip,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    )


def test_mirror_zoom_speed_matches_spec_appendix_a() -> None:
    """Spec Appendix A first example."""
    from clipforge.core.filters import build_clip_args

    re = _empty_effects().model_copy(
        update={
            "mirror_applied": True,
            "zoom_factor": 1.08,
            "speed_factor": 1.05,
        }
    )
    args = build_clip_args(
        clip=_clip(re),
        source_path=Path("src.mp4"),
        output=_output(),
        target_dimensions=(1080, 1920),
    )
    assert args.video_filter == (
        "hflip,"
        "crop=iw/1.08:ih/1.08,"
        "setpts=PTS/1.05,"
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "setsar=1"
    )
    assert args.audio_filter == "atempo=1.050"


def test_full_stack_matches_spec_appendix_a() -> None:
    """Spec Appendix A second example, with parameters chosen to match."""
    import math

    from clipforge.core.filters import build_clip_args

    re = _empty_effects().model_copy(
        update={
            "mirror_applied": True,
            "zoom_factor": 1.10,
            "speed_factor": 1.06,
            "rotation_deg": 2.0,
            "edge_crop_pct": 0.03,
            "color_brightness": 0.04,
            "color_contrast": 1.06,
            "color_saturation": 1.03,
            "noise_level": 8.0,
            "vignette_angle": math.pi / 4,
        }
    )
    args = build_clip_args(
        clip=_clip(re),
        source_path=Path("src.mp4"),
        output=_output(),
        target_dimensions=(1080, 1920),
    )
    expected = (
        "hflip,"
        "rotate=2.000*PI/180:fillcolor=black,"
        "crop=iw*0.96:ih*0.96,"
        "crop=iw*0.94:ih*0.94,"
        "crop=iw/1.10:ih/1.10,"
        "eq=brightness=0.040:contrast=1.060:saturation=1.030,"
        "noise=alls=8:allf=t,"
        "vignette=angle=0.785,"
        "setpts=PTS/1.06,"
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "setsar=1"
    )
    assert args.video_filter == expected


def test_pixel_shift_modifies_final_crop() -> None:
    from clipforge.core.filters import build_clip_args

    re = _empty_effects().model_copy(update={"pixel_shift_x": 3, "pixel_shift_y": -2})
    args = build_clip_args(
        clip=_clip(re),
        source_path=Path("src.mp4"),
        output=_output(),
        target_dimensions=(1080, 1920),
    )
    assert args.video_filter is not None
    assert "crop=1080:1920:3:-2" in args.video_filter
    assert args.video_filter.count("crop=") == 1


def test_atempo_outside_range_chains() -> None:
    from clipforge.core.filters import build_clip_args

    re = _empty_effects().model_copy(update={"speed_factor": 0.3})
    args = build_clip_args(
        clip=_clip(re),
        source_path=Path("src.mp4"),
        output=_output(),
        target_dimensions=(1080, 1920),
    )
    assert args.audio_filter is not None
    assert args.audio_filter.count("atempo") >= 2


def test_pitch_preservation_uses_rubberband() -> None:
    from clipforge.core.filters import build_clip_args

    re = _empty_effects().model_copy(update={"speed_factor": 1.1, "pitch_preservation": True})
    args = build_clip_args(
        clip=_clip(re),
        source_path=Path("src.mp4"),
        output=_output(),
        target_dimensions=(1080, 1920),
    )
    assert args.audio_filter == "rubberband=tempo=1.10"


def test_aspect_original_skips_target_crop() -> None:
    from clipforge.core.filters import build_clip_args

    args = build_clip_args(
        clip=_clip(_empty_effects()),
        source_path=Path("src.mp4"),
        output=_output(aspect="original"),
        target_dimensions=(1920, 1080),
    )
    assert args.video_filter == "setsar=1"


def test_output_args_libx264_balanced() -> None:
    from clipforge.core.filters import build_clip_args

    args = build_clip_args(
        clip=_clip(_empty_effects()),
        source_path=Path("src.mp4"),
        output=_output(),
        target_dimensions=(1080, 1920),
    )
    joined = " ".join(args.output_args)
    assert "-c:v libx264" in joined
    assert "-preset medium" in joined
    assert "-crf 20" in joined
    assert "-pix_fmt yuv420p" in joined
    assert "-c:a aac" in joined
    assert "-movflags +faststart" in joined


def test_output_args_fast_preset() -> None:
    from clipforge.core.filters import build_clip_args

    args = build_clip_args(
        clip=_clip(_empty_effects()),
        source_path=Path("src.mp4"),
        output=_output(quality="fast"),
        target_dimensions=(1080, 1920),
    )
    joined = " ".join(args.output_args)
    assert "-preset veryfast" in joined
    assert "-crf 23" in joined


def test_output_args_nvenc_balanced() -> None:
    from clipforge.core.filters import build_clip_args

    args = build_clip_args(
        clip=_clip(_empty_effects()),
        source_path=Path("src.mp4"),
        output=_output(codec="h264_nvenc"),
        target_dimensions=(1080, 1920),
    )
    joined = " ".join(args.output_args)
    assert "-c:v h264_nvenc" in joined
    assert "-preset p4" in joined
    assert "-cq 23" in joined


def test_atempo_above_range_chains() -> None:
    from clipforge.core.filters import build_clip_args

    re = _empty_effects().model_copy(update={"speed_factor": 3.0})
    args = build_clip_args(
        clip=_clip(re),
        source_path=Path("src.mp4"),
        output=_output(),
        target_dimensions=(1080, 1920),
    )
    assert args.audio_filter is not None
    assert args.audio_filter.count("atempo") >= 2


def test_film_grain_filter() -> None:
    from clipforge.core.filters import build_clip_args

    re = _empty_effects().model_copy(update={"film_grain_level": 12.0})
    args = build_clip_args(
        clip=_clip(re),
        source_path=Path("src.mp4"),
        output=_output(),
        target_dimensions=(1080, 1920),
    )
    assert args.video_filter is not None
    assert "noise=c0s=12:allf=t" in args.video_filter


def test_audio_mode_mute() -> None:
    from clipforge.core.filters import build_clip_args
    from clipforge.core.models import OutputConfig

    out = OutputConfig(aspect="9:16", codec="libx264", quality="balanced", audio_mode="mute")
    args = build_clip_args(
        clip=_clip(_empty_effects()),
        source_path=Path("src.mp4"),
        output=out,
        target_dimensions=(1080, 1920),
    )
    joined = " ".join(args.output_args)
    assert "-af volume=0" in joined


def test_audio_mode_remove() -> None:
    from clipforge.core.filters import build_clip_args
    from clipforge.core.models import OutputConfig

    out = OutputConfig(aspect="9:16", codec="libx264", quality="balanced", audio_mode="remove")
    args = build_clip_args(
        clip=_clip(_empty_effects()),
        source_path=Path("src.mp4"),
        output=out,
        target_dimensions=(1080, 1920),
    )
    joined = " ".join(args.output_args)
    assert "-an" in joined


def test_output_args_include_target_fps() -> None:
    from clipforge.core.filters import build_clip_args
    from clipforge.core.models import OutputConfig

    out = OutputConfig(
        aspect="9:16", codec="libx264", quality="balanced", audio_mode="keep", target_fps=60
    )
    args = build_clip_args(
        clip=_clip(_empty_effects()),
        source_path=Path("src.mp4"),
        output=out,
        target_dimensions=(1080, 1920),
    )
    joined = " ".join(args.output_args)
    assert "-r 60" in joined
