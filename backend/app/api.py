"""HTTP API for FIRETRACK.

Every analytical response carries the scientific context it was computed with:
the AOI, its grid size, the sensor availability, the calibration status and the
unit of the reported activity. That is deliberate - a number is never returned
without the information needed to interpret it correctly.
"""

from __future__ import annotations

import csv
import io
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal, Sequence

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agreement, analytics, config, db, firms, geo, harmonize, ingest, regions, report

app = FastAPI(
    title="FIRETRACK API",
    version=config.APP_VERSION,
    description="Harmonised NASA FIRMS MODIS/VIIRS burning-activity analytics.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_CAVEAT = (
    "FIRMS hotspots are thermal-anomaly detections, not confirmed wildfires. "
    "Missing observations are excluded, never counted as zero activity."
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class AOIPayload(BaseModel):
    region_id: str | None = None
    bbox: list[float] | None = None
    polygon: list[list[float]] | None = None
    name: str | None = None


class QueryPayload(BaseModel):
    aoi: AOIPayload = Field(default_factory=AOIPayload)
    start: str | None = None
    end: str | None = None
    confidence: Literal["all", "nominal", "high"] = "all"
    sensors: list[str] | None = None


class MonthPayload(QueryPayload):
    year: int | None = None
    month: int | None = None


class HistoryPayload(QueryPayload):
    metric: Literal["harmonized", "raw"] = "harmonized"
    start_year: int | None = None
    end_year: int | None = None


class AnomalyPayload(QueryPayload):
    z_threshold: float | None = None


class CriticalPeriodPayload(QueryPayload):
    percentile: float = 90.0
    min_days: int = 3


class DetectionPayload(QueryPayload):
    limit: int = 100
    offset: int = 0
    frp_min: float | None = None
    confidence_min: int | None = None
    order: Literal["recent", "frp", "confidence"] = "recent"
    search: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SERIES_CACHE: dict[str, harmonize.HarmonizedSeries] = {}
_CACHE_LIMIT = 24


def _cache_token() -> str:
    return db.meta_get("last_ingest_at", "none")


def resolve_aoi(payload: AOIPayload) -> geo.AOI:
    try:
        return geo.normalize_aoi(payload.model_dump(), regions=regions.REGIONS)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _validate_period(start: str | None, end: str | None) -> tuple[str | None, str | None]:
    for value in (start, end):
        if value:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid date: {value}") from exc
    if start and end and start > end:
        raise HTTPException(status_code=400, detail="The start date must precede the end date.")
    return start, end


def get_series(payload: QueryPayload) -> harmonize.HarmonizedSeries:
    if db.is_empty():
        raise HTTPException(
            status_code=409,
            detail="No hotspot records are loaded yet. Ingest a FIRMS file or load the bundled snapshot.",
        )
    aoi = resolve_aoi(payload.aoi)
    start, end = _validate_period(payload.start, payload.end)
    sensors = tuple(sorted(payload.sensors)) if payload.sensors else ()
    key = f"{geo.aoi_key(aoi)}|{start}|{end}|{payload.confidence}|{sensors}|{_cache_token()}"
    cached = _SERIES_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        harmonised = harmonize.build(aoi, start=start, end=end,
                                     confidence=payload.confidence,
                                     sensors=list(sensors) or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not harmonised.series.dates:
        raise HTTPException(
            status_code=404,
            detail="No observations available for this area and period.",
        )
    if len(_SERIES_CACHE) >= _CACHE_LIMIT:
        _SERIES_CACHE.pop(next(iter(_SERIES_CACHE)))
    _SERIES_CACHE[key] = harmonised
    return harmonised


def _default_period(harmonised: harmonize.HarmonizedSeries, start=None, end=None):
    s = harmonised.series
    return start or s.start, end or s.end


# ---------------------------------------------------------------------------
# Catalogue / metadata
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    total = 0
    try:
        total = db.scalar("SELECT COUNT(*) FROM detections", default=0)
    except Exception:  # noqa: BLE001 - database may not exist yet
        total = 0
    return {
        "status": "ok",
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        "detections": total,
        "ready": total > 0,
        "map_key_configured": bool(config.FIRMS_MAP_KEY),
        "server_time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


@app.get("/api/catalog")
def catalog() -> dict:
    info = ingest.summary()
    coverage = []
    if info.get("ready"):
        for row in db.query(
            "SELECT sensor, COUNT(*) n, MIN(acq_date) lo, MAX(acq_date) hi FROM detections GROUP BY sensor"
        ):
            meta = config.SENSORS.get(row["sensor"], {})
            coverage.append({
                "sensor": row["sensor"],
                "label": meta.get("label", row["sensor"]),
                "colour": meta.get("colour", "#94a3b8"),
                "detections": row["n"],
                "first_date": row["lo"],
                "last_date": row["hi"],
                "product": meta.get("product"),
                "pixel_km": meta.get("pixel_km"),
            })
    availability = [
        dict(r) for r in db.query(
            "SELECT sensor, COUNT(*) days, MIN(acq_date) lo, MAX(acq_date) hi "
            "FROM sensor_days WHERE observed = 1 GROUP BY sensor ORDER BY sensor"
        )
    ] if info.get("ready") else []
    active = {row["sensor"] for row in coverage}
    return {
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        "tagline": "Two Satellite Perspectives. One Consistent History of Burning Activity.",
        "ready": info.get("ready"),
        "detections": info.get("detections", 0),
        "min_date": info.get("min_date"),
        "max_date": info.get("max_date"),
        # Only sensors that actually delivered records are offered as filters, so
        # the interface cannot present an empty toggle to the user. All configured
        # sensors remain documented in config.SENSORS and on the Methodology page.
        "sensors": [
            {"id": key, **{k: v for k, v in meta.items()}}
            for key, meta in config.SENSORS.items()
            if not active or key in active
        ],
        "coverage": coverage,
        "availability": availability,
        "batches": info.get("batches", []),
        "grid_deg": config.GRID_DEG,
        "map_key_configured": bool(config.FIRMS_MAP_KEY),
        "parameters": {
            "min_overlap_days_for_calibration": config.MIN_OVERLAP_DAYS_FOR_CALIBRATION,
            "max_ratio_cv_for_calibration": config.MAX_RATIO_CV_FOR_CALIBRATION,
            "min_coverage_fraction": config.MIN_COVERAGE_FRACTION,
            "anomaly_z_threshold": config.ANOMALY_Z_THRESHOLD,
        },
        "caveat": DATA_CAVEAT,
    }


@app.get("/api/provenance")
def provenance() -> dict:
    batches = [dict(r) for r in db.query(
        "SELECT id, created_at, kind, description, files, rows_read, rows_kept, rows_rejected,"
        " min_date, max_date, sensors, quality, notes FROM ingest_batches ORDER BY created_at"
    )]
    return {
        "application": {"name": config.APP_NAME, "version": config.APP_VERSION},
        "data_provider": "NASA FIRMS (Fire Information for Resource Management System), EOSDIS/LANCE",
        "source_url": "https://firms.modaps.eosdis.nasa.gov/",
        "products": {
            "modis": "MODIS Collection 6.1 active fire (Terra + Aqua), 1 km",
            "viirs": "VIIRS Collection 2 375 m active fire (Suomi-NPP, NOAA-20, NOAA-21)",
        },
        "retrieval": {
            "mode": "local records built by scripts/download_firms_snapshot.py and/or the FIRMS area API",
            "map_key_configured": bool(config.FIRMS_MAP_KEY),
            "batches": batches,
        },
        "processing": {
            "grid_deg": config.GRID_DEG,
            "confidence_mapping": "MODIS 0-100 retained; VIIRS l/n/h mapped to ordinal 25/65/90",
            "calibration": "overlap-period ratio of mean daily detection rates",
        },
        "quality_flags": {
            "NRT": "near real time, provisional, superseded by standard processing after ~5 months",
            "SP": "standard processing (science quality)",
        },
        "disclaimer": DATA_CAVEAT + " Not an official emergency alerting system.",
    }


@app.get("/api/regions")
def region_presets() -> dict:
    return {"regions": regions.preset_list()}


@app.get("/api/search")
def search_locations(q: str = Query("", min_length=0, max_length=80)) -> dict:
    return {"results": regions.search(q)}


# ---------------------------------------------------------------------------
# Harmonisation / calendar
# ---------------------------------------------------------------------------

@app.post("/api/harmonization")
def harmonization(payload: QueryPayload) -> dict:
    h = get_series(payload)
    return {
        "context": analytics.series_context(h),
        "calibration": h.calibration.to_dict(),
        "sensor_timeline": analytics.sensor_timeline(h)["sensors"],
        "availability": {
            sensor: {
                "observed_days": len(days),
                "first": min(days) if days else None,
                "last": max(days) if days else None,
            }
            for sensor, days in h.series.observed.items()
        },
        "transitions": agreement.transition_diagnostics(h),
    }


@app.post("/api/calendar/month")
def calendar_month(payload: MonthPayload) -> dict:
    h = get_series(payload)
    today = date.today()
    year = payload.year or today.year
    month = payload.month or today.month
    if not 1 <= month <= 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12.")
    if not 1970 <= year <= 2200:
        raise HTTPException(status_code=400, detail="Year out of range.")
    return analytics.calendar_month(h, year, month)


@app.post("/api/calendar/year")
def calendar_year(payload: MonthPayload) -> dict:
    h = get_series(payload)
    year = payload.year or date.today().year
    return analytics.calendar_year(h, year)


@app.post("/api/calendar/history")
def calendar_history(payload: HistoryPayload) -> dict:
    h = get_series(payload)
    return analytics.history_matrix(
        h, metric=payload.metric,
        start_year=payload.start_year, end_year=payload.end_year,
    )


@app.post("/api/analytics/trends")
def analytics_trends(payload: QueryPayload) -> dict:
    h = get_series(payload)
    return analytics.trends(h)


@app.post("/api/anomalies")
def anomaly_list(payload: AnomalyPayload) -> dict:
    h = get_series(payload)
    start, end = _validate_period(payload.start, payload.end)
    return analytics.anomalies(h, start=start, end=end, z_threshold=payload.z_threshold)


@app.post("/api/critical-periods")
def critical_period_list(payload: CriticalPeriodPayload) -> dict:
    """Contiguous runs of unusually high burning activity."""
    h = get_series(payload)
    start, end = _validate_period(payload.start, payload.end)
    if not 50 <= payload.percentile <= 99.9:
        raise HTTPException(status_code=400, detail="percentile must be between 50 and 99.9")
    if not 1 <= payload.min_days <= 60:
        raise HTTPException(status_code=400, detail="min_days must be between 1 and 60")
    return analytics.critical_periods(
        h, start=start, end=end, percentile=payload.percentile, min_days=payload.min_days
    )


@app.post("/api/compare/sensors")
def compare_sensors(payload: QueryPayload) -> dict:
    h = get_series(payload)
    start, end = _validate_period(payload.start, payload.end)
    return agreement.compare_sensors(h, start=start, end=end)


# ---------------------------------------------------------------------------
# Map layers
# ---------------------------------------------------------------------------

@app.post("/api/map/cells")
def map_cells(payload: QueryPayload) -> dict:
    """Grid-cell activity for the map's harmonised layer."""
    h = get_series(payload)
    per_cell: dict[tuple[int, int], dict] = {}
    res = config.GRID_DEG
    west, south, east, north = h.series.aoi.bbox
    ix_lo, iy_lo = geo.cell_index(south, west, res)
    ix_hi, iy_hi = geo.cell_index(north, east, res)

    # The map must use the same confidence and sensor filters as the analytics,
    # otherwise the same selection shows different totals on different pages.
    columns = harmonize.CONFIDENCE_FILTERS.get(payload.confidence, ("n_high", "n_nominal", "n_low"))
    count_expr = " + ".join(columns)
    params: list = [payload.start or h.series.start, payload.end or h.series.end,
                    ix_lo, ix_hi, iy_lo, iy_hi]
    sensor_clause = ""
    if payload.sensors:
        sensor_clause = f" AND sensor IN ({','.join('?' for _ in payload.sensors)})"
        params.extend(payload.sensors)

    rows = db.query(
        f"""
        SELECT cell_ix, cell_iy, sensor, SUM({count_expr}) n, SUM(frp_sum) frp
        FROM daily_cells
        WHERE acq_date BETWEEN ? AND ?
          AND cell_ix BETWEEN ? AND ? AND cell_iy BETWEEN ? AND ?
          {sensor_clause}
        GROUP BY cell_ix, cell_iy, sensor
        """,
        params,
    )
    for row in rows:
        lat = (row["cell_ix"] + 0.5) * res - 90.0
        lon = (row["cell_iy"] + 0.5) * res - 180.0
        if not h.series.aoi.contains(lat, lon):
            continue
        entry = per_cell.setdefault((row["cell_ix"], row["cell_iy"]), {
            "lat": round(lat, 4), "lon": round(lon, 4), "total": 0, "frp": 0.0,
            "per_sensor": {}, "frp_by_sensor": {},
        })
        entry["total"] += row["n"]
        entry["frp"] += row["frp"] or 0.0
        entry["per_sensor"][row["sensor"]] = row["n"]
        entry["frp_by_sensor"][row["sensor"]] = round(row["frp"] or 0.0, 1)

    cells = sorted(per_cell.values(), key=lambda c: -c["total"])
    for c in cells:
        c["frp"] = round(c["frp"], 1)
    return {
        "cells": cells,
        "max_total": max((c["total"] for c in cells), default=0),
        "count": len(cells),
        "grid_deg": res,
        "frp_note": "frp is the sum of raw per-sensor FRP; it is not a harmonised quantity",
        "period": {"start": payload.start or h.series.start, "end": payload.end or h.series.end},
        "calibration": h.calibration.to_dict(),
    }


@app.post("/api/map/points")
def map_points(payload: QueryPayload) -> dict:
    """Individual detections for one day, for click-through inspection."""
    aoi = resolve_aoi(payload.aoi)
    start, end = _validate_period(payload.start, payload.end)
    start = start or end or str(date.today())
    end = end or start
    rows, total, truncated = _filtered_detections(aoi, start, end, payload.confidence,
                                                  payload.sensors, None, None, limit=4000)
    return {
        "points": rows,
        "total": total,
        "truncated": truncated,
        "period": {"start": start, "end": end},
        "caveat": DATA_CAVEAT,
    }


# ---------------------------------------------------------------------------
# Detection records / data explorer
# ---------------------------------------------------------------------------

def _filtered_detections(
    aoi: geo.AOI,
    start: str,
    end: str,
    confidence: str = "all",
    sensors: Sequence[str] | None = None,
    frp_min: float | None = None,
    confidence_min: int | None = None,
    limit: int = 100,
    offset: int = 0,
    order: str = "recent",
    search: str | None = None,
    max_scan: int = 400_000,
) -> tuple[list[dict], int, bool]:
    w, s, e, n = aoi.bbox
    clauses = ["acq_date BETWEEN ? AND ?", "lat BETWEEN ? AND ?", "lon BETWEEN ? AND ?"]
    params: list = [start, end, s, n, w, e]
    if sensors:
        clauses.append(f"sensor IN ({','.join('?' for _ in sensors)})")
        params.extend(sensors)
    if frp_min is not None:
        clauses.append("frp >= ?")
        params.append(frp_min)
    if confidence == "nominal":
        clauses.append("confidence >= 50")
    elif confidence == "high":
        clauses.append("confidence >= 80")
    if confidence_min is not None:
        clauses.append("confidence >= ?")
        params.append(confidence_min)
    if search:
        clauses.append("(platform LIKE ? OR sensor LIKE ? OR CAST(acq_date AS TEXT) LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])

    where = " AND ".join(clauses)
    order_sql = {
        "recent": "acq_date DESC, acq_time DESC",
        "frp": "frp DESC NULLS LAST",
        "confidence": "confidence DESC NULLS LAST",
    }[order]

    # A plain bounding box can be counted and paginated by SQLite directly. Only
    # a drawn polygon needs the point-in-polygon pass, which has to scan rows.
    if not aoi.polygon:
        total = db.scalar(f"SELECT COUNT(*) FROM detections WHERE {where}", params, default=0) or 0
        page = db.query(
            f"SELECT * FROM detections WHERE {where} ORDER BY {order_sql} LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        return [_row_to_dict(row) for row in page], total, False

    cursor = db.connect().execute(
        f"SELECT * FROM detections WHERE {where} ORDER BY {order_sql}", tuple(params)
    )
    total = 0
    scanned = 0
    collected: list[dict] = []
    truncated = False
    for row in cursor:
        scanned += 1
        if scanned > max_scan:
            truncated = True
            break
        if not aoi.contains(row["lat"], row["lon"]):
            continue
        total += 1
        if total > offset and len(collected) < limit:
            collected.append(_row_to_dict(row))
    cursor.close()
    return collected, total, truncated


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "sensor": row["sensor"],
        "platform": row["platform"],
        "instrument": row["instrument"],
        "product": row["product"],
        "processing": row["processing"],
        "lat": row["lat"],
        "lon": row["lon"],
        "acq_date": row["acq_date"],
        "acq_time": row["acq_time"],
        "acq_ts": row["acq_ts"],
        "confidence": row["confidence"],
        "confidence_raw": row["confidence_raw"],
        "confidence_class": row["confidence_class"],
        "frp": row["frp"],
        "brightness": row["brightness"],
        "brightness_bg": row["brightness_bg"],
        "daynight": row["daynight"],
        "version": row["version"],
        "source_file": row["source_file"],
    }


@app.post("/api/detections")
def detections(payload: DetectionPayload) -> dict:
    aoi = resolve_aoi(payload.aoi)
    h = get_series(payload)
    start, end = _default_period(h, payload.start, payload.end)
    rows, total, truncated = _filtered_detections(
        aoi, start, end, payload.confidence, payload.sensors, payload.frp_min,
        payload.confidence_min, limit=min(payload.limit, 500), offset=payload.offset,
        order=payload.order, search=payload.search,
    )
    return {
        "rows": rows,
        "total": total,
        "offset": payload.offset,
        "limit": payload.limit,
        "truncated": truncated,
        "period": {"start": start, "end": end},
        "context": analytics.series_context(h),
        "caveat": DATA_CAVEAT,
    }


@app.post("/api/export/detections.csv")
def export_detections(payload: DetectionPayload) -> StreamingResponse:
    aoi = resolve_aoi(payload.aoi)
    h = get_series(payload)
    start, end = _default_period(h, payload.start, payload.end)

    w, s, e, n = aoi.bbox
    clauses = ["acq_date BETWEEN ? AND ?", "lat BETWEEN ? AND ?", "lon BETWEEN ? AND ?"]
    params: list = [start, end, s, n, w, e]
    if payload.sensors:
        clauses.append(f"sensor IN ({','.join('?' for _ in payload.sensors)})")
        params.extend(payload.sensors)
    if payload.frp_min is not None:
        clauses.append("frp >= ?")
        params.append(payload.frp_min)
    if payload.confidence == "nominal":
        clauses.append("confidence >= 50")
    elif payload.confidence == "high":
        clauses.append("confidence >= 80")
    where = " AND ".join(clauses)

    columns = [
        "sensor", "instrument", "platform", "product", "processing",
        "latitude", "longitude", "acq_date", "acq_time", "acq_ts_utc",
        "confidence", "confidence_raw", "confidence_class", "frp_mw",
        "brightness_k", "brightness_bg_k", "scan", "track", "daynight",
        "version", "source_file",
    ]

    def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        def flush():
            data = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            return data

        writer.writerow(columns)
        yield flush()
        cursor = db.connect().execute(
            f"SELECT * FROM detections WHERE {where} ORDER BY acq_date, acq_time", tuple(params)
        )
        n_rows = 0
        for row in cursor:
            if aoi.polygon and not aoi.contains(row["lat"], row["lon"]):
                continue
            writer.writerow([
                row["sensor"], row["instrument"], row["platform"], row["product"], row["processing"],
                row["lat"], row["lon"], row["acq_date"], row["acq_time"], row["acq_ts"],
                row["confidence"], row["confidence_raw"], row["confidence_class"], row["frp"],
                row["brightness"], row["brightness_bg"], row["scan"], row["track"], row["daynight"],
                row["version"], row["source_file"],
            ])
            n_rows += 1
            if n_rows % 5000 == 0:
                yield flush()
        cursor.close()
        yield flush()

    filename = f"firetrack_detections_{start}_{end}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/export/analytics.csv")
def export_analytics(payload: QueryPayload) -> StreamingResponse:
    h = get_series(payload)
    start, end = _default_period(h, payload.start, payload.end)
    points = h.points(start, end)
    sensors = h.series.sensors
    header = ["date", "observed", "raw_total", "harmonized", "coverage",
              "frp_sum_raw_all_sensors"] + \
             [f"n_{s}" for s in sensors] + [f"frp_{s}" for s in sensors] + ["sensors_observing"]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for p in points:
        writer.writerow([
            p.date, int(p.observed), p.raw_total,
            round(p.harmonized, 3) if p.harmonized is not None else "",
            round(p.coverage, 3), round(p.frp_total, 1),
            *[p.per_sensor.get(s, 0) for s in sensors],
            *[round(p.frp_by_sensor.get(s, 0.0), 1) for s in sensors],
            "|".join(p.sensors_observing),
        ])
    data = buffer.getvalue()
    buffer.close()
    return StreamingResponse(
        iter([data]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="firetrack_daily_{start}_{end}.csv"'},
    )


@app.post("/api/export/report.html")
def export_report(payload: MonthPayload) -> HTMLResponse:
    h = get_series(payload)
    today = date.today()
    year = payload.year or today.year
    month = payload.month or today.month
    cal = analytics.calendar_month(h, year, month)
    tr = analytics.trends(h)
    summary = cal["summary"]
    start = cal["summary"]["start"]
    end = cal["summary"]["end"]
    critical = analytics.critical_periods(h, start=start, end=end)
    doc = report.render_report({
        "context": cal["context"],
        "summary": summary,
        "baseline": cal["baseline"],
        "comparison": cal["comparison"],
        "trend": tr["trend"],
        "yearly": tr["yearly"],
        "monthly_profile": tr["monthly_profile"],
        "critical": critical,
    })
    return HTMLResponse(content=doc)


# ---------------------------------------------------------------------------
# Ingestion endpoints (local convenience)
# ---------------------------------------------------------------------------

@app.post("/api/ingest/snapshot")
def ingest_snapshot(force: bool = False) -> dict:
    try:
        results = ingest.ingest_snapshot_dir(force=force)
    except Exception as exc:  # noqa: BLE001 - surface a readable error
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc
    _SERIES_CACHE.clear()
    return {"ingested": results, "summary": ingest.summary()}


MAX_ARCHIVE_BYTES = 500 * 1024 * 1024


@app.post("/api/ingest/archive")
async def ingest_archive(request: Request, name: str = Query(..., min_length=1, max_length=200)) -> dict:
    """Import a NASA FIRMS Archive Download file (CSV, CSV.GZ or ZIP).

    The archive is the only route to science-quality (standard processing) data
    for older dates without a MAP_KEY, so it is a first-class input rather than
    a script-only path. The file is stored under ``data/raw/archive`` and every
    batch keeps its filename for provenance.
    """
    import zipfile

    safe = Path(name).name.replace("..", "_")
    suffix = "".join(Path(safe).suffixes).lower()
    if not (suffix.endswith(".csv") or suffix.endswith(".gz") or suffix.endswith(".zip")):
        raise HTTPException(status_code=400, detail="Upload a .csv, .csv.gz or .zip FIRMS archive file.")

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(body) > MAX_ARCHIVE_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than the 500 MB import limit.")

    config.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stored = config.ARCHIVE_DIR / safe
    stored.write_bytes(body)

    paths: list[Path] = []
    if safe.lower().endswith(".zip"):
        extract_dir = config.ARCHIVE_DIR / f"{stored.stem}_extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(stored) as archive:
                for member in archive.namelist():
                    if member.endswith("/"):
                        continue
                    if not member.lower().endswith((".csv", ".csv.gz", ".txt")):
                        continue
                    target = extract_dir / Path(member).name
                    with archive.open(member) as src, open(target, "wb") as dst:
                        dst.write(src.read())
                    paths.append(target)
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="That ZIP file could not be read.") from exc
        if not paths:
            raise HTTPException(status_code=400, detail="The ZIP contained no CSV files.")
    else:
        paths = [stored]

    try:
        result = ingest.ingest_paths(
            paths,
            kind="archive",
            description=f"NASA FIRMS archive import: {safe}",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from exc

    _SERIES_CACHE.clear()
    payload = result.to_dict()
    payload["summary"] = ingest.summary()
    if result.rows_kept == 0 and result.rows_duplicate > 0:
        payload["message"] = (
            "Every record in this file is already in the database "
            f"({result.rows_duplicate:,} duplicates skipped)."
        )
    elif result.rows_kept == 0:
        payload["message"] = (
            "No usable records were found. Check that this is a FIRMS active-fire CSV "
            f"({result.rows_rejected:,} rows rejected)."
        )
    return payload


@app.get("/api/ingest/status")
def ingest_status() -> dict:
    return ingest.summary() | {"caveat": DATA_CAVEAT}


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

def mount_frontend() -> None:
    if config.FRONTEND_DIST.exists() and (config.FRONTEND_DIST / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIST), html=True), name="ui")
    else:
        @app.get("/", response_class=HTMLResponse)
        def missing_ui() -> str:
            return (
                "<html><body style='background:#0b1220;color:#e2e8f0;font-family:system-ui;"
                "padding:48px;line-height:1.7'><h1>FIRETRACK API is running</h1>"
                "<p>The web interface has not been built yet.</p>"
                "<pre style='background:#111c2e;padding:16px;border-radius:8px'>"
                "cd frontend\npnpm install\npnpm build</pre>"
                "<p>API documentation: <a style='color:#f97316' href='/docs'>/docs</a></p>"
                "</body></html>"
            )


@app.exception_handler(HTTPException)
def http_error(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})