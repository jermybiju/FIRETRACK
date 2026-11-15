"""Small, dependency-free geospatial helpers.

The project deliberately avoids GeoPandas/Shapely: every operation needed here
(bbox filtering, point-in-polygon, area, grid binning, great-circle distance)
is short enough to implement directly, which keeps installation trivial on a
hackathon laptop.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence

EARTH_RADIUS_KM = 6371.0088


@dataclass
class AOI:
    """A user-selected area of interest."""

    name: str
    bbox: tuple[float, float, float, float]  # west, south, east, north
    polygon: list[list[float]] | None = None  # [[lon, lat], ...] closed ring
    kind: str = "bbox"
    id: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def area_km2(self) -> float:
        if self.polygon and len(self.polygon) >= 3:
            return polygon_area_km2(self.polygon)
        return bbox_area_km2(self.bbox)

    def contains(self, lat: float, lon: float) -> bool:
        w, s, e, n = self.bbox
        if not (s <= lat <= n and w <= lon <= e):
            return False
        if not self.polygon:
            return True
        return point_in_polygon(lon, lat, self.polygon)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "bbox": list(self.bbox),
            "polygon": self.polygon,
            "area_km2": round(self.area_km2, 1),
        }


def bbox_area_km2(bbox: Sequence[float]) -> float:
    """Spherical-excess area of a lat/lon box (accurate at all latitudes)."""
    w, s, e, n = (math.radians(v) for v in bbox)
    return EARTH_RADIUS_KM**2 * abs(math.sin(n) - math.sin(s)) * abs(e - w)


def polygon_area_km2(ring: Iterable[Sequence[float]]) -> float:
    """Area of a small polygon via equal-area projection about its centroid.

    Accurate to well under 1 % for regions smaller than a continent, which is
    the scale this application is designed for.
    """
    pts = list(ring)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return 0.0
    lat0 = sum(p[1] for p in pts) / len(pts)
    kx = math.cos(math.radians(lat0))
    xy = [(p[0] * kx, p[1]) for p in pts]
    acc = 0.0
    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % len(xy)]
        acc += x1 * y2 - x2 * y1
    deg2 = abs(acc) / 2.0
    # 1 degree of latitude = 111.195 km; longitude scaled by cos(lat) already
    return deg2 * (111.195**2)


def point_in_polygon(lon: float, lat: float, ring: Sequence[Sequence[float]]) -> bool:
    """Ray casting; the ring may or may not repeat its first point."""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def cell_index(lat: float, lon: float, res: float) -> tuple[int, int]:
    """Integer index of the analysis-grid cell containing (lat, lon)."""
    return int(math.floor((lat + 90.0) / res)), int(math.floor((lon + 180.0) / res))


def cell_bounds(ix: int, iy: int, res: float) -> tuple[float, float]:
    """South-west corner of a grid cell."""
    return ix * res - 90.0, iy * res - 180.0


def bbox_of(points: Iterable[Sequence[float]]) -> tuple[float, float, float, float]:
    lats = [p[1] for p in points]
    lons = [p[0] for p in points]
    return (min(lons), min(lats), max(lons), max(lats))


def normalize_aoi(payload: dict | None, regions: dict[str, dict] | None = None) -> AOI:
    """Validate an AOI request coming from the browser.

    Accepts {"region_id": "..."} or {"bbox": [w,s,e,n]} with an optional
    "polygon" ring. Raises ValueError with a user-facing message.
    """
    payload = payload or {}
    if payload.get("region_id") and regions and payload["region_id"] in regions:
        reg = regions[payload["region_id"]]
        return AOI(
            name=reg["name"],
            bbox=tuple(reg["bbox"]),
            polygon=reg.get("polygon"),
            kind="region",
            id=payload["region_id"],
        )

    bbox = payload.get("bbox")
    polygon = payload.get("polygon")
    name = (payload.get("name") or "Custom area").strip()[:80] or "Custom area"

    if polygon:
        if len(polygon) < 3:
            raise ValueError("A polygon needs at least three vertices.")
        pts = [[float(p[0]), float(p[1])] for p in polygon]
        for lon, lat in pts:
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError("Polygon coordinates must be valid longitude/latitude.")
        bbox = list(bbox_of(pts)) if not bbox else [float(v) for v in bbox]
        return AOI(name=name, bbox=_validate_bbox(bbox), polygon=pts, kind="polygon")

    if not bbox or len(bbox) != 4:
        raise ValueError("Provide a bounding box [west, south, east, north].")
    return AOI(name=name, bbox=_validate_bbox([float(v) for v in bbox]), kind="bbox")


def _validate_bbox(bbox: Sequence[float]) -> tuple[float, float, float, float]:
    w, s, e, n = bbox
    if not (-180 <= w < e <= 180):
        raise ValueError("Longitude must satisfy -180 <= west < east <= 180.")
    if not (-90 <= s < n <= 90):
        raise ValueError("Latitude must satisfy -90 <= south < north <= 90.")
    if (e - w) * (n - s) < 1e-6:
        raise ValueError("The selected area is too small to analyse.")
    return (w, s, e, n)


def aoi_key(aoi: AOI) -> str:
    """Stable key for caching aggregates per AOI."""
    import hashlib
    import json

    blob = json.dumps(
        {"bbox": aoi.bbox, "polygon": aoi.polygon}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha1(blob.encode()).hexdigest()[:16]
