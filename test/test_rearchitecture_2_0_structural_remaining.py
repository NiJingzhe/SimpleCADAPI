"""TDD coverage for the remaining structural 2.0 items."""

from __future__ import annotations

import json
import unittest
import simplecadapi as scad
from simplecadapi.graph import GraphSession


class TestRemainingStructuralKernel(unittest.TestCase):
    def test_curve_builders_return_ocp_wrapped_shapes(self):
        shapes = [
            scad.make_line_redge((0, 0, 0), (1, 0, 0)),
            scad.make_circle_redge((0, 0, 0), 1.0),
            scad.make_three_point_arc_redge((0, 0, 0), (1, 1, 0), (2, 0, 0)),
            scad.make_angle_arc_redge((0, 0, 0), 1.0, 0.0, 1.57),
            scad.make_spline_redge([(0, 0, 0), (1, 1, 0), (2, 0, 0)]),
            scad.make_helix_rwire(1.0, 3.0, 0.5),
        ]
        for shape in shapes:
            self.assertTrue(hasattr(shape, "wrapped"))
            self.assertFalse(hasattr(shape, "cq_edge"))
            self.assertFalse(hasattr(shape, "cq_wire"))

    def test_loft_sweep_and_helical_sweep_do_not_depend_on_cadquery_feature_builders(
        self,
    ):
        rect1 = scad.make_rectangle_rwire(2.0, 2.0, center=(0, 0, 0))
        rect2 = scad.make_rectangle_rwire(1.0, 1.0, center=(0, 0, 2.0))
        profile = scad.make_circle_rface((0, 0, 0), 0.5)
        path = scad.make_segment_rwire((0, 0, 0), (0, 0, 3.0))
        helix_profile = scad.make_rectangle_rwire(0.4, 0.2)

        loft = scad.loft_rsolid([rect1, rect2])
        sweep = scad.sweep_rsolid(profile, path)
        helical = scad.helical_sweep_rsolid(
            helix_profile, pitch=1.0, height=2.0, radius=1.0
        )
        for solid in (loft, sweep, helical):
            self.assertIsInstance(solid, scad.Solid)
            self.assertTrue(hasattr(solid, "wrapped"))
            self.assertFalse(hasattr(solid, "cq_solid"))


class TestRemainingStructuralSemanticAndFrame(unittest.TestCase):
    def test_semantic_delta_uses_higher_level_entity_types(self):
        with GraphSession() as session:
            face = scad.make_circle_rface((0, 0, 0), 2.0)
            scad.extrude_rsolid(face, (0, 0, 1), 3.0)

        nodes = session.graph.topological_order()
        created_entity_types = {
            ref.entity_type
            for node in nodes
            if node.semantic_delta is not None
            for ref in node.semantic_delta.created
        }
        self.assertIn("Sketch", created_entity_types)
        self.assertIn("Feature", created_entity_types)
        self.assertNotEqual(created_entity_types, {"ShapeOutput"})

    def test_graph_session_owns_independent_frame_graph(self):
        with GraphSession() as session:
            with scad.SimpleWorkplane(origin=(1.0, 2.0, 3.0)):
                scad.make_point_rvertex(1.0, 0.0, 0.0)

        self.assertTrue(hasattr(session, "frame_graph"))
        self.assertGreaterEqual(session.frame_graph.node_count, 1)

    def test_session_and_model_export_include_frame_graph(self):
        with GraphSession() as session:
            with scad.SimpleWorkplane(origin=(1.0, 2.0, 3.0)):
                scad.make_point_rvertex(1.0, 0.0, 0.0)

        session_payload = scad.import_session_json(scad.export_session_json(session))
        self.assertIn("frame_graph", session_payload)
        self.assertGreaterEqual(session_payload["frame_graph"].node_count, 1)

        model_payload = scad.import_model_json(scad.export_model_json(session))
        self.assertIn("frame_graph", model_payload)
        self.assertGreaterEqual(model_payload["frame_graph"].node_count, 1)

        raw_model = json.loads(scad.export_model_json(session))
        self.assertIn("frame_graph", raw_model)
        self.assertGreaterEqual(len(raw_model["frame_graph"]["nodes"]), 1)

    def test_model_export_merges_assembly_part_frames_into_frame_graph(self):
        a = scad.make_box_rsolid(1.0, 1.0, 1.0)
        b = scad.make_box_rsolid(1.0, 1.0, 1.0)
        asm = scad.make_assembly_rassembly([("a", a), ("b", b)])
        asm = scad.translate_part_rassembly(asm, "b", (5.0, 0.0, 0.0), frame="world")

        with GraphSession() as session:
            scad.make_circle_rface((0.0, 0.0, 0.0), 2.0)

        payload = scad.import_model_json(scad.export_model_json(session, assembly=asm))
        self.assertIn("frame_graph", payload)
        frame_nodes = payload["frame_graph"].to_dict()["nodes"]
        frame_ids = {node["frame_id"] for node in frame_nodes}
        self.assertIn("assembly:assembly", frame_ids)
        self.assertIn("assembly:assembly:part:a", frame_ids)
        self.assertIn("assembly:assembly:part:b", frame_ids)

    def test_model_export_includes_semantic_entity_registry_for_sketch_feature_and_constraints(
        self,
    ):
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
            face = scad.make_circle_rface((0.0, 0.0, 0.0), 2.0)
            scad.extrude_rsolid(face, (0.0, 0.0, 1.0), 3.0)

        raw = json.loads(scad.export_model_json(session, assembly=asm))
        self.assertIn("semantic_entity_registry", raw)
        entity_types = {item["entity_type"] for item in raw["semantic_entity_registry"]}
        self.assertIn("Sketch", entity_types)
        self.assertIn("Feature", entity_types)
        self.assertIn("AssemblyConstraint", entity_types)


class TestHelicalSweepMacroRecording(unittest.TestCase):
    def test_helical_sweep_expands_to_helix_plus_sweep_nodes(self):
        with GraphSession() as session:
            profile = scad.make_rectangle_rwire(0.4, 0.2)
            result = scad.helical_sweep_rsolid(
                profile, pitch=1.0, height=2.0, radius=1.0
            )

        self.assertIsInstance(result, scad.Solid)
        ops = [node.op for node in session.graph.topological_order()]
        self.assertIn("make_helix_redge", ops)
        self.assertIn("make_wire_from_edges_rwire", ops)
        self.assertIn("make_sweep_rsolid", ops)
        self.assertNotIn("helical_sweep", ops)

    def test_helical_sweep_roundtrip_replays_as_macro_graph(self):
        with GraphSession() as session:
            profile = scad.make_rectangle_rwire(0.4, 0.2)
            swept = scad.helical_sweep_rsolid(
                profile, pitch=1.0, height=2.0, radius=1.0
            )

        restored = scad.import_graph_json(scad.export_graph_json(session.graph))
        ops = [node.op for node in restored.topological_order()]

        self.assertIn("make_helix_redge", ops)
        self.assertIn("make_wire_from_edges_rwire", ops)
        self.assertIn("make_sweep_rsolid", ops)
        self.assertNotIn("helical_sweep", ops)

        replayed = scad.replay_graph(restored)
        self.assertEqual(len(replayed), 1)
        self.assertAlmostEqual(replayed[0].get_volume(), swept.get_volume(), places=4)


if __name__ == "__main__":
    unittest.main()
