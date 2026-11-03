# Real University Dataset Import

NEXUS accepts **real university data** as the primary optimization input. Synthetic S1/S2/S3 data remains available for testing only.

## Supported input methods

| Method | How | Notes |
|---|---|---|
| A. Packaged university Excel | UI “Jan 2025 University Allocation” or `python main.py excel <file.xlsx>` | Course–faculty allocation workbook |
| B. CSV / Excel upload | UI Upload dialog or `python main.py import <folder>` | Canonical CSVs + optional `timetable.csv` |
| C. Synthetic | UI S1/S2/S3 or `python main.py optimize` | Development / benchmarks only |

CSV upload remains fully supported.

The packaged allocation-workbook importer models each discovered lab room with
capacity for 80 students. For mapped CSV/Excel imports, room capacities are read
from the supplied room table.

## Canonical CSV files

Templates live in `data/templates/`:

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
- students: `student_id,programme,selections`

### Optional institutional columns

`school_id`, `department_id`, `programme_id`, `stream`, `semester`, `academic_year`, `course_type`, `batch`, `designation`, `building`

These enrich reporting and NEP multidisciplinary context. They are **not invented** when absent.
Sections may also provide an optional `session_pattern` such as `2:LAB` to preserve a
course allocation's session type when it differs from the course's default pattern.
In the section timetable view, course allocations with the same semester and class
section name are shown together; a trailing `Lab` or `Practical` suffix does not make
a separate displayed class section. A comma-separated class label shares that course
allocation with each named section in the section timetable.

### Baseline timetable columns

`Day, Period, Section, Room, Faculty ID` are required (aliases accepted). Optional: `mode` (`fixed` / `preferred` / `flexible`), `session_index`, course metadata, school/stream.

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

1. Open NEXUS (`python main.py web`)
2. Upload Excel and/or CSV files (optional timetable baseline)
3. Generate a timetable, then choose the semester and university class section (for example AIML A, Gen C, DA A, IT Gen, or IT CCIT)
4. View all of that class section's course allocations in the weekly calendar or tabular layout
5. Apply a fixed / preferred / flexible baseline policy to the selected class section's course allocations, or temporarily block a room/faculty member and repair the schedule
6. CP-SAT keeps core hard constraints enabled; the original timetable is preserved for comparison
7. Export optimized timetable as CSV

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
