/** Burning Activity Calendar — the signature feature.
 *
 *  Four views share one selection: the month heat map, the yearly profile, the
 *  multi-year history matrix, and the comparison of a month against its
 *  historical median. Missing observations are always rendered as missing, not
 *  as zero.
 */

import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { DayInspector, HeatLegend, MonthGrid, YearMatrix } from "../components/Calendar";
import { BarChart, LineChart } from "../components/charts";
import { Badge, EmptyBox, ErrorBox, InfoNote, Loading, Panel, Segmented, Stat } from "../components/ui";
import {
  MONTHS, MONTHS_SHORT, formatNumber, formatPercent, quantile, shiftMonth,
} from "../format";
import { useApp, useAsync } from "../state";
import type { MonthCalendar } from "../types";
import { calendarSvg, downloadPng, downloadSvg, figureFilename } from "../figure";

type View = "month" | "year" | "history" | "compare";

export function CalendarPage() {
  const { query, catalog, sensors, setSensors, confidence, setConfidence } = useApp();
  const latest = catalog?.max_date ?? new Date().toISOString().slice(0, 10);
  const [year, setYear] = useState(() => Number(latest.slice(0, 4)));
  const [month, setMonth] = useState(() => Number(latest.slice(5, 7)));
  const [view, setView] = useState<View>("month");
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [figureBusy, setFigureBusy] = useState(false);
  const [figureError, setFigureError] = useState<string | null>(null);

  useEffect(() => {
    if (!catalog?.max_date) return;
    setYear(Number(catalog.max_date.slice(0, 4)));
    setMonth(Number(catalog.max_date.slice(5, 7)));
  }, [catalog?.max_date]);

  const monthQuery = useAsync(
    () => api.month({ ...query, year, month }),
    [query, year, month],
    view === "month" || view === "compare",
  );
  const yearQuery = useAsync(
    () => api.year({ ...query, year }),
    [query, year],
    view === "year",
  );
  const historyQuery = useAsync(
    () => api.history({ ...query, metric: "harmonized" }),
    [query],
    view === "history" || view === "compare",
  );

  const calendar = monthQuery.data;
  const selected = useMemo(() => {
    if (!calendar) return null;
    const iso = selectedDay ?? calendar.days.find((d) => d.observed)?.date ?? null;
    return calendar.days.find((d) => d.date === iso) ?? null;
  }, [calendar, selectedDay]);

  const monthMax = useMemo(() => {
    if (!calendar) return 1;
    const values = calendar.days.map((d) => d.harmonized).filter((v): v is number => v !== null);
    return values.length ? Math.max(quantile(values, 0.95), 1) : 1;
  }, [calendar]);

  const goMonth = (delta: number) => {
    const next = shiftMonth(year, month, delta);
    setYear(next.year);
    setMonth(next.month);
    setSelectedDay(null);
    setFigureError(null);
  };

  const exportFigure = async (kind: "svg" | "png") => {
    if (!calendar) return;
    setFigureBusy(true);
    setFigureError(null);
    try {
      const svg = calendarSvg(calendar, {
        aoiName: calendar.context.aoi.name,
        unit: calendar.context.unit,
        sensors: calendar.context.sensors,
      });
      const name = figureFilename(calendar, calendar.context.aoi.name, kind);
      if (kind === "svg") downloadSvg(svg, name);
      else await downloadPng(svg, name);
    } catch (error) {
      setFigureError((error as Error).message);
    } finally {
      setFigureBusy(false);
    }
  };

  const compareBars = useMemo(() => {
    if (!historyQuery.data) return [];
    return historyQuery.data.rows.map((row) => {
      const cell = row.months[month - 1];
      return {
        label: String(row.year),
        value: cell.complete ? cell.value : null,
      };
    });
  }, [historyQuery.data, month]);

  const median = calendar?.baseline?.median ?? null;

  return (
    <>
      <div className="page-head">
        <div className="eyebrow">Signature feature</div>
        <h1 className="page-title">Burning Activity Calendar</h1>
        <p className="page-sub">
          Daily and monthly burning activity for the selected area, harmonised across the MODIS and
          VIIRS record. Compare any month with its own historical median and see exactly which sensors
          were observing.
        </p>
      </div>

      <Panel
        className="mb-0"
        title="Calendar controls"
        actions={
          <div className="row">
            <Segmented
              ariaLabel="Calendar view"
              value={view}
              onChange={(next) => setView(next)}
              options={[
                { value: "month", label: "Month" },
                { value: "year", label: "Year" },
                { value: "history", label: "History" },
                { value: "compare", label: "Compare" },
              ]}
            />
          </div>
        }
      >
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div className="row">
            <button className="btn btn-sm" type="button" onClick={() => goMonth(-1)} aria-label="Previous month">←</button>
            <select
              className="select"
              style={{ width: 130 }}
              value={month}
              onChange={(event) => {
                setMonth(Number(event.target.value));
                setSelectedDay(null);
              }}
              aria-label="Month"
            >
              {MONTHS.map((name, index) => (
                <option key={name} value={index + 1}>{name}</option>
              ))}
            </select>
            <select
              className="select"
              style={{ width: 100 }}
              value={year}
              onChange={(event) => {
                setYear(Number(event.target.value));
                setSelectedDay(null);
              }}
              aria-label="Year"
            >
              {(historyQuery.data?.years?.length
                ? historyQuery.data.years
                : catalog?.min_date
                  ? Array.from(
                      { length: Number(latest.slice(0, 4)) - Number(catalog.min_date.slice(0, 4)) + 1 },
                      (_, index) => Number(catalog.min_date!.slice(0, 4)) + index,
                    ).reverse()
                  : [year]
              ).map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <button className="btn btn-sm" type="button" onClick={() => goMonth(1)} aria-label="Next month">→</button>
          </div>

          <div className="row">
            <Segmented
              ariaLabel="Confidence filter"
              value={confidence}
              onChange={(next) => setConfidence(next)}
              options={[
                { value: "all", label: "All" },
                { value: "nominal", label: "Nominal+" },
                { value: "high", label: "High" },
              ]}
            />
            <div className="row" style={{ gap: 4 }}>
              {(catalog?.sensors ?? []).map((sensor) => {
                const on = sensors.length === 0 || sensors.includes(sensor.id);
                return (
                  <button
                    key={sensor.id}
                    type="button"
                    className="sensor-chip"
                    aria-pressed={on}
                    onClick={() => {
                      const base = sensors.length === 0 ? catalog!.sensors.map((s) => s.id) : sensors;
                      const next = base.includes(sensor.id)
                        ? base.filter((id) => id !== sensor.id)
                        : [...base, sensor.id];
                      if (next.length === 0) return;
                      setSensors(next.length === catalog!.sensors.length ? [] : next);
                    }}
                  >
                    <span className="swatch" style={{ background: sensor.colour }} />
                    {sensor.label.replace(" (Terra + Aqua)", "").replace("VIIRS ", "")}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </Panel>

      {(monthQuery.loading || yearQuery.loading || historyQuery.loading) && <Loading />}
      {(monthQuery.error || yearQuery.error || historyQuery.error) && (
        <ErrorBox
          message={monthQuery.error || yearQuery.error || historyQuery.error || ""}
          onRetry={() => {
            monthQuery.reload();
            yearQuery.reload();
            historyQuery.reload();
          }}
        />
      )}

      {view === "month" && calendar && (
        <>
          <div className="grid grid-4 mt-14">
            <Stat
              label="Harmonised activity"
              value={formatNumber(calendar.summary.expected_total)}
              note={calendar.context.unit}
            />
            <Stat
              label={`vs ${MONTHS[month - 1]} median`}
              value={
                calendar.comparison.percent_deviation !== null && calendar.comparison.percent_reliable
                  ? formatPercent(calendar.comparison.percent_deviation)
                  : formatNumber(calendar.comparison.absolute_deviation)
              }
              note={
                calendar.comparison.median === null
                  ? "no historical baseline yet"
                  : `median ${formatNumber(calendar.comparison.median)} · ${
                      calendar.baseline.n_years
                    } year(s)`
              }
            />
            <Stat
              label="Observed days"
              value={`${calendar.summary.observed_days}/${calendar.summary.days_in_period}`}
              note={`coverage ${Math.round(calendar.summary.coverage * 100)}% ${
                calendar.summary.complete ? "· complete" : "· incomplete"
              }`}
            />
            <Stat
              label="Raw detections"
              value={formatNumber(calendar.summary.raw_total)}
              note="unadjusted, all selected sensors"
            />
          </div>

          <div className="grid mt-14" style={{ gridTemplateColumns: "minmax(0, 2.1fr) minmax(0, 1fr)" }}>
            <Panel
              title="Daily burning activity"
              subtitle="Click a day to inspect its detections and sensor coverage."
              actions={
                <div className="row" style={{ gap: 8 }}>
                  <HeatLegend max={monthMax} />
                  <button
                    className="btn btn-sm btn-ghost"
                    type="button"
                    disabled={figureBusy}
                    onClick={() => exportFigure("svg")}
                    title="Download this calendar as a standalone SVG"
                  >
                    SVG
                  </button>
                  <button
                    className="btn btn-sm btn-ghost"
                    type="button"
                    disabled={figureBusy}
                    onClick={() => exportFigure("png")}
                    title="Download this calendar as a PNG for slides or briefings"
                  >
                    {figureBusy ? "…" : "PNG"}
                  </button>
                </div>
              }
            >
              <MonthGrid
                calendar={calendar}
                selectedDate={selected?.date ?? null}
                onSelectDay={setSelectedDay}
              />
              {figureError && <div className="note mt-8" style={{ color: "var(--danger)" }}>{figureError}</div>}
            </Panel>

            <Panel title="Day inspector">
              <DayInspector day={selected} max={monthMax} />
            </Panel>
          </div>

          <div className="grid grid-2 mt-14">
            <Panel
              title="Historical monthly median"
              subtitle={`${MONTHS[month - 1]} baseline across all complete years in the record`}
            >
              <MedianPanel calendar={calendar} />
            </Panel>

            <Panel
              title="Activity by sensor"
              subtitle="Raw detections per sensor within the selected month"
              actions={<Badge tone="info">{calendar.context.unit}</Badge>}
            >
              <div className="col">
                {Object.entries(calendar.summary.per_sensor)
                  .sort((a, b) => b[1] - a[1])
                  .map(([sensor, count]) => {
                    const meta = calendar.context.sensors.find((s) => s.id === sensor);
                    const share = calendar.summary.raw_total ? count / calendar.summary.raw_total : 0;
                    return (
                      <div key={sensor} className="col" style={{ gap: 4 }}>
                        <div className="spread" style={{ fontSize: 12.5 }}>
                          <span className="row" style={{ gap: 6 }}>
                            <i style={{ width: 9, height: 9, borderRadius: 2, background: meta?.colour, display: "inline-block" }} />
                            {meta?.label ?? sensor}
                          </span>
                          <span className="tnum">{formatNumber(count)} · {Math.round(share * 100)}%</span>
                        </div>
                        <div style={{ height: 4, background: "var(--panel-3)", borderRadius: 2 }}>
                          <div style={{ width: `${share * 100}%`, height: 4, borderRadius: 2, background: meta?.colour }} />
                        </div>
                      </div>
                    );
                  })}
                {Object.keys(calendar.summary.per_sensor).length === 0 && (
                  <EmptyBox title="No detections in this month" />
                )}
              </div>
            </Panel>
          </div>
        </>
      )}

      {view === "year" && yearQuery.data && (
        <div className="mt-14">
          <Panel
            title={`${yearQuery.data.year} monthly profile`}
            subtitle={
              yearQuery.data.complete_months
                ? `${yearQuery.data.complete_months} complete months · yearly total ${formatNumber(
                    yearQuery.data.year_total,
                  )} · peak ${yearQuery.data.peak_month_name}`
                : "No complete month in this year for the current selection."
            }
          >
            <BarChart
              data={yearQuery.data.months.map((entry) => ({
                label: MONTHS_SHORT[entry.month - 1],
                value: entry.complete ? entry.expected_total : null,
                muted: !entry.complete,
              }))}
              valueFormat={(value) => formatNumber(value)}
            />
            <div className="table-wrap mt-14">
              <table className="data">
                <thead>
                  <tr>
                    <th>Month</th>
                    <th className="num">Harmonised</th>
                    <th className="num">Raw</th>
                    <th className="num">Observed days</th>
                    <th className="num">Coverage</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {yearQuery.data.months.map((entry) => (
                    <tr key={entry.month}>
                      <td>{entry.month_name}</td>
                      <td className="num">{formatNumber(entry.expected_total)}</td>
                      <td className="num">{formatNumber(entry.raw_total)}</td>
                      <td className="num">{entry.observed_days}/{entry.days_in_period}</td>
                      <td className="num">{Math.round(entry.coverage * 100)}%</td>
                      <td>
                        {entry.complete ? (
                          <Badge tone="ok">complete</Badge>
                        ) : entry.has_data ? (
                          <Badge tone="warn">incomplete</Badge>
                        ) : (
                          <Badge>no data</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}

      {view === "history" && historyQuery.data && (
        <div className="mt-14">
          <Panel
            title="Historical burning calendar"
            subtitle="Every observed month on the common 0.25° grid. Click a cell to open that month."
          >
            <YearMatrix
              matrix={historyQuery.data}
              onSelectMonth={(y, m) => {
                setYear(y);
                setMonth(m);
                setView("month");
              }}
            />
          </Panel>
        </div>
      )}

      {view === "compare" && historyQuery.data && calendar && (
        <div className="grid grid-2 mt-14">
          <Panel
            title={`${MONTHS[month - 1]} across all years`}
            subtitle="Coverage-corrected harmonised activity for this calendar month, year by year."
          >
            <BarChart
              data={compareBars.map((bar) => ({ ...bar, muted: bar.value === null }))}
              valueFormat={(value) => formatNumber(value)}
            />
            {median !== null && (
              <div className="note">
                Dashed reference: historical median {formatNumber(median)} ({calendar.baseline.n_years} years).
                {calendar.baseline.n_years === 0 && " No complete year available yet."}
              </div>
            )}
            <div className="row mt-8">
              {median !== null && (
                <Badge tone="info">median {formatNumber(median)}</Badge>
              )}
              <Badge>{calendar.baseline.sufficient ? "baseline sufficient" : "baseline needs ≥3 years"}</Badge>
            </div>
          </Panel>

          <Panel title="Selected month vs baseline" subtitle={`${MONTHS[month - 1]} ${year}`}>
            <MedianPanel calendar={calendar} />
          </Panel>
        </div>
      )}
    </>
  );
}

function MedianPanel({ calendar }: { calendar: MonthCalendar }) {
  const { baseline, comparison, summary } = calendar;
  if (baseline.median === null) {
    return (
      <>
        <div className="empty">
          <div style={{ color: "var(--text)", fontWeight: 600, marginBottom: 6 }}>
            No historical median available for {MONTHS[calendar.month - 1]}
          </div>
          A median needs at least three complete years of this calendar month. This record currently
          contains {baseline.n_years} usable year(s)
          {baseline.years_used.length ? ` (${baseline.years_used.join(", ")})` : ""}.
        </div>
        <InfoNote tone="info">
          Months with fewer than 80% of their days observed are excluded rather than averaged in, so a
          partially observed month can never masquerade as a quiet one.
        </InfoNote>
      </>
    );
  }

  const direction = comparison.direction;
  return (
    <div className="col">
      <div className="grid grid-2" style={{ gap: 10 }}>
        <div>
          <div className="stat-label">Observed</div>
          <div style={{ fontSize: 22, fontWeight: 650 }}>{formatNumber(comparison.observed)}</div>
        </div>
        <div>
          <div className="stat-label">Historical median</div>
          <div style={{ fontSize: 22, fontWeight: 650 }}>{formatNumber(comparison.median)}</div>
        </div>
      </div>

      <div className="kv mt-8">
        <div className="kv-row">
          <span className="kv-key">Absolute deviation</span>
          <span className={`kv-val delta ${direction === "above" ? "up" : direction === "below" ? "down" : "flat"}`}>
            {comparison.absolute_deviation === null
              ? "—"
              : `${comparison.absolute_deviation > 0 ? "+" : ""}${formatNumber(comparison.absolute_deviation)}`}
          </span>
        </div>
        <div className="kv-row">
          <span className="kv-key">Percent deviation</span>
          <span className={`kv-val delta ${direction === "above" ? "up" : direction === "below" ? "down" : "flat"}`}>
            {comparison.percent_deviation !== null && comparison.percent_reliable
              ? formatPercent(comparison.percent_deviation, 1)
              : "not meaningful"}
          </span>
        </div>
        <div className="kv-row">
          <span className="kv-key">Robust z-score</span>
          <span className="kv-val">{comparison.z_score ?? "—"}</span>
        </div>
        <div className="kv-row">
          <span className="kv-key">Baseline years</span>
          <span className="kv-val">{baseline.n_years}</span>
        </div>
        <div className="kv-row">
          <span className="kv-key">Baseline range (p25–p75)</span>
          <span className="kv-val">
            {baseline.p25 === null ? "—" : `${formatNumber(baseline.p25)} – ${formatNumber(baseline.p75)}`}
          </span>
        </div>
        <div className="kv-row">
          <span className="kv-key">Coverage this month</span>
          <span className="kv-val">{Math.round(summary.coverage * 100)}%</span>
        </div>
      </div>

      {comparison.percent_deviation !== null && !comparison.percent_reliable && (
        <div className="note">
          A percentage is not reported because the baseline is only {formatNumber(baseline.median)}{" "}
          detections; the absolute difference is the honest comparison at that magnitude.
        </div>
      )}

      <InfoNote tone={Math.abs(comparison.z_score ?? 0) >= 2.5 ? "warn" : "info"}>
        {comparison.z_score !== null && Math.abs(comparison.z_score) >= 2.5 ? (
          <>
            <strong>Unusual activity.</strong> This month is {Math.abs(comparison.z_score).toFixed(1)} robust
            standard deviations {direction} the {MONTHS[calendar.month - 1]} median. That is a statistical
            flag, not a confirmation of wildfire activity.
          </>
        ) : (
          <>
            Activity is within the normal range for {MONTHS[calendar.month - 1]}: the robust z-score is{" "}
            {comparison.z_score ?? "unavailable"} against a threshold of 2.5.
          </>
        )}
      </InfoNote>
    </div>
  );
}
