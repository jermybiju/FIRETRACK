# FIRETRACK validation report

> **Independent audit notice (2026-11-15):** FIRETRACK currently treats global product date availability and successful area-query windows as proof that a sensor observed the selected AOI. A successful empty FIRMS hotspot query does not establish local satellite coverage or cloud-free observation. As a result, zero-activity days, coverage-normalised values, calibration, historical completeness, trends and anomaly results are **not validated for the selected area**. See [the submission audit](docs/SUBMISSION_AUDIT_2026-11-15.md). Do not present those metrics as scientific findings until area-specific observation/coverage evidence is integrated and the analytics are updated.

**Build:** FIRETRACK 1.0.0 · **Validation date:** 2026-11-14 · **Environment:** Windows 11,
Python 3.12, SQLite 3, Chromium unavailable for automated UI capture.

This report records what was actually executed and measured. Nothing here is estimated. Where
something was **not** verified, it says so.

---

## 1. Automated test suite

```
python run_tests.py
Ran 85 tests
All tests passed.
```

85 tests in 8 groups:

| Group | Tests | What is asserted |
|---|---|---|
| Record parsing (`test_firms`) | 17 | sensor inference from satellite codes and filenames, MODIS 0–100 and VIIRS `l/n/h` confidence mapping, coordinate/date rejection, time normalisation, CSV streaming, invalid rows surfaced not raised |
| Geometry (`test_geo`) | 18 | spherical box area, polygon area, point-in-polygon, grid index round-trip (including negative coordinates), haversine, AOI validation errors, stable AOI keys, per-latitude cell area |
| Ingestion (`test_science.TestIngestion`) | 3 | row counts, zero rejections, batch labelling, date bounds |
| Calibration (`TestCalibration`) | 3 | recovers a known 3:18 sensor ratio as weight 0.1667; ≥60-day overlap gate; short overlaps fall back to weights 1.0 |
| Coverage normalisation (`TestCoverageNormalisation`) | 3 | a single-sensor day equals a two-sensor day; raw totals still differ; single-sensor days are scaled up, not down |
| Missing data (`TestMissingData`) | 5 | a delivery gap yields `observed=false` and `null`, not `0`; incomplete months flagged; incomplete months excluded from the baseline; coverage-corrected totals; empty periods return `null` |
| Historical median and anomalies (`TestHistoricalMedian`, `TestAnomalies`) | 9 | median uses complete years only and excludes the evaluated year; seasonal signal visible; percentage suppressed below a 5-detection baseline; robust z arithmetic; `MAD = 0` yields no z; boosted month flagged, normal month not flagged, incomplete month skipped |
| Trends, calendar, API (`TestTrendsAndCalendar`, `test_api`) | 27 | history matrix shape, Mann–Kendall on synthetic monotonic/flat series, year totals, sensor shares, and 14 HTTP endpoint tests including pagination, CSV field preservation, report sections, sensor comparison, anomalies, map cells, and archive upload (accept, de-duplicate, reject wrong type and empty body) |

API tests skip automatically when `httpx` is absent, so the scientific tests never depend on it.

**Synthetic data is confined to the tests.** The fixture writes a batch labelled
`test_synthetic` / "SYNTHETIC TEST FIXTURE - not NASA observations" into a throw-away database under
`data/_test/`. The application database is never touched.

## 2. Real NASA data ingestion

Executed against the key-free FIRMS global snapshot downloaded on 2026-11-14:

| File | Rows read | Rows kept | Duplicates | Rejected |
|---|---|---|---|---|
| `J1_VIIRS_C2_Global_7d.csv` (NOAA-20) | 399,872 | 399,872 | 0 | 0 |
| `J2_VIIRS_C2_Global_7d.csv` (NOAA-21) | 395,418 | 395,417 | 1 | 0 |
| `MODIS_C6_1_Global_7d.csv` (Terra + Aqua) | 76,114 | 76,114 | 0 | 0 |
| `SUOMI_VIIRS_C2_Global_7d.csv` (S-NPP) | 0 | 0 | 0 | 0 |
| **Total** | **871,404** | **871,403** | **1** | **0** |

Date range 2026-11-07 → 2026-11-14 (8 days), quality **NRT / provisional**.

Observations on the data itself:

- The single duplicate is a genuine repeated pixel in the NOAA-21 file; the unique index
  `(sensor, acq_date, acq_time, lat, lon)` removed it. This confirms duplicate handling works on real
  data rather than only in theory.
- **Suomi-NPP VIIRS returned header-only files** (112 bytes) for both the 7-day and 48-hour products at
  download time, i.e. that platform was not delivering near-real-time data. It is therefore absent
  from the demo record. The application handles this correctly: an absent sensor is not zero activity,
  it is simply not part of the observing set. This is a real availability change of exactly the kind
  the harmonisation exists to absorb.
