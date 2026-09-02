# PyInstaller spec — run from Crypto-AI-Master-Intelligence/
# Output: dist/Crypto-AI-Master-Intelligence.exe (onefile)

from __future__ import annotations

from PyInstaller.building.build_main import EXE, PYZ, Analysis
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

datas = [
    ("frontend/dist", "frontend/dist"),
    ("config", "config"),
    (".env.example", "."),
]
binaries = []
hiddenimports = [
    "backend.main",
    "backend.desktop_app",
    "backend.services.dashboard",
    "backend.data_sources.onchain",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "webview.platforms.mshtml",
]

for pkg in (
    "uvicorn",
    "starlette",
    "anyio",
    "fastapi",
    "sklearn",
    "numpy",
    "pandas",
    "scipy",
    "sqlalchemy",
    "pydantic",
    "pydantic_settings",
    "httpx",
    "yaml",
    "apscheduler",
    "webview",
    "dateutil",
):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        hiddenimports += collect_submodules(pkg)

for pkg in ("xgboost", "lightgbm", "numba"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    ["backend/desktop_app.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Crypto-AI-Master-Intelligence",
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
