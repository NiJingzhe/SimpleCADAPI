"""Execute emitted product operations without starting a COM application."""

import copy
import math
from types import SimpleNamespace

import pytest

from simplecadapi.product.placement import Placement, placement_ticks
from simplecadapi.topology import OperationGraph
from simplecadapi.translator.solidworks_translator import (
    CAPABILITIES,
    SolidWorksTranslator,
)
from simplecadapi.translator.solidworks_translator.emitters import emit_native_node
from simplecadapi.translator.solidworks_translator.runtime import (
    assemble_runtime_source,
)
from simplecadapi.translator.solidworks_translator.translator import _SolidWorksCompiler
from simplecadapi.translator.types import SupportLevel


@pytest.fixture
def runtime():
    namespace = {"math": math}
    exec(assemble_runtime_source(), namespace)
    cls = namespace["SimpleCADSolidWorksRuntime"]
    value = cls.__new__(cls)
    value.outputs = {}
    value.product_values = {}
    return value


def emit(runtime, op, params, inputs=(), node_id="result"):
    return runtime.emit_node(
        {
            "node_id": node_id,
            "op": op,
            "params": params,
            "inputs": [{"node_id": key} for key in inputs],
        }
    )[0]


@pytest.fixture
def assembly(runtime):
    # Part connector registration is essential for resolving public aliases.
    runtime.outputs["part"] = [
        {"kind": "part", "body": object(), "material": {"name": "steel"}}
    ]
    emit(
        runtime,
        "make_placement_connector_rconnector",
        {"connector_id": "mount"},
        node_id="connector",
    )
    part = emit(
        runtime, "make_add_connector_rpart", {}, ["part", "connector"], "connected"
    )
    source = {
        "kind": "assembly",
        "components": [
            {
                "component_id": "a",
                "item": part,
                "placement": {
                    "kind": "placement",
                    "params": {"origin": [1.0, 2.0, 3.0]},
                },
            },
            {
                "component_id": "b",
                "item": {
                    "kind": "assembly",
                    "components": [],
                    "public_connectors": [
                        {
                            "public_connector_id": "nested",
                            "component_id": "child",
                            "connector_id": "mount",
                        },
                    ],
                },
                "placement": {
                    "kind": "placement",
                    "params": {"origin": [7.0, 8.0, 9.0]},
                },
            },
        ],
    }
    runtime.outputs["assembly"] = [source]
    return source


def test_public_connector_preserves_source_and_nested_alias(runtime, assembly):
    params = {
        "public_connector_id": "interface",
        "source_component_id": "a",
        "source_connector_id": "mount",
        "name": "Mount",
    }
    result = emit(runtime, "make_set_public_connector_rassembly", params, ["assembly"])
    assert result["public_connectors"] == [
        {
            "public_connector_id": "interface",
            "component_id": "a",
            "connector_id": "mount",
            "name": "Mount",
        }
    ]
    assert "public_connectors" not in assembly
    assert result["components"] is assembly["components"]
    assert runtime.product_values["result"] is result
    assert assembly["components"][0]["item"]["material"] == {"name": "steel"}
    assert "connectors" not in runtime.outputs["part"][0]
    nested = emit(
        runtime,
        "make_set_public_connector_rassembly",
        {**params, "source_component_id": "b", "source_connector_id": "nested"},
        ["assembly"],
    )
    assert nested["public_connectors"][0]["component_id"] == "b"


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"source_component_id": "missing"}, "missing component"),
        ({"source_connector_id": "missing"}, "missing connector"),
        ({"public_connector_id": ""}, "non-empty"),
    ],
)
def test_invalid_public_connector_rejected(runtime, assembly, changes, match):
    params = {
        "public_connector_id": "interface",
        "source_component_id": "a",
        "source_connector_id": "mount",
    }
    with pytest.raises(RuntimeError, match=match):
        emit(
            runtime,
            "make_set_public_connector_rassembly",
            {**params, **changes},
            ["assembly"],
        )
    assert "result" not in runtime.outputs
    assert "public_connectors" not in assembly


def test_duplicate_public_connector_rejected(runtime, assembly):
    params = {
        "public_connector_id": "interface",
        "source_component_id": "a",
        "source_connector_id": "mount",
    }
    first = emit(runtime, "make_set_public_connector_rassembly", params, ["assembly"])
    with pytest.raises(RuntimeError, match="duplicate public_connector_id"):
        emit(
            runtime,
            "make_set_public_connector_rassembly",
            params,
            ["result"],
            "duplicate",
        )
    assert len(first["public_connectors"]) == 1


