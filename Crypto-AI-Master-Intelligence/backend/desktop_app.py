"""Desktop entry: local API + pywebview window. No live trading.

Windows + PyInstaller: never call ``uvicorn.run()`` from a background thread
(it installs signal handlers). Never open WebView2 on bare ``127.0.0.1``
(port 80) — that is ERR_CONNECTION_REFUSED even when :8787 is healthy.
Hold the listen port with a stdlib boot page, then hand it to uvicorn.
"""

from __future__ import annotations

import html
import json
import multiprocessing
import os
import socket
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from backend.core.paths import DATA_ROOT, prepare_runtime

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
FROZEN_HEALTH_TIMEOUT_S = 180.0
DEV_HEALTH_TIMEOUT_S = 60.0
HEALTH_POLL_S = 0.5
LOOPBACK_NO_PROXY = "127.0.0.1,localhost,::1"
WEBVIEW2_DIRECT_ARGS = "--proxy-server=direct:// --proxy-bypass-list=<-loopback>;127.0.0.1;localhost"


def desktop_log_path() -> Path:
    return DATA_ROOT / "logs" / "desktop.log"


def append_desktop_log(message: str) -> Path:
    path = desktop_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} | {message}\n")
    return path


def install_crash_hooks() -> None:
    def _hook(exc_type, exc, tb) -> None:  # noqa: ANN001
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        append_desktop_log(f"unhandled\n{text}")
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook

    def _thread_hook(args: threading.ExceptHookArgs) -> None:
        text = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        append_desktop_log(f"thread_unhandled thread={args.thread}\n{text}")

    threading.excepthook = _thread_hook


def health_timeout_seconds(frozen: bool | None = None) -> float:
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    return FROZEN_HEALTH_TIMEOUT_S if is_frozen else DEV_HEALTH_TIMEOUT_S


def window_url(host: str, port: int) -> str:
    """Always include the port. Bare 127.0.0.1 is port 80 and will refuse."""
    return f"http://{host}:{int(port)}"


def configure_loopback_access() -> None:
    """Clash/V2Ray system proxy must not intercept 127.0.0.1 or WebView2."""
    for key in ("NO_PROXY", "no_proxy"):
        parts = [item.strip() for item in os.environ.get(key, "").split(",") if item.strip()]
        for item in LOOPBACK_NO_PROXY.split(","):
            if item not in parts:
                parts.append(item)
        os.environ[key] = ",".join(parts)
    existing = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
    if "proxy-server" not in existing:
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"{existing} {WEBVIEW2_DIRECT_ARGS}".strip()
    append_desktop_log(
        "proxy_env HTTP_PROXY=%s HTTPS_PROXY=%s NO_PROXY=%s WEBVIEW2=%s"
        % (
            os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or "",
            os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "",
            os.environ.get("NO_PROXY", ""),
            os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", ""),
        )
    )


def tcp_is_open(host: str, port: int, timeout_s: float = 0.3) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_s)
        return sock.connect_ex((host, port)) == 0


def local_http_get(host: str, port: int, path: str = "/", timeout_s: float = 2.0) -> tuple[int, bytes]:
    """Raw TCP HTTP GET. urllib honors HTTP_PROXY and will miss loopback."""
    if not path.startswith("/"):
        path = "/" + path
    payload = (
        f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
    ).encode("ascii")
    with socket.create_connection((host, port), timeout=timeout_s) as sock:
        sock.settimeout(timeout_s)
        sock.sendall(payload)
        chunks: list[bytes] = []
        while True:
            piece = sock.recv(65536)
            if not piece:
                break
            chunks.append(piece)
    header, _sep, body = b"".join(chunks).partition(b"\r\n\r\n")
    parts = header.split(b"\r\n", 1)[0].split()
    code = int(parts[1]) if len(parts) >= 2 else 0
    return code, body


def pick_listen_port(host: str, preferred: int, span: int = 20) -> int:
    candidates = [preferred, *range(preferred + 1, preferred + span)]
    for port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as checker:
            checker.settimeout(0.3)
            if checker.connect_ex((host, port)) == 0:
                continue
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind((host, port))
            return port
        except OSError:
            continue
        finally:
            probe.close()
    raise RuntimeError(f"no free TCP port on {host} near {preferred}")


