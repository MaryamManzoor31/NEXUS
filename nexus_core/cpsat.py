"""M6 + M7 - CP-SAT engine. Stage A places sections (start, room, faculty); Stage B assigns students with times fixed.
Status strings are passed through unchanged: OPTIMAL / FEASIBLE / INFEASIBLE / UNKNOWN / MODEL_INVALID."""
from __future__ import annotations
import time
from collections import defaultdict
from ortools.sat.python import cp_model
from .models import *
from .common import shared_counts, starts_for, sec_slots

W_PLACED = 1000
# Soft change-cost weights (S8). Documented defaults; override via cpsat(..., w_move=...).
W_MOVE_DEFAULT = 5
W_ROOM_DEFAULT = 2
W_FAC_DEFAULT = 3


def _solver(limit, seed, workers, num_sections=0):
    # Apply consistent runtime and reproducibility settings to each solver stage.
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = limit
    s.parameters.random_seed = seed
    s.parameters.num_workers = workers if workers is not None else 1
    # For large datasets (e.g. real university scale with >60 sections) or tight limits,
    # prevent presolve probing & symmetry detection from exhausting the entire search time budget.
    if num_sections > 60 or limit <= 20:
        s.parameters.symmetry_level = 0
        s.parameters.cp_model_probing_level = 0
    return s


def _baseline_hint_schedule(ds: Dataset, hint: Schedule | None) -> Schedule | None:
    """Prefer an explicit hint; otherwise materialize Dataset.baseline as a warm-start schedule."""
    if hint is not None:
        return hint
    if ds.baseline:
        return ds.baseline_schedule()
    return None


