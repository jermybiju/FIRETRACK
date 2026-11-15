# FIRETRACK scientific methodology

> **Independent audit notice (2026-11-15):** FIRETRACK currently treats global product date availability and successful area-query windows as proof that a sensor observed the selected AOI. A successful empty FIRMS hotspot query does not establish local satellite coverage or cloud-free observation. As a result, zero-activity days, coverage-normalised values, calibration, historical completeness, trends and anomaly results are **not validated for the selected area**. See [the submission audit](docs/SUBMISSION_AUDIT_2026-11-15.md). Do not present those metrics as scientific findings until area-specific observation/coverage evidence is integrated and the analytics are updated.

This document is the reference derivation behind every number the interface shows. It is written so
that a reviewer can reproduce the calculation by hand from the code and the raw files.

---

## 1. Objective

Produce a **consistent long-term series of burning activity** for any user-selected area, from a
record that is built by different instruments with different resolution, sensitivity, overpass
schedule and availability — without inventing data and without presenting a sensor transition as an
environmental signal.

Success is not "one number that looks monotonic". Success is a series in which a change of the
observing constellation does not, by itself, move the value.

## 2. Inputs

NASA FIRMS active-fire detections (MODIS Collection 6.1; VIIRS Collection 2 375 m for Suomi-NPP,
NOAA-20 and NOAA-21). Each record carries coordinates, acquisition date and time (UTC), satellite,
confidence, version, brightness temperature(s), fire radiative power (FRP), scan/track, day/night and
the processing stream.

Handled fields:

| Concept | MODIS source field | VIIRS source field |
|---|---|---|
| Brightness temperature | `brightness` | `bright_ti4` |
| Background temperature | `bright_t31` | `bright_ti5` |
| Confidence | numeric 0–100 | category `l` / `n` / `h` (or words) |

Nothing is imputed. A missing FRP stays `NULL`; it never becomes zero, because zero FRP would be a
measurement.

## 3. Validation of records

Every row passes through one normalisation function (`app.firms.normalize_row`). A row is **rejected**
(not repaired) when:

- coordinates are missing, non-numeric or outside −90…90 / −180…180;
- the acquisition date cannot be parsed, or lies outside 2000–2100;
- the sensor cannot be resolved from satellite code, instrument field or filename.

Accepted rows are de-duplicated on `(sensor, acq_date, acq_time, lat, lon)` — the same pixel at the
same overpass, delivered twice (for example by an overlapping 7-day and 48-hour file, or by two
archive requests) is stored once. Rejections and duplicates are counted per batch and shown in the
interface.

## 4. Spatial harmonisation

A 1 km MODIS pixel and a 375 m VIIRS pixel cannot be compared as units, and adding their counts
compares nothing. Both are therefore aggregated to a **common 0.25° grid** (≈27.8 km at the equator).

- Cell index: `ix = floor((lat + 90)/0.25)`, `iy = floor((lon + 180)/0.25)`.
- A cell belongs to an area when **its centre** falls inside the area (bounding box or drawn polygon).
- Cell area is computed per cell latitude: `111.195·Δ × 111.195·Δ·cos(lat)` km², and the analysed
  area is the *sum of included cell areas*, not the nominal bounding-box area.
- Raw detections remain in the database untouched, so any aggregate can be traced back to records.

Consequence: every statistic shares the same spatial support. A "detection" in the calendar and a
"detection" in the sensor comparison mean the same thing.

## 5. Temporal harmonisation

### 5.1 Availability, not absence

A sensor is marked **observing** on every date between its first and last delivered record in the
ingested product, because FIRMS products are daily-complete. Dates outside that span are *unknown*,
and a date with no observing sensor produces `null` — never `0`.

**Delivery windows bound availability.** NASA publishes the exact date range of every product
(`data_availability`). Those ranges are stored in `product_windows` and a date is only marked
observed if it falls inside the sensor's reported window *and* the sensor was actually queried. Two
consequences:

- A sensor that has stopped delivering returns empty responses; those dates are **not** treated as
  observed. The harmonised index therefore never assumes a contribution from a sensor that could not
  have supplied one.
- A date outside the reported window that nonetheless contains real detections is **kept**, because
  the detections prove delivery. Detections are never deleted by this rule — only availability rows
  are, and only where there is no data.

Worked example from this record: Suomi-NPP ceased operations on 2026-11-02 (NASA alert and
`VIIRS_SNPP_NRT` ending that day). Its last detection is 2026-11-02. Before the correction, the
availability calendar kept it "observing" to 2026-11-14, which deflated the harmonised value on those
12 days by about 23 % (expected contribution included but impossible). After the correction those days
are 30 % higher and S-NPP is correctly absent.

