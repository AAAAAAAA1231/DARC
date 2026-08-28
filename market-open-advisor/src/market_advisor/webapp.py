"""Local browser UI. Avoids PyInstaller EXEs that Windows Defender flags."""

from __future__ import annotations

import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .engine import Report, run_report
from .html_report import render_html, render_loading
from .model import DEFAULT_VERIFY_SIMS
from .universe import DEFAULT_PER_MARKET


class AppState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.message = "正在启动…"
        self.done = False
        self.error: str | None = None
        self.report: Report | None = None
        self.generation = 0

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "done": self.done,
                "message": self.message,
                "error": self.error,
                "generation": self.generation,
            }


def render_status_page(state: AppState) -> str:
    with state.lock:
        error = state.error
        done = state.done
        message = state.message
        report = state.report
    if error:
        return render_loading(message=error, failed=True)
    if done and report is not None:
        return render_html(report)
    return render_loading(message=message, failed=False)


def run_web(
    n_verify: int = DEFAULT_VERIFY_SIMS,
    seed: int | None = 20260828,
    per_market: int = DEFAULT_PER_MARKET,
    host: str = "127.0.0.1",
    port: int = 0,
) -> None:
    state = AppState()

    def compute() -> None:
        with state.lock:
            state.done = False
            state.error = None
            state.message = "正在拉取行情并计算每只股票的建议…"
        try:
            report = run_report(
                n_verify=n_verify,
                seed=seed,
                per_market=per_market,
                progress=lambda msg: _set_message(state, msg),
            )
            with state.lock:
                state.report = report
                state.done = True
                state.message = "完成"
                state.generation += 1
        except Exception as exc:  # noqa: BLE001
            with state.lock:
                state.error = str(exc)
                state.done = True
                state.generation += 1

    def kick() -> None:
        threading.Thread(target=compute, daemon=True).start()

    kick()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:  # noqa: A003
            return

        def _send(self, body: str, content_type: str = "text/html; charset=utf-8", code: int = 200) -> None:
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/status":
                self._send(json.dumps(state.snapshot(), ensure_ascii=False), "application/json; charset=utf-8")
                return
            if path == "/refresh":
                kick()
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return
            self._send(render_status_page(state))

    httpd = ThreadingHTTPServer((host, port), Handler)
    actual_port = httpd.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"
    print(f"开盘建议已启动：{url}", flush=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.2)
    webbrowser.open(url)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        httpd.shutdown()


def _set_message(state: AppState, message: str) -> None:
    with state.lock:
        state.message = message
