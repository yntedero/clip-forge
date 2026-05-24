"""Unit tests for ``scripts/fetch_ffmpeg.py``.

The script is tested by importing it directly from its file path so it
does not need to be a package member.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "fetch_ffmpeg.py"


def _load_fetch_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fetch_ffmpeg", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["fetch_ffmpeg"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fetch_mod() -> ModuleType:
    return _load_fetch_module()


def test_constants_present(fetch_mod: ModuleType) -> None:
    assert isinstance(fetch_mod.FFMPEG_VERSION, str)
    assert "." in fetch_mod.FFMPEG_VERSION
    assert isinstance(fetch_mod.SOURCES, dict)
    assert "windows" in fetch_mod.SOURCES


def test_sha256_of_file(fetch_mod: ModuleType, tmp_path: Path) -> None:
    file = tmp_path / "blob.bin"
    file.write_bytes(b"hello clipforge")
    expected = hashlib.sha256(b"hello clipforge").hexdigest()
    assert fetch_mod.sha256_of_file(file) == expected


def test_extract_zip_picks_ffmpeg_and_ffprobe(fetch_mod: ModuleType, tmp_path: Path) -> None:
    archive = tmp_path / "ffmpeg.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("ffmpeg-7.1.1/bin/ffmpeg.exe", b"FFMPEG_BINARY")
        zf.writestr("ffmpeg-7.1.1/bin/ffprobe.exe", b"FFPROBE_BINARY")
        zf.writestr("ffmpeg-7.1.1/README.txt", b"unrelated")

    out_dir = tmp_path / "ffmpeg_out"
    fetch_mod.extract_archive(archive, out_dir, platform="windows")

    assert (out_dir / "ffmpeg.exe").read_bytes() == b"FFMPEG_BINARY"
    assert (out_dir / "ffprobe.exe").read_bytes() == b"FFPROBE_BINARY"
    assert not (out_dir / "README.txt").exists()


def test_extract_missing_binary_raises(fetch_mod: ModuleType, tmp_path: Path) -> None:
    archive = tmp_path / "ffmpeg.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("ffmpeg-7.1.1/bin/ffmpeg.exe", b"FFMPEG_BINARY")
        # ffprobe missing

    out_dir = tmp_path / "ffmpeg_out"
    with pytest.raises(fetch_mod.FetchError, match="ffprobe"):
        fetch_mod.extract_archive(archive, out_dir, platform="windows")


def test_main_idempotent_when_binaries_present(
    fetch_mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir = tmp_path / "ffmpeg"
    out_dir.mkdir()
    (out_dir / "ffmpeg.exe").write_bytes(b"existing")
    (out_dir / "ffprobe.exe").write_bytes(b"existing")

    called: dict[str, bool] = {"downloaded": False}

    def _fake_download(url: str, dest: Path) -> None:
        called["downloaded"] = True

    monkeypatch.setattr(fetch_mod, "download", _fake_download)

    exit_code = fetch_mod.main(["--platform", "windows", "--out-dir", str(out_dir)])

    assert exit_code == 0
    assert called["downloaded"] is False


def test_main_force_redownloads(
    fetch_mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir = tmp_path / "ffmpeg"
    out_dir.mkdir()
    (out_dir / "ffmpeg.exe").write_bytes(b"old")
    (out_dir / "ffprobe.exe").write_bytes(b"old")

    def _fake_download(url: str, dest: Path) -> None:
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr("ffmpeg-7.1.1/bin/ffmpeg.exe", b"FRESH_FFMPEG")
            zf.writestr("ffmpeg-7.1.1/bin/ffprobe.exe", b"FRESH_FFPROBE")

    def _fake_verify(path: Path, expected: str) -> None:
        return None

    monkeypatch.setattr(fetch_mod, "download", _fake_download)
    monkeypatch.setattr(fetch_mod, "verify_sha256", _fake_verify)

    exit_code = fetch_mod.main(["--platform", "windows", "--out-dir", str(out_dir), "--force"])

    assert exit_code == 0
    assert (out_dir / "ffmpeg.exe").read_bytes() == b"FRESH_FFMPEG"
    assert (out_dir / "ffprobe.exe").read_bytes() == b"FRESH_FFPROBE"


def test_verify_sha256_mismatch_raises(fetch_mod: ModuleType, tmp_path: Path) -> None:
    file = tmp_path / "blob.bin"
    file.write_bytes(b"hello")
    with pytest.raises(fetch_mod.FetchError, match="SHA-256"):
        fetch_mod.verify_sha256(file, expected="0" * 64)


def test_verify_sha256_match_passes(fetch_mod: ModuleType, tmp_path: Path) -> None:
    file = tmp_path / "blob.bin"
    file.write_bytes(b"hello")
    expected = hashlib.sha256(b"hello").hexdigest()
    fetch_mod.verify_sha256(file, expected=expected)


def test_constants_includes_all_platforms(fetch_mod: ModuleType) -> None:
    for platform in ("windows", "linux", "macos"):
        assert platform in fetch_mod.SOURCES, f"missing platform: {platform}"
        entry = fetch_mod.SOURCES[platform]
        for key in (
            "url",
            "sha256",
            "archive_type",
            "ffmpeg_member_suffix",
            "ffprobe_member_suffix",
            "out_ffmpeg",
            "out_ffprobe",
        ):
            assert key in entry, f"{platform} missing key: {key}"


def test_detect_platform_windows(fetch_mod: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch_mod.sys, "platform", "win32")
    assert fetch_mod.detect_platform() == "windows"


def test_detect_platform_macos(fetch_mod: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch_mod.sys, "platform", "darwin")
    assert fetch_mod.detect_platform() == "macos"


def test_detect_platform_linux(fetch_mod: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch_mod.sys, "platform", "linux")
    assert fetch_mod.detect_platform() == "linux"


def test_detect_platform_unknown_raises(
    fetch_mod: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch_mod.sys, "platform", "haiku")
    with pytest.raises(fetch_mod.FetchError, match="unsupported platform"):
        fetch_mod.detect_platform()


def test_verify_sha256_placeholder_raises(fetch_mod: ModuleType, tmp_path: Path) -> None:
    file = tmp_path / "blob.bin"
    file.write_bytes(b"x")
    with pytest.raises(fetch_mod.FetchError, match="placeholder is still"):
        fetch_mod.verify_sha256(file, expected="REPLACE_WITH_ACTUAL_SHA256")


def test_extract_tar_picks_ffmpeg_and_ffprobe(fetch_mod: ModuleType, tmp_path: Path) -> None:
    import io
    import tarfile

    archive = tmp_path / "ffmpeg.tar.xz"
    with tarfile.open(archive, "w:xz") as tf:
        for name, data in (
            ("ffmpeg-7.1.1/ffmpeg", b"FFMPEG_BINARY"),
            ("ffmpeg-7.1.1/ffprobe", b"FFPROBE_BINARY"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

    out_dir = tmp_path / "ffmpeg_out"
    fetch_mod.extract_archive(archive, out_dir, platform="linux")

    assert (out_dir / "ffmpeg").read_bytes() == b"FFMPEG_BINARY"
    assert (out_dir / "ffprobe").read_bytes() == b"FFPROBE_BINARY"


def test_extract_zip_corrupt_raises(fetch_mod: ModuleType, tmp_path: Path) -> None:
    archive = tmp_path / "corrupt.zip"
    archive.write_bytes(b"this is not a zip file")
    out_dir = tmp_path / "out"
    with pytest.raises(fetch_mod.FetchError, match="corrupt zip"):
        fetch_mod.extract_archive(archive, out_dir, platform="windows")


def test_main_detect_platform_failure_returns_2(
    fetch_mod: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(fetch_mod.sys, "platform", "haiku")
    exit_code = fetch_mod.main(["--out-dir", str(tmp_path / "out")])
    assert exit_code == 2
