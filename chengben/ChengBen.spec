# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ("chengben/static", "chengben/static"),
    ("chengben/resources", "chengben/resources"),
]
binaries = []
hiddenimports = collect_submodules("chengben") + [
    "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    "h11", "httptools", "anyio", "starlette", "fastapi", "pydantic",
    "openpyxl",
]
for pkg in ("uvicorn", "starlette", "fastapi", "anyio", "openpyxl"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(["run.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hiddenimports, excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="ChengBen", debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=True)
