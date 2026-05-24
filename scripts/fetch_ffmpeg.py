"""Download and unpack a pinned FFmpeg static build.

Runs standalone with stdlib only so it can be invoked both as
``uv run python scripts/fetch_ffmpeg.py`` and in CI before the project is
installable.

Verifies the download against a pinned SHA-256 to catch upstream changes.
Idempotent: if the binaries already exist and ``--force`` is not set, exits
with no action.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Final

FFMPEG_VERSION: Final[str] = "7.1.1"

SOURCES: Final[dict[str, dict[str, str]]] = {
    "windows": {
        "url": (
            "https://github.com/GyanD/codexffmpeg/releases/download/"
            f"{FFMPEG_VERSION}/ffmpeg-{FFMPEG_VERSION}-essentials_build.zip"
        ),
        "sha256": "04861d3339c5ebe38b56c19a15cf2c0cc97f5de4fa8910e4d47e5e6404e4a2d4",
        "archive_type": "zip",
        "ffmpeg_member_suffix": "bin/ffmpeg.exe",
        "ffprobe_member_suffix": "bin/ffprobe.exe",
        "out_ffmpeg": "ffmpeg.exe",
        "out_ffprobe": "ffprobe.exe",
    },
    "linux": {
        "url": ("https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"),
        "sha256": "REPLACE_WITH_ACTUAL_SHA256",
        "archive_type": "tar",
        "ffmpeg_member_suffix": "ffmpeg",
        "ffprobe_member_suffix": "ffprobe",
        "out_ffmpeg": "ffmpeg",
        "out_ffprobe": "ffprobe",
    },
    "macos": {
        "url": "https://evermeet.cx/ffmpeg/getrelease/zip",
        "sha256": "REPLACE_WITH_ACTUAL_SHA256",
        "archive_type": "zip",
        "ffmpeg_member_suffix": "ffmpeg",
        "ffprobe_member_suffix": "ffprobe",
        "out_ffmpeg": "ffmpeg",
        "out_ffprobe": "ffprobe",
    },
}

DEFAULT_OUT_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "resources" / "ffmpeg"


class FetchError(RuntimeError):
    """Anything that goes wrong while fetching or extracting FFmpeg."""


def detect_platform() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    raise FetchError(f"unsupported platform: {sys.platform!r}")


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: Path, expected: str) -> None:
    if expected == "REPLACE_WITH_ACTUAL_SHA256":
        actual = sha256_of_file(path)
        raise FetchError(
            "SHA-256 placeholder is still in SOURCES. Re-run after updating "
            f"the entry with: {actual}"
        )
    actual = sha256_of_file(path)
    if actual.lower() != expected.lower():
        raise FetchError(f"SHA-256 mismatch for {path.name}: expected {expected}, got {actual}")


def download(url: str, dest: Path) -> None:
    """Stream ``url`` to ``dest`` using stdlib."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "clipforge-fetch-ffmpeg/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, dest.open("wb") as fh:
        shutil.copyfileobj(response, fh)


def _extract_member(archive: Path, suffix: str, out_path: Path, archive_type: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_type == "zip":
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                if member.endswith(suffix):
                    with zf.open(member) as src, out_path.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                    return
        raise FetchError(f"member ending in {suffix!r} not found in {archive}")
    if archive_type == "tar":
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                if member.name.endswith(suffix):
                    extracted = tf.extractfile(member)
                    if extracted is None:
                        raise FetchError(f"could not read {member.name} from {archive}")
                    with out_path.open("wb") as dst:
                        shutil.copyfileobj(extracted, dst)
                    out_path.chmod(0o755)
                    return
        raise FetchError(f"member ending in {suffix!r} not found in {archive}")
    raise FetchError(f"unknown archive_type: {archive_type!r}")


def extract_archive(archive: Path, out_dir: Path, platform: str) -> None:
    """Extract ffmpeg + ffprobe binaries from ``archive`` into ``out_dir``."""
    if platform not in SOURCES:
        raise FetchError(f"unknown platform: {platform!r}")
    source = SOURCES[platform]
    out_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_out = out_dir / source["out_ffmpeg"]
    ffprobe_out = out_dir / source["out_ffprobe"]

    try:
        _extract_member(
            archive,
            source["ffmpeg_member_suffix"],
            ffmpeg_out,
            source["archive_type"],
        )
    except FetchError as exc:
        raise FetchError(f"ffmpeg binary: {exc}") from exc
    try:
        _extract_member(
            archive,
            source["ffprobe_member_suffix"],
            ffprobe_out,
            source["archive_type"],
        )
    except FetchError as exc:
        raise FetchError(f"ffprobe binary: {exc}") from exc


def already_present(out_dir: Path, platform: str) -> bool:
    source = SOURCES[platform]
    return (out_dir / source["out_ffmpeg"]).exists() and (out_dir / source["out_ffprobe"]).exists()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--platform",
        choices=[*SOURCES.keys(), "auto"],
        default="auto",
        help="target platform; 'auto' detects from sys.platform",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="where to place ffmpeg/ffprobe binaries",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-download even if binaries already exist",
    )
    args = parser.parse_args(argv)

    platform = detect_platform() if args.platform == "auto" else args.platform
    out_dir: Path = args.out_dir

    if not args.force and already_present(out_dir, platform):
        print(
            f"ffmpeg + ffprobe already present in {out_dir}; skipping (use --force to redownload).",
            file=sys.stderr,
        )
        return 0

    source = SOURCES[platform]
    print(f"Downloading FFmpeg {FFMPEG_VERSION} for {platform}...", file=sys.stderr)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "ffmpeg-archive"
            download(source["url"], archive)
            verify_sha256(archive, source["sha256"])
            extract_archive(archive, out_dir, platform)
    except FetchError as exc:
        print(f"fetch_ffmpeg: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"fetch_ffmpeg: I/O error: {exc}", file=sys.stderr)
        return 3

    print(f"Installed FFmpeg binaries to {out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
