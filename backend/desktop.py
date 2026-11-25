"""
OpenShorts Studio Pro Native Desktop Shell (pywebview + Uvicorn).
Starts the local FastAPI backend in a background daemon thread and opens a native
desktop window immediately with an Obsidian splash screen and zero-copy file/folder pickers.
Supports --silent (and pythonw.exe windowless execution) with log redirection and
CREATE_NO_WINDOW child-process wrapping on Windows.
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from typing import Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DESKTOP_LOG_PATH = os.path.join(BASE_DIR, "storage", "temp", "desktop_app.log")

SPLASH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    width: 100%; height: 100%;
    background: #09090B;
    color: #F4F4F5;
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", sans-serif;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    user-select: none;
  }
  .splash {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 18px;
    text-align: center;
    padding: 32px;
  }
  .wordmark {
    font-size: 24px;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #FAFAFA;
  }
  .spinner {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 3px solid rgba(139, 92, 246, 0.2);
    border-top-color: #8B5CF6;
    animation: spin 0.8s linear infinite;
  }
  .subtitle {
    font-size: 13px;
    color: #A1A1AA;
    letter-spacing: 0.01em;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
</head>
<body>
  <div class="splash">
    <div class="wordmark">OpenShorts Studio Pro</div>
    <div class="spinner"></div>
    <div class="subtitle">Starting AI Studio Engine...</div>
  </div>
</body>
</html>
"""


def _configure_silent_logging() -> None:
    """Redirects stdout/stderr to storage/temp/desktop_app.log in UTF-8 line-buffered mode."""
    os.makedirs(os.path.dirname(DESKTOP_LOG_PATH), exist_ok=True)
    log_f = open(DESKTOP_LOG_PATH, "a", encoding="utf-8", buffering=1)
    sys.stdout = log_f
    sys.stderr = log_f


def _install_no_window_popen() -> None:
    """Idempotently wraps subprocess.Popen on Windows so child tools never flash a console."""
    if sys.platform != "win32":
        return
    if getattr(subprocess.Popen, "_openshorts_no_window", False):
        return

    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    create_new_console = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
    detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
    orig_popen = subprocess.Popen

    class _NoWindowPopen(orig_popen):
        _openshorts_no_window = True

        def __init__(self, *args, **kwargs):
            flags = int(kwargs.get("creationflags", 0) or 0)
            if not (flags & create_no_window) and not (flags & create_new_console) and not (flags & detached):
                kwargs["creationflags"] = flags | create_no_window
            super().__init__(*args, **kwargs)

    subprocess.Popen = _NoWindowPopen


