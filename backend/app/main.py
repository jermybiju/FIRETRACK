"""Entry point: ``python -m app.main``.

Starts the FIRETRACK API and serves the built web interface from the same
process, so one command runs the whole application.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from . import config, db, ingest


def bootstrap(verbose: bool = True) -> None:
    """Prepare the database, ingesting the bundled snapshot on first run."""
    db.init_db()
    if db.is_empty():
        files = ingest.snapshot_files()
        if files:
            if verbose:
                print(f"[FIRETRACK] First run: loading {len(files)} NASA FIRMS snapshot file(s)...")
            started = time.time()
            results = ingest.ingest_snapshot_dir()
            if verbose:
                for item in results:
                    print(
                        f"  {item['files'][0]:32s} {item['rows_kept']:>8,} rows "
                        f"({item['min_date']} .. {item['max_date']})"
                    )
                print(f"[FIRETRACK] Ready in {time.time() - started:.1f}s")
        elif verbose:
            print(
                "[FIRETRACK] No hotspot records found.\n"
                "  Run: python scripts/download_firms_snapshot.py\n"
                "  or import a FIRMS archive file from the Data Explorer page."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the FIRETRACK server")
    parser.add_argument("--host", default=os.environ.get("FIRETRACK_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("FIRETRACK_PORT", "8000")))
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes (development)")
    parser.add_argument("--no-ingest", action="store_true", help="skip first-run ingestion")
    args = parser.parse_args()

    if not args.no_ingest:
        bootstrap()

    from .api import app, mount_frontend

    mount_frontend()

    import uvicorn

    print(f"[FIRETRACK] http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
