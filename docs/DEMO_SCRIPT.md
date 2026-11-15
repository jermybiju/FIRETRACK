# FIRETRACK demo script

A five-minute demo for judges who are intelligent but not remote-sensing specialists, plus a
90-second version and instructions for capturing screenshots yourself. Every number quoted below was
read from the bundled database, the configuration, or computed with the shipped code; none is a
guess.

## Before you present

```powershell
cd FIRETRACK
.\run.ps1 -OpenBrowser
```

Wait until the browser shows the interface, then check the sidebar footer: it should read
"871,403 detections loaded" and "7 Nov 2026 → 14 Nov 2026". Check the API too:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health | ConvertTo-Json
```

The response should contain `"ready": true`. If it does not, go to Troubleshooting before the demo,
not during it.

Browser setup: 100% zoom (`Ctrl+0`), bookmarks bar hidden (`Ctrl+Shift+B`), one window at about
1600 × 1000. Set the area to the default "Sahel & Sudan fire belt" and the range to "full record" by
clicking the area chip in the top bar, choosing the Sahel preset, then using "Full record" on the
map page or the reset button at the bottom of the overview.

## The five-minute demo

| Time | Do this | Point at | Say |
|---|---|---|---|
| 0:00 | Open `http://127.0.0.1:8000/#/overview` | The page title, then the four statistics | "MODIS and VIIRS count fires differently. FIRETRACK turns both into one comparable daily series. This build holds 871,403 real NASA detections from eight days, late 2026, seen by three sensors." |
| 0:20 | Point at the "SNAPSHOT DATA" badge, then at "3" in Sensors observing | Badge, sensor labels | "No API key: this is NASA's free rolling snapshot. Three sensors are in this window — MODIS, NOAA-20 and NOAA-21 — and the interface says so instead of pretending the constellation is constant." |
| 0:35 | Click "Open the burning calendar →" | The month grid | "This is the signature view. Each square is one UTC day, coloured by activity. The dark squares showing a dash are days with no observation — not quiet days — and they are excluded from every average." |
| 0:50 | Point at the line "8 of 30 days observed · coverage 27% · incomplete" | That line | "Eight days of thirty. So the month is marked incomplete and kept out of the historical median. We would rather show a gap than a fake trend." |
| 1:00 | Click the square for 10 November | Day inspector on the right | "That day: 1,969 MODIS, 15,558 NOAA-20 and 11,129 NOAA-21 detections, 28,656 raw and 28,656 harmonised. The two agree here because all three sensors observed and calibration is not yet applied — I will show why." |
| 1:15 | Click "Month", "Year", "History", "Compare" in turn | The panel below | "Four views share one selection: a month, a year profile, a multi-year matrix, and a month-versus-median comparison. Empty states are explicit, never zero-filled." |
| 1:30 | Click "Fire Map" in the sidebar | Circles and legend | "Every cell on the same 0.25-degree grid the statistics use. Circle size and colour are detection counts; the panel on the right explains how not to misread it." |
| 1:45 | Click "Full record", then "Draw box" and drag a box over Sudan | The stat cards and "Sensor split" | "Draw any area and everything follows: calendar, map, statistics. Here you can see VIIRS dominates the count, which is the problem the next page quantifies." |
| 2:05 | Click the area chip, re-select "Sahel & Sudan fire belt", then click "MODIS vs VIIRS" | The four top statistics and paired chart | "Back to the whole fire belt for the sensor comparison. On the eight days both observed: about ten times more VIIRS detections than MODIS. The page shows the ratio, rank correlation, spatial overlap and a one-kilometre co-detection test — agreement, not accuracy." |
| 2:25 | Scroll to "Spatial agreement" and "Co-detection test" | Jaccard and the 1 km paragraph | "These are the evidence behind the calibration: the instruments see overlapping but not identical places. The note says a MODIS pixel can contain several VIIRS detections, so this cannot be a validation score." |
| 2:45 | Click "Methodology" in the sidebar, scroll to "Live calibration status" | The badge "insufficient overlap" and paired days | "This is the honest part. Calibration needs 60 co-observed days and a stable ratio; we have eight. So weights are 1.0 and the unit is coverage-normalised detections, not a calibrated index. The code reports the raw ratio but refuses to apply it." |
| 3:10 | Scroll to "3 · Harmonisation" and "6 · Limitations" | The formula and the limitation list | "Common grid, coverage normalisation, gated ratio calibration. The limitations are written down: cloud, hotspots that are not wildfires, NRT being provisional, small areas, no serial-correlation correction." |
| 3:30 | Click "Historical Analytics" | The warning note and coverage table | "The trend test needs four complete years; every year here is partial, so no trend is claimed. The table shows exactly why each year was excluded." |
| 3:45 | Click "Anomaly Explorer" | "0 months checked, 12 skipped" | "Same discipline. Anomalies are robust z-scores against the same calendar month; with no complete month there is nothing to compare, and the page says so instead of inventing flags." |
| 4:00 | Click "Data Explorer" | The record table, then Provenance | "Every record as NASA delivered it: coordinates, time, confidence, FRP, brightness, processing level, source file. Filters apply to the table and the export." |
| 4:15 | Click "Download detections CSV", then "Download report" | The two downloaded files | "The CSV is every matching record, not the visible page. The report is one self-contained HTML file with the area, period, sources, comparisons, method and limitations — printable to PDF." |
| 4:35 | Return to the overview | The lede | "Two satellite perspectives, one consistent history. The consistency is the contribution; the honesty about what the data cannot support is the rest of it." |