def stage_a(ds: Dataset, limit=30, seed=329, workers=None, allow_unscheduled=True, top_pairs=100000,
            blocked_rooms=frozenset(), blocked_faculty=frozenset(), blocked_slots=frozenset(), prev=None,
            w_move=None, w_room=None, w_fac=None, hint=None):
    """Returns (status, Schedule-without-enrolment, extra info).

    Fixed baseline assignments (Dataset.baseline mode=fixed) are hard-constrained (H10).
    Preferred assignments contribute soft change costs when w_* > 0; flexible ones are hints only.
    """
    t0 = time.time()
    m = cp_model.CpModel()
    hint = _baseline_hint_schedule(ds, hint)
    if w_move is None:
        w_move = W_MOVE_DEFAULT if ds.baseline else 0
    if w_room is None:
        w_room = W_ROOM_DEFAULT if ds.baseline else 0
    if w_fac is None:
        w_fac = W_FAC_DEFAULT if ds.baseline else 0

    # Decision variables represent session times, chosen rooms/faculty, and section placement.
    start, rlit, flit, placed = {}, {}, {}, {}
    room_iv, fac_iv = defaultdict(list), defaultdict(list)
    change_terms = []
    fixed_applied = 0
    sec_ids = sorted(ds.sections)
    for sid in sec_ids:
        sec = ds.sections[sid]
        specs = ds.section_sessions(sid)
        placed[sid] = m.NewBoolVar(f"pl_{sid}") if allow_unscheduled else m.NewConstant(1)
        facs = [f for f in ds.faculty.values() if sec.course_id in f.qualified and f.id not in blocked_faculty]
        for f in facs:
            flit[sid, f.id] = m.NewBoolVar(f"f_{sid}_{f.id}")
        m.Add(sum(flit[sid, f.id] for f in facs) == placed[sid])          # empty sum -> forces unplaced / infeasible

        # Fixed faculty from any baseline row for this section (H10).
        fixed_fac = next(
            (ba.faculty_id for k in range(len(specs))
             if (ba := ds.baseline.get((sid, k))) and ba.mode == FIXED),
            None,
        )
        if fixed_fac is not None:
            if (sid, fixed_fac) in flit:
                m.Add(flit[sid, fixed_fac] == placed[sid])
                fixed_applied += 1
            else:
                # Fixed faculty is not a feasible candidate -> force unscheduled when allowed.
                if allow_unscheduled:
                    m.Add(placed[sid] == 0)
                else:
                    m.Add(placed[sid] == 1)
                    m.Add(sum(flit[sid, f.id] for f in facs) == 1)  # remains infeasible if empty

        for k, spec in enumerate(specs):
            ok = starts_for(spec.duration)
            start[sid, k] = m.NewIntVarFromDomain(cp_model.Domain.FromValues(ok), f"st_{sid}_{k}")
            rooms = [r for r in ds.rooms.values() if r.type == spec.room_type and r.capacity >= sec.capacity
                     and r.id not in blocked_rooms]
            for r in rooms:
                rlit[sid, k, r.id] = m.NewBoolVar(f"r_{sid}_{k}_{r.id}")
                room_iv[r.id].append(m.NewOptionalFixedSizeIntervalVar(start[sid, k], spec.duration, rlit[sid, k, r.id], ""))
                bad = set(r.unavailable) | set(blocked_slots)
                if bad:
                    allowed = [v for v in ok if not any(t in bad for t in range(v, v + spec.duration))]
                    m.AddLinearExpressionInDomain(start[sid, k], cp_model.Domain.FromValues(allowed)).OnlyEnforceIf(rlit[sid, k, r.id])
            m.Add(sum(rlit[sid, k, r.id] for r in rooms) == placed[sid])
            for f in facs:
                bad = set(f.unavailable) | set(blocked_slots)
                if bad:
                    allowed = [v for v in ok if not any(t in bad for t in range(v, v + spec.duration))]
                    m.AddLinearExpressionInDomain(start[sid, k], cp_model.Domain.FromValues(allowed)).OnlyEnforceIf(flit[sid, f.id])
                fac_iv[f.id].append(m.NewOptionalFixedSizeIntervalVar(start[sid, k], spec.duration, flit[sid, f.id], ""))

            ba = ds.baseline.get((sid, k))
            if ba is None:
                continue
            if ba.mode == FIXED:
                # Hard-lock time and room when the resources remain legal candidates.
                if ba.start_slot in ok:
                    m.Add(start[sid, k] == ba.start_slot).OnlyEnforceIf(placed[sid])
                    fixed_applied += 1
                if (sid, k, ba.room_id) in rlit:
                    m.Add(rlit[sid, k, ba.room_id] == placed[sid])
                    fixed_applied += 1
                elif allow_unscheduled:
                    m.Add(placed[sid] == 0)
            elif ba.mode == PREFERRED and (w_move or w_room or w_fac):
                # Soft minimal-change penalties for preferred baseline rows (S8).
                if w_move and ba.start_slot in ok:
                    same_t = m.NewBoolVar(f"same_t_{sid}_{k}")
                    m.Add(start[sid, k] == ba.start_slot).OnlyEnforceIf(same_t)
                    m.Add(start[sid, k] != ba.start_slot).OnlyEnforceIf(same_t.Not())
                    change_terms.append(w_move * (1 - same_t))
                if w_room and (sid, k, ba.room_id) in rlit:
                    change_terms.append(w_room * (1 - rlit[sid, k, ba.room_id]))
                if w_fac and (sid, ba.faculty_id) in flit:
                    change_terms.append(w_fac * (1 - flit[sid, ba.faculty_id]))

    for r in room_iv:
        m.AddNoOverlap(room_iv[r])                                          # H2
    for f in fac_iv:
        m.AddNoOverlap(fac_iv[f])                                           # H1
    loads, maxload = {}, m.NewIntVar(0, 60, "maxload")
    for f in ds.faculty.values():                                           # H14 workload limit + S3 balance
        terms = [(flit[s, f.id], ds.section_hours(s)) for s in sec_ids if (s, f.id) in flit]
        if not terms:
            continue
        loads[f.id] = sum(l * h for l, h in terms)
        m.Add(loads[f.id] <= f.max_hours)
        m.Add(maxload >= loads[f.id])
    # S2: soft penalty for overlapping sessions of courses that share many students (guides Stage A)
    sh = shared_counts(ds)
    # Cap pair explosion for real multi-section institutional datasets
    max_p = min(top_pairs, 50) if len(sec_ids) > 60 else top_pairs
    pairs = sorted(sh.items(), key=lambda kv: -kv[1])[:max_p]
    conf = []
    MAX_CONF_TERMS = 500 if len(sec_ids) > 60 else 100000
    for (c1, c2), w in pairs:
        for s1 in (s for s in sec_ids if ds.sections[s].course_id == c1):
            for s2 in (s for s in sec_ids if ds.sections[s].course_id == c2):
                for k1, sp1 in enumerate(ds.section_sessions(s1)):
                    for k2, sp2 in enumerate(ds.section_sessions(s2)):
                        a, b = start[s1, k1], start[s2, k2]
                        l1, l2, ov = m.NewBoolVar(""), m.NewBoolVar(""), m.NewBoolVar("")
                        m.Add(a >= b + sp2.duration).OnlyEnforceIf(l1.Not())   # l1 false => a starts after b ends
                        m.Add(b >= a + sp1.duration).OnlyEnforceIf(l2.Not())
                        m.Add(ov >= l1 + l2 - 1)
                        conf.append((w, ov))
                        if hint is not None and s1 not in hint.unscheduled and s2 not in hint.unscheduled:
                            if (s1, k1) in hint.placement and (s2, k2) in hint.placement:
                                t1 = hint.placement[(s1, k1)][0]
                                t2 = hint.placement[(s2, k2)][0]
                                v1 = int(t1 < t2 + sp2.duration)
                                v2 = int(t2 < t1 + sp1.duration)
                                m.AddHint(l1, v1)
                                m.AddHint(l2, v2)
                                m.AddHint(ov, int(v1 and v2))
                        if len(conf) >= MAX_CONF_TERMS:
                            break
                    if len(conf) >= MAX_CONF_TERMS:
                        break
                if len(conf) >= MAX_CONF_TERMS:
                    break
            if len(conf) >= MAX_CONF_TERMS:
                break
        if len(conf) >= MAX_CONF_TERMS:
            break

    if hint is not None:                                                    # warm start from baseline / prior schedule
        fac_loads = defaultdict(int)
        for sid in sec_ids:
            is_placed = int(sid not in hint.unscheduled and (sid, 0) in hint.placement)
            if allow_unscheduled:
                m.AddHint(placed[sid], is_placed)

            h_fac = hint.faculty.get(sid)
            for (s_, f_), l in flit.items():
                if s_ == sid:
                    m.AddHint(l, int(is_placed and h_fac == f_))
            if is_placed and h_fac:
                fac_loads[h_fac] += ds.section_hours(sid)

            for k, spec in enumerate(ds.section_sessions(sid)):
                ok = starts_for(spec.duration)
                if is_placed and (sid, k) in hint.placement:
                    st_val, r_val = hint.placement[(sid, k)]
                    m.AddHint(start[sid, k], st_val)
                    for (s_, k_, r_), l in rlit.items():
                        if s_ == sid and k_ == k:
                            m.AddHint(l, int(r_val == r_))
                else:
                    m.AddHint(start[sid, k], ok[0] if ok else 0)
                    for (s_, k_, r_), l in rlit.items():
                        if s_ == sid and k_ == k:
                            m.AddHint(l, 0)

        max_l = max(fac_loads.values()) if fac_loads else 0
        m.AddHint(maxload, max_l)

    obj = sum(W_PLACED * (1 - placed[s]) for s in sec_ids) if allow_unscheduled else 0
    # Prefer placing sections, then reduce student conflicts, peak load, and unnecessary baseline changes.
    obj = obj + sum(w * ov for w, ov in conf) + maxload + sum(change_terms)
    m.Minimize(obj)
    solver = _solver(limit, seed, workers, num_sections=len(sec_ids))
    st = solver.Solve(m)
    name = solver.StatusName(st)
    sched = Schedule(method="cpsat", status=name)
    info = {
        "n_conflict_terms": len(conf),
        "wall_a": solver.WallTime(),
        "fixed_constraints_applied": fixed_applied,
        "change_cost_terms": len(change_terms),
        "w_move": w_move, "w_room": w_room, "w_fac": w_fac,
    }
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        info["objective"] = solver.ObjectiveValue(); info["best_bound"] = solver.BestObjectiveBound()
        for sid in sec_ids:
            if not solver.Value(placed[sid]):
                sched.unscheduled.append(sid); continue
            for k in range(len(ds.section_sessions(sid))):
                rid = next(r for (s, kk, r), l in rlit.items() if s == sid and kk == k and solver.Value(l))
                sched.placement[(sid, k)] = (solver.Value(start[sid, k]), rid)
            sched.faculty[sid] = next(f for (s, f), l in flit.items() if s == sid and solver.Value(l))
    else:                                                                   # never report a hint as a solver-produced schedule
        sched.unscheduled = list(sec_ids)
    sched.runtime = time.time() - t0
    return name, sched, info


