import unittest

from nexus_core.common import sec_slots
from nexus_core.cpsat import stage_a
from nexus_core.member_allocator import allocate_faculty_members
from nexus_core.models import (
    CLASS,
    LAB,
    Course,
    Dataset,
    Faculty,
    Room,
    Section,
    SessionSpec,
    Student,
)


class AllocationConstraintTests(unittest.TestCase):
    def test_room_is_reused_for_same_type_meetings_when_possible(self):
        course = Course("A", "Course A", "Major", 2, (SessionSpec(1, CLASS), SessionSpec(1, CLASS)))
        ds = Dataset(
            "room-continuity",
            {"A": course},
            {"A1": Section("A1", "A", 10)},
            {"F1": Faculty("F1", "Faculty 1", frozenset({"A"}), 8)},
            {
                "R1": Room("R1", CLASS, 20),
                "R2": Room("R2", CLASS, 20),
            },
            {"S1": Student("S1", "P", ("A",))},
        )

        status, schedule, info = stage_a(ds, limit=3, allow_unscheduled=False)

        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(schedule.placement[("A1", 0)][1], schedule.placement[("A1", 1)][1])
        self.assertEqual(info["n_room_continuity_terms"], 1)
        self.assertEqual(info["n_faculty_consecutive_terms"], 1)

    def test_stage_a_rejects_invalid_room_and_faculty_candidates(self):
        def make_dataset(*, room_type=CLASS, room_capacity=20, room_unavailable=(),
                         faculty_unavailable=(), qualified=True, max_hours=8):
            course = Course("A", "Course A", "Major", 1, (SessionSpec(1, CLASS),))
            faculty = Faculty(
                "F1", "Faculty 1", frozenset({"A"}) if qualified else frozenset(),
                max_hours, frozenset(faculty_unavailable),
            )
            room = Room("R1", room_type, room_capacity, frozenset(room_unavailable))
            return Dataset(
                "hard-resource-rules",
                {"A": course},
                {"A1": Section("A1", "A", 20)},
                {"F1": faculty},
                {"R1": room},
                {},
            )

        cases = [
            make_dataset(room_capacity=19),
            make_dataset(room_type=LAB),
            make_dataset(room_unavailable=range(50)),
            make_dataset(faculty_unavailable=range(50)),
            make_dataset(qualified=False),
            make_dataset(max_hours=0),
        ]
        for ds in cases:
            with self.subTest(ds=ds.name):
                status, schedule, _ = stage_a(ds, limit=2)
                self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
                self.assertEqual(schedule.unscheduled, ["A1"])

    def test_faculty_and_room_are_not_double_booked(self):
        course = Course("A", "Course A", "Major", 1, (SessionSpec(1, CLASS),))
        ds = Dataset(
            "no-double-booking",
            {"A": course},
            {sid: Section(sid, "A", 10) for sid in ("A1", "A2")},
            {"F1": Faculty("F1", "Faculty 1", frozenset({"A"}), 8)},
            {
                "R1": Room("R1", CLASS, 20),
                "R2": Room("R2", CLASS, 20),
            },
            {},
        )

        status, schedule, _ = stage_a(ds, limit=2)

        self.assertIn(status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(set(schedule.placement), {("A1", 0), ("A2", 0)})
        self.assertFalse(
            sec_slots(ds, schedule.placement, "A1")
            & sec_slots(ds, schedule.placement, "A2")
        )

    def test_member_allocator_does_not_assign_unqualified_faculty_or_invent_adjuncts(self):
        course = Course("A", "Course A", "Major", 1, (SessionSpec(1, CLASS),))
        ds = Dataset(
            "faculty-qualification",
            {"A": course},
            {
                "A1": Section("A1", "A", 10),
                "A2": Section("A2", "A", 10),
            },
            {
                "F1": Faculty("F1", "Qualified", frozenset({"A"}), 1),
                "F2": Faculty("F2", "Unqualified", frozenset(), 16),
            },
            {"R1": Room("R1", CLASS, 20)},
            {},
        )

        result = allocate_faculty_members(ds)

        self.assertEqual(result.faculty_assignments, {"A1": "F1"})
        self.assertEqual(result.unassigned_sections, ["A2"])
        self.assertNotIn("FAC_ADJUNCT_01", ds.faculty)
        self.assertTrue(all(ds.sections[sid].course_id in ds.faculty[fid].qualified
                            for sid, fid in result.faculty_assignments.items()))

    def test_member_allocator_repairs_unqualified_and_over_limit_preassignments(self):
        course = Course("A", "Course A", "Major", 1, (SessionSpec(1, CLASS),))
        ds = Dataset(
            "preassignment-repair",
            {"A": course},
            {sid: Section(sid, "A", 10) for sid in ("A1", "A2", "A3")},
            {
                "F1": Faculty("F1", "Qualified, max one", frozenset({"A"}), 1),
                "F2": Faculty("F2", "Qualified, max two", frozenset({"A"}), 2),
                "F3": Faculty("F3", "Unqualified", frozenset(), 16),
            },
            {"R1": Room("R1", CLASS, 20)},
            {},
        )

        result = allocate_faculty_members(
            ds, pre_assigned={"A1": "F3", "A2": "F1", "A3": "F1"}
        )

        self.assertEqual(result.faculty_assignments, {"A2": "F1", "A1": "F2", "A3": "F2"})
        assigned_hours = {member["id"]: member["assigned_hours"] for member in result.faculty_summary}
        self.assertEqual(assigned_hours, {"F1": 1, "F2": 2, "F3": 0})
        self.assertEqual(result.stats["pre_assigned_sections"], 1)


if __name__ == "__main__":
    unittest.main()
