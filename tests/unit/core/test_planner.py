"""Tests for clipforge.core.planner."""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest


def _make_metadata(duration_sec: float = 60.0):
    from clipforge.core.models import VideoMetadata

    return VideoMetadata(
        duration_sec=duration_sec,
        width=1920,
        height=1080,
        fps=30.0,
        has_audio=True,
    )


def _make_job(
    duration_min: float = 3.0,
    duration_max: float = 5.0,
    strategy: str = "sequential",
    sample_count: int | None = None,
    skip_start: float = 0.0,
    skip_end: float = 0.0,
    seed: int | None = None,
):
    from clipforge.core.models import (
        EffectsConfig,
        EffectSettings,
        JobSpec,
        OutputConfig,
        SlicingConfig,
    )

    off = EffectSettings(enabled=False, intensity=0.0, probability=0.0)
    return JobSpec(
        source_path=Path("input.mp4"),
        output_root=Path("/tmp/out"),
        slicing=SlicingConfig(
            strategy=strategy,  # type: ignore[arg-type]
            min_length_sec=duration_min,
            max_length_sec=duration_max,
            skip_start_sec=skip_start,
            skip_end_sec=skip_end,
            random_sample_count=sample_count,
        ),
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
        seed=seed,
    )


def test_sequential_basic() -> None:
    from clipforge.core.planner import plan_job

    plans = plan_job(_make_job(seed=42), _make_metadata(60.0), seed=42)
    assert len(plans) > 0
    assert plans[0].index == 0
    assert plans[-1].index == len(plans) - 1


def test_sequential_total_duration_fits() -> None:
    from clipforge.core.planner import plan_job

    job = _make_job(duration_min=3.0, duration_max=5.0, seed=1)
    plans = plan_job(job, _make_metadata(30.0), seed=1)
    total = sum(p.length_sec for p in plans)
    assert total <= 30.0


def test_sequential_lengths_within_bounds() -> None:
    from clipforge.core.planner import plan_job

    job = _make_job(duration_min=3.0, duration_max=5.0, seed=1)
    plans = plan_job(job, _make_metadata(60.0), seed=1)
    for p in plans:
        assert 3.0 - 1e-9 <= p.length_sec <= 5.0 + 1e-9


def test_skip_start_end_honored() -> None:
    from clipforge.core.planner import plan_job

    job = _make_job(skip_start=5.0, skip_end=5.0, seed=1)
    plans = plan_job(job, _make_metadata(30.0), seed=1)
    for p in plans:
        assert p.start_sec >= 5.0 - 1e-9
        assert p.start_sec + p.length_sec <= 25.0 + 1e-9


def test_planning_error_when_source_too_short() -> None:
    from clipforge.core.exceptions import PlanningError
    from clipforge.core.planner import plan_job

    job = _make_job(duration_min=10.0, duration_max=15.0)
    with pytest.raises(PlanningError):
        plan_job(job, _make_metadata(5.0))


def test_random_sample_count() -> None:
    from clipforge.core.planner import plan_job

    job = _make_job(
        strategy="random_sample",
        duration_min=3.0,
        duration_max=5.0,
        sample_count=8,
        seed=1,
    )
    plans = plan_job(job, _make_metadata(120.0), seed=1)
    assert len(plans) == 8


def test_random_sample_no_overlap() -> None:
    from clipforge.core.planner import plan_job

    job = _make_job(
        strategy="random_sample",
        duration_min=3.0,
        duration_max=5.0,
        sample_count=5,
        seed=1,
    )
    plans = plan_job(job, _make_metadata(120.0), seed=1)
    sorted_plans = sorted(plans, key=lambda p: p.start_sec)
    for a, b in itertools.pairwise(sorted_plans):
        assert a.start_sec + a.length_sec <= b.start_sec + 1e-9


def test_random_sample_density_too_high_raises() -> None:
    from clipforge.core.exceptions import PlanningError
    from clipforge.core.planner import plan_job

    # 30 clips of >=3s require >=90s; only 30s available → impossible.
    job = _make_job(
        strategy="random_sample",
        duration_min=3.0,
        duration_max=5.0,
        sample_count=30,
        seed=1,
    )
    with pytest.raises(PlanningError):
        plan_job(job, _make_metadata(30.0))


def test_determinism_same_seed() -> None:
    from clipforge.core.planner import plan_job

    job = _make_job(seed=7)
    md = _make_metadata(60.0)
    a = plan_job(job, md, seed=7)
    b = plan_job(job, md, seed=7)
    assert a == b


def test_determinism_different_seed_differs() -> None:
    from clipforge.core.planner import plan_job

    job = _make_job(seed=7)
    md = _make_metadata(60.0)
    a = plan_job(job, md, seed=7)
    b = plan_job(job, md, seed=8)
    assert a != b


def test_effects_pre_resolved() -> None:
    from clipforge.core.planner import plan_job

    job = _make_job(seed=1)
    plans = plan_job(job, _make_metadata(30.0), seed=1)
    # All disabled → mirror_applied False on every clip
    for p in plans:
        assert p.effects.mirror_applied is False


def test_output_path_naming() -> None:
    from clipforge.core.planner import plan_job

    job = _make_job(seed=1)
    plans = plan_job(job, _make_metadata(30.0), seed=1)
    expected_dir = job.output_root / (job.source_path.stem + "_clips")
    for p in plans:
        assert p.output_path.parent == expected_dir
        assert p.output_path.name.endswith(".mp4")
        assert f"clip_{p.index + 1:04d}" in p.output_path.name
