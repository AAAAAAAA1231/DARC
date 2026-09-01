from __future__ import annotations

import argparse
import http.server
import socketserver
import sys
from datetime import timezone
from pathlib import Path

from .models import utcnow
from .report import render_html, render_json, render_text
from .scoring import score_many, summarize_venues
from .sources import DEFAULT_NETWORKS, collect_snapshots


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fiftyx-radar",
        description="按「新场子 + 独占叙事 + 浅开盘」扫描该关注的新币。不是投资建议。",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--html", metavar="PATH", help="写成 HTML 报告")
    parser.add_argument("--serve", action="store_true", help="生成 HTML 并在本地打开一个静态页")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--networks",
        default=",".join(DEFAULT_NETWORKS),
        help="逗号分隔的 GeckoTerminal 网络 id",
    )
    parser.add_argument("--min-score", type=int, default=55, help="名单最低分")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    networks = tuple(n.strip() for n in args.networks.split(",") if n.strip())
    generated_at = utcnow().astimezone(timezone.utc)

    snapshots = collect_snapshots(networks=networks)
    scored = score_many(snapshots)
    venues = summarize_venues(snapshots)
    watchable = [s for s in scored if s.score.total >= args.min_score]

    if args.json:
        sys.stdout.write(render_json(venues, watchable, generated_at))
        return 0

    text = render_text(venues, watchable, generated_at)
    sys.stdout.write(text)

    html_path = Path(args.html) if args.html else None
    if args.serve:
        html_path = html_path or Path("fiftyx-radar-report.html")
    if html_path:
        html_path.write_text(render_html(venues, watchable, generated_at), encoding="utf-8")
        print(f"\nHTML: {html_path.resolve()}", file=sys.stderr)

    if args.serve:
        directory = str(html_path.parent.resolve())

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *handler_args, **handler_kwargs):
                super().__init__(*handler_args, directory=directory, **handler_kwargs)

        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("127.0.0.1", args.port), Handler) as httpd:
            print(f"打开 http://127.0.0.1:{args.port}/{html_path.name}", file=sys.stderr)
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
