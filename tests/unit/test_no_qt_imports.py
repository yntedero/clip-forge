"""Static boundary enforcement: clipforge.core must not import Qt."""

from __future__ import annotations

import ast
from pathlib import Path

_CORE_DIR = Path(__file__).resolve().parents[1].parent / "src" / "clipforge" / "core"
_CLI_PATH = _CORE_DIR.parent / "cli.py"

_FORBIDDEN = ("PySide6", "qtawesome", "clipforge.gui", "clipforge.app")


def _imports_of(path: Path, *, top_level_only: bool = False) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    nodes = tree.body if top_level_only else ast.walk(tree)
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_core_does_not_import_qt() -> None:
    for py_file in _CORE_DIR.rglob("*.py"):
        for imp in _imports_of(py_file):
            for forbidden in _FORBIDDEN:
                assert not imp.startswith(forbidden), f"{py_file} imports forbidden {imp!r}"


def test_cli_does_not_import_qt_at_module_level() -> None:
    """cli.py may import core but not Qt/app at the top level.

    The ``app.run`` path is only triggered when no subcommand is given;
    the import for it must be lazy.
    """
    for imp in _imports_of(_CLI_PATH, top_level_only=True):
        for forbidden in ("PySide6", "qtawesome", "clipforge.app"):
            assert not imp.startswith(forbidden), f"cli.py imports forbidden {imp!r} at top level"