def stage_b(ds: Dataset, sched: Schedule, limit=30, seed=329, workers=None):
    """Student sectioning with times fixed: maximise placed selections. Mutates sched.enrolment."""
    t0 = time.time()
    # Times are fixed from Stage A; this stage only chooses student-to-section assignments.
    occ = {sid: sec_slots(ds, sched.placement, sid) for sid in ds.sections if sid not in sched.unscheduled}
    by_course = defaultdict(list)
    for sid in occ:
        by_course[ds.sections[sid].course_id].append(sid)
    m, a = cp_model.CpModel(), {}
    for stid, st in ds.students.items():
        mine = []
        for c in st.selections:
            opts = by_course.get(c, [])
            for s in opts:
                a[stid, s] = m.NewBoolVar("")
            if opts:
                m.Add(sum(a[stid, s] for s in opts) <= 1)                    # H11
            mine += opts
        for i, s1 in enumerate(mine):
            for s2 in mine[i + 1:]:
                if occ[s1] & occ[s2]:
                    m.Add(a[stid, s1] + a[stid, s2] <= 1)                    # H3
    per_sec = defaultdict(list)
    for (stid, s), v in a.items():
        per_sec[s].append(v)
    for s, vs in per_sec.items():
        m.Add(sum(vs) <= ds.sections[s].capacity)                            # H12
    m.Maximize(sum(a.values()))
    solver = _solver(limit, seed, workers, num_sections=len(ds.sections))
    st = solver.Solve(m)
    name = solver.StatusName(st)
    enrol = {stid: {} for stid in ds.students}
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (stid, s), v in a.items():
            if solver.Value(v):
                enrol[stid][ds.sections[s].course_id] = s
    sched.enrolment = enrol
    return name, time.time() - t0


def cpsat(ds: Dataset, limit_a=30, limit_b=30, seed=329, workers=None, **kw) -> Schedule:
    t0 = time.time()
    name, sched, info = stage_a(ds, limit=limit_a, seed=seed, workers=workers, **kw)
    sched.info.update(info)
    if name in ("OPTIMAL", "FEASIBLE"):
        nb, _ = stage_b(ds, sched, limit=limit_b, seed=seed, workers=workers)
        sched.info["status_b"] = nb
        if nb not in ("OPTIMAL", "FEASIBLE"):
            sched.info["status_b_reason"] = f"Stage B ended with {nb}; student selections may remain unassigned."
    else:
        sched.info["status_b"] = "NOT_RUN"
        sched.info["status_b_reason"] = f"Stage A ended with {name}; no student allocation was attempted."
    sched.status = name
    sched.runtime = time.time() - t0
    return sched
