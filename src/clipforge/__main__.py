"""Module entry point: ``python -m clipforge`` (with optional subcommand)."""

from __future__ import annotations

from clipforge.cli import main


def main_entry() -> int:
    return main()


if __name__ == "__main__":
    raise SystemExit(main_entry())
