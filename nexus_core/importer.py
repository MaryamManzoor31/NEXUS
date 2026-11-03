"""Flexible CSV/Excel import and column mapping for real university datasets.

Never invents missing faculty, rooms, students, or allocations. Missing required
fields are reported as Issues so the user can supply a mapping or value.
"""
from __future__ import annotations
import csv
import io
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .input_validator import Issue, check_dataset, parse_pattern, _slots
from .models import (
    ASSIGNMENT_MODES, BaselineAssignment, CLASS, Course, Dataset, Faculty,
    FIXED, FLEXIBLE, LAB, PREFERRED, Room, Schedule, Section, SessionSpec,
    Student, day_period_to_slot,
)


MAIN_NS = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

# Canonical NEXUS fields per entity table.
ENTITY_FIELDS: dict[str, dict[str, dict]] = {
    "courses": {
        "course_id": {"required": True, "aliases": ["course_id", "course id", "code", "course_code", "subject_code", "subject id"]},
        "title": {"required": True, "aliases": ["title", "course_title", "course name", "subject", "subject_name", "name"]},
        "category": {"required": False, "aliases": ["category", "course_category", "nep_category"]},
        "credits": {"required": False, "aliases": ["credits", "credit", "cr"]},
        "pattern": {"required": False, "aliases": ["pattern", "sessions", "contact_pattern"]},
        "course_type": {"required": False, "aliases": ["course_type", "type", "ctype", "l-t-p type"]},
        "school_id": {"required": False, "aliases": ["school_id", "school", "school name"]},
        "department_id": {"required": False, "aliases": ["department_id", "department", "dept", "dept_id"]},
        "programme_id": {"required": False, "aliases": ["programme_id", "programme", "program", "program_id"]},
        "stream": {"required": False, "aliases": ["stream", "specialization", "branch"]},
        "semester": {"required": False, "aliases": ["semester", "sem"]},
        "academic_year": {"required": False, "aliases": ["academic_year", "year", "ay"]},
        "duration": {"required": False, "aliases": ["duration", "hours", "duration_hrs", "duration (hrs)"]},
        "room_type": {"required": False, "aliases": ["room_type", "session_room_type"]},
    },
    "sections": {
        "section_id": {"required": True, "aliases": ["section_id", "section", "sec_id", "class_section"]},
        "course_id": {"required": True, "aliases": ["course_id", "course", "course_code", "code", "subject_code"]},
        "capacity": {"required": False, "aliases": ["capacity", "cap", "max_students", "strength"]},
        "school_id": {"required": False, "aliases": ["school_id", "school"]},
        "department_id": {"required": False, "aliases": ["department_id", "department", "dept"]},
        "programme_id": {"required": False, "aliases": ["programme_id", "programme", "program"]},
        "stream": {"required": False, "aliases": ["stream", "specialization"]},
        "semester": {"required": False, "aliases": ["semester", "sem"]},
        "batch": {"required": False, "aliases": ["batch", "cohort", "group"]},
    },
    "faculty": {
        "faculty_id": {"required": True, "aliases": ["faculty_id", "faculty id", "teacher_id", "staff_id", "id"]},
        "name": {"required": True, "aliases": ["name", "faculty_name", "teacher", "faculty name"]},
        "qualified": {"required": False, "aliases": ["qualified", "courses", "qualified_courses", "can_teach"]},
        "max_hours": {"required": False, "aliases": ["max_hours", "max hours", "workload", "contact_hours"]},
        "unavailable": {"required": False, "aliases": ["unavailable", "blocked_slots"]},
        "school_id": {"required": False, "aliases": ["school_id", "school"]},
        "department_id": {"required": False, "aliases": ["department_id", "department", "dept"]},
        "designation": {"required": False, "aliases": ["designation", "rank", "title"]},
    },
    "rooms": {
        "room_id": {"required": True, "aliases": ["room_id", "room", "classroom", "room name", "hall"]},
        "type": {"required": False, "aliases": ["type", "room_type"]},
        "capacity": {"required": False, "aliases": ["capacity", "cap", "seats"]},
        "unavailable": {"required": False, "aliases": ["unavailable", "blocked_slots"]},
        "school_id": {"required": False, "aliases": ["school_id", "school"]},
        "building": {"required": False, "aliases": ["building", "block"]},
    },
    "students": {
        "student_id": {"required": True, "aliases": ["student_id", "student", "roll", "roll_no", "reg_no"]},
        "programme": {"required": False, "aliases": ["programme", "program", "programme_id"]},
        "selections": {"required": False, "aliases": ["selections", "courses", "selected_courses", "course_ids"]},
        "school_id": {"required": False, "aliases": ["school_id", "school"]},
        "stream": {"required": False, "aliases": ["stream"]},
        "semester": {"required": False, "aliases": ["semester", "sem"]},
        "batch": {"required": False, "aliases": ["batch", "section", "cohort"]},
    },
    "timetable": {
        "section_id": {"required": True, "aliases": ["section_id", "section", "sec_id"]},
        "course_id": {"required": False, "aliases": ["course_id", "course code", "course_code", "code"]},
        "course_title": {"required": False, "aliases": ["course_title", "course title", "title"]},
        "category": {"required": False, "aliases": ["category"]},
        "day": {"required": True, "aliases": ["day", "weekday"]},
        "period": {"required": True, "aliases": ["period", "slot", "period_no"]},
        "duration": {"required": False, "aliases": ["duration", "duration (hrs)", "hours", "duration_hrs"]},
        "room_id": {"required": True, "aliases": ["room_id", "room", "classroom"]},
        "room_type": {"required": False, "aliases": ["room_type", "room type"]},
        "faculty_id": {"required": True, "aliases": ["faculty_id", "faculty id", "teacher_id"]},
        "faculty_name": {"required": False, "aliases": ["faculty_name", "faculty name", "teacher"]},
        "mode": {"required": False, "aliases": ["mode", "flexibility", "assignment_mode", "fixed"]},
        "school_id": {"required": False, "aliases": ["school_id", "school"]},
        "stream": {"required": False, "aliases": ["stream"]},
        "session_index": {"required": False, "aliases": ["session_index", "session", "k"]},
    },
}

