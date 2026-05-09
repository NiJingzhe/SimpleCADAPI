"""Tests for Phase 7: serialization and replay."""

import json
import unittest
from copy import deepcopy

import simplecadapi as scad
from simplecadapi.topology import OperationGraph, TopoDelta
from simplecadapi.graph import GraphSession, record_operation
from simplecadapi.serializer import (
    export_graph_json,
    import_graph_json,
    replay_graph,
    PUBLIC_API_COVERAGE,
)


class TestGraphSerialization(unittest.TestCase):
    def test_roundtrip_empty(self):
        graph = OperationGraph()
        data = graph.to_dict()
        restored = OperationGraph.from_dict(data)
        self.assertEqual(restored.node_count, 0)
        self.assertEqual(restored.graph_id, graph.graph_id)

    def test_roundtrip_with_nodes(self):
        graph = OperationGraph()
        n1 = graph.add_node("make_line_redge", {"start": (0, 0, 0), "end": (10, 0, 0)})
        n2 = graph.add_node(
            "make_line_redge", {"start": (10, 0, 0), "end": (10, 20, 0)}
        )
        n3 = graph.add_node(
            "make_wire_from_edges_rwire", {"edge_count": 2}, inputs=[n1, n2]
        )

        data = graph.to_dict()
        restored = OperationGraph.from_dict(data)

        self.assertEqual(restored.node_count, 3)
        self.assertEqual(restored.edge_count, 2)

        # Verify node order is preserved
        r_nodes = restored.topological_order()
        r_ops = [n.op for n in r_nodes]
        self.assertIn("make_line_redge", r_ops)
        self.assertIn("make_wire_from_edges_rwire", r_ops)

    def test_roundtrip_json(self):
        graph = OperationGraph()
        n1 = graph.add_node("make_line_redge", {"start": (0, 0, 0), "end": (10, 0, 0)})
        n2 = graph.add_node(
            "make_wire_from_edges_rwire", {"edge_count": 1}, inputs=[n1]
        )

        json_str = graph.to_json()
        restored = OperationGraph.from_json(json_str)

        self.assertEqual(restored.node_count, 2)
        self.assertEqual(restored.graph_id, graph.graph_id)

    def test_json_is_valid_json(self):
        graph = OperationGraph()
        graph.add_node("make_line_redge", {"start": (0, 0, 0), "end": (10, 20, 0)})
        json_str = graph.to_json()
        parsed = json.loads(json_str)
        self.assertIn("graph_id", parsed)
        self.assertIn("nodes", parsed)
        self.assertIn("edges", parsed)

    def test_roundtrip_preserves_params(self):
        graph = OperationGraph()
        graph.add_node(
            "make_translate_rshape",
            {"vector": [10.5, 20.0, 30.0], "center": [1, 2, 3]},
        )
        json_str = graph.to_json()
        restored = OperationGraph.from_json(json_str)
        node = restored.nodes[0]
        self.assertEqual(node.params["vector"], [10.5, 20.0, 30.0])
        self.assertEqual(node.params["center"], [1, 2, 3])

    def test_roundtrip_preserves_tags(self):
        graph = OperationGraph()
        graph.add_node("make_line_redge", {}, tags={"primitive", "profile"})
        json_str = graph.to_json()
        restored = OperationGraph.from_json(json_str)
        self.assertIn("primitive", restored.nodes[0].tags)
        self.assertIn("profile", restored.nodes[0].tags)


