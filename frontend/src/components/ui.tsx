/** Small, dependency-free presentation components shared across pages. */

import React from "react";

export function Panel({
  title, subtitle, actions, children, className = "", bodyClass = "",
}: {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClass?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || actions) && (
        <header className="panel-head">
          <div>
            {title && <h2 className="panel-title">{title}</h2>}
            {subtitle && <p className="panel-sub">{subtitle}</p>}
          </div>
          {actions && <div className="panel-actions">{actions}</div>}
        </header>
      )}
      <div className={`panel-body ${bodyClass}`}>{children}</div>
    </section>
  );
}

export function Stat({
  label, value, unit, note, delta, deltaDirection,
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  note?: React.ReactNode;
  delta?: React.ReactNode;
  deltaDirection?: "up" | "down" | "flat";
}) {
  return (
    <div className="panel stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}
        {unit && <span className="stat-unit">{unit}</span>}
      </div>
      {delta !== undefined && (
        <div className={`stat-note delta ${deltaDirection ?? "flat"}`}>{delta}</div>
      )}
      {note && <div className="stat-note">{note}</div>}
    </div>
  );
}

export function Loading({ label = "Loading observations…" }: { label?: string }) {
  return (
    <div className="loading-block" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="errorbox" role="alert">
      <strong>Something went wrong.</strong>
      <div style={{ marginTop: 6 }}>{message}</div>
      {onRetry && (
        <button className="btn btn-sm mt-8" onClick={onRetry} type="button">
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyBox({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="empty">
      <div style={{ color: "var(--text)", fontWeight: 600, marginBottom: 4 }}>{title}</div>
      {children}
    </div>
  );
}

export function Badge({
  children, tone = "default",
}: {
  children: React.ReactNode;
  tone?: "default" | "warn" | "ok" | "fire" | "info";
}) {
  const cls = tone === "default" ? "" : tone;
  return <span className={`badge ${cls}`}>{children}</span>;
}

export function Segmented<T extends string>({
  options, value, onChange, ariaLabel,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel?: string;
}) {
  return (
    <div className="segmented" role="group" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={option.value === value ? "on" : ""}
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function SensorToggles({
  sensors, active, onToggle,
}: {
  sensors: { id: string; label: string; colour: string }[];
  active: string[];
  onToggle: (id: string) => void;
}) {
  return (
    <div className="row" role="group" aria-label="Sensor filter">
      {sensors.map((sensor) => {
        const on = active.length === 0 || active.includes(sensor.id);
        return (
          <button
            key={sensor.id}
            type="button"
            className="sensor-chip"
            aria-pressed={on}
            onClick={() => onToggle(sensor.id)}
            title={on ? `Hide ${sensor.label}` : `Show ${sensor.label}`}
          >
            <span className="swatch" style={{ background: sensor.colour }} />
            {sensor.label.replace(" (Terra + Aqua)", "").replace("VIIRS ", "")}
          </button>
        );
      })}
    </div>
  );
}

export function InfoNote({ children, tone = "" }: { children: React.ReactNode; tone?: "" | "info" | "warn" }) {
  return <div className={`callout ${tone}`}>{children}</div>;
}

export function KVRows({ rows }: { rows: [React.ReactNode, React.ReactNode][] }) {
  return (
    <div className="kv">
      {rows.map(([key, value], index) => (
        <div className="kv-row" key={index}>
          <span className="kv-key">{key}</span>
          <span className="kv-val">{value}</span>
        </div>
      ))}
    </div>
  );
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="panel-title" style={{ marginBottom: 8 }}>{children}</h2>;
}
