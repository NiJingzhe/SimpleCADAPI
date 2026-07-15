from __future__ import annotations

import importlib
import json

import pytest
import simplecadapi as scad


common_module = importlib.import_module("examples.21_weaving_machine.common")
inventory_module = importlib.import_module("examples.21_weaving_machine.inventory")
main_module = importlib.import_module("examples.21_weaving_machine.main")
parameters_module = importlib.import_module("examples.21_weaving_machine.parameters")


@pytest.fixture(scope="module")
def machine_artifact():
    return main_module.build_replayable_representative_machine(
        parameters=parameters_module.default_machine_parameters(),
        inventory=inventory_module.default_inventory(),
        detail=parameters_module.DetailLevel.REPRESENTATIVE,
    )


def _parts(item):
    if isinstance(item, scad.Part):
        yield item
        return
    for component in item.components:
        yield from _parts(component.item)


def test_whole_machine_has_the_authoritative_a_level_product_tree(machine_artifact):
    machine = machine_artifact.build.machine
    report = scad.inspect_assembly_constraints_rconstraintreport(assembly=machine)

    assert tuple(machine.component_ids()) == inventory_module.TOP_LEVEL_COMPONENT_IDS
    assert machine.grounded_component_ids == ("a00_skeleton",)
    assert (
        len(machine.constraint_ids())
        == len(inventory_module.TOP_LEVEL_COMPONENT_IDS) - 1
    )
    assert report.solved
    assert not report.unsolved_component_ids
    assert all(item.within_tolerance for item in report.residuals)
    assert machine_artifact.build.structural_support.passed
    assert (
        machine_artifact.build.structural_support.supported_parts
        == machine_artifact.build.structural_support.total_parts
    )
    assert not machine_artifact.build.structural_support.unsupported
    assert len(machine_artifact.build.structural_support.support_links) > 300

    for component_id in inventory_module.TOP_LEVEL_COMPONENT_IDS:
        subsystem = machine.get_component(component_id).item
        assert isinstance(subsystem, scad.Assembly)
        assert "machine_mount" in subsystem.connector_ids()
        assert subsystem.component_ids()


def test_representative_machine_contains_recognizable_mechanism_families(
    machine_artifact,
):
    machine = machine_artifact.build.machine
    guide_upper = machine.get_component("a40_upper_guide_frame").item
    guide_lower = machine.get_component("a41_lower_guide_frame").item
    filling = machine.get_component("a60_filling_system").item
    reed = machine.get_component("a70_open_reed").item
    takeup = machine.get_component("a90_linear_takeup").item

    assert (
        len([item for item in guide_upper.component_ids() if "guide_sample" in item])
        == 10
    )
    assert (
        len([item for item in guide_lower.component_ids() if "guide_sample" in item])
        == 10
    )
    assert (
        len([item for item in filling.component_ids() if item.startswith("rapier_")])
        == 3
    )
    assert (
        len([item for item in filling.component_ids() if item.startswith("hook_head_")])
        == 3
    )
    assert len([item for item in reed.component_ids() if "blade_sample" in item]) == 30
    assert {"left_rail", "right_rail", "left_screw", "right_screw"}.issubset(
        takeup.component_ids()
    )


def test_every_recursive_machine_part_has_material_volume_and_role_tags(
    machine_artifact,
):
    parts = tuple(_parts(machine_artifact.build.machine))

    assert len(parts) > 200
    assert all(part.material is not None for part in parts)
    assert all(part.body.get_volume() > 0.0 for part in parts)
    assert all(
        any(tag.startswith("role.") for tag in scad.list_tags(shape=part.body))
        for part in parts
    )


def test_machine_model_graph_is_assembly_terminal_and_topology_independent(
    machine_artifact,
):
    payload = json.loads(machine_artifact.model_json)
    operations = tuple(node["op"] for node in payload["graph"]["nodes"])

    assert machine_artifact.replay_signature_equal
    assert machine_artifact.graph_nodes > 1000
    assert operations.count("make_solve_assembly_constraints_rassembly") >= 1
    assert "make_compound_from_assembly_rcompound" not in operations
    assert "make_face_connector_rconnector" not in operations
    assert "make_edge_connector_rconnector" not in operations
    assert "make_vertex_connector_rconnector" not in operations
    assert common_module.semantic_signature(
        machine_artifact.build.machine
    ) == common_module.semantic_signature(machine_artifact.replayed_machine)


def test_machine_exports_step_stl_and_truthful_evidence(machine_artifact, tmp_path):
    parameters = parameters_module.default_machine_parameters()
    inventory = inventory_module.default_inventory()

    main_module._write_machine_outputs(
        artifact=machine_artifact,
        parameters=parameters,
        inventory=inventory,
        output_dir=tmp_path,
        write_stl=True,
    )

    stem = "weaving_machine_a00_representative_home"
    step_path = tmp_path / f"{stem}.step"
    stl_path = tmp_path / f"{stem}.stl"
    evidence_path = tmp_path / f"{stem}.evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert step_path.stat().st_size > 0
    assert stl_path.stat().st_size > 0
    assert evidence["claims"]["whole_machine_geometry_constructed"]
    assert evidence["claims"]["all_a_level_subsystems_present"]
    assert evidence["claims"]["strict_replay"]
    assert evidence["claims"]["all_visible_parts_structurally_supported"]
    assert evidence["structural_support"]["passed"]
    assert (
        evidence["structural_support"]["supported_parts"]
        == evidence["structural_support"]["total_parts"]
    )
    assert not evidence["structural_support"]["unsupported_paths"]
    assert not evidence["claims"]["functional_a40_guide_indexing"]
    assert not evidence["claims"]["manufacturing_release"]
    assert evidence["top_level_component_ids"] == list(
        inventory_module.TOP_LEVEL_COMPONENT_IDS
    )
    assert evidence["model_sha256"] == machine_artifact.model_sha256


def test_machine_preview_maps_every_replayed_part_to_a_material_group(
    machine_artifact,
):
    preview = scad.make_compound_from_assembly_rcompound(
        assembly=machine_artifact.replayed_machine
    )

    solids = main_module._machine_preview_solids(
        machine=machine_artifact.replayed_machine,
        preview=preview,
    )

    assert len(solids) == machine_artifact.build.structural_support.total_parts
    assert all(
        any(tag.startswith("role.preview.") for tag in scad.list_tags(shape=solid))
        for solid in solids
    )


def test_cli_defaults_to_the_whole_machine():
    args = main_module._parser().parse_args([])

    assert args.target == "machine"
