/** Thin typed wrapper around the FIRETRACK HTTP API. */

import type {
  Anomalies, AOI, Catalog, CriticalPeriods, DetectionsPage, Harmonization, HistoryMatrix,
  MapCells, MonthCalendar, Region, SearchResult, SensorCompare, Trends, YearCalendar,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export interface QueryBody {
  aoi: AOI;
  start?: string | null;
  end?: string | null;
  confidence?: "all" | "nominal" | "high";
  sensors?: string[] | null;
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  const init: RequestInit = body
    ? {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    : { method: "GET" };
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError("Cannot reach the FIRETRACK server. Is it still running?", 0);
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") detail = payload.detail;
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ ready: boolean; detections: number; map_key_configured: boolean }>("/api/health"),
  catalog: () => request<Catalog>("/api/catalog"),
  regions: () => request<{ regions: Region[] }>("/api/regions"),
  search: (q: string) => request<{ results: SearchResult[] }>(`/api/search?q=${encodeURIComponent(q)}`),
  harmonization: (query: QueryBody) => request<Harmonization>("/api/harmonization", query),
  month: (query: QueryBody & { year?: number; month?: number }) =>
    request<MonthCalendar>("/api/calendar/month", query),
  year: (query: QueryBody & { year?: number }) => request<YearCalendar>("/api/calendar/year", query),
  history: (query: QueryBody & { metric?: "harmonized" | "raw" }) =>
    request<HistoryMatrix>("/api/calendar/history", query),
  trends: (query: QueryBody) => request<Trends>("/api/analytics/trends", query),
  anomalies: (query: QueryBody & { z_threshold?: number }) => request<Anomalies>("/api/anomalies", query),
  criticalPeriods: (query: QueryBody & { percentile?: number; min_days?: number }) =>
    request<CriticalPeriods>("/api/critical-periods", query),
  compare: (query: QueryBody) => request<SensorCompare>("/api/compare/sensors", query),
  mapCells: (query: QueryBody) => request<MapCells>("/api/map/cells", query),
  detections: (query: QueryBody & {
    limit?: number; offset?: number; frp_min?: number | null;
    confidence_min?: number | null; order?: string; search?: string | null;
  }) => request<DetectionsPage>("/api/detections", query),
  ingestSnapshot: () =>
    request<{ ingested: unknown[]; summary: unknown }>("/api/ingest/snapshot", {}),

  /** Upload a NASA FIRMS Archive Download file (.csv, .csv.gz or .zip). */
  uploadArchive: async (file: File) => {
    const response = await fetch(`/api/ingest/archive?name=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: file,
    });
    if (!response.ok) {
      let detail = `Import failed (${response.status})`;
      try {
        const payload = await response.json();
        if (typeof payload?.detail === "string") detail = payload.detail;
      } catch {
        /* keep the generic message */
      }
      throw new ApiError(detail, response.status);
    }
    return (await response.json()) as {
      rows_read: number;
      rows_kept: number;
      rows_duplicate: number;
      rows_rejected: number;
      min_date: string | null;
      max_date: string | null;
      sensors: string[];
      quality: string;
      message?: string;
      summary: { detections: number; min_date: string | null; max_date: string | null };
    };
  },
};

/** Trigger a browser download for a POST-only export endpoint. */
export async function downloadExport(
  path: string,
  body: unknown,
  filename: string,
): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiError(`Export failed (${response.status})`, response.status);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
