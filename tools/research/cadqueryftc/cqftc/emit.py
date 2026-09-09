"""FTC emission layer for the CadQuery translator.

Single source of the output format: block headers with the closed role
vocabulary, sketch-script profiles (local coordinates, pooled points, arcs via
circumcenter), QL predicate synthesis from selection fingerprints, and the
``@scad.part`` module shell.  The replayer decides *what* a block is; this
module decides *what it looks like* as FTC source.

Conventions (docs/skill/references/discipline/feature-tree-convention.md):

- Block header: ``# ---- feature: <slug> (<role>[, profile=geometry|sketch]
  [, path=geometry]) ----``.  Roles are the FTC closed vocabulary; slugs carry
  no sequence numbers (a dedup suffix appears only on collision).
- CadQuery traces carry no constraints: every translated profile is
  transcribed geometry, so planar profiles annotate ``profile=geometry``
  (geometry-tier case 2) while still being authored through the sketch API.
- Interpolated splines and helices cannot be expressed by the planar
  constraint sketch API; they stay on the geometry API with an honest
  ``path=geometry`` / ``profile=geometry`` annotation.
- Selections are QL predicates synthesized from trace fingerprints plus
  cardinality; bare topology enumeration does not appear in generated source.
- Numbers are literals (the trace has no named parameters; the translator does
  not invent names).
"""

from __future__ import annotations

import math
import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .tracer.trace_schema import GeoFingerprint

Vec3 = Tuple[float, float, float]

ROLE_VOCAB = frozenset({"build", "add", "subtract", "intersect", "modify", "pattern", "annotate"})

_POINT_TOL = 6  # digits, same pooled-point tolerance as the HistCAD translator
_QL_TOL = 1e-3  # mm band around fingerprint values


def fmt_num(value: float) -> str:
    number = float(value)
    if abs(number) < 1e-12:
        number = 0.0
    text = f"{number:.12g}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"-0", ""}:
        text = "0"
    return text


def fmt_vec(vec: Sequence[float]) -> str:
    return "(" + ", ".join(fmt_num(v) for v in vec) + ")"


def fmt_plane(origin: Vec3, u_dir: Vec3, v_dir: Vec3) -> str:
    return (
        "{'origin': " + fmt_vec(origin) + ", "
        "'x_axis': " + fmt_vec(u_dir) + ", "
        "'y_axis': " + fmt_vec(v_dir) + "}"
    )


