"""M6 + M7 - CP-SAT engine. Stage A places sections (start, room, faculty); Stage B assigns students with times fixed.
Status strings are passed through unchanged: OPTIMAL / FEASIBLE / INFEASIBLE / UNKNOWN / MODEL_INVALID."""
from __future__ import annotations
import time
from collections import defaultdict
from ortools.sat.python import cp_model
from .models import *
from .common import (
    EXTENDED_SESSIONS,
    LUNCH_SLOTS,
    STUDENT_DAY_SESSIONS,
    allowed_student_day_sessions,
    semester_session_starts,
    shared_counts,
    student_section_options,
    starts_for,
    sec_slots,
)

# Soft change-cost weights (S8). Documented defaults; override via cpsat(..., w_move=...).
W_MOVE_DEFAULT = 5
W_ROOM_DEFAULT = 2
W_FAC_DEFAULT = 3
W_EARLY_START = 100
W_ROOM_CONTINUITY = 2
W_FACULTY_CONSECUTIVE = 1
MAX_TOTAL_SOLVE_SECONDS = 90.0
DEFAULT_TOTAL_SOLVE_SECONDS = 30.0


def _solver(limit, seed, workers, num_sections=0):
    # Apply consistent runtime and reproducibility settings to each solver stage.
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = limit
    s.parameters.random_seed = seed
    # A single worker keeps fixed-seed runs reproducible; callers can opt into
    # parallel search explicitly with the workers argument.
    s.parameters.num_workers = workers if workers is not None else (4 if num_sections > 60 else 1)
    # For large datasets (e.g. real university scale with >60 sections) or tight limits,
    # prevent presolve probing & symmetry detection from exhausting the entire search time budget.
    if num_sections > 60 or limit <= 20:
        s.parameters.symmetry_level = 0
        s.parameters.cp_model_probing_level = 0
    return s


def _baseline_hint_schedule(ds: Dataset, hint: Schedule | None) -> Schedule | None:
    """Use an explicit CP-SAT hint or materialize the supplied baseline."""
    if hint is not None:
        return hint
    return ds.baseline_schedule() if ds.baseline else None


def _hint_respects_semester_sessions(ds: Dataset, hint: Schedule) -> bool:
    """Reject a CP-SAT warm start whose baseline starts violate current windows."""
    for sid, section in ds.sections.items():
        mode = ds.meta.get("semester_sessions", {}).get(str(section.semester).strip())
        if not mode:
            continue
        for index, spec in enumerate(ds.section_sessions(sid)):
            placement = hint.placement.get((sid, index))
            if placement is None:
                continue
            legal_starts = semester_session_starts(
                section.semester, mode, starts_for(spec.duration), spec.duration
            )
            if placement[0] not in legal_starts:
                return False
    return True


