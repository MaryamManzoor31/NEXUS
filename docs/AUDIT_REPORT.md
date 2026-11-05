# NEXUS Codebase Audit and Implementation Report

Audit and implementation completed against the user-provided comprehensive brief. The implementation preserves the existing Flask application, canonical data model, independent validator, and two-stage OR-Tools CP-SAT design.

## Workflow and architecture changes

- Dashboard startup loads and displays the packaged original allocation and baseline without invoking CP-SAT. `/api/current` and `/api/original` do not optimize.
- Excel, CSV, and mapped imports load and validate data without scheduling. Optimization runs only after the user's explicit action.
- The original baseline remains a separate `Schedule`; an optimization result is stored separately and compared with it. Original input files are not overwritten.
- Stage A schedules section time, room, and faculty; Stage B assigns students against the fixed Stage A timetable. Both use CP-SAT. The disconnected second faculty-assignment engine was removed from the active web and CLI path.
- Solver failure now returns an explicit API failure. Partial solutions keep solver statuses and expose unscheduled sections and unplaced course selections.
- Solver metrics include objective, best bound, branches, conflicts, and runtime. CLI results use unique UTC run IDs rather than reusing historical filenames.
- API requests are serialized against the process-global active schedule state. This protects single-process concurrent requests; it does not make multi-worker deployment persistent or coordinated.
- A missing CSV template directory was restored as a schema example and is clearly labelled synthetic.

## Constraint implementation matrix

The complete ID-by-ID matrix is in [`CONSTRAINTS.md`](CONSTRAINTS.md). Summary:

| Rules | CP-SAT | Independent validator | Coverage |
|---|---|---|---|
| H1-H2 faculty and room conflicts | Stage A interval no-overlap | Yes | Unit regressions |
| H3 student overlap | Stage B conflict constraints | Yes | Unit regressions |
| H4-H8 capacity, room type, qualification, availability, day bounds | Stage A | Yes | Unit and workbook import tests |
| H9-H10 section completion reporting and fixed baseline assignments | Stage A placement variables and fixed constraints | Yes | Unit regressions |
| H11-H12 selection integrity and section capacity | Stage B | Yes | Unit regressions |
| H13 blocked resources during repair | Stage A blocked-resource arguments | Checks engine output; repair is limited to blocked room/faculty requests | Unit regression; full disruption workflows remain limited |
| H14 faculty weekly workload | Stage A load constraints | Yes | Unit regression |
| H15 category, daily required hours, 5-hour cap, extended window, lunch | Stage B `session_type[student,day]` equivalent variables and class-hour/lunch constraints | Yes; includes same-day unplaced offerings when their daily load is unambiguous | Morning, afternoon, extended, partial-allocation, and validator regressions |
| H16 semester session and student category windows | Stage A semester windows and Stage B category compatibility | Yes | Unit regressions |
| H17 student/cohort offering compatibility | Stage B eligible-section filtering | Yes | Unit regression |
| H18 120-minute consecutive-class wait bound with protected extended lunch | Stage B pairwise assignment implications | Yes using timetable clock boundaries | Solver and validator regressions |

H15 and H18 are hard constraints, not display preferences. If a required daily load cannot fit a legal window or lunch, Stage B leaves it unallocated and the result reports incomplete allocation. It does not assign a half-day category by dropping an inconvenient selection. Section placements for an unplaced course remain visible as unplaced diagnostics.

Soft objectives and scale-specific trade-offs (including omitting optional objectives above 30 sections) are documented in `CONSTRAINTS.md`.

## Audit findings addressed

1. Startup used to optimize implicitly; the startup and import paths are now baseline-first and solver-free.
2. Greedy scheduling/warm-start/fallback logic was removed from the active implementation. CP-SAT baseline hints are still permitted.
3. Faculty allocation had a separate engine path that did not flow into the final section solver assignments; the active path now uses Stage A CP-SAT faculty assignments.
4. A partial allocation could appear compatible with a half-day by dropping a required class. Daily required hours now account for eligible scheduled section options and category selection remains consistent across the day.
5. Student waiting time now has a hard CP-SAT implication and an independent validation rule.
6. UI and API paths now distinguish load-only from explicit optimization; static demo metrics were removed and original/optimized views are separate.
7. Missing CSV templates made import and comparison workflows fail; a synthetic schema example set was restored.
8. Historical results remain untouched; new CLI and audit runs are timestamped.

## Actual experiment results

Run `20261105T105926Z`, OR-Tools `9.15.6755`, outputs under [`experiments/results/audit_runs/20261105T105926Z`](../experiments/results/audit_runs/20261105T105926Z/summary.json).

| Dataset | CP-SAT Stage A / B | Sections | Student selections | Independent validation | Runtime |
|---|---|---:|---:|---|---:|
| Packaged Jan 2025, Semester 6, morning | FEASIBLE / OPTIMAL | 296/318 | 324/374 (50 unplaced) | VALID_INCOMPLETE, 0 hard violations | 21.17 s |
| Synthetic S3, 20 students, seed 329 | FEASIBLE / OPTIMAL | 43/43 | 40/180 (140 unplaced) | VALID_INCOMPLETE, 0 hard violations | 15.70 s |

The university data has 48 representative student records, not individual university enrolments. The optimized run's 324/374 figure is therefore coverage of representative choices, not actual student allocation coverage. The separately validated source baseline is INVALID with 123 H5 room-type mismatches and has 10 sections without a baseline row. Comparison counts and full validator messages are in the university JSON artifact. Do not use the historical experiment outputs as results from this code version.

## Verification

- `python -m pytest -q` in a workspace-local temporary directory: final run **104 passed, 8 subtests passed**.
- JavaScript syntax: `node --check web/static/js/app.js` passed.
- Python compilation: `python -m py_compile main.py web/server.py web/serializer.py nexus_core/cpsat.py nexus_core/validator.py nexus_core/excel_parser.py` passed.
- Packaged university and synthetic CP-SAT runs were executed and written to the run folder above.

## Remaining limitations

- Workbook section capacities (40 lab / 70 lecture), room capacities (80), and availability are assumptions because the workbook lacks authoritative inventory/availability data.
- The baseline's 123 H5 mismatches cannot be corrected responsibly without an authoritative room-use mapping.
- Representative student records cannot support claims about individual university enrolment coverage. Actual student-course choices are required.
- Web uploads and optimization state remain in-memory and are cleared on restart; SQLite is CLI-only and is not integrated into the web session lifecycle. The API lock is process-local, so multiple server workers need shared persistence/coordination.
- Repair currently accepts blocked room/faculty inputs; time-slot disruptions and full scenario history are not implemented.
- Full Excel export is not implemented; CSV and JSON exports are available.
- Above 30 sections, optional conflict-pair and consecutive-teaching objectives are omitted to control CP-SAT model build. Hard constraints remain enforced.
