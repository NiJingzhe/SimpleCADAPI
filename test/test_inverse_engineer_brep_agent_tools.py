from __future__ import annotations

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from simplecadapi.inverse_engineer import brep
from simplecadapi.inverse_engineer.brep.agent_tools import (
    AGENT_TOOL_NAMES,
    BRepToolError,
    agent_tool_schemas,
    call_agent_tool,
)
from simplecadapi.kernel.ocp_export import export_step_shapes


@pytest.fixture
def box_step(tmp_path):
    path = tmp_path / "box.step"
    export_step_shapes([BRepPrimAPI_MakeBox(2.0, 3.0, 4.0).Shape()], str(path))
    brep.clear_step_model_cache()
    yield path
    brep.clear_step_model_cache()


def test_agent_registry_contains_all_migrated_tools():
    expected = {
        "get_model_summary",
        "inspect_entity",
        "get_topology_neighborhood",
        "measure_relation",
        "make_section",
        "extract_face_boundaries",
        "probe_point",
        "render_region",
        "compare_global_properties",
        "compare_boundary_distance",
        "compute_material_difference",
        "compare_sections",
        "build_difference_regions",
        "find_nearby_entities",
        "compare_entities",
        "evaluate_result",
        "compare_brep_strict",
    }

    assert set(AGENT_TOOL_NAMES) == expected
    assert {item["function"]["name"] for item in agent_tool_schemas()} == expected
    assert len(AGENT_TOOL_NAMES) == 17
    assert len(agent_tool_schemas()) == 17


def test_agent_tool_dispatches_inspection_and_comparison(box_step):
    summary = call_agent_tool(
        "get_model_summary",
        {"model_path": str(box_step)},
    )
    face = call_agent_tool(
        "inspect_entity",
        {"model_path": str(box_step), "entity_id": "face:0"},
    )
    comparison = call_agent_tool(
        "compare_global_properties",
        {"target_path": str(box_step), "current_path": str(box_step)},
    )

    assert summary["volume"] == pytest.approx(24.0)
    assert face["kind"] == "face"
    assert comparison["volume"]["absolute_delta"] == pytest.approx(0.0)


def test_agent_tools_expose_opt_in_groups_and_compact_boundaries(box_step):
    summary = call_agent_tool(
        "get_model_summary",
        {
            "model_path": str(box_step),
            "include_parameter_groups": True,
            "max_parameter_groups": 2,
            "examples_per_group": 1,
        },
    )
    face = call_agent_tool(
        "extract_face_boundaries",
        {
            "model_path": str(box_step),
            "face_id": "face:0",
            "compact": True,
            "samples_per_edge": 4,
        },
    )

    assert summary["parameter_groups"]["pattern_inference"] == "not_performed"
    assert (
        len(summary["parameter_groups"]["surfaces"]["groups"][0]["example_entity_ids"])
        == 1
    )
    assert face["compact"] is True
    assert "samples_3d" not in face["outer"]["edges"][0]
    assert "axes" in summary["parameter_groups"]
    assert "adjacency_signatures" in summary["parameter_groups"]


def test_agent_schemas_expose_bounded_definition_and_compact_options():
    schemas = {
        item["function"]["name"]: item["function"]["parameters"]["properties"]
        for item in agent_tool_schemas()
    }

    assert "include_surface_definition" in schemas["inspect_entity"]
    assert "max_surface_control_points" in schemas["inspect_entity"]
    assert "include_curve_definitions" in schemas["extract_face_boundaries"]
    assert "curve_definition_edge_ids" in schemas["extract_face_boundaries"]
    assert "max_total_control_points" in schemas["extract_face_boundaries"]
    assert "compact" in schemas["make_section"]
    assert schemas["make_section"]["samples_per_edge"]["minimum"] == 4
    assert schemas["compare_sections"]["samples_per_edge"]["minimum"] == 4


def test_agent_tool_dispatches_compact_section(box_step):
    section = call_agent_tool(
        "make_section",
        {
            "model_path": str(box_step),
            "origin": [0.0, 0.0, 2.0],
            "normal": [0.0, 0.0, 1.0],
            "compact": True,
        },
    )

    assert section["compact"] is True
    assert section["closed_contour_count"] == 1
    assert "samples_3d" not in section["edges"][0]


def test_agent_material_defaults_to_volume_only(box_step):
    material = call_agent_tool(
        "compute_material_difference",
        {"target_path": str(box_step), "current_path": str(box_step)},
    )

    assert material["method"] == "common_volume"
    assert material["missing_material"]["components"] is None


def test_inspect_entity_exposes_endpoint_differentials_without_adding_a_tool(box_step):
    edge = call_agent_tool(
        "inspect_entity",
        {
            "model_path": str(box_step),
            "entity_id": "edge:0",
            "include_curve_definition": True,
        },
    )

    assert len(AGENT_TOOL_NAMES) == 17
    assert edge["geometry"]["endpoint_differentials"]["start"]["d1"] is not None
    assert "control_points" not in edge["geometry"]["parameters"]


def test_agent_tool_rejects_unknown_name():
    with pytest.raises(BRepToolError, match="Unknown BREP tool"):
        call_agent_tool("not_a_tool", {})


def test_agent_tool_validates_json_boolean_types():
    with pytest.raises(BRepToolError, match="not of type 'boolean'"):
        call_agent_tool(
            "evaluate_result",
            {
                "target_path": "target.step",
                "current_path": "current.step",
                "replay_succeeded": "false",
            },
        )
