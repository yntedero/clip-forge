"""Module entry point: ``python -m clipforge``."""

from __future__ import annotations

from clipforge.app import run


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
