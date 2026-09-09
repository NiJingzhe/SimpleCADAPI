"""Formalized single-solid L-bracket for STEP and Gmsh workflows.

Rebuilt per the single-part-modeling workflow and the Feature Tree
Convention (block-structured features, named parameters). Geometry and
FEM interface tags are equivalent to the legacy direct-script version;
equivalence evidence lives in verify/ (external verification policy).
"""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad


OUT_DIR = Path(__file__).resolve().parent / "out"
PACKAGE_PATH = OUT_DIR / "ap242_gmsh_bracket.scadpkg"
CACHE = scad.CachePolicy(root=OUT_DIR / ".cache")

# ---- params ----
BRACKET_WIDTH = scad.var("bracket_width", 40.0, unit="mm")
BRACKET_HEIGHT = scad.var("bracket_height", 36.0, unit="mm")
BRACKET_DEPTH = scad.var("bracket_depth", 28.0, unit="mm")
PLATE_THICKNESS = scad.var("plate_thickness", 4.0, unit="mm")
MOUNT_HOLE_RADIUS = scad.var("mount_hole_radius", 2.5, unit="mm", tolerance=0.1)
MOUNT_HOLE_SPACING = scad.var("mount_hole_spacing", 22.0, unit="mm")
MOUNT_HOLE_HEIGHT_RATIO = scad.var("mount_hole_height_ratio", 0.62)
LOAD_HOLE_RADIUS = scad.var("load_hole_radius", 3.0, unit="mm", tolerance=0.1)
LOAD_HOLE_X = scad.var("load_hole_x", 12.0, unit="mm")
RIB_THICKNESS = scad.var("rib_thickness", 3.0, unit="mm")
RIB_HEIGHT = scad.var("rib_height", 18.0, unit="mm")
RIB_DEPTH = scad.var("rib_depth", 18.0, unit="mm")
RIB_OFFSET_Y = scad.var("rib_offset_y", 11.0, unit="mm")
CUT_OVERSHOOT = scad.var("cut_overshoot", 1.0, unit="mm")
TAG_MATCH_MAX_DISTANCE = 10.0  # face-matcher selection-parameter guard (mm)


def _f(scalar) -> float:
    """Evaluate a ScalarLike to a plain canonical float.

    Unit-declared vars cannot mix with unitless vars inside one expression
    (UnitValidationError at evaluate()), so every derived coordinate is
    computed here in plain-float space.
    """
    return float(scalar.evaluate()) if hasattr(scalar, "evaluate") else float(scalar)


def _assert_params() -> None:
    """Design-parameter feasibility guards (geometry checks live in verify/)."""
    t = _f(PLATE_THICKNESS)
    width = _f(BRACKET_WIDTH)
    height = _f(BRACKET_HEIGHT)
    depth = _f(BRACKET_DEPTH)
    spacing = _f(MOUNT_HOLE_SPACING)
    mount_r = _f(MOUNT_HOLE_RADIUS)
    ratio = _f(MOUNT_HOLE_HEIGHT_RATIO)
    load_r = _f(LOAD_HOLE_RADIUS)
    load_x = _f(LOAD_HOLE_X)
    rib_t = _f(RIB_THICKNESS)
    rib_h = _f(RIB_HEIGHT)
    rib_d = _f(RIB_DEPTH)
    rib_y = _f(RIB_OFFSET_Y)

    assert 0.0 < 2.0 * t < min(width, height, depth), "plate thickness must fit all spans"
    assert 2.0 * mount_r < spacing, "mount holes would merge"
    assert spacing / 2.0 + mount_r < width / 2.0, "mount holes outside wall width"
    assert 0.0 < ratio < 1.0, "mount hole height ratio must be in (0, 1)"
    hole_z = ratio * height
    assert mount_r < hole_z < height - mount_r, "mount hole outside wall height"
    assert -t / 2.0 + load_r < load_x < depth - t / 2.0 - load_r, "load hole outside shelf footprint"
    assert load_r < t / 2.0 + rib_y - rib_t / 2.0, "load hole would reach rib band"
    assert 2.0 * rib_y - rib_t > 0.0, "ribs would overlap at the symmetry plane"
    assert rib_y - rib_t / 2.0 > load_r, "ribs would collide with the load hole"
    assert rib_h + t <= height, "rib would overtop the wall"
    assert rib_d <= depth - t, "rib would overrun the shelf depth"
    assert _f(CUT_OVERSHOOT) > 0.0, "cut overshoot must be positive"


