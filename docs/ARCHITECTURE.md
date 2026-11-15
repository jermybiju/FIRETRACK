# FIRETRACK architecture

FIRETRACK is a single-process application. One Python process serves both the JSON API and the
built web interface on one port, and one SQLite file holds all data. There is no separate database
server, no message queue, no tile server and no external geospatial service in the analysis path.
The reason is practical: a judge can open the folder, run one command, and have the whole system
running on a laptop. The only network-dependent part is the optional map basemap; all analysis works
offline once the data is ingested.

## Process and deployment layout

```text
 Browser (Chrome / Edge / Firefox)
   |
   |  GET /#/calendar          (static files)
   |  POST /api/calendar/month (JSON)
   v
 uvicorn 0.32  ---  FastAPI 0.115 app  (backend/app/api.py)
   |
   +-- mount "/"  ->  StaticFiles(frontend/dist, html=True)
   |                    index.html + content-hashed JS/CSS
   |
   +-- /api/* routes
   |      |
   |      +-- analytics.py      calendar, baselines, trends, anomalies
   |      +-- agreement.py      MODIS vs VIIRS comparison
   |      +-- harmonize.py      grid aggregation, calibration, H(t)
   |      +-- report.py         self-contained HTML report
   |      +-- geo.py / regions.py   AOI validation, grid maths, offline gazetteer
   |      |
   |      +-- db.py  ->  SQLite  data/firetrack.db  (WAL)
   |
   +-- startup (backend/app/main.py)
          db.init_db()
          if database empty: ingest.ingest_snapshot_dir()
                 |
                 +-- firms.py reads data/raw/snapshot/*.csv or *.csv.gz
```

The server is started by `run.ps1` (Windows) or `run.sh` (macOS/Linux). Both set `PYTHONPATH` to
`backend/`, create or reuse a virtual environment, install FastAPI and uvicorn if they are missing,
and then run `python -m app.main`.

## Components

| Component | Technology | Location | Responsibility |
|---|---|---|---|
| HTTP service | FastAPI 0.115.6, uvicorn 0.32.1 | `backend/app/main.py`, `api.py` | Routing, request validation, JSON/CSV/HTML responses, static mount |
| Scientific core | Python 3.10+ standard library only | `harmonize.py`, `analytics.py`, `agreement.py` | Grid aggregation, calibration, coverage normalisation, statistics |
| Ingestion | `csv` from the standard library | `firms.py`, `ingest.py` | CSV parsing, field normalisation, deduplication, table rebuilds |
| Geospatial helpers | `math` only, no Shapely or GeoPandas | `geo.py`, `regions.py` | AOI validation, point-in-polygon, cell indices, cell area, presets |
| Storage | SQLite 3 via `sqlite3` | `db.py`, `data/firetrack.db` | Raw records, derived aggregates, availability, provenance |
| Report renderer | `html` plus inline SVG strings | `report.py` | One-file HTML report with embedded charts and CSS |
| Web interface | React 18.3, TypeScript 5.6, Vite 5.4 | `frontend/src` | Eight pages, hash routing, shared state |
| Map | Leaflet 1.9.4 | `components/MapView.tsx` | Tile basemap, activity circles, area drawing |
| Charts | Hand-written SVG | `components/charts.tsx` | Line, bar, stacked bar, sparkline; no charting library |
| Design system | Hand-written CSS | `src/styles.css` | Colour tokens, layout, panels, tables, calendar grid |
| Launchers | PowerShell and bash | `run.ps1`, `run.sh` | Environment setup and process start |

## Backend module responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | Paths, sensor catalogue, scientific parameters, `.env` loading, environment overrides |
| `main.py` | Argument parsing, first-run bootstrap, uvicorn start, frontend mount |
| `api.py` | Twenty HTTP endpoints, request models, AOI/date validation, per-series cache |
| `db.py` | Schema, one connection per thread, WAL pragmas, query helpers, metadata keys |
| `firms.py` | Column aliases, sensor inference, confidence mapping, timestamp normalisation, FIRMS API client |
| `ingest.py` | Streaming inserts, duplicate handling, `daily_cells` rebuild, `sensor_days` availability, batches |
| `geo.py` | AOI dataclass, bbox/polygon validation, cell indices, spherical cell area, hash key |
| `regions.py` | Ten preset regions and a 60-entry offline city gazetteer |
| `harmonize.py` | AOI series loading, overlap calibration, `H(t)`, period aggregation, median/MAD comparison |
| `analytics.py` | Month/year/history calendars, Mann-Kendall, Theil-Sen, robust z-score anomalies |
| `agreement.py` | Paired-day correlation, magnitude ratio, spatial Jaccard, 1 km co-detection, transitions |
| `report.py` | Self-contained HTML export |
| `__init__.py` | Package marker |

## Frontend structure

The interface has no router library. `App.tsx` reads `window.location.hash`, strips the leading
`#/`, ignores query parameters, and falls back to `overview`. A `hashchange` listener keeps the
route in sync. Hash routing is deliberate: every page is served from the same `index.html`, so the
static file mount never needs an SPA rewrite rule.

