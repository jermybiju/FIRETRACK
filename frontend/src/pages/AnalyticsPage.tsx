/** Historical analytics: yearly series, seasonal profile, trend test. */

import React from "react";
import { api } from "../api";
import { BarChart, LineChart } from "../components/charts";
import { Badge, EmptyBox, ErrorBox, InfoNote, KVRows, Loading, Panel, Stat } from "../components/ui";
import { MONTHS_SHORT, formatDate, formatNumber } from "../format";
import { useApp, useAsync } from "../state";

export function AnalyticsPage() {
  const { query, catalog } = useApp();
  const trends = useAsync(() => api.trends(query), [query]);
  const critical = useAsync(() => api.criticalPeriods({ ...query, percentile: 90, min_days: 3 }), [query]);

  if (trends.loading) return <Loading label="Computing trends…" />;
  if (trends.error) return <ErrorBox message={trends.error} onRetry={trends.reload} />;
  if (!trends.data) return null;

  const data = trends.data;
  const completeYears = data.yearly.filter((y) => y.complete);
  const mk = data.trend.mann_kendall;
  const significant = mk.p !== null && mk.p < 0.05;

  return (
    <>
      <div className="page-head">
        <div className="eyebrow">Historical analytics</div>
        <h1 className="page-title">Burning activity through time</h1>
        <p className="page-sub">
          Long-term behaviour of the selected area on the harmonised series. Only complete years enter
          the trend test; partial years stay visible in the chart but are excluded from the statistics.
        </p>
      </div>

      {completeYears.length === 0 && (
        <InfoNote tone="warn">
          <strong>Not enough complete years for a trend.</strong> This record spans{" "}
          {formatDate(catalog?.min_date)} → {formatDate(catalog?.max_date)}; the
          Mann–Kendall test needs at least four complete years and the historical median needs three.
          Import a longer FIRMS record (see the Methodology page) to unlock these statistics.
        </InfoNote>
      )}

      <div className="grid grid-4">
        <Stat
          label="Years in record"
          value={data.yearly.length}
          note={`${completeYears.length} complete`}
        />
        <Stat
          label="Theil–Sen slope"
          value={data.trend.theil_sen_slope_per_year === null ? "—" : formatNumber(data.trend.theil_sen_slope_per_year)}
          note="per year, robust to single extremes"
        />
        <Stat
          label="Mann–Kendall p"
          value={mk.p === null ? "—" : mk.p < 0.001 ? "<0.001" : mk.p.toFixed(3)}
          note={significant ? "significant at 0.05" : "not significant at 0.05"}
        />
        <Stat
          label="Peak year"
          value={data.top_years[0]?.year ?? "—"}
          note={data.top_years[0] ? `${formatNumber(data.top_years[0].value)} harmonised` : "no complete year"}
        />
      </div>

      <Panel
        className="mt-14"
        title="Yearly harmonised activity"
        subtitle="Coverage-corrected totals; grey bars are incomplete years excluded from the trend"
        actions={<Badge tone="info">{data.context.unit}</Badge>}
      >
        <BarChart
          data={data.yearly.map((year) => ({
            label: String(year.year).slice(2),
            value: year.complete ? year.expected_total : null,
            muted: !year.complete,
          }))}
          valueFormat={(value) => formatNumber(value)}
        />
      </Panel>

      <div className="grid grid-2 mt-14">
        <Panel title="Seasonal profile" subtitle="Median across complete years, by calendar month">          <LineChart
            series={[
              {
                id: "seasonal",
                label: "Median monthly activity",
                color: "var(--cyan)",
                points: data.monthly_profile.map((entry, index) => ({ x: index, y: entry.median })),
              },
            ]}
            ticks={MONTHS_SHORT.map((label, index) => ({ x: index, label }))}
            height={210}
            yLabel="Seasonal profile"
          />
          <div className="note mt-8">
            The shape of this curve is the burning fingerprint of the selected area — when its fire
            season starts, peaks and ends.
          </div>
        </Panel>

        <Panel title="Trend test" subtitle={data.trend.method}>
          <KVRows
            rows={[
              ["Years used", data.trend.n_years],
              ["Theil–Sen slope", data.trend.theil_sen_slope_per_year === null ? "—" : `${formatNumber(data.trend.theil_sen_slope_per_year)} / year`],
              ["Mann–Kendall S", mk.s ?? "—"],
              ["Mann–Kendall z", mk.z ?? "—"],
              ["p-value (two-sided)", mk.p ?? "—"],
              ["Verdict", mk.trend.replace(/_/g, " ")],
            ]}
          />
          <div className={`callout mt-14 ${significant ? "warn" : "info"}`}>
            {significant
              ? "A monotonic trend is detected at the 0.05 level. This is a statistical statement about detections, not proof of a change in fire regime: sensor improvements, land-use policy and climate all act at once."
              : "No monotonic trend is detected at the 0.05 level for this selection. Absence of a significant trend is not evidence that nothing changed."}
          </div>
          <div className="note mt-8">{data.trend.note}</div>
        </Panel>
      </div>

      <Panel
        className="mt-14"
        title="Critical burning periods"
        subtitle={
          critical.data
            ? critical.data.method
            : "Contiguous days above the historical 90th percentile for the same calendar month"
        }
        actions={<Badge tone="fire">top {critical.data?.periods.length ?? 0} periods</Badge>}
      >
        {critical.loading && <div className="note">Analysing periods…</div>}
        {critical.error && <div className="errorbox">{critical.error}</div>}
        {critical.data && critical.data.periods.length === 0 && (
          <EmptyBox title="No critical periods found">
            No run of {critical.data.min_days}+ consecutive days exceeded the 90th percentile of its
            calendar month. That can mean a quiet record, or a record too short to build a baseline.
          </EmptyBox>
        )}
        {critical.data && critical.data.periods.length > 0 && (
          <>
            <div className="table-wrap" style={{ maxHeight: 320, overflowY: "auto" }}>
              <table className="data">
                <thead>
                  <tr>
                    <th>Period</th>
                    <th className="num">Days</th>
                    <th className="num">Peak activity</th>
                    <th>Peak date</th>
                    <th className="num">Month threshold</th>
                    <th>Sensors</th>
                  </tr>
                </thead>
                <tbody>
                  {critical.data.periods.slice(0, 15).map((period) => (
                    <tr key={`${period.start}-${period.end}`}>
                      <td className="mono">{period.start} → {period.end}</td>
                      <td className="num">{period.duration_days}</td>
                      <td className="num">{formatNumber(period.peak_value)}</td>
                      <td className="mono">{period.peak_date}</td>
                      <td className="num">{period.threshold === null ? "—" : formatNumber(period.threshold)}</td>
                      <td className="faint">{period.sensors.length}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="note mt-8">
              A period ends where observations are missing or where a month fails the coverage gate,
              so a long event can be split in two. High activity is <strong>not</strong> a confirmed
              wildfire emergency: agricultural burning and other thermal anomalies are included.
            </div>
          </>
        )}
      </Panel>

      <div className="grid grid-2 mt-14">
        <Panel title="Highest-activity months" subtitle="Complete months only">
          {data.top_months.length ? (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr><th>Rank</th><th>Month</th><th className="num">Harmonised</th><th className="num">Raw</th></tr>
                </thead>
                <tbody>
                  {data.top_months.map((month, index) => (
                    <tr key={month.label}>
                      <td className="mono">{index + 1}</td>
                      <td>{month.label}</td>
                      <td className="num">{formatNumber(month.value)}</td>
                      <td className="num">{formatNumber(month.raw_total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyBox title="No complete month yet">Import a longer record to rank months.</EmptyBox>
          )}
        </Panel>

        <Panel title="Highest-activity years" subtitle="Complete years only">
          {data.top_years.length ? (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr><th>Rank</th><th>Year</th><th className="num">Harmonised</th><th className="num">Raw</th></tr>
                </thead>
                <tbody>
                  {data.top_years.map((year, index) => (
                    <tr key={year.year}>
                      <td className="mono">{index + 1}</td>
                      <td>{year.year}</td>
                      <td className="num">{formatNumber(year.value)}</td>
                      <td className="num">{formatNumber(year.raw_total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyBox title="No complete year yet">A year needs 80% monthly coverage to count.</EmptyBox>
          )}
        </Panel>
      </div>

      <Panel
        className="mt-14"
        title="Year-by-year coverage"
        subtitle="Why a year was or was not used in the statistics"
      >
        <div className="table-wrap" style={{ maxHeight: 340, overflowY: "auto" }}>
          <table className="data">
            <thead>
              <tr>
                <th>Year</th>
                <th className="num">Harmonised</th>
                <th className="num">Raw</th>
                <th className="num">Observed days</th>
                <th className="num">Coverage</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.yearly.map((year) => (
                <tr key={year.year}>
                  <td>{year.year}</td>
                  <td className="num">{formatNumber(year.expected_total)}</td>
                  <td className="num">{formatNumber(year.raw_total)}</td>
                  <td className="num">{year.observed_days}</td>
                  <td className="num">{Math.round(year.coverage * 100)}%</td>
                  <td>{year.complete ? <Badge tone="ok">used</Badge> : <Badge tone="warn">excluded</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <InfoNote tone="info">
        Activity is reported in <strong>{data.context.unit}</strong>. Harmonised values rescale the
        observed sensors to a constant reference mix; raw totals are shown alongside so the effect of
        that correction is always visible.
      </InfoNote>
    </>
  );
}
