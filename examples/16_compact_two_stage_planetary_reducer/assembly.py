"""Top-level compact two-stage planetary reducer assembly."""

from __future__ import annotations
import math
from pathlib import Path
from typing import Callable

import simplecadapi as scad

if __package__:
    from .bearings import (
        make_coaxial_bearing_rplacement,
        make_planet_bearing_rplacements,
        make_radial_ball_bearing_rassembly,
    )
    from .carriers import make_stage_carrier_rpart
    from .dimensions import (
        INPUT_BEARING_Z,
        INTERMEDIATE_BEARING_Z,
        OUTPUT_BEARING_Z,
        PLANET_COUNT,
        STAGE1_PLANET_BEARING,
        STAGE2_PLANET_BEARING,
        STAGE_1,
        STAGE_2,
        TOTAL_REDUCTION,
        StageSpec,
        UNIVERSAL_RADIAL_BEARING,
    )
    from .flanges import make_input_flange_rpart, make_output_flange_rpart
    from .gears import (
        make_planet_component_rplacement,
        make_stage_planet_gear_rpart,
        make_stage_ring_gear_rpart,
        make_stage_sun_gear_rpart,
    )
    from .housing import make_reducer_housing_rpart
    from .materials import make_reducer_material_rmaterial, make_reducer_materials_rdict
    from .shafts import make_input_shaft_rpart
else:
    from bearings import (
        make_coaxial_bearing_rplacement,
        make_planet_bearing_rplacements,
        make_radial_ball_bearing_rassembly,
    )
    from carriers import make_stage_carrier_rpart
    from dimensions import (
        INPUT_BEARING_Z,
        INTERMEDIATE_BEARING_Z,
        OUTPUT_BEARING_Z,
        PLANET_COUNT,
        STAGE1_PLANET_BEARING,
        STAGE2_PLANET_BEARING,
        STAGE_1,
        STAGE_2,
        TOTAL_REDUCTION,
        StageSpec,
        UNIVERSAL_RADIAL_BEARING,
    )
    from flanges import make_input_flange_rpart, make_output_flange_rpart
    from gears import (
        make_planet_component_rplacement,
        make_stage_planet_gear_rpart,
        make_stage_ring_gear_rpart,
        make_stage_sun_gear_rpart,
    )
    from housing import make_reducer_housing_rpart
    from materials import make_reducer_material_rmaterial, make_reducer_materials_rdict
    from shafts import make_input_shaft_rpart

def _assemble_two_stage_planetary_reducer(
    *,
    components: dict[str, scad.Part],
    bearing: scad.Assembly,
) -> scad.Assembly:
    reducer = scad.make_assembly_rassembly(
        assembly_id="compact_two_stage_planetary_reducer",
        name="58.8 mm OD 20:1 through-bolted herringbone planetary actuator reducer",
    )
    reducer = _add_fixed_components_rassembly(
        assembly=reducer,
        components=(
            ("housing", components["housing"], scad.identity_placement_rplacement(), "Fixed outer housing"),
            ("input_flange", components["input_flange"], scad.identity_placement_rplacement(), "Rotating input flange"),
            ("output_flange", components["output_flange"], scad.identity_placement_rplacement(), "Rotating output flange"),
            ("input_shaft", components["input_shaft"], scad.identity_placement_rplacement(), "Input shaft"),
            ("stage1_carrier", components["stage1_carrier"], scad.identity_placement_rplacement(), "Stage 1 carrier and stage 2 sun shaft"),
            ("stage2_carrier", components["stage2_carrier"], scad.identity_placement_rplacement(), "Stage 2 carrier and output shaft"),
            ("stage1_ring", components["stage1_ring"], _gear_stage_rplacement(stage=STAGE_1), "Stage 1 fixed ring"),
            ("stage1_sun", components["stage1_sun"], _gear_stage_rplacement(stage=STAGE_1), "Stage 1 sun"),
            ("stage2_ring", components["stage2_ring"], _gear_stage_rplacement(stage=STAGE_2), "Stage 2 fixed ring"),
            ("stage2_sun", components["stage2_sun"], _gear_stage_rplacement(stage=STAGE_2), "Stage 2 sun"),
        ),
    )
    for index in range(PLANET_COUNT):
        reducer = scad.add_component_rassembly(
            assembly=reducer,
            item=components["stage1_planet"],
            component_id=f"stage1_planet_{index + 1}",
            placement=make_planet_component_rplacement(stage=STAGE_1, planet_index=index),
            name=f"Stage 1 planet gear {index + 1}",
        )
        reducer = scad.add_component_rassembly(
            assembly=reducer,
            item=components["stage2_planet"],
            component_id=f"stage2_planet_{index + 1}",
            placement=make_planet_component_rplacement(stage=STAGE_2, planet_index=index),
            name=f"Stage 2 planet gear {index + 1}",
        )
    reducer = _add_bearing_components_rassembly(assembly=reducer, bearing=bearing)
    reducer = _add_public_interface_connectors_rassembly(assembly=reducer)
    reducer = _add_reducer_constraints_rassembly(assembly=reducer)
    reducer = scad.solve_assembly_constraints_rassembly(assembly=reducer, strict=True)
    _ground_constraint_report(assembly=reducer)
    return reducer