| Route | Page component | Content |
|---|---|---|
| `/#/overview` | `pages/Overview.tsx` | Mission statement, headline statistics, latest-month grid, guided demo links |
| `/#/calendar` | `pages/CalendarPage.tsx` | Month heat map, year profile, multi-year history matrix, month-vs-median view |
| `/#/map` | `pages/MapPage.tsx` | Leaflet activity grid, sensor layers, date range, draw-a-box/polygon, top cells |
| `/#/analytics` | `pages/AnalyticsPage.tsx` | Yearly series, seasonal profile, trend test, top months/years, coverage audit |
| `/#/compare` | `pages/ComparePage.tsx` | Paired daily series, agreement metrics, spatial overlap, co-detection |
| `/#/anomalies` | `pages/AnomaliesPage.tsx` | Robust z-score flags at 2.0/2.5/3.0 with full explanations |
| `/#/explorer` | `pages/ExplorerPage.tsx` | Filterable raw records, provenance, CSV and report exports |
| `/#/methodology` | `pages/MethodologyPage.tsx` | Method, data sources, validation approach, limitations, live calibration |

Shared state lives in `state.tsx` (`AppProvider`): the selected AOI, date range, confidence filter
and sensor filter are persisted in `localStorage` under `firetrack.*` keys. A `useAsync` hook wraps
every request and discards stale responses by sequence number, so quickly changing the month cannot
render an older answer.

The charts are hand-built SVG in `charts.tsx`; the only third-party visual dependency is Leaflet.
The CSS in `styles.css` is a small design system: custom properties for colour, spacing and radius,
one accent colour (fire orange) with instrument hues, and components for panels, badges, tables,
segmented controls and the calendar grid. There is no CSS framework and no icon package; icons are
inline SVG paths.

## HTTP API

Every analytical response carries the context needed to read it: AOI, grid size, sensors observing,
calibration status and unit. The API does not return a bare number.

| Method | Path | Returns | Used by UI |
|---|---|---|---|
| GET | `/api/health` | Status, version, detection count, `ready`, `map_key_configured`, server time | No |
| GET | `/api/catalog` | Sensor catalogue, coverage, availability, batches, grid size, parameters, caveat | Yes |
| GET | `/api/provenance` | Provider, source URL, products, retrieval batches, processing notes, disclaimer | No |
| GET | `/api/regions` | Ten preset regions with bbox, biome and description | Yes |
| GET | `/api/search?q=` | Matching preset regions and gazetteer cities | Yes |
| POST | `/api/harmonization` | Series context, calibration weights/status, sensor timeline, availability, transitions | Yes |
| POST | `/api/calendar/month` | Day cells, month summary, historical median, comparison, context | Yes |
| POST | `/api/calendar/year` | Twelve monthly summaries, complete-month count, peak month, year total | Yes |
| POST | `/api/calendar/history` | Year-by-month matrix (harmonised or raw) with coverage and completeness | Yes |
| POST | `/api/analytics/trends` | Yearly series, seasonal profile, Mann-Kendall + Theil-Sen, top months/years | Yes |
| POST | `/api/anomalies` | Threshold, months checked/skipped, elevated and depressed flags with method | Yes |
| POST | `/api/compare/sensors` | Paired daily series, ratio, correlations, Jaccard, per-platform rows, co-detection | Yes |
| POST | `/api/map/cells` | Grid cells with centre coordinates, totals, FRP sum and per-sensor split | Yes |
| POST | `/api/map/points` | Individual detections for one day, capped at 4,000, with a truncation flag | No |
| POST | `/api/detections` | Filtered page (limit capped at 500), total, truncation flag, period, context | Yes |
| POST | `/api/export/detections.csv` | Streaming CSV of every matching detection, not just the visible page | Yes |
| POST | `/api/export/analytics.csv` | Daily CSV: observed, raw total, harmonised, coverage, FRP, per-sensor counts | Yes |
| POST | `/api/export/report.html` | Self-contained HTML report with inline SVG charts | Yes |
| POST | `/api/ingest/snapshot?force=` | Re-ingests the bundled snapshot, clears the series cache, returns batches | No |
| GET | `/api/ingest/status` | Ingest summary plus the data caveat | No |

Errors return `{"detail": "..."}` with a readable message: `400` for an invalid AOI, date or month,
`404` when an area and period contain no observations, `409` when the database is empty, `500` when
ingestion fails. An `HTTPException` handler in `api.py` normalises this shape.

## Storage

Six tables are created on first use:

| Table | Contents |
|---|---|
| `detections` | One row per FIRMS detection, unmodified apart from normalisation; includes `cell_ix`/`cell_iy` |
| `daily_cells` | Detections aggregated by cell, UTC date and sensor; the table every statistic reads |
| `sensor_days` | One row per sensor and date, `observed = 1` when that product delivered data |
| `ingest_batches` | Provenance for every ingest: kind, files, row counts, date range, sensors, quality |
| `meta` | Schema version, last ingest time and batch id |
| `areas` | Reserved for saved AOIs; the current interface stores saved areas in the browser |

