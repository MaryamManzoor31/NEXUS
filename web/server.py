"""Flask server for NEXUS Timetable Generator Web Application."""
from __future__ import annotations
import os
import json
import tempfile
import shutil
from flask import Flask, request, jsonify, render_template, send_from_directory, Response

from nexus_core.models import Dataset, Schedule
from nexus_core.data_generator import generate
from nexus_core.cpsat import cpsat, stage_a, stage_b
from nexus_core.validator import validate
from nexus_core.metrics import compute
from nexus_core.input_validator import load_csv, check_dataset
from nexus_core.excel_parser import parse_allocation_workbook
from nexus_core.member_allocator import allocate_faculty_members
from web.serializer import serialize_schedule, generate_timetable_csv

app = Flask(__name__, template_folder="templates", static_folder="static")

DEFAULT_EXCEL_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "data", "Course - Faculty Allocation - Jan 2025 onwards (30-11-24)(1).xlsx"
))

# Current in-memory state
STATE = {
    "dataset": None,
    "schedule": None,
    "active_method": "cpsat",
    "meta": {},
    "alloc_result": None,
}


def _ensure_default_dataset():
    if STATE["dataset"] is None:
        if os.path.isfile(DEFAULT_EXCEL_PATH):
            try:
                ds, meta = parse_allocation_workbook(DEFAULT_EXCEL_PATH, semester_filter="6")
                alloc = allocate_faculty_members(ds, meta["pre_assigned_faculty"], meta["raw_faculty_info"])
                # Apply allocations
                for sid, fid in alloc.faculty_assignments.items():
                    if fid in ds.faculty:
                        ds.faculty[fid] = ds.faculty[fid].__class__(
                            id=ds.faculty[fid].id,
                            name=ds.faculty[fid].name,
                            qualified=ds.faculty[fid].qualified | {ds.sections[sid].course_id},
                            max_hours=ds.faculty[fid].max_hours,
                            unavailable=ds.faculty[fid].unavailable
                        )
                sch = cpsat(ds, limit_a=15, limit_b=10, seed=329)
                STATE["dataset"] = ds
                STATE["schedule"] = sch
                STATE["meta"] = meta
                STATE["alloc_result"] = alloc
                STATE["active_method"] = "cpsat"
                return
            except Exception as e:
                print(f"[NEXUS] Default Excel load notice: {e}, falling back to synthetic S1")
        # Fallback: generate demo dataset S1
        ds = generate(20, "S1", 329)
        sch = cpsat(ds, limit_a=15, limit_b=10, seed=329)
        STATE["dataset"] = ds
        STATE["schedule"] = sch
        STATE["active_method"] = "cpsat"


@app.route("/")
def index():
    _ensure_default_dataset()
    return render_template("index.html")


@app.route("/api/current")
def get_current():
    _ensure_default_dataset()
    ds = STATE["dataset"]
    sch = STATE["schedule"]
    report = validate(ds, sch)
    metrics = compute(ds, sch)
    data = serialize_schedule(ds, sch, report, metrics)
    return jsonify({
        "success": True,
        "data": data,
        "active_method": STATE.get("active_method", "cpsat"),
        "is_excel": bool(ds.meta.get("source_file"))
    })


