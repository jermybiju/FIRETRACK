# FIRETRACK data flow

This document follows one NASA FIRMS CSV row from the moment it is downloaded to the moment it is
painted as a coloured square in the burning calendar, then explains where every derived number
comes from.

## Pipeline at a glance

```text
 NASA FIRMS global rolling CSV (7 days, no key)
            |
            v
 data/raw/snapshot/*.csv.gz ----- optional: data/raw/api/*.csv (MAP_KEY backfill)
            |                                    |
            +----------------+-------------------+
                             v
                 firms.iter_firms_file()            streaming, one row at a time
                             |
                             v
                 firms.normalize_row()              aliases, sensor, confidence, UTC, cell index
                             |
              +--------------+---------------+
              |                              |
              v                              v
      detections (raw rows)          ingest.rebuild_daily_cells()
      unique per sensor/date/                |
      time/lat/lon                          v
                                     daily_cells (derived)
                                             |
              sensor_days (availability)     |
              derived per sensor/date        |
                             |               |
                             +-------+-------+
                                     v
                     harmonize.load_series(aoi)
                     per-sensor daily counts inside the AOI
                                     |
                                     v
                     harmonize.calibrate()        weights w_s, rates rho_s, status
                                     |
                                     v
                     HarmonizedSeries._build()    H(t) for each observed day
                                     |
                                     v
                     analytics.calendar_month()   day cells, summary, median, z-score
                                     |
                                     v
                     POST /api/calendar/month -> JSON -> React MonthGrid
```

## Step by step

1. **Download.** `scripts/download_firms_snapshot.py` fetches the key-free global 48 h and 7 d files
   for MODIS, Suomi-NPP, NOAA-20 and NOAA-21 into `data/raw/snapshot/`, writing a `.meta.json`
   sidecar with URL, UTC download time, byte count and SHA-256. The script writes plain `.csv`; the
   copies bundled with this project are gzip-compressed (`.csv.gz`) to keep the repository small, and
   their metadata records the compressed name and notes that the hash is over the original downloaded
   bytes. The reader accepts both. The bundled files were downloaded on 2026-11-14.
2. **File selection.** `ingest.snapshot_files()` keeps one file per sensor and prefers the widest
   window (`_7d` over `_48h`), so the same dates are not ingested twice from two windows.
3. **Parse and normalise.** `firms.iter_firms_file()` yields one `Detection` or one `RowError` per
   CSV row. `normalize_row()` resolves column aliases (`latitude`/`lat`, `bright_ti4`/`brightness`),
   infers the sensor from `satellite` and then from the filename, maps confidence onto a 0-100
   ordinal, builds an ISO-8601 UTC timestamp and computes the grid cell index.
4. **Insert raw rows.** `ingest.ingest_detections()` batches 20,000 rows per `executemany` into
   `detections` with `INSERT OR IGNORE`. The unique index on
   `(sensor, acq_date, acq_time, lat, lon)` makes a repeated file a no-op rather than a duplicate.
5. **Rebuild the grid.** After the rows are committed, `rebuild_daily_cells()` replaces the entire
   `daily_cells` table from `detections` with one `GROUP BY`.
6. **Record availability.** Every date between a sensor's earliest and latest delivered date is
   written to `sensor_days` with `observed = 1`.
7. **Load a series.** For a chosen AOI, `harmonize.load_series()` finds the grid cells whose centres
   fall inside the AOI, queries `daily_cells` for those cells, and produces, per sensor, a map of
   date to detection count plus the set of dates that sensor observed.
8. **Calibrate and harmonise.** `calibrate()` derives the weights and rates; `HarmonizedSeries`
   computes `H(t)` for every date; `analytics` turns that into calendar cells, aggregate summaries,
   baselines, trends and anomalies. Only then does the API return JSON.

## The arithmetic

For each UTC date *t* the harmonised value is:

```text
                 Σ_observed(t) w_s · d_s(t)  ×  (Σ_all w_s · ρ_s)
      H(t)  =   ------------------------------------------------
                            Σ_observed(t) w_s · ρ_s
```

equivalently:

```text
      H(t) = ( Σ_s w_s · d_s(t) ) × ( Σ_all w_s · ρ_s ) / ( Σ_observed(t) w_s · ρ_s )
```

