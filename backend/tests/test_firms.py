"""Unit tests for FIRMS record parsing and normalisation.

These tests use small inline strings only; no NASA file is required and no
synthetic record is presented as real data.
"""

from __future__ import annotations

import io
import unittest

from app import config, firms


class TestSensorInference(unittest.TestCase):
    def test_modis_satellite_codes(self):
        self.assertEqual(firms.infer_sensor("T", "", ""), "modis")
        self.assertEqual(firms.infer_sensor("A", "", ""), "modis")

    def test_viirs_platform_codes(self):
        self.assertEqual(firms.infer_sensor("N20", "", ""), "viirs_noaa20")
        self.assertEqual(firms.infer_sensor("N21", "", ""), "viirs_noaa21")
        self.assertEqual(firms.infer_sensor("N", "", ""), "viirs_snpp")

    def test_filename_fallback(self):
        self.assertEqual(firms.infer_sensor("", "", "J1_VIIRS_C2_Global_7d.csv"), "viirs_noaa20")
        self.assertEqual(firms.infer_sensor("", "", "MODIS_C6_1_Global_7d.csv"), "modis")

    def test_unknown_returns_none(self):
        self.assertIsNone(firms.infer_sensor("ZZ", "", "unknown.csv"))


class TestConfidence(unittest.TestCase):
    def test_modis_numeric_is_preserved(self):
        value, klass = firms.normalize_confidence("85", "modis")
        self.assertEqual(value, 85)
        self.assertEqual(klass, "high")

    def test_modis_zero(self):
        value, klass = firms.normalize_confidence("0", "modis")
        self.assertEqual(value, 0)
        self.assertEqual(klass, "low")

    def test_viirs_letters(self):
        self.assertEqual(firms.normalize_confidence("l", "viirs_snpp")[0], 25)
        self.assertEqual(firms.normalize_confidence("n", "viirs_snpp")[0], 65)
        self.assertEqual(firms.normalize_confidence("h", "viirs_snpp")[0], 90)

    def test_viirs_words(self):
        # Current FIRMS VIIRS files spell the category out.
        self.assertEqual(firms.normalize_confidence("nominal", "viirs_noaa20")[0], 65)
        self.assertEqual(firms.normalize_confidence("low", "viirs_noaa20")[1], "low")

    def test_out_of_range_is_clamped(self):
        self.assertEqual(firms.normalize_confidence("150", "modis")[0], 100)

    def test_unparseable(self):
        self.assertEqual(firms.normalize_confidence("unknown", "modis"), (None, None))


class TestRowNormalisation(unittest.TestCase):
    MODIS_ROW = {
        "latitude": "-3.12", "longitude": "-60.02", "brightness": "330.1",
        "scan": "1.1", "track": "1.0", "acq_date": "2020-08-15", "acq_time": "1345",
        "satellite": "A", "confidence": "72", "version": "6.1NRT",
        "bright_t31": "290.2", "frp": "18.4", "daynight": "D",
    }

    def _normalise(self, row):
        return firms.normalize_row(
            row, default_sensor=None, product="MODIS C6.1",
            source_file="test.csv", grid_deg=config.GRID_DEG,
        )

    def test_happy_path(self):
        det = self._normalise(self.MODIS_ROW)
        self.assertEqual(det.sensor, "modis")
        self.assertEqual(det.platform, "Aqua")
        self.assertEqual(det.acq_date, "2020-08-15")
        self.assertEqual(det.acq_time, "1345")
        self.assertEqual(det.acq_ts, "2020-08-15T13:45:00Z")
        self.assertEqual(det.processing, "NRT")
        self.assertAlmostEqual(det.frp, 18.4)
        self.assertAlmostEqual(det.brightness_bg, 290.2)

    def test_missing_coordinates_rejected(self):
        row = dict(self.MODIS_ROW)
        row["latitude"] = ""
        with self.assertRaises(firms.RowError):
            self._normalise(row)

    def test_out_of_range_coordinates_rejected(self):
        row = dict(self.MODIS_ROW)
        row["latitude"] = "95"
        with self.assertRaises(firms.RowError):
            self._normalise(row)

    def test_bad_date_rejected(self):
        row = dict(self.MODIS_ROW)
        row["acq_date"] = "15/08/2020"
        with self.assertRaises(firms.RowError):
            self._normalise(row)

    def test_pre_satellite_date_rejected(self):
        row = dict(self.MODIS_ROW)
        row["acq_date"] = "1990-01-01"
        with self.assertRaises(firms.RowError):
            self._normalise(row)

    def test_missing_time_is_tolerated(self):
        row = dict(self.MODIS_ROW)
        row["acq_time"] = ""
        det = self._normalise(row)
        self.assertEqual(det.acq_time, "")
        self.assertEqual(det.acq_ts, "2020-08-15T00:00:00Z")

    def test_bad_time_is_zeroed(self):
        row = dict(self.MODIS_ROW)
        row["acq_time"] = "9999"
        det = self._normalise(row)
        self.assertEqual(det.acq_time, "0000")

    def test_viirs_columns(self):
        row = {
            "latitude": "10.0", "longitude": "20.0", "bright_ti4": "340.5",
            "scan": "0.4", "track": "0.4", "acq_date": "2023-03-01", "acq_time": "0120",
            "satellite": "N21", "confidence": "high", "version": "2.0NRT",
            "bright_ti5": "295.0", "frp": "3.2", "daynight": "N",
        }
        det = firms.normalize_row(row, default_sensor=None, product="VIIRS C2",
                                  source_file="J2.csv", grid_deg=config.GRID_DEG)
        self.assertEqual(det.sensor, "viirs_noaa21")
        self.assertEqual(det.instrument, "VIIRS")
        self.assertAlmostEqual(det.brightness, 340.5)
        self.assertAlmostEqual(det.brightness_bg, 295.0)


class TestCsvStreaming(unittest.TestCase):
    def test_reads_from_buffer(self):
        payload = (
            "latitude,longitude,acq_date,acq_time,satellite,confidence,version,frp\n"
            "1.0,2.0,2020-01-01,1200,T,80,6.1,5.0\n"
            "3.0,4.0,2020-01-02,1300,T,60,6.1,7.0\n"
        )
        rows = list(firms.iter_csv_rows(io.StringIO(payload)))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["latitude"], "1.0")

    def test_invalid_rows_are_surfaced_not_raised(self):
        payload = (
            "latitude,longitude,acq_date,acq_time,satellite,confidence,version,frp\n"
            "999,2.0,2020-01-01,1200,T,80,6.1,5.0\n"
        )
        results = list(firms.iter_firms_file(
            io.StringIO(payload), default_sensor=None, product="p",
            source_file="mem.csv", grid_deg=0.25,
        ))
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], firms.RowError)


if __name__ == "__main__":
    unittest.main()