A unique index on `(sensor, acq_date, acq_time, lat, lon)` makes re-ingesting the same file
idempotent. `daily_cells` has a composite primary key on `(cell_ix, cell_iy, acq_date, sensor)` and
is declared `WITHOUT ROWID` because it is only ever accessed by its key. Connections use WAL mode,
`NORMAL` synchronous, a 64,000 KiB page cache and one connection per thread.

## Key design decisions

1. **Keep raw and derived data side by side.** `detections` preserves every point; `daily_cells` is
   the only table the analytics read. A raw count can therefore never be silently mixed with a
   harmonised index, and the map and explorer can always show the underlying records.
2. **Rebuild derived tables instead of incrementing them.** Every ingest deletes and recreates
   `daily_cells` from `detections` with a single `GROUP BY`. Duplicate rows can never be counted
   twice, and a bug in the aggregation is fixed by re-running it, not by migrating data.
3. **Missing observations are null, not zero.** A day with no observing sensor produces
   `harmonized: null` and `observed: false`. Every aggregation filters those days out and reports
   coverage next to the result.
4. **Calibration is gated and labelled.** Weights are applied only when the overlap is at least 60
   co-observed days and the ratio is stable (CV ≤ 0.35). Otherwise weights stay at 1.0 and the unit
   changes from "MODIS-equivalent detections" to "coverage-normalised detections" in the API and in
   every screen that shows a value.
5. **One spatial unit for both instruments.** Everything is computed on a 0.25° grid, so a
   "detection" means the same area for MODIS and VIIRS before any comparison is made.
6. **Parameters are configuration, not hidden constants.** Grid size, overlap gate, CV limit,
   coverage gate and anomaly threshold are in `config.py`, overridable by environment variable, and
   exposed in `/api/catalog` so the interface can display them.
7. **One process, one port.** Static files are mounted at `/` after the API routes are registered.
   The browser and the API share an origin, so no proxy is needed in normal use.
8. **Standard library first.** The only runtime dependencies are FastAPI and uvicorn. Statistics,
   geospatial maths, CSV parsing and chart rendering are implemented directly, which keeps install
   size and failure modes small.
9. **Every ingest leaves a receipt.** `ingest_batches` records which files were read, how many rows
   were kept, rejected or duplicated, and whether the batch was provisional (NRT) or science quality.

## Ports, configuration and build

Default: `http://127.0.0.1:8000`, serving both UI and API.

```powershell
cd FIRETRACK
.\run.ps1                      # start on port 8000
.\run.ps1 -Port 8010           # another port
.\run.ps1 -OpenBrowser         # start and open the interface
.\run.ps1 -SkipInstall         # start without checking dependencies
```

```bash
./run.sh                       # macOS / Linux
PORT=8010 ./run.sh
```

| Environment variable | Default | Effect |
|---|---|---|
| `FIRETRACK_HOST` | `127.0.0.1` | Bind address |
| `FIRETRACK_PORT` | `8000` | HTTP port |
| `FIRETRACK_DB` | `data/firetrack.db` | SQLite file path |
| `FIRETRACK_DATA_DIR` | `data` | Root for raw files, database and exports |
| `FIRETRACK_GRID_DEG` | `0.25` | Analysis grid resolution in degrees |
| `FIRMS_MAP_KEY` | empty | Enables the area-API backfill and the "key configured" badge |

`.env` in the project root is read at import time; real environment variables win over the file.

The interface is a build step, not a runtime dependency:

```powershell
cd frontend
pnpm install
pnpm build        # runs "tsc --noEmit && vite build", output in frontend/dist
pnpm dev          # development server on http://127.0.0.1:5173, proxies /api to :8000
```

`run.ps1` prints a warning when `frontend/dist/index.html` is absent. In that case the API still
works and `/` returns a small HTML page listing the build commands, so a missing build never looks
like a broken server.

## Startup sequence

1. `run.ps1` selects a Python 3.10+ interpreter, reuses `.venv` or `.pydeps`, and installs
   `requirements.txt` if FastAPI or uvicorn cannot be imported.
2. `app.main` parses `--host`, `--port`, `--reload` and `--no-ingest`.
3. Unless `--no-ingest` is passed, `bootstrap()` creates the schema and, if `detections` is empty,
   ingests the bundled snapshot files.
4. `mount_frontend()` attaches `frontend/dist` at `/` when it exists; otherwise a fallback page is
   registered.
5. uvicorn serves the FastAPI app on the requested host and port.

## Deliberate omissions

There is no authentication, no multi-user support, no background job scheduler and no map tile proxy.
The only write path is `POST /api/ingest/archive`, which accepts a single bounded FIRMS file (500 MB
cap, extension-checked, flattened ZIP members) and is intended for a local single-user session; it is
not a general upload API. CORS is open to all origins for local development. FIRETRACK is a
single-user research prototype, and the interface says so.