Do not say "accurate", "validated", "precision" or any percentage that is not on screen. If asked for
accuracy, answer: "We deliberately do not report one. It would need independent burned-area
perimeters, which this prototype does not have." That answer is on the Methodology page.

## The ninety-second version

| Time | Do this | Say |
|---|---|---|
| 0:00 | Overview | "NASA's MODIS and VIIRS see fire differently, so a naive sum of hotspots jumps whenever a sensor joins. FIRETRACK harmonises them on one 0.25-degree grid with coverage-aware scaling." |
| 0:15 | Calendar, click 10 November | "A burning calendar. Eight observed days this month, twenty-two without observation, shown as gaps — never as zeros. That day: 28,656 detections, all three sensors observing." |
| 0:35 | Compare page | "The comparison page is the evidence: about ten times more VIIRS detections than MODIS on the shared days, with spatial overlap and a one-kilometre co-detection test. Agreement, not accuracy." |
| 0:55 | Methodology, live calibration | "The calibration gate is 60 days and a stable ratio; we have eight, so it refuses to calibrate and labels the output coverage-normalised counts. The code enforces that, and the interface repeats the label." |
| 1:15 | Analytics or Anomalies | "Trends and anomalies only run on complete years and complete months. With one week of data, they return nothing rather than something misleading." |
| 1:25 | Overview | "One command runs it, one SQLite file holds it, and every ingest leaves a provenance receipt. That is the deliverable." |

## Capturing the screenshots yourself

Automated capture was not possible in the build environment: headless browsers could not open the
IPC channel, so no capture step could drive the page. The steps below use an ordinary interactive
browser and take about five minutes.

Preparation:

1. Start the server with `.\run.ps1 -OpenBrowser` and wait for the overview to finish loading.
2. Use Chrome or Edge. Set the window to roughly 1600 × 1000, zoom to 100% (`Ctrl+0`), hide the
   bookmarks bar (`Ctrl+Shift+B`).
3. Wait until no spinner is visible and the charts have drawn before each capture.

Open all eight routes in order (optional helper):

```powershell
$routes = "overview","calendar","map","analytics","compare","anomalies","explorer","methodology"
foreach ($r in $routes) { Start-Process "http://127.0.0.1:8000/#/$r"; Start-Sleep -Seconds 2 }
```

Capture each tab with either method:

- **Windows Snipping Tool:** press `Win+Shift+S`, drag a rectangle around the browser content, then
  paste into Paint or save from the snipping notification as PNG.
- **Chrome or Edge DevTools:** press `F12`, then `Ctrl+Shift+P`, type `screenshot`, and run
  "Capture screenshot" (viewport) or "Capture full size screenshot" (whole page). The file lands in
  the Downloads folder.

Save the set into `docs/screenshots/` (create the folder if it does not exist) with these names, and
check each image against the live page before submitting — do not ship a stale capture.

