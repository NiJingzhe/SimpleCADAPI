#!/usr/bin/env python3
"""Root-cause analysis for HistCAD constraint conflicts during FTC translation.

Question: WHY does translating a HistCAD sketch with its own constraints fail
to solve, when the constraints were extracted from the very same model?

Method (all analysis happens on the tool side; the translator stays pure):

1. Reproduce — render each feature's translated constrained prefix (the same
   StepEmitter the translator uses) and solve it here, classifying the
   outcome: solved / drifted (solve moves points > 1e-3 mm off the
   transcribed coordinates) / conflicting (solver-inconsistent) / exec_error.
2. Residuals — for EVERY dataset constraint, compute the value implied by the
   transcribed 4-decimal coordinates and compare it with the stated value.
   A residual near 1e-4 means rounding noise; near 0 means the entry is
   exactly consistent with the coordinates.
3. Cross-tabulate residual scale and dof against solve outcome. The working
   hypotheses to confirm or kill:
     - over-determination: conflicting features concentrate at dof=0 (no
       slack left to absorb rounding), solved features carry dof>0;
     - rounding: conflicting features' residuals sit at the 4-decimal
       quantization scale while solved features' are ~0;
     - localization: the largest residual in a conflicting feature is among
       the constraint ids the solver names.
4. halfSpace dialect — DeepCAD Distance entries carry halfSpace0/1 (which side
   of the other line each line lies on); measure how often that flag agrees
   with the side implied by the coordinates, overall and among failures.

Usage:
    python tools/research/histjson/histcad_conflicts.py --tar JSON.tar.gz
        [--count N] [--stride K] [--uids a/b,c/d] [--dump-uid UID]
        [--report PATH]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tarfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from histcad_to_ftc import (  # noqa: E402
    StepEmitter,
    circumcenter,
    entity_kind,
    eval_value_expr,
)

# residual buckets in millimeters (degrees for angular kinds)
_BUCKETS = [
    (1e-9, "exact(<1e-9)"),
    (1e-7, "solver_tol(1e-9..1e-7)"),
    (1e-5, "sub_round(1e-7..1e-5)"),
    (1e-3, "round4(1e-5..1e-3)"),
    (math.inf, "coarse(>1e-3)"),
]


def _bucket(residual: Optional[float]) -> str:
    if residual is None:
        return "unmeasurable"
    for edge, name in _BUCKETS:
        if residual < edge:
            return name
    return "coarse(>1e-3)"


# ---------------------------------------------------------------------------
# per-constraint residual engine


def _line_angle(data: Dict[str, Any]) -> float:
    sx, sy = data["start"]
    ex, ey = data["end"]
    return math.degrees(math.atan2(ey - sy, ex - sx))


def _line_len(data: Dict[str, Any]) -> float:
    return math.dist(data["start"], data["end"])


def _point_line_distance(p: Sequence[float], data: Dict[str, Any]) -> float:
    (sx, sy), (ex, ey) = data["start"], data["end"]
    dx, dy = ex - sx, ey - sy
    return abs(dx * (p[1] - sy) - dy * (p[0] - sx)) / math.hypot(dx, dy)


def _round_entity(step_em: StepEmitter, target: str) -> Dict[str, Any]:
    eid = target.partition(".")[0]
    data = step_em.sketch.get(eid)
    return data if isinstance(data, dict) else {}


def _radius_of(kind: str, data: Dict[str, Any]) -> Optional[float]:
    if kind == "circle":
        return float(data["radius"])
    if kind == "arc":
        return math.dist(circumcenter(data["start"], data["middle"], data["end"]), data["start"])
    return None


def _center_of(kind: str, data: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    if kind == "circle":
        return (float(data["center"][0]), float(data["center"][1]))
    if kind == "arc":
        return circumcenter(data["start"], data["middle"], data["end"])
    if kind == "ellipse":
        return (float(data["center"][0]), float(data["center"][1]))
    return None


def _reflect(point: Sequence[float], a: Sequence[float], b: Sequence[float]) -> Tuple[float, float]:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 < 1e-18:
        return float(point[0]), float(point[1])
    t = ((point[0] - ax) * dx + (point[1] - ay) * dy) / length2
    proj = (ax + t * dx, ay + t * dy)
    return (2 * proj[0] - point[0], 2 * proj[1] - point[1])


def _tangent_residual(em: StepEmitter, entry: Sequence[Any]) -> Tuple[Optional[float], str]:
    da, db = _round_entity(em, str(entry[0])), _round_entity(em, str(entry[1]))
    if not da or not db:
        return None, "unresolved"
    ka, kb = entity_kind(str(entry[0]).partition(".")[0]), entity_kind(str(entry[1]).partition(".")[0])
    radii = [_radius_of(ka, da), _radius_of(kb, db)]
    centers = [_center_of(ka, da), _center_of(kb, db)]
    if ka == "line" and kb == "line":
        return None, "line-line"
    if ka == "line" or kb == "line":
        line_index = 0 if ka == "line" else 1
        curve_index = 1 - line_index
        radius = radii[curve_index]
        center = centers[curve_index]
        if radius is None or center is None:
            return None, "line-curve?"
        gap = _point_line_distance(center, (da if line_index == 0 else db)) - radius
        return abs(gap), "line-curve"
    if radii[0] is not None and radii[1] is not None and centers[0] and centers[1]:
        d = math.dist(centers[0], centers[1])
        external = abs(d - (radii[0] + radii[1]))
        internal = abs(d - abs(radii[0] - radii[1]))
        if internal < external:
            return internal, "curve-curve:int"
        return external, "curve-curve:ext"
    return None, "curve-curve?"


def _distance_residual(em: StepEmitter, entry: Sequence[Any]) -> Tuple[Optional[float], str, Optional[str]]:
    payload = entry[2]
    stated = abs(eval_value_expr(payload.get("length")) or 0.0) if eval_value_expr(payload.get("length")) is not None else None
    direction = str(payload.get("direction", "MINIMUM"))
    if stated is None:
        return None, "unparsed-value", direction
    ta, tb = str(entry[0]), str(entry[1])
    ka, kb = entity_kind(ta.partition(".")[0]), entity_kind(tb.partition(".")[0])
    da, db = _round_entity(em, ta), _round_entity(em, tb)
    if not da or not db:
        return None, "unresolved", direction
    point_a = em.point_xy(ta) if "." in ta else None
    point_b = em.point_xy(tb) if "." in tb else None
    half = f"+hs({payload.get('halfSpace0')},{payload.get('halfSpace1')})" if "halfSpace0" in payload else ""
    if point_a and point_b:
        if direction == "HORIZONTAL":
            return abs(abs(point_b[0] - point_a[0]) - stated), f"point-point:H{half}", direction
        if direction == "VERTICAL":
            return abs(abs(point_b[1] - point_a[1]) - stated), f"point-point:V{half}", direction
        return abs(math.dist(point_a, point_b) - stated), f"point-point:MIN{half}", direction
    if ka == "line" and kb == "line":
        offset = _point_line_distance(da["start"], db)
        parallel = abs(abs(_line_angle(da) - _line_angle(db)) % 180.0)
        parallel = min(parallel, 180.0 - parallel)
        form = f"line-line:{direction}{half}"
        return abs(offset - stated), form, direction
    # curve-curve / curve-line distance: try the plausible readings and keep
    # the one closest to the stated value — this classifies the dialect
    candidates: List[Tuple[float, str]] = []
    ca, cb = _center_of(ka, da), _center_of(kb, db)
    ra, rb = _radius_of(ka, da), _radius_of(kb, db)
    if ca and cb:
        d = math.dist(ca, cb)
        candidates.append((abs(d - stated), "center-dist"))
        if ra is not None and rb is not None:
            candidates.append((abs(abs(d - (ra + rb)) - stated), "surface:ext"))
            candidates.append((abs(abs(d - abs(ra - rb)) - stated), "surface:int"))
    if ka == "line" and cb is not None:
        candidates.append((abs(_point_line_distance(cb, da) - stated), "center-line"))
    if kb == "line" and ca is not None:
        candidates.append((abs(_point_line_distance(ca, db) - stated), "center-line"))
    if not candidates:
        return None, f"{ka}-{kb}:?", direction
    candidates.sort()
    return candidates[0][0], f"{ka}-{kb}:{candidates[0][1]}{half}", direction


def _entry_residual(em: StepEmitter, ctype: str, entry: Any, label: str) -> Dict[str, Any]:
    record: Dict[str, Any] = {"label": label, "ctype": ctype, "residual": None, "form": ctype}
    if not isinstance(entry, list):
        record["form"] = f"{ctype}:non-list"
        return record
    refs = [str(t) for t in entry if isinstance(t, str)]
    datas = [_round_entity(em, t) for t in refs]
    kinds = [entity_kind(t.partition(".")[0]) for t in refs]

    if ctype == "Coincident" and len(refs) == 2:
        pa, pb = em.point_xy(refs[0]), em.point_xy(refs[1])
        if pa and pb:
            record["residual"] = math.dist(pa, pb)
            record["form"] = "coincident"
    elif ctype in {"Horizontal", "Vertical"}:
        if len(refs) == 2:
            pa, pb = em.point_xy(refs[0]), em.point_xy(refs[1])
            if pa and pb:
                axis = 1 if ctype == "Horizontal" else 0
                record["residual"] = abs(pb[axis] - pa[axis])
                record["form"] = f"points-{ctype.lower()}"
        elif len(refs) == 1 and datas[0] and kinds[0] == "line":
            axis = 1 if ctype == "Horizontal" else 0
            record["residual"] = abs(datas[0]["end"][axis] - datas[0]["start"][axis])
            record["form"] = f"line-{ctype.lower()}"
    elif ctype == "Parallel" and all(d and k == "line" for d, k in zip(datas, kinds)) and len(datas) >= 2:
        angles = [_line_angle(d) for d in datas if d]
        worst = 0.0
        for a, b in zip(angles, angles[1:]):
            diff = abs(a - b) % 180.0
            worst = max(worst, min(diff, 180.0 - diff))
        record["residual"] = worst
        record["angular"] = True
        record["form"] = "parallel"
    elif ctype == "Perpendicular" and len(datas) == 2 and all(d and k == "line" for d, k in zip(datas, kinds)):
        diff = abs(_line_angle(datas[0]) - _line_angle(datas[1])) % 90.0
        record["residual"] = min(diff, 90.0 - diff)
        record["angular"] = True
        record["form"] = "perpendicular"
    elif ctype == "Equal" and len(datas) == 2:
        if all(k == "line" for k in kinds):
            record["residual"] = abs(_line_len(datas[0]) - _line_len(datas[1]))
            record["form"] = "equal-length"
        elif all(k in {"circle", "arc"} for k in kinds):
            ra, rb = _radius_of(kinds[0], datas[0]), _radius_of(kinds[1], datas[1])
            if ra is not None and rb is not None:
                record["residual"] = abs(ra - rb)
                record["form"] = "equal-radius"
    elif ctype == "Tangent" and len(refs) == 2:
        record["residual"], record["form"] = _tangent_residual(em, entry)
    elif ctype == "Concentric" and len(datas) >= 2:
        centers = [_center_of(k, d) for d, k in zip(datas, kinds) if d]
        centers = [c for c in centers if c]
        if len(centers) >= 2:
            record["residual"] = max(math.dist(a, b) for a, b in zip(centers, centers[1:]))
            record["form"] = "concentric"
    elif ctype in {"Radius", "Diameter", "MajorRadius", "MinorRadius"} and len(entry) == 2:
        value = eval_value_expr(entry[1])
        if value is not None and datas[0]:
            key = {"Radius": "radius", "Diameter": "radius", "MajorRadius": "major", "MinorRadius": "minor"}[ctype]
            if kinds[0] == "arc" and key == "radius":
                implied = _radius_of("arc", datas[0])
                stated = value / 2.0 if ctype == "Diameter" else value
                if implied is not None:
                    record["residual"] = abs(implied - stated)
                    record["form"] = f"{ctype.lower()}:arc"
            elif key in datas[0]:
                implied = float(datas[0][key])
                stated = value / 2.0 if ctype == "Diameter" else value
                record["residual"] = abs(implied - stated)
                record["form"] = ctype.lower()
    elif ctype == "Length" and len(entry) == 2 and datas[0] and kinds[0] == "line":
        value = eval_value_expr(entry[1])
        if value is not None:
            record["residual"] = abs(_line_len(datas[0]) - value)
            record["form"] = "length"
        else:
            other = _round_entity(em, str(entry[1]))
            if other and entity_kind(str(entry[1]).partition(".")[0]) == "line":
                record["residual"] = abs(_line_len(datas[0]) - _line_len(other))
                record["form"] = "length-equal"
    elif ctype == "Angle" and len(entry) == 3 and datas[0] and datas[1]:
        value = eval_value_expr(entry[2])
        if value is not None and kinds[0] == "line" and kinds[1] == "line":
            a = _line_angle(datas[0]) % 180.0
            b = _line_angle(datas[1]) % 180.0
            diff = abs(a - b) % 180.0
            record["residual"] = min(diff, 180.0 - diff) if value == 0 or value == 180 else min(
                abs(((b - a) % 360.0) - (value % 360.0)) % 180.0,
                180.0 - abs(((b - a) % 360.0) - (value % 360.0)) % 180.0,
            )
            record["angular"] = True
            record["form"] = "angle"
    elif ctype == "Normal" and len(datas) == 2:
        line_index = 0 if kinds[0] == "line" else 1
        curve_index = 1 - line_index
        center = _center_of(kinds[curve_index], datas[curve_index])
        if center is not None:
            record["residual"] = _point_line_distance(center, datas[line_index])
            record["form"] = "normal"
    elif ctype == "Mirror" and len(entry) == 3 and all(datas):
        a_data, axis_data, b_data = datas
        if kinds[1] == "line":
            pts_a = [a_data["start"], a_data["end"]] if kinds[0] == "line" else (
                [a_data["start"], a_data["middle"], a_data["end"]] if kinds[0] == "arc" else [a_data["center"]]
            )
            pts_b = [b_data["start"], b_data["end"]] if kinds[2] == "line" else (
                [b_data["start"], b_data["middle"], b_data["end"]] if kinds[2] == "arc" else [b_data["center"]]
            )
            reflected = [_reflect(p, axis_data["start"], axis_data["end"]) for p in pts_a]
            direct = max(math.dist(p, q) for p, q in zip(reflected, pts_b)) if len(reflected) == len(pts_b) else None
            flipped = max(math.dist(p, q) for p, q in zip(reflected, list(reversed(pts_b)))) if len(reflected) == len(pts_b) else None
            if direct is not None and flipped is not None:
                record["residual"] = min(direct, flipped)
                record["form"] = "mirror"
    elif ctype == "Midpoint" and len(entry) == 2:
        if isinstance(entry[1], list) and len(entry[1]) == 2:
            pa, pb = em.point_xy(str(entry[1][0])), em.point_xy(str(entry[1][1]))
            mid = em.point_xy(refs[0])
            if pa and pb and mid:
                record["residual"] = math.dist(mid, ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2))
                record["form"] = "midpoint-3pt"
        elif datas[1] and kinds[1] == "line":
            mid = em.point_xy(refs[0])
            middle = ((datas[1]["start"][0] + datas[1]["end"][0]) / 2, (datas[1]["start"][1] + datas[1]["end"][1]) / 2)
            if mid:
                record["residual"] = math.dist(mid, middle)
                record["form"] = "midpoint"
    elif ctype == "Fix":
        record["residual"] = 0.0
        record["form"] = "fix"
    elif ctype == "Distance" and len(entry) == 3 and isinstance(entry[2], dict):
        record["residual"], record["form"], _direction = _distance_residual(em, entry)
    return record


def constraint_residuals(step: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Residual of every constraint entry in one HistCAD step."""
    em = StepEmitter(step, 0, constraints_mode="on")
    out: List[Dict[str, Any]] = []
    counter = 0
    for ctype, entries in sorted((step.get("constraints") or {}).items()):
        if not isinstance(entries, list):
            entries = [entries]
        for entry in entries:
            counter += 1
            out.append(_entry_residual(em, str(ctype), entry, f"h{counter}_{ctype}"))
    return out


