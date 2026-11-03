"""M2 acceptance: valid fixtures load, malformed fixtures are rejected with readable messages."""
import os, shutil, tempfile, unittest
from nexus_core.input_validator import load_csv, save_csv, check_dataset
from nexus_core.data_generator import generate
from nexus_core.models import Section, SessionSpec, LAB
from nexus_core import db
from tests.fixtures import tiny


class LoaderTests(unittest.TestCase):
    # Each test starts from a fresh valid CSV set and can mutate one input file.
    def setUp(self):
        self.d = tempfile.mkdtemp(); save_csv(tiny(), self.d)

    def tearDown(self):
        shutil.rmtree(self.d)

    def edit(self, fn, old, new):
        p = os.path.join(self.d, fn)
        with open(p) as fh: t = fh.read()
        assert old in t
        with open(p, "w") as fh: fh.write(t.replace(old, new, 1))

    def test_valid_roundtrip(self):
        ds, iss = load_csv(self.d)
        self.assertIsNotNone(ds); self.assertEqual(len(ds.sections), 4); self.assertFalse(ds.synthetic)
        self.assertEqual(ds.students["S1"].selections, ("A", "B"))
        self.assertEqual(ds.faculty["F1"].unavailable, frozenset({5}))

    def test_missing_file(self):
        os.remove(os.path.join(self.d, "rooms.csv")); ds, iss = load_csv(self.d)
        self.assertIsNone(ds); self.assertIn("file missing", str(iss[0]))

    def test_wrong_columns(self):
        self.edit("rooms.csv", "capacity", "cap"); ds, iss = load_csv(self.d)
        self.assertIsNone(ds); self.assertIn("expected columns", str(iss[0]))

    def test_malformed_number(self):
        self.edit("rooms.csv", "R1,CLASS,30", "R1,CLASS,thirty"); ds, iss = load_csv(self.d)
        self.assertIsNone(ds); self.assertTrue(any("rooms.csv line 2" in str(i) and "malformed" in str(i) for i in iss))

    def test_duplicate_id(self):
        self.edit("rooms.csv", "R2,CLASS", "R1,CLASS"); ds, iss = load_csv(self.d)
        self.assertIsNone(ds); self.assertTrue(any("duplicate id R1" in str(i) for i in iss))

    def test_unknown_course_in_student(self):
        self.edit("students.csv", "A;B", "A;ZZZ"); ds, iss = load_csv(self.d)
        self.assertIsNone(ds); self.assertTrue(any("unknown course ZZZ" in str(i) for i in iss))

    def test_bad_duration(self):
        self.edit("courses.csv", "2:LAB", "9:LAB"); ds, iss = load_csv(self.d)
        self.assertIsNone(ds); self.assertTrue(any("duration 9" in str(i) for i in iss))

    def test_warning_no_qualified_faculty_still_loads(self):
        self.edit("faculty.csv", "A;B;L", "B;L"); self.edit("faculty.csv", "B,", "B,")   # F1 loses A; F2 has only B
        ds, iss = load_csv(self.d)
        self.assertIsNotNone(ds); self.assertTrue(any(i.severity == "WARNING" and "no faculty qualified" in i.message for i in iss))

    def test_database_roundtrip(self):
        ds = generate(30, "S3", 1); con = db.connect(); db.save_dataset(con, ds); back = db.load_dataset(con)
        self.assertEqual(set(back.courses), set(ds.courses)); self.assertEqual(back.students["S0001"].selections, ds.students["S0001"].selections)
        self.assertEqual(back.faculty["F01"].qualified, ds.faculty["F01"].qualified)
        self.assertEqual({c.id: c.sessions for c in back.courses.values()}, {c.id: c.sessions for c in ds.courses.values()})

    def test_database_roundtrip_preserves_section_session_overrides(self):
        ds = tiny()
        ds.sections["A1"] = Section("A1", "A", 20, sessions=(SessionSpec(2, LAB),))
        con = db.connect()
        db.save_dataset(con, ds)

        back = db.load_dataset(con)

        self.assertEqual(back.section_sessions("A1"), (SessionSpec(2, LAB),))
        self.assertIsNone(back.sections["B1"].sessions)

    def test_generated_data_has_no_errors(self):
        for sc in ("S1", "S2", "S3"):
            self.assertFalse([i for i in check_dataset(generate(60, sc, 7)) if i.severity == "ERROR"])


if __name__ == "__main__":
    unittest.main()
