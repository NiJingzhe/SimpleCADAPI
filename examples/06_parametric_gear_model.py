"""Tidy parametric gear-like model JSON example.

This example is intentionally lightweight enough for automated tests. It is not a
full involute gear generator; it demonstrates the same release-critical behavior:
expression parameters, derived numeric construction values, canonical graph
export, and exactly one explicit `leaf_ids` output.

Run from the repository root with:
    uv run python examples/06_parametric_gear_model.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import simplecadapi as scad


def _involute_spur_profile_points(
    *,
    tooth_count: int,
    module: float,
    pressure_angle_deg: float = 20.0,
    backlash: float = 0.03,
    profile_points: int = 10,
    root_arc_points: int = 4,
    tip_arc_points: int = 4,
) -> list[tuple[float, float, float]]:
    """Sample a closed 2D involute spur gear outline in the XY plane."""

    import math

    if tooth_count < 8:
        raise ValueError("tooth_count must be >= 8")
    if module <= 0:
        raise ValueError("module must be > 0")

    pressure_angle = math.radians(pressure_angle_deg)
    pitch_radius = 0.5 * module * tooth_count
    tip_radius = pitch_radius + module
    root_radius = pitch_radius - 1.25 * module
    base_radius = pitch_radius * math.cos(pressure_angle)
    if root_radius <= 0:
        raise ValueError("invalid gear dimensions: root radius <= 0")

    half_tooth_angle = (math.pi / (2.0 * tooth_count)) - (
        backlash / (2.0 * pitch_radius)
    )
    inv_pitch = math.tan(pressure_angle) - pressure_angle
    r_start = max(root_radius, base_radius)

    def flank_angle_at_radius(radius: float) -> float:
        ratio = min(1.0, max(0.0, base_radius / radius))
        phi = math.acos(ratio)
        inv_r = math.tan(phi) - phi
        return half_tooth_angle + inv_pitch - inv_r

    radii = [
        r_start + (tip_radius - r_start) * i / (profile_points - 1)
        for i in range(profile_points)
    ]

    flank_pos: list[tuple[float, float]] = []
    flank_neg: list[tuple[float, float]] = []
    for radius in radii:
        beta = flank_angle_at_radius(radius)
        x = radius * math.cos(beta)
        y = radius * math.sin(beta)
        flank_pos.append((x, y))
        flank_neg.append((x, -y))

    start_angle = math.atan2(flank_pos[0][1], flank_pos[0][0])
    tip_angle_neg = math.atan2(flank_neg[-1][1], flank_neg[-1][0])
    tip_angle_pos = math.atan2(flank_pos[-1][1], flank_pos[-1][0])

    tip_arc = [
        (
            tip_radius
            * math.cos(
                tip_angle_neg + (tip_angle_pos - tip_angle_neg) * i / tip_arc_points
            ),
            tip_radius
            * math.sin(
                tip_angle_neg + (tip_angle_pos - tip_angle_neg) * i / tip_arc_points
            ),
        )
        for i in range(1, tip_arc_points)
    ]

    tooth_local: list[tuple[float, float]] = []
    tooth_local.append((root_radius * math.cos(-start_angle), root_radius * math.sin(-start_angle)))
    tooth_local.extend(flank_neg)
    tooth_local.extend(tip_arc)
    tooth_local.extend(reversed(flank_pos))
    tooth_local.append((root_radius * math.cos(start_angle), root_radius * math.sin(start_angle)))

    def rotate_xy(point: tuple[float, float], angle: float) -> tuple[float, float]:
        c = math.cos(angle)
        s = math.sin(angle)
        return (point[0] * c - point[1] * s, point[0] * s + point[1] * c)

    tooth_pitch_angle = 2.0 * math.pi / tooth_count
    outline: list[tuple[float, float]] = []
    for k in range(tooth_count):
        center_angle = k * tooth_pitch_angle
        tooth_world = [rotate_xy(point, center_angle) for point in tooth_local]
        outline.extend(tooth_world if not outline else tooth_world[1:])

        a0 = center_angle + start_angle
        a1 = center_angle + tooth_pitch_angle - start_angle
        for i in range(1, root_arc_points):
            angle = a0 + (a1 - a0) * i / root_arc_points
            outline.append((root_radius * math.cos(angle), root_radius * math.sin(angle)))

    cleaned: list[tuple[float, float]] = []
    for point in outline:
        if not cleaned:
            cleaned.append(point)
            continue
        if math.hypot(point[0] - cleaned[-1][0], point[1] - cleaned[-1][1]) > 1e-7:
            cleaned.append(point)

    return [(x, y, 0.0) for x, y in cleaned]


def build_model(output_dir: Path) -> dict:
    """Build a small replayable involute spur gear and write model JSON.

    Args:
        output_dir: Directory that receives `parametric_gear.model.json`.

    Returns:
        The parsed exported model payload.
    """

    tooth_count_value = 14
    module_value = 1.4
    thickness = scad.var("thickness", 4.0)
    bore_radius = scad.var("bore_radius", 2.2)

    # Keep derived construction facts as numerics; this example verifies they do
    # not become top-level model variables such as `pitch_radius`.
    profile_points = _involute_spur_profile_points(
        tooth_count=tooth_count_value,
        module=module_value,
    )

    with scad.GraphSession() as session:
        profile = scad.make_polyline_rwire(profile_points, closed=True)
        gear = scad.extrude_rsolid(profile, (0.0, 0.0, 1.0), thickness)
        bore = scad.make_cylinder_rsolid(
            bore_radius,
            thickness + 2.0,
            bottom_face_center=(0.0, 0.0, -1.0),
        )
        gear = scad.cut_rsolidlist(gear, bore)
        # Keep the final output as a single explicit leaf node.
        gear = scad.translate_shape(gear, (0.0, 0.0, 0.0))

    model_json = scad.export_model_json(session)
    payload = json.loads(model_json)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "parametric_gear.model.json").write_text(model_json, encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("examples/out/parametric_gear"),
    )
    args = parser.parse_args()

    payload = build_model(args.output_dir)
    var_names = [
        node.get("name")
        for node in payload["expression_graph"]["nodes"]
        if node.get("kind") == "var"
    ]

    print("leaf_count", len(payload["leaf_ids"]))
    print("graph_nodes", len(payload["graph"]["nodes"]))
    print("vars", ",".join(str(name) for name in var_names))
    print("wrote", args.output_dir / "parametric_gear.model.json")


if __name__ == "__main__":
    main()
