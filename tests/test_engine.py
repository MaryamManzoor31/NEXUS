"""M5/M6/M7/M8 acceptance: every scheduler's output is judged by the independent validator, not by its own flag."""
import unittest
from nexus_core.data_generator import generate
from nexus_core.greedy import greedy
from nexus_core.cpsat import cpsat, stage_a
from nexus_core.validator import validate
from nexus_core.metrics import compute
from nexus_core.models import *
from tests.fixtures import tiny, tiny_valid


class GreedyTests(unittest.TestCase):
    # The heuristic may be incomplete, but it must not emit invalid placements.
    def test_no_violations_on_feasible(self):
        for sc in ("S1", "S2", "S3"):
            ds = generate(60, sc, 11); r = validate(ds, greedy(ds))
            self.assertNotEqual(r.status, "INVALID", r.violations[:3])

    def test_reports_unscheduled(self):
        ds = generate(40, "S3", 3, unqualified_course=True); s = greedy(ds); r = validate(ds, s)
        self.assertNotEqual(r.status, "INVALID"); self.assertTrue(r.unscheduled)
        self.assertEqual(sorted(r.unscheduled), sorted(s.unscheduled))


class CpSatTests(unittest.TestCase):
    # Check solver status, schedule validity, repeatability, and blocked resources.
    def test_tiny_complete_and_valid(self):
        ds = tiny(); s = cpsat(ds, limit_a=10, limit_b=10)
        self.assertEqual(s.status, "OPTIMAL"); self.assertEqual(validate(ds, s).status, "VALID_COMPLETE")

    def test_generated_valid(self):
        ds = generate(20, "S3", 329); s = cpsat(ds, limit_a=15, limit_b=10)
        r = validate(ds, s); self.assertNotEqual(r.status, "INVALID", r.violations[:3])
        self.assertIn(s.status, ("OPTIMAL", "FEASIBLE"))

    def test_same_seed_same_result(self):
        ds = generate(15, "S2", 5); a = cpsat(ds, limit_a=10, limit_b=5, seed=9); b = cpsat(ds, limit_a=10, limit_b=5, seed=9)
        self.assertEqual(a.placement, b.placement)

    def test_proven_infeasible_labelled_infeasible(self):
        ds = generate(30, "S3", 3, unqualified_course=True)
        name, sched, _ = stage_a(ds, limit=10, allow_unscheduled=False)
        self.assertEqual(name, "INFEASIBLE"); self.assertFalse(sched.placement)

    def test_infeasible_instance_never_outputs_violations(self):
        ds = generate(30, "S3", 3, unqualified_course=True); s = cpsat(ds, limit_a=10, limit_b=5)
        r = validate(ds, s); self.assertNotEqual(r.status, "INVALID"); self.assertTrue(r.unscheduled)

    def test_blocked_room_is_never_used(self):
        ds = tiny(); name, s, _ = stage_a(ds, limit=10, blocked_rooms={"R1"})
        self.assertTrue(all(r != "R1" for _, r in s.placement.values()))


class MetricsTests(unittest.TestCase):
    # Compare reported metrics against small values that can be checked by hand.
    def test_hand_checked_values(self):
        ds, s = tiny(), tiny_valid(); m = compute(ds, s)
        self.assertEqual(m["validator_status"], "VALID_COMPLETE"); self.assertEqual(m["scheduled_sections"], "4/4")
        self.assertEqual(m["unplaced_selections"], "0/5"); self.assertEqual(m["fully_scheduled_students_pct"], 100.0)
        # occupied room-slots: A1 1 + B1 1 + B2 1 + L1 2 = 5 ; available = 30 + (30-1) + 30 = 89 -> 5/89 = 5.6%
        self.assertEqual(m["room_utilization_pct"], 5.6)
        # loads: F1 = A1 1h + L1 2h = 3 ; F2 = B1 1h + B2 1h = 2
        self.assertEqual(m["faculty_load_range_h"], (2, 3))

    def test_unplaced_counts(self):
        ds, s = tiny(), tiny_valid(); s.enrolment["S3"] = {}; m = compute(ds, s)
        self.assertEqual(m["unplaced_selections"], "1/5"); self.assertEqual(m["fully_scheduled_students_pct"], round(100 * 2 / 3, 1))


if __name__ == "__main__":
    unittest.main()