class SlugAllocator:
    """Slug registry: stable op-semantic names, deduped on collision."""

    def __init__(self) -> None:
        self._counts: Dict[str, int] = {}

    def allocate(self, base: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "feature"
        count = self._counts.get(slug, 0) + 1
        self._counts[slug] = count
        return slug if count == 1 else f"{slug}-{count}"


def block_header(slug: str, role: str, *, tiers: Sequence[str] = ()) -> str:
    if role not in ROLE_VOCAB:
        raise ValueError(f"role {role!r} outside the FTC closed vocabulary")
    parts = [role, *tiers]
    return f"# ---- feature: {slug} ({', '.join(parts)}) ----"


def _part_id(stem: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(stem)).strip("-.") or "part"
    return f"cq-{cleaned}"


class SketchScript:
    """Accumulate one sketch document as FTC source lines (local 2D coords).

    ``snapshot_entities`` mirrors every entity in emission order, and
    ``render`` is the single capture choke point: it fires ``sink`` with the
    finished sketch, and whatever the sink returns (recovered constraint
    lines) is appended after the entities.  Every construction site — plain
    profiles, loft sections, sweep paths, pattern seeds — is captured by
    construction; no call site has to remember to collect anything.
    """

    def __init__(
        self,
        name: str,
        origin: Vec3,
        u_dir: Vec3,
        v_dir: Vec3,
        *,
        sink: Optional[Callable[["SketchScript"], List[str]]] = None,
        closed: bool = True,
    ) -> None:
        self.name = name
        self.origin = origin
        self.u_dir = u_dir
        self.v_dir = v_dir
        self.sink = sink
        self.closed = closed
        self.lines: List[str] = [
            f"s = scad.make_sketch_rsketch(name={name!r}, plane={fmt_plane(origin, u_dir, v_dir)})"
        ]
        self.snapshot_entities: List[Dict[str, Any]] = []
        self._points: Dict[Tuple[float, float], str] = {}
        self._point_n = 0
        self._entity_n = 0

    def point(self, x: float, y: float) -> str:
        key = (round(float(x), _POINT_TOL), round(float(y), _POINT_TOL))
        existing = self._points.get(key)
        if existing is not None:
            return existing
        self._point_n += 1
        ref = f"{self.name}_p{self._point_n}"
        self._points[key] = ref
        self.lines.append(f"s = scad.add_point_rsketch(sketch=s, point_id={ref!r}, x={fmt_num(x)}, y={fmt_num(y)})")
        self.snapshot_entities.append({"id": ref, "kind": "point", "xy": [float(x), float(y)]})
        return ref

    def _entity(self, kind: str) -> str:
        self._entity_n += 1
        return f"{kind}_{self._entity_n}"

    def line(self, start_ref: str, end_ref: str) -> None:
        eid = self._entity("line")
        self.lines.append(f"s = scad.add_line_rsketch(sketch=s, entity_id={eid!r}, start={start_ref!r}, end={end_ref!r})")
        self.snapshot_entities.append({"id": eid, "kind": "line", "start": start_ref, "end": end_ref})

    def circle(self, center_ref: str, radius: float) -> None:
        eid = self._entity("circle")
        self.lines.append(f"s = scad.add_circle_rsketch(sketch=s, entity_id={eid!r}, center={center_ref!r}, radius={fmt_num(radius)})")
        self.snapshot_entities.append({"id": eid, "kind": "circle", "center": center_ref, "radius": float(radius)})

    def arc3(self, start: Tuple[float, float], mid: Tuple[float, float], end: Tuple[float, float]) -> None:
        """Three-point arc via circumcenter, endpoints ordered so the sweep
        passes through the middle point (same semantics as the HistCAD
        translator)."""
        cx, cy = circumcenter(start, mid, end)
        start_pt, end_pt = start, end
        a0 = math.atan2(start[1] - cy, start[0] - cx)
        a1 = math.atan2(end[1] - cy, end[0] - cx)
        am = math.atan2(mid[1] - cy, mid[0] - cx)
        if not ((am - a0) % (2.0 * math.pi) <= (a1 - a0) % (2.0 * math.pi)):
            start_pt, end_pt = end_pt, start_pt
        start_ref = self.point(*start_pt)
        end_ref = self.point(*end_pt)
        center_ref = self.point(cx, cy)
        eid = self._entity("arc")
        self.lines.append(
            f"s = scad.add_arc_rsketch(sketch=s, entity_id={eid!r}, start={start_ref!r}, end={end_ref!r}, center={center_ref!r})"
        )
        self.snapshot_entities.append(
            {"id": eid, "kind": "arc", "start": start_ref, "end": end_ref, "center": center_ref}
        )

    def to_local(self, point: Vec3) -> Tuple[float, float]:
        delta = (point[0] - self.origin[0], point[1] - self.origin[1], point[2] - self.origin[2])
        return (
            _dot(delta, self.u_dir),
            _dot(delta, self.v_dir),
        )

    def render(self, indent: str = "    ", header: Optional[str] = None) -> List[str]:
        """Finalize the sketch: fire the capture sink, append its constraint
        lines after the entities, and return the indented source lines.

        ``header`` overrides the make_sketch line (pattern loops emit a plane
        whose origin is a loop-variable expression, not a literal).
        """
        rendered = list(self.lines)
        if header is not None:
            rendered[0] = header
        if self.sink is not None:
            rendered.extend(self.sink(self))
        return [indent + line for line in rendered]


def circumcenter(p0: Tuple[float, float], pm: Tuple[float, float], p1: Tuple[float, float]) -> Tuple[float, float]:
    d = 2.0 * (p0[0] * (pm[1] - p1[1]) + pm[0] * (p1[1] - p0[1]) + p1[0] * (p0[1] - pm[1]))
    if abs(d) < 1e-12:
        raise ValueError("collinear arc points")
    ux = (
        (p0[0] ** 2 + p0[1] ** 2) * (pm[1] - p1[1])
        + (pm[0] ** 2 + pm[1] ** 2) * (p1[1] - p0[1])
        + (p1[0] ** 2 + p1[1] ** 2) * (p0[1] - pm[1])
    ) / d
    uy = (
        (p0[0] ** 2 + p0[1] ** 2) * (p1[0] - pm[0])
        + (pm[0] ** 2 + pm[1] ** 2) * (p0[0] - p1[0])
        + (p1[0] ** 2 + p1[1] ** 2) * (pm[0] - p0[0])
    ) / d
    return ux, uy


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def emit_profile_sketch(
    profile: Dict[str, Any],
    var: str,
    *,
    as_wire: bool = False,
    sink: Optional[Callable[["SketchScript"], List[str]]] = None,
) -> Tuple[List[str], str, List[str]]:
    """Emit one profile dict as a sketch script + face (or wire) expression.

    Profile dicts come from the replayer: ``kind`` in {circle, rect,
    wire_path, spline_path} with global-coord geometry plus a frame
    {normal, u, v, extrude} and origin.  Returns (lines, expr, notes);
    notes are nonempty for geometry-tier splines (nothing to constrain).
    ``sink`` is forwarded to the SketchScript — capture and constraint
    recovery are its concern (single choke point), not this function's.
    """
    notes: List[str] = []
    frame = profile.get("frame") or {}
    origin = profile.get("origin", (0.0, 0.0, 0.0))
    u_dir = frame.get("u", (1.0, 0.0, 0.0))
    v_dir = frame.get("v", (0.0, 1.0, 0.0))
    kind = profile["kind"]

    if kind == "spline_path":
        point_lines = ",\n            ".join(fmt_vec(p) for p in profile["points"])
        lines = [
            f"    {var}_wire = scad.make_interpolated_spline_rwire(",
            "        points=[",
            f"            {point_lines},",
            "        ],",
            f"        periodic={bool(profile.get('closed', False))!r},",
            "    )",
        ]
        if as_wire:
            return lines, f"{var}_wire", ["spline profile: geometry tier (interpolated, no constraints)"]
        lines.append(f"    {var}_profile = scad.make_face_from_wire_rface(wire={var}_wire)")
        return lines, f"{var}_profile", ["spline profile: geometry tier (interpolated, no constraints)"]

    sketch = SketchScript(
        var,
        origin,
        u_dir,
        v_dir,
        sink=sink,
        closed=bool(profile.get("closed", True)),
    )

    if kind == "circle":
        center_ref = sketch.point(*sketch.to_local(profile["origin"]))
        sketch.circle(center_ref, float(profile["radius"]))
    elif kind == "rect":
        hw = float(profile["width"]) / 2.0
        hh = float(profile["height"]) / 2.0
        corner_refs = [sketch.point(su * hw, sv * hh) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        corner_refs.append(corner_refs[0])
        for start_ref, end_ref in zip(corner_refs, corner_refs[1:]):
            sketch.line(start_ref, end_ref)
    elif kind == "wire_path":
        segments = profile["segments"]
        first_start = segments[0]["start"]
        cursor_ref: Optional[str] = None
        for segment in segments:
            if segment["kind"] == "line":
                start_ref = sketch.point(*sketch.to_local(segment["start"]))
                end_ref = sketch.point(*sketch.to_local(segment["end"]))
                sketch.line(start_ref, end_ref)
                cursor_ref = end_ref
            elif segment["kind"] == "arc3":
                # Endpoints reuse pooled points so the wire stays connected.
                sketch.arc3(
                    sketch.to_local(segment["start"]),
                    sketch.to_local(segment["mid"]),
                    sketch.to_local(segment["end"]),
                )
                cursor_ref = sketch.point(*sketch.to_local(segment["end"]))
            else:
                notes.append(f"wire segment kind {segment['kind']!r} skipped")
        if profile.get("closed") and segments:
            last_end = segments[-1]["end"]
            if tuple(float(c) for c in last_end) != tuple(float(c) for c in first_start):
                sketch.line(sketch.point(*sketch.to_local(last_end)), sketch.point(*sketch.to_local(first_start)))
        del cursor_ref
    else:
        raise ValueError(f"unsupported profile kind for sketch emission: {kind}")

    lines = sketch.render()
    if as_wire:
        lines.append(f"    {var}_wire = scad.make_wire_from_sketch_rwire(sketch=s, profile=0)")
        return lines, f"{var}_wire", notes
    lines.append(f"    {var}_profile = scad.make_face_from_sketch_rface(sketch=s, profile=0)")
    return lines, f"{var}_profile", notes


def _band_predicates(path: str, values: Sequence[float], tol: float = _QL_TOL) -> List[str]:
    if not values:
        return []
    # Snap to 9 decimals first: fingerprint centers carry 1e-13-scale noise
    # that would otherwise leak into the emitted literals.
    rounded = [round(float(v), 9) for v in values]
    if all(abs(v) < 1e-9 for v in rounded):
        rounded = [0.0 for _ in rounded]
    lo = min(rounded) - tol
    hi = max(rounded) + tol
    preds = [f"ql.prop({path!r}, '>=', {fmt_num(lo)})"]
    if hi > lo:
        preds.append(f"ql.prop({path!r}, '<=', {fmt_num(hi)})")
    return preds


def emit_ql_edges_selector(fingerprints: Sequence[GeoFingerprint]) -> Optional[str]:
    """Synthesize a QL edge selector from trace fingerprints + cardinality."""
    fps = [fp for fp in fingerprints if fp.kind == "edge"]
    if not fps:
        return None
    preds: List[str] = []
    types = sorted({fp.geom_type for fp in fps if fp.geom_type})
    if len(types) == 1:
        preds.append(f"ql.prop('geom.type', '==', {types[0]!r})")
    for axis_index, axis in enumerate("xyz"):
        centers = [fp.center[axis_index] for fp in fps if fp.center]
        if centers:
            preds.extend(_band_predicates(f"geom.center.{axis}", centers))
    lengths = [fp.length for fp in fps if fp.length]
    if lengths:
        preds.extend(_band_predicates("geom.length", lengths))
    if not preds:
        return None
    chain = "ql.edges()"
    for pred in preds:
        chain += f".where({pred})"
    chain += f".take({len(fps)}).exactly({len(fps)})"
    return chain


def emit_ql_faces_selector(fingerprints: Sequence[GeoFingerprint], fallback_selector: Optional[str] = None) -> Optional[str]:
    """Synthesize a QL face selector (shell removal, face-bound workplanes)."""
    fps = [fp for fp in fingerprints if fp.kind == "face"]
    if fps:
        preds: List[str] = []
        types = sorted({fp.geom_type for fp in fps if fp.geom_type})
        if len(types) == 1:
            preds.append(f"ql.prop('geom.type', '==', {types[0]!r})")
        for axis_index, axis in enumerate("xyz"):
            centers = [fp.center[axis_index] for fp in fps if fp.center]
            if centers:
                preds.extend(_band_predicates(f"geom.center.{axis}", centers))
            normals = [fp.normal[axis_index] for fp in fps if fp.normal]
            if normals and max(abs(n) for n in normals) > 0.9:
                preds.extend(_band_predicates(f"geom.normal.{axis}", [n for n in normals if abs(n) > 0.9]))
        areas = [fp.area for fp in fps if fp.area]
        if areas:
            preds.extend(_band_predicates("geom.area", areas))
        if not preds:
            return None
        chain = "ql.faces()"
        for pred in preds:
            chain += f".where({pred})"
        chain += f".take({len(fps)}).exactly({len(fps)})"
        return chain
    if fallback_selector:
        mapping = {
            ">X": ("geom.normal.x", ">=", 0.9),
            "<X": ("geom.normal.x", "<=", -0.9),
            ">Y": ("geom.normal.y", ">=", 0.9),
            "<Y": ("geom.normal.y", "<=", -0.9),
            ">Z": ("geom.normal.z", ">=", 0.9),
            "<Z": ("geom.normal.z", "<=", -0.9),
        }
        spec = mapping.get(str(fallback_selector).strip())
        if spec is not None:
            path, op, value = spec
            return f"ql.faces().where(ql.prop({path!r}, {op!r}, {value}))"
    return None


def emit_module(
    *,
    stem: str,
    feature_lines: Sequence[str],
    uses_ql: bool,
    has_body: bool,
    unsupported: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> str:
    """Assemble the FTC module shell (histjson-translator shape)."""
    lines: List[str] = [f'"""FTC source generated from CadQuery trace: {stem}."""', ""]
    lines.append("from pathlib import Path")
    lines.append("")
    lines.append("import simplecadapi as scad")
    if uses_ql:
        lines.append("from simplecadapi import ql")
    lines.extend([""])
    if notes:
        for note in notes:
            lines.append(f"# {note}")
        lines.append("")
    lines.extend(
        [
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
            f"@scad.part(id={_part_id(stem)!r}, revision='1.0.0', "
            "project_root=Path(__file__).parent)",
            "def build() -> scad.Part:",
        ]
    )
    lines.extend(feature_lines if feature_lines else ["    pass  # no translatable feature produced"])
    if unsupported:
        for note in unsupported:
            lines.append(f"    # untranslated: {note}")
    if has_body:
        lines.extend(
            [
                "    global BODIES",
                "    BODIES = list(bodies)",
                "    return _merge_bodies(bodies)",
            ]
        )
    else:
        lines.append("    raise RuntimeError('feature tree produced no solid')")
    lines.append("")
    return "\n".join(lines)
