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
            "samples_per_edge": 2,
        },
    )

    assert summary["parameter_groups"]["pattern_inference"] == "not_performed"
    assert (
        len(summary["parameter_groups"]["surfaces"]["groups"][0]["example_entity_ids"])
        == 1
    )
    assert face["compact"] is True
    assert "samples_3d" not in face["outer"]["edges"][0]


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
