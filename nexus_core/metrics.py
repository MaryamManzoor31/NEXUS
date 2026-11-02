"""Metrics (partial M8). Formulas follow master plan 7.7; denominators are stated in each key."""
from __future__ import annotations
import statistics
from collections import defaultdict
from .models import *
from .validator import validate, section_slots


def compute(ds: Dataset, sched: Schedule):
    # Derive reported scores from the independently validated schedule.
    rep = validate(ds, sched)
    total_sel = sum(len(s.selections) for s in ds.students.values())
    unplaced = len(rep.unplaced)
    full = sum(1 for st in ds.students if not any(x[0] == st for x in rep.unplaced))
    placed_slots = defaultdict(set)
    load = defaultdict(int)
    for sid in ds.sections:
        if sid in rep.unscheduled:
            continue
        load[sched.faculty[sid]] += ds.section_hours(sid)
        for k, spec in enumerate(ds.section_sessions(sid)):
            s, r = sched.placement[(sid, k)]
            placed_slots[r] |= set(range(s, s + spec.duration))
    # Room utilization compares occupied room-periods with all available room-periods.
    avail = sum(N_SLOTS - len(r.unavailable) for r in ds.rooms.values())
    used = sum(len(v) for v in placed_slots.values())
    loads = [load.get(f, 0) for f in ds.faculty]
    return {
        "method": sched.method, "validator_status": rep.status, "solver_status": sched.status,
        "hard_violations": len(rep.violations), "violations_by_rule": rep.by_rule(),
        "scheduled_sections": f"{len(ds.sections) - len(rep.unscheduled)}/{len(ds.sections)}",
        "unplaced_selections": f"{unplaced}/{total_sel}",
        "fully_scheduled_students_pct": round(100 * full / len(ds.students), 1) if ds.students else None,
        "room_utilization_pct": round(100 * used / avail, 1) if avail else None,   # occupied / all available room-slots
        "faculty_load_range_h": (min(loads), max(loads)) if loads else None,
        "faculty_load_std_h": round(statistics.pstdev(loads), 2) if loads else None,
        "runtime_s": round(sched.runtime, 2),
    }
