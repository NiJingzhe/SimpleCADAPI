"""Reducer housing sleeve and fixed-axis connector datums."""

from __future__ import annotations

import simplecadapi as scad

from common import (
    _apply_tags,
    add_placement_axis_connector_rpart,
    make_annular_cylinder_rsolid,
    make_axis_part_rpart,
)
from dimensions import (
    HOUSING_DATUM_INNER_RADIUS,
    HOUSING_DATUM_OUTER_RADIUS,
    HOUSING_HEIGHT,
    HOUSING_INNER_RADIUS,
    HOUSING_OUTER_RADIUS,
    HOUSING_BOTTOM_Z,
    INPUT_BEARING_Z,
    INPUT_FLANGE_TOP_Z,
    INTERMEDIATE_BEARING_Z,
    OUTPUT_BEARING_Z,
    OUTPUT_FLANGE_TOP_Z,
    STAGE_1,
    STAGE_2,
)


def make_reducer_housing_rpart(*, material: scad.Material) -> scad.Part:
    """Create the 50 mm OD housing sleeve with internal datum collars."""

    sleeve = make_annular_cylinder_rsolid(
        outer_radius=HOUSING_OUTER_RADIUS,
        inner_radius=HOUSING_INNER_RADIUS,
        height=HOUSING_HEIGHT,
        bottom_z=HOUSING_BOTTOM_Z,
        tag="role.housing_sleeve",
    )
    collars = []
    datum_zs = (
        INPUT_FLANGE_TOP_Z,
        STAGE_1.top_z,
        STAGE_2.top_z,
        OUTPUT_FLANGE_TOP_Z,
    )
    for index, target_z in enumerate(datum_zs):
        collar = make_annular_cylinder_rsolid(
            outer_radius=HOUSING_DATUM_OUTER_RADIUS,
            inner_radius=HOUSING_DATUM_INNER_RADIUS,
            height=0.36,
            bottom_z=target_z - 0.36,
            tag=f"role.housing_axis_datum_{index + 1}",
        )
        collars.append(collar)

    housing = scad.union_rsolid([sleeve, collars], glue=False)
    housing = _apply_tags(
        housing,
        tags=("role.fixed_housing", "group.two_stage_reducer"),
    )
    print(
        f"housing_envelope: diameter={HOUSING_OUTER_RADIUS * 2.0:.1f} "
        f"height={HOUSING_HEIGHT:.1f} datum_count={len(datum_zs)} faces={len(housing.get_faces())}"
    )
    part = make_axis_part_rpart(
        part_id="reducer_housing",
        solid=housing,
        name="Compact fixed reducer housing sleeve",
        material=material,
        connector_specs=(
            {
                "connector_id": "input_axis",
                "center_xy": (0.0, 0.0),
                "target_z": STAGE_1.top_z,
                "normal_z": 1.0,
            },
            {
                "connector_id": "stage1_axis",
                "center_xy": (0.0, 0.0),
                "target_z": STAGE_1.top_z,
                "normal_z": 1.0,
            },
            {
                "connector_id": "stage2_axis",
                "center_xy": (0.0, 0.0),
                "target_z": STAGE_2.top_z,
                "normal_z": 1.0,
            },
            {
                "connector_id": "output_axis",
                "center_xy": (0.0, 0.0),
                "target_z": OUTPUT_FLANGE_TOP_Z,
                "normal_z": 1.0,
            },
        ),
    )
    for connector_id, z in (
        ("input_bearing_axis", INPUT_BEARING_Z),
        ("intermediate_bearing_axis", INTERMEDIATE_BEARING_Z),
        ("output_bearing_axis", OUTPUT_BEARING_Z),
    ):
        part = add_placement_axis_connector_rpart(
            part=part,
            connector_id=connector_id,
            origin=(0.0, 0.0, z),
            name=connector_id.replace("_", " "),
        )
    return part
