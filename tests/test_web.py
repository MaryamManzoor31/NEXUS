"""Unit tests for NEXUS Web UI and endpoints (Module M10)."""
import unittest
from unittest.mock import patch
from web.server import app, _schedule_excel_dataset
from web.serializer import serialize_schedule
from nexus_core.models import BaselineAssignment, PREFERRED, Schedule, Section
from tests.fixtures import tiny, tiny_valid

class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_index_route(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"NEXUS Timetable Generator", resp.data)

    def test_index_has_section_first_calendar_controls(self):
        with patch("web.server._ensure_default_dataset"):
            resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        for control in (
            b'id="filterSemester"',
            b'id="filterSection"',
            b'id="btnCalendarView"',
            b'id="btnTabularView"',
            b'<details class="sidebar-disclosure">',
            b'<summary>Additional constraints</summary>',
        ):
            self.assertIn(control, resp.data)
        self.assertNotIn(b'Scheduling rules', resp.data)

    def test_current_schedule_api(self):
        resp = self.client.get("/api/current")
        self.assertEqual(resp.status_code, 200)
        data = resp.json
        self.assertTrue(data["success"])
        self.assertIn("data", data)
        self.assertIn("metrics", data["data"])
        self.assertIn("grid_data", data["data"])

    def test_generate_cpsat(self):
        resp = self.client.post("/api/generate", json={
            "scenario": "S1",
            "students": 20,
            "algorithm": "cpsat"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["metrics"]["validator_status"], "VALID_COMPLETE")
        self.assertIn("stage_a_status", data["data"]["metrics"])
        self.assertIn("stage_b_status", data["data"]["metrics"])

    def test_generation_rejects_non_cpsat_algorithm(self):
        resp = self.client.post("/api/generate", json={
            "scenario": "S1",
            "students": 20,
            "algorithm": "greedy"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Only CP-SAT", resp.json["error"])

    @patch("web.server.cpsat")
    def test_excel_scheduler_requires_every_section(self, solver):
        expected = Schedule(status="OPTIMAL")
        solver.return_value = expected
        ds = tiny()

        result = _schedule_excel_dataset(ds)

        self.assertIs(result, expected)
        solver.assert_called_once_with(
            ds,
            limit_a=60,
            limit_b=10,
            seed=329,
            allow_unscheduled=False,
        )

    def test_section_view_metadata_includes_semester_and_baseline_policy(self):
        ds = tiny()
        ds.sections["A1"] = Section("A1", "A", 20, semester="6", batch="AIML A", stream="AIML")
        ds.baseline[("A1", 0)] = BaselineAssignment("A1", 0, 0, "R1", "F1", PREFERRED)
        section = serialize_schedule(ds, tiny_valid())["entities"]["sections"]["A1"]
        self.assertEqual(section["semester"], "6")
        self.assertEqual(section["batch"], "AIML A")
        self.assertTrue(section["has_baseline"])
        self.assertEqual(section["baseline_mode"], PREFERRED)
        self.assertTrue(section["scheduled"])

    def test_course_allocations_share_university_section_key(self):
        ds = tiny()
        ds.sections["A1"] = Section("A1", "A", 20, semester="6", batch="AIML A")
        ds.sections["L1"] = Section("L1", "L", 20, semester="6", batch="AIML A LAB")

        sections = serialize_schedule(ds, tiny_valid())["entities"]["sections"]

        self.assertEqual(sections["A1"]["university_section"], "AIML A")
        self.assertEqual(sections["A1"]["university_section_names"], ["AIML A"])
        self.assertEqual(sections["A1"]["university_section_key"], sections["L1"]["university_section_key"])

    def test_multi_section_course_allocation_appears_in_each_named_section(self):
        ds = tiny()
        ds.sections["B2"] = Section("B2", "B", 20, semester="6", batch="DA  A, DA B")

        section = serialize_schedule(ds, tiny_valid())["entities"]["sections"]["B2"]

        self.assertEqual(section["university_section_names"], ["DA A", "DA B"])

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
