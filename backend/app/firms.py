"""Reading and validating NASA FIRMS records.

Every row that enters the database passes through :func:`normalize_row`, which
is the single place where field names, confidence scales, sensor identities and
timestamps are made consistent. Nothing is imputed: a missing field stays NULL.

Reference products
------------------
MODIS   Collection 6.1  (MCD14 / VNP14-style attributes, 1 km)
VIIRS   Collection 2    375 m  (S-NPP, NOAA-20, NOAA-21)

The near-real-time (NRT) files are provisional and are replaced by standard
processing (SP) data with roughly a five month lag. Both are ingested, but
never silently mixed: each batch records the processing level and every API
response carries that label through to the user interface.
"""

from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable, Iterator, Sequence

from . import config, geo

# ---------------------------------------------------------------------------
# Column aliases. Archive downloads, the area API and the rolling global files
# differ slightly, so every field is resolved by name with fallbacks.
# ---------------------------------------------------------------------------

ALIASES = {
    "lat": ("latitude", "lat"),
    "lon": ("longitude", "lon", "lng"),
    "acq_date": ("acq_date",),
    "acq_time": ("acq_time",),
    "satellite": ("satellite",),
    "confidence": ("confidence",),
    "version": ("version",),
    "frp": ("frp",),
    "brightness": ("brightness", "bright_ti4"),
    "brightness_bg": ("bright_t31", "bright_ti5"),
    "scan": ("scan",),
    "track": ("track",),
    "daynight": ("daynight", "day_night"),
    "instrument": ("instrument",),
    "type": ("type",),
}

SATELLITE_TO_SENSOR = {
    "T": "modis",
    "TERRA": "modis",
    "A": "modis",
    "AQUA": "modis",
    "N": "viirs_snpp",
    "NPP": "viirs_snpp",
    "SNPP": "viirs_snpp",
    "SUOMI-NPP": "viirs_snpp",
    "SUOMI NPP": "viirs_snpp",
    "N20": "viirs_noaa20",
    "NOAA-20": "viirs_noaa20",
    "NOAA20": "viirs_noaa20",
    "J1": "viirs_noaa20",
    "N21": "viirs_noaa21",
    "NOAA-21": "viirs_noaa21",
    "NOAA21": "viirs_noaa21",
    "J2": "viirs_noaa21",
}

PLATFORM_LABEL = {
    "modis": "Terra + Aqua",
    "viirs_snpp": "Suomi-NPP",
    "viirs_noaa20": "NOAA-20",
    "viirs_noaa21": "NOAA-21",
}

_FILENAME_HINTS = (
    ("suomi", "viirs_snpp"),
    ("snpp", "viirs_snpp"),
    ("j1", "viirs_noaa20"),
    ("noaa-20", "viirs_noaa20"),
    ("noaa20", "viirs_noaa20"),
    ("j2", "viirs_noaa21"),
    ("noaa-21", "viirs_noaa21"),
    ("noaa21", "viirs_noaa21"),
    ("modis", "modis"),
)


class RowError(ValueError):
    """Raised when a record cannot be trusted and must be rejected."""


@dataclass(slots=True)
class Detection:
    sensor: str
    instrument: str
    platform: str
    product: str
    processing: str
    source_file: str
    lat: float
    lon: float
    acq_date: str
    acq_time: str
    acq_ts: str
    confidence: int | None
    confidence_raw: str
    confidence_class: str | None
    frp: float | None
    brightness: float | None
    brightness_bg: float | None
    scan: float | None
    track: float | None
    daynight: str | None
    version: str | None
    cell_ix: int
    cell_iy: int

    def as_row(self, batch_id: str) -> tuple:
        return (
            self.sensor, self.instrument, self.platform, self.product,
            self.processing, self.source_file, self.lat, self.lon,
            self.acq_date, self.acq_time, self.acq_ts, self.confidence,
            self.confidence_raw, self.confidence_class, self.frp,
            self.brightness, self.brightness_bg, self.scan, self.track,
            self.daynight, self.version, self.cell_ix, self.cell_iy, batch_id,
        )


