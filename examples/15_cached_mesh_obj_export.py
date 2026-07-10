"""Example 15: export an internal cached mesh as OBJ.

Run from the repository root with:
    uv run python examples/15_cached_mesh_obj_export.py

This is a developer-facing example for the mesh-cache groundwork. It
intentionally does not call the public STL exporter. Instead it builds a normal
SimpleCAD solid, reads the framework's internal cached mesh, and writes a common
Wavefront OBJ mesh file from that pure triangle data.

Application code should not depend on ``simplecadapi._mesh``. Future structural
checking APIs will consume the same internal mesh cache without exposing mesh
extraction to framework users.
"""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad
import simplecadapi._mesh as internal_mesh


OUT_DIR = Path("examples/out/cached_mesh_obj_export")


def build_demo_solid() -> scad.Solid:
    """Build a small bracket-like solid using only normal modeling APIs."""

    base = scad.make_box_rsolid(
        width=34.0,
        height=20.0,
        depth=6.0,
        bottom_face_center=(0.0, 0.0, 0.0),
    )
    through_hole = scad.make_cylinder_rsolid(
        radius=4.0,
        height=12.0,
        bottom_face_center=(0.0, 0.0, -3.0),
        axis=(0.0, 0.0, 1.0),
    )
    mount_slot = scad.make_box_rsolid(
        width=8.0,
        height=24.0,
        depth=10.0,
        bottom_face_center=(10.0, 0.0, -2.0),
    )
    boss = scad.make_cylinder_rsolid(
        radius=7.0,
        height=5.0,
        bottom_face_center=(-10.0, 0.0, 6.0),
        axis=(0.0, 0.0, 1.0),
    )

    bracket = scad.cut_rsolid(
        base,
        through_hole,
        mount_slot,
        skip_non_intersecting=False,
    )
    bracket = scad.union_rsolid([bracket, boss])
    return scad.apply_tag(shape=bracket, tag="role.cached_mesh_obj_demo")


def write_cached_mesh_obj(solid: scad.Solid, path: Path) -> internal_mesh.TriMesh:
    """Write a Solid's internal cached mesh to Wavefront OBJ."""

    mesh = internal_mesh.cached_mesh(solid)
    if mesh is None:
        detail = internal_mesh.mesh_error(solid) or "no internal mesh cache"
        raise RuntimeError(f"Solid has no cached mesh: {detail}")

    lines = [
        "# OBJ written from SimpleCAD internal cached mesh",
        "# This example intentionally bypasses scad.export_stl(...).",
    ]
    for x, y, z in mesh.vertices:
        lines.append(f"v {x:.9g} {y:.9g} {z:.9g}")
    for a, b, c in mesh.triangles:
        lines.append(f"f {int(a) + 1} {int(b) + 1} {int(c) + 1}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return mesh


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    solid = build_demo_solid()
    obj_path = OUT_DIR / "cached_mesh_bracket.obj"
    mesh = write_cached_mesh_obj(solid=solid, path=obj_path)
    lower, upper = mesh.bounds

    print("volume", round(solid.get_volume(), 3))
    print("faces", len(solid.get_faces()))
    print("mesh", f"vertices={mesh.vertex_count}", f"triangles={mesh.triangle_count}")
    print("bounds", f"min={tuple(round(v, 3) for v in lower)}", f"max={tuple(round(v, 3) for v in upper)}")
    print("wrote_obj", obj_path)


if __name__ == "__main__":
    main()
