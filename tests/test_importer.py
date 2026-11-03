"""Real-dataset import, baseline timetable, fixed assignments, and comparison tests."""
import os
import shutil
import tempfile
import unittest

from nexus_core.input_validator import load_csv, save_csv
from nexus_core.importer import (
    import_folder, load_timetable_csv, set_assignment_modes, suggest_mapping, build_dataset_from_mapped_tables,
)
from nexus_core.models import *
from nexus_core.cpsat import cpsat
from nexus_core.validator import validate
from nexus_core.compare import compare_schedules
from tests.fixtures import tiny


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATES = os.path.join(ROOT, "data", "templates")


class ImporterTests(unittest.TestCase):
    def test_template_folder_loads_with_baseline(self):
        ds, issues = load_csv(TEMPLATES, name="template_demo")
        self.assertIsNotNone(ds, msg=str(issues))
        self.assertFalse(ds.synthetic)
        self.assertEqual(len(ds.courses), 3)
        self.assertEqual(len(ds.sections), 3)
        self.assertGreaterEqual(len(ds.baseline), 3)
        self.assertTrue(any(b.mode == FIXED for b in ds.baseline.values()))
        self.assertEqual(ds.courses["CS101"].school_id, "SOET")
        self.assertEqual(ds.sections["CS101_A"].stream, "CSE")

    def test_import_folder_flexible_mapping(self):
        result = import_folder(TEMPLATES, name="mapped_demo")
        self.assertIsNotNone(result.dataset, msg=str(result.issues))
        self.assertEqual(result.dataset.name, "mapped_demo")
        self.assertGreater(result.summary.get("baseline_assignments", 0), 0)
        self.assertTrue(result.previews)

    def test_suggest_mapping_aliases(self):
        cols = ["Course Code", "Course Title", "Category", "Credits", "pattern"]
        m = suggest_mapping(cols, "courses")
        self.assertEqual(m["course_id"], "Course Code")
        self.assertEqual(m["title"], "Course Title")

    def test_missing_required_mapping_reported(self):
        rows = [{"X": "1", "Y": "2"}]
        mapping = {"title": "Y"}  # missing course_id
        result = build_dataset_from_mapped_tables({"courses": (rows, mapping)})
        self.assertIsNone(result.dataset)
        self.assertTrue(any("course_id" in i.message for i in result.issues))

    def test_does_not_invent_unknown_faculty_when_attaching(self):
        ds = tiny()
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "timetable.csv")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("Day,Period,Section,Room,Faculty ID\n")
                fh.write("Monday,Period 1,A1,R1,UNKNOWN_FAC\n")
            result = load_timetable_csv(path, ds=ds, allow_resources_from_timetable=False)
            self.assertIsNone(result.dataset)
            self.assertTrue(any("unknown or missing faculty" in i.message for i in result.issues))
        finally:
            shutil.rmtree(d)

    def test_fixed_assignment_preserved_by_cpsat_and_validator(self):
        ds = tiny()
        # Fix A1 at slot 0 in R1 with F1
        ds.baseline[( "A1", 0 )] = BaselineAssignment("A1", 0, 0, "R1", "F1", FIXED)
        # Prefer B1 elsewhere
        ds.baseline[("B1", 0)] = BaselineAssignment("B1", 0, 1, "R1", "F2", PREFERRED)
        sch = cpsat(ds, limit_a=20, limit_b=10, seed=329, w_move=5, w_room=2, w_fac=3)
        self.assertIn(sch.status, ("OPTIMAL", "FEASIBLE"))
        self.assertIn(("A1", 0), sch.placement)
        self.assertEqual(sch.placement[("A1", 0)], (0, "R1"))
        self.assertEqual(sch.faculty["A1"], "F1")
        rep = validate(ds, sch)
        self.assertEqual(rep.count("H10"), 0)

    def test_validator_detects_broken_fixed_assignment(self):
        ds = tiny()
        ds.baseline[("A1", 0)] = BaselineAssignment("A1", 0, 0, "R1", "F1", FIXED)
        sch = Schedule(method="hand", status="HAND")
        sch.placement = {("A1", 0): (2, "R2"), ("B1", 0): (1, "R1"), ("B2", 0): (3, "R2"), ("L1", 0): (6, "L1")}
        sch.faculty = {"A1": "F1", "B1": "F2", "B2": "F2", "L1": "F1"}
        sch.enrolment = {"S1": {"A": "A1", "B": "B1"}, "S2": {"A": "A1", "L": "L1"}, "S3": {"B": "B2"}}
        rep = validate(ds, sch)
        self.assertEqual(rep.status, "INVALID")
        self.assertGreaterEqual(rep.count("H10"), 1)

    def test_set_assignment_modes_and_compare(self):
        ds, issues = load_csv(TEMPLATES, name="cmp")
        self.assertIsNotNone(ds, msg=str(issues))
        set_assignment_modes(ds, PREFERRED)
        original = ds.baseline_schedule()
        sch = cpsat(ds, limit_a=20, limit_b=10, seed=329)
        self.assertIn(sch.status, ("OPTIMAL", "FEASIBLE", "UNKNOWN"))
        if sch.status in ("OPTIMAL", "FEASIBLE"):
            cmp = compare_schedules(ds, original, sch)
            self.assertIn(cmp.optimized_validator, ("VALID_COMPLETE", "VALID_INCOMPLETE", "INVALID"))
            self.assertTrue(cmp.notes)

    def test_classic_csv_roundtrip_still_works(self):
        d = tempfile.mkdtemp()
        try:
            save_csv(tiny(), d)
            ds, iss = load_csv(d)
            self.assertIsNotNone(ds, msg=str(iss))
            self.assertEqual(len(ds.sections), 4)
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
