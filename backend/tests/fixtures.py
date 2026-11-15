"""Synthetic fixtures for the automated tests.

EVERY record created here is SYNTHETIC and exists only to exercise software
behaviour: known sensor rates, known coverage gaps, known anomalies. It is
labelled ``kinds='test_synthetic'`` in the database and is never used by the
application's demo data, which comes from NASA FIRMS.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

SYNTHETIC_DESCRIPTION = "SYNTHETIC TEST FIXTURE - not NASA observations"


def fresh_database() -> Path:
    """Point the application at a throw-away database and return its path.

    The file is created inside the project (``data/_test``) rather than the OS
    temp directory so the tests also work in sandboxes that block writes outside
    the working folder.
    """
    import uuid

    project_root = Path(__file__).resolve().parents[2]
    directory = project_root / "data" / "_test"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"test-{uuid.uuid4().hex[:8]}.db"
    os.environ["FIRETRACK_DB"] = str(path)
    from app import db

    db.reset_connection()
    db.init_db()
    return path


def _dets_for_day(day: str, sensor: str, count: int, platform: str, instrument: str,
                  product: str, confidence: str = "nominal"):
    from app import firms, geo

    out = []
    for index in range(count):
        lat = 0.75 + (index % 4) * 0.5
        lon = 0.75 + ((index // 4) % 4) * 0.5
        minutes = index % (24 * 60)
        acq_time = f"{minutes // 60:02d}{minutes % 60:02d}"
        cell_ix, cell_iy = geo.cell_index(lat, lon, 0.25)
        out.append(
            firms.Detection(
                sensor=sensor,
                instrument=instrument,
                platform=platform,
                product=product,
                processing="SP",
                source_file="synthetic_fixture.csv",
                lat=lat,
                lon=lon,
                acq_date=day,
                acq_time=acq_time,
                acq_ts=f"{day}T{acq_time[:2]}:{acq_time[2:]}:00Z",
                confidence=65 if confidence == "nominal" else 90,
                confidence_raw=confidence,
                confidence_class=confidence,
                frp=10.0,
                brightness=330.0,
                brightness_bg=290.0,
                scan=1.0,
                track=1.0,
                daynight="D",
                version="6.1",
                cell_ix=cell_ix,
                cell_iy=cell_iy,
            )
        )
    return out


def build_synthetic(
    start: str = "2019-01-01",
    end: str = "2021-12-31",
    modis_per_day: int = 3,
    viirs_per_day: int = 18,
    *,
    skip_months: tuple[str, ...] = (),
    skip_ranges: tuple[tuple[str, str], ...] = (),
    sensor_gaps: tuple[tuple[str, str, str], ...] = (),
    boost: dict[str, float] | None = None,
    spike_ranges: tuple[tuple[str, str, float], ...] = (),
) -> dict:
    """Create a synthetic MODIS+VIIRS record with a known seasonal pattern.

    Winter months carry three times the activity of summer months, so a seasonal
    calibration can be reasoned about exactly. ``skip_ranges`` removes whole days
    (simulating a data gap) and ``sensor_gaps`` removes one sensor over a date
    range, which is how single-sensor days are exercised.
    """
    from app import db, ingest

    boost = boost or {}
    current = date.fromisoformat(start)
    last = date.fromisoformat(end)
    detections = []

    def skipped(day_iso: str) -> bool:
        return any(lo <= day_iso <= hi for lo, hi in skip_ranges)

    def sensor_gap(day_iso: str, sensor: str) -> bool:
        return any(lo <= day_iso <= hi and s == sensor for lo, hi, s in sensor_gaps)

    while current <= last:
        day = current.isoformat()
        month = current.month
        if f"{current.year}-{month:02d}" in skip_months or skipped(day):
            current += timedelta(days=1)
            continue
        seasonal = 3.0 if month in (1, 2, 12) else 1.0
        scale = seasonal * boost.get(f"{current.year}-{month:02d}", 1.0)
        # A short spike mimics a real fire episode: a few days far above normal.
        for lo, hi, factor in spike_ranges:
            if lo <= day <= hi:
                scale *= factor
        if not sensor_gap(day, "modis"):
            detections.extend(
                _dets_for_day(day, "modis", int(round(modis_per_day * scale)),
                              "Terra + Aqua", "MODIS", "MODIS C6.1")
            )
        if not sensor_gap(day, "viirs_noaa20"):
            detections.extend(
                _dets_for_day(day, "viirs_noaa20", int(round(viirs_per_day * scale)),
                              "NOAA-20", "VIIRS", "VIIRS C2")
            )
        current += timedelta(days=1)

    result = ingest.ingest_detections(
        detections,
        kind="test_synthetic",
        description=SYNTHETIC_DESCRIPTION,
        files=["synthetic_fixture.csv"],
    )

    # The ingester marks a sensor's whole date span as observed, because real
    # FIRMS products are daily-complete. To model a genuine delivery gap the
    # availability rows for the skipped dates must be removed afterwards.
    if skip_ranges:
        for lo, hi in skip_ranges:
            db.connect().execute(
                "DELETE FROM sensor_days WHERE acq_date BETWEEN ? AND ?", (lo, hi)
            )
    for lo, hi, sensor in sensor_gaps:
        db.connect().execute(
            "DELETE FROM sensor_days WHERE sensor = ? AND acq_date BETWEEN ? AND ?",
            (sensor, lo, hi),
        )
    db.connect().commit()

    return result.to_dict()


_FIXTURE: dict | None = None


def get_fixture() -> dict:
    """Build the shared synthetic fixture once per test run.

    Four calendar years are generated so that a boosted month has at least three
    baseline years available for the anomaly test.
    """
    global _FIXTURE
    if _FIXTURE is None:
        fresh_database()
        _FIXTURE = build_synthetic(
            start="2018-01-01",
            end="2021-12-31",
            skip_ranges=(("2020-06-05", "2020-06-14"),),
            sensor_gaps=(("2020-07-01", "2020-07-03", "viirs_noaa20"),),
            boost={"2021-02": 2.5},
        )
    return _FIXTURE


AOI_BBOX = (0.0, 0.0, 4.0, 4.0)