class TestExportImport(unittest.TestCase):
    def test_export_graph_json(self):
        with GraphSession() as session:
            record_operation("make_line_redge", {"start": (0, 0, 0), "end": (10, 0, 0)})
        json_str = export_graph_json(session.graph)
        parsed = json.loads(json_str)
        self.assertEqual(len(parsed["nodes"]), 1)

    def test_export_graph_json_includes_display_payload(self):
        with scad.GraphSession() as session:
            body = scad.make_box_rsolid(10, 10, 10)
            tool = scad.make_cylinder_rsolid(2.0, 15.0, bottom_face_center=(3, 3, -2.5))
            scad.cut_rsolidlist(body, tool)

        payload = json.loads(export_graph_json(session.graph))
        leaf = next(
            node for node in payload["nodes"] if node["op"] == "make_cut_rsolidlist"
        )

        self.assertIn("display", leaf)
        self.assertEqual(leaf["display"]["category"], "boolean")
        self.assertIn("label", leaf["display"])
        self.assertIn("summary", leaf["display"])

    def test_export_graph_json_display_payload_includes_selection_counts(self):
        with scad.GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            edges = box.get_edges()[:4]
            scad.fillet_rsolid(box, edges, 0.2)

        payload = json.loads(export_graph_json(session.graph))
        fillet_node = next(
            node for node in payload["nodes"] if node["op"] == "make_fillet_rsolid"
        )

        self.assertIn("display", fillet_node)
        self.assertEqual(fillet_node["display"]["selection_count"], 4)

    def test_export_graph_json_includes_schema_metadata(self):
        with scad.GraphSession() as session:
            scad.make_box_rsolid(1.0, 1.0, 1.0)

        payload = json.loads(export_graph_json(session.graph))
        self.assertIn("schema_version", payload)
        self.assertIn("producer_version", payload)
        self.assertIn("capabilities", payload)
        self.assertTrue(payload["capabilities"]["selection_ref_strategies"])
        self.assertTrue(payload["capabilities"]["display_payload"])

    def test_export_graph_json_includes_scalar_field_tree(self):
        sphere = scad.field.make_sphere_rscalarfield((0.0, 0.0, 0.0), 1.4)
        box = scad.field.make_box_rscalarfield((0.3, 0.0, 0.0), (1.0, 0.8, 0.8))
        field = scad.field.smooth_subtract_rscalarfield(sphere, box, 0.1)

        with scad.GraphSession() as session:
            scad.make_field_surface_rsolid(field, resolution=(12, 12, 12), iso=0.0)

        payload = json.loads(export_graph_json(session.graph))
        node = next(
            node
            for node in payload["nodes"]
            if node["op"] == "make_field_surface_rsolid"
        )

        self.assertEqual(node["params"]["field_serialization_mode"], "scalar_field")
        self.assertEqual(node["params"]["field_tree"]["op"], "smooth_subtract")

    def test_export_graph_json_marks_callable_field_as_opaque(self):
        def sphere_fn(x, y, z):
            return (x**2 + y**2 + z**2) ** 0.5 - 1.0

        with scad.GraphSession() as session:
            scad.make_field_surface_rsolid(
                sphere_fn,
                bounds=((-2.0, -2.0, -2.0), (2.0, 2.0, 2.0)),
                resolution=(10, 10, 10),
                iso=0.0,
            )

        payload = json.loads(export_graph_json(session.graph))
        node = next(
            node
            for node in payload["nodes"]
            if node["op"] == "make_field_surface_rsolid"
        )

        self.assertEqual(node["params"]["field_serialization_mode"], "opaque_callable")
        self.assertNotIn("field_tree", node["params"])


class TestCoverageMatrix(unittest.TestCase):
    def test_public_api_coverage_accounts_for_current_geometry_exports(self):
        expected = {
            "make_box_rsolid",
            "make_cylinder_rsolid",
            "make_sphere_rsolid",
            "make_cone_rsolid",
            "make_circle_rwire",
            "make_rectangle_rface",
            "make_wire_from_edges_rwire",
            "translate_shape",
            "rotate_shape",
            "mirror_shape",
            "extrude_rsolid",
            "revolve_rsolid",
            "loft_rsolid",
            "sweep_rsolid",
            "helical_sweep_rsolid",
            "union_rsolid",
            "cut_rsolidlist",
            "intersect_rsolidlist",
            "fillet_rsolid",
            "chamfer_rsolid",
            "shell_rsolid",
            "linear_pattern_rsolidlist",
            "radial_pattern_rsolidlist",
            "make_field_surface_rsolid",
        }
        self.assertTrue(expected.issubset(PUBLIC_API_COVERAGE.keys()))

    def test_known_out_of_scope_entries_are_explicit(self):
        self.assertEqual(
            PUBLIC_API_COVERAGE["make_field_surface_rsolid"]["status"], "replayable"
        )
        self.assertIn(
            "callable", PUBLIC_API_COVERAGE["make_field_surface_rsolid"]["reason"]
        )

    def test_import_graph_json(self):
        json_str = '{"schema_version": "1.0", "graph_id": "test", "nodes": [{"node_id": "n1", "op": "make_line_redge", "params": {"start": [0, 0, 0], "end": [10, 0, 0]}, "inputs": [], "output_count": 1, "tags": []}], "edges": []}'
        graph = import_graph_json(json_str)
        self.assertEqual(graph.node_count, 1)
        self.assertEqual(graph.nodes[0].op, "make_line_redge")

    def test_import_graph_json_rejects_unsupported_schema(self):
        json_str = (
            '{"schema_version": "2.0", "graph_id": "test", "nodes": [], "edges": []}'
        )
        with self.assertRaises(ValueError):
            import_graph_json(json_str)


