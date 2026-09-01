# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

SPECDIR = os.path.abspath(SPECPATH)
ROOT = os.path.abspath(os.path.join(SPECDIR, ".."))

datas = [
    (os.path.join(SPECDIR, "suite", "static"), os.path.join("suite", "static")),
    (os.path.join(ROOT, "web3-radar", "web3_radar", "static"), os.path.join("web3_radar", "static")),
    (os.path.join(ROOT, "web3-radar", "web3_radar", "resources"), os.path.join("web3_radar", "resources")),
]
binaries = []
hiddenimports = (
    collect_submodules("suite")
    + collect_submodules("radar")
    + collect_submodules("football_predictor")
    + collect_submodules("web3_radar")
    + [
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "h11",
        "httptools",
        "anyio",
        "anyio._backends._asyncio",
        "starlette",
        "fastapi",
        "pydantic",
        "numpy",
        "pandas",
        "httpx",
        "certifi",
        "aiosqlite",
    ]
)

for pkg in ("uvicorn", "starlette", "fastapi", "anyio"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [os.path.join(SPECDIR, "desk_suite.py")],
    pathex=[
        SPECDIR,
        os.path.join(ROOT, "fiftyx-radar"),
        os.path.join(ROOT, "football-predictor"),
        os.path.join(ROOT, "web3-radar"),
    ],
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
    name="GongZuoTai",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
