"""Focused 2.0 operation-level tests for remaining core operations."""

from __future__ import annotations

import unittest

import simplecadapi as scad
from simplecadapi.graph import GraphSession


class TestRearchitecture20CoreOps(unittest.TestCase):
    def test_cylinder_accepts_expression_parameters(self):
        r = scad.var("r", 1.5)
        h = scad.var("h", 4.0)
        solid = scad.make_cylinder_rsolid(r, h, bottom_face_center=(0, 0, 0))
        self.assertIsInstance(solid, scad.Solid)
        self.assertGreater(solid.get_volume(), 0.0)

    def test_revolve_accepts_expression_angle(self):
        angle = scad.var("angle", 180.0)
        face = scad.make_rectangle_rface(1.0, 2.0, center=(1.0, 0.0, 0.0))
        solid = scad.revolve_rsolid(face, axis=(0, 1, 0), angle=angle, origin=(0, 0, 0))
        self.assertIsInstance(solid, scad.Solid)

    def test_revolve_produces_topology_delta_at_runtime(self):
        face = scad.make_rectangle_rface(1.0, 2.0, center=(1.0, 0.0, 0.0))
        with GraphSession() as session:
            solid = scad.revolve_rsolid(
                face, axis=(0, 1, 0), angle=180.0, origin=(0, 0, 0)
            )

        self.assertIsInstance(solid, scad.Solid)
        leaf = session.graph.leaf_nodes()[0]
        self.assertEqual(leaf.op, "make_revolve_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_revolve_topology_delta_survives_graph_json_roundtrip(self):
        face = scad.make_rectangle_rface(1.0, 2.0, center=(1.0, 0.0, 0.0))
        with GraphSession() as session:
            scad.revolve_rsolid(face, axis=(0, 1, 0), angle=180.0, origin=(0, 0, 0))

        restored = scad.import_graph_json(scad.export_graph_json(session.graph))
        leaf = restored.leaf_nodes()[0]

        self.assertEqual(leaf.op, "make_revolve_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_loft_produces_topology_delta_at_runtime(self):
        a = scad.make_rectangle_rwire(2.0, 2.0, center=(0.0, 0.0, 0.0))
        b = scad.make_rectangle_rwire(1.0, 1.0, center=(0.0, 0.0, 2.0))
        with GraphSession() as session:
            solid = scad.loft_rsolid([a, b])

        self.assertIsInstance(solid, scad.Solid)
        leaf = session.graph.leaf_nodes()[0]
        self.assertEqual(leaf.op, "make_loft_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_loft_topology_delta_survives_graph_json_roundtrip(self):
        a = scad.make_rectangle_rwire(2.0, 2.0, center=(0.0, 0.0, 0.0))
        b = scad.make_rectangle_rwire(1.0, 1.0, center=(0.0, 0.0, 2.0))
        with GraphSession() as session:
            scad.loft_rsolid([a, b])

        restored = scad.import_graph_json(scad.export_graph_json(session.graph))
        leaf = restored.leaf_nodes()[0]

        self.assertEqual(leaf.op, "make_loft_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_sweep_produces_topology_delta_at_runtime(self):
        profile = scad.make_circle_rface((0.0, 0.0, 0.0), 0.5)
        path = scad.make_segment_rwire((0.0, 0.0, 0.0), (0.0, 0.0, 3.0))
        with GraphSession() as session:
            solid = scad.sweep_rsolid(profile, path)

        self.assertIsInstance(solid, scad.Solid)
        leaf = session.graph.leaf_nodes()[0]
        self.assertEqual(leaf.op, "make_sweep_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_sweep_topology_delta_survives_graph_json_roundtrip(self):
        profile = scad.make_circle_rface((0.0, 0.0, 0.0), 0.5)
        path = scad.make_segment_rwire((0.0, 0.0, 0.0), (0.0, 0.0, 3.0))
        with GraphSession() as session:
            scad.sweep_rsolid(profile, path)

        restored = scad.import_graph_json(scad.export_graph_json(session.graph))
        leaf = restored.leaf_nodes()[0]

        self.assertEqual(leaf.op, "make_sweep_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_fillet_accepts_expression_radius_and_records_param_expr(self):
        radius = scad.var("fillet_r", 0.2)
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            result = scad.fillet_rsolid(box, box.get_edges()[:4], radius)

        self.assertIsInstance(result, scad.Solid)
        leaf = session.graph.leaf_nodes()[0]
        self.assertEqual(leaf.op, "make_fillet_rsolid")
        self.assertIn("radius", leaf.param_exprs)

    def test_chamfer_accepts_expression_distance_and_records_param_expr(self):
        distance = scad.var("chamfer_d", 0.2)
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            result = scad.chamfer_rsolid(box, box.get_edges()[:4], distance)

        self.assertIsInstance(result, scad.Solid)
        leaf = session.graph.leaf_nodes()[0]
        self.assertEqual(leaf.op, "make_chamfer_rsolid")
        self.assertIn("distance", leaf.param_exprs)

    def test_shell_accepts_expression_thickness_and_records_param_expr(self):
        thickness = scad.var("shell_t", 0.2)
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            result = scad.shell_rsolid(box, [box.get_faces()[0]], thickness)

        self.assertIsInstance(result, scad.Solid)
        leaf = session.graph.leaf_nodes()[0]
        self.assertEqual(leaf.op, "make_shell_rsolid")
        self.assertIn("thickness", leaf.param_exprs)

    def test_shell_produces_topology_delta_at_runtime(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            result = scad.shell_rsolid(box, [box.get_faces()[0]], 0.2)

        self.assertIsInstance(result, scad.Solid)
        leaf = session.graph.leaf_nodes()[0]
        self.assertEqual(leaf.op, "make_shell_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_shell_topology_delta_survives_graph_json_roundtrip(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            scad.shell_rsolid(box, [box.get_faces()[0]], 0.2)

        restored = scad.import_graph_json(scad.export_graph_json(session.graph))
        leaf = restored.leaf_nodes()[0]

        self.assertEqual(leaf.op, "make_shell_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )


if __name__ == "__main__":
    unittest.main()
