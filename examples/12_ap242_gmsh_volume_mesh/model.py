"""Build a named single-solid L-bracket for STEP and Gmsh workflows."""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad


OUT_DIR = Path(__file__).resolve().parents[1] / "out" / "ap242_gmsh_volume_mesh"
PACKAGE_PATH = OUT_DIR / "ap242_gmsh_bracket.scadpkg"
CACHE = scad.CachePolicy(root=OUT_DIR / ".cache")

BRACKET_WIDTH = 40.0
BRACKET_HEIGHT = 36.0
BRACKET_DEPTH = 28.0
PLATE_THICKNESS = 4.0
MOUNT_HOLE_RADIUS = 2.5
MOUNT_HOLE_SPACING = 22.0
LOAD_HOLE_RADIUS = 3.0
LOAD_HOLE_X = 12.0
RIB_THICKNESS = 3.0
RIB_HEIGHT = 18.0
RIB_DEPTH = 18.0


def _tag_closest_face(
    body: scad.Solid,
    *,
    center: tuple[float, float, float],
    normal: tuple[float, float, float] | None,
    tag: str,
) -> scad.Solid:
    """Tag one final face while preserving the active graph source binding."""

    candidates: list[tuple[float, scad.Face]] = []
    for face in body.get_faces():
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
    if distance_sq > 100.0:
        raise ValueError(f"final face match for {tag} is too distant: distance^2={distance_sq}")
    return scad.apply_tag_rselection(scope=body, targets=[selected], tag=tag)


def _rib(*, y_center: float) -> scad.Solid:
    profile = scad.make_polyline_rwire(
        [
            (0.0, y_center - RIB_THICKNESS / 2.0, PLATE_THICKNESS),
            (0.0, y_center - RIB_THICKNESS / 2.0, PLATE_THICKNESS + RIB_HEIGHT),
            (RIB_DEPTH, y_center - RIB_THICKNESS / 2.0, PLATE_THICKNESS),
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


@scad.part(
    id="ap242_gmsh_bracket",
    revision="2.0.0",
    inputs=(scad.file_input(path="examples/12_ap242_gmsh_volume_mesh/model.py"),),
    cache=CACHE,
)
def build_bracket() -> scad.Part:
    """Create one manifold L-bracket with named FEM boundary interfaces."""

    wall = scad.make_box_rsolid(
        width=PLATE_THICKNESS,
        height=BRACKET_WIDTH,
        depth=BRACKET_HEIGHT,
        bottom_face_center=(0.0, 0.0, 0.0),
        tag_prefix="bracket.wall",
    )
    shelf = scad.make_box_rsolid(
        width=BRACKET_DEPTH,
        height=BRACKET_WIDTH,
        depth=PLATE_THICKNESS,
        bottom_face_center=(BRACKET_DEPTH / 2.0 - PLATE_THICKNESS / 2.0, 0.0, 0.0),
        tag_prefix="bracket.shelf",
    )
    body = scad.union_rsolid(wall, shelf, _rib(y_center=-11.0), _rib(y_center=11.0))

    cutters = []
    for index, y in enumerate(
        (-MOUNT_HOLE_SPACING / 2.0, MOUNT_HOLE_SPACING / 2.0),
        start=1,
    ):
        cutters.append(
            scad.make_cylinder_rsolid(
                radius=MOUNT_HOLE_RADIUS,
                height=PLATE_THICKNESS + 2.0,
                bottom_face_center=(-PLATE_THICKNESS / 2.0 - 1.0, y, BRACKET_HEIGHT * 0.62),
                axis=(1.0, 0.0, 0.0),
                tag_prefix=f"bracket.mount_hole_{index}",
            )
        )
    cutters.append(
        scad.make_cylinder_rsolid(
            radius=LOAD_HOLE_RADIUS,
            height=PLATE_THICKNESS + 2.0,
            bottom_face_center=(LOAD_HOLE_X, 0.0, -1.0),
            axis=(0.0, 0.0, 1.0),
            tag_prefix="bracket.load_hole",
        )
    )
    body = scad.cut_rsolid(body, cutters, skip_non_intersecting=False)
    body = scad.apply_tag(body, "role.structural_l_bracket")

    body = _tag_closest_face(
        body,
        center=(0.0, 0.0, BRACKET_HEIGHT / 2.0),
        normal=(-1.0, 0.0, 0.0),
        tag="interface.fixed_support",
    )
    body = _tag_closest_face(
        body,
        center=((BRACKET_DEPTH + RIB_DEPTH - PLATE_THICKNESS) / 2.0, 0.0, PLATE_THICKNESS),
        normal=(0.0, 0.0, 1.0),
        tag="interface.load_surface",
    )
    for index, y in enumerate((-MOUNT_HOLE_SPACING / 2.0, MOUNT_HOLE_SPACING / 2.0), start=1):
        body = _tag_closest_face(
            body,
            center=(PLATE_THICKNESS / 2.0, y, BRACKET_HEIGHT * 0.62),
            normal=None,
            tag=f"interface.mount_hole_{index}",
        )
    body = _tag_closest_face(
        body,
        center=(LOAD_HOLE_X, 0.0, PLATE_THICKNESS / 2.0),
        normal=None,
        tag="interface.load_hole",
    )

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
    print("faces", len(result.part.body.get_faces()))
    print("volume", f"{result.part.body.get_volume():.3f}")


if __name__ == "__main__":
    main()
