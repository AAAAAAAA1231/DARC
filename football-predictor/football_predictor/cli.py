from __future__ import annotations

import argparse
import sys
import traceback

from .config import APP_NAME, LEAGUES, LEAGUE_ORDER
from .model.pipeline import Predictor
from .report import format_report


def _print(msg: str) -> None:
    print(msg, flush=True)


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="football-predictor", description=APP_NAME)
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("upcoming", help="列出未来赛程")
    p = sub.add_parser("predict", help="预测一场比赛")
    p.add_argument("--league", required=True, choices=LEAGUE_ORDER, help="laliga / bundesliga / seriea")
    p.add_argument("--home", required=True)
    p.add_argument("--away", required=True)

    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 2

    pred = Predictor()
    try:
        pred.build(progress=_print)
    except Exception:
        traceback.print_exc()
        return 1

    if args.cmd == "upcoming":
        fixtures = pred.upcoming()
        if not fixtures:
            _print("未获取到近期赛程，请检查网络。")
            return 1
        for fx in fixtures:
            status = "已完赛" if fx.status == "post" else "未赛"
            league_cn = LEAGUES[fx.league].name_cn
            _print(f"[{league_cn}] {fx.label}  ({status})")
        return 0

    result = pred.predict(args.league, args.home, args.away, progress=_print)
    _print(format_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
