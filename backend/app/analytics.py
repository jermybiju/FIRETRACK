"""Burning-activity calendar, historical baselines, trends and anomalies.

Everything here is computed from :class:`harmonize.HarmonizedSeries`, so the
calendar and the statistics always share the same coverage handling. In
particular, a month that was only partly observed is marked incomplete and is
excluded from the historical median - it is never silently reported as "low
activity".
"""

from __future__ import annotations

import math
import statistics
from datetime import date
from typing import Iterable

from . import config, db, geo
from .harmonize import (
    AOISeries,
    HarmonizedSeries,
    _sensor_sort_key,
    aggregate_period,
    compare_to_baseline,
    daily_median_baseline,
    days_in_month,
)

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _sensor_meta(sensor: str) -> dict:
    info = config.SENSORS.get(sensor, {})
    return {
        "id": sensor,
        "label": info.get("label", sensor),
        "instrument": info.get("instrument", "?"),
        "colour": info.get("colour", "#94a3b8"),
        "pixel_km": info.get("pixel_km"),
    }


def calibration_block(harmonised: HarmonizedSeries) -> dict:
    return harmonised.calibration.to_dict()


def series_context(harmonised: HarmonizedSeries) -> dict:
    s = harmonised.series
    return {
        "aoi": s.aoi.to_dict(),
        "grid_deg": config.GRID_DEG,
        "grid_cells": s.grid_cells,
        "grid_area_km2": round(s.grid_area_km2, 1),
        "sensors": [_sensor_meta(x) for x in s.sensors],
        "record_start": s.start,
        "record_end": s.end,
        "detections": s.n_detections,
        "calibration": calibration_block(harmonised),
        "unit": harmonised.calibration.to_dict()["unit"],
    }


# ---------------------------------------------------------------------------
# Calendar views
# ---------------------------------------------------------------------------

def calendar_month(
    harmonised: HarmonizedSeries,
    year: int,
    month: int,
) -> dict:
    """Daily activity for one month, with the historical median for that month."""
    start = date(year, month, 1).isoformat()
    end = date(year, month, days_in_month(year, month)).isoformat()
    points = harmonised.points(start, end)
    by_day = {p.date: p for p in points}

    days = []
    for day_num in range(1, days_in_month(year, month) + 1):
        iso = date(year, month, day_num).isoformat()
        p = by_day.get(iso)
        if p is None:
            days.append({
                "date": iso, "day": day_num, "observed": False,
                "harmonized": None, "raw_total": None, "per_sensor": {},
                "sensors_observing": [], "coverage": 0.0, "frp_total": 0.0,
            })
        else:
            d = p.to_dict()
            d["day"] = day_num
            days.append(d)

    agg = aggregate_period(harmonised, start, end)
    baseline = daily_median_baseline(harmonised, month, exclude_year=year)
    comparison = compare_to_baseline(agg.get("expected_total"), baseline)

    return {
        "year": year,
        "month": month,
        "month_name": MONTH_NAMES[month - 1],
        "days": days,
        "summary": agg,
        "baseline": baseline,
        "comparison": comparison,
        "context": series_context(harmonised),
    }


def calendar_year(harmonised: HarmonizedSeries, year: int) -> dict:
    """Twelve monthly summaries for one year."""
    months = []
    for month in range(1, 13):
        start = date(year, month, 1).isoformat()
        end = date(year, month, days_in_month(year, month)).isoformat()
        agg = aggregate_period(harmonised, start, end)
        months.append({
            "month": month,
            "month_name": MONTH_NAMES[month - 1],
            **agg,
        })
    complete = [m for m in months if m["complete"]]
    peak = max(complete, key=lambda m: m["expected_total"] or 0) if complete else None
    return {
        "year": year,
        "months": months,
        "complete_months": len(complete),
        "peak_month": peak["month"] if peak else None,
        "peak_month_name": peak["month_name"] if peak else None,
        "year_total": round(sum(m["expected_total"] for m in complete), 2) if complete else None,
        "context": series_context(harmonised),
    }