def stage_a(ds: Dataset, limit=30, seed=329, workers=None, allow_unscheduled=True, top_pairs=100000,
            blocked_rooms=frozenset(), blocked_faculty=frozenset(), blocked_slots=frozenset(),
            w_move=None, w_room=None, w_fac=None, hint=None, priority_pairs=(), deadline=None):
    """Returns (status, Schedule-without-enrolment, extra info).

    Fixed baseline assignments (Dataset.baseline mode=fixed) are hard-constrained (H10).
    Preferred assignments contribute soft change costs when w_* > 0; flexible ones are hints only.
    """
    t0 = time.time()
    m = cp_model.CpModel()
    hint = _baseline_hint_schedule(ds, hint)
    if hint is not None and not _hint_respects_semester_sessions(ds, hint):
        hint = None
    if w_move is None:
        w_move = W_MOVE_DEFAULT if ds.baseline else 0
    if w_room is None:
        w_room = W_ROOM_DEFAULT if ds.baseline else 0
    if w_fac is None:
        w_fac = W_FAC_DEFAULT if ds.baseline else 0
    if len(ds.sections) > 30:
        # This soft tie-breaker creates several reified booleans for every
        # candidate faculty/session pair and dominates model-build time. Keep
        # resource, qualification, workload and student-conflict constraints;
        # simply omit the optional consecutive-teaching preference at scale.
        consecutive_limit = 0
    else:
        consecutive_limit = 10000

    # Decision variables represent session times, chosen rooms/faculty, and section placement.
    start, rlit, flit, placed, session_day = {}, {}, {}, {}, {}
    room_iv, fac_iv = defaultdict(list), defaultdict(list)
    change_terms = []
    change_cost_bound = 0
    room_continuity_terms = []
    time_preference_terms = []
    fixed_applied = 0
    sec_ids = sorted(ds.sections)
    for sid in sec_ids:
        if deadline is not None and time.monotonic() >= deadline:
            sched = Schedule(method="cpsat", status="UNKNOWN", unscheduled=list(sec_ids))
            return "UNKNOWN", sched, {
                "n_conflict_terms": 0, "n_gap_terms": 0,
                "n_room_continuity_terms": 0, "n_faculty_consecutive_terms": 0,
                "wall_a": time.monotonic() - t0, "fixed_constraints_applied": fixed_applied,
                "change_cost_terms": len(change_terms), "w_move": w_move,
                "w_room": w_room, "w_fac": w_fac, "budget_expired_during_model_build": True,
            }
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
            session_day[sid, k] = m.NewIntVar(0, DAYS - 1, f"day_{sid}_{k}")
            m.AddDivisionEquality(session_day[sid, k], start[sid, k], PERIODS)
            semester_mode = ds.meta.get("semester_sessions", {}).get(str(sec.semester).strip())
            period = m.NewIntVar(0, PERIODS - 1, f"period_{sid}_{k}")
            m.AddModuloEquality(period, start[sid, k], PERIODS)
            if semester_mode == AFTERNOON_SESSION:
                distance = m.NewIntVar(0, PERIODS - 1, f"start_distance_{sid}_{k}")
                m.AddAbsEquality(distance, period - 5)
            else:
                distance = period
            # Prefer an 08:00 start for automatic/morning schedules and a 13:10
            # start for afternoon schedules, without forcing it when resources or
            # student-conflict constraints require another period.
            time_preference_terms.append(W_EARLY_START * distance)
            if semester_mode:
                allowed_starts = semester_session_starts(sec.semester, semester_mode, ok, spec.duration)
                if allowed_starts:
                    m.AddLinearExpressionInDomain(
                        start[sid, k], cp_model.Domain.FromValues(allowed_starts)
                    ).OnlyEnforceIf(placed[sid])
                else:
                    m.Add(placed[sid] == 0)
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
                    change_cost_bound += max(0, w_move)
                if w_room and (sid, k, ba.room_id) in rlit:
                    change_terms.append(w_room * (1 - rlit[sid, k, ba.room_id]))
                    change_cost_bound += max(0, w_room)
                if w_fac and (sid, ba.faculty_id) in flit:
                    change_terms.append(w_fac * (1 - flit[sid, ba.faculty_id]))
                    change_cost_bound += max(0, w_fac)

        # Prefer reusing one room for successive meetings of the same section
        # when both sessions have the same room type and a room can host both.
        for k in range(len(specs) - 1):
            if specs[k].room_type != specs[k + 1].room_type:
                continue
            common_rooms = sorted(
                rid for rid in ds.rooms
                if (sid, k, rid) in rlit and (sid, k + 1, rid) in rlit
            )
            if not common_rooms:
                continue
            same_room_terms = []
            for rid in common_rooms:
                both = m.NewBoolVar(f"same_room_{sid}_{k}_{rid}")
                m.Add(both <= rlit[sid, k, rid])
                m.Add(both <= rlit[sid, k + 1, rid])
                m.Add(both >= rlit[sid, k, rid] + rlit[sid, k + 1, rid] - 1)
                same_room_terms.append(both)
            same_room = m.NewBoolVar(f"room_reused_{sid}_{k}")
            m.Add(same_room == sum(same_room_terms))
            room_continuity_terms.append(
                W_ROOM_CONTINUITY * (placed[sid] - same_room)
            )

    for r in room_iv:
        m.AddNoOverlap(room_iv[r])                                          # H2
    for f in fac_iv:
        m.AddNoOverlap(fac_iv[f])                                           # H1

    # Mildly discourage one faculty member from teaching back-to-back sessions.
    # This is soft, so unavoidable teaching blocks remain schedulable.
    faculty_sessions = defaultdict(list)
    for sid, fid in flit:
        for k in range(len(ds.section_sessions(sid))):
            faculty_sessions[fid].append((sid, k))
    faculty_consecutive_terms = []
    faculty_ids = sorted(faculty_sessions)
    # Give every candidate faculty a share of the large-instance sample. A single
    # global early break would otherwise penalize only the first faculty IDs.
    consecutive_budget = max(consecutive_limit, len(faculty_ids) if consecutive_limit else 0)
    base_quota, extra_quota = divmod(consecutive_budget, max(1, len(faculty_ids)))
    for faculty_index, fid in enumerate(faculty_ids):
        if deadline is not None and time.monotonic() >= deadline:
            sched = Schedule(method="cpsat", status="UNKNOWN", unscheduled=list(sec_ids))
            return "UNKNOWN", sched, {
                "n_conflict_terms": 0, "n_gap_terms": 0,
                "n_room_continuity_terms": len(room_continuity_terms),
                "n_faculty_consecutive_terms": len(faculty_consecutive_terms),
                "wall_a": time.monotonic() - t0, "fixed_constraints_applied": fixed_applied,
                "change_cost_terms": len(change_terms), "w_move": w_move,
                "w_room": w_room, "w_fac": w_fac, "budget_expired_during_model_build": True,
            }
        candidates = faculty_sessions[fid]
        quota = base_quota + int(faculty_index < extra_quota)
        made_for_faculty = 0
        for i, (sid1, k1) in enumerate(candidates):
            # Pair opposite ends so a faculty member's bounded sample spans
            # their candidate sessions, including sessions within one section.
            for j in range(len(candidates) - 1, i, -1):
                sid2, k2 = candidates[j]
                sp1 = ds.section_sessions(sid1)[k1]
                sp2 = ds.section_sessions(sid2)[k2]
                same_faculty = m.NewBoolVar("")
                f1, f2 = flit[sid1, fid], flit[sid2, fid]
                m.Add(same_faculty <= f1)
                m.Add(same_faculty <= f2)
                m.Add(same_faculty >= f1 + f2 - 1)
                forward = m.NewBoolVar("")
                backward = m.NewBoolVar("")
                m.Add(start[sid2, k2] == start[sid1, k1] + sp1.duration).OnlyEnforceIf(forward)
                m.Add(start[sid2, k2] != start[sid1, k1] + sp1.duration).OnlyEnforceIf(forward.Not())
                m.Add(start[sid1, k1] == start[sid2, k2] + sp2.duration).OnlyEnforceIf(backward)
                m.Add(start[sid1, k1] != start[sid2, k2] + sp2.duration).OnlyEnforceIf(backward.Not())
                consecutive_forward = m.NewBoolVar("")
                consecutive_backward = m.NewBoolVar("")
                m.Add(consecutive_forward <= same_faculty)
                m.Add(consecutive_forward <= forward)
                m.Add(consecutive_forward >= same_faculty + forward - 1)
                m.Add(consecutive_backward <= same_faculty)
                m.Add(consecutive_backward <= backward)
                m.Add(consecutive_backward >= same_faculty + backward - 1)
                consecutive = m.NewBoolVar("")
                m.AddMaxEquality(consecutive, [consecutive_forward, consecutive_backward])
                faculty_consecutive_terms.append(W_FACULTY_CONSECUTIVE * consecutive)
                made_for_faculty += 1
                if made_for_faculty >= quota:
                    break
            if made_for_faculty >= quota:
                break
    max_possible_load = sum(ds.section_hours(sid) for sid in sec_ids)
    loads, maxload = {}, m.NewIntVar(0, max_possible_load, "maxload")
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
    pairs = list(priority_pairs) + sorted(sh.items(), key=lambda kv: -kv[1])[:max_p]
    conf = []
    gap_terms = []
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
                        # A clash is more harmful than any single gap, so prioritize
                        # avoiding overlap before packing non-conflicting classes.
                        conf.append((PERIODS * w, ov))

                        if len(gap_terms) < MAX_CONF_TERMS:
                            same_day = m.NewBoolVar("")
                            m.Add(session_day[s1, k1] == session_day[s2, k2]).OnlyEnforceIf(same_day)
                            m.Add(session_day[s1, k1] != session_day[s2, k2]).OnlyEnforceIf(same_day.Not())
                            active_pair = m.NewBoolVar("")
                            m.Add(active_pair <= placed[s1])
                            m.Add(active_pair <= placed[s2])
                            m.Add(active_pair >= placed[s1] + placed[s2] - 1)
                            gap = m.NewIntVar(0, PERIODS - 1, "")
                            m.Add(gap == a - (b + sp2.duration)).OnlyEnforceIf(
                                [active_pair, same_day, l1.Not()]
                            )
                            m.Add(gap == b - (a + sp1.duration)).OnlyEnforceIf(
                                [active_pair, same_day, l2.Not()]
                            )
                            m.Add(gap == 0).OnlyEnforceIf(
                                [active_pair, same_day, l1, l2]
                            )
                            m.Add(gap == 0).OnlyEnforceIf(same_day.Not())
                            m.Add(gap == 0).OnlyEnforceIf(active_pair.Not())

                            # Credit one actually-free midday period as required lunch,
                            # so the gap objective does not treat lunch as idle time.
                            lunch_gap_slots = []
                            for lunch_period in LUNCH_SLOTS:
                                after_b = m.NewBoolVar("")
                                m.Add(after_b <= active_pair)
                                m.Add(after_b <= same_day)
                                m.Add(after_b + l1 <= 1)
                                m.Add(b + sp2.duration <= lunch_period).OnlyEnforceIf(after_b)
                                m.Add(a >= lunch_period + 1).OnlyEnforceIf(after_b)

                                after_a = m.NewBoolVar("")
                                m.Add(after_a <= active_pair)
                                m.Add(after_a <= same_day)
                                m.Add(after_a + l2 <= 1)
                                m.Add(a + sp1.duration <= lunch_period).OnlyEnforceIf(after_a)
                                m.Add(b >= lunch_period + 1).OnlyEnforceIf(after_a)
                                lunch_gap_slots.extend((after_b, after_a))
                            lunch_credit = m.NewBoolVar("")
                            m.AddMaxEquality(lunch_credit, lunch_gap_slots)
                            necessary_gap = m.NewIntVar(0, PERIODS - 1, "")
                            m.Add(necessary_gap == gap - lunch_credit)
                            gap_terms.append((w, necessary_gap))
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

    time_preference_bound = W_EARLY_START * (PERIODS - 1) * len(start)
    gap_cost_bound = sum(w * (PERIODS - 1) for w, _ in gap_terms)
    room_continuity_bound = W_ROOM_CONTINUITY * len(room_continuity_terms)
    faculty_consecutive_bound = W_FACULTY_CONSECUTIVE * len(faculty_consecutive_terms)
    placement_weight = (
        sum(w for w, _ in conf) + gap_cost_bound + change_cost_bound
        + time_preference_bound + room_continuity_bound
        + faculty_consecutive_bound + max_possible_load + 1
    )
    obj = sum(placement_weight * (1 - placed[s]) for s in sec_ids) if allow_unscheduled else 0
    # Prefer placing sections, then reduce student conflicts, peak load, and unnecessary baseline changes.
    obj = (
        obj
        + sum(w * ov for w, ov in conf)
        + sum(w * gap for w, gap in gap_terms)
        + maxload + sum(change_terms) + sum(time_preference_terms)
        + sum(room_continuity_terms) + sum(faculty_consecutive_terms)
    )
    m.Minimize(obj)
    solver_limit = float(limit)
    if deadline is not None:
        solver_limit = min(solver_limit, deadline - time.monotonic())
    if solver_limit <= 0:
        sched = Schedule(method="cpsat", status="UNKNOWN", unscheduled=list(sec_ids))
        info = {
            "n_conflict_terms": len(conf), "n_gap_terms": len(gap_terms),
            "n_room_continuity_terms": len(room_continuity_terms),
            "n_faculty_consecutive_terms": len(faculty_consecutive_terms),
            "wall_a": 0.0, "fixed_constraints_applied": fixed_applied,
            "change_cost_terms": len(change_terms), "w_move": w_move,
            "w_room": w_room, "w_fac": w_fac,
        }
        return "UNKNOWN", sched, info
    solver = _solver(solver_limit, seed, workers, num_sections=len(sec_ids))
    st = solver.Solve(m)
    name = solver.StatusName(st)
    sched = Schedule(method="cpsat", status=name)
    info = {
        "n_conflict_terms": len(conf),
        "n_gap_terms": len(gap_terms),
        "n_room_continuity_terms": len(room_continuity_terms),
        "n_faculty_consecutive_terms": len(faculty_consecutive_terms),
        "wall_a": solver.WallTime(),
        "stage_a_branches": solver.NumBranches() if hasattr(solver, "NumBranches") else None,
        "stage_a_conflicts": solver.NumConflicts() if hasattr(solver, "NumConflicts") else None,
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


def stage_b(ds: Dataset, sched: Schedule, limit=30, seed=329, workers=None, deadline=None):
    """Assign every selected course under fixed section times and student-day rules."""
    t0 = time.time()
    # Times are fixed from Stage A; this stage only chooses student-to-section assignments.
    occ = {
        sid: slots
        for sid in ds.sections
        if sid not in sched.unscheduled
        and (slots := sec_slots(ds, sched.placement, sid)) is not None
    }
    by_course = defaultdict(list)
    section_day_sessions = defaultdict(lambda: defaultdict(list))
    section_day_intervals = defaultdict(lambda: defaultdict(list))
    for sid in occ:
        by_course[ds.sections[sid].course_id].append(sid)
        for k, spec in enumerate(ds.section_sessions(sid)):
            start = sched.placement[(sid, k)][0]
            day = start // PERIODS
            slots = tuple(range(start, start + spec.duration))
            section_day_sessions[sid][day].append(slots)
            start_period, end_period = slots[0] % PERIODS, slots[-1] % PERIODS
            start_text = SESSION_TIMES[start_period][0]
            end_text = SESSION_TIMES[end_period][1]
            start_minute = int(start_text[:2]) * 60 + int(start_text[3:])
            end_minute = int(end_text[:2]) * 60 + int(end_text[3:])
            section_day_intervals[sid][day].append((start_minute, end_minute))

    m, a = cp_model.CpModel(), {}
    student_day_options = defaultdict(list)
    student_day_intervals = defaultdict(list)
    student_course_options = {}
    for stid, st in ds.students.items():
        if deadline is not None and time.monotonic() >= deadline:
            sched.enrolment = {student_id: {} for student_id in ds.students}
            sched.student_categories = {student_id: {} for student_id in ds.students}
            return "UNKNOWN", time.monotonic() - t0
        mine = []
        course_options = {}
        for c in st.selections:
            opts = student_section_options(ds, st, c, by_course.get(c, []))
            course_options[c] = opts
            for s in opts:
                assignment = m.NewBoolVar(f"enrol_{stid}_{s}")
                a[stid, s] = assignment
                for day, sessions in section_day_sessions[s].items():
                    student_day_options[stid, day].append((assignment, sessions))
                    for start_minute, end_minute in section_day_intervals[s][day]:
                        student_day_intervals[stid, day].append(
                            (start_minute, end_minute, assignment)
                        )
            if opts:
                m.Add(sum(a[stid, s] for s in opts) <= 1)                    # H11
            mine += opts
        student_course_options[stid] = course_options
        for i, s1 in enumerate(mine):
            if deadline is not None and time.monotonic() >= deadline:
                sched.enrolment = {student_id: {} for student_id in ds.students}
                sched.student_categories = {student_id: {} for student_id in ds.students}
                return "UNKNOWN", time.monotonic() - t0
            for s2 in mine[i + 1:]:
                if occ[s1] & occ[s2]:
                    m.Add(a[stid, s1] + a[stid, s2] <= 1)                    # H3
    per_sec = defaultdict(list)
    for (stid, s), v in a.items():
        per_sec[s].append(v)
    for s, vs in per_sec.items():
        m.Add(sum(vs) <= ds.sections[s].capacity)                            # H12

    category_vars = {}
    extended_vars = []
    compactness_terms = []
    shift_switch_terms = []
    for stid in ds.students:
        if deadline is not None and time.monotonic() >= deadline:
            sched.enrolment = {student_id: {} for student_id in ds.students}
            sched.student_categories = {student_id: {} for student_id in ds.students}
            return "UNKNOWN", time.monotonic() - t0
        active_days = []
        day_modes = {}
        for day in range(DAYS):
            options = student_day_options.get((stid, day), [])
            unique_assignments = list({assignment.Index(): assignment for assignment, _ in options}.values())
            active = m.NewBoolVar(f"active_{stid}_{day}")
            active_days.append(active)
            if unique_assignments:
                m.Add(sum(unique_assignments) >= active)
                m.Add(sum(unique_assignments) <= len(unique_assignments) * active)
            else:
                m.Add(active == 0)

            modes = {
                mode: m.NewBoolVar(f"{mode}_{stid}_{day}")
                for mode in STUDENT_DAY_SESSIONS
            }
            category_vars[stid, day] = modes
            day_modes[day] = modes
            m.Add(sum(modes.values()) == active)
            semester_mode = ds.meta.get("semester_sessions", {}).get(str(st.semester).strip())
            if semester_mode in (MORNING_SESSION, AFTERNOON_SESSION):
                extended_mode = (
                    EXTENDED_EARLY_SESSION
                    if semester_mode == MORNING_SESSION
                    else EXTENDED_LATE_SESSION
                )
                m.Add(modes[semester_mode] + modes[extended_mode] == active)
                for mode, variable in modes.items():
                    if mode not in (semester_mode, extended_mode):
                        m.Add(variable == 0)
            extended_vars.extend(modes[mode] for mode in EXTENDED_SESSIONS)

            daily_hours = []
            required_daily_hours = []
            required_lunch_occupancy = []
            period_assignments = defaultdict(list)
            # Derive required load from the course selections and scheduled section
            # offerings. When every eligible section gives the course the same
            # daily load, count that requirement even if the student selection is
            # left unassigned in a partial result. This prevents half-day status
            # from being manufactured by dropping a required class.
            for course_id, section_options in student_course_options[stid].items():
                if not section_options:
                    continue
                option_daily_hours = []
                option_lunch_hours = []
                for section_id in section_options:
                    sessions = section_day_sessions[section_id].get(day, [])
                    option_daily_hours.append(sum(len(slots) for slots in sessions))
                    option_lunch_hours.append(sum(
                        1 for slots in sessions for slot in slots
                        if slot % PERIODS in LUNCH_SLOTS
                    ))
                if len(set(option_daily_hours)) == 1:
                    required_daily_hours.append(option_daily_hours[0])
                else:
                    required_daily_hours.extend(
                        len(slots) * a[stid, section_id]
                        for section_id in section_options
                        for slots in section_day_sessions[section_id].get(day, [])
                    )
                if len(set(option_lunch_hours)) == 1:
                    required_lunch_occupancy.extend([1] * option_lunch_hours[0])
                else:
                    required_lunch_occupancy.extend(
                        a[stid, section_id]
                        for section_id in section_options
                        if (stid, section_id) in a
                        for slots in section_day_sessions[section_id].get(day, [])
                        for slot in slots if slot % PERIODS in LUNCH_SLOTS
                    )
            for assignment, sessions in options:
                allowed_modes = allowed_student_day_sessions(sessions)
                if allowed_modes:
                    m.Add(assignment <= sum(modes[mode] for mode in allowed_modes))
                else:
                    m.Add(assignment == 0)
                daily_hours.extend(len(slots) * assignment for slots in sessions)
                for slots in sessions:
                    for slot in slots:
                        period_assignments[slot % PERIODS].append(assignment)

            extended = sum(modes[mode] for mode in EXTENDED_SESSIONS)
            # Half-day categories have an explicit five-hour cap; extended
            # categories require more than five hours and a continuous one-hour
            # lunch break. LUNCH_SLOTS are the adjacent 12:05 and 13:10 periods.
            for mode in (MORNING_SESSION, AFTERNOON_SESSION):
                m.Add(sum(required_daily_hours) <= 5).OnlyEnforceIf(modes[mode])
            for mode in EXTENDED_SESSIONS:
                m.Add(sum(required_daily_hours) >= 6).OnlyEnforceIf(modes[mode])
                # At least one of the adjacent lunch periods must be completely
                # free, yielding a continuous break of roughly one hour.
                m.Add(sum(required_lunch_occupancy) <= 1).OnlyEnforceIf(modes[mode])

            # Penalize occupied periods spread across the day's envelope. Since student
            # clashes are hard constraints, each period has at most one selected class.
            first = m.NewIntVar(0, PERIODS, f"first_{stid}_{day}")
            last = m.NewIntVar(-1, PERIODS - 1, f"last_{stid}_{day}")
            for period, assignments in period_assignments.items():
                occupied = m.NewBoolVar(f"period_{stid}_{day}_{period}")
                m.AddMaxEquality(occupied, assignments)
                m.Add(first <= period).OnlyEnforceIf(occupied)
                m.Add(last >= period).OnlyEnforceIf(occupied)
            m.Add(first == 0).OnlyEnforceIf(active.Not())
            m.Add(last == -1).OnlyEnforceIf(active.Not())
            # The envelope penalty is bounded by nine periods per active day. This
            # breaks ties after maximizing allocated selections and preferring shorter shifts.
            # Credit one lunch period on extended days; any extra free period still
            # counts as a gap, including an overlong lunch window.
            compactness_terms.append(
                (last - first + 1) - sum(daily_hours) - extended
            )

        # Prefer one morning or afternoon batch for the whole week, while allowing
        # a day to switch when the student's selected classes make that necessary.
        week_active = m.NewBoolVar(f"week_active_{stid}")
        week_morning = m.NewBoolVar(f"week_morning_{stid}")
        week_afternoon = m.NewBoolVar(f"week_afternoon_{stid}")
        m.Add(week_morning + week_afternoon == week_active)
        m.Add(sum(active_days) >= week_active)
        m.Add(sum(active_days) <= DAYS * week_active)
        switch_vars = []
        for day, modes in day_modes.items():
            switch = m.NewBoolVar(f"shift_switch_{stid}_{day}")
            day_morning = modes[MORNING_SESSION] + modes[EXTENDED_EARLY_SESSION]
            day_afternoon = modes[AFTERNOON_SESSION] + modes[EXTENDED_LATE_SESSION]
            m.Add(day_morning <= week_morning + switch)
            m.Add(day_afternoon <= week_afternoon + switch)
            switch_vars.append(switch)
        shift_switch_terms.extend(switch_vars)

    # Keep the waiting time between consecutive selected classes at or below
    # two hours. Times use the timetable's real clock boundaries, including
    # the short breaks between teaching periods. A continuous 60-minute part
    # of the noon-to-2 PM window is exempt only on an extended day.
    for stid in ds.students:
        for day in range(DAYS):
            meetings = sorted(
                student_day_intervals.get((stid, day), []),
                key=lambda item: (item[0], item[1], item[2].Index()),
            )
            for i, (start_i, end_i, assign_i) in enumerate(meetings):
                for j in range(i + 1, len(meetings)):
                    start_j, end_j, assign_j = meetings[j]
                    if start_j < end_i or start_j - end_i <= 120:
                        continue
                    middle = {
                        variable.Index(): variable
                        for middle_start, middle_end, variable in meetings[i + 1:j]
                        if middle_start >= end_i and middle_end <= start_j
                    }
                    terms = list(middle.values())
                    lunch_minutes = max(
                        0, min(start_j, 14 * 60) - max(end_i, 12 * 60)
                    )
                    if lunch_minutes >= 60:
                        modes = category_vars.get((stid, day), {})
                        terms.extend(
                            modes[mode] for mode in EXTENDED_SESSIONS if mode in modes
                        )
                    m.Add(assign_i + assign_j <= 1 + sum(terms))

    compactness_weight = DAYS * len(ds.students) + 1
    secondary_objective_bound = DAYS * len(ds.students) * (
        2 * compactness_weight + PERIODS
    )
    placement_weight = secondary_objective_bound + 1
    m.Maximize(
        placement_weight * sum(a.values())
        - compactness_weight * sum(extended_vars)
        - sum(compactness_terms)
        - compactness_weight * sum(shift_switch_terms)
    )
    solver_limit = float(limit)
    if deadline is not None:
        solver_limit = min(solver_limit, deadline - time.monotonic())
    if solver_limit <= 0:
        sched.enrolment = {stid: {} for stid in ds.students}
        sched.student_categories = {stid: {} for stid in ds.students}
        return "UNKNOWN", time.time() - t0
    solver = _solver(solver_limit, seed, workers, num_sections=len(ds.sections))
    st = solver.Solve(m)
    name = solver.StatusName(st)
    sched.info["stage_b_branches"] = solver.NumBranches() if hasattr(solver, "NumBranches") else None
    sched.info["stage_b_conflicts"] = solver.NumConflicts() if hasattr(solver, "NumConflicts") else None
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        sched.info["stage_b_objective"] = solver.ObjectiveValue()
        sched.info["stage_b_best_bound"] = solver.BestObjectiveBound()
    enrol = {stid: {} for stid in ds.students}
    categories = {stid: {} for stid in ds.students}
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (stid, s), v in a.items():
            if solver.Value(v):
                enrol[stid][ds.sections[s].course_id] = s
        for (stid, day), modes in category_vars.items():
            selected = next((mode for mode, var in modes.items() if solver.Value(var)), None)
            if selected:
                categories[stid][day] = selected
    sched.enrolment = enrol
    sched.student_categories = categories
    return name, time.time() - t0


def _unplaced_choices(ds: Dataset, sched: Schedule):
    return [
        (stid, course_id)
        for stid, student in ds.students.items()
        for course_id in student.selections
        if course_id not in sched.enrolment.get(stid, {})
    ]


def _unplaced_choice_diagnostics(ds: Dataset, sched: Schedule):
    """Classify unplaced selections without claiming a specific cause when evidence is ambiguous."""
    sections_by_course = defaultdict(list)
    for sid, section in ds.sections.items():
        sections_by_course[section.course_id].append(sid)

    section_enrolment = defaultdict(int)
    for enrolments in sched.enrolment.values():
        for sid in enrolments.values():
            section_enrolment[sid] += 1

    section_slots = {
        sid: sec_slots(ds, sched.placement, sid)
        for sid in ds.sections
        if sid not in sched.unscheduled
    }

    diagnostics = []
    for stid, course_id in _unplaced_choices(ds, sched):
        student = ds.students[stid]
        candidates = student_section_options(
            ds, student, course_id, sections_by_course.get(course_id, [])
        )
        scheduled = [sid for sid in candidates if section_slots.get(sid) is not None]
        selected_sections = list(sched.enrolment.get(stid, {}).values())
        if sched.info.get("status_b") == "INFEASIBLE":
            reason = "hard_constraint_conflict"
            description = (
                "No complete student allocation satisfies the session windows, "
                "class-hour limits, lunch, waiting-time, overlap, and capacity constraints."
            )
        elif sched.info.get("status_b") not in ("OPTIMAL", "FEASIBLE"):
            reason = "student_solver_incomplete"
            description = f"Student allocation solver ended with {sched.info.get('status_b', 'NOT_RUN')}."
        elif not candidates:
            reason = "no_offering"
            description = "No section is available for this course and student cohort."
        elif not scheduled:
            reason = "section_unscheduled"
            description = "No section for this course was scheduled."
        elif all(
            section_enrolment[sid] >= ds.sections[sid].capacity
            for sid in scheduled
        ):
            reason = "capacity"
            description = "All scheduled sections for this course reached capacity."
        elif all(
            any(section_slots[sid] & section_slots.get(chosen, set()) for chosen in selected_sections)
            for sid in scheduled
        ):
            reason = "student_conflict"
            description = "Every scheduled section overlaps another course assigned to this student."
        elif sched.info.get("complete_allocation_status") == "UNKNOWN":
            reason = "allocation_not_proven"
            description = (
                "This selection remains unplaced in the current partial solution; "
                "the solver has not proved whether a complete allocation exists."
            )
        else:
            reason = "hard_constraint_conflict"
            description = (
                "This selection could not fit in the best feasible allocation while "
                "respecting session windows, daily hours, lunch, overlaps, waiting time, and capacity."
            )
        diagnostics.append({
            "student_id": stid,
            "course_id": course_id,
            "reason": reason,
            "description": description,
            "candidate_sections": scheduled,
        })
    return diagnostics


def _priority_course_pairs(ds: Dataset, unplaced):
    weights = defaultdict(int)
    for stid, course_id in unplaced:
        student = ds.students[stid]
        for other_course in student.selections:
            if other_course != course_id:
                pair = tuple(sorted((course_id, other_course)))
                weights[pair] += 1000
    return list(weights.items())


def cpsat(
    ds: Dataset,
    limit_a=30,
    limit_b=30,
    seed=329,
    workers=None,
    total_limit=DEFAULT_TOTAL_SOLVE_SECONDS,
    **kw,
) -> Schedule:
    """Run both stages under one bounded wall-clock budget."""
    # The S2/S3 shared-student pair objective expands quickly on generated data.
    # Keep placement, resource, and all hard constraints; omit only that optional
    # conflict-pair preference for larger generated cohorts to retain a feasible
    # incumbent inside the documented budget.
    if ds.synthetic and len(ds.sections) > 30 and "top_pairs" not in kw:
        kw["top_pairs"] = 0
    if workers is None and ds.synthetic and len(ds.sections) > 20:
        workers = 4
    t0 = time.monotonic()
    budget = min(MAX_TOTAL_SOLVE_SECONDS, max(0.1, float(total_limit)))
    # Reserve time for validation, serialization, and the HTTP response.
    deadline = t0 + max(0.05, budget - 0.5)
    limit_a = min(float(limit_a), budget * 0.62)
    name, sched, info = stage_a(
        ds, limit=limit_a, seed=seed, workers=workers, deadline=deadline, **kw
    )
    sched.info.update(info)
    sched.info["time_budget_s"] = budget
    sched.info["student_conflict_refinements"] = 0
    stage_a_solver_status = name
    sched.info["stage_a_status"] = stage_a_solver_status

    if name in ("OPTIMAL", "FEASIBLE"):
        remaining = deadline - time.monotonic()
        if remaining > 0.05:
            nb, stage_b_elapsed = stage_b(
                ds,
                sched,
                limit=min(float(limit_b), remaining),
                seed=seed,
                workers=workers,
                deadline=deadline,
            )
            sched.info["wall_b"] = stage_b_elapsed
        else:
            nb = "UNKNOWN"
            sched.enrolment = {stid: {} for stid in ds.students}
            sched.student_categories = {stid: {} for stid in ds.students}
        sched.info["status_b"] = nb
        if nb not in ("OPTIMAL", "FEASIBLE"):
            sched.info["complete_allocation_status"] = (
                "INFEASIBLE" if nb == "INFEASIBLE" else "UNKNOWN"
            )
            sched.info["status_b_reason"] = (
                f"Stage B ended with {nb} inside the {budget:g}-second total budget; "
                "student selections may remain unassigned."
            )
        else:
            sched.info["refinement_unplaced_choices"] = len(_unplaced_choices(ds, sched))
            sched.info["complete_allocation_status"] = (
                ("INFEASIBLE" if nb == "OPTIMAL" else "UNKNOWN")
                if sched.info["refinement_unplaced_choices"] else "FEASIBLE"
            )
            if sched.info["refinement_unplaced_choices"]:
                if nb == "OPTIMAL":
                    sched.info["complete_allocation_reason"] = (
                        f"The best feasible partial allocation leaves "
                        f"{sched.info['refinement_unplaced_choices']} required selections unplaced "
                        "under the hard session, workload, lunch, overlap, waiting-time, and capacity constraints."
                    )
                else:
                    sched.info["complete_allocation_reason"] = (
                        "A partial allocation was found, but the solver did not prove whether "
                        "a complete allocation exists within its time limit."
                    )
    else:
        sched.info["status_b"] = "NOT_RUN"
        sched.info["status_b_reason"] = f"Stage A ended with {name}; no student allocation was attempted."

    sched.status = name
    sched.info["unplaced_choice_diagnostics"] = _unplaced_choice_diagnostics(ds, sched)
    sched.runtime = time.monotonic() - t0
    return sched
