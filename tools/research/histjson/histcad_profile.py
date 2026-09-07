#!/usr/bin/env python3
"""Profile HistCAD sequence tarballs for FTC translation feasibility.

Streams every JSON member of the given ``.tar.gz`` archives (no extraction)
and aggregates the feature/entity/constraint vocabulary actually present in
the data, so coverage gaps against the SimpleCADAPI FTC pipeline can be
sized with counts instead of anecdotes.

Usage:
    python tools/research/histcad_profile.py <seq.tar.gz> [<seq.tar.gz> ...]
        [--limit N] [--out PATH]

Output: a human-readable report on stdout and a machine-readable JSON dump
(default ``tools/research/out/histcad_profile.json``).
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import sys
import tarfile
from pathlib import Path

Point2 = tuple[float, float]

# ---------------------------------------------------------------------------
# step classification


def classify_step(step: dict) -> str:
    if not isinstance(step, dict):
        return "malformed"
    op = step.get("operation")
    if op == "Fillet":
        return "fillet"
    if op == "Chamfer":
        return "chamfer"
    if "pitch" in step or "turns" in step:
        return "helix"
    if "start" in step and "end" in step and "axis" in step:
        return "revolve"
    if "towards" in step or "opposite" in step:
        return "extrude"
    return "unknown"


def op_mode(step: dict) -> str:
    mode = step.get("operation")
    return mode if isinstance(mode, str) else "malformed"


# ---------------------------------------------------------------------------
# value expressions


def value_expr_shape(value) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        text = value.strip().lower()
        if text.endswith(("mm", "millimeter", "millimetre")):
            return "mm"
        if text.endswith(("in", "inch")):
            return "in"
        if text.endswith(("cm", "centimeter")):
            return "cm"
        if "*" in text:
            return "expr"
        return f"other_str:{value.strip()!r}" if len(text) < 24 else "other_str:long"
    return type(value).__name__


def value_expr_number(value) -> float | None:
    """Best-effort mm value of a HistCAD value_expr."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip().replace(" ", "")
    factor = 1.0
    if text.endswith("mm"):
        text = text[: -len("mm")]
    elif text.endswith("in"):
        text = text[: -len("in")]
        factor = 25.4
    try:
        # "0.25*in" was already stripped to "0.25*" -> drop trailing operator
        text = text.rstrip("*")
        return float(text) * factor
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# sketch topology (endpoint chaining by rounded coordinates)


def _round_pt(pt) -> tuple:
    try:
        return (round(float(pt[0]), 4), round(float(pt[1]), 4))
    except (TypeError, ValueError, IndexError):
        return ("bad",)


def entity_endpoints(kind: str, data: dict) -> list[tuple]:
    if kind == "line":
        return [_round_pt(data.get("start")), _round_pt(data.get("end"))]
    if kind == "arc":
        return [_round_pt(data.get("start")), _round_pt(data.get("end"))]
    if kind == "nurbs":
        controls = data.get("controls") or []
        if len(controls) >= 2 and not data.get("periodic"):
            return [_round_pt(controls[0]), _round_pt(controls[-1])]
        return []
    return []


def sketch_topology(sketch: dict, tol_digits: int = 3) -> dict:
    """Chain non-circular entities by coincident endpoints (rounded)."""
    parent: dict[tuple, tuple] = {}
    rank: dict[tuple, int] = {}

    def find(x: tuple) -> tuple:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: tuple, b: tuple) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1

    def add(p: tuple) -> None:
        if p not in parent:
            parent[p] = p
            rank[p] = 0

    endpoint_count: dict[tuple, int] = collections.Counter()
    chain_entities = 0
    for eid, data in sketch.items():
        if not isinstance(data, dict):
            continue
        kind = str(eid).split("_", 1)[0]
        pts = entity_endpoints(kind, data)
        if len(pts) == 2 and pts[0] != pts[1]:
            chain_entities += 1
            for p in pts:
                add(p)
                endpoint_count[p] += 1
            union(pts[0], pts[1])

    components: dict[tuple, int] = collections.Counter()
    for p in parent:
        components[find(p)] += 1
    dangling = sum(1 for p, c in endpoint_count.items() if c == 1)
    circles = sum(
        1
        for eid, data in sketch.items()
        if isinstance(data, dict) and str(eid).split("_", 1)[0] == "circle"
    )
    # count components containing at least 2 distinct endpoints -> loop-ish
    loops = sum(1 for root, size in components.items() if size >= 2)
    return {
        "entities": len(sketch),
        "chain_entities": chain_entities,
        "components": len(components),
        "multi_endpoint_components": loops,
        "dangling_endpoints": dangling,
        "circles": circles,
    }


