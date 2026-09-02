from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from suite.boot import repo_root, setup_sys_path

setup_sys_path()

from suite import airdrop_api, football_api, launch_api, radar_api  # noqa: E402
from web3_radar.api import app as chain_app  # noqa: E402
from web3_radar.config import ensure_dirs  # noqa: E402


def _suite_static() -> Path:
    root = repo_root()
    candidates = [
        Path(__file__).resolve().parent / "static",
        root / "suite" / "static",
        root / "desk-suite" / "suite" / "static",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


STATIC_DIR = _suite_static()


class FootballSearchBody(BaseModel):
    query: str = Field(default="", min_length=0)


def create_app() -> FastAPI:
    ensure_dirs()
    app = FastAPI(title="工作台", version="1.0.0")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "app": "工作台", "modules": ["radar", "football", "contracts", "airdrops", "launches"]}

    @app.get("/api/cycle")
    async def cycle() -> dict:
        from web3_radar.engine.cycle import current_cycle

        try:
            return current_cycle().to_dict()
        except Exception as exc:
            raise HTTPException(502, f"四年周期数据暂时拉不到：{exc}") from exc

    @app.post("/api/radar/scan")
    async def radar_scan() -> dict:
        return radar_api.start()

    @app.get("/api/radar/status")
    async def radar_status() -> dict:
        return radar_api.status()

    @app.get("/api/radar/html")
    async def radar_html() -> HTMLResponse:
        return HTMLResponse(radar_api.current_html())

    @app.get("/api/radar/json")
    async def radar_json() -> PlainTextResponse:
        return PlainTextResponse(radar_api.current_json(), media_type="application/json")

    @app.post("/api/football/run")
    async def football_run() -> dict:
        return football_api.start("all")

    @app.post("/api/football/search")
    async def football_search(body: FootballSearchBody) -> dict:
        query = (body.query or "").strip()
        if not query:
            raise HTTPException(400, "请输入：下一场皇马 / 巴萨vs马竞 / 德甲")
        return football_api.start("search", query)

    @app.get("/api/football/status")
    async def football_status() -> JSONResponse:
        return JSONResponse(football_api.status())

    @app.post("/api/airdrops/scan")
    async def airdrop_scan() -> dict:
        return airdrop_api.start()

    @app.get("/api/airdrops/status")
    async def airdrop_status() -> JSONResponse:
        return JSONResponse(airdrop_api.status())

    @app.post("/api/launches/scan")
    async def launch_scan() -> dict:
        return launch_api.start()

    @app.get("/api/launches/status")
    async def launch_status() -> JSONResponse:
        return JSONResponse(launch_api.status())

    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")
    app.mount("/chain", chain_app)
    return app


app = create_app()
