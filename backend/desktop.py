"""
OpenShorts Studio Pro Native Desktop Shell (pywebview + Uvicorn).
Starts the local FastAPI backend in a background daemon thread and opens a native
desktop window with zero-copy file/folder pickers, falling back cleanly to the
default web browser when --web is passed or WebView2/pywebview is unavailable.
"""

import argparse
import json
import os
import sys
import threading
import time
import urllib.request
import webbrowser
from typing import Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


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


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenShorts Studio Pro Desktop Launcher")
    parser.add_argument("--lan", action="store_true", help="Bind 0.0.0.0 for LAN mobile access")
    parser.add_argument("--web", action="store_true", help="Open in default web browser instead of pywebview")
    parser.add_argument("--debug", action="store_true", help="Enable WebView DevTools")
    parser.add_argument("--port", type=int, default=8000, help="HTTP server port (default: 8000)")
    args = parser.parse_args()

    if args.lan:
        os.environ["OPENSHORTS_LAN"] = "1"
        host = "0.0.0.0"
    else:
        os.environ["OPENSHORTS_LAN"] = "0"
        host = "127.0.0.1"

    port = int(args.port)
    server = None
    server_thread: Optional[threading.Thread] = None

    if _is_openshorts_running(port):
        print(f"[INFO] OpenShorts backend already running on http://127.0.0.1:{port}; attaching window.")
    else:
        import uvicorn
        from backend.main import app

        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None

        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()

        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if _is_openshorts_running(port):
                break
            time.sleep(0.15)

    url = f"http://127.0.0.1:{port}"

    def _run_web_fallback(reason: str) -> None:
        print(f"[INFO] {reason} Opening {url} in default browser...")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            _shutdown_backend(server, server_thread)

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
            url,
            js_api=bridge,
            width=1380,
            height=860,
            min_size=(1024, 680),
            background_color="#09090B",
        )
        bridge.attach_window(win)
        try:
            webview.start(debug=args.debug)
        finally:
            _shutdown_backend(server, server_thread)
    except Exception as e:
        _run_web_fallback(f"Native WebView failed to start ({e}).")


if __name__ == "__main__":
    main()