For API backfills, every queried window is also recorded as observed, so a window that returned no
detections is correctly read as "no hotspot detected" rather than "no data".

### 5.2 Why a percentage must not be applied to a missing day

A month with 6 observed days out of 30 is not a quiet month; it is a mostly unobserved month.
Monthly aggregation therefore reports:

- `observed_days` and `coverage = observed_days / days_in_month`;
- `observed_total` (sum over observed days);
- `expected_total = mean_daily × days_in_month` (coverage-corrected estimate);
- `complete = coverage ≥ 0.80`.

Only `complete` months enter medians and trend tests.

## 6. The harmonised activity index

Let `dₛ(t)` be the detection count of sensor `s` on date `t` (on the common grid), `ρₛ` the sensor's
mean daily count in the area, `wₛ` its weight, and `A(t)` the set of sensors observing date `t`.

```
raw(t)        = Σ_{s ∈ A(t)} dₛ(t)
weighted(t)   = Σ_{s ∈ A(t)} wₛ·dₛ(t)
expected(t)   = Σ_{s ∈ A(t)} wₛ·ρₛ            (an "average day" for this sensor mix)
expected_all  = Σ_{all s}    wₛ·ρₛ            (an "average day" for the full constellation)

H(t)          = weighted(t) × expected_all / expected(t)      if expected(t) > 0
H(t)          = weighted(t)                                   otherwise
```

`H(t)` is in **MODIS-equivalent detections per day** when calibrated, and
**coverage-normalised detections per day** when not.

Interpretation: `H` estimates what the full constellation would have seen. Two days with the same
underlying burning, observed by different numbers of sensors, obtain the same value. This is the
central property the test suite asserts (`test_single_sensor_day_matches_two_sensor_day`).

**Assumption stated plainly:** the normalisation assumes the missing sensors would have detected in
proportion to their average rate. It cannot correct a situation where, say, only the morning overpass
was available during a diurnal fire cycle. That residual effect is not quantified here.

## 7. Calibration weights

Reference sensor: MODIS (the longest record). `w_MODIS = 1`.

For each VIIRS platform `p`, over dates where **both** MODIS and `p` observed the area:

```
w_p = mean(d_MODIS over common dates) / mean(d_p over common dates)
```

Gating:

| Condition | Behaviour |
|---|---|
| Co-observed days < 60 | ratio reported, **not applied**; all weights 1.0 |
| Ratio CV across 4 consecutive sub-periods > 0.35 | calibration **rejected**; all weights 1.0 |
| No MODIS record, or no VIIRS record | `single_sensor`, weights 1.0 |

The weight is a **multiplicative bias correction**. It does not linearise the relationship: VIIRS
detects small fires that MODIS misses entirely, so the transform is a scaling of the aggregate, not a
per-fire equivalence. The interface states this wherever the weights appear.

## 8. Calendar products

| Product | Definition |
|---|---|
| Day cell | `H(t)`, the observing sensor set, per-sensor raw counts, FRP sum, coverage |
| Month summary | coverage-corrected expected total, observed total, mean/median/max daily, raw total |
| Year profile | twelve month summaries; peak month among complete months |
| History matrix | year × month of coverage-corrected totals (or raw totals, selectable) |
| Historical median | median of the same calendar month over complete years, excluding the evaluated year |

### Why median and MAD

A single extreme fire year would inflate a mean and standard deviation enough to hide every other
anomaly. The baseline therefore uses the **median**, dispersion uses the **median absolute deviation**,
and the anomaly statistic is

```
z = (x − median) / (1.4826 × MAD)
```

flagged at `|z| ≥ 2.5` by default (configurable to 2.0 or 3.0 in the interface). If `MAD = 0`
(all baseline years identical) the z-score is undefined; the implementation then falls back to a
percentage criterion (`|deviation| ≥ 100%`) and records **which criterion fired** in the flag.

A percentage deviation is only reported when the baseline median is at least 5 detections; below that,
a percentage is numerically unstable and the absolute difference is the honest comparison.

## 9. Fire radiative power (FRP)

FRP is stored and reported **per sensor**. It is never presented as a harmonised quantity.

- MODIS and VIIRS retrieve FRP with different pixel sizes, spectral channels and algorithms. There is
  no defensible conversion between them in this project, so no weight is applied to FRP.
- Where a single number is convenient (a map cell, a monthly KPI, a report card), it is the **plain
  sum of raw sensor FRP** and is labelled as such: *"sum of raw sensor FRP (not harmonised)"*.
