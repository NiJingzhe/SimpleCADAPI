"""Gear and carrier parts for the four-planet planetary reducer."""

from __future__ import annotations

import simplecadapi as scad

from common import ground_solid, make_axis_part_rpart, make_z_rotation_rplacement
from dimensions import (
    ADDENDUM_FACTOR,
    BACKLASH,
    CARRIER_ARM_WIDTH,
    CARRIER_BOTTOM_Z,
    CARRIER_HUB_RADIUS,
    CARRIER_PIN_BOSS_RADIUS,
    CARRIER_PIN_HEIGHT,
    CARRIER_THICKNESS,
    CLEARANCE_FACTOR,
    GEAR_AXIS_Z,
    GEAR_HEIGHT,
    MODULE,
    PLANET_CENTER_RADIUS,
    PLANET_COUNT,
    PLANET_PIN_CLEARANCE_RADIUS,
    PLANET_PIN_RADIUS,
    PLANET_TEETH,
    PRESSURE_ANGLE,
    RING_RIM_THICKNESS,
    RING_TEETH,
    SUN_BORE_RADIUS,
    SUN_TEETH,
    planet_angle_degrees,
    planet_center_xy,
)


def make_sun_gear_rpart(*, material: scad.Material) -> scad.Part:
    """Create the input sun gear with a service bore and axis connector."""

    sun = scad.std.gear.make_spur_gear_rsolid(
        n_teeth=SUN_TEETH,
        module=MODULE,
        pressure_angle=PRESSURE_ANGLE,
        gear_height=GEAR_HEIGHT,
        addendum_factor=ADDENDUM_FACTOR,
        clearance_factor=CLEARANCE_FACTOR,
        backlash=BACKLASH,
    )
    bore = scad.make_cylinder_rsolid(
        radius=SUN_BORE_RADIUS,
        height=GEAR_HEIGHT + 2.0,
        bottom_face_center=(0.0, 0.0, -1.0),
        axis=(0.0, 0.0, 1.0),
    )
    sun = scad.cut_rsolid(sun, bore, skip_non_intersecting=False)
    sun = scad.apply_tag(shape=sun, tag="role.sun_input_gear")
    ground_solid(label="sun_gear", solid=sun)
    return make_axis_part_rpart(
        part_id="sun_input_gear",
        body=sun,
        name="Input sun gear, 24 teeth",
        material=material,
        connector_specs=(("axis", (0.0, 0.0, GEAR_AXIS_Z), "Sun input axis"),),
    )


def make_ring_gear_rpart(*, material: scad.Material) -> scad.Part:
    """Create the fixed internal ring gear without an enclosing housing."""

    ring = scad.std.gear.make_spur_ring_gear_rsolid(
        n_teeth=RING_TEETH,
        module=MODULE,
        pressure_angle=PRESSURE_ANGLE,
        gear_height=GEAR_HEIGHT,
        rim_thickness=RING_RIM_THICKNESS,
        backlash=BACKLASH,
        addendum_factor=ADDENDUM_FACTOR,
        clearance_factor=CLEARANCE_FACTOR,
    )
    ring = scad.apply_tag(shape=ring, tag="role.fixed_internal_ring_gear")
    ground_solid(label="ring_gear", solid=ring)
    return make_axis_part_rpart(
        part_id="fixed_ring_gear",
        body=ring,
        name="Fixed internal ring gear, 60 teeth",
        material=material,
        connector_specs=(("axis", (0.0, 0.0, GEAR_AXIS_Z), "Fixed ring axis"),),
    )


def make_planet_gear_rpart(*, material: scad.Material) -> scad.Part:
    """Create one reusable planet gear with a carrier-pin bore."""

    planet = scad.std.gear.make_spur_gear_rsolid(
        n_teeth=PLANET_TEETH,
        module=MODULE,
        pressure_angle=PRESSURE_ANGLE,
        gear_height=GEAR_HEIGHT,
        addendum_factor=ADDENDUM_FACTOR,
        clearance_factor=CLEARANCE_FACTOR,
        backlash=BACKLASH,
    )
    bore = scad.make_cylinder_rsolid(
        radius=PLANET_PIN_CLEARANCE_RADIUS,
        height=GEAR_HEIGHT + 2.0,
        bottom_face_center=(0.0, 0.0, -1.0),
        axis=(0.0, 0.0, 1.0),
    )
    planet = scad.cut_rsolid(planet, bore, skip_non_intersecting=False)
    planet = scad.apply_tag(shape=planet, tag="role.reusable_planet_gear")
    ground_solid(label="planet_gear", solid=planet)
    return make_axis_part_rpart(
        part_id="planet_gear",
        body=planet,
        name="Reusable planet gear, 18 teeth",
        material=material,
        connector_specs=(("axis", (0.0, 0.0, GEAR_AXIS_Z), "Planet spin axis"),),
    )


