# CONSTRAINTS.md  (M3)
Hard constraints define validity; soft ones rank valid schedules. A soft penalty never excuses a hard violation.
Source column: PS = signed problem statement 329; TD = team design decision; Plan = NEXUS_Master_Plan §7.4.

The two CP-SAT stages share one wall-clock deadline. The general default is 30 seconds, and the engine cap is 90 seconds. The packaged Excel workflow requests up to 50 seconds for Stage A and 35 seconds for Stage B within a 90-second total budget. The Diagnostics view reports actual time spent by each stage and summarizes unplaced sections and student selections. Startup only loads the original baseline and does not invoke the solver.

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
| H15 | Morning 08:00-13:00 and afternoon 13:00-18:00 are limited to 5 class hours; required daily load over 5 hours needs the matching extended 08:00-16:00 or 10:00-18:00 window and an uninterrupted 60-minute lunch break between 12:00-14:00; unplaced choices cannot reduce required load | yes | Stage B | test_stage_b_allows_extended_session_with_lunch_break / test_stage_b_uses_required_daily_hours_even_when_one_choice_cannot_be_placed / test_validator_does_not_hide_over_five_required_hours_by_leaving_choice_unplaced | TD |
| H16 | Explicit morning/afternoon batch follows its regular window or the corresponding extended window; auto mode assigns per-student shifts | yes | Stage A + Stage B | test_stage_a_enforces_semester_session_window / test_validator_rejects_wrong_semester_window | TD |
| H17 | Core-course section matches the student's department/programme/stream/batch/semester when source metadata identifies one; minor/elective offerings can be cross-program | yes | Stage B | test_stage_b_uses_student_cohort_and_cross_program_electives | TD |
| H18 | Waiting time between consecutive attended classes is at most 120 real clock minutes; an extended student's qualifying lunch interval is protected | yes | Stage B | test_stage_b_enforces_two_hour_waiting_limit / test_validator_rejects_three_hour_student_wait / test_extended_lunch_is_exempt_from_two_hour_wait_limit | TD |

| ID | Soft objective | Status |
|---|---|---|
| S1 | Maximise placed student selections | Stage B CP-SAT objective |
| S2 | Avoid overlap of courses sharing many students | Stage A CP-SAT penalty weighted by shared-student count; if Stage B leaves choices unplaced, bounded Stage A refinements prioritize those students' course pairs and retain only improvements |
| S3 | Balance faculty workload | Stage A: minimise maximum load |
| S4 | Minimize timetable gaps after hard H18 waiting-time bound | Stage A gap objective; Stage B minimizes assigned students' daily span |
| S5 | Prefer the selected batch's start time when feasible | Stage A weighted start-period objective |
| S6 | Keep student batch consistent during the week | Stage B soft penalty for morning/afternoon batch switches |
| S7 | Reuse rooms for successive same-type sessions and avoid back-to-back faculty sessions | Stage A soft preferences; the consecutive-session tie-breaker is omitted for instances over 30 sections to keep model build bounded |
| S8 | Minimal change from original timetable (preferred baseline) | Stage A soft weights `w_move` / `w_room` / `w_fac` (defaults 5/2/3 when baseline present) |
| S9 | Balance overall room utilization | not implemented |

Room capacity, room type, room/faculty availability, faculty qualification, faculty load limits, and simultaneous-use conflicts are enforced against dataset fields. The packaged workbook does not provide authoritative room or section capacities or room/faculty unavailable periods. The parser's 40/70 section capacities and 80-seat rooms are estimates; empty unavailable sets mean availability is unknown, not confirmed. The packaged baseline has 123 H5 laboratory-to-classroom mismatches and 10 sections without baseline entries. These are reported, not silently relabeled; a room inventory or authoritative room-use map is needed to determine whether these are source mapping errors or real assignments.

The workbook parser creates two **representative** student records per cohort to model cohort conflicts. They are not individual university enrolments, so student-allocation percentages from this mode are indicative only. Import actual student records to claim individual allocation coverage.

Stage A status is passed through unchanged (OPTIMAL / FEASIBLE / INFEASIBLE / UNKNOWN / MODEL_INVALID). Student allocation has its own `status_b` result; when Stage A has no usable solution, Stage B is `NOT_RUN`. With the default `allow_unscheduled=True`, the solver maximizes placed sections and lists any unplaced sections; the strict Stage A API can require all sections and report infeasibility. No alternate timetable construction or fallback path is used. A CP-SAT baseline hint is allowed. Stage B maximizes feasible placed selections and reports unplaced choices and whether complete allocation was proven infeasible or remains unproven.

For synthetic datasets with more than 20 sections, CP-SAT uses four search workers unless a caller specifies a worker count. For synthetic datasets over 30 sections, it omits the optional course-pair overlap objective, and for all instances over 30 sections it omits the optional consecutive-teaching preference. Hard constraints remain in the model. This trades some quality optimization for a more reliable chance of finding a feasible incumbent within the runtime budget.

