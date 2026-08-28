# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = collect_submodules("market_advisor") + collect_submodules("tzdata")
hiddenimports += ["numpy", "tkinter", "zoneinfo", "tzdata"]

a = Analysis(
    ["../src/market_advisor/__main__.py"],
    pathex=["../src"],
    binaries=[],
    datas=collect_data_files("tzdata"),
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pandas", "matplotlib", "scipy"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="OpenAdvisor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
)
