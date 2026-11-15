#!/usr/bin/env python3
"""FIRETRACK launcher.

Works from any directory and needs no PYTHONPATH:

    python run.py                 # http://127.0.0.1:8000, or the next free port
    python run.py --port 9000
    python run.py --help

Two things this file is responsible for:

1. Putting ``backend/`` on the import path, so ``python run.py`` works anywhere.
2. Picking a usable port. On Windows it is very easy to leave an old server
   running (a closed terminal does not always kill it), and the resulting
   "only one usage of each socket address" error tells a beginner nothing.
   If the requested port is taken and no port was chosen explicitly, the next
   free port is used and reported.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"

if not BACKEND.exists():
    raise SystemExit(f"backend/ not found next to run.py (looked in {BACKEND})")

FIRST_PORT = 8000
LAST_PORT = 8020


def is_free(host: str, port: int) -> bool:
    """True when we can bind the port right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
            return True
        except OSError:
            return False


def resolve_port(argv: list[str], host: str) -> tuple[list[str], int, bool]:
    """Return (argv with a port, chosen port, whether it was auto-selected)."""
    for index, item in enumerate(argv):
        if item == "--port" and index + 1 < len(argv):
            return argv, int(argv[index + 1]), False
        if item.startswith("--port="):
            return argv, int(item.split("=", 1)[1]), False
    if os.environ.get("FIRETRACK_PORT"):
        return argv, int(os.environ["FIRETRACK_PORT"]), False

    for port in range(FIRST_PORT, LAST_PORT + 1):
        if is_free(host, port):
            return argv + ["--port", str(port)], port, port != FIRST_PORT
    raise SystemExit(
        f"No free port between {FIRST_PORT} and {LAST_PORT}. "
        "Close the other servers or pass --port."
    )


def main() -> int:
    sys.path.insert(0, str(BACKEND))
    from app.main import main as server_main  # noqa: PLC0415 - after the path setup

    argv = sys.argv[1:]
    host = "127.0.0.1"
    for index, item in enumerate(argv):
        if item == "--host" and index + 1 < len(argv):
            host = argv[index + 1]
        elif item.startswith("--host="):
            host = item.split("=", 1)[1]

    argv, port, auto = resolve_port(argv, host)
    if auto:
        print(f"[FIRETRACK] port {FIRST_PORT} is already in use - using {port} instead")
        print(f"[FIRETRACK] (stop the old server to get port {FIRST_PORT} back: "
              f"Get-NetTCPConnection -LocalPort {FIRST_PORT} | "
              f"Select-Object -ExpandProperty OwningProcess -Unique | "
              f"ForEach-Object {{ Stop-Process -Id $_ -Force }})")

    # app.main parses sys.argv itself, so the chosen port is passed that way.
    sys.argv = [sys.argv[0], *argv]
    return server_main()


if __name__ == "__main__":
    sys.exit(main())
