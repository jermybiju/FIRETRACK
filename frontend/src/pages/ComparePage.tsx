/** MODIS vs VIIRS: agreement metrics, paired series and spatial overlap. */

import React from "react";
import { api } from "../api";
import { LineChart } from "../components/charts";
import { Badge, EmptyBox, ErrorBox, InfoNote, KVRows, Loading, Panel, Stat } from "../components/ui";
import { formatNumber } from "../format";
import { useApp, useAsync } from "../state";

export function ComparePage() {
  const { query } = useApp();
  const compare = useAsync(() => api.compare(query), [query]);

  if (compare.loading) return <Loading label="Comparing MODIS and VIIRS…" />;
  if (compare.error) return <ErrorBox message={compare.error} onRetry={compare.reload} />;
  if (!compare.data) return null;

  const data = compare.data;

  if (!data.available) {
    return (
      <>
        <div className="page-head">
          <div className="eyebrow">Sensor agreement</div>
          <h1 className="page-title">MODIS vs VIIRS</h1>
        </div>
        <EmptyBox title="Comparison not possible for this selection">{data.reason}</EmptyBox>
      </>
    );
  }

  const daily = data.daily!;
  const spatial = data.spatial!;
  const co = data.co_detection;
  const series = data.daily_series ?? [];

  return (
    <>
      <div className="page-head">
        <div className="eyebrow">Sensor agreement</div>
        <h1 className="page-title">MODIS vs VIIRS</h1>
        <p className="page-sub">
          The overlapping record, measured on co-observed dates only. These numbers are the empirical
          basis for the harmonisation weights — and the reason a raw hotspot sum is not comparable
          across instruments.
        </p>
      </div>

      <div className="grid grid-4">
        <Stat
          label="Co-observed days"
          value={formatNumber(data.paired_days)}
          note={`${data.period?.start} → ${data.period?.end}`}
        />
        <Stat
          label="VIIRS / MODIS detection ratio"
          value={daily.ratio_modis_over_viirs === null ? "—" : (1 / daily.ratio_modis_over_viirs).toFixed(1)}
          unit="×"
          note="VIIRS detects more hotspots per day"
        />
        <Stat
          label="Daily rank correlation"
          value={daily.spearman === null ? "—" : daily.spearman.toFixed(3)}
          note="Spearman on paired daily counts"
        />
        <Stat
          label="Co-detection within 1 km"
          value={co?.fraction != null ? `${Math.round(co.fraction * 100)}%` : "—"}
          note={co?.available ? `${formatNumber(co.matched)} of ${formatNumber(co.sampled)} MODIS detections` : "not available"}
        />
      </div>

      <Panel
        className="mt-14"
        title="Paired daily detections"
        subtitle={`MODIS vs pooled VIIRS, ${data.daily_bucket === "month" ? "monthly means" : "daily counts"}, co-observed dates only`}
      >
        <LineChart
          series={[
            {
              id: "viirs",
              label: "VIIRS (pooled)",
              color: "var(--violet)",
              points: series.map((row, index) => ({ x: index, y: row.viirs })),
            },
            {
              id: "modis",
              label: "MODIS",
              color: "var(--amber)",
              points: series.map((row, index) => ({ x: index, y: row.modis })),
            },
          ]}
          ticks={series
            .map((row, index) => ({ x: index, label: row.date.slice(5) }))
            .filter((_, index) => index % Math.max(1, Math.floor(series.length / 8)) === 0)}
          height={230}
          yLabel="Detections per day"
        />
        <div className="legend mt-8">
          <span className="legend"><i style={{ width: 9, height: 9, borderRadius: 2, background: "var(--violet)", display: "inline-block" }} /> VIIRS (pooled)</span>
          <span className="legend"><i style={{ width: 9, height: 9, borderRadius: 2, background: "var(--amber)", display: "inline-block" }} /> MODIS</span>
        </div>
      </Panel>

      <div className="grid grid-2 mt-14">
        <Panel title="Agreement metrics" subtitle="Computed on real observations only">
          <KVRows
            rows={[
              ["MODIS mean per co-observed day", formatNumber(daily.modis_mean, 1)],
              ["VIIRS mean per co-observed day", formatNumber(daily.viirs_mean, 1)],
              ["Ratio MODIS / VIIRS", daily.ratio_modis_over_viirs ?? "—"],
              ["Median daily ratio", daily.median_daily_ratio ?? "—"],
              ["Pearson r (log1p counts)", daily.pearson_log ?? "—"],
              ["Spearman rho", daily.spearman ?? "—"],
            ]}
          />
          <div className="note mt-8">
            A ratio well below 1 is expected: VIIRS pixels are ~7× smaller in area and its detection
            threshold is lower, so it resolves fires MODIS cannot.
          </div>
        </Panel>

        <Panel title="Spatial agreement" subtitle="Per 0.25° cell over the selected period">
          <KVRows
            rows={[
              ["Cells active in MODIS", formatNumber(spatial.modis_active_cells)],
              ["Cells active in VIIRS", formatNumber(spatial.viirs_active_cells)],
              ["Cells active in both", formatNumber(spatial.cells_in_both)],
              ["Jaccard overlap", spatial.jaccard ?? "—"],
              ["Spearman on cell totals", spatial.spearman_cell_totals ?? "—"],
              ["Cells compared", formatNumber(spatial.cells_compared)],
            ]}
          />
          <div className="note mt-8">
            Jaccard is the share of active cells seen by both instruments. High values mean both
            sensors highlight the same landscape; low values mean they disagree about where burning is.
          </div>
        </Panel>
      </div>

      {data.per_platform && (
        <Panel className="mt-14" title="Per VIIRS platform" subtitle="Each platform compared with MODIS independently">
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Platform</th>
                  <th className="num">Co-observed days</th>
                  <th className="num">MODIS mean</th>
                  <th className="num">VIIRS mean</th>
                  <th className="num">Ratio</th>
                  <th className="num">Spearman</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.per_platform).map(([sensor, row]) => (
                  <tr key={sensor}>
                    <td>{sensor.replace("viirs_", "VIIRS ")}</td>
                    <td className="num">{formatNumber(row.paired_days as number)}</td>
                    <td className="num">{formatNumber(row.modis_mean as number, 1)}</td>
                    <td className="num">{formatNumber(row.viirs_mean as number, 1)}</td>
                    <td className="num">{row.ratio_modis_over_viirs ?? "—"}</td>
                    <td className="num">{row.spearman ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {co?.available && (
        <Panel className="mt-14" title="Co-detection test" subtitle={`Same-day matching within ${co.radius_km} km`}>
          <p className="prose">
            {Math.round((co.fraction ?? 0) * 100)}% of sampled MODIS detections have a VIIRS detection
            within {co.radius_km} km on the same UTC day. This is the most direct available test of
            "do the instruments see the same fire", and it is still not a validation score: a MODIS
            pixel can contain several VIIRS detections, and overpass times differ.
          </p>
          <p className="note">{co.note}</p>
        </Panel>
      )}

      <div className="grid grid-2 mt-14">
        <Panel title="Why the records differ">
          <ul className="prose" style={{ margin: 0, paddingLeft: 18 }}>
            <li><strong>Pixel size</strong> — MODIS 1 km, VIIRS 375 m: one MODIS detection can cover ~7 VIIRS pixels.</li>
            <li><strong>Sensitivity</strong> — VIIRS detects smaller and cooler fires, so it finds more of them.</li>
            <li><strong>Overpass schedule</strong> — Terra and Aqua cross in the morning and early afternoon; VIIRS platforms add different times.</li>
            <li><strong>Algorithms and confidence</strong> — MODIS reports 0–100 confidence, VIIRS reports a category. They are not the same quantity.</li>
            <li><strong>Availability</strong> — the constellation changes: S-NPP (2012), NOAA-20 (2018), NOAA-21 (2023).</li>
          </ul>
        </Panel>
        <Panel title="What FIRETRACK does about it">
          <ul className="prose" style={{ margin: 0, paddingLeft: 18 }}>
            <li>Aggregates both instruments onto the same 0.25° grid before comparing anything.</li>
            <li>Measures the VIIRS/MODIS ratio only on dates both observed, then applies it as a multiplicative weight.</li>
            <li>Refuses to apply the weight when the overlap is shorter than 60 days or the ratio is unstable (CV &gt; 0.35).</li>
            <li>Normalises every day to a constant reference sensor mix, so sensor transitions do not create fake steps.</li>
            <li>Keeps raw counts visible everywhere the harmonised value appears.</li>
          </ul>
          {data.limitations && (
            <div className="mt-8">
              {data.limitations.map((line) => (
                <div className="note" key={line}>· {line}</div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <InfoNote tone="info">
        No accuracy percentage is claimed here. A defensible accuracy figure would require independent
        burned-area or ground-truth perimeters, which this prototype does not include.
      </InfoNote>

      <div className="row mt-14">
        <Badge tone="info">{data.paired_days} co-observed days</Badge>
        <Badge>grid {data.context?.grid_deg}°</Badge>
      </div>
    </>
  );
}
