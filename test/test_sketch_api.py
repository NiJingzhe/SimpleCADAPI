"""Focused tests for declarative sketch construction and constraints."""

from __future__ import annotations

import unittest

import simplecadapi as scad


class TestSketchApi(unittest.TestCase):
    def test_sketch_accepts_wire_and_can_build_profile_faces(self):
        wire = scad.make_rectangle_rwire(2.0, 1.0)
        sketch = scad.Sketch([wire])

        self.assertEqual(len(sketch.curves()), 1)
        self.assertEqual(len(sketch.closed_wires()), 1)
        faces = sketch.to_faces()
        self.assertEqual(len(faces), 1)
        self.assertIsInstance(faces[0], scad.Face)

    def _make_constrained_rectangle(self):
        width = scad.var("sketch_width", 2.0)
        height = scad.var("sketch_height", 1.0)
        sketch = scad.make_sketch_rsketch("rect")
        p0 = scad.make_sketch_point_rsketchref(sketch, "p0", 0.0, 0.0)
        p1 = scad.make_sketch_point_rsketchref(sketch, "p1", 2.0, 0.0)
        p2 = scad.make_sketch_point_rsketchref(sketch, "p2", 2.0, 1.0)
        p3 = scad.make_sketch_point_rsketchref(sketch, "p3", 0.0, 1.0)
        sketch = scad.add_line_rsketch(sketch, "bottom", p0, p1)
        sketch = scad.add_line_rsketch(sketch, "right", p1, p2)
        sketch = scad.add_line_rsketch(sketch, "top", p2, p3)
        sketch = scad.add_line_rsketch(sketch, "left", p3, p0)
        bottom = scad.get_sketch_entity_rsketchref(sketch, "bottom")
        right = scad.get_sketch_entity_rsketchref(sketch, "right")
        top = scad.get_sketch_entity_rsketchref(sketch, "top")
        left = scad.get_sketch_entity_rsketchref(sketch, "left")
        sketch = scad.constrain_horizontal_rsketch(sketch, bottom)
        sketch = scad.constrain_vertical_rsketch(sketch, right)
        sketch = scad.constrain_parallel_rsketch(sketch, bottom, top)
        sketch = scad.constrain_parallel_rsketch(sketch, left, right)
        sketch = scad.constrain_perpendicular_rsketch(sketch, bottom, right)
        sketch = scad.constrain_equal_length_rsketch(sketch, bottom, top)
        sketch = scad.constrain_equal_length_rsketch(sketch, left, right)
        sketch = scad.constrain_distance_rsketch(sketch, p0, p1, width)
        sketch = scad.constrain_distance_rsketch(sketch, p0, p3, height)
        sketch = scad.constrain_fix_rsketch(sketch, p0)
        return sketch

    def test_isomorphic_sketch_api_solves_rectangle_and_builds_face(self):
        sketch = self._make_constrained_rectangle()

        result = scad.solve_sketch_rsketchresult(
            sketch, require_fully_constrained=True
        )
        self.assertEqual(result.status, "solved")
        self.assertEqual(result.dof, 0)
        self.assertAlmostEqual(result.residual_norm, 0.0, places=7)

        face = scad.make_face_from_sketch_rface(sketch)
        self.assertIsInstance(face, scad.Face)
        self.assertAlmostEqual(face.get_area(), 2.0, places=6)

    def test_circle_sketch_constraints_build_circular_face(self):
        sketch = scad.make_sketch_rsketch("circle")
        center = scad.make_sketch_point_rsketchref(sketch, "center", 0.0, 0.0)
        sketch = scad.add_circle_rsketch(sketch, "outer", center, 1.5)
        circle = scad.get_sketch_entity_rsketchref(sketch, "outer")
        sketch = scad.constrain_fix_rsketch(sketch, center)
        sketch = scad.constrain_radius_rsketch(sketch, circle, 1.5)

        result = scad.solve_sketch_rsketchresult(
            sketch, require_fully_constrained=True
        )
        self.assertEqual(result.status, "solved")
        face = scad.make_face_from_sketch_rface(sketch)
        self.assertAlmostEqual(face.get_area(), 3.141592653589793 * 2.25, places=5)

    def test_underconstrained_and_conflicting_sketches_report_diagnostics(self):
        sketch = scad.make_sketch_rsketch("open")
        p0 = scad.make_sketch_point_rsketchref(sketch, "p0", 0.0, 0.0)
        p1 = scad.make_sketch_point_rsketchref(sketch, "p1", 1.0, 0.0)
        sketch = scad.add_line_rsketch(sketch, "line", p0, p1)
        result = scad.solve_sketch_rsketchresult(sketch, strict=False)
        self.assertEqual(result.status, "underconstrained")
        self.assertGreater(result.dof, 0)

        bad = scad.make_sketch_rsketch("bad")
        a = scad.make_sketch_point_rsketchref(bad, "a", 0.0, 0.0)
        b = scad.make_sketch_point_rsketchref(bad, "b", 1.0, 0.0)
        bad = scad.add_line_rsketch(bad, "line", a, b)
        bad = scad.constrain_distance_rsketch(bad, a, b, 1.0)
        bad = scad.constrain_distance_rsketch(bad, a, b, 2.0)
        bad = scad.constrain_fix_rsketch(bad, a)
        bad_result = scad.solve_sketch_rsketchresult(bad, strict=False)
        self.assertEqual(bad_result.status, "conflicting")
        self.assertTrue(any(diag.code == "residual_too_large" for diag in bad_result.diagnostics))

    def test_sketch_refs_are_scoped_to_their_sketch(self):
        first = scad.make_sketch_rsketch("first")
        second = scad.make_sketch_rsketch("second")
        p0 = scad.make_sketch_point_rsketchref(first, "p0", 0.0, 0.0)
        p1 = scad.make_sketch_point_rsketchref(second, "p1", 1.0, 0.0)

        with self.assertRaises(Exception):
            scad.add_line_rsketch(first, "bad", p0, p1)

    def test_graph_replay_preserves_sketch_to_face_result(self):
        with scad.GraphSession() as session:
            sketch = self._make_constrained_rectangle()
            face = scad.make_face_from_sketch_rface(sketch)

        ops = [node.op for node in session.graph.nodes]
        self.assertIn("make_sketch_rsketch", ops)
        self.assertIn("make_constrain_parallel_rsketch", ops)
        self.assertIn("make_face_from_sketch_rface", ops)
        replayed = scad.replay_model_json(scad.export_model_json(session))
        self.assertEqual(len(replayed), 1)
        self.assertIsInstance(replayed[0], scad.Face)
        self.assertAlmostEqual(replayed[0].get_area(), face.get_area(), places=6)


if __name__ == "__main__":
    unittest.main()
