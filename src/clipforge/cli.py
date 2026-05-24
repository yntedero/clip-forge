"""CLI subcommands.

Subcommand-aware entry point. ``python -m clipforge`` with no subcommand
opens the GUI. ``python -m clipforge plan ...`` exercises the core domain
headlessly and emits a JSON report.

This module does NOT import Qt at module scope so that pure-domain CLI
invocations don't pay the Qt import cost.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from clipforge.core.exceptions import ClipForgeError
from clipforge.core.models import JobSpec, VideoMetadata
from clipforge.core.planner import plan_job
from clipforge.core.presets import discover_builtins, discover_user_presets

if TYPE_CHECKING:
    from clipforge.core.models import Preset


def _default_metadata() -> VideoMetadata:
    return VideoMetadata(
        duration_sec=60.0,
        width=1920,
        height=1080,
        fps=30.0,
        has_audio=True,
    )


def _find_preset(name: str, user_dir: Path | None) -> Preset:
    candidates = list(discover_builtins())
    if user_dir is not None:
        candidates.extend(discover_user_presets(user_dir))
    for p in candidates:
        if p.name == name:
            return p
    raise ClipForgeError(f"preset not found: {name!r}")


def _target_dimensions(aspect: str, metadata: VideoMetadata) -> tuple[int, int]:
    if aspect == "9:16":
        return (1080, 1920)
    if aspect == "16:9":
        return (1920, 1080)
    if aspect == "1:1":
        return (1080, 1080)
    if aspect == "4:5":
        return (1080, 1350)
    return (metadata.width, metadata.height)


def cmd_plan(args: argparse.Namespace) -> int:
    try:
        metadata = _default_metadata()
        if args.metadata_json is not None:
            text = Path(args.metadata_json).read_text(encoding="utf-8")
            metadata = VideoMetadata.model_validate_json(text)
        preset = _find_preset(args.preset, user_dir=args.user_presets_dir)
        job = JobSpec(
            source_path=Path(args.source),
            output_root=Path(args.output_root),
            slicing=preset.slicing,
            effects=preset.effects,
            output=preset.output,
            mode=preset.mode,
            seed=args.seed,
        )
        plans = plan_job(job, metadata, seed=args.seed)
    except ClipForgeError as exc:
        print(f"clipforge: {exc}", file=sys.stderr)
        return 1

    first_argv: list[str] = []
    if plans:
        from clipforge.core.filters import build_clip_args

        target = _target_dimensions(preset.output.aspect, metadata)
        first = build_clip_args(plans[0], Path(args.source), preset.output, target)
        first_argv = (
            first.input_args
            + (["-vf", first.video_filter] if first.video_filter else [])
            + (["-af", first.audio_filter] if first.audio_filter else [])
            + first.output_args
        )

    report = {
        "source": str(job.source_path),
        "preset": preset.name,
        "clip_count": len(plans),
        "total_clip_duration_sec": round(sum(p.length_sec for p in plans), 3),
        "first_clip_ffmpeg_argv": first_argv,
    }
    if args.pretty:
        print(json.dumps(report, indent=2))
    else:
        print(json.dumps(report))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clipforge")
    subparsers = parser.add_subparsers(dest="subcommand")

    plan_p = subparsers.add_parser("plan", help="produce a plan JSON report")
    plan_p.add_argument("source", help="path to source video (need not exist for M1)")
    plan_p.add_argument("preset", help="preset name (built-in or user)")
    plan_p.add_argument("--output-root", default="output", dest="output_root")
    plan_p.add_argument("--seed", type=int, default=None)
    plan_p.add_argument("--pretty", action="store_true")
    plan_p.add_argument("--metadata-json", default=None, dest="metadata_json")
    plan_p.add_argument("--user-presets-dir", default=None, type=Path, dest="user_presets_dir")
    plan_p.set_defaults(func=cmd_plan)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.subcommand is None:
        from clipforge.app import run

        return run()
    func = args.func
    return int(func(args))
