"""Tests for the three scientific corrections (A1 availability, A2 FRP, A3 periods).

Synthetic fixtures only, in throw-away databases. Each class restores the
environment so it cannot disturb the other test modules.
"""

from __future__ import annotations

import os
import unittest

import fixtures
from app import analytics, db, geo, harmonize, ingest

AOI = geo.AOI(name="Corrections box", bbox=fixtures.AOI_BBOX)


class _EnvGuard(unittest.TestCase):
    """Points the app at a private database and restores it afterwards."""

    @classmethod
    def setUpClass(cls):
        fixtures.get_fixture()  # make sure the shared fixture database exists
        cls._previous_db = os.environ.get("FIRETRACK_DB")
        cls.path = fixtures.fresh_database()

    @classmethod
    def tearDownClass(cls):
        if cls._previous_db:
            os.environ["FIRETRACK_DB"] = cls._previous_db
        db.reset_connection()


class TestAvailabilityCorrection(_EnvGuard):
    """A1: availability must not extend past a sensor's delivery window."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The sensor delivers through 2019-06-30 only, so later dates genuinely
        # have no detections and a stale availability row is unambiguous.
        fixtures.build_synthetic(start="2018-01-01", end="2019-06-30")
        ingest.store_product_windows([
            {"data_id": "MODIS_SP", "min_date": "2000-11-01", "max_date": "2026-11-15"},
            {"data_id": "VIIRS_NOAA20_SP", "min_date": "2018-04-01", "max_date": "2019-06-30"},
        ])

    def test_windows_are_stored_per_sensor(self):
        windows = ingest.sensor_window_map()
        self.assertEqual(windows["viirs_noaa20"], ("2018-04-01", "2019-06-30"))
        self.assertIn("modis", windows)

    def test_register_observation_days_ignores_dates_outside_window(self):
        """A queried date after the sensor stopped must not become 'observed'."""
        before = db.scalar(
            "SELECT COUNT(*) FROM sensor_days WHERE sensor = ? AND acq_date > ?",
            ("viirs_noaa20", "2019-06-30"), default=0,
        )
        ingest.register_observation_days("viirs_noaa20", ["2019-07-05", "2019-07-06", "2019-07-07"])
        after = db.scalar(
            "SELECT COUNT(*) FROM sensor_days WHERE sensor = ? AND acq_date > ?",
            ("viirs_noaa20", "2019-06-30"), default=0,
        )
        self.assertEqual(after, before, "dates outside the delivery window were registered")

    def test_stale_days_removed_but_detections_preserved(self):
        # Simulate the historical bug: availability rows past the window, no data.
        conn = db.connect()
        stale = [("viirs_noaa20", f"2019-07-{d:02d}") for d in range(1, 11)]
        conn.executemany(
            "INSERT OR REPLACE INTO sensor_days(sensor, acq_date, observed, n_global) VALUES(?,?,1,0)",
            stale,
        )
        conn.commit()

        detections_before = db.scalar("SELECT COUNT(*) FROM detections", default=0)
        report = ingest.bound_sensor_days()
        detections_after = db.scalar("SELECT COUNT(*) FROM detections", default=0)

        self.assertGreater(report["trimmed"], 0)
        self.assertEqual(detections_before, detections_after,
                         "the availability repair must never delete detections")
        left = db.query(
            "SELECT acq_date FROM sensor_days WHERE sensor = ? AND acq_date BETWEEN ? AND ?",
            ("viirs_noaa20", "2019-07-01", "2019-07-10"),
        )
        self.assertEqual([r["acq_date"] for r in left], [],
                         "stale availability days were not removed")

    def test_days_with_real_detections_are_protected(self):
        """Even outside the reported window, a date with detections is preserved."""
        from app import firms

        det = fixtures._dets_for_day("2019-08-15", "viirs_noaa20", 1, "NOAA-20", "VIIRS", "VIIRS C2")
        ingest.ingest_detections(det, kind="test_synthetic", description=fixtures.SYNTHETIC_DESCRIPTION)
        db.connect().execute(
            "INSERT OR REPLACE INTO sensor_days(sensor, acq_date, observed, n_global) VALUES(?,?,1,0)",
            ("viirs_noaa20", "2019-08-15"),
        )
        db.connect().commit()

        report = ingest.bound_sensor_days()
        self.assertGreaterEqual(report["protected"], 1)
        kept = db.scalar(
            "SELECT COUNT(*) FROM sensor_days WHERE sensor = ? AND acq_date = ?",
            ("viirs_noaa20", "2019-08-15"), default=0,
        )
        self.assertEqual(kept, 1, "a day with real detections must not be trimmed")

    def test_other_sensors_untouched(self):
        before = db.scalar("SELECT COUNT(*) FROM sensor_days WHERE sensor = 'modis'", default=0)
        ingest.bound_sensor_days()
        after = db.scalar("SELECT COUNT(*) FROM sensor_days WHERE sensor = 'modis'", default=0)
        self.assertEqual(before, after, "MODIS availability must be unaffected")


class TestFrpSeparation(_EnvGuard):
    """A2: FRP is reported per sensor; any cross-sensor sum is labelled."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fixtures.build_synthetic(start="2019-01-01", end="2019-03-31")
        cls.harmonised = harmonize.build(AOI)

    def test_daily_point_has_per_sensor_frp(self):
        point = self.harmonised.day("2019-02-01")
        self.assertIsNotNone(point)
        self.assertEqual(set(point.frp_by_sensor), set(point.sensors_observing))
        for sensor, count in point.per_sensor.items():
            # the fixture gives every detection FRP = 10.0
            self.assertAlmostEqual(point.frp_by_sensor[sensor], count * 10.0, delta=0.01)

    def test_total_is_labelled_as_unharmonised_sum(self):
        payload = self.harmonised.day("2019-02-01").to_dict()
        self.assertIn("frp_by_sensor", payload)
        self.assertIn("frp_total", payload)
        self.assertEqual(payload["frp_total_label"], "sum of raw sensor FRP (not harmonised)")
        self.assertAlmostEqual(
            payload["frp_total"], sum(payload["frp_by_sensor"].values()), delta=0.2
        )

    def test_period_summary_keeps_sensors_apart(self):
        agg = harmonize.aggregate_period(self.harmonised, "2019-02-01", "2019-02-28")
        self.assertIn("frp_by_sensor", agg)
        self.assertEqual(set(agg["frp_by_sensor"]), {"modis", "viirs_noaa20"})
        daily_sum = sum(
            p.frp_by_sensor.get("modis", 0.0)
            for p in self.harmonised.points("2019-02-01", "2019-02-28")
        )
        self.assertAlmostEqual(agg["frp_by_sensor"]["modis"], daily_sum, delta=0.5)
        self.assertAlmostEqual(
            agg["frp_total"], sum(agg["frp_by_sensor"].values()), delta=0.5
        )

    def test_sensor_frp_differs_between_sensors(self):
        """VIIRS has more detections than MODIS here, so its FRP must differ too."""
        agg = harmonize.aggregate_period(self.harmonised, "2019-02-01", "2019-02-28")
        self.assertNotAlmostEqual(
            agg["frp_by_sensor"]["modis"], agg["frp_by_sensor"]["viirs_noaa20"], delta=1.0
        )


