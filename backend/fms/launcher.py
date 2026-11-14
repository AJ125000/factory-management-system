"""Desktop launcher for the hub (what FMS.exe runs on the owner's laptop).

- Starts the hub server in the background and shows an icon in the system tray
  with "Open FMS", "Open data folder" and "Quit".
- Opens FMS in its own window (Microsoft Edge "app" mode: no tabs or address bar),
  falling back to the default browser.
- Only one copy runs: starting FMS again just opens the window of the running one.

    FMS.exe [--port 8765] [--data-dir PATH] [--no-tray] [--no-window]
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from dataclasses import replace
from pathlib import Path

from .config import Settings

log = logging.getLogger("fms.launcher")

MUTEX_NAME = "FMSHubMutex"  # also used by the installer to ask the user to close FMS
EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def hub_url(settings: Settings) -> str:
    return f"http://{settings.host}:{settings.port}/"


def hub_running(settings: Settings, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(f"{hub_url(settings)}api/health", timeout=timeout) as resp:
            return resp.status == 200
    except OSError:
        return False


def open_window(url: str) -> None:
    """Open FMS in its own window if Edge is available, else in the default browser."""
    edge = next((p for p in EDGE_PATHS if Path(p).is_file()), None)
    if edge:
        subprocess.Popen([edge, f"--app={url}"], close_fds=True)
    else:
        webbrowser.open(url)


def open_folder(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606 - opening Explorer
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def claim_single_instance() -> bool:
    """Windows: a named mutex marks FMS as running (the installer checks it too)."""
    if sys.platform != "win32":
        return True
    import ctypes

    ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)  # type: ignore[attr-defined]
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


class HubServer:
    """The FastAPI hub running in a background thread, stoppable from the tray."""

    def __init__(self, settings: Settings) -> None:
        import uvicorn

        from .main import create_app

        config = uvicorn.Config(
            create_app(settings), host=settings.host, port=settings.port, log_config=None
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, name="fms-hub", daemon=True)

    def start(self, wait: float = 20.0) -> bool:
        self.thread.start()
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if self.server.started:
                return True
            if not self.thread.is_alive():
                return False
            time.sleep(0.1)
        return False

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)


def run_tray(settings: Settings, hub: HubServer) -> None:
    """Show the tray icon until the owner chooses Quit."""
    import pystray
    from PIL import Image

    icon_path = Path(__file__).parent / "static" / "icons" / "icon-192.png"
    image = Image.open(icon_path) if icon_path.is_file() else Image.new("RGB", (64, 64), "teal")

    def quit_fms(icon, _item):
        hub.stop()
        icon.stop()

    icon = pystray.Icon(
        "FMS",
        image,
        "Factory Management System",
        menu=pystray.Menu(
            pystray.MenuItem("Open FMS", lambda: open_window(hub_url(settings)), default=True),
            pystray.MenuItem("Open data folder", lambda: open_folder(settings.data_dir)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit FMS", quit_fms),
        ),
    )
    icon.run()


def parse_args(argv: list[str] | None = None) -> tuple[Settings, argparse.Namespace]:
    defaults = Settings()
    parser = argparse.ArgumentParser(prog="FMS", description="Factory Management System")
    parser.add_argument("--port", type=int, default=defaults.port)
    parser.add_argument("--data-dir", type=Path, default=defaults.data_dir)
    parser.add_argument("--no-tray", action="store_true", help="run without the tray icon")
    parser.add_argument("--no-window", action="store_true", help="don't open the FMS window")
    args = parser.parse_args(argv)
    return replace(defaults, port=args.port, data_dir=args.data_dir), args


def main(argv: list[str] | None = None) -> int:
    from .logging_setup import configure_logging

    settings, args = parse_args(argv)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(settings.log_dir)

    # Already running (e.g. started at login): just bring up the window.
    if not claim_single_instance() or hub_running(settings):
        log.info("FMS is already running; opening its window")
        if not args.no_window:
            open_window(hub_url(settings))
        return 0

    hub = HubServer(settings)
    if not hub.start():
        log.error("The FMS hub failed to start (is port %s in use?)", settings.port)
        return 1
    log.info("FMS hub running at %s", hub_url(settings))
    if not args.no_window:
        open_window(hub_url(settings))

    if args.no_tray:
        try:
            while hub.thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            hub.stop()
    else:
        run_tray(settings, hub)
    return 0


if __name__ == "__main__":
    sys.exit(main())
