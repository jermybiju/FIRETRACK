"""HTTP API tests against the synthetic fixture database.

Skipped automatically when httpx (needed by Starlette's TestClient) is not
installed, so the core science tests never depend on an extra package.
"""

from __future__ import annotations

import unittest

import fixtures

try:  # pragma: no cover - environment dependent
    from fastapi.testclient import TestClient

    HAVE_CLIENT = True
except Exception:  # noqa: BLE001
    HAVE_CLIENT = False


@unittest.skipUnless(HAVE_CLIENT, "httpx is required for API tests (pip install -r requirements-dev.txt)")
class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.get_fixture()
        from app.api import app

        cls.client = TestClient(app)
        cls.body = {"aoi": {"bbox": [0.0, 0.0, 4.0, 4.0]}, "start": "2018-01-01", "end": "2021-12-31"}

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ready"])

    def test_catalog(self):
        payload = self.client.get("/api/catalog").json()
        self.assertTrue(payload["ready"])
        self.assertEqual(sorted(payload["coverage"][0])[0], "colour")

    def test_calendar_month(self):
        response = self.client.post("/api/calendar/month", json={**self.body, "year": 2021, "month": 2})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["days"]), 28)
        self.assertIsNotNone(payload["summary"]["expected_total"])
        self.assertTrue(payload["comparison"]["direction"] in {"above", "below", "equal"})

    def test_invalid_aoi_is_rejected(self):
        response = self.client.post("/api/calendar/month", json={"aoi": {"bbox": [10, 0, -10, 5]}})
        self.assertEqual(response.status_code, 400)

    def test_invalid_month_is_rejected(self):
        response = self.client.post("/api/calendar/month", json={**self.body, "year": 2021, "month": 13})
        self.assertEqual(response.status_code, 400)

    def test_detections_pagination(self):
        response = self.client.post("/api/detections", json={**self.body, "limit": 5, "offset": 0})
        payload = response.json()
        self.assertEqual(len(payload["rows"]), 5)
        self.assertGreater(payload["total"], 5)
        second = self.client.post("/api/detections", json={**self.body, "limit": 5, "offset": 5}).json()
        self.assertNotEqual(payload["rows"][0]["id"], second["rows"][0]["id"])

    def test_csv_export_has_rows_and_fields(self):
        response = self.client.post(
            "/api/export/detections.csv",
            json={**self.body, "start": "2020-01-01", "end": "2020-01-02"},
        )
        self.assertEqual(response.status_code, 200)
        lines = response.text.strip().splitlines()
        self.assertGreater(len(lines), 1)
        header = lines[0].split(",")
        for field in ("latitude", "longitude", "acq_date", "confidence", "frp_mw", "source_file"):
            self.assertIn(field, header)
        self.assertEqual(len(lines[0].split(",")), len(lines[1].split(",")))

    def test_report_contains_required_sections(self):
        response = self.client.post("/api/export/report.html", json={**self.body, "year": 2021, "month": 2})
        self.assertEqual(response.status_code, 200)
        text = response.text
        for section in ("Activity summary", "Comparison with the historical median",
                        "Data sources", "Scientific limitations"):
            self.assertIn(section, text)

    def test_compare_sensors(self):
        payload = self.client.post("/api/compare/sensors", json=self.body).json()
        self.assertTrue(payload["available"])
        self.assertGreater(payload["paired_days"], 100)

    def test_anomalies(self):
        payload = self.client.post("/api/anomalies", json=self.body).json()
        self.assertEqual(payload["threshold"], 2.5)
        self.assertTrue(any(f["year"] == 2021 and f["month"] == 2 for f in payload["anomalies"]))

    def test_map_cells(self):
        payload = self.client.post("/api/map/cells", json=self.body).json()
        self.assertGreater(payload["count"], 0)
        self.assertGreater(payload["max_total"], 0)

    def test_archive_upload_accepts_a_real_csv(self):
        csv_text = (
            "latitude,longitude,acq_date,acq_time,satellite,confidence,version,frp\n"
            "1.5,2.5,2019-05-01,1010,T,40,6.1,12.5\n"
        )
        response = self.client.post(
            "/api/ingest/archive?name=tiny_archive.csv", content=csv_text.encode()
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["rows_read"], 1)
        self.assertEqual(payload["rows_kept"], 1)
        self.assertEqual(payload["quality"], "science")
        self.assertEqual(payload["min_date"], "2019-05-01")

    def test_archive_upload_skips_duplicates(self):
        csv_text = (
            "latitude,longitude,acq_date,acq_time,satellite,confidence,version,frp\n"
            "1.5,2.5,2019-05-01,1010,T,40,6.1,12.5\n"
        )
        first = self.client.post(
            "/api/ingest/archive?name=tiny_archive.csv", content=csv_text.encode()
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.post(
            "/api/ingest/archive?name=tiny_archive.csv", content=csv_text.encode()
        )
        payload = second.json()
        self.assertEqual(payload["rows_kept"], 0)
        self.assertGreaterEqual(payload["rows_duplicate"], 1)
        self.assertIn("already in the database", payload["message"])

    def test_archive_upload_rejects_wrong_type_and_empty_body(self):
        bad = self.client.post("/api/ingest/archive?name=notes.txt", content=b"hello")
        self.assertEqual(bad.status_code, 400)
        empty = self.client.post("/api/ingest/archive?name=x.csv", content=b"")
        self.assertEqual(empty.status_code, 400)


if __name__ == "__main__":
    unittest.main()