class TestReplay(unittest.TestCase):
    def test_replay_builds_graph(self):
        """A simple low-level graph can be replayed."""
        with GraphSession() as session:
            n1 = record_operation(
                "make_line_redge", {"start": (0, 0, 0), "end": (1, 0, 0)}
            )
            n2 = record_operation(
                "make_line_redge", {"start": (1, 0, 0), "end": (1, 1, 0)}
            )
            record_operation(
                "make_wire_from_edges_rwire", {"edge_count": 2}, inputs=[n1, n2]
            )

        results = replay_graph(session.graph)
        self.assertIsNotNone(results)
        self.assertGreater(len(results), 0)

    def test_replay_preserves_volume(self):
        with GraphSession() as session:
            record_operation(
                "make_extrude_rsolid", {"direction": (0, 0, 1), "distance": 10.0}
            )

        results = replay_graph(session.graph)
        self.assertGreaterEqual(len(results), 0)

    def test_replay_empty_graph(self):
        graph = OperationGraph()
        results = replay_graph(graph)
        self.assertEqual(results, [])

    def test_replay_original_api_rectangle_extrude_roundtrip(self):
        with scad.GraphSession() as session:
            profile = scad.make_rectangle_rface(2.0, 1.0)
            solid = scad.extrude_rsolid(profile, (0, 0, 1), 3.0)

        graph_json = export_graph_json(session.graph)
        restored = import_graph_json(graph_json)
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Solid)
        self.assertAlmostEqual(results[0].get_volume(), solid.get_volume(), places=5)

    def test_replay_original_api_circle_wire_roundtrip(self):
        with scad.GraphSession() as session:
            wire = scad.make_circle_rwire((0, 0, 0), 2.0)

        graph_json = export_graph_json(session.graph)
        restored = import_graph_json(graph_json)
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Wire)
        self.assertTrue(results[0].is_closed())

    def test_replay_original_api_loft_roundtrip(self):
        with scad.GraphSession() as session:
            a = scad.make_rectangle_rwire(2.0, 2.0, center=(0, 0, 0))
            b = scad.make_rectangle_rwire(1.0, 1.0, center=(0, 0, 2.0))
            lofted = scad.loft_rsolid([a, b])

        graph_json = export_graph_json(session.graph)
        restored = import_graph_json(graph_json)
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Solid)
        self.assertAlmostEqual(results[0].get_volume(), lofted.get_volume(), places=5)

    def test_replay_wire_face_extrude_edit_chain_roundtrip(self):
        with scad.GraphSession() as session:
            e1 = scad.make_line_redge((0, 0, 0), (1, 0, 0))
            e2 = scad.make_line_redge((1, 0, 0), (1, 1, 0))
            e3 = scad.make_line_redge((1, 1, 0), (0, 1, 0))
            e4 = scad.make_line_redge((0, 1, 0), (0, 0, 0))
            wire = scad.make_wire_from_edges_rwire([e1, e2, e3, e4])
            face = scad.make_face_from_wire_rface(wire)
            solid = scad.extrude_rsolid(face, (0, 0, 1), 2.0)

        graph_json = export_graph_json(session.graph)
        restored = import_graph_json(graph_json)
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Solid)
        self.assertAlmostEqual(results[0].get_volume(), solid.get_volume(), places=5)

    def test_replay_fillet_roundtrip_with_selected_edges(self):
        with scad.GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            edges = box.get_edges()[:4]
            filleted = scad.fillet_rsolid(box, edges, 0.2)

        graph_json = export_graph_json(session.graph)
        restored = import_graph_json(graph_json)
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Solid)
        self.assertAlmostEqual(results[0].get_volume(), filleted.get_volume(), places=5)

    def test_replay_chamfer_roundtrip_with_selected_edges(self):
        with scad.GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            edges = box.get_edges()[:4]
            chamfered = scad.chamfer_rsolid(box, edges, 0.2)

        graph_json = export_graph_json(session.graph)
        restored = import_graph_json(graph_json)
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Solid)
        self.assertAlmostEqual(
            results[0].get_volume(), chamfered.get_volume(), places=5
        )

    def test_replay_shell_roundtrip_with_selected_faces(self):
        with scad.GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            shelled = scad.shell_rsolid(box, [box.get_faces()[0]], 0.2)

        graph_json = export_graph_json(session.graph)
        restored = import_graph_json(graph_json)
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Solid)
        self.assertAlmostEqual(results[0].get_volume(), shelled.get_volume(), places=5)

    def test_replay_fillet_roundtrip_with_selector_hint_fallback(self):
        with scad.GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            edges = box.get_edges()[:4]
            filleted = scad.fillet_rsolid(box, edges, 0.2)

        payload = json.loads(export_graph_json(session.graph))
        fillet_node = next(
            node for node in payload["nodes"] if node["op"] == "make_fillet_rsolid"
        )
        self.assertGreater(len(fillet_node["params"]["selected_edges"]), 0)
        self.assertIn("selector_hint", fillet_node["params"]["selected_edges"][0])

        damaged = deepcopy(payload)
        damaged_fillet = next(
            node for node in damaged["nodes"] if node["op"] == "make_fillet_rsolid"
        )
        for ref in damaged_fillet["params"]["selected_edges"]:
            ref["topo_id"] = "missing_edge_ref"
        damaged_fillet["params"]["selected_edge_indices"] = []

        restored = import_graph_json(json.dumps(damaged))
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Solid)
        self.assertAlmostEqual(results[0].get_volume(), filleted.get_volume(), places=5)

    def test_replay_shell_roundtrip_with_selector_hint_fallback(self):
        with scad.GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            shelled = scad.shell_rsolid(box, [box.get_faces()[0]], 0.2)

        payload = json.loads(export_graph_json(session.graph))
        shell_node = next(
            node for node in payload["nodes"] if node["op"] == "make_shell_rsolid"
        )
        self.assertGreater(len(shell_node["params"]["selected_faces"]), 0)
        self.assertIn("selector_hint", shell_node["params"]["selected_faces"][0])

        damaged = deepcopy(payload)
        damaged_shell = next(
            node for node in damaged["nodes"] if node["op"] == "make_shell_rsolid"
        )
        for ref in damaged_shell["params"]["selected_faces"]:
            ref["topo_id"] = "missing_face_ref"
        damaged_shell["params"]["selected_face_indices"] = []

        restored = import_graph_json(json.dumps(damaged))
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Solid)
        self.assertAlmostEqual(results[0].get_volume(), shelled.get_volume(), places=5)

    def test_replay_fillet_roundtrip_with_ql_selector(self):
        with scad.GraphSession() as session:
            rod = scad.make_cylinder_rsolid(1.0, 5.0, bottom_face_center=(0, 0, 0))
            selector = (
                scad.ql.edges()
                .where(scad.ql.curve_type("circle"))
                .order_by(scad.ql.center_axis("z"))
                .take(1)
                .exactly(1)
            )
            filleted = scad.fillet_rsolid(rod, selector, 0.15)

        payload = json.loads(export_graph_json(session.graph))
        fillet_node = next(
            node for node in payload["nodes"] if node["op"] == "make_fillet_rsolid"
        )
        self.assertIn("selection_query", fillet_node["params"])
        self.assertEqual(
            fillet_node["params"]["selection_query"]["target_kind"], "edge"
        )

        restored = import_graph_json(json.dumps(payload))
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Solid)
        self.assertAlmostEqual(results[0].get_volume(), filleted.get_volume(), places=5)

    def test_replay_chamfer_roundtrip_with_traversal_selector(self):
        with scad.GraphSession() as session:
            box = scad.make_box_rsolid(2.0, 3.0, 4.0)
            selector = (
                scad.ql.faces()
                .where(scad.ql.prop("geom.normal.z", ">", 0.9))
                .order_by(scad.ql.key("geom.center.z"), desc=True)
                .take(1)
                .exactly(1)
                .boundary("wire")
                .where(scad.ql.prop("topo.loop_role", "==", "outer"))
                .take(1)
                .exactly(1)
                .boundary("edge")
                .exactly(4)
            )
            chamfered = scad.chamfer_rsolid(box, selector, 0.15)

        payload = json.loads(export_graph_json(session.graph))
        chamfer_node = next(
            node for node in payload["nodes"] if node["op"] == "make_chamfer_rsolid"
        )
        self.assertIn("selection_query", chamfer_node["params"])
        self.assertEqual(
            chamfer_node["params"]["selection_query"]["traversal"]["relation"],
            "boundary",
        )
        self.assertEqual(
            chamfer_node["params"]["selection_query"]["source"]["traversal"][
                "relation"
            ],
            "boundary",
        )

        restored = import_graph_json(json.dumps(payload))
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Solid)
        self.assertAlmostEqual(
            results[0].get_volume(), chamfered.get_volume(), places=5
        )

    def test_replay_mirror_roundtrip(self):
        with scad.GraphSession() as session:
            box = scad.make_box_rsolid(2.0, 3.0, 4.0)
            mirrored = scad.mirror_shape(box, (0, 0, 0), (1, 0, 0))

        restored = import_graph_json(export_graph_json(session.graph))
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Solid)
        self.assertAlmostEqual(results[0].get_volume(), mirrored.get_volume(), places=5)

    def test_replay_sweep_roundtrip(self):
        with scad.GraphSession() as session:
            profile = scad.make_circle_rface((0, 0, 0), 0.5)
            path = scad.make_segment_rwire((0, 0, 0), (0, 0, 3.0))
            swept = scad.sweep_rsolid(profile, path)

        restored = import_graph_json(export_graph_json(session.graph))
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Solid)
        self.assertAlmostEqual(results[0].get_volume(), swept.get_volume(), places=5)

    def test_replay_helical_sweep_roundtrip(self):
        with scad.GraphSession() as session:
            profile = scad.make_rectangle_rwire(0.4, 0.2)
            swept = scad.helical_sweep_rsolid(
                profile, pitch=1.0, height=2.0, radius=1.0
            )

        restored = import_graph_json(export_graph_json(session.graph))
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Solid)
        self.assertAlmostEqual(results[0].get_volume(), swept.get_volume(), places=4)

    def test_replay_linear_pattern_roundtrip(self):
        with scad.GraphSession() as session:
            box = scad.make_box_rsolid(1.0, 1.0, 1.0)
            pattern = scad.linear_pattern_rsolidlist(box, (1, 0, 0), 4, 1.5)

        restored = import_graph_json(export_graph_json(session.graph))
        results = replay_graph(restored)

        self.assertEqual(len(results), 4)
        self.assertTrue(all(isinstance(shape, scad.Solid) for shape in results))
        self.assertAlmostEqual(
            sum(s.get_volume() for s in results),
            sum(s.get_volume() for s in pattern),
            places=5,
        )

    def test_replay_radial_pattern_roundtrip(self):
        with scad.GraphSession() as session:
            box = scad.make_box_rsolid(1.0, 1.0, 1.0)
            pattern = scad.radial_pattern_rsolidlist(
                box, (0, 0, 0), (0, 0, 1), 4, 360.0
            )

        restored = import_graph_json(export_graph_json(session.graph))
        results = replay_graph(restored)

        self.assertEqual(len(results), 4)
        self.assertTrue(all(isinstance(shape, scad.Solid) for shape in results))
        self.assertAlmostEqual(
            sum(s.get_volume() for s in results),
            sum(s.get_volume() for s in pattern),
            places=5,
        )

    def test_replay_field_surface_roundtrip_from_scalar_field_tree(self):
        sphere = scad.field.make_sphere_rscalarfield((0.0, 0.0, 0.0), 1.4)
        capsule = scad.field.make_capsule_rscalarfield(
            (-0.5, 0.0, -0.8), (0.8, 0.0, 0.9), 0.35
        )
        box = scad.field.translate_rscalarfield(
            scad.field.make_box_rscalarfield((0.0, 0.0, 0.0), (1.0, 0.9, 0.9)),
            (0.45, 0.0, 0.0),
        )
        field = scad.field.smooth_subtract_rscalarfield(
            scad.field.union_rscalarfield(sphere, capsule),
            box,
            0.12,
        )

        with scad.GraphSession() as session:
            solid = scad.make_field_surface_rsolid(
                field, resolution=(14, 14, 14), iso=0.0
            )

        restored = import_graph_json(export_graph_json(session.graph))
        results = replay_graph(restored)

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], scad.Solid)
        self.assertAlmostEqual(results[0].get_volume(), solid.get_volume(), places=4)

    def test_replay_field_surface_from_callable_raises_clear_error(self):
        def sphere_fn(x, y, z):
            return (x**2 + y**2 + z**2) ** 0.5 - 1.0

        with scad.GraphSession() as session:
            scad.make_field_surface_rsolid(
                sphere_fn,
                bounds=((-2.0, -2.0, -2.0), (2.0, 2.0, 2.0)),
                resolution=(10, 10, 10),
                iso=0.0,
            )

        restored = import_graph_json(export_graph_json(session.graph))
        with self.assertRaises(ValueError):
            replay_graph(restored)


if __name__ == "__main__":
    unittest.main()
