"""Backfill the historical NASA FIRMS record through the area API.

Why this script exists
----------------------
FIRMS publishes only rolling 24 h / 48 h / 7 d files without a key. The full
archive (MODIS since November 2000, VIIRS since 2012) is available in two ways:

1. The FIRMS Archive Download page (manual, per request, needs an Earthdata
   login) - upload those CSVs through the Data Explorer page.
2. The FIRMS area API (automated) - requires a free MAP_KEY, which is emailed
   instantly: https://firms.modaps.eosdis.nasa.gov/api/map_key/

This script implements (2). It requests contiguous 5-day windows (the API limit)
for one area, per sensor, and then ingests everything in a single batch so the
analysis tables are rebuilt once.

Example
-------
    python scripts/fetch_firms_api.py \
        --map-key $env:FIRMS_MAP_KEY \
        --region sahel_belt \
        --start 2000-11-01

The API allows 5,000 transactions per 10 minutes; a multi-day request counts as
several transactions, so a 25-year backfill is a long-running job. Progress is
printed per month and the process can be stopped and resumed: files already on
disk are skipped.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import config, db, firms, geo, ingest, regions  # noqa: E402

# FIRMS "standard processing" lags near-real-time by roughly five months.
SP_LAG_DAYS = 150


def daterange_windows(start: date, end: date, size: int) -> list[tuple[date, int]]:
    windows = []
    cursor = start
    while cursor <= end:
        remaining = (end - cursor).days + 1
        length = min(size, remaining)
        windows.append((cursor, length))
        cursor += timedelta(days=length)
    return windows


def resolve_area(args) -> geo.AOI:
    if args.region:
        aoi = regions.region_aoi(args.region)
        if aoi is None:
            raise SystemExit(f"Unknown region '{args.region}'. Known: {', '.join(regions.REGIONS)}")
        return aoi
    if args.bbox:
        parts = [part.strip() for part in str(args.bbox).replace(" ", ",").split(",") if part.strip()]
        if len(parts) != 4:
            raise SystemExit("--bbox needs four comma-separated numbers: west,south,east,north")
        try:
            values = [float(part) for part in parts]
        except ValueError as exc:
            raise SystemExit(f"--bbox values must be numbers: {exc}") from exc
        return geo.normalize_aoi({"bbox": values, "name": "API backfill area"})
    raise SystemExit("Provide --region or --bbox west,south,east,north")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill FIRMS history via the area API")
    parser.add_argument("--map-key", default=os.environ.get("FIRMS_MAP_KEY", ""),
                        help="FIRMS MAP_KEY (or set the FIRMS_MAP_KEY environment variable)")
    parser.add_argument("--region", help="preset region id (see backend/app/regions.py)")
    parser.add_argument("--bbox", help="west,south,east,north")
    parser.add_argument("--start", default="2000-11-01")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--sensors", nargs="*", default=["modis", "viirs_snpp", "viirs_noaa20", "viirs_noaa21"])
    parser.add_argument("--mode", choices=["auto", "sp", "nrt"], default="auto")
    parser.add_argument("--out", default=str(config.RAW_DIR / "api"))
    parser.add_argument("--sleep", type=float, default=0.15, help="seconds between requests")
    parser.add_argument("--retries", type=int, default=4,
                        help="attempts per window when FIRMS throttles the key")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-availability", action="store_true")
    parser.add_argument("--no-ingest", action="store_true", help="download only, do not ingest")
    args = parser.parse_args()

    if not args.map_key:
        raise SystemExit(
            "A NASA FIRMS MAP_KEY is required.\n"
            "Get one free at https://firms.modaps.eosdis.nasa.gov/api/map_key/ then either\n"
            "  set FIRMS_MAP_KEY=... in .env, or pass --map-key YOURKEY"
        )

    if args.list_availability:
        for row in firms.fetch_data_availability(args.map_key):
            print(f"  {row.get('data_id', '?'):<18} {row.get('min_date', '?')} .. {row.get('max_date', '?')}")
        return 0

    aoi = resolve_area(args)
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    today = date.today()
    total_windows = 0
    plan: list[tuple[str, str, date, int]] = []
    for sensor in args.sensors:
        info = firms.API_SOURCES.get(sensor)
        if not info:
            print(f"  ! unknown sensor {sensor}, skipping")
            continue
        min_from = config.SENSORS[sensor]["records_from"]
        sensor_start = max(start, date.fromisoformat(min_from))
        for window_start, length in daterange_windows(sensor_start, end, 5):
            sp_cutoff = today - timedelta(days=SP_LAG_DAYS)
            if args.mode == "sp":
                source = info["sp"]
                if window_start > sp_cutoff:
                    continue
            elif args.mode == "nrt":
                source = info["nrt"]
            else:
                source = info["sp"] if window_start <= sp_cutoff else info["nrt"]
            plan.append((sensor, source, window_start, length))
            total_windows += 1

    print(f"[FIRETRACK] area: {aoi.name}  bbox={aoi.bbox}")
    print(f"[FIRETRACK] {start} -> {end} · {total_windows} API windows")
    if args.dry_run:
        for sensor, source, window_start, length in plan[:10]:
            print(f"  {sensor:<14} {source:<18} {window_start} +{length}d")
        print("  ... (dry run, nothing downloaded)")
        return 0

    db.init_db()
    failures: list[tuple[str, str, str]] = []
    downloaded = 0
    rows_total = 0
    queried: dict[str, list[str]] = {}
    consecutive_key_failures = 0

    started = time.time()
    for index, (sensor, source, window_start, length) in enumerate(plan, start=1):
        tag = f"{sensor}_{source}_{window_start.isoformat()}_{length}d"
        path = out_dir / f"{tag}.csv"
        queried.setdefault(sensor, []).extend(
            (window_start + timedelta(days=offset)).isoformat() for offset in range(length)
        )
        if path.exists() and path.stat().st_size > 0:
            rows_total += max(0, path.read_text(encoding="utf-8", errors="replace").count("\n") - 1)
            continue

        payload = None
        for attempt in range(1, args.retries + 1):
            try:
                payload = firms.fetch_area_csv(args.map_key, source, aoi.bbox,
                                               window_start.isoformat(), length)
                consecutive_key_failures = 0
                break
            except firms.FirmsApiError as exc:
                message = str(exc)
                # FIRMS reports rate-limit throttling with the same body it uses
                # for a bad key, so retry with backoff before believing it.
                if "MAP_KEY" in message and attempt < args.retries:
                    wait = 15 * attempt
                    print(f"  ~ throttled at {window_start} ({sensor}); waiting {wait}s "
                          f"[attempt {attempt}/{args.retries}]")
                    time.sleep(wait)
                    continue
                payload = None
                if "MAP_KEY" in message:
                    consecutive_key_failures += 1
                failures.append((sensor, window_start.isoformat(), message))
                print(f"  ! {sensor} {window_start} failed: {message}")
                break

        if payload is None:
            if consecutive_key_failures >= 3:
                print("[FIRETRACK] the key is being rejected repeatedly; stopping. "
                      "Re-run later to resume from the files already downloaded.")
                break
            continue

        path.write_text(payload, encoding="utf-8")
        line_count = max(0, payload.count("\n") - 1)
        rows_total += line_count
        downloaded += 1
        if index % 25 == 0 or index == len(plan):
            elapsed = time.time() - started
            rate = index / elapsed * 60 if elapsed > 0 else 0
            eta = (len(plan) - index) / max(0.01, rate) if rate > 0 else 0
            print(f"  {index}/{len(plan)} windows · {rows_total:,} rows · "
                  f"{rate:.0f} win/min · ETA {eta:.0f} min")
        time.sleep(args.sleep)

    print(f"[FIRETRACK] downloaded {downloaded} new files, {rows_total:,} CSV rows")
    if failures:
        print(f"[FIRETRACK] {len(failures)} window(s) failed; rerun to retry them")

    if args.no_ingest:
        print("[FIRETRACK] skipping ingest (--no-ingest)")
        return 0

    files = sorted(out_dir.glob("*.csv"))
    if not files:
        print("[FIRETRACK] no files to ingest")
        return 0

    # Standard-processing and near-real-time windows are ingested as separate
    # batches so the provenance label stays exact: a mixed batch would have to
    # be called provisional, which would understate 25 years of science data.
    sp_files = [p for p in files if "_SP_" in p.name]
    nrt_files = [p for p in files if "_NRT_" in p.name]
    print(f"[FIRETRACK] ingesting {len(sp_files)} SP and {len(nrt_files)} NRT file(s)...")

    # NASA is the authority on which dates each product actually delivered.
    # These windows bound the availability calendar, so a sensor that stopped
    # delivering is not counted as observing.
    try:
        availability = firms.fetch_data_availability(args.map_key)
        stored = ingest.store_product_windows(availability)
        print(f"[FIRETRACK] stored {stored} NASA delivery windows")
    except firms.FirmsApiError as exc:
        print(f"[FIRETRACK] could not refresh delivery windows: {exc}")

    total_kept = total_dup = total_rejected = 0
    for batch, kind, label in (
        (sp_files, "api_sp", "standard processing"),
        (nrt_files, "api_nrt", "near real time"),
    ):
        if not batch:
            continue
        result = ingest.ingest_paths(
            batch,
            kind=kind,
            description=f"FIRMS area-API backfill ({label}) {aoi.name} {start}..{end}",
        )
        total_kept += result.rows_kept
        total_dup += result.rows_duplicate
        total_rejected += result.rows_rejected
        print(f"  {label}: {result.rows_kept:,} new · {result.rows_duplicate:,} duplicates · "
              f"{result.rows_rejected:,} rejected")

    # A window that returned no detections is still evidence the sensor observed
    # the area, so availability is recorded explicitly for every queried date -
    # but only inside that sensor's NASA delivery window.
    for sensor, days in queried.items():
        ingest.register_observation_days(sensor, days)

    trimmed = ingest.bound_sensor_days()
    if trimmed.get("trimmed"):
        print(f"[FIRETRACK] removed {trimmed['trimmed']} observation day(s) outside "
              f"NASA delivery windows (detections untouched)")

    print(f"[FIRETRACK] done: {total_kept:,} new detections "
          f"({total_dup:,} duplicates skipped, {total_rejected:,} rejected)")
    summary = ingest.summary()
    print(f"[FIRETRACK] record now: {summary['min_date']} .. {summary['max_date']} "
          f"· {summary['detections']:,} detections")
    return 0


if __name__ == "__main__":
    sys.exit(main())