# ---------------------------------------------------------------------------
# per-archive profiling


def profile_archive(path: Path, limit: int | None) -> dict:
    profile = {
        "archive": path.name,
        "files": 0,
        "steps": 0,
        "steps_by_type": collections.Counter(),
        "modes_by_type": collections.defaultdict(collections.Counter),
        "step_keysets": collections.Counter(),
        "entity_kinds": collections.Counter(),
        "sketch_entity_buckets": collections.Counter(),
        "constraint_kinds": collections.Counter(),
        "constraint_arg_shapes": collections.Counter(),
        "value_expr_shapes": collections.Counter(),
        "extrude_directionality": collections.Counter(),
        "revolve": {
            "start_nonzero": 0,
            "span_360": 0,
            "span_lt_360": 0,
            "nonpositive_span": 0,
            "spans": collections.Counter(),
        },
        "helix": {
            "handedness": collections.Counter(),
            "turns_integer": 0,
            "turns_fractional": 0,
        },
        "fillet": {
            "radius_scalar": 0,
            "radius_list": 0,
            "near_point_counts": collections.Counter(),
        },
        "chamfer": {
            "angle_45": 0,
            "angle_other": collections.Counter(),
            "plane_axis_aligned": 0,
            "plane_arbitrary": 0,
        },
        "cs": {
            "identity": 0,
            "rotation_only": 0,
            "translation_only": 0,
            "general": 0,
        },
        "sketch_topology": {
            "single_loop": 0,
            "multi_loop": 0,
            "open_chain": 0,
            "circle_only": 0,
            "max_entities": 0,
        },
        "files_with": collections.Counter(),
        "multi_newbody_files": 0,
        "unknown_steps": 0,
        "json_errors": 0,
    }

    def note_file(flags: set[str], newbody_count: int) -> None:
        for flag in flags:
            profile["files_with"][flag] += 1
        if newbody_count > 1:
            profile["multi_newbody_files"] += 1

    with tarfile.open(path, "r:gz") as tar:
        members = (m for m in tar if m.isfile() and m.name.endswith(".json"))
        for member in members:
            if limit is not None and profile["files"] >= limit:
                break
            profile["files"] += 1
            try:
                steps = json.load(tar.extractfile(member))
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
                profile["json_errors"] += 1
                continue
            if not isinstance(steps, list):
                profile["json_errors"] += 1
                continue

            file_flags: set[str] = set()
            newbody_count = 0
            for step in steps:
                kind = classify_step(step)
                profile["steps"] += 1
                profile["steps_by_type"][kind] += 1
                if kind == "unknown":
                    profile["unknown_steps"] += 1
                    file_flags.add("unknown_step")
                keyset = tuple(sorted(step.keys())) if isinstance(step, dict) else ()
                profile["step_keysets"][f"{kind}: {keyset}"] += 1

                mode = op_mode(step)
                profile["modes_by_type"][kind][mode] += 1
                if mode == "NewBody":
                    newbody_count += 1

                if kind == "extrude":
                    towards = float(step.get("towards") or 0.0)
                    opposite = float(step.get("opposite") or 0.0)
                    if towards > 0 and opposite > 0:
                        profile["extrude_directionality"]["both_sided"] += 1
                    elif towards > 0:
                        profile["extrude_directionality"]["towards_only"] += 1
                    elif opposite > 0:
                        profile["extrude_directionality"]["opposite_only"] += 1
                    else:
                        profile["extrude_directionality"]["zero"] += 1

                if kind == "revolve":
                    start = float(step.get("start") or 0.0)
                    end = float(step.get("end") or 0.0)
                    info = profile["revolve"]
                    if abs(start) > 1e-9:
                        info["start_nonzero"] += 1
                    span = end - start
                    if span <= 0:
                        info["nonpositive_span"] += 1
                    elif abs(span - 360.0) < 1e-6:
                        info["span_360"] += 1
                    else:
                        info["span_lt_360"] += 1
                        info["spans"][f"{math.floor(span / 90) * 90}-{math.floor(span / 90) * 90 + 90}"] += 1

                if kind == "helix":
                    info = profile["helix"]
                    info["handedness"][str(step.get("handedness"))] += 1
                    turns = float(step.get("turns") or 0.0)
                    if abs(turns - round(turns)) < 1e-9:
                        info["turns_integer"] += 1
                    else:
                        info["turns_fractional"] += 1

                if kind == "fillet":
                    info = profile["fillet"]
                    radius = step.get("radius")
                    if isinstance(radius, list):
                        info["radius_list"] += 1
                    else:
                        info["radius_scalar"] += 1
                    info["near_point_counts"][len(step.get("near_points") or [])] += 1

                if kind == "chamfer":
                    info = profile["chamfer"]
                    angle = step.get("angle")
                    if angle is None or abs(float(angle) - 45.0) < 1e-6:
                        info["angle_45"] += 1
                    else:
                        info["angle_other"][str(angle)] += 1
                    plane = step.get("plane") or []
                    if len(plane) == 3 and sum(
                        1 for v in plane if abs(float(v)) < 1e-9
                    ) == 2:
                        info["plane_axis_aligned"] += 1
                    else:
                        info["plane_arbitrary"] += 1

                cs = step.get("coordinate_system")
                if isinstance(cs, dict):
                    euler = cs.get("Euler Angles") or [0, 0, 0]
                    trans = cs.get("Translation Vector") or [0, 0, 0]
                    has_rot = any(abs(float(v)) > 1e-9 for v in euler)
                    has_trans = any(abs(float(v)) > 1e-9 for v in trans)
                    bucket = (
                        "general" if has_rot and has_trans
                        else "rotation_only" if has_rot
                        else "translation_only" if has_trans
                        else "identity"
                    )
                    profile["cs"][bucket] += 1

                sketch = step.get("sketch")
                if isinstance(sketch, dict) and sketch:
                    topo = sketch_topology(sketch)
                    profile["sketch_topology"]["max_entities"] = max(
                        profile["sketch_topology"]["max_entities"], topo["entities"]
                    )
                    buckets = profile["sketch_entity_buckets"]
                    buckets[
                        "1" if topo["entities"] == 1
                        else "2-4" if topo["entities"] <= 4
                        else "5-10" if topo["entities"] <= 10
                        else "11-30" if topo["entities"] <= 30
                        else "31+"
                    ] += 1
                    st = profile["sketch_topology"]
                    if topo["dangling_endpoints"] > 0:
                        st["open_chain"] += 1
                        file_flags.add("open_chain_sketch")
                    elif topo["circles"] == topo["entities"]:
                        st["circle_only"] += 1
                    elif topo["multi_endpoint_components"] > 1:
                        st["multi_loop"] += 1
                    else:
                        st["single_loop"] += 1
                    for eid, data in sketch.items():
                        if not isinstance(data, dict):
                            continue
                        ekind = str(eid).split("_", 1)[0]
                        profile["entity_kinds"][ekind] += 1
                        if ekind == "ellipse":
                            file_flags.add("ellipse")
                        if ekind == "elliptical_arc":
                            file_flags.add("elliptical_arc")
                        if ekind == "nurbs":
                            file_flags.add("nurbs")
                            if data.get("periodic"):
                                file_flags.add("nurbs_periodic")

                constraints = step.get("constraints")
                if isinstance(constraints, dict):
                    for ctype, entries in constraints.items():
                        profile["constraint_kinds"][str(ctype)] += 1
                        if isinstance(entries, list):
                            for entry in entries:
                                shape = []
                                if isinstance(entry, str):
                                    shape.append("ref")
                                elif isinstance(entry, list):
                                    for item in entry:
                                        if isinstance(item, str):
                                            shape.append(
                                                "point" if "." in item else "entity"
                                            )
                                        else:
                                            shape.append(type(item).__name__)
                                profile["constraint_arg_shapes"][
                                    f"{ctype}({', '.join(shape)})"
                                ] += 1
                        elif isinstance(entries, str):
                            profile["constraint_arg_shapes"][f"{ctype}(bare_str)"] += 1

                # value_expr shapes anywhere in Distance/Length/Radius/etc.
                if isinstance(constraints, dict):
                    for ctype in (
                        "Distance", "Length", "Radius", "Diameter",
                        "MajorRadius", "MinorRadius",
                    ):
                        for entry in constraints.get(ctype, []) or []:
                            if isinstance(entry, list):
                                for item in entry[1:]:
                                    if isinstance(item, dict):
                                        length = item.get("length")
                                        if length is not None:
                                            profile["value_expr_shapes"][
                                                value_expr_shape(length)
                                            ] += 1
                                    else:
                                        profile["value_expr_shapes"][
                                            value_expr_shape(item)
                                        ] += 1

            note_file(file_flags, newbody_count)
    return profile


