/** Shared response types for the FIRETRACK API. */

export interface SensorMeta {
  id: string;
  label: string;
  instrument: string;
  colour: string;
  pixel_km: number | null;
}

export interface AOI {
  region_id?: string | null;
  bbox?: [number, number, number, number] | null;
  polygon?: [number, number][] | null;
  name?: string | null;
}

export interface AOIInfo {
  id: string | null;
  name: string;
  kind: string;
  bbox: [number, number, number, number];
  polygon: [number, number][] | null;
  area_km2: number;
}

export interface Calibration {
  status: string;
  calibrated: boolean;
  reference_sensor: string;
  weights: Record<string, number>;
  rates_per_day: Record<string, number>;
  paired_days: Record<string, number>;
  ratios: Record<string, number | null>;
  ratio_cv: number | null;
  unit: string;
  notes: string[];
}

export interface SeriesContext {
  aoi: AOIInfo;
  grid_deg: number;
  grid_cells: number;
  grid_area_km2: number;
  sensors: SensorMeta[];
  record_start: string;
  record_end: string;
  detections: number;
  calibration: Calibration;
  unit: string;
}

export interface PeriodSummary {
  start: string;
  end: string;
  days_in_period: number;
  observed_days: number;
  coverage: number;
  complete: boolean;
  observed_total: number | null;
  expected_total: number | null;
  mean_daily: number | null;
  median_daily: number | null;
  max_daily: number | null;
  raw_total: number;
  per_sensor: Record<string, number>;
  frp_total: number;
  frp_by_sensor?: Record<string, number>;
  frp_total_label?: string;
  sensors: string[];
  has_data: boolean;
}

export interface DayCell {
  date: string;
  day: number;
  observed: boolean;
  harmonized: number | null;
  raw_total: number | null;
  per_sensor: Record<string, number>;
  sensors_observing: string[];
  coverage: number;
  frp_total: number;
  frp_by_sensor?: Record<string, number>;
  frp_total_label?: string;
}

export interface CriticalPeriod {
  start: string;
  end: string;
  duration_days: number;
  peak_date: string;
  peak_value: number;
  mean_value: number;
  total_value: number;
  threshold: number | null;
  month: number;
  baseline_years: number[];
  sensors: string[];
  coverage_min: number;
}

export interface CriticalPeriods {
  periods: CriticalPeriod[];
  method: string;
  percentile: number;
  min_days: number;
  window: { start: string; end: string };
  baseline: Record<string, { threshold: number | null; n_days: number; median: number | null; p90: number | null; max: number | null }>;
  context: SeriesContext;
  caveats: string[];
}

export interface Baseline {
  month: number;
  years_used: number[];
  n_years: number;
  median: number | null;
  p25: number | null;
  p75: number | null;
  mad: number | null;
  min: number | null;
  max: number | null;
  sufficient: boolean;
  excluded_years: number[];
  samples: { year: number; expected_total: number | null; raw_total: number }[];
}

export interface Comparison {
  observed: number | null;
  median: number | null;
  absolute_deviation: number | null;
  percent_deviation: number | null;
  z_score: number | null;
  direction: "above" | "below" | "equal" | "unknown";
  percent_reliable: boolean;
}

export interface MonthCalendar {
  year: number;
  month: number;
  month_name: string;
  days: DayCell[];
  summary: PeriodSummary;
  baseline: Baseline;
  comparison: Comparison;
  context: SeriesContext;
}

export interface MonthSummary extends PeriodSummary {
  month: number;
  month_name: string;
}

export interface YearCalendar {
  year: number;
  months: MonthSummary[];
  complete_months: number;
  peak_month: number | null;
  peak_month_name: string | null;
  year_total: number | null;
  context: SeriesContext;
}

export interface HistoryCell {
  month: number;
  value: number | null;
  raw_total: number;
  coverage: number;
  complete: boolean;
  observed_days: number;
  per_sensor: Record<string, number>;
}

export interface HistoryMatrix {
  metric: "harmonized" | "raw";
  years: number[];
  rows: { year: number; months: HistoryCell[] }[];
  scale: { min: number | null; max: number | null; p50: number | null; p90: number | null; n: number };
  context: SeriesContext;
}

export interface TrendYear {
  year: number;
  expected_total: number | null;
  raw_total: number;
  coverage: number;
  complete: boolean;
  observed_days: number;
}

export interface Trends {
  yearly: TrendYear[];
  monthly_profile: { month: number; month_name: string; median: number | null; mean: number | null; n_years: number }[];
  daily: { date: string; harmonized: number; raw_total: number }[];
  top_months: { year: number; month: number; label: string; value: number; raw_total: number }[];
  top_years: { year: number; value: number | null; raw_total: number }[];
  trend: {
    method: string;
    years_used: number[];
    n_years: number;
    theil_sen_slope_per_year: number | null;
    mann_kendall: { n: number; s: number | null; z: number | null; p: number | null; trend: string };
    note: string;
  };
  context: SeriesContext;
}