class TestCriticalPeriods(_EnvGuard):
    """A3: contiguous high-activity periods with gaps and incomplete months handled."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fixtures.build_synthetic(
            start="2018-01-01", end="2021-12-31",
            skip_ranges=(("2020-06-05", "2020-06-14"),),
            # A five-day episode far above normal, which is how a real fire
            # period looks: a small share of days, clearly above the 90th
            # percentile of the same calendar month.
            spike_ranges=(("2021-02-10", "2021-02-14", 12.0),
                          ("2021-02-27", "2021-03-03", 12.0)),
        )
        cls.harmonised = harmonize.build(AOI)
        cls.result = analytics.critical_periods(cls.harmonised)

    def test_detects_the_boosted_period(self):
        periods = self.result["periods"]
        self.assertGreater(len(periods), 0)
        self.assertTrue(
            any(p["start"].startswith("2021-02") or p["end"].startswith("2021-02") for p in periods),
            "the boosted February 2021 should produce a critical period",
        )

    def test_each_period_has_required_fields(self):
        period = self.result["periods"][0]
        for field in ("start", "end", "duration_days", "peak_date", "peak_value",
                      "threshold", "baseline_years", "sensors"):
            self.assertIn(field, period)
        self.assertGreaterEqual(period["duration_days"], self.result["min_days"])
        self.assertGreaterEqual(period["peak_value"], period["threshold"])

    def test_periods_do_not_span_calendar_months(self):
        """Every reported period has one calendar-month threshold."""
        for period in self.result["periods"]:
            self.assertEqual(
                period["start"][:7], period["end"][:7],
                f"period {period['start']}..{period['end']} spans calendar months",
            )

    def test_missing_days_break_a_period(self):
        """No period may span the 2020-06-05..14 data gap."""
        for period in self.result["periods"]:
            spans_gap = period["start"] <= "2020-06-14" and period["end"] >= "2020-06-05"
            self.assertFalse(
                spans_gap,
                f"period {period['start']}..{period['end']} bridges a data gap",
            )

    def test_incomplete_month_is_excluded(self):
        """June 2020 failed the coverage gate, so it cannot host a period."""
        for period in self.result["periods"]:
            self.assertFalse(
                period["start"].startswith("2020-06") and period["end"].startswith("2020-06"),
                "a period was placed inside an incomplete month",
            )

    def test_thresholds_come_from_complete_months(self):
        baseline = self.result["baseline"]
        for month in range(1, 13):
            entry = baseline[month]
            if entry["threshold"] is None:
                continue
            self.assertGreater(entry["n_days"], 0)
            self.assertGreaterEqual(entry["threshold"], entry["median"])

    def test_percentile_is_configurable(self):
        loose = analytics.critical_periods(self.harmonised, percentile=50, min_days=1)
        strict = analytics.critical_periods(self.harmonised, percentile=95, min_days=1)
        self.assertGreaterEqual(len(loose["periods"]), len(strict["periods"]))

    def test_caveat_about_emergencies_present(self):
        joined = " ".join(self.result["caveats"]).lower()
        self.assertIn("not a confirmed wildfire emergency", joined)


if __name__ == "__main__":
    unittest.main()
