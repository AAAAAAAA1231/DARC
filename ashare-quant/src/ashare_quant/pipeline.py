"""End-to-end demo / research pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from .backtest.engine import BacktestResult, run_backtest
from .backtest.walkforward import WalkForwardResult, walk_forward
from .config import AppConfig, load_config
from .data.provider import MarketData, default_data_dir
from .ideas import generate_ideas
from .monte_carlo.simulator import MonteCarloResult, run_monte_carlo
from .paper.simulator import DISCLAIMER, run_paper
from .report import write_report
from .universe.filter import filter_universe


@dataclass
class PipelineResult:
    asof: str
    universe: pd.DataFrame
    ideas: pd.DataFrame
    backtest: BacktestResult
    walkforward: WalkForwardResult
    monte_carlo: MonteCarloResult
    output_dir: Path
    disclaimer: str = DISCLAIMER
    extra: dict = field(default_factory=dict)


def ensure_market(cfg: AppConfig, data_path: Path | None = None, regenerate: bool = False) -> MarketData:
    data_dir = default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    path = Path(data_path) if data_path else data_dir / "synthetic_bars.csv"
    if path.exists() and not regenerate:
        return MarketData.from_csv(path)
    market = MarketData.synthetic(cfg)
    market.save(path)
    return market


def run_pipeline(
    cfg: AppConfig | None = None,
    *,
    output_dir: str | Path | None = None,
    data_path: str | Path | None = None,
    regenerate: bool = False,
    skip_monte_carlo: bool = False,
) -> PipelineResult:
    cfg = cfg or load_config()
    out = Path(output_dir) if output_dir else Path(__file__).resolve().parents[2] / "output"
    out.mkdir(parents=True, exist_ok=True)

    market = ensure_market(cfg, Path(data_path) if data_path else None, regenerate=regenerate)
    asof = pd.to_datetime(market.bars["date"].max()).date()
    uni = filter_universe(market.bars, market.meta, asof, cfg)
    selected = uni.loc[uni.get("selected", False) == True, "symbol"].tolist() if "selected" in uni.columns else []

    bt = run_backtest(market.bars, market.meta, cfg, symbols=selected or None)
    wf = walk_forward(market.bars, market.meta, cfg, symbols=selected or None)
    mc = (
        MonteCarloResult({"skipped": True}, pd.DataFrame(), {}, {}, ["已跳过蒙特卡洛"])
        if skip_monte_carlo
        else run_monte_carlo(wf.oos_equity if not wf.oos_equity.empty else bt.equity, market.bars, market.meta, cfg, selected, bt.weights_last)
    )
    ideas = generate_ideas(market.bars, market.meta, cfg, asof, panel=bt.panel, weights=bt.weights_last)
    paper = run_paper(market.bars, market.meta, cfg, symbols=selected or None)

    uni.to_csv(out / "universe.csv", index=False)
    ideas.to_csv(out / "ideas.csv", index=False)
    if not bt.trades.empty:
        bt.trades.to_csv(out / "trades.csv", index=False)
    bt.equity.rename("equity").to_csv(out / "equity.csv")
    wf.oos_equity.rename("oos_equity").to_csv(out / "oos_equity.csv")
    if not wf.folds.empty:
        wf.folds.to_csv(out / "walkforward_folds.csv", index=False)
    if not mc.distribution.empty:
        mc.distribution.to_csv(out / "monte_carlo.csv", index=False)
    paper.result.equity.rename("paper_equity").to_csv(out / "paper_equity.csv")

    snapshot = {
        "asof": asof.isoformat(),
        "disclaimer": DISCLAIMER,
        "universe_selected": int(uni["selected"].sum()) if "selected" in uni.columns else 0,
        "universe_eligible": int(uni["eligible"].sum()) if "eligible" in uni.columns else 0,
        "backtest": bt.metrics,
        "walkforward": wf.oos_metrics,
        "monte_carlo": mc.summary,
        "adjusted_ensemble": mc.adjusted_ensemble,
        "adjusted_risk": mc.adjusted_risk,
        "mc_notes": mc.notes,
        "weights": bt.weights_last,
        "n_ideas": int(len(ideas)),
        "n_buy": int((ideas["action"] == "buy").sum()) if len(ideas) else 0,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
    (out / "snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_report(out, snapshot, ideas, wf, mc, bt)

    return PipelineResult(
        asof=asof.isoformat(),
        universe=uni,
        ideas=ideas,
        backtest=bt,
        walkforward=wf,
        monte_carlo=mc,
        output_dir=out,
        extra={"paper_metrics": paper.result.metrics, "snapshot": snapshot},
    )