TABLE_ALIASES = {
    "courses": ["courses", "course", "subjects", "subject"],
    "sections": ["sections", "section", "batches", "classes"],
    "faculty": ["faculty", "teachers", "staff", "faculty_members"],
    "rooms": ["rooms", "room", "classrooms", "labs", "venues"],
    "students": ["students", "student", "learners", "enrolments_students"],
    "timetable": ["timetable", "schedule", "assignments", "baseline", "existing_timetable"],
}


@dataclass
class TablePreview:
    entity: str
    filename: str
    columns: list[str]
    suggested_mapping: dict[str, str]
    row_count: int
    sample_rows: list[dict]


@dataclass
class ImportResult:
    dataset: Dataset | None
    issues: list[Issue] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    previews: list[TablePreview] = field(default_factory=list)


def _norm(s: str) -> str:
    return re.sub(r"[\s_\-]+", " ", (s or "").strip().lower())


def _norm_id(s: str) -> str:
    return re.sub(r"\s+", "_", (s or "").strip())


def suggest_mapping(columns: list[str], entity: str) -> dict[str, str]:
    """Map detected columns to canonical NEXUS fields for one entity."""
    fields = ENTITY_FIELDS[entity]
    used = set()
    mapping = {}
    col_by_norm = {_norm(c): c for c in columns}
    for field_name, spec in fields.items():
        for alias in spec["aliases"]:
            key = _norm(alias)
            if key in col_by_norm and col_by_norm[key] not in used:
                mapping[field_name] = col_by_norm[key]
                used.add(col_by_norm[key])
                break
    return mapping


def detect_entity_from_filename(filename: str) -> str | None:
    stem = _norm(os.path.splitext(os.path.basename(filename))[0])
    for entity, aliases in TABLE_ALIASES.items():
        if stem in aliases or any(a in stem for a in aliases):
            return entity
    return None


def read_tabular_file(path: str) -> tuple[list[str], list[dict]]:
    """Read a CSV or single-sheet Excel (.xlsx) file into header + row dicts."""
    lower = path.lower()
    if lower.endswith(".xlsx"):
        return _read_xlsx_first_sheet(path)
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rd = csv.DictReader(fh)
        if not rd.fieldnames:
            return [], []
        cols = list(rd.fieldnames)
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in rd]
        return cols, rows