# ---------------------------------------------------------------------------
# halfSpace dialect check (DeepCAD line-line MINIMUM distances)


def _halfspace_audit(step: Dict[str, Any]) -> List[Dict[str, Any]]:
    sketch = step.get("sketch") or {}
    records: List[Dict[str, Any]] = []
    for ctype, entries in sorted((step.get("constraints") or {}).items()):
        if ctype != "Distance" or not isinstance(entries, list):
            continue
        for entry in entries:
            if not (isinstance(entry, list) and len(entry) == 3 and isinstance(entry[2], dict)):
                continue
            payload = entry[2]
            if "halfSpace0" not in payload:
                continue
            da, db = sketch.get(str(entry[0])), sketch.get(str(entry[1]))
            if not (isinstance(da, dict) and isinstance(db, dict)):
                continue
            if entity_kind(str(entry[0])) != "line" or entity_kind(str(entry[1])) != "line":
                continue

            def side(probe: Sequence[float], line: Dict[str, Any]) -> str:
                (sx, sy), (ex, ey) = line["start"], line["end"]
                cross = (ex - sx) * (probe[1] - sy) - (ey - sy) * (probe[0] - sx)
                return "LEFT" if cross >= 0 else "RIGHT"

            records.append({
                "stated0": payload.get("halfSpace0"),
                "stated1": payload.get("halfSpace1"),
                "implied0": side(da["start"], db),
                "implied1": side(db["start"], da),
            })
    return records


