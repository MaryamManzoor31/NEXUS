# NEXUS Timetable Generator

NEXUS builds and validates university timetables with Google OR-Tools CP-SAT. The solver schedules sections first, then assigns students to the scheduled course sections while enforcing timetable constraints.

## Requirements

- Python 3.10 or newer
- Packages listed in [`requirements.txt`](requirements.txt)

## Install and start

From the project directory:

```bash
python -m venv .venv
```

Activate the virtual environment, then install dependencies and start the dashboard:

```bash
python -m pip install -r requirements.txt
python main.py web
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001). Stop the server with `Ctrl+C`.

You can also start the web app with `python web_app.py`; that entry point uses port `5002`.

## Use the dashboard

1. Choose the dataset and semester. For each included semester, choose automatic, morning, or afternoon scheduling.
2. Click **Optimize timetable** to run CP-SAT.
3. Review the section and student views, then open **Diagnostics** for solver status, stage runtimes, unscheduled sections, unplaced student selections, and likely resource blockers.
4. Use the export controls to download the timetable.

The dashboard opens on the source baseline when one is available. Loading the page alone does not optimize the timetable or assign students; run optimization to create a CP-SAT schedule.

### Solver time limits

The packaged Excel workflow can use up to 90 seconds total: up to 50 seconds for section scheduling and 35 seconds for student allocation. Other solver workflows use a 30-second default unless configured otherwise.

The solver may return a feasible partial timetable when it cannot place everything. **FEASIBLE** means it found a valid schedule, not necessarily that it proved an optimal one. An **OPTIMAL** student-allocation stage can still leave selections unplaced when no complete allocation fits the sections and hard constraints in that run. Diagnostics shows these remaining sections and selections.

### Scheduling rules

Student day categories are assigned from required class duration. Morning and afternoon days are limited to five class hours; extended days use an 8 AM–4 PM or 10 AM–6 PM window with a protected lunch break. Student overlap and maximum waiting-gap rules are enforced by the solver. See [`docs/CONSTRAINTS.md`](docs/CONSTRAINTS.md) for the full constraint list and time-slot details.

## Use university data

### Excel workbook

The dashboard includes the packaged January 2025 allocation workbook. From the command line, provide a workbook path:

```bash
python main.py excel "data/Course - Faculty Allocation - Jan 2025 onwards (30-11-24)(1).xlsx" --sem 6
```

You can attach an existing timetable as the optimization baseline:

```bash
python main.py excel "data/Course - Faculty Allocation - Jan 2025 onwards (30-11-24)(1).xlsx" --sem 6 --baseline experiments/results/timetable_univ_jan2025_sem_6.csv
```

### CSV folder

CSV folders use the templates in [`data/templates/`](data/templates/). The template rows are examples; replace them with your own data.

```bash
python main.py validate-csv data/templates
python main.py import data/templates --mode preferred
```

See [`docs/REAL_DATA_IMPORT.md`](docs/REAL_DATA_IMPORT.md) for accepted fields and baseline assignment modes.

## Synthetic example

Generate and optimize a synthetic instance:

```bash
python main.py optimize --scenario S3 --students 100 --seed 329
```

Supported scenarios are `S1`, `S2`, and `S3`.

## Project structure

| Path | Purpose |
|---|---|
| `nexus_core/cpsat.py` | CP-SAT section scheduling and student allocation |
| `nexus_core/validator.py` | Independent hard-constraint validation |
| `nexus_core/importer.py` | CSV import and baseline timetable handling |
| `nexus_core/excel_parser.py` | University workbook parsing |
| `web/server.py` | Flask routes and solver configuration |
| `web/templates/` and `web/static/` | Dashboard interface |
| `tests/` | Automated checks |

Workbook-generated student records are representative cohort records, not actual individual enrolments. Workbook-derived section and room capacities may be estimates, and missing availability data means unknown availability. The packaged baseline also has unresolved laboratory-to-classroom H5 mismatches; see [`docs/CONSTRAINTS.md`](docs/CONSTRAINTS.md).

## More documentation

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/CONSTRAINTS.md`](docs/CONSTRAINTS.md)
- [`docs/REAL_DATA_IMPORT.md`](docs/REAL_DATA_IMPORT.md)
- [`docs/AUDIT_REPORT.md`](docs/AUDIT_REPORT.md)
