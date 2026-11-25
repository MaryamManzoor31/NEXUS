"""Compare CP-SAT time budgets on representative NEXUS datasets.

Run from the repository root with:
    python experiments/benchmark_solver.py

The benchmark is deterministic at the dataset and seed level. CP-SAT's parallel
search may still produce small run-to-run differences on larger instances.
Results are written under experiments/results/benchmarks/.
"""
from __future__ import annotations

import csv
import json
import os
import platform
import statistics
import sys
from datetime import datetime, timezone

import ortools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from nexus_core.cpsat import cpsat
from nexus_core.data_generator import generate
from nexus_core.excel_parser import parse_allocation_workbook
from nexus_core.metrics import compute
from nexus_core.validator import validate
from web.server import _apply_semester_sessions, _attach_default_baseline


SEED = 329
BUDGETS_SECONDS = (30, 60, 90)


def build_cases():
    def load_university():
        workbook = os.path.join(
            ROOT, "data", "Course - Faculty Allocation - Jan 2025 onwards (30-11-24)(1).xlsx"
        )
        ds, _ = parse_allocation_workbook(workbook, semester_filter="6")
        _apply_semester_sessions(ds, "6", {"6": "auto"})
        _attach_default_baseline(ds, "6")
        return ds

    cases = [
        ("synthetic_S1_20", lambda: generate(20, "S1", SEED)),
        ("synthetic_S3_100", lambda: generate(100, "S3", SEED)),
    ]
    workbook = os.path.join(ROOT, "data", "Course - Faculty Allocation - Jan 2025 onwards (30-11-24)(1).xlsx")
    if os.path.isfile(workbook):
        cases.append(("university_semester6", load_university))
    return cases


def run_case(case_name, factory, budget):
    ds = factory()
    if case_name == "university_semester6" and budget == 90:
        stage_a_limit, stage_b_limit = 50, 35
    else:
        stage_a_limit, stage_b_limit = budget * 0.62, budget * 0.38
    schedule = cpsat(
        ds,
        limit_a=stage_a_limit,
        limit_b=stage_b_limit,
        total_limit=budget,
        seed=SEED,
    )
    report = validate(ds, schedule)
    metrics = compute(ds, schedule)
    return {
        "dataset": case_name,
        "budget_s": budget,
        "sections": len(ds.sections),
        "students": len(ds.students),
        "stage_a_status": schedule.info.get("stage_a_status", schedule.status),
        "stage_b_status": schedule.info.get("status_b", "NOT_RUN"),
        "validation_status": report.status,
        "scheduled_sections": len(ds.sections) - len(report.unscheduled),
        "total_sections": len(ds.sections),
        "placed_selections": metrics["placed_selections"],
        "total_selections": metrics["total_selections"],
        "hard_constraint_violations": len(report.violations),
        "violations": [
            {"rule": rule, "message": message}
            for rule, message in report.violations
        ],
        "workload_std_hours": metrics["faculty_load_std_h"],
        "runtime_s": round(schedule.runtime, 3),
        "best_bound_stage_a": schedule.info.get("best_bound"),
        "objective_stage_a": schedule.info.get("objective"),
        "best_bound_stage_b": schedule.info.get("stage_b_best_bound"),
        "objective_stage_b": schedule.info.get("stage_b_objective"),
        "complete_allocation_status": schedule.info.get("complete_allocation_status"),
    }


def summarize(rows):
    output = []
    for budget in BUDGETS_SECONDS:
        group = [row for row in rows if row["budget_s"] == budget]
        output.append({
            "budget_s": budget,
            "instances": len(group),
            "instances_zero_hard_violations": sum(
                row["hard_constraint_violations"] == 0 for row in group
            ),
            "total_scheduled_sections": sum(row["scheduled_sections"] for row in group),
            "total_sections": sum(row["total_sections"] for row in group),
            "total_placed_selections": sum(row["placed_selections"] for row in group),
            "total_selections": sum(row["total_selections"] for row in group),
            "total_hard_constraint_violations": sum(
                row["hard_constraint_violations"] for row in group
            ),
            "mean_workload_std_hours": round(
                statistics.mean(row["workload_std_hours"] for row in group), 3
            ) if group else None,
            "mean_runtime_s": round(statistics.mean(row["runtime_s"] for row in group), 3)
            if group else None,
        })
    return output


def main():
    cases = build_cases()
    rows = []
    for name, factory in cases:
        for budget in BUDGETS_SECONDS:
            print(f"Running {name} with {budget}s budget...", flush=True)
            row = run_case(name, factory, budget)
            rows.append(row)
            print(json.dumps(row, sort_keys=True), flush=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = os.path.join(ROOT, "experiments", "results", "benchmarks")
    os.makedirs(out_dir, exist_ok=True)
    payload = {
        "benchmark_id": timestamp,
        "seed": SEED,
        "budgets_s": list(BUDGETS_SECONDS),
        "ortools_version": ortools.__version__,
        "python_version": platform.python_version(),
        "instances": rows,
        "summary": summarize(rows),
    }
    json_path = os.path.join(out_dir, f"solver_comparison_{timestamp}.json")
    csv_path = os.path.join(out_dir, f"solver_comparison_{timestamp}.csv")
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"JSON report: {json_path}")
    print(f"CSV report: {csv_path}")
    print("Summary:")
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