def _read_xlsx_first_sheet(path: str) -> tuple[list[str], list[dict]]:
    with zipfile.ZipFile(path, "r") as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in ss.findall(".//ns:si", MAIN_NS):
                shared.append("".join(t.text or "" for t in si.findall(".//ns:t", MAIN_NS)))
        sheet_path = "xl/worksheets/sheet1.xml"
        if sheet_path not in z.namelist():
            # fall back to first worksheet
            sheets = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
            if not sheets:
                return [], []
            sheet_path = sheets[0]
        root = ET.fromstring(z.read(sheet_path))
        grid = []
        for row in root.findall(".//ns:row", MAIN_NS):
            cells = {}
            for c in row.findall("ns:c", MAIN_NS):
                ref = c.attrib.get("r", "")
                col = "".join(ch for ch in ref if ch.isalpha())
                v = c.find("ns:v", MAIN_NS)
                val = v.text if v is not None else ""
                if c.attrib.get("t") == "s" and val.isdigit():
                    idx = int(val)
                    val = shared[idx] if idx < len(shared) else val
                cells[col] = (val or "").strip()
            if cells:
                # expand to ordered columns A,B,C...
                max_col = max(cells)
                ordered = []
                col = "A"
                while True:
                    ordered.append(cells.get(col, ""))
                    if col == max_col:
                        break
                    # next Excel column letter (simple A..Z only for mapping previews)
                    col = chr(ord(col) + 1) if len(col) == 1 and col < "Z" else col + "A"
                    if len(col) > 3:
                        break
                grid.append(ordered)
        if not grid:
            return [], []
        # use first non-empty row as header
        header = [h or f"COL_{i+1}" for i, h in enumerate(grid[0])]
        rows = []
        for vals in grid[1:]:
            if not any(vals):
                continue
            row = {header[i]: (vals[i] if i < len(vals) else "") for i in range(len(header))}
            rows.append(row)
        return header, rows


def preview_folder(folder: str) -> list[TablePreview]:
    """Detect files in a folder and suggest column mappings."""
    previews = []
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith((".csv", ".xlsx")):
            continue
        path = os.path.join(folder, name)
        entity = detect_entity_from_filename(name)
        cols, rows = read_tabular_file(path)
        if not cols:
            continue
        if entity is None:
            # try content-based guess from suggested mappings coverage
            best, best_n = None, -1
            for cand in ENTITY_FIELDS:
                m = suggest_mapping(cols, cand)
                req = sum(1 for f, spec in ENTITY_FIELDS[cand].items() if spec["required"] and f in m)
                if req > best_n:
                    best, best_n = cand, req
            entity = best or "timetable"
        mapping = suggest_mapping(cols, entity)
        previews.append(TablePreview(
            entity=entity,
            filename=name,
            columns=cols,
            suggested_mapping=mapping,
            row_count=len(rows),
            sample_rows=rows[:3],
        ))
    return previews


def _get(row: dict, mapping: dict, field: str, default: str = "") -> str:
    col = mapping.get(field)
    if not col:
        return default
    return (row.get(col) or default).strip()


def _parse_period(raw: str) -> int:
    m = re.search(r"(\d+)", raw or "")
    if not m:
        raise ValueError(f"cannot parse period from {raw!r}")
    return int(m.group(1))


def _parse_mode(raw: str, default: str = PREFERRED) -> str:
    v = (raw or default).strip().lower()
    if v in ("1", "true", "yes", "fixed"):
        return FIXED
    if v in ("0", "false", "no", "flexible", "flex"):
        return FLEXIBLE
    if v in ASSIGNMENT_MODES:
        return v
    return default