def _runtime_components() -> dict[str, scad.Part]:
    materials = make_reducer_materials_rdict()
    return {
        "housing": make_reducer_housing_rpart(material=materials["housing"]),
        "input_flange": make_input_flange_rpart(material=materials["shaft"]),
        "output_flange": make_output_flange_rpart(material=materials["shaft"]),
        "input_shaft": make_input_shaft_rpart(material=materials["shaft"]),
        "stage1_ring": make_stage_ring_gear_rpart(stage=STAGE_1, material=materials["gear"]),
        "stage1_sun": make_stage_sun_gear_rpart(stage=STAGE_1, bore_radius=1.56, material=materials["gear"]),
        "stage1_planet": make_stage_planet_gear_rpart(stage=STAGE_1, bearing=STAGE1_PLANET_BEARING, material=materials["gear"]),
        "stage1_carrier": make_stage_carrier_rpart(stage=STAGE_1, material=materials["carrier"]),
        "stage2_ring": make_stage_ring_gear_rpart(stage=STAGE_2, material=materials["gear"]),
        "stage2_sun": make_stage_sun_gear_rpart(stage=STAGE_2, bore_radius=1.43, material=materials["gear"]),
        "stage2_planet": make_stage_planet_gear_rpart(stage=STAGE_2, bearing=STAGE2_PLANET_BEARING, material=materials["gear"]),
        "stage2_carrier": make_stage_carrier_rpart(stage=STAGE_2, material=materials["carrier"]),
    }


def make_two_stage_planetary_reducer_rassembly() -> scad.Assembly:
    """Build the full 20:1 compact reducer assembly and solve constraints."""

    print(
        f"ratio_plan: stage1={STAGE_1.fixed_ring_ratio:.1f}:1 "
        f"stage2={STAGE_2.fixed_ring_ratio:.1f}:1 total={TOTAL_REDUCTION:.1f}:1"
    )
    bearing = make_radial_ball_bearing_rassembly(
        bearing_id="micro_radial_ball_bearing",
        spec=UNIVERSAL_RADIAL_BEARING,
        tag_prefix="reducer.bearing.micro.radial",
    )
    return _assemble_two_stage_planetary_reducer(
        components=_runtime_components(),
        bearing=bearing,
    )


def _durable_part(
    *, definition_id: str, factory: Callable[[], scad.Part]
) -> scad.PartBuildResult:
    @scad.part(
        id=definition_id,
        revision="1.0.0",
        cache="off",
        project_root=Path(__file__).resolve().parents[2],
    )
    def build() -> scad.Part:
        return factory()

    return build()


def _bearing_component_part(*, role: str) -> scad.Part:
    bearing = make_radial_ball_bearing_rassembly(
        bearing_id="micro_radial_ball_bearing",
        spec=UNIVERSAL_RADIAL_BEARING,
        tag_prefix="reducer.bearing.micro.radial",
    )
    component_id = "ball_00" if role == "ball" else role
    return bearing.get_component(component_id).item


