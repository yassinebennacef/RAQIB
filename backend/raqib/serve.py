"""`python -m raqib.serve [--port 8000] [--lan]` - API under /api, built UI at /."""
from __future__ import annotations

import argparse
import socket

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


def main() -> None:
    ap = argparse.ArgumentParser(description="Serve the RAQIB API and web app")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--lan", action="store_true", help="listen on all interfaces (open the demo from a phone)")
    args = ap.parse_args()
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    ui = "web app + API" if (C.FRONTEND_DIST / "index.html").exists() else "API only (frontend/dist not built)"
    print(f"RAQIB - {ui}")
    print(f"  Local:   http://127.0.0.1:{args.port}")
    if args.lan:
        print(f"  Network: http://{lan_ip()}:{args.port}")
    print(f"  API docs: http://127.0.0.1:{args.port}/docs")
    uvicorn.run("raqib.api:app", host=host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
