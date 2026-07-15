"""A20 representative independent warp packages and fixed guidance."""

from __future__ import annotations

import simplecadapi as scad

from .parameters import MachineParameters
from .representative_parts import (
    ComponentSpec,
    make_box_part,
    make_cylinder_part,
    make_spool_part,
    make_static_assembly,
)


def make_warp_supply(
    *,
    parameters: MachineParameters,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    spool = make_spool_part(
        part_id="w_01_warp_package",
        name="W-01 representative independent warp package",
        material=materials["guide_polymer"],
        tags=("role.warp_supply", "role.representative_instance"),
    )
    rack_post = make_box_part(
        part_id="w_00_warp_rack_post",
        name="A20 warp creel structural post",
        size=(60.0, 60.0, 1080.0),
        material=materials["structural_steel"],
        tags=("role.warp_supply", "role.creel_frame", "role.structural_support"),
    )
    package_beam = make_box_part(
        part_id="w_00_warp_package_beam",
        name="A20 warp package spindle beam",
        size=(50.0, 720.0, 50.0),
        material=materials["structural_steel"],
        tags=("role.warp_supply", "role.spindle_support"),
    )
    spindle = make_cylinder_part(
        part_id="w_02_warp_package_spindle",
        name="W-02 supported warp-package spindle",
        radius=6.0,
        length=100.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["stainless"],
        tags=("role.warp_supply", "role.package_spindle"),
    )
    guide_plate = make_box_part(
        part_id="w_guide_plate",
        name="A20 fixed warp guide plate",
        size=(18.0, 360.0, 150.0),
        material=materials["machined_aluminum"],
        tags=("role.warp_supply", "role.fixed_yarn_guide"),
    )
    guide_eye = make_cylinder_part(
        part_id="w_04_tension_eye",
        name="W-04 ceramic-eye tension-arm reference",
        radius=9.0,
        length=12.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["ceramic"],
        tags=("role.warp_supply", "role.yarn_contact"),
    )
    tension_arm = make_cylinder_part(
        part_id="w_04_tension_arm",
        name="W-04 supported warp tension arm",
        radius=3.5,
        length=82.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["stainless"],
        tags=("role.warp_supply", "role.tension_arm"),
    )
    guide_post = make_box_part(
        part_id="w_03_guide_frame_post",
        name="W-03 fixed warp-guide frame post",
        size=(50.0, 50.0, 650.0),
        material=materials["structural_steel"],
        tags=("role.warp_supply", "role.guide_frame_support"),
    )
    guide_crossbeam = make_box_part(
        part_id="w_03_guide_frame_crossbeam",
        name="W-03 fixed warp-guide frame crossbeam",
        size=(50.0, 500.0, 50.0),
        material=materials["structural_steel"],
        tags=("role.warp_supply", "role.guide_frame_support"),
    )
    guide_base_sill = make_box_part(
        part_id="w_03_guide_frame_base_sill",
        name="W-03 warp-guide frame base sill",
        size=(60.0, 960.0, 40.0),
        material=materials["structural_steel"],
        tags=("role.warp_supply", "role.frame_interface"),
    )
    base_z = parameters.base_datum_z.value + 40.0
    rack_x = parameters.supply_rack_x.value - 65.0
    components = [
        ComponentSpec(
            "creel_post_left", rack_post, (rack_x, -340.0, base_z), rack_post.name
        ),
        ComponentSpec(
            "creel_post_right", rack_post, (rack_x, 340.0, base_z), rack_post.name
        ),
        ComponentSpec(
            "lower_package_beam", package_beam, (rack_x, 0.0, -215.0), package_beam.name
        ),
        ComponentSpec(
            "upper_package_beam", package_beam, (rack_x, 0.0, 145.0), package_beam.name
        ),
        ComponentSpec(
            "guide_post_left", guide_post, (-600.0, -220.0, base_z), guide_post.name
        ),
        ComponentSpec(
            "guide_post_right", guide_post, (-600.0, 220.0, base_z), guide_post.name
        ),
        ComponentSpec(
            "guide_crossbeam",
            guide_crossbeam,
            (-600.0, 0.0, -105.0),
            guide_crossbeam.name,
        ),
        ComponentSpec(
            "guide_base_sill",
            guide_base_sill,
            (-600.0, 0.0, parameters.base_datum_z.value),
            guide_base_sill.name,
        ),
        ComponentSpec(
            "fixed_guide_plate", guide_plate, (-600.0, 0.0, -75.0), guide_plate.name
        ),
    ]
    representative_y = (-270.0, -90.0, 90.0, 270.0)
    representative_z = (-190.0, 170.0)
    for row, z_value in enumerate(representative_z):
        for column, y_value in enumerate(representative_y):
            package_id = f"warp_package_{row}_{column}"
            components.extend(
                (
                    ComponentSpec(
                        package_id,
                        spool,
                        (parameters.supply_rack_x.value, y_value, z_value),
                        f"Representative warp package row {row + 1}, position {column + 1}",
                    ),
                    ComponentSpec(
                        f"spindle_{row}_{column}",
                        spindle,
                        (rack_x + 25.0, y_value, z_value),
                        "Supported warp package spindle",
                    ),
                    ComponentSpec(
                        f"tension_eye_{row}_{column}",
                        guide_eye,
                        (-690.0, y_value * 0.55, z_value * 0.35),
                        "Representative independent warp tension eye",
                    ),
                    ComponentSpec(
                        f"tension_arm_{row}_{column}",
                        tension_arm,
                        (-678.0, y_value * 0.55, z_value * 0.35),
                        "Warp tension-eye mounting arm",
                    ),
                )
            )
    assembly = make_static_assembly(
        assembly_id="a20_warp_supply",
        name="A20 representative warp packages, tension eyes, and fixed guidance",
        components=components,
    )
    print("a20_warp_supply: displayed_ends=8 authoritative_count=unresolved")
    return assembly
