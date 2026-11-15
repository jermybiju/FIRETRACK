# FIRETRACK final submission audit — 15 November 2026

## Verdict: NOT READY TO SUBMIT

This audit was conducted on the supplied copy at `C:\Users\user\OneDrive\Documents\Codex\FIRETRACK_GPT_AUDIT`. The user's separately supplied project copy was not accessed. A backup was created outside this directory at `C:\Users\user\Documents\Codex\FIRETRACK_GPT_AUDIT-backup-20261115-230000`; the main SQLite file in the backup matched the supplied copy by SHA-256. `.env` was not copied or read. Tests used synthetic scratch databases under the backup's `data/_test`.

## Inventory

The project is a Python/FastAPI + SQLite backend and React/TypeScript/Vite + Leaflet frontend. The documented UI has eight pages: Overview, Burning Calendar, Fire Map, Historical Analytics, MODIS vs VIIRS, Anomaly Explorer, Data Explorer, and Methodology. Backend modules cover FIRMS parsing, ingestion/deduplication, AOI geometry, harmonization, analytics, comparison, exports, and API endpoints. Data includes a 1,220,961-row `data/firetrack.db`, bundled global FIRMS snapshots, and extensive area API CSVs. The root includes launch scripts, requirements, tests, and methodology, architecture, data-flow, demo, validation, presentation, and AI-use documents. No `.git` directory was visible; `git status` failed with access denied, so Git state is unknown. A `.env` file is present; its contents were deliberately not read or exposed, and `.gitignore` excludes `.env`.

The listed feature inventory includes NASA FIRMS; MODIS and VIIRS platforms; AOI presets/search/coordinates/drawn box and polygon; 0.25-degree grid and deduplication; calendar and historical analytics; calibration/comparison; anomaly explorer; map/chart dashboard; detections and analytics CSVs; HTML report exports. Alerts are not documented as an implemented feature. Feature presence is not evidence that calculations are valid.

## Critical scientific blocker — area coverage is unsupported

`backend/app/ingest.py` marks every day between detections as observed and `register_observation_days()` marks successful area-query windows observed even if the response contains no detections. `backend/app/harmonize.py::load_series()` then loads `sensor_days` globally, without associating those dates with the selected AOI. The available NASA `data_availability` windows are product-level date ranges, not AOI-specific observation/clear-sky evidence. Consequently, the code can treat an empty query as a zero count, count global dates as AOI coverage, and inflate the paired-day sample used for calibration and completeness gates.

I reproduced this safely with an empty scratch database: zero detections, a successful queried date, and `sensor_days.observed = true`. NASA FIRMS documents its area service as returning hotspot detections for an area/date/sensor and `data_availability` as product date availability. NASA also explains that fires can be missed between overpasses or obscured by cloud, smoke, or canopy. These sources do not make a successful empty hotspot query proof of local observation.

Because no AOI-specific footprint or clear-sky coverage evidence is supplied to this application, calibration weights, “coverage-normalised” values, zero-activity days, historical completeness, trend and anomaly results cannot be validated for AOIs. The bundled synthetic tests validate arithmetic under their simulated observation flags; they do not validate this real-world coverage assumption. The code path remains a release blocker. The app must not be described as scientifically validated until it uses spatially and temporally appropriate coverage evidence or disables the affected inferences and labels the remaining data as detections only.

## NASA challenge alignment

The official challenge calls for a web application harmonizing MODIS and VIIRS active-fire hotspots into a burning activity calendar for a selected area, with historical patterns and unusual conditions. FIRETRACK has a strong feature-level match. Its current AOI coverage model undermines the validity of those results. NASA endorsement is not claimed. Sources: [official challenge](https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/), [2026 event page](https://www.spaceappschallenge.org/2026/).

## Severity and repair status

- **Critical, not fixed:** AOI sensor “observation” and coverage are inferred from product-level date ranges and empty FIRMS queries. This affects zero handling, calibration, completeness, trends and anomalies.
- **High, not verified:** complete API/integration tests, application startup and browser UI.
- **Medium, not verified:** frontend production build; bundled pnpm module links were not usable in this sandbox.
- No database migration, deletion, or overwrite was performed. No application code was changed. The docs now disclose the blocker at the top of README, methodology, and validation report and point to this audit.

A full analytics correction requires additional coverage evidence and coordinated backend/API/UI semantics; making only a superficial wording change in code would leave unsupported values in the charts, so that code change was not made.

## Verification results

- Backup: created as a timestamped directory outside the supplied project; database file exists and SHA-256 matched source. Backup excludes `.env`; the included database row count is 1,220,961.
- Database: read-only `PRAGMA integrity_check` returned `ok`; tables present: areas, daily_cells, detections, ingest_batches, meta, product_windows, sensor_days.
- Backend tests: 88 tests passed across `test_geo`, `test_firms`, `test_corrections`, and `test_science` (41 + 47). The full runner stalled on its first API anomaly test for over two minutes and was interrupted. API tests are therefore not verified.
- Frontend: `node --version` returned 24.22.1 and `pnpm --version` returned 11.25.0. `pnpm build` failed while trying to create a symlink in the sandbox package store; direct TypeScript invocation could not resolve the installed React/Leaflet type packages. TypeScript and production build are not verified.
- Browser/E2E: not run. No browser verification is claimed.
- Startup/API health: not run.
- NASA source verification: official FIRMS area and data-availability endpoint documentation and official NASA FIRMS notes were checked. FIRMS detection records represent thermal anomalies, not confirmed wildfires; product type and processing quality need to remain visible.
- Documentation: methodology and attribution to NASA FIRMS exist. A project software license was not found in the enumerated files, and third-party/basemap attribution/license requirements were not fully audited.

## NASA Space Apps judging dimensions

- **Relevance:** strong feature match to challenge.
- **Impact:** plausible monitoring/analysis use; not evaluated with users.
- **Creativity:** no comparative judging assessment made.
- **Validity:** currently blocked by unsupported AOI coverage assumptions.
- **Presentation:** substantial demo/documentation exist; browser usability was not verified.

## Launch and demo

The README documents `.\run.cmd` from the project root and `http://127.0.0.1:8000`; this instruction was not executed or verified. Do not present the built-in coverage, calibration, historical trend, or anomaly values as validated evidence. A safer demo should identify records as FIRMS thermal-anomaly detections and explicitly show the coverage limitation until fixed.

## Suggested official submission description (only after the blocker is fixed or clearly scoped)

“FIRETRACK explores how MODIS and VIIRS active-fire hotspot records can be compared in an area-based calendar. It combines NASA FIRMS detections with maps, historical views, sensor comparisons, and explainable anomaly exploration, while exposing the source records and methodology. The current prototype does not yet have AOI-specific satellite observation or cloud-clear coverage evidence, so empty dates and derived calibration, completeness, trend, and anomaly statistics require further validation. FIRMS hotspots are thermal anomalies, not confirmed wildfires.”

This description is candid, but the unresolved validity blocker means the current verdict remains **NOT READY TO SUBMIT**.
