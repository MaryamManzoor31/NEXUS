"""M5/M6/M7/M8 acceptance: every scheduler's output is judged by the independent validator, not by its own flag."""
import unittest
from dataclasses import replace
from unittest.mock import patch
from ortools.sat.python import cp_model
from nexus_core.data_generator import generate
from nexus_core.cpsat import (
    cpsat,
    stage_a,
    stage_b,
    _priority_course_pairs,
)
from nexus_core.common import EXTENDED_SESSIONS
from nexus_core.validator import validate
from nexus_core.metrics import compute
from nexus_core.models import *
from tests.fixtures import tiny, tiny_valid


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
        ds = tiny(); a = cpsat(ds, limit_a=10, limit_b=5, seed=9); b = cpsat(ds, limit_a=10, limit_b=5, seed=9)
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

    def test_unplaced_choices_prioritize_conflicting_course_pairs(self):
        ds = tiny()
        pairs = dict(_priority_course_pairs(ds, [("S1", "A"), ("S2", "A")]))
        self.assertEqual(pairs[("A", "B")], 1000)
        self.assertEqual(pairs[("A", "L")], 1000)

    def test_stage_a_adds_priority_conflict_terms(self):
        ds = tiny()
        _, _, info = stage_a(ds, limit=10, top_pairs=0, priority_pairs=[(("A", "B"), 1000)])
        self.assertGreater(info["n_conflict_terms"], 0)

    def test_stage_a_packs_shared_student_classes_without_gaps(self):
        ds = tiny()
        ds.sections = {sid: ds.sections[sid] for sid in ("A1", "B1")}
        ds.courses = {course_id: ds.courses[course_id] for course_id in ("A", "B")}
        ds.faculty = {"F1": ds.faculty["F1"]}
        ds.rooms = {"R1": ds.rooms["R1"]}
        ds.students = {"S": Student("S", "FYUP", ("A", "B"))}

        with patch("nexus_core.cpsat.starts_for", return_value=[0, 1, 2]):
            status, sched, info = stage_a(
                ds, limit=10, allow_unscheduled=False, hint=Schedule()
            )

        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        starts = sorted(start for start, _ in sched.placement.values())
        self.assertEqual(starts, [0, 1])
        self.assertGreater(info["n_gap_terms"], 0)

    def test_stage_b_assigns_morning_session_for_half_day_classes(self):
        ds, sched = student_day_instance([0, 1])
        status, _ = stage_b(ds, sched, limit=10)
        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(len(sched.enrolment["S"]), 2)
        self.assertEqual(sched.student_categories["S"][0], MORNING_SESSION)
        self.assertEqual(validate(ds, sched).count("H15"), 0)

    def test_stage_b_assigns_afternoon_session_for_half_day_classes(self):
        ds, sched = student_day_instance([5, 6])
        status, _ = stage_b(ds, sched, limit=10)
        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(len(sched.enrolment["S"]), 2)
        self.assertEqual(sched.student_categories["S"][0], AFTERNOON_SESSION)
        self.assertEqual(validate(ds, sched).count("H15"), 0)

    def test_stage_b_keeps_student_in_their_semester_session(self):
        for mode, slots in ((MORNING_SESSION, [0, 10]), (AFTERNOON_SESSION, [5, 15])):
            ds, sched = student_day_instance(slots)
            ds.sections = {
                sid: replace(section, semester="6")
                for sid, section in ds.sections.items()
            }
            ds.students["S"] = replace(ds.students["S"], semester="6")
            ds.meta["semester_sessions"] = {"6": mode}

            status, _ = stage_b(ds, sched, limit=10)

            self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
            self.assertEqual(len(sched.enrolment["S"]), 2)
            self.assertEqual(set(sched.student_categories["S"].values()), {mode})

    def test_stage_b_automatically_assigns_a_student_shift(self):
        ds, sched = student_day_instance([0, 1])
        ds.sections = {
            sid: replace(section, semester="6")
            for sid, section in ds.sections.items()
        }
        ds.students["S"] = replace(ds.students["S"], semester="6")
        ds.meta["semester_sessions"] = {"6": "auto"}

        status, _ = stage_b(ds, sched, limit=10)

        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(sched.student_categories["S"][0], MORNING_SESSION)
        self.assertEqual(validate(ds, sched).count("H16"), 0)

    def test_half_day_batches_can_extend_when_daily_load_exceeds_five_hours(self):
        cases = (
            (MORNING_SESSION, [0, 1, 2, 3, 4, 6], EXTENDED_EARLY_SESSION),
            (AFTERNOON_SESSION, [2, 3, 4, 6, 7, 8], EXTENDED_LATE_SESSION),
        )
        for batch_mode, slots, expected in cases:
            with self.subTest(batch_mode=batch_mode):
                ds, sched = student_day_instance(slots)
                ds.sections = {
                    sid: replace(section, semester="6")
                    for sid, section in ds.sections.items()
                }
                ds.students["S"] = replace(ds.students["S"], semester="6")
                ds.meta["semester_sessions"] = {"6": batch_mode}

                status, _ = stage_b(ds, sched, limit=10)

                self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
                self.assertEqual(sched.student_categories["S"][0], expected)
                self.assertEqual(validate(ds, sched).status, "VALID_COMPLETE")

    def test_stage_b_does_not_use_extended_for_five_or_fewer_hours(self):
        ds, sched = student_day_instance([0, 5])
        status, _ = stage_b(ds, sched, limit=10)
        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(len(sched.enrolment["S"]), 1)
        self.assertNotIn(sched.student_categories["S"][0], EXTENDED_SESSIONS)
        self.assertEqual(validate(ds, sched).count("H15"), 0)

    def test_stage_b_allows_extended_session_with_lunch_break(self):
        ds, sched = student_day_instance([0, 1, 2, 3, 4, 6])
        status, _ = stage_b(ds, sched, limit=10)
        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(len(sched.enrolment["S"]), 6)
        self.assertEqual(sched.student_categories["S"][0], EXTENDED_EARLY_SESSION)
        self.assertEqual(validate(ds, sched).status, "VALID_COMPLETE")

    def test_stage_b_uses_required_daily_hours_even_when_one_choice_cannot_be_placed(self):
        ds, sched = student_day_instance([0, 1, 2, 3, 4, 0])
        status, _ = stage_b(ds, sched, limit=10)

        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(len(sched.enrolment["S"]), 5)
        self.assertIn(sched.student_categories["S"][0], EXTENDED_SESSIONS)
        self.assertEqual(validate(ds, sched).count("H15"), 0)
        self.assertEqual(len(validate(ds, sched).unplaced), 1)

    def test_stage_b_does_not_split_a_day_across_half_day_categories(self):
        ds, sched = student_day_instance([0, 1, 2, 3, 4, 5])
        status, _ = stage_b(ds, sched, limit=10)
        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        # The six required hours straddle morning and afternoon, and the only
        # extended timing cannot provide lunch with both classes required.
        self.assertEqual(len(sched.enrolment["S"]), 0)
        self.assertEqual(sched.student_categories.get("S", {}), {})
        self.assertEqual(len(validate(ds, sched).unplaced), 6)

    def test_stage_b_enforces_two_hour_waiting_limit(self):
        ds, sched = student_day_instance([0, 4])
        status, _ = stage_b(ds, sched, limit=10)
        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(len(sched.enrolment["S"]), 1)
        self.assertEqual(validate(ds, sched).count("H18"), 0)

    def test_extended_lunch_is_exempt_from_two_hour_wait_limit(self):
        ds, sched = student_day_instance([0, 1, 2, 3, 6, 7])
        sched.enrolment = {"S": {f"C{i}": f"C{i}" for i in range(6)}}
        sched.student_categories = {"S": {0: EXTENDED_EARLY_SESSION}}
        self.assertEqual(validate(ds, sched).count("H18"), 0)

    def test_validator_rejects_three_hour_student_wait(self):
        ds, sched = student_day_instance([0, 4])
        sched.enrolment = {"S": {"C0": "C0", "C1": "C1"}}
        sched.student_categories = {"S": {0: MORNING_SESSION}}
        self.assertEqual(validate(ds, sched).count("H18"), 1)

    def test_validator_uses_actual_multi_session_daily_duration(self):
        ds, sched = student_day_instance([0])
        sid = "C0"
        ds.courses["C0"] = Course("C0", "Course 0", "Major", 3, (SessionSpec(1, CLASS), SessionSpec(1, CLASS)))
        ds.sections[sid] = Section(sid, "C0", 20)
        ds.students["S"] = Student("S", "FYUP", ("C0",))
        sched.placement[(sid, 1)] = (1, "R")
        sched.enrolment = {"S": {"C0": sid}}
        sched.student_categories = {"S": {0: MORNING_SESSION}}

        self.assertEqual(validate(ds, sched).count("H15"), 0)

    def test_validator_does_not_hide_over_five_required_hours_by_leaving_choice_unplaced(self):
        ds, sched = student_day_instance([0, 1, 2, 3, 4, 0])
        sched.enrolment = {"S": {f"C{i}": f"C{i}" for i in range(5)}}
        sched.student_categories = {"S": {0: MORNING_SESSION}}

        self.assertGreaterEqual(validate(ds, sched).count("H15"), 1)

    def test_validator_rejects_wrong_category(self):
        ds, sched = student_day_instance([0, 5])
        sched.enrolment = {"S": {"C0": "C0", "C1": "C1"}}
        sched.student_categories = {"S": {0: MORNING_SESSION}}
        self.assertEqual(validate(ds, sched).count("H15"), 1)

    def test_validator_rejects_extended_without_lunch_break(self):
        ds, sched = student_day_instance([0, 1, 2, 3, 4, 5])
        sched.enrolment = {"S": {f"C{i}": f"C{i}" for i in range(6)}}
        sched.student_categories = {"S": {0: EXTENDED_EARLY_SESSION}}
        self.assertEqual(validate(ds, sched).count("H15"), 1)

    def test_stage_a_enforces_semester_session_window(self):
        for mode in (MORNING_SESSION, AFTERNOON_SESSION):
            ds = tiny()
            ds.sections = {
                sid: replace(section, semester="6")
                for sid, section in ds.sections.items()
            }
            ds.meta["semester_sessions"] = {"6": mode}

            status, sched, _ = stage_a(ds, limit=10, allow_unscheduled=True)

            self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
            for (sid, k), (start, _) in sched.placement.items():
                period = start % PERIODS
                duration = ds.section_sessions(sid)[k].duration
                if mode == MORNING_SESSION:
                    self.assertGreaterEqual(period, 0)
                    self.assertLessEqual(period + duration, 8)
                else:
                    self.assertGreaterEqual(period, 2)
                    self.assertLessEqual(period + duration, PERIODS)
            self.assertEqual(validate(ds, sched).count("H16"), 0)

    def test_cpsat_places_single_session_sections_in_morning_window(self):
        ds, _ = student_day_instance([0] * 7)
        ds.sections = {
            sid: replace(section, semester="6")
            for sid, section in ds.sections.items()
        }
        ds.meta["semester_sessions"] = {"6": MORNING_SESSION}

        status, hint, _ = stage_a(ds, limit=10)

        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(len(hint.placement), 7)
        self.assertEqual(len(hint.unscheduled), 0)
        self.assertTrue(all(start % PERIODS < 8 for start, _ in hint.placement.values()))
        self.assertEqual(validate(ds, hint).count("H16"), 0)

    def test_morning_window_allows_starts_after_eight_and_respects_end_time(self):
        from nexus_core.common import semester_session_starts, starts_for

        one_hour = semester_session_starts("6", MORNING_SESSION, starts_for(1), 1)
        two_hours = semester_session_starts("6", MORNING_SESSION, starts_for(2), 2)
        self.assertEqual({slot % PERIODS for slot in one_hour}, set(range(8)))
        self.assertEqual({slot % PERIODS for slot in two_hours}, set(range(7)))

    def test_morning_schedule_prefers_eight_when_preferred_baseline_starts_at_nine(self):
        ds = tiny()
        ds.sections = {"A1": replace(ds.sections["A1"], semester="6")}
        ds.courses = {"A": ds.courses["A"]}
        ds.students = {"S": Student("S", "FYUP", ("A",), semester="6")}
        ds.meta["semester_sessions"] = {"6": MORNING_SESSION}
        ds.baseline = {
            ("A1", 0): BaselineAssignment("A1", 0, 1, "R1", "F1", PREFERRED)
        }

        status, sched, _ = stage_a(ds, limit=10, allow_unscheduled=False)

        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(sched.placement[("A1", 0)][0] % PERIODS, 0)

    def test_validator_rejects_wrong_semester_window(self):
        ds = tiny()
        ds.sections = {
            sid: replace(section, semester="6")
            for sid, section in ds.sections.items()
        }
        ds.meta["semester_sessions"] = {"6": AFTERNOON_SESSION}

        self.assertGreater(validate(ds, tiny_valid()).count("H16"), 0)

    def test_unknown_does_not_fall_back_to_hint(self):
        class UnknownSolver:
            def Solve(self, model):
                return cp_model.UNKNOWN

            def StatusName(self, status):
                return "UNKNOWN"

            def WallTime(self):
                return 0.0

        ds = tiny()
        with patch("nexus_core.cpsat._solver", return_value=UnknownSolver()):
            status, sched, _ = stage_a(ds, hint=tiny_valid())
        self.assertEqual(status, "UNKNOWN")
        self.assertEqual(sched.status, "UNKNOWN")
        self.assertFalse(sched.placement)
        self.assertEqual(set(sched.unscheduled), set(ds.sections))

    def test_unknown_stage_a_is_reported_and_skips_stage_b(self):
        class UnknownSolver:
            def Solve(self, model):
                return cp_model.UNKNOWN

            def StatusName(self, status):
                return "UNKNOWN"

            def WallTime(self):
                return 0.0

        with patch("nexus_core.cpsat._solver", return_value=UnknownSolver()):
            sched = cpsat(tiny())
        self.assertEqual(sched.status, "UNKNOWN")
        self.assertEqual(sched.info["status_b"], "NOT_RUN")
        self.assertIn("Stage A ended with UNKNOWN", sched.info["status_b_reason"])
        self.assertEqual(validate(tiny(), sched).status, "VALID_INCOMPLETE")

    def test_unknown_stage_b_status_is_preserved(self):
        class UnknownSolver:
            def Solve(self, model):
                return cp_model.UNKNOWN

            def StatusName(self, status):
                return "UNKNOWN"

        sched = tiny_valid()
        with patch("nexus_core.cpsat._solver", return_value=UnknownSolver()):
            status, _ = stage_b(tiny(), sched)
        self.assertEqual(status, "UNKNOWN")
        self.assertEqual(sched.enrolment, {stid: {} for stid in tiny().students})

    def test_stage_b_timeout_is_exposed_in_metrics(self):
        sched = tiny_valid()
        with patch("nexus_core.cpsat.stage_a", return_value=("FEASIBLE", sched, {})):
            with patch("nexus_core.cpsat.stage_b", return_value=("UNKNOWN", 0.0)):
                result = cpsat(tiny())
        self.assertEqual(result.status, "FEASIBLE")
        metrics = compute(tiny(), result)
        self.assertEqual(metrics["stage_b_status"], "UNKNOWN")
        self.assertIn("student selections may remain unassigned", metrics["stage_b_status_reason"])