def build_dataset_from_mapped_tables(
    tables: dict[str, tuple[list[dict], dict[str, str]]],
    name: str = "import",
    default_assignment_mode: str = PREFERRED,
    require_students: bool = False,
) -> ImportResult:
    """Build a Dataset from mapped entity tables. `tables[entity] = (rows, mapping)`."""
    issues: list[Issue] = []
    courses, sections, faculty, rooms, students = {}, {}, {}, {}, {}
    baseline: dict = {}

    # ---- courses ----
    if "courses" in tables:
        rows, mapping = tables["courses"]
        for i, row in enumerate(rows, start=2):
            cid = _get(row, mapping, "course_id")
            title = _get(row, mapping, "title")
            if not cid or not title:
                issues.append(Issue("ERROR", f"courses line {i}", "course_id and title are required"))
                continue
            if cid in courses:
                issues.append(Issue("ERROR", f"courses line {i}", f"duplicate id {cid}"))
                continue
            pattern_txt = _get(row, mapping, "pattern")
            try:
                if pattern_txt:
                    sessions = parse_pattern(pattern_txt)
                else:
                    dur = int(_get(row, mapping, "duration", "1") or "1")
                    rtype = (_get(row, mapping, "room_type", CLASS) or CLASS).upper()
                    if "lab" in rtype.lower():
                        rtype = LAB
                    else:
                        rtype = CLASS
                    sessions = (SessionSpec(max(1, min(dur, 6)), rtype),)
                credits = int(_get(row, mapping, "credits", "3") or "3")
            except (ValueError, TypeError) as e:
                issues.append(Issue("ERROR", f"courses line {i}", f"malformed record ({e})"))
                continue
            courses[cid] = Course(
                id=cid,
                title=title,
                category=_get(row, mapping, "category", "Core") or "Core",
                credits=credits,
                sessions=sessions,
                school_id=_get(row, mapping, "school_id"),
                department_id=_get(row, mapping, "department_id"),
                programme_id=_get(row, mapping, "programme_id"),
                stream=_get(row, mapping, "stream"),
                semester=_get(row, mapping, "semester"),
                academic_year=_get(row, mapping, "academic_year"),
                course_type=_get(row, mapping, "course_type"),
            )

    # ---- rooms ----
    if "rooms" in tables:
        rows, mapping = tables["rooms"]
        for i, row in enumerate(rows, start=2):
            rid = _norm_id(_get(row, mapping, "room_id"))
            if not rid:
                issues.append(Issue("ERROR", f"rooms line {i}", "room_id is required"))
                continue
            if rid in rooms:
                issues.append(Issue("ERROR", f"rooms line {i}", f"duplicate id {rid}"))
                continue
            try:
                rtype = (_get(row, mapping, "type", CLASS) or CLASS).upper()
                if "lab" in rtype.lower():
                    rtype = LAB
                else:
                    rtype = CLASS if rtype not in (CLASS, LAB) else rtype
                capacity = int(_get(row, mapping, "capacity", "60") or "60")
                unavailable = _slots(_get(row, mapping, "unavailable"))
            except (ValueError, TypeError) as e:
                issues.append(Issue("ERROR", f"rooms line {i}", f"malformed record ({e})"))
                continue
            rooms[rid] = Room(
                id=rid, type=rtype, capacity=capacity, unavailable=unavailable,
                school_id=_get(row, mapping, "school_id"),
                building=_get(row, mapping, "building"),
            )

    # ---- faculty ----
    if "faculty" in tables:
        rows, mapping = tables["faculty"]
        for i, row in enumerate(rows, start=2):
            fid = _get(row, mapping, "faculty_id")
            faculty_name = _get(row, mapping, "name")
            if not fid or not faculty_name:
                issues.append(Issue("ERROR", f"faculty line {i}", "faculty_id and name are required"))
                continue
            if fid in faculty:
                issues.append(Issue("ERROR", f"faculty line {i}", f"duplicate id {fid}"))
                continue
            try:
                qualified = frozenset(x for x in _get(row, mapping, "qualified").split(";") if x)
                max_hours = int(_get(row, mapping, "max_hours", "16") or "16")
                unavailable = _slots(_get(row, mapping, "unavailable"))
            except (ValueError, TypeError) as e:
                issues.append(Issue("ERROR", f"faculty line {i}", f"malformed record ({e})"))
                continue
            faculty[fid] = Faculty(
                id=fid, name=faculty_name, qualified=qualified, max_hours=max_hours, unavailable=unavailable,
                school_id=_get(row, mapping, "school_id"),
                department_id=_get(row, mapping, "department_id"),
                designation=_get(row, mapping, "designation"),
            )

    # ---- sections ----
    if "sections" in tables:
        rows, mapping = tables["sections"]
        for i, row in enumerate(rows, start=2):
            sid = _get(row, mapping, "section_id")
            cid = _get(row, mapping, "course_id")
            if not sid or not cid:
                issues.append(Issue("ERROR", f"sections line {i}", "section_id and course_id are required"))
                continue
            if sid in sections:
                issues.append(Issue("ERROR", f"sections line {i}", f"duplicate id {sid}"))
                continue
            try:
                capacity = int(_get(row, mapping, "capacity", "60") or "60")
            except (ValueError, TypeError) as e:
                issues.append(Issue("ERROR", f"sections line {i}", f"malformed record ({e})"))
                continue
            sections[sid] = Section(
                id=sid, course_id=cid, capacity=capacity,
                school_id=_get(row, mapping, "school_id"),
                department_id=_get(row, mapping, "department_id"),
                programme_id=_get(row, mapping, "programme_id"),
                stream=_get(row, mapping, "stream"),
                semester=_get(row, mapping, "semester"),
                batch=_get(row, mapping, "batch"),
            )

    # ---- students ----
    if "students" in tables:
        rows, mapping = tables["students"]
        for i, row in enumerate(rows, start=2):
            stid = _get(row, mapping, "student_id")
            if not stid:
                issues.append(Issue("ERROR", f"students line {i}", "student_id is required"))
                continue
            if stid in students:
                issues.append(Issue("ERROR", f"students line {i}", f"duplicate id {stid}"))
                continue
            sels = tuple(x for x in _get(row, mapping, "selections").split(";") if x)
            students[stid] = Student(
                id=stid,
                programme=_get(row, mapping, "programme", "Unknown") or "Unknown",
                selections=sels,
                school_id=_get(row, mapping, "school_id"),
                stream=_get(row, mapping, "stream"),
                semester=_get(row, mapping, "semester"),
                batch=_get(row, mapping, "batch"),
            )
    elif require_students:
        issues.append(Issue("ERROR", "students", "student records are required for this import"))

    # ---- timetable / baseline (may also seed missing entities if explicitly present in rows) ----
    if "timetable" in tables:
        rows, mapping = tables["timetable"]
        session_counter: dict[str, int] = defaultdict(int)
        for i, row in enumerate(rows, start=2):
            sid = _get(row, mapping, "section_id")
            fid = _get(row, mapping, "faculty_id")
            rid = _norm_id(_get(row, mapping, "room_id"))
            day = _get(row, mapping, "day")
            period_raw = _get(row, mapping, "period")
            if not sid or not fid or not rid or not day or not period_raw:
                issues.append(Issue(
                    "ERROR", f"timetable line {i}",
                    "section_id, faculty_id, room_id, day and period are required"
                ))
                continue
            try:
                period = _parse_period(period_raw)
                start = day_period_to_slot(day, period)
                dur = int(_get(row, mapping, "duration", "1") or "1")
                mode = _parse_mode(_get(row, mapping, "mode"), default_assignment_mode)
                k_raw = _get(row, mapping, "session_index")
                k = int(k_raw) if k_raw else session_counter[sid]
            except (ValueError, TypeError) as e:
                issues.append(Issue("ERROR", f"timetable line {i}", f"malformed record ({e})"))
                continue

            cid = _get(row, mapping, "course_id")
            title = _get(row, mapping, "course_title") or cid or sid
            rtype_raw = (_get(row, mapping, "room_type", CLASS) or CLASS).upper()
            rtype = LAB if "lab" in rtype_raw.lower() or "lab" in sid.lower() else CLASS

            # Seed course/section/faculty/room only from values present in the row — never invent IDs.
            if cid and cid not in courses:
                courses[cid] = Course(
                    id=cid,
                    title=title,
                    category=_get(row, mapping, "category", "Core") or "Core",
                    credits=3,
                    sessions=(SessionSpec(max(1, min(dur, 6)), rtype),),
                    school_id=_get(row, mapping, "school_id"),
                    stream=_get(row, mapping, "stream"),
                )
            if not cid:
                # section must already exist or we cannot attach a course
                if sid not in sections:
                    issues.append(Issue(
                        "ERROR", f"timetable line {i}",
                        f"section {sid} has no course_id and is not in sections table"
                    ))
                    continue
                cid = sections[sid].course_id

            if sid not in sections:
                sections[sid] = Section(
                    id=sid, course_id=cid, capacity=60,
                    school_id=_get(row, mapping, "school_id"),
                    stream=_get(row, mapping, "stream"),
                )
            elif sections[sid].course_id != cid:
                issues.append(Issue(
                    "ERROR", f"timetable line {i}",
                    f"section {sid} course mismatch: {sections[sid].course_id} vs {cid}"
                ))
                continue

            if fid not in faculty:
                fname = _get(row, mapping, "faculty_name") or fid
                faculty[fid] = Faculty(
                    id=fid, name=fname, qualified=frozenset({cid}), max_hours=16
                )
            else:
                f = faculty[fid]
                faculty[fid] = Faculty(
                    id=f.id, name=f.name, qualified=f.qualified | {cid},
                    max_hours=f.max_hours, unavailable=f.unavailable,
                    school_id=f.school_id, department_id=f.department_id, designation=f.designation,
                )

            if rid not in rooms:
                rooms[rid] = Room(id=rid, type=rtype, capacity=80)

            key = (sid, k)
            if key in baseline:
                issues.append(Issue("ERROR", f"timetable line {i}", f"duplicate baseline entry for {sid} session {k}"))
                continue
            baseline[key] = BaselineAssignment(
                section_id=sid, session_index=k, start_slot=start,
                room_id=rid, faculty_id=fid, mode=mode,
            )
            session_counter[sid] = max(session_counter[sid], k + 1)

            # Ensure course session pattern covers this session index
            if cid in courses and k >= len(courses[cid].sessions):
                c = courses[cid]
                extra = list(c.sessions)
                while len(extra) <= k:
                    extra.append(SessionSpec(max(1, min(dur, 6)), rtype))
                courses[cid] = Course(
                    id=c.id, title=c.title, category=c.category, credits=c.credits,
                    sessions=tuple(extra), school_id=c.school_id, department_id=c.department_id,
                    programme_id=c.programme_id, stream=c.stream, semester=c.semester,
                    academic_year=c.academic_year, course_type=c.course_type,
                )

    # Required entities for optimization
    for label, obj in (("courses", courses), ("sections", sections), ("faculty", faculty), ("rooms", rooms)):
        if not obj:
            issues.append(Issue("ERROR", label, f"no {label} records imported"))

    if not students:
        issues.append(Issue(
            "WARNING", "students",
            "no student records imported; Stage B allocation will be empty until students are supplied"
        ))

    if any(i.severity == "ERROR" for i in issues):
        return ImportResult(None, issues, summary={
            "courses": len(courses), "sections": len(sections), "faculty": len(faculty),
            "rooms": len(rooms), "students": len(students), "baseline_assignments": len(baseline),
        })

    ds = Dataset(
        name=name,
        courses=courses,
        sections=sections,
        faculty=faculty,
        rooms=rooms,
        students=students,
        synthetic=False,
        meta={
            "import_source": "mapped_tables",
            "default_assignment_mode": default_assignment_mode,
            "baseline_count": len(baseline),
        },
        baseline=baseline,
    )
    issues += check_dataset(ds)
    if any(i.severity == "ERROR" for i in issues):
        return ImportResult(None, issues, summary={
            "courses": len(courses), "sections": len(sections), "faculty": len(faculty),
            "rooms": len(rooms), "students": len(students), "baseline_assignments": len(baseline),
        })

    return ImportResult(ds, issues, summary={
        "courses": len(courses), "sections": len(sections), "faculty": len(faculty),
        "rooms": len(rooms), "students": len(students), "baseline_assignments": len(baseline),
        "fixed": sum(1 for b in baseline.values() if b.mode == FIXED),
        "preferred": sum(1 for b in baseline.values() if b.mode == PREFERRED),
        "flexible": sum(1 for b in baseline.values() if b.mode == FLEXIBLE),
    })


