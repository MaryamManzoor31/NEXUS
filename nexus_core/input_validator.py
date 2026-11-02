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
        for x in ds.courses[s.course_id].sessions:
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
    # Export each dataset entity type to its own CSV table.
    os.makedirs(folder, exist_ok=True)
    def w(name, header, rows):
        with open(os.path.join(folder, name), "w", newline="") as fh:
            cw = csv.writer(fh); cw.writerow(header); cw.writerows(rows)
    w("courses.csv", ["course_id", "title", "category", "credits", "pattern"],
      [[c.id, c.title, c.category, c.credits, ";".join(f"{x.duration}:{x.room_type}" for x in c.sessions)] for c in ds.courses.values()])
    w("sections.csv", ["section_id", "course_id", "capacity"], [[s.id, s.course_id, s.capacity] for s in ds.sections.values()])
    w("faculty.csv", ["faculty_id", "name", "qualified", "max_hours", "unavailable"],
      [[f.id, f.name, ";".join(sorted(f.qualified)), f.max_hours, ";".join(map(str, sorted(f.unavailable)))] for f in ds.faculty.values()])
    w("rooms.csv", ["room_id", "type", "capacity", "unavailable"],
      [[r.id, r.type, r.capacity, ";".join(map(str, sorted(r.unavailable)))] for r in ds.rooms.values()])
    w("students.csv", ["student_id", "programme", "selections"],
      [[s.id, s.programme, ";".join(s.selections)] for s in ds.students.values()])


def load_csv(folder, name="csv_import"):
    """Returns (Dataset | None, issues). Dataset is None if any ERROR exists."""
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
        with open(path, newline="") as fh:
            rd = csv.DictReader(fh)
            if rd.fieldnames is None or any(c not in rd.fieldnames for c in cols):
                issues.append(Issue("ERROR", fn, f"expected columns {cols}, found {rd.fieldnames}")); continue
            tables[fn] = list(rd)
    if issues:
        return None, issues
    objs = {k: {} for k in ("courses", "sections", "faculty", "rooms", "students")}
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
    build("courses.csv", "courses", "course_id", lambda r: Course(r["course_id"], r["title"], r["category"], int(r["credits"]), parse_pattern(r["pattern"])))
    build("sections.csv", "sections", "section_id", lambda r: Section(r["section_id"], r["course_id"], int(r["capacity"])))
    build("faculty.csv", "faculty", "faculty_id", lambda r: Faculty(r["faculty_id"], r["name"], frozenset(x for x in r["qualified"].split(";") if x), int(r["max_hours"]), _slots(r["unavailable"])))
    build("rooms.csv", "rooms", "room_id", lambda r: Room(r["room_id"], r["type"].upper(), int(r["capacity"]), _slots(r["unavailable"])))
    build("students.csv", "students", "student_id", lambda r: Student(r["student_id"], r["programme"], tuple(x for x in r["selections"].split(";") if x)))
    ds = Dataset(name, objs["courses"], objs["sections"], objs["faculty"], objs["rooms"], objs["students"], synthetic=False)
    issues += check_dataset(ds)
    if any(i.severity == "ERROR" for i in issues):
        return None, issues
    return ds, issues