def _is_openshorts_running(port: int) -> bool:
    """Probes http://127.0.0.1:{port}/api/status with a 0.8s timeout."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/status")
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "online"
    except Exception:
        pass
    return False


class DesktopBridge:
    """JavaScript-to-Python bridge exposed to the pywebview window."""

    def __init__(self) -> None:
        self._window = None

    def attach_window(self, window) -> None:
        """Stores the pywebview Window instance privately (underscore-prefixed)."""
        self._window = window

    def pick_video_file(self) -> str:
        """Opens a native file dialog for video selection and returns the path string or ''."""
        if not self._window:
            return ""
        try:
            import webview

            open_mode = getattr(
                getattr(webview, "FileDialog", None),
                "OPEN",
                getattr(webview, "OPEN_DIALOG", 10),
            )
            result = self._window.create_file_dialog(
                open_mode,
                allow_multiple=False,
                file_types=(
                    "Video Files (*.mp4;*.mkv;*.mov;*.webm;*.ts;*.avi;*.m4v)",
                    "All files (*.*)",
                ),
            )
            if result and len(result) > 0:
                return str(result[0])
        except Exception as e:
            print(f"[WARN] Native video picker error: {e}")
        return ""

    def pick_export_folder(self) -> str:
        """Opens a native folder dialog and returns the selected directory path or ''."""
        if not self._window:
            return ""
        try:
            import webview

            folder_mode = getattr(
                getattr(webview, "FileDialog", None),
                "FOLDER",
                getattr(webview, "FOLDER_DIALOG", 20),
            )
            result = self._window.create_file_dialog(folder_mode)
            if result and len(result) > 0:
                return str(result[0])
        except Exception as e:
            print(f"[WARN] Native folder picker error: {e}")
        return ""

    def is_desktop_app(self) -> bool:
        """Identifies the runtime as the native desktop wrapper."""
        return True


def _shutdown_backend(server, server_thread: Optional[threading.Thread] = None) -> None:
    """Cancels active background jobs and gracefully stops the owned Uvicorn server."""
    try:
        from backend.main import JOB_CANCEL_EVENTS, STATE_LOCK

        with STATE_LOCK:
            for ev in list(JOB_CANCEL_EVENTS.values()):
                try:
                    ev.set()
                except Exception:
                    pass
    except Exception:
        pass

    if server is not None:
        try:
            server.should_exit = True
        except Exception:
            pass

    if server_thread is not None and server_thread.is_alive():
        server_thread.join(timeout=3.0)


def _run_desktop() -> None:
    parser = argparse.ArgumentParser(description="OpenShorts Studio Pro Desktop Launcher")
    parser.add_argument("--lan", action="store_true", help="Bind 0.0.0.0 for LAN mobile access")
    parser.add_argument("--web", action="store_true", help="Open in default web browser instead of pywebview")
    parser.add_argument("--debug", action="store_true", help="Enable WebView DevTools")
    parser.add_argument("--silent", action="store_true", help="Run windowless-safe with log file redirection")
    parser.add_argument("--port", type=int, default=8000, help="HTTP server port (default: 8000)")
    args = parser.parse_args()

    is_silent = bool(args.silent or sys.stdout is None or sys.stderr is None)
    if is_silent:
        _configure_silent_logging()
        _install_no_window_popen()

    if args.lan:
        os.environ["OPENSHORTS_LAN"] = "1"
        host = "0.0.0.0"
    else:
        os.environ["OPENSHORTS_LAN"] = "0"
        host = "127.0.0.1"

    port = int(args.port)
    url = f"http://127.0.0.1:{port}"
    server_holder = {"server": None, "thread": None}

    def _ensure_server_started() -> bool:
        if _is_openshorts_running(port):
            print(f"[INFO] OpenShorts backend already running on {url}; attaching window.")
            return True

        import uvicorn
        from backend.main import app

        config = uvicorn.Config(app, host=host, port=port, log_level="info", use_colors=False)
        srv = uvicorn.Server(config)
        srv.install_signal_handlers = lambda: None
        th = threading.Thread(target=srv.run, daemon=True)
        th.start()
        server_holder["server"] = srv
        server_holder["thread"] = th

        deadline = time.monotonic() + 25.0
        while time.monotonic() < deadline:
            if _is_openshorts_running(port):
                return True
            time.sleep(0.15)
        return False

    def _run_web_fallback(reason: str) -> None:
        if is_silent:
            msg = (
                f"WebView2 / pywebview is unavailable ({reason}).\n\n"
                "Please run run.bat --web to launch OpenShorts Studio Pro in your default web browser."
            )
            print(f"[ERROR] {msg}")
            if sys.platform == "win32":
                try:
                    import ctypes
                    ctypes.windll.user32.MessageBoxW(0, msg, "OpenShorts Studio Pro", 0x30)
                except Exception:
                    pass
            _shutdown_backend(server_holder["server"], server_holder["thread"])
            return

        print(f"[INFO] {reason} Starting server and opening {url} in default browser...")
        _ensure_server_started()
        webbrowser.open(url)
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            _shutdown_backend(server_holder["server"], server_holder["thread"])

    if args.web:
        _run_web_fallback("Browser mode (--web) requested.")
        return

    try:
        import webview
    except Exception as e:
        _run_web_fallback(f"pywebview unavailable ({e}).")
        return

    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
        bridge = DesktopBridge()
        win = webview.create_window(
            "OpenShorts Studio Pro",
            html=SPLASH_HTML,
            js_api=bridge,
            width=1380,
            height=860,
            min_size=(1024, 680),
            background_color="#09090B",
        )
        bridge.attach_window(win)

        def on_ready(window) -> None:
            if _ensure_server_started():
                window.load_url(url)
            else:
                err_html = """<!DOCTYPE html>
<html><body style="background:#09090B;color:#F4F4F5;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
<div style="max-width:460px;text-align:center;padding:24px;">
  <h2 style="color:#F87171;margin-bottom:10px;">Failed to Start AI Studio Engine</h2>
  <p style="color:#A1A1AA;font-size:13px;line-height:1.5;">
    The local server did not respond within 25 seconds.<br>
    Check <code>storage/temp/desktop_app.log</code> or run <code>run.bat</code> for details.
  </p>
</div></body></html>"""
                window.load_html(err_html)

        try:
            webview.start(on_ready, win, debug=args.debug)
        finally:
            _shutdown_backend(server_holder["server"], server_holder["thread"])
    except Exception as e:
        _run_web_fallback(f"Native WebView failed to start ({e}).")


def main() -> None:
    is_silent = ("--silent" in sys.argv) or (sys.stdout is None) or (sys.stderr is None)
    try:
        _run_desktop()
    except Exception as e:
        if is_silent:
            try:
                _configure_silent_logging()
                traceback.print_exc()
            except Exception:
                pass
            if sys.platform == "win32":
                try:
                    import ctypes
                    ctypes.windll.user32.MessageBoxW(
                        0,
                        f"OpenShorts failed to start:\n{e}\n\nSee storage\\temp\\desktop_app.log or run run.bat for details.",
                        "OpenShorts Studio Pro",
                        0x10,
                    )
                except Exception:
                    pass
        else:
            raise


if __name__ == "__main__":
    main()
