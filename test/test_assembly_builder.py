from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import simplecadapi as scad
from simplecadapi.artifacts.canonical import ArtifactValidationError, content_hash


GENERATOR = {
    "simplecadapi_version": "2.0.4b1",
    "ocp_version": "7.9.3.1",
    "python_abi": "cp313",
    "platform_tag": "darwin-arm64",
    "semantic_registry_version": "simplecad-operations-2.0",
}


def _policy(root: Path) -> scad.CachePolicy:
    return scad.CachePolicy(root=root)


def _build_nested_gear_train(tmp_path: Path):
    @scad.part(id="train_base", cache=_policy(tmp_path / "cache"))
    def build_base() -> scad.Part:
        body = scad.make_box_rsolid(width=30.0, height=8.0, depth=2.0)
        part = scad.make_part_rpart(part_id="train_base", body=body)
        left = scad.make_placement_connector_rconnector(
            connector_id="left_axis",
            placement=scad.make_placement_rplacement(origin=(5.0, 4.0, 2.0)),
        )
        right = scad.make_placement_connector_rconnector(
            connector_id="right_axis",
            placement=scad.make_placement_rplacement(origin=(25.0, 4.0, 2.0)),
        )
        part = scad.add_connector_rpart(part=part, connector=left)
        return scad.add_connector_rpart(part=part, connector=right)

    @scad.part(id="train_gear", cache=_policy(tmp_path / "cache"))
    def build_gear() -> scad.Part:
        body = scad.make_cylinder_rsolid(radius=4.0, height=3.0)
        part = scad.make_part_rpart(part_id="train_gear", body=body)
        axis = scad.make_placement_connector_rconnector(
            connector_id="axis",
            placement=scad.make_placement_rplacement(origin=(0.0, 0.0, 0.0)),
        )
        return scad.add_connector_rpart(part=part, connector=axis)

    base = build_base()
    gear = build_gear()

    @scad.assemble(
        id="gear_train",
        definitions=(base, gear),
    )
    def build_train() -> scad.Assembly:
        identity = scad.identity_placement_rplacement()
        assembly = scad.make_assembly_rassembly(assembly_id="gear_train")
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=base.value,
            component_id="base",
            placement=identity,
        )
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=gear.value,
            component_id="gear_a",
            placement=identity,
        )
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=gear.value,
            component_id="gear_b",
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
        return scad.forward_connector_rassembly(
            assembly=assembly,
            connector_id="output_axis",
            source_component_id="gear_b",
            source_connector_id="axis",
        )

    train = build_train()

    @scad.assemble(
        id="nested_train_pair",
        definitions=(train,),
    )
    def build_pair() -> scad.Assembly:
        assembly = scad.make_assembly_rassembly(assembly_id="nested_train_pair")
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=train.value,
            component_id="train_left",
            placement=scad.identity_placement_rplacement(),
        )
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=train.value,
            component_id="train_right",
            placement=scad.make_placement_rplacement(origin=(50.0, 0.0, 0.0)),
        )
        return scad.forward_connector_rassembly(
            assembly=assembly,
            connector_id="service_axis",
            source_component_id="train_right",
            source_connector_id="output_axis",
        )

    return base, gear, train, build_pair()


def test_assemble_external_reference_round_trip_preserves_hierarchy_and_coupling(
    tmp_path: Path,
) -> None:
    _base, gear, train, pair = _build_nested_gear_train(tmp_path)

    assert len(train.definition.definition_refs) == 2
    assert [item.definition_id for item in train.definition.instances].count("train_gear") == 2
    assert [item.constraint_kind for item in train.value.constraints] == [
        "revolute",
        "revolute",
        "gear",
    ]
    assert scad.inspect_assembly_constraints_rconstraintreport(train.value).solved

    output = pair.export_definition(path=tmp_path / "pair.assembly-definition.zip")
    loaded = scad.load_assembly_definition(output)
    rebuilt = scad.materialize_definition(loaded)

    assert loaded.canonical_bytes == pair.definition.canonical_bytes
    assert isinstance(rebuilt, scad.Assembly)
    assert rebuilt.component_ids() == ("train_left", "train_right")
    assert rebuilt.connector_ids() == ("service_axis",)
    left = rebuilt.get_component("train_left").item
    right = rebuilt.get_component("train_right").item
    assert left is right
    assert isinstance(left, scad.Assembly)
    assert left.get_component("gear_a").item is left.get_component("gear_b").item
    assert left.get_component("gear_a").item.part_id == gear.value.part_id
    assert left.constraint_ids() == ("mesh", "support_a", "support_b")
    assert scad.inspect_assembly_constraints_rconstraintreport(left).solved

    written = {item.name for item in tmp_path.glob("*.zip")}
    assert "pair.assembly-definition.zip" in written
    assert any(name.endswith(".part-definition.zip") for name in written)
    assert any(
        name.endswith(".assembly-definition.zip")
        and name != "pair.assembly-definition.zip"
        for name in written
    )