class MetricsTests(unittest.TestCase):
    # Compare reported metrics against small values that can be checked by hand.
    def test_hand_checked_values(self):
        ds, s = tiny(), tiny_valid(); m = compute(ds, s)
        self.assertEqual(m["validator_status"], "VALID_COMPLETE"); self.assertEqual(m["scheduled_sections"], "4/4")
        self.assertEqual(m["unplaced_selections"], "0/5"); self.assertEqual(m["fully_scheduled_students_pct"], 100.0)
        # Five occupied session-slots out of 149 available room-slots is 3.4%.
        self.assertEqual(m["room_utilization_pct"], 3.4)
        # loads: F1 = A1 1h + L1 2h = 3 ; F2 = B1 1h + B2 1h = 2
        self.assertEqual(m["faculty_load_range_h"], (2, 3))

    def test_unplaced_counts(self):
        ds, s = tiny(), tiny_valid(); s.enrolment["S3"] = {}; m = compute(ds, s)
        self.assertEqual(m["unplaced_selections"], "1/5"); self.assertEqual(m["fully_scheduled_students_pct"], round(100 * 2 / 3, 1))


def student_day_instance(slots):
    courses = {
        f"C{i}": Course(f"C{i}", f"Course {i}", "Major", 1, (SessionSpec(1, CLASS),))
        for i in range(len(slots))
    }
    sections = {
        cid: Section(cid, cid, 20)
        for cid in courses
    }
    student = Student("S", "FYUP", tuple(courses))
    ds = Dataset(
        "student-day",
        courses,
        sections,
        {"F": Faculty("F", "Faculty", frozenset(courses), 20)},
        {"R": Room("R", CLASS, 30)},
        {"S": student},
    )
    sched = Schedule(method="test", status="FEASIBLE")
    sched.placement = {
        (cid, 0): (slot, "R")
        for cid, slot in zip(courses, slots)
    }
    sched.faculty = {cid: "F" for cid in courses}
    return ds, sched


if __name__ == "__main__":
    unittest.main()

