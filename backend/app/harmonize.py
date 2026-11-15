"""MODIS / VIIRS harmonisation.

The problem in one sentence
---------------------------
MODIS (1 km, 2000-) and VIIRS (375 m, 2012-) do not count the same fires, and
the constellation changes over time (Aqua in 2002, S-NPP in 2012, NOAA-20 in
2018, NOAA-21 in 2023). A naive "sum of all hotspots" therefore jumps whenever
a sensor is added or retired, and a naive comparison of 2005 with 2025 compares
different instruments.

The method implemented here
---------------------------
1. **Common spatial unit.** Both instruments are aggregated onto the same
   0.25 degree grid. Every statistic is computed on that grid, so a "detection"
   means the same spatial thing for both sensors.
2. **Coverage normalisation.** Each date carries the set of sensors that were
   actually observing. Activity is rescaled to a constant "full constellation"
   reference, so a day observed by two VIIRS platforms is directly comparable
   with a MODIS-only day in 2005. Missing observations are never treated as
   zero: a date with no observing sensor yields ``None``, not ``0``.
3. **Overlap-period ratio calibration.** During the period when MODIS and a
   VIIRS platform both observed the same area, the ratio of their mean daily
   detection rates is measured on the *same dates*. That ratio becomes the
   sensor weight, converting VIIRS detections into MODIS-equivalent units.
   The ratio is only trusted when the overlap is long enough
   (>= 60 co-observed dates) and stable across sub-periods (CV <= 0.35).
   Otherwise the weights are set to 1 and the result is explicitly labelled
   as *coverage-normalised counts*, not a calibrated index.

What this method does NOT do
----------------------------
* It does not claim that one MODIS pixel equals one VIIRS pixel.
* It does not remove cloud effects: FIRMS reports detections, not observation
  attempts, so a cloudy day and a fire-free day can look the same at pixel level.
  This limitation is why sub-monthly comparisons require the coverage gate.
* The ratio calibration is a single multiplicative correction; it cannot fix a
  resolution-driven non-linearity (VIIRS resolves small fires MODIS misses).
  It is a bias correction, not a full radiometric harmonisation.
"""

from __future__ import annotations

import bisect
import math
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable, Sequence

from . import config, db, geo

# Confidence filter -> which stored classes to include.
CONFIDENCE_FILTERS = {
    "all": ("n_high", "n_nominal", "n_low"),
    "nominal": ("n_high", "n_nominal"),
    "high": ("n_high",),
}


def _cell_area_km2(lat_center: float, res: float) -> float:
    """Area of one grid cell at its central latitude."""
    dy = 111.195 * res
    dx = 111.195 * res * math.cos(math.radians(lat_center))
    return abs(dx * dy)


@dataclass
class AOISeries:
    """Daily detection aggregates for one AOI, per sensor."""

    aoi: geo.AOI
    start: str
    end: str
    dates: list[str]
    sensors: list[str]
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    frp: dict[str, dict[str, float]] = field(default_factory=dict)
    observed: dict[str, set[str]] = field(default_factory=dict)
    grid_cells: int = 0
    grid_area_km2: float = 0.0
    n_detections: int = 0

    def count(self, sensor: str, day: str) -> int:
        return self.counts.get(sensor, {}).get(day, 0)

    @property
    def density_divisor(self) -> float:
        """Detections -> detections per 1000 km2."""
        return (self.grid_area_km2 / 1000.0) if self.grid_area_km2 > 0 else 1.0


def _aoi_cells(aoi: geo.AOI, res: float) -> list[tuple[int, int, float]]:
    """Grid cells whose centre lies inside the AOI, with their cell area."""
    w, s, e, n = aoi.bbox
    ix0, iy0 = geo.cell_index(s, w, res)
    ix1, iy1 = geo.cell_index(n, e, res)
    out: list[tuple[int, int, float]] = []
    for ix in range(ix0, ix1 + 1):
        lat_c = (ix + 0.5) * res - 90.0
        for iy in range(iy0, iy1 + 1):
            lon_c = (iy + 0.5) * res - 180.0
            if aoi.contains(lat_c, lon_c):
                out.append((ix, iy, _cell_area_km2(lat_c, res)))
    return out