def _durable_bearing() -> scad.AssemblyBuildResult:
    bearing_id = "micro_radial_ball_bearing"
    outer = _durable_part(
        definition_id=f"{bearing_id}_outer_ring",
        factory=lambda: _bearing_component_part(role="outer_ring"),
    )
    inner = _durable_part(
        definition_id=f"{bearing_id}_inner_ring",
        factory=lambda: _bearing_component_part(role="inner_ring"),
    )
    ball = _durable_part(
        definition_id=f"{bearing_id}_ball",
        factory=lambda: _bearing_component_part(role="ball"),
    )

    @scad.assemble(
        id=bearing_id,
        revision="1.0.0",
        definitions=(outer, inner, ball),
        cache="off",
        project_root=Path(__file__).resolve().parents[2],
    )
    def build() -> scad.Assembly:
        spec = UNIVERSAL_RADIAL_BEARING
        bearing = scad.make_assembly_rassembly(
            assembly_id=bearing_id,
            name="Reusable micro radial ball bearing",
        )
        identity = scad.identity_placement_rplacement()
        bearing = scad.add_component_rassembly(
            assembly=bearing,
            item=outer.part,
            component_id="outer_ring",
            placement=identity,
        )
        bearing = scad.add_component_rassembly(
            assembly=bearing,
            item=inner.part,
            component_id="inner_ring",
            placement=identity,
        )
        pitch_radius = (spec.bore_diameter + spec.outer_diameter) / 4.0
        digits = max(2, len(str(spec.ball_count - 1)))
        for index in range(spec.ball_count):
            angle = 2.0 * math.pi * index / spec.ball_count
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            component_id = f"ball_{index:0{digits}d}"
            bearing = scad.add_component_rassembly(
                assembly=bearing,
                item=ball.part,
                component_id=component_id,
                placement=scad.make_placement_rplacement(
                    origin=(pitch_radius * cos_a, pitch_radius * sin_a, 0.0),
                    x_axis=(cos_a, sin_a, 0.0),
                    y_axis=(-sin_a, cos_a, 0.0),
                ),
            )
            bearing = scad.ground_component_rassembly(
                assembly=bearing,
                component_id=component_id,
            )
        bearing = scad.ground_component_rassembly(
            assembly=bearing,
            component_id="outer_ring",
        )
        bearing = scad.add_revolute_constraint_rassembly(
            assembly=bearing,
            constraint_id="inner_outer_revolute",
            connector_a=scad.make_connector_ref_rconnectorref(
                component_id="outer_ring", connector_id="axis"
            ),
            connector_b=scad.make_connector_ref_rconnectorref(
                component_id="inner_ring", connector_id="axis"
            ),
            drive_angle_degrees=None,
            name="Inner ring spins in outer ring",
        )
        offset = scad.make_placement_rplacement(
            origin=(0.0, 0.0, -spec.width / 2.0)
        )
        bearing = scad.forward_connector_rassembly(
            assembly=bearing,
            connector_id="outer_axis",
            source_component_id="outer_ring",
            source_connector_id="axis",
            name="Outer ring housing axis",
            offset=offset,
        )
        return scad.forward_connector_rassembly(
            assembly=bearing,
            connector_id="inner_axis",
            source_component_id="inner_ring",
            source_connector_id="axis",
            name="Inner ring shaft axis",
            offset=offset,
        )

    return build()


def build_two_stage_planetary_reducer_product() -> scad.AssemblyBuildResult:
    factories: tuple[tuple[str, str, Callable[[], scad.Part]], ...] = (
        ("housing", "reducer_housing", lambda: make_reducer_housing_rpart(material=make_reducer_material_rmaterial(key="housing"))),
        ("input_flange", "input_flange", lambda: make_input_flange_rpart(material=make_reducer_material_rmaterial(key="shaft"))),
        ("output_flange", "output_flange", lambda: make_output_flange_rpart(material=make_reducer_material_rmaterial(key="shaft"))),
        ("input_shaft", "input_shaft", lambda: make_input_shaft_rpart(material=make_reducer_material_rmaterial(key="shaft"))),
        ("stage1_ring", "stage1_ring_gear", lambda: make_stage_ring_gear_rpart(stage=STAGE_1, material=make_reducer_material_rmaterial(key="gear"))),
        ("stage1_sun", "stage1_sun_gear", lambda: make_stage_sun_gear_rpart(stage=STAGE_1, bore_radius=1.56, material=make_reducer_material_rmaterial(key="gear"))),
        ("stage1_planet", "stage1_planet_gear", lambda: make_stage_planet_gear_rpart(stage=STAGE_1, bearing=STAGE1_PLANET_BEARING, material=make_reducer_material_rmaterial(key="gear"))),
        ("stage1_carrier", "stage1_carrier", lambda: make_stage_carrier_rpart(stage=STAGE_1, material=make_reducer_material_rmaterial(key="carrier"))),
        ("stage2_ring", "stage2_ring_gear", lambda: make_stage_ring_gear_rpart(stage=STAGE_2, material=make_reducer_material_rmaterial(key="gear"))),
        ("stage2_sun", "stage2_sun_gear", lambda: make_stage_sun_gear_rpart(stage=STAGE_2, bore_radius=1.43, material=make_reducer_material_rmaterial(key="gear"))),
        ("stage2_planet", "stage2_planet_gear", lambda: make_stage_planet_gear_rpart(stage=STAGE_2, bearing=STAGE2_PLANET_BEARING, material=make_reducer_material_rmaterial(key="gear"))),
        ("stage2_carrier", "stage2_carrier", lambda: make_stage_carrier_rpart(stage=STAGE_2, material=make_reducer_material_rmaterial(key="carrier"))),
    )
    results = {
        key: _durable_part(definition_id=definition_id, factory=factory)
        for key, definition_id, factory in factories
    }
    bearing = _durable_bearing()

    @scad.assemble(
        id="compact_two_stage_planetary_reducer",
        revision="1.0.0",
        definitions=(*results.values(), bearing),
        cache="off",
        project_root=Path(__file__).resolve().parents[2],
    )
    def build() -> scad.Assembly:
        return _assemble_two_stage_planetary_reducer(
            components={key: result.part for key, result in results.items()},
            bearing=bearing.assembly,
        )

    return build()


