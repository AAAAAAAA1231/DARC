from __future__ import annotations

import argparse
import http.server
import os
import socketserver
import sys
import tempfile
import threading
import time
import webbrowser
from datetime import timezone
from pathlib import Path

from .models import utcnow
from .report import render_html, render_json, render_scanning_html, render_text
from .scoring import score_many, summarize_venues
from .sources import DEFAULT_NETWORKS, collect_snapshots


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fiftyx-radar",
        description="按「新场子 + 独占叙事 + 浅开盘」扫描该关注的新币。不是投资建议。",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--text", action="store_true", help="只在终端打印，不打开浏览器")
    parser.add_argument("--html", metavar="PATH", help="写成 HTML 报告")
    parser.add_argument("--serve", action="store_true", help="生成 HTML 并在本地打开一个静态页")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--networks",
        default=",".join(DEFAULT_NETWORKS),
        help="逗号分隔的 GeckoTerminal 网络 id",
    )
    parser.add_argument("--min-score", type=int, default=55, help="名单最低分")
    return parser


def use_browser_ui(args: argparse.Namespace) -> bool:
    if args.json or args.text:
        return False
    if args.html and not args.serve:
        return False
    return True


def _configure_stdio() -> None:
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def _say(message: str) -> None:
    print(message, flush=True)


def _report_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    return Path(tempfile.gettempdir()) / "fiftyx-radar-report.html"


def open_in_browser(target: str) -> bool:
    """Open a file path or URL in the default browser.

    Frozen Windows exes must not use webbrowser first: it can re-launch the exe
    because sys.executable points at FiftyXRadar.exe.
    """
    if sys.platform == "win32":
        try:
            os.startfile(target)  # type: ignore[attr-defined]
            return True
        except OSError:
            pass
    try:
        return bool(webbrowser.open(target, new=2))
    except Exception:
        return False


def _start_server(directory: str, start_port: int) -> tuple[socketserver.TCPServer, int]:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *handler_args, **handler_kwargs):
            super().__init__(*handler_args, directory=directory, **handler_kwargs)

        def log_message(self, format: str, *log_args) -> None:  # noqa: A003
            return

    socketserver.TCPServer.allow_reuse_address = True
    last_error: OSError | None = None
    for port in range(start_port, start_port + 20):
        try:
            httpd = socketserver.TCPServer(("127.0.0.1", port), Handler)
            return httpd, port
        except OSError as exc:
            last_error = exc
            continue
    raise OSError(f"没有可用端口（从 {start_port} 起）") from last_error


def _serve_in_background(directory: str, port: int) -> tuple[socketserver.TCPServer, int, threading.Thread]:
    httpd, bound = _start_server(directory, port)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    return httpd, bound, thread


def keep_window_open() -> None:
    _say("\n浏览器已打开。关掉这个黑窗口，或按回车退出。")
    try:
        input()
    except EOFError:
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return


def run(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)
    networks = tuple(n.strip() for n in args.networks.split(",") if n.strip())
    ui = use_browser_ui(args)
    html_path = _report_path(args.html) if (args.html or ui or args.serve) else None
    httpd = None
    target = ""

    if ui and html_path is not None:
        html_path.write_text(render_scanning_html(), encoding="utf-8")
        _say("正在扫描新场子和新盘，浏览器马上打开…")
        httpd, port, _thread = _serve_in_background(str(html_path.parent.resolve()), args.port)
        args.port = port
        target = f"http://127.0.0.1:{port}/{html_path.name}"
        if not args.no_browser:
            opened = open_in_browser(target)
            if not opened:
                opened = open_in_browser(str(html_path.resolve()))
            if opened:
                _say(f"已打开 {target}")
            else:
                _say(f"没能自动打开浏览器，请手动打开：{target}")

    generated_at = utcnow().astimezone(timezone.utc)
    snapshots = collect_snapshots(networks=networks)
    scored = score_many(snapshots)
    venues = summarize_venues(snapshots)
    watchable = [s for s in scored if s.score.total >= args.min_score]

    if args.json:
        sys.stdout.write(render_json(venues, watchable, generated_at))
        return 0

    if not ui:
        sys.stdout.write(render_text(venues, watchable, generated_at))

    if html_path:
        html_path.write_text(render_html(venues, watchable, generated_at), encoding="utf-8")
        if not ui:
            print(f"\nHTML: {html_path.resolve()}", file=sys.stderr)
        else:
            _say("扫描完成，浏览器页面会自动刷新成结果。")
            if target:
                _say(target)

    if ui:
        try:
            keep_window_open()
        except KeyboardInterrupt:
            return 0
        finally:
            if httpd is not None:
                httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
