# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for AShareQuant.exe (Windows) / one-file desktop app."""

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

SPECDIR = Path(SPECPATH).resolve()
ROOT = SPECDIR  # spec lives in ashare-quant/

datas = [
    (str(ROOT / "config" / "default.yaml"), "config"),
    (str(ROOT / "src" / "ashare_quant" / "resources" / "default.yaml"), "ashare_quant/resources"),
    (str(ROOT / "src" / "ashare_quant" / "web" / "templates"), "ashare_quant/web/templates"),
    (str(ROOT / "src" / "ashare_quant" / "web" / "static"), "ashare_quant/web/static"),
]
binaries = []
hiddenimports = collect_submodules("ashare_quant") + collect_submodules("uvicorn")
hiddenimports += [
    "tkinter",
    "matplotlib.backends.backend_agg",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
]

for pkg in ("ashare_quant", "uvicorn", "fastapi", "starlette", "matplotlib", "scipy", "pandas", "pydantic", "yaml", "jinja2"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