| Symbol | Meaning | Where it comes from |
|---|---|---|
| `s` | One sensor: `modis`, `viirs_snpp`, `viirs_noaa20`, `viirs_noaa21` | `config.SENSORS` |
| `d_s(t)` | Detections by sensor `s` in the AOI on date `t`, after the confidence filter | `daily_cells` aggregated by `load_series()` |
| `w_s` | Calibration weight converting sensor `s` into MODIS-equivalent units | `calibrate()`; `1.0` for MODIS and whenever calibration is not applied |
| `ρ_s` | Mean daily detections by sensor `s` on the dates it observed the AOI | `calibrate()`: total detections ÷ number of observed days |
| `Σ_observed(t)` | Sum over the sensors that actually observed on date `t` | `sensor_days` filtered to the requested period |
| `Σ_all` | Sum over every sensor present in the loaded record | `series.sensors` |

The factor `Σ_all w_s · ρ_s` is constant for a series; `HarmonizedSeries` stores it as
`full_mix_expected`. The factor `Σ_observed(t) w_s · ρ_s` changes with the observing set, and it is
what rescales a two-sensor day onto the same footing as a four-sensor day. When no sensor observed,
`H(t)` is `None` — never zero.

### Worked example from the bundled data

For the Sahel preset (bbox 21, 7, 33, 14), the eight-day record gives mean daily rates of
1,263.0 MODIS, 6,793.12 NOAA-20 and 6,361.38 NOAA-21 detections, so
`full_mix_expected = 14,417.5`.

On 2026-11-10 the three sensors recorded 1,969 MODIS, 15,558 NOAA-20 and 11,129 NOAA-21
detections: 28,656 in total. All three observed that day and every weight is 1.0, so both
the numerator and the denominator of the correction factor equal 14,417.5:

```text
      H = 28,656 × (14,417.5 / 14,417.5) = 28,656
```

This is the identity case, and it is the correct result for this bundle: every sensor reported on
all eight days, so the coverage factor is 1.0 for every date and `H(t)` equals the raw count. The
correction becomes visible only when the observing set changes — which needs a longer record than
eight days. The code path is exercised, but the demo cannot show a large correction.

### Period totals

`aggregate_period()` separates the observed total from a coverage-corrected estimate. It computes:

```text
      mean_daily    = mean of H(t) over observed days
      expected_total = mean_daily × days_in_period
      coverage       = observed_days / days_in_period
      complete       = coverage >= 0.80
```

November 2026 in the Sahel bundle has 8 observed days out of 30, so coverage is 0.267 and the month
is incomplete. `mean_daily` is 14,417.5, which makes `expected_total` 432,525 — the "433k" figure on
the overview. That number is an extrapolation from eight days to a 30-day month. The calendar view
shows the same estimate next to a separate coverage statistic and an "incomplete" label, and the month
grid states the coverage in words. It is never presented as an observed monthly total.

## Where the weights come from

`calibrate()` works on the AOI series, not on a global constant, so weights are area-specific.

1. For each sensor, compute `ρ_s` over the dates that sensor observed the AOI.
2. If MODIS is absent, or no VIIRS platform is present, return status `single_sensor` with weights
   of 1.0 and a note explaining why.
3. For each VIIRS platform, take the dates where MODIS and that platform both observed. The ratio
   `modis_mean / viirs_mean` on those dates becomes the candidate weight. MODIS is the reference
   and always keeps `w = 1`.
4. If the overlap has at least 16 dates, split it into four consecutive blocks and compute the same
   ratio in each block. The coefficient of variation of those block ratios is the stability check.
5. Apply the weight only when the overlap has at least 60 co-observed dates. A shorter overlap is
   reported but not applied.
6. If the CV exceeds 0.35, the calibration is rejected: status `unstable_ratio`, all weights reset
   to 1.0.
7. If no weight was applied, the status is `insufficient_overlap` and the unit becomes
   "coverage-normalised detections". Otherwise the status is `ok` and the unit is
   "MODIS-equivalent detections".

On the bundled record every platform has 8 co-observed days, well below 60. The ratios are computed
and reported (0.186 for NOAA-20, 0.199 for NOAA-21 in the Sahel selection) but not applied, so all
weights are 1.0 and the status is `insufficient_overlap`. With fewer than 16 overlap dates there are
no stability blocks, so `ratio_cv` is `null`. This is the honest state of a one-week record; the
overview, the map, the calendar's unit labels, the comparison page and the methodology page all
carry it.

