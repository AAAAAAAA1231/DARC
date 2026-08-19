# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ("shigongtu/static", "shigongtu/static"),
    ("shigongtu/resources", "shigongtu/resources"),
]
binaries = []
hiddenimports = collect_submodules("shigongtu") + [
    "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    "h11", "httptools", "anyio", "starlette", "fastapi", "pydantic",
    "ezdxf", "ezdxf.addons",
]
for pkg in ("uvicorn", "starlette", "fastapi", "anyio", "ezdxf"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(["run.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hiddenimports, excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="ShiGongTu", debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=True)
