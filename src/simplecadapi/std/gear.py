"""Involute gear standard parts built with constraint sketches.

Each gear profile is assembled in a constraint sketch using:
  - **B-spline edges** for analytic involute tooth flanks and tangent
    root transitions
  - **Arc edges** for root and tip circular arcs
  - **Line edges** for radial connectors when root lies inside base circle
  - **Construction circles** (root / pitch / tip) with radius and
    concentricity constraints capturing the design intent

The sketch is solved and promoted to a face via
``make_face_from_sketch_rface``.  Spur gears are extruded; helical and
herringbone gears use multi-section loft with progressively rotated
    copies of the same profile.  Spur ring gears build a multi-loop face from
    an outer rim wire and an inward internal-tooth inner wire, then extrude it
    directly.  Helical and herringbone ring gears loft the internal tooth void
    and subtract it from an extruded outer rim.  Racks build a trapezoidal-tooth
    profile along a straight line.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from ..core import Solid, Wire, Face
from ..math import fit_cubic_bspline_control_points
from ..operations import (
    add_arc_rsketch,
    add_bspline_rsketch,
    add_circle_rsketch,
    add_line_rsketch,
    add_point_rsketch,
    constrain_concentric_rsketch,
    constrain_fix_rsketch,
    constrain_radius_rsketch,
    cut_rsolid,
    extrude_rsolid,
    loft_rsolid,
    make_circle_rwire,
    make_face_from_wire_rface,
    make_face_from_wires_rface,
    make_face_from_sketch_rface,
    make_sketch_rsketch,
    make_wire_from_sketch_rwire,
    rotate_shape,
    translate_shape,
)

__all__ = [
    "make_spur_gear_rsolid",
    "make_helical_gear_rsolid",
    "make_herringbone_gear_rsolid",
    "make_spur_ring_gear_rsolid",
    "make_helical_ring_gear_rsolid",
    "make_herringbone_ring_gear_rsolid",
    "make_spur_rack_rsolid",
    "make_helical_rack_rsolid",
    "make_herringbone_rack_rsolid",
]


# ---------------------------------------------------------------------------
# Involute geometry helpers
# ---------------------------------------------------------------------------

def _involute_point(base_radius: float, t: float) -> Tuple[float, float]:
    """Return a point on the involute of a circle at parameter *t*."""
    return (
        base_radius * (math.cos(t) + t * math.sin(t)),
        base_radius * (math.sin(t) - t * math.cos(t)),
    )


def _involute_t_for_radius(base_radius: float, target_radius: float) -> float:
    """Solve the involute parameter *t* for a given radial distance."""
    ratio = target_radius / base_radius
    return math.sqrt(max(ratio * ratio - 1.0, 0.0))


def _rotate_xy(point: Tuple[float, float], angle: float) -> Tuple[float, float]:
    """Rotate a 2-D point about the origin by *angle* (radians)."""
    ca, sa = math.cos(angle), math.sin(angle)
    return (point[0] * ca - point[1] * sa, point[0] * sa + point[1] * ca)


def _unit_xy(angle: float) -> Tuple[float, float]:
    return (math.cos(angle), math.sin(angle))


def _cubic_bezier_bspline(
    control_points: List[Tuple[float, float]],
) -> Tuple[List[List[float]], int, List[float], List[int]]:
    return [[x, y] for x, y in control_points], 3, [0.0, 1.0], [4, 4]


def _involute_bspline_control_points(
    base_radius: float,
    tip_radius: float,
    start_radius: float,
    start_angle: float,
    mirror: bool,
    reverse: bool = False,
    n_segments: int = 6,
) -> Tuple[List[List[float]], int, List[float], List[int]]:
    """Fit one analytic involute flank using the shared cubic B-spline helper."""
    t_start = _involute_t_for_radius(base_radius, start_radius)
    t_end = _involute_t_for_radius(base_radius, tip_radius)
    sample_count = max(8, int(n_segments) * 8 + 1)

    samples: List[Tuple[float, float]] = []
    for index in range(sample_count):
        frac = index / (sample_count - 1)
        t = t_start + (t_end - t_start) * frac
        point = _involute_point(base_radius, t)
        if mirror:
            point = (point[0], -point[1])
        samples.append(_rotate_xy(point, start_angle))

    if reverse:
        samples = list(reversed(samples))

    fit = fit_cubic_bspline_control_points(
        samples,
        tolerance=1e-4,
        fairing=1e-8,
    )
    return (
        [[float(x), float(y)] for x, y in fit.control_points],
        int(fit.degree),
        [float(knot) for knot in fit.unique_knots],
        [int(multiplicity) for multiplicity in fit.multiplicities],
    )


def _root_fillet_control_points(
    start: Tuple[float, float],
    end: Tuple[float, float],
    start_tangent_angle: float,
    end_tangent_angle: float,
) -> Tuple[List[List[float]], int, List[float], List[int]]:
    """Approximate the generated root transition with a tangent cubic fillet."""
    chord = math.hypot(end[0] - start[0], end[1] - start[1])
    handle = chord * 0.45
    ts = _unit_xy(start_tangent_angle)
    te = _unit_xy(end_tangent_angle)
    controls = [
        start,
        (start[0] + ts[0] * handle, start[1] + ts[1] * handle),
        (end[0] - te[0] * handle, end[1] - te[1] * handle),
        end,
    ]
    return _cubic_bezier_bspline(controls)


def _compute_tooth_geometry(
    n_teeth: int,
    module: float,
    pressure_angle: float,
    root_radius: Optional[float] = None,
    tip_radius: Optional[float] = None,
) -> dict:
    """Compute geometric parameters for an involute tooth-space profile."""
    pitch_radius = module * n_teeth / 2.0
    base_radius = pitch_radius * math.cos(pressure_angle)
    resolved_tip_radius = pitch_radius + module if tip_radius is None else float(tip_radius)
    resolved_root_radius = (
        max(pitch_radius - 1.25 * module, base_radius * 0.5)
        if root_radius is None else float(root_radius)
    )
    tooth_angle = 2.0 * math.pi / n_teeth

    pitch_half_angle = (math.pi * module / 2.0) / (2.0 * pitch_radius)
    inv_alpha = math.tan(pressure_angle) - pressure_angle
    base_half_angle = pitch_half_angle + inv_alpha

    left_start = -base_half_angle
    right_start = +base_half_angle

    t_tip = _involute_t_for_radius(base_radius, resolved_tip_radius)
    tip_half_span = t_tip - math.atan(t_tip)
    left_tip_angle = left_start + tip_half_span
    right_tip_angle = right_start - tip_half_span

    return {
        "pitch_radius": pitch_radius,
        "base_radius": base_radius,
        "tip_radius": resolved_tip_radius,
        "root_radius": resolved_root_radius,
        "tooth_angle": tooth_angle,
        "left_start": left_start,
        "right_start": right_start,
        "left_tip_angle": left_tip_angle,
        "right_tip_angle": right_tip_angle,
        "prev_right_start": right_start - tooth_angle,
    }


# ---------------------------------------------------------------------------
# Constraint-sketch-driven gear profile (B-spline flanks + arc root/tip)
# ---------------------------------------------------------------------------

def _build_gear_profile_face(
    n_teeth: int,
    module: float,
    pressure_angle: float,
    return_sketch: bool = False,
    root_radius: Optional[float] = None,
    tip_radius: Optional[float] = None,
    build_face: bool = True,
):
    """Build the full gear 2-D profile as a Face via a constraint sketch.

    Each tooth contributes:
      - arc (root, previous tooth to this tooth)
      - optional tangent fillet (root to base, left side)
      - bspline (left visible involute flank to tip)
      - arc (tip, left to right)
      - bspline (right involute flank to visible flank start)
      - optional tangent fillet (base to root, right side)

    Construction circles (root, pitch, tip) carry radius + concentric
    constraints.  Profile continuity is expressed by shared point ids.
    """
    geo = _compute_tooth_geometry(
        n_teeth, module, pressure_angle,
        root_radius=root_radius, tip_radius=tip_radius,
    )
    root_radius = geo["root_radius"]
    base_radius = geo["base_radius"]
    tip_radius = geo["tip_radius"]
    tooth_angle = geo["tooth_angle"]
    left_start = geo["left_start"]
    right_start = geo["right_start"]
    left_tip_angle = geo["left_tip_angle"]
    right_tip_angle = geo["right_tip_angle"]
    flank_start_radius = max(base_radius, root_radius)
    needs_root_connectors = root_radius < base_radius - 1e-8
    t_flank_start = _involute_t_for_radius(base_radius, flank_start_radius)
    flank_start_span = t_flank_start - math.atan(t_flank_start)
    left_flank_start_angle = left_start + flank_start_span
    right_flank_start_angle = right_start - flank_start_span
    root_left_angle = left_start if needs_root_connectors else left_flank_start_angle
    root_right_angle = right_start if needs_root_connectors else right_flank_start_angle
    prev_right_start = root_right_angle - tooth_angle

    sketch = make_sketch_rsketch(name=f"gear_{n_teeth}t_m{module}", plane="XY")

    # Add center point for construction circles
    sketch = add_point_rsketch(sketch, "center", 0.0, 0.0)
    sketch = constrain_fix_rsketch(sketch, "center")

    # Construction circles
    sketch = add_circle_rsketch(sketch, "root_circle", "center", root_radius, construction=True)
    sketch = add_circle_rsketch(sketch, "pitch_circle", "center", geo["pitch_radius"], construction=True)
    sketch = add_circle_rsketch(sketch, "tip_circle", "center", tip_radius, construction=True)
    sketch = constrain_radius_rsketch(sketch, "root_circle", root_radius)
    sketch = constrain_radius_rsketch(sketch, "pitch_circle", geo["pitch_radius"])
    sketch = constrain_radius_rsketch(sketch, "tip_circle", tip_radius)
    sketch = constrain_concentric_rsketch(sketch, "root_circle", "pitch_circle")
    sketch = constrain_concentric_rsketch(sketch, "tip_circle", "pitch_circle")

    # Pre-compute all tooth geometry
    tooth_data = []
    for i in range(n_teeth):
        offset = tooth_angle * i
        a_root_start = prev_right_start + offset
        a_root_end = root_left_angle + offset
        a_base_start = left_flank_start_angle + offset
        a_base_end = right_flank_start_angle + offset
        a_tip_start = left_tip_angle + offset
        a_tip_end = right_tip_angle + offset

        tooth_data.append({
            "rs": (root_radius * math.cos(a_root_start), root_radius * math.sin(a_root_start)),
            "re": (root_radius * math.cos(a_root_end), root_radius * math.sin(a_root_end)),
            "bs": (flank_start_radius * math.cos(a_base_start), flank_start_radius * math.sin(a_base_start)),
            "be": (flank_start_radius * math.cos(a_base_end), flank_start_radius * math.sin(a_base_end)),
            "ts": (tip_radius * math.cos(a_tip_start), tip_radius * math.sin(a_tip_start)),
            "te": (tip_radius * math.cos(a_tip_end), tip_radius * math.sin(a_tip_end)),
        })

    # Phase 1: Add resolved profile points. Edges share these ids to express
    # coincident endpoints without hundreds of redundant fix constraints.
    for i, td in enumerate(tooth_data):
        for key, (px, py) in [("rs", td["rs"]), ("re", td["re"]), ("bs", td["bs"]),
                               ("be", td["be"]), ("ts", td["ts"]), ("te", td["te"])]:
            pid = f"t{i}_{key}"
            sketch = add_point_rsketch(sketch, pid, px, py)

    # Phase 2: Add all edges
    for i, td in enumerate(tooth_data):
        rs_id = f"t{i}_rs"
        re_id = f"t{i}_re"
        bs_id = f"t{i}_bs" if needs_root_connectors else re_id
        be_id = f"t{i}_be"
        ts_id = f"t{i}_ts"
        te_id = f"t{i}_te"
        next_rs_id = f"t{(i+1)%n_teeth}_rs"
        right_flank_end_id = be_id if needs_root_connectors else next_rs_id

        # Root arc: rs → re
        sketch = add_arc_rsketch(sketch, f"arc_root_{i}", rs_id, re_id, "center")

        # Tangent root fillet: re -> bs (only when root lies inside base circle)
        if needs_root_connectors:
            fillet_cps, fillet_deg, fillet_knots, fillet_mults = _root_fillet_control_points(
                td["re"], td["bs"],
                start_tangent_angle=root_left_angle + tooth_angle * i + math.pi / 2.0,
                end_tangent_angle=left_start + tooth_angle * i,
            )
            sketch = add_bspline_rsketch(
                sketch, f"fillet_left_{i}", re_id, f"t{i}_bs",
                control_points=fillet_cps, degree=fillet_deg,
                knots=fillet_knots, multiplicities=fillet_mults,
            )

        # Left involute flank: bs → ts (B-spline)
        left_cps, left_deg, left_knots, left_mults = _involute_bspline_control_points(
            base_radius, tip_radius, flank_start_radius,
            start_angle=left_start + tooth_angle * i,
            mirror=False,
        )
        sketch = add_bspline_rsketch(
            sketch, f"bspline_left_{i}", bs_id, ts_id,
            control_points=left_cps, degree=left_deg,
            knots=left_knots, multiplicities=left_mults,
        )

        # Tip arc: ts → te
        sketch = add_arc_rsketch(sketch, f"arc_tip_{i}", ts_id, te_id, "center")

        # Right involute flank: te → be (B-spline)
        right_cps, right_deg, right_knots, right_mults = _involute_bspline_control_points(
            base_radius, tip_radius, flank_start_radius,
            start_angle=right_start + tooth_angle * i,
            mirror=True,
            reverse=True,
        )
        sketch = add_bspline_rsketch(
            sketch, f"bspline_right_{i}", te_id, right_flank_end_id,
            control_points=right_cps, degree=right_deg,
            knots=right_knots, multiplicities=right_mults,
        )

        # Tangent root fillet: be -> next rs (only when root lies inside base circle)
        if needs_root_connectors:
            next_td = tooth_data[(i + 1) % n_teeth]
            fillet_cps, fillet_deg, fillet_knots, fillet_mults = _root_fillet_control_points(
                td["be"], next_td["rs"],
                start_tangent_angle=right_start + tooth_angle * i + math.pi,
                end_tangent_angle=root_right_angle + tooth_angle * i + math.pi / 2.0,
            )
            sketch = add_bspline_rsketch(
                sketch, f"fillet_right_{i}", be_id, next_rs_id,
                control_points=fillet_cps, degree=fillet_deg,
                knots=fillet_knots, multiplicities=fillet_mults,
            )

    face = make_face_from_sketch_rface(sketch, profile=0) if build_face else None
    if return_sketch:
        return face, sketch
    if face is None:
        return make_face_from_sketch_rface(sketch, profile=0)
    return face


def _rotate_profile_wire_3d(
    wire: Wire, angle_deg: float, z: float,
) -> Wire:
    """Return a copy of *wire* rotated about Z and translated to height *z*."""
    rotated = rotate_shape(wire, angle_deg, axis=(0, 0, 1), origin=(0, 0, 0))
    if z != 0.0:
        rotated = translate_shape(rotated, (0.0, 0.0, z))
    return rotated


def _profile_face_to_wire(face: Face) -> Wire:
    """Extract the outer wire from a profile face."""
    return face.get_outer_wire()


# ---------------------------------------------------------------------------
# Public API: External gears
# ---------------------------------------------------------------------------

def make_spur_gear_rsolid(
    n_teeth: int,
    module: float,
    pressure_angle: float = 20.0,
    gear_height: float = 6.0,
) -> Solid:
    """Create an involute spur gear (straight teeth, helix angle = 0).

    Parameters
    ----------
    n_teeth : int
        Number of teeth (>= 3).
    module : float
        Gear module in mm (pitch diameter = module * n_teeth).
    pressure_angle : float, default 20
        Pressure angle in degrees.
    gear_height : float, default 6.0
        Gear thickness / extrusion height along Z in mm.
    """
    if n_teeth < 3:
        raise ValueError("n_teeth must be at least 3")
    if module <= 0:
        raise ValueError("module must be positive")
    if gear_height <= 0:
        raise ValueError("gear_height must be positive")

    pa = math.radians(pressure_angle)
    face = _build_gear_profile_face(n_teeth, module, pa)
    return extrude_rsolid(face, direction=(0.0, 0.0, 1.0), distance=gear_height)


def make_helical_gear_rsolid(
    n_teeth: int,
    module: float,
    pressure_angle: float = 20.0,
    helix_angle: float = 30.0,
    gear_height: float = 8.0,
) -> Solid:
    """Create an involute helical gear.

    Parameters
    ----------
    n_teeth : int
        Number of teeth (>= 3).
    module : float
        Gear module in mm.
    pressure_angle : float, default 20
        Pressure angle in degrees.
    helix_angle : float, default 30
        Helix angle in degrees.
    gear_height : float, default 8.0
        Gear thickness along Z in mm.
    """
    if n_teeth < 3:
        raise ValueError("n_teeth must be at least 3")
    if module <= 0:
        raise ValueError("module must be positive")
    if gear_height <= 0:
        raise ValueError("gear_height must be positive")
    if helix_angle == 0:
        return make_spur_gear_rsolid(n_teeth, module, pressure_angle, gear_height)

    pa = math.radians(pressure_angle)
    pitch_diameter = module * n_teeth
    twist_total = math.degrees(
        2.0 * math.pi * gear_height * math.tan(math.radians(helix_angle))
        / (math.pi * pitch_diameter)
    )

    n_sections = max(6, int(abs(twist_total) / 5.0) + 2)
    _, sketch = _build_gear_profile_face(
        n_teeth, module, pa, return_sketch=True, build_face=False,
    )
    base_wire = make_wire_from_sketch_rwire(sketch)

    sections = []
    for i in range(n_sections + 1):
        frac = i / n_sections
        z = gear_height * frac
        twist = twist_total * frac
        sections.append(_rotate_profile_wire_3d(base_wire, twist, z))

    return loft_rsolid(sections, ruled=False)


def make_herringbone_gear_rsolid(
    n_teeth: int,
    module: float,
    pressure_angle: float = 20.0,
    helix_angle: float = 32.0,
    gear_height: float = 10.0,
) -> Solid:
    """Create an involute herringbone (double-helical) gear.

    Parameters
    ----------
    n_teeth : int
        Number of teeth (>= 3).
    module : float
        Gear module in mm.
    pressure_angle : float, default 20
        Pressure angle in degrees.
    helix_angle : float, default 32
        Helix angle of each half in degrees.
    gear_height : float, default 10.0
        Total gear thickness along Z in mm.
    """
    if n_teeth < 3:
        raise ValueError("n_teeth must be at least 3")
    if module <= 0:
        raise ValueError("module must be positive")
    if gear_height <= 0:
        raise ValueError("gear_height must be positive")
    if helix_angle == 0:
        return make_spur_gear_rsolid(n_teeth, module, pressure_angle, gear_height)

    pa = math.radians(pressure_angle)
    pitch_diameter = module * n_teeth
    half_height = gear_height / 2.0
    half_twist = math.degrees(
        2.0 * math.pi * half_height * math.tan(math.radians(helix_angle))
        / (math.pi * pitch_diameter)
    )

    n_sections_per_half = max(4, int(abs(half_twist) / 5.0) + 2)
    _, sketch = _build_gear_profile_face(
        n_teeth, module, pa, return_sketch=True, build_face=False,
    )
    base_wire = make_wire_from_sketch_rwire(sketch)

    sections: List[Wire] = []

    for i in range(n_sections_per_half + 1):
        frac = i / n_sections_per_half
        z = half_height * frac
        twist = half_twist * frac
        sections.append(_rotate_profile_wire_3d(base_wire, twist, z))

    for i in range(1, n_sections_per_half + 1):
        frac = i / n_sections_per_half
        z = half_height + half_height * frac
        twist = half_twist * (1.0 - frac)
        sections.append(_rotate_profile_wire_3d(base_wire, twist, z))

    return loft_rsolid(sections, ruled=False)


# ---------------------------------------------------------------------------
# Internal ring gears (multi-loop profile faces)
# ---------------------------------------------------------------------------

def _internal_ring_radii(
    n_teeth: int,
    module: float,
    rim_thickness: float,
) -> Tuple[float, float, float, float]:
    """Return (pitch, internal tooth tip, internal root, outer rim) radii."""
    pitch_radius = module * n_teeth / 2.0
    internal_tip_radius = pitch_radius - module
    internal_root_radius = pitch_radius + 1.25 * module
    outer_radius = internal_root_radius + rim_thickness
    return pitch_radius, internal_tip_radius, internal_root_radius, outer_radius


def _compute_internal_tooth_geometry(
    n_teeth: int,
    module: float,
    pressure_angle: float,
    backlash: float = 0.0,
) -> dict:
    """Compute the inward-facing tooth boundary for an internal gear."""
    backlash_value = float(backlash)
    if not math.isfinite(backlash_value):
        raise ValueError("backlash must be finite")
    if backlash_value < 0:
        raise ValueError("backlash must be non-negative")

    pitch_radius, tip_radius, root_radius, _outer_radius = _internal_ring_radii(
        n_teeth, module, rim_thickness=0.0,
    )
    if tip_radius <= 0:
        raise ValueError("internal tooth tip radius must be positive")

    base_radius = pitch_radius * math.cos(pressure_angle)
    tooth_angle = 2.0 * math.pi / n_teeth
    pitch_half_angle = (math.pi * module / 2.0) / (2.0 * pitch_radius)
    inv_alpha = math.tan(pressure_angle) - pressure_angle
    backlash_half_angle = backlash_value / (2.0 * pitch_radius)
    base_half_angle = pitch_half_angle - inv_alpha - backlash_half_angle

    def internal_half_angle(radius: float) -> float:
        t = _involute_t_for_radius(base_radius, max(radius, base_radius))
        inv_r = t - math.atan(t)
        return base_half_angle + inv_r

    flank_tip_radius = max(base_radius, tip_radius)
    needs_tip_connectors = tip_radius < base_radius - 1e-8
    tip_half_angle = internal_half_angle(flank_tip_radius)
    root_half_angle = internal_half_angle(root_radius)

    return {
        "pitch_radius": pitch_radius,
        "base_radius": base_radius,
        "tip_radius": tip_radius,
        "root_radius": root_radius,
        "flank_tip_radius": flank_tip_radius,
        "needs_tip_connectors": needs_tip_connectors,
        "tooth_angle": tooth_angle,
        "backlash": backlash_value,
        "backlash_half_angle": backlash_half_angle,
        "left_base_angle": -base_half_angle,
        "right_base_angle": base_half_angle,
        "left_tip_angle": -tip_half_angle,
        "right_tip_angle": tip_half_angle,
        "left_root_angle": -root_half_angle,
        "right_root_angle": root_half_angle,
    }


def _internal_involute_bspline_control_points(
    base_radius: float,
    start_radius: float,
    end_radius: float,
    start_angle: float,
    mirror: bool,
    reverse: bool = False,
) -> Tuple[List[List[float]], int, List[float], List[int]]:
    """Build one true internal-gear involute flank as a B-spline."""
    return _involute_bspline_control_points(
        base_radius,
        tip_radius=end_radius,
        start_radius=start_radius,
        start_angle=start_angle,
        mirror=mirror,
        reverse=reverse,
    )


def _build_internal_gear_profile_wire(
    n_teeth: int,
    module: float,
    pressure_angle: float,
    return_sketch: bool = False,
    backlash: float = 0.0,
):
    """Build the inner boundary wire for an inward-facing internal gear."""
    geo = _compute_internal_tooth_geometry(n_teeth, module, pressure_angle, backlash)
    root_radius = geo["root_radius"]
    tip_radius = geo["tip_radius"]
    flank_tip_radius = geo["flank_tip_radius"]
    base_radius = geo["base_radius"]
    tooth_angle = geo["tooth_angle"]
    needs_tip_connectors = geo["needs_tip_connectors"]

    sketch = make_sketch_rsketch(name=f"internal_gear_{n_teeth}t_m{module}", plane="XY")
    sketch = add_point_rsketch(sketch, "center", 0.0, 0.0)
    sketch = constrain_fix_rsketch(sketch, "center")

    sketch = add_circle_rsketch(sketch, "tip_circle", "center", tip_radius, construction=True)
    sketch = add_circle_rsketch(sketch, "pitch_circle", "center", geo["pitch_radius"], construction=True)
    sketch = add_circle_rsketch(sketch, "root_circle", "center", root_radius, construction=True)
    sketch = constrain_radius_rsketch(sketch, "tip_circle", tip_radius)
    sketch = constrain_radius_rsketch(sketch, "pitch_circle", geo["pitch_radius"])
    sketch = constrain_radius_rsketch(sketch, "root_circle", root_radius)
    sketch = constrain_concentric_rsketch(sketch, "tip_circle", "pitch_circle")
    sketch = constrain_concentric_rsketch(sketch, "root_circle", "pitch_circle")

    tooth_data = []
    for i in range(n_teeth):
        offset = tooth_angle * i
        root_arc_start_angle = geo["right_root_angle"] - tooth_angle + offset
        root_arc_end_angle = geo["left_root_angle"] + offset
        left_root_angle = geo["left_root_angle"] + offset
        right_root_angle = geo["right_root_angle"] + offset
        left_tip_angle = geo["left_tip_angle"] + offset
        right_tip_angle = geo["right_tip_angle"] + offset

        tooth_data.append({
            "rs": (root_radius * math.cos(root_arc_start_angle), root_radius * math.sin(root_arc_start_angle)),
            "re": (root_radius * math.cos(root_arc_end_angle), root_radius * math.sin(root_arc_end_angle)),
            "lb": (flank_tip_radius * math.cos(left_tip_angle), flank_tip_radius * math.sin(left_tip_angle)),
            "lt": (tip_radius * math.cos(left_tip_angle), tip_radius * math.sin(left_tip_angle)),
            "rt": (tip_radius * math.cos(right_tip_angle), tip_radius * math.sin(right_tip_angle)),
            "rb": (flank_tip_radius * math.cos(right_tip_angle), flank_tip_radius * math.sin(right_tip_angle)),
            "rr": (root_radius * math.cos(right_root_angle), root_radius * math.sin(right_root_angle)),
            "left_root_angle": left_root_angle,
            "right_root_angle": right_root_angle,
            "left_tip_angle": left_tip_angle,
            "right_tip_angle": right_tip_angle,
        })

    point_keys = ["rs", "re", "lb", "lt", "rt", "rb", "rr"]
    for i, td in enumerate(tooth_data):
        for key in point_keys:
            px, py = td[key]
            pid = f"t{i}_{key}"
            sketch = add_point_rsketch(sketch, pid, px, py)

    for i, td in enumerate(tooth_data):
        rs_id = f"t{i}_rs"
        re_id = f"t{i}_re"
        lb_id = f"t{i}_lb"
        lt_id = f"t{i}_lt"
        rt_id = f"t{i}_rt"
        rb_id = f"t{i}_rb"
        next_rs_id = f"t{(i + 1) % n_teeth}_rs"

        sketch = add_arc_rsketch(sketch, f"arc_internal_root_{i}", rs_id, re_id, "center")

        left_cps, left_deg, left_knots, left_mults = _internal_involute_bspline_control_points(
            base_radius,
            start_radius=flank_tip_radius,
            end_radius=root_radius,
            start_angle=geo["left_base_angle"] + tooth_angle * i,
            mirror=True,
            reverse=True,
        )
        sketch = add_bspline_rsketch(
            sketch, f"bspline_internal_left_{i}", re_id, lb_id,
            control_points=left_cps, degree=left_deg,
            knots=left_knots, multiplicities=left_mults,
        )

        if needs_tip_connectors:
            transition_angle = math.atan2(td["lt"][1] - td["lb"][1], td["lt"][0] - td["lb"][0])
            cps, deg, knots, mults = _root_fillet_control_points(
                td["lb"], td["lt"], transition_angle, transition_angle,
            )
            sketch = add_bspline_rsketch(
                sketch, f"transition_internal_left_{i}", lb_id, lt_id,
                control_points=cps, degree=deg,
                knots=knots, multiplicities=mults,
            )
            tip_left_id = lt_id
            tip_right_id = rt_id
        else:
            tip_left_id = lb_id
            tip_right_id = rb_id

        sketch = add_arc_rsketch(sketch, f"arc_internal_tip_{i}", tip_left_id, tip_right_id, "center")

        if needs_tip_connectors:
            transition_angle = math.atan2(td["rb"][1] - td["rt"][1], td["rb"][0] - td["rt"][0])
            cps, deg, knots, mults = _root_fillet_control_points(
                td["rt"], td["rb"], transition_angle, transition_angle,
            )
            sketch = add_bspline_rsketch(
                sketch, f"transition_internal_right_{i}", rt_id, rb_id,
                control_points=cps, degree=deg,
                knots=knots, multiplicities=mults,
            )

        right_cps, right_deg, right_knots, right_mults = _internal_involute_bspline_control_points(
            base_radius,
            start_radius=flank_tip_radius,
            end_radius=root_radius,
            start_angle=geo["right_base_angle"] + tooth_angle * i,
            mirror=False,
        )
        sketch = add_bspline_rsketch(
            sketch, f"bspline_internal_right_{i}", rb_id, next_rs_id,
            control_points=right_cps, degree=right_deg,
            knots=right_knots, multiplicities=right_mults,
        )

    wire = make_wire_from_sketch_rwire(sketch, profile=0)
    if return_sketch:
        return wire, sketch
    return wire


def _build_ring_gear_face(
    n_teeth: int,
    module: float,
    pressure_angle: float,
    rim_thickness: float,
    backlash: float = 0.0,
) -> Face:
    """Build the 2-D ring-gear face directly from outer and inner loops."""
    _pitch_radius, _internal_tip_radius, _internal_root_radius, outer_radius = _internal_ring_radii(
        n_teeth, module, rim_thickness,
    )

    outer_wire = make_circle_rwire(center=(0.0, 0.0, 0.0), radius=outer_radius)
    inner_wire = _build_internal_gear_profile_wire(
        n_teeth, module, pressure_angle, backlash=backlash,
    )
    return make_face_from_wires_rface(outer_wire, [inner_wire])


def make_spur_ring_gear_rsolid(
    n_teeth: int,
    module: float,
    pressure_angle: float = 20.0,
    gear_height: float = 6.0,
    rim_thickness: float = 3.0,
    backlash: float = 0.0,
) -> Solid:
    """Create an internal spur ring gear.

    Parameters
    ----------
    n_teeth : int
        Number of internal teeth (>= 3).
    module : float
        Gear module in mm.
    pressure_angle : float, default 20
        Pressure angle in degrees.
    gear_height : float, default 6.0
        Ring gear thickness along Z in mm.
    rim_thickness : float, default 3.0
        Thickness of the rim beyond the tooth tips in mm.
    backlash : float, default 0.0
        Circumferential tooth-space clearance at the pitch circle in mm.
    """
    if n_teeth < 3:
        raise ValueError("n_teeth must be at least 3")
    if module <= 0:
        raise ValueError("module must be positive")
    if gear_height <= 0:
        raise ValueError("gear_height must be positive")
    if rim_thickness <= 0:
        raise ValueError("rim_thickness must be positive")

    pa = math.radians(pressure_angle)
    face = _build_ring_gear_face(n_teeth, module, pa, rim_thickness, backlash)
    return extrude_rsolid(face, direction=(0.0, 0.0, 1.0), distance=gear_height)


def make_helical_ring_gear_rsolid(
    n_teeth: int,
    module: float,
    pressure_angle: float = 20.0,
    helix_angle: float = 25.0,
    gear_height: float = 8.0,
    rim_thickness: float = 3.0,
    backlash: float = 0.0,
) -> Solid:
    """Create an internal helical ring gear."""
    if helix_angle == 0:
        return make_spur_ring_gear_rsolid(
            n_teeth, module, pressure_angle, gear_height, rim_thickness, backlash,
        )

    pa = math.radians(pressure_angle)
    pitch_diameter = module * n_teeth
    twist_total = math.degrees(
        2.0 * math.pi * gear_height * math.tan(math.radians(helix_angle))
        / (math.pi * pitch_diameter)
    )

    n_sections = max(6, int(abs(twist_total) / 5.0) + 2)
    _pitch_radius, _internal_tip_radius, _internal_root_radius, outer_radius = _internal_ring_radii(
        n_teeth, module, rim_thickness,
    )

    outer_wire = make_circle_rwire(center=(0.0, 0.0, 0.0), radius=outer_radius)
    outer_solid = extrude_rsolid(
        make_face_from_wire_rface(outer_wire),
        direction=(0.0, 0.0, 1.0),
        distance=gear_height,
    )
    inner_wire = _build_internal_gear_profile_wire(n_teeth, module, pa, backlash=backlash)

    inner_sections = []
    for i in range(n_sections + 1):
        frac = i / n_sections
        z = gear_height * frac
        twist = twist_total * frac
        inner_sections.append(_rotate_profile_wire_3d(inner_wire, twist, z))

    inner_loft = loft_rsolid(inner_sections, ruled=False)
    return cut_rsolid(outer_solid, inner_loft)


def make_herringbone_ring_gear_rsolid(
    n_teeth: int,
    module: float,
    pressure_angle: float = 20.0,
    helix_angle: float = 30.0,
    gear_height: float = 10.0,
    rim_thickness: float = 3.0,
    backlash: float = 0.0,
) -> Solid:
    """Create an internal herringbone ring gear."""
    if helix_angle == 0:
        return make_spur_ring_gear_rsolid(
            n_teeth, module, pressure_angle, gear_height, rim_thickness, backlash,
        )

    pa = math.radians(pressure_angle)
    pitch_diameter = module * n_teeth
    half_height = gear_height / 2.0
    half_twist = math.degrees(
        2.0 * math.pi * half_height * math.tan(math.radians(helix_angle))
        / (math.pi * pitch_diameter)
    )

    n_sections_per_half = max(4, int(abs(half_twist) / 5.0) + 2)
    _pitch_radius, _internal_tip_radius, _internal_root_radius, outer_radius = _internal_ring_radii(
        n_teeth, module, rim_thickness,
    )

    outer_wire = make_circle_rwire(center=(0.0, 0.0, 0.0), radius=outer_radius)
    outer_solid = extrude_rsolid(
        make_face_from_wire_rface(outer_wire),
        direction=(0.0, 0.0, 1.0),
        distance=gear_height,
    )
    inner_wire = _build_internal_gear_profile_wire(n_teeth, module, pa, backlash=backlash)

    inner_sections: List[Wire] = []

    for i in range(n_sections_per_half + 1):
        frac = i / n_sections_per_half
        z = half_height * frac
        twist = half_twist * frac
        inner_sections.append(_rotate_profile_wire_3d(inner_wire, twist, z))

    for i in range(1, n_sections_per_half + 1):
        frac = i / n_sections_per_half
        z = half_height + half_height * frac
        twist = half_twist * (1.0 - frac)
        inner_sections.append(_rotate_profile_wire_3d(inner_wire, twist, z))

    inner_loft = loft_rsolid(inner_sections, ruled=False)
    return cut_rsolid(outer_solid, inner_loft)


# ---------------------------------------------------------------------------
# Racks (straight / helical / herringbone)
# ---------------------------------------------------------------------------

def _build_rack_profile_points(
    module: float,
    n_teeth: int,
    pressure_angle: float,
) -> List[Tuple[float, float]]:
    """Compute a straight rack profile as a point list (trapezoidal teeth)."""
    addendum = module
    dedendum = 1.25 * module
    pitch = math.pi * module
    half_tooth = pitch / 2.0

    flank_offset = addendum * math.tan(pressure_angle)
    root_flank_offset = dedendum * math.tan(pressure_angle)

    total_width = n_teeth * pitch
    x_start = -total_width / 2.0

    points: List[Tuple[float, float]] = []
    points.append((x_start, -dedendum))

    for i in range(n_teeth):
        x0 = x_start + i * pitch
        x_pitch_left = x0 + half_tooth / 2.0
        x_tip_left = x_pitch_left - flank_offset
        x_tip_right = x_pitch_left + half_tooth + flank_offset
        x_root_right = x0 + pitch

        points.append((x0 + root_flank_offset, -dedendum))
        points.append((x_tip_left, addendum))
        points.append((x_tip_right, addendum))
        points.append((x_root_right - root_flank_offset, -dedendum))

    points.append((x_start + total_width, -dedendum))
    return points


def _build_rack_profile_face(
    module: float,
    n_teeth: int,
    pressure_angle: float,
) -> Face:
    """Build the rack 2-D profile face via a constraint sketch (line loop)."""
    points = _build_rack_profile_points(module, n_teeth, pressure_angle)

    sketch = make_sketch_rsketch(name=f"rack_m{module}_n{n_teeth}", plane="XY")

    for idx, (px, py) in enumerate(points):
        sketch = add_point_rsketch(sketch, f"p{idx}", px, py)

    for idx in range(len(points)):
        nxt = (idx + 1) % len(points)
        sketch = add_line_rsketch(sketch, f"l{idx}", f"p{idx}", f"p{nxt}")

    return make_face_from_sketch_rface(sketch, profile=0)


def make_spur_rack_rsolid(
    module: float,
    n_teeth: int = 10,
    pressure_angle: float = 20.0,
    rack_height: float = 6.0,
) -> Solid:
    """Create a straight-tooth rack.

    Parameters
    ----------
    module : float
        Gear module in mm (tooth pitch = pi * module).
    n_teeth : int, default 10
        Number of teeth along the rack.
    pressure_angle : float, default 20
        Pressure angle in degrees.
    rack_height : float, default 6.0
        Rack thickness along Z in mm.
    """
    if module <= 0:
        raise ValueError("module must be positive")
    if n_teeth < 1:
        raise ValueError("n_teeth must be at least 1")
    if rack_height <= 0:
        raise ValueError("rack_height must be positive")

    pa = math.radians(pressure_angle)
    face = _build_rack_profile_face(module, n_teeth, pa)
    return extrude_rsolid(face, direction=(0.0, 0.0, 1.0), distance=rack_height)


def make_helical_rack_rsolid(
    module: float,
    n_teeth: int = 10,
    pressure_angle: float = 20.0,
    helix_angle: float = 25.0,
    rack_height: float = 8.0,
) -> Solid:
    """Create a helical rack."""
    if helix_angle == 0:
        return make_spur_rack_rsolid(module, n_teeth, pressure_angle, rack_height)

    pa = math.radians(pressure_angle)
    pitch = math.pi * module
    twist_total = math.degrees(
        2.0 * math.pi * rack_height * math.tan(math.radians(helix_angle))
        / (math.pi * pitch)
    )

    n_sections = max(6, int(abs(twist_total) / 5.0) + 2)
    face = _build_rack_profile_face(module, n_teeth, pa)
    base_wire = face.get_outer_wire()

    sections = []
    for i in range(n_sections + 1):
        frac = i / n_sections
        z = rack_height * frac
        twist = twist_total * frac
        sections.append(_rotate_profile_wire_3d(base_wire, twist, z))

    return loft_rsolid(sections, ruled=False)


def make_herringbone_rack_rsolid(
    module: float,
    n_teeth: int = 10,
    pressure_angle: float = 20.0,
    helix_angle: float = 30.0,
    rack_height: float = 10.0,
) -> Solid:
    """Create a herringbone rack."""
    if helix_angle == 0:
        return make_spur_rack_rsolid(module, n_teeth, pressure_angle, rack_height)

    pa = math.radians(pressure_angle)
    pitch = math.pi * module
    half_height = rack_height / 2.0
    half_twist = math.degrees(
        2.0 * math.pi * half_height * math.tan(math.radians(helix_angle))
        / (math.pi * pitch)
    )

    n_sections_per_half = max(4, int(abs(half_twist) / 5.0) + 2)
    face = _build_rack_profile_face(module, n_teeth, pa)
    base_wire = face.get_outer_wire()

    sections: List[Wire] = []

    for i in range(n_sections_per_half + 1):
        frac = i / n_sections_per_half
        z = half_height * frac
        twist = half_twist * frac
        sections.append(_rotate_profile_wire_3d(base_wire, twist, z))

    for i in range(1, n_sections_per_half + 1):
        frac = i / n_sections_per_half
        z = half_height + half_height * frac
        twist = half_twist * (1.0 - frac)
        sections.append(_rotate_profile_wire_3d(base_wire, twist, z))

    return loft_rsolid(sections, ruled=False)
