/** Area-of-interest selector: presets, search, coordinates, saved areas. */

import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useApp } from "../state";
import type { Region, SearchResult } from "../types";
import { Badge, InfoNote } from "./ui";

type Tab = "regions" | "search" | "coords";

const SAVED_KEY = "firetrack.savedAreas";

export interface SavedArea {
  id: string;
  name: string;
  bbox: [number, number, number, number];
  polygon: [number, number][] | null;
  savedAt: string;
}

export function loadSavedAreas(): SavedArea[] {
  try {
    return JSON.parse(localStorage.getItem(SAVED_KEY) ?? "[]") as SavedArea[];
  } catch {
    return [];
  }
}

export function AreaPanel({ onClose, onRequestDraw }: {
  onClose: () => void;
  onRequestDraw: () => void;
}) {
  const { aoi, setAoi, catalog } = useApp();
  const [tab, setTab] = useState<Tab>("regions");
  const [regions, setRegions] = useState<Region[]>([]);
  const [term, setTerm] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [lat, setLat] = useState("9.0");
  const [lon, setLon] = useState("27.0");
  const [radius, setRadius] = useState("150");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<SavedArea[]>(loadSavedAreas());

  useEffect(() => {
    api.regions().then((data) => setRegions(data.regions)).catch(() => setRegions([]));
  }, []);

  useEffect(() => {
    if (tab !== "search" || term.trim().length < 2) {
      setResults([]);
      return;
    }
    let cancelled = false;
    setSearching(true);
    const timer = setTimeout(() => {
      api
        .search(term.trim())
        .then((data) => {
          if (!cancelled) setResults(data.results);
        })
        .catch(() => {
          if (!cancelled) setResults([]);
        })
        .finally(() => {
          if (!cancelled) setSearching(false);
        });
    }, 180);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [term, tab]);

  const applyBBox = (
    bbox: [number, number, number, number],
    name: string,
    extra: { region_id?: string; polygon?: [number, number][] | null } = {},
  ) => {
    setError(null);
    setAoi({ bbox, name, polygon: extra.polygon ?? null, region_id: extra.region_id ?? null });
    onClose();
  };

  const applyCoords = () => {
    const latitude = Number(lat);
    const longitude = Number(lon);
    const radiusKm = Number(radius);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      setError("Enter numeric latitude and longitude.");
      return;
    }
    if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180) {
      setError("Latitude must be within ±90 and longitude within ±180.");
      return;
    }
    if (!Number.isFinite(radiusKm) || radiusKm <= 0) {
      setError("Enter a radius greater than zero kilometres.");
      return;
    }
    const dLat = radiusKm / 111.195;
    const dLon = radiusKm / (111.195 * Math.max(0.05, Math.cos((latitude * Math.PI) / 180)));
    applyBBox(
      [
        Math.max(-180, longitude - dLon),
        Math.max(-90, latitude - dLat),
        Math.min(180, longitude + dLon),
        Math.min(90, latitude + dLat),
      ],
      `${latitude.toFixed(2)}, ${longitude.toFixed(2)} · ${radiusKm} km`,
    );
  };

  const saveCurrent = () => {
    if (!aoi.bbox) return;
    const entry: SavedArea = {
      id: `saved-${Date.now()}`,
      name: aoi.name || "Saved area",
      bbox: aoi.bbox as [number, number, number, number],
      polygon: (aoi.polygon as [number, number][] | null) ?? null,
      savedAt: new Date().toISOString(),
    };
    const next = [entry, ...loadSavedAreas()].slice(0, 8);
    localStorage.setItem(SAVED_KEY, JSON.stringify(next));
    setSaved(next);
  };

  const removeSaved = (id: string) => {
    const next = loadSavedAreas().filter((item) => item.id !== id);
    localStorage.setItem(SAVED_KEY, JSON.stringify(next));
    setSaved(next);
  };

  const dataNote = useMemo(() => {
    if (!catalog?.min_date) return "No records loaded.";
    return `Available records: ${catalog.min_date} → ${catalog.max_date} (${catalog.detections.toLocaleString()} detections)`;
  }, [catalog]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Select an area of interest"
      style={{
        position: "fixed", inset: 0, zIndex: 3000,
        background: "rgba(3, 6, 12, 0.78)", backdropFilter: "blur(3px)",
        display: "grid", placeItems: "center", padding: 16, overflowY: "auto",
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="panel" style={{ width: "min(760px, 100%)", maxHeight: "90vh", overflow: "auto" }}>
        <header className="panel-head" style={{ paddingBottom: 10 }}>
          <div>
            <h2 className="panel-title">Select an area of interest</h2>
            <p className="panel-sub">Every map, calendar and statistic follows this selection.</p>
          </div>
          <div className="panel-actions">
            <button className="btn btn-ghost btn-sm" onClick={onClose} type="button">Close</button>
          </div>
        </header>

        <div className="panel-body">
          <div className="row" style={{ marginBottom: 12 }}>
            <div className="segmented" role="tablist">
              {([
                ["regions", "Regions"],
                ["search", "Search"],
                ["coords", "Coordinates"],
              ] as [Tab, string][]).map(([key, label]) => (
                <button
                  key={key} type="button" role="tab" aria-selected={tab === key}
                  className={tab === key ? "on" : ""} onClick={() => setTab(key)}
                >
                  {label}
                </button>
              ))}
            </div>
            <button className="btn btn-sm" type="button" onClick={onRequestDraw}>
              Draw on map →
            </button>
            <button className="btn btn-ghost btn-sm" type="button" onClick={saveCurrent}>
              Save current area
            </button>
          </div>

          {error && <InfoNote tone="warn">{error}</InfoNote>}

          {tab === "regions" && (
            <div className="grid grid-2" style={{ gap: 8 }}>
              {regions.map((region) => (
                <button
                  key={region.id}
                  type="button"
                  className="panel"
                  onClick={() => applyBBox(region.bbox, region.name, { region_id: region.id })}
                  style={{
                    textAlign: "left", padding: "10px 12px", cursor: "pointer",
                    borderColor: aoi.region_id === region.id ? "var(--accent-line)" : undefined,
                    background: aoi.region_id === region.id ? "var(--accent-soft)" : undefined,
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{region.name}</div>
                  <div className="note" style={{ marginTop: 2 }}>{region.biome}</div>
                </button>
              ))}
            </div>
          )}

          {tab === "search" && (
            <div className="col">
              <div className="field">
                <label className="field-label" htmlFor="area-search">Place name</label>
                <input
                  id="area-search"
                  className="input"
                  placeholder="e.g. Sudan, Khartoum, Amazon, Australia…"
                  value={term}
                  onChange={(event) => setTerm(event.target.value)}
                  autoFocus
                />
              </div>
              {searching && <div className="note">Searching…</div>}
              <div className="col" style={{ gap: 6 }}>
                {results.map((result) => (
                  <button
                    key={result.id}
                    type="button"
                    className="row"
                    onClick={() => applyBBox(result.bbox, result.name)}
                    style={{
                      justifyContent: "space-between", background: "var(--panel-2)",
                      border: "1px solid var(--border)", borderRadius: 8, padding: "8px 10px",
                      color: "var(--text)", cursor: "pointer", font: "inherit", textAlign: "left",
                    }}
                  >
                    <span>
                      <strong style={{ fontSize: 13 }}>{result.name}</strong>
                      <span className="faint" style={{ marginLeft: 8, fontSize: 12 }}>{result.subtitle}</span>
                    </span>
                    <Badge>{result.kind}</Badge>
                  </button>
                ))}
                {!searching && term.trim().length >= 2 && results.length === 0 && (
                  <div className="note">No match in the offline gazetteer. Try coordinates or draw on the map.</div>
                )}
              </div>
            </div>
          )}

          {tab === "coords" && (
            <div className="col">
              <div className="grid grid-3" style={{ gap: 10 }}>
                <div className="field">
                  <label className="field-label" htmlFor="lat">Latitude</label>
                  <input id="lat" className="input" value={lat} onChange={(e) => setLat(e.target.value)} />
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="lon">Longitude</label>
                  <input id="lon" className="input" value={lon} onChange={(e) => setLon(e.target.value)} />
                </div>
                <div className="field">
                  <label className="field-label" htmlFor="radius">Radius (km)</label>
                  <input id="radius" className="input" value={radius} onChange={(e) => setRadius(e.target.value)} />
                </div>
              </div>
              <div>
                <button className="btn btn-primary" type="button" onClick={applyCoords}>
                  Use this area
                </button>
              </div>
            </div>
          )}

          {saved.length > 0 && (
            <div className="mt-14">
              <div className="field-label" style={{ marginBottom: 6 }}>Saved areas</div>
              <div className="row">
                {saved.map((item) => (
                  <span key={item.id} className="row" style={{ gap: 2 }}>
                    <button
                      className="btn btn-sm" type="button"
                      onClick={() => applyBBox(item.bbox, item.name, { polygon: item.polygon })}
                    >
                      {item.name}
                    </button>
                    <button
                      className="btn btn-ghost btn-sm btn-icon" type="button"
                      aria-label={`Remove ${item.name}`}
                      onClick={() => removeSaved(item.id)}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}

          <p className="note mt-14">{dataNote}</p>
        </div>
      </div>
    </div>
  );
}
