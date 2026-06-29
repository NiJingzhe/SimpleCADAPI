"""Example 11: standalone std.gear internal ring gears.

This example intentionally avoids planetary assemblies.  It exports three
separate ring-gear models so the internal tooth profile can be inspected
without overlapped sun/planet gears or assembly placement noise:

- spur internal ring gear
- helical internal ring gear
- herringbone internal ring gear

Each model is exported as model JSON, STEP, and FCStd.
"""

import json
import sys
from pathlib import Path

import simplecadapi as scad


# Ring gear sketches contain many profile entities and produce deep graphs.
sys.setrecursionlimit(10000)


MODULE = 1.5
RING_TEETH = 66
GEAR_HEIGHT = 8.0
HELIX_ANGLE = 25.0
RIM_THICKNESS = 4.0
BACKLASH = 0.08 * MODULE
OUTPUT_DIR = Path("examples/out/ring_gears")


def _export_ring(name, description, build_ring):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    model_path = OUTPUT_DIR / f"{name}.model.json"
    step_path = OUTPUT_DIR / f"{name}.step"
    fcstd_path = OUTPUT_DIR / f"{name}.FCStd"

    with scad.GraphSession() as session:
        ring = build_ring()
        model_json = scad.export_model_json(session)

    model_path.write_text(model_json, encoding="utf-8")
    scad.export_step(ring, str(step_path))

    fcstd_status = str(fcstd_path)
    try:
        scad.translate_model_json_to_fcstd(model_json, str(fcstd_path.resolve()))
    except Exception as exc:
        fcstd_status = f"skipped ({exc.__class__.__name__})"

    payload = json.loads(model_json)
    print(f"=== {description} ===")
    print(f"  volume: {ring.get_volume():.1f}")
    print(f"  graph nodes: {len(payload['graph']['nodes'])}")
    print(f"  model: {model_path}")
    print(f"  step:  {step_path}")
    print(f"  fcstd: {fcstd_status}")
    print()


def main():
    print(
        "ring_z={ring_z}  module={module}  height={height}  "
        "rim={rim}  helix={helix}  backlash={backlash}".format(
            ring_z=RING_TEETH,
            module=MODULE,
            height=GEAR_HEIGHT,
            rim=RIM_THICKNESS,
            helix=HELIX_ANGLE,
            backlash=BACKLASH,
        )
    )
    print(f"output_dir={OUTPUT_DIR}")
    print()

    _export_ring(
        "spur_ring_gear",
        "Spur internal ring gear",
        lambda: scad.std_gear.make_spur_ring_gear_rsolid(
            n_teeth=RING_TEETH,
            module=MODULE,
            gear_height=GEAR_HEIGHT,
            rim_thickness=RIM_THICKNESS,
            backlash=BACKLASH,
        ),
    )

    _export_ring(
        "helical_ring_gear",
        "Helical internal ring gear",
        lambda: scad.std_gear.make_helical_ring_gear_rsolid(
            n_teeth=RING_TEETH,
            module=MODULE,
            helix_angle=HELIX_ANGLE,
            gear_height=GEAR_HEIGHT,
            rim_thickness=RIM_THICKNESS,
            backlash=BACKLASH,
        ),
    )

    _export_ring(
        "herringbone_ring_gear",
        "Herringbone internal ring gear",
        lambda: scad.std_gear.make_herringbone_ring_gear_rsolid(
            n_teeth=RING_TEETH,
            module=MODULE,
            helix_angle=HELIX_ANGLE,
            gear_height=GEAR_HEIGHT,
            rim_thickness=RIM_THICKNESS,
            backlash=BACKLASH,
        ),
    )


if __name__ == "__main__":
    main()
