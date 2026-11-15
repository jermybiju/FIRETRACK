/** Fire map: harmonised activity grid with per-sensor layers and area drawing. */

import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { MapView, type DrawMode } from "../components/MapView";
import { Badge, ErrorBox, InfoNote, Loading, Panel, Segmented } from "../components/ui";
import { formatNumber, sensorColour, sensorLabel } from "../format";
import { useApp, useAsync } from "../state";

export function MapPage({ drawRequest, onDrawHandled }: {
  drawRequest: boolean;
  onDrawHandled: () => void;
}) {
  const { aoi, setAoi, query, catalog, range, setRange, sensors, setSensors } = useApp();
  const [drawMode, setDrawMode] = useState<DrawMode>("none");

  useEffect(() => {
    if (drawRequest) {
      setDrawMode("rect");
      onDrawHandled();
    }
  }, [drawRequest, onDrawHandled]);

  const cellsQuery = useAsync(() => api.mapCells(query), [query]);

  const cells = cellsQuery.data?.cells ?? [];
  const maxTotal = cellsQuery.data?.max_total ?? 0;

  const quickRanges = useMemo(() => {
    if (!catalog?.min_date || !catalog?.max_date) return [];
    const max = catalog.max_date;
    const back = (days: number) => {
      const end = new Date(`${max}T00:00:00Z`);
      end.setUTCDate(end.getUTCDate() - days + 1);
      return end.toISOString().slice(0, 10);
    };
    return [
      { label: "Full record", start: catalog.min_date, end: catalog.max_date },
      { label: "Last 7 days", start: back(7), end: catalog.max_date },
      { label: "Last 3 days", start: back(3), end: catalog.max_date },
    ];
  }, [catalog?.min_date, catalog?.max_date]);

  const summary = useMemo(() => {
    const bySensor: Record<string, number> = {};
    for (const cell of cells) {
      for (const [sensor, count] of Object.entries(cell.per_sensor)) {
        bySensor[sensor] = (bySensor[sensor] ?? 0) + count;
      }
    }
    return {
      total: Object.values(bySensor).reduce((a, b) => a + b, 0),
      bySensor,
    };
  }, [cells]);

  return (
    <>
      <div className="page-head">
        <div className="eyebrow">Interactive map</div>
        <h1 className="page-title">Fire Map</h1>
        <p className="page-sub">
          Grid-cell burning activity for the selected area and period. Cells are the same 0.25° units
          used by every statistic in FIRETRACK, so what you see here is what the calendar counts.
        </p>
      </div>

      <Panel
        title="Map controls"
        actions={
          <div className="row">
            <button
              className={`btn btn-sm${drawMode === "rect" ? " btn-primary" : ""}`}
              type="button"
              onClick={() => setDrawMode(drawMode === "rect" ? "none" : "rect")}
            >
              Draw box
            </button>
            <button
              className={`btn btn-sm${drawMode === "polygon" ? " btn-primary" : ""}`}
              type="button"
              onClick={() => setDrawMode(drawMode === "polygon" ? "none" : "polygon")}
            >
              Draw polygon
            </button>
          </div>
        }
      >
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div className="row">
            <div className="field">
              <label className="field-label" htmlFor="map-start">Start</label>
              <input
                id="map-start"
                className="input"
                type="date"
                style={{ width: 150 }}
                value={range.start ?? ""}
                min={catalog?.min_date ?? undefined}
                max={catalog?.max_date ?? undefined}
                onChange={(event) => setRange({ start: event.target.value || null, end: range.end })}
              />
            </div>
            <div className="field">
              <label className="field-label" htmlFor="map-end">End</label>
              <input
                id="map-end"
                className="input"
                type="date"
                style={{ width: 150 }}
                value={range.end ?? ""}
                min={catalog?.min_date ?? undefined}
                max={catalog?.max_date ?? undefined}
                onChange={(event) => setRange({ start: range.start, end: event.target.value || null })}
              />
            </div>
            <div className="row" style={{ alignSelf: "flex-end", paddingBottom: 2 }}>
              {quickRanges.map((quick) => (
                <button
                  key={quick.label}
                  className="btn btn-ghost btn-sm"
                  type="button"
                  onClick={() => setRange({ start: quick.start, end: quick.end })}
                >
                  {quick.label}
                </button>
              ))}
            </div>
          </div>

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
      </Panel>

      {cellsQuery.loading && <Loading label="Loading activity grid…" />}
      {cellsQuery.error && <ErrorBox message={cellsQuery.error} onRetry={cellsQuery.reload} />}

      {cellsQuery.data && (
        <>
          <div className="mt-14">
            <MapView
              aoi={aoi}
              cells={cells}
              maxTotal={maxTotal}
              sensors={sensors}
              drawMode={drawMode}
              onDraw={(area) => {
                setDrawMode("none");
                setAoi({
                  bbox: area.bbox,
                  polygon: area.polygon,
                  name: area.polygon ? "Drawn polygon" : "Drawn box",
                  region_id: null,
                });
              }}
              onDrawCancel={() => setDrawMode("none")}
            />
          </div>

          <div className="grid grid-4 mt-14">
            <div className="panel stat">
              <div className="stat-label">Grid cells active</div>
              <div className="stat-value">{formatNumber(cells.length)}</div>
              <div className="stat-note">of {formatNumber(cellsQuery.data.count)} in view</div>
            </div>
            <div className="panel stat">
              <div className="stat-label">Detections in view</div>
              <div className="stat-value">{formatNumber(summary.total)}</div>
              <div className="stat-note">
                {cellsQuery.data.period.start} → {cellsQuery.data.period.end}
              </div>
            </div>
            <div className="panel stat">
              <div className="stat-label">Peak cell</div>
              <div className="stat-value">{formatNumber(maxTotal)}</div>
              <div className="stat-note">detections in one 0.25° cell</div>
            </div>
            <div className="panel stat">
              <div className="stat-label">Harmonisation</div>
              <div className="stat-value" style={{ fontSize: 15 }}>
                {cellsQuery.data.calibration.calibrated ? "Calibrated" : "Coverage-normalised"}
              </div>
              <div className="stat-note">{cellsQuery.data.calibration.status.replace(/_/g, " ")}</div>
            </div>
          </div>

          <div className="grid grid-2 mt-14">
            <Panel title="Sensor split in this view">
              <div className="col">
                {Object.entries(summary.bySensor)
                  .sort((a, b) => b[1] - a[1])
                  .map(([sensor, count]) => {
                    const share = summary.total ? count / summary.total : 0;
                    return (
                      <div key={sensor} className="col" style={{ gap: 4 }}>
                        <div className="spread" style={{ fontSize: 12.5 }}>
                          <span className="row" style={{ gap: 6 }}>
                            <i style={{ width: 9, height: 9, borderRadius: 2, background: sensorColour(sensor), display: "inline-block" }} />
                            {sensorLabel(sensor)}
                          </span>
                          <span className="tnum">{formatNumber(count)} · {Math.round(share * 100)}%</span>
                        </div>
                        <div style={{ height: 4, background: "var(--panel-3)", borderRadius: 2 }}>
                          <div style={{ width: `${share * 100}%`, height: 4, borderRadius: 2, background: sensorColour(sensor) }} />
                        </div>
                      </div>
                    );
                  })}
                {Object.keys(summary.bySensor).length === 0 && <div className="empty">No detections in this selection.</div>}
              </div>
            </Panel>

            <Panel title="Reading this map correctly">
              <ul className="prose" style={{ margin: 0, paddingLeft: 18 }}>
                <li>Circle size and colour both encode detections per 0.25° cell — larger, brighter means more detections.</li>
                <li>Cells are aggregated over the whole selected period; a cell does not mean a fire is burning now.</li>
                <li>Blank areas may be unobserved rather than fire-free: cloud cover suppresses detections.</li>
                <li>Detections may be agricultural burning, industrial flares or volcanic heat, not only wildfires.</li>
              </ul>
              <div className="row mt-14">
                <Badge tone="warn">not an emergency alert</Badge>
                <Badge tone="info">{cellsQuery.data.grid_deg}° grid</Badge>
              </div>
            </Panel>
          </div>

          {cells.length > 0 && (
            <Panel className="mt-14" title="Highest-activity cells" subtitle="Top 12 cells by detection count">
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Latitude</th>
                      <th>Longitude</th>
                      <th className="num">Detections</th>
                      <th className="num">FRP (MW)</th>
                      <th>Dominant sensor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cells.slice(0, 12).map((cell) => {
                      const dominant = Object.entries(cell.per_sensor).sort((a, b) => b[1] - a[1])[0];
                      return (
                        <tr key={`${cell.lat}-${cell.lon}`}>
                          <td className="mono">{cell.lat.toFixed(2)}</td>
                          <td className="mono">{cell.lon.toFixed(2)}</td>
                          <td className="num">{formatNumber(cell.total)}</td>
                          <td className="num">{formatNumber(cell.frp)}</td>
                          <td>{dominant ? sensorLabel(dominant[0]) : "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}

          {!cellsQuery.data.calibration.calibrated && (
            <InfoNote tone="warn">
              <strong>Sensors are not calibrated for this record yet.</strong> The map shows coverage-normalised
              counts with equal weights. {cellsQuery.data.calibration.notes[0]}
            </InfoNote>
          )}
        </>
      )}
    </>
  );
}
