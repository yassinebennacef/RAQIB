"""`python -m raqib.serve [--port 8000] [--lan]` - API under /api, built UI at /."""
from __future__ import annotations

import argparse
import os
import socket
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from . import config as C


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def open_when_ready(url: str, timeout: float = 90.0) -> None:
    """Open the browser once /api/health answers (models are loaded at startup)."""
    if os.environ.get("RAQIB_NO_BROWSER") == "1":
        return

    def run() -> None:
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                with urllib.request.urlopen(url + "/api/health", timeout=2) as r:
                    if r.status == 200:
                        webbrowser.open(url)
                        return
            except OSError:
                time.sleep(0.5)
    threading.Thread(target=run, daemon=True).start()


def main() -> None:
    ap = argparse.ArgumentParser(description="Serve the RAQIB API and web app")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--lan", action="store_true", help="listen on all interfaces (open the demo from a phone)")
    ap.add_argument("--open", action="store_true", help="open the browser when the server is ready")
    ap.add_argument("--ui", choices=["v1", "v2"], default=None,
                    help="web app to serve (default: v2 when frontend-v2/dist exists, else v1)")
    args = ap.parse_args()
    if args.ui:
        os.environ["RAQIB_UI"] = args.ui
    C.FRONTEND_DIST = C.frontend_dist()
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    ui = (f"web app ({C.FRONTEND_DIST.parent.name}) + API" if (C.FRONTEND_DIST / "index.html").exists()
          else "API only (no built web app)")
    print(f"RAQIB - {ui}")
    print(f"  Local:   http://127.0.0.1:{args.port}")
    if args.lan:
        print(f"  Network: http://{lan_ip()}:{args.port}")
    print(f"  API docs: http://127.0.0.1:{args.port}/docs")
    if args.open:
        open_when_ready(f"http://127.0.0.1:{args.port}")
    uvicorn.run("raqib.api:app", host=host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
