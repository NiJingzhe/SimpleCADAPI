"""Regression tests for operation source provenance."""

import json

import simplecadapi as scad
from simplecadapi.serializer import export_graph_json
from simplecadapi.source_mapping import canonical_source_payload
from simplecadapi.topology import OperationGraph


def test_source_mapping_records_call_span_and_assignment_target():
    with scad.GraphSession(graph_id="source_mapping") as session:
        width = 10.0
        body = scad.make_box_rsolid(
            width=width,
            height=2.0,
            depth=3.0,
        )

    node = session.graph.nodes[0]
    assert node.source is not None
    assert node.source["path"].endswith("test_source_mapping.py")
    assert node.source["path_kind"] == "project_relative"
    assert node.source["line"] <= node.source["end_line"]
    assert node.source["call_text"].startswith("scad.make_box_rsolid")
    assert node.source["assignment_targets"] == ["body"]
    assert "input_bindings" not in node.source


def test_source_mapping_disambiguates_same_line_calls_and_round_trips():
    with scad.GraphSession(graph_id="source_mapping_same_line") as session:
        first = scad.make_box_rsolid(1.0, 1.0, 1.0); second = scad.make_box_rsolid(2.0, 2.0, 2.0)

    nodes = session.graph.topological_order()
    assert len(nodes) == 2
    assert nodes[0].source is not None
    assert nodes[1].source is not None
    assert nodes[0].source["assignment_targets"] == ["first"]
    assert nodes[1].source["assignment_targets"] == ["second"]
    assert nodes[0].source["column"] < nodes[1].source["column"]

    payload = json.loads(export_graph_json(session.graph))
    assert payload["capabilities"]["source_mapping"] is True
    assert "local_path" not in payload["nodes"][0]["source"]
    restored = OperationGraph.from_dict(payload)
    assert restored.nodes[0].source == canonical_source_payload(nodes[0].source)
    assert restored.nodes[1].source == canonical_source_payload(nodes[1].source)


def test_source_mapping_does_not_claim_nested_call_as_assignment_output():
    with scad.GraphSession(graph_id="source_mapping_nested") as session:
        body = scad.make_box_rsolid(1.0, 1.0, 1.0)
        moved = scad.translate_shape(
            shape=body,
            vector=(1.0, 0.0, 0.0),
        )

    translate_node = session.graph.topological_order()[1]
    assert translate_node.source is not None
    assert translate_node.source["assignment_targets"] == ["moved"]


def test_source_mapping_records_complex_targets_and_return():
    class Holder:
        pass

    holder = Holder()
    with scad.GraphSession(graph_id="source_mapping_targets") as session:
        holder.body = scad.make_box_rsolid(1.0, 1.0, 1.0)
        items = [None]
        index = 0
        items[index] = scad.make_box_rsolid(2.0, 2.0, 2.0)

    first, second = session.graph.topological_order()
    assert first.source is not None
    assert first.source["assignment_targets"] == ["holder.body"]
    assert second.source is not None
    assert second.source["assignment_targets"] == ["items[index]"]


def test_source_mapping_records_return_and_requires_session_builder():
    @scad.requires_session
    def build_box():
        return scad.make_box_rsolid(1.0, 1.0, 1.0)

    with scad.GraphSession(graph_id="source_mapping_return") as session:
        result = build_box()

    node = session.graph.nodes[0]
    assert result.get_metadata("graph")["node_id"] == node.node_id
    assert node.source is not None
    assert node.source["call_text"] == "scad.make_box_rsolid(1.0, 1.0, 1.0)"
    assert node.source["assignment_targets"] == []


def test_macro_nodes_share_the_user_callsite_and_assignment_target():
    with scad.GraphSession(graph_id="source_mapping_macro") as session:
        profile = scad.make_rectangle_rface(width=2.0, height=1.0)

    nodes = session.graph.topological_order()
    assert len(nodes) > 1
    assert profile.get_metadata("graph")["node_id"] == nodes[-1].node_id
    assert all(node.source is not None for node in nodes)

    callsite_ids = {node.source["callsite_id"] for node in nodes if node.source}
    call_texts = {node.source["call_text"] for node in nodes if node.source}
    targets = {
        tuple(node.source["assignment_targets"])
        for node in nodes
        if node.source
    }
    assert len(callsite_ids) == 1
    assert call_texts == {
        "scad.make_rectangle_rface(width=2.0, height=1.0)"
    }
    assert targets == {("profile",)}
