# Architecture
```mermaid
flowchart TD
    A[Fixed-schema CSV import + validation] --> B[Canonical data model + SQLite schema]
    G[Synthetic generator S1/S2/S3 for testing] --> B
    B --> E[Google OR-Tools CP-SAT]
    E --> EA[Stage A: section time, room, faculty]
    EA --> EB[Stage B: student-to-section allocation]
    EB --> F[Independent validator]
    F --> M[Metrics and JSON/CSV reporting]
    M --> H[Flask UI and API]
    H --> J[CP-SAT disruption repair]
```
```mermaid
erDiagram
    COURSES ||--o{ COURSE_SESSIONS : has
    COURSES ||--o{ SECTIONS : offered_as
    COURSES ||--o{ STUDENT_SELECTIONS : chosen_in
    STUDENTS ||--o{ STUDENT_SELECTIONS : makes
    FACULTY ||--o{ FACULTY_QUALIFICATIONS : qualified
    COURSES ||--o{ FACULTY_QUALIFICATIONS : taught_by
    FACULTY ||--o{ FACULTY_AVAILABILITY : unavailable
    ROOMS ||--o{ ROOM_AVAILABILITY : unavailable
    TIMETABLE_RUNS ||--o{ ASSIGNMENTS : produces
    TIMETABLE_RUNS ||--o{ ENROLMENTS : produces
```

Timetable generation and student allocation use CP-SAT only. Failed CP-SAT runs are not replaced by heuristic schedules.
Real university Excel/CSV import, optional baseline `timetable.csv`, fixed/preferred/flexible assignment modes,
independent H10 validation, and original-versus-optimized comparison are implemented. Flexible column mapping is
available through `nexus_core.importer` and `/api/import/*`. Full Excel export remains limited (CSV/JSON export work).
