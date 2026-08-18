# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ("hub/static", "hub/static"),
    ("qingbiao/static", "qingbiao/static"),
    ("qingbiao/resources", "qingbiao/resources"),
    ("anquan/static", "anquan/static"),
    ("anquan/resources", "anquan/resources"),
    ("jindu/static", "jindu/static"),
    ("jindu/resources", "jindu/resources"),
    ("zhiliang/static", "zhiliang/static"),
    ("zhiliang/resources", "zhiliang/resources"),
    ("chengben/static", "chengben/static"),
    ("chengben/resources", "chengben/resources"),
    ("jishubiao/static", "jishubiao/static"),
    ("jishubiao/resources", "jishubiao/resources"),
]
binaries = []
hiddenimports = (
    collect_submodules("hub")
    + collect_submodules("qingbiao")
    + collect_submodules("anquan")
    + collect_submodules("jindu")
    + collect_submodules("zhiliang")
    + collect_submodules("chengben")
    + collect_submodules("jishubiao")
    + [
        "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
        "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
        "uvicorn.lifespan", "uvicorn.lifespan.on",
        "h11", "httptools", "anyio", "starlette", "fastapi", "pydantic",
        "openpyxl", "docx", "lxml", "lxml.etree", "ezdxf", "pypdf", "olefile",
        "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
    ]
)
for pkg in ("uvicorn", "starlette", "fastapi", "anyio", "openpyxl", "docx", "lxml", "ezdxf", "PIL"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(["run.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hiddenimports, excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="GongCheng", debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=True)
