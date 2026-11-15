"""MODIS vs VIIRS agreement analysis.

This module answers the question the challenge is really about: *how different
are the two records, and where?* It deliberately reports several complementary
measures rather than a single "accuracy" number, because no ground-truth fire
perimeter is available here:

* **Temporal agreement** - correlation of the paired daily series over dates both
  instruments observed the area.
* **Magnitude bias** - ratio of mean daily detections (the quantity the
  harmonisation calibration uses).
* **Spatial agreement** - correlation and overlap of per-cell activity, which
  shows whether both sensors see the *same places* even when counts differ.
* **Co-detection** - fraction of MODIS detections with a VIIRS detection within
  1 km on the same day: the most direct "do they see the same fire" test.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Sequence

from . import config, db, geo
from .harmonize import AOISeries, HarmonizedSeries, _sensor_sort_key


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    n = len(x)
    if n < 3:
        return None
    mx, my = statistics.fmean(x), statistics.fmean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = math.sqrt(sum((a - mx) ** 2 for a in x))
    dy = math.sqrt(sum((b - my) ** 2 for b in y))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) < 3:
        return None
    return pearson(_ranks(x), _ranks(y))


def _log1p(values: Sequence[float]) -> list[float]:
    return [math.log1p(max(0.0, v)) for v in values]


def _cell_totals(aoi: geo.AOI, sensors: Sequence[str], start: str, end: str) -> dict:
    """Per-grid-cell detection totals for the given sensors."""
    res = config.GRID_DEG
    w, s, e, n = aoi.bbox
    ix0, iy0 = geo.cell_index(s, w, res)
    ix1, iy1 = geo.cell_index(n, e, res)
    placeholders = ",".join("?" for _ in sensors)
    rows = db.query(
        f"""
        SELECT cell_ix, cell_iy, sensor, SUM(n) AS n
        FROM daily_cells
        WHERE sensor IN ({placeholders})
          AND cell_ix BETWEEN ? AND ? AND cell_iy BETWEEN ? AND ?
          AND acq_date BETWEEN ? AND ?
        GROUP BY cell_ix, cell_iy, sensor
        """,
        (*sensors, ix0, ix1, iy0, iy1, start, end),
    )
    out: dict[str, dict[tuple[int, int], int]] = {s: {} for s in sensors}
    for row in rows:
        key = (row["cell_ix"], row["cell_iy"])
        lat = (key[0] + 0.5) * res - 90.0
        lon = (key[1] + 0.5) * res - 180.0
        if not aoi.contains(lat, lon):
            continue
        out[row["sensor"]][key] = row["n"]
    return out


def co_detection(
    aoi: geo.AOI,
    start: str,
    end: str,
    radius_km: float = 1.0,
    max_modis: int = 15000,
) -> dict:
    """Fraction of MODIS detections matched by a VIIRS detection nearby, same day.

    Matching is done on a 0.02 degree bucket grid (about 2 km at the equator) so
    the comparison stays linear in the number of detections.
    """
    w, s, e, n = aoi.bbox
    base = db.query(
        """
        SELECT lat, lon, acq_date FROM detections
        WHERE sensor = 'modis' AND acq_date BETWEEN ? AND ?
          AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?
        """,
        (start, end, s, n, w, e),
    )
    modis_pts = [(r["lat"], r["lon"], r["acq_date"]) for r in base if aoi.contains(r["lat"], r["lon"])]
    viirs_rows = db.query(
        """
        SELECT lat, lon, acq_date FROM detections
        WHERE sensor LIKE 'viirs%' AND acq_date BETWEEN ? AND ?
          AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?
        """,
        (start, end, s, n, w, e),
    )
    viirs_buckets: dict[tuple[str, int, int], list[tuple[float, float]]] = defaultdict(list)
    for r in viirs_rows:
        if not aoi.contains(r["lat"], r["lon"]):
            continue
        key = (r["acq_date"], int(r["lat"] // 0.02), int(r["lon"] // 0.02))
        viirs_buckets[key].append((r["lat"], r["lon"]))

    if not modis_pts:
        return {"available": False, "reason": "No MODIS detections in this period and area.",
                "matched": 0, "checked": 0}
    sample = modis_pts if len(modis_pts) <= max_modis else modis_pts[:: max(1, len(modis_pts) // max_modis)]

    cos_lat = math.cos(math.radians(sum(p[0] for p in sample) / len(sample)))
    matched = 0
    for lat, lon, day in sample:
        ix, iy = int(lat // 0.02), int(lon // 0.02)
        found = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for vlat, vlon in viirs_buckets.get((day, ix + dx, iy + dy), ()):
                    dlat = (vlat - lat) * 111.195
                    dlon = (vlon - lon) * 111.195 * cos_lat
                    if math.hypot(dlat, dlon) <= radius_km:
                        found = True
                        break
                if found:
                    break
            if found:
                break
        matched += 1 if found else 0

    fraction = matched / len(sample) if sample else None
    return {
        "available": True,
        "radius_km": radius_km,
        "modis_detections": len(modis_pts),
        "sampled": len(sample),
        "matched": matched,
        "fraction": round(fraction, 4) if fraction is not None else None,
        "note": (
            "Same-day, same-location matching only. A MODIS pixel is 1 km and a VIIRS "
            "pixel 375 m, so one MODIS detection can correspond to several VIIRS detections "
            "and vice versa; this is an agreement indicator, not a validation score."
        ),
    }


def compare_sensors(
    harmonised: HarmonizedSeries,
    start: str | None = None,
    end: str | None = None,
    include_co_detection: bool = True,
) -> dict:
    series: AOISeries = harmonised.series
    dates = [d for d in series.dates if (start is None or d >= start) and (end is None or d <= end)]
    viiirs = [s for s in series.sensors if s.startswith("viirs")]
    if "modis" not in series.sensors or not viiirs:
        return {
            "available": False,
            "reason": "Both MODIS and at least one VIIRS platform must have observations "
                      "in this area and period to compare them.",
            "sensors": [_meta(s) for s in series.sensors],
        }

    paired_days = [
        d for d in dates
        if d in series.observed.get("modis", set())
        and any(d in series.observed.get(v, set()) for v in viiirs)
    ]
    viirs_daily = {d: sum(series.count(v, d) for v in viiirs) for d in paired_days}
    modis_daily = {d: series.count("modis", d) for d in paired_days}

    mv = [modis_daily[d] for d in paired_days]
    vv = [viirs_daily[d] for d in paired_days]
    mean_m = statistics.fmean(mv) if mv else None
    mean_v = statistics.fmean(vv) if vv else None
    per_platform = {}
    for sensor in viiirs:
        common = [d for d in dates if d in series.observed.get("modis", set())
                  and d in series.observed.get(sensor, set())]
        if not common:
            per_platform[sensor] = {"paired_days": 0}
            continue
        m = [series.count("modis", d) for d in common]
        v = [series.count(sensor, d) for d in common]
        per_platform[sensor] = {
            "paired_days": len(common),
            "modis_mean": round(statistics.fmean(m), 2),
            "viirs_mean": round(statistics.fmean(v), 2),
            "ratio_modis_over_viirs": round(statistics.fmean(m) / statistics.fmean(v), 4)
            if statistics.fmean(v) > 0 else None,
            "pearson_log": _round(pearson(_log1p(m), _log1p(v))),
            "spearman": _round(spearman(m, v)),
        }

    cells = _cell_totals(series.aoi, ["modis", *viiirs], series.start if start is None else start,
                         series.end if end is None else end)
    modis_cells = cells.get("modis", {})
    viirs_cells: dict[tuple[int, int], int] = defaultdict(int)
    for v in viiirs:
        for key, n in cells.get(v, {}).items():
            viirs_cells[key] += n
    shared = sorted(set(modis_cells) & set(viirs_cells))
    cell_pairs = [(modis_cells[k], viirs_cells[k]) for k in shared]
    active_m = {k for k, n in modis_cells.items() if n > 0}
    active_v = {k for k, n in viirs_cells.items() if n > 0}
    union = active_m | active_v
    jaccard = len(active_m & active_v) / len(union) if union else None

    co = co_detection(series.aoi, start or series.start, end or series.end) if include_co_detection else None

    daily_series = [
        {"date": day, "modis": modis_daily[day], "viirs": viirs_daily[day]}
        for day in paired_days
    ]
    bucket = "day"
    if len(daily_series) > 900:
        grouped: dict[str, dict[str, float]] = {}
        for row in daily_series:
            key = row["date"][:7]
            entry = grouped.setdefault(key, {"modis": 0.0, "viirs": 0.0, "n": 0})
            entry["modis"] += row["modis"]
            entry["viirs"] += row["viirs"]
            entry["n"] += 1
        daily_series = [
            {"date": key, "modis": round(value["modis"] / value["n"], 2),
             "viirs": round(value["viirs"] / value["n"], 2)}
            for key, value in sorted(grouped.items())
        ]
        bucket = "month"

    return {
        "available": True,
        "period": {"start": start or series.start, "end": end or series.end},
        "paired_days": len(paired_days),
        "daily_series": daily_series,
        "daily_bucket": bucket,
        "daily": {
            "modis_mean": round(mean_m, 2) if mean_m is not None else None,
            "viirs_mean": round(mean_v, 2) if mean_v is not None else None,
            "ratio_modis_over_viirs": round(mean_m / mean_v, 4) if mean_v else None,
            "pearson_log": _round(pearson(_log1p(mv), _log1p(vv))),
            "spearman": _round(spearman(mv, vv)),
            "median_daily_ratio": _round(
                statistics.median([m / v for m, v in zip(mv, vv) if v > 0]) if any(vv) else None
            ),
        },
        "per_platform": per_platform,
        "spatial": {
            "modis_active_cells": len(active_m),
            "viirs_active_cells": len(active_v),
            "cells_in_both": len(active_m & active_v),
            "jaccard": _round(jaccard),
            "spearman_cell_totals": _round(spearman([p[0] for p in cell_pairs], [p[1] for p in cell_pairs]))
            if len(cell_pairs) >= 3 else None,
            "cells_compared": len(cell_pairs),
        },
        "co_detection": co,
        "sensors": [_meta(s) for s in series.sensors],
        "interpretation": {
            "ratio_below_one": "VIIRS detects more hotspots than MODIS in this area, as expected "
                               "from its 375 m pixels and lower detection threshold.",
            "jaccard": "Jaccard is the share of active cells seen by both instruments; values well "
                       "below 1 mean the two records highlight different parts of the landscape.",
        },
        "limitations": [
            "Different pixel sizes mean counts are not interchangeable (a MODIS pixel can contain "
            "several VIIRS detections).",
            "VIIRS and MODIS overpass times differ, so a fast-moving fire front may be caught by "
            "only one instrument on a given day.",
            "Cloud cover affects both instruments but not identically.",
        ],
        "context": {
            "aoi": series.aoi.to_dict(),
            "grid_deg": config.GRID_DEG,
        },
    }


def _round(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None else None


def _meta(sensor: str) -> dict:
    info = config.SENSORS.get(sensor, {})
    return {"id": sensor, "label": info.get("label", sensor), "colour": info.get("colour", "#94a3b8"),
            "pixel_km": info.get("pixel_km")}


def transition_diagnostics(harmonised: HarmonizedSeries) -> dict:
    """Detect step changes at known sensor-introduction dates.

    The harmonised series should show a smaller step than raw pooled counts.
    This is a *diagnostic*, not a validation score: with a short record there are
    no transitions to measure and the result says so.
    """
    series = harmonised.series
    changes = []
    for sensor, info in config.SENSORS.items():
        if sensor not in series.sensors:
            continue
        start = info.get("records_from")
        if not start or not (series.start < start <= series.end):
            continue
        points = {p.date: p for p in harmonised.points()}
        before = [p for d, p in points.items() if d < start and p.harmonized is not None]
        after = [p for d, p in points.items() if d >= start and p.harmonized is not None]
        if len(before) < 5 or len(after) < 5:
            changes.append({"sensor": sensor, "date": start, "available": False,
                            "reason": "not enough observations on both sides of the transition"})
            continue
        h_before = statistics.fmean([p.harmonized for p in before])
        h_after = statistics.fmean([p.harmonized for p in after])
        r_before = statistics.fmean([p.raw_total for p in before])
        r_after = statistics.fmean([p.raw_total for p in after])
        changes.append({
            "sensor": sensor,
            "date": start,
            "available": True,
            "harmonized_before": round(h_before, 2),
            "harmonized_after": round(h_after, 2),
            "harmonized_step_pct": round((h_after - h_before) / h_before * 100, 2) if h_before else None,
            "raw_before": round(r_before, 2),
            "raw_after": round(r_after, 2),
            "raw_step_pct": round((r_after - r_before) / r_before * 100, 2) if r_before else None,
        })
    return {
        "transitions": changes,
        "note": "A smaller step in the harmonised series than in raw counts is the intended effect "
                "of coverage normalisation, but a transition inside a seasonal change cannot be "
                "separated from it by this diagnostic.",
    }
