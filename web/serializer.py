"""Serialization utilities to convert NEXUS timetable models and schedules into JSON & CSV."""
from __future__ import annotations
import csv
import io
import re
from collections import Counter, defaultdict
from nexus_core.models import (
    Dataset, Schedule, DAYS, PERIODS, SESSION_TIMES, CLASS, LAB,
    MORNING_SESSION, AFTERNOON_SESSION, EXTENDED_EARLY_SESSION, EXTENDED_LATE_SESSION,
)
from nexus_core.validator import validate, Report
from nexus_core.metrics import compute
from nexus_core.common import is_minor_or_elective

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

PERIOD_TIMES = [
    (
        f"{start} - {end}",
        start,
        end,
    )
    for start, end in SESSION_TIMES
]

STUDENT_SESSION_LABELS = {
    MORNING_SESSION: "Morning Session (8:00 AM-1:00 PM)",
    AFTERNOON_SESSION: "Afternoon Session (1:00 PM-6:00 PM)",
    EXTENDED_EARLY_SESSION: "Extended Session (8:00 AM-4:00 PM)",
    EXTENDED_LATE_SESSION: "Extended Session (10:00 AM-6:00 PM)",
}

CONSTRAINT_SPECS = [
    ("H1", "Faculty Clash", "Faculty teaches at most one session at any time", "PS, ITC"),
    ("H2", "Room Clash", "Room hosts at most one session at any time", "PS, ITC-2007"),
    ("H3", "Student Clash", "Student attends at most one session at any time", "PS, ITC-2007 T2"),
    ("H4", "Room Capacity", "Room capacity is >= section capacity & enrolment", "PS"),
    ("H5", "Room Type", "Room type matches requirement (Labs strictly in Labs)", "PS"),
    ("H6", "Faculty Qualification", "Faculty is qualified for the assigned course", "PS"),
    ("H7", "Availability", "Faculty and room availability restrictions respected", "PS"),
    ("H8", "Day Boundary", "Each session fits completely within the same day", "TD"),
    ("H9", "Complete Schedule", "Each section is fully placed or marked unscheduled", "TD"),
    ("H10", "Fixed Assignments", "Fixed baseline timetable assignments must be preserved", "PS O6 / real-data baseline"),
    ("H11", "Enrolment Integrity", "At most one section per course selected by student", "TD"),
    ("H12", "Section Capacity", "Student enrolment does not exceed section limit", "TD"),
    ("H13", "Resource Blocking", "Blocked/unavailable resources remain unused", "PS"),
    ("H14", "Faculty Workload", "Faculty weekly hours do not exceed max_hours limit", "TD"),
    ("H15", "Student Day Sessions", "Morning and afternoon days have at most five class hours; days requiring more must use an extended window with a protected lunch break between noon and 2 PM", "TD"),
    ("H16", "Semester Session Window", "Students stay in their selected morning/afternoon batch or its matching extended window; automatic mode assigns per student", "TD"),
    ("H17", "Student Offering Scope", "Core courses use a section offered to the student's department/programme/stream/batch/semester; minor and elective sections remain cross-program", "TD"),
    ("H18", "Student Waiting Time", "Waiting gaps between consecutive classes are at most 120 minutes; an extended-session lunch break is protected", "TD"),
]


