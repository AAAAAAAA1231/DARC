# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ("qingbiao/static", "qingbiao/static"),
    ("qingbiao/resources", "qingbiao/resources"),
]
binaries = []
hiddenimports = collect_submodules("qingbiao") + [
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
    "openpyxl",
    "docx",
    "lxml",
    "lxml.etree",
    "pypdf",
    "olefile",
    "httpx",
    "certifi",
    "python_multipart",
    "multipart",
]

for pkg in ("uvicorn", "starlette", "fastapi", "anyio", "docx", "openpyxl", "lxml"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

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
    name="QingBiao",
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
