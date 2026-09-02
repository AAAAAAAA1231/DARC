"""Desktop entry: local API + pywebview window. No live trading.

Windows + PyInstaller note: never call ``uvicorn.run()`` from a background
thread. That helper installs signal handlers, which fails or hangs off the
main thread and leaves Edge on ERR_CONNECTION_REFUSED.
"""

from __future__ import annotations

import html
import json
import multiprocessing
import socket
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from backend.core.paths import DATA_ROOT, prepare_runtime

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
FROZEN_HEALTH_TIMEOUT_S = 180.0
DEV_HEALTH_TIMEOUT_S = 60.0
HEALTH_POLL_S = 0.5


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
    # Background thread must not touch process-wide signal handlers.
    server.install_signal_handlers = lambda: None
    return server


def wait_for_health(
    url: str,
    timeout_s: float,
    interval_s: float = HEALTH_POLL_S,
    abort: Callable[[], bool] | None = None,
) -> bool:
    deadline = time.monotonic() + timeout_s
    health = url.rstrip("/") + "/api/health"
    last_note = 0.0
    while time.monotonic() < deadline:
        if abort and abort():
            append_desktop_log("health_wait_aborted")
            return False
        try:
            with urllib.request.urlopen(health, timeout=2) as response:
                if 200 <= response.status < 300:
                    append_desktop_log(f"health_ok {health}")
                    return True
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            now = time.monotonic()
            if now - last_note >= 10:
                append_desktop_log(f"health_wait {health} still_down {exc}")
                last_note = now
        time.sleep(interval_s)
    append_desktop_log(f"health_timeout {health} after {timeout_s}s")
    return False


def splash_html(url: str, log_path: Path) -> str:
    safe_url = html.escape(url, quote=True)
    js_url = json.dumps(url.rstrip("/"))
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
    <p>首次打开可能需要 1–3 分钟（解压模型库）。就绪后会自动进入终端。</p>
    <p>请等待本窗口跳转。不要在 Edge 里单独打开 <code>127.0.0.1</code>（没有端口会连不上）。正确地址是 <code>{safe_url}</code>。</p>
    <p>日志：<code>{safe_log}</code></p>
    <p id="st">正在检测 /api/health …</p>
  </div>
  <script>
    const base = {js_url};
    async function poll() {{
      try {{
        const res = await fetch(base + "/api/health", {{ cache: "no-store" }});
        if (res.ok) {{ location.replace(base + "/"); return; }}
      }} catch (e) {{}}
      setTimeout(poll, 500);
    }}
    poll();
  </script>
</body>
</html>
"""


def error_html(url: str, log_path: Path, detail: str) -> str:
    safe_url = html.escape(url)
    safe_log = html.escape(str(log_path))
    safe_detail = html.escape(detail or "本地 API 没有在时限内响应 /api/health。")
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
    <p>这就是 Edge 提示「127.0.0.1 拒绝连接 / ERR_CONNECTION_REFUSED」的原因：本机没有进程在监听。</p>
    <p>预期地址：<code>{safe_url}</code>（必须带端口，不要只打开 127.0.0.1）。</p>
    <p>请把下面的日志发给开发者：<code>{safe_log}</code></p>
    <pre>{safe_detail}</pre>
  </div>
</body>
</html>
"""


def show_windows_error(title: str, text: str) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
    except Exception:  # noqa: BLE001
        append_desktop_log(f"messagebox_failed {text}")


def serve_api(host: str, port: int, errors: list[str]) -> None:
    try:
        append_desktop_log(f"importing_app host={host} port={port}")
        from backend.main import app

        server = build_uvicorn_server(app, host, port)
        append_desktop_log(f"uvicorn_starting {host}:{port}")
        server.run()
        append_desktop_log("uvicorn_exited")
        errors.append("uvicorn exited before the window closed")
    except Exception as exc:  # noqa: BLE001
        text = f"{exc}\n{traceback.format_exc()}"
        append_desktop_log(f"uvicorn_failed {text}")
        errors.append(text)


def resolve_bind() -> tuple[str, int]:
    from backend.core.config import get_settings

    settings = get_settings()
    host = (settings.host or DEFAULT_HOST).strip() or DEFAULT_HOST
    if host in {"0.0.0.0", "::"}:
        host = DEFAULT_HOST
    preferred = int(settings.port or DEFAULT_PORT)
    port = pick_listen_port(host, preferred)
    if port != preferred:
        append_desktop_log(f"port_in_use preferred={preferred} using={port}")
    return host, port


def run() -> None:
    prepare_runtime()
    install_crash_hooks()
    log_path = append_desktop_log(
        f"desktop_boot frozen={getattr(sys, 'frozen', False)} exe={sys.executable} data={DATA_ROOT}"
    )
    try:
        from backend.core.config import get_settings
        from backend.core.logging import get_logger

        get_logger("desktop")
        host, port = resolve_bind()
        app_name = get_settings().app_name
    except Exception as exc:  # noqa: BLE001
        detail = f"{exc}\n{traceback.format_exc()}"
        append_desktop_log(f"config_failed {detail}")
        show_windows_error("启动失败", f"配置加载失败。\n日志：{log_path}\n\n{exc}")
        raise

    url = f"http://{host}:{port}"
    errors: list[str] = []
    thread = threading.Thread(target=serve_api, args=(host, port, errors), daemon=True, name="cami-api")
    thread.start()

    splash = splash_html(url, log_path)
    import webview

    window = webview.create_window(app_name, html=splash, width=1440, height=900)

    def after_gui() -> None:
        ok = wait_for_health(
            url,
            timeout_s=health_timeout_seconds(),
            abort=lambda: bool(errors) and not thread.is_alive(),
        )
        if ok:
            append_desktop_log(f"opening_window {url}")
            try:
                window.load_url(url)
            except Exception as exc:  # noqa: BLE001
                append_desktop_log(f"load_url_failed {exc}")
            return
        detail = errors[0] if errors else "health check timed out"
        append_desktop_log(f"startup_failed {detail}")
        try:
            window.load_html(error_html(url, log_path, detail))
        except Exception as exc:  # noqa: BLE001
            append_desktop_log(f"load_html_failed {exc}")
        show_windows_error(
            "本地引擎没有启动",
            f"浏览器因此会显示「拒绝连接」。\n请打开日志：\n{log_path}\n\n地址必须是 {url}",
        )

    webview.start(after_gui)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    run()
