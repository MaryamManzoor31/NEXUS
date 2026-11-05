"""Unit tests for NEXUS Web UI and endpoints (Module M10)."""
import unittest
from unittest.mock import patch
from web.server import app, _apply_semester_sessions, _schedule_excel_dataset
from web.server import STATE, STATE_LOCK
from web.serializer import serialize_schedule
from nexus_core.models import AFTERNOON_SESSION, BaselineAssignment, MORNING_SESSION, PREFERRED, Schedule, Section
from tests.fixtures import tiny, tiny_valid

class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_index_route(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"NEXUS | Academic Timetable", resp.data)

    def test_index_has_section_first_calendar_controls(self):
        with patch("web.server._ensure_default_dataset"):
            resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        for control in (
            b'id="filterSemester"',
            b'id="filterSection"',
            b'id="groupSemesterSession"',
            b'id="semesterSessionControls"',
            b'id="btnCalendarView"',
            b'id="btnTabularView"',
            b'<details class="sidebar-disclosure">',
            b'<summary>Additional constraints</summary>',
        ):
            self.assertIn(control, resp.data)
        self.assertNotIn(b'Scheduling rules', resp.data)

    def test_api_state_lock_is_released_after_request(self):
        response = self.client.get("/api/current")
        self.assertEqual(response.status_code, 200)
        acquired = STATE_LOCK.acquire(blocking=False)
        self.assertTrue(acquired)
        if acquired:
            STATE_LOCK.release()

    def test_current_schedule_api_loads_baseline_without_optimizing(self):
        previous = STATE.copy()
        STATE.update({
            "dataset": None, "schedule": None, "original_schedule": None,
            "comparison": None, "meta": {},
            "active_method": "baseline", "import_issues": [],
        })
        try:
            with patch("web.server.cpsat", side_effect=AssertionError("startup must not optimize")):
                resp = self.client.get("/api/current")
        finally:
            STATE.clear()
            STATE.update(previous)
        self.assertEqual(resp.status_code, 200)
        data = resp.json
        self.assertTrue(data["success"])
        self.assertEqual(data["active_method"], "baseline")
        self.assertIn("data", data)
        self.assertIn("metrics", data["data"])
        self.assertIn("grid_data", data["data"])
        self.assertEqual(data["data"]["metrics"]["method"], "baseline")
        self.assertTrue(data["data"]["meta"]["original_timetable_loaded"])
        self.assertEqual(data["data"]["meta"]["student_data_mode"], "representative")

    def test_generate_cpsat(self):
        resp = self.client.post("/api/generate", json={
            "scenario": "S1",
            "students": 20,
            "algorithm": "cpsat"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json
        self.assertTrue(data["success"])
        self.assertIn(data["data"]["metrics"]["validator_status"], ("VALID_COMPLETE", "VALID_INCOMPLETE"))
        if data["data"]["metrics"]["validator_status"] == "VALID_INCOMPLETE":
            self.assertGreater(data["data"]["metrics"]["total_selections"], 0)
            self.assertGreater(data["data"]["metrics"]["unplaced_selections"].split("/")[0], "0")
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
            limit_a=50,
            limit_b=35,
            total_limit=90.0,
            seed=329,
            workers=4,
            allow_unscheduled=True,
        )

    def test_semester_session_configuration_requires_all_included_semesters(self):
        ds = tiny()
        ds.sections = {
            sid: Section(
                section.id, section.course_id, section.capacity, semester="6"
            )
            for sid, section in ds.sections.items()
        }

        with self.assertRaisesRegex(ValueError, "Choose a morning or afternoon"):
            _apply_semester_sessions(ds, "all", {})

        _apply_semester_sessions(ds, "all", {"6": AFTERNOON_SESSION})
        self.assertEqual(ds.meta["semester_sessions"], {"6": AFTERNOON_SESSION})

    @patch("web.server.parse_allocation_workbook")
    @patch("web.server.os.path.isfile", return_value=True)
    def test_load_excel_rejects_missing_semester_session_choice(self, _isfile, parse_workbook):
        ds = tiny()
        ds.sections = {
            sid: Section(section.id, section.course_id, section.capacity, semester="6")
            for sid, section in ds.sections.items()
        }
        parse_workbook.return_value = (ds, {})

        response = self.client.post("/api/load-excel", json={"semester": "6"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Choose a morning or afternoon session", response.json["error"])

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

    def test_schedule_metadata_exposes_ten_session_grid_and_student_sessions(self):
        ds = tiny()
        ds.meta["semester_sessions"] = {"6": MORNING_SESSION}
        sched = tiny_valid()
        sched.student_categories = {"S1": {0: MORNING_SESSION}}

        payload = serialize_schedule(ds, sched)

        self.assertEqual(payload["meta"]["total_slots"], 50)
        self.assertEqual(len(payload["meta"]["periods"]), 10)
        self.assertEqual(payload["meta"]["periods"][0]["label"], "Session 1")
        self.assertEqual(payload["meta"]["periods"][0]["time"], "08:00 - 08:55")
        self.assertEqual(
            [period["time"] for period in payload["meta"]["periods"]],
            [
                "08:00 - 08:55",
                "09:00 - 09:55",
                "10:00 - 10:55",
                "11:05 - 12:00",
                "12:05 - 13:00",
                "13:10 - 14:05",
                "14:10 - 15:05",
                "15:10 - 16:00",
                "16:15 - 17:10",
                "17:15 - 18:00",
            ],
        )
        self.assertEqual(
            payload["entities"]["students"]["S1"]["session_by_day"]["Monday"],
            "Morning Session (8:00 AM-1:00 PM)",
        )
        self.assertIn("H15", {constraint["id"] for constraint in payload["constraints"]})
        self.assertIn("H16", {constraint["id"] for constraint in payload["constraints"]})
        self.assertIn("H18", {constraint["id"] for constraint in payload["constraints"]})
        self.assertEqual(payload["meta"]["semester_sessions"], {"6": MORNING_SESSION})

    def test_unplaced_selection_diagnostics_are_serialized(self):
        ds = tiny()
        sched = tiny_valid()
        del sched.enrolment["S1"]["B"]
        sched.info["unplaced_choice_diagnostics"] = [{
            "student_id": "S1",
            "course_id": "B",
            "reason": "student_conflict",
            "description": "Every section overlaps an assigned class.",
            "candidate_sections": ["B1", "B2"],
        }]

        payload = serialize_schedule(ds, sched)

        self.assertEqual(payload["unplaced_selection_details"][0]["reason"], "student_conflict")
        self.assertEqual(payload["metrics"]["unplaced_reason_counts"], {"student_conflict": 1})

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
        self.assertIn(resp.status_code, (200, 404))
        if resp.status_code == 200:
            self.assertTrue(resp.json["success"])
            self.assertEqual(resp.json["data"]["metrics"]["method"], "baseline")
        else:
            self.assertIn("not found", resp.json["error"].lower())

if __name__ == "__main__":
    unittest.main()
