"""Download the key-free NASA FIRMS global near-real-time snapshot.

NASA FIRMS publishes rolling global CSV files (24 h / 48 h / 7 d) at
https://firms.modaps.eosdis.nasa.gov/data/active_fire/ with no API key. These
are the only FIRMS products that are downloadable without a MAP_KEY or an
Earthdata login, so they are what the bundled demo snapshot is built from.

They are REAL observations, but they are NRT (provisional) and cover only a
short window. For the full historical record since 2000 use one of:

    python scripts/fetch_firms_api.py --map-key ...    (area API, 5-day chunks)
    upload a FIRMS Archive Download .zip/.csv via the app (science quality)

Usage:
    python scripts/download_firms_snapshot.py [--out data/raw/snapshot]

Every file is written with a sidecar *.meta.json recording the URL, download
time, byte size and SHA-256 so provenance is reproducible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

BASE = "https://firms.modaps.eosdis.nasa.gov/data/active_fire"

# (friendly sensor id, FIRMS product folder, file stem)
PRODUCTS = [
    ("modis", "modis-c6.1/csv", "MODIS_C6_1_Global_7d"),
    ("modis", "modis-c6.1/csv", "MODIS_C6_1_Global_48h"),
    ("viirs_snpp", "suomi-npp-viirs-c2/csv", "SUOMI_VIIRS_C2_Global_7d"),
    ("viirs_snpp", "suomi-npp-viirs-c2/csv", "SUOMI_VIIRS_C2_Global_48h"),
    ("viirs_noaa20", "noaa-20-viirs-c2/csv", "J1_VIIRS_C2_Global_7d"),
    ("viirs_noaa20", "noaa-20-viirs-c2/csv", "J1_VIIRS_C2_Global_48h"),
    ("viirs_noaa21", "noaa-21-viirs-c2/csv", "J2_VIIRS_C2_Global_7d"),
    ("viirs_noaa21", "noaa-21-viirs-c2/csv", "J2_VIIRS_C2_Global_48h"),
]

UA = "FIRETRACK/1.0 (NASA Space Apps Challenge; research prototype)"


def download(url: str, dest: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    h = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as fh:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
            fh.write(chunk)
    return {
        "url": url,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": size,
        "sha256": h.hexdigest(),
        "user_agent": UA,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw/snapshot")
    ap.add_argument("--only", nargs="*", default=None, help="restrict to these file stems")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    failures = []
    for sensor, folder, stem in PRODUCTS:
        if args.only and stem not in args.only:
            continue
        url = f"{BASE}/{folder}/{stem}.csv"
        dest = os.path.join(args.out, f"{stem}.csv")
        try:
            meta = download(url, dest)
            meta.update({"sensor_id": sensor, "stem": stem})
            with open(dest + ".meta.json", "w", encoding="utf-8") as fh:
                json.dump(meta, fh, indent=2)
            # a header-only file means the product is currently empty, keep it
            with open(dest, "rb") as fh:
                head = fh.readline().decode("utf-8", "replace").strip()
            print(f"OK   {stem:26s} {meta['bytes']:>10,} B  {head[:60]}")
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures.append((stem, str(exc)))
            print(f"FAIL {stem:26s} {exc}")

    print(f"\n{len(failures)} failure(s)")
    return 1 if failures and len(failures) == len(PRODUCTS) else 0


if __name__ == "__main__":
    sys.exit(main())