def load_series(
    aoi: geo.AOI,
    start: str | None = None,
    end: str | None = None,
    confidence: str = "all",
    sensors: Sequence[str] | None = None,
) -> AOISeries:
    """Load daily, per-sensor counts for an AOI on the common grid."""
    db.init_db()
    res = config.GRID_DEG
    cells = _aoi_cells(aoi, res)
    if not cells:
        raise ValueError("The selected area is smaller than one analysis grid cell.")

    cell_index = {(ix, iy): area for ix, iy, area in cells}
    cell_ixs = sorted({c[0] for c in cells})
    cell_iys = sorted({c[1] for c in cells})

    obs_rows = db.query("SELECT sensor, acq_date FROM sensor_days WHERE observed = 1")
    all_dates = sorted({row["acq_date"] for row in obs_rows})
    if start:
        all_dates = [d for d in all_dates if d >= start]
    if end:
        all_dates = [d for d in all_dates if d <= end]
    lo = all_dates[0] if all_dates else (start or "2000-01-01")
    hi = all_dates[-1] if all_dates else (end or "2100-01-01")

    observed: dict[str, set[str]] = {}
    for row in obs_rows:
        observed.setdefault(row["sensor"], set()).add(row["acq_date"])
    if start:
        observed = {k: {d for d in v if d >= start} for k, v in observed.items()}
    if end:
        observed = {k: {d for d in v if d <= end} for k, v in observed.items()}
    observed = {k: v for k, v in observed.items() if v}

    wanted = set(sensors) if sensors else set(config.SENSORS)
    columns = CONFIDENCE_FILTERS.get(confidence, CONFIDENCE_FILTERS["all"])
    count_expr = " + ".join(columns)

    counts: dict[str, dict[str, int]] = {}
    frp: dict[str, dict[str, float]] = {}
    n_detections = 0
    used_cells: set[tuple[int, int]] = set()

    # Query in latitude bands to keep SQLite's index effective on large AOIs.
    batch = 40
    for i in range(0, len(cell_ixs), batch):
        band = cell_ixs[i : i + batch]
        placeholders = ",".join("?" for _ in band)
        rows = db.query(
            f"""
            SELECT cell_ix, cell_iy, acq_date, sensor, ({count_expr}) AS n, frp_sum
            FROM daily_cells
            WHERE cell_ix IN ({placeholders})
              AND cell_iy BETWEEN ? AND ?
              AND acq_date BETWEEN ? AND ?
            """,
            (*band, min(cell_iys), max(cell_iys), lo, hi),
        )
        for row in rows:
            key = (row["cell_ix"], row["cell_iy"])
            if key not in cell_index:
                continue
            sensor = row["sensor"]
            if sensor not in wanted:
                continue
            n = row["n"] or 0
            if n <= 0:
                continue
            used_cells.add(key)
            bucket = counts.setdefault(sensor, {})
            bucket[row["acq_date"]] = bucket.get(row["acq_date"], 0) + n
            frp_bucket = frp.setdefault(sensor, {})
            if row["frp_sum"]:
                frp_bucket[row["acq_date"]] = frp_bucket.get(row["acq_date"], 0.0) + row["frp_sum"]
            n_detections += n

    sensors_present = sorted(observed.keys(), key=_sensor_sort_key)
    area = sum(cell_index[c] for c in used_cells) if used_cells else sum(a for _, _, a in cells)

    return AOISeries(
        aoi=aoi,
        start=lo,
        end=hi,
        dates=all_dates,
        sensors=sensors_present,
        counts=counts,
        frp=frp,
        observed=observed,
        grid_cells=len(cells),
        grid_area_km2=area,
        n_detections=n_detections,
    )


def _sensor_sort_key(sensor: str) -> int:
    order = ["modis", "viirs_snpp", "viirs_noaa20", "viirs_noaa21"]
    return order.index(sensor) if sensor in order else 99


@dataclass
class Calibration:
    """Sensor weights derived from the MODIS/VIIRS overlap period."""

    status: str
    weights: dict[str, float]
    rates: dict[str, float]
    paired_days: dict[str, int]
    ratios: dict[str, float | None]
    ratio_cv: float | None
    reference_sensor: str = "modis"
    notes: list[str] = field(default_factory=list)

    @property
    def calibrated(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "calibrated": self.calibrated,
            "reference_sensor": self.reference_sensor,
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "rates_per_day": {k: round(v, 4) for k, v in self.rates.items()},
            "paired_days": self.paired_days,
            "ratios": {k: (round(v, 4) if v is not None else None) for k, v in self.ratios.items()},
            "ratio_cv": round(self.ratio_cv, 4) if self.ratio_cv is not None else None,
            "unit": ("MODIS-equivalent detections" if self.calibrated
                     else "coverage-normalised detections"),
            "notes": self.notes,
        }


