"""Minimal ffprobe wrapper.

Reads basic video metadata via a synchronous ``subprocess`` call to the
bundled ffprobe. Returns a :class:`VideoMetadata` object.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from clipforge.core.exceptions import ClipForgeError
from clipforge.core.models import VideoMetadata
from clipforge.infra.paths import ffprobe_path


class ProbeError(ClipForgeError):
    """ffprobe failed or returned unexpected output."""


def probe(source: Path) -> VideoMetadata:
    """Run ffprobe on ``source`` and return :class:`VideoMetadata`."""
    if not source.is_file():
        raise ProbeError(f"file not found: {source}")
    binary = ffprobe_path()
    if not binary.is_file():
        raise ProbeError(f"ffprobe binary missing at {binary} — run scripts/fetch_ffmpeg.py")
    args = [
        str(binary),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(source),
    ]
    from clipforge.infra.ffmpeg import _subprocess_kwargs

    try:
        result = subprocess.run(  # type: ignore[call-overload]
            args,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            **_subprocess_kwargs(),
        )
    except subprocess.CalledProcessError as exc:
        raise ProbeError(f"ffprobe failed (exit {exc.returncode}): {exc.stderr.strip()}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("ffprobe timed out") from exc

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"ffprobe output not JSON: {exc}") from exc

    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        None,
    )
    if video_stream is None:
        raise ProbeError(f"no video stream in {source}")

    duration_str = data.get("format", {}).get("duration") or video_stream.get("duration")
    if duration_str is None:
        raise ProbeError(f"no duration reported for {source}")
    try:
        duration_sec = float(duration_str)
    except ValueError as exc:
        raise ProbeError(f"bad duration: {duration_str!r}") from exc

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    if width <= 0 or height <= 0:
        raise ProbeError(f"bad dimensions: {width}x{height}")

    fps_str = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate", "0/1")
    fps = _parse_rate(fps_str)

    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))

    return VideoMetadata(
        duration_sec=duration_sec,
        width=width,
        height=height,
        fps=fps,
        has_audio=has_audio,
    )


def _parse_rate(rate: str) -> float:
    if "/" in rate:
        num_str, den_str = rate.split("/", 1)
        try:
            num = float(num_str)
            den = float(den_str)
        except ValueError:
            return 30.0
        if den == 0.0:
            return 30.0
        return num / den
    try:
        return float(rate)
    except ValueError:
        return 30.0
