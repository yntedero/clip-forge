# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ClipForge.

Builds a one-folder bundle at ``dist/ClipForge/`` containing ClipForge.exe
plus its dependencies and resources. Inno Setup wraps this folder into a
single ClipForgeSetup.exe.
"""

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 (SPECPATH provided by PyInstaller)

datas = [
    (str(ROOT / "resources" / "themes"), "resources/themes"),
    (str(ROOT / "resources" / "presets"), "resources/presets"),
    (str(ROOT / "resources" / "ffmpeg"), "resources/ffmpeg"),
    (str(ROOT / "resources" / "icons"), "resources/icons"),
]

block_cipher = None

a = Analysis(  # noqa: F821
    [str(ROOT / "src" / "clipforge" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "clipforge",
        "clipforge.app",
        "clipforge.cli",
        "clipforge.core",
        "clipforge.core.effects",
        "clipforge.core.filters",
        "clipforge.core.models",
        "clipforge.core.planner",
        "clipforge.core.presets",
        "clipforge.infra",
        "clipforge.infra.ffmpeg",
        "clipforge.infra.ffprobe",
        "clipforge.infra.paths",
        "clipforge.job_runner",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PIL",
        "numpy",
        "matplotlib",
        "scipy",
        "pandas",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ClipForge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "resources" / "icons" / "app.ico"),
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ClipForge",
)
