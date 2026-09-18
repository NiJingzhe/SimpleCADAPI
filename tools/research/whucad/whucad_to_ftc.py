#!/usr/bin/env python3
"""Translate decoded WHUCAD feature sequences into SimpleCADAPI FTC sources.

One feature block per WHUCAD operation (sketch → promotion → extrude/revolve →
boolean), following the Feature Tree Convention: block headers
``# ---- feature: <slug> (<role>) ----`` and explicit dataflow rebinding.
Topology references (Chamfer/Fillet/Shell selects) become ``ql`` geometric
predicates via whucad_select.py.

Translated sources are TRAINING DATA: they contain the model and nothing
else. The translator ONLY translates — unsupported forms are skipped with a
header annotation (never approximated); whether the result matches the
packaged BRep truth is a question for whucad_validate.py.

Usage:
    python tools/research/whucad/whucad_to_ftc.py <model.h5> [--out PATH]
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

import numpy as np

import whucad_select as wsel
import whucad_vec as w
from whucad_vec import (ExtrudeFeature, FinishFeature, HoleFeature, Line,
                        RevolveFeature, Spline)

_FMT_DIGITS = 9


def _fmt(value: float) -> str:
    return repr(round(float(value), _FMT_DIGITS))


def _vec(values) -> str:
    return "(" + ", ".join(_fmt(v) for v in values) + ")"


class UnsupportedForm(Exception):
    """Sketch/feature form the translator does not map (data-driven)."""


# ---------------------------------------------------------------------------
# sketch emission


class SketchEmitter:
    """Emits sketch entity lines for one feature, mirroring the FTC sketch
    profile ordering (circles standalone; line/arc chains by pooled endpoints)."""

    def __init__(self, name: str, plan: w.SketchPlan):
        self.name = name
        self.plan = plan
        self.lines: List[str] = []
        self.pool: dict = {}
        self.counter = 0
        plane = (
            "{'origin': " + _vec(plan.plane_origin)
            + ", 'x_axis': " + _vec(plan.plane_x_axis)
            + ", 'y_axis': " + _vec(plan.plane_y_axis) + "}"
        )
        self.lines.append(f"s = scad.make_sketch_rsketch(name={self.name!r}, plane={plane})")

    def point(self, x: float, y: float) -> str:
        key = (round(x, 6), round(y, 6))
        for pid, (px, py) in self.pool.items():
            if (round(px, 6), round(py, 6)) == key:
                return pid
        self.counter += 1
        pid = f"{self.name}_p{self.counter}"
        self.pool[pid] = (float(x), float(y))
        self.lines.append(f"s = scad.add_point_rsketch(sketch=s, point_id={pid!r}, x={_fmt(x)}, y={_fmt(y)})")
        return pid

    def emit(self) -> None:
        for loop_index, loop in enumerate(self.plan.profile.loops):
            for curve_index, curve in enumerate(loop.curves):
                eid = f"{self.name}_e{loop_index}_{curve_index}"
                if isinstance(curve, Line):
                    start = self.point(curve.start_point[0], curve.start_point[1])
                    end = self.point(curve.end_point[0], curve.end_point[1])
                    self.lines.append(f"s = scad.add_line_rsketch(sketch=s, entity_id={eid!r}, start={start!r}, end={end!r})")
                elif isinstance(curve, w.Circle):
                    center = self.point(curve.center[0], curve.center[1])
                    self.lines.append(f"s = scad.add_circle_rsketch(sketch=s, entity_id={eid!r}, center={center!r}, radius={_fmt(curve.radius)})")
                elif isinstance(curve, w.Arc):
                    cx, cy = float(curve.center[0]), float(curve.center[1])
                    start_pt, end_pt = curve.start_point, curve.end_point
                    mid = curve.mid_point
                    # promotion sweeps counter-clockwise start→end, so order
                    # the endpoints so the sweep passes through the mid point
                    a0 = math.atan2(start_pt[1] - cy, start_pt[0] - cx)
                    a1 = math.atan2(end_pt[1] - cy, end_pt[0] - cx)
                    am = math.atan2(mid[1] - cy, mid[0] - cx)
                    if not ((am - a0) % (2 * math.pi) <= (a1 - a0) % (2 * math.pi)):
                        start_pt, end_pt = end_pt, start_pt
                    start = self.point(start_pt[0], start_pt[1])
                    end = self.point(end_pt[0], end_pt[1])
                    center = self.point(cx, cy)
                    self.lines.append(f"s = scad.add_arc_rsketch(sketch=s, entity_id={eid!r}, start={start!r}, end={end!r}, center={center!r})")
                elif isinstance(curve, Spline):
                    raise UnsupportedForm("spline entity")
                else:
                    raise UnsupportedForm(f"curve {type(curve).__name__}")

    def face_lines(self, face_var: str) -> List[str]:
        if len(self.plan.profile.loops) != 1:
            raise UnsupportedForm(f"{len(self.plan.profile.loops)}-loop profile")
        return [f"{face_var} = scad.make_face_from_sketch_rface(sketch=s, profile=0)"]


# ---------------------------------------------------------------------------
# feature helpers


def _role(operation: str) -> str:
    return {"AddFeatureOperation": "add", "CutFeatureOperation": "subtract",
            "IntersectFeatureOperation": "intersect"}.get(operation, "build")


def _axis_line(feature: RevolveFeature, history: List[Any]) -> Tuple[Tuple[float, ...], Tuple[float, ...]]:
    """Axis line (origin point, unit direction) from the dataset's Wire/Sketch
    reference: curve #no of sketch #body_no (1-based over sketch features)."""
    ax = feature.axis_select
    if ax.select_type != "Wire" or ax.body_type != "Sketch":
        raise UnsupportedForm(f"axis {ax.select_type}/{ax.body_type}")
    bucket = [f for f in history if isinstance(f, (ExtrudeFeature, RevolveFeature))]
    if not 1 <= ax.body_no <= len(bucket):
        raise UnsupportedForm(f"axis sketch #{ax.body_no} out of range")
    plan = bucket[ax.body_no - 1].sketch
    curves = [c for loop in plan.profile.loops for c in loop.curves]
    if not 1 <= ax.no <= len(curves):
        raise UnsupportedForm(f"axis curve #{ax.no} out of range")
    curve = curves[ax.no - 1]
    if not isinstance(curve, Line):
        raise UnsupportedForm("non-line revolve axis")
    p0 = wsel.to3d(plan, curve.start_point)
    p1 = wsel.to3d(plan, curve.end_point)
    direction = p1 - p0
    norm = float(np.linalg.norm(direction))
    if norm < 1e-9:
        raise UnsupportedForm("degenerate axis")
    return tuple(p0), tuple(direction / norm)