export interface AnomalyFlag {
  period: string;
  label: string;
  year: number;
  month: number;
  kind: string;
  observed: number;
  median: number;
  absolute_deviation: number;
  percent_deviation: number | null;
  z_score: number | null;
  direction: "above" | "below" | "equal";
  z_threshold: number;
  magnitude: number;
  coverage: number;
  observed_days: number;
  raw_total: number;
  baseline_years: number[];
  n_years: number;
  method: string;
  flagged: boolean;
}

export interface Anomalies {
  threshold: number;
  method: string;
  months_checked: number;
  months_skipped_incomplete: number;
  anomalies: AnomalyFlag[];
  elevated: AnomalyFlag[];
  depressed: AnomalyFlag[];
  context: SeriesContext;
  caveats: string[];
}

export interface SensorCompare {
  available: boolean;
  reason?: string;
  period?: { start: string; end: string };
  paired_days?: number;
  daily_series?: { date: string; modis: number; viirs: number }[];
  daily_bucket?: "day" | "month";
  daily?: {
    modis_mean: number | null;
    viirs_mean: number | null;
    ratio_modis_over_viirs: number | null;
    pearson_log: number | null;
    spearman: number | null;
    median_daily_ratio: number | null;
  };
  per_platform?: Record<string, Record<string, number | null>>;
  spatial?: {
    modis_active_cells: number;
    viirs_active_cells: number;
    cells_in_both: number;
    jaccard: number | null;
    spearman_cell_totals: number | null;
    cells_compared: number;
  };
  co_detection?: {
    available: boolean;
    reason?: string;
    radius_km?: number;
    modis_detections?: number;
    sampled?: number;
    matched?: number;
    fraction?: number | null;
    note?: string;
  } | null;
  sensors?: SensorMeta[];
  interpretation?: Record<string, string>;
  limitations?: string[];
  context?: { aoi: AOIInfo; grid_deg: number };
}

export interface MapCell {
  lat: number;
  lon: number;
  total: number;
  frp: number;
  frp_by_sensor?: Record<string, number>;
  per_sensor: Record<string, number>;
}

export interface MapCells {
  cells: MapCell[];
  max_total: number;
  count: number;
  grid_deg: number;
  period: { start: string; end: string };
  calibration: Calibration;
}

export interface DetectionRow {
  id: number;
  sensor: string;
  platform: string;
  instrument: string;
  product: string;
  processing: string;
  lat: number;
  lon: number;
  acq_date: string;
  acq_time: string;
  acq_ts: string;
  confidence: number | null;
  confidence_raw: string;
  confidence_class: string | null;
  frp: number | null;
  brightness: number | null;
  brightness_bg: number | null;
  daynight: string | null;
  version: string | null;
  source_file: string;
}

export interface DetectionsPage {
  rows: DetectionRow[];
  total: number;
  offset: number;
  limit: number;
  truncated: boolean;
  period: { start: string; end: string };
  context: SeriesContext;
  caveat: string;
}

export interface Harmonization {
  context: SeriesContext;
  calibration: Calibration;
  sensor_timeline: {
    id: string;
    label: string;
    instrument: string;
    colour: string;
    first_date: string;
    last_date: string;
    observed_days: number;
    detections: number;
    mean_per_observed_day: number | null;
    share: number | null;
  }[];
  availability: Record<string, { observed_days: number; first: string | null; last: string | null }>;
  transitions: {
    transitions: {
      sensor: string;
      date: string;
      available: boolean;
      reason?: string;
      harmonized_step_pct?: number | null;
      raw_step_pct?: number | null;
      harmonized_before?: number;
      harmonized_after?: number;
      raw_before?: number;
      raw_after?: number;
    }[];
    note: string;
  };
}

export interface Catalog {
  app: string;
  version: string;
  tagline: string;
  ready: boolean;
  detections: number;
  min_date: string | null;
  max_date: string | null;
  sensors: (SensorMeta & { product: string; records_from: string })[];
  coverage: {
    sensor: string;
    label: string;
    colour: string;
    detections: number;
    first_date: string;
    last_date: string;
    product: string;
    pixel_km: number;
  }[];
  availability: { sensor: string; days: number; lo: string; hi: string }[];
  batches: {
    id: string;
    created_at: string;
    kind: string;
    description: string;
    rows_read: number;
    rows_kept: number;
    rows_rejected: number;
    min_date: string;
    max_date: string;
    quality: string;
  }[];
  grid_deg: number;
  map_key_configured: boolean;
  parameters: Record<string, number>;
  caveat: string;
}

export interface Region {
  id: string;
  name: string;
  bbox: [number, number, number, number];
  description: string;
  biome: string;
}

export interface SearchResult {
  kind: "region" | "city";
  id: string;
  name: string;
  subtitle: string;
  bbox: [number, number, number, number];
  lat?: number;
  lon?: number;
}