def test_assemble_keeps_authored_placements_separate_from_solved_snapshot(
    tmp_path: Path,
) -> None:
    _base, _gear, train, _pair = _build_nested_gear_train(tmp_path)

    authored = {
        instance.instance_id: instance.placement
        for instance in train.definition.instances
    }
    solved = {
        item["instance_id"]: item["placement"]
        for item in train.definition.solved_snapshot["component_placements"]
    }

    identity = scad.identity_placement_rplacement().to_dict()
    assert authored["gear_a"] == identity
    assert authored["gear_b"] == identity
    assert solved["gear_a"]["origin"] == [5.0, 4.0, 2.0]
    assert solved["gear_b"]["origin"] == [25.0, 4.0, 2.0]
    assert train.definition.interface_hashes.geometry == content_hash(
        {
            "instances": [
                {
                    "instance_id": instance.instance_id,
                    "definition_id": instance.definition_id,
                    "geometry_hash": train.definition.resolved_definitions[
                        instance.definition_id
                    ].interface_hashes.geometry,
                    "placement": instance.placement,
                }
                for instance in train.definition.instances
            ]
        }
    )

    rebuilt = scad.materialize_definition(train.definition)
    assert isinstance(rebuilt, scad.Assembly)
    assert rebuilt.get_component("gear_a").placement.to_dict() == solved["gear_a"]
    assert rebuilt.get_component("gear_b").placement.to_dict() == solved["gear_b"]


def test_assemble_rejects_undeclared_and_wrong_runtime_definition_identity(
    tmp_path: Path,
) -> None:
    @scad.part(id="declared_part", cache=_policy(tmp_path / "cache"))
    def declared(width: float = 1.0) -> scad.Part:
        body = scad.make_box_rsolid(width=width, height=1.0, depth=1.0)
        return scad.make_part_rpart(part_id="declared_part", body=body)

    expected = declared(1.0)
    wrong = declared(2.0)

    @scad.assemble(id="wrong_identity", definitions=(expected,))
    def build_wrong() -> scad.Assembly:
        assembly = scad.make_assembly_rassembly("wrong_identity")
        return scad.add_component_rassembly(
            assembly,
            wrong.value,
            "part",
            scad.identity_placement_rplacement(),
        )

    @scad.assemble(id="undeclared", definitions=())
    def build_undeclared() -> scad.Assembly:
        assembly = scad.make_assembly_rassembly("undeclared")
        return scad.add_component_rassembly(
            assembly,
            expected.value,
            "part",
            scad.identity_placement_rplacement(),
        )

    with pytest.raises(ArtifactValidationError, match="reference_identity_mismatch"):
        build_wrong()
    with pytest.raises(ArtifactValidationError, match="reference_missing"):
        build_undeclared()


def test_assembly_graph_validation_rejects_hash_and_connector_mismatches(
    tmp_path: Path,
) -> None:
    _base, _gear, train, _pair = _build_nested_gear_train(tmp_path)
    definition = train.definition

    first_ref = definition.definition_refs[0]
    wrong_ref = replace(first_ref, content_hash="sha256:" + "0" * 64)
    wrong_hash = replace(
        definition,
        definition_refs=(wrong_ref, *definition.definition_refs[1:]),
        content_hash="",
    )
    with pytest.raises(ArtifactValidationError) as hash_error:
        scad.validate_assembly_definition_graph(wrong_hash)
    assert hash_error.value.reason == "reference_identity_mismatch"
    assert hash_error.value.path == "/definition_refs/0"

    relations = [dict(item) for item in definition.relations]
    relations[0] = {
        **relations[0],
        "connector_b": {
            **relations[0]["connector_b"],
            "connector_id": "missing_axis",
        },
    }
    missing_connector = replace(
        definition,
        relations=tuple(relations),
        content_hash="",
    )
    with pytest.raises(ArtifactValidationError) as connector_error:
        scad.validate_assembly_definition_graph(missing_connector)
    assert connector_error.value.reason == "reference_missing"
    assert connector_error.value.path == "/relations/0/connector_b/connector_id"


