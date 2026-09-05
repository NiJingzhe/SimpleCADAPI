"""Render the BLDC actuator showcase images from the captured package.

Outputs (examples/out/integrated_bldc_joint_actuator/):
  bldc_assembly.png    assembled actuator, isometric hero view
  bldc_front.png       assembled, front view
  bldc_exploded.png    exploded view (each leaf part offset away from centroid)

The script re-opens the captured .scadpkg in this fresh process (which also
serves as the package reopen gate), materializes the definition DAG, and
applies each component's composed placement to its part body before render.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import simplecadapi as scad
from simplecadapi.kernel.ocp_properties import center_of_mass

OUT_DIR = Path(__file__).resolve().parents[1] / "out" / "integrated_bldc_joint_actuator"
PACKAGE = OUT_DIR / "integrated_bldc_joint_actuator.scadpkg"

EXPLODE_AXIAL = 3.0     # stretch the coaxial stack along z
EXPLODE_RADIAL = 2.6    # off-axis parts (planets, balls) fly outward by r * this
EXPLODE_SPREAD = 10.0    # extra radial spread for off-axis parts, mm
LEVEL_PITCH = 7.0       # vertical pitch separating concentric same-z rings, mm
Z_BAND = 2.0            # z-band width that groups "same height" parts, mm


def _center(solid: scad.Solid):
    return center_of_mass(solid.wrapped)


def _axis_radius(solid: scad.Solid) -> float:
    """Max radial extent of the solid from the z axis (bbox x/y extremes)."""
    from simplecadapi.kernel.ocp_properties import bounding_box

    bb = bounding_box(solid.wrapped)
    return max(abs(bb.xmin), abs(bb.xmax), abs(bb.ymin), abs(bb.ymax))


def _z_rotation(placement: scad.Placement) -> tuple[float, tuple[float, float, float]]:
    """Placement -> (z-rotation degrees, translation). Asserts the frame is a
    pure z-rotation (true for every placement in this coaxial actuator)."""
    x, y, z = placement.x_axis, placement.y_axis, placement.z_axis
    if abs(z[2] - 1.0) > 1e-9 or abs(x[2]) > 1e-9 or abs(y[2]) > 1e-9:
        raise ValueError(f"non-z-rotation placement frame: x={x} y={y} z={z}")
    if (x[0] * y[1] - x[1] * y[0]) < 0:
        raise ValueError(f"left-handed frame: x={x} y={y}")
    angle = math.degrees(math.atan2(x[1], x[0]))
    return angle, placement.origin


def _compose(
    parent: tuple[float, tuple[float, float, float]],
    child: tuple[float, tuple[float, float, float]],
) -> tuple[float, tuple[float, float, float]]:
    p_angle, p_t = parent
    c_angle, c_t = child
    rad = math.radians(p_angle)
    cos, sin = math.cos(rad), math.sin(rad)
    t = (
        cos * c_t[0] - sin * c_t[1] + p_t[0],
        sin * c_t[0] + cos * c_t[1] + p_t[1],
        c_t[2] + p_t[2],
    )
    return p_angle + c_angle, t


def _flatten(
    item, transform: tuple[float, tuple[float, float, float]], out: list, path: str = ""
):
    if isinstance(item, scad.Part):
        out.append((path or item.part_id, item, transform))
        return
    for cid in item.component_ids():
        component = item.get_component(cid)
        child = _z_rotation(component.placement)
        _flatten(component.item, _compose(transform, child), out, f"{path}/{cid}")


def _place(body: scad.Solid, transform: tuple[float, tuple[float, float, float]]) -> scad.Solid:
    angle, t = transform
    shape = body
    if abs(angle) > 1e-9:
        shape = scad.rotate_shape(shape, angle, axis=(0.0, 0.0, 1.0))
    if any(abs(v) > 1e-12 for v in t):
        shape = scad.translate_shape(shape, t)
    return shape


def main() -> None:
    definition = scad.load_product_package(PACKAGE)
    root = scad.materialize_definition(definition)
    print(f"materialized: {type(root).__name__}")

    leaves: list[tuple[str, scad.Part, tuple]] = []
    _flatten(root, (0.0, (0.0, 0.0, 0.0)), leaves)
    print(f"leaf parts: {len(leaves)}")

    placed = [(name, _place(part.body, tf)) for name, part, tf in leaves]
    centers = [_center(body) for _, body in placed]
    centroid = (
        sum(c.x for c in centers) / len(centers),
        sum(c.y for c in centers) / len(centers),
        sum(c.z for c in centers) / len(centers),
    )
    total_volume = sum(body.get_volume() for _, body in placed)
    print(f"volume={total_volume:.1f} mm^3 centroid={tuple(round(v, 1) for v in centroid)}")

    solids = [body for _, body in placed]
    scad.render_screenshot_rpath(
        shapes=solids, output_path=str(OUT_DIR / "bldc_assembly.png"),
        view=(30.0, 35.0), show_axes=False, show_callouts=False, show_legend=False)
    scad.render_screenshot_rpath(
        shapes=solids, output_path=str(OUT_DIR / "bldc_front.png"),
        view=(0.0, 0.0), show_axes=False, show_callouts=False, show_legend=False)

    # Cylindrical staged explode: concentric same-height rings (bearing races,
    # ring gears) would move as one clump under a plain centroid offset, so
    # parts are banded by height and stacked vertically by radius rank, while
    # off-axis parts (planets, bearing balls) fan out along their own azimuth.
    bands: dict[int, list[int]] = {}
    for i, (name, body) in enumerate(placed):
        bands.setdefault(int(round(_center(body).z / Z_BAND)), []).append(i)

    exploded = []
    for band, indices in bands.items():
        ranked = sorted(indices, key=lambda i: _axis_radius(placed[i][1]), reverse=True)
        for level, i in enumerate(ranked):
            name, body = placed[i]
            c = _center(body)
            radial_c = math.hypot(c.x, c.y)
            if radial_c > 1.0:
                push = radial_c * EXPLODE_RADIAL + EXPLODE_SPREAD
                dx = c.x / radial_c * push
                dy = c.y / radial_c * push
            else:
                dx = dy = 0.0
            dz = (c.z - centroid[2]) * EXPLODE_AXIAL + level * LEVEL_PITCH
            exploded.append(scad.translate_shape(body, (dx, dy, dz)))
    scad.render_screenshot_rpath(
        shapes=exploded, output_path=str(OUT_DIR / "bldc_exploded.png"),
        view=(25.0, 45.0), show_axes=False, show_callouts=False, show_legend=False)

    for name in ("bldc_assembly.png", "bldc_front.png", "bldc_exploded.png"):
        path = OUT_DIR / name
        print(f"render {path} ({path.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
