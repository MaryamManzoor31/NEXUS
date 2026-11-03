"""Flask server for NEXUS Timetable Generator Web Application."""
from __future__ import annotations
import os
import json
import tempfile
import shutil
from flask import Flask, request, jsonify, render_template, send_from_directory, Response

from nexus_core.models import Dataset, Schedule, Faculty, PREFERRED
from nexus_core.data_generator import generate
from nexus_core.cpsat import cpsat, stage_a, stage_b
from nexus_core.validator import validate
from nexus_core.metrics import compute
from nexus_core.input_validator import load_csv, check_dataset
from nexus_core.excel_parser import parse_allocation_workbook
from nexus_core.member_allocator import allocate_faculty_members
from nexus_core.importer import import_folder, load_timetable_csv, set_assignment_modes, preview_folder
from nexus_core.compare import compare_schedules
from web.serializer import serialize_schedule, generate_timetable_csv

app = Flask(__name__, template_folder="templates", static_folder="static")

DEFAULT_EXCEL_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "data", "Course - Faculty Allocation - Jan 2025 onwards (30-11-24)(1).xlsx"
))
DEFAULT_BASELINE_CSV = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "experiments", "results", "timetable_univ_jan2025_sem_6.csv"
))
EXCEL_STAGE_A_TIME_LIMIT = 60

# Current in-memory state
STATE = {
    "dataset": None,
    "schedule": None,
    "original_schedule": None,
    "active_method": "cpsat",
    "meta": {},
    "alloc_result": None,
    "comparison": None,
    "import_issues": [],
}


def _qualify_faculty(ds: Dataset, sid: str, fid: str) -> None:
    f = ds.faculty[fid]
    ds.faculty[fid] = Faculty(
        id=f.id,
        name=f.name,
        qualified=f.qualified | {ds.sections[sid].course_id},
        max_hours=f.max_hours,
        unavailable=f.unavailable,
        school_id=f.school_id,
        department_id=f.department_id,
        designation=f.designation,
    )


def _schedule_excel_dataset(
    ds: Dataset,
    limit_b: int = 10,
    limit_a: int = EXCEL_STAGE_A_TIME_LIMIT,
) -> Schedule:
    """Schedule every imported workbook section with enough time for the full model."""
    return cpsat(
        ds,
        limit_a=max(EXCEL_STAGE_A_TIME_LIMIT, limit_a),
        limit_b=limit_b,
        seed=329,
        allow_unscheduled=False,
    )


def _excel_solver_failure(sch: Schedule):
    if sch.status in ("OPTIMAL", "FEASIBLE"):
        return None
    return jsonify({
        "success": False,
        "error": (
            "CP-SAT did not find a complete timetable. "
            f"Stage A ended with {sch.status}; try again or review the imported constraints."
        ),
        "solver_status": sch.status,
    }), 503


def _attach_default_baseline(ds: Dataset, semester: str = "6") -> list[str]:
    """Attach the shipped university timetable CSV when it matches the semester filter."""
    notes = []
    if semester not in ("6", "all"):
        return notes
    if not os.path.isfile(DEFAULT_BASELINE_CSV):
        notes.append("No packaged baseline timetable CSV found.")
        return notes
    result = load_timetable_csv(
        DEFAULT_BASELINE_CSV, ds=ds, default_mode=PREFERRED, allow_resources_from_timetable=True
    )
    notes.extend(str(i) for i in result.issues)
    if result.dataset is not None:
        notes.append(f"Attached baseline timetable with {result.summary.get('baseline_assignments', 0)} assignments.")
    return notes


def _store_run(ds, sch, meta=None, alloc_res=None, issues=None):
    original = ds.baseline_schedule() if ds.baseline else None
    comparison = None
    if original is not None and sch.status in ("OPTIMAL", "FEASIBLE"):
        comparison = compare_schedules(ds, original, sch).to_dict()
    STATE["dataset"] = ds
    STATE["schedule"] = sch
    STATE["original_schedule"] = original
    STATE["comparison"] = comparison
    STATE["meta"] = meta or ds.meta
    STATE["alloc_result"] = alloc_res
    STATE["active_method"] = "cpsat"
    STATE["import_issues"] = issues or []


