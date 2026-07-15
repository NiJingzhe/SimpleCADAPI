"""A80 handed edge hooks, magazines, opposed insertion, and longitudinal rails."""

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


def _make_edge_hook(
    *,
    right: bool,
    materials: dict[str, scad.Material],
) -> scad.Part:
    suffix = "right" if right else "left"
    stem = scad.make_box_rsolid(
        width=8.0,
        height=28.0,
        depth=48.0,
        bottom_face_center=(0.0, 0.0, 0.0),
    )
    nose = scad.make_cylinder_rsolid(
        radius=8.0,
        height=8.0,
        bottom_face_center=(0.0, (12.0 if right else -12.0), 40.0),
        axis=(0.0, 1.0 if right else -1.0, 0.0),
    )
    foot = scad.make_box_rsolid(
        width=20.0,
        height=14.0,
        depth=10.0,
        bottom_face_center=(0.0, (7.0 if right else -7.0), 0.0),
    )
    body = scad.union_rsolid(stem, nose, foot, glue=False)
    body = apply_tags(
        shape=body,
        tags=("role.edge_hook", "role.yarn_contact", "role.handed_part"),
    )
    return make_part(
        part_id=f"h_0{'2' if right else '1'}_{suffix}_edge_hook",
        name=f"H-0{'2' if right else '1'} {suffix} J-shaped edge hook",
        body=body,
        material=materials["stainless"],
        connectors=(),
    )


def make_width_control(
    *,
    parameters: MachineParameters,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    left_hook = _make_edge_hook(right=False, materials=materials)
    right_hook = _make_edge_hook(right=True, materials=materials)
    rail = make_u_part(
        part_id="h_06_c_hook_rail",
        name="H-06 open C-shaped longitudinal hook rail",
        outer_width=40.0,
        height=34.0,
        depth=parameters.takeup_travel.value + 120.0,
        wall=7.0,
        material=materials["wear_rail"],
        tags=("role.width_control", "role.traveling_hook_rail", "role.service_opening"),
    )
    magazine = make_box_part(
        part_id="h_03_hook_magazine",
        name="H-03/H-04 spring hook magazine envelope",
        size=(90.0, 46.0, 170.0),
        material=materials["guard"],
        tags=("role.width_control", "role.hook_magazine"),
    )
    insertion_slide = make_box_part(
        part_id="h_05_hook_insertion_slide",
        name="H-05 opposed short-stroke hook insertion slide",
        size=(34.0, 110.0, 32.0),
        material=materials["machined_aluminum"],
        tags=("role.width_control", "role.insertion_slide"),
    )
    sync_shaft = make_cylinder_part(
        part_id="h_07_sync_shaft",
        name="H-07 positive left/right hook synchronization shaft",
        radius=12.0,
        length=500.0,
        axis=(0.0, 1.0, 0.0),
        material=materials["stainless"],
        tags=("role.width_control", "role.mechanical_phase_lock"),
    )
    motor = make_cylinder_part(
        part_id="m9_hook_drive",
        name="M9 hook insertion servo/reducer envelope",
        radius=42.0,
        length=95.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["drive"],
        tags=("role.width_control", "role.motor_envelope"),
    )
    rail_post = make_box_part(
        part_id="h_06_hook_rail_post",
        name="H-06 longitudinal hook-rail support post",
        size=(40.0, 40.0, 513.0),
        material=materials["structural_steel"],
        tags=("role.width_control", "role.structural_support"),
    )
    magazine_post = make_box_part(
        part_id="h_03_magazine_post",
        name="H-03/H-04 hook-magazine support post",
        size=(50.0, 50.0, 445.0),
        material=materials["structural_steel"],
        tags=("role.width_control", "role.magazine_support"),
    )
    shaft_bearing = make_box_part(
        part_id="h_07_sync_shaft_bearing",
        name="H-07 hook sync-shaft bearing block",
        size=(50.0, 50.0, 60.0),
        material=materials["machined_aluminum"],
        tags=("role.width_control", "role.shaft_support"),
    )
    drive_shelf = make_box_part(
        part_id="h_07_drive_shelf",
        name="H-07/M9 hook-drive mounting shelf",
        size=(170.0, 90.0, 20.0),
        material=materials["structural_steel"],
        tags=("role.width_control", "role.motor_mount"),
    )
    fold = parameters.effective_width.value / 2.0
    components = [
        ComponentSpec(
            "left_hook_rail",
            rail,
            (0.0, -fold, -17.0),
            "Left longitudinal hook rail",
            x_axis=(0.0, 1.0, 0.0),
            y_axis=(0.0, 0.0, 1.0),
        ),
        ComponentSpec(
            "right_hook_rail",
            rail,
            (0.0, fold, -17.0),
            "Right longitudinal hook rail",
            x_axis=(0.0, 1.0, 0.0),
            y_axis=(0.0, 0.0, 1.0),
        ),
        ComponentSpec("left_hook", left_hook, (8.0, -fold, 0.0), left_hook.name),
        ComponentSpec("right_hook", right_hook, (8.0, fold, 0.0), right_hook.name),
        ComponentSpec(
            "left_magazine",
            magazine,
            (-35.0, -fold - 120.0, -85.0),
            "Left hook magazine",
        ),
        ComponentSpec(
            "right_magazine",
            magazine,
            (-35.0, fold + 120.0, -85.0),
            "Right hook magazine",
        ),
        ComponentSpec(
            "left_insertion_slide",
            insertion_slide,
            (0.0, -fold - 70.0, -16.0),
            "Left insertion slide",
        ),
        ComponentSpec(
            "right_insertion_slide",
            insertion_slide,
            (0.0, fold + 70.0, -16.0),
            "Right insertion slide",
        ),
        ComponentSpec(
            "sync_shaft", sync_shaft, (-90.0, -250.0, -150.0), sync_shaft.name
        ),
        ComponentSpec("m9_drive", motor, (-135.0, -250.0, -150.0), motor.name),
        ComponentSpec(
            "left_magazine_post",
            magazine_post,
            (-35.0, -fold - 120.0, parameters.base_datum_z.value + 40.0),
            magazine_post.name,
        ),
        ComponentSpec(
            "right_magazine_post",
            magazine_post,
            (-35.0, fold + 120.0, parameters.base_datum_z.value + 40.0),
            magazine_post.name,
        ),
        ComponentSpec(
            "left_shaft_bearing",
            shaft_bearing,
            (-90.0, -250.0, -180.0),
            shaft_bearing.name,
        ),
        ComponentSpec(
            "right_shaft_bearing",
            shaft_bearing,
            (-90.0, 250.0, -180.0),
            shaft_bearing.name,
        ),
        ComponentSpec(
            "m9_drive_shelf", drive_shelf, (-85.0, -250.0, -212.0), drive_shelf.name
        ),
    ]
    for side, y_value in (("left", -fold), ("right", fold)):
        for station, x_value in (
            ("inlet", 30.0),
            ("middle", 550.0),
            ("outlet", 1070.0),
        ):
            components.append(
                ComponentSpec(
                    f"{side}_{station}_rail_post",
                    rail_post,
                    (x_value, y_value, parameters.base_datum_z.value + 40.0),
                    rail_post.name,
                )
            )
    assembly = make_static_assembly(
        assembly_id="a80_width_hooks",
        name="A80 handed edge hooks, opposed insertion, and traveling C rails",
        components=components,
    )
    print(f"a80_width_control: fold_lines=+/-{fold:g} hooks_per_cycle=2")
    return assembly