def _add_fixed_components_rassembly(*,
assembly: scad.Assembly,
components: tuple[tuple[str, scad.Part, scad.Placement, str], ...],) -> scad.Assembly:
    for component_id, item, placement, name in components:
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=item,
            component_id=component_id,
            placement=placement,
            name=name,
        )
    print(f"base_components: count={len(components)}")
    return assembly


def _add_bearing_components_rassembly(*,
assembly: scad.Assembly,
bearing: scad.Assembly,) -> scad.Assembly:
    bearing_component_count = 0
    for component_id, bearing, placement, name in (
        (
            "input_bearing",
            bearing,
            make_coaxial_bearing_rplacement(z=INPUT_BEARING_Z),
            "Input shaft radial ball bearing",
        ),
        (
            "intermediate_bearing",
            bearing,
            make_coaxial_bearing_rplacement(z=INTERMEDIATE_BEARING_Z),
            "Intermediate shaft radial ball bearing",
        ),
        (
            "output_bearing",
            bearing,
            make_coaxial_bearing_rplacement(z=OUTPUT_BEARING_Z),
            "Output shaft radial ball bearing",
        ),
    ):
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=bearing,
            component_id=component_id,
            placement=placement,
            name=name,
        )
        bearing_component_count += 1

    for index, placement in enumerate(make_planet_bearing_rplacements(stage=STAGE_1)):
        component_id = f"stage1_planet_bearing_{index + 1}"
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=bearing,
            component_id=component_id,
            placement=placement,
            name=f"Stage 1 planet {index + 1} ball bearing",
        )
        bearing_component_count += 1

    for index, placement in enumerate(make_planet_bearing_rplacements(stage=STAGE_2)):
        component_id = f"stage2_planet_bearing_{index + 1}"
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=bearing,
            component_id=component_id,
            placement=placement,
            name=f"Stage 2 planet {index + 1} ball bearing",
        )
        bearing_component_count += 1

    print(f"bearing_components: count={bearing_component_count} grounded=0")
    return assembly


def _add_public_interface_connectors_rassembly(*, assembly: scad.Assembly) -> scad.Assembly:
    """Expose stable actuator module datums without leaking private component ids."""

    forwarded = (
        ("housing_mount_axis", "housing", "output_axis", "Fixed case mounting datum"),
        ("input_motor_axis", "input_flange", "axis", "Input flange datum for motor can"),
        ("output_link_axis", "output_flange", "axis", "Output flange datum for driven link"),
    )
    for connector_id, source_component_id, source_connector_id, name in forwarded:
        assembly = scad.forward_connector_rassembly(
            assembly=assembly,
            connector_id=connector_id,
            source_component_id=source_component_id,
            source_connector_id=source_connector_id,
            name=name,
        )
    print("reducer_public_connectors: " + ",".join(connector_id for connector_id, *_ in forwarded))
    return assembly


