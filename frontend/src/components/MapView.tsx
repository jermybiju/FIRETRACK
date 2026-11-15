/** Leaflet map: harmonised activity grid, per-sensor layers and area drawing. */

import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { AOI } from "../types";
import type { MapCell } from "../types";
import { heatColor, sensorColour, sensorShort } from "../format";

export type DrawMode = "none" | "rect" | "polygon";

export interface DrawnArea {
  bbox: [number, number, number, number];
  polygon: [number, number][] | null;
}

const BASEMAPS = {
  dark: {
    label: "Dark",
    // CARTO's dark tiles now require an API key and serve a watermarked tile
    // without one, so the default basemap is Esri's key-free dark canvas.
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    attribution: "Tiles &copy; Esri &mdash; Esri, DeLorme, HERE",
    subdomains: "",
    maxZoom: 16,
  },
  imagery: {
    label: "Satellite",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: "Tiles &copy; Esri &mdash; Esri, Maxar, Earthstar Geographics",
    subdomains: "",
    maxZoom: 18,
  },
  blueMarble: {
    label: "NASA Blue Marble",
    url:
      "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/" +
      "default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
    attribution: "Imagery &copy; NASA EOSDIS GIBS",
    subdomains: "abc",
    maxZoom: 8,
  },
} as const;

type BasemapKey = keyof typeof BASEMAPS;

