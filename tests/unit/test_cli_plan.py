"""Tests for the CLI 'plan' subcommand."""

from __future__ import annotations

import json
import subprocess
import sys


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "clipforge", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_plan_basic_runs() -> None:
    result = _run_cli("plan", "source.mp4", "TikTok Soft", "--seed", "42")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["preset"] == "TikTok Soft"
    assert data["clip_count"] > 0
    assert "first_clip_ffmpeg_argv" in data


def test_plan_deterministic_with_seed() -> None:
    a = _run_cli("plan", "source.mp4", "TikTok Soft", "--seed", "7")
    b = _run_cli("plan", "source.mp4", "TikTok Soft", "--seed", "7")
    assert a.stdout == b.stdout


def test_plan_unknown_preset_fails() -> None:
    result = _run_cli("plan", "source.mp4", "Nonexistent Preset")
    assert result.returncode != 0
    assert "not found" in result.stderr.lower() or "unknown" in result.stderr.lower()


def test_plan_pretty_flag_multiline() -> None:
    result = _run_cli("plan", "source.mp4", "TikTok Soft", "--seed", "1", "--pretty")
    assert result.returncode == 0
    assert "\n" in result.stdout.rstrip()
