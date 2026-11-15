/** Hand-built SVG charts: full control over the dark scientific styling, and
 *  no charting dependency to keep the bundle small and the build reliable. */

import React from "react";

export interface Point {
  x: number;
  y: number | null;
}

export interface ChartSeries {
  id: string;
  label: string;
  color: string;
  points: Point[];
  dashed?: boolean;
}

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalised = value / magnitude;
  const step = normalised <= 1 ? 1 : normalised <= 2 ? 2 : normalised <= 5 ? 5 : 10;
  return step * magnitude;
}

function pathFor(points: Point[], width: number, height: number, maxX: number, maxY: number): string {
  let d = "";
  let started = false;
  for (const point of points) {
    if (point.y === null) {
      started = false;
      continue;
    }
    const px = (point.x / Math.max(1, maxX)) * width;
    const py = height - (point.y / maxY) * height;
    d += `${started ? "L" : "M"}${px.toFixed(2)} ${py.toFixed(2)} `;
    started = true;
  }
  return d;
}

export function LineChart({
  series, height = 190, yLabel, ticks, baseline, showArea = true, markerAt,
}: {
  series: ChartSeries[];
  height?: number;
  yLabel?: string;
  ticks?: { x: number; label: string }[];
  baseline?: number | null;
  showArea?: boolean;
  markerAt?: number | null;
}) {
  const width = 760;
  const padL = 46;
  const padB = 26;
  const padT = 10;
  const plotW = width - padL - 10;
  const plotH = height - padB - padT;

  const allY = series.flatMap((s) => s.points.map((p) => p.y)).filter((v): v is number => v !== null);
  const maxX = Math.max(1, ...series.flatMap((s) => s.points.map((p) => p.x)));
  const maxY = niceMax(Math.max(1, ...allY, baseline ?? 0));

  const hasData = allY.length > 0;

  return (
    <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={yLabel ?? "chart"}>
      <g transform={`translate(${padL},${padT})`}>
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => (
          <g key={frac}>
            <line className="gridline" x1={0} x2={plotW} y1={plotH * (1 - frac)} y2={plotH * (1 - frac)} />
            <text className="axis" x={-8} y={plotH * (1 - frac) + 3} textAnchor="end">
              {Math.round(maxY * frac).toLocaleString()}
            </text>
          </g>
        ))}

        {baseline !== null && baseline !== undefined && (
          <line
            x1={0} x2={plotW} y1={plotH - (baseline / maxY) * plotH} y2={plotH - (baseline / maxY) * plotH}
            stroke="var(--cyan)" strokeWidth={1.2} strokeDasharray="6 4" opacity={0.85}
          />
        )}

        {hasData && showArea && series.length === 1 && (
          <path
            d={`${pathFor(series[0].points, plotW, plotH, maxX, maxY)} L${plotW} ${plotH} L0 ${plotH} Z`}
            fill={series[0].color}
            opacity={0.1}
          />
        )}

        {series.map((s) => (
          <path
            key={s.id}
            className="series-line"
            d={pathFor(s.points, plotW, plotH, maxX, maxY)}
            stroke={s.color}
            strokeDasharray={s.dashed ? "5 4" : undefined}
            strokeLinejoin="round"
          />
        ))}

        {markerAt !== null && markerAt !== undefined && maxX > 0 && (
          <line
            x1={(markerAt / maxX) * plotW} x2={(markerAt / maxX) * plotW}
            y1={0} y2={plotH} stroke="var(--accent)" strokeWidth={1} strokeDasharray="3 3" opacity={0.8}
          />
        )}

        {ticks?.map((tick) => (
          <text
            key={`${tick.x}-${tick.label}`}
            className="axis"
            x={(tick.x / Math.max(1, maxX)) * plotW}
            y={plotH + 15}
            textAnchor="middle"
          >
            {tick.label}
          </text>
        ))}

        {!hasData && (
          <text x={plotW / 2} y={plotH / 2} textAnchor="middle" fill="var(--text-faint)" fontSize={12}>
            No observations for this selection
          </text>
        )}
      </g>
    </svg>
  );
}