def history_matrix(
    harmonised: HarmonizedSeries,
    metric: str = "harmonized",
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict:
    """Year x month matrix used by the historical calendar heatmap.

    ``metric`` selects the harmonized index (coverage-normalised) or the raw
    pooled detection total, which is kept available precisely so the difference
    between the two can be inspected.
    """
    s = harmonised.series
    years = sorted({int(d[:4]) for d in s.dates})
    if start_year:
        years = [y for y in years if y >= start_year]
    if end_year:
        years = [y for y in years if y <= end_year]

    rows = []
    for year in years:
        cells = []
        for month in range(1, 13):
            start = date(year, month, 1).isoformat()
            end = date(year, month, days_in_month(year, month)).isoformat()
            agg = aggregate_period(harmonised, start, end)
            value = agg["expected_total"] if metric == "harmonized" else agg["raw_total"]
            cells.append({
                "month": month,
                "value": round(value, 2) if value is not None else None,
                "raw_total": agg["raw_total"],
                "coverage": agg["coverage"],
                "complete": agg["complete"],
                "observed_days": agg["observed_days"],
                "per_sensor": agg["per_sensor"],
            })
        rows.append({"year": year, "months": cells})

    values = [c["value"] for r in rows for c in r["months"] if c["value"] is not None and c["complete"]]
    scale = _scale_summary(values)
    return {
        "metric": metric,
        "years": years,
        "rows": rows,
        "scale": scale,
        "context": series_context(harmonised),
    }


def _scale_summary(values: list[float]) -> dict:
    if not values:
        return {"min": None, "max": None, "p50": None, "p90": None, "n": 0}
    ordered = sorted(values)
    def pct(p: float) -> float:
        idx = min(len(ordered) - 1, max(0, int(round(p * (len(ordered) - 1)))))
        return ordered[idx]
    return {
        "min": round(ordered[0], 2),
        "max": round(ordered[-1], 2),
        "p50": round(pct(0.5), 2),
        "p90": round(pct(0.9), 2),
        "n": len(ordered),
    }


def sensor_timeline(harmonised: HarmonizedSeries) -> dict:
    """When each sensor observed the area, and how much it contributed."""
    s = harmonised.series
    out = []
    for sensor in s.sensors:
        days = sorted(s.observed.get(sensor, set()))
        if not days:
            continue
        counts = [s.count(sensor, d) for d in days]
        out.append({
            **_sensor_meta(sensor),
            "first_date": days[0],
            "last_date": days[-1],
            "observed_days": len(days),
            "detections": sum(counts),
            "mean_per_observed_day": round(sum(counts) / len(days), 2) if days else None,
            "share": None,
        })
    total = sum(row["detections"] for row in out) or 1
    for row in out:
        row["share"] = round(row["detections"] / total, 4)
    return {"sensors": out, "context": series_context(harmonised)}


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------

def _mann_kendall(values: list[float]) -> dict:
    """Non-parametric monotonic-trend test (Mann-Kendall, normal approximation).

    Reported because a least-squares slope on a short, noisy, autocorrelated
    series would overstate confidence. The p-value here is two-sided and does
    not correct for serial correlation, which is stated in the interface.
    """
    n = len(values)
    if n < 4:
        return {"n": n, "s": None, "z": None, "p": None, "trend": "insufficient_data"}
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = values[j] - values[i]
            s += 1 if diff > 0 else (-1 if diff < 0 else 0)
    var = n * (n - 1) * (2 * n + 5) / 18.0
    if s > 0:
        z = (s - 1) / math.sqrt(var)
    elif s < 0:
        z = (s + 1) / math.sqrt(var)
    else:
        z = 0.0
    p = 2 * (1 - _normal_cdf(abs(z)))
    trend = "no_significant_trend"
    if p < 0.05:
        trend = "increasing" if z > 0 else "decreasing"
    return {"n": n, "s": s, "z": round(z, 3), "p": round(p, 4), "trend": trend,
            "significant_at_0_05": p < 0.05}


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _theil_sen(values: list[float]) -> float | None:
    """Median of pairwise slopes: robust to a single extreme fire year."""
    n = len(values)
    if n < 2:
        return None
    slopes = []
    for i in range(n - 1):
        for j in range(i + 1, n):
            slopes.append((values[j] - values[i]) / (j - i))
    return statistics.median(slopes) if slopes else None


def trends(harmonised: HarmonizedSeries) -> dict:
    s = harmonised.series
    years = sorted({int(d[:4]) for d in s.dates})

    yearly = []
    for year in years:
        start = date(year, 1, 1).isoformat()
        end = date(year, 12, 31).isoformat()
        agg = aggregate_period(harmonised, start, end)
        yearly.append({
            "year": year,
            "expected_total": agg["expected_total"],
            "raw_total": agg["raw_total"],
            "coverage": agg["coverage"],
            "complete": agg["complete"],
            "observed_days": agg["observed_days"],
        })

    complete_years = [y for y in yearly if y["complete"] and y["expected_total"] is not None]
    values = [y["expected_total"] for y in complete_years]
    mk = _mann_kendall(values)
    slope = _theil_sen(values)

    monthly = []
    for month in range(1, 13):
        totals = []
        for year in years:
            start = date(year, month, 1).isoformat()
            end = date(year, month, days_in_month(year, month)).isoformat()
            agg = aggregate_period(harmonised, start, end)
            if agg["complete"] and agg["expected_total"] is not None:
                totals.append(agg["expected_total"])
        monthly.append({
            "month": month,
            "month_name": MONTH_NAMES[month - 1],
            "median": round(statistics.median(totals), 2) if totals else None,
            "mean": round(statistics.fmean(totals), 2) if totals else None,
            "n_years": len(totals),
        })

    monthly_rows = []
    for row in harmonised.points():
        if row.harmonized is None:
            continue
        monthly_rows.append({"date": row.date, "harmonized": row.harmonized,
                             "raw_total": row.raw_total})

    all_months = []
    for year in years:
        for month in range(1, 13):
            start = date(year, month, 1).isoformat()
            end = date(year, month, days_in_month(year, month)).isoformat()
            agg = aggregate_period(harmonised, start, end)
            if agg["complete"] and agg["expected_total"] is not None:
                all_months.append({
                    "year": year, "month": month,
                    "label": f"{MONTH_NAMES[month - 1]} {year}",
                    "value": agg["expected_total"],
                    "raw_total": agg["raw_total"],
                })

    top_months = sorted(all_months, key=lambda m: -m["value"])[:5]
    top_years = sorted(complete_years, key=lambda y: -(y["expected_total"] or 0))[:5]

    return {
        "yearly": yearly,
        "monthly_profile": monthly,
        "daily": monthly_rows,
        "top_months": top_months,
        "top_years": [{"year": y["year"], "value": y["expected_total"],
                       "raw_total": y["raw_total"]} for y in top_years],
        "trend": {
            "method": "Mann-Kendall (normal approximation) + Theil-Sen slope",
            "years_used": [y["year"] for y in complete_years],
            "n_years": len(values),
            "theil_sen_slope_per_year": round(slope, 2) if slope is not None else None,
            "mann_kendall": mk,
            "note": (
                "Only complete years are used. The test does not correct for "
                "serial correlation and is not a statement about causation."
            ),
        },
        "context": series_context(harmonised),
    }


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * (pct / 100.0)
    lower = int(math.floor(position))
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def critical_periods(
    harmonised: HarmonizedSeries,
    start: str | None = None,
    end: str | None = None,
    percentile: float = 90.0,
    min_days: int = 3,
) -> dict:
    """Contiguous runs of unusually high burning activity.

    Definition
    ----------
    For each calendar month, the *baseline distribution* is every daily value in
    that month across all **complete** months of the record. The threshold is the
    chosen percentile (default the 90th) of that distribution, so a "critical"
    day is one that exceeds 90 % of the same calendar month's normal days.

    A period grows while consecutive days stay above their month's threshold. It
    is **broken** by any day that is not observed, and days belonging to an
    incomplete month never enter a period at all - so a gap can never be bridged,
    and missing coverage can never look like a fire season.

    This is a statistical description of unusual burning, not an emergency
    declaration: agricultural burning and other thermal anomalies are included.
    """
    s = harmonised.series
    window_start = start or s.start
    window_end = end or s.end

    # Completeness per calendar month, using the same rule as the rest of the app.
    month_complete: dict[tuple[int, int], bool] = {}
    baseline_daily: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    for year in sorted({int(d[:4]) for d in s.dates}):
        for month in range(1, 13):
            key = (year, month)
            if key in month_complete:
                continue
            m_start = date(year, month, 1).isoformat()
            m_end = date(year, month, days_in_month(year, month)).isoformat()
            agg = aggregate_period(harmonised, m_start, m_end)
            month_complete[key] = bool(agg["complete"])
            if agg["complete"]:
                baseline_daily[month].extend(
                    p.harmonized for p in harmonised.points(m_start, m_end)
                    if p.harmonized is not None
                )

    thresholds = {m: _percentile(vals, percentile) for m, vals in baseline_daily.items()}
    baseline_stats = {
        m: {
            "threshold": round(thresholds[m], 2) if thresholds[m] is not None else None,
            "n_days": len(vals),
            "median": round(statistics.median(vals), 2) if vals else None,
            "p90": round(_percentile(vals, 90) or 0, 2) if vals else None,
            "max": round(max(vals), 2) if vals else None,
        }
        for m, vals in baseline_daily.items()
    }

    periods: list[dict] = []
    current: list = []

    def close(run: list) -> None:
        if len(run) < min_days:
            return
        peak = max(run, key=lambda p: p.harmonized)
        month = int(run[0].date[5:7])
        periods.append({
            "start": run[0].date,
            "end": run[-1].date,
            "duration_days": len(run),
            "peak_date": peak.date,
            "peak_value": round(peak.harmonized, 2),
            "mean_value": round(statistics.fmean(p.harmonized for p in run), 2),
            "total_value": round(sum(p.harmonized for p in run), 2),
            "threshold": round(thresholds[month], 2) if thresholds.get(month) is not None else None,
            "month": month,
            "baseline_years": sorted({
                int(d[:4]) for d in s.dates
                if int(d[5:7]) == month and month_complete.get((int(d[:4]), month), False)
            }),
            "sensors": sorted(
                {sensor for p in run for sensor in p.sensors_observing},
                key=_sensor_sort_key,
            ),
            "coverage_min": round(min(p.coverage for p in run), 3),
        })

    for point in harmonised.points(window_start, window_end):
        year, month = int(point.date[:4]), int(point.date[5:7])
        usable = (
            point.harmonized is not None
            and month_complete.get((year, month), False)
            and thresholds.get(month) is not None
            and point.harmonized > thresholds[month]
        )
        if usable:
            # Each emitted period carries one month's threshold and baseline.
            # Close at a month boundary so that metadata describes every day.
            if current and current[-1].date[:7] != point.date[:7]:
                close(current)
                current = []
            current.append(point)
        else:
            close(current)
            current = []
    close(current)

    periods.sort(key=lambda p: p["peak_value"], reverse=True)
    return {
        "periods": periods,
        "method": (
            f"contiguous days above the {percentile:.0f}th percentile of the same calendar month "
            "across complete months; broken by missing observations, incomplete months, and "
            "calendar-month boundaries"
        ),
        "percentile": percentile,
        "min_days": min_days,
        "window": {"start": window_start, "end": window_end},
        "baseline": baseline_stats,
        "context": series_context(harmonised),
        "caveats": [
            "High activity is not a confirmed wildfire emergency: agricultural burning, flaring and "
            "other thermal anomalies are included.",
            "A period ends at a data gap; a longer event may be split in two.",
            "Periods are only evaluated inside months that pass the coverage gate.",
        ],
    }


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------

def anomalies(
    harmonised: HarmonizedSeries,
    start: str | None = None,
    end: str | None = None,
    z_threshold: float | None = None,
    min_years: int = 3,
) -> dict:
    """Flag months whose activity departs from their own historical median.

    Method: for each month M of year Y, build the baseline from all *complete*
    months M in other years, take the median, and compute a robust z-score
    ``(x - median) / (1.4826 * MAD)``. Flags are statistical, not emergency
    declarations.
    """
    threshold = z_threshold if z_threshold is not None else config.ANOMALY_Z_THRESHOLD
    s = harmonised.series
    years = sorted({int(d[:4]) for d in s.dates})
    flags = []
    checked = 0
    skipped_incomplete = 0

    for year in years:
        for month in range(1, 13):
            m_start = date(year, month, 1).isoformat()
            m_end = date(year, month, days_in_month(year, month)).isoformat()
            if end and m_start > end:
                continue
            if start and m_end < start:
                continue
            agg = aggregate_period(harmonised, m_start, m_end)
            if not agg["complete"] or agg["expected_total"] is None:
                skipped_incomplete += 1
                continue
            baseline = daily_median_baseline(harmonised, month, exclude_year=year, min_years=min_years)
            if not baseline["sufficient"]:
                continue
            checked += 1
            cmp = compare_to_baseline(agg["expected_total"], baseline)
            z = cmp.get("z_score")
            pct = cmp.get("percent_deviation")
            magnitude = abs(cmp.get("absolute_deviation") or 0.0)
            if z is not None:
                criterion = "robust_z"
                flagged = abs(z) >= threshold
            else:
                # MAD can be zero when every baseline year is identical. A
                # percentage deviation is then the only available criterion, and
                # the flag records which rule fired.
                criterion = "percent_deviation"
                flagged = pct is not None and abs(pct) >= 100
            if flagged:
                flags.append({
                    "period": f"{year}-{month:02d}",
                    "label": f"{MONTH_NAMES[month - 1]} {year}",
                    "year": year,
                    "month": month,
                    "kind": "monthly",
                    **cmp,
                    "criterion": criterion,
                    "z_threshold": threshold,
                    "magnitude": round(magnitude, 2),
                    "coverage": agg["coverage"],
                    "observed_days": agg["observed_days"],
                    "raw_total": agg["raw_total"],
                    "baseline_years": baseline["years_used"],
                    "n_years": baseline["n_years"],
                    "method": (
                        "robust z-score against the historical monthly median"
                        if criterion == "robust_z"
                        else "percentage deviation (baseline dispersion was zero)"
                    ),
                    "flagged": True,
                })

    direction = lambda f: 0 if f["direction"] == "above" else 1  # noqa: E731
    flags.sort(key=lambda f: (direction(f), -f["magnitude"]))

    return {
        "threshold": threshold,
        "method": "robust z-score (median / MAD) against the same calendar month",
        "months_checked": checked,
        "months_skipped_incomplete": skipped_incomplete,
        "anomalies": flags,
        "elevated": [f for f in flags if f["direction"] == "above"],
        "depressed": [f for f in flags if f["direction"] == "below"],
        "context": series_context(harmonised),
        "caveats": [
            "A statistical anomaly is not a confirmed wildfire emergency.",
            "Cloud cover, sensor outages and very small AOIs can all produce deviations.",
            "Months below the coverage threshold are excluded rather than flagged.",
        ],
    }
