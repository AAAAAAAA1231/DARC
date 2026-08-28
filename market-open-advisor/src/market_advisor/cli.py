"""Headless JSON/text report used by tests and --once."""

from __future__ import annotations

import argparse
import json
import sys

from .engine import run_report
from .model import DEFAULT_VERIFY_SIMS
from .universe import DEFAULT_PER_MARKET


def format_text(report) -> str:
    lines = [
        f"打开时刻 {report.opened_at}",
        report.disclaimer,
        "",
    ]
    for item in report.items:
        chg = "" if item.change_pct is None else f"{item.change_pct:+.2f}%"
        spot = "" if item.spot is None else f"{item.spot:.2f}"
        lines.extend(
            [
                f"【{item.market_name} / {item.exchange}】{item.index_name}  {item.session}  源 {item.data_source}",
                f"  现价 {spot}  {chg}    最近收盘 {item.last_close:.2f}（{item.last_date}）",
                f"  建议：{item.action}    参考仓位 {item.size_pct}%    状态 {item.regime}",
                f"  100亿次极限  E[r]={item.expected_return:.3%}  P(up)={item.p_up:.1%}  "
                f"P5={item.p05:.3%}  P50={item.p50:.3%}  P95={item.p95:.3%}",
                f"  核验模拟 {item.n_verify_sims:,} 次，偏差 {item.verify_error:.2e}",
            ]
        )
        for reason in item.reasons:
            lines.append(f"  - {reason}")
        if item.stocks:
            lines.append(f"  个股建议 {len(item.stocks)} 只：")
            for stock in item.stocks:
                schg = "" if stock.change_pct is None else f"{stock.change_pct:+.2f}%"
                sspot = "" if stock.spot is None else f"{stock.spot:.2f}"
                lines.append(
                    f"    {stock.symbol} {stock.index_name}  {stock.action} 仓位{stock.size_pct}%  "
                    f"现价 {sspot} {schg}  E[r]={stock.expected_return:.3%}  P(up)={stock.p_up:.1%}  {stock.regime}"
                )
        lines.append("")
    if report.errors:
        lines.append("部分场所失败：")
        lines.extend(f"  {err}" for err in report.errors)
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="打开时刻按交易场所给出股票操作建议")
    parser.add_argument("--once", action="store_true", help="计算一次后打印并退出，不打开窗口")
    parser.add_argument("--json", action="store_true", help="与 --once 合用，输出 JSON")
    parser.add_argument("--web", action="store_true", help="在浏览器中打开建议（Windows 推荐）")
    parser.add_argument("--per-market", type=int, default=DEFAULT_PER_MARKET, help="每个交易场所拉取的个股数量")
    parser.add_argument(
        "--verify-sims",
        type=int,
        default=DEFAULT_VERIFY_SIMS,
        help="蒙特卡洛核验次数（建议取值始终是 100 亿次解析极限）",
    )
    parser.add_argument("--seed", type=int, default=20260828)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.once or args.html or args.json:
        report = run_report(n_verify=args.verify_sims, seed=args.seed, per_market=args.per_market)
        if args.html:
            from pathlib import Path

            from .html_report import write_html

            path = write_html(report, Path(args.html))
            sys.stderr.write(f"已写入 {path}\n")
        if args.json:
            sys.stdout.write(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n")
        elif args.once:
            sys.stdout.write(format_text(report))
        return 0
    if args.web or sys.platform.startswith("win"):
        from .webapp import run_web

        run_web(n_verify=args.verify_sims, seed=args.seed, per_market=args.per_market)
        return 0
    try:
        from .gui import run_gui
    except ModuleNotFoundError:
        from .webapp import run_web

        run_web(n_verify=args.verify_sims, seed=args.seed, per_market=args.per_market)
        return 0
    run_gui(n_verify=args.verify_sims, seed=args.seed, per_market=args.per_market)
    return 0