def _ensure_default_dataset():
    if STATE["dataset"] is None:
        if os.path.isfile(DEFAULT_EXCEL_PATH):
            try:
                ds, meta = parse_allocation_workbook(DEFAULT_EXCEL_PATH, semester_filter="6")
                alloc = allocate_faculty_members(ds, meta["pre_assigned_faculty"], meta["raw_faculty_info"])
                for sid, fid in alloc.faculty_assignments.items():
                    if fid in ds.faculty and sid in ds.sections:
                        _qualify_faculty(ds, sid, fid)
                notes = _attach_default_baseline(ds, "6")
                sch = _schedule_excel_dataset(ds)
                _store_run(ds, sch, meta=meta, alloc_res=alloc, issues=notes)
                return
            except Exception as e:
                print(f"[NEXUS] Default Excel load notice: {e}, falling back to synthetic S1")
        # Fallback: generate demo dataset S1
        ds = generate(20, "S1", 329)
        sch = cpsat(ds, limit_a=15, limit_b=10, seed=329)
        _store_run(ds, sch)


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
        "is_excel": bool(ds.meta.get("source_file")),
        "baseline_count": len(ds.baseline),
        "comparison": STATE.get("comparison"),
        "import_issues": STATE.get("import_issues", []),
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
        _store_run(ds, sch)

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
            for sid, fid in alloc_res.faculty_assignments.items():
                if fid in ds.faculty and sid in ds.sections:
                    _qualify_faculty(ds, sid, fid)

        notes = _attach_default_baseline(ds, semester)
        sch = _schedule_excel_dataset(ds, limit_b=limit_b, limit_a=limit_a)
        failure = _excel_solver_failure(sch)
        if failure:
            return failure
        _store_run(ds, sch, meta=meta, alloc_res=alloc_res, issues=notes)

        report = validate(ds, sch)
        metrics = compute(ds, sch)
        data = serialize_schedule(ds, sch, report, metrics)

        return jsonify({
            "success": True,
            "data": data,
            "active_method": "cpsat",
            "allocation_stats": alloc_res.stats if alloc_res else None,
            "baseline_count": len(ds.baseline),
            "comparison": STATE.get("comparison"),
            "import_issues": notes,
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
    baseline_tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", prefix="nexus_upload_", delete=False) as upload:
            temp_path = upload.name
        excel_file.save(temp_path)
        ds, meta = parse_allocation_workbook(temp_path, semester_filter=semester)
        alloc_res = allocate_faculty_members(ds, meta["pre_assigned_faculty"], meta["raw_faculty_info"])
        for sid, fid in alloc_res.faculty_assignments.items():
            if fid in ds.faculty and sid in ds.sections:
                _qualify_faculty(ds, sid, fid)

        notes = []
        baseline_file = request.files.get("timetable_file") or request.files.get("baseline_file")
        if baseline_file and baseline_file.filename:
            with tempfile.NamedTemporaryFile(suffix=".csv", prefix="nexus_baseline_", delete=False) as bf:
                baseline_tmp = bf.name
            baseline_file.save(baseline_tmp)
            result = load_timetable_csv(
                baseline_tmp, ds=ds, default_mode=PREFERRED, allow_resources_from_timetable=True
            )
            notes.extend(str(i) for i in result.issues)
            if result.dataset is None:
                return jsonify({
                    "success": False,
                    "error": "Baseline timetable validation failed",
                    "issues": notes,
                }), 400
        else:
            notes.extend(_attach_default_baseline(ds, semester))

        sch = _schedule_excel_dataset(ds, limit_b=limit_b, limit_a=limit_a)
        failure = _excel_solver_failure(sch)
        if failure:
            return failure
        _store_run(ds, sch, meta=meta, alloc_res=alloc_res, issues=notes)

        report = validate(ds, sch)
        metrics = compute(ds, sch)
        data = serialize_schedule(ds, sch, report, metrics)

        return jsonify({
            "success": True,
            "data": data,
            "allocation_stats": alloc_res.stats,
            "baseline_count": len(ds.baseline),
            "comparison": STATE.get("comparison"),
            "import_issues": notes,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        for p in (temp_path, baseline_tmp):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
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
        for sid, fid in alloc_res.faculty_assignments.items():
            if fid in ds.faculty and sid in ds.sections:
                _qualify_faculty(ds, sid, fid)

        sch = (
            _schedule_excel_dataset(ds)
            if ds.meta.get("source_file")
            else cpsat(ds, limit_a=15, limit_b=10, seed=329)
        )
        failure = _excel_solver_failure(sch) if ds.meta.get("source_file") else None
        if failure:
            return failure
        _store_run(ds, sch, meta=meta, alloc_res=alloc_res, issues=STATE.get("import_issues", []))

        report = validate(ds, sch)
        metrics = compute(ds, sch)
        data = serialize_schedule(ds, sch, report, metrics)
        return jsonify({
            "success": True,
            "data": data,
            "allocation_stats": alloc_res.stats,
            "faculty_summary": alloc_res.faculty_summary,
            "comparison": STATE.get("comparison"),
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
    _store_run(ds, sch, issues=[str(i) for i in issues])

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
    # Expect files: courses, faculty, rooms, sections, students; optional timetable/baseline CSV.
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

        for key, out_name in (("timetable", "timetable.csv"), ("baseline", "timetable.csv"), ("assignments", "timetable.csv")):
            file = request.files.get(key)
            if file and file.filename:
                file.save(os.path.join(temp_dir, out_name))
                break

        default_mode = request.form.get("assignment_mode", PREFERRED)
        ds, issues = load_csv(temp_dir, default_assignment_mode=default_mode)
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
        _store_run(ds, sch, issues=[str(i) for i in issues])

        report = validate(ds, sch)
        metrics = compute(ds, sch)
        data = serialize_schedule(ds, sch, report, metrics)

        return jsonify({
            "success": True,
            "data": data,
            "issues": [str(i) for i in issues],
            "baseline_count": len(ds.baseline),
            "comparison": STATE.get("comparison"),
            "summary": {
                "courses": len(ds.courses),
                "sections": len(ds.sections),
                "faculty": len(ds.faculty),
                "rooms": len(ds.rooms),
                "students": len(ds.students),
                "baseline_assignments": len(ds.baseline),
            },
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.route("/api/import/preview", methods=["POST"])
def api_import_preview():
    """Upload a mixed CSV/Excel folder-as-files payload and return detected columns + suggested mappings."""
    temp_dir = tempfile.mkdtemp(prefix="nexus_preview_")
    try:
        saved = 0
        for key in request.files:
            f = request.files.get(key)
            if f and f.filename:
                f.save(os.path.join(temp_dir, os.path.basename(f.filename)))
                saved += 1
        if not saved:
            return jsonify({"success": False, "error": "No files uploaded"}), 400
        previews = preview_folder(temp_dir)
        return jsonify({
            "success": True,
            "previews": [
                {
                    "entity": p.entity,
                    "filename": p.filename,
                    "columns": p.columns,
                    "suggested_mapping": p.suggested_mapping,
                    "row_count": p.row_count,
                    "sample_rows": p.sample_rows,
                }
                for p in previews
            ],
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.route("/api/import/mapped", methods=["POST"])
def api_import_mapped():
    """Import mapped CSV/Excel files, validate, optionally optimize with CP-SAT."""
    temp_dir = tempfile.mkdtemp(prefix="nexus_mapped_")
    try:
        body_mappings = request.form.get("mappings")
        mappings = json.loads(body_mappings) if body_mappings else None
        default_mode = request.form.get("assignment_mode", PREFERRED)
        optimize = request.form.get("optimize", "true").lower() != "false"
        limit_a = int(request.form.get("limit_a", 15))
        limit_b = int(request.form.get("limit_b", 10))

        for key in request.files:
            f = request.files.get(key)
            if f and f.filename:
                f.save(os.path.join(temp_dir, os.path.basename(f.filename)))

        result = import_folder(temp_dir, mappings=mappings, default_assignment_mode=default_mode)
        if result.dataset is None:
            return jsonify({
                "success": False,
                "error": "Import validation failed",
                "issues": [str(i) for i in result.issues],
                "summary": result.summary,
                "previews": [
                    {"entity": p.entity, "filename": p.filename, "columns": p.columns,
                     "suggested_mapping": p.suggested_mapping, "row_count": p.row_count}
                    for p in result.previews
                ],
            }), 400

        ds = result.dataset
        payload = {
            "success": True,
            "issues": [str(i) for i in result.issues],
            "summary": result.summary,
            "baseline_count": len(ds.baseline),
        }
        if optimize:
            sch = cpsat(ds, limit_a=limit_a, limit_b=limit_b, seed=329)
            _store_run(ds, sch, issues=[str(i) for i in result.issues])
            report = validate(ds, sch)
            metrics = compute(ds, sch)
            payload["data"] = serialize_schedule(ds, sch, report, metrics)
            payload["comparison"] = STATE.get("comparison")
        else:
            STATE["dataset"] = ds
            STATE["schedule"] = None
            STATE["original_schedule"] = ds.baseline_schedule() if ds.baseline else None
            STATE["import_issues"] = [str(i) for i in result.issues]
            payload["message"] = "Dataset imported; call generate/optimize to run CP-SAT."
        return jsonify(payload)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.route("/api/baseline/modes", methods=["POST"])
def api_baseline_modes():
    """Mark baseline assignments as fixed / preferred / flexible before re-optimizing."""
    if STATE["dataset"] is None:
        return jsonify({"success": False, "error": "No active dataset"}), 400
    body = request.get_json(force=True, silent=True) or {}
    mode = body.get("mode", PREFERRED)
    section_ids = body.get("section_ids")
    reoptimize = bool(body.get("reoptimize", True))
    limit_a = int(body.get("limit_a", 15))
    limit_b = int(body.get("limit_b", 10))
    try:
        set_assignment_modes(STATE["dataset"], mode, section_ids)
        payload = {"success": True, "mode": mode, "baseline_count": len(STATE["dataset"].baseline)}
        if reoptimize:
            ds = STATE["dataset"]
            sch = (
                _schedule_excel_dataset(ds, limit_b=limit_b)
                if ds.meta.get("source_file")
                else cpsat(ds, limit_a=limit_a, limit_b=limit_b, seed=329)
            )
            failure = _excel_solver_failure(sch) if ds.meta.get("source_file") else None
            if failure:
                return failure
            _store_run(STATE["dataset"], sch, meta=STATE.get("meta"), alloc_res=STATE.get("alloc_result"))
            report = validate(STATE["dataset"], sch)
            metrics = compute(STATE["dataset"], sch)
            payload["data"] = serialize_schedule(STATE["dataset"], sch, report, metrics)
            payload["comparison"] = STATE.get("comparison")
        return jsonify(payload)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/compare")
def api_compare():
    """Return original-vs-optimized comparison for the active run."""
    if STATE.get("comparison") is None:
        ds, sch, original = STATE.get("dataset"), STATE.get("schedule"), STATE.get("original_schedule")
        if ds is None or sch is None or original is None:
            return jsonify({"success": False, "error": "No baseline comparison available"}), 404
        STATE["comparison"] = compare_schedules(ds, original, sch).to_dict()
    return jsonify({"success": True, "comparison": STATE["comparison"]})


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