def _wall_body() -> scad.Solid:
    """Feature-block helper: the vertical mounting wall (basic box form)."""
    return scad.make_box_rsolid(
        width=PLATE_THICKNESS,
        height=BRACKET_WIDTH,
        depth=BRACKET_HEIGHT,
        bottom_face_center=(0.0, 0.0, 0.0),
        tag_prefix="bracket.wall",
    )


def _shelf_solid() -> scad.Solid:
    """Feature-block helper: the horizontal load shelf (basic box form)."""
    return scad.make_box_rsolid(
        width=BRACKET_DEPTH,
        height=BRACKET_WIDTH,
        depth=PLATE_THICKNESS,
        bottom_face_center=((_f(BRACKET_DEPTH) - _f(PLATE_THICKNESS)) / 2.0, 0.0, 0.0),
        tag_prefix="bracket.shelf",
    )


def _gusset_rib_solid(y_center: float) -> scad.Solid:
    """Feature-block helper: one transcribed triangular gusset rib."""
    t = _f(PLATE_THICKNESS)
    rib_t = _f(RIB_THICKNESS)
    y0 = y_center - rib_t / 2.0
    profile = scad.make_polyline_rwire(
        [
            (0.0, y0, t),
            (0.0, y0, t + _f(RIB_HEIGHT)),
            (_f(RIB_DEPTH), y0, t),
        ],
        closed=True,
    )
    face = scad.make_face_from_wire_rface(profile, normal=(0.0, 1.0, 0.0))
    return scad.extrude_rsolid(
        profile=face,
        direction=(0.0, 1.0, 0.0),
        distance=RIB_THICKNESS,
        tag_prefix="bracket.rib",
    )


def _mount_hole_tools() -> list[scad.Solid]:
    """Feature-block helper: through-cut tools for the wall mount holes."""
    t = _f(PLATE_THICKNESS)
    hole_z = _f(MOUNT_HOLE_HEIGHT_RATIO) * _f(BRACKET_HEIGHT)
    tools = []
    for index, y in enumerate(
        (-_f(MOUNT_HOLE_SPACING) / 2.0, _f(MOUNT_HOLE_SPACING) / 2.0),
        start=1,
    ):
        tools.append(
            scad.make_cylinder_rsolid(
                radius=MOUNT_HOLE_RADIUS,
                height=t + 2.0 * _f(CUT_OVERSHOOT),
                bottom_face_center=(-t / 2.0 - _f(CUT_OVERSHOOT), y, hole_z),
                axis=(1.0, 0.0, 0.0),
                tag_prefix=f"bracket.mount_hole_{index}",
            )
        )
    return tools


def _load_hole_tool() -> scad.Solid:
    """Feature-block helper: through-cut tool for the shelf load hole."""
    t = _f(PLATE_THICKNESS)
    return scad.make_cylinder_rsolid(
        radius=LOAD_HOLE_RADIUS,
        height=t + 2.0 * _f(CUT_OVERSHOOT),
        bottom_face_center=(_f(LOAD_HOLE_X), 0.0, -_f(CUT_OVERSHOOT)),
        axis=(0.0, 0.0, 1.0),
        tag_prefix="bracket.load_hole",
    )


