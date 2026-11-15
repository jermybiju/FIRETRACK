/** Calendar visualisations: month heatmap, year matrix, legend. */

import React, { useMemo } from "react";
import type { DayCell, HistoryMatrix, MonthCalendar } from "../types";
import {
  HEAT_RAMP, MONTHS_SHORT, NO_DATA_COLOR, WEEKDAYS, formatNumber, heatColor,
  heatTextColor, quantile, sensorColour, sensorShort, todayIso, weekdayIndex,
} from "../format";

export function HeatLegend({ max, unit }: { max: number; unit?: string }) {
  return (
    <div className="legend">
      <span>low</span>
      <span className="legend-steps">
        {HEAT_RAMP.map((colour) => (
          <span key={colour} style={{ background: colour }} />
        ))}
      </span>
      <span>high</span>
      <span style={{ marginLeft: 6 }}>
        {unit ? `${unit} · ` : ""}max {formatNumber(max)}
      </span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 4, marginLeft: 8 }}>
        <i style={{ width: 12, height: 9, background: NO_DATA_COLOR, border: "1px solid var(--border)", borderRadius: 2, display: "inline-block" }} />
        no observation
      </span>
    </div>
  );
}

function valueMax(days: DayCell[]): number {
  const values = days.map((d) => d.harmonized).filter((v): v is number => v !== null && v > 0);
  if (!values.length) return 1;
  return Math.max(quantile(values, 0.95), values[0]);
}

export function MonthGrid({
  calendar, selectedDate, onSelectDay,
}: {
  calendar: MonthCalendar;
  selectedDate: string | null;
  onSelectDay: (date: string) => void;
}) {
  const max = useMemo(() => valueMax(calendar.days), [calendar.days]);
  const leading = calendar.days.length ? weekdayIndex(calendar.days[0].date) : 0;
  const today = todayIso();

  return (
    <div>
      <div className="month-grid-header">
        <div>
          <div className="panel-title">{calendar.month_name} {calendar.year}</div>
          <div className="note">
            {calendar.summary.observed_days} of {calendar.summary.days_in_period} days observed
            {" · "}coverage {Math.round(calendar.summary.coverage * 100)}%
            {calendar.summary.complete
              ? " · complete month"
              : " · incomplete, excluded from the historical median"}
          </div>
        </div>
      </div>

      <div className="calendar" style={{ marginTop: 12 }} role="grid" aria-label={`${calendar.month_name} ${calendar.year} burning activity`}>
        {WEEKDAYS.map((day) => (
          <div className="cal-weekday" key={day} role="columnheader">{day}</div>
        ))}
        {Array.from({ length: leading }).map((_, index) => (
          <div className="cal-cell blank" key={`blank-${index}`} aria-hidden="true" />
        ))}
        {calendar.days.map((day) => {
          const observed = day.observed && day.harmonized !== null;
          const background = observed ? heatColor(day.harmonized, max) : NO_DATA_COLOR;
          const textColour = observed ? heatTextColor(day.harmonized, max) : "var(--text-faint)";
          return (
            <button
              key={day.date}
              type="button"
              role="gridcell"
              className={`cal-cell${selectedDate === day.date ? " selected" : ""}${day.date === today ? " today" : ""}`}
              style={{ background, borderColor: observed ? "transparent" : "var(--border)" }}
              onClick={() => onSelectDay(day.date)}
              aria-label={`${day.date}: ${observed ? `${formatNumber(day.harmonized)} harmonised detections` : "no observation"}`}
            >
              <div className="row" style={{ justifyContent: "space-between", gap: 2 }}>
                <span className="cal-day" style={{ color: textColour }}>{day.day}</span>
                {observed && (
                  <span className="cal-sensors" aria-hidden="true">
                    {day.sensors_observing.map((sensor) => (
                      <i key={sensor} style={{ background: sensorColour(sensor) }} />
                    ))}
                  </span>
                )}
              </div>
              <div className="cal-value" style={{ color: textColour }}>
                {observed ? formatNumber(day.harmonized) : "—"}
              </div>
            </button>
          );
        })}
      </div>

      <div className="note" style={{ marginTop: 10 }}>
        Each cell is one UTC day. Coloured dots mark which sensors observed that day; days without an
        observing sensor are shown as “no observation”, never as zero activity.
      </div>
    </div>
  );
}

