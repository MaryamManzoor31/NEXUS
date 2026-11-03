"""Serialization utilities to convert NEXUS timetable models and schedules into JSON & CSV."""
from __future__ import annotations
import csv
import io
from collections import defaultdict
from nexus_core.models import Dataset, Schedule, DAYS, PERIODS, CLASS, LAB
from nexus_core.validator import validate, Report
from nexus_core.metrics import compute

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
PERIOD_TIMES = [
    ("09:00 - 10:00", "09:00", "10:00"),
    ("10:00 - 11:00", "10:00", "11:00"),
    ("11:15 - 12:15", "11:15", "12:15"),
    ("12:15 - 13:15", "12:15", "13:15"),
    ("14:00 - 15:00", "14:00", "15:00"),
    ("15:00 - 16:00", "15:00", "16:00"),
]

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
            "credits": c.credits,
            "sessions": [{"duration": s.duration, "room_type": s.room_type} for s in c.sessions],
        }

    sections_dict = {}
    for s in ds.sections.values():
        fid = sched.faculty.get(s.id, "")
        fname = faculty_dict[fid]["name"] if fid in faculty_dict else "Unassigned"
        c = ds.courses.get(s.course_id)
        sections_dict[s.id] = {
            "id": s.id,
            "course_id": s.course_id,
            "course_title": c.title if c else s.course_id,
            "category": c.category if c else "",
            "capacity": s.capacity,
            "faculty_id": fid,
            "faculty_name": fname,
            "hours": ds.section_hours(s.id),
        }

    students_dict = {}
    for st in ds.students.values():
        enrol = sched.enrolment.get(st.id, {})
        students_dict[st.id] = {
            "id": st.id,
            "programme": st.programme,
            "selections": list(st.selections),
            "enrolled": enrol,
            "placed_count": len(enrol),
            "total_selected": len(st.selections),
        }

    # Grids: 5 days x 6 periods = 30 slots
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
    for stid, cid in report.unplaced:
        c = ds.courses.get(cid)
        unplaced_list.append({
            "student_id": stid,
            "course_id": cid,
            "course_title": c.title if c else cid,
        })

    unscheduled_list = []
    for sid in report.unscheduled:
        sec = ds.sections.get(sid)
        cid = sec.course_id if sec else ""
        c = ds.courses.get(cid) if cid else None
        unscheduled_list.append({
            "section_id": sid,
            "course_id": cid,
            "course_title": c.title if c else cid,
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
                {"index": i, "label": f"Period {i+1}", "time": PERIOD_TIMES[i][0]}
                for i in range(PERIODS)
            ],
            "semester_filter": ds.meta.get("semester_filter", "all"),
            "source_file": ds.meta.get("source_file", ""),
        },
        "metrics": {
            "method": sched.method,
            "validator_status": report.status,
            "solver_status": sched.status,
            "stage_a_status": metrics.get("stage_a_status", sched.status),
            "stage_b_status": metrics.get("stage_b_status", "NOT_RUN"),
            "stage_b_status_reason": metrics.get("stage_b_status_reason"),
            "runtime_s": round(sched.runtime, 3),
            "scheduled_sections": metrics.get("scheduled_sections", f"{len(ds.sections)-len(report.unscheduled)}/{len(ds.sections)}"),
            "unplaced_selections": metrics.get("unplaced_selections", f"{len(report.unplaced)}"),
            "fully_scheduled_students_pct": metrics.get("fully_scheduled_students_pct", 0.0),
            "room_utilization_pct": metrics.get("room_utilization_pct", 0.0),
            "hard_violations": report.status != "VALID_COMPLETE" and len(report.violations),
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
            f"Period {item['period']+1}",
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
