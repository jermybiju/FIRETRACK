# FIRETRACK
 **Live Demo:** https://jermybiju.github.io/FIRETRACK/

> **Independent audit notice (2026-11-15):** FIRETRACK currently treats global product date availability and successful area-query windows as proof that a sensor observed the selected AOI. A successful empty FIRMS hotspot query does not establish local satellite coverage or cloud-free observation. As a result, zero-activity days, coverage-normalised values, calibration, historical completeness, trends and anomaly results are **not validated for the selected area**. See [the submission audit](docs/SUBMISSION_AUDIT_2026-11-15.md). Do not present those metrics as scientific findings until area-specific observation/coverage evidence is integrated and the analytics are updated.

**Unified Satellite Burning Activity Intelligence Platform**

> Two satellite perspectives. One consistent history of burning activity.

FIRETRACK harmonises NASA FIRMS **MODIS** and **VIIRS** active-fire detections into a single,
coverage-aware record of burning activity, and presents it as an interactive **burning activity
calendar** — the way people actually read a fire season.

Built for the NASA Space Apps Challenge 2026 — *Harmonization of MODIS and VIIRS Hot Spots*.

---

## 1. The problem

MODIS has observed thermal anomalies since November 2000 at 1 km. VIIRS has added 375 m
observations since 2012. Together they span a quarter of a century, and together they are *not one
measurement*:

| Effect | What goes wrong in a naive combined record |
|---|---|
| Sensor transitions | Totals jump when NOAA-20 (2018) or NOAA-21 (2023) come online, as if the world caught fire |
| Resolution and sensitivity | VIIRS detects roughly 5–10× more hotspots than MODIS in productive fire regions |
| Observation coverage | A four-sensor day and a one-sensor day are not comparable; a day with no observation is not a zero |

A "sum of all hotspots" chart therefore says more about the satellite programme than about fire.
FIRETRACK corrects for these effects explicitly, documents every assumption, and keeps the raw
counts visible so the correction can be inspected rather than trusted.

## 2. What the application does

- **Burning Activity Calendar** (signature feature): month heat map of daily activity, yearly
  profile, multi-year history matrix, and a comparison of any month against its own historical
  median — with sensor coverage shown on every cell.
- **Historical monthly median**: median of the same calendar month across *complete* years, with
  absolute and (where meaningful) percentage deviation, robust z-score, baseline period and coverage.
- **Interactive fire map**: 0.25° activity grid, per-sensor layers, box and polygon drawing, cell
  inspection, NASA Blue Marble or dark basemap.
- **Historical analytics**: yearly series, seasonal profile, top months and years, Mann–Kendall trend
  test with Theil–Sen slope on complete years only.
- **Critical burning periods**: contiguous runs of days above the 90th percentile of the same calendar
  month, broken by missing/unusable days, incomplete months and calendar-month boundaries.
  Each period stays within one month so its threshold and baseline describe that month.
- **Fire radiative power**: reported per sensor and never mixed. Any cross-sensor total is labelled as
  a raw sum, because MODIS and VIIRS retrieve FRP differently.
- **MODIS vs VIIRS**: paired daily correlation, magnitude ratio, spatial Jaccard, per-cell rank
  correlation and same-day 1 km co-detection — the evidence behind the calibration weights.
- **Anomaly explorer**: explainable flags against the historical median, never presented as
  emergency declarations.
- **Data explorer and exports**: filterable hotspot table, CSV of real records, daily analytics CSV,
  and a self-contained HTML report.
- **Methodology page**: the full derivation, parameters in force, and limitations.

## 3. Data

| Sensor | Product | Pixel | Record begins | Streams |
|---|---|---|---|---|
| MODIS (Terra + Aqua) | Collection 6.1 active fire | 1 km | 2000-11 | NRT / SP / archive |
| VIIRS Suomi-NPP | Collection 2 375 m | 375 m | 2012-01 | NRT / SP / archive |
| VIIRS NOAA-20 | Collection 2 375 m | 375 m | 2018-04 | NRT / SP / archive |
| VIIRS NOAA-21 | Collection 2 375 m | 375 m | 2023-01 | NRT / SP / archive |

Source: [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) (Fire Information for Resource
Management System, EOSDIS / LANCE).

**Verified product availability.** Read from the FIRMS `data_availability` endpoint with a live
MAP_KEY on 2026-11-14 — verified, not assumed:

| FIRMS data id | First date | Last date |
|---|---|---|
| `MODIS_SP` (science quality) | 2000-11-01 | 2026-08-31 |
| `MODIS_NRT` (provisional) | 2026-09-01 | present |
| `VIIRS_SNPP_SP` | 2012-01-20 | 2026-07-31 |
| `VIIRS_SNPP_NRT` | 2026-08-01 | 2026-11-02 |
| `VIIRS_NOAA20_SP` | 2018-04-01 | 2026-07-31 |
| `VIIRS_NOAA20_NRT` | 2026-08-01 | present |
| `VIIRS_NOAA21_SP` | 2023-03-01 | 2026-07-31 |
| `VIIRS_NOAA21_NRT` | 2024-01-17 | present |

