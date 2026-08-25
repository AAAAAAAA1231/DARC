# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("web3_radar/static", "web3_radar/static"), ("web3_radar/resources", "web3_radar/resources")]
binaries = []
hiddenimports = collect_submodules("web3_radar") + [
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
    "watchfiles",
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

for pkg in ("uvicorn", "starlette", "fastapi", "anyio"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

icns = Path("web3_radar/resources/chainradar.icns")
if sys.platform == "darwin" and icns.is_file():
    icon_file = "web3_radar/resources/chainradar.icns"
else:
    icon_file = "web3_radar/resources/chainradar.ico"

a = Analysis(
    ["run.py"],
    pathex=["."],
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
    name="ChainRadar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=sys.platform != "darwin",
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
    version="version_info.txt" if sys.platform == "win32" else None,
    uac_admin=False,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="ChainRadar.app",
        icon=icon_file,
        bundle_identifier="com.chainradar.app",
        info_plist={
            "CFBundleName": "链上雷达",
            "CFBundleDisplayName": "链上雷达",
            "CFBundleShortVersionString": "1.2.3",
            "CFBundleVersion": "1.2.3",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
        },
    )
