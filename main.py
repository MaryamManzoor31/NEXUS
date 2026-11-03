"""NEXUS command line.  Use `python main.py optimize|export-csv|validate-csv|import|excel|web`."""
import argparse, json, os, sys
from nexus_core.data_generator import generate
from nexus_core.cpsat import cpsat
from nexus_core.metrics import compute
from nexus_core.validator import validate
from nexus_core.input_validator import load_csv, save_csv, check_dataset
from nexus_core.importer import import_folder, load_timetable_csv
from nexus_core.compare import compare_schedules
from nexus_core.models import Faculty, PREFERRED, FIXED, FLEXIBLE
from nexus_core import db


def _qualify(ds, sid, fid):
    f = ds.faculty[fid]
    ds.faculty[fid] = Faculty(
        id=f.id, name=f.name,
        qualified=f.qualified | {ds.sections[sid].course_id},
        max_hours=f.max_hours, unavailable=f.unavailable,
        school_id=f.school_id, department_id=f.department_id, designation=f.designation,
    )


def main():
    # Each subcommand selects one operation and its command-line options.
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("optimize", aliases=["compare"], help="generate a SYNTHETIC instance and run CP-SAT")
    g.add_argument("--students", type=int, default=100); g.add_argument("--scenario", default="S3", choices=["S1", "S2", "S3"])
    g.add_argument("--seed", type=int, default=329)
    g.add_argument("--limit-a", type=int, default=30); g.add_argument("--limit-b", type=int, default=20)
    g.add_argument("--out", default="experiments/results"); g.add_argument("--db", default=None)
    e = sub.add_parser("export-csv", help="write a synthetic instance as CSV files (data/synthetic/<name>)")
    e.add_argument("--students", type=int, default=100); e.add_argument("--scenario", default="S3"); e.add_argument("--seed", type=int, default=329)
    v = sub.add_parser("validate-csv", help="load + validate a CSV folder; bad records are reported and rejected")
    v.add_argument("folder")
    imp = sub.add_parser("import", help="import real university CSV/Excel folder (optional timetable baseline) and run CP-SAT")
    imp.add_argument("folder", help="folder containing courses/sections/faculty/rooms/students and optional timetable.csv")
    imp.add_argument("--name", default=None)
    imp.add_argument("--mode", default=PREFERRED, choices=[FIXED, PREFERRED, FLEXIBLE],
                     help="default baseline assignment mode when timetable.csv is present")
    imp.add_argument("--limit-a", type=int, default=30); imp.add_argument("--limit-b", type=int, default=20)
    imp.add_argument("--out", default="experiments/results")
    imp.add_argument("--no-optimize", action="store_true", help="validate/import only; do not run CP-SAT")
    w = sub.add_parser("web", help="start the interactive web timetable dashboard")
    w.add_argument("--port", type=int, default=5000); w.add_argument("--host", default="127.0.0.1")
    x = sub.add_parser("excel", help="load a university allocation Excel file, allocate members, and generate timetable")
    x.add_argument("file", help="path to the .xlsx workbook")
    x.add_argument("--sem", default="6", help="semester filter: 2, 4, 6, 8, or all (default: 6)")
    x.add_argument("--allocate-members", action="store_true", default=True, help="allocate unassigned faculty members")
    x.add_argument("--baseline", default=None, help="optional existing timetable CSV used as optimization baseline")
    x.add_argument("--mode", default=PREFERRED, choices=[FIXED, PREFERRED, FLEXIBLE])
    x.add_argument("--out", default="experiments/results", help="output directory for results")
    a = ap.parse_args()
    if a.cmd == "web":
        from web.server import app
        print(f"\nNEXUS Web App running at http://{a.host}:{a.port}\n")
        app.run(host=a.host, port=a.port, debug=False)
    elif a.cmd == "excel":
        from nexus_core.excel_parser import parse_allocation_workbook
        from nexus_core.member_allocator import allocate_faculty_members
        print(f"\n[EXCEL INGESTION] Reading: {a.file} (Semester: {a.sem})")
        ds, meta = parse_allocation_workbook(a.file, semester_filter=a.sem)
        print(f"Loaded: {len(ds.courses)} courses, {len(ds.sections)} sections, {len(ds.faculty)} faculty, {len(ds.rooms)} rooms")
        print(f"Pre-assigned sections: {meta['total_pre_assigned']} | Unassigned: {meta['total_unassigned']}")

        if a.allocate_members:
            alloc = allocate_faculty_members(ds, meta["pre_assigned_faculty"], meta["raw_faculty_info"])
            print(f"[FACULTY ALLOCATION] Active faculty: {alloc.stats['active_faculty_count']} | Workload utilization: {alloc.stats['overall_utilization_pct']}%")
            for sid, fid in alloc.faculty_assignments.items():
                if fid in ds.faculty and sid in ds.sections:
                    _qualify(ds, sid, fid)

        if a.baseline:
            result = load_timetable_csv(
                a.baseline, ds=ds, default_mode=a.mode, allow_resources_from_timetable=True
            )
            for i in result.issues:
                print(i)
            if result.dataset is None:
                print("REJECTED: baseline timetable could not be attached")
                sys.exit(1)
            print(f"[BASELINE] Attached {result.summary.get('baseline_assignments', 0)} assignments (mode={a.mode})")

        print("[TIMETABLE SOLVER] Running CP-SAT...")
        sch = cpsat(ds, limit_a=30, limit_b=20, seed=329)
        rep = validate(ds, sch)
        met = compute(ds, sch)
        print(f"Solver Status: {sch.status} | Validator: {rep.status}")
        print(f"Scheduled sections: {met['scheduled_sections']} | Room utilization: {met['room_utilization_pct']}%")
        print(f"Hard constraint violations: {len(rep.violations)}")
        if ds.baseline and sch.status in ("OPTIMAL", "FEASIBLE"):
            cmp = compare_schedules(ds, ds.baseline_schedule(), sch)
            print(f"[COMPARE] moved={len(cmp.moved_classes)} faculty_changes={len(cmp.faculty_changes)} room_changes={len(cmp.room_changes)}")
            for note in cmp.notes:
                print(" ", note)

        os.makedirs(a.out, exist_ok=True)
        base = os.path.join(a.out, f"timetable_{ds.name}")
        from web.serializer import generate_timetable_csv
        with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
            f.write(generate_timetable_csv(ds, sch))
        print(f"Timetable saved to: {base}.csv\n")
    elif a.cmd == "import":
        result = import_folder(a.folder, name=a.name, default_assignment_mode=a.mode)
        for i in result.issues:
            print(i)
        if result.dataset is None:
            print("REJECTED")
            sys.exit(1)
        ds = result.dataset
        print(f"LOADED summary: {result.summary}")
        if a.no_optimize:
            sys.exit(0)
        print("[TIMETABLE SOLVER] Running CP-SAT on imported real dataset...")
        sch = cpsat(ds, a.limit_a, a.limit_b, seed=329)
        rep = validate(ds, sch)
        met = compute(ds, sch)
        print(json.dumps(met, indent=2))
        os.makedirs(a.out, exist_ok=True)
        base = os.path.join(a.out, f"timetable_{ds.name}")
        from web.serializer import generate_timetable_csv
        with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
            f.write(generate_timetable_csv(ds, sch))
        if ds.baseline and sch.status in ("OPTIMAL", "FEASIBLE"):
            cmp = compare_schedules(ds, ds.baseline_schedule(), sch)
            with open(base + "_compare.json", "w", encoding="utf-8") as f:
                json.dump(cmp.to_dict(), f, indent=2)
            print("saved", base + "_compare.json")
        print("saved", base + ".csv")
    elif a.cmd == "export-csv":
        # Generate a dataset and write its tables as CSV files.
        ds = generate(a.students, a.scenario, a.seed); path = os.path.join("data", "synthetic", ds.name)
        save_csv(ds, path); print("wrote", path)
    elif a.cmd == "validate-csv":
        # Report validation issues and return a failing exit code for rejected input.
        ds, iss = load_csv(a.folder)
        for i in iss: print(i)
        print("REJECTED" if ds is None else f"LOADED {len(ds.courses)} courses, {len(ds.sections)} sections, {len(ds.students)} students")
        if ds is not None and ds.baseline:
            print(f"BASELINE assignments: {len(ds.baseline)}")
        sys.exit(1 if ds is None else 0)
    else:
        # Run CP-SAT, persist run details, and save a JSON summary.
        ds = generate(a.students, a.scenario, a.seed)
        print(f"[SYNTHETIC] {ds.name}: {len(ds.courses)} courses, {len(ds.sections)} sections, {len(ds.faculty)} faculty, {len(ds.rooms)} rooms, {len(ds.students)} students")
        sch = cpsat(ds, a.limit_a, a.limit_b, a.seed)
        os.makedirs(a.out, exist_ok=True)
        con = db.connect(a.db or ":memory:"); db.save_dataset(con, ds)
        metrics = compute(ds, sch)
        db.save_run(con, ds, sch, validate(ds, sch))
        rows = [metrics]
        print(json.dumps(metrics))
        base = os.path.join(a.out, f"{ds.name}")
        json.dump({"dataset": ds.name, "synthetic": True, "ortools": __import__("ortools").__version__, "results": rows}, open(base + ".json", "w"), indent=1, default=list)
        print("saved", base + ".json")


if __name__ == "__main__":
    main()