def import_folder(
    folder: str,
    name: str | None = None,
    mappings: dict[str, dict[str, str]] | None = None,
    default_assignment_mode: str = PREFERRED,
) -> ImportResult:
    """Import a folder of CSV/Excel files with optional explicit column mappings.

    `mappings` maps entity -> {canonical_field: source_column}.
    When omitted, suggested mappings from headers are used.
    """
    previews = preview_folder(folder)
    if not previews:
        return ImportResult(None, [Issue("ERROR", folder, "no CSV/Excel files found")], previews=[])

    tables: dict[str, tuple[list[dict], dict[str, str]]] = {}
    issues: list[Issue] = []
    for prev in previews:
        path = os.path.join(folder, prev.filename)
        _, rows = read_tabular_file(path)
        mapping = (mappings or {}).get(prev.entity) or prev.suggested_mapping
        # ensure required fields mapped
        missing = [
            f for f, spec in ENTITY_FIELDS[prev.entity].items()
            if spec["required"] and f not in mapping
        ]
        if missing:
            issues.append(Issue(
                "ERROR", prev.filename,
                f"unmapped required fields for {prev.entity}: {missing}. Detected columns: {prev.columns}"
            ))
            continue
        tables[prev.entity] = (rows, mapping)

    if issues:
        return ImportResult(None, issues, previews=previews)

    result = build_dataset_from_mapped_tables(
        tables,
        name=name or os.path.basename(os.path.abspath(folder)),
        default_assignment_mode=default_assignment_mode,
    )
    result.previews = previews
    return result


