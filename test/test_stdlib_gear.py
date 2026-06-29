"""Tests for the standard-parts library: gears, ring gears, and racks."""

import json
import math
import unittest

import simplecadapi as scad


class TestSpurGear(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_spur_gear(self):
        solid = scad.std_gear.make_spur_gear_rsolid(
            n_teeth=10, module=2.0, pressure_angle=20.0, gear_height=5.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)

    def test_default_pressure_angle(self):
        solid = scad.std_gear.make_spur_gear_rsolid(
            n_teeth=20, module=1.5, gear_height=4.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)

    def test_more_teeth_larger_volume(self):
        small = scad.std_gear.make_spur_gear_rsolid(n_teeth=10, module=2.0, gear_height=5.0)
        large = scad.std_gear.make_spur_gear_rsolid(n_teeth=24, module=2.0, gear_height=5.0)
        self.assertGreater(large.get_volume(), small.get_volume())

    def test_height_scales_volume(self):
        short = scad.std_gear.make_spur_gear_rsolid(n_teeth=12, module=2.0, gear_height=4.0)
        tall = scad.std_gear.make_spur_gear_rsolid(n_teeth=12, module=2.0, gear_height=8.0)
        self.assertAlmostEqual(tall.get_volume(), 2.0 * short.get_volume(), places=0)

    def test_invalid_params(self):
        with self.assertRaises(Exception):
            scad.std_gear.make_spur_gear_rsolid(n_teeth=2, module=2.0)
        with self.assertRaises(Exception):
            scad.std_gear.make_spur_gear_rsolid(n_teeth=10, module=-1.0)
        with self.assertRaises(Exception):
            scad.std_gear.make_spur_gear_rsolid(n_teeth=10, module=2.0, gear_height=0.0)

    def test_tip_radius_bounds(self):
        n_teeth = 20
        module = 2.0
        solid = scad.std_gear.make_spur_gear_rsolid(n_teeth=n_teeth, module=module, gear_height=4.0)
        expected_tip = module * n_teeth / 2.0 + module
        max_r = 0.0
        for face in solid.get_faces():
            for wire in face.get_wires():
                for edge in wire.get_edges():
                    for vertex in edge.get_vertices():
                        x, y, _ = vertex.get_coordinates()
                        max_r = max(max_r, math.sqrt(x * x + y * y))
        self.assertLess(max_r, expected_tip * 1.05)
        self.assertGreater(max_r, expected_tip * 0.95)

    def test_external_gear_root_transition_is_not_radial_line_patch(self):
        _face, sketch = scad.std_gear._build_gear_profile_face(
            n_teeth=18,
            module=1.5,
            pressure_angle=math.radians(20.0),
            return_sketch=True,
        )
        self.assertNotIn("line_up_0", sketch.entities)
        self.assertNotIn("line_down_0", sketch.entities)
        self.assertEqual(sketch.entities["fillet_left_0"].kind, "bspline")
        self.assertEqual(sketch.entities["fillet_right_0"].kind, "bspline")

    def test_external_gear_involute_bspline_uses_analytic_endpoints(self):
        _face, sketch = scad.std_gear._build_gear_profile_face(
            n_teeth=18,
            module=1.5,
            pressure_angle=math.radians(20.0),
            return_sketch=True,
        )
        left = sketch.entities["bspline_left_0"]
        first_cp = left.data["control_points"][0]
        last_cp = left.data["control_points"][-1]
        start = sketch.entities["t0_bs"].data
        tip = sketch.entities["t0_ts"].data

        self.assertAlmostEqual(first_cp[0], start["x"], places=8)
        self.assertAlmostEqual(first_cp[1], start["y"], places=8)
        self.assertAlmostEqual(last_cp[0], tip["x"], places=8)
        self.assertAlmostEqual(last_cp[1], tip["y"], places=8)

    def test_external_gear_profile_only_fixes_center_point(self):
        _face, sketch = scad.std_gear._build_gear_profile_face(
            n_teeth=18,
            module=1.5,
            pressure_angle=math.radians(20.0),
            return_sketch=True,
        )
        fix_constraints = [constraint for constraint in sketch.constraints if constraint.kind == "fix"]

        self.assertEqual(len(fix_constraints), 1)
        self.assertEqual(fix_constraints[0].targets[0]["entity_id"], "center")

    def test_involute_bspline_uses_shared_fit_helper(self):
        original = scad.std_gear.fit_cubic_bspline_control_points
        calls = []

        def wrapped(*args, **kwargs):
            calls.append((args, kwargs))
            return original(*args, **kwargs)

        scad.std_gear.fit_cubic_bspline_control_points = wrapped
        try:
            scad.std_gear._build_gear_profile_face(
                n_teeth=12,
                module=1.5,
                pressure_angle=math.radians(20.0),
            )
        finally:
            scad.std_gear.fit_cubic_bspline_control_points = original

        self.assertGreater(len(calls), 0)
        self.assertTrue(all(call[1]["tolerance"] == 1e-4 for call in calls))


class TestHelicalGear(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_helical_gear(self):
        solid = scad.std_gear.make_helical_gear_rsolid(
            n_teeth=12, module=2.0, helix_angle=25.0, gear_height=8.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)

    def test_zero_helix_falls_back_to_spur(self):
        spur = scad.std_gear.make_spur_gear_rsolid(n_teeth=12, module=2.0, gear_height=6.0)
        helical = scad.std_gear.make_helical_gear_rsolid(
            n_teeth=12, module=2.0, gear_height=6.0, helix_angle=0.0,
        )
        self.assertAlmostEqual(spur.get_volume(), helical.get_volume(), places=0)

    def test_invalid_params(self):
        with self.assertRaises(Exception):
            scad.std_gear.make_helical_gear_rsolid(n_teeth=2, module=2.0)


class TestHerringboneGear(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_herringbone_gear(self):
        solid = scad.std_gear.make_herringbone_gear_rsolid(
            n_teeth=12, module=2.0, helix_angle=25.0, gear_height=10.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)

    def test_zero_helix_falls_back_to_spur(self):
        spur = scad.std_gear.make_spur_gear_rsolid(n_teeth=12, module=2.0, gear_height=8.0)
        herringbone = scad.std_gear.make_herringbone_gear_rsolid(
            n_teeth=12, module=2.0, gear_height=8.0, helix_angle=0.0,
        )
        self.assertAlmostEqual(spur.get_volume(), herringbone.get_volume(), places=0)


class TestSpurRingGear(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_ring_gear(self):
        solid = scad.std_gear.make_spur_ring_gear_rsolid(
            n_teeth=20, module=2.0, gear_height=5.0, rim_thickness=4.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)

    def test_ring_volume_less_than_disc(self):
        n_teeth = 20
        module = 2.0
        rim_thickness = 4.0
        ring = scad.std_gear.make_spur_ring_gear_rsolid(
            n_teeth=n_teeth, module=module, gear_height=5.0, rim_thickness=rim_thickness,
        )
        pitch_radius = module * n_teeth / 2.0
        outer_r = pitch_radius + 1.25 * module + rim_thickness
        disc = scad.make_cylinder_rsolid(radius=outer_r, height=5.0)
        self.assertLess(ring.get_volume(), disc.get_volume())

    def test_ring_profile_uses_internal_tooth_radii(self):
        n_teeth = 66
        module = 1.5
        pressure_angle = math.radians(20.0)
        face = scad.std_gear._build_ring_gear_face(
            n_teeth=n_teeth,
            module=module,
            pressure_angle=pressure_angle,
            rim_thickness=4.0,
        )
        inner_wire = face.get_inner_wires()[0]

        vertex_radii = [
            math.hypot(x, y)
            for edge in inner_wire.get_edges()
            for vertex in edge.get_vertices()
            for x, y, _z in [vertex.get_coordinates()]
        ]
        pitch_radius = module * n_teeth / 2.0
        base_radius = pitch_radius * math.cos(pressure_angle)
        self.assertAlmostEqual(min(vertex_radii), pitch_radius - module, places=5)
        self.assertAlmostEqual(max(vertex_radii), pitch_radius + 1.25 * module, places=5)
        self.assertGreater(min(vertex_radii), base_radius + 0.5 * module)

    def test_spur_ring_gear_uses_direct_multi_loop_face_not_2d_cut(self):
        with scad.GraphSession() as session:
            scad.std_gear.make_spur_ring_gear_rsolid(
                n_teeth=20, module=2.0, gear_height=5.0, rim_thickness=4.0,
            )

        payload = json.loads(scad.export_model_json(session))
        ops = [node["op"] for node in payload["graph"]["nodes"]]
        self.assertIn("make_face_from_wires_rface", ops)
        self.assertNotIn("make_2d_cut_rface", ops)

    def test_internal_profile_wire_uses_internal_bspline_flanks(self):
        _wire, sketch = scad.std_gear._build_internal_gear_profile_wire(
            n_teeth=66,
            module=1.5,
            pressure_angle=math.radians(20.0),
            return_sketch=True,
        )
        left = sketch.entities["bspline_internal_left_0"]
        right = sketch.entities["bspline_internal_right_0"]
        self.assertEqual(left.kind, "bspline")
        self.assertEqual(right.kind, "bspline")
        self.assertNotIn("bspline_left_0", sketch.entities)
        self.assertNotIn("bspline_right_0", sketch.entities)

    def test_internal_profile_only_fixes_center_point(self):
        _wire, sketch = scad.std_gear._build_internal_gear_profile_wire(
            n_teeth=20,
            module=1.5,
            pressure_angle=math.radians(20.0),
            return_sketch=True,
        )
        fix_constraints = [constraint for constraint in sketch.constraints if constraint.kind == "fix"]

        self.assertEqual(len(fix_constraints), 1)
        self.assertEqual(fix_constraints[0].targets[0]["entity_id"], "center")

    def test_ring_backlash_increases_internal_tooth_space(self):
        n_teeth = 66
        module = 1.5
        pressure_angle = math.radians(20.0)
        backlash = 0.12
        no_backlash = scad.std_gear._compute_internal_tooth_geometry(
            n_teeth, module, pressure_angle, backlash=0.0,
        )
        with_backlash = scad.std_gear._compute_internal_tooth_geometry(
            n_teeth, module, pressure_angle, backlash=backlash,
        )

        no_backlash_space = no_backlash["tooth_angle"] - (
            no_backlash["right_root_angle"] - no_backlash["left_root_angle"]
        )
        with_backlash_space = with_backlash["tooth_angle"] - (
            with_backlash["right_root_angle"] - with_backlash["left_root_angle"]
        )

        self.assertGreater(with_backlash_space, no_backlash_space)
        self.assertAlmostEqual(
            with_backlash_space - no_backlash_space,
            backlash / no_backlash["pitch_radius"],
            places=12,
        )

    def test_invalid_params(self):
        with self.assertRaises(Exception):
            scad.std_gear.make_spur_ring_gear_rsolid(n_teeth=2, module=2.0)
        with self.assertRaises(Exception):
            scad.std_gear.make_spur_ring_gear_rsolid(n_teeth=10, module=2.0, rim_thickness=0.0)
        with self.assertRaises(Exception):
            scad.std_gear.make_spur_ring_gear_rsolid(n_teeth=10, module=2.0, backlash=-0.1)


class TestHelicalRingGear(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_helical_ring(self):
        solid = scad.std_gear.make_helical_ring_gear_rsolid(
            n_teeth=20, module=2.0, helix_angle=20.0, gear_height=8.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)


class TestHerringboneRingGear(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_herringbone_ring(self):
        solid = scad.std_gear.make_herringbone_ring_gear_rsolid(
            n_teeth=20, module=2.0, helix_angle=20.0, gear_height=10.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)


class TestSpurRack(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_rack(self):
        solid = scad.std_gear.make_spur_rack_rsolid(module=2.0, n_teeth=8, rack_height=5.0)
        self.assertGreater(solid.get_volume(), 0.0)

    def test_more_teeth_larger_volume(self):
        short = scad.std_gear.make_spur_rack_rsolid(module=2.0, n_teeth=5, rack_height=5.0)
        long = scad.std_gear.make_spur_rack_rsolid(module=2.0, n_teeth=10, rack_height=5.0)
        self.assertGreater(long.get_volume(), short.get_volume())

    def test_invalid_params(self):
        with self.assertRaises(Exception):
            scad.std_gear.make_spur_rack_rsolid(module=-1.0)
        with self.assertRaises(Exception):
            scad.std_gear.make_spur_rack_rsolid(module=2.0, n_teeth=0)

    def test_rack_profile_has_no_fix_constraints(self):
        with scad.GraphSession() as session:
            scad.std_gear.make_spur_rack_rsolid(module=2.0, n_teeth=5, rack_height=5.0)

        payload = json.loads(scad.export_model_json(session))
        ops = [node["op"] for node in payload["graph"]["nodes"]]
        self.assertNotIn("make_constrain_fix_rsketch", ops)


class TestHelicalRack(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_helical_rack(self):
        solid = scad.std_gear.make_helical_rack_rsolid(
            module=2.0, n_teeth=8, helix_angle=25.0, rack_height=8.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)


class TestHerringboneRack(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_herringbone_rack(self):
        solid = scad.std_gear.make_herringbone_rack_rsolid(
            module=2.0, n_teeth=8, helix_angle=30.0, rack_height=10.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)


class Test2DFaceBoolean(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_make_2d_cut_rface_creates_hole(self):
        outer = scad.make_circle_rface(center=(0, 0, 0), radius=10.0)
        inner = scad.make_circle_rface(center=(0, 0, 0), radius=4.0)
        ring = scad.make_2d_cut_rface(outer, inner)
        self.assertAlmostEqual(
            ring.get_area(), math.pi * (100 - 16), places=1,
        )
        self.assertEqual(len(ring.get_inner_wires()), 1)

    def test_make_face_from_wires_rface_creates_hole(self):
        outer = scad.make_circle_rwire(center=(0, 0, 0), radius=10.0)
        inner = scad.make_circle_rwire(center=(0, 0, 0), radius=4.0)
        ring = scad.make_face_from_wires_rface(outer, [inner])
        self.assertAlmostEqual(
            ring.get_area(), math.pi * (100 - 16), places=1,
        )
        self.assertEqual(len(ring.get_inner_wires()), 1)

    def test_make_2d_union_rface(self):
        a = scad.make_circle_rface(center=(0, 0, 0), radius=5.0)
        b = scad.make_circle_rface(center=(3, 0, 0), radius=5.0)
        merged = scad.make_2d_union_rface(a, b)
        self.assertGreater(merged.get_area(), math.pi * 25)

    def test_make_2d_intersect_rface(self):
        a = scad.make_circle_rface(center=(0, 0, 0), radius=5.0)
        b = scad.make_circle_rface(center=(3, 0, 0), radius=5.0)
        overlap = scad.make_2d_intersect_rface(a, b)
        self.assertGreater(overlap.get_area(), 0.0)
        self.assertLess(overlap.get_area(), math.pi * 25)


if __name__ == "__main__":
    unittest.main()