def calibrate(series: AOISeries, min_overlap_days: int | None = None) -> Calibration:
    """Derive per-sensor multiplicative weights from co-observed dates.

    Weight w_s converts a detection by sensor s into reference-sensor-equivalent
    units: the reference (MODIS) keeps w = 1, a VIIRS platform with twice the
    detection rate gets w = 0.5.
    """
    min_overlap = min_overlap_days or config.MIN_OVERLAP_DAYS_FOR_CALIBRATION
    notes: list[str] = []
    weights = {s: 1.0 for s in series.sensors}
    rates: dict[str, float] = {}
    paired_days: dict[str, int] = {}
    ratios: dict[str, float | None] = {}

    for sensor in series.sensors:
        days = series.observed.get(sensor, set())
        if days:
            total = sum(series.count(sensor, d) for d in days)
            rates[sensor] = total / len(days)

    if "modis" not in series.sensors:
        notes.append("No MODIS record for this area; calibration reference unavailable.")
        return Calibration("single_sensor", weights, rates, paired_days, ratios, None, notes=notes)

    viiirs = [s for s in series.sensors if s.startswith("viirs")]
    if not viiirs:
        notes.append("No VIIRS record for this area; only MODIS observations exist.")
        return Calibration("single_sensor", weights, rates, paired_days, ratios, None, notes=notes)

    all_block_ratios: list[float] = []
    for sensor in viiirs:
        common = sorted(series.observed.get("modis", set()) & series.observed.get(sensor, set()))
        paired_days[sensor] = len(common)
        if not common:
            ratios[sensor] = None
            notes.append(f"No dates where MODIS and {sensor} both observed this area.")
            continue
        modis_mean = sum(series.count("modis", d) for d in common) / len(common)
        viirs_mean = sum(series.count(sensor, d) for d in common) / len(common)
        if viirs_mean <= 0:
            ratios[sensor] = None
            notes.append(f"{sensor} recorded no detections on the co-observed dates.")
            continue
        ratio = modis_mean / viirs_mean
        ratios[sensor] = ratio

        # Stability: ratio computed in four consecutive blocks of the overlap.
        if len(common) >= 16:
            block = len(common) // 4
            block_ratios = []
            for b in range(4):
                chunk = common[b * block : (b + 1) * block] if b < 3 else common[3 * block :]
                if not chunk:
                    continue
                mv = sum(series.count("modis", d) for d in chunk) / len(chunk)
                vv = sum(series.count(sensor, d) for d in chunk) / len(chunk)
                if vv > 0:
                    block_ratios.append(mv / vv)
            all_block_ratios.extend(block_ratios)

        if len(common) < min_overlap:
            notes.append(
                f"{sensor}: {len(common)} co-observed days is below the {min_overlap}-day "
                "minimum, so the ratio is reported but not applied."
            )
            continue
        weights[sensor] = ratio

    ratio_cv = None
    if len(all_block_ratios) >= 2:
        mean = statistics.fmean(all_block_ratios)
        if mean > 0:
            ratio_cv = statistics.pstdev(all_block_ratios) / mean

    if ratio_cv is not None and ratio_cv > config.MAX_RATIO_CV_FOR_CALIBRATION:
        notes.append(
            f"The overlap ratio varies too much between sub-periods (CV {ratio_cv:.2f} > "
            f"{config.MAX_RATIO_CV_FOR_CALIBRATION}); calibration rejected."
        )
        return Calibration("unstable_ratio", {s: 1.0 for s in series.sensors},
                           rates, paired_days, ratios, ratio_cv, notes=notes)

    applied = [s for s in viiirs if weights.get(s, 1.0) != 1.0]
    if not applied:
        notes.append(
            "Overlap period is too short to calibrate: showing coverage-normalised "
            "counts with equal sensor weights instead of a calibrated index."
        )
        return Calibration("insufficient_overlap", weights, rates, paired_days, ratios,
                           ratio_cv, notes=notes)

    status = "ok"
    if ratio_cv is not None:
        notes.append(f"Overlap ratio stability: CV {ratio_cv:.2f} across 4 sub-periods.")
    return Calibration(status, weights, rates, paired_days, ratios, ratio_cv, notes=notes)