export function MapView({
  aoi, cells, maxTotal, sensors, drawMode, onDraw, onDrawCancel, height,
}: {
  aoi: AOI;
  cells: MapCell[];
  maxTotal: number;
  sensors: string[];
  drawMode: DrawMode;
  onDraw: (area: DrawnArea) => void;
  onDrawCancel: () => void;
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const baseRef = useRef<L.TileLayer | null>(null);
  const overlayRef = useRef<L.LayerGroup | null>(null);
  const aoiRef = useRef<L.LayerGroup | null>(null);
  const drawRef = useRef<L.LayerGroup | null>(null);
  const [basemap, setBasemap] = useState<BasemapKey>("dark");
  const [ready, setReady] = useState(false);

  // Initialise once.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      zoomControl: true,
      attributionControl: true,
      preferCanvas: true,
      worldCopyJump: true,
    }).setView([8, 24], 4);
    L.control.scale({ imperial: false, position: "bottomright" }).addTo(map);

    const config = BASEMAPS.dark;
    baseRef.current = L.tileLayer(config.url, {
      attribution: config.attribution,
      subdomains: config.subdomains as unknown as string,
      maxZoom: config.maxZoom,
    }).addTo(map);

    overlayRef.current = L.layerGroup().addTo(map);
    aoiRef.current = L.layerGroup().addTo(map);
    drawRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    setReady(true);

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Basemap switch.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !baseRef.current) return;
    const config = BASEMAPS[basemap];
    baseRef.current.setUrl(config.url);
    baseRef.current.options.subdomains = config.subdomains as unknown as string;
    baseRef.current.options.maxZoom = config.maxZoom;
    (baseRef.current as L.TileLayer).redraw();
  }, [basemap]);

  // Activity grid.
  useEffect(() => {
    const map = mapRef.current;
    const overlay = overlayRef.current;
    if (!map || !overlay || !ready) return;
    overlay.clearLayers();
    const max = maxTotal || 1;
    const visible = cells.filter((cell) => {
      if (sensors.length === 0) return true;
      return Object.keys(cell.per_sensor).some((key) => sensors.includes(key));
    });
    const limit = 4000;
    visible.slice(0, limit).forEach((cell) => {
      const ratio = Math.sqrt(cell.total / max);
      const colour = heatColor(cell.total, max);
      const radius = 3 + ratio * 14;
      const marker = L.circleMarker([cell.lat, cell.lon], {
        radius,
        color: colour,
        weight: 0.6,
        opacity: 0.75,
        fillColor: colour,
        fillOpacity: 0.42,
      });
      const parts = Object.entries(cell.per_sensor)
        .sort((a, b) => b[1] - a[1])
        .map(([sensor, count]) =>
          `${sensorShort(sensor)}: ${count.toLocaleString()}` +
          ` <span style="opacity:.65">(${(cell.frp_by_sensor?.[sensor] ?? 0).toLocaleString()} MW)</span>`,
        )
        .join("<br>");
      marker.bindPopup(
        `<h4>${cell.total.toLocaleString()} detections</h4>` +
          `<div style="color:#9fb0c7">${parts}</div>` +
          `<div style="color:#6b7f99;margin-top:4px">FRP sum ${cell.frp.toLocaleString()} MW ` +
          `&mdash; raw, not harmonised</div>`,
      );
      marker.addTo(overlay);
    });
  }, [cells, maxTotal, sensors, ready]);

  // Area outline.
  useEffect(() => {
    const map = mapRef.current;
    const layer = aoiRef.current;
    if (!map || !layer || !ready) return;
    layer.clearLayers();
    if (aoi.polygon && aoi.polygon.length > 2) {
      const ring = aoi.polygon.map(([lon, lat]) => [lat, lon] as [number, number]);
      L.polygon(ring, { color: "#f97316", weight: 2, fillOpacity: 0.06, dashArray: "5 4" }).addTo(layer);
      map.fitBounds(L.latLngBounds(ring).pad(0.12), { animate: false });
    } else if (aoi.bbox) {
      const [w, s, e, n] = aoi.bbox;
      L.rectangle([[s, w], [n, e]], { color: "#f97316", weight: 2, fillOpacity: 0.06, dashArray: "5 4" })
        .addTo(layer);
      map.fitBounds([[s, w], [n, e]], { animate: false, padding: [12, 12] });
    }
  }, [aoi, ready]);

  // Drawing.
  useEffect(() => {
    const map = mapRef.current;
    const layer = drawRef.current;
    if (!map || !layer || !ready) return;
    layer.clearLayers();

    if (drawMode === "none") {
      map.dragging.enable();
      map.doubleClickZoom.enable();
      map.getContainer().style.cursor = "";
      return;
    }

    map.dragging.disable();
    map.doubleClickZoom.disable();
    map.getContainer().style.cursor = "crosshair";

    if (drawMode === "rect") {
      let start: L.LatLng | null = null;
      let rect: L.Rectangle | null = null;

      const onDown = (event: L.LeafletMouseEvent) => {
        start = event.latlng;
        rect = L.rectangle(L.latLngBounds(start, start), {
          color: "#f97316", weight: 1.5, fillOpacity: 0.12, dashArray: "4 3",
        }).addTo(layer);
      };
      const onMove = (event: L.LeafletMouseEvent) => {
        if (!start || !rect) return;
        rect.setBounds(L.latLngBounds(start, event.latlng));
      };
      const onUp = (event: L.LeafletMouseEvent) => {
        if (!start) return;
        const bounds = L.latLngBounds(start, event.latlng);
        start = null;
        if (bounds.getNorth() - bounds.getSouth() < 0.05 || bounds.getEast() - bounds.getWest() < 0.05) {
          layer.clearLayers();
          return;
        }
        onDraw({
          bbox: [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()],
          polygon: null,
        });
      };

      map.on("mousedown", onDown).on("mousemove", onMove).on("mouseup", onUp);
      return () => {
        map.off("mousedown", onDown).off("mousemove", onMove).off("mouseup", onUp);
      };
    }

    // Polygon drawing
    const points: [number, number][] = [];
    let preview: L.Polyline | null = null;
    const markers: L.CircleMarker[] = [];
    const onClick = (event: L.LeafletMouseEvent) => {
      points.push([event.latlng.lng, event.latlng.lat]);
      markers.push(
        L.circleMarker(event.latlng, {
          radius: 4, color: "#f97316", fillColor: "#f97316", fillOpacity: 1, weight: 1,
        }).addTo(layer),
      );
      if (preview) preview.remove();
      preview = L.polyline(points.map(([lon, lat]) => [lat, lon] as [number, number]), {
        color: "#f97316", weight: 1.5, dashArray: "4 3",
      }).addTo(layer);
    };
    const onDouble = () => {
      if (points.length < 3) {
        layer.clearLayers();
        markers.length = 0;
        points.length = 0;
        return;
      }
      const lats = points.map((p) => p[1]);
      const lons = points.map((p) => p[0]);
      onDraw({
        bbox: [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)],
        polygon: [...points],
      });
      points.length = 0;
    };
    map.on("click", onClick).on("dblclick", onDouble);
    return () => {
      map.off("click", onClick).off("dblclick", onDouble);
    };
  }, [drawMode, onDraw, ready]);

  return (
    <div className="map-shell" style={height ? { height } : undefined}>
      <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />

      {drawMode !== "none" && (
        <div className="map-overlay top-left" style={{ borderColor: "var(--accent-line)" }}>
          <strong style={{ color: "var(--text)" }}>
            {drawMode === "rect" ? "Drag to draw a box" : "Click to add points · double-click to finish"}
          </strong>
          <div className="row" style={{ marginTop: 6 }}>
            <button className="btn btn-sm btn-ghost" type="button" onClick={onDrawCancel}>
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="map-overlay top-right">
        <div className="row" style={{ gap: 6 }}>
          <span className="field-label" style={{ margin: 0 }}>Basemap</span>
          <div className="segmented">
            {(Object.keys(BASEMAPS) as BasemapKey[]).map((key) => (
              <button
                key={key} type="button" className={basemap === key ? "on" : ""}
                aria-pressed={basemap === key} onClick={() => setBasemap(key)}
              >
                {BASEMAPS[key].label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="map-overlay bottom-left">
        <div className="map-status">
          <span><strong style={{ color: "var(--text)" }}>{cells.length.toLocaleString()}</strong> grid cells with detections</span>
          <span>Colour and size: detections per 0.25° cell</span>
        </div>
      </div>
    </div>
  );
}

export function SensorLegend({ sensors }: { sensors: { id: string; label: string }[] }) {
  return (
    <div className="legend">
      {sensors.map((sensor) => (
        <span key={sensor.id} className="legend">
          <i style={{ width: 9, height: 9, borderRadius: "50%", background: sensorColour(sensor.id), display: "inline-block" }} />
          {sensor.label}
        </span>
      ))}
    </div>
  );
}
