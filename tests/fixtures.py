import copy
from nexus_core.models import *


def tiny():
    """Hand-checkable instance: 3 courses, 4 sections, 2 faculty, 3 rooms, 3 students."""
    # A small dataset makes scheduler and validator tests quick and predictable.
    C = lambda i, pat: Course(i, i, "Major", 3, tuple(SessionSpec(d, t) for d, t in pat))
    courses = {"A": C("A", [(1, CLASS)]), "B": C("B", [(1, CLASS)]), "L": C("L", [(2, LAB)])}
    sections = {"A1": Section("A1", "A", 20), "B1": Section("B1", "B", 20), "B2": Section("B2", "B", 20), "L1": Section("L1", "L", 20)}
    faculty = {"F1": Faculty("F1", "F1", frozenset({"A", "B", "L"}), 10, frozenset({5})),
               "F2": Faculty("F2", "F2", frozenset({"B"}), 10)}
    rooms = {"R1": Room("R1", CLASS, 30), "R2": Room("R2", CLASS, 20, frozenset({7})), "L1": Room("L1", LAB, 30)}
    students = {"S1": Student("S1", "FYUP", ("A", "B")), "S2": Student("S2", "FYUP", ("A", "L")), "S3": Student("S3", "FYUP", ("B",))}
    return Dataset("tiny", courses, sections, faculty, rooms, students)


def tiny_valid():
    """A fully valid schedule for tiny()."""
    # This known-good schedule is the baseline for validator mutation tests.
    s = Schedule(method="hand")
    s.placement = {("A1", 0): (0, "R1"), ("B1", 0): (1, "R1"), ("B2", 0): (2, "R2"), ("L1", 0): (2, "L1")}
    s.faculty = {"A1": "F1", "B1": "F2", "B2": "F2", "L1": "F1"}
    s.enrolment = {"S1": {"A": "A1", "B": "B1"}, "S2": {"A": "A1", "L": "L1"}, "S3": {"B": "B2"}}
    return s


def mutate(sched, **changes):
    s = copy.deepcopy(sched)
    for k, v in changes.items():
        getattr(s, k).update(v) if isinstance(v, dict) else setattr(s, k, v)
    return s
