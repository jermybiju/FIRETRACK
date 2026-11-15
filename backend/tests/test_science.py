"""Scientific behaviour tests on a synthetic, explicitly-labelled record.

The fixture has known sensor rates (3 MODIS + 18 VIIRS detections per summer
day, tripled in winter), a known coverage gap and a known boosted month. That
makes the harmonisation arithmetic checkable by hand.
"""

from __future__ import annotations

import unittest

import fixtures
from app import analytics, geo, harmonize


class ScienceTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ingest = fixtures.get_fixture()
        cls.aoi = geo.AOI(name="Synthetic test box", bbox=fixtures.AOI_BBOX)

    def build(self):
        return harmonize.build(self.aoi)


class TestIngestion(ScienceTestBase):
    def test_records_loaded(self):
        self.assertGreater(self.ingest["rows_kept"], 1000)
        self.assertEqual(self.ingest["rows_rejected"], 0)
        self.assertEqual(sorted(self.ingest["sensors"]), ["modis", "viirs_noaa20"])

    def test_synthetic_batch_is_labelled(self):
        self.assertEqual(self.ingest["kind"], "test_synthetic")
        self.assertIn("SYNTHETIC", self.ingest["description"])

    def test_date_bounds(self):
        self.assertEqual(self.ingest["min_date"], "2018-01-01")
        self.assertEqual(self.ingest["max_date"], "2021-12-31")


class TestCalibration(ScienceTestBase):
    def test_ratio_is_recovered(self):
        harmonised = self.build()
        calibration = harmonised.calibration
        self.assertEqual(calibration.status, "ok", calibration.notes)
        # 3 MODIS per 18 VIIRS detections -> weight 1/6
        self.assertAlmostEqual(calibration.weights["viirs_noaa20"], 3 / 18, delta=0.01)
        self.assertEqual(calibration.weights["modis"], 1.0)

    def test_paired_days_are_counted(self):
        harmonised = self.build()
        self.assertGreater(harmonised.calibration.paired_days["viirs_noaa20"], 1000)

    def test_short_overlap_refuses_calibration(self):
        short = geo.AOI(name="short", bbox=fixtures.AOI_BBOX)
        harmonised = harmonize.build(short, start="2021-12-01", end="2021-12-10")
        self.assertFalse(harmonised.calibration.calibrated)
        self.assertIn(harmonised.calibration.status, {"insufficient_overlap", "single_sensor"})
        for weight in harmonised.calibration.weights.values():
            self.assertEqual(weight, 1.0)


class TestCoverageNormalisation(ScienceTestBase):
    def test_single_sensor_day_matches_two_sensor_day(self):
        """The core promise: losing a sensor must not change the index."""
        harmonised = self.build()
        both = harmonised.day("2020-07-05")      # both sensors observing
        modis_only = harmonised.day("2020-07-02")  # VIIRS gap
        self.assertIsNotNone(both)
        self.assertIsNotNone(modis_only)
        self.assertEqual(len(modis_only.sensors_observing), 1)
        self.assertEqual(len(both.sensors_observing), 2)
        self.assertAlmostEqual(both.harmonized, modis_only.harmonized, delta=0.01)

    def test_raw_total_still_differs(self):
        harmonised = self.build()
        both = harmonised.day("2020-07-05")
        modis_only = harmonised.day("2020-07-02")
        self.assertNotEqual(both.raw_total, modis_only.raw_total)

    def test_harmonised_is_larger_than_raw_on_single_sensor_days(self):
        harmonised = self.build()
        modis_only = harmonised.day("2020-07-02")
        self.assertGreater(modis_only.harmonized, modis_only.raw_total)


class TestMissingData(ScienceTestBase):
    def test_gap_is_not_zero(self):
        harmonised = self.build()
        calendar = analytics.calendar_month(harmonised, 2020, 6)
        gap_days = [day for day in calendar["days"] if 5 <= day["day"] <= 14]
        self.assertEqual(len(gap_days), 10)
        for day in gap_days:
            self.assertFalse(day["observed"])
            self.assertIsNone(day["harmonized"])
            self.assertIsNone(day["raw_total"])

    def test_incomplete_month_flagged(self):
        harmonised = self.build()
        calendar = analytics.calendar_month(harmonised, 2020, 6)
        self.assertFalse(calendar["summary"]["complete"])
        self.assertLess(calendar["summary"]["coverage"], 0.8)
        self.assertEqual(calendar["summary"]["observed_days"], 20)

    def test_incomplete_month_excluded_from_baseline(self):
        harmonised = self.build()
        baseline = harmonize.daily_median_baseline(harmonised, 6, exclude_year=2021)
        self.assertNotIn(2020, baseline["years_used"])
        self.assertIn(2019, baseline["years_used"])

    def test_coverage_corrected_total(self):
        harmonised = self.build()
        calendar = analytics.calendar_month(harmonised, 2020, 6)
        summary = calendar["summary"]
        expected = summary["observed_total"] * (30 / 20)
        self.assertAlmostEqual(summary["expected_total"], expected, delta=0.5)

    def test_empty_period_returns_nulls(self):
        harmonised = self.build()
        empty = harmonize.aggregate_period(harmonised, "2030-01-01", "2030-01-31")
        self.assertFalse(empty["has_data"])
        self.assertIsNone(empty["expected_total"])
        self.assertEqual(empty["observed_days"], 0)