def serialize_schedule(ds: Dataset, sched: Schedule, report: Report = None, metrics: dict = None) -> dict:
    if report is None:
        report = validate(ds, sched)
    if metrics is None:
        metrics = compute(ds, sched)

    violations_map = defaultdict(list)
    for rule, msg in report.violations:
        violations_map[rule].append(msg)

    # Constraints verification details
    constraints_list = []
    for cid, name, desc, src in CONSTRAINT_SPECS:
        v_count = len(violations_map.get(cid, []))
        if v_count == 0:
            status = "PASSED"
            badge = "success"
        else:
            status = "VIOLATED"
            badge = "danger"

        constraints_list.append({
            "id": cid,
            "name": name,
            "description": desc,
            "source": src,
            "status": status,
            "badge": badge,
            "violations_count": v_count,
            "messages": violations_map.get(cid, [])[:5],
        })

    # Faculty load calculation
    faculty_assigned_hours = defaultdict(int)
    for sid, fid in sched.faculty.items():
        if sid in ds.sections:
            faculty_assigned_hours[fid] += ds.section_hours(sid)

    # Build entities dictionary
    faculty_dict = {}
    for f in ds.faculty.values():
        faculty_dict[f.id] = {
            "id": f.id,
            "name": f.name,
            "max_hours": f.max_hours,
            "assigned_hours": faculty_assigned_hours[f.id],
            "qualified": sorted(list(f.qualified)),
            "unavailable": sorted(list(f.unavailable)),
        }

    rooms_dict = {}
    for r in ds.rooms.values():
        rooms_dict[r.id] = {
            "id": r.id,
            "type": r.type,
            "capacity": r.capacity,
            "unavailable": sorted(list(r.unavailable)),
        }

    courses_dict = {}
    for c in ds.courses.values():
        courses_dict[c.id] = {
            "id": c.id,
            "title": c.title,
            "category": c.category,
            "course_type": c.course_type or c.category,
            "department_id": c.department_id,
            "programme_id": c.programme_id,
            "stream": c.stream,
            "credits": c.credits,
            "sessions": [{"duration": s.duration, "room_type": s.room_type} for s in c.sessions],
        }

    sections_dict = {}
    baseline_modes_by_section = defaultdict(set)
    for assignment in ds.baseline.values():
        baseline_modes_by_section[assignment.section_id].add(assignment.mode)

    for s in ds.sections.values():
        fid = sched.faculty.get(s.id, "")
        fname = faculty_dict[fid]["name"] if fid in faculty_dict else "Unassigned"
        c = ds.courses.get(s.course_id)
        baseline_modes = baseline_modes_by_section.get(s.id, set())
        university_section_names = [
            re.sub(
                r"\s+", " ",
                re.sub(r"\s+(?:lab|practical)$", "", name.strip(), flags=re.IGNORECASE).strip()
            )
            for name in s.batch.split(",")
        ] if s.batch.strip() else [s.id]
        university_section_names = [name for name in university_section_names if name] or [s.id]
        university_section = university_section_names[0]
        semester = s.semester or (c.semester if c else "")
        sections_dict[s.id] = {
            "id": s.id,
            "course_id": s.course_id,
            "course_title": c.title if c else s.course_id,
            "category": c.category if c else "",
            "capacity": s.capacity,
            "semester": semester,
            "batch": s.batch,
            "university_section": university_section,
            "university_section_names": university_section_names,
            "university_section_key": f"{semester.casefold()}::{university_section.casefold()}",
            "stream": s.stream or (c.stream if c else ""),
            "programme": s.programme_id or (c.programme_id if c else ""),
            "faculty_id": fid,
            "faculty_name": fname,
            "hours": ds.section_hours(s.id),
            "has_baseline": bool(baseline_modes),
            "baseline_mode": next(iter(baseline_modes)) if len(baseline_modes) == 1 else ("mixed" if baseline_modes else ""),
            "scheduled": s.id not in report.unscheduled,
        }

    students_dict = {}
    for st in ds.students.values():
        enrol = sched.enrolment.get(st.id, {})
        students_dict[st.id] = {
            "id": st.id,
            "programme": st.programme,
            "department_id": st.department_id,
            "selections": list(st.selections),
            "enrolled": enrol,
            "section_by_course": {
                course_id: {
                    "section_id": section_id,
                    "university_section": sections_dict.get(section_id, {}).get("university_section", section_id),
                    "course_type": (ds.courses[course_id].course_type or ds.courses[course_id].category)
                    if course_id in ds.courses else "",
                }
                for course_id, section_id in enrol.items()
            },
            "minor_electives": [
                course_id for course_id in st.selections
                if course_id in ds.courses
                and is_minor_or_elective(ds.courses[course_id])
            ],
            "minor_elective_enrolments": {
                course_id: section_id
                for course_id, section_id in enrol.items()
                if course_id in ds.courses and is_minor_or_elective(ds.courses[course_id])
            },
            "placed_count": len(enrol),
            "total_selected": len(st.selections),
            "session_by_day": {
                DAY_NAMES[day]: STUDENT_SESSION_LABELS[mode]
                for day, mode in sched.student_categories.get(st.id, {}).items()
                if 0 <= day < len(DAY_NAMES) and mode in STUDENT_SESSION_LABELS
            },
        }

    # Grids: 5 days x 10 teaching sessions = 50 slots
    # by_section[sec_id] -> list of placement sessions
    # by_faculty[fac_id] -> list of placement sessions
    # by_room[room_id]   -> list of placement sessions
    # by_student[st_id]  -> list of placement sessions
    by_section = defaultdict(list)
    by_faculty = defaultdict(list)
    by_room = defaultdict(list)
    by_student = defaultdict(list)
    master_list = []

    # Map each section session placement
    sec_session_items = {}
    for (sid, k), (start_slot, rid) in sched.placement.items():
        if sid not in ds.sections:
            continue
        sec = ds.sections[sid]
        course = ds.courses.get(sec.course_id)
        specs = ds.section_sessions(sid)
        spec = specs[k] if k < len(specs) else None
        duration = spec.duration if spec else 1
        room_type = spec.room_type if spec else CLASS

        fid = sched.faculty.get(sid, "")
        fname = faculty_dict[fid]["name"] if fid in faculty_dict else fid

        day = start_slot // PERIODS
        period = start_slot % PERIODS
        day_name = DAY_NAMES[day] if 0 <= day < len(DAY_NAMES) else f"Day {day}"
        period_time = PERIOD_TIMES[period][0] if 0 <= period < len(PERIOD_TIMES) else f"P{period+1}"

        item = {
            "section_id": sid,
            "session_index": k,
            "course_id": sec.course_id,
            "course_title": course.title if course else sec.course_id,
            "category": course.category if course else "",
            "room_id": rid,
            "room_type": room_type,
            "faculty_id": fid,
            "faculty_name": fname,
            "start_slot": start_slot,
            "day": day,
            "day_name": day_name,
            "period": period,
            "period_time": period_time,
            "duration": duration,
            "is_lab": (room_type == LAB),
            "slots": list(range(start_slot, start_slot + duration)),
        }

        sec_session_items[(sid, k)] = item
        by_section[sid].append(item)
        if fid:
            by_faculty[fid].append(item)
        if rid:
            by_room[rid].append(item)
        master_list.append(item)

    # Student timetables
    for stid, st in ds.students.items():
        enrol = sched.enrolment.get(stid, {})
        for cid, sid in enrol.items():
            specs = ds.section_sessions(sid) if sid in ds.sections else ()
            for k in range(len(specs)):
                if (sid, k) in sec_session_items:
                    by_student[stid].append(sec_session_items[(sid, k)])

    # Sort master list by day and period
    master_list.sort(key=lambda x: (x["day"], x["period"], x["section_id"]))

    unplaced_list = []
    allocation_diagnostics = {
        (item["student_id"], item["course_id"]): item
        for item in sched.info.get("unplaced_choice_diagnostics", [])
    }
    for stid, cid in report.unplaced:
        c = ds.courses.get(cid)
        item = {
            "student_id": stid,
            "course_id": cid,
            "course_title": c.title if c else cid,
        }
        diagnostic = allocation_diagnostics.get((stid, cid))
        if diagnostic:
            item.update({
                "reason": diagnostic["reason"],
                "description": diagnostic["description"],
                "candidate_sections": diagnostic["candidate_sections"],
            })
        unplaced_list.append(item)
    unplaced_reason_counts = dict(Counter(
        item["reason"] for item in unplaced_list if item.get("reason")
    ))

    unscheduled_list = []
    for sid in report.unscheduled:
        sec = ds.sections.get(sid)
        cid = sec.course_id if sec else ""
        c = ds.courses.get(cid) if cid else None
        specs = ds.section_sessions(sid) if sec else ()
        qualified_faculty = [f.id for f in ds.faculty.values() if cid in f.qualified]
        rooms_by_session = [
            [r.id for r in ds.rooms.values() if r.type == spec.room_type and r.capacity >= sec.capacity]
            for spec in specs
        ]
        if not qualified_faculty:
            likely_blocker = "No qualified faculty is listed for this course."
        elif any(not room_ids for room_ids in rooms_by_session):
            likely_blocker = "At least one required session has no matching room with sufficient capacity."
        else:
            likely_blocker = (
                "No single cause is confirmed. Check time-slot conflicts, faculty workload, room availability, "
                "fixed baseline assignments, and the solver search limit."
            )
        unscheduled_list.append({
            "section_id": sid,
            "course_id": cid,
            "course_title": c.title if c else cid,
            "likely_blocker": likely_blocker,
            "qualified_faculty": qualified_faculty,
            "matching_rooms_by_session": rooms_by_session,
        })

    # Faculty summary and allocation stats
    faculty_summary = []
    total_teaching_hours = 0
    total_capacity_hours = 0
    fac_sections_map = defaultdict(list)
    for sid, fid in sched.faculty.items():
        if fid:
            fac_sections_map[fid].append(sid)

    for f in ds.faculty.values():
        assigned_h = faculty_assigned_hours[f.id]
        total_teaching_hours += assigned_h
        total_capacity_hours += f.max_hours

        # Infer designation
        name_lower = f.name.lower()
        if 'dr.' in name_lower or 'prof.' in name_lower:
            desig = "Professor" if f.max_hours <= 12 else ("Associate Professor" if f.max_hours <= 14 else "Assistant Professor")
        else:
            desig = "Assistant Professor"

        if assigned_h == 0:
            status = "AVAILABLE"
            status_badge = "neutral"
        elif assigned_h <= f.max_hours - 4:
            status = "UNDERLOADED"
            status_badge = "info"
        elif assigned_h <= f.max_hours:
            status = "OPTIMAL"
            status_badge = "success"
        else:
            status = "OVERLOADED"
            status_badge = "danger"

        sec_details = []
        for sid in fac_sections_map.get(f.id, []):
            sec_obj = ds.sections.get(sid)
            c_obj = ds.courses.get(sec_obj.course_id) if sec_obj else None
            sec_details.append({
                "section_id": sid,
                "course_id": sec_obj.course_id if sec_obj else "",
                "course_title": c_obj.title if c_obj else "",
                "hours": ds.section_hours(sid) if sid in ds.sections else 0
            })

        faculty_summary.append({
            "id": f.id,
            "name": f.name,
            "designation": desig,
            "max_hours": f.max_hours,
            "assigned_hours": assigned_h,
            "utilization_pct": round((assigned_h / f.max_hours) * 100, 1) if f.max_hours > 0 else 0.0,
            "status": status,
            "status_badge": status_badge,
            "sections_count": len(sec_details),
            "sections": sec_details,
            "qualified_count": len(f.qualified)
        })

    faculty_summary.sort(key=lambda x: (-x["assigned_hours"], x["name"]))

    allocation_stats = {
        "total_sections": len(ds.sections),
        "assigned_sections": sum(1 for sid in ds.sections if sid in sched.faculty and sched.faculty[sid]),
        "active_faculty_count": sum(1 for f in faculty_summary if f["assigned_hours"] > 0),
        "total_faculty_count": len(ds.faculty),
        "total_teaching_hours": total_teaching_hours,
        "total_capacity_hours": total_capacity_hours,
        "overall_utilization_pct": round((total_teaching_hours / max(1, total_capacity_hours)) * 100, 1)
    }

    return {
        "meta": {
            "dataset_name": ds.name,
            "synthetic": ds.synthetic,
            "total_courses": len(ds.courses),
            "total_sections": len(ds.sections),
            "total_faculty": len(ds.faculty),
            "total_rooms": len(ds.rooms),
            "total_students": len(ds.students),
            "total_slots": DAYS * PERIODS,
            "days": DAY_NAMES,
            "periods": [
                {"index": i, "label": f"Session {i+1}", "time": PERIOD_TIMES[i][0]}
                for i in range(PERIODS)
            ],
            "semester_filter": ds.meta.get("semester_filter", "all"),
            "semester_sessions": ds.meta.get("semester_sessions", {}),
            "source_file": ds.meta.get("source_file", ""),
            "student_data_mode": ds.meta.get("student_data_mode", "actual" if ds.students else "unavailable"),
            "student_data_note": ds.meta.get("student_data_note", ""),
            "capacity_basis": ds.meta.get("capacity_basis", "Imported from source data"),
            "availability_basis": ds.meta.get("availability_basis", "Imported from source data"),
            "original_timetable_loaded": bool(ds.baseline),
            "baseline_validation_note": ds.meta.get("baseline_validation_note", ""),
        },
        "metrics": {
            "method": sched.method,
            "validator_status": report.status,
            "solver_status": sched.status,
            "stage_a_status": metrics.get("stage_a_status", sched.status),
            "stage_a_objective": metrics.get("stage_a_objective"),
            "stage_a_best_bound": metrics.get("stage_a_best_bound"),
            "stage_a_branches": metrics.get("stage_a_branches"),
            "stage_a_conflicts": metrics.get("stage_a_conflicts"),
            "stage_a_time_s": metrics.get("stage_a_time_s"),
            "stage_b_status": metrics.get("stage_b_status", "NOT_RUN"),
            "stage_b_status_reason": metrics.get("stage_b_status_reason"),
            "stage_b_objective": metrics.get("stage_b_objective"),
            "stage_b_best_bound": metrics.get("stage_b_best_bound"),
            "stage_b_branches": metrics.get("stage_b_branches"),
            "stage_b_conflicts": metrics.get("stage_b_conflicts"),
            "stage_b_time_s": metrics.get("stage_b_time_s"),
            "time_budget_s": metrics.get("time_budget_s"),
            "complete_allocation_status": metrics.get("complete_allocation_status"),
            "complete_allocation_reason": metrics.get("complete_allocation_reason"),
            "runtime_s": round(sched.runtime, 3),
            "scheduled_sections": metrics.get("scheduled_sections", f"{len(ds.sections)-len(report.unscheduled)}/{len(ds.sections)}"),
            "unplaced_selections": metrics.get("unplaced_selections", f"{len(report.unplaced)}"),
            "placed_selections": metrics.get("placed_selections", 0),
            "total_selections": metrics.get("total_selections", 0),
            "fully_scheduled_students_pct": metrics.get("fully_scheduled_students_pct", 0.0),
            "room_utilization_pct": metrics.get("room_utilization_pct", 0.0),
            "hard_violations": report.status != "VALID_COMPLETE" and len(report.violations),
            "unplaced_reason_counts": unplaced_reason_counts,
            "faculty_load_std_h": metrics.get("faculty_load_std_h", 0.0),
        },
        "constraints": constraints_list,
        "allocation_stats": allocation_stats,
        "faculty_summary": faculty_summary,
        "entities": {
            "courses": courses_dict,
            "sections": sections_dict,
            "faculty": faculty_dict,
            "rooms": rooms_dict,
            "students": students_dict,
        },
        "grid_data": {
            "by_section": dict(by_section),
            "by_faculty": dict(by_faculty),
            "by_room": dict(by_room),
            "by_student": dict(by_student),
        },
        "master_list": master_list,
        "unplaced_selections": unplaced_list,
        "unscheduled_sections": unscheduled_list,
        "unplaced_selection_details": unplaced_list,
    }


def generate_timetable_csv(ds: Dataset, sched: Schedule) -> str:
    """Generate CSV string of the entire master timetable."""
    data = serialize_schedule(ds, sched)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Day", "Period", "Time Range", "Section", "Course Code",
        "Course Title", "Category", "Duration (Hrs)", "Room",
        "Room Type", "Faculty ID", "Faculty Name"
    ])
    for item in data["master_list"]:
        writer.writerow([
            item["day_name"],
            f"Session {item['period']+1}",
            item["period_time"],
            item["section_id"],
            item["course_id"],
            item["course_title"],
            item["category"],
            item["duration"],
            item["room_id"],
            item["room_type"],
            item["faculty_id"],
            item["faculty_name"],
        ])
    return output.getvalue()

