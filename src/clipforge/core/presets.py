"""Preset load/save and built-in discovery."""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Final

from pydantic import ValidationError as _PydanticValidationError

from clipforge.core.exceptions import PresetError
from clipforge.core.models import Preset

CURRENT_SCHEMA_VERSION: Final[int] = 1

BUILTIN_PRESET_NAMES: Final[tuple[str, ...]] = (
    "TikTok Soft",
    "TikTok Hard Uniq",
    "YouTube Shorts",
    "Instagram Reels",
    "Plain Slice",
)


def _resolve_resources_dir(subdir: str) -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        path = Path(meipass) / "resources" / subdir
        if path.is_dir():
            return path
    return Path(__file__).resolve().parents[3] / "resources" / subdir


def load_preset_from_json(text: str) -> Preset:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PresetError(f"malformed JSON: {exc}") from exc
    version = data.get("schema_version", 1)
    if not isinstance(version, int) or version < 1 or version > CURRENT_SCHEMA_VERSION:
        raise PresetError(f"unsupported schema_version: {version!r}")
    try:
        return Preset.model_validate(data)
    except _PydanticValidationError as exc:
        raise PresetError(f"invalid preset: {exc}") from exc


def load_preset_from_file(path: Path) -> Preset:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PresetError(f"cannot read preset {path}: {exc}") from exc
    return load_preset_from_json(text)


def save_preset_to_file(preset: Preset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = preset.model_dump_json(indent=2)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.write("\n")
        os.replace(tmp_name, path)
    except OSError as exc:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise PresetError(f"cannot write preset {path}: {exc}") from exc


def discover_builtins() -> list[Preset]:
    directory = _resolve_resources_dir("presets")
    presets: list[Preset] = []
    for json_path in sorted(directory.glob("*.json")):
        p = load_preset_from_file(json_path)
        if not p.builtin:
            raise PresetError(f"{json_path} loaded but builtin flag is False")
        presets.append(p)
    return presets


def discover_user_presets(presets_dir: Path) -> list[Preset]:
    if not presets_dir.is_dir():
        return []
    presets: list[Preset] = []
    for json_path in sorted(presets_dir.glob("*.cfp.json")):
        presets.append(load_preset_from_file(json_path))
    return presets
