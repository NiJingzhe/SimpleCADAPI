"""TDD coverage for remaining primitive/transform expression integration."""

from __future__ import annotations

import unittest

import simplecadapi as scad
from simplecadapi.graph import GraphSession


class TestRemainingPrimitiveExpressionSupport(unittest.TestCase):
    def test_cone_accepts_expression_parameters(self):
        r = scad.var("br", 2.0)
        h = scad.var("h", 5.0)
        solid = scad.make_cone_rsolid(r, h, top_radius=r / 2)
        self.assertIsInstance(solid, scad.Solid)

    def test_sphere_accepts_expression_radius_and_center(self):
        r = scad.var("sr", 2.0)
        x = scad.var("sx", 1.0)
        solid = scad.make_sphere_rsolid(r, center=(x, 0.0, 0.0))
        self.assertIsInstance(solid, scad.Solid)

    def test_three_point_arc_accepts_expression_points(self):
        x = scad.var("ax", 1.0)
        edge = scad.make_three_point_arc_redge(
            (0.0, 0.0, 0.0), (x, 1.0, 0.0), (2.0, 0.0, 0.0)
        )
        self.assertIsInstance(edge, scad.Edge)

    def test_angle_arc_accepts_expression_radius_and_angles(self):
        r = scad.var("ar", 2.0)
        start = scad.var("a0", 0.0)
        end = scad.var("a1", 1.57)
        edge = scad.make_angle_arc_redge((0.0, 0.0, 0.0), r, start, end)
        self.assertIsInstance(edge, scad.Edge)

    def test_spline_accepts_expression_points(self):
        y = scad.var("sy", 1.0)
        edge = scad.make_spline_redge([(0.0, 0.0, 0.0), (1.0, y, 0.0), (2.0, 0.0, 0.0)])
        self.assertIsInstance(edge, scad.Edge)


class TestRemainingTransformExpressionSupport(unittest.TestCase):
    def test_translate_accepts_expression_vector(self):
        dx = scad.var("dx", 1.0)
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        moved = scad.translate_shape(box, (dx, 0.0, 0.0))
        self.assertIsInstance(moved, scad.Solid)

    def test_rotate_accepts_expression_angle_and_axis(self):
        angle = scad.var("rot", 30.0)
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        moved = scad.rotate_shape(box, angle, (0.0, 0.0, 1.0))
        self.assertIsInstance(moved, scad.Solid)

    def test_mirror_accepts_expression_plane_origin(self):
        x = scad.var("mx", 0.0)
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        mirrored = scad.mirror_shape(box, (x, 0.0, 0.0), (1.0, 0.0, 0.0))
        self.assertIsInstance(mirrored, scad.Solid)


class TestSemanticDeltaProduction(unittest.TestCase):
    def test_operation_nodes_can_carry_semantic_delta_for_primitives(self):
        with GraphSession() as session:
            scad.make_box_rsolid(1.0, 1.0, 1.0)

        leaf = session.graph.leaf_nodes()[0]
        self.assertIsNotNone(leaf.semantic_delta)
        self.assertGreaterEqual(len(leaf.semantic_delta.created), 1)


if __name__ == "__main__":
    unittest.main()
