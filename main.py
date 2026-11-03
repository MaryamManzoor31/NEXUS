"""NEXUS command line.  Use `python main.py optimize|export-csv|validate-csv|excel|web`."""
import argparse, csv, json, os, sys
from nexus_core.data_generator import generate
from nexus_core.cpsat import cpsat
from nexus_core.metrics import compute
from nexus_core.validator import validate
from nexus_core.input_validator import load_csv, save_csv, check_dataset
from nexus_core import db


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
    w = sub.add_parser("web", help="start the interactive web timetable dashboard")
    w.add_argument("--port", type=int, default=5000); w.add_argument("--host", default="127.0.0.1")
    x = sub.add_parser("excel", help="load a university allocation Excel file, allocate members, and generate timetable")
    x.add_argument("file", help="path to the .xlsx workbook")
    x.add_argument("--sem", default="6", help="semester filter: 2, 4, 6, 8, or all (default: 6)")
    x.add_argument("--allocate-members", action="store_true", default=True, help="allocate unassigned faculty members")
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
                if fid in ds.faculty:
                    ds.faculty[fid] = ds.faculty[fid].__class__(
                        id=ds.faculty[fid].id,
                        name=ds.faculty[fid].name,
                        qualified=ds.faculty[fid].qualified | {ds.sections[sid].course_id},
                        max_hours=ds.faculty[fid].max_hours,
                        unavailable=ds.faculty[fid].unavailable
                    )

        print("[TIMETABLE SOLVER] Running CP-SAT...")
        sch = cpsat(ds, limit_a=30, limit_b=20, seed=329)
        rep = validate(ds, sch)
        met = compute(ds, sch)
        print(f"Solver Status: {sch.status} | Validator: {rep.status}")
        print(f"Scheduled sections: {met['scheduled_sections']} | Room utilization: {met['room_utilization_pct']}%")
        print(f"Hard constraint violations: {len(rep.violations)}")

        os.makedirs(a.out, exist_ok=True)
        base = os.path.join(a.out, f"timetable_{ds.name}")
        from web.serializer import generate_timetable_csv
        with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
            f.write(generate_timetable_csv(ds, sch))
        print(f"Timetable saved to: {base}.csv\n")
    elif a.cmd == "export-csv":
        # Generate a dataset and write its tables as CSV files.
        ds = generate(a.students, a.scenario, a.seed); path = os.path.join("data", "synthetic", ds.name)
        save_csv(ds, path); print("wrote", path)
    elif a.cmd == "validate-csv":
        # Report validation issues and return a failing exit code for rejected input.
        ds, iss = load_csv(a.folder)
        for i in iss: print(i)
        print("REJECTED" if ds is None else f"LOADED {len(ds.courses)} courses, {len(ds.sections)} sections, {len(ds.students)} students")
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
