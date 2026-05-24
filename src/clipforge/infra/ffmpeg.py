"""FFmpeg process runner — drives one clip at a time via ``QProcess``.

Minimal M2-ish wrapper sufficient for the v1.0.1 release. Full progress
parsing, hardware encoder probes, and concurrent dispatch land later.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from clipforge.core.exceptions import ClipForgeError
from clipforge.infra.paths import ffmpeg_path


class FFmpegRunError(ClipForgeError):
    """FFmpeg exited non-zero on a clip."""


class FFmpegProcess(QObject):
    """Wrapper around a single FFmpeg invocation."""

    finished = Signal(int)  # exit code
    error = Signal(str)
    progress = Signal(float)  # 0.0 .. 1.0 (best-effort, may stay at 0)

    def __init__(
        self,
        argv: list[str],
        expected_duration_sec: float,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._argv = argv
        self._expected_duration_sec = max(0.001, expected_duration_sec)
        self._stderr_buffer = bytearray()
        self._proc = QProcess(self)
        self._proc.setProgram(str(ffmpeg_path()))
        self._proc.setArguments(argv)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._on_stdout)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_proc_error)

    def start(self) -> None:
        self._proc.start()

    def cancel(self) -> None:
        if self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.terminate()
            if not self._proc.waitForFinished(2000):
                self._proc.kill()

    def stderr_tail(self) -> str:
        return self._stderr_buffer.decode("utf-8", errors="replace")[-2000:]

    def _on_stdout(self) -> None:
        raw = self._proc.readAllStandardOutput()
        data: bytes = raw.data() if hasattr(raw, "data") else b""  # type: ignore[assignment]
        if not data:
            return
        self._stderr_buffer.extend(data)
        # Parse -progress key=value lines for out_time_ms
        for line in data.splitlines():
            text = line.decode("utf-8", errors="replace").strip()
            if text.startswith("out_time_ms=") or text.startswith("out_time_us="):
                try:
                    value = int(text.split("=", 1)[1])
                except ValueError:
                    continue
                seconds = value / 1_000_000.0
                fraction = min(1.0, max(0.0, seconds / self._expected_duration_sec))
                self.progress.emit(fraction)

    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if exit_code != 0:
            self.error.emit(self.stderr_tail())
        self.finished.emit(exit_code)

    def _on_proc_error(self, _err: QProcess.ProcessError) -> None:
        self.error.emit(self._proc.errorString())


def build_clip_argv(
    input_args: list[str],
    video_filter: str | None,
    audio_filter: str | None,
    output_args: list[str],
) -> list[str]:
    """Assemble a flat argv list for ``FFmpegProcess``."""
    argv: list[str] = ["-y", *input_args]
    if video_filter:
        argv.extend(["-vf", video_filter])
    if audio_filter:
        argv.extend(["-af", audio_filter])
    argv.extend(["-progress", "pipe:1"])
    argv.extend(output_args)
    return argv


def run_clip_blocking(
    input_args: list[str],
    video_filter: str | None,
    audio_filter: str | None,
    output_args: list[str],
    on_progress: Callable[[float], None] | None = None,
    timeout_sec: int = 600,
) -> Path:
    """Run a single FFmpeg invocation synchronously (no Qt event loop).

    Used by tests / CLI smoke. Returns the output path on success;
    raises :class:`FFmpegRunError` on failure.
    """
    import subprocess  # local import — keep top namespace clean

    argv = [
        str(ffmpeg_path()),
        *build_clip_argv(input_args, video_filter, audio_filter, output_args),
    ]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_sec, check=False)
    if proc.returncode != 0:
        raise FFmpegRunError(f"ffmpeg exit {proc.returncode}: {proc.stderr[-2000:]}")
    output_path = Path(output_args[-1])
    if on_progress is not None:
        on_progress(1.0)
    return output_path
