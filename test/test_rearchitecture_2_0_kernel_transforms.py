"""TDD coverage for the OCP-native transform slice."""

from __future__ import annotations

import unittest
import simplecadapi as scad


class TestOcpTransformBuilders(unittest.TestCase):
    def test_translate_shape_uses_ocp_wrapped_storage(self):
        edge = scad.make_line_redge((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        moved = scad.translate_shape(edge, (1.0, 0.0, 0.0))
        self.assertIsInstance(moved, scad.Edge)
        self.assertTrue(hasattr(moved, "wrapped"))
        self.assertFalse(hasattr(moved, "cq_edge"))
        self.assertAlmostEqual(moved.get_length(), edge.get_length(), places=5)

    def test_rotate_shape_uses_ocp_wrapped_storage(self):
        edge = scad.make_line_redge((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        rotated = scad.rotate_shape(edge, 90.0, (0.0, 0.0, 1.0))
        self.assertIsInstance(rotated, scad.Edge)
        self.assertTrue(hasattr(rotated, "wrapped"))
        self.assertFalse(hasattr(rotated, "cq_edge"))
        self.assertAlmostEqual(rotated.get_length(), edge.get_length(), places=5)

    def test_mirror_shape_uses_ocp_wrapped_storage(self):
        solid = scad.make_box_rsolid(1.0, 2.0, 3.0)
        mirrored = scad.mirror_shape(solid, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        self.assertIsInstance(mirrored, scad.Solid)
        self.assertTrue(hasattr(mirrored, "wrapped"))
        self.assertFalse(hasattr(mirrored, "cq_solid"))
        self.assertAlmostEqual(mirrored.get_volume(), solid.get_volume(), places=5)


if __name__ == "__main__":
    unittest.main()
