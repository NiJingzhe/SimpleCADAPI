"""A40/A41 fixed guide frames with real D0 guide cartridges and handed ends."""

from __future__ import annotations

import simplecadapi as scad

from .common import apply_tags, make_part
from .parameters import MachineParameters
from .representative_parts import (
    ComponentSpec,
    make_box_part,
    make_cylinder_part,
    make_static_assembly,
    make_u_part,
)


def _make_frame_plate(
    *,
    upper: bool,
    materials: dict[str, scad.Material],
) -> scad.Part:
    suffix = "upper" if upper else "lower"
    plate = scad.make_box_rsolid(
        width=12.0,
        height=430.0,
        depth=116.0,
        bottom_face_center=(0.0, 0.0, 0.0),
    )
    window = scad.make_box_rsolid(
        width=16.0,
        height=330.0,
        depth=76.0,
        bottom_face_center=(0.0, 0.0, 20.0),
    )
    plate = scad.cut_rsolid(plate, window, skip_non_intersecting=False)
    plate = apply_tags(
        shape=plate,
        tags=("role.guide_frame", "role.transfer_window", "role.fixed_frame"),
    )
    return make_part(
        part_id=f"g_01_{suffix}_frame_plate",
        name=f"G-01/G-02 {suffix} machined guide-frame plate",
        body=plate,
        material=materials["machined_aluminum"],
        connectors=(),
    )


def make_guide_frame(
    *,
    upper: bool,
    parameters: MachineParameters,
    materials: dict[str, scad.Material],
    guide_cartridge: scad.Assembly,
) -> scad.Assembly:
    suffix = "upper" if upper else "lower"
    level = 1.0 if upper else -1.0
    frame_bottom = level * parameters.guide_frame_half_height.value - (
        52.0 if upper else 52.0
    )
    plate = _make_frame_plate(upper=upper, materials=materials)
    rail = make_box_part(
        part_id=f"g_03_{suffix}_long_wear_rail",
        name=f"G-03/G-04 {suffix} replaceable long wear rail",
        size=(30.0, 330.0, 3.0),
        material=materials["wear_rail"],
        tags=("role.replaceable_wear_rail", "role.guide_row_support"),
    )
    pusher = make_cylinder_part(
        part_id=f"g_07_{suffix}_pusher",
        name=f"G-07/G-10 {suffix} row pusher and follower",
        radius=8.0,
        length=80.0,
        axis=(0.0, 1.0, 0.0),
        material=materials["stainless"],
        tags=("role.guide_row_pusher", "role.sliding_member"),
    )
    shuttle = make_u_part(
        part_id=f"g_05_{suffix}_transfer_shuttle",
        name=f"G-05/G-06 handed {suffix} transfer shuttle",
        outer_width=34.0,
        height=44.0,
        depth=18.0,
        wall=7.0,
        material=materials["guide_polymer"],
        tags=("role.guide_transfer_shuttle", "role.handed_part"),
    )
    frame_spacer = make_cylinder_part(
        part_id=f"g_01_{suffix}_frame_spacer",
        name=f"G-01/G-02 {suffix} precision frame spacer",
        radius=6.0,
        length=40.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["stainless"],
        tags=("role.guide_frame", "role.frame_spacer"),
    )
    center_guide = make_box_part(
        part_id=f"g_11_{suffix}_central_guide_plate",
        name=f"G-11 {suffix} central fixed warp-guide plate",
        size=(8.0, 330.0, 10.0),
        material=materials["machined_aluminum"],
        tags=("role.guide_frame", "role.fixed_warp_guide"),
    )
    lock_bar = make_box_part(
        part_id=f"g_12_{suffix}_pitch_lock_bar",
        name=f"G-12 {suffix} pitch-position locking bar",
        size=(16.0, 330.0, 8.0),
        material=materials["stainless"],
        tags=("role.guide_frame", "role.pitch_lock"),
    )
    x_value = parameters.x_guide.value
    components: list[ComponentSpec] = [
        ComponentSpec(
            "front_plate", plate, (x_value - 20.0, 0.0, frame_bottom), plate.name
        ),
        ComponentSpec(
            "rear_plate", plate, (x_value + 20.0, 0.0, frame_bottom), plate.name
        ),
    ]
    row_z = (
        level * parameters.guide_frame_half_height.value - 20.0,
        level * parameters.guide_frame_half_height.value + 20.0,
    )
    for row, z_value in enumerate(row_z):
        for face, rail_z in (("lower", z_value - 15.0), ("upper", z_value + 12.0)):
            components.append(
                ComponentSpec(
                    f"wear_rail_{row}_{face}",
                    rail,
                    (x_value, 0.0, rail_z),
                    f"{suffix.title()} row {row + 1} {face} wear rail",
                )
            )
        for column, y_value in enumerate((-132.0, -66.0, 0.0, 66.0, 132.0)):
            components.append(
                ComponentSpec(
                    f"guide_sample_{row}_{column}",
                    guide_cartridge,
                    (x_value, y_value, z_value - 12.0),
                    f"Representative {suffix} guide block row {row + 1}, sample {column + 1}",
                )
            )
        components.extend(
            (
                ComponentSpec(
                    f"left_pusher_{row}",
                    pusher,
                    (x_value, -245.0, z_value),
                    f"{suffix.title()} row left pusher",
                ),
                ComponentSpec(
                    f"right_pusher_{row}",
                    pusher,
                    (x_value, 165.0, z_value),
                    f"{suffix.title()} row right follower",
                ),
            )
        )
    components.extend(
        (
            ComponentSpec(
                "central_fixed_guide",
                center_guide,
                (x_value, 0.0, level * parameters.guide_frame_half_height.value - 5.0),
                center_guide.name,
            ),
            ComponentSpec(
                "pitch_lock_bar",
                lock_bar,
                (
                    x_value - 30.0,
                    0.0,
                    level * parameters.guide_frame_half_height.value - 4.0,
                ),
                lock_bar.name,
            ),
        )
    )
    for side, y_value in (("left", -195.0), ("right", 195.0)):
        for level_id, z_offset in (("lower", 10.0), ("upper", 98.0)):
            components.append(
                ComponentSpec(
                    f"{side}_{level_id}_frame_spacer",
                    frame_spacer,
                    (x_value - 20.0, y_value, frame_bottom + z_offset),
                    frame_spacer.name,
                )
            )
    for side, y_value in (("left", -205.0), ("right", 205.0)):
        components.append(
            ComponentSpec(
                f"{side}_handed_shuttle",
                shuttle,
                (
                    x_value,
                    y_value,
                    level * parameters.guide_frame_half_height.value - 22.0,
                ),
                f"{suffix.title()} {side} handed transfer shuttle",
            )
        )
    assembly = make_static_assembly(
        assembly_id=f"a{'40' if upper else '41'}_{suffix}_guide_frame",
        name=f"A{'40' if upper else '41'} fixed {suffix} two-row bias guide frame",
        components=components,
    )
    print(
        f"a{'40' if upper else '41'}_guide_frame: displayed_blocks=10 "
        "authoritative_count=unresolved topology=assumption_only"
    )
    return assembly
