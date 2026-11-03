"""M2 - CSV import + input validation. Bad records are rejected with readable messages."""
from __future__ import annotations
import csv
import os
from dataclasses import dataclass
from .models import *


@dataclass
class Issue:
    severity: str          # ERROR (reject) | WARNING (loads, but scheduling may fail)
    where: str
    message: str

    def __str__(self):
        return f"[{self.severity}] {self.where}: {self.message}"


def _slots(txt):
    return frozenset(int(x) for x in txt.split(";") if x.strip() != "")


def parse_pattern(txt):
    """'1:CLASS;1:CLASS;2:LAB' -> tuple of SessionSpec"""
    out = []
    for part in txt.split(";"):
        d, t = part.split(":")
        out.append(SessionSpec(int(d), t.strip().upper()))
    return tuple(out)


def check_dataset(ds: Dataset):
    """Semantic checks on an already-built dataset. Returns list[Issue]."""
    # Validate relationships and values after CSV rows have been parsed.
    iss = []
    max_cap = {}
    for r in ds.rooms.values():
        max_cap[r.type] = max(max_cap.get(r.type, 0), r.capacity)
    for c in ds.courses.values():
        if not c.sessions:
            iss.append(Issue("ERROR", f"course {c.id}", "no sessions defined"))
        for x in c.sessions:
            if not 1 <= x.duration <= PERIODS:
                iss.append(Issue("ERROR", f"course {c.id}", f"session duration {x.duration} outside 1..{PERIODS}"))
            if x.room_type not in (CLASS, LAB):
                iss.append(Issue("ERROR", f"course {c.id}", f"unknown room type {x.room_type}"))
    for s in ds.sections.values():
        if s.course_id not in ds.courses:
            iss.append(Issue("ERROR", f"section {s.id}", f"unknown course {s.course_id}"))
            continue
        if s.capacity <= 0:
            iss.append(Issue("ERROR", f"section {s.id}", "capacity must be positive"))
        for x in ds.section_sessions(s.id):
            if s.capacity > max_cap.get(x.room_type, 0):
                iss.append(Issue("WARNING", f"section {s.id}", f"capacity {s.capacity} exceeds every {x.room_type} room"))
        if not any(s.course_id in f.qualified for f in ds.faculty.values()):
            iss.append(Issue("WARNING", f"section {s.id}", f"no faculty qualified for {s.course_id}"))
    for f in ds.faculty.values():
        for c in f.qualified:
            if c not in ds.courses:
                iss.append(Issue("ERROR", f"faculty {f.id}", f"qualified for unknown course {c}"))
        if f.max_hours <= 0:
            iss.append(Issue("ERROR", f"faculty {f.id}", "max_hours must be positive"))
        if any(not 0 <= t < N_SLOTS for t in f.unavailable):
            iss.append(Issue("ERROR", f"faculty {f.id}", f"unavailable slot outside 0..{N_SLOTS-1}"))
    for r in ds.rooms.values():
        if r.capacity <= 0:
            iss.append(Issue("ERROR", f"room {r.id}", "capacity must be positive"))
        if r.type not in (CLASS, LAB):
            iss.append(Issue("ERROR", f"room {r.id}", f"unknown room type {r.type}"))
    for st in ds.students.values():
        if len(set(st.selections)) != len(st.selections):
            iss.append(Issue("ERROR", f"student {st.id}", "duplicate course selection"))
        for c in st.selections:
            if c not in ds.courses:
                iss.append(Issue("ERROR", f"student {st.id}", f"selects unknown course {c}"))
            elif not ds.sections_of(c):
                iss.append(Issue("WARNING", f"student {st.id}", f"course {c} has no sections"))
    return iss


def save_csv(ds: Dataset, folder):
    # Export each dataset entity type to its own CSV table (classic schema + optional institutional fields).
    os.makedirs(folder, exist_ok=True)
    def w(name, header, rows):
        with open(os.path.join(folder, name), "w", newline="", encoding="utf-8") as fh:
            cw = csv.writer(fh); cw.writerow(header); cw.writerows(rows)
    w("courses.csv",
      ["course_id", "title", "category", "credits", "pattern",
       "school_id", "department_id", "programme_id", "stream", "semester", "academic_year", "course_type"],
      [[c.id, c.title, c.category, c.credits, ";".join(f"{x.duration}:{x.room_type}" for x in c.sessions),
        c.school_id, c.department_id, c.programme_id, c.stream, c.semester, c.academic_year, c.course_type]
       for c in ds.courses.values()])
    w("sections.csv",
      ["section_id", "course_id", "capacity", "school_id", "department_id", "programme_id", "stream", "semester", "batch", "session_pattern"],
      [[s.id, s.course_id, s.capacity, s.school_id, s.department_id, s.programme_id, s.stream, s.semester, s.batch,
        ";".join(f"{x.duration}:{x.room_type}" for x in s.sessions) if s.sessions is not None else ""]
       for s in ds.sections.values()])
    w("faculty.csv",
      ["faculty_id", "name", "qualified", "max_hours", "unavailable", "school_id", "department_id", "designation"],
      [[f.id, f.name, ";".join(sorted(f.qualified)), f.max_hours, ";".join(map(str, sorted(f.unavailable))),
        f.school_id, f.department_id, f.designation]
       for f in ds.faculty.values()])
    w("rooms.csv",
      ["room_id", "type", "capacity", "unavailable", "school_id", "building"],
      [[r.id, r.type, r.capacity, ";".join(map(str, sorted(r.unavailable))), r.school_id, r.building]
       for r in ds.rooms.values()])
    w("students.csv",
      ["student_id", "programme", "selections", "school_id", "stream", "semester", "batch"],
      [[s.id, s.programme, ";".join(s.selections), s.school_id, s.stream, s.semester, s.batch]
       for s in ds.students.values()])
    if ds.baseline:
        from .models import slot_to_day_period
        rows = []
        for ba in sorted(ds.baseline.values(), key=lambda x: (x.section_id, x.session_index)):
            day, period = slot_to_day_period(ba.start_slot)
            sec = ds.sections[ba.section_id]
            course = ds.courses[sec.course_id]
            fac = ds.faculty.get(ba.faculty_id)
            room = ds.rooms.get(ba.room_id)
            rows.append([
                day, f"Period {period}", ba.section_id, sec.course_id, course.title, course.category,
                ds.section_sessions(ba.section_id)[ba.session_index].duration,
                ba.room_id, room.type if room else "", ba.faculty_id, fac.name if fac else "",
                ba.mode, ba.session_index, sec.school_id, sec.stream,
            ])
        w("timetable.csv",
          ["Day", "Period", "Section", "Course Code", "Course Title", "Category", "Duration (Hrs)",
           "Room", "Room Type", "Faculty ID", "Faculty Name", "mode", "session_index", "school_id", "stream"],
          rows)


