# START HERE

You are looking at **FIRETRACK** — a working application, not a mockup. This file tells you exactly
what to type, what you will see, and what is still missing.

---

## 1. Run it (one step)

In VS Code, open the folder `FIRETRACK`, then open a terminal (`` Ctrl+` ``):

```powershell
.\run.cmd
```

Wait for `Starting server on http://127.0.0.1:8000`, then open that address in your browser.

The first start takes one to two minutes because it creates a Python environment and loads the NASA
data. Later starts take a few seconds.

**Why `run.cmd` and not `run.ps1`?** Many Windows machines block `.ps1` scripts unless you change the
PowerShell execution policy, which is an unnecessary hurdle. The `.cmd` launcher is a plain batch file,
so it always runs — you can even double-click it.

If you prefer PowerShell, this form works without changing any policy:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Or start the server directly, with no launcher at all:

```powershell
.\.venv\Scripts\python.exe run.py
```

`run.py` sets up its own import path, so `python run.py` works from any directory — you never need to
set `PYTHONPATH`.

## 2. What you will see

Eight pages, reachable from the left sidebar:

| Page | What it is for |
|---|---|
| **Overview** | Mission, live record status, current-month calendar preview, guided demo |
| **Burning Calendar** | The signature feature: month heat map, year profile, multi-year matrix, month vs historical median |
| **Fire Map** | 0.25° activity grid, sensor layers, box/polygon drawing, NASA Blue Marble basemap |
| **Historical Analytics** | Yearly series, seasonal profile, Mann–Kendall trend, top months and years |
| **MODIS vs VIIRS** | Agreement metrics, paired daily chart, spatial overlap, co-detection |
| **Anomaly Explorer** | Explainable flags against the historical monthly median |
| **Data Explorer** | Filterable records, CSV export, HTML report download |
| **Methodology** | The science, the parameters, the limitations |

Click the area chip in the top bar to change region, search a place, type coordinates, or draw on
the map. Everything on every page follows that selection.

## 3. The honest status of the data

Two real records are loaded:

| Record | Span | Detections | Quality |
|---|---|---|---|
| Aegean & Anatolia (default area) | 2000-11-01 → 2026-11-14 | 349,558 in this area | science (SP) + recent NRT |
| Global rolling snapshot | 2026-11-07 → 2026-11-14 | 871,403 worldwide | provisional (NRT) |

Whole database: **1,220,961 detections** across MODIS, VIIRS S-NPP, NOAA-20 and NOAA-21.

On the **Aegean history the science is fully live**: calibration succeeds (weights ≈0.19–0.21 for
VIIRS), 25 complete years feed the August median, the same 25 years enter the trend test, and the anomaly
detector independently ranks the 2007, 2021 and 2023 Greek fire seasons as the extremes.

On the **8-day global snapshot alone** the app refuses to calibrate and reports no medians or trends,
because a median needs three complete years and calibration needs 60 co-observed days. If you select a
far-away area that only exists in the 8-day snapshot, you will see those honest empty states — not a
fabricated baseline.

If the history ever goes missing, load it with one command:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_downloaded.py
```

## 4. Unlock the full history (recommended before the demo)

1. Get a free NASA FIRMS key in about a minute:
   <https://firms.modaps.eosdis.nasa.gov/api/map_key/> — enter your e-mail, the key arrives immediately.
2. Put it in a file named `.env` next to `run.ps1`:
   ```
   FIRMS_MAP_KEY=paste_your_key_here
   ```
3. Run the backfill for one region (start with a few years to see it work, then go back further):
   ```powershell
   .\.venv\Scripts\python.exe scripts\fetch_firms_api.py --region sahel_belt --start 2018-01-01
   ```
4. Restart `.\run.ps1`. The calendar now has real history, the median becomes available, and the
   calibration switches from *insufficient_overlap* to *calibrated*.

The backfill downloads 5-day windows, so a full 25-year pull is a long job. It is resumable: files
already on disk are skipped if you stop it.

## 5. Check that it works

```powershell
python run_tests.py -v
```

Expect: `Ran 85 tests` / `All tests passed.`

## 6. Where things live

```
FIRETRACK/
  run.ps1                    start everything (Windows)
  run.sh                     start everything (macOS / Linux)
  run_tests.py               test suite
  requirements.txt           two packages: fastapi, uvicorn
  .env.example               copy to .env for your FIRMS key
  backend/app/
    firms.py                 reading and validating FIRMS records
    ingest.py                database ingestion, dedupe, grid rebuild
    harmonize.py             the harmonisation engine
    analytics.py             calendar, medians, trends, anomalies
    agreement.py             MODIS vs VIIRS comparison
    report.py                HTML report
    api.py                   HTTP API
  backend/tests/             the 85 tests
  frontend/src/              React interface (edit here)
  frontend/dist/             built interface (served by the app)
  data/raw/snapshot/         the downloaded NASA files
  data/firetrack.db          the database (rebuilt automatically)
  docs/                      methodology, architecture, demo script, validation
  README.md                  the full project description
```

## 7. Changing the interface

Node.js is only needed for this. From the `frontend` folder:

```powershell
pnpm install
pnpm build          # rebuilds frontend/dist, which the server serves
```

For live editing, `pnpm dev` runs a development server on port 5173 that proxies `/api` to port 8000 —
run `.\run.ps1` in a second terminal at the same time.

## 8. What is finished and what is not

**Working and tested**

- Real NASA FIRMS ingestion, validation, de-duplication and provenance.
- Harmonisation: common grid, coverage normalisation, overlap calibration with gating.
- Burning calendar (month, year, multi-year, compare) and historical monthly median with coverage rules.
- Historical analytics, Mann–Kendall/Theil–Sen, anomaly detection.
- MODIS vs VIIRS agreement and co-detection.
- Map, area selection (preset, search, coordinates, drawn box, drawn polygon, saved areas).
- Data explorer, detections CSV, daily analytics CSV, self-contained HTML report.
- 82 passing tests; 18 API endpoints exercised against real data.

**Not finished or not verified**

- **The interface has not been visually inspected in a browser** from this build environment (headless
  browsers cannot start here). Please open it once and walk the eight pages before presenting.
- The long historical record is not included, for the reasons in section 3 — the import path is ready.
- No independent ground-truth validation, so no accuracy figure is claimed anywhere.
- Region-to-region comparison is described in the roadmap but not implemented.

## 9. If something goes wrong

| Symptom | Fix |
|---|---|
| `run.ps1 ... is not digitally signed` | Use `.\run.cmd` (plain batch file, no policy needed) |
| `No module named 'app'` | You ran `-m app.main` directly; use `python run.py` instead — it sets the path itself |
| `python` not found | Install Python 3.10+ and tick "Add python.exe to PATH" |
| Port 8000 already in use | `python run.py --port 8010` |
| "No hotspot records are loaded" | Run `python scripts\download_firms_snapshot.py`, then restart |
| Interface shows only text | Run `pnpm build` inside `frontend/` |
| Map is blank | The basemap needs internet; the activity layer still renders |
| First start seems stuck | It is ingesting 871k rows — give it two minutes |
