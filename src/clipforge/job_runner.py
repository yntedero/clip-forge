"""Job runner — orchestrates planning + per-clip FFmpeg execution.

Lives in the application layer (top of the stack). Imports core + infra.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from clipforge.core.filters import build_clip_args
from clipforge.core.models import JobSpec, VideoMetadata
from clipforge.core.planner import plan_job
from clipforge.infra.ffmpeg import run_clip_blocking
from clipforge.infra.ffprobe import probe


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


class JobRunner(QObject):
    """Runs a job on a background thread, emitting progress and per-clip events."""

    progress = Signal(int, int)  # done, total
    clip_finished = Signal(str)  # output path
    job_finished = Signal()
    job_failed = Signal(str)  # error message
    log = Signal(str)  # human-readable log lines

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cancelled = False
        self._thread: QThread | None = None

    def cancel(self) -> None:
        self._cancelled = True

    def run_async(self, job: JobSpec) -> None:
        """Spawn a worker thread to run the job."""
        self._cancelled = False

        worker = _JobWorker(job)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.progress)
        worker.clip_finished.connect(self.clip_finished)
        worker.log.connect(self.log)
        worker.job_finished.connect(self._on_finished)
        worker.job_failed.connect(self._on_failed)
        worker.job_finished.connect(thread.quit)
        worker.job_failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _on_finished(self) -> None:
        self.job_finished.emit()

    def _on_failed(self, msg: str) -> None:
        self.job_failed.emit(msg)


class _JobWorker(QObject):
    """Worker that runs the job synchronously in its own thread."""

    progress = Signal(int, int)
    clip_finished = Signal(str)
    log = Signal(str)
    job_finished = Signal()
    job_failed = Signal(str)

    def __init__(self, job: JobSpec) -> None:
        super().__init__()
        self._job = job

    def run(self) -> None:
        try:
            self._run_impl()
        except Exception as exc:
            self.job_failed.emit(str(exc))

    def _run_impl(self) -> None:
        job = self._job
        self.log.emit(f"Probing {job.source_path}…")
        metadata = probe(job.source_path)
        self.log.emit(
            f"Source: {metadata.width}x{metadata.height}, "
            f"{metadata.duration_sec:.1f}s, "
            f"{'audio' if metadata.has_audio else 'no audio'}"
        )
        plans = plan_job(job, metadata, seed=job.seed)
        total = len(plans)
        self.log.emit(f"Planned {total} clips.")
        if total == 0:
            self.job_failed.emit("No clips planned — source too short or skip values too large.")
            return

        target = _target_dimensions(job.output.aspect, metadata)
        output_dir = plans[0].output_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        for i, clip in enumerate(plans):
            args = build_clip_args(clip, job.source_path, job.output, target)
            try:
                self.log.emit(
                    f"Rendering clip {i + 1}/{total}: "
                    f"{clip.start_sec:.2f}s + {clip.length_sec:.2f}s"
                )
                out_path = run_clip_blocking(
                    args.input_args,
                    args.video_filter,
                    args.audio_filter,
                    args.output_args,
                )
            except Exception as exc:
                self.job_failed.emit(f"ffmpeg failed on clip {i + 1}: {exc}")
                return
            self.clip_finished.emit(str(out_path))
            self.progress.emit(i + 1, total)

        self.job_finished.emit()


def run_job_blocking(
    job: JobSpec,
    on_progress: Callable[[int, int], None] | None = None,
    on_log: Callable[[str], None] | None = None,
) -> list[Path]:
    """Synchronous job runner — used by tests and CLI smoke."""
    if on_log:
        on_log(f"Probing {job.source_path}…")
    metadata = probe(job.source_path)
    plans = plan_job(job, metadata, seed=job.seed)
    total = len(plans)
    if on_log:
        on_log(f"Planned {total} clips.")
    if total == 0:
        raise RuntimeError("no clips planned")

    target = _target_dimensions(job.output.aspect, metadata)
    output_dir = plans[0].output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    for i, clip in enumerate(plans):
        args = build_clip_args(clip, job.source_path, job.output, target)
        if on_log:
            on_log(
                f"Rendering clip {i + 1}/{total}: {clip.start_sec:.2f}s + {clip.length_sec:.2f}s"
            )
        out = run_clip_blocking(
            args.input_args, args.video_filter, args.audio_filter, args.output_args
        )
        outputs.append(out)
        if on_progress:
            on_progress(i + 1, total)
    return outputs
