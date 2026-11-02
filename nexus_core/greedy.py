"""M5 - greedy two-phase baseline. Phase 1 places sections (most constrained first); phase 2 assigns students."""
from __future__ import annotations
import time
from collections import defaultdict
from .models import *
from .common import shared_counts, starts_for, sec_slots


def assign_students_greedy(ds: Dataset, sched: Schedule):
    # Track section capacity and occupied periods while assigning each student's choices.
    occ = {sid: sec_slots(ds, sched.placement, sid) for sid in ds.sections if sid not in sched.unscheduled}
    left = {sid: ds.sections[sid].capacity for sid in occ}
    by_course = defaultdict(list)
    for sid in occ:
        by_course[ds.sections[sid].course_id].append(sid)
    enrol = {}
    for stid, st in ds.students.items():
        mine, taken = {}, set()
        for c in sorted(st.selections, key=lambda c: len(by_course.get(c, []))):     # fewest options first
            for sid in sorted(by_course.get(c, []), key=lambda s: -left[s]):
                if left[sid] > 0 and not (occ[sid] & taken):
                    mine[c] = sid; left[sid] -= 1; taken |= occ[sid]; break
        enrol[stid] = mine
    sched.enrolment = enrol


def greedy(ds: Dataset, seed=329) -> Schedule:
    # Place difficult-to-staff sections first, then choose conflict-free resources.
    t0 = time.time()
    sh = shared_counts(ds)
    sched = Schedule(method="greedy", status="HEURISTIC")
    fac_busy, room_busy = defaultdict(set), defaultdict(set)
    load = defaultdict(int)
    course_slots = defaultdict(list)                       # course -> list of slot-sets already used
    n_qual = {c: sum(1 for f in ds.faculty.values() if c in f.qualified) for c in ds.courses}
    order = sorted(ds.sections.values(), key=lambda s: (
        n_qual[s.course_id],                               # scarce faculty first
        -any(x.room_type == LAB for x in ds.courses[s.course_id].sessions),
        -s.capacity, s.id))
    def conflict_cost(cid, slots):
        cost = 0
        for other, used in course_slots.items():
            w = sh.get((min(cid, other), max(cid, other)), 0)
            if w:
                cost += w * sum(1 for u in used if u & slots)
        return cost
    for sec in order:
        specs = ds.section_sessions(sec.id)
        hours = ds.section_hours(sec.id)
        facs = sorted((f for f in ds.faculty.values() if sec.course_id in f.qualified and load[f.id] + hours <= f.max_hours),
                      key=lambda f: load[f.id])
        done = False
        for f in facs:
            chosen, tmp_f, tmp_r = [], set(), defaultdict(set)
            ok = True
            for k, spec in enumerate(specs):
                best = None
                rooms = sorted((r for r in ds.rooms.values() if r.type == spec.room_type and r.capacity >= sec.capacity),
                               key=lambda r: r.capacity)
                for start in starts_for(spec.duration):
                    sl = set(range(start, start + spec.duration))
                    if sl & f.unavailable or sl & fac_busy[f.id] or sl & tmp_f:
                        continue
                    for r in rooms:
                        if sl & r.unavailable or sl & room_busy[r.id] or sl & tmp_r[r.id]:
                            continue
                        cost = conflict_cost(sec.course_id, sl | tmp_f)
                        if best is None or cost < best[0]:
                            best = (cost, start, r.id, sl)
                        break
                    if best and best[0] == 0:
                        break
                if best is None:
                    ok = False; break
                _, start, rid, sl = best
                chosen.append((k, start, rid)); tmp_f |= sl; tmp_r[rid] |= sl
            if ok:
                for k, start, rid in chosen:
                    sched.placement[(sec.id, k)] = (start, rid)
                    sl = set(range(start, start + specs[k].duration))
                    fac_busy[f.id] |= sl; room_busy[rid] |= sl
                sched.faculty[sec.id] = f.id; load[f.id] += hours
                course_slots[sec.course_id].append(tmp_f)
                done = True; break
        if not done:
            # Keep the schedule honest when no valid placement is available.
            sched.unscheduled.append(sec.id)
    assign_students_greedy(ds, sched)
    sched.runtime = time.time() - t0
    return sched