def _tag_interface_face(
    body: scad.Solid,
    *,
    center: tuple[float, float, float],
    normal: tuple[float, float, float] | None,
    tag: str,
) -> scad.Solid:
    """interface-names helper: tag the final face nearest ``center``.

    Selection-parameter guard: a candidate must exist within
    TAG_MATCH_MAX_DISTANCE of the target center (parameter guard on the
    matcher, not a geometry verification).
    """
    candidates: list[tuple[float, scad.Face]] = []
    for face in scad.ql.faces().resolve(body):
        actual_center = face.get_center()
        if normal is not None:
            actual_normal = face.get_normal_at()
            alignment = (
                actual_normal.x * normal[0]
                + actual_normal.y * normal[1]
                + actual_normal.z * normal[2]
            )
            if alignment < 0.8:
                continue
        distance_sq = (
            (actual_center.x - center[0]) ** 2
            + (actual_center.y - center[1]) ** 2
            + (actual_center.z - center[2]) ** 2
        )
        candidates.append((distance_sq, face))
    if not candidates:
        raise ValueError(f"no final face matches {tag}")
    distance_sq, selected = min(candidates, key=lambda item: item[0])
    if distance_sq > TAG_MATCH_MAX_DISTANCE**2:
        raise ValueError(
            f"final face match for {tag} is too distant: distance^2={distance_sq}"
        )
    return scad.apply_tag_rselection(scope=body, targets=[selected], tag=tag)


def build_stage(stage: str) -> scad.Solid:
    """Return the body at a stage boundary ("s1" base+ribs, "s2" final)."""
    _assert_params()
    t = _f(PLATE_THICKNESS)
    rib_y = _f(RIB_OFFSET_Y)
    hole_z = _f(MOUNT_HOLE_HEIGHT_RATIO) * _f(BRACKET_HEIGHT)

    # ---- feature: wall (build) ----
    body = _wall_body()

    # ---- feature: shelf (add) ----
    body = scad.union_rsolid(body, _shelf_solid())

    # ---- feature: gusset-ribs (add, profile=geometry) ----
    body = scad.union_rsolid(
        body, _gusset_rib_solid(-rib_y), _gusset_rib_solid(rib_y)
    )
    if stage == "s1":
        return body

    # ---- feature: mount-holes (subtract, profile=geometry) ----
    body = scad.cut_rsolid(body, _mount_hole_tools(), skip_non_intersecting=False)

    # ---- feature: load-hole (subtract, profile=geometry) ----
    body = scad.cut_rsolid(body, _load_hole_tool(), skip_non_intersecting=False)

    # ---- feature: role-name (annotate) ----
    body = scad.apply_tag(body, "role.structural_l_bracket")

    # ---- feature: interface-names (annotate) ----
    body = _tag_interface_face(
        body,
        center=(0.0, 0.0, _f(BRACKET_HEIGHT) / 2.0),
        normal=(-1.0, 0.0, 0.0),
        tag="interface.fixed_support",
    )
    body = _tag_interface_face(
        body,
        center=((_f(BRACKET_DEPTH) + _f(RIB_DEPTH) - t) / 2.0, 0.0, t),
        normal=(0.0, 0.0, 1.0),
        tag="interface.load_surface",
    )
    for index, y in enumerate(
        (-_f(MOUNT_HOLE_SPACING) / 2.0, _f(MOUNT_HOLE_SPACING) / 2.0),
        start=1,
    ):
        body = _tag_interface_face(
            body,
            center=(t / 2.0, y, hole_z),
            normal=None,
            tag=f"interface.mount_hole_{index}",
        )
    body = _tag_interface_face(
        body,
        center=(_f(LOAD_HOLE_X), 0.0, t / 2.0),
        normal=None,
        tag="interface.load_hole",
    )
    return body


@scad.part(
    id="ap242_gmsh_bracket",
    revision="2.1.0",
    inputs=(scad.file_input(path="model.py"),),
    cache=CACHE,
)
def build_bracket() -> scad.Part:
    """Create one manifold L-bracket with named FEM boundary interfaces."""

    body = build_stage("s2")
    part = scad.make_part_rpart(
        part_id="ap242_gmsh_bracket",
        body=body,
        name="Named ribbed L-bracket",
    )
    material = scad.make_material_rmaterial(
        material_id="aluminum_6061_t6",
        name="Aluminum 6061-T6",
        density=2.70e-6,
        density_unit="kg/mm^3",
        color=(0.72, 0.74, 0.78),
    )
    return scad.assign_material_rpart(part, material)


def main() -> None:
    result = build_bracket()
    scad.capture(result, PACKAGE_PATH)
    print("product_package", PACKAGE_PATH)
    print("faces", len(scad.ql.faces().resolve(result.part.body)))
    print("volume", f"{result.part.body.get_volume():.3f}")


if __name__ == "__main__":
    main()
