/** Data Explorer: inspect, filter and export the underlying hotspot records. */

import React, { useEffect, useMemo, useRef, useState } from "react";
import { api, downloadExport } from "../api";
import { Badge, ErrorBox, InfoNote, Loading, Panel, Segmented } from "../components/ui";
import { formatNumber, formatTime, sensorLabel } from "../format";
import { useApp, useAsync } from "../state";

const PAGE_SIZE = 50;

export function ExplorerPage() {
  const { query, catalog, range } = useApp();
  const [order, setOrder] = useState<"recent" | "frp" | "confidence">("recent");
  const [frpMin, setFrpMin] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<
    { ok: boolean; message: string; detail?: string } | null
  >(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const handleUpload = async (file: File) => {
    setImporting(true);
    setImportResult(null);
    try {
      const result = await api.uploadArchive(file);
      const detail =
        `${formatNumber(result.rows_kept)} detections kept · ` +
        `${formatNumber(result.rows_duplicate)} duplicates skipped · ` +
        `${formatNumber(result.rows_rejected)} rejected` +
        (result.min_date ? ` · ${result.min_date} → ${result.max_date}` : "");
      setImportResult({
        ok: true,
        message: result.message ?? `Imported ${file.name}.`,
        detail,
      });
      if (fileRef.current) fileRef.current.value = "";
    } catch (error) {
      setImportResult({ ok: false, message: (error as Error).message });
    } finally {
      setImporting(false);
    }
  };

  const frpValue = frpMin.trim() === "" ? null : Number(frpMin);
  const searchValue = search.trim() === "" ? null : search.trim();

  const detections = useAsync(
    () =>
      api.detections({
        ...query,
        limit: PAGE_SIZE,
        offset,
        order,
        frp_min: Number.isFinite(frpValue as number) ? frpValue : null,
        search: searchValue,
      }),
    [query, offset, order, frpValue, searchValue],
  );

  useEffect(() => {
    setOffset(0);
  }, [query, order, frpValue, searchValue]);

  const rows = detections.data?.rows ?? [];
  const total = detections.data?.total ?? 0;
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const exportBody = useMemo(
    () => ({
      ...query,
      frp_min: Number.isFinite(frpValue as number) ? frpValue : null,
      search: searchValue,
    }),
    [query, frpValue, searchValue],
  );

  const runExport = async (kind: "csv" | "analytics" | "report") => {
    setBusy(kind);
    setExportError(null);
    try {
      if (kind === "csv") {
        await downloadExport(
          "/api/export/detections.csv",
          exportBody,
          `firetrack_detections_${range.start ?? "start"}_${range.end ?? "end"}.csv`,
        );
      } else if (kind === "analytics") {
        await downloadExport(
          "/api/export/analytics.csv",
          query,
          `firetrack_daily_${range.start ?? "start"}_${range.end ?? "end"}.csv`,
        );
      } else {
        const latest = catalog?.max_date ?? new Date().toISOString().slice(0, 10);
        await downloadExport(
          "/api/export/report.html",
          { ...query, year: Number(latest.slice(0, 4)), month: Number(latest.slice(5, 7)) },
          "firetrack_report.html",
        );
      }
    } catch (error) {
      setExportError((error as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <div className="page-head">
        <div className="eyebrow">Data explorer</div>
        <h1 className="page-title">Hotspot records &amp; exports</h1>
        <p className="page-sub">
          Every record exactly as NASA delivered it — coordinates, acquisition time, confidence, FRP,
          brightness temperatures, processing level and source file. Filters apply to the table and the
          CSV export alike.
        </p>
      </div>

      <Panel
        title="Import a NASA FIRMS archive file"
        subtitle="CSV, CSV.GZ or ZIP from the FIRMS Archive Download — science-quality (standard processing) data"
      >
        <div className="grid grid-2">
          <div className="col">
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.gz,.zip"
              className="input"
              disabled={importing}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void handleUpload(file);
              }}
              aria-label="Choose a FIRMS archive file"
            />
            <div className="note">
              This is the official route to standard-processing data for older dates without an API key.
              Files are copied into <code>data/raw/archive</code>, every record keeps its source file
              name, and duplicate rows are skipped automatically.
            </div>
          </div>
          <div className="col">
            {importing && (
              <div className="row">
                <span className="spinner" aria-hidden="true" />
                <span className="note">Reading and validating the archive…</span>
              </div>
            )}
            {importResult && (
              <div className={`callout ${importResult.ok ? "info" : "warn"}`}>
                <strong>{importResult.message}</strong>
                {importResult.detail && <div className="note mt-8">{importResult.detail}</div>}
                {importResult.ok && (
                  <button
                    className="btn btn-sm mt-8"
                    type="button"
                    onClick={() => window.location.reload()}
                  >
                    Reload to use the new record
                  </button>
                )}
              </div>
            )}
            {!importing && !importResult && (
              <div className="note">
                Nothing imported yet. A typical FIRMS archive ZIP for a region and year is a few
                megabytes; the import limit is 500 MB per file.
              </div>
            )}
          </div>
        </div>
      </Panel>

      <Panel className="mt-14" title="Filters">
        <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
          <div className="field">
            <label className="field-label" htmlFor="frp">Minimum FRP (MW)</label>
            <input
              id="frp"
              className="input"
              style={{ width: 130 }}
              inputMode="decimal"
              placeholder="any"
              value={frpMin}
              onChange={(event) => setFrpMin(event.target.value)}
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="search">Search</label>
            <input
              id="search"
              className="input"
              style={{ width: 190 }}
              placeholder="platform, sensor or date"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div className="field">
            <span className="field-label">Order</span>
            <Segmented
              ariaLabel="Sort order"
              value={order}
              onChange={(next) => setOrder(next)}
              options={[
                { value: "recent", label: "Most recent" },
                { value: "frp", label: "Highest FRP" },
                { value: "confidence", label: "Confidence" },
              ]}
            />
          </div>
          <div className="topbar-spacer" />
          <div className="row">
            <button className="btn btn-sm" type="button" disabled={busy !== null} onClick={() => runExport("csv")}>
              {busy === "csv" ? "Preparing…" : "Download detections CSV"}
            </button>
            <button className="btn btn-sm" type="button" disabled={busy !== null} onClick={() => runExport("analytics")}>
              {busy === "analytics" ? "Preparing…" : "Download daily analytics"}
            </button>
            <button className="btn btn-sm btn-primary" type="button" disabled={busy !== null} onClick={() => runExport("report")}>
              {busy === "report" ? "Preparing…" : "Download report"}
            </button>
          </div>
        </div>
        {exportError && <div className="errorbox mt-8">{exportError}</div>}
        <div className="note mt-8">
          The detections CSV contains every matching record (not just this page) and preserves the
          original source fields. The report is a self-contained HTML file with the area, period,
          sources, comparisons, charts, methodology and limitations.
        </div>
      </Panel>

      {detections.loading && <Loading label="Querying records…" />}
      {detections.error && <ErrorBox message={detections.error} onRetry={detections.reload} />}

      {detections.data && (
        <>
          <Panel
            className="mt-14"
            title={`${formatNumber(total)} matching records`}
            subtitle={
              detections.data.truncated
                ? "Scan limit reached for this area; narrow the date range for exact totals."
                : `Period ${detections.data.period.start} → ${detections.data.period.end}`
            }
            actions={<Badge tone="info">{detections.data.context.unit}</Badge>}
          >
            <div className="table-wrap" style={{ maxHeight: 520, overflow: "auto" }}>
              <table className="data">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Time</th>
                    <th>Sensor</th>
                    <th>Platform</th>
                    <th className="num">Lat</th>
                    <th className="num">Lon</th>
                    <th className="num">Confidence</th>
                    <th className="num">FRP (MW)</th>
                    <th>Day/night</th>
                    <th>Processing</th>
                    <th>Source file</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id}>
                      <td className="mono">{row.acq_date}</td>
                      <td className="mono">{formatTime(row.acq_time)}</td>
                      <td>{sensorLabel(row.sensor)}</td>
                      <td>{row.platform}</td>
                      <td className="num mono">{row.lat.toFixed(4)}</td>
                      <td className="num mono">{row.lon.toFixed(4)}</td>
                      <td className="num">
                        {row.confidence ?? "—"}
                        <span className="faint"> {row.confidence_class ?? ""}</span>
                      </td>
                      <td className="num">{row.frp === null ? "—" : row.frp.toFixed(1)}</td>
                      <td>{row.daynight === "D" ? "day" : row.daynight === "N" ? "night" : "—"}</td>
                      <td>
                        <Badge tone={row.processing === "NRT" ? "warn" : "ok"}>{row.processing}</Badge>
                      </td>
                      <td className="mono faint" style={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {row.source_file}
                      </td>
                    </tr>
                  ))}
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={11} className="faint">No records match these filters.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="row mt-14" style={{ justifyContent: "space-between" }}>
              <span className="note">
                Page {page} of {formatNumber(pages)} · {formatNumber(rows.length)} rows shown
              </span>
              <div className="row">
                <button
                  className="btn btn-sm"
                  type="button"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  ← Previous
                </button>
                <button
                  className="btn btn-sm"
                  type="button"
                  disabled={offset + PAGE_SIZE >= total}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  Next →
                </button>
              </div>
            </div>
          </Panel>

          <div className="grid grid-2 mt-14">
            <Panel title="Field definitions">
              <div className="kv">
                <div className="kv-row"><span className="kv-key">confidence</span><span className="kv-val">MODIS 0–100; VIIRS mapped 25/65/90</span></div>
                <div className="kv-row"><span className="kv-key">frp</span><span className="kv-val">Fire radiative power, MW</span></div>
                <div className="kv-row"><span className="kv-key">brightness</span><span className="kv-val">MODIS band 21/22 or VIIRS I4 brightness temperature (K)</span></div>
                <div className="kv-row"><span className="kv-key">processing</span><span className="kv-val">NRT provisional vs SP standard processing</span></div>
                <div className="kv-row"><span className="kv-key">acq_time</span><span className="kv-val">UTC, HHMM</span></div>
              </div>
            </Panel>

            <Panel title="Provenance">
              <div className="kv">
                <div className="kv-row"><span className="kv-key">Provider</span><span className="kv-val">NASA FIRMS (EOSDIS / LANCE)</span></div>
                <div className="kv-row"><span className="kv-key">Records loaded</span><span className="kv-val">{formatNumber(catalog?.detections ?? 0)}</span></div>
                <div className="kv-row"><span className="kv-key">Grid</span><span className="kv-val">{catalog?.grid_deg}°</span></div>
                {catalog?.batches?.slice(0, 3).map((batch) => (
                  <div className="kv-row" key={batch.id}>
                    <span className="kv-key">{batch.kind}</span>
                    <span className="kv-val">{formatNumber(batch.rows_kept)} rows · {batch.quality}</span>
                  </div>
                ))}
              </div>
            </Panel>
          </div>

          <InfoNote tone="info">
            Records are <Badge tone={catalog?.batches?.every((b) => b.quality === "science") ? "ok" : "warn"}>
              {catalog?.batches?.every((b) => b.quality === "science") ? "science quality" : "partly provisional"}
            </Badge>{" "}
            data. Near-real-time records are replaced by standard processing roughly five months later;
            re-import the archive to upgrade them.
          </InfoNote>
        </>
      )}
    </>
  );
}
