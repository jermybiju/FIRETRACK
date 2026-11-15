"""Self-contained HTML report export.

The report is a single .html file with no external assets: charts are inline SVG
and styling is embedded, so it can be e-mailed, opened offline, or printed to
PDF from any browser. That keeps the deliverable dependency-free.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Sequence

from . import config


def _esc(text) -> str:
    return html.escape(str(text if text is not None else ""))


def _fmt(value, digits: int = 0, dash: str = "&mdash;") -> str:
    if value is None:
        return dash
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    if isinstance(value, int):
        return f"{value:,}"
    return _esc(value)


def svg_bars(
    labels: Sequence[str],
    values: Sequence[float | None],
    *,
    width: int = 720,
    height: int = 220,
    color: str = "#f97316",
    baseline: float | None = None,
    title: str = "",
) -> str:
    """Minimal, accessible inline SVG bar chart."""
    clean = [(lab, v) for lab, v in zip(labels, values)]
    numeric = [v for _, v in clean if v is not None]
    if not numeric:
        return f'<p class="muted">No data available for {_esc(title)}.</p>'
    vmax = max(max(numeric), baseline or 0) or 1
    pad_l, pad_b, pad_t = 48, 34, 12
    plot_w = width - pad_l - 12
    plot_h = height - pad_b - pad_t
    slot = plot_w / max(1, len(clean))
    bar_w = max(2.0, slot * 0.7)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{_esc(title)}" '
        f'class="chart" preserveAspectRatio="none">'
    ]
    # gridlines
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        y = pad_t + plot_h * (1 - frac)
        parts.append(f'<line x1="{pad_l}" x2="{width - 12}" y1="{y:.1f}" y2="{y:.1f}" '
                     f'stroke="#1e293b" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l - 8}" y="{y + 4:.1f}" class="axis" text-anchor="end">'
                     f'{vmax * frac:,.0f}</text>')
    if baseline is not None and vmax:
        y = pad_t + plot_h * (1 - baseline / vmax)
        parts.append(f'<line x1="{pad_l}" x2="{width - 12}" y1="{y:.1f}" y2="{y:.1f}" '
                     f'stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="6 4"/>')
        parts.append(f'<text x="{width - 14}" y="{y - 6:.1f}" class="axis" text-anchor="end" '
                     f'fill="#38bdf8">historical median</text>')
    for i, (lab, val) in enumerate(clean):
        x = pad_l + i * slot + (slot - bar_w) / 2
        if val is None:
            parts.append(f'<rect x="{x:.1f}" y="{pad_t + plot_h - 6}" width="{bar_w:.1f}" height="6" '
                         f'fill="#334155" opacity="0.6"><title>{_esc(lab)}: no data</title></rect>')
        else:
            h = max(1.0, plot_h * (val / vmax))
            parts.append(
                f'<rect x="{x:.1f}" y="{pad_t + plot_h - h:.1f}" width="{bar_w:.1f}" '
                f'height="{h:.1f}" fill="{color}" rx="1.5"><title>{_esc(lab)}: {val:,.1f}</title></rect>'
            )
        parts.append(f'<text x="{pad_l + i * slot + slot / 2:.1f}" y="{height - 14}" '
                     f'class="axis" text-anchor="middle">{_esc(lab)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def render_report(payload: dict) -> str:
    ctx = payload.get("context", {})
    aoi = ctx.get("aoi", {})
    summary = payload.get("summary", {})
    baseline = payload.get("baseline", {})
    comparison = payload.get("comparison", {})
    trend = payload.get("trend", {})
    yearly = payload.get("yearly", [])
    monthly = payload.get("monthly_profile", [])
    sensors = ctx.get("sensors", [])
    calibration = ctx.get("calibration", {})
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    year_labels = [str(r["year"]) for r in yearly]
    year_values = [r.get("expected_total") for r in yearly]
    month_labels = [m["month_name"][:3] for m in monthly]
    month_values = [m.get("median") for m in monthly]

    comparison_rows = ""
    if comparison.get("median") is not None:
        comparison_rows = f"""
        <tr><td>Observed activity ({_esc(summary.get('start'))} to {_esc(summary.get('end'))})</td>
            <td class="num">{_fmt(comparison.get('observed'), 0)}</td></tr>
        <tr><td>Historical median for this calendar month</td>
            <td class="num">{_fmt(comparison.get('median'), 0)}</td></tr>
        <tr><td>Absolute deviation</td>
            <td class="num">{_fmt(comparison.get('absolute_deviation'), 0)}</td></tr>
        <tr><td>Percent deviation</td>
            <td class="num">{('%+.1f%%' % comparison['percent_deviation']) if comparison.get('percent_deviation') is not None else '&mdash;'}</td></tr>
        <tr><td>Robust z-score (MAD based)</td>
            <td class="num">{comparison.get('z_score') if comparison.get('z_score') is not None else '&mdash;'}</td></tr>
        <tr><td>Years in baseline</td>
            <td class="num">{_fmt(baseline.get('n_years'))}</td></tr>
        """
    else:
        comparison_rows = (
            '<tr><td colspan="2" class="muted">No historical median could be computed: the record '
            'does not contain enough complete months of the same calendar month.</td></tr>'
        )

    sensor_rows = "".join(
        f"<tr><td>{_esc(s.get('label'))}</td><td>{_esc(s.get('instrument'))}</td>"
        f"<td class=\"num\">{_esc(s.get('pixel_km'))} km</td></tr>"
        for s in sensors
    )

    per_sensor_rows = "".join(
        f"<tr><td>{_esc(s)}</td><td class=\"num\">{_fmt(n)}</td>"
        f"<td class=\"num\">{_fmt(round(n / summary.get('raw_total') * 100, 1) if summary.get('raw_total') else None, 1)}%</td>"
        f"<td class=\"num\">{_fmt((summary.get('frp_by_sensor') or {}).get(s), 1)}</td></tr>"
        for s, n in sorted((summary.get("per_sensor") or {}).items(), key=lambda kv: -kv[1])
    )

    calibration_notes = "".join(f"<li>{_esc(n)}</li>" for n in calibration.get("notes", [])) or "<li>None.</li>"

    periods = (payload.get("critical") or {}).get("periods", [])
    if periods:
        rows = "".join(
            f"<tr><td>{_esc(p['start'])} &rarr; {_esc(p['end'])}</td>"
            f"<td class=\"num\">{_fmt(p['duration_days'])}</td>"
            f"<td class=\"num\">{_fmt(p['peak_value'], 1)}</td>"
            f"<td className=\"num\">{_esc(p['peak_date'])}</td>"
            f"<td class=\"num\">{_fmt(p['threshold'], 1)}</td></tr>"
            for p in periods[:12]
        )
        critical_rows = f"""
    <table>
      <thead><tr><th>Period</th><th class="num">Days</th><th class="num">Peak</th>
        <th class="num">Peak date</th><th class="num">Threshold</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <p class="muted">Contiguous days above the 90th percentile of the same calendar month across
       complete months, broken by missing observations and incomplete months. High activity is not a
       confirmed wildfire emergency.</p>"""
    else:
        critical_rows = (
            '<p class="muted">No critical period in this month: no run of at least three consecutive '
            'days exceeded the historical 90th percentile for its calendar month, or the month does '
            'not pass the coverage gate.</p>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FIRETRACK activity report &mdash; {_esc(aoi.get('name'))}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 32px; background: #0b1220; color: #e2e8f0;
         font: 15px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }}
  .wrap {{ max-width: 880px; margin: 0 auto; }}
  h1 {{ font-size: 26px; margin: 0 0 4px; letter-spacing: -0.02em; }}
  h2 {{ font-size: 16px; margin: 32px 0 10px; color: #f8fafc;
        border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
  .tag {{ color: #f97316; font-size: 12px; letter-spacing: .18em; text-transform: uppercase; }}
  .muted {{ color: #94a3b8; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }}
  .card {{ background: #111c2e; border: 1px solid #1e293b; border-radius: 10px; padding: 14px; }}
  .kpi {{ font-size: 22px; font-weight: 650; color: #fff; }}
  .kpi-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: #94a3b8; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th, td {{ text-align: left; padding: 7px 8px; border-bottom: 1px solid #1e293b; }}
  th {{ color: #94a3b8; font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .chart {{ width: 100%; height: auto; display: block; }}
  .axis {{ fill: #94a3b8; font-size: 10px; }}
  ul {{ padding-left: 20px; }}
  li {{ margin: 4px 0; }}
  .foot {{ margin-top: 36px; padding-top: 12px; border-top: 1px solid #1e293b; font-size: 12px; color: #94a3b8; }}
  @media print {{ body {{ background: #fff; color: #111; }} .card {{ border-color: #ddd; }}
    h1, h2, .kpi {{ color: #111; }} .muted, .foot {{ color: #444; }} }}
</style>
</head>
<body>
<div class="wrap">
  <div class="tag">FIRETRACK &middot; Harmonised burning activity report</div>
  <h1>{_esc(aoi.get('name') or 'Selected area')}</h1>
  <p class="muted">Area of interest {_esc(aoi.get('bbox'))} &middot; grid {_esc(ctx.get('grid_deg'))}&deg;
     &middot; generated {_esc(generated)}</p>

  <h2>Activity summary</h2>
  <div class="grid">
    <div class="card"><div class="kpi-label">Harmonised activity</div>
      <div class="kpi">{_fmt(summary.get('expected_total'), 0)}</div>
      <div class="muted">{_esc(ctx.get('unit'))}, coverage-corrected</div></div>
    <div class="card"><div class="kpi-label">Raw detections</div>
      <div class="kpi">{_fmt(summary.get('raw_total'), 0)}</div>
      <div class="muted">all sensors, unadjusted</div></div>
    <div class="card"><div class="kpi-label">Observed days</div>
      <div class="kpi">{_fmt(summary.get('observed_days'))} / {_fmt(summary.get('days_in_period'))}</div>
      <div class="muted">coverage {_fmt((summary.get('coverage') or 0) * 100, 0)}%</div></div>
    <div class="card"><div class="kpi-label">FRP, raw sum</div>
      <div class="kpi">{_fmt(summary.get('frp_total'), 0)}</div>
      <div class="muted">MW, all sensors added &mdash; not harmonised</div></div>
  </div>

  <h2>Comparison with the historical median</h2>
  <table><tbody>{comparison_rows}</tbody></table>
  <p class="muted">Baseline period: all complete months of the same calendar month in the record
     ({_esc(', '.join(str(y) for y in baseline.get('years_used', [])) or 'none')}).
     Months below the {int(config.MIN_COVERAGE_FRACTION * 100)}% coverage gate are excluded rather
     than counted as low activity.</p>

  <h2>Contribution by sensor</h2>
  <table>
    <thead><tr><th>Sensor</th><th class="num">Raw detections</th><th class="num">Share</th>
      <th class="num">FRP (MW)</th></tr></thead>
    <tbody>{per_sensor_rows or '<tr><td colspan="4" class="muted">No detections in this period.</td></tr>'}</tbody>
  </table>
  <p class="muted">FRP is reported per sensor because MODIS and VIIRS retrieve it differently.
     Their sum is a plain addition of raw values and is not a harmonised measurement.</p>

  <h2>Critical burning periods</h2>
  {critical_rows}

  <h2>Yearly harmonised activity</h2>
  {svg_bars(year_labels, year_values, title="Yearly harmonised activity")}

  <h2>Seasonal profile (median across years)</h2>
  {svg_bars(month_labels, month_values, width=720, height=200, color="#38bdf8", title="Seasonal profile")}

  <h2>Trend test</h2>
  <p>{_esc(trend.get('method', ''))} &middot; {_fmt(trend.get('n_years'))} complete years.<br>
     Theil&ndash;Sen slope: <strong>{_fmt(trend.get('theil_sen_slope_per_year'), 2)}</strong> per year &middot;
     Mann&ndash;Kendall p = <strong>{_fmt((trend.get('mann_kendall') or {}).get('p'), 4)}</strong>
     ({_esc((trend.get('mann_kendall') or {}).get('trend', 'insufficient data'))}).</p>
  <p class="muted">{_esc(trend.get('note', ''))}</p>

  <h2>Data sources</h2>
  <table>
    <thead><tr><th>Sensor</th><th>Instrument</th><th class="num">Native pixel</th></tr></thead>
    <tbody>{sensor_rows}</tbody>
  </table>
  <p class="muted">Record span {_esc(ctx.get('record_start'))} to {_esc(ctx.get('record_end'))};
     {_fmt(ctx.get('detections'))} raw detections in the analysis grid
     ({_fmt(ctx.get('grid_area_km2'), 0)} km&sup2;).</p>

  <h2>Harmonisation status</h2>
  <p><strong>{_esc(calibration.get('status'))}</strong> &mdash; unit: {_esc(calibration.get('unit'))}.
     Weights: {_esc(calibration.get('weights'))}.</p>
  <ul>{calibration_notes}</ul>

  <h2>Scientific limitations</h2>
  <ul>
    <li>A FIRMS hotspot is a thermal anomaly detection, not a confirmed wildfire: it may be
        agricultural burning, an industrial flare, or a volcanic source.</li>
    <li>Missing observations are never treated as zero activity. Days without an observing
        sensor are excluded, and their coverage is shown everywhere.</li>
    <li>Cloud cover and sensor outages reduce detections; FIRMS does not report observation
        attempts at pixel level, so this cannot be fully corrected.</li>
    <li>Near-real-time (NRT) records are provisional and are superseded by standard-processing
        data. Check the provenance section of the application.</li>
    <li>The harmonised index is a bias-corrected, coverage-normalised count. It is not a burned
        area, not an emission estimate, and not a measure of fire severity.</li>
    <li>Statistical anomalies flag unusual patterns relative to history. They are not emergency
        declarations and this application is not an official alerting system.</li>
  </ul>

  <div class="foot">
    FIRETRACK &middot; Unified Satellite Burning Activity Intelligence Platform &middot;
    data &copy; NASA FIRMS (EOSDIS / LANCE). Generated from local records; see the in-app
    Methodology page for the full derivation.
  </div>
</div>
</body>
</html>"""
