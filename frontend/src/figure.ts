/** Downloadable figures: the burning calendar as a standalone SVG or PNG.
 *
 *  The challenge asks for downloadable "analytics and visualizations", and a
 *  report full of charts is not the same as a single, readable calendar image a
 *  fire manager can drop into a briefing. This renders the current month view
 *  into a self-contained SVG (no external CSS, no fonts to fetch) and can
 *  rasterise it to PNG in the browser.
 */

import type { MonthCalendar } from "./types";
import { HEAT_RAMP, NO_DATA_COLOR, MONTHS, WEEKDAYS, formatNumber, weekdayIndex } from "./format";

const BG = "#0b1220";
const PANEL = "#0c1626";
const BORDER = "#1b2b44";
const TEXT = "#e8eef7";
const DIM = "#9fb0c7";
const FAINT = "#6b7f99";
const ACCENT = "#f97316";

function esc(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function heat(value: number | null, max: number): string {
  if (value === null || !Number.isFinite(value) || value <= 0) return NO_DATA_COLOR;
  if (max <= 0) return HEAT_RAMP[1];
  const ratio = Math.min(1, Math.sqrt(value / max));
  const index = Math.min(HEAT_RAMP.length - 1, Math.max(1, Math.round(ratio * (HEAT_RAMP.length - 1))));
  return HEAT_RAMP[index];
}

/** Build a standalone SVG of one month of harmonised burning activity. */
export function calendarSvg(
  calendar: MonthCalendar,
  options: { aoiName: string; unit: string; sensors: { id: string; label: string }[] },
): string {
  const width = 900;
  const margin = 28;
  const header = 96;
  const cols = 7;
  const gap = 5;
  const cellW = (width - margin * 2 - gap * (cols - 1)) / cols;
  const cellH = 62;
  const rows = Math.ceil((weekdayIndex(calendar.days[0]?.date ?? "2020-01-06") + calendar.days.length) / 7);
  const gridTop = header;
  const gridHeight = rows * (cellH + gap);
  const legendTop = gridTop + gridHeight + 18;
  const height = legendTop + 82;

  const values = calendar.days
    .map((d) => d.harmonized)
    .filter((v): v is number => v !== null && Number.isFinite(v));
  const max = values.length ? Math.max(...values) : 1;

  const parts: string[] = [];
  parts.push(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" ` +
      `viewBox="0 0 ${width} ${height}" font-family="system-ui, -apple-system, Segoe UI, sans-serif">`,
  );
  parts.push(`<rect width="${width}" height="${height}" fill="${BG}"/>`);

  // Header
  parts.push(
    `<text x="${margin}" y="${margin + 8}" fill="${ACCENT}" font-size="10" letter-spacing="2">` +
      `FIRETRACK · HARMONISED BURNING ACTIVITY</text>`,
  );
  parts.push(
    `<text x="${margin}" y="${margin + 36}" fill="${TEXT}" font-size="22" font-weight="600">` +
      `${esc(calendar.month_name)} ${calendar.year} — ${esc(options.aoiName)}</text>`,
  );
  parts.push(
    `<text x="${margin}" y="${margin + 56}" fill="${DIM}" font-size="11">` +
      `${calendar.summary.observed_days} of ${calendar.summary.days_in_period} days observed · ` +
      `coverage ${Math.round(calendar.summary.coverage * 100)}% · ` +
      `${calendar.summary.complete ? "complete month" : "incomplete, excluded from medians"}</text>`,
  );
  const compared =
    calendar.comparison.median === null
      ? "no historical median available"
      : `median ${formatNumber(calendar.comparison.median)} · ` +
        (calendar.comparison.percent_deviation !== null && calendar.comparison.percent_reliable
          ? `${calendar.comparison.percent_deviation > 0 ? "+" : ""}${calendar.comparison.percent_deviation.toFixed(1)}%`
          : `difference ${formatNumber(calendar.comparison.absolute_deviation)}`);
  parts.push(
    `<text x="${margin}" y="${margin + 74}" fill="${FAINT}" font-size="11">` +
      `${formatNumber(calendar.summary.expected_total)} ${esc(options.unit)} · ${esc(compared)}</text>`,
  );

  // Weekday headers
  WEEKDAYS.forEach((day, index) => {
    const x = margin + index * (cellW + gap);
    parts.push(
      `<text x="${x}" y="${gridTop - 6}" fill="${FAINT}" font-size="9" letter-spacing="1.2">` +
        `${day.toUpperCase()}</text>`,
    );
  });

  // Day cells
  const leading = weekdayIndex(calendar.days[0]?.date ?? "2020-01-06");
  calendar.days.forEach((day, index) => {
    const slot = leading + index;
    const col = slot % 7;
    const row = Math.floor(slot / 7);
    const x = margin + col * (cellW + gap);
    const y = gridTop + row * (cellH + gap);
    const observed = day.observed && day.harmonized !== null;
    const fill = observed ? heat(day.harmonized, max) : NO_DATA_COLOR;
    parts.push(
      `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${cellW.toFixed(1)}" height="${cellH}" ` +
        `rx="7" fill="${fill}" stroke="${observed ? "none" : BORDER}"/>`,
    );
    const textColour = observed && (day.harmonized ?? 0) / max > 0.55 ? "#10161f" : TEXT;
    parts.push(
      `<text x="${(x + 7).toFixed(1)}" y="${(y + 15).toFixed(1)}" fill="${observed ? textColour : FAINT}" ` +
        `font-size="10" font-weight="600">${day.day}</text>`,
    );
    parts.push(
      `<text x="${(x + 7).toFixed(1)}" y="${(y + 38).toFixed(1)}" fill="${observed ? textColour : FAINT}" ` +
        `font-size="14" font-weight="600">${observed ? formatNumber(day.harmonized) : "—"}</text>`,
    );
    if (observed) {
      // Sensor dots: one per observing platform, using the interface colours.
      const colours: Record<string, string> = {
        modis: "#f59e0b",
        viirs_snpp: "#38bdf8",
        viirs_noaa20: "#a78bfa",
        viirs_noaa21: "#34d399",
      };
      day.sensors_observing.forEach((sensor, dot) => {
        parts.push(
          `<circle cx="${(x + 10 + dot * 8).toFixed(1)}" cy="${(y + 50).toFixed(1)}" r="2.6" ` +
            `fill="${colours[sensor] ?? DIM}"/>`,
        );
      });
    }
  });

  // Legend
  const stepW = 26;
  HEAT_RAMP.forEach((colour, index) => {
    parts.push(
      `<rect x="${margin + 46 + index * stepW}" y="${legendTop}" width="${stepW - 2}" height="10" ` +
        `rx="2" fill="${colour}"/>`,
    );
  });
  parts.push(
    `<text x="${margin}" y="${legendTop + 9}" fill="${FAINT}" font-size="10">low</text>`,
    `<text x="${margin + 46 + HEAT_RAMP.length * stepW + 6}" y="${legendTop + 9}" fill="${FAINT}" font-size="10">` +
      `high · max ${formatNumber(max)}</text>`,
  );
  parts.push(
    `<rect x="${margin}" y="${legendTop + 22}" width="12" height="10" rx="2" fill="${NO_DATA_COLOR}" ` +
      `stroke="${BORDER}"/>`,
    `<text x="${margin + 18}" y="${legendTop + 31}" fill="${FAINT}" font-size="10">` +
      `no observation (missing data, not zero burning)</text>`,
  );

  // Footer
  const sensorText = options.sensors.map((s) => s.label.replace(" (Terra + Aqua)", "")).join(" · ");
  parts.push(
    `<line x1="${margin}" x2="${width - margin}" y1="${height - 30}" y2="${height - 30}" stroke="${BORDER}"/>`,
    `<text x="${margin}" y="${height - 14}" fill="${FAINT}" font-size="9">` +
      `Sensors in this record: ${esc(sensorText)}. Source: NASA FIRMS (MODIS C6.1, VIIRS C2 375 m). ` +
      `A hotspot is a thermal anomaly detection, not a confirmed wildfire.</text>`,
  );

  parts.push("</svg>");
  return parts.join("");
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

export function downloadSvg(svg: string, filename: string): void {
  triggerDownload(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }), filename);
}

/** Rasterise the SVG to a 2x PNG using a canvas — no extra dependency. */
export async function downloadPng(svg: string, filename: string): Promise<void> {
  const match = /width="(\d+)" height="(\d+)"/.exec(svg);
  const width = match ? Number(match[1]) : 900;
  const height = match ? Number(match[2]) : 600;
  const scale = 2;
  const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  try {
    const image = new Image();
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("Could not render the figure."));
      image.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = width * scale;
    canvas.height = height * scale;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas is not available in this browser.");
    context.scale(scale, scale);
    context.fillStyle = BG;
    context.fillRect(0, 0, width, height);
    context.drawImage(image, 0, 0, width, height);
    const png = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!png) throw new Error("Could not encode the PNG.");
    triggerDownload(png, filename);
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function figureFilename(calendar: MonthCalendar, aoiName: string, ext: string): string {
  const slug = aoiName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 40) || "area";
  return `firetrack_${slug}_${calendar.year}-${String(calendar.month).padStart(2, "0")}.${ext}`;
}

export function figureTitle(calendar: MonthCalendar): string {
  return `${MONTHS[calendar.month - 1]} ${calendar.year}`;
}
