/** Global application state: area, date range, filters and data catalogue. */

import React, {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from "react";
import { api, type QueryBody } from "./api";
import type { AOI, Catalog } from "./types";

export interface DateRange {
  start: string | null;
  end: string | null;
}

export interface AppState {
  aoi: AOI;
  setAoi: (aoi: AOI) => void;
  range: DateRange;
  setRange: (range: DateRange) => void;
  confidence: "all" | "nominal" | "high";
  setConfidence: (value: "all" | "nominal" | "high") => void;
  sensors: string[];
  setSensors: (value: string[]) => void;
  catalog: Catalog | null;
  catalogError: string | null;
  refreshCatalog: () => void;
  dataVersion: number;
  query: QueryBody;
}

// The default area is the one with the longest ingested record, so the first
// screen a reviewer sees already has history behind its calendar.
const DEFAULT_AOI: AOI = { region_id: "aegean", name: "Aegean & Anatolia" };

const AppContext = createContext<AppState | null>(null);

function loadStored<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [aoi, setAoiState] = useState<AOI>(() => loadStored("firetrack.aoi", DEFAULT_AOI));
  const [range, setRangeState] = useState<DateRange>(() =>
    loadStored<DateRange>("firetrack.range", { start: null, end: null }),
  );
  const [confidence, setConfidenceState] = useState<"all" | "nominal" | "high">(() =>
    loadStored("firetrack.confidence", "all" as const),
  );
  const [sensors, setSensorsState] = useState<string[]>(() => loadStored<string[]>("firetrack.sensors", []));
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [dataVersion, setDataVersion] = useState(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const refreshCatalog = useCallback(() => {
    api
      .catalog()
      .then((data) => {
        if (!mounted.current) return;
        setCatalog(data);
        setCatalogError(null);
      })
      .catch((error: Error) => {
        if (!mounted.current) return;
        setCatalogError(error.message);
      });
  }, []);

  useEffect(() => {
    refreshCatalog();
  }, [refreshCatalog, dataVersion]);

  // Default the date range to the full record once the catalogue is known.
  useEffect(() => {
    if (!catalog?.min_date || !catalog?.max_date) return;
    setRangeState((current) => {
      if (current.start || current.end) return current;
      return { start: catalog.min_date, end: catalog.max_date };
    });
  }, [catalog?.min_date, catalog?.max_date]);

  const setAoi = useCallback((next: AOI) => {
    setAoiState(next);
    localStorage.setItem("firetrack.aoi", JSON.stringify(next));
  }, []);

  const setRange = useCallback((next: DateRange) => {
    setRangeState(next);
    localStorage.setItem("firetrack.range", JSON.stringify(next));
  }, []);

  const setConfidence = useCallback((next: "all" | "nominal" | "high") => {
    setConfidenceState(next);
    localStorage.setItem("firetrack.confidence", JSON.stringify(next));
  }, []);

  const setSensors = useCallback((next: string[]) => {
    setSensorsState(next);
    localStorage.setItem("firetrack.sensors", JSON.stringify(next));
  }, []);

  const query = useMemo<QueryBody>(
    () => ({
      aoi,
      start: range.start,
      end: range.end,
      confidence,
      sensors: sensors.length ? sensors : null,
    }),
    [aoi, range.start, range.end, confidence, sensors],
  );

  const value: AppState = {
    aoi,
    setAoi,
    range,
    setRange,
    confidence,
    setConfidence,
    sensors,
    setSensors,
    catalog,
    catalogError,
    refreshCatalog: () => setDataVersion((v) => v + 1),
    dataVersion,
    query,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppState {
  const context = useContext(AppContext);
  if (!context) throw new Error("useApp must be used inside AppProvider");
  return context;
}

export interface AsyncResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/** Minimal data-fetching hook with stale-response protection. */
export function useAsync<T>(
  loader: () => Promise<T>,
  deps: React.DependencyList,
  enabled = true,
): AsyncResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const requestId = useRef(0);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    loader()
      .then((result) => {
        if (id !== requestId.current) return;
        setData(result);
        setLoading(false);
      })
      .catch((err: Error) => {
        if (id !== requestId.current) return;
        setError(err.message);
        setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce, enabled]);

  return { data, loading, error, reload: () => setNonce((n) => n + 1) };
}