def _add_reducer_constraints_rassembly(*, assembly: scad.Assembly) -> scad.Assembly:
    assembly = scad.ground_component_rassembly(assembly=assembly, component_id="housing")
    assembly = scad.ground_component_rassembly(assembly=assembly, component_id="stage1_ring")
    assembly = scad.ground_component_rassembly(assembly=assembly, component_id="stage2_ring")

    fixed_pairs = (
        ("stage1_ring_fixed", "housing", "stage1_axis", "stage1_ring", "axis"),
        ("stage2_ring_fixed", "housing", "stage2_axis", "stage2_ring", "axis"),
        ("input_flange_to_shaft", "input_flange", "axis", "input_shaft", "flange_axis"),
        ("stage1_sun_to_input_shaft", "input_shaft", "sun_axis", "stage1_sun", "axis"),
        ("stage2_sun_to_stage1_carrier", "stage1_carrier", "stage2_sun_axis", "stage2_sun", "axis"),
        ("output_flange_to_stage2_carrier", "stage2_carrier", "output_axis", "output_flange", "axis"),
    )
    for constraint_id, a_component, a_connector, b_component, b_connector in fixed_pairs:
        assembly = scad.add_fixed_constraint_rassembly(
            assembly=assembly,
            constraint_id=constraint_id,
            connector_a=_ref(component_id=a_component, connector_id=a_connector),
            connector_b=_ref(component_id=b_component, connector_id=b_connector),
            name=constraint_id.replace("_", " "),
        )

    revolutes = (
        ("input_shaft_revolute", "housing", "input_axis", "input_shaft", "sun_axis"),
        ("stage1_carrier_revolute", "housing", "stage2_axis", "stage1_carrier", "carrier_axis"),
        ("stage2_carrier_revolute", "housing", "output_axis", "stage2_carrier", "carrier_axis"),
    )
    for constraint_id, a_component, a_connector, b_component, b_connector in revolutes:
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id=constraint_id,
            connector_a=_ref(component_id=a_component, connector_id=a_connector),
            connector_b=_ref(component_id=b_component, connector_id=b_connector),
            drive_angle_degrees=0.0,
            angle_limit=None,
            name=constraint_id.replace("_", " "),
        )

    assembly = _add_stage_mesh_constraints_rassembly(
        assembly=assembly,
        stage=STAGE_1,
        driver_component_id="input_shaft",
        driver_connector_id="sun_axis",
        ring_component_id="stage1_ring",
        carrier_component_id="stage1_carrier",
    )
    assembly = _add_stage_mesh_constraints_rassembly(
        assembly=assembly,
        stage=STAGE_2,
        driver_component_id="stage1_carrier",
        driver_connector_id="carrier_axis",
        ring_component_id="stage2_ring",
        carrier_component_id="stage2_carrier",
    )
    assembly = _add_bearing_interface_constraints_rassembly(assembly=assembly)
    print("constraints_added: fixed=6 revolute=27 gear_mesh=6 internal_mesh=6")
    return assembly


def _add_bearing_interface_constraints_rassembly(*, assembly: scad.Assembly) -> scad.Assembly:
    coaxial_interfaces = (
        ("input_bearing_outer_to_housing", "housing", "input_bearing_axis", "input_bearing", "outer_axis"),
        ("input_bearing_inner_to_shaft", "input_shaft", "input_bearing_axis", "input_bearing", "inner_axis"),
        ("intermediate_bearing_outer_to_housing", "housing", "intermediate_bearing_axis", "intermediate_bearing", "outer_axis"),
        ("intermediate_bearing_inner_to_stage1_carrier", "stage1_carrier", "intermediate_bearing_axis", "intermediate_bearing", "inner_axis"),
        ("output_bearing_outer_to_housing", "housing", "output_bearing_axis", "output_bearing", "outer_axis"),
        ("output_bearing_inner_to_stage2_carrier", "stage2_carrier", "output_bearing_axis", "output_bearing", "inner_axis"),
    )
    for constraint_id, a_component, a_connector, bearing_component, bearing_connector in coaxial_interfaces:
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id=constraint_id,
            connector_a=_ref(component_id=a_component, connector_id=a_connector),
            connector_b=_ref(component_id=bearing_component, connector_id=bearing_connector),
            drive_angle_degrees=None,
            angle_limit=None,
            name=constraint_id.replace("_", " "),
        )

    for stage, carrier_component_id in ((STAGE_1, "stage1_carrier"), (STAGE_2, "stage2_carrier")):
        for index in range(PLANET_COUNT):
            planet_id = f"{stage.stage_id}_planet_{index + 1}"
            bearing_id = f"{stage.stage_id}_planet_bearing_{index + 1}"
            assembly = scad.add_revolute_constraint_rassembly(
                assembly=assembly,
                constraint_id=f"{bearing_id}_outer_to_planet",
                connector_a=_ref(component_id=planet_id, connector_id="bearing_axis"),
                connector_b=_ref(component_id=bearing_id, connector_id="outer_axis"),
                drive_angle_degrees=None,
                angle_limit=None,
                name=f"{bearing_id} outer ring to planet gear bore",
            )
            assembly = scad.add_revolute_constraint_rassembly(
                assembly=assembly,
                constraint_id=f"{bearing_id}_inner_to_carrier_pin",
                connector_a=_ref(
                    component_id=carrier_component_id,
                    connector_id=f"planet_{index + 1}_bearing_axis",
                ),
                connector_b=_ref(component_id=bearing_id, connector_id="inner_axis"),
                drive_angle_degrees=None,
                angle_limit=None,
                name=f"{bearing_id} inner ring to carrier pin",
            )
    return assembly