@dataclass
class DailyPoint:
    date: str
    per_sensor: dict[str, int]
    raw_total: int
    harmonized: float | None
    sensors_observing: list[str]
    coverage: float            # observing sensors / full constellation
    frp_total: float           # sum of FRP across sensors - NOT harmonised
    frp_by_sensor: dict[str, float]
    observed: bool

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "per_sensor": self.per_sensor,
            "raw_total": self.raw_total,
            "harmonized": round(self.harmonized, 2) if self.harmonized is not None else None,
            "sensors_observing": self.sensors_observing,
            "coverage": round(self.coverage, 3),
            # FRP is reported per sensor. The total is a plain sum of raw sensor
            # values and is deliberately labelled as such: MODIS and VIIRS
            # retrieve FRP differently, so their sum is not a harmonised quantity.
            "frp_by_sensor": {k: round(v, 1) for k, v in self.frp_by_sensor.items()},
            "frp_total": round(self.frp_total, 1),
            "frp_total_label": "sum of raw sensor FRP (not harmonised)",
            "observed": self.observed,
        }


class HarmonizedSeries:
    """The merged, coverage-aware daily burning-activity series."""

    def __init__(self, series: AOISeries, calibration: Calibration):
        self.series = series
        self.calibration = calibration
        self.full_mix_expected = sum(
            calibration.weights.get(s, 1.0) * calibration.rates.get(s, 0.0)
            for s in series.sensors
        )
        self._points: dict[str, DailyPoint] = {}
        self._build()
        self._dates = sorted(self._points)

    def _build(self) -> None:
        s = self.series
        weights = self.calibration.weights
        rates = self.calibration.rates
        for day in s.dates:
            observing = sorted(
                (sensor for sensor in s.sensors if day in s.observed.get(sensor, set())),
                key=_sensor_sort_key,
            )
            per_sensor = {sensor: s.count(sensor, day) for sensor in observing}
            raw = sum(per_sensor.values())
            frp_by_sensor = {
                sensor: s.frp.get(sensor, {}).get(day, 0.0) for sensor in observing
            }
            frp_total = sum(frp_by_sensor.values())
            coverage = len(observing) / len(s.sensors) if s.sensors else 0.0

            if not observing:
                harmonized = None
            else:
                expected_here = sum(weights.get(sensor, 1.0) * rates.get(sensor, 0.0)
                                    for sensor in observing)
                weighted = sum(weights.get(sensor, 1.0) * per_sensor.get(sensor, 0)
                               for sensor in observing)
                if expected_here > 0 and self.full_mix_expected > 0:
                    harmonized = weighted * (self.full_mix_expected / expected_here)
                else:
                    harmonized = float(weighted)
            self._points[day] = DailyPoint(
                date=day,
                per_sensor=per_sensor,
                raw_total=raw,
                harmonized=harmonized,
                sensors_observing=observing,
                coverage=coverage,
                frp_total=frp_total,
                frp_by_sensor=frp_by_sensor,
                observed=bool(observing),
            )

    def points(self, start: str | None = None, end: str | None = None) -> list[DailyPoint]:
        lo = 0 if start is None else bisect.bisect_left(self._dates, start)
        hi = len(self._dates) if end is None else bisect.bisect_right(self._dates, end)
        return [self._points[d] for d in self._dates[lo:hi]]

    def day(self, day: str) -> DailyPoint | None:
        return self._points.get(day)

    def values(self, start: str | None = None, end: str | None = None) -> list[float]:
        return [p.harmonized for p in self.points(start, end) if p.harmonized is not None]


def build(
    aoi: geo.AOI,
    start: str | None = None,
    end: str | None = None,
    confidence: str = "all",
    sensors: Sequence[str] | None = None,
) -> HarmonizedSeries:
    series = load_series(aoi, start=start, end=end, confidence=confidence, sensors=sensors)
    calibration = calibrate(series)
    return HarmonizedSeries(series, calibration)


# ---------------------------------------------------------------------------
# Period aggregation helpers
# ---------------------------------------------------------------------------

def days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def month_dates(year: int, month: int) -> list[str]:
    n = days_in_month(year, month)
    return [date(year, month, d).isoformat() for d in range(1, n + 1)]


