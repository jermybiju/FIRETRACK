"""Reconcile the availability calendar with NASA's reported delivery windows.

Fixes the class of bug where a sensor that has stopped delivering is still
counted as "observing" on later dates (its API windows simply return no rows).

What it does
  1. Reads the FIRMS data_availability table with your MAP_KEY.
  2. Stores the reported date range for every FIRMS fire product.
  3. Deletes availability rows that fall outside those ranges.

What it never does
  * It never deletes detections. Historical observations are preserved exactly.
  * It never touches a sensor that has no reported window.

    python scripts/repair_availability.py             # dry run: show what would go
    python scripts/repair_availability.py --apply     # perform the change
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import config, db, firms, ingest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="actually delete stale rows")
    parser.add_argument("--window", default="", help="comma list, e.g. 2026-11-01,2026-11-30 (display only)")
    args = parser.parse_args()

    db.init_db()
    key = config.FIRMS_MAP_KEY
    if not key:
        print("FIRMS_MAP_KEY is not set; cannot read NASA availability. Add it to .env.")
        return 1

    availability = firms.fetch_data_availability(key)
    stored = ingest.store_product_windows(availability)
    print(f"stored {stored} product windows from NASA")

    before = {r["sensor"]: r["n"] for r in db.query(
        "SELECT sensor, COUNT(*) n FROM sensor_days WHERE observed = 1 GROUP BY sensor")}
    detections_before = db.scalar("SELECT COUNT(*) FROM detections", default=0)

    report = ingest.bound_sensor_days(dry_run=not args.apply)
    print()
    print(f"{'sensor':<15}{'window':<26}{'removed':>9}{'days before':>13}{'days after':>12}")
    for row in report["detail"]:
        lo, hi = row["window"]
        after = row.get("days_after", before.get(row["sensor"], 0))
        print(f"{row['sensor']:<15}{lo + ' .. ' + hi:<26}{row['removed']:>9}"
              f"{before.get(row['sensor'], 0):>13}{after:>12}")
    print()

    if not args.apply:
        print(f"DRY RUN: {report['trimmed']} stale availability day(s) would be removed.")
        print("Run again with --apply to perform it (a backup is still your responsibility).")
        return 0

    after = {r["sensor"]: r["n"] for r in db.query(
        "SELECT sensor, COUNT(*) n FROM sensor_days WHERE observed = 1 GROUP BY sensor")}
    detections_after = db.scalar("SELECT COUNT(*) FROM detections", default=0)
    print(f"removed {report['trimmed']} availability day(s)")
    print(f"detections before={detections_before:,} after={detections_after:,} "
          f"(unchanged: {detections_before == detections_after})")
    for sensor in sorted(set(before) | set(after)):
        print(f"  {sensor:<15} {before.get(sensor, 0):>6} -> {after.get(sensor, 0):>6}")
    print()
    print("Restart the server so cached series are rebuilt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
