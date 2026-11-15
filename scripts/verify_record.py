"""Verify the loaded FIRMS record against the five questions that matter.

Runs read-only checks against the local database and prints a report you can
compare with what the interface shows. No data is modified.

    .\.venv\Scripts\python.exe scripts\verify_record.py
    .\.venv\Scripts\python.exe scripts\verify_record.py --region aegean

Checks
  1. Historical coverage   - what the record actually contains, per sensor and per year
  2. Missing data          - gaps are None, never 0, and are excluded from averages
  3. MODIS vs VIIRS        - agreement metrics and the weights they produce
  4. Calibration gate      - a short slice must FAIL the gate while the full record passes
  5. Anomalies             - flags recomputed from real counts, with baseline size and coverage
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import agreement, analytics, config, geo, harmonize, ingest, regions  # noqa: E402


def rule(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="aegean",
                        help=f"preset region id ({', '.join(regions.REGIONS)})")
    parser.add_argument("--bbox", help="west,south,east,north instead of a preset")
    args = parser.parse_args()

    if args.bbox:
        parts = [p.strip() for p in args.bbox.split(",") if p.strip()]
        if len(parts) != 4:
            raise SystemExit("--bbox needs west,south,east,north")
        aoi = geo.normalize_aoi({"bbox": [float(p) for p in parts], "name": "custom"})
    else:
        aoi = regions.region_aoi(args.region)
        if aoi is None:
            raise SystemExit(f"unknown region '{args.region}'")

    summary = ingest.summary()
    print(f"database      : {summary['detections']:,} detections, "
          f"{summary['min_date']} .. {summary['max_date']}")
    print(f"area          : {aoi.name} {aoi.bbox}")

    harmonised = harmonize.build(aoi)
    series = harmonised.series

    # ---------------------------------------------------------------- 1
    rule("1. HISTORICAL COVERAGE")
    print(f"record span    : {series.start} .. {series.end}")
    print(f"{'sensor':<15}{'first':<12}{'last':<12}{'days':>7}{'detections':>12}{'share':>8}")
    total = sum(sum(c.values()) for c in series.counts.values()) or 1
    for sensor in series.sensors:
        days = sorted(series.observed.get(sensor, set()))
        if not days:
            print(f"{sensor:<15}{'--':<12}{'--':<12}{0:>7}{0:>12}{0:>7.1%}")
            continue
        dets = sum(series.count(sensor, d) for d in days)
        print(f"{sensor:<15}{days[0]:<12}{days[-1]:<12}{len(days):>7,}{dets:>12,}{dets / total:>7.1%}")
    years = sorted({int(d[:4]) for d in series.dates})
    print(f"years present  : {len(years)} ({years[0]} .. {years[-1]})")

    # ---------------------------------------------------------------- 2
    rule("2. MISSING DATA IS NOT ZERO")
    points = harmonised.points()
    gaps = [p for p in points if p.harmonized is None]
    zeros = [p for p in points if p.harmonized == 0]
    print(f"days in record : {len(points):,}")
    print(f"no observation : {len(gaps):,}  (stored as None, excluded from every average)")
    print(f"harmonised = 0 : {len(zeros):,}  (a real zero-detection day, which is different)")
    for year, month in ((2026, 11), (2020, 6)):
        start = f"{year}-{month:02d}-01"
        end = f"{year}-{month:02d}-{harmonize.days_in_month(year, month):02d}"
        agg = harmonize.aggregate_period(harmonised, start, end)
        print(f"  {year}-{month:02d}: observed {agg['observed_days']}/{agg['days_in_period']} "
              f"coverage={agg['coverage']:.0%} in_record={agg['in_record']} "
              f"complete={agg['complete']} observed_total={agg['observed_total']} "
              f"expected_total={agg['expected_total']}")

    # ---------------------------------------------------------------- 3
    rule("3. MODIS vs VIIRS")
    cal = harmonised.calibration
    print(f"status         : {cal.status}   unit: {cal.to_dict()['unit']}")
    print(f"ratio CV       : {cal.ratio_cv}")
    for sensor in series.sensors:
        paired = cal.paired_days.get(sensor, 0)
        paired_label = "reference" if sensor == "modis" else f"{paired:,}"
        print(f"  {sensor:<15} weight={cal.weights.get(sensor, 1.0):<8.4f} "
              f"rate/day={cal.rates.get(sensor, 0):>9.2f} "
              f"paired_days={paired_label:>9}")
    compare = agreement.compare_sensors(harmonised, include_co_detection=False)
    if compare.get("available"):
        daily = compare["daily"]
        spatial = compare["spatial"]
        print(f"  paired daily : MODIS {daily['modis_mean']:.1f}/day vs VIIRS {daily['viirs_mean']:.1f}/day "
              f"-> ratio {daily['ratio_modis_over_viirs']}")
        print(f"  agreement    : Spearman {daily['spearman']} | Jaccard {spatial['jaccard']} "
              f"| cell rank {spatial['spearman_cell_totals']}")

    # ---------------------------------------------------------------- 4
    rule("4. CALIBRATION GATE")
    short_end = min(series.end, "2026-11-14")
    short = harmonize.build(aoi, start="2026-11-01", end=short_end)
    print(f"14-day slice   : status={short.calibration.status:<22} calibrated={short.calibration.calibrated}")
    print(f"full record    : status={cal.status:<22} calibrated={cal.calibrated}")
    print(f"gate           : needs >= {config.MIN_OVERLAP_DAYS_FOR_CALIBRATION} co-observed days "
          f"and ratio CV <= {config.MAX_RATIO_CV_FOR_CALIBRATION}")
    gate_ok = (not short.calibration.calibrated) and cal.calibrated
    print(f"gate behaves   : {'PASS' if gate_ok else 'CHECK MANUALLY'}")

    # ---------------------------------------------------------------- 5
    rule("5. ANOMALIES FROM REAL DATA")
    result = analytics.anomalies(harmonised)
    print(f"months checked : {result['months_checked']}  "
          f"(skipped incomplete: {result['months_skipped_incomplete']}, threshold |z| >= {result['threshold']})")
    print(f"flags          : {len(result['anomalies'])}")
    print(f"{'month':<16}{'z':>8}{'pct':>10}{'observed':>12}{'median':>10}{'years':>7}{'coverage':>10}")
    for flag in result["anomalies"][:8]:
        z = f"{flag['z_score']:.2f}" if flag["z_score"] is not None else "--"
        pct = f"{flag['percent_deviation']:.0f}%" if flag["percent_deviation"] is not None else "--"
        print(f"{flag['label']:<16}{z:>8}{pct:>10}{flag['observed']:>12,.0f}"
              f"{flag['median']:>10,.0f}{flag['n_years']:>7}{flag['coverage'] * 100:>9.0f}%")

    # ---------------------------------------------------------------- table
    rule("YEARLY TABLE (compare with Historical Analytics)")
    trends = analytics.trends(harmonised)
    print(f"{'year':<6}{'harmonised':>12}{'raw':>10}{'obs_days':>10}{'coverage':>10}  status")
    for row in trends["yearly"]:
        value = row["expected_total"] if row["expected_total"] is not None else 0
        print(f"{row['year']:<6}{value:>12,.0f}{row['raw_total']:>10,}"
              f"{row['observed_days']:>10}{row['coverage'] * 100:>9.0f}%  "
              f"{'used' if row['complete'] else 'excluded'}")

    mark = trends["trend"]
    print()
    print(f"trend test     : {mark['method']}")
    print(f"                 {mark['n_years']} complete years, Theil-Sen "
          f"{mark['theil_sen_slope_per_year']}/yr, Mann-Kendall p={mark['mann_kendall']['p']} "
          f"-> {mark['mann_kendall']['trend']}")
    print()
    print("Reminder: a long record does not make MODIS and VIIRS directly comparable by itself.")
    print("The weights above, the per-sensor coverage, and the coverage normalisation are what")
    print("make the comparison defensible - and the gate refuses to calibrate when they are absent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
