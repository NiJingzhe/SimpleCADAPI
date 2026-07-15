"""A30/A31 representative moving bias-package chains."""

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


def make_bias_supply(
    *,
    upper: bool,
    parameters: MachineParameters,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    level = 1.0 if upper else -1.0
    suffix = "upper" if upper else "lower"
    center_z = level * 330.0
    spool = make_spool_part(
        part_id=f"b_04_{suffix}_bias_package",
        name=f"B-04 representative {suffix} moving bias package",
        material=materials["guide_polymer"],
        tags=("role.bias_supply", "role.representative_instance"),
        length=58.0,
        core_radius=18.0,
        flange_radius=27.0,
    )
    chain_run = make_box_part(
        part_id=f"b_01_{suffix}_chain_run",
        name=f"B-01 {suffix} precision-chain envelope",
        size=(420.0, 16.0, 14.0),
        material=materials["belt"],
        tags=("role.bias_supply", "role.indexed_chain"),
    )
    carrier = make_box_part(
        part_id=f"b_04_{suffix}_carrier_plate",
        name=f"B-04 {suffix} bridge carrier plate",
        size=(54.0, 112.0, 8.0),
        material=materials["machined_aluminum"],
        tags=("role.bias_supply", "role.package_carrier"),
    )
    sprocket = make_cylinder_part(
        part_id=f"b_02_{suffix}_sprocket",
        name=f"B-02/B-03 {suffix} chain sprocket envelope",
        radius=65.0,
        length=18.0,
        axis=(0.0, 1.0, 0.0),
        material=materials["drive"],
        tags=("role.bias_supply", "role.positive_index_input"),
    )
    bed = make_box_part(
        part_id=f"b_00_{suffix}_chain_bed",
        name=f"B-00 {suffix} bias-chain support bed",
        size=(520.0, 180.0, 30.0),
        material=materials["structural_steel"],
        tags=("role.bias_supply", "role.chain_support"),
    )
    post_height = center_z - parameters.base_datum_z.value - 95.0
    support_post = make_box_part(
        part_id=f"b_00_{suffix}_chain_post",
        name=f"B-00 {suffix} bias-chain support post",
        size=(50.0, 50.0, post_height),
        material=materials["structural_steel"],
        tags=("role.bias_supply", "role.structural_support"),
    )
    foundation_stringer = make_box_part(
        part_id=f"b_00_{suffix}_foundation_stringer",
        name=f"B-00 {suffix} bias-chain foundation stringer",
        size=(470.0, 50.0, 40.0),
        material=materials["structural_steel"],
        tags=("role.bias_supply", "role.frame_interface"),
    )
    spindle = make_cylinder_part(
        part_id=f"b_05_{suffix}_package_spindle",
        name=f"B-05 {suffix} package spindle",
        radius=5.0,
        length=80.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["stainless"],
        tags=("role.bias_supply", "role.package_spindle"),
    )
    pedestal = make_box_part(
        part_id=f"b_05_{suffix}_bearing_pedestal",
        name=f"B-05 {suffix} package bearing pedestal",
        size=(12.0, 36.0, 36.0),
        material=materials["machined_aluminum"],
        tags=("role.bias_supply", "role.spindle_support"),
    )
    components: list[ComponentSpec] = []
    for side, y_value in (("left", -65.0), ("right", 65.0)):
        components.append(
            ComponentSpec(
                f"foundation_stringer_{side}",
                foundation_stringer,
                (-790.0, y_value, parameters.base_datum_z.value),
                foundation_stringer.name,
            )
        )
    components.append(
        ComponentSpec(
            "chain_support_bed", bed, (-790.0, 0.0, center_z - 92.0), bed.name
        )
    )
    for x_label, x_value in (("rear", -1000.0), ("front", -580.0)):
        for y_label, y_value in (("left", -65.0), ("right", 65.0)):
            components.append(
                ComponentSpec(
                    f"support_post_{x_label}_{y_label}",
                    support_post,
                    (x_value, y_value, parameters.base_datum_z.value + 40.0),
                    support_post.name,
                )
            )
    for y_value in (-50.0, 50.0):
        for z_offset in (-65.0, 65.0):
            components.append(
                ComponentSpec(
                    f"chain_{int(y_value)}_{int(z_offset)}",
                    chain_run,
                    (-790.0, y_value, center_z + z_offset),
                    f"{suffix.title()} bias chain straight run",
                )
            )
    for side, x_value in (("rear", -1000.0), ("front", -580.0)):
        for y_label, y_value in (("left", -59.0), ("right", 41.0)):
            components.append(
                ComponentSpec(
                    f"sprocket_{side}_{y_label}",
                    sprocket,
                    (x_value, y_value, center_z),
                    f"{suffix.title()} {side} {y_label} chain sprocket",
                )
            )
    representative_x = (-930.0, -790.0, -650.0)
    for index, x_value in enumerate(representative_x):
        components.extend(
            (
                ComponentSpec(
                    f"carrier_{index}",
                    carrier,
                    (x_value, 0.0, center_z + 65.0),
                    f"Representative {suffix} moving carrier {index + 1}",
                ),
                ComponentSpec(
                    f"package_{index}",
                    spool,
                    (x_value, 0.0, center_z + 94.0),
                    f"Representative {suffix} bias package {index + 1}",
                ),
                ComponentSpec(
                    f"package_spindle_{index}",
                    spindle,
                    (x_value - 40.0, 0.0, center_z + 94.0),
                    f"Representative {suffix} package spindle {index + 1}",
                ),
                ComponentSpec(
                    f"left_pedestal_{index}",
                    pedestal,
                    (x_value - 35.0, 0.0, center_z + 73.0),
                    pedestal.name,
                ),
                ComponentSpec(
                    f"right_pedestal_{index}",
                    pedestal,
                    (x_value + 35.0, 0.0, center_z + 73.0),
                    pedestal.name,
                ),
            )
        )
    assembly = make_static_assembly(
        assembly_id=f"a{'30' if upper else '31'}_{suffix}_bias_supply",
        name=f"A{'30' if upper else '31'} {suffix} moving bias supply chain",
        components=components,
    )
    print(
        f"a{'30' if upper else '31'}_bias_supply: "
        f"displayed_packages={len(representative_x)} direction={'positive' if upper else 'negative'}"
    )
    return assembly