# ---------------------------------------------------------------------------
# translator


class Translator:
    def __init__(self, features: List[Any], uid: str):
        self.features = features
        self.uid = uid
        self.notes: List[str] = []
        self.first_solid = True

    # -- driver --------------------------------------------------------------

    def translate(self) -> str:
        lines: List[str] = [
            f'"""FTC source generated from WHUCAD {self.uid}."""',
            "",
            "import simplecadapi as scad",
            "",
            "BODIES = None  # all solid bodies before single-solid merge",
            "",
            "",
            "def _merge_bodies(bodies):",
            "    result = bodies[0]",
            "    for extra in bodies[1:]:",
            "        try:",
            "            result = scad.union_rsolid(result, [extra])",
            "        except Exception:",
            "            pass  # disjoint bodies stay outside the single-solid contract",
            "    return result",
            "",
            "",
            f"@scad.part(id={'whucad-' + self.uid.replace('/', '-')!r}, revision='1.0.0')",
            "def build() -> scad.Part:",
        ]
        if any(isinstance(f, FinishFeature) for f in self.features):
            lines.insert(2, "from simplecadapi import ql")

        for index, feature in enumerate(self.features):
            try:
                lines.extend(self._emit_feature(index, feature))
            except (UnsupportedForm, wsel.UnsupportedSelect) as exc:
                kind = getattr(feature, "kind", type(feature).__name__)
                self.notes.append(f"step {index}: unsupported {kind} ({exc})")

        if self.first_solid:
            # nothing translated — keep the source executable, empty part
            self.notes.append("model: no feature translated")
            lines.append("    bodies = []")
        lines.append("    global BODIES")
        lines.append("    BODIES = list(bodies)")
        lines.append("    return _merge_bodies(bodies)")
        header_notes = [f"    # {note}" for note in self.notes]
        return "\n".join(lines[:6] + header_notes + lines[6:]) + "\n"

    # -- feature dispatch ------------------------------------------------------

    def _emit_feature(self, index: int, feature: Any) -> List[str]:
        if isinstance(feature, (ExtrudeFeature, RevolveFeature)):
            return self._emit_solid(index, feature)
        if isinstance(feature, HoleFeature):
            return self._emit_hole(index, feature)
        if isinstance(feature, FinishFeature):
            return self._emit_finish(index, feature)
        raise UnsupportedForm(getattr(feature, "kind", type(feature).__name__))

    def _emit_solid(self, index: int, feature: Any) -> List[str]:
        name = f"f{index}"
        emitter = SketchEmitter(name, feature.sketch)
        emitter.emit()
        face_var = f"{name}_face"
        tool_var = f"{name}_tool"
        normal = feature.sketch.plane_normal
        if isinstance(feature, ExtrudeFeature):
            if (feature.extent_type1, feature.extent_type2) != ("OffsetLimit", "OffsetLimit"):
                raise UnsupportedForm(f"extent {feature.extent_type1}/{feature.extent_type2}")
            lines = emitter.face_lines(face_var)
            neg = (-normal[0], -normal[1], -normal[2])
            # signed span [−e2, +e1]; inverted pads (negative extents) cross
            # the sketch plane
            plus = feature.extent_one + max(-feature.extent_two, 0.0)
            minus = feature.extent_two + max(-feature.extent_one, 0.0)
            plus, minus = max(plus, 0.0), max(minus, 0.0)
            if plus > 0 and minus > 0:
                lines.append(
                    f"{tool_var} = scad.union_rsolid(\n"
                    f"    scad.extrude_rsolid(profile={face_var}, direction={_vec(normal)}, distance={_fmt(plus)}),\n"
                    f"    [scad.extrude_rsolid(profile={face_var}, direction={_vec(neg)}, distance={_fmt(minus)})])"
                )
            elif plus > 0 or minus > 0:
                distance = plus if plus > 0 else minus
                direction = normal if plus > 0 else neg
                lines.append(f"{tool_var} = scad.extrude_rsolid(profile={face_var}, "
                             f"direction={_vec(direction)}, distance={_fmt(distance)})")
            else:
                raise UnsupportedForm("zero-extent extrude")
            role = "build" if self.first_solid else _role(feature.operation)
            slug = f"{feature.kind.lower()}-{index + 1}"
            out = [f"    # ---- feature: {slug} ({role}, profile=geometry) ----"]
        else:
            if feature.angle_two > 1e-9:
                raise UnsupportedForm("two-sided revolve")
            origin, axis_dir = _axis_line(feature, self.features)
            lines = emitter.face_lines(face_var)
            lines.append(f"{tool_var} = scad.revolve_rsolid(profile={face_var}, "
                         f"axis={_vec(axis_dir)}, angle={_fmt(feature.angle_one)}, "
                         f"origin={_vec(origin)})")
            role = "build" if self.first_solid else _role(feature.operation)
            slug = f"{feature.kind.lower()}-{index + 1}"
            out = [f"    # ---- feature: {slug} ({role}, profile=geometry) ----"]
        out.extend(f"    {line}" for line in emitter.lines)
        out.extend(f"    {line}" for line in lines)
        out.extend(self._boolean_lines(feature.operation, tool_var))
        return out

    def _boolean_lines(self, operation: str, tool_var: str) -> List[str]:
        out: List[str] = []
        if self.first_solid:
            out.append(f"    bodies = [{tool_var}]")
            self.first_solid = False
            return out
        role = _role(operation)
        if role == "add":
            out.append("    _merged = False")
            out.append("    _next = []")
            out.append("    for _b in bodies:")
            out.append("        try:")
            out.append(f"            _next.append(scad.union_rsolid(_b, [{tool_var}]))")
            out.append("            _merged = True")
            out.append("        except Exception:")
            out.append("            _next.append(_b)")
            out.append("    bodies = _next")
            out.append("    if not _merged:")
            out.append(f"        bodies.extend([{tool_var}])")
        elif role == "subtract":
            out.append(f"    bodies = [scad.cut_rsolid(_b, [{tool_var}]) for _b in bodies]")
        elif role == "intersect":
            out.append(f"    bodies = [scad.intersect_rsolid(_b, {tool_var}) for _b in bodies]")
        else:
            out.append(f"    bodies.extend([{tool_var}])")
        return out

    def _emit_hole(self, index: int, feature: HoleFeature) -> List[str]:
        if feature.bottom_mode != "OffsetLimit":
            raise UnsupportedForm(f"hole bottom {feature.bottom_mode}")
        emitter = SketchEmitter(f"f{index}", feature.sketch)
        pid = emitter.point(float(feature.point_pos[0]), float(feature.point_pos[1]))
        emitter.lines.append(f"s = scad.add_circle_rsketch(sketch=s, entity_id='f{index}_e0', center={pid!r}, radius={_fmt(feature.radius)})")
        face_var = f"f{index}_face"
        tool_var = f"f{index}_tool"
        normal = feature.sketch.plane_normal
        lines = emitter.face_lines(face_var)
        lines.append(f"{tool_var} = scad.extrude_rsolid(profile={face_var}, "
                     f"direction={_vec(normal)}, distance={_fmt(feature.depth)})")
        out = [f"    # ---- feature: hole-{index + 1} (subtract, profile=geometry) ----"]
        out.extend(f"    {line}" for line in emitter.lines)
        out.extend(f"    {line}" for line in lines)
        out.extend(self._boolean_lines("CutFeatureOperation", tool_var))
        return out

    def _emit_finish(self, index: int, feature: FinishFeature) -> List[str]:
        if self.first_solid:
            raise UnsupportedForm("modify feature before any solid feature")
        registry = wsel.FeatureRegistry(self.features)
        slug = f"{feature.kind.lower()}-{index + 1}"
        out = [f"    # ---- feature: {slug} (modify, profile=geometry) ----"]
        out.append("    body = _merge_bodies(bodies)")
        if feature.kind in ("Chamfer", "Fillet"):
            for i, edge_desc in enumerate(self._edge_descs(feature, registry)):
                var = f"sel{i}"
                out.extend(f"    {line}" for line in
                           wsel.edge_predicate_lines(var, edge_desc, "        "))
                if feature.kind == "Fillet":
                    out.append(f"    body = scad.fillet_rsolid(solid=body, edges={var}.exactly(1), "
                               f"radius={_fmt(feature.params['radius'])})")
                else:
                    if edge_desc.reference_normal is None:
                        raise wsel.UnsupportedSelect("chamfer without anchor face")
                    out.append(f"    body = scad.chamfer_rsolid(solid=body, edges={var}.exactly(1), "
                               f"distance={_fmt(feature.params['length1'])}, "
                               f"angle={_fmt(math.degrees(math.atan2(feature.params['angle_or_length2'], feature.params['length1'])))}, "
                               f"reference_direction={_vec(edge_desc.reference_normal)})")
        elif feature.kind == "Shell":
            # FTC shell maps the internal thickness only; the dataset's
            # external thickness (CATIA ExternalThickness) has no mapping
            if feature.params.get('second_thickness', 0.0) > 1e-9:
                raise UnsupportedForm("non-zero external shell thickness")
            if len(feature.select_list) != 1:
                raise wsel.UnsupportedSelect("multi-face shell")
            _, face_desc, _ = wsel.resolve_face(feature.select_list[0], registry)
            out.extend(f"    {line}" for line in
                       wsel.face_predicate_lines("sel", face_desc, "        "))
            out.append("    body = scad.shell_rsolid(solid=body, faces_to_remove=sel.exactly(1), "
                       f"thickness={_fmt(feature.params['thickness'])})")
        else:
            raise UnsupportedForm(feature.kind)
        out.append("    bodies = [body]")
        return out

    def _edge_descs(self, feature: FinishFeature, registry: wsel.FeatureRegistry
                    ) -> List[wsel.EdgeDesc]:
        descs: List[wsel.EdgeDesc] = []
        for select in feature.select_list:
            if select.select_type == "Edge":
                descs.append(wsel.resolve_edge(select, registry))
            elif select.select_type == "Face" and not select.operation_list \
                    and select.body_type == "Pad" and select.no in (1, 2):
                # a cap face: its single circular boundary
                source = registry.lookup(select)
                if not isinstance(source, ExtrudeFeature):
                    raise wsel.UnsupportedSelect(f"cap edge of {select.body_type}")
                descs.append(wsel.cap_boundary_edge(source, select.no))
            elif select.select_type == "Face" and select.no == 0:
                # a lateral wall face: every edge of that wall
                descs.extend(wsel.lateral_boundary_edges(select, registry))
            else:
                raise wsel.UnsupportedSelect(f"{feature.kind} on {select.select_type}"
                                             f"/{select.body_type}#{select.no}")
        return descs


# ---------------------------------------------------------------------------
# CLI


def translate_features(features: List[Any], uid: str) -> str:
    for feature in features:
        feature._history = features
    return Translator(features, uid).translate()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("h5_file", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    uid = f"{args.h5_file.parent.name}/{args.h5_file.stem}"
    features = w.load_h5(args.h5_file)
    source = translate_features(features, uid)
    out_path = args.out or args.h5_file.with_suffix(".ftc.py")
    out_path.write_text(source)
    print(f"wrote {out_path} ({source.count(chr(10))} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