# ---------------------------------------------------------------------------
# reporting


def render(profile: dict) -> str:
    lines = []
    add = lines.append
    files = profile["files"]
    add(f"# {profile['archive']}")
    add(f"files={files} steps={profile['steps']} "
        f"json_errors={profile['json_errors']} unknown_steps={profile['unknown_steps']}")
    add(f"steps_by_type: {dict(profile['steps_by_type'])}")
    for kind, modes in sorted(profile["modes_by_type"].items()):
        add(f"modes[{kind}]: {dict(modes)}")
    add(f"entity_kinds: {dict(profile['entity_kinds'])}")
    add(f"sketch_entity_buckets: {dict(profile['sketch_entity_buckets'])}")
    add(f"sketch_topology: { {k: v for k, v in profile['sketch_topology'].items()} }")
    add(f"constraint_kinds: {dict(profile['constraint_kinds'].most_common())}")
    add(f"cs: {dict(profile['cs'])}")
    add(f"extrude_directionality: {dict(profile['extrude_directionality'])}")
    add(f"revolve: {dict(profile['revolve'])}")
    add(f"helix: {dict(profile['helix'])}")
    add(f"fillet: {dict(profile['fillet'])}")
    add(f"chamfer: angle_45={profile['chamfer']['angle_45']} "
        f"angle_other={dict(profile['chamfer']['angle_other'])} "
        f"plane_axis={profile['chamfer']['plane_axis_aligned']} "
        f"plane_arbitrary={profile['chamfer']['plane_arbitrary']}")
    add(f"value_expr_shapes: {dict(profile['value_expr_shapes'])}")
    add(f"files_with: {dict(profile['files_with'])}")
    add(f"multi_newbody_files: {profile['multi_newbody_files']}")
    add("-- step keysets --")
    for keyset, count in profile["step_keysets"].most_common():
        add(f"  {count:7d}  {keyset}")
    add("-- constraint arg shapes --")
    for shape, count in profile["constraint_arg_shapes"].most_common():
        add(f"  {count:7d}  {shape}")
    return "\n".join(lines)


def to_jsonable(obj):
    if isinstance(obj, collections.Counter):
        return {str(k): v for k, v in obj.most_common()}
    if isinstance(obj, collections.defaultdict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--limit", type=int, default=None, help="cap files per archive")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    out_path = args.out or Path(__file__).resolve().parent / "out" / "histcad_profile.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for archive in args.archives:
        if not archive.exists():
            print(f"missing archive: {archive}", file=sys.stderr)
            return 2
        profile = profile_archive(archive, args.limit)
        print(render(profile))
        print()
        results.append(to_jsonable(profile))

    out_path.write_text(json.dumps(results, indent=2))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
