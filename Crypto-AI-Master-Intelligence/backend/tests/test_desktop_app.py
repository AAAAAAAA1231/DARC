from __future__ import annotations

import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from backend.desktop_app import (
    build_uvicorn_server,
    close_boot_splash,
    configure_loopback_access,
    error_html,
    health_timeout_seconds,
    local_http_get,
    pick_listen_port,
    splash_html,
    start_boot_http,
    stop_boot_http,
    tcp_is_open,
    wait_for_health,
    wait_for_http_ok,
    window_url,
)


def test_health_timeout_is_longer_when_frozen():
    assert health_timeout_seconds(frozen=True) >= 120
    assert health_timeout_seconds(frozen=False) >= 30
    assert health_timeout_seconds(frozen=True) > health_timeout_seconds(frozen=False)


def test_pick_listen_port_skips_occupied():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    occupied = listener.getsockname()[1]
    try:
        nxt = pick_listen_port("127.0.0.1", occupied)
        assert nxt != occupied
    finally:
        listener.close()


def test_wait_for_health_true_then_false(tmp_path: Path):
    class Health(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/api/ready":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, *_args) -> None:  # noqa: ANN002
            return

    server = HTTPServer(("127.0.0.1", 0), Health)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert wait_for_health(f"http://127.0.0.1:{port}", timeout_s=3, interval_s=0.05)
    finally:
        server.shutdown()
        server.server_close()
    assert wait_for_health("http://127.0.0.1:1", timeout_s=0.4, interval_s=0.1) is False


def test_window_url_always_includes_port():
    assert window_url("127.0.0.1", 8787) == "http://127.0.0.1:8787"
    assert ":8787" in window_url("127.0.0.1", 8787)
    assert window_url("127.0.0.1", 8787) != "http://127.0.0.1"


def test_boot_http_serves_splash_and_not_ready():
    page = splash_html("http://127.0.0.1:8787", Path("desktop.log"))
    httpd, port = start_boot_http("127.0.0.1", 0, page)
    try:
        assert port > 0
        url = f"http://127.0.0.1:{port}"
        assert wait_for_http_ok(url + "/", timeout_s=3)
        code, body = local_http_get("127.0.0.1", port, "/")
        assert code == 200
        assert "正在启动" in body.decode("utf-8")
        assert "8787" in body.decode("utf-8")
        ready_code, _ready_body = local_http_get("127.0.0.1", port, "/api/ready")
        assert ready_code == 503
        assert wait_for_health(url, timeout_s=0.4, interval_s=0.1) is False
    finally:
        stop_boot_http(httpd)


def test_splash_and_error_html_point_at_ported_url(tmp_path: Path):
    log = tmp_path / "desktop.log"
    splash = splash_html("http://127.0.0.1:8787", log)
    assert "http://127.0.0.1:8787" in splash
    assert "/api/ready" in splash
    assert "127.0.0.1" in splash
    err = error_html("http://127.0.0.1:8787", log, "boom")
    assert "拒绝连接" in err
    assert "8787" in err
    assert "boom" in err


def test_wait_for_http_ok_ignores_http_proxy(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    httpd, port = start_boot_http("127.0.0.1", 0, "<html>proxy-bypass</html>")
    try:
        assert tcp_is_open("127.0.0.1", port)
        assert wait_for_http_ok(f"http://127.0.0.1:{port}/", timeout_s=3)
        code, body = local_http_get("127.0.0.1", port, "/")
        assert code == 200
        assert b"proxy-bypass" in body
    finally:
        stop_boot_http(httpd)


def test_configure_loopback_access_sets_no_proxy(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.delenv("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", raising=False)
    configure_loopback_access()
    assert "127.0.0.1" in os.environ["NO_PROXY"]
    assert "direct://" in os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"]


def test_close_boot_splash_is_safe_without_pyinstaller():
    close_boot_splash("hello")


def test_uvicorn_server_disables_signal_handlers():
    async def app(_scope, _receive, send):  # noqa: ANN001
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    server = build_uvicorn_server(app, "127.0.0.1", 18790)
    assert server.install_signal_handlers.__name__ == "<lambda>"
    server.install_signal_handlers()
