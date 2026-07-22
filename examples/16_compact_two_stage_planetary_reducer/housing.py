"""Reducer housing sleeve and fixed-axis connector datums."""

from __future__ import annotations

import math

import simplecadapi as scad

from common import (
    _apply_tags,
    add_placement_axis_connector_rpart,
    make_annular_cylinder_rsolid,
)
from dimensions import (
    HOUSING_BODY_OUTER_RADIUS,
    HOUSING_DATUM_INNER_RADIUS,
    HOUSING_DATUM_OUTER_RADIUS,
    HOUSING_END_FLANGE_OUTER_RADIUS,
    HOUSING_FRONT_FLANGE_THICKNESS,
    HOUSING_HEIGHT,
    HOUSING_INNER_RADIUS,
    HOUSING_MOUNT_COUNTERBORE_DEPTH,
    HOUSING_MOUNT_COUNTERBORE_DIAMETER,
    HOUSING_MOUNT_HOLE_CIRCLE_RADIUS,
    HOUSING_MOUNT_HOLE_COUNT,
    HOUSING_MOUNT_HOLE_DIAMETER,
    HOUSING_MOUNT_HOLE_OFFSET_DEGREES,
    HOUSING_MOUNT_HOLES_PER_SECTOR,
    HOUSING_MOUNT_PAD_INNER_RADIUS,
    HOUSING_MOUNT_PAD_OUTER_RADIUS,
    HOUSING_MOUNT_SECTOR_CENTER_OFFSET_DEGREES,
    HOUSING_MOUNT_SECTOR_COUNT,
    HOUSING_MOUNT_SECTOR_GAP_WIDTH,
    HOUSING_OUTER_RADIUS,
    HOUSING_BOTTOM_Z,
    HOUSING_REAR_FLANGE_THICKNESS,
    INPUT_BEARING_Z,
    INPUT_FLANGE_TOP_Z,
    INPUT_SEAL_BORE_RADIUS,
    INPUT_SEAL_RUNNING_CLEARANCE,
    INTERMEDIATE_BEARING_Z,
    OUTPUT_BEARING_Z,
    OUTPUT_FLANGE_TOP_Z,
    OUTPUT_SEAL_BORE_RADIUS,
    OUTPUT_SEAL_RUNNING_CLEARANCE,
    STAGE_1,
    STAGE_2,
)


