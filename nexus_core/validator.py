"""M4 - independent validator. Sees ONLY the dataset and the schedule; never trusts a solver flag.
Status: INVALID | VALID_INCOMPLETE | VALID_COMPLETE."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from .models import *


@dataclass
class Report:
    status: str
    violations: list = field(default_factory=list)       # (rule, message)
    unscheduled: list = field(default_factory=list)
    unplaced: list = field(default_factory=list)         # (student, course)
    missing_info: list = field(default_factory=list)     # informational gaps

    def count(self, rule):
        return sum(1 for r, _ in self.violations if r == rule)

    def by_rule(self):
        d = defaultdict(int)
        for r, _ in self.violations:
            d[r] += 1
        return dict(d)

    def to_dict(self):
        return {
            "status": self.status,
            "hard_violations": len(self.violations),
            "violations_by_rule": self.by_rule(),
            "violations": [{"rule": r, "message": m} for r, m in self.violations],
            "unscheduled_sections": list(self.unscheduled),
            "unassigned_selections": [{"student": s, "course": c} for s, c in self.unplaced],
            "missing_info": list(self.missing_info),
        }


def section_slots(ds, sched, sec_id):
    """set of slots occupied by a scheduled section, or None if not (fully) scheduled"""
    n = len(ds.section_sessions(sec_id))
    if any((sec_id, k) not in sched.placement for k in range(n)):
        return None
    out = set()
    for k, spec in enumerate(ds.section_sessions(sec_id)):
        s = sched.placement[(sec_id, k)][0]
        out |= set(range(s, s + spec.duration))
    return out


def validate(ds: Dataset, sched: Schedule) -> Report:
    # Build violations from the dataset and schedule, without trusting solver status.
    V = []
    add = lambda rule, msg: V.append((rule, msg))
    # ---- well-formedness + H5/H8/H9 ---------------------------------------------------------------
    scheduled = set()
    for key in sched.placement:
        if key[0] not in ds.sections:
            add("MALFORMED", f"placement for unknown section {key[0]}")
    for sid, sec in ds.sections.items():
        specs = ds.section_sessions(sid)
        have = [k for k in range(len(specs)) if (sid, k) in sched.placement]
        if sid in sched.unscheduled:
            if have:
                add("H9", f"{sid} listed unscheduled but has placed sessions")
            continue
        if len(have) != len(specs):
            add("H9", f"{sid}: {len(have)}/{len(specs)} sessions placed and not listed as unscheduled")
            continue
        if sid not in sched.faculty or sched.faculty[sid] not in ds.faculty:
            add("MALFORMED", f"{sid} has no valid faculty"); continue
        scheduled.add(sid)
        for k, spec in enumerate(specs):
            start, rid = sched.placement[(sid, k)]
            if rid not in ds.rooms:
                add("MALFORMED", f"{sid}#{k} unknown room {rid}"); continue
            if not (0 <= start and start + spec.duration <= N_SLOTS) or start // PERIODS != (start + spec.duration - 1) // PERIODS:
                add("H8", f"{sid}#{k} start {start} with duration {spec.duration} leaves its day or the week")
            room = ds.rooms[rid]
            if room.type != spec.room_type:
                add("H5", f"{sid}#{k} needs {spec.room_type}, got {room.type} {rid}")
            if room.capacity < sec.capacity:
                add("H4", f"{sid}#{k} section capacity {sec.capacity} > room {rid} capacity {room.capacity}")
            if any(t in room.unavailable for t in range(start, start + spec.duration)):
                add("H7", f"{sid}#{k} uses room {rid} while unavailable")
    # ---- H1 / H2 / H6 / H7 / H14 ------------------------------------------------------------------
    fac_use, room_use, load = defaultdict(list), defaultdict(list), defaultdict(int)
    for sid in scheduled:
        f = ds.faculty[sched.faculty[sid]]
        if ds.sections[sid].course_id not in f.qualified:
            add("H6", f"{f.id} not qualified for {ds.sections[sid].course_id} ({sid})")
        load[f.id] += ds.section_hours(sid)
        for k, spec in enumerate(ds.section_sessions(sid)):
            start, rid = sched.placement[(sid, k)]
            for t in range(start, start + spec.duration):
                fac_use[(f.id, t)].append(f"{sid}#{k}")
                room_use[(rid, t)].append(f"{sid}#{k}")
                if t in f.unavailable:
                    add("H7", f"{sid}#{k} puts {f.id} in unavailable slot {t}")
    for (f, t), who in fac_use.items():
        if len(who) > 1:
            add("H1", f"faculty {f} double-booked in slot {t}: {who}")
    for (r, t), who in room_use.items():
        if len(who) > 1:
            add("H2", f"room {r} double-booked in slot {t}: {who}")
    for f, h in load.items():
        if h > ds.faculty[f].max_hours:
            add("H14", f"faculty {f} load {h}h > max {ds.faculty[f].max_hours}h")
    # Check that student choices match courses, avoid timetable clashes, and fit section capacity.
    count = defaultdict(int)
    occupied = {sid: section_slots(ds, sched, sid) for sid in scheduled}
    unplaced = []
    for stid, st in ds.students.items():
        enr = sched.enrolment.get(stid, {})
        for c in enr:
            if c not in st.selections:
                add("H11", f"{stid} enrolled in {c} which was not selected")
        chosen = []
        for c in st.selections:
            sid = enr.get(c)
            if sid is None:
                unplaced.append((stid, c)); continue
            if sid not in ds.sections or ds.sections[sid].course_id != c:
                add("H11", f"{stid}: section {sid} is not a section of {c}"); continue
            if sid not in scheduled:
                add("H11", f"{stid} enrolled in unscheduled section {sid}"); continue
            count[sid] += 1
            chosen.append(sid)
        for i, a in enumerate(chosen):
            for b in chosen[i + 1:]:
                ov = occupied[a] & occupied[b]
                if ov:
                    add("H3", f"student {stid}: {a} and {b} overlap in slots {sorted(ov)}")
    for sid, n in count.items():
        if n > ds.sections[sid].capacity:
            add("H12", f"{sid} has {n} students > capacity {ds.sections[sid].capacity}")
    # ---- H10 fixed baseline preservation ----------------------------------------------------------
    missing_info = []
    for (sid, k), ba in ds.baseline.items():
        if ba.mode != FIXED:
            continue
        if sid not in scheduled:
            add("H10", f"fixed assignment for {sid}#{k} is unscheduled")
            continue
        if (sid, k) not in sched.placement:
            add("H10", f"fixed assignment for {sid}#{k} missing from placement")
            continue
        st, rid = sched.placement[(sid, k)]
        if st != ba.start_slot:
            add("H10", f"{sid}#{k} start moved from fixed slot {ba.start_slot} to {st}")
        if rid != ba.room_id:
            add("H10", f"{sid}#{k} room changed from fixed {ba.room_id} to {rid}")
        if sched.faculty.get(sid) != ba.faculty_id:
            add("H10", f"{sid} faculty changed from fixed {ba.faculty_id} to {sched.faculty.get(sid)}")
    if not ds.students:
        missing_info.append("No students in dataset; course-allocation completeness cannot be assessed.")
    if ds.baseline and not any(ba.mode == FIXED for ba in ds.baseline.values()):
        missing_info.append("Baseline timetable present but no assignments marked fixed.")
    uns = [s for s in ds.sections if s not in scheduled]
    # Incomplete schedules are distinct from schedules that break hard rules.
    if V:
        status = "INVALID"
    elif uns or unplaced:
        status = "VALID_INCOMPLETE"
    else:
        status = "VALID_COMPLETE"
    return Report(status, V, uns, unplaced, missing_info)
