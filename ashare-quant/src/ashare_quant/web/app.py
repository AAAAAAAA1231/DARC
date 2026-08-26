from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import AppConfig, load_config
from ..paper.simulator import DISCLAIMER
from ..pipeline import run_pipeline

TEMPLATES = Path(__file__).with_name("templates")
STATIC = Path(__file__).with_name("static")


def _load_snapshot(output_dir: Path) -> dict:
    p = output_dir / "snapshot.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def create_app(cfg: AppConfig | None = None, output_dir: str | Path | None = None, data_path: str | Path | None = None) -> FastAPI:
    cfg = cfg or load_config()
    out = Path(output_dir) if output_dir else Path(__file__).resolve().parents[3] / "output"
    out.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="A股量化辅助系统", docs_url="/api/docs")
    templates = Jinja2Templates(directory=str(TEMPLATES))
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
    app.mount("/artifacts", StaticFiles(directory=str(out)), name="artifacts")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        snap = _load_snapshot(out)
        ideas_path = out / "ideas.csv"
        ideas = []
        if ideas_path.exists():
            import pandas as pd

            df = pd.read_csv(ideas_path)
            ideas = df.head(40).fillna("").to_dict(orient="records")
        folds = []
        fp = out / "walkforward_folds.csv"
        if fp.exists():
            import pandas as pd

            folds = pd.read_csv(fp).fillna("").to_dict(orient="records")
        uni_n = {"selected": snap.get("universe_selected", 0), "eligible": snap.get("universe_eligible", 0)}
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "disclaimer": snap.get("disclaimer", DISCLAIMER),
                "snap": snap,
                "ideas": ideas,
                "folds": folds,
                "uni_n": uni_n,
                "has_oos_chart": (out / "oos_equity.png").exists(),
                "has_mc_chart": (out / "monte_carlo.png").exists(),
            },
        )

    @app.post("/api/run")
    def api_run():
        result = run_pipeline(cfg, output_dir=out, data_path=data_path)
        return JSONResponse(result.extra.get("snapshot", {}))

    @app.get("/api/snapshot")
    def api_snapshot():
        return JSONResponse(_load_snapshot(out))

    @app.get("/api/ideas")
    def api_ideas():
        p = out / "ideas.csv"
        if not p.exists():
            return JSONResponse({"ideas": []})
        import pandas as pd

        return JSONResponse({"ideas": pd.read_csv(p).fillna("").to_dict(orient="records")})

    @app.get("/health")
    def health():
        return {"ok": True, "output": str(out), "has_snapshot": (out / "snapshot.json").exists()}

    return app