def load_csv(folder, name="csv_import", default_assignment_mode="preferred"):
    """Returns (Dataset | None, issues). Dataset is None if any ERROR exists.

    Classic fixed-schema CSV folders remain supported. Extra institutional columns are
    accepted when present. An optional timetable.csv is attached as the optimization baseline.
    """
    # Read required files first; malformed rows and semantic issues are reported below.
    issues, tables = [], {}
    spec = {"courses.csv": ["course_id", "title", "category", "credits", "pattern"],
            "sections.csv": ["section_id", "course_id", "capacity"],
            "faculty.csv": ["faculty_id", "name", "qualified", "max_hours", "unavailable"],
            "rooms.csv": ["room_id", "type", "capacity", "unavailable"],
            "students.csv": ["student_id", "programme", "selections"]}
    for fn, cols in spec.items():
        path = os.path.join(folder, fn)
        if not os.path.exists(path):
            issues.append(Issue("ERROR", fn, "file missing")); continue
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rd = csv.DictReader(fh)
            if rd.fieldnames is None or any(c not in rd.fieldnames for c in cols):
                issues.append(Issue("ERROR", fn, f"expected columns {cols}, found {rd.fieldnames}")); continue
            tables[fn] = list(rd)
    if issues:
        return None, issues
    objs = {k: {} for k in ("courses", "sections", "faculty", "rooms", "students")}
    def g(row, key, default=""):
        return (row.get(key) or default).strip()

    def build(fn, key, idcol, make):
        for i, row in enumerate(tables[fn], start=2):
            where = f"{fn} line {i}"
            try:
                o = make(row)
            except (ValueError, KeyError, TypeError) as e:
                issues.append(Issue("ERROR", where, f"malformed record ({e})")); continue
            if row[idcol] in objs[key]:
                issues.append(Issue("ERROR", where, f"duplicate id {row[idcol]}")); continue
            objs[key][row[idcol]] = o
    build("courses.csv", "courses", "course_id", lambda r: Course(
        r["course_id"], r["title"], r["category"], int(r["credits"]), parse_pattern(r["pattern"]),
        school_id=g(r, "school_id"), department_id=g(r, "department_id"), programme_id=g(r, "programme_id"),
        stream=g(r, "stream"), semester=g(r, "semester"), academic_year=g(r, "academic_year"),
        course_type=g(r, "course_type")))
    build("sections.csv", "sections", "section_id", lambda r: Section(
        r["section_id"], r["course_id"], int(r["capacity"]),
        school_id=g(r, "school_id"), department_id=g(r, "department_id"), programme_id=g(r, "programme_id"),
        stream=g(r, "stream"), semester=g(r, "semester"), batch=g(r, "batch"),
        sessions=parse_pattern(g(r, "session_pattern")) if g(r, "session_pattern") else None))
    build("faculty.csv", "faculty", "faculty_id", lambda r: Faculty(
        r["faculty_id"], r["name"], frozenset(x for x in r["qualified"].split(";") if x),
        int(r["max_hours"]), _slots(r["unavailable"]),
        school_id=g(r, "school_id"), department_id=g(r, "department_id"), designation=g(r, "designation")))
    build("rooms.csv", "rooms", "room_id", lambda r: Room(
        r["room_id"], r["type"].upper(), int(r["capacity"]), _slots(r["unavailable"]),
        school_id=g(r, "school_id"), building=g(r, "building")))
    build("students.csv", "students", "student_id", lambda r: Student(
        r["student_id"], r["programme"], tuple(x for x in r["selections"].split(";") if x),
        school_id=g(r, "school_id"), stream=g(r, "stream"), semester=g(r, "semester"), batch=g(r, "batch")))
    ds = Dataset(name, objs["courses"], objs["sections"], objs["faculty"], objs["rooms"], objs["students"], synthetic=False)
    issues += check_dataset(ds)
    if any(i.severity == "ERROR" for i in issues):
        return None, issues

    # Optional original timetable baseline (preserves uploaded CSV; attaches normalized baseline only).
    for tt_name in ("timetable.csv", "assignments.csv", "baseline.csv"):
        tt_path = os.path.join(folder, tt_name)
        if os.path.isfile(tt_path):
            from .importer import load_timetable_csv
            result = load_timetable_csv(tt_path, ds=ds, default_mode=default_assignment_mode)
            issues.extend(result.issues)
            if result.dataset is None:
                return None, issues
            ds = result.dataset
            break
    return ds, issues
