# NEXUS

AI-based university timetable generation aligned with NEP 2020 multidisciplinary structures.

**Optimization engine:** Google OR-Tools **CP-SAT only** (constraint-based AI optimization — not machine learning).

## Quick start

```bash
cd NEXUS
pip install ortools flask
python -m pytest -q
python main.py web
```

Open http://127.0.0.1:5000

## Real university data (primary workflow)

1. Prepare CSV files (templates in `data/templates/`), **or** use the university allocation Excel workbook under `data/`.
2. Optionally include `timetable.csv` with the **existing** timetable (faculty, room, day/period, section, school/stream metadata).
3. Mark assignments as `fixed`, `preferred`, or `flexible`.
4. Run CP-SAT; compare original vs optimized; export CSV.

```bash
# CSV folder with optional baseline timetable
python main.py validate-csv data/templates
python main.py import data/templates --mode preferred

# Excel allocation + baseline timetable
python main.py excel "data/Course - Faculty Allocation - Jan 2025 onwards (30-11-24)(1).xlsx" --baseline experiments/results/timetable_univ_jan2025_sem_6.csv
```

CSV upload remains available in the web UI (Upload File).

Details: [`docs/REAL_DATA_IMPORT.md`](docs/REAL_DATA_IMPORT.md)

## Synthetic testing

```bash
python main.py optimize --scenario S3 --students 100 --seed 329
```

## Key modules

| Module | Role |
|---|---|
| `nexus_core/cpsat.py` | Stage A scheduling + Stage B student allocation (CP-SAT) |
| `nexus_core/importer.py` | Flexible CSV/Excel mapping + baseline timetable |
| `nexus_core/validator.py` | Independent hard-constraint validation |
| `nexus_core/compare.py` | Original vs optimized report |
| `web/server.py` | Flask UI / API |

## Documentation

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/CONSTRAINTS.md`](docs/CONSTRAINTS.md)
- [`docs/REAL_DATA_IMPORT.md`](docs/REAL_DATA_IMPORT.md)
