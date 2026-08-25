from __future__ import annotations

import argparse
import json
import sys

from . import config
from .data_source import fetch_universe
from .engine import calibrate, ensure_bars, predict_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="a-share", description="大A多因子研判与百亿次模拟校正")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_uni = sub.add_parser("fetch-universe", help="拉取沪深京全部A股列表")
    p_uni.add_argument("--force", action="store_true")

    p_bars = sub.add_parser("fetch-bars", help="拉取日K（腾讯前复权）")
    p_bars.add_argument("--limit", type=int, default=None)
    p_bars.add_argument("--workers", type=int, default=16)

    p_sim = sub.add_parser("simulate", help="Monte Carlo 校正方法权重")
    p_sim.add_argument("--n", type=int, default=config.N_SIMS_DELIVERY)
    p_sim.add_argument("--sample-size", type=int, default=240)
    p_sim.add_argument("--workers", type=int, default=None)

    p_pred = sub.add_parser("predict", help="对全部股票给出走势与止盈止损")
    p_pred.add_argument("--workers", type=int, default=None)

    p_run = sub.add_parser("run", help="全流程：列表、K线、10B模拟、预测")
    p_run.add_argument("--n", type=int, default=config.N_SIMS_DELIVERY)
    p_run.add_argument("--bars-limit", type=int, default=None)
    p_run.add_argument("--sample-size", type=int, default=240)

    p_serve = sub.add_parser("serve", help="启动研判终端")
    p_serve.add_argument("--host", default=config.DEFAULT_HOST)
    p_serve.add_argument("--port", type=int, default=config.DEFAULT_PORT)

    args = parser.parse_args(argv)
    if args.cmd == "fetch-universe":
        stocks = fetch_universe(force=args.force)
        print(f"universe={len(stocks)} -> {config.UNIVERSE_PATH}")
        return 0
    if args.cmd == "fetch-bars":
        if not config.UNIVERSE_PATH.exists():
            fetch_universe()
        stats = ensure_bars(limit=args.limit, max_workers=args.workers)
        print(json.dumps(stats, ensure_ascii=False))
        return 0
    if args.cmd == "simulate":
        if not config.UNIVERSE_PATH.exists():
            fetch_universe()
        result = calibrate(n_sims=args.n, sample_size=args.sample_size, workers=args.workers)
        print(
            f"n_sims={result['n_sims']:,} elapsed={result['elapsed_sec']}s "
            f"best_sharpe={result['best_sharpe']:.4f} -> {config.CALIBRATION_PATH}"
        )
        return 0
    if args.cmd == "predict":
        rows = predict_all(workers=args.workers)
        print(f"predictions={len(rows)} -> {config.PREDICTIONS_PATH}")
        return 0
    if args.cmd == "run":
        stocks = fetch_universe()
        print(f"universe={len(stocks)}")
        stats = ensure_bars(limit=args.bars_limit)
        print("bars", stats)
        result = calibrate(stocks=stocks, n_sims=args.n, sample_size=args.sample_size)
        print(f"simulated {result['n_sims']:,} in {result['elapsed_sec']}s")
        rows = predict_all(stocks)
        print(f"predictions={len(rows)}")
        return 0
    if args.cmd == "serve":
        import uvicorn
        from .webapp import app

        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
