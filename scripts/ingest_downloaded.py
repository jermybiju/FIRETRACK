"""Ingest every FIRMS CSV that scripts/fetch_firms_api.py has downloaded.

The downloader caches one CSV per 5-day window under ``data/raw/api``. This
script ingests them as two separate batches - standard processing (science) and
near-real-time (provisional) - so the provenance label on each batch is exact
instead of averaging the two qualities into one.

Run it after an interrupted backfill, or any time you want to pick up files that
were downloaded but not yet loaded.

    python scripts/ingest_downloaded.py
    python scripts/ingest_downloaded.py --dir data/raw/api
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import config, db, ingest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest downloaded FIRMS area-API files")
    parser.add_argument("--dir", default=str(config.RAW_DIR / "api"))
    args = parser.parse_args()

    directory = Path(args.dir)
    if not directory.exists():
        print(f"[FIRETRACK] no folder at {directory}; run scripts/fetch_firms_api.py first")
        return 1

    files = sorted(directory.glob("*.csv"))
    if not files:
        print(f"[FIRETRACK] no CSV files in {directory}")
        return 1

    sp_files = [p for p in files if "_SP_" in p.name]
    nrt_files = [p for p in files if "_NRT_" in p.name]
    other = [p for p in files if p not in sp_files and p not in nrt_files]
    print(f"[FIRETRACK] {len(files)} files: {len(sp_files)} SP, {len(nrt_files)} NRT, {len(other)} other")

    db.init_db()
    started = time.time()
    totals = {"kept": 0, "duplicate": 0, "rejected": 0}

    for batch, kind, label in (
        (sp_files, "api_sp", "standard processing"),
        (nrt_files, "api_nrt", "near real time"),
        (other, "archive", "unclassified"),
    ):
        if not batch:
            continue
        print(f"[FIRETRACK] ingesting {len(batch)} {label} file(s)...")
        result = ingest.ingest_paths(
            batch,
            kind=kind,
            description=f"FIRMS area-API backfill ({label}), {len(batch)} files",
        )
        totals["kept"] += result.rows_kept
        totals["duplicate"] += result.rows_duplicate
        totals["rejected"] += result.rows_rejected
        print(f"  {result.rows_kept:,} new · {result.rows_duplicate:,} duplicates · "
              f"{result.rows_rejected:,} rejected")

    summary = ingest.summary()
    print()
    print(f"[FIRETRACK] {totals['kept']:,} new detections in {time.time() - started:.0f}s")
    print(f"[FIRETRACK] record now: {summary['min_date']} .. {summary['max_date']} · "
          f"{summary['detections']:,} detections")
    print(f"[FIRETRACK] database: {db.db_path()} "
          f"({db.db_path().stat().st_size / 1e6:.0f} MB)")
    print("[FIRETRACK] restart the server, then pick the region in the area selector.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