- Zero rows were rejected, which means the field mapping and validation accept the current FIRMS
  schema (including VIIRS confidence delivered as the words `low`/`nominal`/`high` rather than
  `l`/`n`/`h`).

## 3. Endpoints exercised end to end

All of the following returned HTTP 200 with well-formed payloads against the real database:

`/api/health`, `/api/catalog`, `/api/regions`, `/api/search`, `/api/provenance`,
`/api/harmonization`, `/api/calendar/month`, `/api/calendar/year`, `/api/calendar/history`,
`/api/analytics/trends`, `/api/anomalies`, `/api/compare/sensors`, `/api/map/cells`, `/api/map/points`,
`/api/ingest/archive` (uploaded a five-row slice of the real MODIS file: parsed, all five correctly
recognised as duplicates already in the database, and wrong-type and empty uploads rejected with 400),
`/api/detections`, `/api/export/detections.csv`, `/api/export/analytics.csv`,
`/api/export/report.html`.

Exports verified: the detections CSV contains 115,340 records for the Sahel box over November 2026 with
21 original source fields; the daily analytics CSV contains one row per day with per-sensor columns;
the HTML report contains the summary, historical comparison, data-source, methodology and limitation
sections.

## 4. Measured MODIS/VIIRS agreement (Sahel box, 21–33°E, 7–14°N)

Computed from real observations over the 8 co-observed days:

| Metric | Value |
|---|---|
| Co-observed days | 8 |
| MODIS mean detections per day | 1,263.0 |
| VIIRS mean detections per day (NOAA-20 + NOAA-21) | 13,154.5 |
| Ratio MODIS / VIIRS | 0.096 (VIIRS ≈ 10.4×) |
| Median daily ratio | 0.0962 |
| Pearson r (log1p counts) | 0.7525 |
| Spearman rho | 0.881 |
| Cells active — MODIS / VIIRS / both | 609 / 838 / 603 |
| Jaccard overlap of active cells | 0.7145 |
| Spearman across per-cell totals | 0.871 |
| Same-day co-detection within 1 km | 59.6 % (6,021 of 10,104 MODIS detections) |

Reading: both instruments agree strongly about *where* burning is (Jaccard 0.71, cell Spearman 0.87)
and about *when* it varies (Spearman 0.88), while disagreeing by an order of magnitude about *how
much* (ratio 0.096). That is precisely why a raw pooled count is not a harmonised series, and why the
calibration is a magnitude correction rather than a spatial one.

These figures are **agreement diagnostics over eight days**, in one region, in one season. They are
not generalisable and they are not accuracy measures.

## 5. Calibration status on the bundled data

`status = insufficient_overlap`. The ratio (0.096 and 0.198 per platform) is reported, but **not
applied**, because 8 co-observed days is far below the 60-day minimum. Weights stay at 1.0 and the
interface labels the output *coverage-normalised detections*.

Consequently, on the bundled snapshot alone:

- the calendar renders 8 observed days and marks the other 22 days of November as *no observation*;
- no historical median exists for any month (a baseline needs ≥ 3 complete years);
- the trend test reports `insufficient_data` (0 complete years);
- the anomaly list is empty because no month is complete and there is no baseline.

This is the designed behaviour, and it is stated in the interface rather than hidden.

## 5b. Long-record validation (Aegean & Anatolia, 2000–2026)

A second record was built through the FIRMS area API with a live MAP_KEY, to prove that the pipeline
produces real science on real history rather than only passing tests.

**Ingest.** 3,895 five-day API windows, one CSV each, covering 20–28°E / 35–41°N:

| Batch | Rows kept | Duplicates | Rejected | Quality |
|---|---|---|---|---|
| Standard processing (`api_sp`, 3,775 files) | 337,317 | 0 | 0 | science |
| Near-real-time (`api_nrt`, 120 files) | 12,241 | 249 | 0 | provisional |
| Global snapshot (already loaded) | 871,403 | 1 | 0 | provisional |
| **Total record** | **1,220,961** | | | |

Record span **2000-11-01 → 2026-11-14**. Sensor composition in the Aegean area: MODIS 59,265
detections over 9,510 days; VIIRS S-NPP 156,297 over 5,413; NOAA-20 93,482 over 3,150; NOAA-21 40,755
over 1,398.

**Calibration now succeeds** (`status = ok`, unit *MODIS-equivalent detections*):

