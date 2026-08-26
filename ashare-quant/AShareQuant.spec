# -*- mode: python ; coding: utf-8 -*-
"""Slim one-file Windows EXE: keep under upload limits, still double-clickable."""

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

SPECDIR = Path(SPECPATH).resolve()
ROOT = SPECDIR

datas = [
    (str(ROOT / "config" / "default.yaml"), "config"),
    (str(ROOT / "src" / "ashare_quant" / "resources" / "default.yaml"), "ashare_quant/resources"),
    (str(ROOT / "src" / "ashare_quant" / "web" / "templates"), "ashare_quant/web/templates"),
    (str(ROOT / "src" / "ashare_quant" / "web" / "static"), "ashare_quant/web/static"),
]

hiddenimports = collect_submodules("ashare_quant") + collect_submodules("uvicorn")
hiddenimports += [
    "tkinter",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "pandas",
    "numpy",
    "yaml",
    "pydantic",
    "jinja2",
    "fastapi",
    "starlette",
    "dateutil",
    "anyio",
    "h11",
    "sniffio",
    "click",
]

# matplotlib/scipy are optional for charts; excluding them is what makes the EXE attachable.
excludes = [
    "matplotlib",
    "scipy",
    "PIL",
    "Pillow",
    "pytest",
    "IPython",
    "notebook",
    "jupyter",
]

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AShareQuant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