class TestHistoricalMedian(ScienceTestBase):
    def test_median_uses_complete_years(self):
        harmonised = self.build()
        calendar = analytics.calendar_month(harmonised, 2021, 1)
        baseline = calendar["baseline"]
        self.assertIn(2019, baseline["years_used"])
        self.assertIn(2020, baseline["years_used"])
        self.assertNotIn(2021, baseline["years_used"])
        self.assertIsNotNone(baseline["median"])

    def test_seasonal_signal_is_visible(self):
        harmonised = self.build()
        january = harmonize.aggregate_period(harmonised, "2020-01-01", "2020-01-31")
        july = harmonize.aggregate_period(harmonised, "2020-07-01", "2020-07-31")
        self.assertGreater(january["expected_total"], july["expected_total"] * 2)

    def test_percent_suppressed_for_tiny_baselines(self):
        comparison = harmonize.compare_to_baseline(4.0, {"median": 2.0, "mad": 0.4})
        self.assertFalse(comparison["percent_reliable"])
        self.assertIsNotNone(comparison["percent_deviation"])

    def test_percent_allowed_for_meaningful_baselines(self):
        comparison = harmonize.compare_to_baseline(150.0, {"median": 100.0, "mad": 10.0})
        self.assertTrue(comparison["percent_reliable"])
        self.assertAlmostEqual(comparison["percent_deviation"], 50.0)

    def test_robust_z_score(self):
        comparison = harmonize.compare_to_baseline(150.0, {"median": 100.0, "mad": 10.0})
        # (150 - 100) / (1.4826 * 10)
        self.assertAlmostEqual(comparison["z_score"], 3.37, delta=0.02)

    def test_zero_mad_yields_no_z(self):
        comparison = harmonize.compare_to_baseline(150.0, {"median": 100.0, "mad": 0.0})
        self.assertIsNone(comparison["z_score"])


class TestAnomalies(ScienceTestBase):
    def test_boosted_month_is_flagged(self):
        harmonised = self.build()
        result = analytics.anomalies(harmonised)
        feb_2021 = [flag for flag in result["anomalies"]
                    if flag["year"] == 2021 and flag["month"] == 2]
        self.assertEqual(len(feb_2021), 1)
        self.assertTrue(feb_2021[0]["flagged"])
        self.assertEqual(feb_2021[0]["direction"], "above")

    def test_normal_month_is_not_flagged(self):
        harmonised = self.build()
        result = analytics.anomalies(harmonised)
        flagged = {(flag["year"], flag["month"]) for flag in result["anomalies"]}
        self.assertNotIn((2020, 3), flagged)

    def test_incomplete_months_are_skipped_not_flagged(self):
        harmonised = self.build()
        result = analytics.anomalies(harmonised)
        self.assertNotIn((2020, 6), {(f["year"], f["month"]) for f in result["anomalies"]})
        self.assertGreater(result["months_skipped_incomplete"], 0)


class TestTrendsAndCalendar(ScienceTestBase):
    def test_history_matrix_shape(self):
        harmonised = self.build()
        matrix = analytics.history_matrix(harmonised)
        self.assertEqual(matrix["years"], [2018, 2019, 2020, 2021])
        self.assertEqual(len(matrix["rows"]), 4)
        self.assertEqual(len(matrix["rows"][0]["months"]), 12)

    def test_trend_uses_all_complete_years(self):
        harmonised = self.build()
        result = analytics.trends(harmonised)
        self.assertEqual(result["trend"]["n_years"], 4)
        self.assertIn(
            result["trend"]["mann_kendall"]["trend"],
            {"increasing", "decreasing", "no_significant_trend"},
        )

    def test_year_calendar_totals(self):
        harmonised = self.build()
        year = analytics.calendar_year(harmonised, 2020)
        self.assertEqual(len(year["months"]), 12)
        self.assertGreater(year["year_total"], 0)
        self.assertEqual(year["complete_months"], 11)  # June 2020 is incomplete

    def test_sensor_timeline(self):
        harmonised = self.build()
        timeline = analytics.sensor_timeline(harmonised)["sensors"]
        self.assertEqual(len(timeline), 2)
        shares = sum(row["share"] for row in timeline)
        self.assertAlmostEqual(shares, 1.0, delta=0.01)

    def test_mann_kendall_detects_monotonic_series(self):
        values = [1, 2, 3, 4, 5, 6]
        result = analytics._mann_kendall(values)
        self.assertEqual(result["trend"], "increasing")
        self.assertLess(result["p"], 0.05)

    def test_mann_kendall_flat_series(self):
        result = analytics._mann_kendall([5, 5, 5, 5, 5])
        self.assertEqual(result["trend"], "no_significant_trend")


class TestConfidenceFilter(ScienceTestBase):
    def test_high_confidence_reduces_counts(self):
        harmonised = self.build()
        # The fixture labels everything "nominal", so a high-only filter removes it.
        series = harmonize.load_series(self.aoi, confidence="high")
        self.assertEqual(series.n_detections, 0)


if __name__ == "__main__":
    unittest.main()