def build_uvicorn_server(app: Any, host: str, port: int) -> Any:
    from uvicorn import Config, Server

    config = Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        lifespan="on",
    )
    server = Server(config)
    server.install_signal_handlers = lambda: None
    return server


class _BootHandler(BaseHTTPRequestHandler):
    page: bytes = b""

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/ready":
            body = b'{"ok":false,"booting":true}'
            self.send_response(503)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = type(self).page
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *args: object) -> None:
        return


class BootServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def start_boot_http(host: str, preferred: int, page: str, span: int = 20) -> tuple[ThreadingHTTPServer, int]:
    handler = type("BootHandler", (_BootHandler,), {"page": page.encode("utf-8")})
    last_err: Exception | None = None
    ports = [preferred, *range(preferred + 1, preferred + span)] if preferred else [0]
    for port in ports:
        try:
            httpd = BootServer((host, port), handler)
        except OSError as exc:
            last_err = exc
            continue
        bound = int(httpd.server_address[1])

        def _serve(server: ThreadingHTTPServer = httpd) -> None:
            try:
                append_desktop_log(f"boot_http_serve_forever {server.server_address}")
                server.serve_forever()
                append_desktop_log("boot_http_serve_stopped")
            except Exception as exc:  # noqa: BLE001
                append_desktop_log(f"boot_http_serve_failed {exc}\n{traceback.format_exc()}")

        thread = threading.Thread(target=_serve, daemon=True, name="cami-boot-http")
        thread.start()
        append_desktop_log(f"boot_http_listening {host}:{bound}")
        return httpd, bound
    raise RuntimeError(f"boot http bind failed: {last_err}")


def stop_boot_http(httpd: ThreadingHTTPServer | None) -> None:
    if httpd is None:
        return
    append_desktop_log("boot_http_stopping")
    try:
        httpd.shutdown()
    except Exception as exc:  # noqa: BLE001
        append_desktop_log(f"boot_http_shutdown {exc}")
    try:
        httpd.server_close()
    except Exception as exc:  # noqa: BLE001
        append_desktop_log(f"boot_http_close {exc}")


def wait_for_http_ok(url: str, timeout_s: float, interval_s: float = 0.1) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = int(parsed.port or 80)
    path = parsed.path or "/"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            code, _body = local_http_get(host, port, path, timeout_s=2)
            if 200 <= code < 300:
                return True
        except (OSError, ValueError, TimeoutError):
            pass
        time.sleep(interval_s)
    return False


def wait_for_health(
    url: str,
    timeout_s: float,
    interval_s: float = HEALTH_POLL_S,
    abort: Callable[[], bool] | None = None,
) -> bool:
    parsed = urlparse(url.rstrip("/") + "/api/ready")
    host = parsed.hostname or "127.0.0.1"
    port = int(parsed.port or 80)
    path = parsed.path or "/api/ready"
    deadline = time.monotonic() + timeout_s
    last_note = 0.0
    while time.monotonic() < deadline:
        if abort and abort():
            append_desktop_log("health_wait_aborted")
            return False
        try:
            code, _body = local_http_get(host, port, path, timeout_s=2)
            if 200 <= code < 300:
                append_desktop_log(f"health_ok {host}:{port}{path}")
                return True
            exc: object = f"http_{code}"
        except (OSError, ValueError, TimeoutError) as err:
            exc = err
        now = time.monotonic()
        if now - last_note >= 10:
            append_desktop_log(f"health_wait {host}:{port}{path} still_down {exc}")
            last_note = now
        time.sleep(interval_s)
    append_desktop_log(f"health_timeout {host}:{port}{path} after {timeout_s}s")
    return False


