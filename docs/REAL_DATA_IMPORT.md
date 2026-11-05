# Real University Dataset Import

NEXUS accepts **real university data** as the primary optimization input. Synthetic S1/S2/S3 data remains available for testing only.

## Supported input methods

| Method | How | Notes |
|---|---|---|
| A. Packaged university Excel | UI “Jan 2025 University Allocation” or `python main.py excel <file.xlsx>` | Course–faculty allocation workbook |
| B. CSV / Excel upload | UI Upload dialog or `python main.py import <folder>` | Canonical CSVs + optional `timetable.csv` |
| C. Synthetic | UI S1/S2/S3 or `python main.py optimize` | Development / benchmarks only |

CSV upload remains fully supported.

The packaged allocation-workbook parser currently estimates section capacities
(40 for lab sections, 70 for lecture sections) and sets discovered room capacities
to 80. The workbook contains no authoritative room or section capacities. These
estimates are surfaced as assumptions in the dashboard and should be replaced by
the campus room inventory before capacity-sensitive operational use. Mapped CSV
imports use the supplied room inventory.

## Canonical CSV files

Templates live in `data/templates/`:

The included example rows are synthetic schema examples, not university records.

1. `courses.csv`
2. `sections.csv`
3. `faculty.csv`
4. `rooms.csv`
5. `students.csv`
6. `timetable.csv` *(optional baseline / original timetable)*

### Required classic columns

- courses: `course_id,title,category,credits,pattern`
- sections: `section_id,course_id,capacity`
- faculty: `faculty_id,name,qualified,max_hours,unavailable`
- rooms: `room_id,type,capacity,unavailable`
- students: `student_id,programme`, plus at least one of `selections`, `minor_electives`, or `elective_selections`. Those choice columns are merged into the student's selected course IDs.

### Optional institutional columns

`school_id`, `department_id`, `programme_id`, `stream`, `semester`, `academic_year`, `course_type`, `batch`, `designation`, `building`

These enrich reporting and NEP multidisciplinary context. They are **not invented** when absent.
For real individual elective timetables, each `students.csv` row must identify that student's selected course IDs. Aggregate elective counts in an allocation workbook cannot identify which individual selected each course.
Student department, programme, stream, semester, and batch values help match core courses to the correct section. Minor and elective selections can be assigned across departments when a student selects them.
Sections may also provide an optional `session_pattern` such as `2:LAB` to preserve a
course allocation's session type when it differs from the course's default pattern.
In the section timetable view, course allocations with the same semester and class
section name are shown together; a trailing `Lab` or `Practical` suffix does not make
a separate displayed class section. A comma-separated class label shares that course
allocation with each named section in the section timetable.

### Baseline timetable columns

`Day, Period, Section, Room, Faculty ID` are required (aliases accepted). Optional: `mode` (`fixed` / `preferred` / `flexible`), `session_index`, course metadata, school/stream.
The scheduling grid uses 10 teaching sessions per day from 08:00 to 18:00. Session 8 ends at 16:00 and Session 10 ends at 18:00 to honor the student session cutoffs. If a baseline includes a `Time Range` column, its start time is mapped to the nearest session start; otherwise `Session 1` through `Session 10` map to the corresponding session.

For university workbook schedules, choose one session for every included semester: morning or afternoon. Morning-semester offerings must start at 08:00; afternoon offerings must fit within 13:00-18:00. These are hard CP-SAT constraints and are independently checked by H16. Student assignments remain best-effort: Stage B maximizes placed selections and the report lists unplaced choices with likely causes. Morning offerings all start together at 08:00, so student conflicts may make 100% allocation impossible.

The packaged workbook parser creates two representative student records per cohort (48 total in the Semester 6 filter). They are not individual university enrolment records. The bundled timetable CSV has 308 baseline assignments, leaving 10 of 318 sections without an entry. Independent validation currently finds 123 H5 lab-to-classroom mismatches. The workbook and bundled CSV do not provide enough authoritative room-use data to determine whether these are mapping errors or actual placements. Do not interpret historical experiment JSON or CSV outputs as current verified optimization results; create a new run after correcting the source room map and use actual student records for allocation claims. Web state is currently in memory only; API requests are serialized within one process, but a restart clears uploaded and optimized session data. Multi-worker deployment requires shared persistence and coordination.

Synthetic schedules that do not provide semester session settings retain the existing per-student daily category behavior, including extended-session lunch constraints.

## Assignment modes

| Mode | Meaning |
|---|---|
| `fixed` | Hard constraint (H10). CP-SAT must keep time/room/faculty. |
| `preferred` | Soft preference. Change incurs objective cost (S8). Warm-started as a hint. |
| `flexible` | Hint only; free to move. |

Default for imported baselines: **preferred**.

## CLI examples

```bash
# Validate a CSV folder (including optional timetable.csv)
python main.py validate-csv data/templates

# Import real folder and optimize with CP-SAT
python main.py import data/templates --mode preferred --limit-a 30 --limit-b 20

# Excel allocation + existing timetable baseline
python main.py excel data/your_allocation.xlsx --baseline path/to/timetable.csv --mode fixed
```

## Web UI

1. Open NEXUS (`python main.py web`); the packaged workbook and original baseline load without optimization.
2. Inspect the original baseline and its independent validation findings.
3. Choose the semester and session policy, then click **Optimize timetable** to run CP-SAT.
4. Switch between the original and optimized timetable; compare assignments and export the optimized result.
5. Use actual student records and authoritative room/availability inventories when operational individual allocation or resource claims are required.

## Rules

- Original uploaded files are not overwritten; NEXUS builds a normalized internal dataset.
- Missing required fields produce validation errors — they are never silently filled in.
- Unknown faculty / room / section references in a baseline are rejected unless those values appear in the timetable file itself and attachment is explicitly allowed.
- An empty or timed-out CP-SAT run is never reported as a successful complete timetable.

## API endpoints

- `POST /api/upload-csv` — classic 5 CSVs + optional `timetable`
- `POST /api/upload-excel` — allocation workbook + optional `timetable_file`
- `POST /api/import/preview` — detect columns / suggested mappings
- `POST /api/import/mapped` — mapped multi-file import
- `POST /api/baseline/modes` — reclassify fixed/preferred/flexible
- `GET /api/compare` — original vs optimized report

