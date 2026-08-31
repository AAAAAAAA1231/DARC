from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .scanner import THESIS, run_scan

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="Golden Dog Radar", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "golden-dog-radar"}


@app.get("/api/thesis")
async def thesis():
    return THESIS


@app.get("/api/scan")
async def scan(force: bool = Query(False)):
    return await run_scan(force=force)


if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    async def index():
        return FileResponse(DIST / "index.html")