| Quantity | Value |
|---|---|
| Weight, MODIS (reference) | 1.0000 |
| Weight, VIIRS S-NPP | 0.1969 |
| Weight, VIIRS NOAA-20 | 0.1905 |
| Weight, VIIRS NOAA-21 | 0.2130 |
| Co-observed days (S-NPP / NOAA-20 / NOAA-21) | 5,413 / 3,150 / 1,398 |
| Ratio stability (CV across 4 sub-periods) | 0.2335 (gate: ≤ 0.35) |

VIIRS detects roughly five times more hotspots than MODIS in this region, so its weight is ≈0.2 —
derived from data, not assumed.

**Sensor-transition diagnostic.** Mean activity in the 60 days before versus after each sensor
introduction, raw pooled counts against the harmonised series:

| Introduction | Raw pooled count | Harmonised series |
|---|---|---|
| VIIRS S-NPP, 2012-01-20 | **+753.8 %** | −13.3 % |
| VIIRS NOAA-20, 2018-04-01 | **+342.6 %** | −10.1 % |
| VIIRS NOAA-21, 2023-01-17 | **+241.7 %** | −4.7 % |

This is the central quantitative claim of the project: adding a sensor multiplies the naive count by
2.4–7.5×, while the harmonised series stays within ±13 %. The residual difference includes genuine
seasonal change, so this is a diagnostic, not proof.

**Historical calendar and median.** August 2024 was observed on 31 of 31 days: harmonised activity
2,094 against a historical August median of 1,241 computed from **25 complete years** (2001–2023, 2025,
2026 — 2024 itself excluded). Deviation +853 (+68.7 %), robust z = 1.23, i.e. *above the median but not
flagged*. That restraint is the point: the system does not cry anomaly at every busy month.

**Trends.** 25 complete years entered the test. Theil–Sen slope +37.11 per year; Mann–Kendall
p = 0.3875 → **no significant monotonic trend** is claimed, despite the positive slope.

Two years were excluded, and both exclusions matter:

- **2000** covers only November–December (17 % of the year), so it is not an annual total.
- **2026** covers 318 of 365 days (87 %), which passes a naive 80 % coverage test while still
  missing the end of the year. An earlier version of the code counted it as complete; the rule now
  also requires the record to span the whole period (`in_record`). Dropping that single year moved
  the Theil–Sen slope from +12.02 to +37.11 per year — a useful reminder that the slope is sensitive
  to the endpoint years, which is exactly why the p-value, and not the slope, is the headline.
Reporting the slope together with a non-significant p-value is the honest outcome.

**Anomalies.** 312 months checked, 12 skipped as incomplete, 23 flagged. The strongest are:

| Month | Deviation | Robust z |
|---|---|---|
| August 2007 | +1,025 % | 18.33 |
| July 2007 | +398 % | 15.41 |
| August 2021 | +509 % | 9.10 |
| August 2012 | +210 % | 3.76 |
| October 2008 | +171 % | 3.23 |
| August 2023 | +189 % | 3.38 |

The detector, working only from harmonised counts, independently ranks **August 2007, August 2021 and
August 2023** as the extreme seasons in this region — the three fire seasons that are documented as the
worst in Greece in the satellite era. That is a meaningful corroboration that the harmonised series
tracks real burning, and it is worth stating carefully: it demonstrates that known extreme events rise
to the top of the ranking, not that every detection is a verified wildfire.

**Top years and months** (coverage-corrected): 2007 (28,193), 2021 (13,082), 2011 (12,620), 2008
(11,719); top months August 2007 (13,967) and August 2021 (7,560).

**Performance after indexing** (multi-year record, 349,807 records in the demo area):

| Operation | Time |
|---|---|
| Historical matrix (27 years × 12 months) | 0.12 s |
| Detection table page | 0.17–0.38 s |
| Map grid (486 cells) | 1.26 s |
| Sensor comparison (incl. 1 km co-detection) | 4.75 s |
| Anomaly scan (324 months) | 4.8 s |

Database size 575 MB; derived tables hold 295,458 grid rows and 19,471 sensor-day rows. Two
performance defects were found and fixed during this run: the detection page counted matches with a
Python row scan (7.0 s → 0.17 s after a SQL count plus a covering index), and the map endpoint
aggregated cells globally before filtering (1.7 s → 1.26 s after pushing the cell bounds into SQL).

**What this record still does not prove.** No independent burned-area comparison was made, so no
accuracy figure is claimed. The transition diagnostic cannot separate a sensor effect from a real
seasonal change inside the same window.

## 5c. Post-audit corrections (A1, A2, A3)

Three defects were found in the audit and corrected. A full database backup was taken first
(`data/backups/firetrack-before-A1A2A3-<timestamp>.db`, 618.6 MB) and detections were never deleted.

