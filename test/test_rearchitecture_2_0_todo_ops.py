"""TDD coverage for remaining Phase 1 expressionized primitive/profile APIs."""

from __future__ import annotations

import unittest

import simplecadapi as scad
from simplecadapi.graph import GraphSession


class TestRemainingPrimitiveProfileExpressionSupport(unittest.TestCase):
    def test_point_accepts_expression_coordinates_and_records_param_exprs(self):
        x = scad.var("px", 1.0)
        y = scad.var("py", 2.0)

        with GraphSession() as session:
            point = scad.make_point_rvertex(x, y, 3.0)

        self.assertIsInstance(point, scad.Vertex)
        leaf = session.graph.leaf_nodes()[0]
        self.assertIn("x", leaf.param_exprs)
        self.assertIn("y", leaf.param_exprs)

    def test_line_accepts_expression_points_and_records_param_exprs(self):
        x = scad.var("lx", 2.0)

        with GraphSession() as session:
            edge = scad.make_line_redge((0.0, 0.0, 0.0), (x, 0.0, 0.0))

        self.assertIsInstance(edge, scad.Edge)
        leaf = session.graph.leaf_nodes()[0]
        self.assertIn("end", leaf.param_exprs)

    def test_rectangle_wire_accepts_expression_dimensions_and_records_param_exprs(self):
        w = scad.var("rw", 3.0)
        h = scad.var("rh", 2.0)

        with GraphSession() as session:
            wire = scad.make_rectangle_rwire(w, h)

        self.assertIsInstance(wire, scad.Wire)
        ops = session.graph.topological_order()
        self.assertTrue(any(node.op == "make_line_redge" for node in ops))
        self.assertTrue(any(node.op == "make_wire_from_edges_rwire" for node in ops))
        line_nodes = [node for node in ops if node.op == "make_line_redge"]
        self.assertTrue(
            any(
                "start" in node.param_exprs or "end" in node.param_exprs
                for node in line_nodes
            )
        )

    def test_polyline_accepts_expression_points_and_records_param_exprs(self):
        y = scad.var("ply", 1.0)

        with GraphSession() as session:
            wire = scad.make_polyline_rwire(
                [(0.0, 0.0, 0.0), (1.0, y, 0.0), (2.0, 0.0, 0.0)],
                closed=False,
            )

        self.assertIsInstance(wire, scad.Wire)
        ops = session.graph.topological_order()
        line_nodes = [node for node in ops if node.op == "make_line_redge"]
        self.assertGreaterEqual(len(line_nodes), 2)
        self.assertTrue(
            any(
                "start" in node.param_exprs or "end" in node.param_exprs
                for node in line_nodes
            )
        )


if __name__ == "__main__":
    unittest.main()