# ---------------------------------------------------------------------------
# case evaluation


# audit criterion (NOT translation policy): a constrained solve must reproduce
# the transcribed coordinates; rounding reflow stays below ~2e-4 mm
_MAX_SOLVE_DRIFT = 1e-3


def _audit_feature(step: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Solve one feature's translated constrained prefix and classify it.

    This is the audit side of the wall: the translator emits constraints
    unconditionally; here we run them and report what happened.
    """
    import simplecadapi as scad  # noqa: PLC0415

    emitter = StepEmitter(step, index, constraints_mode="on")
    try:
        feature = emitter.emit_feature()
    except Exception as exc:  # noqa: BLE001
        return {"outcome": "unsupported", "status": str(exc)[:80], "dof": None,
                "max_move": None, "failed_constraints": []}
    if not feature["constraint_lines"]:
        return {"outcome": "no-constraints", "status": None, "dof": None,
                "max_move": None, "failed_constraints": []}
    namespace: Dict[str, Any] = {"scad": scad}
    source = "\n".join(feature["sketch_lines"] + feature["constraint_lines"])
    try:
        exec(compile(source, "<histcad-audit>", "exec"), namespace)  # noqa: S102
        result = scad.inspect_sketch_rsketchresult(namespace["s"], strict=False)
    except Exception as exc:  # noqa: BLE001
        return {"outcome": "exec_error", "status": str(exc)[:120], "dof": None,
                "max_move": None, "failed_constraints": []}
    failed = [d.constraint_id for d in result.diagnostics if d.severity == "error" and d.constraint_id]
    record: Dict[str, Any] = {
        "status": result.status,
        "dof": int(result.dof),
        "failed_constraints": failed,
        "max_move": None,
    }
    if result.status in {"conflicting", "failed"} or failed:
        record["outcome"] = "conflicting"
        return record
    worst = 0.0
    seen = False
    for pid, (x, y) in emitter.pool.items():
        solved = result.solved_points.get(pid)
        if solved is not None:
            seen = True
            worst = max(worst, math.hypot(solved[0] - x, solved[1] - y))
    record["max_move"] = worst if seen else None
    if worst > _MAX_SOLVE_DRIFT:
        record["outcome"] = "drifted"
    else:
        record["outcome"] = "solved"
    return record


def _evaluate(payload: Dict[str, Any]) -> Dict[str, Any]:
    uid = payload["uid"]
    per_feature: List[Dict[str, Any]] = []
    for index, step in enumerate(payload["steps"]):
        residuals = constraint_residuals(step)
        measured = [r["residual"] for r in residuals if r["residual"] is not None]
        halfspace = _halfspace_audit(step)
        audit = _audit_feature(step, index)
        per_feature.append({
            "feature": index,
            **audit,
            "max_residual": max(measured) if measured else None,
            "residuals": residuals,
            "halfspace": halfspace,
        })
    return {
        "uid": uid,
        "features": per_feature,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tar", type=Path, required=True)
    parser.add_argument("--uids", type=str, default="")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--stride", type=int, default=83)
    parser.add_argument("--dump-uid", type=str, default="")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args(argv)

    with tarfile.open(args.tar, "r:gz") as tar:
        members = [m.name for m in tar if m.name.endswith(".json")]
        if args.uids or args.dump_uid:
            wanted = {f"{u}.json" for u in (args.uids + "," + args.dump_uid).split(",") if u}
            members = [m for m in members if m in wanted]
        else:
            members = members[:: args.stride][: args.count]
        def _read(member: str) -> bytes:
            handle = tar.extractfile(member)
            if handle is None:
                raise ValueError(f"cannot read tar member {member}")
            return handle.read()

        payloads = [
            {"uid": m[: -len(".json")], "steps": json.loads(_read(m))}
            for m in sorted(members)
        ]

    print(f"analyzing {len(payloads)} cases from {args.tar.name}")
    results = [_evaluate(p) for p in payloads]

    # -- aggregate: outcome x residual bucket, outcome x dof ----------------
    outcome_bucket: Dict[str, Counter] = defaultdict(Counter)
    outcome_dof: Dict[str, Counter] = defaultdict(Counter)
    failed_kind_bucket: Dict[str, Counter] = defaultdict(Counter)
    localized = 0
    localizable = 0
    solved_moves: List[float] = []
    drifted_moves: List[float] = []
    kind_stats: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    halfspace_total = Counter()
    halfspace_bad = Counter()
    for result in results:
        for feature in result["features"]:
            outcome = feature["outcome"]
            outcome_bucket[outcome][_bucket(feature["max_residual"])] += 1
            if feature["dof"] is not None:
                outcome_dof[outcome]["dof=0" if feature["dof"] == 0 else "dof>0"] += 1
            if outcome in {"conflicting", "exec_error", "unsupported"}:
                failed_set = set(feature["failed_constraints"])
                worst = max(
                    (r for r in feature["residuals"] if r["residual"] is not None),
                    key=lambda r: r["residual"],
                    default=None,
                )
                if worst is not None:
                    localizable += 1
                    if worst["label"] in failed_set:
                        localized += 1
                for r in feature["residuals"]:
                    if r["label"] in failed_set and r["residual"] is not None:
                        failed_kind_bucket[r["ctype"]][_bucket(r["residual"])] += 1
            if outcome == "solved" and feature["max_move"] is not None:
                solved_moves.append(feature["max_move"])
            if outcome == "drifted" and feature["max_move"] is not None:
                drifted_moves.append(feature["max_move"])
            for r in feature["residuals"]:
                if r["residual"] is not None:
                    kind_stats[r["ctype"]]["all"].append(r["residual"])
                    if outcome in {"conflicting", "exec_error"} and r["label"] in set(feature["failed_constraints"]):
                        kind_stats[r["ctype"]]["failed"].append(r["residual"])
            for record in feature["halfspace"]:
                key0 = (record["stated0"] == record["implied0"], record["stated1"] == record["implied1"])
                key = f"s0:{'ok' if key0[0] else 'flip'} s1:{'ok' if key0[1] else 'flip'}"
                halfspace_total[key] += 1
                if outcome in {"conflicting", "drifted", "exec_error"}:
                    halfspace_bad[key] += 1

    print("\n== outcome x max-residual bucket (per feature) ==")
    for outcome, buckets in sorted(outcome_bucket.items()):
        total = sum(buckets.values())
        print(f"  {outcome:14s} n={total:4d}  " + "  ".join(f"{name}={count}" for name, count in buckets.items()))
    print("\n== outcome x dof ==")
    for outcome, dofs in sorted(outcome_dof.items()):
        print(f"  {outcome:14s}  " + "  ".join(f"{k}={v}" for k, v in sorted(dofs.items())))
    print(f"\n== localization: worst-residual constraint among solver-named failed ids: {localized}/{localizable} ==")
    if solved_moves:
        solved_moves.sort()
        print(
            "== solved-feature point displacement (solver reflow): "
            f"median={solved_moves[len(solved_moves) // 2]:.2e} p90={solved_moves[int(0.9 * len(solved_moves))]:.2e} max={solved_moves[-1]:.2e}"
        )
    if drifted_moves:
        drifted_moves.sort()
        print(
            "== drifted-feature point displacement: "
            f"min={drifted_moves[0]:.2e} median={drifted_moves[len(drifted_moves) // 2]:.2e} max={drifted_moves[-1]:.2e}"
        )
    print("\n== failed constraint kinds x their own residual bucket ==")
    for ctype, buckets in sorted(failed_kind_bucket.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"  {ctype:12s} n={sum(buckets.values()):4d}  " + "  ".join(f"{name}={count}" for name, count in buckets.items()))
    print("\n== per-kind residual medians (all vs failed) ==")
    for ctype, stats in sorted(kind_stats.items(), key=lambda kv: -len(kv[1]["all"])):
        allv = sorted(stats["all"])
        fail = sorted(stats["failed"])
        med = allv[len(allv) // 2] if allv else float("nan")
        fmed = fail[len(fail) // 2] if fail else float("nan")
        print(f"  {ctype:12s} n={len(allv):5d} median={med:.2e}  failed-n={len(fail):4d} failed-median={fmed:.2e}")
    if sum(halfspace_total.values()):
        print("\n== DeepCAD halfSpace vs coordinate-implied side ==")
        for key, count in sorted(halfspace_total.items()):
            bad_count = halfspace_bad.get(key, 0)
            print(f"  {key}: total={count} in-nonsolving-features={bad_count}")

    if args.dump_uid:
        for result in results:
            if result["uid"] != args.dump_uid:
                continue
            print(f"\n== dump {result['uid']} ==")
            for feature in result["features"]:
                print(
                    f"  feature {feature['feature']}: {feature['outcome']} status={feature['status']} "
                    f"dof={feature['dof']} failed={feature['failed_constraints']}"
                )
                for r in sorted(feature["residuals"], key=lambda r: -(r["residual"] or 0.0)):
                    value = f"{r['residual']:.3e}" if r["residual"] is not None else "n/a"
                    print(f"    {r['label']:24s} {r['form']:26s} residual={value}")

    report = args.report or Path(__file__).resolve().parent / "out" / "histcad_conflicts.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(
        {
            "tar": args.tar.name,
            "cases": [
                {
                    "uid": r["uid"],
                    "features": [
                        {k: v for k, v in f.items() if k != "residuals"} | {"residuals": f["residuals"]}
                        for f in r["features"]
                    ],
                }
                for r in results
            ],
        },
        indent=2,
    ))
    print(f"\nwrote {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