def test_assembly_loader_reports_cycle_with_instance_path(tmp_path: Path) -> None:
    cycle_ref = scad.PartRef(
        definition_id="cycle_child",
        definition_kind="assembly",
        path="cycle.assembly-definition.zip",
        revision="r1",
        content_hash="sha256:" + "1" * 64,
        byte_length=0,
    )
    definition = scad.AssemblyDefinition(
        definition_id="cycle_root",
        revision="r1",
        tolerance_profile="simplecad-default",
        generator=GENERATOR,
        definition_refs=(cycle_ref,),
        instances=(
            scad.PartInstance(
                instance_id="child",
                definition_id="cycle_child",
                name=None,
                placement=scad.Placement((0.0, 0.0, 0.0)).to_dict(),
            ),
        ),
        relations=(),
        grounded_instance_ids=(),
        public_connectors=(),
        interface_hashes=scad.InterfaceHashes(
            geometry=content_hash({"instances": []}),
            connectors={},
            bindings={},
            material=None,
        ),
    )
    path = tmp_path / "cycle.assembly-definition.zip"
    path.write_bytes(scad.encode_assembly_definition(definition))

    with pytest.raises(ArtifactValidationError) as error:
        scad.load_assembly_definition(path)
    assert error.value.reason == "reference_cycle"
    assert "child" in error.value.message


def test_assemble_rejects_dependency_tolerance_profile_conflict(tmp_path: Path) -> None:
    @scad.part(
        id="profile_part",
        cache=_policy(tmp_path / "cache"),
        tolerance_profile="alternate-profile",
    )
    def build_part() -> scad.Solid:
        return scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)

    part = build_part()

    with pytest.raises(ArtifactValidationError, match="profile_incompatible"):

        @scad.assemble(id="profile_conflict", definitions=(part,))
        def build() -> scad.Assembly:
            return scad.make_assembly_rassembly("profile_conflict")


def test_assemble_reuses_independent_constraint_components(tmp_path: Path) -> None:
    policy = _policy(tmp_path / "cache")

    @scad.part(id="incremental_base", cache=policy)
    def build_base() -> scad.Part:
        part = scad.make_part_rpart(
            "incremental_base",
            scad.make_box_rsolid(width=2.0, height=2.0, depth=2.0),
        )
        return scad.add_connector_rpart(
            part,
            scad.make_placement_connector_rconnector(
                "mate",
                scad.identity_placement_rplacement(),
            ),
        )

    @scad.part(id="incremental_tool_a", cache=policy)
    def build_tool_a(connector_x: float) -> scad.Part:
        part = scad.make_part_rpart(
            "incremental_tool_a",
            scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0),
        )
        return scad.add_connector_rpart(
            part,
            scad.make_placement_connector_rconnector(
                "mate",
                scad.make_placement_rplacement(origin=(connector_x, 0.0, 0.0)),
            ),
        )

    @scad.part(id="incremental_tool_b", cache=policy)
    def build_tool_b() -> scad.Part:
        part = scad.make_part_rpart(
            "incremental_tool_b",
            scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0),
        )
        return scad.add_connector_rpart(
            part,
            scad.make_placement_connector_rconnector(
                "mate",
                scad.identity_placement_rplacement(),
            ),
        )

    base = build_base()
    tool_b = build_tool_b()

    def assembly_builder(tool_a: scad.PartBuildResult):
        @scad.assemble(
            id="incremental_pair",
            definitions=(base, tool_a, tool_b),
            cache=policy,
        )
        def build_pair() -> scad.Assembly:
            assembly = scad.make_assembly_rassembly("incremental_pair")
            for component_id, item, origin in (
                ("base_a", base.value, (0.0, 0.0, 0.0)),
                ("tool_a", tool_a.value, (4.0, 0.0, 0.0)),
                ("base_b", base.value, (20.0, 0.0, 0.0)),
                ("tool_b", tool_b.value, (24.0, 0.0, 0.0)),
            ):
                assembly = scad.add_component_rassembly(
                    assembly,
                    item,
                    component_id,
                    scad.make_placement_rplacement(origin=origin),
                )
            assembly = scad.ground_component_rassembly(assembly, "base_a")
            assembly = scad.ground_component_rassembly(assembly, "base_b")
            assembly = scad.add_fixed_constraint_rassembly(
                assembly,
                "constraint_a",
                scad.make_connector_ref_rconnectorref("base_a", "mate"),
                scad.make_connector_ref_rconnectorref("tool_a", "mate"),
            )
            return scad.add_fixed_constraint_rassembly(
                assembly,
                "constraint_b",
                scad.make_connector_ref_rconnectorref("base_b", "mate"),
                scad.make_connector_ref_rconnectorref("tool_b", "mate"),
            )

        return build_pair

    initial_builder = assembly_builder(build_tool_a(0.0))
    cold = initial_builder()
    warm = initial_builder()
    changed = assembly_builder(build_tool_a(2.0))()

    assert (cold.solve_report.component_hits, cold.solve_report.component_misses) == (
        0,
        2,
    )
    assert (warm.solve_report.component_hits, warm.solve_report.component_misses) == (
        2,
        0,
    )
    assert warm.solve_report.hit
    assert (
        changed.solve_report.component_hits,
        changed.solve_report.component_misses,
    ) == (1, 1)
    assert changed.solve_report.dirty_connectors == ("tool_a.mate",)
    assert changed.solve_report.dirty_relations == ("constraint_a",)
    assert len(changed.solve_report.dirty_components) == 1
    assert sum(item.cache_hit for item in changed.solve_report.component_results) == 1
    assert scad.inspect_assembly_constraints_rconstraintreport(changed.value).solved


