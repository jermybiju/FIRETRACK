/** Overview: mission statement, live snapshot, guided demo entry points. */

import React from "react";
import { api } from "../api";
import { HeatLegend, MonthGrid } from "../components/Calendar";
import { StackedBars } from "../components/charts";
import { Badge, ErrorBox, InfoNote, Loading, Panel, Stat } from "../components/ui";
import { formatDate, formatNumber, quantile } from "../format";
import { useApp, useAsync } from "../state";
import type { Route } from "../App";

export function OverviewPage({ onNavigate }: { onNavigate: (route: Route) => void }) {
  const { query, catalog, setAoi, setRange } = useApp();
  const latest = catalog?.max_date ?? new Date().toISOString().slice(0, 10);
  const year = Number(latest.slice(0, 4));
  const month = Number(latest.slice(5, 7));

  const monthQuery = useAsync(() => api.month({ ...query, year, month }), [query, year, month]);
  const harmonization = useAsync(() => api.harmonization(query), [query]);

  const recordDays =
    catalog?.min_date && catalog?.max_date
      ? Math.round(
          (Date.parse(catalog.max_date) - Date.parse(catalog.min_date)) / 86_400_000,
        ) + 1
      : 0;

  const calendar = monthQuery.data;
  const monthMax = calendar
    ? Math.max(1, quantile(calendar.days.map((d) => d.harmonized).filter((v): v is number => v !== null), 0.95))
    : 1;

  const sensorColours = Object.fromEntries(
    (catalog?.sensors ?? []).map((sensor) => [sensor.id, sensor.colour]),
  );
  const sensorLabels = Object.fromEntries(
    (catalog?.sensors ?? []).map((sensor) => [sensor.id, sensor.label.replace(" (Terra + Aqua)", "")]),
  );

  const chartDays = (calendar?.days ?? []).filter((d) => d.observed);

  const demo = (preset: string) => {
    if (preset === "sahel") {
      setAoi({ region_id: "sahel_belt", name: "Sahel & Sudan fire belt" });
      onNavigate("calendar");
    } else if (preset === "compare") {
      setAoi({ region_id: "amazon_arc", name: "Amazon deforestation arc" });
      onNavigate("compare");
    } else {
      onNavigate("analytics");
    }
  };

  return (
    <>
      <section className="panel" style={{ padding: "26px 24px", marginBottom: 14, overflow: "hidden", position: "relative" }}>
        <div
          aria-hidden="true"
          style={{
            position: "absolute", inset: 0, pointerEvents: "none",
            background:
              "radial-gradient(560px 240px at 88% 0%, rgba(249,115,22,0.16), transparent 66%)," +
              "radial-gradient(480px 260px at 6% 110%, rgba(56,189,248,0.12), transparent 62%)",
          }}
        />
        <div style={{ position: "relative" }}>
          <div className="eyebrow">NASA Space Apps Challenge · Harmonization of MODIS and VIIRS Hot Spots</div>
          <h1 className="page-title" style={{ fontSize: 32, maxWidth: "20ch" }}>
            Two satellite perspectives. One consistent history of burning activity.
          </h1>
          <p className="page-sub" style={{ fontSize: 15, maxWidth: "74ch" }}>
            NASA's MODIS and VIIRS instruments detect active fire in different ways, at different
            resolutions, on changing schedules. FIRETRACK turns those two records into one
            coverage-aware time series and lets you read it as a calendar — the same way people read a
            fire season.
          </p>
          <div className="row mt-14">
            <button className="btn btn-primary" type="button" onClick={() => onNavigate("calendar")}>
              Open the burning calendar →
            </button>
            <button className="btn" type="button" onClick={() => onNavigate("map")}>
              Explore the fire map
            </button>
            <button className="btn btn-ghost" type="button" onClick={() => onNavigate("methodology")}>
              How harmonisation works
            </button>
          </div>
        </div>
      </section>

      {catalog?.ready === false && (
        <InfoNote tone="warn">
          <strong>No hotspot records are loaded.</strong> Run{" "}
          <code>python scripts/download_firms_snapshot.py</code> then restart the server, or import a
          FIRMS archive file from the Data Explorer.
        </InfoNote>
      )}

      {catalog?.ready && recordDays > 0 && recordDays < 400 && (
        <InfoNote tone="warn">
          <strong>This record holds {recordDays} days of observations.</strong> The challenge asks for
          the record from the early 2000s to the present, which needs either a free FIRMS MAP_KEY or a
          FIRMS Archive Download import. Until then the calibration, the historical median and the
          trend test correctly report that they lack the history to run.
          <div className="row mt-8" style={{ gap: 10 }}>
            <a
              className="btn btn-sm btn-primary"
              href="https://firms.modaps.eosdis.nasa.gov/api/map_key/"
              target="_blank"
              rel="noreferrer"
            >
              Get a free MAP_KEY
            </a>
            <code>python scripts/fetch_firms_api.py --region sahel_belt --start 2000-11-01</code>
          </div>
        </InfoNote>
      )}

      {(monthQuery.loading || harmonization.loading) && <Loading />}
      {(monthQuery.error || harmonization.error) && (
        <ErrorBox message={monthQuery.error || harmonization.error || ""} onRetry={monthQuery.reload} />
      )}

      {calendar && (
        <>
          <div className="grid grid-4">
            <Stat
              label="Detections in record"
              value={formatNumber(catalog?.detections ?? 0)}
              note={`${formatDate(catalog?.min_date)} → ${formatDate(catalog?.max_date)}`}
            />
            <Stat
              label="Sensors observing"
              value={calendar.context.sensors.length}
              note={calendar.context.sensors.map((s) => s.label.replace(" (Terra + Aqua)", "")).join(" · ")}
            />
            <Stat
              label={`Latest month activity`}
              value={formatNumber(calendar.summary.expected_total)}
              note={`${calendar.month_name} ${calendar.year} · ${calendar.context.unit}`}
            />
            <Stat
              label="Area analysed"
              value={formatNumber(calendar.context.grid_area_km2)}
              unit="km²"
              note={`${calendar.context.grid_cells} cells at ${calendar.context.grid_deg}°`}
            />
          </div>

          <div className="grid mt-14" style={{ gridTemplateColumns: "minmax(0, 1.55fr) minmax(0, 1fr)" }}>
            <Panel
              title={`${calendar.month_name} ${calendar.year} at a glance`}
              subtitle="Daily harmonised activity in the selected area"
              actions={<HeatLegend max={monthMax} />}
            >
              <MonthGrid calendar={calendar} selectedDate={null} onSelectDay={() => onNavigate("calendar")} />
            </Panel>

            <div className="col">
              <Panel title="Sensor contribution" subtitle="Raw detections per sensor in the latest month">
                {chartDays.length > 0 ? (
                  <StackedBars
                    data={chartDays.map((day) => ({
                      label: String(day.day),
                      values: day.per_sensor,
                    }))}
                    colors={sensorColours}
                    labels={sensorLabels}
                    height={150}
                  />
                ) : (
                  <div className="empty">No observations in this month.</div>
                )}
              </Panel>

              <Panel title="Data status">
                <div className="kv">
                  <div className="kv-row">
                    <span className="kv-key">Record</span>
                    <span className="kv-val">
                      {formatDate(catalog?.min_date)} → {formatDate(catalog?.max_date)}
                    </span>
                  </div>
                  <div className="kv-row">
                    <span className="kv-key">Grid</span>
                    <span className="kv-val">{catalog?.grid_deg}° common grid</span>
                  </div>
                  <div className="kv-row">
                    <span className="kv-key">Calibration</span>
                    <span className="kv-val">
                      <Badge tone={calendar.context.calibration.calibrated ? "ok" : "warn"}>
                        {calendar.context.calibration.calibrated ? "calibrated" : calendar.context.calibration.status.replace(/_/g, " ")}
                      </Badge>
                    </span>
                  </div>
                  <div className="kv-row">
                    <span className="kv-key">Provenance</span>
                    <span className="kv-val">
                      {catalog?.batches?.some((b) => b.quality === "science") ? "science quality" : "NRT provisional"}
                    </span>
                  </div>
                </div>
                <div className="note mt-8">
                  A FIRMS hotspot is a thermal anomaly, not a confirmed wildfire. Missing observations
                  are never counted as zero.
                </div>
              </Panel>
            </div>
          </div>

          <div className="grid grid-3 mt-14">
            <Panel title="1 · Read the season" subtitle="Calendar">
              <p className="note">
                The month view colours every observed day by harmonised activity and marks which sensors
                saw it. Empty cells are missing observations, not quiet days.
              </p>
              <button className="btn btn-sm mt-8" type="button" onClick={() => onNavigate("calendar")}>
                Open calendar
              </button>
            </Panel>
            <Panel title="2 · Compare with history" subtitle="Historical median">
              <p className="note">
                Any month is compared with its own historical median across complete years, with the
                baseline period, coverage and a robust z-score shown next to it.
              </p>
              <button className="btn btn-sm mt-8" type="button" onClick={() => demo("compare")}>
                Compare a month
              </button>
            </Panel>
            <Panel title="3 · Check the sensors" subtitle="MODIS vs VIIRS">
              <p className="note">
                See how much the two instruments disagree in your area, where, and by how much — the
                evidence behind the harmonisation weights.
              </p>
              <button className="btn btn-sm mt-8" type="button" onClick={() => onNavigate("compare")}>
                Sensor agreement
              </button>
            </Panel>
          </div>

          <Panel
            className="mt-14"
            title="Guided scientific demo"
            subtitle="Jump straight into a defensible example"
          >
            <div className="grid grid-3">
              <button className="panel" type="button" style={{ padding: 14, textAlign: "left", cursor: "pointer" }} onClick={() => demo("sahel")}>
                <div className="eyebrow" style={{ marginBottom: 4 }}>Fire belt</div>
                <strong>Sahel & Sudan savanna</strong>
                <div className="note mt-8">
                  The dominant November burning region on Earth — a strong seasonal signal to read in
                  the calendar.
                </div>
              </button>
              <button className="panel" type="button" style={{ padding: 14, textAlign: "left", cursor: "pointer" }} onClick={() => demo("compare")}>
                <div className="eyebrow" style={{ marginBottom: 4 }}>Deforestation</div>
                <strong>Amazon arc</strong>
                <div className="note mt-8">
                  Examine how differently MODIS and VIIRS see land-clearing fires in a fragmented
                  landscape.
                </div>
              </button>
              <button className="panel" type="button" style={{ padding: 14, textAlign: "left", cursor: "pointer" }} onClick={() => demo("trends")}>
                <div className="eyebrow" style={{ marginBottom: 4 }}>Long view</div>
                <strong>Historical analytics</strong>
                <div className="note mt-8">
                  Yearly series, seasonal profile, top months and a Mann–Kendall trend test on complete
                  years only.
                </div>
              </button>
            </div>
            <div className="row mt-14">
              <button
                className="btn btn-ghost btn-sm"
                type="button"
                onClick={() => {
                  setAoi({ region_id: "aegean", name: "Aegean & Anatolia" });
                  setRange({ start: catalog?.min_date ?? null, end: catalog?.max_date ?? null });
                }}
              >
                Reset to the bundled default area and full record
              </button>
            </div>
          </Panel>
        </>
      )}

      {harmonization.data && (
        <Panel className="mt-14" title="Sensor availability in this area" subtitle="What the harmonisation is correcting for">
          <div className="grid grid-3">
            {harmonization.data.sensor_timeline.map((sensor) => (
              <div key={sensor.id} className="panel" style={{ padding: 12 }}>
                <div className="row" style={{ gap: 6 }}>
                  <i style={{ width: 9, height: 9, borderRadius: 2, background: sensor.colour, display: "inline-block" }} />
                  <strong style={{ fontSize: 13 }}>{sensor.label}</strong>
                </div>
                <div className="note mt-8">
                  {sensor.observed_days.toLocaleString()} observed days ·{" "}
                  {formatNumber(sensor.detections)} detections
                </div>
                <div className="note">
                  {formatDate(sensor.first_date)} → {formatDate(sensor.last_date)}
                </div>
              </div>
            ))}
          </div>
          <div className="note mt-14">
            Rotation of the daily series by the observing-sensor mix is what keeps a two-satellite day
            comparable with a four-satellite day.
          </div>
        </Panel>
      )}
    </>
  );
}