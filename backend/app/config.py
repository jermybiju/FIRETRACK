"""Runtime configuration for the FIRETRACK backend.

Everything is overridable with environment variables so the app can run on a
laptop with no configuration at all, while still allowing a deployment to point
at a different database or supply a NASA FIRMS MAP_KEY.
"""

from __future__ import annotations

import os
from pathlib import Path

# app/config.py -> app -> backend -> FIRETRACK
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file without adding a dependency.

    Existing environment variables win, so a shell export always overrides the
    file. This is where a FIRMS MAP_KEY normally comes from.
    """
    if not path.exists():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    except OSError:
        return


load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = Path(os.environ.get("FIRETRACK_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
SNAPSHOT_DIR = RAW_DIR / "snapshot"
ARCHIVE_DIR = RAW_DIR / "archive"
EXPORT_DIR = DATA_DIR / "exports"
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

DB_PATH = Path(os.environ.get("FIRETRACK_DB", DATA_DIR / "firetrack.db"))

# A free, instantly-issued key: https://firms.modaps.eosdis.nasa.gov/api/map_key/
FIRMS_MAP_KEY = os.environ.get("FIRMS_MAP_KEY", "").strip()

# Spatial resolution of the common analysis grid, in degrees.
GRID_DEG = float(os.environ.get("FIRETRACK_GRID_DEG", "0.25"))

APP_NAME = "FIRETRACK"
APP_VERSION = "1.0.0"

# --- Scientific parameters (documented in docs/METHODOLOGY.md) ---------------

# A day counts as "observed" for a sensor when the sensor reported at least one
# detection anywhere in the ingested product for that date. Globally there are
# always some fires, so an empty global day means the sensor did not deliver.
MIN_OVERLAP_DAYS_FOR_CALIBRATION = 60
# Coefficient of variation of the MODIS/VIIRS ratio across sub-periods above
# which the multiplicative calibration is declared unstable.
MAX_RATIO_CV_FOR_CALIBRATION = 0.35
# Coverage below this fraction marks a month/period as incomplete.
MIN_COVERAGE_FRACTION = 0.80
# Also require the record to span the whole period. A year that is still in
# progress (for example data ending in mid-November) can otherwise pass an 80%
# coverage test while missing weeks of the fire season. Set
# FIRETRACK_REQUIRE_FULL_PERIOD=0 in .env to count such years anyway.
REQUIRE_FULL_PERIOD = os.environ.get("FIRETRACK_REQUIRE_FULL_PERIOD", "1") not in ("0", "false", "False")
# Robust z-score threshold for flagging unusual activity.
ANOMALY_Z_THRESHOLD = 2.5

CONFIDENCE_CLASSES = {
    "modis": [(0, 29, "low"), (30, 79, "nominal"), (80, 100, "high")],
    "viirs": [(0, 49, "low"), (50, 79, "nominal"), (80, 100, "high")],
}
# Ordinal value assigned to the VIIRS letter confidence, which FIRMS publishes
# as a category (l/n/h) rather than a calibrated probability.
VIIRS_CONFIDENCE_ORDINAL = {"l": 25, "n": 65, "h": 90}

SENSORS = {
    "modis": {
        "label": "MODIS (Terra + Aqua)",
        "instrument": "MODIS",
        "pixel_km": 1.0,
        "product": "MODIS C6.1",
        "records_from": "2000-11-01",
        "colour": "#f59e0b",
    },
    "viirs_snpp": {
        "label": "VIIRS Suomi-NPP",
        "instrument": "VIIRS",
        "pixel_km": 0.375,
        "product": "VIIRS C2 375 m",
        "records_from": "2012-01-20",
        "colour": "#38bdf8",
    },
    "viirs_noaa20": {
        "label": "VIIRS NOAA-20",
        "instrument": "VIIRS",
        "pixel_km": 0.375,
        "product": "VIIRS C2 375 m",
        "records_from": "2018-04-01",
        "colour": "#a78bfa",
    },
    "viirs_noaa21": {
        "label": "VIIRS NOAA-21",
        "instrument": "VIIRS",
        "pixel_km": 0.375,
        "product": "VIIRS C2 375 m",
        "records_from": "2023-01-17",
        "colour": "#34d399",
    },
}
