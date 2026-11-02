"""M1 - canonical data model. Course / Section / Student selection / Enrolment are kept separate."""
from __future__ import annotations
from dataclasses import dataclass, field

DAYS, PERIODS = 5, 6                      # slot = day * PERIODS + period  (30 slots)
N_SLOTS = DAYS * PERIODS
CLASS, LAB = "CLASS", "LAB"

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


@dataclass(frozen=True)
class Section:
    id: str
    course_id: str
    capacity: int                         # planned size


@dataclass(frozen=True)
class Faculty:
    id: str
    name: str
    qualified: frozenset                  # course ids
    max_hours: int
    unavailable: frozenset = frozenset()  # slot indices


@dataclass(frozen=True)
class Room:
    id: str
    type: str
    capacity: int
    unavailable: frozenset = frozenset()


@dataclass(frozen=True)
class Student:
    id: str
    programme: str
    selections: tuple                     # course ids = the pathway


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

    def sections_of(self, course_id):
        return [s for s in self.sections.values() if s.course_id == course_id]

    def section_sessions(self, sec_id):
        return self.courses[self.sections[sec_id].course_id].sessions

    def section_hours(self, sec_id):
        return sum(x.duration for x in self.section_sessions(sec_id))


@dataclass
class Schedule:
    """Solver output. placement[(section, k)] = (start_slot, room_id); faculty[section] = faculty id;
    enrolment[student][course] = section. unscheduled = sections the method could not place."""
    method: str = ""
    placement: dict = field(default_factory=dict)
    faculty: dict = field(default_factory=dict)
    enrolment: dict = field(default_factory=dict)
    unscheduled: list = field(default_factory=list)
    status: str = ""                      # solver status string
    runtime: float = 0.0
    info: dict = field(default_factory=dict)


def slots_covered(start: int, duration: int):
    # Return every period occupied by one session.
    return range(start, start + duration)
