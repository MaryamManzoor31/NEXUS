# CONSTRAINTS.md  (M3)
Hard constraints define validity; soft ones rank valid schedules. A soft penalty never excuses a hard violation.
Source column: PS = signed problem statement 329; TD = team design decision; Plan = NEXUS_Master_Plan §7.4.

| ID | Hard constraint | Validator | CP-SAT | Greedy | Test | Source |
|---|---|---|---|---|---|---|
| H1 | Faculty teaches at most one session at a time | yes | yes | yes | test_m_faculty_clash_H1 | PS, ITC |
| H2 | Room hosts at most one session at a time | yes | yes | yes | test_m_room_clash_H2 | PS, ITC-2007 |
| H3 | Student attends at most one session at a time | yes | Stage B | phase 2 | test_m_student_clash_H3 | PS, ITC-2007 T2 |
| H4 | Room capacity >= section capacity (validator also checks enrolment) | yes | yes | yes | test_m_room_capacity_H4 | PS |
| H5 | Room type matches session (labs in labs) | yes | yes | yes | test_m_room_type_H5 | PS |
| H6 | Faculty qualified for the course | yes | yes | yes | test_m_unqualified_faculty_H6 | PS, Algethami & Laesanklang 2021 |
| H7 | Faculty and room availability respected | yes | yes | yes | test_m_faculty/room_unavailable_H7 | PS |
| H8 | Session stays inside one day and the week | yes | yes | yes | test_m_day_boundary_H8 | TD |
| H9 | Each section fully scheduled, or listed unscheduled | yes | yes | yes | test_m_missing_session_H9 | TD |
| H10 | Block / fixed activities (internships, field work, teaching practice) | **not modelled** | no | no | none | PS scope item O6 - representation awaiting mentor decision |
| H11 | One section per selected course, only of that course | yes | Stage B | phase 2 | test_m_enrol_*_H11 | TD |
| H12 | Section enrolment limit | yes | Stage B | phase 2 | test_m_section_capacity_H12 | TD |
| H13 | Unavailable resources unused during repair | via blocked_* arguments | yes (engine level) | no | test_blocked_room_is_never_used | PS (adjustments); repair module M9 pending |
| H14 | Faculty weekly load <= max_hours (added; not in plan register) | yes | yes | yes | test_m_workload_H14 | TD |

| ID | Soft objective | Status |
|---|---|---|
| S1 | Maximise placed student selections | Stage B objective; greedy phase 2 heuristic |
| S2 | Avoid overlap of courses sharing many students | Stage A penalty weighted by shared-student count |
| S3 | Balance faculty workload | Stage A: minimise maximum load |
| S4-S8 | utilization, gaps, preferences, fairness, change cost | not implemented |

Solver status is passed through unchanged (OPTIMAL / FEASIBLE / INFEASIBLE / UNKNOWN). INFEASIBLE is reported only when
Stage A runs with `allow_unscheduled=False`; by default sections that cannot be placed are listed as unscheduled.
