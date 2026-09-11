#!/usr/bin/env python3
"""Differential check: whucad_vec.py port vs the original WHUCAD cadlib decode.

Run from CADIR root with the WHUCAD clone available:

    .venv/bin/python tools/research/whucad/check_port.py [glob]

Compares, per feature: kind order, quantized curve geometry, plane frame,
extents/angles, finish params, and the select trees. Dev-only script; the
production tool never imports the original cadlib.
"""

from __future__ import annotations

import argparse
import glob as _glob
import os
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

# original WHUCAD cadlib clone (fazhihe/WHUCAD), e.g. .../WHUCAD containing cadlib/
_WHUCAD_CLONE = os.environ.get("WHUCAD_REPO", "")

import whucad_vec as mine  # noqa: E402

# the original cadlib is importable only after --whucad-repo is on sys.path
# (done in main); resolved lazily by _load_original()
theirs = None
ARGS_N = 256


def _load_original():
    global theirs, ARGS_N
    if theirs is None:
        import importlib

        theirs = importlib.import_module("cadlib.CAD_Class")
        ARGS_N = importlib.import_module("cadlib.macro").ARGS_N
    return theirs


def curve_sig(c) -> tuple:
    if isinstance(c, theirs.Line):
        return ("Line", tuple(np.round(c.start_point, 6)), tuple(np.round(c.end_point, 6)))
    if isinstance(c, theirs.Circle):
        return ("Circle", tuple(np.round(c.center, 6)), round(float(c.radius), 6))
    if isinstance(c, theirs.Arc):
        return ("Arc", tuple(np.round(c.center, 6)), round(float(c.radius), 6),
                round(float(c.start_arc), 6), round(float(c.end_arc), 6))
    if isinstance(c, theirs.Spline):
        return ("Spline", tuple(tuple(np.round(p, 6)) for p in c.point_list))
    return (type(c).__name__,)


def loop_sig(loop) -> tuple:
    return tuple(curve_sig(c) for c in loop.children)


def profile_sig(profile) -> tuple:
    return tuple(loop_sig(loop) for loop in profile.children)


def select_sig(s) -> tuple:
    return (s.select_type, s.body_type, s.body_no, s.no,
            tuple(select_sig(x) for x in s.operation_list),
            tuple(select_sig(x) for x in s.no_shared_included),
            tuple((k, tuple(select_sig(x) for x in v)) for k, v in s.all_oriented_included.items()))


def my_curve_sig(c) -> tuple:
    if isinstance(c, mine.Line):
        return ("Line", tuple(np.round(c.start_point, 6)), tuple(np.round(c.end_point, 6)))
    if isinstance(c, mine.Circle):
        return ("Circle", tuple(np.round(c.center, 6)), round(float(c.radius), 6))
    if isinstance(c, mine.Arc):
        return ("Arc", tuple(np.round(c.center, 6)), round(float(c.radius), 6),
                round(float(c.start_arc), 6), round(float(c.end_arc), 6))
    if isinstance(c, mine.Spline):
        return ("Spline", tuple(tuple(np.round(p, 6)) for p in c.point_list))
    return (type(c).__name__,)


def my_loop_sig(loop) -> tuple:
    return tuple(my_curve_sig(c) for c in loop.curves)


def my_profile_sig(profile) -> tuple:
    return tuple(my_loop_sig(loop) for loop in profile.loops)


def my_select_sig(s) -> tuple:
    return (s.select_type, s.body_type, s.body_no, s.no,
            tuple(my_select_sig(x) for x in s.operation_list),
            tuple(my_select_sig(x) for x in s.no_shared_included),
            tuple((k, tuple(my_select_sig(x) for x in v)) for k, v in s.all_oriented_included.items()))