## How `daily_cells` is rebuilt

`ingest.rebuild_daily_cells()` is called at the end of every ingest, including a partial one:

```sql
DELETE FROM daily_cells;

INSERT INTO daily_cells
    (cell_ix, cell_iy, acq_date, sensor, n, frp_sum, n_high, n_nominal, n_low)
SELECT cell_ix, cell_iy, acq_date, sensor, COUNT(*), SUM(COALESCE(frp, 0)),
       SUM(CASE WHEN confidence_class = 'high'    THEN 1 ELSE 0 END),
       SUM(CASE WHEN confidence_class = 'nominal' THEN 1 ELSE 0 END),
       SUM(CASE WHEN confidence_class = 'low'     THEN 1 ELSE 0 END)
FROM detections
GROUP BY cell_ix, cell_iy, acq_date, sensor;
```

The confidence columns let the API apply the `all` / `nominal` / `high` filter without touching raw
rows: `all` sums all three, `nominal` sums high and nominal, `high` uses high only. Rebuilding from
raw rows means deduplication, batch deletion and a changed confidence rule all produce a consistent
aggregate with no migration.

## How availability is derived

`daily_cells` answers "how many detections", not "was the sensor looking". `sensor_days` answers the
second question.

- During ingest, each parsed row contributes its `acq_date` to a per-sensor list. The earliest and
  latest dates in that list define a span, and every date in the span is marked `observed = 1`.
  The reasoning is that a FIRMS global product is a complete daily product: if it delivered on the
  first and last day of a file, it delivered on the days between.
- During an API backfill, `ingest.register_observation_days()` additionally marks every date that
  was queried, even when the response contained no detections. A successful empty answer means "no
  hotspot detected", not "no data".
- Dates outside any sensor's span have no row and are treated as unknown. They are never counted as
  zeros.

Two consequences are worth stating plainly. First, availability is **global for the ingested
product**, not local to the AOI: a sensor that delivered data somewhere on Earth counts as observing
for every AOI on that date. This is deliberate, because a global FIRMS file either arrives or does
not. Second, `sensor_days.n_global` exists in the schema but is not populated in this version; only
the `observed` flag and the primary key are used.

## Raw versus derived data

| Data | Location | Kind | Rebuildable |
|---|---|---|---|
| FIRMS CSV files | `data/raw/snapshot/`, `data/raw/api/` | Raw, as downloaded (the bundled 7 d files are stored gzip-compressed) | No — re-download |
| `detections` rows | SQLite | Raw, normalised but not aggregated | No — only by re-ingest |
| `daily_cells` rows | SQLite | Derived | Yes — from `detections` |
| `sensor_days` rows | SQLite | Derived availability | Yes — from the ingested date spans |
| `ingest_batches` rows | SQLite | Provenance, written once per ingest | No |
| `meta` keys | SQLite | Bookkeeping (`schema_version`, `last_ingest_at`) | Yes |
| Exports | Browser downloads (streamed by the API) | Derived artefacts | Yes |

The demo database in this workspace holds 871,403 detections in 8 UTC days (2026-11-07 to
2026-11-14), 160,739 `daily_cells` rows and 4 ingest batches. Three sensors are present: MODIS with
76,114 detections, VIIRS NOAA-20 with 399,872 and VIIRS NOAA-21 with 395,417. The Suomi-NPP global
file was header-only when the snapshot was downloaded, so that platform contributes nothing to this
build; the loader handles all four products.

## The three data entry paths

### 1. Bundled key-free snapshot (what the demo uses)

```powershell
python scripts/download_firms_snapshot.py
python -m app.main --port 8000     # first start ingests automatically
```

No key, no login. Coverage is limited to the rolling windows NASA publishes: roughly the last
8 days for the 7 d files. `ingest.snapshot_files()` picks one file per sensor, `ingest_batches`
records `kind = snapshot` and `quality = provisional`, and the first-run bootstrap in `main.py`
loads everything if `detections` is empty. To force a re-ingest of the same files, call
`POST /api/ingest/snapshot?force=true` (this clears the in-process series cache) or delete
`data/firetrack.db` and restart.

### 2. MAP_KEY area-API backfill (long history)

```powershell
python scripts/fetch_firms_api.py --map-key YOURKEY --region sahel_belt --start 2000-11-01
```

