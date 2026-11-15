"""Geometry and area-of-interest validation tests."""

from __future__ import annotations

import math
import unittest

from app import geo


class TestAreas(unittest.TestCase):
    def test_bbox_area_one_degree_at_equator(self):
        area = geo.bbox_area_km2((0, 0, 1, 1))
        # 1 degree of latitude is ~111.195 km; longitude shrinks with latitude.
        self.assertAlmostEqual(area, 111.195**2, delta=5)

    def test_bbox_area_shrinks_with_latitude(self):
        equator = geo.bbox_area_km2((0, 0, 1, 1))
        high = geo.bbox_area_km2((0, 60, 1, 61))
        self.assertLess(high, equator * 0.6)

    def test_polygon_matches_bbox_for_square(self):
        square = [[0, 0], [1, 0], [1, 1], [0, 1]]
        self.assertAlmostEqual(
            geo.polygon_area_km2(square), geo.bbox_area_km2((0, 0, 1, 1)),
            delta=geo.bbox_area_km2((0, 0, 1, 1)) * 0.02,
        )

    def test_polygon_area_with_repeated_first_point(self):
        ring = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
        self.assertGreater(geo.polygon_area_km2(ring), 0)


class TestPointInPolygon(unittest.TestCase):
    SQUARE = [[0, 0], [2, 0], [2, 2], [0, 2]]

    def test_inside(self):
        self.assertTrue(geo.point_in_polygon(1.0, 1.0, self.SQUARE))

    def test_outside(self):
        self.assertFalse(geo.point_in_polygon(3.0, 1.0, self.SQUARE))
        self.assertFalse(geo.point_in_polygon(1.0, -1.0, self.SQUARE))

    def test_degenerate_polygon(self):
        self.assertFalse(geo.point_in_polygon(0, 0, [[0, 0], [1, 1]]))


class TestGrid(unittest.TestCase):
    def test_cell_index_and_bounds_roundtrip(self):
        ix, iy = geo.cell_index(10.1, 20.2, 0.25)
        lat0, lon0 = geo.cell_bounds(ix, iy, 0.25)
        self.assertLessEqual(lat0, 10.1)
        self.assertLess(10.1, lat0 + 0.25)
        self.assertLessEqual(lon0, 20.2)
        self.assertLess(20.2, lon0 + 0.25)

    def test_cell_index_negative_coordinates(self):
        ix, iy = geo.cell_index(-33.9, -70.6, 0.25)
        lat0, lon0 = geo.cell_bounds(ix, iy, 0.25)
        self.assertLessEqual(lat0, -33.9)
        self.assertLess(-33.9, lat0 + 0.25)
        self.assertLessEqual(lon0, -70.6)
        self.assertLess(-70.6, lon0 + 0.25)


class TestHaversine(unittest.TestCase):
    def test_known_distance(self):
        # Paris -> London is about 344 km.
        distance = geo.haversine_km(48.8566, 2.3522, 51.5074, -0.1278)
        self.assertAlmostEqual(distance, 344, delta=6)

    def test_zero_distance(self):
        self.assertEqual(geo.haversine_km(0, 0, 0, 0), 0)


class TestNormalizeAOI(unittest.TestCase):
    REGIONS = {"demo": {"name": "Demo", "bbox": [0, 0, 1, 1]}}

    def test_region_lookup(self):
        aoi = geo.normalize_aoi({"region_id": "demo"}, regions=self.REGIONS)
        self.assertEqual(aoi.name, "Demo")
        self.assertEqual(aoi.bbox, (0, 0, 1, 1))

    def test_explicit_bbox(self):
        aoi = geo.normalize_aoi({"bbox": [-1, -2, 3, 4], "name": "X"})
        self.assertEqual(aoi.bbox, (-1, -2, 3, 4))
        self.assertEqual(aoi.kind, "bbox")

    def test_polygon_derives_bbox(self):
        aoi = geo.normalize_aoi({"polygon": [[0, 0], [1, 0], [1, 1]]})
        self.assertEqual(aoi.bbox, (0, 0, 1, 1))
        self.assertEqual(aoi.kind, "polygon")

    def test_inverted_longitude_rejected(self):
        with self.assertRaises(ValueError):
            geo.normalize_aoi({"bbox": [10, 0, -10, 5]})

    def test_inverted_latitude_rejected(self):
        with self.assertRaises(ValueError):
            geo.normalize_aoi({"bbox": [0, 10, 5, 0]})

    def test_missing_bbox_rejected(self):
        with self.assertRaises(ValueError):
            geo.normalize_aoi({})

    def test_too_small_area_rejected(self):
        with self.assertRaises(ValueError):
            geo.normalize_aoi({"bbox": [0, 0, 0.0001, 0.0001]})

    def test_polygon_containment(self):
        aoi = geo.normalize_aoi({"polygon": [[0, 0], [2, 0], [2, 2], [0, 2]]})
        self.assertTrue(aoi.contains(1, 1))
        self.assertFalse(aoi.contains(3, 3))
        self.assertGreater(aoi.area_km2, 0)

    def test_aoi_key_is_stable(self):
        first = geo.normalize_aoi({"bbox": [0, 0, 2, 2]})
        second = geo.normalize_aoi({"bbox": [0, 0, 2, 2]})
        self.assertEqual(geo.aoi_key(first), geo.aoi_key(second))


class TestCellArea(unittest.TestCase):
    def test_cell_area_matches_degree_box(self):
        from app.harmonize import _cell_area_km2

        self.assertAlmostEqual(_cell_area_km2(0.0, 0.25), 111.195**2 * 0.25**2, delta=1)
        # At 60 degrees a cell is about half as wide.
        ratio = _cell_area_km2(60.0, 0.25) / _cell_area_km2(0.0, 0.25)
        self.assertAlmostEqual(ratio, 0.5, delta=0.02)


if __name__ == "__main__":
    unittest.main()
