First user-installable release of ClipForge.

## What's in this release

- **ClipForgeSetup.exe** — Windows installer (~80 MB, all bundled). Double-click to install. No admin required; installs per-user under `%LOCALAPPDATA%\Programs\ClipForge\`.
- Functional desktop UI: drop a video, pick a preset, click Start, get clips.
- 5 built-in presets: TikTok Soft, TikTok Hard Uniq, YouTube Shorts, Instagram Reels, Plain Slice.
- FFmpeg 7.1.1 bundled; no separate install needed.

## How to install

1. Download `ClipForgeSetup.exe` from the assets below.
2. Run it. Windows SmartScreen may warn (the installer is unsigned for v1.0.1) — click *More info* → *Run anyway*.
3. ClipForge appears in your Start Menu. Launch it, drop a video, pick a preset, hit Start. Your clips appear in `~/ClipForge Output/`.

## Status

This is the foundational release. Core domain (slicer, effects resolver, filter builder, preset loader) is fully tested (100 unit tests, 90%+ branch coverage on core modules). The UI is functional but minimal — full Neon Cut theming, preview dialog, settings dialog, and batch processing arrive in later releases.