@scad.requires_session
def make_reducer_housing_rpart(*, material: scad.Material) -> scad.Part:
    """Create the through-bolted housing sleeve with internal datum collars."""

    sleeve = make_annular_cylinder_rsolid(
        outer_radius=HOUSING_BODY_OUTER_RADIUS,
        inner_radius=HOUSING_INNER_RADIUS,
        height=HOUSING_HEIGHT,
        bottom_z=HOUSING_BOTTOM_Z,
        tag_prefix="reducer.housing.sleeve",
        tag="role.housing_sleeve",
    )
    front_flange = _make_end_flange_rsolid(
        label="front",
        inner_radius=OUTPUT_SEAL_BORE_RADIUS,
        thickness=HOUSING_FRONT_FLANGE_THICKNESS,
        bottom_z=HOUSING_BOTTOM_Z + HOUSING_HEIGHT - HOUSING_FRONT_FLANGE_THICKNESS,
        tag_prefix="reducer.housing.front.end.cap",
    )
    rear_flange = _make_end_flange_rsolid(
        label="rear",
        inner_radius=INPUT_SEAL_BORE_RADIUS,
        thickness=HOUSING_REAR_FLANGE_THICKNESS,
        bottom_z=HOUSING_BOTTOM_Z,
        tag_prefix="reducer.housing.rear.end.cap",
    )
    mount_pad = _make_mount_sector_pad_rsolid(tag_prefix="reducer.housing.mount.sector.pad")
    collars = []
    datum_zs = (
        INPUT_FLANGE_TOP_Z,
        STAGE_1.top_z,
        STAGE_2.top_z,
        OUTPUT_FLANGE_TOP_Z,
    )
    for index, target_z in enumerate(datum_zs):
        # The end caps themselves provide the input/output seal lands.  Avoid
        # adding fully contained datum collars at those end faces; they carry no
        # new mechanical information and make downstream translators less robust.
        if target_z <= HOUSING_BOTTOM_Z + HOUSING_REAR_FLANGE_THICKNESS:
            continue
        if target_z >= HOUSING_BOTTOM_Z + HOUSING_HEIGHT - HOUSING_FRONT_FLANGE_THICKNESS:
            continue
        collar = make_annular_cylinder_rsolid(
            outer_radius=HOUSING_DATUM_OUTER_RADIUS,
            inner_radius=HOUSING_DATUM_INNER_RADIUS,
            height=0.36,
            bottom_z=target_z - 0.36,
            tag_prefix=f"reducer.housing.datum.collar.i{index + 1}",
            tag=f"role.housing_axis_datum_{index + 1}",
        )
        collars.append(collar)

    # The housing now has real through-bolt sector pads.  The full-height pad is
    # cut after union, so each screw path clears both the visible pad and the
    # underlying housing body instead of stopping at a cosmetic front pocket.
    housing = scad.union_rsolid([sleeve, front_flange, rear_flange, mount_pad, collars], glue=False)
    housing = scad.cut_rsolid(
        housing,
        [
            _make_mount_gap_cutters_rsolids(tag_prefix="reducer.housing.mount.gap"),
            _make_mount_hole_cutters_rsolids(tag_prefix="reducer.housing.mount.hole"),
        ],
        skip_non_intersecting=False,
    )
    housing = _apply_tags(
        housing,
        tags=("role.fixed_housing", "role.case_to_link_interface", "group.two_stage_reducer"),
    )
    print(
        f"housing_through_bolts: sectors={HOUSING_MOUNT_SECTOR_COUNT} holes={HOUSING_MOUNT_HOLE_COUNT} "
        f"hole_d={HOUSING_MOUNT_HOLE_DIAMETER:.1f} counterbore_d={HOUSING_MOUNT_COUNTERBORE_DIAMETER:.1f}"
    )
    print(
        f"housing_envelope: diameter={HOUSING_OUTER_RADIUS * 2.0:.1f} "
        f"height={HOUSING_HEIGHT:.1f} datum_count={len(datum_zs)} faces={len(housing.get_faces())}"
    )
    part = scad.make_part_rpart(
        part_id="reducer_housing",
        body=housing,
        name="Compact fixed reducer housing sleeve",
    )
    part = scad.assign_material_rpart(part=part, material=material)
    # The scalloped sector pads deliberately make the output face non-simple.
    # Housing axes are design datums, not manufactured face picks, so keep these
    # connectors topology-free for stable replay and FreeCAD translation.
    for connector_id, z in (
        ("input_axis", STAGE_1.top_z),
        ("stage1_axis", STAGE_1.top_z),
        ("stage2_axis", STAGE_2.top_z),
        ("output_axis", OUTPUT_FLANGE_TOP_Z),
    ):
        part = add_placement_axis_connector_rpart(
            part=part,
            connector_id=connector_id,
            origin=(0.0, 0.0, z),
            name=connector_id.replace("_", " "),
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
    print(f"part_reducer_housing: connectors={len(part.connectors)} material=True")
    return part


@scad.requires_session
def _make_end_flange_rsolid(
    *,
    label: str,
    inner_radius: float,
    thickness: float,
    bottom_z: float,
    tag_prefix: str,
) -> scad.Solid:
    """Build one sealed housing end cap.

    The end cap is only the annular plate around the rotating input/output
    flange.  Housing screws live in the through-bolt columns, not in small
    half-depth pockets on this cap.
    """

    flange = make_annular_cylinder_rsolid(
        outer_radius=HOUSING_END_FLANGE_OUTER_RADIUS,
        inner_radius=inner_radius,
        height=thickness,
        bottom_z=bottom_z,
        tag_prefix=tag_prefix,
        tag=f"role.housing_{label}_sealed_end_cap",
    )
    clearance = OUTPUT_SEAL_RUNNING_CLEARANCE if label == "front" else INPUT_SEAL_RUNNING_CLEARANCE
    print(
        f"{label}_seal_land: bore_radius={inner_radius:.2f} clearance={clearance:.2f}"
    )
    return flange


@scad.requires_session
def _make_mount_sector_pad_rsolid(*, tag_prefix: str) -> scad.Solid:
    """Build four graceful full-height sector pads before the global hole cut."""

    outer = scad.make_cylinder_rsolid(
        radius=HOUSING_MOUNT_PAD_OUTER_RADIUS,
        height=HOUSING_HEIGHT,
        bottom_face_center=(0.0, 0.0, HOUSING_BOTTOM_Z),
        axis=(0.0, 0.0, 1.0),
        tag_prefix=f"{tag_prefix}.outer",
        result_tag=f"solid.{tag_prefix}.outer",
    )
    inner = scad.make_cylinder_rsolid(
        radius=HOUSING_MOUNT_PAD_INNER_RADIUS,
        height=HOUSING_HEIGHT + 2.0,
        bottom_face_center=(0.0, 0.0, HOUSING_BOTTOM_Z - 1.0),
        axis=(0.0, 0.0, 1.0),
        tag_prefix=f"{tag_prefix}.inner",
        result_tag=f"solid.{tag_prefix}.inner.cutter",
    )
    pad = scad.cut_rsolid(outer, inner, skip_non_intersecting=False)
    pad = _apply_tags(
        pad,
        tags=("role.housing_sector_mount_pads", "role.case_to_link_interface"),
    )
    print(
        f"housing_sector_pads: sectors={HOUSING_MOUNT_SECTOR_COUNT} "
        f"holes_per_sector={HOUSING_MOUNT_HOLES_PER_SECTOR} "
        f"outer_diameter={HOUSING_MOUNT_PAD_OUTER_RADIUS * 2.0:.1f}"
    )
    return pad


@scad.requires_session
def _make_mount_gap_cutters_rsolids(*, tag_prefix: str) -> list[scad.Solid]:
    """Build shallow radial gap cutters that divide the outer band into sectors."""

    cutters = []
    gap_inner_radius = HOUSING_BODY_OUTER_RADIUS + 0.15
    gap_center_radius = (gap_inner_radius + HOUSING_MOUNT_PAD_OUTER_RADIUS + 0.8) / 2.0
    gap_radial_depth = HOUSING_MOUNT_PAD_OUTER_RADIUS - gap_inner_radius + 1.0
    for index in range(HOUSING_MOUNT_SECTOR_COUNT):
        gap_angle = (
            HOUSING_MOUNT_SECTOR_CENTER_OFFSET_DEGREES
            + 45.0
            + 360.0 * index / HOUSING_MOUNT_SECTOR_COUNT
        )
        gap = scad.make_box_rsolid(
            width=gap_radial_depth,
            height=HOUSING_MOUNT_SECTOR_GAP_WIDTH,
            depth=HOUSING_HEIGHT + 2.0,
            bottom_face_center=(gap_center_radius, 0.0, HOUSING_BOTTOM_Z - 1.0),
            tag_prefix=f"{tag_prefix}.i{index + 1}",
            result_tag=f"solid.{tag_prefix}.i{index + 1}.cutter",
        )
        cutters.append(
            scad.rotate_shape(
                shape=gap,
                angle=gap_angle,
                axis=(0.0, 0.0, 1.0),
                origin=(0.0, 0.0, 0.0),
            )
        )

    # These cuts shape only the outer mounting band.  The inner housing shell is
    # intentionally left continuous, so the final part remains one case instead
    # of four separate ears connected only by fasteners.
    return cutters


@scad.requires_session
def _make_mount_hole_cutters_rsolids(*, tag_prefix: str) -> list[scad.Solid]:
    """Build one shared cutter set for the boss and housing body holes."""

    cutters = []
    for sector_index in range(HOUSING_MOUNT_SECTOR_COUNT):
        sector_angle_degrees = (
            HOUSING_MOUNT_SECTOR_CENTER_OFFSET_DEGREES
            + 360.0 * sector_index / HOUSING_MOUNT_SECTOR_COUNT
        )
        offsets = (
            -HOUSING_MOUNT_HOLE_OFFSET_DEGREES,
            0.0,
            HOUSING_MOUNT_HOLE_OFFSET_DEGREES,
        )
        for hole_index in range(HOUSING_MOUNT_HOLES_PER_SECTOR):
            angle_degrees = sector_angle_degrees + offsets[hole_index]
            angle = math.radians(angle_degrees)
            cutters.extend(
                _make_single_mount_hole_cutters_rsolids(
                    angle=angle,
                    tag_prefix=(
                        f"{tag_prefix}.sector.i{sector_index + 1}.i{hole_index + 1}"
                    ),
                )
            )
    return cutters


@scad.requires_session
def _make_single_mount_hole_cutters_rsolids(
    *,
    angle: float,
    tag_prefix: str,
) -> list[scad.Solid]:
    """Build through and counterbore cutters for one housing screw."""

    x = HOUSING_MOUNT_HOLE_CIRCLE_RADIUS * math.cos(angle)
    y = HOUSING_MOUNT_HOLE_CIRCLE_RADIUS * math.sin(angle)
    cutters = []

    # The through cutter spans the entire housing.  If this stops short, the
    # front view still looks like a screw hole, but a real screw would hit the
    # rear half of the case exactly as the review screenshot showed.
    cutters.append(
        scad.make_cylinder_rsolid(
            radius=HOUSING_MOUNT_HOLE_DIAMETER / 2.0,
            height=HOUSING_HEIGHT + 2.0,
            bottom_face_center=(x, y, HOUSING_BOTTOM_Z - 1.0),
            axis=(0.0, 0.0, 1.0),
            tag_prefix=f"{tag_prefix}.through",
            result_tag=f"solid.{tag_prefix}.through.cutter",
        )
    )
    # Counterbores are added on both ends so the actuator can be mounted from
    # either side during integration or service.  This also gives enough head
    # diameter to visually read as an M3-class fastener interface.
    cutters.append(
        scad.make_cylinder_rsolid(
            radius=HOUSING_MOUNT_COUNTERBORE_DIAMETER / 2.0,
            height=HOUSING_MOUNT_COUNTERBORE_DEPTH + 0.4,
            bottom_face_center=(
                x,
                y,
                HOUSING_BOTTOM_Z + HOUSING_HEIGHT - HOUSING_MOUNT_COUNTERBORE_DEPTH,
            ),
            axis=(0.0, 0.0, 1.0),
            tag_prefix=f"{tag_prefix}.front.counterbore",
            result_tag=f"solid.{tag_prefix}.front.counterbore.cutter",
        )
    )
    cutters.append(
        scad.make_cylinder_rsolid(
            radius=HOUSING_MOUNT_COUNTERBORE_DIAMETER / 2.0,
            height=HOUSING_MOUNT_COUNTERBORE_DEPTH + 0.4,
            bottom_face_center=(x, y, HOUSING_BOTTOM_Z - 0.2),
            axis=(0.0, 0.0, 1.0),
            tag_prefix=f"{tag_prefix}.rear.counterbore",
            result_tag=f"solid.{tag_prefix}.rear.counterbore.cutter",
        )
    )
    return cutters
