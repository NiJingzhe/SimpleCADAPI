"""Tests for the standard-parts library: gears, ring gears, and racks."""

import json
import math
import unittest
from unittest import mock

import simplecadapi as scad


def _loft_nodes_for(factory):
    with scad.GraphSession() as session:
        factory()

    payload = json.loads(scad.export_model_json(session=session))
    return [
        node for node in payload["graph"]["nodes"] if node["op"] == "make_loft_rsolid"
    ]


class TestStdGearSurface(unittest.TestCase):
    def test_preferred_nested_std_export_surface(self):
        self.assertFalse(hasattr(scad, "std" + "_gear"))
        solid = scad.std.gear.make_spur_gear_rsolid(
            n_teeth=8,
            module=1.0,
            gear_height=2.0,
        )

        self.assertGreater(solid.get_volume(), 0.0)

    def test_public_gear_factories_follow_make_rtype_naming(self):
        factory_names = [
            name
            for name in scad.std.gear.__all__
            if callable(getattr(scad.std.gear, name, None))
        ]

        self.assertGreater(len(factory_names), 0)
        for name in factory_names:
            self.assertTrue(name.startswith("make_"), name)
            self.assertIn("_r", name, name)


class TestSpurGear(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_spur_gear(self):
        solid = scad.std.gear.make_spur_gear_rsolid(
            n_teeth=10,
            module=2.0,
            pressure_angle=20.0,
            gear_height=5.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)

    def test_default_pressure_angle(self):
        solid = scad.std.gear.make_spur_gear_rsolid(
            n_teeth=20,
            module=1.5,
            gear_height=4.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)

    def test_more_teeth_larger_volume(self):
        small = scad.std.gear.make_spur_gear_rsolid(
            n_teeth=10, module=2.0, gear_height=5.0
        )
        large = scad.std.gear.make_spur_gear_rsolid(
            n_teeth=24, module=2.0, gear_height=5.0
        )
        self.assertGreater(large.get_volume(), small.get_volume())

    def test_height_scales_volume(self):
        short = scad.std.gear.make_spur_gear_rsolid(
            n_teeth=12, module=2.0, gear_height=4.0
        )
        tall = scad.std.gear.make_spur_gear_rsolid(
            n_teeth=12, module=2.0, gear_height=8.0
        )
        self.assertAlmostEqual(tall.get_volume(), 2.0 * short.get_volume(), places=0)

    def test_invalid_params(self):
        with self.assertRaises(Exception):
            scad.std.gear.make_spur_gear_rsolid(n_teeth=2, module=2.0)
        with self.assertRaises(Exception):
            scad.std.gear.make_spur_gear_rsolid(n_teeth=10, module=-1.0)
        with self.assertRaises(Exception):
            scad.std.gear.make_spur_gear_rsolid(n_teeth=10, module=2.0, gear_height=0.0)
        with self.assertRaises(Exception):
            scad.std.gear.make_spur_gear_rsolid(n_teeth=10, module=2.0, backlash=-0.1)
        with self.assertRaises(Exception):
            scad.std.gear.make_spur_gear_rsolid(
                n_teeth=10, module=2.0, addendum_factor=0.0
            )

    def test_tip_radius_bounds(self):
        n_teeth = 20
        module = 2.0
        solid = scad.std.gear.make_spur_gear_rsolid(
            n_teeth=n_teeth, module=module, gear_height=4.0
        )
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
        _face, sketch = scad.std.gear._build_gear_profile_face(
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
        _face, sketch = scad.std.gear._build_gear_profile_face(
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
        _face, sketch = scad.std.gear._build_gear_profile_face(
            n_teeth=18,
            module=1.5,
            pressure_angle=math.radians(20.0),
            return_sketch=True,
        )
        fix_constraints = [
            constraint for constraint in sketch.constraints if constraint.kind == "fix"
        ]

        self.assertEqual(len(fix_constraints), 1)
        self.assertEqual(fix_constraints[0].targets[0]["entity_id"], "center")

    def test_external_gear_backlash_reduces_pitch_tooth_thickness(self):
        n_teeth = 18
        module = 1.5
        pressure_angle = math.radians(20.0)
        backlash = 0.12
        no_backlash = scad.std.gear._compute_tooth_geometry(
            n_teeth,
            module,
            pressure_angle,
            backlash=0.0,
        )
        with_backlash = scad.std.gear._compute_tooth_geometry(
            n_teeth,
            module,
            pressure_angle,
            backlash=backlash,
        )

        no_backlash_width = no_backlash["right_start"] - no_backlash["left_start"]
        with_backlash_width = with_backlash["right_start"] - with_backlash["left_start"]

        self.assertLess(with_backlash_width, no_backlash_width)
        self.assertAlmostEqual(
            no_backlash_width - with_backlash_width,
            backlash / no_backlash["pitch_radius"],
            places=12,
        )

    def test_external_gear_addendum_and_clearance_factors_control_radii(self):
        n_teeth = 18
        module = 1.5
        pressure_angle = math.radians(20.0)
        geo = scad.std.gear._compute_tooth_geometry(
            n_teeth,
            module,
            pressure_angle,
            addendum_factor=0.8,
            clearance_factor=0.1,
        )
        pitch_radius = module * n_teeth / 2.0

        self.assertAlmostEqual(geo["tip_radius"], pitch_radius + 0.8 * module)
        self.assertAlmostEqual(geo["root_radius"], pitch_radius - 0.9 * module)

    def test_involute_bspline_uses_shared_fit_helper(self):
        original = scad.std.gear.fit_cubic_bspline_control_points
        calls = []

        def wrapped(*args, **kwargs):
            calls.append((args, kwargs))
            return original(*args, **kwargs)

        scad.std.gear.fit_cubic_bspline_control_points = wrapped
        try:
            scad.std.gear._build_gear_profile_face(
                n_teeth=12,
                module=1.5,
                pressure_angle=math.radians(20.0),
            )
        finally:
            scad.std.gear.fit_cubic_bspline_control_points = original

        self.assertEqual(len(calls), 1)
        self.assertTrue(all(call[1]["tolerance"] == 1e-4 for call in calls))

    def test_external_gear_reuses_rotated_canonical_involute(self):
        n_teeth = 12
        _face, sketch = scad.std.gear._build_gear_profile_face(
            n_teeth=n_teeth,
            module=1.5,
            pressure_angle=math.radians(20.0),
            return_sketch=True,
        )
        tooth_angle = 2.0 * math.pi / n_teeth
        first = sketch.entities["bspline_left_0"].data["control_points"]
        second = sketch.entities["bspline_left_1"].data["control_points"]

        for source, actual in zip(first, second):
            expected = scad.std.gear._rotate_xy(tuple(source), tooth_angle)
            self.assertAlmostEqual(actual[0], expected[0], places=10)
            self.assertAlmostEqual(actual[1], expected[1], places=10)

    def test_external_gear_builds_only_two_canonical_root_fillets(self):
        original = scad.std.gear._root_fillet_control_points
        calls = []

        def wrapped(*args, **kwargs):
            calls.append((args, kwargs))
            return original(*args, **kwargs)

        scad.std.gear._root_fillet_control_points = wrapped
        try:
            scad.std.gear._build_gear_profile_face(
                n_teeth=18,
                module=1.5,
                pressure_angle=math.radians(20.0),
            )
        finally:
            scad.std.gear._root_fillet_control_points = original

        self.assertEqual(len(calls), 2)

    def test_external_gear_builds_sketch_with_bounded_clone_count(self):
        from simplecadapi.sketch import Sketch

        original = Sketch.clone
        calls = []

        def wrapped(sketch, *args, **kwargs):
            calls.append(sketch)
            return original(sketch, *args, **kwargs)

        with mock.patch.object(Sketch, "clone", wrapped):
            scad.std.gear._build_gear_profile_face(
                n_teeth=18,
                module=1.5,
                pressure_angle=math.radians(20.0),
            )

        self.assertLessEqual(len(calls), 2)

    def test_external_gear_linear_sketch_edits_strict_replay(self):
        with scad.GraphSession() as session:
            original = scad.std.gear.make_spur_gear_rsolid(
                n_teeth=12,
                module=2.0,
                gear_height=4.0,
            )

        replayed = scad.replay_model_json(
            json_str=scad.export_model_json(session=session), strict=True
        )[0]
        self.assertAlmostEqual(replayed.get_volume(), original.get_volume(), places=6)


class TestStraightBevelGear(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_straight_bevel_gear(self):
        solid = scad.std.gear.make_straight_bevel_gear_rsolid(
            n_teeth=18,
            module=4.0,
            pitch_angle=45.0,
            pressure_angle=20.0,
            face_width=18.0,
        )

        self.assertGreater(solid.get_volume(), 0.0)
        meta = solid.get_metadata("std.gear.straight_bevel")
        self.assertEqual(meta["n_teeth"], 18)
        self.assertEqual(meta["module"], 4.0)
        self.assertEqual(meta["pitch_angle"], 45.0)
        self.assertAlmostEqual(meta["outer_pitch_radius"], 36.0)
        self.assertAlmostEqual(
            meta["outer_cone_distance"],
            36.0 / math.sin(math.radians(45.0)),
        )
        print(
            "straight_bevel_gear: "
            f"volume={solid.get_volume():.3f} "
            f"inner_scale={meta['inner_scale']:.6f}"
        )

    def test_straight_bevel_gear_uses_ruled_similar_sections(self):
        loft_nodes = _loft_nodes_for(
            lambda: scad.std.gear.make_straight_bevel_gear_rsolid(
                n_teeth=18,
                module=4.0,
                pitch_angle=45.0,
                face_width=18.0,
            )
        )

        self.assertEqual(len(loft_nodes), 1)
        self.assertEqual(loft_nodes[0]["params"]["profile_count"], 2)
        self.assertTrue(loft_nodes[0]["params"]["ruled"])

    def test_straight_bevel_gear_strict_replay(self):
        with scad.GraphSession() as session:
            original = scad.std.gear.make_straight_bevel_gear_rsolid(
                n_teeth=18,
                module=4.0,
                pitch_angle=45.0,
                face_width=18.0,
            )
            model_json = scad.export_model_json(session=session)

        replayed = scad.replay_model_json(json_str=model_json, strict=True)
        self.assertEqual(len(replayed), 1)
        self.assertAlmostEqual(
            replayed[0].get_volume(), original.get_volume(), places=5
        )

    def test_invalid_straight_bevel_gear_params(self):
        invalid_kwargs = (
            {"n_teeth": 2, "module": 4.0},
            {"n_teeth": 18, "module": 0.0},
            {"n_teeth": 18, "module": 4.0, "pitch_angle": 0.0},
            {"n_teeth": 18, "module": 4.0, "pitch_angle": 90.0},
            {"n_teeth": 18, "module": 4.0, "face_width": 60.0},
        )
        for kwargs in invalid_kwargs:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                scad.std.gear.make_straight_bevel_gear_rsolid(**kwargs)


class TestHelicalGear(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_helical_gear(self):
        solid = scad.std.gear.make_helical_gear_rsolid(
            n_teeth=12,
            module=2.0,
            helix_angle=25.0,
            gear_height=8.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)

    def test_zero_helix_falls_back_to_spur(self):
        spur = scad.std.gear.make_spur_gear_rsolid(
            n_teeth=12, module=2.0, gear_height=6.0
        )
        helical = scad.std.gear.make_helical_gear_rsolid(
            n_teeth=12,
            module=2.0,
            gear_height=6.0,
            helix_angle=0.0,
        )
        self.assertAlmostEqual(spur.get_volume(), helical.get_volume(), places=0)

    def test_invalid_params(self):
        with self.assertRaises(Exception):
            scad.std.gear.make_helical_gear_rsolid(n_teeth=2, module=2.0)

    def test_helical_gear_uses_one_continuous_twisted_sweep(self):
        with scad.GraphSession() as session:
            solid = scad.std.gear.make_helical_gear_rsolid(
                n_teeth=12,
                module=2.0,
                helix_angle=25.0,
                gear_height=8.0,
            )

        payload = json.loads(scad.export_model_json(session=session))
        twisted_nodes = [
            node
            for node in payload["graph"]["nodes"]
            if node["op"] == "make_twisted_sweep_rsolid"
        ]
        self.assertEqual(len(twisted_nodes), 1)
        self.assertNotIn("topo_delta", twisted_nodes[0])
        self.assertFalse(
            any(node["op"] == "make_loft_rsolid" for node in payload["graph"]["nodes"])
        )
        self.assertEqual(len(solid.get_faces()), 74)

        replayed = scad.replay_model_json(
            json_str=json.dumps(payload), strict=True
        )[0]
        self.assertEqual(len(replayed.get_faces()), 74)
        self.assertAlmostEqual(replayed.get_volume(), solid.get_volume(), places=6)


class TestHerringboneGear(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_herringbone_gear(self):
        solid = scad.std.gear.make_herringbone_gear_rsolid(
            n_teeth=12,
            module=2.0,
            helix_angle=25.0,
            gear_height=10.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)

    def test_zero_helix_falls_back_to_spur(self):
        spur = scad.std.gear.make_spur_gear_rsolid(
            n_teeth=12, module=2.0, gear_height=8.0
        )
        herringbone = scad.std.gear.make_herringbone_gear_rsolid(
            n_teeth=12,
            module=2.0,
            gear_height=8.0,
            helix_angle=0.0,
        )
        self.assertAlmostEqual(spur.get_volume(), herringbone.get_volume(), places=0)

    def test_herringbone_gear_unions_two_replayable_twisted_halves(self):
        with scad.GraphSession() as session:
            solid = scad.std.gear.make_herringbone_gear_rsolid(
                n_teeth=12,
                module=2.0,
                helix_angle=25.0,
                gear_height=10.0,
            )

        payload = json.loads(scad.export_model_json(session=session))
        operations = [node["op"] for node in payload["graph"]["nodes"]]
        self.assertEqual(operations.count("make_twisted_sweep_rsolid"), 2)
        self.assertEqual(operations.count("make_union_rsolid"), 1)
        self.assertNotIn("make_loft_rsolid", operations)
        self.assertTrue(
            all(
                "topo_delta" not in node
                for node in payload["graph"]["nodes"]
                if node["op"] == "make_twisted_sweep_rsolid"
            )
        )
        self.assertEqual(len(solid.get_faces()), 146)

        replayed = scad.replay_model_json(
            json_str=json.dumps(payload), strict=True
        )[0]
        self.assertEqual(len(replayed.get_faces()), 146)
        self.assertAlmostEqual(replayed.get_volume(), solid.get_volume(), places=6)

    def test_stdlib_graph_tracking_scope_does_not_leak(self):
        with scad.GraphSession() as session:
            scad.std.gear.make_herringbone_gear_rsolid(
                n_teeth=8,
                module=1.0,
                helix_angle=20.0,
                gear_height=4.0,
            )
            profile = scad.make_rectangle_rface(
                width=1.0,
                height=1.0,
                center=(0.0, 0.0, 0.0),
            )
            scad.twisted_sweep_rsolid(
                profile=profile,
                distance=2.0,
                twist_angle=15.0,
            )

        payload = json.loads(scad.export_model_json(session=session))
        twisted_nodes = [
            node
            for node in payload["graph"]["nodes"]
            if node["op"] == "make_twisted_sweep_rsolid"
        ]
        self.assertEqual(len(twisted_nodes), 3)
        self.assertEqual(
            sum("topo_delta" in node for node in twisted_nodes),
            1,
        )


class TestSpurRingGear(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_ring_gear(self):
        solid = scad.std.gear.make_spur_ring_gear_rsolid(
            n_teeth=20,
            module=2.0,
            gear_height=5.0,
            rim_thickness=4.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)

    def test_ring_volume_less_than_disc(self):
        n_teeth = 20
        module = 2.0
        rim_thickness = 4.0
        ring = scad.std.gear.make_spur_ring_gear_rsolid(
            n_teeth=n_teeth,
            module=module,
            gear_height=5.0,
            rim_thickness=rim_thickness,
        )
        pitch_radius = module * n_teeth / 2.0
        outer_r = pitch_radius + 1.25 * module + rim_thickness
        disc = scad.make_cylinder_rsolid(radius=outer_r, height=5.0)
        self.assertLess(ring.get_volume(), disc.get_volume())

    def test_ring_profile_uses_internal_tooth_radii(self):
        n_teeth = 66
        module = 1.5
        pressure_angle = math.radians(20.0)
        face = scad.std.gear._build_ring_gear_face(
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
        self.assertAlmostEqual(
            max(vertex_radii), pitch_radius + 1.25 * module, places=5
        )
        self.assertGreater(min(vertex_radii), base_radius + 0.5 * module)

    def test_spur_ring_gear_uses_direct_multi_loop_face_not_2d_cut(self):
        with scad.GraphSession() as session:
            scad.std.gear.make_spur_ring_gear_rsolid(
                n_teeth=20,
                module=2.0,
                gear_height=5.0,
                rim_thickness=4.0,
            )

        payload = json.loads(scad.export_model_json(session))
        ops = [node["op"] for node in payload["graph"]["nodes"]]
        self.assertIn("make_face_from_wires_rface", ops)
        self.assertNotIn("make_2d_cut_rface", ops)

    def test_internal_profile_wire_uses_internal_bspline_flanks(self):
        _wire, sketch = scad.std.gear._build_internal_gear_profile_wire(
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
        _wire, sketch = scad.std.gear._build_internal_gear_profile_wire(
            n_teeth=20,
            module=1.5,
            pressure_angle=math.radians(20.0),
            return_sketch=True,
        )
        fix_constraints = [
            constraint for constraint in sketch.constraints if constraint.kind == "fix"
        ]

        self.assertEqual(len(fix_constraints), 1)
        self.assertEqual(fix_constraints[0].targets[0]["entity_id"], "center")

    def test_ring_backlash_increases_internal_tooth_space(self):
        n_teeth = 66
        module = 1.5
        pressure_angle = math.radians(20.0)
        backlash = 0.12
        no_backlash = scad.std.gear._compute_internal_tooth_geometry(
            n_teeth,
            module,
            pressure_angle,
            backlash=0.0,
        )
        with_backlash = scad.std.gear._compute_internal_tooth_geometry(
            n_teeth,
            module,
            pressure_angle,
            backlash=backlash,
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

    def test_ring_addendum_and_clearance_factors_control_internal_radii(self):
        n_teeth = 66
        module = 1.5
        pitch, tip, root, outer = scad.std.gear._internal_ring_radii(
            n_teeth,
            module,
            rim_thickness=4.0,
            addendum_factor=0.8,
            clearance_factor=0.1,
        )

        self.assertAlmostEqual(tip, pitch - 0.8 * module)
        self.assertAlmostEqual(root, pitch + 0.9 * module)
        self.assertAlmostEqual(outer, root + 4.0)

    def test_invalid_params(self):
        with self.assertRaises(Exception):
            scad.std.gear.make_spur_ring_gear_rsolid(n_teeth=2, module=2.0)
        with self.assertRaises(Exception):
            scad.std.gear.make_spur_ring_gear_rsolid(
                n_teeth=10, module=2.0, rim_thickness=0.0
            )
        with self.assertRaises(Exception):
            scad.std.gear.make_spur_ring_gear_rsolid(
                n_teeth=10, module=2.0, backlash=-0.1
            )


class TestHelicalRingGear(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_helical_ring(self):
        solid = scad.std.gear.make_helical_ring_gear_rsolid(
            n_teeth=20,
            module=2.0,
            helix_angle=20.0,
            gear_height=8.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)

    def test_helical_ring_uses_small_step_ruled_inner_loft(self):
        loft_nodes = _loft_nodes_for(
            lambda: scad.std.gear.make_helical_ring_gear_rsolid(
                n_teeth=20,
                module=2.0,
                helix_angle=20.0,
                gear_height=8.0,
            )
        )

        self.assertEqual(len(loft_nodes), 1)
        self.assertEqual(loft_nodes[0]["params"]["profile_count"], 7)
        self.assertTrue(loft_nodes[0]["params"]["ruled"])


class TestHerringboneRingGear(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_herringbone_ring(self):
        solid = scad.std.gear.make_herringbone_ring_gear_rsolid(
            n_teeth=20,
            module=2.0,
            helix_angle=20.0,
            gear_height=10.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)

    def test_herringbone_ring_uses_small_step_ruled_inner_loft(self):
        with scad.GraphSession() as session:
            scad.std.gear.make_herringbone_ring_gear_rsolid(
                n_teeth=20,
                module=2.0,
                helix_angle=20.0,
                gear_height=10.0,
            )

        payload = json.loads(scad.export_model_json(session=session))
        loft_nodes = [
            node
            for node in payload["graph"]["nodes"]
            if node["op"] == "make_loft_rsolid"
        ]
        cut_nodes = [
            node
            for node in payload["graph"]["nodes"]
            if node["op"] == "make_cut_rsolid"
        ]

        self.assertEqual(len(loft_nodes), 1)
        self.assertEqual(loft_nodes[0]["params"]["profile_count"], 9)
        self.assertTrue(loft_nodes[0]["params"]["ruled"])
        self.assertEqual(loft_nodes[0]["params"]["tracking_policy"], "graph")
        self.assertEqual(len(cut_nodes), 1)
        self.assertEqual(cut_nodes[0]["params"]["tracking_policy"], "graph")
        self.assertNotIn("topo_delta", cut_nodes[0])


class TestCycloidalDisc(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_cycloidal_disc(self):
        solid = scad.std.gear.make_cycloidal_disc_rsolid(
            n_lobes=10,
            ring_pin_pitch_radius=18.0,
            roller_radius=1.6,
            eccentricity=0.8,
            gear_height=5.7,
            bore_radius=3.45,
            output_pin_count=3,
            output_pin_pitch_radius=6.4,
            output_pin_clearance_radius=2.05,
            output_pin_phase=60.0,
        )

        self.assertGreater(solid.get_volume(), 0.0)
        meta = solid.get_metadata("std.gear.cycloidal_disc")
        self.assertEqual(meta["pin_count"], 11)
        self.assertEqual(meta["n_lobes"], 10)
        self.assertEqual(meta["segment_count"], 10)
        self.assertLess(meta["radius_min"], meta["radius_max"])

    def test_cycloidal_disc_uses_one_bspline_per_lobe(self):
        with scad.GraphSession() as session:
            scad.std.gear.make_cycloidal_disc_rsolid(
                n_lobes=8,
                ring_pin_pitch_radius=15.0,
                roller_radius=1.2,
                eccentricity=0.7,
                gear_height=4.0,
            )

        payload = json.loads(scad.export_model_json(session))
        ops = [node["op"] for node in payload["graph"]["nodes"]]
        self.assertEqual(ops.count("make_spline_redge"), 8)
        self.assertEqual(ops.count("make_line_redge"), 0)

    def test_cycloidal_disc_holes_reduce_volume(self):
        plain = scad.std.gear.make_cycloidal_disc_rsolid(
            n_lobes=10,
            ring_pin_pitch_radius=18.0,
            roller_radius=1.6,
            eccentricity=0.8,
            gear_height=5.7,
        )
        bored = scad.std.gear.make_cycloidal_disc_rsolid(
            n_lobes=10,
            ring_pin_pitch_radius=18.0,
            roller_radius=1.6,
            eccentricity=0.8,
            gear_height=5.7,
            bore_radius=3.45,
            output_pin_count=3,
            output_pin_pitch_radius=6.4,
            output_pin_clearance_radius=2.05,
        )

        self.assertLess(bored.get_volume(), plain.get_volume())

    def test_twin_disc_workflow_uses_half_lobe_phase(self):
        n_lobes = 4
        output_pin_phase = 60.0
        half_lobe_phase = 180.0 / n_lobes

        with scad.GraphSession() as session:
            scad.std.gear.make_cycloidal_disc_rsolid(
                n_lobes=n_lobes,
                ring_pin_pitch_radius=10.0,
                roller_radius=0.9,
                eccentricity=0.45,
                gear_height=2.0,
                bore_radius=1.5,
                output_pin_count=3,
                output_pin_pitch_radius=3.0,
                output_pin_clearance_radius=0.9,
                output_pin_phase=output_pin_phase,
            )
            upper = scad.std.gear.make_cycloidal_disc_rsolid(
                n_lobes=n_lobes,
                ring_pin_pitch_radius=10.0,
                roller_radius=0.9,
                eccentricity=0.45,
                gear_height=2.0,
                bore_radius=1.5,
                output_pin_count=3,
                output_pin_pitch_radius=3.0,
                output_pin_clearance_radius=0.9,
                output_pin_phase=output_pin_phase - half_lobe_phase,
            )
            scad.rotate_shape(
                upper,
                half_lobe_phase,
                axis=(0.0, 0.0, 1.0),
                origin=(0.0, 0.0, 0.0),
            )

        upper_meta = upper.get_metadata("std.gear.cycloidal_disc")
        self.assertEqual(
            upper_meta["output_pin_phase"],
            output_pin_phase - half_lobe_phase,
        )

        payload = json.loads(scad.export_model_json(session))
        ops = [node["op"] for node in payload["graph"]["nodes"]]
        rotate_angles = [
            node["params"]["angle"]
            for node in payload["graph"]["nodes"]
            if node["op"] == "make_rotate_rshape"
        ]
        self.assertEqual(ops.count("make_spline_redge"), n_lobes * 2)
        self.assertEqual(rotate_angles, [half_lobe_phase])

    def test_invalid_params(self):
        with self.assertRaises(Exception):
            scad.std.gear.make_cycloidal_disc_rsolid(
                n_lobes=1,
                ring_pin_pitch_radius=18.0,
                roller_radius=1.6,
                eccentricity=0.8,
            )
        with self.assertRaises(Exception):
            scad.std.gear.make_cycloidal_disc_rsolid(
                n_lobes=10,
                ring_pin_pitch_radius=18.0,
                roller_radius=1.6,
                eccentricity=0.8,
                output_pin_count=3,
            )


class TestSpurRack(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_rack(self):
        solid = scad.std.gear.make_spur_rack_rsolid(
            module=2.0, n_teeth=8, rack_height=5.0
        )
        self.assertGreater(solid.get_volume(), 0.0)

    def test_more_teeth_larger_volume(self):
        short = scad.std.gear.make_spur_rack_rsolid(
            module=2.0, n_teeth=5, rack_height=5.0
        )
        long = scad.std.gear.make_spur_rack_rsolid(
            module=2.0, n_teeth=10, rack_height=5.0
        )
        self.assertGreater(long.get_volume(), short.get_volume())

    def test_invalid_params(self):
        with self.assertRaises(Exception):
            scad.std.gear.make_spur_rack_rsolid(module=-1.0)
        with self.assertRaises(Exception):
            scad.std.gear.make_spur_rack_rsolid(module=2.0, n_teeth=0)

    def test_rack_profile_has_no_fix_constraints(self):
        with scad.GraphSession() as session:
            scad.std.gear.make_spur_rack_rsolid(module=2.0, n_teeth=5, rack_height=5.0)

        payload = json.loads(scad.export_model_json(session))
        ops = [node["op"] for node in payload["graph"]["nodes"]]
        self.assertNotIn("make_constrain_fix_rsketch", ops)


class TestHelicalRack(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_helical_rack(self):
        solid = scad.std.gear.make_helical_rack_rsolid(
            module=2.0,
            n_teeth=8,
            helix_angle=25.0,
            rack_height=8.0,
        )
        self.assertGreater(solid.get_volume(), 0.0)


class TestHerringboneRack(unittest.TestCase):
    def setUp(self):
        scad.GraphSession()

    def test_basic_herringbone_rack(self):
        solid = scad.std.gear.make_herringbone_rack_rsolid(
            module=2.0,
            n_teeth=8,
            helix_angle=30.0,
            rack_height=10.0,
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
            ring.get_area(),
            math.pi * (100 - 16),
            places=1,
        )
        self.assertEqual(len(ring.get_inner_wires()), 1)

    def test_make_face_from_wires_rface_creates_hole(self):
        outer = scad.make_circle_rwire(center=(0, 0, 0), radius=10.0)
        inner = scad.make_circle_rwire(center=(0, 0, 0), radius=4.0)
        ring = scad.make_face_from_wires_rface(outer, [inner])
        self.assertAlmostEqual(
            ring.get_area(),
            math.pi * (100 - 16),
            places=1,
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
