"""Example 12: herringbone planetary gearset using std.gear.

This example rebuilds the planetary inspection case with the current internal
ring gear profile and nonzero ring backlash.  It exports a static gearset with:

- one herringbone sun gear
- three herringbone planet gears
- one herringbone internal ring gear

The model is intentionally exported as separate solids, not a boolean union, so
the tooth meshes remain inspectable in STEP and FCStd.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import simplecadapi as scad
from simplecadapi import ql


# Gear sketches contain many profile entities and produce deep graphs.
sys.setrecursionlimit(20000)


MODULE = 1.5
SUN_TEETH = 18
PLANET_TEETH = 24
RING_TEETH = SUN_TEETH + 2 * PLANET_TEETH
PLANET_COUNT = 3
GEAR_HEIGHT = 8.0
HELIX_ANGLE = 25.0
RIM_THICKNESS = 4.0
RING_BACKLASH = 0.08 * MODULE
OUTPUT_DIR = Path("examples/out/herringbone_planetary_gears")


def _planet_spin_angle(carrier_angle_deg: float) -> float:
    """Phase each planet so its gaps face the sun and ring contact lines."""
    planet_half_pitch_deg = 180.0 / PLANET_TEETH
    return carrier_angle_deg + 180.0 - planet_half_pitch_deg


def build_herringbone_planetary_gearset():
    """Build placed planetary gearset solids and return them with model JSON."""
    planet_center_radius = MODULE * (SUN_TEETH + PLANET_TEETH) / 2.0

    with scad.GraphSession() as session:
        ring = scad.std_gear.make_herringbone_ring_gear_rsolid(
            n_teeth=RING_TEETH,
            module=MODULE,
            helix_angle=HELIX_ANGLE,
            gear_height=GEAR_HEIGHT,
            rim_thickness=RIM_THICKNESS,
            backlash=RING_BACKLASH,
        )
        sun = scad.std_gear.make_herringbone_gear_rsolid(
            n_teeth=SUN_TEETH,
            module=MODULE,
            helix_angle=HELIX_ANGLE,
            gear_height=GEAR_HEIGHT,
        )
        planet_base = scad.std_gear.make_herringbone_gear_rsolid(
            n_teeth=PLANET_TEETH,
            module=MODULE,
            helix_angle=HELIX_ANGLE,
            gear_height=GEAR_HEIGHT,
        )

        planets = []
        for index in range(PLANET_COUNT):
            carrier_angle_deg = 360.0 * index / PLANET_COUNT
            carrier_angle_rad = math.radians(carrier_angle_deg)
            center = (
                planet_center_radius * math.cos(carrier_angle_rad),
                planet_center_radius * math.sin(carrier_angle_rad),
                0.0,
            )
            planet = scad.rotate_shape(
                planet_base,
                _planet_spin_angle(carrier_angle_deg),
                axis=(0.0, 0.0, 1.0),
                origin=(0.0, 0.0, 0.0),
            )
            planets.append(scad.translate_shape(planet, center))

        shapes = [ring, sun, *planets]
        model_json = scad.export_model_json(session)

    return shapes, model_json


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    model_path = OUTPUT_DIR / "herringbone_planetary_gearset.model.json"
    step_path = OUTPUT_DIR / "herringbone_planetary_gearset.step"
    fcstd_path = OUTPUT_DIR / "herringbone_planetary_gearset.FCStd"

    shapes, model_json = build_herringbone_planetary_gearset()
    model_path.write_text(model_json, encoding="utf-8")
    scad.export_step(shapes, str(step_path))

    fcstd_status = str(fcstd_path)
    try:
        scad.translate_model_json_to_fcstd(model_json, str(fcstd_path.resolve()))
    except Exception as exc:  # pragma: no cover - depends on local FreeCAD install
        fcstd_status = f"skipped ({exc.__class__.__name__})"

    payload = json.loads(model_json)
    face_counts = [len(ql.faces().resolve(shape)) for shape in shapes]
    volumes = [shape.get_volume() for shape in shapes]

    print(
        "sun_z={sun}  planet_z={planet}  ring_z={ring}  planets={count}  "
        "module={module}  height={height}  helix={helix}  ring_backlash={backlash}".format(
            sun=SUN_TEETH,
            planet=PLANET_TEETH,
            ring=RING_TEETH,
            count=PLANET_COUNT,
            module=MODULE,
            height=GEAR_HEIGHT,
            helix=HELIX_ANGLE,
            backlash=RING_BACKLASH,
        )
    )
    print(f"planet_center_radius={MODULE * (SUN_TEETH + PLANET_TEETH) / 2.0:.3f}")
    print(f"shape_count={len(shapes)}")
    print("face_counts=" + ",".join(str(count) for count in face_counts))
    print("volumes=" + ",".join(f"{volume:.1f}" for volume in volumes))
    print(f"graph_nodes={len(payload['graph']['nodes'])}")
    print(f"model={model_path}")
    print(f"step={step_path}")
    print(f"fcstd={fcstd_status}")


if __name__ == "__main__":
    main()
