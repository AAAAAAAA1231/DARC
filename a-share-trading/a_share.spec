# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hidden = [
    "a_share_trading",
    "a_share_trading.desktop",
    "a_share_trading.webapp",
    "a_share_trading.config",
    "a_share_trading.method_catalog",
    "a_share_trading.markets",
]
hidden += collect_submodules("uvicorn")
hidden += collect_submodules("fastapi")
hidden += collect_submodules("starlette")
hidden += [
    "pydantic",
    "pydantic_core",
    "annotated_types",
    "typing_inspection",
    "anyio",
    "anyio._backends._asyncio",
    "h11",
    "click",
    "colorama",
    "idna",
    "sniffio",
    "jinja2",
    "markupsafe",
]

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("web", "web"),
        ("data/universe.json", "data"),
        ("data/calibration.json", "data"),
        ("data/predictions.json", "data"),
    ],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["numba", "numpy", "pandas", "pytest", "matplotlib", "scipy", "IPython", "pip"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="大A量化研判系统",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
