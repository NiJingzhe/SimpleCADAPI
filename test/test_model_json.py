"""Focused tests for canonical 2.0 model JSON export."""

from __future__ import annotations

import json
import unittest

import simplecadapi as scad
from simplecadapi.graph import GraphSession


class TestModelJson(unittest.TestCase):
    def test_model_json_contains_graph_and_expression_graph(self):
        r = scad.var("r", 2.0)
        with GraphSession() as session:
            scad.make_circle_rface((0, 0, 0), r)

        payload = scad.import_model_json(scad.export_model_json(session))

        self.assertIn("graph", payload)
        self.assertIn("expression_graph", payload)
        self.assertIn("canonical_contract", payload)
        self.assertGreaterEqual(payload["graph"].node_count, 1)
        self.assertGreaterEqual(payload["expression_graph"].node_count, 1)

    def test_model_json_declares_canonical_contract_and_graph_roles(self):
        with GraphSession() as session:
            scad.make_box_rsolid(1.0, 2.0, 3.0)

        payload = scad.import_model_json(scad.export_model_json(session))

        self.assertIn("canonical_contract", payload)
        contract = payload["canonical_contract"]
        self.assertEqual(contract["contract_version"], "2.0-final-state")
        self.assertEqual(contract["graph_roles"]["graph"], "canonical_low_level_graph")
        self.assertEqual(contract["graph_roles"]["leaf_ids"], "explicit_result_set")
        self.assertEqual(contract["replay_policy"]["preferred_graph"], "graph")
        self.assertIn("core_op_set", contract)
        self.assertGreaterEqual(len(contract["core_op_set"]), 1)

    def test_model_json_includes_geometry_and_delta_registries(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(2.0, 3.0, 4.0)
            scad.translate_shape(box, (1.0, 0.0, 0.0))

        payload = json.loads(scad.export_model_json(session))

        self.assertIn("geometry_registry", payload)
        self.assertIn("semantic_delta_log", payload)
        self.assertIn("topology_delta_log", payload)
        self.assertGreaterEqual(len(payload["geometry_registry"]), 1)
        self.assertGreaterEqual(len(payload["semantic_delta_log"]), 1)

    def test_model_json_includes_sketch_assembly_and_constraint_registries(self):
        a = scad.make_box_rsolid(1.0, 1.0, 1.0)
        b = scad.make_box_rsolid(1.0, 1.0, 1.0)
        asm = scad.make_assembly_rassembly([("a", a), ("b", b)])
        asm = scad.constrain_offset_rassembly(
            asm,
            asm.part("a").anchor("bbox.top"),
            asm.part("b").anchor("bbox.bottom"),
            scad.var("gap", 2.0),
            axis="z",
        )

        with GraphSession() as session:
            face = scad.make_circle_rface((0, 0, 0), scad.var("r", 2.0))
            scad.extrude_rsolid(face, (0, 0, 1), 3.0)

        payload = json.loads(scad.export_model_json(session, assembly=asm))

        self.assertIn("sketch_profile_registry", payload)
        self.assertIn("assembly_registry", payload)
        self.assertIn("constraint_registry", payload)
        self.assertGreaterEqual(len(payload["sketch_profile_registry"]), 1)
        self.assertGreaterEqual(len(payload["assembly_registry"]), 1)
        self.assertGreaterEqual(len(payload["constraint_registry"]), 1)

    def test_model_json_import_preserves_registry_payloads(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(2.0, 3.0, 4.0)
            scad.translate_shape(box, (1.0, 0.0, 0.0))

        payload = scad.import_model_json(scad.export_model_json(session))

        self.assertIn("geometry_registry", payload)
        self.assertIn("canonical_contract", payload)
        self.assertIn("semantic_delta_log", payload)
        self.assertIn("topology_delta_log", payload)
        self.assertGreaterEqual(len(payload["geometry_registry"]), 1)

    def test_model_json_import_preserves_extended_registries(self):
        a = scad.make_box_rsolid(1.0, 1.0, 1.0)
        b = scad.make_box_rsolid(1.0, 1.0, 1.0)
        asm = scad.make_assembly_rassembly([("a", a), ("b", b)])
        asm = scad.constrain_offset_rassembly(
            asm,
            asm.part("a").anchor("bbox.top"),
            asm.part("b").anchor("bbox.bottom"),
            2.0,
            axis="z",
        )

        with GraphSession() as session:
            face = scad.make_circle_rface((0, 0, 0), 2.0)
            scad.extrude_rsolid(face, (0, 0, 1), 3.0)

        payload = scad.import_model_json(scad.export_model_json(session, assembly=asm))

        self.assertIn("sketch_profile_registry", payload)
        self.assertIn("assembly_registry", payload)
        self.assertIn("constraint_registry", payload)
        self.assertGreaterEqual(len(payload["sketch_profile_registry"]), 1)
        self.assertGreaterEqual(len(payload["assembly_registry"]), 1)
        self.assertGreaterEqual(len(payload["constraint_registry"]), 1)

    def test_model_json_graph_contains_only_low_level_ops(self):
        with GraphSession() as session:
            profile = scad.make_rectangle_rwire(0.4, 0.2)
            scad.helical_sweep_rsolid(profile, pitch=1.0, height=2.0, radius=1.0)

        payload = json.loads(scad.export_model_json(session))

        self.assertIn("graph", payload)
        core_ops = [node["op"] for node in payload["graph"]["nodes"]]
        self.assertIn("make_helix_redge", core_ops)
        self.assertIn("make_wire_from_edges_rwire", core_ops)
        self.assertIn("make_sweep_rsolid", core_ops)
        self.assertNotIn("helical_sweep", core_ops)

    def test_model_json_can_replay_without_graph_json_api(self):
        with GraphSession() as session:
            face = scad.make_circle_rface((0, 0, 0), 1.2)
            original = scad.extrude_rsolid(face, (0, 0, 1), 2.5)

        replayed = scad.replay_model_json(scad.export_model_json(session))

        self.assertEqual(len(replayed), 1)
        self.assertIsInstance(replayed[0], scad.Solid)
        self.assertAlmostEqual(
            replayed[0].get_volume(), original.get_volume(), places=5
        )

    def test_model_json_replay_uses_single_low_level_graph_for_macro_ops(self):
        with GraphSession() as session:
            profile = scad.make_rectangle_rwire(0.4, 0.2)
            original = scad.helical_sweep_rsolid(
                profile, pitch=1.0, height=2.0, radius=1.0
            )

        replayed = scad.replay_model_json(scad.export_model_json(session))

        self.assertEqual(len(replayed), 1)
        self.assertIsInstance(replayed[0], scad.Solid)
        self.assertAlmostEqual(
            replayed[0].get_volume(), original.get_volume(), places=4
        )

    def test_graph_lowers_make_box_to_profile_plus_extrude(self):
        with GraphSession() as session:
            scad.make_box_rsolid(2.0, 3.0, 4.0, bottom_face_center=(1.0, 2.0, 3.0))

        payload = json.loads(scad.export_model_json(session))
        core_ops = [node["op"] for node in payload["graph"]["nodes"]]

        self.assertIn("make_line_redge", core_ops)
        self.assertIn("make_wire_from_edges_rwire", core_ops)
        self.assertIn("make_face_from_wire_rface", core_ops)
        self.assertIn("make_extrude_rsolid", core_ops)
        self.assertNotIn("make_box", core_ops)

    def test_graph_lowers_make_circle_face_to_wire_plus_face(self):
        with GraphSession() as session:
            scad.make_circle_rface((0.0, 0.0, 0.0), 2.0)

        payload = json.loads(scad.export_model_json(session))
        core_ops = [node["op"] for node in payload["graph"]["nodes"]]

        self.assertIn("make_circle_redge", core_ops)
        self.assertIn("make_wire_from_edges_rwire", core_ops)
        self.assertIn("make_face_from_wire_rface", core_ops)
        self.assertNotIn("make_circle_face", core_ops)

    def test_graph_lowers_make_cylinder_to_circle_face_plus_extrude(self):
        with GraphSession() as session:
            scad.make_cylinder_rsolid(1.0, 3.0, bottom_face_center=(0.0, 0.0, 0.0))

        payload = json.loads(scad.export_model_json(session))
        core_ops = [node["op"] for node in payload["graph"]["nodes"]]

        self.assertIn("make_circle_redge", core_ops)
        self.assertIn("make_wire_from_edges_rwire", core_ops)
        self.assertIn("make_face_from_wire_rface", core_ops)
        self.assertIn("make_extrude_rsolid", core_ops)
        self.assertNotIn("make_cylinder", core_ops)

    def test_graph_lowers_rectangle_face_further_to_wire_plus_face(self):
        with GraphSession() as session:
            scad.make_box_rsolid(2.0, 3.0, 4.0)

        payload = json.loads(scad.export_model_json(session))
        core_ops = [node["op"] for node in payload["graph"]["nodes"]]

        self.assertIn("make_line_redge", core_ops)
        self.assertIn("make_wire_from_edges_rwire", core_ops)
        self.assertIn("make_face_from_wire_rface", core_ops)
        self.assertNotIn("make_rectangle_face", core_ops)

    def test_graph_lowers_make_sphere_to_revolve_chain(self):
        with GraphSession() as session:
            scad.make_sphere_rsolid(2.0, center=(0.0, 0.0, 0.0))

        payload = json.loads(scad.export_model_json(session))
        core_ops = [node["op"] for node in payload["graph"]["nodes"]]

        self.assertIn("make_revolve_rsolid", core_ops)
        self.assertIn("make_line_redge", core_ops)
        self.assertIn("make_wire_from_edges_rwire", core_ops)
        self.assertIn("make_face_from_wire_rface", core_ops)
        self.assertNotIn("make_polyline_wire", core_ops)
        self.assertNotIn("make_sphere", core_ops)

    def test_graph_lowers_make_cone_to_revolve_chain(self):
        with GraphSession() as session:
            scad.make_cone_rsolid(2.0, 4.0, top_radius=0.5)

        payload = json.loads(scad.export_model_json(session))
        core_ops = [node["op"] for node in payload["graph"]["nodes"]]

        self.assertIn("make_revolve_rsolid", core_ops)
        self.assertIn("make_line_redge", core_ops)
        self.assertIn("make_wire_from_edges_rwire", core_ops)
        self.assertIn("make_face_from_wire_rface", core_ops)
        self.assertNotIn("make_polyline_wire", core_ops)
        self.assertNotIn("make_cone", core_ops)

    def test_graph_lowers_rectangle_wire_to_lines_plus_wire_assembly(self):
        with GraphSession() as session:
            scad.make_rectangle_rwire(2.0, 3.0)

        payload = json.loads(scad.export_model_json(session))
        core_ops = [node["op"] for node in payload["graph"]["nodes"]]

        self.assertIn("make_line_redge", core_ops)
        self.assertIn("make_wire_from_edges_rwire", core_ops)
        self.assertNotIn("make_rectangle_wire", core_ops)

    def test_graph_lowers_circle_wire_to_edge_plus_wire_assembly(self):
        with GraphSession() as session:
            scad.make_circle_rwire((0.0, 0.0, 0.0), 2.0)

        payload = json.loads(scad.export_model_json(session))
        core_ops = [node["op"] for node in payload["graph"]["nodes"]]

        self.assertIn("make_circle_redge", core_ops)
        self.assertIn("make_wire_from_edges_rwire", core_ops)
        self.assertNotIn("make_circle_wire", core_ops)

    def test_graph_lowers_linear_pattern_to_explicit_transforms(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(1.0, 1.0, 1.0)
            scad.linear_pattern_rsolidlist(box, (1.0, 0.0, 0.0), 4, 1.5)

        payload = json.loads(scad.export_model_json(session))
        core_ops = [node["op"] for node in payload["graph"]["nodes"]]

        self.assertIn("make_translate_rshape", core_ops)
        self.assertNotIn("linear_pattern", core_ops)

    def test_graph_lowers_radial_pattern_to_explicit_rotates(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(1.0, 1.0, 1.0)
            scad.radial_pattern_rsolidlist(
                box, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 4, 360.0
            )

        payload = json.loads(scad.export_model_json(session))
        core_ops = [node["op"] for node in payload["graph"]["nodes"]]

        self.assertIn("make_rotate_rshape", core_ops)
        self.assertNotIn("radial_pattern", core_ops)

    def test_graph_lowers_remaining_wire_convenience_ops(self):
        with GraphSession() as session:
            scad.make_polyline_rwire(
                [(0.0, 0.0, 0.0), (1.0, 0.2, 0.0), (2.0, 0.0, 0.0)]
            )
            scad.make_segment_rwire((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
            scad.make_three_point_arc_rwire(
                (0.0, 0.0, 0.0), (1.0, 1.0, 0.0), (2.0, 0.0, 0.0)
            )
            scad.make_angle_arc_rwire((0.0, 0.0, 0.0), 1.0, 0.0, 1.57)
            scad.make_spline_rwire([(0.0, 0.0, 0.0), (1.0, 1.0, 0.0), (2.0, 0.0, 0.0)])
            scad.make_helix_rwire(1.0, 2.0, 0.8)

        payload = json.loads(scad.export_model_json(session))
        core_ops = [node["op"] for node in payload["graph"]["nodes"]]

        self.assertIn("make_line_redge", core_ops)
        self.assertIn("make_three_point_arc_redge", core_ops)
        self.assertIn("make_angle_arc_redge", core_ops)
        self.assertIn("make_spline_redge", core_ops)
        self.assertIn("make_helix_redge", core_ops)
        self.assertIn("make_wire_from_edges_rwire", core_ops)
        self.assertNotIn("make_polyline_wire", core_ops)
        self.assertNotIn("make_segment_wire", core_ops)
        self.assertNotIn("make_three_point_arc_wire", core_ops)
        self.assertNotIn("make_angle_arc_wire", core_ops)
        self.assertNotIn("make_spline_wire", core_ops)
        self.assertNotIn("make_helix_wire", core_ops)

    def test_graph_preserves_explicit_selected_refs_for_detail_features(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            scad.fillet_rsolid(box, box.get_edges()[:2], 0.3)

        payload = json.loads(scad.export_model_json(session))
        fillet_nodes = [
            node
            for node in payload["graph"]["nodes"]
            if node["op"] == "make_fillet_rsolid"
        ]

        self.assertEqual(len(fillet_nodes), 1)
        fillet_params = fillet_nodes[0]["params"]
        self.assertIn("selected_edges", fillet_params)
        self.assertGreaterEqual(len(fillet_params["selected_edges"]), 1)
        self.assertIn("topo_id", fillet_params["selected_edges"][0])

    def test_graph_ops_stay_within_declared_canonical_op_set(self):
        with GraphSession() as session:
            scad.make_box_rsolid(2.0, 3.0, 4.0)
            scad.make_cylinder_rsolid(1.0, 3.0)
            scad.make_sphere_rsolid(1.5)
            profile = scad.make_rectangle_rwire(0.4, 0.2)
            scad.helical_sweep_rsolid(profile, pitch=1.0, height=2.0, radius=1.0)

        payload = json.loads(scad.export_model_json(session))
        contract = payload["canonical_contract"]
        core_ops = {node["op"] for node in payload["graph"]["nodes"]}

        self.assertTrue(core_ops.issubset(set(contract["core_op_set"])))
        self.assertNotIn("make_box", core_ops)
        self.assertNotIn("make_cylinder", core_ops)
        self.assertNotIn("make_sphere", core_ops)
        self.assertNotIn("helical_sweep", core_ops)
        self.assertNotIn("make_polyline_wire", core_ops)

    def test_graph_selection_refs_follow_declared_schema(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            scad.fillet_rsolid(box, box.get_edges()[:2], 0.3)

        payload = json.loads(scad.export_model_json(session))
        contract = payload["canonical_contract"]
        selection_schema = contract["selection_ref_schema"]
        fillet_node = next(
            node
            for node in payload["graph"]["nodes"]
            if node["op"] == "make_fillet_rsolid"
        )
        selected_edge_ref = fillet_node["params"]["selected_edges"][0]

        self.assertEqual(
            selection_schema["replay_resolution_order"],
            [
                "explicit_topo_refs",
                "stable_indices",
                "selection_query",
                "selector_hint",
            ],
        )
        self.assertEqual(selection_schema["edge_param"], "selected_edges")
        self.assertEqual(selection_schema["face_param"], "selected_faces")
        self.assertTrue(
            set(selection_schema["required_topo_ref_fields"]).issubset(
                selected_edge_ref.keys()
            )
        )
        self.assertEqual(selected_edge_ref["kind"], "EDGE")
        self.assertIn("selector_hint", selected_edge_ref)

    def test_model_json_replay_prefers_selected_refs_over_selection_query(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            original = scad.fillet_rsolid(box, box.get_edges()[:4], 0.2)

        payload = json.loads(scad.export_model_json(session))
        fillet_node = next(
            node
            for node in payload["graph"]["nodes"]
            if node["op"] == "make_fillet_rsolid"
        )
        fillet_node["params"]["selection_query"] = (
            scad.ql.edges().take(1).exactly(1).to_dict()
        )

        replayed = scad.replay_model_json(json.dumps(payload))

        self.assertEqual(len(replayed), 1)
        self.assertIsInstance(replayed[0], scad.Solid)
        self.assertAlmostEqual(
            replayed[0].get_volume(), original.get_volume(), places=5
        )

    def test_model_json_replay_preserves_linear_pattern_multi_output(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(1.0, 1.0, 1.0)
            originals = scad.linear_pattern_rsolidlist(box, (1.0, 0.0, 0.0), 4, 1.5)

        replayed = scad.replay_model_json(scad.export_model_json(session))

        self.assertEqual(len(replayed), 4)
        self.assertAlmostEqual(
            sum(shape.get_volume() for shape in replayed),
            sum(shape.get_volume() for shape in originals),
            places=5,
        )

    def test_model_json_replay_preserves_radial_pattern_multi_output(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(1.0, 1.0, 1.0)
            originals = scad.radial_pattern_rsolidlist(
                box, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 4, 360.0
            )

        replayed = scad.replay_model_json(scad.export_model_json(session))

        self.assertEqual(len(replayed), 4)
        self.assertAlmostEqual(
            sum(shape.get_volume() for shape in replayed),
            sum(shape.get_volume() for shape in originals),
            places=5,
        )


class TestOperationGraphDeltaSerialization(unittest.TestCase):
    def test_graph_json_roundtrip_preserves_semantic_delta(self):
        with GraphSession() as session:
            scad.make_box_rsolid(1.0, 1.0, 1.0)

        restored = scad.import_graph_json(scad.export_graph_json(session.graph))
        leaf = restored.leaf_nodes()[0]

        self.assertIsNotNone(leaf.semantic_delta)
        self.assertGreaterEqual(len(leaf.semantic_delta.created), 1)

    def test_graph_json_roundtrip_preserves_topology_delta(self):
        with GraphSession() as session:
            body = scad.make_box_rsolid(4.0, 4.0, 4.0)
            tool = scad.make_cylinder_rsolid(
                0.75, 6.0, bottom_face_center=(0.0, 0.0, -1.0)
            )
            scad.cut_rsolidlist(body, tool)

        restored = scad.import_graph_json(scad.export_graph_json(session.graph))
        leaf = restored.leaf_nodes()[0]

        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_semantic_delta_created_refs_are_bound_to_real_graph_and_node_ids(self):
        with GraphSession() as session:
            scad.make_box_rsolid(1.0, 1.0, 1.0)

        leaf = session.graph.leaf_nodes()[0]
        self.assertIsNotNone(leaf.semantic_delta)
        self.assertGreaterEqual(len(leaf.semantic_delta.created), 1)

        for ref in leaf.semantic_delta.created:
            with self.subTest(ref=ref):
                self.assertEqual(ref.graph_id, session.graph.graph_id)
                self.assertEqual(ref.node_id, leaf.node_id)
                self.assertNotEqual(ref.graph_id, "pending")
                self.assertNotEqual(ref.node_id, "pending")


if __name__ == "__main__":
    unittest.main()