def make_carrier_rpart(*, material: scad.Material) -> scad.Part:
    """Create the four-pin carrier output spider."""

    hub = scad.make_cylinder_rsolid(
        radius=CARRIER_HUB_RADIUS,
        height=CARRIER_THICKNESS,
        bottom_face_center=(0.0, 0.0, CARRIER_BOTTOM_Z),
        axis=(0.0, 0.0, 1.0),
    )
    arms: list[scad.Solid] = []
    pin_bosses: list[scad.Solid] = []
    pins: list[scad.Solid] = []
    for index in range(PLANET_COUNT):
        angle = planet_angle_degrees(index=index)
        x, y = planet_center_xy(index=index)
        arm = scad.make_box_rsolid(
            width=PLANET_CENTER_RADIUS + CARRIER_PIN_BOSS_RADIUS,
            height=CARRIER_ARM_WIDTH,
            depth=CARRIER_THICKNESS,
            bottom_face_center=(PLANET_CENTER_RADIUS / 2.0, 0.0, CARRIER_BOTTOM_Z),
        )
        arms.append(
            scad.rotate_shape(
                shape=arm,
                angle=angle,
                axis=(0.0, 0.0, 1.0),
                origin=(0.0, 0.0, 0.0),
            )
        )
        pin_bosses.append(
            scad.make_cylinder_rsolid(
                radius=CARRIER_PIN_BOSS_RADIUS,
                height=CARRIER_THICKNESS,
                bottom_face_center=(x, y, CARRIER_BOTTOM_Z),
                axis=(0.0, 0.0, 1.0),
            )
        )
        pins.append(
            scad.make_cylinder_rsolid(
                radius=PLANET_PIN_RADIUS,
                height=CARRIER_PIN_HEIGHT,
                bottom_face_center=(x, y, CARRIER_BOTTOM_Z),
                axis=(0.0, 0.0, 1.0),
            )
        )
    carrier = scad.union_rsolid([hub, arms, pin_bosses, pins], glue=False)
    center_bore = scad.make_cylinder_rsolid(
        radius=SUN_BORE_RADIUS + 0.8,
        height=CARRIER_THICKNESS + 2.0,
        bottom_face_center=(0.0, 0.0, CARRIER_BOTTOM_Z - 1.0),
        axis=(0.0, 0.0, 1.0),
    )
    carrier = scad.cut_rsolid(carrier, center_bore, skip_non_intersecting=False)
    carrier = scad.apply_tag(shape=carrier, tag="role.four_pin_output_carrier")
    ground_solid(label="carrier", solid=carrier)
    connector_specs = [
        ("axis", (0.0, 0.0, GEAR_AXIS_Z), "Carrier output axis"),
        ("output_axis", (0.0, 0.0, GEAR_AXIS_Z), "Public output axis"),
    ]
    connector_specs.extend(
        (
            f"planet_{index + 1}_axis",
            (*planet_center_xy(index=index), GEAR_AXIS_Z),
            f"Planet {index + 1} carrier pin axis",
        )
        for index in range(PLANET_COUNT)
    )
    return make_axis_part_rpart(
        part_id="four_pin_output_carrier",
        body=carrier,
        name="Four-pin output carrier spider",
        material=material,
        connector_specs=tuple(connector_specs),
    )


def make_planet_component_rplacement(*, index: int) -> scad.Placement:
    """Return the placement for one of the four equally spaced planets."""

    angle = planet_angle_degrees(index=index)
    x, y = planet_center_xy(index=index)
    tooth_phase = angle + 180.0 - (180.0 / PLANET_TEETH)
    print(
        f"planet_{index + 1}: center=({x:.3f},{y:.3f},0.000) "
        f"carrier_angle={angle:.1f} spin_phase={tooth_phase:.1f}"
    )
    return make_z_rotation_rplacement(origin=(x, y, 0.0), angle_degrees=tooth_phase)
