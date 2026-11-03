"""Original vs optimized timetable comparison. Does not claim improvement without metrics."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field

from .models import Dataset, Schedule, slot_to_day_period
from .metrics import compute
from .validator import validate


@dataclass
class ComparisonReport:
    original_status: str
    optimized_status: str
    original_validator: str
    optimized_validator: str
    moved_classes: list[dict] = field(default_factory=list)
    faculty_changes: list[dict] = field(default_factory=list)
    room_changes: list[dict] = field(default_factory=list)
    unscheduled_original: list[str] = field(default_factory=list)
    unscheduled_optimized: list[str] = field(default_factory=list)
    conflict_delta: dict = field(default_factory=dict)
    metrics_original: dict = field(default_factory=dict)
    metrics_optimized: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "original_status": self.original_status,
            "optimized_status": self.optimized_status,
            "original_validator": self.original_validator,
            "optimized_validator": self.optimized_validator,
            "moved_classes": self.moved_classes,
            "faculty_changes": self.faculty_changes,
            "room_changes": self.room_changes,
            "unscheduled_original": self.unscheduled_original,
            "unscheduled_optimized": self.unscheduled_optimized,
            "conflict_delta": self.conflict_delta,
            "metrics_original": self.metrics_original,
            "metrics_optimized": self.metrics_optimized,
            "notes": self.notes,
            "counts": {
                "moved_classes": len(self.moved_classes),
                "faculty_changes": len(self.faculty_changes),
                "room_changes": len(self.room_changes),
            },
        }


def compare_schedules(ds: Dataset, original: Schedule, optimized: Schedule) -> ComparisonReport:
    """Compare baseline/original timetable with an optimized CP-SAT result."""
    rep_o = validate(ds, original)
    rep_n = validate(ds, optimized)
    met_o = compute(ds, original)
    met_n = compute(ds, optimized)

    moved, fac_ch, room_ch = [], [], []
    keys = set(original.placement) | set(optimized.placement)
    for sid, k in sorted(keys):
        o = original.placement.get((sid, k))
        n = optimized.placement.get((sid, k))
        if o is None or n is None:
            continue
        o_slot, o_room = o
        n_slot, n_room = n
        if o_slot != n_slot:
            od, op = slot_to_day_period(o_slot)
            nd, np_ = slot_to_day_period(n_slot)
            moved.append({
                "section_id": sid, "session": k,
                "from": {"slot": o_slot, "day": od, "period": op},
                "to": {"slot": n_slot, "day": nd, "period": np_},
            })
        if o_room != n_room:
            room_ch.append({"section_id": sid, "session": k, "from": o_room, "to": n_room})

    for sid in sorted(set(original.faculty) | set(optimized.faculty)):
        of = original.faculty.get(sid)
        nf = optimized.faculty.get(sid)
        if of and nf and of != nf:
            fac_ch.append({"section_id": sid, "from": of, "to": nf})

    notes = []
    # Only claim improvement when hard violations or completeness clearly improve.
    if rep_n.status == "INVALID" and rep_o.status != "INVALID":
        notes.append("Optimized timetable introduced hard-constraint violations; not an improvement.")
    elif len(rep_n.violations) < len(rep_o.violations):
        notes.append("Optimized timetable has fewer hard-constraint violations than the original.")
    elif len(rep_n.violations) > len(rep_o.violations):
        notes.append("Optimized timetable has more hard-constraint violations than the original.")
    else:
        notes.append("Hard-violation count is unchanged; review soft metrics before claiming improvement.")

    if len(rep_n.unscheduled) < len(rep_o.unscheduled):
        notes.append("More sections are scheduled after optimization.")
    elif len(rep_n.unscheduled) > len(rep_o.unscheduled):
        notes.append("Fewer sections are scheduled after optimization.")

    return ComparisonReport(
        original_status=original.status,
        optimized_status=optimized.status,
        original_validator=rep_o.status,
        optimized_validator=rep_n.status,
        moved_classes=moved,
        faculty_changes=fac_ch,
        room_changes=room_ch,
        unscheduled_original=list(rep_o.unscheduled),
        unscheduled_optimized=list(rep_n.unscheduled),
        conflict_delta={
            "original_hard_violations": len(rep_o.violations),
            "optimized_hard_violations": len(rep_n.violations),
            "original_by_rule": rep_o.by_rule(),
            "optimized_by_rule": rep_n.by_rule(),
            "original_unplaced_selections": len(rep_o.unplaced),
            "optimized_unplaced_selections": len(rep_n.unplaced),
        },
        metrics_original=met_o,
        metrics_optimized=met_n,
        notes=notes,
    )