- The daily CSV export carries one FRP column per sensor, plus the raw sum in a column named
  `frp_sum_raw_all_sensors`.
- FRP is not converted to burned area, emissions, or severity anywhere.

## 10. Critical burning periods

A **critical period** is a contiguous run of days whose harmonised activity exceeds the 90th
percentile of the same calendar month across all complete months in the record (configurable to a
different percentile or minimum length through the API).

Construction:

1. For each calendar month, pool every daily value from **complete** months only. The 90th percentile
   of that pool is the month's threshold.
2. Walk the selected period day by day. A day joins the current run when it is observed, belongs to a
   complete month, and exceeds that month's threshold.
3. A run is **broken** by any missing or unusable day, so a data gap can never be bridged and
   incomplete coverage can never masquerade as a fire season.
4. A run is closed at each calendar-month boundary. A streak continuing into the next month is
   split so each segment is compared with that month's threshold and reports that month's baseline.
5. Runs shorter than the minimum length (default 3 days) are discarded.
6. Each period reports start, end, duration, peak value and date, mean, threshold, the baseline years
   used, the sensors involved, and the minimum daily coverage.

This is a statistical description of unusual burning, not an emergency declaration: agricultural
burning, flaring and other thermal anomalies are included, and the interface says so.

Every reported period stays within one calendar month because its threshold and baseline are month-specific.
An above-threshold streak crossing into a new month is split at that boundary. Each segment is kept
only if it meets the minimum-duration rule. Pre-boundary examples are superseded; regenerate numeric
top-period results from the current implementation before quoting them.

## 11. Sensor comparison

Five complementary measures over co-observed dates:

1. **Paired daily correlation** — Pearson on `log1p` counts, and Spearman on raw counts.
2. **Magnitude ratio** — the same quantity the calibration uses.
3. **Spatial agreement** — Jaccard overlap of active cells, plus Spearman across per-cell totals.
4. **Co-detection** — share of MODIS detections with a VIIRS detection within 1 km on the same UTC day
   (bucket grid at 0.02°, neighbourhood search, haversine test).
5. **Transition diagnostic** — step size in raw vs harmonised activity around known sensor
   introduction dates, where the record is long enough to contain them.

None of these is an accuracy score. They measure agreement between instruments, which is the question
the challenge actually asks.

## 12. Trends

- Only complete years enter the test.
- **Mann–Kendall** (normal approximation, two-sided p) for monotonic trend detection.
- **Theil–Sen** slope for a robust magnitude, insensitive to a single extreme year.
- No correction for serial correlation — stated in the interface and the report. A detected trend
  concerns *detections*, not burned area, emissions, or causation.

## 13. Parameters in force

| Parameter | Value | Where |
|---|---|---|
| Analysis grid | 0.25° | `config.GRID_DEG` |
| Minimum overlap for calibration | 60 days | `config.MIN_OVERLAP_DAYS_FOR_CALIBRATION` |
| Maximum ratio CV | 0.35 | `config.MAX_RATIO_CV_FOR_CALIBRATION` |
| Complete-month coverage gate | 0.80 | `config.MIN_COVERAGE_FRACTION` |
| Anomaly z threshold | 2.5 | `config.ANOMALY_Z_THRESHOLD` |
| VIIRS confidence ordinals | 25 / 65 / 90 | `config.VIIRS_CONFIDENCE_ORDINAL` |
| Duplicate key | sensor + date + time + lat + lon | `db.py` unique index |

These are configuration, not hidden assumptions: the interface lists them on the Methodology page and
the exported report repeats them.

## 14. What this method does not do

- It does not detect fires that were never observed (cloud, smoke, sensor outage, small fire).
- It does not convert detections to burned area, emissions or fire severity.
- It does not calibrate per season or per biome; weights are per area and constant in time.
- It does not validate against independent ground truth, so it claims no accuracy percentage.
- It does not distinguish wildfire from agricultural burning, flaring or volcanic heat.

## 15. Reproducibility

```powershell
# 1. real, key-free snapshot (NRT)
python scripts/download_firms_snapshot.py

# 2. historical backfill (MAP_KEY)
python scripts/fetch_firms_api.py --map-key YOUR_KEY --region sahel_belt --start 2000-11-01

# 3. rebuild all derived tables from raw records
python -c "from app import ingest; ingest.rebuild_daily_cells()"

# 4. verify the science
python run_tests.py -v
```

Every ingest batch stores file names, row counts, rejection counts, date bounds and quality level;
the Data Explorer and the API (`/api/provenance`) expose them.

