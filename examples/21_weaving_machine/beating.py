"""A70 open-reed cassette and serial Z/X beat-up stages."""

from __future__ import annotations

import simplecadapi as scad

from .parameters import MachineParameters
from .representative_parts import (
    ComponentSpec,
    make_box_part,
    make_cylinder_part,
    make_static_assembly,
)


def make_open_reed(
    *,
    parameters: MachineParameters,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    reed_beam = make_box_part(
        part_id="d_01_reed_beam",
        name="D-01 high-inertia open-reed beam",
        size=(48.0, 410.0, 42.0),
        material=materials["structural_steel"],
        tags=("role.open_reed", "role.beatup_reaction_path"),
    )
    cassette = make_box_part(
        part_id="d_04_reed_cassette",
        name="D-04 removable reed cassette clamp",
        size=(28.0, 370.0, 28.0),
        material=materials["machined_aluminum"],
        tags=("role.open_reed", "role.replaceable_cassette"),
    )
    blade = make_box_part(
        part_id="d_02_open_reed_blade",
        name="D-02 single-ended polished open-reed blade",
        size=(92.0, 2.0, 16.0),
        material=materials["stainless"],
        tags=(
            "role.open_reed_blade",
            "role.yarn_contact",
            "role.representative_instance",
        ),
    )
    x_rail = make_box_part(
        part_id="d_05_beatup_x_rail",
        name="D-05 wide-spaced beat-up X rail",
        size=(360.0, 34.0, 28.0),
        material=materials["structural_steel"],
        tags=("role.open_reed", "role.x_slide", "role.beatup_reaction_path"),
    )
    z_rail = make_box_part(
        part_id="d_06_reed_z_rail",
        name="D-06 reed entry/exit Z rail",
        size=(34.0, 34.0, 280.0),
        material=materials["structural_steel"],
        tags=("role.open_reed", "role.z_slide"),
    )
    motor = make_cylinder_part(
        part_id="m7_m8_reed_drive",
        name="M7/M8 reed servo and screw envelope",
        radius=45.0,
        length=105.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["drive"],
        tags=("role.open_reed", "role.motor_envelope"),
    )
    crosshead = make_box_part(
        part_id="d_04_reed_crosshead",
        name="D-04 reed crosshead spanning both Z slides",
        size=(60.0, 500.0, 30.0),
        material=materials["machined_aluminum"],
        tags=("role.open_reed", "role.rail_carriage"),
    )
    support_post = make_box_part(
        part_id="d_05_beatup_rail_support",
        name="D-05 beat-up rail support post",
        size=(60.0, 60.0, 400.0),
        material=materials["structural_steel"],
        tags=("role.open_reed", "role.structural_support"),
    )
    motor_shelf = make_box_part(
        part_id="d_07_reed_motor_shelf",
        name="D-07 reed-drive mounting shelf",
        size=(140.0, 120.0, 20.0),
        material=materials["structural_steel"],
        tags=("role.open_reed", "role.motor_mount"),
    )
    home_x = -300.0
    components: list[ComponentSpec] = [
        ComponentSpec("reed_beam", reed_beam, (home_x, 0.0, -21.0), reed_beam.name),
        ComponentSpec(
            "reed_cassette", cassette, (home_x + 32.0, 0.0, 21.0), cassette.name
        ),
        ComponentSpec(
            "reed_crosshead", crosshead, (home_x - 20.0, 0.0, -30.0), crosshead.name
        ),
        ComponentSpec("left_x_rail", x_rail, (-180.0, -245.0, -130.0), x_rail.name),
        ComponentSpec("right_x_rail", x_rail, (-180.0, 245.0, -130.0), x_rail.name),
        ComponentSpec(
            "left_z_rail", z_rail, (home_x - 20.0, -245.0, -140.0), z_rail.name
        ),
        ComponentSpec(
            "right_z_rail", z_rail, (home_x - 20.0, 245.0, -140.0), z_rail.name
        ),
        ComponentSpec(
            "m7_z_drive", motor, (home_x - 100.0, -285.0, 180.0), "M7 reed Z drive"
        ),
        ComponentSpec(
            "m8_x_drive",
            motor,
            (-390.0, 285.0, -130.0),
            "M8 beat-up X drive with force interface",
        ),
        ComponentSpec(
            "m7_motor_shelf",
            motor_shelf,
            (home_x - 45.0, -285.0, 115.0),
            motor_shelf.name,
        ),
        ComponentSpec(
            "m8_motor_shelf", motor_shelf, (-335.0, 285.0, -205.0), motor_shelf.name
        ),
    ]
    for x_label, support_x in (("rear", -330.0), ("front", -30.0)):
        for y_label, support_y in (("left", -245.0), ("right", 245.0)):
            components.append(
                ComponentSpec(
                    f"{x_label}_{y_label}_rail_support",
                    support_post,
                    (
                        support_x,
                        support_y,
                        parameters.base_datum_z.value + 40.0,
                    ),
                    support_post.name,
                )
            )
    for index, y_value in enumerate(range(-174, 175, 12)):
        components.append(
            ComponentSpec(
                f"blade_sample_{index:02d}",
                blade,
                (home_x + 92.0, float(y_value), 25.0),
                f"Representative open-reed blade {index + 1}",
            )
        )
    assembly = make_static_assembly(
        assembly_id="a70_open_reed",
        name="A70 removable open-reed cassette with serial Z-entry and X-beat stages",
        components=components,
    )
    print(
        "a70_open_reed: displayed_blades=30 authoritative_count=unresolved path=Z,X,-Z,-X"
    )
    return assembly