def test_nested_forwarded_connector_change_invalidates_parent_component(
    tmp_path: Path,
) -> None:
    policy = _policy(tmp_path / "cache")

    @scad.part(id="nested_connector_part", cache=policy)
    def build_child(connector_x: float) -> scad.Part:
        part = scad.make_part_rpart(
            "nested_connector_part",
            scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0),
        )
        return scad.add_connector_rpart(
            part,
            scad.make_placement_connector_rconnector(
                "mate",
                scad.make_placement_rplacement(origin=(connector_x, 0.0, 0.0)),
            ),
        )

    def build_stage(child: scad.PartBuildResult) -> scad.AssemblyBuildResult:
        @scad.assemble(
            id="nested_connector_stage",
            definitions=(child,),
            cache=policy,
        )
        def stage() -> scad.Assembly:
            assembly = scad.make_assembly_rassembly("nested_connector_stage")
            assembly = scad.add_component_rassembly(
                assembly,
                child.value,
                "child",
                scad.identity_placement_rplacement(),
            )
            return scad.forward_connector_rassembly(
                assembly,
                "output",
                "child",
                "mate",
            )

        return stage()

    def parent_builder(stage: scad.AssemblyBuildResult):
        @scad.assemble(
            id="nested_connector_parent",
            definitions=(stage,),
            cache=policy,
        )
        def parent() -> scad.Assembly:
            assembly = scad.make_assembly_rassembly("nested_connector_parent")
            assembly = scad.add_component_rassembly(
                assembly,
                stage.value,
                "grounded",
                scad.identity_placement_rplacement(),
            )
            assembly = scad.add_component_rassembly(
                assembly,
                stage.value,
                "moving",
                scad.make_placement_rplacement(origin=(10.0, 0.0, 0.0)),
            )
            assembly = scad.ground_component_rassembly(assembly, "grounded")
            return scad.add_fixed_constraint_rassembly(
                assembly,
                "nested_fixed",
                scad.make_connector_ref_rconnectorref("grounded", "output"),
                scad.make_connector_ref_rconnectorref("moving", "output"),
            )

        return parent

    initial_stage = build_stage(build_child(0.0))
    initial_parent_builder = parent_builder(initial_stage)
    cold = initial_parent_builder()
    warm = initial_parent_builder()
    changed_stage = build_stage(build_child(3.0))
    changed = parent_builder(changed_stage)()

    assert (cold.solve_report.component_hits, cold.solve_report.component_misses) == (
        0,
        1,
    )
    assert (warm.solve_report.component_hits, warm.solve_report.component_misses) == (
        1,
        0,
    )
    assert (
        changed.solve_report.component_hits,
        changed.solve_report.component_misses,
    ) == (0, 1)
    assert changed.solve_report.dirty_connectors == (
        "grounded.output",
        "moving.output",
    )
    assert changed.solve_report.dirty_relations == ("nested_fixed",)
    assert scad.inspect_assembly_constraints_rconstraintreport(changed.value).solved