def compare_case(vec: np.ndarray) -> list:
    problems = []
    m_features = mine.decode_vec(vec, is_numerical=True)
    t_seq = theirs.Macro_Seq.from_vector(vec, is_numerical=True, n=ARGS_N)
    t_features = t_seq.extrude_operation

    kinds_m = [f.kind for f in m_features]
    kinds_t = [type(f).__name__ for f in t_features]
    kinds_m = [{'Ext': 'Extrude', 'Rev': 'Revolve'}.get(k, k) for k in kinds_m]
    if kinds_m != kinds_t:
        problems.append(f"kind mismatch: {kinds_m} vs {kinds_t}")
        return problems
    kinds_t = kinds_m  # aligned below

    for mf, tf in zip(m_features, t_features):
        if isinstance(mf, mine.UnsupportedFeature):
            continue
        if isinstance(mf, mine.ExtrudeFeature):
            t = tf
            if mf.operation != t.operation:
                problems.append(f"op {mf.operation} vs {t.operation}")
            for a, b in (("extent_one", t.extent_one), ("extent_two", t.extent_two)):
                got = getattr(mf, a)
                if abs(got - float(b)) > 1e-9:
                    problems.append(f"{a} {got} vs {b}")
            if (mf.extent_type1, mf.extent_type2) != (t.extent_type1, t.extent_type2):
                problems.append(f"ext types {(mf.extent_type1, mf.extent_type2)} vs {(t.extent_type1, t.extent_type2)}")
            if my_profile_sig(mf.sketch.profile_quantized) != profile_sig(t.sketch_profile):
                problems.append(f"profile mismatch: {my_profile_sig(mf.sketch.profile_quantized)} vs {profile_sig(t.sketch_profile)}")
            if not np.allclose(mf.sketch.plane_origin, t.sketch_plane.origin, atol=1e-9):
                problems.append(f"origin {mf.sketch.plane_origin} vs {t.sketch_plane.origin}")
            if not np.allclose(mf.sketch.plane_x_axis, t.sketch_plane.x_axis, atol=1e-7):
                problems.append(f"x_axis {mf.sketch.plane_x_axis} vs {t.sketch_plane.x_axis}")
            sels_m = [my_select_sig(s) for s in mf.select_list]
            sels_t = [select_sig(s) for s in (t.select_list or [])]
            if sels_m != sels_t:
                problems.append(f"selects {sels_m} vs {sels_t}")
        elif isinstance(mf, mine.RevolveFeature):
            t = tf
            for a, b in (("angle_one", t.angle_one), ("angle_two", t.angle_two)):
                if abs(getattr(mf, a) - float(b)) > 1e-6:
                    problems.append(f"{a} {getattr(mf, a)} vs {b}")
            if my_profile_sig(mf.sketch.profile_quantized) != profile_sig(t.sketch_profile):
                problems.append("profile mismatch (rev)")
            if my_select_sig(mf.axis_select) != select_sig(t.select_list[0]):
                problems.append("axis select mismatch")
        elif isinstance(mf, mine.FinishFeature):
            t = tf
            sels_m = [my_select_sig(s) for s in mf.select_list]
            sels_t = [select_sig(s) for s in t.select_list]
            if sels_m != sels_t:
                problems.append(f"selects {sels_m} vs {sels_t}")
            for key, tval in (("thickness", t.thickness), ("second_thickness", t.second_thickness)) if mf.kind == 'Shell' else ():
                if abs(mf.params[key] - float(tval)) > 1e-9:
                    problems.append(f"{key} {mf.params[key]} vs {tval}")
            if mf.kind == 'Chamfer':
                if abs(mf.params['length1'] - float(t.length1)) > 1e-9 or abs(mf.params['angle_or_length2'] - float(t.angle_or_length2)) > 1e-9:
                    problems.append(f"chamfer params {mf.params} vs ({t.length1}, {t.angle_or_length2})")
            if mf.kind == 'Fillet':
                if abs(mf.params['radius'] - float(t.radius)) > 1e-9:
                    problems.append(f"radius {mf.params['radius']} vs {t.radius}")
        elif isinstance(mf, mine.HoleFeature):
            t = tf
            if not np.allclose(mf.point_pos, t.point_pos, atol=1e-9):
                problems.append(f"hole pos {mf.point_pos} vs {t.point_pos}")
            if abs(mf.radius - float(t.radius)) > 1e-9 or abs(mf.depth - float(t.depth)) > 1e-9:
                problems.append(f"hole r/d {mf.radius}/{mf.depth} vs {t.radius}/{t.depth}")
            if my_select_sig(mf.plane_ref) != select_sig(t.plane_ref):
                problems.append("hole plane_ref mismatch")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("glob", nargs="?", default="data/vec/0000/*.h5",
                        help="h5 glob relative to --whucad-repo (default: data/vec/0000/*.h5)")
    parser.add_argument("--whucad-repo", default=_WHUCAD_CLONE or "../WHUCAD",
                        help="clone of fazhihe/WHUCAD containing cadlib/ (or set WHUCAD_REPO)")
    args = parser.parse_args()
    if not Path(args.whucad_repo, "cadlib").is_dir():
        parser.error(f"--whucad-repo {args.whucad_repo!r} has no cadlib/ — pass the WHUCAD clone path")
    sys.path.insert(0, str(Path(args.whucad_repo).resolve()))

    paths = sorted(_glob.glob(str(Path(args.whucad_repo) / args.glob)))
    _load_original()
    n_fail = 0
    kind_counts: dict = {}
    for p in paths:
        import h5py
        with h5py.File(p, "r") as fp:
            vec = fp["vec"][:].astype(int)
        try:
            problems = compare_case(vec)
        except Exception as exc:  # noqa: BLE001
            problems = [f"exception: {exc!r}"]
        try:
            feats = mine.decode_vec(vec, is_numerical=True)
            for f in feats:
                kind_counts[f.kind] = kind_counts.get(f.kind, 0) + 1
        except Exception:
            pass
        if problems:
            n_fail += 1
            print(f"FAIL {Path(p).name}: {problems[:3]}")
    print(f"\nchecked {len(paths)} cases, {n_fail} with problems")
    print("feature kinds decoded:", dict(sorted(kind_counts.items())))
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
