"""Assembly and kinematic constraints for a four-planet planetary reducer."""

from __future__ import annotations

import simplecadapi as scad

from dimensions import (
    FIXED_RING_REDUCTION,
    PLANET_COUNT,
    PLANET_PITCH_RADIUS,
    RING_PITCH_RADIUS,
    SUN_PITCH_RADIUS,
)
from materials import make_materials_rdict
from parts import (
    make_carrier_rpart,
    make_planet_component_rplacement,
    make_planet_gear_rpart,
    make_ring_gear_rpart,
    make_sun_gear_rpart,
)


def make_four_planet_planetary_reducer_rassembly() -> scad.Assembly:
    """Build and solve the exposed four-planet fixed-ring reducer gearset."""

    print(
        f"ratio_plan: fixed_ring={FIXED_RING_REDUCTION:.3f}:1 "
        f"planets={PLANET_COUNT} sun_r={SUN_PITCH_RADIUS:.3f} "
        f"planet_r={PLANET_PITCH_RADIUS:.3f} ring_r={RING_PITCH_RADIUS:.3f}"
    )
    materials = make_materials_rdict()
    sun = make_sun_gear_rpart(material=materials["gear"])
    ring = make_ring_gear_rpart(material=materials["ring"])
    planet = make_planet_gear_rpart(material=materials["gear"])
    carrier = make_carrier_rpart(material=materials["carrier"])

    reducer = scad.make_assembly_rassembly(
        assembly_id="four_planet_planetary_reducer",
        name="Exposed 3.5:1 four-planet fixed-ring planetary reducer gearset",
    )
    for component_id, item, placement, name in (
        ("fixed_ring", ring, scad.identity_placement_rplacement(), "Fixed internal ring gear"),
        ("sun_input", sun, scad.identity_placement_rplacement(), "Input sun gear"),
        ("output_carrier", carrier, scad.identity_placement_rplacement(), "Four-pin output carrier"),
    ):
        reducer = scad.add_component_rassembly(
            assembly=reducer,
            item=item,
            component_id=component_id,
            placement=placement,
            name=name,
        )
    for index in range(PLANET_COUNT):
        reducer = scad.add_component_rassembly(
            assembly=reducer,
            item=planet,
            component_id=f"planet_{index + 1}",
            placement=make_planet_component_rplacement(index=index),
            name=f"Planet gear {index + 1}",
        )

    reducer = _add_public_connectors_rassembly(assembly=reducer)
    reducer = _add_kinematic_constraints_rassembly(assembly=reducer)
    reducer = scad.solve_assembly_constraints_rassembly(assembly=reducer, strict=True)
    _ground_constraint_report(assembly=reducer)
    print(
        f"planetary_components: count={len(reducer.component_ids())} "
        f"constraints={len(reducer.constraint_ids())}"
    )
    return reducer


def _add_public_connectors_rassembly(*, assembly: scad.Assembly) -> scad.Assembly:
    forwarded = (
        ("fixed_axis", "fixed_ring", "axis", "Fixed ring datum"),
        ("input_axis", "sun_input", "axis", "Sun input datum"),
        ("output_axis", "output_carrier", "output_axis", "Carrier output datum"),
    )
    for connector_id, component_id, source_connector_id, name in forwarded:
        assembly = scad.forward_connector_rassembly(
            assembly=assembly,
            connector_id=connector_id,
            source_component_id=component_id,
            source_connector_id=source_connector_id,
            name=name,
        )
    print("public_connectors: " + ",".join(connector_id for connector_id, *_ in forwarded))
    return assembly


def _add_kinematic_constraints_rassembly(*, assembly: scad.Assembly) -> scad.Assembly:
    assembly = scad.ground_component_rassembly(assembly=assembly, component_id="fixed_ring")
    revolutes = (
        ("sun_input_revolute", "fixed_ring", "axis", "sun_input", "axis", 0.0),
        ("carrier_output_revolute", "fixed_ring", "axis", "output_carrier", "axis", 0.0),
    )
    for constraint_id, a_component, a_connector, b_component, b_connector, drive_angle in revolutes:
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id=constraint_id,
            connector_a=_ref(component_id=a_component, connector_id=a_connector),
            connector_b=_ref(component_id=b_component, connector_id=b_connector),
            drive_angle_degrees=drive_angle,
            angle_limit=None,
            name=constraint_id.replace("_", " "),
        )
    for index in range(PLANET_COUNT):
        planet_id = f"planet_{index + 1}"
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id=f"planet_{index + 1}_pin_revolute",
            connector_a=_ref(component_id="output_carrier", connector_id=f"planet_{index + 1}_axis"),
            connector_b=_ref(component_id=planet_id, connector_id="axis"),
            drive_angle_degrees=None,
            angle_limit=None,
            name=f"Planet {index + 1} pin bearing revolute",
        )
        assembly = scad.add_gear_constraint_rassembly(
            assembly=assembly,
            constraint_id=f"sun_to_planet_{index + 1}_external_mesh",
            connector_a=_ref(component_id="sun_input", connector_id="axis"),
            connector_b=_ref(component_id=planet_id, connector_id="axis"),
            pitch_radius_a=SUN_PITCH_RADIUS,
            pitch_radius_b=PLANET_PITCH_RADIUS,
            phase_offset=None,
            name=f"Sun external mesh to planet {index + 1}",
        )
        assembly = scad.add_belt_constraint_rassembly(
            assembly=assembly,
            constraint_id=f"ring_to_planet_{index + 1}_internal_mesh",
            connector_a=_ref(component_id="fixed_ring", connector_id="axis"),
            connector_b=_ref(component_id=planet_id, connector_id="axis"),
            pulley_radius_a=RING_PITCH_RADIUS,
            pulley_radius_b=PLANET_PITCH_RADIUS,
            phase_offset=None,
            name=f"Fixed ring internal mesh to planet {index + 1}",
        )
    print(
        f"constraints_added: grounded=1 revolute={2 + PLANET_COUNT} "
        f"external_mesh={PLANET_COUNT} internal_mesh={PLANET_COUNT}"
    )
    return assembly


def _ref(*, component_id: str, connector_id: str) -> scad.ConnectorRef:
    return scad.make_connector_ref_rconnectorref(
        component_id=component_id,
        connector_id=connector_id,
    )


def _ground_constraint_report(*, assembly: scad.Assembly) -> None:
    report = scad.inspect_assembly_constraints_rconstraintreport(assembly=assembly)
    print(
        f"assembly_constraints: solved={report.solved} grounded={len(report.grounded_component_ids)} "
        f"solved_components={len(report.solved_component_ids)} unsolved={len(report.unsolved_component_ids)}"
    )
    for residual in report.residuals:
        print(
            f"constraint_{residual.constraint_id}: translation={residual.translation_error:.6g} "
            f"angle={residual.angular_error_degrees:.6g} ok={residual.within_tolerance}"
        )