That table explains a detail visible in the bundled snapshot: Suomi-NPP had no delivering stream after
2026-11-02, which is exactly why its rolling CSV arrived header-only.

**The demo record.** Two real datasets are loaded:

1. **Global rolling snapshot** (`data/raw/snapshot/*.csv.gz`) — key-free, near-real-time (provisional),
   8 days: 2026-11-07 → 2026-11-14, 871,403 detections from MODIS, NOAA-20 and NOAA-21. This is what
   first run ingests automatically, so the app works with no key at all.
2. **Aegean & Anatolia history** — 2000-11-01 → 2026-11-14, the default area, built through the FIRMS
   area API: 337,317 standard-processing plus 12,241 near-real-time detections in 3,895 five-day
   requests. Whole record: **1,220,961 detections** across MODIS, VIIRS S-NPP, NOAA-20 and NOAA-21.

On the long record the science is fully active — calibration succeeds, medians span 25 years, and the
anomaly detector independently ranks the 2007, 2021 and 2023 Greek fire seasons as the extremes. The
measured results are in [`docs/VALIDATION_REPORT.md`](docs/VALIDATION_REPORT.md) §5b.

On the 8-day global snapshot alone the app deliberately refuses to calibrate (`insufficient_overlap`)
and reports no medians or trends. That is the honest behaviour, not a bug: the alternatives would be to
fabricate a baseline or to pretend that one week is a climatology.

**To add history for another area**, choose one:

```powershell
# A. Automated backfill (free MAP_KEY, emailed instantly)
python scripts/fetch_firms_api.py --map-key YOUR_KEY --bbox 21,7,33,14 --start 2000-11-01

# B. Manual archive import (science quality). Request CSV/ZIP for your area at
#    https://firms.modaps.eosdis.nasa.gov/download/ then either
#    - use "Import a NASA FIRMS archive file" on the Data Explorer page, or
#    - upload via the API:
curl -X POST --data-binary "@firms_archive.zip" "http://127.0.0.1:8000/api/ingest/archive?name=firms_archive.zip"
```

A 26-year backfill is rate-limited by NASA to roughly 500 transactions per 10 minutes, so it is a long
job (about 80 minutes for 3,895 windows). It is resumable: files already on disk are skipped, and
`python scripts/ingest_downloaded.py` loads whatever was downloaded. If the key is throttled the
downloader retries with backoff instead of failing.

Put the key in `.env` (`FIRMS_MAP_KEY=...`) to have the interface report it as configured.

## 4. Harmonisation, in one page

1. **Common spatial unit.** Both instruments are aggregated onto the same **0.25° grid**; a cell
   belongs to an area when its centre falls inside it. Analytics read the grid, never raw pixels.
2. **Coverage normalisation.** Each date carries the set of sensors that actually delivered data:

   ```
   H(t) = Σ wₛ·dₛ(t)  ×  (Σ_all wₛ·ρₛ) / (Σ_observed wₛ·ρₛ)
   ```

   `dₛ(t)` is the sensor's detection count, `ρₛ` its mean daily rate in the area, `wₛ` its
   calibration weight. A date with no observing sensor yields **no value**, never a zero.
3. **Overlap-period ratio calibration.** On dates MODIS and a VIIRS platform both observed the area,
   `w_VIIRS = mean(MODIS)/mean(VIIRS)`, so VIIRS detections become MODIS-equivalent. Applied only
   when the overlap has **≥ 60 co-observed days** and the ratio is stable across four sub-periods
   (**CV ≤ 0.35**). Otherwise weights stay at 1.0 and the output is labelled
   *coverage-normalised counts*.
4. **Confidence.** MODIS 0–100 retained; VIIRS `l/n/h` mapped to an ordinal 25/65/90 and explicitly
   labelled as *not a probability*. Filters act on the published classes.
5. **Raw counts stay visible.** The uncalibrated pooled count is computed and exported beside every
   harmonised value, so the effect of harmonisation can always be measured.

The full derivation, including what the method does **not** correct, is in
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## 5. Quick start

Requirements: **Python 3.10+**. Node.js is only needed if you want to modify the interface.

```powershell
cd FIRETRACK
.\run.cmd
```

then open <http://127.0.0.1:8000>.

`run.cmd` is a batch file, so it works even where PowerShell blocks unsigned `.ps1` scripts (the
default on many Windows machines). The first run creates `.venv`, installs two packages (FastAPI,
uvicorn) and ingests the bundled snapshot — around one to two minutes. Later runs start in a few seconds.

