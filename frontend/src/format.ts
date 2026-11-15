/** Formatting helpers and the shared sequential colour ramp. */

export const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
export const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 100_000) return `${Math.round(value / 1000)}k`;
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatExact(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return Math.round(value).toLocaleString();
}

export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${d} ${MONTHS_SHORT[m - 1]} ${y}`;
}

export function formatDateShort(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${d} ${MONTHS_SHORT[m - 1]}`;
}

export function formatTime(hhmm: string | null | undefined): string {
  if (!hhmm || hhmm.length < 4) return "—";
  return `${hhmm.slice(0, 2)}:${hhmm.slice(2, 4)} UTC`;
}

/** Sequential ramp for burning activity: dark and cool -> bright and hot. */
export const HEAT_RAMP = [
  "#17233a",
  "#3d2739",
  "#6b2c3a",
  "#982f34",
  "#c2412c",
  "#e97226",
  "#fbbf24",
];

export const NO_DATA_COLOR = "#0e1726";

export function heatColor(value: number | null | undefined, max: number): string {
  if (value === null || value === undefined || !Number.isFinite(value) || value <= 0) {
    return NO_DATA_COLOR;
  }
  if (max <= 0) return HEAT_RAMP[1];
  const ratio = Math.min(1, Math.sqrt(value / max));
  const index = Math.min(HEAT_RAMP.length - 1, Math.max(1, Math.round(ratio * (HEAT_RAMP.length - 1))));
  return HEAT_RAMP[index];
}

export function heatTextColor(value: number | null | undefined, max: number): string {
  if (value === null || value === undefined || max <= 0) return "var(--text-faint)";
  return value / max > 0.55 ? "#10161f" : "#f8fafc";
}

export function quantile(values: number[], q: number): number {
  const clean = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (!clean.length) return 0;
  const pos = (clean.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  if (clean[base + 1] !== undefined) return clean[base] + rest * (clean[base + 1] - clean[base]);
  return clean[base];
}

export function sensorColour(sensor: string): string {
  const map: Record<string, string> = {
    modis: "#f59e0b",
    viirs_snpp: "#38bdf8",
    viirs_noaa20: "#a78bfa",
    viirs_noaa21: "#34d399",
  };
  return map[sensor] ?? "#94a3b8";
}

export function sensorLabel(sensor: string): string {
  const map: Record<string, string> = {
    modis: "MODIS",
    viirs_snpp: "VIIRS S-NPP",
    viirs_noaa20: "VIIRS NOAA-20",
    viirs_noaa21: "VIIRS NOAA-21",
  };
  return map[sensor] ?? sensor;
}

export function sensorShort(sensor: string): string {
  const map: Record<string, string> = {
    modis: "MODIS",
    viirs_snpp: "S-NPP",
    viirs_noaa20: "N20",
    viirs_noaa21: "N21",
  };
  return map[sensor] ?? sensor;
}

export function clamp(value: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, value));
}

export function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

/** Monday-first weekday index for a YYYY-MM-DD date. */
export function weekdayIndex(iso: string): number {
  const d = new Date(`${iso}T00:00:00Z`);
  return (d.getUTCDay() + 6) % 7;
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function shiftMonth(year: number, month: number, delta: number): { year: number; month: number } {
  const zero = year * 12 + (month - 1) + delta;
  return { year: Math.floor(zero / 12), month: (zero % 12) + 1 };
}
