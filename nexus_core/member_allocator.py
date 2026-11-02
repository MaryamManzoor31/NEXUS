"""M10 - Faculty Member Allocation Engine.
Allocates university faculty members to course sections based on:
1. Pinned / pre-assigned faculty from spreadsheet.
2. Departmental domain and course continuity.
3. Statutory teaching contact hour limits by academic rank (Prof: 12h, Assoc Prof: 14h, Asst Prof: 16h).
4. Balanced workload distribution across Core, PE, and Practical Lab sessions.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from .models import Dataset, Faculty, Section, LAB, CLASS


@dataclass
class AllocationResult:
    faculty_assignments: dict[str, str]    # sec_id -> faculty_id
    faculty_summary: list[dict]            # detailed workload & assignment list per faculty
    unassigned_sections: list[str]         # sections requiring adjunct/external staffing
    stats: dict                            # overall utilization metrics


def allocate_faculty_members(
    ds: Dataset,
    pre_assigned: dict[str, str] | None = None,
    raw_faculty_info: dict | None = None,
    allow_adjunct_pool: bool = True
) -> AllocationResult:
    """Allocate faculty members to all sections in the dataset.

    Args:
        ds: The canonical NEXUS Dataset.
        pre_assigned: Dict of {section_id: faculty_id} for already fixed assignments.
        raw_faculty_info: Optional metadata containing faculty ranks and departments.
        allow_adjunct_pool: If True, introduces adjunct pools if faculty capacity is exhausted.
    Returns:
        AllocationResult with final faculty mapping, workload summaries, and stats.
    """
    pre_assigned = pre_assigned or {}
    raw_faculty_info = raw_faculty_info or {}

    assigned = dict(pre_assigned)
    fac_load = defaultdict(int)
    fac_courses = defaultdict(set)
    fac_sections = defaultdict(list)

    # 1. Register pinned / pre-assigned allocations
    for sid, fid in pre_assigned.items():
        if sid in ds.sections and fid in ds.faculty:
            hours = ds.section_hours(sid)
            fac_load[fid] += hours
            fac_courses[fid].add(ds.sections[sid].course_id)
            fac_sections[fid].append(sid)

    # 2. Identify unassigned sections
    unassigned = [
        sec for sid, sec in ds.sections.items()
        if sid not in assigned or not assigned[sid]
    ]

    # Sort unassigned sections: prioritize lab sections (higher hours) then higher capacity
    unassigned.sort(key=lambda s: (
        -any(x.room_type == LAB for x in ds.section_sessions(s.id)),
        -ds.section_hours(s.id),
        s.id
    ))

    # Helper function to get rank weight
    def rank_info(fid: str) -> tuple[str, int]:
        f = ds.faculty.get(fid)
        raw = raw_faculty_info.get(fid, {})
        desig = raw.get('designation', 'Assistant Professor') if raw else 'Assistant Professor'
        max_h = f.max_hours if f else 16
        return desig, max_h

    # 3. Allocation loop
    still_unassigned = []
    adjunct_counter = 1

    for sec in unassigned:
        sec_hours = ds.section_hours(sec.id)
        cid = sec.course_id
        is_lab = any(x.room_type == LAB for x in ds.section_sessions(sec.id))

        # Find eligible faculty candidates
        candidates = []
        for fid, f in ds.faculty.items():
            current = fac_load[fid]
            if current + sec_hours <= f.max_hours:
                desig, max_h = rank_info(fid)
                score = 0

                # Priority A: Course continuity (already teaches another section of this course)
                if cid in fac_courses[fid]:
                    score += 50

                # Priority B: Qualified course match
                if cid in f.qualified:
                    score += 20

                # Priority C: Deficit incentive (faculty who need more hours to reach their quota)
                deficit = max_h - current
                score += deficit * 2

                # Priority D: Role-specific suitability
                # Labs: Assistant professors & lecturers often handle practicals
                if is_lab:
                    if 'assistant' in desig.lower() or 'lecturer' in desig.lower():
                        score += 15
                else:
                    # Advanced lectures: associate professors and professors
                    if 'professor' in desig.lower():
                        score += 10

                candidates.append((score, fid))

        if candidates:
            # Pick highest scoring candidate
            candidates.sort(key=lambda x: -x[0])
            best_fid = candidates[0][1]

            assigned[sec.id] = best_fid
            fac_load[best_fid] += sec_hours
            fac_courses[best_fid].add(cid)
            fac_sections[best_fid].append(sec.id)
        else:
            # Capacity full or no qualified faculty under max_hours limit
            if allow_adjunct_pool:
                # Assign to university Adjunct / Co-Faculty pool
                adjunct_id = f"FAC_ADJUNCT_{adjunct_counter:02d}"
                if adjunct_id not in ds.faculty:
                    ds.faculty[adjunct_id] = Faculty(
                        id=adjunct_id,
                        name=f"Adjunct Faculty / Co-Faculty {adjunct_counter}",
                        qualified=frozenset(ds.courses.keys()),
                        max_hours=16,
                        unavailable=frozenset()
                    )
                assigned[sec.id] = adjunct_id
                fac_load[adjunct_id] += sec_hours
                fac_courses[adjunct_id].add(cid)
                fac_sections[adjunct_id].append(sec.id)
                still_unassigned.append(sec.id)
                if fac_load[adjunct_id] >= 14:
                    adjunct_counter += 1
            else:
                still_unassigned.append(sec.id)

    # 4. Generate comprehensive faculty summary report
    faculty_summary = []
    total_teaching_hours = 0
    total_capacity_hours = 0

    for fid, f in ds.faculty.items():
        raw = raw_faculty_info.get(fid, {})
        desig = raw.get('designation', 'Faculty') if raw else 'Faculty'
        dept = raw.get('dept', 'CSE') if raw else 'CSE'
        assigned_h = fac_load[fid]
        sec_list = fac_sections[fid]

        total_teaching_hours += assigned_h
        total_capacity_hours += f.max_hours

        # Workload status categorization
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
        for sid in sec_list:
            sec_obj = ds.sections.get(sid)
            c_obj = ds.courses.get(sec_obj.course_id) if sec_obj else None
            sec_details.append({
                "section_id": sid,
                "course_id": sec_obj.course_id if sec_obj else "",
                "course_title": c_obj.title if c_obj else "",
                "hours": ds.section_hours(sid) if sid in ds.sections else 0,
                "is_lab": any(x.room_type == LAB for x in ds.section_sessions(sid)) if sid in ds.sections else False
            })

        faculty_summary.append({
            "id": fid,
            "name": f.name,
            "designation": desig,
            "dept": dept,
            "max_hours": f.max_hours,
            "assigned_hours": assigned_h,
            "utilization_pct": round((assigned_h / f.max_hours) * 100, 1) if f.max_hours > 0 else 0.0,
            "status": status,
            "status_badge": status_badge,
            "sections_count": len(sec_list),
            "sections": sec_details,
            "qualified_count": len(f.qualified)
        })

    # Sort faculty summary: active faculty with highest teaching load first
    faculty_summary.sort(key=lambda x: (-x["assigned_hours"], x["name"]))

    stats = {
        "total_sections": len(ds.sections),
        "pre_assigned_sections": len(pre_assigned),
        "newly_allocated_sections": len(unassigned) - len(still_unassigned),
        "adjunct_allocated_sections": len(still_unassigned),
        "active_faculty_count": sum(1 for f in faculty_summary if f["assigned_hours"] > 0),
        "total_faculty_count": len(ds.faculty),
        "total_teaching_hours": total_teaching_hours,
        "total_capacity_hours": total_capacity_hours,
        "overall_utilization_pct": round((total_teaching_hours / max(1, total_capacity_hours)) * 100, 1)
    }

    return AllocationResult(
        faculty_assignments=assigned,
        faculty_summary=faculty_summary,
        unassigned_sections=still_unassigned,
        stats=stats
    )
