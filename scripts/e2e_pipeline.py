"""End-to-end pipeline smoke test.

Runs the full ClipForge job pipeline (probe → plan → render) against the
local test video at ``test-video/test-video.mp4`` and reports how many
clips were produced.

Usage:
    uv run python scripts/e2e_pipeline.py [preset_name] [output_root]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from clipforge.core.models import JobSpec
from clipforge.core.presets import discover_builtins
from clipforge.job_runner import run_job_blocking

ROOT = Path(__file__).resolve().parents[1]
TEST_VIDEO = ROOT / "test-video" / "test-video.mp4"


def main() -> int:
    if not TEST_VIDEO.is_file():
        print(f"missing test video: {TEST_VIDEO}", file=sys.stderr)
        return 2
    preset_name = sys.argv[1] if len(sys.argv) > 1 else "Plain Slice"
    out_root = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "e2e-output"
    out_root.mkdir(parents=True, exist_ok=True)

    presets = {p.name: p for p in discover_builtins()}
    if preset_name not in presets:
        print(
            f"unknown preset: {preset_name!r}. Choices: {sorted(presets)}",
            file=sys.stderr,
        )
        return 2
    preset = presets[preset_name]

    job = JobSpec(
        source_path=TEST_VIDEO,
        output_root=out_root,
        slicing=preset.slicing,
        effects=preset.effects,
        output=preset.output,
        mode=preset.mode,
        seed=42,
    )

    print(f"Pipeline: {TEST_VIDEO.name} -> {out_root}/  with '{preset.name}'")
    start = time.monotonic()

    def on_progress(done: int, total: int) -> None:
        print(f"  progress: {done}/{total}")

    def on_log(line: str) -> None:
        print(f"  {line}")

    outputs = run_job_blocking(job, on_progress=on_progress, on_log=on_log)

    elapsed = time.monotonic() - start
    print(f"Done in {elapsed:.1f}s — {len(outputs)} clip(s) produced.")
    for p in outputs[:5]:
        print(f"  {p} ({p.stat().st_size} bytes)")
    if len(outputs) > 5:
        print(f"  ... and {len(outputs) - 5} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