export function DayInspector({ day, max }: { day: DayCell | null; max?: number }) {
  if (!day) {
    return (
      <div className="empty">
        Select a day in the calendar to inspect its detections, sensor coverage and fire radiative power.
      </div>
    );
  }
  const observed = day.observed && day.harmonized !== null;
  return (
    <div className="col">
      <div className="spread">
        <div>
          <div className="stat-label">Selected day</div>
          <div style={{ fontSize: 20, fontWeight: 650 }}>
            {day.date.slice(8, 10)} {MONTHS_SHORT[Number(day.date.slice(5, 7)) - 1]} {day.date.slice(0, 4)}
          </div>
        </div>
        <span
          style={{
            width: 34, height: 34, borderRadius: 9,
            background: observed ? heatColor(day.harmonized, max ?? 1) : NO_DATA_COLOR,
            border: "1px solid var(--border-strong)",
          }}
          aria-hidden="true"
        />
      </div>

      {observed ? (
        <>
          <div className="kv">
            <div className="kv-row"><span className="kv-key">Harmonised activity</span>
              <span className="kv-val">{formatNumber(day.harmonized)}</span></div>
            <div className="kv-row"><span className="kv-key">Raw detections</span>
              <span className="kv-val">{formatNumber(day.raw_total)}</span></div>
            <div className="kv-row"><span className="kv-key">FRP, raw sum</span>
              <span className="kv-val">{formatNumber(day.frp_total)} MW</span></div>
            <div className="kv-row"><span className="kv-key">Sensor coverage</span>
              <span className="kv-val">{Math.round(day.coverage * 100)}%</span></div>
          </div>
          <div className="col" style={{ gap: 4 }}>
            {Object.entries(day.per_sensor)
              .sort((a, b) => b[1] - a[1])
              .map(([sensor, count]) => (
                <div className="spread" key={sensor} style={{ fontSize: 12.5 }}>
                  <span className="row" style={{ gap: 6 }}>
                    <i style={{ width: 8, height: 8, borderRadius: 2, background: sensorColour(sensor), display: "inline-block" }} />
                    {sensorShort(sensor)}
                  </span>
                  <span className="tnum">
                    {formatNumber(count)}
                    <span className="faint"> · {formatNumber(day.frp_by_sensor?.[sensor] ?? 0)} MW</span>
                  </span>
                </div>
              ))}
          </div>
          <div className="note">
            FRP is listed per sensor. The total is a plain sum of raw sensor values and is not a
            harmonised measurement, because MODIS and VIIRS retrieve FRP differently.
          </div>
        </>
      ) : (
        <div className="callout warn">
          No sensor observed this area on this date. This is <strong>missing data</strong>, not zero
          burning activity.
        </div>
      )}
    </div>
  );
}

export function YearMatrix({
  matrix, onSelectMonth,
}: {
  matrix: HistoryMatrix;
  onSelectMonth?: (year: number, month: number) => void;
}) {
  const allValues = matrix.rows.flatMap((row) =>
    row.months.filter((m) => m.complete && m.value !== null).map((m) => m.value as number),
  );
  const p90 = allValues.length ? quantile(allValues, 0.9) : 1;
  const decades = useMemo(() => {
    const byDecade = new Map<string, { year: number; months: HistoryMatrix["rows"][number]["months"] }[]>();
    for (const row of matrix.rows) {
      const key = `${Math.floor(row.year / 10) * 10}s`;
      if (!byDecade.has(key)) byDecade.set(key, []);
      byDecade.get(key)!.push(row);
    }
    return [...byDecade.entries()];
  }, [matrix.rows]);

  if (!matrix.rows.length) {
    return <div className="empty">No monthly records yet.</div>;
  }

  return (
    <div className="col" style={{ gap: 16 }}>
      {decades.map(([label, rows]) => (
        <div key={label}>
          <div className="field-label" style={{ marginBottom: 6 }}>{label}</div>
          <div
            className="matrix"
            style={{ gridTemplateColumns: `56px repeat(12, minmax(0, 1fr))` }}
            role="table"
            aria-label={`Monthly activity, ${label}`}
          >
            <div className="matrix-label" />
            {MONTHS_SHORT.map((month) => (
              <div className="matrix-label" key={month} style={{ justifyContent: "center" }}>{month}</div>
            ))}
            {rows.map((row) => (
              <React.Fragment key={row.year}>
                <div className="matrix-label">{row.year}</div>
                {row.months.map((cell) => {
                  const usable = cell.complete && cell.value !== null;
                  const colour = usable ? heatColor(cell.value, p90) : NO_DATA_COLOR;
                  const text = usable ? heatTextColor(cell.value, p90) : "var(--text-faint)";
                  return (
                    <button
                      key={cell.month}
                      type="button"
                      className={`matrix-cell ${cell.complete ? "complete" : "incomplete"}`}
                      style={{ background: colour, color: text, border: 0 }}
                      title={`${MONTHS_SHORT[cell.month - 1]} ${row.year}: ${
                        usable ? `${formatNumber(cell.value)} harmonised` : "incomplete / no data"
                      } · coverage ${Math.round(cell.coverage * 100)}%`}
                      onClick={() => onSelectMonth?.(row.year, cell.month)}
                    >
                      {usable ? formatNumber(cell.value) : "·"}
                    </button>
                  );
                })}
              </React.Fragment>
            ))}
          </div>
        </div>
      ))}
      <HeatLegend max={p90} />
      <div className="note">
        Values are coverage-corrected harmonised activity for each month. Faded cells were observed on
        too few days to compare and are excluded from medians; they are not low-activity readings.
      </div>
    </div>
  );
}