def _add_stage_mesh_constraints_rassembly(*,
assembly: scad.Assembly,
stage: StageSpec,
driver_component_id: str,
driver_connector_id: str,
ring_component_id: str,
carrier_component_id: str,) -> scad.Assembly:
    for index in range(PLANET_COUNT):
        planet_component_id = f"{stage.stage_id}_planet_{index + 1}"
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id=f"{stage.stage_id}_planet_{index + 1}_revolute",
            connector_a=_ref(
                component_id=carrier_component_id,
                connector_id=f"planet_{index + 1}_axis",
            ),
            connector_b=_ref(component_id=planet_component_id, connector_id="axis"),
            drive_angle_degrees=None,
            angle_limit=None,
            name=f"{stage.label} planet {index + 1} pin bearing axis",
        )
        assembly = scad.add_gear_constraint_rassembly(
            assembly=assembly,
            constraint_id=f"{stage.stage_id}_sun_planet_{index + 1}_external_mesh",
            connector_a=_ref(component_id=driver_component_id, connector_id=driver_connector_id),
            connector_b=_ref(component_id=planet_component_id, connector_id="axis"),
            pitch_radius_a=stage.sun_pitch_radius,
            pitch_radius_b=stage.planet_pitch_radius,
            phase_offset=None,
            name=f"{stage.label} external sun to planet {index + 1} mesh",
        )
        assembly = scad.add_belt_constraint_rassembly(
            assembly=assembly,
            constraint_id=f"{stage.stage_id}_ring_planet_{index + 1}_internal_mesh",
            connector_a=_ref(component_id=ring_component_id, connector_id="axis"),
            connector_b=_ref(component_id=planet_component_id, connector_id="axis"),
            pulley_radius_a=stage.ring_pitch_radius,
            pulley_radius_b=stage.planet_pitch_radius,
            phase_offset=None,
            name=f"{stage.label} internal fixed-ring to planet {index + 1} mesh",
        )
    print(
        f"{stage.stage_id}_constraints: sun_r={stage.sun_pitch_radius:.3f} "
        f"planet_r={stage.planet_pitch_radius:.3f} ring_r={stage.ring_pitch_radius:.3f}"
    )
    return assembly


def _gear_stage_rplacement(*, stage: StageSpec) -> scad.Placement:
    return scad.make_placement_rplacement(
        origin=(0.0, 0.0, stage.bottom_z),
        x_axis=(1.0, 0.0, 0.0),
        y_axis=(0.0, 1.0, 0.0),
    )


def _ref(*, component_id: str, connector_id: str) -> scad.ConnectorRef:
    return scad.make_connector_ref_rconnectorref(
        component_id=component_id,
        connector_id=connector_id,
    )


def _ground_constraint_report(*, assembly: scad.Assembly) -> None:
    report = scad.inspect_assembly_constraints_rconstraintreport(assembly=assembly)
    print(
        f"assembly_constraints: solved={report.solved} components={len(assembly.component_ids())} "
        f"constraints={len(assembly.constraints)} grounded={len(assembly.grounded_component_ids)}"
    )
    for residual in report.residuals:
        print(
            f"constraint_{residual.constraint_id}: translation={residual.translation_error:.6g} "
            f"angle={residual.angular_error_degrees:.6g} ok={residual.within_tolerance}"
        )
    STAGE1_PLANET_BEARING,
    STAGE2_PLANET_BEARING,
    UNIVERSAL_RADIAL_BEARING,
