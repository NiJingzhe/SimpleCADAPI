"""Example 12: herringbone planetary reducer carrier assembly.

This example builds a planetary reducer layout with a fixed internal ring gear:

- one sun-drive carrier plate with a central shaft
- one herringbone sun gear fixed to that sun-drive plate
- one fixed herringbone internal ring gear
- one upper Y-shaped planet-carrier output plate with three pins
- one reusable herringbone planet gear Part instanced three times

The ring gear is the grounded reference in this static CAD assembly. The sun
gear is fixed to the input shaft, while the planet carrier and each planet gear
use revolute joints so the product structure reflects the intended power path:
sun input -> planet gears against fixed ring -> slower planet-carrier output.
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
SUN_HELIX_ANGLE = 25.0
PLANET_HELIX_ANGLE = -SUN_HELIX_ANGLE
RING_HELIX_ANGLE = PLANET_HELIX_ANGLE
RING_RIM_THICKNESS = 5.0
RING_BACKLASH = 0.08 * MODULE
SUN_PITCH_RADIUS = MODULE * SUN_TEETH / 2.0
PLANET_PITCH_RADIUS = MODULE * PLANET_TEETH / 2.0
RING_PITCH_RADIUS = MODULE * RING_TEETH / 2.0
SUN_BORE_RADIUS = 4.2
PLANET_BORE_RADIUS = 3.5
SUN_SHAFT_RADIUS = SUN_BORE_RADIUS - 0.2
SUN_AXIS_SHOULDER_RADIUS = SUN_BORE_RADIUS - 0.05
PLANET_PIN_RADIUS = PLANET_BORE_RADIUS - 0.7
PLANET_PIN_BEARING_RADIUS = PLANET_BORE_RADIUS - 0.3
SUN_DRIVE_PLATE_RADIUS = 14.0
SUN_DRIVE_PLATE_THICKNESS = 4.0
SUN_DRIVE_PLATE_BOTTOM_Z = -8.0
PLANET_CARRIER_THICKNESS = 3.0
PLANET_CARRIER_BOTTOM_Z = GEAR_HEIGHT + 1.0
CARRIER_AXIS_CONNECTOR_Z = PLANET_CARRIER_BOTTOM_Z + PLANET_CARRIER_THICKNESS
SUN_AXIS_CONNECTOR_Z = GEAR_HEIGHT
PLANET_AXIS_CONNECTOR_Z = GEAR_HEIGHT
PLANET_PIN_BOTTOM_Z = -0.25
PLANET_PIN_TOP_CLEARANCE = 0.5
CARRIER_CENTER_CLEARANCE_RADIUS = SUN_BORE_RADIUS + 1.0
CARRIER_HUB_RADIUS = CARRIER_CENTER_CLEARANCE_RADIUS + 4.5
CARRIER_ARM_WIDTH = 8.0
CARRIER_ARM_INNER_CLEARANCE = 0.6
CARRIER_ARM_END_OVERHANG = 1.0
PLANET_PAD_RADIUS = PLANET_BORE_RADIUS + 4.5
SUN_SHAFT_TOP_Z = CARRIER_AXIS_CONNECTOR_Z
OUTPUT_DIR = Path("examples/out/herringbone_planetary_gears")


def _planet_spin_angle(carrier_angle_deg: float) -> float:
    """Phase each planet so a tooth gap faces the sun contact line."""
    planet_half_pitch_deg = 180.0 / PLANET_TEETH
    return carrier_angle_deg + 180.0 - planet_half_pitch_deg


def _z_rotation_placement(origin: tuple[float, float, float], angle_degrees: float):
    angle_rad = math.radians(angle_degrees)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return scad.make_placement_rplacement(
        origin=origin,
        x_axis=(cos_a, sin_a, 0.0),
        y_axis=(-sin_a, cos_a, 0.0),
    )


def _ground_solid(label: str, solid: scad.Solid) -> None:
    faces = ql.select(solid.get_faces()).all()
    tagged_role_faces = ql.select(faces).where(ql.tag("role.*")).all()
    print(
        f"{label}: faces={len(faces)} role_faces={len(tagged_role_faces)} "
        f"volume={solid.get_volume():.1f} tags={','.join(scad.list_tags(solid))}"
    )


def _ground_compound(label: str, compound: scad.Compound) -> None:
    solids = ql.select(compound.get_solids()).all()
    face_count = sum(len(ql.select(solid.get_faces()).all()) for solid in solids)
    volume = sum(solid.get_volume() for solid in solids)
    print(f"{label}: solids={len(solids)} faces={face_count} volume={volume:.1f}")


def _axis_face(
    label: str,
    solid: scad.Solid,
    center_xy: tuple[float, float],
    target_z: float,
    normal_z: float,
) -> scad.Face:
    candidates = []
    for face in ql.select(solid.get_faces()).all():
        normal = face.get_normal_at()
        if normal_z > 0.0 and normal.z < 0.7:
            continue
        if normal_z < 0.0 and normal.z > -0.7:
            continue
        center = face.get_center()
        xy_error = math.hypot(center.x - center_xy[0], center.y - center_xy[1])
        z_error = abs(center.z - target_z)
        candidates.append((z_error * 100.0 + xy_error, face, center, normal))

    if not candidates:
        raise ValueError(f"no connector face found for {label}")

    _score, face, center, normal = min(candidates, key=lambda item: item[0])
    print(
        f"{label}_connector_face: center=({center.x:.3f},{center.y:.3f},{center.z:.3f}) "
        f"normal=({normal.x:.3f},{normal.y:.3f},{normal.z:.3f}) area={face.get_area():.3f}"
    )
    return face


def _cut_axial_bore(label: str, solid: scad.Solid, radius: float) -> scad.Solid:
    cutter = scad.make_cylinder_rsolid(
        radius=radius,
        height=GEAR_HEIGHT + 2.0,
        bottom_face_center=(0.0, 0.0, -1.0),
        axis=(0.0, 0.0, 1.0),
    )
    bored = scad.cut_rsolid(solid, cutter, skip_non_intersecting=False)
    bored = scad.apply_tag(bored, f"solid.cut.{label}")
    faces = ql.select(bored.get_faces()).all()
    print(
        f"{label}: bore_radius={radius:.2f} faces={len(faces)} "
        f"volume={bored.get_volume():.1f} tags={','.join(scad.list_tags(bored))}"
    )
    return bored


def _build_sun_drive_plate() -> scad.Solid:
    plate = scad.make_cylinder_rsolid(
        radius=SUN_DRIVE_PLATE_RADIUS,
        height=SUN_DRIVE_PLATE_THICKNESS,
        bottom_face_center=(0.0, 0.0, SUN_DRIVE_PLATE_BOTTOM_Z),
        axis=(0.0, 0.0, 1.0),
    )
    shaft = scad.make_cylinder_rsolid(
        radius=SUN_SHAFT_RADIUS,
        height=SUN_SHAFT_TOP_Z - SUN_DRIVE_PLATE_BOTTOM_Z,
        bottom_face_center=(0.0, 0.0, SUN_DRIVE_PLATE_BOTTOM_Z),
        axis=(0.0, 0.0, 1.0),
    )
    sun_axis_shoulder = scad.make_cylinder_rsolid(
        radius=SUN_AXIS_SHOULDER_RADIUS,
        height=SUN_AXIS_CONNECTOR_Z - SUN_DRIVE_PLATE_BOTTOM_Z,
        bottom_face_center=(0.0, 0.0, SUN_DRIVE_PLATE_BOTTOM_Z),
        axis=(0.0, 0.0, 1.0),
    )
    drive_plate = scad.union_rsolid(plate, sun_axis_shoulder, shaft, glue=False)
    drive_plate = scad.apply_tag(drive_plate, "role.sun_drive_plate")
    drive_plate = scad.apply_tag(drive_plate, "group.herringbone_planetary")
    _ground_solid("sun_drive_plate", drive_plate)
    return drive_plate


def _build_planet_carrier(planet_center_radius: float) -> scad.Solid:
    arm_inner_x = CARRIER_CENTER_CLEARANCE_RADIUS + CARRIER_ARM_INNER_CLEARANCE
    arm_outer_x = planet_center_radius + PLANET_PAD_RADIUS + CARRIER_ARM_END_OVERHANG
    arm_length = arm_outer_x - arm_inner_x
    arm_center_x = (arm_inner_x + arm_outer_x) / 2.0
    pin_height = (
        PLANET_CARRIER_BOTTOM_Z
        + PLANET_CARRIER_THICKNESS
        + PLANET_PIN_TOP_CLEARANCE
        - PLANET_PIN_BOTTOM_Z
    )
    hub = scad.make_cylinder_rsolid(
        radius=CARRIER_HUB_RADIUS,
        height=PLANET_CARRIER_THICKNESS,
        bottom_face_center=(0.0, 0.0, PLANET_CARRIER_BOTTOM_Z),
        axis=(0.0, 0.0, 1.0),
    )

    solids = [hub]
    for index in range(PLANET_COUNT):
        carrier_angle_deg = 360.0 * index / PLANET_COUNT
        carrier_angle_rad = math.radians(carrier_angle_deg)
        arm = scad.make_box_rsolid(
            CARRIER_ARM_WIDTH,
            arm_length,
            PLANET_CARRIER_THICKNESS,
            bottom_face_center=(arm_center_x, 0.0, PLANET_CARRIER_BOTTOM_Z),
        )
        if carrier_angle_deg != 0.0:
            arm = scad.rotate_shape(
                arm,
                carrier_angle_deg,
                axis=(0.0, 0.0, 1.0),
                origin=(0.0, 0.0, 0.0),
            )
        solids.append(arm)

        center = (
            planet_center_radius * math.cos(carrier_angle_rad),
            planet_center_radius * math.sin(carrier_angle_rad),
        )
        solids.append(
            scad.make_cylinder_rsolid(
                radius=PLANET_PAD_RADIUS,
                height=PLANET_CARRIER_THICKNESS,
                bottom_face_center=(center[0], center[1], PLANET_CARRIER_BOTTOM_Z),
                axis=(0.0, 0.0, 1.0),
            )
        )
        solids.append(
            scad.make_cylinder_rsolid(
                radius=PLANET_PIN_RADIUS,
                height=pin_height,
                bottom_face_center=(center[0], center[1], PLANET_PIN_BOTTOM_Z),
                axis=(0.0, 0.0, 1.0),
            )
        )
        solids.append(
            scad.make_cylinder_rsolid(
                radius=PLANET_PIN_BEARING_RADIUS,
                height=PLANET_AXIS_CONNECTOR_Z - PLANET_PIN_BOTTOM_Z,
                bottom_face_center=(center[0], center[1], PLANET_PIN_BOTTOM_Z),
                axis=(0.0, 0.0, 1.0),
            )
        )

    carrier = scad.union_rsolid(solids, glue=False)
    carrier = scad.cut_rsolid(
        carrier,
        scad.make_cylinder_rsolid(
            radius=CARRIER_CENTER_CLEARANCE_RADIUS,
            height=PLANET_CARRIER_THICKNESS + 2.0,
            bottom_face_center=(0.0, 0.0, PLANET_CARRIER_BOTTOM_Z - 1.0),
            axis=(0.0, 0.0, 1.0),
        ),
        skip_non_intersecting=False,
    )
    carrier = scad.apply_tag(carrier, "role.planet_carrier")
    carrier = scad.apply_tag(carrier, "group.herringbone_planetary")
    print(
        f"planet_carrier_y_top: arms={PLANET_COUNT} arm_width={CARRIER_ARM_WIDTH:.2f} "
        f"arm_length={arm_length:.2f} top_z={PLANET_CARRIER_BOTTOM_Z + PLANET_CARRIER_THICKNESS:.2f} "
        f"hub_radius={CARRIER_HUB_RADIUS:.2f} pad_radius={PLANET_PAD_RADIUS:.2f}"
    )
    _ground_solid("planet_carrier", carrier)
    return carrier


def build_herringbone_planetary_gearset():
    """Build the open planetary carrier assembly and return preview/model JSON."""
    planet_center_radius = MODULE * (SUN_TEETH + PLANET_TEETH) / 2.0

    with scad.GraphSession() as session:
        sun_drive_plate = _build_sun_drive_plate()
        planet_carrier = _build_planet_carrier(planet_center_radius)

        ring = scad.std.gear.make_herringbone_ring_gear_rsolid(
            n_teeth=RING_TEETH,
            module=MODULE,
            helix_angle=RING_HELIX_ANGLE,
            gear_height=GEAR_HEIGHT,
            rim_thickness=RING_RIM_THICKNESS,
            backlash=RING_BACKLASH,
        )
        ring = scad.apply_tag(ring, "role.fixed_ring_gear")
        ring = scad.apply_tag(ring, "group.herringbone_planetary")
        _ground_solid("fixed_ring", ring)

        sun = scad.std.gear.make_herringbone_gear_rsolid(
            n_teeth=SUN_TEETH,
            module=MODULE,
            helix_angle=SUN_HELIX_ANGLE,
            gear_height=GEAR_HEIGHT,
        )
        sun = _cut_axial_bore("sun_bore", sun, SUN_BORE_RADIUS)
        sun = scad.apply_tag(sun, "role.sun_gear")
        sun = scad.apply_tag(sun, "group.herringbone_planetary")
        _ground_solid("sun", sun)

        planet_base = scad.std.gear.make_herringbone_gear_rsolid(
            n_teeth=PLANET_TEETH,
            module=MODULE,
            helix_angle=PLANET_HELIX_ANGLE,
            gear_height=GEAR_HEIGHT,
        )
        planet_base = _cut_axial_bore("planet_bore", planet_base, PLANET_BORE_RADIUS)
        planet_base = scad.apply_tag(planet_base, "role.planet_gear")
        planet_base = scad.apply_tag(planet_base, "group.herringbone_planetary")
        _ground_solid("planet_part", planet_base)

        carrier_material = scad.make_material_rmaterial(
            "matte_anodized_aluminum",
            name="Matte anodized aluminum",
            density=2.7e-6,
            density_unit="kg/mm^3",
            color=(0.28, 0.30, 0.32),
        )
        gear_material = scad.make_material_rmaterial(
            "case_hardened_gear_steel",
            name="Case hardened gear steel",
            density=7.85e-6,
            density_unit="kg/mm^3",
            color=(0.68, 0.70, 0.72),
        )
        print(f"materials: {carrier_material.material_id},{gear_material.material_id}")

        ring_part = scad.make_part_rpart(
            "fixed_herringbone_ring",
            ring,
            name="Fixed herringbone internal ring gear",
        )
        ring_part = scad.assign_material_rpart(ring_part, gear_material)
        ring_part = scad.add_connector_rpart(
            ring_part,
            scad.make_face_connector_rconnector(
                "axis",
                _axis_face("ring_axis", ring, (0.0, 0.0), GEAR_HEIGHT, 1.0),
            ),
        )

        sun_drive_part = scad.make_part_rpart(
            "sun_drive_plate",
            sun_drive_plate,
            name="Grounded sun-drive plate with central shaft",
        )
        sun_drive_part = scad.assign_material_rpart(sun_drive_part, carrier_material)
        sun_drive_part = scad.add_connector_rpart(
            sun_drive_part,
            scad.make_face_connector_rconnector(
                "carrier_axis",
                _axis_face(
                    "sun_drive_carrier_axis",
                    sun_drive_plate,
                    (0.0, 0.0),
                    CARRIER_AXIS_CONNECTOR_Z,
                    1.0,
                ),
            ),
        )
        sun_drive_part = scad.add_connector_rpart(
            sun_drive_part,
            scad.make_face_connector_rconnector(
                "sun_axis",
                _axis_face(
                    "sun_drive_sun_axis",
                    sun_drive_plate,
                    (0.0, 0.0),
                    SUN_AXIS_CONNECTOR_Z,
                    1.0,
                ),
            ),
        )

        carrier_part = scad.make_part_rpart(
            "planet_carrier",
            planet_carrier,
            name="Planet carrier output plate with three pins",
        )
        carrier_part = scad.assign_material_rpart(carrier_part, carrier_material)
        carrier_part = scad.add_connector_rpart(
            carrier_part,
            scad.make_face_connector_rconnector(
                "carrier_axis",
                _axis_face(
                    "planet_carrier_axis",
                    planet_carrier,
                    (0.0, 0.0),
                    CARRIER_AXIS_CONNECTOR_Z,
                    1.0,
                ),
            ),
        )
        for index in range(PLANET_COUNT):
            carrier_angle_deg = 360.0 * index / PLANET_COUNT
            carrier_angle_rad = math.radians(carrier_angle_deg)
            center_xy = (
                planet_center_radius * math.cos(carrier_angle_rad),
                planet_center_radius * math.sin(carrier_angle_rad),
            )
            carrier_part = scad.add_connector_rpart(
                carrier_part,
                scad.make_face_connector_rconnector(
                    f"planet_{index + 1}_axis",
                    _axis_face(
                        f"carrier_planet_{index + 1}_axis",
                        planet_carrier,
                        center_xy,
                        PLANET_AXIS_CONNECTOR_Z,
                        1.0,
                    ),
                ),
            )

        sun_part = scad.make_part_rpart(
            "herringbone_sun", sun, name="Herringbone sun gear"
        )
        sun_part = scad.assign_material_rpart(sun_part, gear_material)
        sun_part = scad.add_connector_rpart(
            sun_part,
            scad.make_face_connector_rconnector(
                "axis",
                _axis_face("sun_axis", sun, (0.0, 0.0), GEAR_HEIGHT, 1.0),
            ),
        )

        planet_part = scad.make_part_rpart(
            "herringbone_planet", planet_base, name="Reusable herringbone planet gear"
        )
        planet_part = scad.assign_material_rpart(planet_part, gear_material)
        planet_part = scad.add_connector_rpart(
            planet_part,
            scad.make_face_connector_rconnector(
                "axis",
                _axis_face("planet_axis", planet_base, (0.0, 0.0), GEAR_HEIGHT, 1.0),
            ),
        )
        print(
            "parts: "
            f"{ring_part.part_id},{sun_drive_part.part_id},{carrier_part.part_id},"
            f"{sun_part.part_id},{planet_part.part_id}"
        )

        gearset = scad.make_assembly_rassembly(
            "herringbone_planetary_gearset",
            name="Fixed-ring herringbone planetary reducer assembly",
        )
        gearset = scad.add_component_rassembly(
            gearset,
            ring_part,
            component_id="fixed_ring",
            placement=_z_rotation_placement((0.0, 0.0, 0.0), 0.0),
            name="Grounded fixed internal ring gear",
        )
        gearset = scad.add_component_rassembly(
            gearset,
            sun_drive_part,
            component_id="sun_drive_plate",
            placement=_z_rotation_placement((0.0, 0.0, 0.0), 0.0),
            name="Grounded sun-drive input plate",
        )
        gearset = scad.add_component_rassembly(
            gearset,
            carrier_part,
            component_id="planet_carrier",
            placement=_z_rotation_placement((0.0, 0.0, 0.0), 0.0),
            name="Planet-carrier output plate",
        )
        gearset = scad.add_component_rassembly(
            gearset,
            sun_part,
            component_id="sun",
            placement=_z_rotation_placement((0.0, 0.0, 0.0), 0.0),
            name="Sun gear fixed to input plate",
        )

        for index in range(PLANET_COUNT):
            carrier_angle_deg = 360.0 * index / PLANET_COUNT
            carrier_angle_rad = math.radians(carrier_angle_deg)
            center = (
                planet_center_radius * math.cos(carrier_angle_rad),
                planet_center_radius * math.sin(carrier_angle_rad),
                0.0,
            )
            spin_angle = _planet_spin_angle(carrier_angle_deg)
            gearset = scad.add_component_rassembly(
                gearset,
                planet_part,
                component_id=f"planet_{index + 1}",
                placement=_z_rotation_placement(center, spin_angle),
                name=f"Planet gear {index + 1}",
            )
            print(
                f"planet_{index + 1}: carrier={carrier_angle_deg:.1f}deg "
                f"center=({center[0]:.3f},{center[1]:.3f},{center[2]:.3f}) "
                f"spin={spin_angle:.1f}deg"
            )

        gearset = scad.ground_component_rassembly(gearset, "fixed_ring")
        gearset = scad.add_revolute_constraint_rassembly(
            gearset,
            "sun_input_revolute",
            scad.make_connector_ref_rconnectorref("fixed_ring", "axis"),
            scad.make_connector_ref_rconnectorref("sun_drive_plate", "sun_axis"),
            name="Sun input shaft rotates inside the fixed ring gear",
        )
        gearset = scad.add_revolute_constraint_rassembly(
            gearset,
            "carrier_output_revolute",
            scad.make_connector_ref_rconnectorref("sun_drive_plate", "carrier_axis"),
            scad.make_connector_ref_rconnectorref("planet_carrier", "carrier_axis"),
            name="Planet carrier rotates around the sun-drive plate axis",
        )
        gearset = scad.add_fixed_constraint_rassembly(
            gearset,
            "sun_fixed_to_drive_plate",
            scad.make_connector_ref_rconnectorref("sun_drive_plate", "sun_axis"),
            scad.make_connector_ref_rconnectorref("sun", "axis"),
            name="Sun gear fixed to the input shaft",
        )
        for index in range(PLANET_COUNT):
            gearset = scad.add_revolute_constraint_rassembly(
                gearset,
                f"planet_{index + 1}_revolute",
                scad.make_connector_ref_rconnectorref("planet_carrier", f"planet_{index + 1}_axis"),
                scad.make_connector_ref_rconnectorref(f"planet_{index + 1}", "axis"),
                name=f"Planet gear {index + 1} rotates on its carrier pin",
            )
        for index in range(PLANET_COUNT):
            planet_ref = scad.make_connector_ref_rconnectorref(
                component_id=f"planet_{index + 1}",
                connector_id="axis",
            )
            gearset = scad.add_gear_constraint_rassembly(
                assembly=gearset,
                constraint_id=f"sun_planet_{index + 1}_external_mesh",
                connector_a=scad.make_connector_ref_rconnectorref(
                    component_id="sun_drive_plate",
                    connector_id="sun_axis",
                ),
                connector_b=planet_ref,
                pitch_radius_a=SUN_PITCH_RADIUS,
                pitch_radius_b=PLANET_PITCH_RADIUS,
                name=f"External sun to planet {index + 1} gear mesh",
            )
            gearset = scad.add_belt_constraint_rassembly(
                assembly=gearset,
                constraint_id=f"ring_planet_{index + 1}_internal_mesh",
                connector_a=scad.make_connector_ref_rconnectorref(
                    component_id="fixed_ring",
                    connector_id="axis",
                ),
                connector_b=planet_ref,
                pulley_radius_a=RING_PITCH_RADIUS,
                pulley_radius_b=PLANET_PITCH_RADIUS,
                name=f"Internal fixed-ring to planet {index + 1} gear mesh",
            )
        print(
            "gear_constraints: "
            f"sun_planet_external={PLANET_COUNT} ring_planet_internal={PLANET_COUNT} "
            f"radii=({SUN_PITCH_RADIUS:.3f},{PLANET_PITCH_RADIUS:.3f},{RING_PITCH_RADIUS:.3f})"
        )
        gearset = scad.solve_assembly_constraints_rassembly(gearset)
        report = scad.inspect_assembly_constraints_rconstraintreport(gearset)
        print(
            "assembly: "
            f"components={','.join(gearset.component_ids())} "
            f"grounded={','.join(gearset.grounded_component_ids)} "
            f"solved={report.solved} constraints={len(gearset.constraints)}"
        )
        for residual in report.residuals:
            print(
                f"constraint_{residual.constraint_id}: "
                f"translation={residual.translation_error:.6g} "
                f"angle={residual.angular_error_degrees:.6g} "
                f"ok={residual.within_tolerance}"
            )

        preview = scad.make_compound_from_assembly_rcompound(gearset)
        _ground_compound("assembly_preview", preview)
        model_json = scad.export_model_json(session)

    return gearset, preview, model_json


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    model_path = OUTPUT_DIR / "herringbone_planetary_gearset.model.json"
    step_path = OUTPUT_DIR / "herringbone_planetary_gearset.step"
    fcstd_path = OUTPUT_DIR / "herringbone_planetary_gearset.FCStd"
    if fcstd_path.exists():
        fcstd_path.unlink()

    assembly, preview, model_json = build_herringbone_planetary_gearset()
    model_path.write_text(model_json, encoding="utf-8")
    scad.export_step(preview, str(step_path))

    fcstd_status = "not attempted"
    try:
        scad.translator.freecad_translator.translate_model_json_to_fcstd(model_json, str(fcstd_path.resolve()))
        fcstd_status = f"{fcstd_path} ({fcstd_path.stat().st_size} bytes)"
    except Exception as exc:  # pragma: no cover - depends on local FreeCAD install
        fcstd_status = f"failed ({exc.__class__.__name__}: {exc})"

    payload = json.loads(model_json)
    replayed = scad.replay_model_json(model_json)
    solids = ql.select(preview.get_solids()).all()
    face_count = sum(len(ql.select(solid.get_faces()).all()) for solid in solids)
    volumes = [solid.get_volume() for solid in solids]

    print(
        "sun_z={sun}  planet_z={planet}  ring_z={ring}  planets={count}  "
        "module={module}  height={height}  sun_helix={sun_helix}  planet_helix={planet_helix}".format(
            sun=SUN_TEETH,
            planet=PLANET_TEETH,
            ring=RING_TEETH,
            count=PLANET_COUNT,
            module=MODULE,
            height=GEAR_HEIGHT,
            sun_helix=SUN_HELIX_ANGLE,
            planet_helix=PLANET_HELIX_ANGLE,
        )
    )
    print(f"planet_center_radius={MODULE * (SUN_TEETH + PLANET_TEETH) / 2.0:.3f}")
    print(f"assembly={assembly.assembly_id}")
    print("components=" + ",".join(assembly.component_ids()))
    print(f"preview_solids={len(solids)}")
    print(f"preview_faces={face_count}")
    print("volumes=" + ",".join(f"{volume:.1f}" for volume in volumes))
    print(f"replay_outputs={len(replayed)}")
    print("replay_types=" + ",".join(type(item).__name__ for item in replayed))
    print(f"graph_nodes={len(payload['graph']['nodes'])}")
    print(f"model={model_path}")
    print(f"step={step_path}")
    print(f"fcstd={fcstd_status}")


if __name__ == "__main__":
    main()
