/** Anomaly Explorer: explainable flags against the historical monthly median. */

import React, { useState } from "react";
import { api } from "../api";
import { Badge, EmptyBox, ErrorBox, InfoNote, Loading, Panel, Segmented, Stat } from "../components/ui";
import { MONTHS, formatNumber, formatPercent } from "../format";
import { useApp, useAsync } from "../state";
import type { AnomalyFlag } from "../types";

export function AnomaliesPage() {
  const { query } = useApp();
  const [threshold, setThreshold] = useState<"2" | "2.5" | "3">("2.5");
  const anomalies = useAsync(
    () => api.anomalies({ ...query, z_threshold: Number(threshold) }),
    [query, threshold],
  );

  if (anomalies.loading) return <Loading label="Scanning for unusual activity…" />;
  if (anomalies.error) return <ErrorBox message={anomalies.error} onRetry={anomalies.reload} />;
  if (!anomalies.data) return null;

  const data = anomalies.data;

  return (
    <>
      <div className="page-head">
        <div className="eyebrow">Explainable anomaly detection</div>
        <h1 className="page-title">Anomaly Explorer</h1>
        <p className="page-sub">
          Months whose activity departs from their own calendar-month median. Every flag reports the
          observed value, the baseline, the deviation, the method and the data coverage that produced it.
        </p>
      </div>

      <Panel
        title="Detection settings"
        actions={
          <Segmented
            ariaLabel="Robust z threshold"
            value={threshold}
            onChange={(next) => setThreshold(next)}
            options={[
              { value: "2", label: "z ≥ 2.0" },
              { value: "2.5", label: "z ≥ 2.5" },
              { value: "3", label: "z ≥ 3.0" },
            ]}
          />
        }
      >
        <div className="grid grid-4">
          <Stat label="Months checked" value={data.months_checked} note="complete months with a basin" />
          <Stat label="Elevated anomalies" value={data.elevated.length} note={`above median, |z| ≥ ${data.threshold}`} />
          <Stat label="Depressed anomalies" value={data.depressed.length} note={`below median, |z| ≥ ${data.threshold}`} />
          <Stat
            label="Skipped (incomplete)"
            value={data.months_skipped_incomplete}
            note="excluded, not treated as zero"
          />
        </div>
        <div className="note mt-14">
          {data.method}. Months below the coverage gate are skipped rather than flagged, because a
          partially observed month cannot be compared with a complete one.
        </div>
      </Panel>

      {data.elevated.length === 0 && data.depressed.length === 0 && (
        <div className="mt-14">
          <EmptyBox title="No anomalies at this threshold">
            Either the record is too short to establish a baseline, or every complete month is within
            normal range. Lower the threshold to see weaker deviations.
          </EmptyBox>
        </div>
      )}

      {data.elevated.length > 0 && (
        <Panel className="mt-14" title="Elevated activity" subtitle="Above the historical median for the same calendar month">
          <div className="grid grid-2">
            {data.elevated.map((flag) => <AnomalyCard key={flag.period} flag={flag} />)}
          </div>
        </Panel>
      )}

      {data.depressed.length > 0 && (
        <Panel className="mt-14" title="Depressed activity" subtitle="Below the historical median for the same calendar month">
          <div className="grid grid-2">
            {data.depressed.map((flag) => <AnomalyCard key={flag.period} flag={flag} />)}
          </div>
        </Panel>
      )}

      <Panel className="mt-14" title="How a flag is produced">
        <ol className="prose" style={{ paddingLeft: 18 }}>
          <li>For each month, activity is aggregated on the common grid with coverage correction.</li>
          <li>Incomplete months (below 80% coverage) are skipped — never counted as low activity.</li>
          <li>The baseline is the median of all <em>other</em> complete years of the same calendar month.</li>
          <li>Deviation is measured with a robust z-score: (x − median) / (1.4826 × MAD).</li>
          <li>A month is flagged when |z| exceeds the threshold; the explanation reports coverage and baseline years.</li>
        </ol>
        <div className="note mt-8">{data.caveats.join(" ")}</div>
      </Panel>

      <InfoNote tone="warn">
        <strong>Statistical anomaly ≠ emergency.</strong> A flagged month is unusual relative to this
        area's own history. It does not confirm a wildfire, and FIRETRACK is not an official alerting
        system.
      </InfoNote>
    </>
  );
}

function AnomalyCard({ flag }: { flag: AnomalyFlag }) {
  const elevated = flag.direction === "above";
  return (
    <div
      className="panel"
      style={{
        padding: 14,
        borderLeft: `3px solid ${elevated ? "var(--accent)" : "var(--cyan)"}`,
      }}
    >
      <div className="spread">
        <strong>{MONTHS[flag.month - 1]} {flag.year}</strong>
        <Badge tone={elevated ? "fire" : "info"}>
          z {flag.z_score !== null ? flag.z_score.toFixed(1) : "—"}
        </Badge>
      </div>
      <div className="kv mt-8">
        <div className="kv-row">
          <span className="kv-key">Observed</span>
          <span className="kv-val">{formatNumber(flag.observed)}</span>
        </div>
        <div className="kv-row">
          <span className="kv-key">Historical median</span>
          <span className="kv-val">{formatNumber(flag.median)}</span>
        </div>
        <div className="kv-row">
          <span className="kv-key">Deviation</span>
          <span className={`kv-val delta ${elevated ? "up" : "down"}`}>
            {flag.absolute_deviation > 0 ? "+" : ""}
            {formatNumber(flag.absolute_deviation)}
            {flag.percent_deviation !== null ? ` (${formatPercent(flag.percent_deviation, 0)})` : ""}
          </span>
        </div>
        <div className="kv-row">
          <span className="kv-key">Coverage</span>
          <span className="kv-val">
            {Math.round(flag.coverage * 100)}% · {flag.observed_days} days
          </span>
        </div>
        <div className="kv-row">
          <span className="kv-key">Baseline years</span>
          <span className="kv-val">{flag.n_years}</span>
        </div>
      </div>
      <div className="note mt-8">
        {elevated ? "More" : "Less"} activity than {MONTHS[flag.month - 1]} usually shows here, based on{" "}
        {flag.n_years} complete year(s). Method: {flag.method}.
      </div>
    </div>
  );
}