@app.route("/api/generate", methods=["POST"])
def api_generate():
    body = request.get_json(force=True, silent=True) or {}
    scenario = body.get("scenario", "S1")
    students = int(body.get("students", 20))
    seed = int(body.get("seed", 329))
    algorithm = body.get("algorithm", "cpsat")
    limit_a = int(body.get("limit_a", 15))
    limit_b = int(body.get("limit_b", 10))
    if algorithm != "cpsat":
        return jsonify({"success": False, "error": "Only CP-SAT timetable generation is supported."}), 400

    try:
        ds = generate(students, scenario, seed)
        sch = cpsat(ds, limit_a=limit_a, limit_b=limit_b, seed=seed)

        STATE["dataset"] = ds
        STATE["schedule"] = sch
        STATE["active_method"] = algorithm

        report = validate(ds, sch)
        metrics = compute(ds, sch)
        data = serialize_schedule(ds, sch, report, metrics)

        return jsonify({
            "success": True,
            "data": data,
            "active_method": "cpsat"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/load-excel", methods=["POST"])
def api_load_excel():
    """Load real university allocation Excel spreadsheet with chosen semester filter."""
    body = request.get_json(force=True, silent=True) or {}
    semester = str(body.get("semester", "6"))
    algorithm = body.get("algorithm", "cpsat")
    limit_a = int(body.get("limit_a", 15))
    limit_b = int(body.get("limit_b", 10))
    allocate_members = body.get("allocate_members", True)
    if algorithm != "cpsat":
        return jsonify({"success": False, "error": "Only CP-SAT timetable generation is supported."}), 400

    if not os.path.isfile(DEFAULT_EXCEL_PATH):
        return jsonify({"success": False, "error": f"Excel file not found at {DEFAULT_EXCEL_PATH}"}), 404

    try:
        ds, meta = parse_allocation_workbook(DEFAULT_EXCEL_PATH, semester_filter=semester)
        alloc_res = None
        if allocate_members:
            alloc_res = allocate_faculty_members(ds, meta["pre_assigned_faculty"], meta["raw_faculty_info"])
            # Apply allocations
            for sid, fid in alloc_res.faculty_assignments.items():
                if fid in ds.faculty:
                    ds.faculty[fid] = ds.faculty[fid].__class__(
                        id=ds.faculty[fid].id,
                        name=ds.faculty[fid].name,
                        qualified=ds.faculty[fid].qualified | {ds.sections[sid].course_id},
                        max_hours=ds.faculty[fid].max_hours,
                        unavailable=ds.faculty[fid].unavailable
                    )

        sch = cpsat(ds, limit_a=limit_a, limit_b=limit_b, seed=329)

        STATE["dataset"] = ds
        STATE["schedule"] = sch
        STATE["meta"] = meta
        STATE["alloc_result"] = alloc_res
        STATE["active_method"] = "cpsat"

        report = validate(ds, sch)
        metrics = compute(ds, sch)
        data = serialize_schedule(ds, sch, report, metrics)

        return jsonify({
            "success": True,
            "data": data,
            "active_method": "cpsat",
            "allocation_stats": alloc_res.stats if alloc_res else None
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/upload-excel", methods=["POST"])
def api_upload_excel():
    """Upload and schedule any university allocation .xlsx spreadsheet."""
    excel_file = request.files.get("excel_file")
    if not excel_file or not excel_file.filename:
        return jsonify({"success": False, "error": "No Excel file provided"}), 400

    semester = request.form.get("semester", "6")
    algorithm = request.form.get("algorithm", "cpsat")
    limit_a = int(request.form.get("limit_a", 15))
    limit_b = int(request.form.get("limit_b", 10))
    if algorithm != "cpsat":
        return jsonify({"success": False, "error": "Only CP-SAT timetable generation is supported."}), 400

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", prefix="nexus_upload_", delete=False) as upload:
            temp_path = upload.name
        excel_file.save(temp_path)
        ds, meta = parse_allocation_workbook(temp_path, semester_filter=semester)
        alloc_res = allocate_faculty_members(ds, meta["pre_assigned_faculty"], meta["raw_faculty_info"])
        for sid, fid in alloc_res.faculty_assignments.items():
            if fid in ds.faculty:
                ds.faculty[fid] = ds.faculty[fid].__class__(
                    id=ds.faculty[fid].id,
                    name=ds.faculty[fid].name,
                    qualified=ds.faculty[fid].qualified | {ds.sections[sid].course_id},
                    max_hours=ds.faculty[fid].max_hours,
                    unavailable=ds.faculty[fid].unavailable
                )

        sch = cpsat(ds, limit_a=limit_a, limit_b=limit_b, seed=329)

        STATE["dataset"] = ds
        STATE["schedule"] = sch
        STATE["meta"] = meta
        STATE["alloc_result"] = alloc_res
        STATE["active_method"] = "cpsat"

        report = validate(ds, sch)
        metrics = compute(ds, sch)
        data = serialize_schedule(ds, sch, report, metrics)

        return jsonify({
            "success": True,
            "data": data,
            "allocation_stats": alloc_res.stats
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@app.route("/api/allocate-members", methods=["POST"])
def api_allocate_members():
    """Trigger the faculty member allocation engine on active dataset."""
    if STATE["dataset"] is None:
        return jsonify({"success": False, "error": "No active dataset loaded"}), 400
    ds = STATE["dataset"]
    meta = STATE.get("meta", {})
    try:
        alloc_res = allocate_faculty_members(
            ds,
            meta.get("pre_assigned_faculty", {}),
            meta.get("raw_faculty_info", {})
        )
        STATE["alloc_result"] = alloc_res
        
        # Apply assignments
        for sid, fid in alloc_res.faculty_assignments.items():
            if fid in ds.faculty:
                ds.faculty[fid] = ds.faculty[fid].__class__(
                    id=ds.faculty[fid].id,
                    name=ds.faculty[fid].name,
                    qualified=ds.faculty[fid].qualified | {ds.sections[sid].course_id},
                    max_hours=ds.faculty[fid].max_hours,
                    unavailable=ds.faculty[fid].unavailable
                )

        # Re-solve schedule with updated allocations
        sch = cpsat(ds, limit_a=15, limit_b=10, seed=329)
        STATE["schedule"] = sch

        report = validate(ds, sch)
        metrics = compute(ds, sch)
        data = serialize_schedule(ds, sch, report, metrics)
        return jsonify({
            "success": True,
            "data": data,
            "allocation_stats": alloc_res.stats,
            "faculty_summary": alloc_res.faculty_summary
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/load-sample", methods=["POST"])
def load_sample():
    sample_path = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic", "synthetic_S3_100_seed329")
    sample_path = os.path.abspath(sample_path)
    if not os.path.isdir(sample_path):
        return jsonify({"success": False, "error": f"Sample path {sample_path} not found"}), 404

    ds, issues = load_csv(sample_path)
    if ds is None:
        return jsonify({
            "success": False,
            "error": "Failed to load sample dataset",
            "issues": [str(i) for i in issues]
        }), 400

    sch = cpsat(ds, limit_a=15, limit_b=10, seed=329)
    STATE["dataset"] = ds
    STATE["schedule"] = sch
    STATE["active_method"] = "cpsat"

    report = validate(ds, sch)
    metrics = compute(ds, sch)
    data = serialize_schedule(ds, sch, report, metrics)
    return jsonify({
        "success": True,
        "data": data,
        "issues": [str(i) for i in issues]
    })


@app.route("/api/upload-csv", methods=["POST"])
def upload_csv():
    # Expect files: courses, faculty, rooms, sections, students
    temp_dir = tempfile.mkdtemp(prefix="nexus_upload_")
    try:
        saved_files = []
        for key in ["courses", "faculty", "rooms", "sections", "students"]:
            file = request.files.get(key)
            if file and file.filename:
                path = os.path.join(temp_dir, f"{key}.csv")
                file.save(path)
                saved_files.append(key)

        missing = [k for k in ["courses", "faculty", "rooms", "sections", "students"] if k not in saved_files]
        if missing:
            return jsonify({
                "success": False,
                "error": f"Missing required CSV files: {', '.join(missing)}"
            }), 400

        ds, issues = load_csv(temp_dir)
        if ds is None:
            return jsonify({
                "success": False,
                "error": "CSV Validation Failed",
                "issues": [str(i) for i in issues]
            }), 400

        algorithm = request.form.get("algorithm", "cpsat")
        limit_a = int(request.form.get("limit_a", 15))
        limit_b = int(request.form.get("limit_b", 10))
        if algorithm != "cpsat":
            return jsonify({"success": False, "error": "Only CP-SAT timetable generation is supported."}), 400

        sch = cpsat(ds, limit_a=limit_a, limit_b=limit_b, seed=329)

        STATE["dataset"] = ds
        STATE["schedule"] = sch
        STATE["active_method"] = "cpsat"

        report = validate(ds, sch)
        metrics = compute(ds, sch)
        data = serialize_schedule(ds, sch, report, metrics)

        return jsonify({
            "success": True,
            "data": data,
            "issues": [str(i) for i in issues]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.route("/api/disruption", methods=["POST"])
def simulate_disruption():
    """Module M9 - Simulate emergency disruption (e.g. room flooded or faculty emergency leave)."""
    if STATE["dataset"] is None or STATE["schedule"] is None:
        return jsonify({"success": False, "error": "No active schedule to repair"}), 400

    body = request.get_json(force=True, silent=True) or {}
    blocked_rooms = frozenset(body.get("blocked_rooms", []))
    blocked_faculty = frozenset(body.get("blocked_faculty", []))

    ds = STATE["dataset"]
    # Re-run CP-SAT Stage A with blocked resources
    try:
        st_a, sch_a, info = stage_a(
            ds,
            limit=15,
            seed=329,
            blocked_rooms=blocked_rooms,
            blocked_faculty=blocked_faculty
        )
        if st_a in ("OPTIMAL", "FEASIBLE"):
            st_b, _ = stage_b(ds, sch_a, limit=10, seed=329)
            sch_a.info["status_b"] = st_b
        else:
            sch_a.info["status_b"] = "NOT_RUN"
            sch_a.info["status_b_reason"] = f"Stage A ended with {st_a}; no student allocation was attempted."
        sch_b = sch_a
        STATE["schedule"] = sch_b
        STATE["active_method"] = "cpsat-repair"

        report = validate(ds, sch_b)
        metrics = compute(ds, sch_b)
        data = serialize_schedule(ds, sch_b, report, metrics)
        return jsonify({
            "success": True,
            "data": data,
            "blocked_rooms": list(blocked_rooms),
            "blocked_faculty": list(blocked_faculty),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/export/csv")
def export_csv():
    _ensure_default_dataset()
    ds = STATE["dataset"]
    sch = STATE["schedule"]
    csv_text = generate_timetable_csv(ds, sch)
    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=timetable_{ds.name}.csv"}
    )


@app.route("/api/export/json")
def export_json():
    _ensure_default_dataset()
    ds = STATE["dataset"]
    sch = STATE["schedule"]
    report = validate(ds, sch)
    metrics = compute(ds, sch)
    data = serialize_schedule(ds, sch, report, metrics)
    return Response(
        json.dumps(data, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename=timetable_{ds.name}.json"}
    )


def create_app():
    return app


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
