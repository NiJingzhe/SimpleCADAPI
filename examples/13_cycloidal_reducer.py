"""Example 13: compact 50 mm x 10 mm cycloidal reducer assembly.

Design plan
===========

Package envelope:
- Maximum outside diameter: 50 mm.
- Maximum stack height: 10 mm.

Reduction stage:
- Fixed pin ring: 11 pins.
- Twin cycloidal discs: 10 lobes each, stacked with 180 degree eccentric
  carrier separation and a half-lobe tooth-index phase for load balance.
- Single-stage reduction: 11 - 1 = 10:1.
- The fixed pin ring contact is represented as a gear-like coupling between the
  input eccentric carrier and each cycloidal disc's relative spin: each disc
  spins -11/10 turn relative to its eccentric carrier for each input turn,
  giving a global cycloidal/output phase of -1/10 input turn.

Structure:
- fixed_housing: outer sleeve, top/bottom retainers, and 11 fixed ring pins.
- input_disk: bottom three-hole threaded mounting disk plus a double eccentric
  cam shaft. The lower cam is at 0 degrees; the upper cam is at 180 degrees.
- lower_cycloidal_disc and upper_cycloidal_disc: 10-lobed discs with eccentric
  bearing bores and three oversize output-pin relief holes. The upper disc is
  tooth-indexed by half a lobe, i.e. 180 degrees divided by 10 lobes = 18
  geometric degrees. A full 180 degree rotation would be symmetry-equivalent
  to the lower disc because the profile has 10 lobes.
- output_disk: top three-hole threaded mounting disk plus three output pins.

Assembly relationships:
- fixed_housing is grounded.
- input_disk is revolute about the housing axis.
- output_disk is revolute about the housing axis.
- lower_cycloidal_disc is revolute on the lower input eccentric cam axis.
- upper_cycloidal_disc is revolute on the upper input eccentric cam axis.
- input_disk to each cycloidal disc has a gear-like pin-ring rolling coupling.

The output pins are fixed to the output disk and pass through oversize circular
holes in both cycloidal discs. The two discs load those pins from opposite
eccentric directions, so the real mechanism keeps the output-pin side load more
balanced through a full rotation. This SDK does not yet have a native
pin-slot/contact primitive, so the example models that relation as clearance
geometry rather than a false coaxial ratio shortcut.

Each cycloidal outline is fit as ten cubic B-spline segments, one segment per
lobe. This keeps the exported topology small and stable while preserving the
analytic pin-wheel profile within a controlled fit tolerance.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import simplecadapi as scad
from simplecadapi import ql


sys.setrecursionlimit(20000)


PACKAGE_DIAMETER = 50.0
PACKAGE_RADIUS = PACKAGE_DIAMETER / 2.0
PACKAGE_HEIGHT = 10.0
OUTPUT_DIR = Path("examples/out/cycloidal_reducer_50mm_10x")

PIN_COUNT = 11
CYCLOID_LOBES = PIN_COUNT - 1
REDUCTION_RATIO = CYCLOID_LOBES
ECCENTRICITY = 0.8
LOWER_ECCENTRIC_CENTER = (ECCENTRICITY, 0.0)
UPPER_ECCENTRIC_CENTER = (-ECCENTRICITY, 0.0)
UPPER_CYCLOID_BODY_PHASE_DEGREES = 180.0 / CYCLOID_LOBES

RING_PIN_PITCH_RADIUS = 18.0
RING_PIN_RADIUS = 0.65
PROFILE_ROLLER_RADIUS = 1.6
HOUSING_INNER_RADIUS = 22.3
RETAINER_INNER_RADIUS = 13.5

BOTTOM_RETAINER_BOTTOM_Z = 1.25
RETAINER_THICKNESS = 0.75
TOP_RETAINER_BOTTOM_Z = 8.0
PIN_BOTTOM_Z = BOTTOM_RETAINER_BOTTOM_Z
PIN_TOP_Z = TOP_RETAINER_BOTTOM_Z + RETAINER_THICKNESS

INPUT_FLANGE_RADIUS = 11.8
OUTPUT_FLANGE_RADIUS = 11.8
FLANGE_THICKNESS = 1.1
INPUT_FLANGE_BOTTOM_Z = 0.0
OUTPUT_FLANGE_BOTTOM_Z = PACKAGE_HEIGHT - FLANGE_THICKNESS
MOUNT_HOLE_COUNT = 3
MOUNT_HOLE_RADIUS = 1.03
MOUNT_HOLE_ENTRY_RADIUS = 1.35
MOUNT_HOLE_ENTRY_DEPTH = 0.28
MOUNT_HOLE_PITCH_RADIUS = 8.8

ECCENTRIC_BOSS_RADIUS = 3.1
INPUT_SHAFT_RADIUS = 0.55
INPUT_CAM_DATUM_PAD_RADIUS = 0.22
INPUT_CAM_DATUM_PAD_HEIGHT = 0.06
INPUT_CAM_DATUM_PAD_OVERLAP = 0.02
CYCLOID_BORE_RADIUS = 3.45
LOWER_CYCLOID_BOTTOM_Z = 2.15
CYCLOID_DISC_HEIGHT = 2.65
CYCLOID_DISC_GAP = 0.20
CYCLOID_BEARING_RACE_HEIGHT = 0.10
LOWER_CYCLOID_TOP_Z = LOWER_CYCLOID_BOTTOM_Z + CYCLOID_DISC_HEIGHT
LOWER_CYCLOID_CONNECTOR_Z = LOWER_CYCLOID_TOP_Z + CYCLOID_BEARING_RACE_HEIGHT
UPPER_CYCLOID_BOTTOM_Z = LOWER_CYCLOID_CONNECTOR_Z + CYCLOID_DISC_GAP
UPPER_CYCLOID_TOP_Z = UPPER_CYCLOID_BOTTOM_Z + CYCLOID_DISC_HEIGHT
UPPER_CYCLOID_CONNECTOR_Z = UPPER_CYCLOID_TOP_Z + CYCLOID_BEARING_RACE_HEIGHT
CYCLOID_STACK_HEIGHT = UPPER_CYCLOID_CONNECTOR_Z - LOWER_CYCLOID_BOTTOM_Z
CYCLOID_LOBE_SAMPLE_COUNT = 33
CYCLOID_SPLINE_TOLERANCE = 0.005
CYCLOID_SPLINE_MAX_CONTROL_POINTS = 20

OUTPUT_PIN_COUNT = 3
OUTPUT_PIN_RADIUS = 1.0
OUTPUT_PIN_CLEARANCE_RADIUS = OUTPUT_PIN_RADIUS + ECCENTRICITY + 0.25
OUTPUT_PIN_PITCH_RADIUS = 6.4
OUTPUT_PIN_PHASE = 60.0
OUTPUT_PIN_BOTTOM_Z = LOWER_CYCLOID_BOTTOM_Z
OUTPUT_PIN_TOP_Z = OUTPUT_FLANGE_BOTTOM_Z + 0.20


def _polar(radius: float, angle_degrees: float) -> tuple[float, float]:
    angle = math.radians(angle_degrees)
    return radius * math.cos(angle), radius * math.sin(angle)


def _z_rotation_placement(origin: tuple[float, float, float], angle_degrees: float):
    angle = math.radians(angle_degrees)
    return scad.make_placement_rplacement(
        origin=origin,
        x_axis=(math.cos(angle), math.sin(angle), 0.0),
        y_axis=(-math.sin(angle), math.cos(angle), 0.0),
    )


def _ground_solid(label: str, solid: scad.Solid) -> None:
    faces = ql.select(solid.get_faces()).all()
    local_roles = [
        tag
        for tag in scad.list_tags(shape=solid, scope="local")
        if tag.startswith("role.")
    ]
    print(
        f"{label}: faces={len(faces)} local_roles={len(local_roles)} "
        f"volume={solid.get_volume():.1f} tags={','.join(scad.list_tags(shape=solid))}"
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


def _make_annular_cylinder(
    *,
    outer_radius: float,
    inner_radius: float,
    bottom_z: float,
    height: float,
) -> scad.Solid:
    outer = scad.make_cylinder_rsolid(
        radius=outer_radius,
        height=height,
        bottom_face_center=(0.0, 0.0, bottom_z),
        axis=(0.0, 0.0, 1.0),
    )
    inner = scad.make_cylinder_rsolid(
        radius=inner_radius,
        height=height + 2.0,
        bottom_face_center=(0.0, 0.0, bottom_z - 1.0),
        axis=(0.0, 0.0, 1.0),
    )
    return scad.cut_rsolid(outer, inner, skip_non_intersecting=False)


def _cut_three_threaded_hole_envelopes(
    solid: scad.Solid,
    *,
    bottom_z: float,
    thickness: float,
    entry_face: str,
    phase_degrees: float = 0.0,
) -> scad.Solid:
    cutters: list[scad.Solid] = []
    for index in range(MOUNT_HOLE_COUNT):
        angle = phase_degrees + 360.0 * index / MOUNT_HOLE_COUNT
        x, y = _polar(MOUNT_HOLE_PITCH_RADIUS, angle)
        cutters.append(
            scad.make_cylinder_rsolid(
                radius=MOUNT_HOLE_RADIUS,
                height=thickness + 0.4,
                bottom_face_center=(x, y, bottom_z - 0.2),
                axis=(0.0, 0.0, 1.0),
            )
        )
        if entry_face == "bottom":
            entry_bottom_z = bottom_z - 0.04
        elif entry_face == "top":
            entry_bottom_z = bottom_z + thickness - MOUNT_HOLE_ENTRY_DEPTH
        else:
            raise ValueError("entry_face must be 'bottom' or 'top'")
        cutters.append(
            scad.make_cylinder_rsolid(
                radius=MOUNT_HOLE_ENTRY_RADIUS,
                height=MOUNT_HOLE_ENTRY_DEPTH + 0.08,
                bottom_face_center=(x, y, entry_bottom_z),
                axis=(0.0, 0.0, 1.0),
            )
        )
    return scad.cut_rsolid(solid, cutters, skip_non_intersecting=False)


def _build_fixed_housing() -> scad.Solid:
    sleeve = _make_annular_cylinder(
        outer_radius=PACKAGE_RADIUS,
        inner_radius=HOUSING_INNER_RADIUS,
        bottom_z=0.0,
        height=PACKAGE_HEIGHT,
    )
    bottom_retainer = _make_annular_cylinder(
        outer_radius=PACKAGE_RADIUS,
        inner_radius=RETAINER_INNER_RADIUS,
        bottom_z=BOTTOM_RETAINER_BOTTOM_Z,
        height=RETAINER_THICKNESS,
    )
    top_retainer = _make_annular_cylinder(
        outer_radius=PACKAGE_RADIUS,
        inner_radius=RETAINER_INNER_RADIUS,
        bottom_z=TOP_RETAINER_BOTTOM_Z,
        height=RETAINER_THICKNESS,
    )
    pins: list[scad.Solid] = []
    for index in range(PIN_COUNT):
        angle = 360.0 * index / PIN_COUNT
        x, y = _polar(RING_PIN_PITCH_RADIUS, angle)
        pins.append(
            scad.make_cylinder_rsolid(
                radius=RING_PIN_RADIUS,
                height=PIN_TOP_Z - PIN_BOTTOM_Z,
                bottom_face_center=(x, y, PIN_BOTTOM_Z),
                axis=(0.0, 0.0, 1.0),
            )
        )
    housing = scad.union_rsolid(
        sleeve,
        bottom_retainer,
        top_retainer,
        pins,
        glue=False,
    )
    housing = scad.apply_tag(housing, "role.fixed_pin_housing")
    housing = scad.apply_tag(housing, "group.cycloidal_reducer")
    _ground_solid("fixed_housing", housing)
    return housing


def _build_input_disk() -> scad.Solid:
    flange = scad.make_cylinder_rsolid(
        radius=INPUT_FLANGE_RADIUS,
        height=FLANGE_THICKNESS,
        bottom_face_center=(0.0, 0.0, INPUT_FLANGE_BOTTOM_Z),
        axis=(0.0, 0.0, 1.0),
    )
    flange = _cut_three_threaded_hole_envelopes(
        flange,
        bottom_z=INPUT_FLANGE_BOTTOM_Z,
        thickness=FLANGE_THICKNESS,
        entry_face="bottom",
        phase_degrees=0.0,
    )
    cam_bottom_z = FLANGE_THICKNESS - 0.20
    input_shaft = scad.make_cylinder_rsolid(
        radius=INPUT_SHAFT_RADIUS,
        height=UPPER_CYCLOID_CONNECTOR_Z - cam_bottom_z,
        bottom_face_center=(0.0, 0.0, cam_bottom_z),
        axis=(0.0, 0.0, 1.0),
    )
    lower_pad_bottom_z = LOWER_CYCLOID_CONNECTOR_Z - INPUT_CAM_DATUM_PAD_HEIGHT
    lower_eccentric_boss = scad.make_cylinder_rsolid(
        radius=ECCENTRIC_BOSS_RADIUS,
        height=lower_pad_bottom_z + INPUT_CAM_DATUM_PAD_OVERLAP - cam_bottom_z,
        bottom_face_center=(*LOWER_ECCENTRIC_CENTER, cam_bottom_z),
        axis=(0.0, 0.0, 1.0),
    )
    lower_datum_pad = scad.make_cylinder_rsolid(
        radius=INPUT_CAM_DATUM_PAD_RADIUS,
        height=INPUT_CAM_DATUM_PAD_HEIGHT,
        bottom_face_center=(*LOWER_ECCENTRIC_CENTER, lower_pad_bottom_z),
        axis=(0.0, 0.0, 1.0),
    )
    upper_boss_bottom_z = UPPER_CYCLOID_BOTTOM_Z - 0.10
    upper_pad_bottom_z = UPPER_CYCLOID_CONNECTOR_Z - INPUT_CAM_DATUM_PAD_HEIGHT
    upper_eccentric_boss = scad.make_cylinder_rsolid(
        radius=ECCENTRIC_BOSS_RADIUS,
        height=upper_pad_bottom_z + INPUT_CAM_DATUM_PAD_OVERLAP - upper_boss_bottom_z,
        bottom_face_center=(*UPPER_ECCENTRIC_CENTER, upper_boss_bottom_z),
        axis=(0.0, 0.0, 1.0),
    )
    upper_datum_pad = scad.make_cylinder_rsolid(
        radius=INPUT_CAM_DATUM_PAD_RADIUS,
        height=INPUT_CAM_DATUM_PAD_HEIGHT,
        bottom_face_center=(*UPPER_ECCENTRIC_CENTER, upper_pad_bottom_z),
        axis=(0.0, 0.0, 1.0),
    )
    input_disk = scad.union_rsolid(
        flange,
        input_shaft,
        lower_eccentric_boss,
        lower_datum_pad,
        upper_eccentric_boss,
        upper_datum_pad,
        glue=False,
    )
    input_disk = scad.apply_tag(input_disk, "role.input_three_thread_disk")
    input_disk = scad.apply_tag(input_disk, "role.double_eccentric_camshaft")
    input_disk = scad.apply_tag(input_disk, "group.cycloidal_reducer")
    _ground_solid("input_disk", input_disk)
    return input_disk


def _build_cycloidal_disc(
    *,
    label: str,
    bottom_z: float,
    output_pin_phase: float,
    body_phase_degrees: float,
    role_tag: str,
) -> scad.Solid:
    disc = scad.std.gear.make_cycloidal_disc_rsolid(
        n_lobes=CYCLOID_LOBES,
        ring_pin_pitch_radius=RING_PIN_PITCH_RADIUS,
        roller_radius=PROFILE_ROLLER_RADIUS,
        eccentricity=ECCENTRICITY,
        gear_height=CYCLOID_DISC_HEIGHT,
        bore_radius=CYCLOID_BORE_RADIUS,
        output_pin_count=OUTPUT_PIN_COUNT,
        output_pin_pitch_radius=OUTPUT_PIN_PITCH_RADIUS,
        output_pin_clearance_radius=OUTPUT_PIN_CLEARANCE_RADIUS,
        output_pin_phase=output_pin_phase,
        sample_count_per_lobe=CYCLOID_LOBE_SAMPLE_COUNT,
        spline_tolerance=CYCLOID_SPLINE_TOLERANCE,
        max_control_points=CYCLOID_SPLINE_MAX_CONTROL_POINTS,
    )
    cycloid_meta = disc.get_metadata("std.gear.cycloidal_disc", {})
    top_z = bottom_z + CYCLOID_DISC_HEIGHT
    connector_z = top_z + CYCLOID_BEARING_RACE_HEIGHT
    disc = scad.translate_shape(disc, (0.0, 0.0, bottom_z))
    bearing_race = _make_annular_cylinder(
        outer_radius=CYCLOID_BORE_RADIUS + 0.75,
        inner_radius=CYCLOID_BORE_RADIUS,
        bottom_z=top_z - 0.02,
        height=CYCLOID_BEARING_RACE_HEIGHT + 0.02,
    )
    disc = scad.union_rsolid(disc, bearing_race, glue=False)
    if body_phase_degrees:
        disc = scad.rotate_shape(
            disc,
            body_phase_degrees,
            axis=(0.0, 0.0, 1.0),
            origin=(0.0, 0.0, 0.0),
        )
    disc = scad.apply_tag(disc, role_tag)
    disc = scad.apply_tag(disc, "role.ten_lobe_cycloidal_disc")
    disc = scad.apply_tag(disc, "group.cycloidal_reducer")
    print(
        f"{label}_profile: "
        f"pins={PIN_COUNT} lobes={CYCLOID_LOBES} "
        f"bottom_z={bottom_z:.2f} connector_z={connector_z:.2f} "
        f"body_phase={body_phase_degrees:.1f} "
        f"raw_output_pin_phase={output_pin_phase:.1f} "
        f"segments={cycloid_meta.get('segment_count', CYCLOID_LOBES)} "
        f"samples_per_lobe={CYCLOID_LOBE_SAMPLE_COUNT} "
        f"control_points={min(cycloid_meta.get('control_point_counts', [0]))}.."
        f"{max(cycloid_meta.get('control_point_counts', [0]))} "
        f"fit_error_max={max(cycloid_meta.get('max_errors', [0.0])):.5f} "
        f"radius_min={cycloid_meta.get('radius_min', 0.0):.3f} "
        f"radius_max={cycloid_meta.get('radius_max', 0.0):.3f}"
    )
    _ground_solid(label, disc)
    return disc


def _build_output_disk() -> scad.Solid:
    flange = scad.make_cylinder_rsolid(
        radius=OUTPUT_FLANGE_RADIUS,
        height=FLANGE_THICKNESS,
        bottom_face_center=(0.0, 0.0, OUTPUT_FLANGE_BOTTOM_Z),
        axis=(0.0, 0.0, 1.0),
    )
    flange = _cut_three_threaded_hole_envelopes(
        flange,
        bottom_z=OUTPUT_FLANGE_BOTTOM_Z,
        thickness=FLANGE_THICKNESS,
        entry_face="top",
        phase_degrees=0.0,
    )
    pins: list[scad.Solid] = []
    for index in range(OUTPUT_PIN_COUNT):
        angle = OUTPUT_PIN_PHASE + 360.0 * index / OUTPUT_PIN_COUNT
        x, y = _polar(OUTPUT_PIN_PITCH_RADIUS, angle)
        pins.append(
            scad.make_cylinder_rsolid(
                radius=OUTPUT_PIN_RADIUS,
                height=OUTPUT_PIN_TOP_Z - OUTPUT_PIN_BOTTOM_Z,
                bottom_face_center=(x, y, OUTPUT_PIN_BOTTOM_Z),
                axis=(0.0, 0.0, 1.0),
            )
        )
    output_disk = scad.union_rsolid(flange, pins, glue=False)
    output_disk = scad.apply_tag(output_disk, "role.output_three_thread_disk")
    output_disk = scad.apply_tag(output_disk, "group.cycloidal_reducer")
    _ground_solid("output_disk", output_disk)
    return output_disk


def build_cycloidal_reducer():
    with scad.GraphSession() as session:
        housing = _build_fixed_housing()
        input_disk = _build_input_disk()
        lower_cycloidal_disc = _build_cycloidal_disc(
            label="lower_cycloidal_disc",
            bottom_z=LOWER_CYCLOID_BOTTOM_Z,
            output_pin_phase=OUTPUT_PIN_PHASE,
            body_phase_degrees=0.0,
            role_tag="role.lower_cycloidal_disc",
        )
        upper_cycloidal_disc = _build_cycloidal_disc(
            label="upper_cycloidal_disc",
            bottom_z=UPPER_CYCLOID_BOTTOM_Z,
            output_pin_phase=OUTPUT_PIN_PHASE - UPPER_CYCLOID_BODY_PHASE_DEGREES,
            body_phase_degrees=UPPER_CYCLOID_BODY_PHASE_DEGREES,
            role_tag="role.upper_cycloidal_disc",
        )
        output_disk = _build_output_disk()

        housing_material = scad.make_material_rmaterial(
            material_id="black_anodized_aluminum",
            name="Black anodized aluminum",
            density=2.7e-6,
            density_unit="kg/mm^3",
            color=(0.08, 0.08, 0.09),
        )
        steel_material = scad.make_material_rmaterial(
            material_id="bearing_steel",
            name="Bearing steel",
            density=7.85e-6,
            density_unit="kg/mm^3",
            color=(0.62, 0.64, 0.66),
        )
        bronze_material = scad.make_material_rmaterial(
            material_id="phosphor_bronze",
            name="Phosphor bronze",
            density=8.8e-6,
            density_unit="kg/mm^3",
            color=(0.72, 0.48, 0.20),
        )
        print(
            "materials: "
            f"{housing_material.material_id},{steel_material.material_id},{bronze_material.material_id}"
        )

        housing_part = scad.make_part_rpart(
            part_id="fixed_pin_housing",
            body=housing,
            name="Fixed housing with eleven pin ring",
        )
        housing_part = scad.assign_material_rpart(housing_part, housing_material)
        housing_part = scad.add_connector_rpart(
            housing_part,
            scad.make_face_connector_rconnector(
                "input_axis",
                _axis_face(
                    "housing_input_axis",
                    housing,
                    (0.0, 0.0),
                    INPUT_FLANGE_BOTTOM_Z,
                    -1.0,
                ),
                flip=True,
            ),
        )
        housing_part = scad.add_connector_rpart(
            housing_part,
            scad.make_face_connector_rconnector(
                "output_axis",
                _axis_face(
                    "housing_output_axis",
                    housing,
                    (0.0, 0.0),
                    PACKAGE_HEIGHT,
                    1.0,
                ),
            ),
        )

        input_part = scad.make_part_rpart(
            part_id="input_three_thread_disk",
            body=input_disk,
            name="Input three threaded-hole disk with double eccentric camshaft",
        )
        input_part = scad.assign_material_rpart(input_part, steel_material)
        input_part = scad.add_connector_rpart(
            input_part,
            scad.make_face_connector_rconnector(
                "axis",
                _axis_face(
                    "input_axis",
                    input_disk,
                    (0.0, 0.0),
                    INPUT_FLANGE_BOTTOM_Z,
                    -1.0,
                ),
                flip=True,
            ),
        )
        input_part = scad.add_connector_rpart(
            input_part,
            scad.make_face_connector_rconnector(
                "lower_eccentric_axis",
                _axis_face(
                    "input_lower_eccentric_axis",
                    input_disk,
                    LOWER_ECCENTRIC_CENTER,
                    LOWER_CYCLOID_CONNECTOR_Z,
                    1.0,
                ),
            ),
        )
        input_part = scad.add_connector_rpart(
            input_part,
            scad.make_face_connector_rconnector(
                "upper_eccentric_axis",
                _axis_face(
                    "input_upper_eccentric_axis",
                    input_disk,
                    UPPER_ECCENTRIC_CENTER,
                    UPPER_CYCLOID_CONNECTOR_Z,
                    1.0,
                ),
            ),
        )

        lower_cycloid_part = scad.make_part_rpart(
            part_id="lower_ten_lobe_cycloidal_disc",
            body=lower_cycloidal_disc,
            name="Lower ten-lobe cycloidal disc",
        )
        lower_cycloid_part = scad.assign_material_rpart(
            lower_cycloid_part, bronze_material
        )
        lower_cycloid_part = scad.add_connector_rpart(
            lower_cycloid_part,
            scad.make_face_connector_rconnector(
                "eccentric_axis",
                _axis_face(
                    "lower_cycloid_eccentric_axis",
                    lower_cycloidal_disc,
                    (0.0, 0.0),
                    LOWER_CYCLOID_CONNECTOR_Z,
                    1.0,
                ),
            ),
        )

        upper_cycloid_part = scad.make_part_rpart(
            part_id="upper_ten_lobe_cycloidal_disc",
            body=upper_cycloidal_disc,
            name="Upper ten-lobe cycloidal disc, 180 degree phased",
        )
        upper_cycloid_part = scad.assign_material_rpart(
            upper_cycloid_part, bronze_material
        )
        upper_cycloid_part = scad.add_connector_rpart(
            upper_cycloid_part,
            scad.make_face_connector_rconnector(
                "eccentric_axis",
                _axis_face(
                    "upper_cycloid_eccentric_axis",
                    upper_cycloidal_disc,
                    (0.0, 0.0),
                    UPPER_CYCLOID_CONNECTOR_Z,
                    1.0,
                ),
            ),
        )

        output_part = scad.make_part_rpart(
            part_id="output_three_thread_disk",
            body=output_disk,
            name="Output three threaded-hole disk with drive pins",
        )
        output_part = scad.assign_material_rpart(output_part, steel_material)
        output_part = scad.add_connector_rpart(
            output_part,
            scad.make_face_connector_rconnector(
                "axis",
                _axis_face(
                    "output_axis",
                    output_disk,
                    (0.0, 0.0),
                    PACKAGE_HEIGHT,
                    1.0,
                ),
            ),
        )

        reducer = scad.make_assembly_rassembly(
            assembly_id="cycloidal_reducer_50mm_10x",
            name="50 mm diameter 10:1 cycloidal reducer",
        )
        reducer = scad.add_component_rassembly(
            assembly=reducer,
            item=housing_part,
            component_id="fixed_housing",
            placement=_z_rotation_placement((0.0, 0.0, 0.0), 0.0),
            name="Grounded fixed pin-ring housing",
        )
        reducer = scad.add_component_rassembly(
            assembly=reducer,
            item=input_part,
            component_id="input_disk",
            placement=_z_rotation_placement((0.0, 0.0, 0.0), 0.0),
            name="Input three-thread-hole disk",
        )
        reducer = scad.add_component_rassembly(
            assembly=reducer,
            item=lower_cycloid_part,
            component_id="lower_cycloidal_disc",
            placement=_z_rotation_placement((ECCENTRICITY, 0.0, 0.0), 0.0),
            name="Lower cycloidal disc riding on 0 degree eccentric cam",
        )
        reducer = scad.add_component_rassembly(
            assembly=reducer,
            item=upper_cycloid_part,
            component_id="upper_cycloidal_disc",
            placement=_z_rotation_placement((-ECCENTRICITY, 0.0, 0.0), 0.0),
            name="Upper cycloidal disc riding on 180 degree eccentric cam",
        )
        reducer = scad.add_component_rassembly(
            assembly=reducer,
            item=output_part,
            component_id="output_disk",
            placement=_z_rotation_placement((0.0, 0.0, 0.0), 0.0),
            name="Output three-thread-hole disk",
        )

        reducer = scad.ground_component_rassembly(reducer, "fixed_housing")
        reducer = scad.add_revolute_constraint_rassembly(
            assembly=reducer,
            constraint_id="input_revolute",
            connector_a=scad.make_connector_ref_rconnectorref(
                component_id="fixed_housing", connector_id="input_axis"
            ),
            connector_b=scad.make_connector_ref_rconnectorref(
                component_id="input_disk", connector_id="axis"
            ),
            name="Input disk rotates in the fixed housing",
        )
        reducer = scad.add_revolute_constraint_rassembly(
            assembly=reducer,
            constraint_id="output_revolute",
            connector_a=scad.make_connector_ref_rconnectorref(
                component_id="fixed_housing", connector_id="output_axis"
            ),
            connector_b=scad.make_connector_ref_rconnectorref(
                component_id="output_disk", connector_id="axis"
            ),
            name="Output disk rotates coaxially in the fixed housing",
        )
        reducer = scad.add_revolute_constraint_rassembly(
            assembly=reducer,
            constraint_id="lower_cycloid_on_eccentric_cam",
            connector_a=scad.make_connector_ref_rconnectorref(
                component_id="input_disk", connector_id="lower_eccentric_axis"
            ),
            connector_b=scad.make_connector_ref_rconnectorref(
                component_id="lower_cycloidal_disc", connector_id="eccentric_axis"
            ),
            name="Lower cycloidal disc rotates on the 0 degree input eccentric cam",
        )
        reducer = scad.add_revolute_constraint_rassembly(
            assembly=reducer,
            constraint_id="upper_cycloid_on_eccentric_cam",
            connector_a=scad.make_connector_ref_rconnectorref(
                component_id="input_disk", connector_id="upper_eccentric_axis"
            ),
            connector_b=scad.make_connector_ref_rconnectorref(
                component_id="upper_cycloidal_disc", connector_id="eccentric_axis"
            ),
            name="Upper cycloidal disc rotates on the 180 degree input eccentric cam",
        )
        reducer = scad.add_gear_constraint_rassembly(
            assembly=reducer,
            constraint_id="fixed_pin_ring_to_lower_cycloid_spin",
            connector_a=scad.make_connector_ref_rconnectorref(
                component_id="input_disk", connector_id="axis"
            ),
            connector_b=scad.make_connector_ref_rconnectorref(
                component_id="lower_cycloidal_disc", connector_id="eccentric_axis"
            ),
            pitch_radius_a=float(PIN_COUNT),
            pitch_radius_b=float(CYCLOID_LOBES),
            name="Fixed pin ring drives the lower cycloidal disc relative spin",
        )
        reducer = scad.add_gear_constraint_rassembly(
            assembly=reducer,
            constraint_id="fixed_pin_ring_to_upper_cycloid_spin",
            connector_a=scad.make_connector_ref_rconnectorref(
                component_id="input_disk", connector_id="axis"
            ),
            connector_b=scad.make_connector_ref_rconnectorref(
                component_id="upper_cycloidal_disc", connector_id="eccentric_axis"
            ),
            pitch_radius_a=float(PIN_COUNT),
            pitch_radius_b=float(CYCLOID_LOBES),
            name="Fixed pin ring drives the upper cycloidal disc relative spin",
        )
        print(
            "assembly_plan: "
            f"diameter={PACKAGE_DIAMETER:.1f} height={PACKAGE_HEIGHT:.1f} "
            f"pins={PIN_COUNT} lobes={CYCLOID_LOBES} reduction={REDUCTION_RATIO}:1 "
            f"eccentricity={ECCENTRICITY:.2f} cycloid_discs=2 "
            f"eccentric_phase_degrees=0,180 "
            f"tooth_index_phase_degrees=0,{UPPER_CYCLOID_BODY_PHASE_DEGREES:.1f} "
            f"stack_height={CYCLOID_STACK_HEIGHT:.2f}"
        )
        print(
            "load_balance: "
            "lower_eccentric=(+e,0) upper_eccentric=(-e,0) "
            "output_pins_pass_through_both_discs contact_not_solved"
        )
        print(
            "kinematic_relation: "
            f"each_cycloid_relative=-{PIN_COUNT}/{CYCLOID_LOBES}*input "
            f"each_cycloid_global=output=-1/{REDUCTION_RATIO}*input via output pin holes"
        )

        reducer = scad.solve_assembly_constraints_rassembly(reducer)
        report = scad.inspect_assembly_constraints_rconstraintreport(reducer)
        print(
            "assembly: "
            f"components={','.join(reducer.component_ids())} "
            f"grounded={','.join(reducer.grounded_component_ids)} "
            f"solved={report.solved} constraints={len(reducer.constraints)}"
        )
        for residual in report.residuals:
            print(
                f"constraint_{residual.constraint_id}: "
                f"translation={residual.translation_error:.6g} "
                f"angle={residual.angular_error_degrees:.6g} "
                f"ok={residual.within_tolerance}"
            )

        preview = scad.make_compound_from_assembly_rcompound(reducer)
        _ground_compound("assembly_preview", preview)
        model_json = scad.export_model_json(session)

    return reducer, preview, model_json


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    model_path = OUTPUT_DIR / "cycloidal_reducer_50mm_10x.model.json"
    step_path = OUTPUT_DIR / "cycloidal_reducer_50mm_10x.step"
    fcstd_path = OUTPUT_DIR / "cycloidal_reducer_50mm_10x.FCStd"
    if fcstd_path.exists():
        fcstd_path.unlink()

    assembly, preview, model_json = build_cycloidal_reducer()
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
        "package: "
        f"diameter={PACKAGE_DIAMETER:.1f} height={PACKAGE_HEIGHT:.1f} "
        f"outer_radius={PACKAGE_RADIUS:.1f}"
    )
    print(
        "mounting: "
        f"input=3xM2.5_envelope output=3xM2.5_envelope "
        f"hole_pcd={2.0 * MOUNT_HOLE_PITCH_RADIUS:.1f}"
    )
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
