import json
from dataclasses import dataclass
import unittest

import simplecadapi as scad
from simplecadapi.topology import TopoKind, TopoRef


class TestGraphSessionApi(unittest.TestCase):
    def test_explicit_session_exports_and_replays_selected_result(self):
        with scad.GraphSession(graph_id="explicit_session") as session:
            scad.make_box_rsolid(width=0.5, height=0.5, depth=0.5)
            result = scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)
            session.capture_result(value=result)

        model_json = scad.export_model_json(session)
        payload = json.loads(model_json)

        self.assertEqual(session.graph.graph_id, "explicit_session")
        self.assertEqual(session.graph.node_count, 2)
        self.assertEqual(payload["leaf_ids"], list(session.result_node_ids))
        self.assertEqual(len(scad.replay_model_json(model_json)), 1)

    def test_repeated_sessions_have_deterministic_graph_payloads(self):
        def build() -> tuple[str, str, tuple[str, ...]]:
            with scad.GraphSession(graph_id="deterministic_session") as session:
                body = scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)
                result = scad.apply_tag(shape=body, tag="role.body")
                session.capture_result(value=result)
            return (
                scad.export_model_json(session),
                scad.export_session_json(session),
                session.result_node_ids,
            )

        self.assertEqual(build(), build())

    def test_repeated_sessions_have_deterministic_auto_sketch_ids(self):
        def build() -> tuple[str, str]:
            with scad.GraphSession(
                graph_id="deterministic_sketch_session"
            ) as session:
                sketch = scad.make_sketch_rsketch(name="profile")
                sketch = scad.add_point_rsketch(
                    sketch=sketch,
                    point_id="center",
                    x=0.0,
                    y=0.0,
                )
                sketch = scad.add_circle_rsketch(
                    sketch=sketch,
                    entity_id="circle",
                    center="center",
                    radius=1.0,
                )
                result = scad.make_face_from_sketch_rface(sketch=sketch)
                session.capture_result(value=result)
            return scad.export_model_json(session), scad.export_session_json(session)

        self.assertEqual(build(), build())

    def test_result_selection_excludes_unrelated_leaf(self):
        with scad.GraphSession(graph_id="selected_result") as session:
            scad.make_box_rsolid(width=0.25, height=0.25, depth=0.25)
            final = scad.make_box_rsolid(width=2.0, height=2.0, depth=2.0)
            session.capture_result(value=final)

        payload = json.loads(scad.export_model_json(session))
        nodes = {node["node_id"]: node for node in payload["graph"]["nodes"]}

        self.assertEqual(payload["leaf_ids"], list(session.result_node_ids))
        self.assertEqual(len(payload["leaf_ids"]), 1)
        self.assertEqual(nodes[payload["leaf_ids"][0]]["params"]["width"], 2.0)

    def test_cross_session_shape_input_is_rejected_at_operation_boundary(self):
        with scad.GraphSession(graph_id="source"):
            foreign = scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)

        with scad.GraphSession(graph_id="target"):
            with self.assertRaisesRegex(ValueError, "source.*target"):
                scad.translate_shape(shape=foreign, vector=(1.0, 0.0, 0.0))

    def test_cross_session_child_assembly_is_rejected(self):
        with scad.GraphSession(graph_id="child_graph"):
            child = scad.make_assembly_rassembly(assembly_id="child")

        with scad.GraphSession(graph_id="parent_graph"):
            parent = scad.make_assembly_rassembly(assembly_id="parent")
            placement = scad.identity_placement_rplacement()
            with self.assertRaisesRegex(ValueError, "child_graph.*parent_graph"):
                scad.add_component_rassembly(
                    assembly=parent,
                    item=child,
                    component_id="child_1",
                    placement=placement,
                )

    def test_unrecorded_child_assembly_is_rejected(self):
        child = scad.make_assembly_rassembly(assembly_id="unrecorded_child")

        with scad.GraphSession(graph_id="parent_graph"):
            parent = scad.make_assembly_rassembly(assembly_id="parent")
            placement = scad.identity_placement_rplacement()
            with self.assertRaisesRegex(ValueError, "unrecorded Assembly"):
                scad.add_component_rassembly(
                    assembly=parent,
                    item=child,
                    component_id="child_1",
                    placement=placement,
                )

    def test_capture_result_walks_dataclasses_and_is_atomic_on_failure(self):
        @dataclass
        class ResultValue:
            body: scad.Solid

        with scad.GraphSession(graph_id="dataclass_result") as session:
            body = scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)
            session.capture_result(value=ResultValue(body=body))

        self.assertEqual(len(session.result_node_ids), 1)
        self.assertEqual(len(scad.replay_model_json(scad.export_model_json(session))), 1)

        with scad.GraphSession(graph_id="atomic_capture") as session:
            body = scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)
            with scad.GraphSession(graph_id="foreign_capture"):
                foreign = scad.make_box_rsolid(width=2.0, height=2.0, depth=2.0)
            with self.assertRaisesRegex(ValueError, "foreign_capture.*atomic_capture"):
                session.capture_result(value=(body, foreign))
            self.assertFalse(session.has_explicit_results)
            self.assertEqual(session.result_node_ids, ())

        with scad.GraphSession(graph_id="topology_capture") as session:
            body = scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)
            node = body._get_runtime("graph.node")
            body._set_runtime(
                "topo.ref",
                TopoRef(
                    graph_id="foreign_topology",
                    node_id=node.node_id,
                    output_slot=0,
                    kind=TopoKind.SOLID,
                    topo_id="solid_0",
                ),
            )
            with self.assertRaisesRegex(
                ValueError, "foreign_topology.*topology_capture"
            ):
                session.capture_result(value=body)
            self.assertFalse(session.has_explicit_results)
            self.assertEqual(session.result_node_ids, ())

    def test_removed_decorator_api_is_not_public(self):
        for name in ("ModelResult", "model", "requires_session", "capture_result"):
            self.assertFalse(hasattr(scad, name), name)


if __name__ == "__main__":
    unittest.main()
