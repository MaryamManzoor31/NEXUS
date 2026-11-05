# Architecture
```mermaid
flowchart TD
    User[User] --> CLI[CLI: main.py]
    User --> Browser[Browser]
    Browser --> UI[Web UI: HTML, CSS, JavaScript]
    UI <--> API[Flask UI and REST API]
    API --> Original[Load and display original baseline]
    UI -->|explicit Optimize action| Optimize[CP-SAT optimization request]

    subgraph Inputs[Data sources]
        CSV[CSV files and optional baseline timetable]
        Excel[University allocation workbook]
        Synthetic[Synthetic data generator]
    end

    CSV --> Import[CSV loader and flexible importer]
    Excel --> Parser[Excel allocation parser]
    Synthetic --> Generator[Synthetic dataset generator]
    CLI --> Import
    CLI --> Parser
    CLI --> Generator
    API --> Import
    API --> Parser
    API --> Generator
    Import --> Model[Canonical Dataset and Schedule models]
    Parser --> Model
    Generator --> Model

    subgraph Core[NEXUS core]
        Model --> InputCheck[Input and dataset validation]
        Model --> Solver[Google OR-Tools CP-SAT]
        Solver --> StageA[Stage A: section time, room, faculty]
        StageA --> StageB[Stage B: student-to-section allocation]
        StageB --> Schedule[Optimized schedule]
        Schedule --> Validator[Independent schedule validator]
        Schedule --> Metrics[Metrics]
    Original --> Compare[Baseline comparison]
    Schedule --> Compare
    end

    InputCheck --> Solver
    Schedule --> Serializer[Web serializer]
    Validator --> Serializer
    Metrics --> Serializer
    Compare --> Serializer
    Serializer --> API
    API --> UI

    CLI --> Persistence[Optional SQLite run persistence]
    Persistence --> DB[(SQLite)]
    API --> State[In-memory web run state]
    State --> Serializer
    CLI --> Reports[CSV and JSON reports]
    Serializer --> Reports
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

The web startup path parses the packaged workbook and attaches the original baseline only. `/api/current` and `/api/original` do not invoke CP-SAT. An explicit optimization request runs Stage A and Stage B and stores its result separately from the baseline in web state. The web app currently stores active state in process memory and serializes API access with a process-local lock; it does not yet persist uploads or runs through SQLite, so restarts clear the active imported/optimized state. Multi-worker deployment requires shared persistence/coordination. No alternative timetable construction or fallback is used. For generated datasets over 30 sections, optional pairwise conflict and back-to-back teaching preferences are omitted to control model build time; resource, qualification, workload, session, and allocation constraints remain hard. The workbook's two representative student rows per cohort and estimated room/section capacities are labeled in the UI; they are not authoritative enrolment or inventory data.

