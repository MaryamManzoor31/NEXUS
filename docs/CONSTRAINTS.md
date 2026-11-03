# CONSTRAINTS.md  (M3)
Hard constraints define validity; soft ones rank valid schedules. A soft penalty never excuses a hard violation.
Source column: PS = signed problem statement 329; TD = team design decision; Plan = NEXUS_Master_Plan §7.4.

| ID | Hard constraint | Validator | CP-SAT | Test | Source |
|---|---|---|---|---|---|---|
| H1 | Faculty teaches at most one session at a time | yes | yes | test_m_faculty_clash_H1 | PS, ITC |
| H2 | Room hosts at most one session at a time | yes | yes | test_m_room_clash_H2 | PS, ITC-2007 |
| H3 | Student attends at most one session at a time | yes | Stage B | test_m_student_clash_H3 | PS, ITC-2007 T2 |
| H4 | Room capacity >= section capacity (validator also checks enrolment) | yes | yes | test_m_room_capacity_H4 | PS |
| H5 | Room type matches session (labs in labs) | yes | yes | test_m_room_type_H5 | PS |
| H6 | Faculty qualified for the course | yes | yes | test_m_unqualified_faculty_H6 | PS, Algethami & Laesanklang 2021 |
| H7 | Faculty and room availability respected | yes | yes | test_m_faculty/room_unavailable_H7 | PS |
| H8 | Session stays inside one day and the week | yes | yes | test_m_day_boundary_H8 | TD |
| H9 | Each section fully scheduled, or listed unscheduled | yes | yes | test_m_missing_session_H9 | TD |
| H10 | Fixed baseline timetable assignments preserved (time/room/faculty) | yes | yes | test_fixed_assignment_preserved / test_validator_detects_broken_fixed_assignment | PS O6 + real-data baseline |
| H11 | One section per selected course, only of that course | yes | Stage B | test_m_enrol_*_H11 | TD |
| H12 | Section enrolment limit | yes | Stage B | test_m_section_capacity_H12 | TD |
| H13 | Unavailable resources unused during repair | via blocked_* arguments | yes (engine level) | test_blocked_room_is_never_used | PS (adjustments); repair module M9 pending |
| H14 | Faculty weekly load <= max_hours (added; not in plan register) | yes | yes | test_m_workload_H14 | TD |

| ID | Soft objective | Status |
|---|---|---|
| S1 | Maximise placed student selections | Stage B CP-SAT objective |
| S2 | Avoid overlap of courses sharing many students | Stage A CP-SAT penalty weighted by shared-student count; if Stage B leaves choices unplaced, bounded Stage A refinements prioritize those students' course pairs and retain only improvements |
| S3 | Balance faculty workload | Stage A: minimise maximum load |
| S4-S7 | utilization, gaps, preferences, fairness | not implemented |
| S8 | Minimal change from original timetable (preferred baseline) | Stage A soft weights `w_move` / `w_room` / `w_fac` (defaults 5/2/3 when baseline present) |

Stage A status is passed through unchanged (OPTIMAL / FEASIBLE / INFEASIBLE / UNKNOWN / MODEL_INVALID). A CP-SAT timeout
does not promote a heuristic hint to a solver-produced schedule. Student allocation has its own `status_b` result;
when Stage A has no usable solution, Stage B is `NOT_RUN`. INFEASIBLE is reported only when Stage A runs with
`allow_unscheduled=False`; by default sections that cannot be placed are listed as unscheduled.