Alternatives that need no execution-policy change:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1     # PowerShell launcher
.\.venv\Scripts\python.exe run.py                      # direct, no launcher
```

macOS / Linux:

```bash
cd FIRETRACK
chmod +x run.sh
./run.sh
```

Manual start, no launcher (works from any directory — `run.py` sets its own import path):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py --port 8000
```

## 6. Configuration

Copy `.env.example` to `.env`. Everything is optional.

| Variable | Default | Purpose |
|---|---|---|
| `FIRMS_MAP_KEY` | *(empty)* | Enables historical backfill; shown as configured in the UI |
| `FIRETRACK_DATA_DIR` | `./data` | Database and raw download location |
| `FIRETRACK_DB` | `data/firetrack.db` | Explicit database path |
| `FIRETRACK_HOST` / `FIRETRACK_PORT` | `127.0.0.1` / `8000` | Bind address |
| `FIRETRACK_GRID_DEG` | `0.25` | Common analysis grid |

Never commit `.env`. The repository's `.gitignore` already excludes it.

## 7. Architecture

```
Browser ──HTTP──> FastAPI (one process, port 8000)
                    ├── /api/*          JSON analytics
                    ├── /docs           OpenAPI docs
                    └── /               React build (frontend/dist)
                          │
                          └── SQLite data/firetrack.db
                                detections   raw FIRMS records (traceability)
                                daily_cells  0.25° aggregates (all analytics)
                                sensor_days  availability calendar
                                ingest_batches provenance
```

| Module | Responsibility |
|---|---|
| `backend/app/firms.py` | CSV parsing, field normalisation, confidence mapping, API client |
| `backend/app/ingest.py` | Ingestion, dedupe, availability, grid rebuild |
| `backend/app/harmonize.py` | Coverage normalisation and ratio calibration |
| `backend/app/analytics.py` | Calendar, medians, trends, anomalies |
| `backend/app/agreement.py` | MODIS/VIIRS agreement and co-detection |
| `backend/app/report.py` | Self-contained HTML report |
| `backend/app/api.py` | HTTP surface |
| `frontend/src` | React + TypeScript + Leaflet UI, hand-written SVG charts |

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/DATA_FLOW.md`](docs/DATA_FLOW.md).

## 8. Testing

```powershell
python run_tests.py -v
```

85 automated tests cover ingestion, validation, sensor identification, confidence mapping, spatial
and temporal aggregation, missing-data handling, duplicate handling, harmonisation arithmetic,
calibration gating, historical medians, anomaly detection, the HTTP API and both CSV exports.

Tests use a clearly-labelled synthetic fixture (`kind = test_synthetic`) and write to a throw-away
database under `data/_test/`. They never touch the application database, and no synthetic record is
ever presented as NASA data. Results are recorded in
[`docs/VALIDATION_REPORT.md`](docs/VALIDATION_REPORT.md).

## 9. Scientific assumptions and limitations

- A FIRMS hotspot is a **thermal anomaly**, not a confirmed wildfire. It may be agricultural burning,
  an industrial flare, gas flaring or volcanic heat.
- **Missing observations are never treated as zero activity.** Days without an observing sensor are
  excluded and their coverage is displayed.
- **Cloud cover is not corrected.** FIRMS reports detections, not observation attempts, so a cloudy
  day and a fire-free day can look alike at pixel level. The coverage model corrects for sensor
  availability only.
- The calibration is a **single multiplicative bias correction** per sensor and area. It cannot
  remove resolution-driven non-linearity (VIIRS resolves fires MODIS misses).
- **No accuracy percentage is claimed.** That would require independent burned-area or ground truth.
- Trend tests do not correct for serial correlation; a detected trend concerns detections, not burned
  area or emissions.
- Near-real-time records are **provisional** and are superseded by standard processing after roughly
  five months. Provenance is shown per batch and per record.
- FIRETRACK is a research prototype, **not an official emergency alert system**.

## 10. Roadmap

- Import the science-quality archive end-to-end and re-run the overlap analysis on a full record.
- Season-aware calibration (per calendar month) where the overlap supports it, with an explicit
  over-fitting test.
- Pixel-level observation masks (cloud/quality) to separate "not observed" from "not burning".
- Optional PostGIS backend for multi-user deployments.
- Region comparison (two AOIs side by side) and a shareable permalink for a selection.

## 11. Credits and licence

Observations: **NASA FIRMS / EOSDIS / LANCE**. Basemap imagery: **NASA EOSDIS GIBS** (Blue Marble)
and **CARTO/OpenStreetMap** (dark basemap).

Academic and competition use. See `docs/AI_USAGE.md` for the AI assistance disclosure.