A free key is issued instantly at `https://firms.modaps.eosdis.nasa.gov/api/map_key/`. The script:

- resolves a preset region or a bbox, then plans contiguous 5-day windows (the API maximum);
- chooses standard processing (SP) for windows older than 150 days and near-real-time (NRT) for
  recent ones, or forces one mode with `--mode`;
- writes one CSV per window into `data/raw/api/`, skipping files that already exist, so the job can
  be stopped and resumed;
- ingests all files as a single batch after download, then registers every queried date as observed;
- records the batch as `api_sp` or `api_nrt`, with `quality = science` for SP and `provisional` for
  NRT.

This path, or an Archive Download import, is what can satisfy the 60-day calibration gate and the
80% coverage gate; the bundled rolling snapshot cannot, because it never holds enough history.

### 3. FIRMS Archive Download import (manual, science quality)

The FIRMS Archive Download page (<https://firms.modaps.eosdis.nasa.gov/download/>) produces a ZIP or
CSV per request after an Earthdata login. Those files are ordinary FIRMS CSVs and are read by the same
parser, so they arrive with `processing = SP` and `quality = science`.

There are two ways in, both using `ingest.ingest_paths(files, kind="archive")`:

**In the browser.** The Data Explorer page has an *Import a NASA FIRMS archive file* panel. Choose a
`.csv`, `.csv.gz` or `.zip`; the browser POSTs the raw bytes to
`/api/ingest/archive?name=<filename>`. The endpoint validates the extension, enforces a 500 MB limit,
stores the file under `data/raw/archive/`, expands a ZIP (member names are flattened and only CSV/GZ/TXT
members are read), then ingests it. The response reports rows kept, duplicates skipped, rejected rows,
date bounds, sensors and the new record total, and the page offers a reload so every view picks up the
longer record.

**From the command line.**

```powershell
python -c "import sys; sys.path.insert(0, 'backend'); from app import ingest; print(ingest.ingest_paths(['C:/path/to/firms_archive.csv'], kind='archive', description='Archive download').to_dict())"
```

The optional `bbox` argument clips rows to a box, `kind` is stored on the batch, and the same
`rebuild_daily_cells()` and availability steps run afterwards. Duplicate rows already present from an
earlier snapshot import are skipped by the unique index, so importing an overlapping archive is safe.

## What the bundled record can and cannot support

| Feature | With 8 days | Why |
|---|---|---|
| Daily calendar cells | Yes | Every day has observed sensors |
| Map of activity | Yes | Raw and harmonised cells are available |
| MODIS vs VIIRS comparison | Yes, on 8 co-observed days | Agreement metrics need only paired dates |
| Coverage-normalised series | Yes | Weights are 1.0 by design |
| Calibrated MODIS-equivalent index | No | Needs at least 60 co-observed days |
| Historical monthly median | No | Needs complete years of that month; three are required before the baseline is treated as sufficient, and there are none here |
| Mann-Kendall / Theil-Sen trend | No | Needs at least 4 complete years; the API returns `insufficient_data` |
| Anomaly flags | No | Every month is incomplete, so nothing is checked |

These are not bugs to work around in the demo. They are the correct behaviour of gates that prevent
a one-week sample from being presented as a climate record.

## Time, space and identity rules

- `acq_date` is the UTC calendar date; `acq_time` is UTC `HHMM`; `acq_ts` is ISO-8601 UTC with
  seconds. Days are UTC days, so an event near local midnight can fall on the neighbouring date.
- A grid cell is `cell_ix = floor((lat + 90) / 0.25)`, `cell_iy = floor((lon + 180) / 0.25)`. Its
  centre is `(cell_ix + 0.5) × 0.25 − 90` latitude and `(cell_iy + 0.5) × 0.25 − 180` longitude.
- An AOI owns a cell when the cell centre is inside the bbox or polygon; a detection belongs to an
  AOI when its cell centre is inside, or, for raw listings and exports, when the point itself passes
  the polygon test.
- Cell area is computed from the cell's central latitude (`111.195 km` per degree, longitude scaled
  by `cos(lat)`), and only cells that contain detections contribute to the reported AOI area.
- Identity of a detection is `(sensor, acq_date, acq_time, lat, lon)`. Two records that differ only
  in brightness or FRP are treated as the same detection.
