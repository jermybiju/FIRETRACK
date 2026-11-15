# FIRETRACK presentation outline

Ten slides for a five-minute pitch. Each slide has a title, three or four bullets for the screen,
and a speaker note. No number appears here that is not in the code, the configuration, the bundled
database, or printed by the test suite.

## Slide 1 — FIRETRACK: two satellite perspectives, one consistent history

- NASA's MODIS and VIIRS both detect active fire, and they disagree by design.
- FIRETRACK harmonises them into one coverage-aware daily series you can read like a calendar.
- A working prototype: real FIRMS data, one command to run, no API key required for the demo.
- Built for the NASA Space Apps "Harmonization of MODIS and VIIRS Hot Spots" challenge.

**Speaker note:** Keep this to twenty seconds. Say that the demo runs on a real but short bundle:
871,403 detections from eight days in November 2026, three sensors. Set the expectation now that the
interesting part is the method and the honesty, not a big history.

## Slide 2 — A naive hotspot count is not a time series

- A new satellite makes the total jump even when nothing changes on the ground.
- VIIRS has 375 m pixels and a lower threshold; MODIS has 1 km pixels. Counts are not interchangeable.
- The constellation changes: the catalogue holds four possible sensors, and the code normalises whatever subset is observing.
- A day with no observation is not a day with no fire, and the two must never look the same.

**Speaker note:** Use one concrete image: summing detections across 2000–2025 produces a step at
2012, 2018 and 2023 that is instrument history, not fire history. That is the artefact the project
exists to remove.

## Slide 3 — Method: make the instruments comparable first

- Aggregate both instruments onto one 0.25° common grid before any statistic is computed.
- Normalise each day for the sensors that actually observed it, so a two-sensor day is comparable to a four-sensor day.
- Calibrate the VIIRS-to-MODIS ratio only on co-observed days, and only when there are at least 60 of them with a stable ratio (CV ≤ 0.35).
- If the gate fails, keep weights at 1.0 and change the label to "coverage-normalised detections".

**Speaker note:** Show the formula from the Methodology page and say it out loud in words: "weighted
detections, rescaled by the ratio of the full sensor mix to the observed mix". Emphasise the refusal:
the code reports the ratio but will not apply it on eight days.

## Slide 4 — The burning calendar

- Each square is one UTC day, coloured by harmonised activity.
- Coloured dots show which sensors observed that day; a dark cell with a dash means no observation.
- Click a day to see raw detections, harmonised value, fire radiative power and coverage.
- Month, year, multi-year history and month-versus-median views share one selection.

**Speaker note:** Click 10 November in the live demo: 28,656 detections, all three sensors. Then
point at the line "8 of 30 days observed, coverage 27%, incomplete" and explain that the month is
excluded from the historical median on purpose.

## Slide 5 — From map to record: every number is inspectable

- The map draws the same 0.25° cells the statistics use, so what you see is what the calendar counts.
- Draw a box or polygon and the whole application follows the new area.
- The Data Explorer shows the original record: time, confidence, FRP, brightness, processing level, source file.
- Exports: every matching detection as CSV, and a self-contained HTML report with method and limitations.

**Speaker note:** The point is auditability. A judge can pick any coloured square, open the explorer,
and see the underlying NASA rows. Nothing is a black box.

## Slide 6 — How different are MODIS and VIIRS, really?

- Compare only dates both instruments observed, never the whole period.
- Report four complementary measures: magnitude ratio, rank correlation, spatial Jaccard, and a 1 km same-day co-detection test.
- In the bundled week, for the Sahel selection, the pooled VIIRS record has roughly ten times as many detections as MODIS, and about 60% of MODIS detections have a VIIRS detection within 1 km the same day.
- These are agreement indicators, not an accuracy score.

**Speaker note:** Explain why the ratio matters for calibration, and why a co-detection fraction is
not a validation: a 1 km MODIS pixel can contain several 375 m VIIRS pixels, and overpass times
differ. The page states this itself.

## Slide 7 — Statistics only where the data supports them

- Mann-Kendall plus a Theil-Sen slope, computed on complete years only; incomplete years stay visible but are excluded.
- Anomalies are robust z-scores against the same calendar month, using median and MAD, default threshold 2.5.
- A month below 80% coverage is skipped, never flagged as low activity.
- With one week of data the trend is `insufficient_data` and the anomaly list is empty — by design.

**Speaker note:** This is a strength, not a gap. Say: "The system tells you when it cannot answer.
That is what makes the answers it does give worth something."

## Slide 8 — Built to be checked

- Real NASA FIRMS ingestion verified: 871,403 rows in four recorded batches, three sensors, eight days.
- 85 automated tests cover the science, geospatial helpers, CSV parsing and the HTTP API; all pass
  (the 14 HTTP tests skip automatically if `httpx` is absent).
- Every ingest writes its files, row counts, rejections, date range and processing quality to the database.
- One command to run, one SQLite file to inspect, one process serving UI and API.

**Speaker note:** Offer the repository commands: `python run_tests.py`, `python
scripts/download_firms_snapshot.py`, and the Methodology page's "Reproducing this" panel. Mention
that synthetic data appears only in labelled tests.

## Slide 9 — What we do not claim

- No accuracy percentage. It would require independent burned-area or ground-truth perimeters, which this prototype does not include.
- The bundled snapshot is eight days, so calibration cannot be applied and long-term trends cannot be computed.
- A FIRMS hotspot is a thermal anomaly, not a confirmed wildfire; agricultural burning, flaring and volcanic heat all appear.
- Cloud cover and NRT provisional processing both limit what any single day means, and FIRETRACK is not an official alerting system.

**Speaker note:** Spend real time here. Judges trust a team that names its limits. Then give the fix:
a free MAP_KEY backfill or a FIRMS Archive Download import supplies the history the gates need.

## Slide 10 — Where this goes next

- Backfill 2000–present with the FIRMS area API or the archive, unlocking calibration, baselines and trends.
- Add independent burned-area perimeters (for example MODIS/VIIRS burned-area products) to move from agreement to validation.
- Estimate calibration per region instead of per selection, and improve cloud handling.
- Schedule monthly ingest so the record stays current without a manual step.

**Speaker note:** Close on the contribution: one consistent, inspectable history of burning activity,
with the uncertainty left visible. Invite judges to try the calendar on their own region of interest.