def load_timetable_csv(
    path: str,
    ds: Dataset | None = None,
    default_mode: str = PREFERRED,
    name: str = "timetable_import",
    allow_resources_from_timetable: bool = False,
) -> ImportResult:
    """Load an existing university timetable CSV.

    If `ds` is provided, baseline assignments are attached to it.
    Missing room/faculty references are errors unless `allow_resources_from_timetable`
    is True, in which case resources that appear in the timetable file itself are
    registered (still never invented from thin air).
    If `ds` is None, entities are built from the timetable rows that contain them.
    """
    cols, rows = read_tabular_file(path)
    if not cols:
        return ImportResult(None, [Issue("ERROR", path, "empty or unreadable timetable file")])
    mapping = suggest_mapping(cols, "timetable")
    missing = [f for f, spec in ENTITY_FIELDS["timetable"].items() if spec["required"] and f not in mapping]
    if missing:
        return ImportResult(None, [Issue(
            "ERROR", path,
            f"unmapped required timetable fields: {missing}. Detected columns: {cols}"
        )])

    if ds is None:
        return build_dataset_from_mapped_tables(
            {"timetable": (rows, mapping)},
            name=name,
            default_assignment_mode=default_mode,
        )

    # Attach baseline onto an existing dataset.
    issues: list[Issue] = []
    baseline = dict(ds.baseline)
    session_counter: dict[str, int] = defaultdict(int)
    for key in baseline:
        session_counter[key[0]] = max(session_counter[key[0]], key[1] + 1)
    added_rooms, added_faculty = [], []

    for i, row in enumerate(rows, start=2):
        sid = _get(row, mapping, "section_id")
        fid = _get(row, mapping, "faculty_id")
        rid = _norm_id(_get(row, mapping, "room_id"))
        day = _get(row, mapping, "day")
        period_raw = _get(row, mapping, "period")
        if not sid:
            issues.append(Issue("ERROR", f"timetable line {i}", "section_id is required"))
            continue
        if sid not in ds.sections:
            issues.append(Issue("ERROR", f"timetable line {i}", f"unknown section {sid}"))
            continue
        cid = ds.sections[sid].course_id
        if not fid:
            issues.append(Issue("ERROR", f"timetable line {i}", "faculty_id is required"))
            continue
        if fid not in ds.faculty:
            if allow_resources_from_timetable:
                fname = _get(row, mapping, "faculty_name") or fid
                ds.faculty[fid] = Faculty(id=fid, name=fname, qualified=frozenset({cid}), max_hours=16)
                added_faculty.append(fid)
            else:
                issues.append(Issue("ERROR", f"timetable line {i}", f"unknown or missing faculty {fid!r}"))
                continue
        if not rid:
            issues.append(Issue("ERROR", f"timetable line {i}", "room_id is required"))
            continue
        if rid not in ds.rooms:
            if allow_resources_from_timetable:
                rtype_raw = (_get(row, mapping, "room_type", CLASS) or CLASS).upper()
                rtype = LAB if "lab" in rtype_raw.lower() else CLASS
                ds.rooms[rid] = Room(id=rid, type=rtype, capacity=80)
                added_rooms.append(rid)
            else:
                issues.append(Issue("ERROR", f"timetable line {i}", f"unknown or missing room {rid!r}"))
                continue
        # Ensure faculty is qualified for the section's course when baseline assigns them.
        f = ds.faculty[fid]
        if cid not in f.qualified:
            ds.faculty[fid] = Faculty(
                id=f.id, name=f.name, qualified=f.qualified | {cid},
                max_hours=f.max_hours, unavailable=f.unavailable,
                school_id=f.school_id, department_id=f.department_id, designation=f.designation,
            )
        try:
            start = day_period_to_slot(day, _parse_period(period_raw))
            mode = _parse_mode(_get(row, mapping, "mode"), default_mode)
            k_raw = _get(row, mapping, "session_index")
            k = int(k_raw) if k_raw else 0
            # if section already has a baseline session and no explicit index, use next
            if not k_raw and (sid, k) in baseline:
                k = session_counter[sid]
        except (ValueError, TypeError) as e:
            issues.append(Issue("ERROR", f"timetable line {i}", f"malformed record ({e})"))
            continue
        if k >= len(ds.section_sessions(sid)):
            issues.append(Issue(
                "ERROR", f"timetable line {i}",
                f"session index {k} exceeds course sessions for {sid}"
            ))
            continue
        key = (sid, k)
        if key in baseline:
            issues.append(Issue("WARNING", f"timetable line {i}", f"overwriting baseline for {sid}#{k}"))
        baseline[key] = BaselineAssignment(
            section_id=sid, session_index=k, start_slot=start,
            room_id=rid, faculty_id=fid, mode=mode,
        )
        session_counter[sid] = max(session_counter[sid], k + 1)

    if added_rooms:
        issues.append(Issue("WARNING", path, f"registered {len(set(added_rooms))} rooms from timetable file"))
    if added_faculty:
        issues.append(Issue("WARNING", path, f"registered {len(set(added_faculty))} faculty from timetable file"))

    if any(i.severity == "ERROR" for i in issues):
        return ImportResult(None, issues)

    ds.baseline = baseline
    ds.meta = dict(ds.meta)
    ds.meta["baseline_count"] = len(baseline)
    ds.meta["baseline_source"] = os.path.basename(path)
    return ImportResult(ds, issues, summary={
        "baseline_assignments": len(baseline),
        "fixed": sum(1 for b in baseline.values() if b.mode == FIXED),
        "preferred": sum(1 for b in baseline.values() if b.mode == PREFERRED),
        "flexible": sum(1 for b in baseline.values() if b.mode == FLEXIBLE),
        "rooms_from_timetable": len(set(added_rooms)),
        "faculty_from_timetable": len(set(added_faculty)),
    })


def set_assignment_modes(ds: Dataset, mode: str, section_ids: list[str] | None = None) -> None:
    """Bulk-set baseline assignment modes. Does not invent baseline rows."""
    if mode not in ASSIGNMENT_MODES:
        raise ValueError(f"mode must be one of {sorted(ASSIGNMENT_MODES)}")
    targets = set(section_ids) if section_ids is not None else None
    updated = {}
    for key, ba in ds.baseline.items():
        if targets is None or ba.section_id in targets:
            updated[key] = BaselineAssignment(
                ba.section_id, ba.session_index, ba.start_slot, ba.room_id, ba.faculty_id, mode
            )
        else:
            updated[key] = ba
    ds.baseline = updated


def import_summary_text(result: ImportResult) -> str:
    lines = []
    for i in result.issues:
        lines.append(str(i))
    if result.summary:
        lines.append("Summary: " + ", ".join(f"{k}={v}" for k, v in result.summary.items()))
    return "\n".join(lines)