export function BarChart({
  data, height = 190, color = "var(--accent)", valueFormat,
}: {
  data: { label: string; value: number | null; muted?: boolean }[];
  height?: number;
  color?: string;
  valueFormat?: (value: number) => string;
}) {
  const width = 760;
  const padL = 46;
  const padB = 30;
  const padT = 10;
  const plotW = width - padL - 10;
  const plotH = height - padB - padT;
  const values = data.map((d) => d.value).filter((v): v is number => v !== null);
  const maxY = niceMax(Math.max(1, ...values));
  const slot = plotW / Math.max(1, data.length);
  const barW = Math.max(2, slot * 0.66);
  const fmt = valueFormat ?? ((v: number) => Math.round(v).toLocaleString());

  return (
    <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="bar chart">
      <g transform={`translate(${padL},${padT})`}>
        {[0, 0.5, 1].map((frac) => (
          <g key={frac}>
            <line className="gridline" x1={0} x2={plotW} y1={plotH * (1 - frac)} y2={plotH * (1 - frac)} />
            <text className="axis" x={-8} y={plotH * (1 - frac) + 3} textAnchor="end">
              {Math.round(maxY * frac).toLocaleString()}
            </text>
          </g>
        ))}
        {data.map((item, index) => {
          const x = index * slot + (slot - barW) / 2;
          if (item.value === null) {
            return (
              <g key={item.label}>
                <rect x={x} y={plotH - 3} width={barW} height={3} fill="var(--border-strong)" rx={1} />
                <title>{item.label}: no data</title>
              </g>
            );
          }
          const h = Math.max(1, (item.value / maxY) * plotH);
          return (
            <g key={item.label}>
              <rect
                className="bar"
                x={x} y={plotH - h} width={barW} height={h} rx={1.5}
                fill={item.muted ? "var(--border-strong)" : color}
              >
                <title>{`${item.label}: ${fmt(item.value)}`}</title>
              </rect>
            </g>
          );
        })}
        {data.map((item, index) => {
          if (data.length > 22 && index % 2 === 1) return null;
          return (
            <text
              key={`l-${item.label}`}
              className="axis"
              x={index * slot + slot / 2}
              y={plotH + 15}
              textAnchor="middle"
            >
              {item.label}
            </text>
          );
        })}
      </g>
    </svg>
  );
}

export function StackedBars({
  data, height = 150, colors, labels,
}: {
  data: { label: string; values: Record<string, number> }[];
  height?: number;
  colors: Record<string, string>;
  labels: Record<string, string>;
}) {
  const width = 760;
  const padL = 42;
  const padB = 22;
  const padT = 8;
  const plotW = width - padL - 10;
  const plotH = height - padB - padT;
  const totals = data.map((d) => Object.values(d.values).reduce((a, b) => a + b, 0));
  const maxY = niceMax(Math.max(1, ...totals));
  const slot = plotW / Math.max(1, data.length);
  const barW = Math.max(1.5, slot * 0.72);
  const keys = Object.keys(colors);

  return (
    <div>
      <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="stacked bars">
        <g transform={`translate(${padL},${padT})`}>
          <line className="gridline" x1={0} x2={plotW} y1={plotH} y2={plotH} />
          <line className="gridline" x1={0} x2={plotW} y1={0} y2={0} />
          <text className="axis" x={-8} y={3} textAnchor="end">{Math.round(maxY).toLocaleString()}</text>
          <text className="axis" x={-8} y={plotH + 3} textAnchor="end">0</text>
          {data.map((item, index) => {
            let acc = 0;
            const x = index * slot + (slot - barW) / 2;
            return (
              <g key={item.label}>
                {keys.map((key) => {
                  const value = item.values[key] ?? 0;
                  if (!value) return null;
                  const h = (value / maxY) * plotH;
                  const y = plotH - acc - h;
                  acc += h;
                  return <rect key={key} x={x} y={y} width={barW} height={h} fill={colors[key]}>
                    <title>{`${item.label} · ${labels[key] ?? key}: ${Math.round(value).toLocaleString()}`}</title>
                  </rect>;
                })}
              </g>
            );
          })}
        </g>
      </svg>
      <div className="row mt-8" style={{ gap: 12 }}>
        {keys.map((key) => (
          <span key={key} className="legend">
            <i style={{ width: 9, height: 9, borderRadius: 2, background: colors[key], display: "inline-block" }} />
            {labels[key] ?? key}
          </span>
        ))}
      </div>
    </div>
  );
}

export function Sparkline({ values, color = "var(--accent)", width = 120, height = 30 }: {
  values: (number | null)[];
  color?: string;
  width?: number;
  height?: number;
}) {
  const clean = values.map((v, i) => ({ x: i, y: v })).filter((p) => p.y !== null) as { x: number; y: number }[];
  if (clean.length < 2) return <span className="faint">—</span>;
  const maxY = Math.max(...clean.map((p) => p.y), 1);
  const path = clean
    .map((p, i) => `${i === 0 ? "M" : "L"}${(p.x / (values.length - 1)) * width} ${height - (p.y / maxY) * height}`)
    .join(" ");
  return (
    <svg width={width} height={height} aria-hidden="true" style={{ display: "block" }}>
      <path d={path} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" />
    </svg>
  );
}