| File | URL | What must be visible |
|---|---|---|
| `01-overview.png` | `http://127.0.0.1:8000/#/overview` | Hero, four statistics, month grid, "SNAPSHOT DATA" badge |
| `02-calendar.png` | `http://127.0.0.1:8000/#/calendar` | Month grid, day inspector with a selected day, historical median panel |
| `03-map.png` | `http://127.0.0.1:8000/#/map` | Activity circles, legend, sensor split, top-cells table |
| `04-analytics.png` | `http://127.0.0.1:8000/#/analytics` | "Not enough complete years" note, coverage table, empty top-months panel |
| `05-compare.png` | `http://127.0.0.1:8000/#/compare` | Co-observed days, ratio statistic, paired daily chart, spatial agreement |
| `06-anomalies.png` | `http://127.0.0.1:8000/#/anomalies` | "No anomalies at this threshold", months checked and skipped counts |
| `07-explorer.png` | `http://127.0.0.1:8000/#/explorer` | Record table, filters, export buttons, provenance panel |
| `08-methodology.png` | `http://127.0.0.1:8000/#/methodology` | "Live calibration status" with insufficient overlap, limitations list |

For a cleaner capture of `04` and `06`, leave the empty states in frame. They are the honest part of
the story.

## Troubleshooting

### The sidebar says "Server unreachable"

The browser is open but the API is not answering.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

- Start it: `.\run.ps1 -OpenBrowser` from the `FIRETRACK` folder.
- If the port is busy, use another: `.\run.ps1 -Port 8010`, then open
  `http://127.0.0.1:8010`.
- "Python 3.10+ was not found": install Python and tick "Add python.exe to PATH".
- A page saying "The web interface has not been built yet" means the API is running but
  `frontend/dist` is missing. Run `cd frontend; pnpm install; pnpm build`.

### "No data loaded" or an HTTP 409

The database is empty, so there is nothing to analyse.

```powershell
Get-ChildItem data\raw\snapshot
python scripts/download_firms_snapshot.py
```

- The snapshot folder must contain a global file per sensor, either plain `.csv` or `.csv.gz`. The
  7 d file is preferred over the 48 h file when both are present.
- Restart the server; first-run bootstrap ingests automatically when `detections` is empty.
- To force a rebuild of the derived tables from the bundled files:
  `Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/ingest/snapshot?force=true"`.
- As a last resort, stop the server, delete `data\firetrack.db`, and restart. It is rebuilt from
  the CSVs on the next start.
- Note that `--no-ingest` deliberately skips the first-run load.

### The map is grey, or tiles are missing

The activity circles are drawn from `/api/map/cells` and do not need the internet. The basemap does:
Leaflet requests CARTO tiles for "Dark" and NASA GIBS Blue Marble tiles for the second option.

- Without a connection the circles still render, at the correct coordinates, on a blank background.
- Say so: "The basemap is a cosmetic reference layer; the data is drawn on top of it."
- If the demo location has internet, load the map once before presenting so tiles are cached.
- Switch the basemap control in the map's top-right corner between "Dark" and "NASA Blue Marble".
- Never present a tile-less map as "no fires" — it is a network condition, not a data condition.

### The Methodology page says "insufficient overlap"

This is the correct result for the bundled data, not an error.

- The calibration needs at least **60 co-observed days** and a ratio CV of **0.35 or less**. The
  bundle has **8** co-observed days.
- The code computes the ratios, reports them, and sets every weight to 1.0. The unit becomes
  "coverage-normalised detections" instead of "MODIS-equivalent detections".
- Explain it in one sentence: "We refuse to calibrate on eight days. The correction machinery is
  built and tested, but this dataset cannot unlock it."
- To unlock it, a free `FIRMS_MAP_KEY` and `scripts/fetch_firms_api.py --region sahel_belt --start
  2000-11-01`, or an Archive Download import, is required. That is stated on the Methodology page.
- Do not describe the series as calibrated, and do not call the weights a validation.

### A chart is empty

Check the date range in the top bar. Most panels are computed for the selected area and period; a
narrow range, a small drawn box, or a month outside 2026-11-07 to 2026-11-14 will legitimately
produce "no observations". Widen the range or reset the area before assuming a bug.

### The database has a fourth batch with zero rows

The Suomi-NPP global file was header-only when the snapshot was downloaded, so it contributes no
detections. The batch is recorded honestly with zero rows. The application works with the three
sensors that delivered data.
