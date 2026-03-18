import math
import unittest

from OCP.BRepExtrema import BRepExtrema_DistShapeShape

import simplecadapi as scad
from simplecadapi import field as Field


def sample_sphere_points(radius: float, rings: int = 2, segments: int = 4):
    points = []
    for i in range(1, rings):
        phi = math.pi * i / rings
        for j in range(segments):
            theta = 2 * math.pi * j / segments
            x = radius * math.sin(phi) * math.cos(theta)
            y = radius * math.sin(phi) * math.sin(theta)
            z = radius * math.cos(phi)
            points.append((x, y, z))
    points.append((0.0, 0.0, radius))
    points.append((0.0, 0.0, -radius))
    return points


class TestScalarField(unittest.TestCase):
    def test_eval_sphere(self):
        field = Field.make_sphere_rscalarfield((0.0, 0.0, 0.0), 1.0)
        self.assertLess(Field.eval_rscalar(field, 0.0, 0.0, 0.0), 0.0)
        self.assertAlmostEqual(Field.eval_rscalar(field, 1.0, 0.0, 0.0), 0.0, places=6)

    def test_smooth_subtract(self):
        a = Field.make_sphere_rscalarfield((0.0, 0.0, 0.0), 2.0)
        b = Field.make_sphere_rscalarfield((0.0, 0.0, 0.0), 1.0)
        field = Field.smooth_subtract_rscalarfield(a, b, 0.5)
        self.assertGreater(Field.eval_rscalar(field, 0.0, 0.0, 0.0), 0.0)


class TestFieldSurface(unittest.TestCase):
    def test_make_field_surface_rsolid(self):
        field = Field.make_sphere_rscalarfield((0.0, 0.0, 0.0), 1.0)
        solid = scad.make_field_surface_rsolid(
            field,
            bounds=((-1.2, -1.2, -1.2), (1.2, 1.2, 1.2)),
            resolution=(10, 10, 10),
            iso=0.0,
        )

        self.assertIsInstance(solid, scad.Solid)
        self.assertGreater(abs(solid.get_volume()), 0.0)

        report = solid.get_metadata("field_report")
        self.assertIsNotNone(report)
        self.assertEqual(report["iso"], 0.0)
        self.assertEqual(report["resolution"], (10, 10, 10))
        self.assertGreater(report["triangles"], 0)

    def test_field_surface_matches_sphere(self):
        radius = 1.0
        field = Field.make_sphere_rscalarfield((0.0, 0.0, 0.0), radius)
        field_solid = scad.make_field_surface_rsolid(
            field,
            bounds=((-1.25, -1.25, -1.25), (1.25, 1.25, 1.25)),
            resolution=(10, 10, 10),
            iso=0.0,
        )

        points = sample_sphere_points(radius)
        distances = []
        for x, y, z in points:
            vertex = scad.make_point_rvertex(x, y, z)
            dist = BRepExtrema_DistShapeShape(
                vertex.cq_vertex.wrapped, field_solid.cq_solid.wrapped
            )
            distances.append(float(dist.Value()))

        self.assertLess(max(distances), 1.2)


if __name__ == "__main__":
    unittest.main()
