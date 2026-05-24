# ClipForge

Desktop app that slices long-form video into short clips and applies configurable per-clip effects to defeat duplicate-detection systems on short-form video platforms.

> **Status:** In active development. See [`docs/superpowers/specs/`](docs/superpowers/specs/) for the current milestone plans.

## Prerequisites

- Windows 10/11 (primary target). macOS/Linux are best-effort.
- `uv` — install via `irm https://astral.sh/uv/install.ps1 | iex` (Windows) or `curl -LsSf https://astral.sh/uv/install.sh | sh` (macOS/Linux). `uv` installs Python 3.12 automatically.

## Quick start

```powershell
# 1. Install dependencies (downloads Python 3.12 if missing)
uv sync --dev

# 2. Download bundled FFmpeg (one-time, idempotent)
uv run python scripts/fetch_ffmpeg.py

# 3. Run the app
uv run python -m clipforge
```

A dark-themed empty window should appear. (Real UI lands in later milestones.)

## Development

```powershell
uv run pytest                      # tests
uv run ruff check .                # lint
uv run ruff format --check .       # format check
uv run mypy src/clipforge          # type check
uv run pre-commit install          # one-time: enable git hooks
```

## Project layout

```
src/clipforge/      # application package
resources/          # bundled assets (fonts, themes, presets, ffmpeg)
scripts/            # build & maintenance scripts
tests/              # pytest suite
docs/               # specs, plans, qa
```

## License

MIT — see [`LICENSE`](LICENSE). FFmpeg is bundled separately under its own license.
