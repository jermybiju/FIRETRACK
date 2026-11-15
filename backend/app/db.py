"""SQLite storage layer.

Two representations of the same detections are kept:

* ``detections``  - every single FIRMS record, untransformed, for the map, the
  data explorer, the CSV export and full traceability.
* ``daily_cells`` - the same data pre-aggregated onto the common analysis grid
  (0.25 deg). All analytics and the calendar read from this table, so MODIS and
  VIIRS are always summarised in identical spatial units.

Keeping both means a "raw count" can never be silently mixed with a
"harmonised index": the raw record is always one query away.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Iterable, Iterator

from . import config

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY,
    sensor TEXT NOT NULL,
    instrument TEXT NOT NULL,
    platform TEXT NOT NULL,
    product TEXT NOT NULL,
    processing TEXT NOT NULL,          -- NRT | SP | ARCHIVE
    source_file TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    acq_date TEXT NOT NULL,            -- UTC calendar date YYYY-MM-DD
    acq_time TEXT,                     -- UTC HHMM
    acq_ts TEXT NOT NULL,              -- ISO-8601 UTC
    confidence INTEGER,                -- ordinal 0-100 (VIIRS letters mapped)
    confidence_raw TEXT,
    confidence_class TEXT,             -- low | nominal | high
    frp REAL,
    brightness REAL,
    brightness_bg REAL,
    scan REAL,
    track REAL,
    daynight TEXT,
    version TEXT,
    cell_ix INTEGER NOT NULL,
    cell_iy INTEGER NOT NULL,
    batch_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_det_date        ON detections(acq_date);
CREATE INDEX IF NOT EXISTS idx_det_sensor_date ON detections(sensor, acq_date);
CREATE INDEX IF NOT EXISTS idx_det_cell        ON detections(cell_ix, cell_iy);
CREATE INDEX IF NOT EXISTS idx_det_latlon      ON detections(lat, lon);
-- Covering index: area queries are counted from the index alone, which is ~30x
-- faster on a multi-year record than scanning the table for the date predicate.
CREATE INDEX IF NOT EXISTS idx_det_latlon_date ON detections(lat, lon, acq_date);
CREATE INDEX IF NOT EXISTS idx_det_batch       ON detections(batch_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_det_pixel
    ON detections(sensor, acq_date, acq_time, lat, lon);

CREATE TABLE IF NOT EXISTS daily_cells (
    cell_ix INTEGER NOT NULL,
    cell_iy INTEGER NOT NULL,
    acq_date TEXT NOT NULL,
    sensor TEXT NOT NULL,
    n INTEGER NOT NULL,
    frp_sum REAL,
    n_high INTEGER NOT NULL DEFAULT 0,
    n_nominal INTEGER NOT NULL DEFAULT 0,
    n_low INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (cell_ix, cell_iy, acq_date, sensor)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_cell_date ON daily_cells(acq_date, sensor);

CREATE TABLE IF NOT EXISTS sensor_days (
    sensor TEXT NOT NULL,
    acq_date TEXT NOT NULL,
    observed INTEGER NOT NULL,         -- 1 = product delivered data that date
    n_global INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (sensor, acq_date)
);

-- Delivery windows reported by NASA FIRMS for each product (data_availability).
-- Availability is bounded by these: a day outside every window is NOT observed,
-- even if a query for that day returned no rows.
CREATE TABLE IF NOT EXISTS product_windows (
    product TEXT PRIMARY KEY,
    sensor TEXT NOT NULL,
    min_date TEXT NOT NULL,
    max_date TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_batches (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    description TEXT,
    files TEXT,
    rows_read INTEGER NOT NULL DEFAULT 0,
    rows_kept INTEGER NOT NULL DEFAULT 0,
    rows_rejected INTEGER NOT NULL DEFAULT 0,
    min_date TEXT,
    max_date TEXT,
    sensors TEXT,
    quality TEXT,                      -- provisional | science | mixed
    notes TEXT
);

CREATE TABLE IF NOT EXISTS areas (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    geojson TEXT NOT NULL,
    bbox TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

_local = threading.local()


def db_path() -> Path:
    """Resolved database path (environment override wins, for tests)."""
    import os

    return Path(os.environ.get("FIRETRACK_DB", config.DB_PATH))


def reset_connection() -> None:
    """Drop the cached connection so a new database path can take effect."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:  # noqa: BLE001 - closing a broken handle is harmless
            pass
        _local.conn = None


def connect() -> sqlite3.Connection:
    """One connection per thread, cached against the active database path."""
    path = db_path()
    cached = getattr(_local, "conn", None)
    if cached is not None and getattr(_local, "path", None) == path:
        return cached
    if cached is not None:
        try:
            cached.close()
        except Exception:  # noqa: BLE001
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-64000")
    _local.conn = conn
    _local.path = path
    return conn


def init_db() -> None:
    conn = connect()
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def query(sql: str, params: Iterable = ()) -> list[sqlite3.Row]:
    return list(connect().execute(sql, tuple(params)).fetchall())


def query_one(sql: str, params: Iterable = ()) -> sqlite3.Row | None:
    return connect().execute(sql, tuple(params)).fetchone()


def scalar(sql: str, params: Iterable = (), default=None):
    row = query_one(sql, params)
    if row is None:
        return default
    return row[0] if row[0] is not None else default


def meta_get(key: str, default: str | None = None) -> str | None:
    row = query_one("SELECT value FROM meta WHERE key = ?", (key,))
    return row["value"] if row else default


def meta_set(key: str, value: str) -> None:
    conn = connect()
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


def is_empty() -> bool:
    try:
        return scalar("SELECT COUNT(*) FROM detections", default=0) == 0
    except sqlite3.OperationalError:
        return True


def iter_detections(sql: str, params: Iterable = ()) -> Iterator[sqlite3.Row]:
    """Stream rows without materialising the whole result set."""
    cur = connect().execute(sql, tuple(params))
    try:
        for row in cur:
            yield row
    finally:
        cur.close()
