"""Host-independent tests for the Fusion 360 translator backend."""

from __future__ import annotations

import ast
import copy
import importlib
import math
import sys
import unittest

import simplecadapi as scad
from simplecadapi import GraphSession
from simplecadapi.translator.errors import TranslationRequestError


def _rectangle_extrusion_model() -> str:
    with GraphSession() as session:
        profile = scad.make_rectangle_rface(width=2.0, height=1.0)
        scad.extrude_rsolid(
            profile=profile,
            direction=(0.0, 0.0, 1.0),
            distance=3.0,
        )
    return scad.export_model_json(session=session)


class TestFusion360Translator(unittest.TestCase):
    def test_backend_imports_without_target_runtime_modules(self):
        before = set(sys.modules)

        fusion = importlib.import_module("simplecadapi.translator.fusion360_translator")

        self.assertNotIn("adsk.core", set(sys.modules) - before)
        self.assertNotIn("adsk.fusion", set(sys.modules) - before)
        self.assertEqual(fusion.CAPABILITIES.backend_id, "fusion360")

    def test_supported_graph_emits_deterministic_compilable_script(self):
        model_json = _rectangle_extrusion_model()
        from simplecadapi.translator.fusion360_translator import Fusion360Translator

        translator = Fusion360Translator(document_name="ContractFusion")
        first = translator.translate_model_json(model_json)
        second = translator.translate_model_json(model_json)

        self.assertEqual(first.content, second.content)
        compile(first.content, "<fusion360-script>", "exec")
        self.assertFalse(first.metadata["target_runtime_validated"])
        self.assertTrue(translator.capabilities.targets[0].requires_external_runtime)

    def test_payload_uses_canonical_periodic_curve_frames(self):
        with GraphSession() as session:
            scad.make_angle_arc_rwire(
                (0.0, 0.0, 0.0),
                2.0,
                0.0,
                math.pi / 2.0,
                normal=(1.0, 0.0, 0.0),
            )
            scad.make_helix_rwire(
                1.0,
                3.0,
                2.0,
                dir=(1.0, 0.0, 0.0),
            )

        from simplecadapi.translator.fusion360_translator import Fusion360Translator

        script = (
            Fusion360Translator()
            .translate_model_json(scad.export_model_json(session))
            .content
        )
        module = ast.parse(script)
        model_payload = next(
            ast.literal_eval(node.value)
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "MODEL_PAYLOAD"
                for target in node.targets
            )
        )
        curve_nodes = {
            node["op"]: node
            for node in model_payload["graph"]["nodes"]
            if node["op"] in {"make_angle_arc_redge", "make_helix_redge"}
        }

        for node in curve_nodes.values():
            self.assertEqual(node["params"]["_kernel_x_axis"], [-0.0, 0.0, 1.0])
            self.assertEqual(node["params"]["_kernel_y_axis"], [0.0, -1.0, 0.0])
        self.assertIn("Circle3D.createByCenter", script)
        self.assertIn("SweepOrientationTypes.ParallelOrientationType", script)

    def test_fallback_scripts_are_deterministic_and_result_scoped(self):
        with GraphSession() as session:
            profile = scad.make_rectangle_rface(
                1.0,
                2.0,
                center=(2.0, 0.0, 0.0),
                normal=(0.0, 1.0, 0.0),
            )
            scad.revolve_rsolid(profile, axis=(0.0, 1.0, 0.0))
            scad.make_box_rsolid(width=4.0, height=5.0, depth=6.0)
        model_json = scad.export_model_json(session)
        payload = scad.import_model_json(model_json)
        graph = payload["graph"]
        result_id = next(
            node.node_id
            for node in graph.topological_order()
            if node.op == "make_revolve_rsolid"
        )
        box_id = next(
            node.node_id
            for node in graph.topological_order()
            if node.op == "make_box_rsolid"
        )

        from simplecadapi.translator.fusion360_translator import Fusion360Translator

        translator = Fusion360Translator(
            result_node_ids=[result_id], source_kernel_fallback=True
        )
        first = translator.translate_model_json(model_json).content
        second = translator.translate_model_json(model_json).content

        self.assertEqual(first, second)
        module = ast.parse(first)
        fallback_steps = next(
            ast.literal_eval(node.value)
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "SOURCE_KERNEL_STEPS"
                for target in node.targets
            )
        )
        self.assertIn(result_id, fallback_steps)
        self.assertNotIn(box_id, fallback_steps)

    def test_implicit_results_prefer_active_assembly_state(self):
        from simplecadapi.topology import OperationGraph
        from simplecadapi.translator.fusion360_translator import Fusion360Translator

        graph = OperationGraph("assembly_states")
        locked = graph.add_node(
            "make_compound_from_assembly_rcompound",
            {"assembly_id": "fixture_locked", "component_count": 1},
            node_id="locked_result",
        )
        operating = graph.add_node(
            "make_compound_from_assembly_rcompound",
            {"assembly_id": "fixture_operating", "component_count": 1},
            node_id="operating_result",
        )
        payload = {
            "schema_version": "2.0",
            "graph": graph,
            "leaf_ids": [locked.node_id, operating.node_id],
        }

        script = Fusion360Translator().translate_model_payload_to_script(
            payload, graph=graph
        )

        self.assertIn("ACTIVE_RESULT_STATE = 'operating'", script)
        self.assertIn("RESULT_NODE_IDS = ['operating_result']", script)

    def test_fallback_accepts_legacy_metadata_only_selector_nodes(self):
        with GraphSession() as session:
            profile = scad.make_rectangle_rface(3.0, 3.0)
            solid = scad.extrude_rsolid(profile, (0.0, 0.0, 1.0), 3.0)
            scad.fillet_rsolid(solid, [solid.get_edges(0)], 0.2)
        payload = scad.import_model_json(scad.export_model_json(session))
        graph_data = copy.deepcopy(payload["graph"].to_dict())
        selector_ids = {
            node["node_id"]
            for node in graph_data["nodes"]
            if node["op"] == "make_select_redge"
        }
        for node in graph_data["nodes"]:
            if node["node_id"] in selector_ids:
                node["inputs"] = []
            else:
                node["inputs"] = [
                    input_ref
                    for input_ref in node.get("inputs", [])
                    if input_ref not in selector_ids
                ]
        graph_data["edges"] = [
            edge
            for edge in graph_data.get("edges", [])
            if edge[0] not in selector_ids and edge[1] not in selector_ids
        ]

        from simplecadapi.topology import OperationGraph
        from simplecadapi.translator.fusion360_translator import Fusion360Translator

        legacy_graph = OperationGraph.from_dict(graph_data)
        result_id = next(
            node.node_id
            for node in legacy_graph.nodes
            if node.op == "make_fillet_rsolid"
        )
        legacy_payload = {
            "schema_version": "2.0",
            "graph": legacy_graph,
            "leaf_ids": [result_id],
        }
        script = Fusion360Translator(
            source_kernel_fallback=True
        ).translate_model_payload_to_script(legacy_payload, graph=legacy_graph)
        module = ast.parse(script)
        fallback_steps = next(
            ast.literal_eval(node.value)
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "SOURCE_KERNEL_STEPS"
                for target in node.targets
            )
        )

        self.assertIn(result_id, fallback_steps)

    def test_explicit_result_only_executes_its_dependency_closure(self):
        with GraphSession() as session:
            profile = scad.make_rectangle_rface(width=2.0, height=1.0)
            scad.extrude_rsolid(profile, (0.0, 0.0, 1.0), 3.0)
            scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)
        model_json = scad.export_model_json(session=session)
        payload = scad.import_model_json(model_json)
        graph = payload["graph"]
        extrusion_id = next(
            node.node_id
            for node in graph.topological_order()
            if node.op == "make_extrude_rsolid"
        )

        from simplecadapi.translator.fusion360_translator import Fusion360Translator

        script = (
            Fusion360Translator(result_node_ids=[extrusion_id])
            .translate_model_json(model_json)
            .content
        )

        self.assertIn(f"RESULT_NODE_IDS = ['{extrusion_id}']", script)
        self.assertIn("active_node_ids = self._result_dependency_ids", script)
        self.assertIn("not in active_node_ids", script)

    def test_unsupported_result_operation_is_rejected_before_host_execution(self):
        with GraphSession() as session:
            scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)

        from simplecadapi.translator.fusion360_translator import Fusion360Translator

        with self.assertRaises(TranslationRequestError):
            Fusion360Translator().translate_model_json(scad.export_model_json(session))


if __name__ == "__main__":
    unittest.main()
