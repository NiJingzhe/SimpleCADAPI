"""Input shaft for the first planetary sun."""

from __future__ import annotations

import simplecadapi as scad

from common import _apply_tags, add_placement_axis_connector_rpart, make_axis_part_rpart
from dimensions import INPUT_BEARING_Z, INPUT_FLANGE_TOP_Z, INPUT_SHAFT_RADIUS, STAGE_1


def make_input_shaft_rpart(*, material: scad.Material) -> scad.Part:
    """Create the input shaft linking the input flange and stage 1 sun."""

    height = STAGE_1.top_z - INPUT_FLANGE_TOP_Z
    shaft = scad.make_cylinder_rsolid(
        radius=INPUT_SHAFT_RADIUS,
        height=height,
        bottom_face_center=(0.0, 0.0, INPUT_FLANGE_TOP_Z),
        axis=(0.0, 0.0, 1.0),
    )
    shaft = _apply_tags(
        shaft,
        tags=("role.input_shaft", "group.two_stage_reducer"),
    )
    print(
        f"input_shaft: radius={INPUT_SHAFT_RADIUS:.3f} bottom_z={INPUT_FLANGE_TOP_Z:.3f} "
        f"top_z={STAGE_1.top_z:.3f} volume={shaft.get_volume():.3f}"
    )
    part = make_axis_part_rpart(
        part_id="input_shaft",
        solid=shaft,
        name="Input shaft to first-stage sun",
        material=material,
        connector_specs=(
            {
                "connector_id": "flange_axis",
                "center_xy": (0.0, 0.0),
                "target_z": INPUT_FLANGE_TOP_Z,
                "normal_z": -1.0,
                "flip": True,
            },
            {
                "connector_id": "sun_axis",
                "center_xy": (0.0, 0.0),
                "target_z": STAGE_1.top_z,
                "normal_z": 1.0,
            },
        ),
    )
    return add_placement_axis_connector_rpart(
        part=part,
        connector_id="input_bearing_axis",
        origin=(0.0, 0.0, INPUT_BEARING_Z),
        name="Input bearing shaft seat axis",
    )
