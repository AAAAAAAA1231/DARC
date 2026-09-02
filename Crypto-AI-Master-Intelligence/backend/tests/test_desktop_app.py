from __future__ import annotations

import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from backend.desktop_app import (
    build_uvicorn_server,
    close_boot_splash,
    error_html,
    health_timeout_seconds,
    pick_listen_port,
    splash_html,
    wait_for_health,
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


def test_splash_and_error_html_point_at_ported_url(tmp_path: Path):
    log = tmp_path / "desktop.log"
    splash = splash_html("http://127.0.0.1:8787", log)
    assert "http://127.0.0.1:8787" in splash
    assert "/api/ready" in splash
    assert "127.0.0.1" in splash
    err = error_html("http://127.0.0.1:8787", log, "boom")
    assert "ERR_CONNECTION_REFUSED" in err
    assert "8787" in err
    assert "boom" in err


def test_close_boot_splash_is_safe_without_pyinstaller():
    close_boot_splash("hello")


def test_uvicorn_server_disables_signal_handlers():
    async def app(_scope, _receive, send):  # noqa: ANN001
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    server = build_uvicorn_server(app, "127.0.0.1", 18790)
    assert server.install_signal_handlers.__name__ == "<lambda>"
    server.install_signal_handlers()
