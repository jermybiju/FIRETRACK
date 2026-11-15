"""Ingestion pipeline: FIRMS CSV -> SQLite (raw records + grid aggregates).

Design notes
------------
* **Streaming.** Global FIRMS files hold hundreds of thousands of rows, so the
  reader yields one CSV row at a time instead of materialising the file.
* **One source of truth.** Raw detections are inserted first; the 0.25 degree
  grid aggregates (``daily_cells``) are then rebuilt from those rows with a
  single GROUP BY. Rebuilding instead of incrementally accumulating guarantees
  that deduplicated rows are never counted twice in the analytics tables.
* **Availability.** A sensor is marked "observing" on every date between the
  first and last date it actually delivered, because each FIRMS product is a
  complete daily product. Dates outside that span are *not* zeros - they are
  unknown, and the analytics treat them that way.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Sequence

from . import config, db, firms


class IngestResult:
    def __init__(self, batch_id: str, kind: str, description: str):
        self.batch_id = batch_id
        self.kind = kind
        self.description = description
        self.rows_read = 0
        self.rows_kept = 0
        self.rows_duplicate = 0
        self.rejections: dict[str, int] = defaultdict(int)
        self.sensors: set[str] = set()
        self.min_date: str | None = None
        self.max_date: str | None = None
        self.files: list[str] = []
        self.observed: set[tuple[str, str]] = set()

    def note_date(self, day: str) -> None:
        if self.min_date is None or day < self.min_date:
            self.min_date = day
        if self.max_date is None or day > self.max_date:
            self.max_date = day

    @property
    def rows_rejected(self) -> int:
        return sum(self.rejections.values())

    @property
    def quality(self) -> str:
        return "provisional" if self.kind in ("snapshot", "api_nrt") else "science"

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "kind": self.kind,
            "description": self.description,
            "rows_read": self.rows_read,
            "rows_kept": self.rows_kept,
            "rows_duplicate": self.rows_duplicate,
            "rows_rejected": self.rows_rejected,
            "rejections": dict(sorted(self.rejections.items(), key=lambda kv: -kv[1])[:10]),
            "sensors": sorted(self.sensors),
            "min_date": self.min_date,
            "max_date": self.max_date,
            "quality": self.quality,
            "files": self.files,
        }


def ingest_detections(
    detections: Iterable[firms.Detection | firms.RowError],
    *,
    kind: str,
    description: str,
    files: Sequence[str] = (),
    availability: dict[str, tuple[str, str]] | None = None,
    chunk: int = 20000,
    rebuild: bool = True,
) -> IngestResult:
    """Insert normalised detections, then refresh derived tables.

    ``rebuild=False`` skips the grid rebuild, which lets a multi-file import
    build ``daily_cells`` once at the end instead of after every file.
    """
    db.init_db()
    conn = db.connect()
    result = IngestResult(str(uuid.uuid4()), kind, description)
    result.files = list(files)

    buffer: list[tuple] = []
    per_sensor_dates: dict[str, list[str]] = defaultdict(list)
    seen = 0
    before = db.scalar("SELECT COUNT(*) FROM detections", default=0)

    for item in detections:
        result.rows_read += 1
        if isinstance(item, firms.RowError):
            result.rejections[str(item)] += 1
            continue
        det = item
        result.sensors.add(det.sensor)
        result.note_date(det.acq_date)
        per_sensor_dates[det.sensor].append(det.acq_date)
        buffer.append(det.as_row(result.batch_id))
        seen += 1
        if len(buffer) >= chunk:
            conn.executemany(firms.INSERT_DETECTION_SQL, buffer)
            conn.commit()
            buffer.clear()
    if buffer:
        conn.executemany(firms.INSERT_DETECTION_SQL, buffer)
    conn.commit()

    after = db.scalar("SELECT COUNT(*) FROM detections", default=0)
    result.rows_kept = max(0, after - before)
    result.rows_duplicate = seen - result.rows_kept

    # Products are daily-complete: every date between a sensor's first and last
    # delivered date counts as observed, even where the area had no detections.
    for sensor, dates in per_sensor_dates.items():
        lo, hi = min(dates), max(dates)
        for day in _daterange(lo, hi):
            result.observed.add((sensor, day))
    for sensor, (lo, hi) in (availability or {}).items():
        if lo and hi:
            for day in _daterange(lo, hi):
                result.observed.add((sensor, day))

    conn.executemany(
        "INSERT INTO sensor_days(sensor, acq_date, observed, n_global) VALUES(?,?,1,0) "
        "ON CONFLICT(sensor, acq_date) DO UPDATE SET observed=1",
        sorted(result.observed),
    )
    conn.execute(
        "INSERT INTO ingest_batches(id, created_at, kind, description, files, rows_read,"
        " rows_kept, rows_rejected, min_date, max_date, sensors, quality, notes)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            result.batch_id,
            firms.now_iso(),
            result.kind,
            result.description,
            json.dumps(result.files),
            result.rows_read,
            result.rows_kept,
            result.rows_rejected,
            result.min_date,
            result.max_date,
            json.dumps(sorted(result.sensors)),
            result.quality,
            json.dumps({"rejections": dict(result.rejections)}),
        ),
    )
    conn.commit()

    if rebuild:
        rebuild_daily_cells()
    db.meta_set("last_ingest_at", firms.now_iso())
    db.meta_set("last_ingest_batch", result.batch_id)
    return result


def _daterange(lo: str, hi: str) -> Iterable[str]:
    start = date.fromisoformat(lo)
    end = date.fromisoformat(hi)
    while start <= end:
        yield start.isoformat()
        start += timedelta(days=1)


def rebuild_daily_cells() -> None:
    """Recompute the common-grid aggregates from the raw records."""
    conn = db.connect()
    conn.execute("DELETE FROM daily_cells")
    conn.execute(
        """
        INSERT INTO daily_cells
            (cell_ix, cell_iy, acq_date, sensor, n, frp_sum, n_high, n_nominal, n_low)
        SELECT cell_ix, cell_iy, acq_date, sensor, COUNT(*), SUM(COALESCE(frp, 0)),
               SUM(CASE WHEN confidence_class='high' THEN 1 ELSE 0 END),
               SUM(CASE WHEN confidence_class='nominal' THEN 1 ELSE 0 END),
               SUM(CASE WHEN confidence_class='low' THEN 1 ELSE 0 END)
        FROM detections
        GROUP BY cell_ix, cell_iy, acq_date, sensor
        """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Snapshot (key-free global rolling files)
# ---------------------------------------------------------------------------

SNAPSHOT_PRODUCTS = {
    "MODIS_C6_1_Global": ("modis", "MODIS C6.1"),
    "SUOMI_VIIRS_C2_Global": ("viirs_snpp", "VIIRS C2 (S-NPP)"),
    "J1_VIIRS_C2_Global": ("viirs_noaa20", "VIIRS C2 (NOAA-20)"),
    "J2_VIIRS_C2_Global": ("viirs_noaa21", "VIIRS C2 (NOAA-21)"),
}


def sensor_for_stem(stem: str) -> tuple[str, str] | None:
    for prefix, meta in SNAPSHOT_PRODUCTS.items():
        if stem.startswith(prefix):
            return meta
    return None


def snapshot_files(directory: Path | None = None) -> list[Path]:
    """Pick one file per sensor, preferring the widest (7 day) window."""
    directory = Path(directory or config.SNAPSHOT_DIR)
    if not directory.exists():
        return []
    files = sorted(
        p for p in directory.iterdir() if p.name.endswith(".csv") or p.name.endswith(".csv.gz")
    )
    chosen: dict[str, Path] = {}
    for path in files:
        stem = _strip_ext(path.name)
        meta = sensor_for_stem(stem)
        if meta is None:
            continue
        sensor = meta[0]
        score = 3 if "_7d" in stem else 2 if "_48h" in stem else 1
        if sensor not in chosen or score > _score(chosen[sensor].name):
            chosen[sensor] = path
    return sorted(chosen.values())


def _score(name: str) -> int:
    stem = _strip_ext(name)
    return 3 if "_7d" in stem else 2 if "_48h" in stem else 1


def _strip_ext(name: str) -> str:
    return name[:-3] if name.endswith(".gz") else name.rsplit(".", 1)[0]


def ingest_snapshot_dir(directory: Path | None = None, force: bool = False) -> list[dict]:
    """Ingest the bundled rolling snapshot; already-ingested files are skipped."""
    db.init_db()
    directory = Path(directory or config.SNAPSHOT_DIR)

    pending = []
    for path in snapshot_files(directory):
        stem = _strip_ext(path.name)
        meta = sensor_for_stem(stem)
        if meta is None:
            continue
        if not force and db.query_one(
            "SELECT id FROM ingest_batches WHERE kind='snapshot' AND files LIKE ?",
            (f"%{path.name}%",),
        ):
            continue
        pending.append((path, meta))

    results: list[dict] = []
    for index, (path, meta) in enumerate(pending):
        sensor, product_label = meta
        stream = firms.iter_firms_file(
            path,
            default_sensor=sensor,
            product=product_label,
            source_file=path.name,
            grid_deg=config.GRID_DEG,
        )
        result = ingest_detections(
            stream,
            kind="snapshot",
            description=f"Key-free FIRMS global rolling snapshot: {path.name}",
            files=[path.name],
            rebuild=(index == len(pending) - 1),
        )
        results.append(result.to_dict())
    return results


# ---------------------------------------------------------------------------
# Arbitrary FIRMS CSV (Archive Download or backfilled API files)
# ---------------------------------------------------------------------------

def ingest_paths(
    paths: Sequence[Path | str],
    *,
    kind: str = "archive",
    description: str | None = None,
    bbox: Sequence[float] | None = None,
) -> IngestResult:
    """Ingest FIRMS CSV files, optionally clipped to a bounding box."""
    db.init_db()
    files = [Path(p) for p in paths if Path(p).exists()]

    def stream():
        for path in files:
            sensor_hint = firms.infer_sensor("", "", path.name)
            for item in firms.iter_firms_file(
                path,
                default_sensor=sensor_hint,
                product="FIRMS archive",
                source_file=path.name,
                grid_deg=config.GRID_DEG,
            ):
                if isinstance(item, firms.RowError):
                    yield item
                elif bbox is None or _in_bbox(item, bbox):
                    yield item

    return ingest_detections(
        stream(),
        kind=kind,
        description=description or f"Imported {len(files)} FIRMS file(s)",
        files=[p.name for p in files],
    )


def _in_bbox(det: firms.Detection, bbox: Sequence[float]) -> bool:
    w, s, e, n = bbox
    return s <= det.lat <= n and w <= det.lon <= e


def register_observation_days(sensor: str, dates: Iterable[str]) -> int:
    """Mark dates as observed for a sensor even when no detection was returned.

    Used by the backfill script: a successful API response for a window proves
    the sensor was processing, so an empty answer there means "no hotspot
    detected", not "no data".

    Dates outside the delivery windows NASA reports for that sensor are skipped:
    a sensor that has ceased returns empty responses, and counting those as
    "observed" would make the harmonised index assume a contribution that could
    never arrive.
    """
    windows = sensor_window_map()
    allowed = windows.get(sensor)
    rows = []
    skipped = 0
    for day in dates:
        if allowed and not (allowed[0] <= day <= allowed[1]):
            skipped += 1
            continue
        rows.append((sensor, day))
    if not rows:
        return 0
    conn = db.connect()
    conn.executemany(
        "INSERT INTO sensor_days(sensor, acq_date, observed, n_global) VALUES(?,?,1,0) "
        "ON CONFLICT(sensor, acq_date) DO UPDATE SET observed=1",
        rows,
    )
    conn.commit()
    if skipped:
        print(f"[FIRETRACK] {sensor}: {skipped} date(s) outside the NASA delivery "
              f"window were not registered as observed")
    return len(rows)


# ---------------------------------------------------------------------------
# Delivery windows: availability must follow what NASA actually delivered
# ---------------------------------------------------------------------------

# FIRMS data ids -> our sensor ids. Burned-area and non-fire products are ignored.
_PRODUCT_TO_SENSOR = {
    "MODIS_SP": "modis",
    "MODIS_NRT": "modis",
    "VIIRS_SNPP_SP": "viirs_snpp",
    "VIIRS_SNPP_NRT": "viirs_snpp",
    "VIIRS_NOAA20_SP": "viirs_noaa20",
    "VIIRS_NOAA20_NRT": "viirs_noaa20",
    "VIIRS_NOAA21_SP": "viirs_noaa21",
    "VIIRS_NOAA21_NRT": "viirs_noaa21",
}


def store_product_windows(availability_rows: Iterable[dict]) -> int:
    """Persist the per-product date ranges NASA reports for its own products."""
    conn = db.connect()
    stored = 0
    now = firms.now_iso()
    for row in availability_rows:
        product = str(row.get("data_id") or "").strip()
        sensor = _PRODUCT_TO_SENSOR.get(product)
        if not sensor:
            continue
        lo = (row.get("min_date") or "").strip()
        hi = (row.get("max_date") or "").strip()
        if not lo or not hi:
            continue
        conn.execute(
            "INSERT INTO product_windows(product, sensor, min_date, max_date, fetched_at) "
            "VALUES(?,?,?,?,?) ON CONFLICT(product) DO UPDATE SET "
            "sensor=excluded.sensor, min_date=excluded.min_date, "
            "max_date=excluded.max_date, fetched_at=excluded.fetched_at",
            (product, sensor, lo, hi, now),
        )
        stored += 1
    conn.commit()
    return stored


def sensor_window_map() -> dict[str, tuple[str, str]]:
    """Union of delivery windows per sensor, e.g. SP (older) + NRT (recent)."""
    try:
        rows = db.query("SELECT sensor, MIN(min_date) lo, MAX(max_date) hi FROM product_windows GROUP BY sensor")
    except Exception:  # noqa: BLE001 - table may not exist yet
        return {}
    return {row["sensor"]: (row["lo"], row["hi"]) for row in rows}


def bound_sensor_days(dry_run: bool = False) -> dict:
    """Remove observation days that fall outside NASA's delivery windows.

    Detections are never touched - only the availability calendar. Returns a
    report of what was removed so the change can be audited.
    """
    windows = sensor_window_map()
    if not windows:
        return {"trimmed": 0, "detail": [], "note": "no product windows stored yet"}

    removed_total = 0
    protected_total = 0
    detail = []
    conn = db.connect()
    for sensor, (lo, hi) in sorted(windows.items()):
        before = db.scalar("SELECT COUNT(*) FROM sensor_days WHERE sensor = ?", (sensor,), default=0)
        stale = db.query(
            "SELECT acq_date FROM sensor_days WHERE sensor = ? AND (acq_date < ? OR acq_date > ?) "
            "ORDER BY acq_date",
            (sensor, lo, hi),
        )
        # Safety: a date with real detections is evidence the sensor delivered,
        # whatever the availability table says. Never drop those.
        with_data = db.query(
            "SELECT DISTINCT acq_date FROM detections WHERE sensor = ? AND (acq_date < ? OR acq_date > ?)",
            (sensor, lo, hi),
        )
        with_data_days = {r["acq_date"] for r in with_data}
        removable = [r["acq_date"] for r in stale if r["acq_date"] not in with_data_days]
        protected = sorted(with_data_days)
        protected_total += len(protected)

        if not removable:
            detail.append({"sensor": sensor, "window": [lo, hi], "removed": 0,
                           "protected": protected, "dates": []})
            continue
        if not dry_run:
            conn.executemany(
                "DELETE FROM sensor_days WHERE sensor = ? AND acq_date = ?",
                [(sensor, day) for day in removable],
            )
        removed_total += len(removable)
        detail.append({
            "sensor": sensor,
            "window": [lo, hi],
            "removed": len(removable),
            "protected": protected,
            "dates": removable[:20],
            "days_before": before,
            "days_after": before - len(removable),
        })
    if not dry_run:
        conn.commit()
    return {"trimmed": removed_total, "protected": protected_total, "detail": detail, "dry_run": dry_run}


def purge_batch(batch_id: str) -> int:
    conn = db.connect()
    cur = conn.execute("DELETE FROM detections WHERE batch_id = ?", (batch_id,))
    removed = cur.rowcount
    conn.execute("DELETE FROM ingest_batches WHERE id = ?", (batch_id,))
    conn.commit()
    rebuild_daily_cells()
    return removed


def clear_all() -> None:
    conn = db.connect()
    for table in ("detections", "daily_cells", "sensor_days", "ingest_batches"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()


def summary() -> dict:
    db.init_db()
    total = db.scalar("SELECT COUNT(*) FROM detections", default=0)
    if not total:
        return {"ready": False, "detections": 0, "sensors": {}, "min_date": None,
                "max_date": None, "batches": []}
    per_sensor = {
        row["sensor"]: row["n"]
        for row in db.query("SELECT sensor, COUNT(*) n FROM detections GROUP BY sensor ORDER BY n DESC")
    }
    return {
        "ready": True,
        "detections": total,
        "sensors": per_sensor,
        "min_date": db.scalar("SELECT MIN(acq_date) FROM detections"),
        "max_date": db.scalar("SELECT MAX(acq_date) FROM detections"),
        "batches": [dict(r) for r in db.query(
            "SELECT id, created_at, kind, description, rows_read, rows_kept, rows_rejected,"
            " min_date, max_date, quality FROM ingest_batches ORDER BY created_at DESC"
        )],
    }
