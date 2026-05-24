UI rework.

## What changed

- **Tabs instead of cards.** The header now has 4 tabs — TikTok Soft, Instagram Reels, YouTube Shorts, Custom — plus any presets you've saved. (Dropped TikTok Hard Uniq and Plain Slice from the visible tabs; their JSON files stay on disk if you want to copy them out.)
- **One window, no preset modal.** Selecting a built-in fills the config below; editing any value flips the active tab to Custom and keeps your edit.
- **All 10 effect rows are always visible.** Effects disabled by the active preset are greyed out but still shown. Toggling one back on switches to Custom.
- **Numeric inputs everywhere.** Clip-length min/max are two `seconds` spinboxes. Each effect has a `%` input next to its slider; the input is authoritative.
- **No more accidental scroll-wheel value changes.** Sliders and number inputs ignore the mouse wheel; only the log panel and the config column scroll.
- **Save current as preset…** writes a `.cfp.json` to `%APPDATA%\ClipForge\presets\`. Saved presets appear as additional tabs on next launch.
- **Footer language switcher** uses real flag PNGs (CC0 from flagcdn.com) so flags render even on Windows builds where the emoji font doesn't include regional indicators.
- **Larger default window** (1280×900) and a scrollable config column so nothing gets cut off at default resolution.
- **Combos now show their text** — forced Fusion style + 2×2 layout for output controls so they have room for "H.264 (libx264)" etc.
- **Drop bar collapses** to filename + path + Change… once a video is loaded.

## Fixes carried over from v1.0.2

Bundled ffmpeg subprocess runs with a cleaned environment and `CREATE_NO_WINDOW` — no more `STATUS_DLL_INIT_FAILED` (`0xC0000142`), no flashing CMD windows.

## Install

Download `ClipForgeSetup.exe`, double-click. SmartScreen will warn (unsigned) → *More info → Run anyway*. Installs per-user under `%LOCALAPPDATA%\Programs\ClipForge\`.
