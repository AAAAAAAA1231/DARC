"""CLI: universe / signals / backtest / walkforward / montecarlo / paper / demo / serve."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config
from .data.provider import MarketData
from .paths import output_dir as default_output_dir
from .pipeline import run_pipeline


def _market(args, cfg):
    from .pipeline import ensure_market

    path = Path(args.data) if getattr(args, "data", None) else None
    return ensure_market(cfg, path, regenerate=getattr(args, "regenerate", False))


def cmd_demo(args) -> int:
    cfg = load_config(args.config)
    result = run_pipeline(
        cfg,
        output_dir=args.output,
        data_path=args.data,
        regenerate=args.regenerate,
        skip_monte_carlo=args.skip_mc,
        mode="quick" if getattr(args, "quick", False) else "full",
    )
    snap = result.extra.get("snapshot", {})
    print(json.dumps({k: snap[k] for k in ("asof", "universe_selected", "n_buy", "walkforward", "monte_carlo") if k in snap}, ensure_ascii=False, indent=2, default=str))
    print(f"output: {result.output_dir}")
    return 0


def cmd_universe(args) -> int:
    from .universe.filter import filter_universe

    cfg = load_config(args.config)
    m = _market(args, cfg)
    asof = args.asof or str(pd_max(m))
    uni = filter_universe(m.bars, m.meta, asof, cfg)
    out = Path(args.output or ".") / "universe.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    uni.to_csv(out, index=False)
    n = int(uni["selected"].sum()) if "selected" in uni.columns else 0
    print(f"selected={n} eligible={int(uni['eligible'].sum()) if 'eligible' in uni.columns else 0} -> {out}")
    return 0


def pd_max(m: MarketData):
    import pandas as pd

    return pd.to_datetime(m.bars["date"]).max().date()


def cmd_signals(args) -> int:
    from .ideas import generate_ideas

    cfg = load_config(args.config)
    m = _market(args, cfg)
    asof = args.asof or str(pd_max(m))
    ideas = generate_ideas(m.bars, m.meta, cfg, asof)
    out = Path(args.output or ".") / "ideas.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    ideas.to_csv(out, index=False)
    print(ideas.head(15).to_string(index=False))
    print(f"wrote {out}")
    return 0


def cmd_backtest(args) -> int:
    from .backtest.engine import run_backtest
    from .universe.filter import filter_universe

    cfg = load_config(args.config)
    m = _market(args, cfg)
    asof = pd_max(m)
    uni = filter_universe(m.bars, m.meta, asof, cfg)
    selected = uni.loc[uni.get("selected", False) == True, "symbol"].tolist() if "selected" in uni.columns else None
    bt = run_backtest(m.bars, m.meta, cfg, symbols=selected)
    print(json.dumps(bt.metrics, indent=2, default=str))
    return 0


def cmd_walkforward(args) -> int:
    from .backtest.walkforward import walk_forward
    from .universe.filter import filter_universe

    cfg = load_config(args.config)
    m = _market(args, cfg)
    uni = filter_universe(m.bars, m.meta, pd_max(m), cfg)
    selected = uni.loc[uni.get("selected", False) == True, "symbol"].tolist() if "selected" in uni.columns else None
    wf = walk_forward(m.bars, m.meta, cfg, symbols=selected)
    print(json.dumps(wf.oos_metrics, indent=2, default=str))
    if not wf.folds.empty:
        print(wf.folds.to_string(index=False))
    return 0


def cmd_montecarlo(args) -> int:
    cfg = load_config(args.config)
    result = run_pipeline(cfg, output_dir=args.output, data_path=args.data, regenerate=False)
    print(json.dumps(result.monte_carlo.summary, indent=2, default=str))
    for n in result.monte_carlo.notes:
        print("-", n)
    return 0


def cmd_paper(args) -> int:
    from .paper.simulator import run_paper
    from .universe.filter import filter_universe

    cfg = load_config(args.config)
    m = _market(args, cfg)
    uni = filter_universe(m.bars, m.meta, pd_max(m), cfg)
    selected = uni.loc[uni.get("selected", False) == True, "symbol"].tolist() if "selected" in uni.columns else None
    paper = run_paper(m.bars, m.meta, cfg, symbols=selected, days=args.days)
    print(paper.disclaimer)
    print(json.dumps(paper.result.metrics, indent=2, default=str))
    return 0


def cmd_desktop(args) -> int:
    from .desktop import main as desktop_main

    return desktop_main()


def cmd_serve(args) -> int:
    import uvicorn

    from .web.app import create_app

    cfg = load_config(args.config)
    app = create_app(cfg, output_dir=args.output, data_path=args.data)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--config", default=None)
    shared.add_argument("--data", default=None)
    shared.add_argument("--output", default=None)

    p = argparse.ArgumentParser(
        prog="ashare-quant",
        description="A股量化信号与风控辅助（非实盘下单）",
        parents=[shared],
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="生成数据并跑完整流水线", parents=[shared])
    d.add_argument("--regenerate", action="store_true")
    d.add_argument("--skip-mc", action="store_true")
    d.add_argument("--quick", action="store_true", help="跳过 Walk-Forward / 蒙特卡洛，适合桌面首次启动")
    d.set_defaults(func=cmd_demo, regenerate=False)

    u = sub.add_parser("universe", parents=[shared])
    u.add_argument("--asof", default=None)
    u.add_argument("--regenerate", action="store_true")
    u.set_defaults(func=cmd_universe)

    s = sub.add_parser("signals", parents=[shared])
    s.add_argument("--asof", default=None)
    s.add_argument("--regenerate", action="store_true")
    s.set_defaults(func=cmd_signals)

    b = sub.add_parser("backtest", parents=[shared])
    b.add_argument("--regenerate", action="store_true")
    b.set_defaults(func=cmd_backtest)

    w = sub.add_parser("walkforward", parents=[shared])
    w.add_argument("--regenerate", action="store_true")
    w.set_defaults(func=cmd_walkforward)

    m = sub.add_parser("montecarlo", parents=[shared])
    m.set_defaults(func=cmd_montecarlo)

    pa = sub.add_parser("paper", parents=[shared])
    pa.add_argument("--days", type=int, default=40)
    pa.add_argument("--regenerate", action="store_true")
    pa.set_defaults(func=cmd_paper)

    sv = sub.add_parser("serve", parents=[shared])
    sv.add_argument("--host", default="0.0.0.0")
    sv.add_argument("--port", type=int, default=8765)
    sv.set_defaults(func=cmd_serve)

    desk = sub.add_parser("desktop", help="打开可双击使用的桌面窗口", parents=[shared])
    desk.set_defaults(func=cmd_desktop)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "output", None) is None:
        args.output = str(default_output_dir())
    return int(args.func(args) or 0)