### A1 — availability now bounded by NASA's delivery windows

NASA's `data_availability` reports that `VIIRS_SNPP_NRT` ends **2026-11-02**, and Earthdata published
an alert that Suomi-NPP ceased operations that day. The database nevertheless marked S-NPP as
"observing" through 2026-11-14, because every queried date had been registered as observed.

| | Before | After |
|---|---|---|
| S-NPP observed days | 5,413 | **5,401** |
| NOAA-21 observed days | 1,398 | **1,355** (standard processing starts 2023-03-01) |
| MODIS / NOAA-20 | 9,510 / 3,150 | unchanged |
| Detections | 1,220,961 | **1,220,961 (unchanged)** |
| S-NPP paired days | 5,413 | 5,401 |
| NOAA-21 weight | 0.2130 | 0.2085 |
| Ratio CV | 0.2335 | 0.2211 |

Effect on the affected days (2026-11-03 → 11-14, all +29 to +31 %): the phantom S-NPP expectation was
removed, so the harmonised value no longer assumes a contribution that could not arrive.

| Date | Before | After | Change |
|---|---|---|---|
| 2026-11-07 | 9.1 | **11.7** | +29 % |
| 2026-11-13 | 41.3 | **53.9** | +31 % |
| 2026-11-14 | 21.2 | **27.6** | +30 % |
| November 2026 total | 230.87 | **294.43** | +27.5 % |
| August 2024 total | 2,093.76 | **2,083.06** | −0.5 % |

The August 2024 change of −0.5 % demonstrates the blast radius: historical months, where every sensor
was delivering, are essentially untouched. A safety rule keeps any out-of-window date that contains
real detections, so the repair can never erase evidence.

### A2 — FRP is separated per sensor

`frp_by_sensor` is now returned by the daily series, the period summary and the map. Every cross-sensor
total is labelled *"sum of raw sensor FRP (not harmonised)"*, the CSV export carries one column per
sensor, and the report shows a per-sensor FRP column. No weight is applied to FRP, because MODIS and
VIIRS retrieve it with different algorithms.

### A3 — critical burning periods

critical_periods() and POST /api/critical-periods provide the Historical Analytics panel and
exported-report section. The threshold is the 90th percentile for the same calendar month across
complete months. Runs break on missing/unusable days, incomplete months, and calendar-month boundaries.
The minimum run length is 3 days. Each reported period therefore has one month-specific threshold and
baseline.

The previous period count and top-period examples were measured before the month-boundary rule. They
are superseded and have been removed rather than presented as current results. Recompute the full-record
period list with the updated implementation before publishing new counts or examples.

### Test results

```
python run_tests.py
Ran 101 tests
All tests passed.
```

This 101-test run predates the A3 calendar-month-boundary change. The new regression check is present
in the current test file, but a post-change test run is not recorded in this report.

85 tests before, **101 now**: 16 new tests cover S-NPP availability ending, preservation of historical
records, protection of days with detections, NOAA-20/MODIS being unaffected, FRP separation and
labelling, and critical-period calculations including gap breaking and incomplete-month exclusion.

## 6. Frontend build

```
tsc --noEmit   → 0 errors
vite build     → 50 modules transformed, dist/ 400 kB JS + 32 kB CSS
```

The built interface was served by the application and verified over HTTP: `/` returned the HTML shell
and both hashed assets returned 200 with correct content types.

**Not verified: interactive rendering in a real browser.** Headless Chromium and Edge cannot start in
the build environment (the sandbox denies the IPC channel they require), so no screenshots were
captured and no automated click-through was performed. The TypeScript compiler, the production build
and the served assets all succeed, and an error boundary is installed so a component failure shows a
message instead of a blank page — but the visual layout has not been observed. A human should open the
application once and confirm the eight routes before a demo.

## 7. Performance observations

| Operation | Observed |
|---|---|
| Full snapshot ingest (871k rows, grid rebuild) | ~80 s (first build; subsequent runs reuse the database) |
| Harmonised series build for a 1,344-cell area | 0.4 s |
| Calendar month / analytics response | < 1 s |
| Map grid for the same area | 844 cells, immediate |

## 8. What is not claimed

- **No accuracy percentage.** No independent burned-area or ground-truth comparison was performed.
- **No long-term validation yet.** The overlap analysis covers 8 days; the calibration gate correctly
  refuses to calibrate on it.
- **No claim that the harmonised index equals burned area, emissions or severity.**
- **No fire prediction and no emergency alerting.** Anomaly flags are statistical statements about
  detections relative to a baseline.
- **No claim of global completeness.** The record covers what was ingested; coverage is displayed
  everywhere.

