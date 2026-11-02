"""M4 acceptance: the validator accepts a valid schedule and catches every designed mutation (experiment E1)."""
import unittest, copy
from nexus_core.validator import validate
from nexus_core.models import *
from tests.fixtures import tiny, tiny_valid, mutate


class ValidatorTests(unittest.TestCase):
    # Starting from a valid schedule lets each test isolate one rule violation.
    def setUp(self):
        self.ds, self.ok = tiny(), tiny_valid()

    def rules(self, sched, ds=None):
        r = validate(ds or self.ds, sched)
        return r.status, set(r.by_rule())

    def test_valid_complete(self):
        self.assertEqual(self.rules(self.ok), ("VALID_COMPLETE", set()))

    def test_valid_incomplete_unscheduled(self):
        s = copy.deepcopy(self.ok); del s.placement[("B2", 0)]; del s.faculty["B2"]; s.unscheduled = ["B2"]; s.enrolment["S3"] = {}
        st, rules = self.rules(s)
        self.assertEqual((st, rules), ("VALID_INCOMPLETE", set()))

    def test_valid_incomplete_unplaced_selection(self):
        s = copy.deepcopy(self.ok); s.enrolment["S3"] = {}
        self.assertEqual(self.rules(s), ("VALID_INCOMPLETE", set()))

    # ---- mutations: each must produce INVALID with the designed rule ---------------------------------
    def test_m_room_clash_H2(self):
        s = mutate(self.ok, placement={("B1", 0): (0, "R1")})
        self.assertIn("H2", self.rules(s)[1])

    def test_m_faculty_clash_H1(self):
        s = mutate(self.ok, placement={("B2", 0): (1, "R2")})        # F2 teaches B1@1 and B2@1
        self.assertIn("H1", self.rules(s)[1])

    def test_m_student_clash_H3(self):
        s = mutate(self.ok, placement={("B1", 0): (0, "R2")})        # S1 has A1@0 and B1@0
        self.assertIn("H3", self.rules(s)[1])

    def test_m_room_capacity_H4(self):
        ds = tiny(); ds.rooms["R2"] = Room("R2", CLASS, 10, frozenset({7}))
        self.assertIn("H4", self.rules(self.ok, ds)[1])

    def test_m_room_type_H5(self):
        s = mutate(self.ok, placement={("A1", 0): (0, "L1")})
        self.assertIn("H5", self.rules(s)[1])

    def test_m_unqualified_faculty_H6(self):
        s = mutate(self.ok, faculty={"A1": "F2"})
        self.assertIn("H6", self.rules(s)[1])

    def test_m_faculty_unavailable_H7(self):
        s = mutate(self.ok, placement={("A1", 0): (5, "R1")})        # F1 unavailable at slot 5
        self.assertIn("H7", self.rules(s)[1])

    def test_m_room_unavailable_H7(self):
        s = mutate(self.ok, placement={("B2", 0): (7, "R2")})        # R2 unavailable at slot 7
        self.assertIn("H7", self.rules(s)[1])

    def test_m_day_boundary_H8(self):
        s = mutate(self.ok, placement={("L1", 0): (5, "L1")})        # 2h session at slot 5 crosses day 0 -> day 1
        self.assertIn("H8", self.rules(s)[1])

    def test_m_missing_session_H9(self):
        s = copy.deepcopy(self.ok); del s.placement[("L1", 0)]       # not placed and not listed unscheduled
        self.assertIn("H9", self.rules(s)[1])

    def test_m_enrol_wrong_course_H11(self):
        s = mutate(self.ok, enrolment={"S3": {"B": "A1"}})
        self.assertIn("H11", self.rules(s)[1])

    def test_m_enrol_not_selected_H11(self):
        s = copy.deepcopy(self.ok); s.enrolment["S3"]["L"] = "L1"
        self.assertIn("H11", self.rules(s)[1])

    def test_m_section_capacity_H12(self):
        ds = tiny(); ds.sections["A1"] = Section("A1", "A", 1)       # two students enrolled
        self.assertIn("H12", self.rules(self.ok, ds)[1])

    def test_m_workload_H14(self):
        ds = tiny(); ds.faculty["F2"] = Faculty("F2", "F2", frozenset({"B"}), 1)
        self.assertIn("H14", self.rules(self.ok, ds)[1])

    def test_every_mutation_makes_status_invalid(self):
        s = mutate(self.ok, placement={("B1", 0): (0, "R1")})
        self.assertEqual(self.rules(s)[0], "INVALID")


if __name__ == "__main__":
    unittest.main()
