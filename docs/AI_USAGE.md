# AI usage disclosure

FIRETRACK was built with substantial AI assistance. This document records what the AI did, what the
human team decided, how the result was verified, and where the verification stops. It is written so
that a judge or reviewer can challenge any claim and re-run the checks.

## Summary

- AI assistance was used for code generation, refactoring, documentation and review.
- The scientific method, the thresholds, the refusal to report an accuracy figure, and the decision
  to ship an eight-day demo with visible limitations were human decisions.
- 85 automated tests exist and all pass, including the 14 HTTP tests (those skip automatically when
  `httpx` is absent, which is why `requirements-dev.txt` lists it).
- Real NASA FIRMS data was ingested and cross-checked against the database.
- All observations displayed by the application come from NASA FIRMS. Synthetic records exist only
  inside labelled software tests.

## How AI was used

| Area | What the AI produced | Human review |
|---|---|---|
| Backend code | FastAPI routes, SQLite schema and queries, CSV parsing, ingestion pipeline, report renderer | Read and tested module by module; behaviour changed where it was wrong |
| Scientific code | Implementations of the harmonised index, calibration gating, Mann-Kendall, Theil-Sen, robust z-score, spatial agreement metrics | Method and parameters specified and checked by the team |
| Frontend | React pages, hash routing, hand-written SVG charts, CSS design system, Leaflet map | Reviewed in the browser; layout, labels and empty states corrected |
| Refactoring | Splitting the scientific core into `harmonize`, `analytics`, `agreement`, `geo`, `regions` | Accepted after the test suite stayed green |
| Tests | Unit and API test scaffolding, synthetic fixtures | Reviewed for what they actually assert, not just that they pass |
| Documentation | Drafts of this documentation set plus in-app methodology text | Corrected against the code; numbers re-read from the database |
| Review | Reading the code for inconsistencies, stale claims and missing caveats | Findings accepted or rejected by the team |

## Scientific and product decisions made by the team

| Decision | Value / position | Why it is a human decision |
|---|---|---|
| Analysis grid | 0.25° | Chosen by the team and configurable through `FIRETRACK_GRID_DEG`; not derived from the source pixels |
| Calibration gate | At least 60 co-observed days | Threshold chosen by the team and recorded in `config.py` |
| Stability gate | Ratio CV ≤ 0.35 across four overlap blocks | Rejects a ratio that the code finds unstable across sub-periods |
| Coverage gate | 80% of days for a complete month or year | Prevents a partly observed month from entering a median |
| Anomaly method | Robust z-score with median and MAD, default threshold 2.5 | Chosen over mean and standard deviation so one extreme year cannot hide everything else |
| Trend method | Mann-Kendall plus Theil-Sen, complete years only | Non-parametric and robust; the serial-correlation limitation is stated rather than hidden |
| Accuracy reporting | None | No independent ground truth exists here; inventing a figure would be the most damaging thing the project could do |
| Demo data | The key-free rolling snapshot, eight days | Honest and reproducible without a key; the length limitation is shown, not concealed |
| Empty states | Explicit gaps, skipped counts and warnings | The interface must never render missing data as zero activity |

## Verification performed

| Check | Result |
|---|---|
| Automated test suite (`python run_tests.py`) | 85 tests, all passing, including the 14 HTTP tests (run with `httpx` installed from `requirements-dev.txt`) |
| HTTP contract | 18 read, analysis, map, record and export endpoints returned HTTP 200 with well-formed payloads against the real database; all three exports were checked, including a detections CSV with 115,340 records for the Sahel selection. The two `/api/ingest/*` routes were not separately exercised; ingestion ran through the first-run bootstrap |
| Real data ingestion | 871,403 detections from four recorded batches, covering 2026-11-07 to 2026-11-14 |
| Per-sensor counts | MODIS 76,114; VIIRS NOAA-20 399,872; VIIRS NOAA-21 395,417 |
| Derived tables | 160,739 `daily_cells` rows rebuilt from the raw records |
| Calibration behaviour | On the bundled data: status `insufficient_overlap`, 8 paired days per platform, all weights 1.0, unit "coverage-normalised detections" |
| Coverage gating | November 2026 in the Sahel: 8 of 30 days observed, coverage 0.267, month marked incomplete, excluded from the median |
| Trend behaviour | With no complete year, the API returns `insufficient_data` rather than a slope |
| Anomaly behaviour | 0 months checked, 12 skipped as incomplete, 0 flags |
| Arithmetic cross-check | The monthly estimate 432,525 equals the mean daily value 14,417.5 multiplied by 30 days |
| Frontend build | `tsc --noEmit` reports no errors and the production build produces the bundle; the served shell and hashed assets return HTTP 200. Visual layout was not observed in the build environment |
| Provenance | Each batch's files, row counts, date range and quality are readable in `ingest_batches` and in the Data Explorer |

