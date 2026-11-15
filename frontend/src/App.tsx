/** Application shell: navigation, area/date context bar, page routing. */

import React, { useEffect, useMemo, useState } from "react";
import { AreaPanel } from "./components/AreaPanel";
import { Badge } from "./components/ui";
import { formatDate } from "./format";
import { useApp } from "./state";
import { OverviewPage } from "./pages/Overview";
import { MapPage } from "./pages/MapPage";
import { CalendarPage } from "./pages/CalendarPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { ComparePage } from "./pages/ComparePage";
import { AnomaliesPage } from "./pages/AnomaliesPage";
import { ExplorerPage } from "./pages/ExplorerPage";
import { MethodologyPage } from "./pages/MethodologyPage";

export type Route =
  | "overview" | "map" | "calendar" | "analytics"
  | "compare" | "anomalies" | "explorer" | "methodology";

const NAV: { route: Route; label: string; icon: React.ReactNode; group: string }[] = [
  { route: "overview", label: "Overview", group: "Mission", icon: <IconGrid /> },
  { route: "calendar", label: "Burning Calendar", group: "Analysis", icon: <IconCalendar /> },
  { route: "map", label: "Fire Map", group: "Analysis", icon: <IconMap /> },
  { route: "analytics", label: "Historical Analytics", group: "Analysis", icon: <IconChart /> },
  { route: "compare", label: "MODIS vs VIIRS", group: "Science", icon: <IconCompare /> },
  { route: "anomalies", label: "Anomaly Explorer", group: "Science", icon: <IconAlert /> },
  { route: "explorer", label: "Data Explorer", group: "Science", icon: <IconTable /> },
  { route: "methodology", label: "Methodology", group: "Reference", icon: <IconBook /> },
];

function parseHash(): Route {
  const raw = window.location.hash.replace(/^#\/?/, "").split("?")[0];
  const found = NAV.find((item) => item.route === raw);
  return found ? found.route : "overview";
}

export function App() {
  const { aoi, range, setRange, catalog, catalogError, query } = useApp();
  const [route, setRoute] = useState<Route>(parseHash);
  const [areaOpen, setAreaOpen] = useState(false);
  const [drawRequest, setDrawRequest] = useState(false);

  useEffect(() => {
    const onHash = () => setRoute(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const go = (next: Route) => {
    window.location.hash = `#/${next}`;
    setRoute(next);
  };

  const groups = useMemo(() => {
    const map = new Map<string, typeof NAV>();
    for (const item of NAV) {
      if (!map.has(item.group)) map.set(item.group, []);
      map.get(item.group)!.push(item);
    }
    return [...map.entries()];
  }, []);

  const areaLabel = aoi.name || "Selected area";

  const statusTone = catalogError ? "err" : catalog?.ready ? "" : "warn";
  const statusText = catalogError
    ? "Server unreachable"
    : catalog?.ready
      ? `${catalog.detections.toLocaleString()} detections loaded`
      : "No data loaded";

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 3c2.5 3.2 1.2 5-0.4 6.4C10 10.9 8.5 12.6 9.4 15c.5-1.6 1.7-2.3 2.6-2.9.2 1.6 1.1 2.4 2.1 3.3 1.2 1.1 2.2 2.4 1.4 4.4-.6 1.5-2 2.4-3.6 2.4-3.1 0-5.6-2.3-5.6-5.6 0-4.3 3.2-6.5 5.7-13.6z" fill="#1a0d02" />
            </svg>
          </div>
          <div>
            <div className="brand-name">FIRETRACK</div>
            <div className="brand-sub">Burning activity intelligence</div>
          </div>
        </div>

        {groups.map(([group, items]) => (
          <React.Fragment key={group}>
            <div className="nav-group">{group}</div>
            {items.map((item) => (
              <button
                key={item.route}
                type="button"
                className={`nav-item${route === item.route ? " active" : ""}`}
                onClick={() => go(item.route)}
                aria-current={route === item.route ? "page" : undefined}
              >
                <span className="nav-icon">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </React.Fragment>
        ))}

        <div className="nav-foot">
          <div>
            <span className={`dot ${statusTone}`} />
            {statusText}
          </div>
          <div>
            {catalog?.min_date
              ? `${formatDate(catalog.min_date)} → ${formatDate(catalog.max_date)}`
              : "NASA FIRMS"}
          </div>
          <div className="faint">Not an official alerting system.</div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <button type="button" className="aoi-chip" onClick={() => setAreaOpen(true)}>
            <IconPin />
            <strong>{areaLabel}</strong>
            <span>· change area</span>
          </button>

          <div className="row" style={{ gap: 6 }}>
            <Badge tone="info">
              {range.start && range.end
                ? `${formatDate(range.start)} → ${formatDate(range.end)}`
                : "full record"}
            </Badge>
            <button
              type="button"
              className="btn btn-sm btn-ghost"
              onClick={() =>
                setRange({ start: catalog?.min_date ?? null, end: catalog?.max_date ?? null })
              }
              title="Reset the date range to the whole loaded record"
            >
              ⟲ full record
            </button>
            <Badge>
              {query.confidence === "all" ? "all confidence" : `${query.confidence} confidence`}
            </Badge>
          </div>

          <div className="topbar-spacer" />

          {catalog?.map_key_configured ? (
            <Badge tone="ok">FIRMS key configured</Badge>
          ) : (
            <Badge tone="warn">snapshot data</Badge>
          )}
          <button className="btn btn-sm btn-primary" type="button" onClick={() => setAreaOpen(true)}>
            Select area
          </button>
        </header>

        <main className="page">
          {route === "overview" && <OverviewPage onNavigate={go} />}
          {route === "map" && (
            <MapPage
              drawRequest={drawRequest}
              onDrawHandled={() => setDrawRequest(false)}
            />
          )}
          {route === "calendar" && <CalendarPage />}
          {route === "analytics" && <AnalyticsPage />}
          {route === "compare" && <ComparePage />}
          {route === "anomalies" && <AnomaliesPage />}
          {route === "explorer" && <ExplorerPage />}
          {route === "methodology" && <MethodologyPage />}
        </main>
      </div>

      {areaOpen && (
        <AreaPanel
          onClose={() => setAreaOpen(false)}
          onRequestDraw={() => {
            setAreaOpen(false);
            setDrawRequest(true);
            go("map");
          }}
        />
      )}
    </div>
  );
}

/* ---------- icons -------------------------------------------------------- */

function IconGrid() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
      <rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  );
}
function IconCalendar() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
      <rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" />
    </svg>
  );
}
function IconMap() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
      <path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z" /><path d="M9 4v14M15 6v14" />
    </svg>
  );
}
function IconChart() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
      <path d="M4 20V4M4 20h16" /><path d="M8 16l4-6 3 3 4-7" />
    </svg>
  );
}
function IconCompare() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
      <path d="M4 8h13l-3-3M20 16H7l3 3" />
    </svg>
  );
}
function IconAlert() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
      <path d="M12 3 2 20h20L12 3z" /><path d="M12 9v5M12 17.2v.1" />
    </svg>
  );
}
function IconTable() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
      <rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 9h18M9 9v11M15 9v11" />
    </svg>
  );
}
function IconBook() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5v-15z" /><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20" />
    </svg>
  );
}
function IconPin() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
      <path d="M12 21s7-6.1 7-11a7 7 0 1 0-14 0c0 4.9 7 11 7 11z" /><circle cx="12" cy="10" r="2.4" />
    </svg>
  );
}
