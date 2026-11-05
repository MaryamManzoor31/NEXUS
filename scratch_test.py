import sys, os
from dataclasses import replace
from collections import defaultdict
sys.path.insert(0, os.path.abspath('nexus'))
from nexus_core.excel_parser import parse_allocation_workbook
from nexus_core.member_allocator import allocate_faculty_members
from nexus_core.cpsat import cpsat
from nexus_core.validator import validate
from nexus_core.models import AFTERNOON_SESSION, Student, Room, LAB

# Monkey patch _solver to use 8 workers
import nexus_core.cpsat as cp_mod
old_solver = cp_mod._solver
def multi_solver(limit, seed, workers, num_sections=0):
    return old_solver(limit, seed, workers=8 if workers is None else workers, num_sections=num_sections)
cp_mod._solver = multi_solver

ds, meta = parse_allocation_workbook('nexus/data/Course - Faculty Allocation - Jan 2025 onwards (30-11-24)(1).xlsx', semester_filter='4')
ds.meta['semester_sessions'] = {'4': AFTERNOON_SESSION}
alloc = allocate_faculty_members(ds, meta['pre_assigned_faculty'], meta['raw_faculty_info'])
for sid, fid in alloc.faculty_assignments.items():
    if fid in ds.faculty and sid in ds.sections:
        ds.faculty[fid] = replace(ds.faculty[fid], qualified=ds.faculty[fid].qualified | {ds.sections[sid].course_id})
for i in range(13, 26):
    lid = f"CS_Lab_{i:02d}"
    ds.rooms[lid] = Room(id=lid, type=LAB, capacity=80, unavailable=frozenset())

# Apply clean cohort student generation
cohort_courses = defaultdict(lambda: {'core': set(), 'elec': set()})
for sid, sec in ds.sections.items():
    c = ds.courses[sec.course_id]
    is_elec = 'elective' in c.category.lower() or 'elective' in c.course_type.lower()
    cohort_name = sec.batch.strip() or sid
    c_clean = cohort_name.split(',')[0].strip()
    if is_elec:
        cohort_courses[c_clean]['elec'].add(c.id)
    else:
        cohort_courses[c_clean]['core'].add(c.id)

students = {}
st_counter = 1
for cohort_name, c_dict in cohort_courses.items():
    core_list = sorted(list(c_dict['core']))
    seen_titles = set()
    clean_cores = []
    for cid in core_list:
        t = ds.courses[cid].title.strip().lower()
        if t not in seen_titles:
            seen_titles.add(t)
            clean_cores.append(cid)
    elec_list = sorted(list(c_dict['elec']))
    if not elec_list:
        for _ in range(2):
            stid = f"STU_{st_counter:03d}_4_{cohort_name}"
            students[stid] = Student(id=stid, programme=cohort_name, selections=tuple(clean_cores), semester='4', batch=cohort_name)
            st_counter += 1
    else:
        for elec_id in elec_list:
            stid = f"STU_{st_counter:03d}_4_{cohort_name}"
            selections = tuple(clean_cores + [elec_id])
            students[stid] = Student(id=stid, programme=cohort_name, selections=selections, semester='4', batch=cohort_name)
            st_counter += 1

ds.students = students
print(f"Created {len(ds.students)} students for Sem 4. Total selections: {sum(len(s.selections) for s in ds.students.values())}")
sch = cpsat(ds, limit_a=25, limit_b=15, seed=329)
rep = validate(ds, sch)
print(f"Sem 4 Result: Status={sch.status}, PlacedSec={len(sch.placement)}/{len(ds.sections)}, Unplaced={len(rep.unplaced)}, Violations={len(rep.violations)}")
print(f"Validation Report: {rep.status}")