The full test list is in `backend/tests/`: `test_science.py` for harmonisation, calibration, coverage,
trends and anomalies; `test_geo.py` for AOI and grid maths; `test_firms.py` for parsing and
normalisation; `test_api.py` for the HTTP surface.

## Data integrity statement

Every detection displayed by FIRETRACK was downloaded from NASA FIRMS (EOSDIS / LANCE), either from
the key-free global rolling files or through the area API with a MAP_KEY. The bundled database
contains no synthetic rows. Synthetic records are generated only by `backend/tests/fixtures.py`,
written to a throw-away database under `data/_test/`, and labelled `kind = "test_synthetic"` with the
description "SYNTHETIC TEST FIXTURE - not NASA observations". A test asserts that this label is
present, so fixture data cannot pass as observations unnoticed.

No observation was imputed. Missing fields stay null, and dates with no observing sensor are null
rather than zero throughout the pipeline.

## What is not verified

- **No accuracy figure.** There is no comparison against burned-area perimeters or ground truth, so
  none is reported. The agreement metrics measure similarity between instruments, not correctness.
- **The HTTP suite needs one extra package.** `httpx` powers Starlette's test client; without it the
  14 tests in `test_api.py` skip rather than fail. It is listed in `requirements-dev.txt`, and in the
  recorded run all 85 tests executed and passed.
- **No automated visual checks.** Headless browsers could not start in the build environment, so the
  build produced no screenshot automatically and no automated click-through was performed. The
  TypeScript check, the production build and the served assets were verified, and each page's data
  contract was traced to the verified analysis functions; a human must still open the eight routes
  once before presenting. Capture steps are in `DEMO_SCRIPT.md`.
- **One sensor is absent from the demo.** The Suomi-NPP global file was header-only at download
  time, so the bundled database contains MODIS, NOAA-20 and NOAA-21 only. The ingestion and
  calibration code path for four sensors is present; the demo does not exercise it with real data.
- **The calibrated path is tested, not demonstrated.** Tests cover a record long enough to apply
  weights; the eight-day bundle cannot. The `ok` calibration status is therefore not visible in the
  demo interface.
- **No scale benchmark.** No continental or global performance measurements were made, and none are
  claimed.

## Reproducing the checks

```powershell
cd FIRETRACK

python run_tests.py

$env:PYTHONPATH = "backend"
python -m unittest discover backend/tests

python scripts/download_firms_snapshot.py

python -c "import sqlite3; print(sqlite3.connect('data/firetrack.db').execute('SELECT COUNT(*) FROM detections').fetchone()[0])"
python -c "import sqlite3; print(sqlite3.connect('data/firetrack.db').execute('SELECT sensor, COUNT(*) FROM detections GROUP BY sensor').fetchall())"
python -c "import sqlite3; print(sqlite3.connect('data/firetrack.db').execute('SELECT kind, files, rows_kept, min_date, max_date FROM ingest_batches').fetchall())"
```

To replace the eight-day bundle with a real historical record:

```powershell
$env:FIRMS_MAP_KEY = "YOUR_FREE_KEY"
python scripts/fetch_firms_api.py --region sahel_belt --start 2000-11-01
```

That is the sequence that would let the 60-day calibration gate and the 80% coverage gate pass. Until
it is run, FIRETRACK reports coverage-normalised counts and no long-term statistics, and the
interface says exactly that.
