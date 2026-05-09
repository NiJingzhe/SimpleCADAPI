"""Focused tests for the minimal 2.0 Sketch object."""

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


if __name__ == "__main__":
    unittest.main()