@pytest.mark.parametrize(
    "op", ["evaluate_assembly_definition", "make_solve_assembly_constraints_rassembly"]
)
def test_emitted_solved_frames_replace_placement_without_mutation(
    runtime, assembly, op
):
    original_placements = copy.deepcopy(
        [c["placement"] for c in assembly["components"]]
    )
    frame = Placement(
        origin=(20.0, -5.0, 3.0), x_axis=(0.0, 1.0, 0.0), y_axis=(-1.0, 0.0, 0.0)
    )
    ticks = placement_ticks(frame)
    placements = (
        [{"instance_id": "a", "placement": ticks}]
        if op == "evaluate_assembly_definition"
        else {"a": frame.to_dict()}
    )
    graph = OperationGraph()
    source = graph.add_node("make_assembly_rassembly", node_id="assembly")
    public = graph.add_node(
        "make_set_public_connector_rassembly",
        params={
            "public_connector_id": "interface",
            "source_component_id": "a",
            "source_connector_id": "mount",
        },
        inputs=[source],
        node_id="public",
    )
    evaluated = graph.add_node(
        op,
        params={
            "component_placements": placements,
            "constraint_report": {"solved": True},
        },
        inputs=[public],
        node_id="solved",
    )
    SolidWorksTranslator()._preflight(graph, evaluated.node_id)
    compiler = _SolidWorksCompiler()
    for node in (public, evaluated):
        source = (
            "def execute():\n    if True:\n"
            + "\n".join(emit_native_node(compiler, node))
            + "\nexecute()"
        )
        exec(source, {"runtime": runtime})
    result = runtime.outputs["solved"][0]
    assert result["components"][0]["placement"]["params"] == frame.to_dict()
    assert [c["placement"] for c in assembly["components"]] == original_placements
    assert result["components"] is not assembly["components"]
    assert result["components"][1] == assembly["components"][1]
    for index in (0, 1):
        assert (
            result["components"][index]["item"] is assembly["components"][index]["item"]
        )
    assert (
        result["public_connectors"] == runtime.outputs["public"][0]["public_connectors"]
    )
    assert runtime.product_values["solved"] is result
    assert evaluated.params["component_placements"] == placements
    payload = compiler._payload_to_jsonable({}, graph, [evaluated])
    assert payload["graph"]["nodes"][0]["params"] == compiler._solidworks_params(
        evaluated
    )
    runtime.emit_node(payload["graph"]["nodes"][0])
    assert (
        runtime.outputs["solved"][0]["components"][0]["placement"]
        == result["components"][0]["placement"]
    )
    if op == "evaluate_assembly_definition":
        assert result["constraint_report"] == {"solved": True}
    matrix = runtime._assembly_with_placements.__globals__["_placement_matrix"](
        result["components"][0]["placement"]
    )
    assert matrix[:9] == [0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    assert matrix[9:12] == pytest.approx([0.020, -0.005, 0.003])


@pytest.mark.parametrize(
    "records,match",
    [
        ([{"instance_id": "unknown", "placement": {}}], "missing component"),
        ([{"instance_id": "a", "placement": {}}] * 2, "Duplicate solved component"),
    ],
)
def test_invalid_evaluation_rejected(runtime, assembly, records, match):
    with pytest.raises(RuntimeError, match=match):
        emit(
            runtime,
            "evaluate_assembly_definition",
            {"component_placements": records},
            ["assembly"],
        )
    assert "result" not in runtime.product_values


def test_current_assembly_operations_have_emitters_and_metadata_support():
    from simplecadapi.recording.serializer import CANONICAL_OP_SET
    from simplecadapi.translator.solidworks_translator.emitters.registry import (
        EMITTER_METHOD_BY_OP,
    )

    assert set(CAPABILITIES.operations) == set(CANONICAL_OP_SET)
    assert "make_add_connector_rassembly" not in EMITTER_METHOD_BY_OP
    for op in ("evaluate_assembly_definition", "make_set_public_connector_rassembly"):
        assert CAPABILITIES.operations[op].level is SupportLevel.METADATA_ONLY
        assert EMITTER_METHOD_BY_OP[op] == "_emit_products"


def test_legacy_solve_integer_coordinates_are_not_ticks(runtime, assembly):
    graph = OperationGraph()
    source = graph.add_node("make_assembly_rassembly", node_id="assembly")
    frame = {
        "origin": [10, 0, 0],
        "x_axis": [1, 0, 0],
        "y_axis": [0, 1, 0],
        "z_axis": [0, 0, 1],
    }
    node = graph.add_node(
        "make_solve_assembly_constraints_rassembly",
        params={"component_placements": {"a": frame}},
        inputs=[source],
    )
    lines = emit_native_node(_SolidWorksCompiler(), node)
    exec(
        "def execute():\n    if True:\n" + "\n".join(lines) + "\nexecute()",
        {"runtime": runtime},
    )
    assert (
        runtime.outputs[node.node_id][0]["components"][0]["placement"]["params"]
        == frame
    )


@pytest.mark.parametrize("owned", [True, False])
@pytest.mark.parametrize("visible", [True, False])
def test_cleanup_only_closes_owned_application(runtime, owned, visible):
    calls = []
    runtime.sw = SimpleNamespace(
        CloseAllDocuments=lambda discard: calls.append(("close", discard)),
        ExitApp=lambda: calls.append(("exit",)),
    )
    runtime.model = object()  # Cleanup must not call a possibly stale model proxy.
    runtime._owns_solidworks = owned
    runtime.visible = visible
    runtime._stop_solidworks()
    assert calls == ([("close", True), ("exit",)] if owned else [])
    assert runtime.sw is None and runtime.model is None
    assert runtime._owns_solidworks is False
    runtime._stop_solidworks()
    assert calls == ([("close", True), ("exit",)] if owned else [])