def aggregate_period(
    harmonised: HarmonizedSeries,
    start: str,
    end: str,
) -> dict:
    """Summarise a period with explicit coverage handling.

    ``expected_total`` is the coverage-corrected estimate: the mean of the
    observed days multiplied by the length of the period. It is only reported
    alongside its coverage so a consumer can reject it (the API does this for
    months below ``MIN_COVERAGE_FRACTION``).
    """
    points = harmonised.points(start, end)
    observed = [p for p in points if p.harmonized is not None]
    n_days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    record = harmonised.series
    # Coverage alone is not enough: a year that is still in progress can pass an
    # 80% coverage test while whole months are simply missing. A period only
    # counts as complete when the record actually spans it end to end.
    in_record = record.start <= start and end <= record.end
    span_ok = in_record or not config.REQUIRE_FULL_PERIOD
    per_sensor: dict[str, int] = {}
    frp_by_sensor: dict[str, float] = {}
    for p in observed:
        for sensor, n in p.per_sensor.items():
            per_sensor[sensor] = per_sensor.get(sensor, 0) + n
        for sensor, value in p.frp_by_sensor.items():
            frp_by_sensor[sensor] = frp_by_sensor.get(sensor, 0.0) + value
    values = [p.harmonized for p in observed]
    mean_daily = statistics.fmean(values) if values else None
    coverage = len(observed) / n_days if n_days else 0.0
    return {
        "start": start,
        "end": end,
        "days_in_period": n_days,
        "observed_days": len(observed),
        "coverage": round(coverage, 3),
        "in_record": in_record,
        "complete": coverage >= config.MIN_COVERAGE_FRACTION and span_ok,
        "observed_total": round(sum(values), 2) if values else None,
        "expected_total": round(mean_daily * n_days, 2) if mean_daily is not None else None,
        "mean_daily": round(mean_daily, 3) if mean_daily is not None else None,
        "median_daily": round(statistics.median(values), 3) if values else None,
        "max_daily": round(max(values), 2) if values else None,
        "raw_total": sum(p.raw_total for p in observed),
        "per_sensor": per_sensor,
        "frp_by_sensor": {k: round(v, 1) for k, v in frp_by_sensor.items()},
        "frp_total": round(sum(frp_by_sensor.values()), 1),
        "frp_total_label": "sum of raw sensor FRP (not harmonised)",
        "sensors": sorted(per_sensor, key=_sensor_sort_key),
        "has_data": bool(values),
    }


def daily_median_baseline(
    harmonised: HarmonizedSeries,
    month: int,
    exclude_year: int | None = None,
    min_years: int = 3,
) -> dict:
    """Historical median monthly activity for one calendar month.

    Only *complete* months enter the baseline, so a month that was observed for
    three days cannot drag the median down. ``None`` values stay ``None``.
    """
    years: list[int] = []
    for day in harmonised.series.dates:
        y, m, _ = (int(x) for x in day.split("-"))
        if m == month and (exclude_year is None or y != exclude_year) and y not in years:
            years.append(y)

    samples: list[dict] = []
    for year in sorted(years):
        start = date(year, month, 1).isoformat()
        end = date(year, month, days_in_month(year, month)).isoformat()
        agg = aggregate_period(harmonised, start, end)
        if agg["complete"] and agg["expected_total"] is not None:
            samples.append({"year": year, **agg})

    values = [s["expected_total"] for s in samples]
    result = {
        "month": month,
        "years_used": [s["year"] for s in samples],
        "n_years": len(samples),
        "median": None,
        "p25": None,
        "p75": None,
        "mad": None,
        "min": None,
        "max": None,
        "sufficient": len(samples) >= min_years,
        "excluded_years": sorted(
            y for y in years
            if y not in {s["year"] for s in samples} and (exclude_year is None or y != exclude_year)
        ),
        "samples": samples,
    }
    if not values:
        return result
    result["median"] = round(statistics.median(values), 2)
    if len(values) >= 4:
        q = statistics.quantiles(values, n=4)
        result["p25"], result["p75"] = round(q[0], 2), round(q[2], 2)
    result["min"], result["max"] = round(min(values), 2), round(max(values), 2)
    med = statistics.median(values)
    result["mad"] = round(statistics.median([abs(v - med) for v in values]), 3)
    return result


def compare_to_baseline(observed: float | None, baseline: dict) -> dict:
    """Deviation from the historical median, with a robust z-score."""
    median = baseline.get("median")
    out = {
        "observed": observed,
        "median": median,
        "absolute_deviation": None,
        "percent_deviation": None,
        "z_score": None,
        "direction": "unknown",
        "percent_reliable": False,
    }
    if observed is None or median is None:
        return out
    out["absolute_deviation"] = round(observed - median, 2)
    out["direction"] = "above" if observed > median else ("below" if observed < median else "equal")
    if median > 0:
        out["percent_deviation"] = round((observed - median) / median * 100.0, 1)
        # Below a handful of detections a percentage is numerically unstable
        # and misleading: report it only when the baseline is meaningful.
        out["percent_reliable"] = median >= 5
    mad = baseline.get("mad")
    if mad and mad > 0:
        out["z_score"] = round((observed - median) / (1.4826 * mad), 2)
    return out
