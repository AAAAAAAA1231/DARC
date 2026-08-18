from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from anquan.api import app as anquan_app
from chengben.api import app as chengben_app
from hub import __app_name__, __version__
from hub.config import DEFAULT_PORT, MODULES, STATIC_DIR, ensure_dirs
from jindu.api import app as jindu_app
from jishubiao.api import app as jishubiao_app
from qingbiao.api import app as qingbiao_app
from zhiliang.api import app as zhiliang_app

ensure_dirs()

app = FastAPI(title=__app_name__, version=__version__)
app.mount("/qingbiao", qingbiao_app)
app.mount("/anquan", anquan_app)
app.mount("/jindu", jindu_app)
app.mount("/zhiliang", zhiliang_app)
app.mount("/chengben", chengben_app)
app.mount("/jishubiao", jishubiao_app)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="hub-static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "app": __app_name__,
        "version": __version__,
        "offline": True,
        "port": DEFAULT_PORT,
        "modules": MODULES,
    }


@app.get("/qingbiao")
async def _r_qb() -> RedirectResponse:
    return RedirectResponse("/qingbiao/")


@app.get("/anquan")
async def _r_aq() -> RedirectResponse:
    return RedirectResponse("/anquan/")


@app.get("/jindu")
async def _r_jd() -> RedirectResponse:
    return RedirectResponse("/jindu/")


@app.get("/zhiliang")
async def _r_zl() -> RedirectResponse:
    return RedirectResponse("/zhiliang/")


@app.get("/chengben")
async def _r_cb() -> RedirectResponse:
    return RedirectResponse("/chengben/")


@app.get("/jishubiao")
async def _r_js() -> RedirectResponse:
    return RedirectResponse("/jishubiao/")
