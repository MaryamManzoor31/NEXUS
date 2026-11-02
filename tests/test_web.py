"""Unit tests for NEXUS Web UI and endpoints (Module M10)."""
import unittest
from web.server import app

class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_index_route(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"NEXUS Timetable Generator", resp.data)

    def test_current_schedule_api(self):
        resp = self.client.get("/api/current")
        self.assertEqual(resp.status_code, 200)
        data = resp.json
        self.assertTrue(data["success"])
        self.assertIn("data", data)
        self.assertIn("metrics", data["data"])
        self.assertIn("grid_data", data["data"])

    def test_generate_greedy(self):
        resp = self.client.post("/api/generate", json={
            "scenario": "S1",
            "students": 20,
            "algorithm": "greedy"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["metrics"]["validator_status"], "VALID_COMPLETE")

    def test_export_csv(self):
        resp = self.client.get("/api/export/csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(b"Day,Period,Time Range,Section", resp.data)

    def test_load_sample(self):
        resp = self.client.post("/api/load-sample")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json["success"])

if __name__ == "__main__":
    unittest.main()