def splash_html(url: str, log_path: Path) -> str:
    safe_url = html.escape(url, quote=True)
    safe_log = html.escape(str(log_path))
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <title>正在启动</title>
  <style>
    body {{ margin:0; font-family:Segoe UI,sans-serif; background:#0b0f14; color:#d8e0ea;
           display:flex; min-height:100vh; align-items:center; justify-content:center; }}
    .card {{ max-width:640px; padding:36px; }}
    h1 {{ font-size:22px; margin:0 0 12px; }}
    p {{ line-height:1.6; color:#9aa8b8; }}
    code {{ color:#7dd3fc; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>正在启动本地引擎</h1>
    <p>首次打开可能需要 1–3 分钟。请留在本页，不要改地址、不要只打开 <code>127.0.0.1</code>（那是 80 端口，会显示拒绝连接）。</p>
    <p>本窗口地址必须是 <code>{safe_url}</code>。</p>
    <p>日志：<code>{safe_log}</code></p>
    <p id="st">引擎加载中…</p>
  </div>
  <script>
    async function poll() {{
      try {{
        const res = await fetch({json.dumps(url.rstrip("/") + "/api/ready")}, {{ cache: "no-store" }});
        if (res.ok) {{ location.replace({json.dumps(url.rstrip("/") + "/?v=zhcn")}); return; }}
      }} catch (e) {{}}
      setTimeout(poll, 400);
    }}
    poll();
  </script>
</body>
</html>
"""


def error_html(url: str, log_path: Path, detail: str) -> str:
    safe_url = html.escape(url)
    safe_log = html.escape(str(log_path))
    safe_detail = html.escape(detail or "本地 API 没有在时限内响应 /api/ready。")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <title>启动失败</title>
  <style>
    body {{ margin:0; font-family:Segoe UI,sans-serif; background:#0b0f14; color:#d8e0ea;
           display:flex; min-height:100vh; align-items:center; justify-content:center; }}
    .card {{ max-width:720px; padding:36px; }}
    h1 {{ font-size:22px; margin:0 0 12px; color:#f87171; }}
    p {{ line-height:1.6; color:#9aa8b8; }}
    code {{ color:#7dd3fc; }}
    pre {{ white-space:pre-wrap; background:#111827; padding:12px; border-radius:8px; color:#fca5a5; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>本地引擎没有启动</h1>
    <p>Edge 提示「127.0.0.1 拒绝连接」通常是窗口打开了 <code>127.0.0.1</code>（80 端口）而引擎在 <code>{safe_url}</code>。</p>
    <p>请把下面的日志发给开发者：<code>{safe_log}</code></p>
    <pre>{safe_detail}</pre>
  </div>
</body>
</html>
"""


def show_windows_message(title: str, text: str, icon: int = 0x10) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, title, icon)
    except Exception:  # noqa: BLE001
        append_desktop_log(f"messagebox_failed {text}")


def show_windows_error(title: str, text: str) -> None:
    show_windows_message(title, text, 0x10)


def close_boot_splash(message: str | None = None) -> None:
    try:
        import pyi_splash
    except Exception:  # noqa: BLE001
        return
    try:
        if message:
            pyi_splash.update_text(message)
        pyi_splash.close()
    except Exception:  # noqa: BLE001
        return


def attach_frozen_stdio() -> None:
    if sys.stdout is not None and sys.stderr is not None:
        return
    path = desktop_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = handle
    if sys.stderr is None:
        sys.stderr = handle


def serve_api(host: str, port: int, errors: list[str], bound: list[int]) -> None:
    try:
        append_desktop_log(f"importing_app host={host} port={port}")
        from backend.main import app

        last_err: Exception | None = None
        for candidate in [port, *range(port + 1, port + 20)]:
            try:
                server = build_uvicorn_server(app, host, candidate)
                bound.append(candidate)
                append_desktop_log(f"uvicorn_starting {host}:{candidate}")
                server.run()
                append_desktop_log("uvicorn_exited")
                errors.append("uvicorn exited before the window closed")
                return
            except OSError as exc:
                last_err = exc
                append_desktop_log(f"uvicorn_bind_retry port={candidate} {exc}")
                if bound:
                    bound.clear()
        raise RuntimeError(f"uvicorn bind failed: {last_err}")
    except Exception as exc:  # noqa: BLE001
        text = f"{exc}\n{traceback.format_exc()}"
        append_desktop_log(f"uvicorn_failed {text}")
        errors.append(text)


def resolve_host_port() -> tuple[str, int]:
    from backend.core.config import get_settings

    settings = get_settings()
    host = (settings.host or DEFAULT_HOST).strip() or DEFAULT_HOST
    if host in {"0.0.0.0", "::"}:
        host = DEFAULT_HOST
    preferred = int(settings.port or DEFAULT_PORT)
    return host, preferred


def _keep_server(thread: threading.Thread) -> None:
    try:
        thread.join()
    except KeyboardInterrupt:
        return


def open_in_browser(url: str) -> None:
    import webbrowser

    webbrowser.open(url, new=2, autoraise=True)


def run() -> None:
    try:
        _run_inner()
    except Exception as exc:  # noqa: BLE001
        close_boot_splash()
        detail = f"{exc}\n{traceback.format_exc()}"
        try:
            append_desktop_log(f"run_failed {detail}")
            log_path = desktop_log_path()
        except Exception:  # noqa: BLE001
            log_path = Path("logs/desktop.log")
        show_windows_error(
            "启动失败",
            f"{exc}\n\n请把 EXE 同目录的日志发给开发者：\n{log_path}",
        )
        # Do not re-raise: PyInstaller would show a second English traceback dialog.


def _run_inner() -> None:
    prepare_runtime()
    attach_frozen_stdio()
    install_crash_hooks()
    configure_loopback_access()
    log_path = append_desktop_log(
        f"desktop_boot frozen={getattr(sys, 'frozen', False)} exe={sys.executable} data={DATA_ROOT}"
    )
    from backend.core.config import get_settings
    from backend.core.logging import get_logger

    get_logger("desktop")
    host, preferred = resolve_host_port()
    app_name = get_settings().app_name
    url = window_url(host, preferred)
    errors: list[str] = []
    bound: list[int] = []
    thread = threading.Thread(
        target=serve_api,
        args=(host, preferred, errors, bound),
        daemon=True,
        name="cami-api",
    )
    thread.start()

    def live_url() -> str:
        return window_url(host, bound[0] if bound else preferred)

    def after_ready(window: Any | None) -> None:
        target = live_url()
        ok = wait_for_health(
            target,
            timeout_s=health_timeout_seconds(),
            abort=lambda: bool(errors) and not thread.is_alive(),
        )
        if ok:
            append_desktop_log(f"engine_ready {target}")
            if window is not None:
                try:
                    window.load_url(target + "/?v=zhcn")
                    return
                except Exception as exc:  # noqa: BLE001
                    append_desktop_log(f"load_url_failed {exc}")
            open_in_browser(target + "/?v=zhcn")
            return
        detail = errors[0] if errors else "health check timed out"
        append_desktop_log(f"startup_failed {detail}")
        if window is not None:
            try:
                window.load_html(error_html(target, log_path, detail))
            except Exception as exc:  # noqa: BLE001
                append_desktop_log(f"load_html_failed {exc}")
        show_windows_error(
            "本地引擎没有启动",
            f"请打开日志：\n{log_path}\n\n地址必须是 {target} （必须带端口）\n"
            "若开了 Clash / V2Ray，请开启「绕过局域网 / 回环地址」。",
        )

    close_boot_splash("opening window")
    try:
        import webview

        # Embedded HTML only — never navigate to HTTP until /api/ready succeeds.
        window = webview.create_window(
            f"{app_name} ({host}:{preferred})",
            url=None,
            html=splash_html(url, log_path),
            width=1440,
            height=900,
        )
        webview.start(lambda: after_ready(window), private_mode=True, storage_path=str(DATA_ROOT / "webview-zh"))
        return
    except Exception as exc:  # noqa: BLE001
        append_desktop_log(f"webview_failed {exc}\n{traceback.format_exc()}")

    after_ready(None)
    if thread.is_alive():
        show_windows_message(
            "请在浏览器打开",
            f"本机窗口组件未能启动。引擎若已就绪，请打开：\n{live_url()}\n\n日志：{log_path}",
            0x40,
        )
        _keep_server(thread)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    run()
