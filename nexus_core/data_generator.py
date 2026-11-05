"""Synthetic NEP-style instances (SYNTHETIC - never present as real university data). Rules: docs/GENERATOR_RULES.md"""
from __future__ import annotations
import math
import random
from .models import *

DEPTS = ["CSE", "ECE", "MECH", "BBA", "PSY"]
POOLS = {"Minor": 10, "Skill-Based": 5, "Ability-Enhancement": 4, "Value-Added": 4}   # + 5 depts x 6 majors = 55 courses


def generate(n_students=500, scenario="S3", seed=329, n_faculty=30, n_class=20, n_lab=5, name=None,
             unqualified_course=False) -> Dataset:
    # A local seeded random generator makes the same inputs reproducible.
    rng = random.Random(seed)
    # ---- courses ---------------------------------------------------------------------------------
    courses, majors = {}, {d: [] for d in DEPTS}
    def add(cid, title, cat, credits, sess):
        courses[cid] = Course(cid, title, cat, credits, tuple(SessionSpec(*x) for x in sess))
    k = 0
    for d in DEPTS:
        for i in range(6):
            k += 1
            cid = f"C{k:02d}"
            lab = i % 3 == 0                                     # every third major has a lab component
            add(cid, f"{d} Major {i+1}", "Major", 4, [(1, CLASS), (1, CLASS)] + ([(2, LAB)] if lab else []))
            majors[d].append(cid)
    pools = {}
    for cat, n in POOLS.items():
        pools[cat] = []
        for i in range(n):
            k += 1
            cid = f"C{k:02d}"
            lab = cat == "Minor" and i % 4 == 0
            add(cid, f"{cat} {i+1}", cat, 3 if cat == "Minor" else 2,
                [(1, CLASS), (1, CLASS)] + ([(2, LAB)] if lab else []) if cat == "Minor" else [(1, CLASS)] * 2)
            pools[cat].append(cid)
    # ---- students (pathways) ---------------------------------------------------------------------
    students = {}
    pop = {cat: [1.0 / (j + 1) ** 0.7 for j in range(len(v))] for cat, v in pools.items()}   # popularity skew
    def pick(cat, n):
        out = []
        while len(out) < n:
            c = rng.choices(pools[cat], pop[cat])[0]
            if c not in out:
                out.append(c)
        return out
    for i in range(n_students):
        # The scenario determines how many core and elective courses each student selects.
        d = DEPTS[i % len(DEPTS)]
        core = majors[d][:4] if scenario == "S3" else majors[d][:5] if scenario == "S2" else majors[d][:6]
        sel = list(core)
        if scenario == "S2":
            sel += pick("Minor", rng.choice([1, 2]))
        elif scenario == "S3":
            sel += pick("Minor", 2) + pick("Skill-Based", 1) + pick("Ability-Enhancement", 1) + pick("Value-Added", 1)
        students[f"S{i+1:04d}"] = Student(f"S{i+1:04d}", "FYUP", tuple(sel))
    # ---- rooms -----------------------------------------------------------------------------------
    rooms = {}
    for i in range(n_class):
        cap = rng.choice([40, 50, 60, 80])
        rooms[f"R{i+1:02d}"] = Room(f"R{i+1:02d}", CLASS, cap)
    for i in range(n_lab):
        rooms[f"L{i+1:02d}"] = Room(f"L{i+1:02d}", LAB, rng.choice([30, 40]))
    max_cap = {CLASS: max(r.capacity for r in rooms.values() if r.type == CLASS),
               LAB: max(r.capacity for r in rooms.values() if r.type == LAB)}
    # ---- sections: planned size from demand, capped by the largest compatible room ----------------
    demand = {c: 0 for c in courses}
    for s in students.values():
        for c in s.selections:
            demand[c] += 1
    sections = {}
    for cid, c in courses.items():
        if demand[cid] == 0:
            continue
        # Create enough sections for demand, within compatible room capacity.
        limit = min(max_cap[x.room_type] for x in c.sessions)
        limit = min(limit, 45)
        n = math.ceil(demand[cid] * 1.1 / limit)
        cap = math.ceil(demand[cid] * 1.1 / n)
        for j in range(n):
            sections[f"{cid}-{chr(65 + j)}"] = Section(f"{cid}-{chr(65 + j)}", cid, cap)
    # ---- faculty: 2-4 qualified courses each; every taught course gets >= 2 qualified faculty -----
    taught = [c for c in courses if demand[c] > 0]
    quals = {f"F{i+1:02d}": set() for i in range(n_faculty)}
    fids = list(quals)
    for c in taught:
        for f in rng.sample(fids, 2):
            quals[f].add(c)
    for f in fids:
        while len(quals[f]) < 3:
            quals[f].add(rng.choice(taught))
    if unqualified_course:                                         # deliberately infeasible fixture
        victim = taught[0]
        for f in fids:
            quals[f].discard(victim)
    faculty = {}
    for f in fids:
        off_day = rng.randrange(DAYS)
        un = frozenset(range(off_day * PERIODS + 5, off_day * PERIODS + PERIODS))   # one afternoon off
        faculty[f] = Faculty(f, f"Faculty {f}", frozenset(quals[f]), 18, un)
    return Dataset(name or f"synthetic_{scenario}_{n_students}_seed{seed}", courses, sections, faculty, rooms,
                   students, True, {"scenario": scenario, "seed": seed, "n_students": n_students})
