import csv
import os
import tempfile
import unittest

from nexus_core.common import student_section_options
from nexus_core.cpsat import stage_b
from nexus_core.importer import build_dataset_from_mapped_tables
from nexus_core.input_validator import load_csv, save_csv
from nexus_core.models import CLASS, Course, Dataset, Faculty, Room, Schedule, Section, SessionSpec, Student
from nexus_core.validator import validate
from web.serializer import serialize_schedule


def choice_tables():
    course_rows = [
        {"code": "CORE", "title": "Core Systems", "category": "Core", "type": "Core", "credits": "3", "pattern": "1:CLASS"},
        {"code": "MINOR", "title": "University Minor", "category": "", "type": "University Minor", "credits": "3", "pattern": "1:CLASS"},
        {"code": "EL", "title": "Open Elective", "category": "Core", "type": "Open Elective", "credits": "3", "pattern": "1:CLASS"},
    ]
    course_map = {"course_id": "code", "title": "title", "category": "category", "course_type": "type", "credits": "credits", "pattern": "pattern"}
    section_rows = [
        {"section_id": "CORE_A", "course_id": "CORE", "capacity": "30", "semester": "6", "batch": "CSE A"},
        {"section_id": "MINOR_X", "course_id": "MINOR", "capacity": "30", "semester": "6", "batch": "OTHER PROGRAM"},
        {"section_id": "EL_X", "course_id": "EL", "capacity": "30", "semester": "6", "batch": "OTHER PROGRAM"},
    ]
    section_map = {"section_id": "section_id", "course_id": "course_id", "capacity": "capacity", "semester": "semester", "batch": "batch"}
    faculty_rows = [
        {"faculty_id": "F_CORE", "name": "Core Faculty", "qualified": "CORE", "max_hours": "8"},
        {"faculty_id": "F_MINOR", "name": "Minor Faculty", "qualified": "MINOR", "max_hours": "8"},
        {"faculty_id": "F_EL", "name": "Elective Faculty", "qualified": "EL", "max_hours": "8"},
    ]
    faculty_map = {"faculty_id": "faculty_id", "name": "name", "qualified": "qualified", "max_hours": "max_hours"}
    room_rows = [{"room_id": "R1", "type": "CLASS", "capacity": "40"}]
    room_map = {"room_id": "room_id", "type": "type", "capacity": "capacity"}
    student_rows = [{
        "student_id": "S1", "programme": "Computer Science and Engineering", "selections": "CORE",
        "minor_electives": "MINOR", "elective_selections": "EL", "semester": "6", "batch": "CSE A",
    }]
    student_map = {
        "student_id": "student_id", "programme": "programme", "selections": "selections",
        "minor_electives": "minor_electives", "elective_selections": "elective_selections",
        "semester": "semester", "batch": "batch",
    }
    return {
        "courses": (course_rows, course_map),
        "sections": (section_rows, section_map),
        "faculty": (faculty_rows, faculty_map),
        "rooms": (room_rows, room_map),
        "students": (student_rows, student_map),
    }


