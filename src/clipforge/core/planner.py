"""Slicing planner.

Turns a :class:`JobSpec` plus :class:`VideoMetadata` into a deterministic
list of :class:`ClipPlan` objects, with effects pre-resolved per clip.
"""

from __future__ import annotations

import random
from pathlib import Path

from clipforge.core.effects import resolve_effects
from clipforge.core.exceptions import PlanningError
from clipforge.core.models import ClipPlan, JobSpec, VideoMetadata

_RANDOM_SAMPLE_MAX_REJECTIONS = 100


def _build_output_path(job: JobSpec, index: int) -> Path:
    stem = job.source_path.stem
    return job.output_root / f"{stem}_clips" / f"{stem}_clip_{index + 1:04d}.mp4"


def _plan_sequential(
    job: JobSpec,
    usable_start: float,
    usable_end: float,
    rng: random.Random,
) -> list[tuple[float, float]]:
    slicing = job.slicing
    out: list[tuple[float, float]] = []
    cursor = usable_start
    while cursor < usable_end:
        length = rng.uniform(slicing.min_length_sec, slicing.max_length_sec)
        if cursor + length > usable_end:
            break
        out.append((cursor, length))
        cursor += length
    return out


def _plan_random_sample(
    job: JobSpec,
    usable_start: float,
    usable_end: float,
    rng: random.Random,
) -> list[tuple[float, float]]:
    slicing = job.slicing
    count = slicing.random_sample_count
    if count is None:
        raise PlanningError("random_sample requires random_sample_count")

    placed: list[tuple[float, float]] = []
    rejections = 0
    while len(placed) < count:
        if rejections >= _RANDOM_SAMPLE_MAX_REJECTIONS:
            raise PlanningError("random_sample density too high for source")
        length = rng.uniform(slicing.min_length_sec, slicing.max_length_sec)
        max_start = usable_end - length
        if max_start <= usable_start:
            rejections += 1
            continue
        start = rng.uniform(usable_start, max_start)
        end = start + length
        # Reject if overlapping any existing clip
        if any(not (end <= s or start >= s + length_existing) for s, length_existing in placed):
            rejections += 1
            continue
        placed.append((start, length))
        rejections = 0

    placed.sort(key=lambda p: p[0])
    return placed


def plan_job(
    job: JobSpec,
    source_metadata: VideoMetadata,
    seed: int | None = None,
) -> list[ClipPlan]:
    slicing = job.slicing
    usable_start = slicing.skip_start_sec
    usable_end = source_metadata.duration_sec - slicing.skip_end_sec
    if usable_end - usable_start < slicing.min_length_sec:
        raise PlanningError(
            f"usable duration {usable_end - usable_start:.2f}s is shorter "
            f"than min_length_sec {slicing.min_length_sec:.2f}s"
        )

    effective_seed = seed if seed is not None else job.seed
    rng = random.Random(effective_seed) if effective_seed is not None else random.Random()

    if slicing.strategy == "sequential":
        ranges = _plan_sequential(job, usable_start, usable_end, rng)
    else:
        ranges = _plan_random_sample(job, usable_start, usable_end, rng)

    plans: list[ClipPlan] = []
    for i, (start, length) in enumerate(ranges):
        effects = resolve_effects(job.effects, clip_index=i, rng=rng)
        plans.append(
            ClipPlan(
                index=i,
                start_sec=start,
                length_sec=length,
                effects=effects,
                output_path=_build_output_path(job, i),
            )
        )
    return plans
