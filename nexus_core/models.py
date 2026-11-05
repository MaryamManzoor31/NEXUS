"""M1 - canonical data model. Course / Section / Student selection / Enrolment are kept separate."""
from __future__ import annotations
from dataclasses import dataclass, field

DAYS, PERIODS = 5, 10                     # 10 teaching sessions per day
N_SLOTS = DAYS * PERIODS
SESSION_TIMES = (
    ("08:00", "08:55"),
    ("09:00", "09:55"),
    ("10:00", "10:55"),
    ("11:05", "12:00"),
    ("12:05", "13:00"),
    ("13:10", "14:05"),
    ("14:10", "15:05"),
    ("15:10", "16:00"),
    ("16:15", "17:10"),
    ("17:15", "18:00"),
)
SESSION_START_MINUTES = tuple(
    int(start[:2]) * 60 + int(start[3:])
    for start, _ in SESSION_TIMES
)
MAX_SESSION_DURATION = 5
CLASS, LAB = "CLASS", "LAB"
MORNING_SESSION = "morning"
AFTERNOON_SESSION = "afternoon"
EXTENDED_EARLY_SESSION = "extended_08_16"
EXTENDED_LATE_SESSION = "extended_10_18"
STUDENT_DAY_SESSIONS = (
    MORNING_SESSION,
    AFTERNOON_SESSION,
    EXTENDED_EARLY_SESSION,
    EXTENDED_LATE_SESSION,
)

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")

# Baseline assignment modes for existing university timetables.
FIXED = "fixed"            # must remain unchanged
PREFERRED = "preferred"    # soft preference / changeable with cost
FLEXIBLE = "flexible"      # may be freely re-optimized

ASSIGNMENT_MODES = frozenset({FIXED, PREFERRED, FLEXIBLE})


# A course can meet in several weekly sessions, each requiring a room type.
@dataclass(frozen=True)
class SessionSpec:
    duration: int                         # in slots (periods)
    room_type: str                        # CLASS | LAB


@dataclass(frozen=True)
class Course:
    id: str
    title: str
    category: str                         # Major, Minor, Skill-Based, Ability-Enhancement, Value-Added, ...
    credits: int
    sessions: tuple[SessionSpec, ...]     # weekly contact pattern
    school_id: str = ""
    department_id: str = ""
    programme_id: str = ""
    stream: str = ""
    semester: str = ""
    academic_year: str = ""
    course_type: str = ""                 # major / minor / elective / skill / ...


@dataclass(frozen=True)
class Section:
    id: str
    course_id: str
    capacity: int                         # planned size
    school_id: str = ""
    department_id: str = ""
    programme_id: str = ""
    stream: str = ""
    semester: str = ""
    batch: str = ""
    sessions: tuple[SessionSpec, ...] | None = None


@dataclass(frozen=True)
class Faculty:
    id: str
    name: str
    qualified: frozenset                  # course ids
    max_hours: int
    unavailable: frozenset = frozenset()  # slot indices
    school_id: str = ""
    department_id: str = ""
    designation: str = ""


@dataclass(frozen=True)
class Room:
    id: str
    type: str
    capacity: int
    unavailable: frozenset = frozenset()
    school_id: str = ""
    building: str = ""


@dataclass(frozen=True)
class Student:
    id: str
    programme: str
    selections: tuple                     # course ids = the pathway
    school_id: str = ""
    stream: str = ""
    semester: str = ""
    batch: str = ""
    department_id: str = ""


@dataclass(frozen=True)
class BaselineAssignment:
    """One session placement from an existing university timetable."""
    section_id: str
    session_index: int
    start_slot: int
    room_id: str
    faculty_id: str
    mode: str = PREFERRED                 # fixed | preferred | flexible


@dataclass
class Dataset:
    # The dataset keeps related entities indexed by ID for quick lookup.
    name: str
    courses: dict
    sections: dict
    faculty: dict
    rooms: dict
    students: dict
    synthetic: bool = True
    meta: dict = field(default_factory=dict)
    # (section_id, session_index) -> BaselineAssignment from the original timetable
    baseline: dict = field(default_factory=dict)

    def sections_of(self, course_id):
        return [s for s in self.sections.values() if s.course_id == course_id]

    def section_sessions(self, sec_id):
        section = self.sections[sec_id]
        return section.sessions if section.sessions is not None else self.courses[section.course_id].sessions

    def section_hours(self, sec_id):
        return sum(x.duration for x in self.section_sessions(sec_id))

    def baseline_schedule(self) -> "Schedule":
        """Materialize the original timetable as a Schedule (no enrolment)."""
        sch = Schedule(method="baseline", status="BASELINE")
        for key, ba in self.baseline.items():
            sch.placement[(ba.section_id, ba.session_index)] = (ba.start_slot, ba.room_id)
            sch.faculty[ba.section_id] = ba.faculty_id
        placed = {sid for (sid, _) in sch.placement}
        sch.unscheduled = [s for s in self.sections if s not in placed]
        return sch


@dataclass
class Schedule:
    """Solver output. placement[(section, k)] = (start_slot, room_id); faculty[section] = faculty id;
    enrolment[student][course] = section. unscheduled = sections the method could not place."""
    method: str = ""
    placement: dict = field(default_factory=dict)
    faculty: dict = field(default_factory=dict)
    enrolment: dict = field(default_factory=dict)
    student_categories: dict = field(default_factory=dict)  # student -> day index -> session mode
    unscheduled: list = field(default_factory=list)
    status: str = ""                      # solver status string
    runtime: float = 0.0
    info: dict = field(default_factory=dict)


def slots_covered(start: int, duration: int):
    # Return every period occupied by one session.
    return range(start, start + duration)


def slot_to_day_period(slot: int) -> tuple[str, int]:
    """Return (day_name, 1-based period) for a slot index."""
    day = slot // PERIODS
    period = slot % PERIODS
    return DAY_NAMES[day], period + 1


def day_period_to_slot(day: str | int, period: int) -> int:
    """Convert day name or 0-based index and 1-based period to a slot index."""
    if isinstance(day, str):
        day_l = day.strip().lower()
        day_idx = next((i for i, n in enumerate(DAY_NAMES) if n.lower() == day_l), None)
        if day_idx is None:
            raise ValueError(f"unknown day {day!r}")
    else:
        day_idx = int(day)
    p = int(period)
    if p < 1 or p > PERIODS:
        raise ValueError(f"period {period} outside 1..{PERIODS}")
    return day_idx * PERIODS + (p - 1)
