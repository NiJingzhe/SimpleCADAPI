"""External-reference assembly definitions with repeated and nested instances."""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad

OUT_DIR = Path(__file__).resolve().parent / "out"
CACHE = scad.CachePolicy(root=Path(__file__).resolve().parent / "out" / ".cache")


@scad.part(id="gear_train_base", cache=CACHE)
def build_base() -> scad.Part:
    body = scad.make_box_rsolid(width=30.0, height=8.0, depth=2.0)
    body = scad.apply_tag(shape=body, tag="role.gear_train_base")
    part = scad.make_part_rpart(part_id="gear_train_base", body=body)
    for connector_id, origin in (
        ("left_axis", (5.0, 4.0, 2.0)),
        ("right_axis", (25.0, 4.0, 2.0)),
    ):
        connector = scad.make_placement_connector_rconnector(
            connector_id=connector_id,
            placement=scad.make_placement_rplacement(origin=origin),
        )
        part = scad.add_connector_rpart(part=part, connector=connector)
    print(
        f"base: volume={part.body.get_volume():.1f} "
        f"connectors={','.join(part.connector_ids())}"
    )
    return part


@scad.part(id="gear_train_gear", cache=CACHE)
def build_gear() -> scad.Part:
    body = scad.make_cylinder_rsolid(radius=4.0, height=3.0)
    body = scad.apply_tag(shape=body, tag="role.gear_train_gear")
    part = scad.make_part_rpart(part_id="gear_train_gear", body=body)
    axis = scad.make_placement_connector_rconnector(
        connector_id="axis",
        placement=scad.make_placement_rplacement(origin=(0.0, 0.0, 0.0)),
    )
    part = scad.add_connector_rpart(part=part, connector=axis)
    print(
        f"gear: volume={part.body.get_volume():.3f} "
        f"faces={len(scad.ql.faces().resolve(part.body))}"
    )
    return part


def build_external_reference_gear_train() -> scad.AssemblyBuildResult:
    base = build_base()
    gear = build_gear()

    @scad.assemble(
        id="external_reference_gear_train",
        definitions=(base, gear),
    )
    def build_stage() -> scad.Assembly:
        identity = scad.identity_placement_rplacement()
        assembly = scad.make_assembly_rassembly(
            assembly_id="external_reference_gear_train",
            name="Two-axis external-reference gear train",
        )
        for component_id, item in (
            ("base", base.value),
            ("gear_a", gear.value),
            ("gear_b", gear.value),
        ):
            assembly = scad.add_component_rassembly(
                assembly=assembly,
                item=item,
                component_id=component_id,
                placement=identity,
            )
        assembly = scad.ground_component_rassembly(
            assembly=assembly,
            component_id="base",
        )
        base_left = scad.make_connector_ref_rconnectorref("base", "left_axis")
        base_right = scad.make_connector_ref_rconnectorref("base", "right_axis")
        gear_a = scad.make_connector_ref_rconnectorref("gear_a", "axis")
        gear_b = scad.make_connector_ref_rconnectorref("gear_b", "axis")
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id="support_a",
            connector_a=base_left,
            connector_b=gear_a,
            drive_angle_degrees=30.0,
        )
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id="support_b",
            connector_a=base_right,
            connector_b=gear_b,
        )
        assembly = scad.add_gear_constraint_rassembly(
            assembly=assembly,
            constraint_id="mesh",
            connector_a=gear_a,
            connector_b=gear_b,
            pitch_radius_a=4.0,
            pitch_radius_b=8.0,
        )
        assembly = scad.solve_assembly_constraints_rassembly(assembly=assembly)
        return scad.set_public_connector_rassembly(assembly=assembly,
        public_connector_id="output_axis",
        source_component_id="gear_b",
        source_connector_id="axis",)

    stage = build_stage()

    @scad.assemble(
        id="nested_external_reference_gear_trains",
        definitions=(stage,),
    )
    def build_pair() -> scad.Assembly:
        assembly = scad.make_assembly_rassembly(
            assembly_id="nested_external_reference_gear_trains",
            name="Repeated nested gear-train definitions",
        )
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=stage.value,
            component_id="train_left",
            placement=scad.identity_placement_rplacement(),
        )
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=stage.value,
            component_id="train_right",
            placement=scad.make_placement_rplacement(origin=(50.0, 0.0, 0.0)),
        )
        return scad.set_public_connector_rassembly(assembly=assembly,
        public_connector_id="service_axis",
        source_component_id="train_right",
        source_connector_id="output_axis",)

    return build_pair()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = build_external_reference_gear_train()
    package_path = OUT_DIR / "nested_external_reference_gear_trains.scadpkg"
    scad.capture(result, package_path)
    step_path = OUT_DIR / "nested_external_reference_gear_trains.step"
    fcstd_path = OUT_DIR / "nested_external_reference_gear_trains.FCStd"
    step_report = scad.exporter.export_product_package_to_step(package_path, step_path)
    scad.translator.freecad_translator.translate_product_package_to_fcstd(
        package_path,
        str(fcstd_path),
        document_name="NestedExternalReferenceGearTrains",
    )
    definition_path = scad.export_assembly_definition(
        result.definition,
        OUT_DIR / "nested_external_reference_gear_trains.assembly-definition.zip",
    )
    loaded = scad.load_product_package(package_path)
    rebuilt = scad.materialize_definition(loaded)
    nested = rebuilt.get_component("train_left").item
    report = scad.inspect_assembly_constraints_rconstraintreport(nested)
    print(f"root={rebuilt.assembly_id} components={len(rebuilt.components)}")
    print(
        f"nested={nested.assembly_id} constraints={len(nested.constraints)} "
        f"solved={report.solved}"
    )
    print(
        f"definition_refs={len(loaded.definition_refs)} "
        f"content_hash={loaded.content_hash}"
    )
    print(f"definition_artifact={definition_path}")
    print(f"product_package={package_path}")
    print(f"step={step_report.output_path}")
    print(f"fcstd={fcstd_path}")


if __name__ == "__main__":
    main()
