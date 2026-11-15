/** Methodology: the scientific reasoning, written for both judges and scientists. */

import React from "react";
import { api } from "../api";
import { Badge, InfoNote, KVRows, Loading, Panel } from "../components/ui";
import { formatNumber } from "../format";
import { useApp, useAsync } from "../state";

export function MethodologyPage() {
  const { query, catalog } = useApp();
  const harmonization = useAsync(() => api.harmonization(query), [query]);
  const calibration = harmonization.data?.calibration;

  return (
    <>
      <div className="page-head">
        <div className="eyebrow">Reference</div>
        <h1 className="page-title">Methodology</h1>
        <p className="page-sub">
          What FIRETRACK measures, how MODIS and VIIRS are made comparable, and exactly what the
          numbers can and cannot support.
        </p>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1.7fr) minmax(0, 1fr)" }}>
        <div className="col">
          <Panel title="1 · The problem">
            <div className="prose">
              <p>
                NASA's <strong>MODIS</strong> instruments have observed thermal anomalies since November
                2000 at 1 km resolution. The <strong>VIIRS</strong> instruments add 375 m observations
                from 2012 onwards. Together they span a quarter of a century — but they are not the same
                instrument, and treating them as one series produces artefacts that look like science.
              </p>
              <p>Three effects break a naive combined record:</p>
              <ul>
                <li>
                  <strong>Sensor transition.</strong> When a new platform comes online, the total number
                  of detections jumps, even if nothing changed on the ground.
                </li>
                <li>
                  <strong>Sensitivity and resolution.</strong> VIIRS detects far more hotspots than
                  MODIS in the same landscape — often 5–10× in productive fire regions.
                </li>
                <li>
                  <strong>Coverage.</strong> A day observed by four instruments and a day observed by
                  one are not comparable, and a day with no observation is not a zero.
                </li>
              </ul>
              <p>
                FIRETRACK addresses each of these explicitly, and keeps the raw counts visible so the
                correction can always be inspected rather than trusted on faith.
              </p>
            </div>
          </Panel>

          <Panel className="mt-14" title="2 · Data sources">
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Sensor</th>
                    <th>Product</th>
                    <th className="num">Pixel</th>
                    <th>Record begins</th>
                    <th>Streams used</th>
                  </tr>
                </thead>
                <tbody>
                  <tr><td>MODIS Terra + Aqua</td><td>Collection 6.1 active fire</td><td className="num">1 km</td><td>2000-11</td><td>NRT / SP / archive</td></tr>
                  <tr><td>VIIRS Suomi-NPP</td><td>Collection 2 375 m</td><td className="num">375 m</td><td>2012-01</td><td>NRT / SP / archive</td></tr>
                  <tr><td>VIIRS NOAA-20</td><td>Collection 2 375 m</td><td className="num">375 m</td><td>2018-04</td><td>NRT / SP / archive</td></tr>
                  <tr><td>VIIRS NOAA-21</td><td>Collection 2 375 m</td><td className="num">375 m</td><td>2023-01</td><td>NRT / SP / archive</td></tr>
                </tbody>
              </table>
            </div>
            <div className="note mt-8">
              Source: NASA FIRMS (Fire Information for Resource Management System, EOSDIS / LANCE).
              Near-real-time records are provisional and are superseded by standard processing with
              roughly a five month lag. Each ingest batch records which stream it came from, and the
              processing level is shown on every record.
            </div>
          </Panel>

          <Panel className="mt-14" title="3 · Harmonisation, step by step">
            <div className="prose">
              <h3>A. Common spatial unit</h3>
              <p>
                Both instruments are aggregated onto the same <strong>{catalog?.grid_deg ?? 0.25}°
                grid</strong>. A cell is assigned to an area when its centre falls inside the area.
                This makes "one detection" mean the same spatial thing for both sensors before any
                statistic is computed, and it removes the temptation to compare a 1 km pixel with a
                375 m pixel.
              </p>

              <h3>B. Coverage normalisation</h3>
              <p>
                Every date carries the set of sensors that actually delivered data. Daily activity is
                rescaled so that a MODIS-only day in 2005 is on the same scale as a four-sensor day in
                2025:
              </p>
              <p>
                <code>H(t) = Σ wₛ·dₛ(t) × (Σ_all wₛ·ρₛ) / (Σ_observed wₛ·ρₛ)</code>
              </p>
              <p>
                where <code>dₛ(t)</code> is the sensor's detection count, <code>ρₛ</code> its mean daily
                rate in this area, and <code>wₛ</code> its calibration weight. A date with no observing
                sensor produces <strong>no value</strong>, never a zero.
              </p>

              <h3>C. Overlap-period ratio calibration</h3>
              <p>
                Where MODIS and a VIIRS platform observed the same area on the same dates, the ratio of
                their mean daily detection rates becomes that platform's weight
                (<code>w = 1</code> for MODIS). The calibration is only applied when the overlap has at
                least <strong>60 co-observed days</strong> and the ratio is stable across four
                sub-periods (coefficient of variation ≤ 0.35). Otherwise the weights stay at 1 and the
                interface labels the output as <em>coverage-normalised counts</em>, not a calibrated
                index.
              </p>

              <h3>D. Why a single multiplicative weight</h3>
              <p>
                The calibration corrects a proportional bias, which is the dominant and most stable
                effect. It cannot correct a resolution-driven non-linearity: VIIRS resolves fires that
                MODIS misses entirely, so the relationship is not perfectly linear. That is stated
                wherever the weight is used, and raw counts are always available beside the harmonised
                value.
              </p>

              <h3>E. Confidence handling</h3>
              <p>
                MODIS publishes a 0–100 confidence; VIIRS publishes a category (low / nominal / high).
                FIRETRACK stores both the original value and an ordinal mapping (25 / 65 / 90) and
                states clearly that the mapped number is <strong>not a probability</strong>. Filters
                operate on the published classes, not on a fabricated continuous scale.
              </p>
            </div>
          </Panel>

          <Panel className="mt-14" title="4 · The burning activity calendar">
            <div className="prose">
              <h3>Daily cells</h3>
              <p>
                The month view colours each UTC day by harmonised activity. Coloured dots mark the
                sensors that observed it. Days with no observing sensor are rendered as
                <em> no observation</em> — visibly different from a low-activity day, and excluded from
                every average.
              </p>

              <h3>Historical monthly median</h3>
              <p>
                For a calendar month M, the baseline is the median of the coverage-corrected totals of M
                across all <strong>complete</strong> years in the record (excluding the year being
                evaluated). A month counts as complete only when at least{" "}
                <strong>80% of its days</strong> were observed. The deviation is reported in absolute
                terms always, and as a percentage only when the baseline is large enough for a
                percentage to be meaningful.
              </p>

              <h3>Robust z-score</h3>
              <p>
                <code>z = (x − median) / (1.4826 × MAD)</code>. The median and median absolute deviation
                are used instead of mean and standard deviation because a single extreme fire year would
                otherwise inflate the spread and hide every other anomaly.
              </p>
            </div>
          </Panel>

          <Panel className="mt-14" title="5 · Validation approach">
            <div className="prose">
              <p>
                Validation here means measuring <em>agreement between the two instruments</em> and
                documenting the behaviour of the harmonisation — not claiming an accuracy figure.
              </p>
              <ul>
                <li><strong>Paired daily correlation</strong> (Pearson on log counts, Spearman) over co-observed dates.</li>
                <li><strong>Magnitude ratio</strong>, the same quantity used for calibration.</li>
                <li><strong>Spatial agreement</strong>: Jaccard overlap of active cells and rank correlation of per-cell totals.</li>
                <li><strong>Co-detection</strong>: share of MODIS detections with a VIIRS detection within 1 km on the same day.</li>
                <li><strong>Transition diagnostics</strong>: step size in raw vs harmonised activity around sensor introduction dates.</li>
              </ul>
              <p>
                Baseline comparison: the uncalibrated pooled detection count is computed alongside every
                harmonised value, so the effect of the correction is always measurable rather than
                asserted.
              </p>
              <InfoNote tone="warn">
                No accuracy percentage is reported. A defensible accuracy figure would need independent
                burned-area perimeters or ground truth, which this prototype does not include. Inventing
                one would be the most damaging thing this project could do.
              </InfoNote>
            </div>
          </Panel>

          <Panel className="mt-14" title="6 · Limitations">
            <div className="prose">
              <ul>
                <li><strong>Cloud cover.</strong> FIRMS reports detections, not observation attempts. A cloudy day and a fire-free day can look identical at pixel level; the coverage model corrects for sensor availability, not for cloud.</li>
                <li><strong>Hotspot ≠ wildfire.</strong> Agricultural burning, land clearing, industrial flares, gas flaring and volcanic heat all produce detections.</li>
                <li><strong>Provisional data.</strong> NRT records are replaced by standard processing after several months; totals can shift slightly when the archive is imported.</li>
                <li><strong>Small areas.</strong> Below one grid cell the statistics are not meaningful, and few detections make percentages unstable — which is why they are suppressed.</li>
                <li><strong>Trend tests.</strong> Mann–Kendall does not correct for serial correlation, and a detected trend is about detections, not about burned area or emissions.</li>
                <li><strong>Calibration scope.</strong> Weights are estimated per area; a global weight would be wrong for a savanna and a boreal forest alike.</li>
              </ul>
            </div>
          </Panel>
        </div>

        <div className="col">
          <Panel title="Live calibration status" subtitle="For the current area selection">
            {harmonization.loading && <Loading label="Reading calibration…" />}
            {calibration && (
              <>
                <div className="row" style={{ marginBottom: 10 }}>
                  <Badge tone={calibration.calibrated ? "ok" : "warn"}>
                    {calibration.status.replace(/_/g, " ")}
                  </Badge>
                  <Badge tone="info">{calibration.unit}</Badge>
                </div>
                <KVRows
                  rows={[
                    ["Reference sensor", calibration.reference_sensor.toUpperCase()],
                    ["Overlap CV", calibration.ratio_cv ?? "—"],
                    ...Object.entries(calibration.weights).map(
                      ([sensor, weight]) => [`w · ${sensor}`, weight.toFixed(4)] as [string, string],
                    ),
                    ...Object.entries(calibration.paired_days).map(
                      ([sensor, days]) => [`paired days · ${sensor}`, days] as [string, number],
                    ),
                  ]}
                />
                {calibration.notes.length > 0 && (
                  <ul className="note mt-14" style={{ paddingLeft: 16 }}>
                    {calibration.notes.map((note) => <li key={note}>{note}</li>)}
                  </ul>
                )}
              </>
            )}
          </Panel>

          <Panel className="mt-14" title="Reproducing this">
            <div className="prose" style={{ fontSize: 12.5 }}>
              <p>Every value in the interface can be regenerated from the raw files:</p>
              <p><code>python scripts/download_firms_snapshot.py</code><br />key-free rolling snapshot</p>
              <p><code>python scripts/fetch_firms_api.py --map-key KEY --region sahel_belt --start 2000-11-01</code><br />
                full historical backfill in 5-day windows</p>
              <p><code>python -m unittest discover backend/tests</code><br />scientific test suite</p>
              <p>
                Ingest batches, file names, row counts and rejected rows are stored in the database and
                surfaced on the Data Explorer page.
              </p>
            </div>
          </Panel>

          <Panel className="mt-14" title="Parameters in force">
            <KVRows
              rows={Object.entries(catalog?.parameters ?? {}).map(
                ([key, value]) => [key.replace(/_/g, " "), String(value)] as [string, string],
              )}
            />
            <div className="note mt-8">
              These thresholds are configuration, not hidden assumptions: they are listed here, in the
              report export, and in <code>backend/app/config.py</code>.
            </div>
          </Panel>

          <Panel className="mt-14" title="AI usage disclosure">
            <div className="prose" style={{ fontSize: 12.5 }}>
              <p>
                FIRETRACK was implemented with AI assistance for code generation, refactoring and
                documentation. The scientific choices — the grid size, the calibration gate, the
                coverage rule, the use of median/MAD, and the refusal to report unvalidated accuracy —
                are documented here so they can be reviewed, contested and changed.
              </p>
              <p>
                All observations shown by the application come from NASA FIRMS. Synthetic data is used
                only in the automated tests, where it is explicitly labelled as synthetic.
              </p>
            </div>
          </Panel>

          <Panel className="mt-14" title="Records loaded">
            <KVRows
              rows={[
                ["Detections", formatNumber(catalog?.detections ?? 0)],
                ["First date", catalog?.min_date ?? "—"],
                ["Last date", catalog?.max_date ?? "—"],
                ["Ingest batches", catalog?.batches.length ?? 0],
                ["FIRMS key", catalog?.map_key_configured ? "configured" : "not set"],
              ]}
            />
          </Panel>
        </div>
      </div>

      <InfoNote tone="warn">
        <strong>FIRETRACK is a research prototype.</strong> It is not an official emergency alert
        system, and a hotspot is not a confirmed wildfire. Always defer to local authorities and
        official fire services for operational decisions.
      </InfoNote>
    </>
  );
}