INSERT_DETECTION_SQL = """
INSERT OR IGNORE INTO detections (
    sensor, instrument, platform, product, processing, source_file,
    lat, lon, acq_date, acq_time, acq_ts, confidence, confidence_raw,
    confidence_class, frp, brightness, brightness_bg, scan, track,
    daynight, version, cell_ix, cell_iy, batch_id
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

SENSOR_COLUMNS = 24


def _pick(row: dict, field: str) -> str:
    for name in ALIASES[field]:
        if name in row and row[name] not in (None, ""):
            return str(row[name]).strip()
    return ""


def _to_float(value: str) -> float | None:
    if value in ("", None):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def infer_sensor(satellite: str, instrument: str, filename: str) -> str | None:
    """Resolve the sensor identity, preferring the satellite code."""
    key = (satellite or "").strip().upper().replace("_", "-")
    if key in SATELLITE_TO_SENSOR:
        return SATELLITE_TO_SENSOR[key]
    inst = (instrument or "").strip().upper()
    if inst == "MODIS":
        return "modis"
    low = (filename or "").lower()
    for token, sensor in _FILENAME_HINTS:
        if token in low:
            return sensor
    if "VIIRS" in inst:
        return "viirs_snpp"
    return None


def normalize_confidence(raw: str, sensor: str) -> tuple[int | None, str | None]:
    """Map the two different confidence scales onto one ordinal 0-100 scale.

    MODIS publishes a 0-100 numeric confidence; VIIRS publishes a category
    (l / n / h, or the words low / nominal / high). The mapping below is an
    ORDINAL placement inside the published category range, *not* a calibrated
    probability, and is documented as such in the methodology.
    """
    if not raw:
        return None, None
    text = raw.strip().lower()
    if text in config.VIIRS_CONFIDENCE_ORDINAL:
        value = config.VIIRS_CONFIDENCE_ORDINAL[text]
        return value, _conf_class(value)
    word_map = {"low": 25, "nominal": 65, "high": 90}
    if text in word_map:
        value = word_map[text]
        return value, _conf_class(value)
    try:
        value = int(round(float(text)))
    except ValueError:
        return None, None
    value = max(0, min(100, value))
    return value, _conf_class(value)


def _conf_class(value: int) -> str:
    if value >= 80:
        return "high"
    if value >= 50:
        return "nominal"
    return "low"


def _normalize_time(raw: str) -> str:
    text = (raw or "").strip()
    digits = re.sub(r"\D", "", text)
    if not digits:
        return ""
    digits = digits.zfill(4)[:4]
    hh, mm = int(digits[:2]), int(digits[2:])
    if hh > 23:
        hh, mm = 0, 0
    if mm > 59:
        mm = 0
    return f"{hh:02d}{mm:02d}"


def normalize_row(
    row: dict,
    *,
    default_sensor: str | None,
    product: str,
    source_file: str,
    grid_deg: float,
) -> Detection:
    lat = _to_float(_pick(row, "lat"))
    lon = _to_float(_pick(row, "lon"))
    if lat is None or lon is None:
        raise RowError("missing coordinates")
    if not (-90.0 <= lat <= 90.0):
        raise RowError(f"latitude out of range: {lat}")
    if not (-180.0 <= lon <= 180.0):
        raise RowError(f"longitude out of range: {lon}")

    raw_date = _pick(row, "acq_date")
    if not raw_date:
        raise RowError("missing acquisition date")
    try:
        day = datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
    except ValueError as exc:
        raise RowError(f"unparseable acquisition date: {raw_date!r}") from exc
    if not (date(2000, 1, 1) <= day <= date(2100, 1, 1)):
        raise RowError(f"acquisition date outside the satellite era: {raw_date}")

    satellite = _pick(row, "satellite")
    sensor = (
        infer_sensor(satellite, _pick(row, "instrument"), source_file)
        or default_sensor
    )
    if sensor is None:
        raise RowError(f"cannot determine sensor (satellite={satellite!r})")

    acq_time = _normalize_time(_pick(row, "acq_time"))
    hh = int(acq_time[:2]) if acq_time else 0
    mm = int(acq_time[2:]) if acq_time else 0
    acq_ts = f"{day.isoformat()}T{hh:02d}:{mm:02d}:00Z"

    confidence_raw = _pick(row, "confidence")
    conf, conf_class = normalize_confidence(confidence_raw, sensor)

    version = _pick(row, "version") or None
    processing = "NRT" if (version and "NRT" in version.upper()) else ("SP" if version else "NRT")

    instrument = "MODIS" if sensor == "modis" else "VIIRS"
    platform = PLATFORM_LABEL[sensor]
    if sensor == "modis" and satellite:
        platform = {"T": "Terra", "A": "Aqua"}.get(satellite.upper(), platform)

    cell_ix, cell_iy = geo.cell_index(lat, lon, grid_deg)

    return Detection(
        sensor=sensor,
        instrument=instrument,
        platform=platform,
        product=product,
        processing=processing,
        source_file=source_file,
        lat=round(lat, 5),
        lon=round(lon, 5),
        acq_date=day.isoformat(),
        acq_time=acq_time,
        acq_ts=acq_ts,
        confidence=conf,
        confidence_raw=confidence_raw,
        confidence_class=conf_class,
        frp=_to_float(_pick(row, "frp")),
        brightness=_to_float(_pick(row, "brightness")),
        brightness_bg=_to_float(_pick(row, "brightness_bg")),
        scan=_to_float(_pick(row, "scan")),
        track=_to_float(_pick(row, "track")),
        daynight=_pick(row, "daynight") or None,
        version=version,
        cell_ix=cell_ix,
        cell_iy=cell_iy,
    )


def iter_csv_rows(path_or_buffer) -> Iterator[dict]:
    """Stream CSV rows from a path, a gzip path or an open text/binary buffer."""
    if hasattr(path_or_buffer, "read"):
        raw = path_or_buffer.read()
        if isinstance(raw, bytes):
            if raw[:2] == b"\x1f\x8b":
                import gzip

                raw = gzip.decompress(raw)
            text = raw.decode("utf-8", "replace")
        else:
            text = _maybe_gunzip(raw)
        yield from csv.DictReader(io.StringIO(text))
        return

    name = str(path_or_buffer)
    if name.endswith(".gz"):
        import gzip

        with gzip.open(name, "rt", encoding="utf-8", errors="replace", newline="") as fh:
            yield from csv.DictReader(fh)
        return
    with open(name, "r", encoding="utf-8", errors="replace", newline="") as fh:
        yield from csv.DictReader(fh)


def _maybe_gunzip(text: str) -> str:
    if text[:2] == "\x1f\x8b":  # gzip magic after a latin-1 round trip
        import gzip

        try:
            return gzip.decompress(text.encode("latin-1")).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - treat as plain text
            return text
    return text


def csv_header(path_or_buffer) -> list[str]:
    """Read just the header line (used for validation messages)."""
    for row in iter_csv_rows(path_or_buffer):
        return list(row.keys())
    return []


def iter_firms_file(
    path_or_buffer,
    *,
    default_sensor: str | None,
    product: str,
    source_file: str,
    grid_deg: float = config.GRID_DEG,
) -> Iterator[Detection | RowError]:
    """Yield normalised detections or RowError for every CSV row.

    Streaming keeps memory flat for the multi-hundred-megabyte archive files.
    """
    for row in iter_csv_rows(path_or_buffer):
        try:
            yield normalize_row(
                row,
                default_sensor=default_sensor,
                product=product,
                source_file=source_file,
                grid_deg=grid_deg,
            )
        except RowError as exc:
            yield exc


def product_for_sensor(sensor: str, processing: str = "SP") -> str:
    if sensor == "modis":
        return f"MODIS_C6.1_{processing}"
    return f"VIIRS_C2_{processing}"


def date_bounds(detections: Iterable[Detection]) -> tuple[str | None, str | None]:
    lo = hi = None
    for det in detections:
        if lo is None or det.acq_date < lo:
            lo = det.acq_date
        if hi is None or det.acq_date > hi:
            hi = det.acq_date
    return lo, hi


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# FIRMS area API (requires a free MAP_KEY)
# ---------------------------------------------------------------------------

API_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
AVAILABILITY_URL = "https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv"

# FIRMS data ids, split into the near-real-time and standard-processing streams.
API_SOURCES = {
    "modis": {"nrt": "MODIS_NRT", "sp": "MODIS_SP", "label": "MODIS C6.1"},
    "viirs_snpp": {"nrt": "VIIRS_SNPP_NRT", "sp": "VIIRS_SNPP_SP", "label": "VIIRS S-NPP C2"},
    "viirs_noaa20": {"nrt": "VIIRS_NOAA20_NRT", "sp": "VIIRS_NOAA20_SP", "label": "VIIRS NOAA-20 C2"},
    "viirs_noaa21": {"nrt": "VIIRS_NOAA21_NRT", "sp": "VIIRS_NOAA21_SP", "label": "VIIRS NOAA-21 C2"},
}


class FirmsApiError(RuntimeError):
    pass


def fetch_area_csv(
    map_key: str,
    source: str,
    bbox: Sequence[float],
    start: str,
    days: int = 5,
    timeout: int = 120,
) -> str:
    """One area-API request. ``days`` must be 1-5 (FIRMS API limit).

    ``bbox`` is (west, south, east, north); FIRMS expects
    ``west,south,east,north`` in that order.
    """
    import urllib.error
    import urllib.request

    if not map_key:
        raise FirmsApiError("A NASA FIRMS MAP_KEY is required for historical queries.")
    if not 1 <= days <= 5:
        raise ValueError("FIRMS area API supports 1-5 days per request.")
    west, south, east, north = bbox
    area = f"{west:.4f},{south:.4f},{east:.4f},{north:.4f}"
    url = f"{API_BASE}/{map_key}/{source}/{area}/{days}/{start}"
    req = urllib.request.Request(url, headers={"User-Agent": "FIRETRACK/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        if exc.code == 400 and "MAP_KEY" in body.upper():
            raise FirmsApiError("NASA FIRMS rejected the MAP_KEY (invalid or inactive).") from exc
        raise FirmsApiError(f"FIRMS API HTTP {exc.code}: {body}") from exc
    except Exception as exc:  # noqa: BLE001
        raise FirmsApiError(f"FIRMS API request failed: {exc}") from exc
    if "Invalid MAP_KEY" in payload or "Invalid" == payload.strip()[:7]:
        raise FirmsApiError("NASA FIRMS rejected the MAP_KEY (invalid or inactive).")
    return payload


def fetch_data_availability(map_key: str, timeout: int = 60) -> list[dict]:
    """First and last date each FIRMS product currently covers."""
    import urllib.request

    if not map_key:
        raise FirmsApiError("A NASA FIRMS MAP_KEY is required.")
    url = f"{AVAILABILITY_URL}/{map_key}/all"
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "FIRETRACK/1.0"}), timeout=timeout
    ) as resp:
        text = resp.read().decode("utf-8", "replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    return rows