class MinorElectiveAllocationTests(unittest.TestCase):
    def test_selected_minor_and_elective_courses_are_imported_and_show_in_student_timetable(self):
        result = build_dataset_from_mapped_tables(choice_tables(), require_students=True)
        self.assertIsNotNone(result.dataset, msg=str(result.issues))
        ds = result.dataset
        self.assertEqual(ds.courses["MINOR"].category, "Minor")
        self.assertEqual(ds.courses["EL"].category, "Program Elective")
        self.assertEqual(ds.students["S1"].selections, ("CORE", "MINOR", "EL"))

        with tempfile.TemporaryDirectory() as folder:
            save_csv(ds, folder)
            restored, issues = load_csv(folder)
            self.assertIsNotNone(restored, msg=str(issues))
            self.assertEqual(restored.students["S1"].selections, ("CORE", "MINOR", "EL"))

        sched = Schedule(
            method="fixture",
            status="FEASIBLE",
            placement={("CORE_A", 0): (0, "R1"), ("MINOR_X", 0): (1, "R1"), ("EL_X", 0): (2, "R1")},
            faculty={"CORE_A": "F_CORE", "MINOR_X": "F_MINOR", "EL_X": "F_EL"},
        )
        status, _ = stage_b(ds, sched, limit=2)
        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        report = validate(ds, sched)
        self.assertEqual(report.count("H3"), 0)
        self.assertEqual(report.count("H17"), 0)

        payload = serialize_schedule(ds, sched, report)
        student = payload["entities"]["students"]["S1"]
        self.assertEqual(student["minor_electives"], ["MINOR", "EL"])
        self.assertEqual(student["minor_elective_enrolments"], {"MINOR": "MINOR_X", "EL": "EL_X"})
        self.assertEqual(
            {item["course_id"] for item in payload["grid_data"]["by_student"]["S1"]},
            {"CORE", "MINOR", "EL"},
        )

    def test_student_csv_can_contain_only_minor_elective_choice_columns(self):
        ds = build_dataset_from_mapped_tables(choice_tables(), require_students=True).dataset
        with tempfile.TemporaryDirectory() as folder:
            save_csv(ds, folder)
            with open(os.path.join(folder, "students.csv"), "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["student_id", "programme", "minor_electives", "semester", "batch"])
                writer.writerow(["S2", "Other Department", "MINOR;EL", "6", "OTHER"])

            restored, issues = load_csv(folder)

        self.assertIsNotNone(restored, msg=str(issues))
        self.assertEqual(restored.students["S2"].selections, ("MINOR", "EL"))

    def test_core_section_matches_student_batch_but_electives_can_cross_programs(self):
        core = Course("C", "Core", "Core", 3, (SessionSpec(1, CLASS),))
        elective = Course("E", "Elective", "Program Elective", 3, (SessionSpec(1, CLASS),), course_type="Open Elective")
        ds = Dataset(
            "section-scope",
            {"C": core, "E": elective},
            {
                "C_A": Section("C_A", "C", 20, semester="6", batch="CSE A"),
                "C_B": Section("C_B", "C", 20, semester="6", batch="CSE B"),
                "E_OTHER": Section("E_OTHER", "E", 20, semester="6", batch="OTHER PROGRAM"),
            },
            {}, {},
            {"S1": Student("S1", "CSE", ("C", "E"), semester="6", batch="CSE A")},
        )

        self.assertEqual(student_section_options(ds, ds.students["S1"], "C", ["C_A", "C_B"]), ["C_A"])
        self.assertEqual(student_section_options(ds, ds.students["S1"], "E", ["E_OTHER"]), ["E_OTHER"])

    def test_overlapping_elective_choices_cannot_both_be_allocated(self):
        courses = {
            course_id: Course(course_id, course_id, "Elective", 3, (SessionSpec(1, CLASS),), course_type="Program Elective")
            for course_id in ("E1", "E2")
        }
        sections = {
            "E1_A": Section("E1_A", "E1", 10),
            "E2_A": Section("E2_A", "E2", 10),
        }
        ds = Dataset(
            "elective-conflict",
            courses,
            sections,
            {"F1": Faculty("F1", "F1", frozenset({"E1"}), 8), "F2": Faculty("F2", "F2", frozenset({"E2"}), 8)},
            {"R1": Room("R1", CLASS, 20), "R2": Room("R2", CLASS, 20)},
            {"S1": Student("S1", "CSE", ("E1", "E2"))},
        )
        sched = Schedule(
            status="FEASIBLE",
            placement={("E1_A", 0): (0, "R1"), ("E2_A", 0): (0, "R2")},
            faculty={"E1_A": "F1", "E2_A": "F2"},
        )

        status, _ = stage_b(ds, sched, limit=2)

        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(len(sched.enrolment["S1"]), 1)
        self.assertEqual(len(validate(ds, sched).unplaced), 1)
        self.assertEqual(validate(ds, sched).count("H3"), 0)


if __name__ == "__main__":
    unittest.main()
