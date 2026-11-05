import itertools
import re
from collections import defaultdict
from .models import *

STUDENT_SESSION_WINDOWS = {
    MORNING_SESSION: frozenset(range(0, 5)),
    # Period 6 begins at 13:10; allowing it in the afternoon's 13:00 start
    # window matches the displayed clock-time boundary (12:05-13:00 is P5).
    AFTERNOON_SESSION: frozenset(range(5, 10)),
    # Extended windows cover 08:00-16:00 and 10:00-18:00 respectively.
    # Periods are atomic; P8 ends at 16:00 and P9 starts at 16:15.
    EXTENDED_EARLY_SESSION: frozenset(range(0, 8)),
    EXTENDED_LATE_SESSION: frozenset(range(2, 10)),
}
EXTENDED_SESSIONS = frozenset({EXTENDED_EARLY_SESSION, EXTENDED_LATE_SESSION})
LUNCH_SLOTS = frozenset({4, 5})
_SCOPE_STOP_WORDS = frozenset({"bachelor", "degree", "technology", "of", "the", "and"})


def split_course_ids(*values):
    """Parse selected course IDs from semicolon- or comma-separated input fields."""
    out = []
    seen = set()
    for value in values:
        if not value:
            continue
        items = value if isinstance(value, (list, tuple, set)) else re.split(r"[;,]", str(value))
        for item in items:
            course_id = str(item).strip()
            if course_id and course_id not in seen:
                out.append(course_id)
                seen.add(course_id)
    return tuple(out)


def normalized_course_category(category="", course_type=""):
    """Preserve minor/elective semantics even when a source labels them as course types."""
    labels = f"{category or ''} {course_type or ''}".casefold()
    if "minor" in labels:
        return "Minor"
    if "elective" in labels:
        return "Program Elective"
    return category or "Core"


def is_minor_or_elective(course):
    labels = f"{course.course_type or ''} {course.category or ''}".casefold()
    return "minor" in labels or "elective" in labels


def _scope_tokens(value):
    tokens = set()
    for part in re.split(r"[;,]", str(value or "").casefold()):
        words = re.findall(r"[a-z0-9]+", part)
        tokens.update(word for word in words if word not in _SCOPE_STOP_WORDS)
    return tokens


def _scope_matches(student_value, section_value):
    student_tokens = _scope_tokens(student_value)
    section_tokens = _scope_tokens(section_value)
    if not student_tokens or not section_tokens:
        return False
    if student_tokens == section_tokens:
        return True
    if len(student_tokens) == 1 or len(section_tokens) == 1:
        return student_tokens <= section_tokens or section_tokens <= student_tokens
    return student_tokens <= section_tokens or section_tokens <= student_tokens


def student_section_options(ds: Dataset, student: Student, course_id: str, section_ids):
    """Return sections for a selected course that fit the student's semester/cohort.

    Minor and elective courses are cross-program offerings by design. Core offerings
    prefer matching batch, stream, programme, or school metadata when such matches
    are present, while incomplete metadata does not make a course disappear.
    """
    options = [
        sid for sid in section_ids
        if sid in ds.sections and ds.sections[sid].course_id == course_id
    ]
    if student.semester:
        semester = str(student.semester).strip().casefold()
        if any(ds.sections[sid].semester for sid in options):
            options = [
                sid for sid in options
                if not ds.sections[sid].semester
                or str(ds.sections[sid].semester).strip().casefold() == semester
            ]
    if not options:
        return []

    course = ds.courses.get(course_id)
    if course and is_minor_or_elective(course):
        return options

    for student_field, section_field in (
        ("batch", "batch"),
        ("stream", "stream"),
        ("department_id", "department_id"),
        ("programme", "programme_id"),
        ("school_id", "school_id"),
    ):
        student_value = getattr(student, student_field, "")
        if not student_value:
            continue
        values = [(sid, getattr(ds.sections[sid], section_field, "")) for sid in options]
        known = [(sid, value) for sid, value in values if value]
        matches = [sid for sid, value in known if _scope_matches(student_value, value)]
        if matches:
            return matches
        # A fully described set of core sections with no matching batch means
        # the student's course choice has no offering for their cohort.
        if student_field == "batch" and len(known) == len(options):
            return []
    return options


def allowed_student_day_sessions(session_slots):
    """Return day-session modes that contain all sessions and preserve an extended lunch break."""
    occupied = {slot % PERIODS for slots in session_slots for slot in slots}
    allowed = []
    for mode in STUDENT_DAY_SESSIONS:
        window = STUDENT_SESSION_WINDOWS[mode]
        if not occupied.issubset(window):
            continue
        # The period grid represents 12:05-14:05 as two adjacent teaching slots.
        # Requiring one to remain free guarantees at least one continuous hour.
        if mode in EXTENDED_SESSIONS and len(occupied & LUNCH_SLOTS) > 1:
            continue
        allowed.append(mode)
    return allowed


def shared_counts(ds: Dataset):
    """number of students who selected both courses (unordered pair)"""
    # These counts help schedulers avoid clashes between popular course pairs.
    sh = defaultdict(int)
    for st in ds.students.values():
        for a, b in itertools.combinations(sorted(st.selections), 2):
            sh[(a, b)] += 1
    return sh


def starts_for(duration):
    """legal start slots: session must stay inside one day"""
    return [d * PERIODS + p for d in range(DAYS) for p in range(PERIODS - duration + 1)]


def semester_session_starts(
    semester: str, mode: str, starts: list[int], duration: int = 1
) -> list[int]:
    """Keep a section inside its selected half-day or corresponding extended window."""
    semester = str(semester or "").strip()
    if not semester or not mode or mode == "auto":
        return starts
    if mode == MORNING_SESSION:
        cutoff = 5 if duration >= 5 else 8
        return [
            slot for slot in starts
            if slot % PERIODS < cutoff and slot % PERIODS + duration <= cutoff
        ]
    if mode == AFTERNOON_SESSION:
        earliest = 5 if duration >= 5 else 2
        return [
            slot for slot in starts
            if slot % PERIODS >= earliest and slot % PERIODS + duration <= PERIODS
        ]
    raise ValueError(f"Unknown semester session {mode!r} for semester {semester}")


def sec_slots(ds, placement, sid):
    # Return None unless every session for the section has a placement.
    out = set()
    for k, spec in enumerate(ds.section_sessions(sid)):
        if (sid, k) not in placement:
            return None
        s = placement[(sid, k)][0]
        out |= set(range(s, s + spec.duration))
    return out
