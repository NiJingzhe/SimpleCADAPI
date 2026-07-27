"""Tests for parameterized bolt and nut standard parts."""

import json
import unittest

import simplecadapi as scad


class TestFastenerSurface(unittest.TestCase):
    def test_preferred_nested_std_export_surface(self):
        bolt = scad.std.fastener.make_bolt_rsolid(diameter=8.0, length=24.0)
        nut = scad.std.fastener.make_nut_rsolid(
            diameter=8.0,
            width=13.0,
            height=6.5,
        )

        self.assertIsInstance(bolt, scad.Solid)
        self.assertIsInstance(nut, scad.Solid)

    def test_public_factories_follow_make_rtype_naming(self):
        factory_names = [
            name
            for name in scad.std.fastener.__all__
            if callable(getattr(scad.std.fastener, name, None))
        ]

        self.assertEqual(factory_names, ["make_bolt_rsolid", "make_nut_rsolid"])
        for name in factory_names:
            self.assertTrue(name.startswith("make_"), name)
            self.assertIn("_r", name, name)


class TestBoltSolid(unittest.TestCase):
    def test_supported_head_and_drive_styles(self):
        styles = (
            ("hex", "none"),
            ("square", "slot"),
            ("cylindrical", "hex_socket"),
            ("button", "cross"),
            ("countersunk", "slot"),
        )
        for head_style, drive_style in styles:
            with self.subTest(head_style=head_style, drive_style=drive_style):
                bolt = scad.std.fastener.make_bolt_rsolid(
                    diameter=8.0,
                    length=24.0,
                    head_style=head_style,
                    thread_style="partial",
                    drive_style=drive_style,
                )
                meta = bolt.get_metadata("std.fastener.bolt")

                self.assertGreater(bolt.get_volume(), 0.0)
                self.assertEqual(meta["head_style"], head_style)
                self.assertEqual(meta["drive_style"], drive_style)
                self.assertEqual(meta["thread_start"], 24.0 - meta["thread_length"])

    def test_thread_styles_record_expected_interval(self):
        none = scad.std.fastener.make_bolt_rsolid(
            diameter=8.0,
            length=24.0,
            thread_style="none",
        )
        full = scad.std.fastener.make_bolt_rsolid(
            diameter=8.0,
            length=24.0,
            thread_style="full",
        )
        partial = scad.std.fastener.make_bolt_rsolid(
            diameter=8.0,
            length=24.0,
            thread_style="partial",
            thread_length=15.0,
        )

        none_meta = none.get_metadata("std.fastener.bolt")
        full_meta = full.get_metadata("std.fastener.bolt")
        partial_meta = partial.get_metadata("std.fastener.bolt")
        self.assertEqual(none_meta["thread_length"], 0.0)
        self.assertEqual(full_meta["thread_start"], 0.0)
        self.assertEqual(full_meta["thread_length"], 24.0)
        self.assertEqual(partial_meta["thread_start"], 9.0)
        self.assertEqual(partial_meta["thread_length"], 15.0)

    def test_metric_coarse_series_and_basic_thread_dimensions(self):
        bolt = scad.std.fastener.make_bolt_rsolid(
            diameter=10.0,
            length=40.0,
        )
        meta = bolt.get_metadata("std.fastener.bolt")

        self.assertEqual(meta["thread_pitch"], 1.5)
        self.assertEqual(meta["thread_pitch_source"], "metric_coarse")
        self.assertAlmostEqual(meta["pitch_diameter"], 10.0 - 0.6495 * 1.5, places=5)
        self.assertAlmostEqual(
            meta["basic_minor_diameter"],
            10.0 - 1.0825 * 1.5,
            places=5,
        )
        self.assertEqual(meta["thread_style"], "partial")
        self.assertEqual(meta["thread_start"], 14.0)
        self.assertEqual(meta["thread_length"], 26.0)
        self.assertAlmostEqual(meta["head_width"], 16.0)
        self.assertAlmostEqual(meta["head_height"], 6.4)
        self.assertAlmostEqual(meta["head_across_corners"], 16.0 / 0.8660254038)
        self.assertAlmostEqual(meta["underhead_fillet_radius"], 0.6)
        self.assertEqual(meta["recommended_mating_hole_chamfer_min"], 0.6)

    def test_explicit_thread_pitch_is_required_outside_coarse_series(self):
        with self.assertRaises(ValueError):
            scad.std.fastener.make_bolt_rsolid(diameter=9.0, length=24.0)

        bolt = scad.std.fastener.make_bolt_rsolid(
            diameter=9.0,
            length=24.0,
            thread_pitch=1.25,
        )
        self.assertEqual(
            bolt.get_metadata("std.fastener.bolt")["thread_pitch_source"],
            "explicit",
        )

    def test_auto_uses_full_thread_when_standard_partial_length_exceeds_length(self):
        bolt = scad.std.fastener.make_bolt_rsolid(
            diameter=4.0,
            length=13.0,
            thread_detail="cosmetic",
        )
        meta = bolt.get_metadata("std.fastener.bolt")

        self.assertEqual(meta["requested_thread_style"], "auto")
        self.assertEqual(meta["thread_style"], "full")
        self.assertEqual(meta["thread_length"], 13.0)

    def test_modeled_external_thread_strict_replay(self):
        with scad.GraphSession() as session:
            bolt = scad.std.fastener.make_bolt_rsolid(
                diameter=8.0,
                length=24.0,
                head_style="button",
                thread_style="partial",
                thread_detail="modeled",
                thread_form="v",
                thread_pitch=1.25,
                thread_depth=0.65,
                thread_length=18.0,
                drive_style="cross",
            )
            model_json = scad.export_model_json(session=session)

        payload = json.loads(model_json)
        ops = [node["op"] for node in payload["graph"]["nodes"]]
        self.assertIn("make_helix_redge", ops)
        self.assertIn("make_sweep_rsolid", ops)
        self.assertIn("make_cut_rsolid", ops)
        self.assertTrue(
            all("topo_delta" not in node for node in payload["graph"]["nodes"])
        )

        replayed = scad.replay_model_json(json_str=model_json, strict=True)
        self.assertEqual(len(replayed), 1)
        self.assertAlmostEqual(replayed[0].get_volume(), bolt.get_volume(), places=5)
        print(
            "modeled_bolt: "
            f"volume={bolt.get_volume():.3f} faces={len(bolt.get_faces())}"
        )

    def test_external_thread_stabilization_records_only_selected_phase(self):
        with scad.GraphSession() as session:
            bolt = scad.std.fastener.make_bolt_rsolid(
                diameter=6.0,
                length=18.0,
                thread_style="full",
                thread_detail="modeled",
                thread_form="v",
                thread_pitch=1.0,
                thread_depth=0.45,
            )
            model_json = scad.export_model_json(session=session)

        meta = bolt.get_metadata("std.fastener.bolt")
        payload = json.loads(model_json)
        ops = [node["op"] for node in payload["graph"]["nodes"]]
        self.assertNotEqual(meta["thread_phase_degrees"], 0.0)
        self.assertEqual(ops.count("make_rotate_rshape"), 1)
        replayed = scad.replay_model_json(json_str=model_json, strict=True)
        self.assertAlmostEqual(replayed[0].get_volume(), bolt.get_volume(), places=5)

    def test_invalid_bolt_parameters(self):
        invalid_kwargs = (
            {"diameter": 0.0, "length": 24.0},
            {"diameter": 8.0, "length": 24.0, "head_style": "wing"},
            {"diameter": 8.0, "length": 24.0, "head_width": 7.0},
            {
                "diameter": 8.0,
                "length": 24.0,
                "thread_style": "partial",
                "thread_length": 24.0,
            },
            {
                "diameter": 8.0,
                "length": 24.0,
                "thread_style": "full",
                "thread_length": 12.0,
            },
            {
                "diameter": 8.0,
                "length": 24.0,
                "drive_style": "none",
                "drive_size": 4.0,
            },
        )
        for kwargs in invalid_kwargs:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                scad.std.fastener.make_bolt_rsolid(**kwargs)


class TestNutSolid(unittest.TestCase):
    def test_supported_nut_and_hole_styles(self):
        for nut_style in ("hex", "square", "round", "knurled"):
            for hole_style in ("through", "blind"):
                with self.subTest(nut_style=nut_style, hole_style=hole_style):
                    kwargs = {"hole_depth": 5.0} if hole_style == "blind" else {}
                    nut = scad.std.fastener.make_nut_rsolid(
                        diameter=8.0,
                        width=13.0,
                        height=6.5,
                        nut_style=nut_style,
                        hole_style=hole_style,
                        **kwargs,
                    )
                    meta = nut.get_metadata("std.fastener.nut")

                    self.assertGreater(nut.get_volume(), 0.0)
                    self.assertEqual(meta["nut_style"], nut_style)
                    self.assertEqual(meta["hole_style"], hole_style)

    def test_blind_hole_retains_more_material_than_through_hole(self):
        through = scad.std.fastener.make_nut_rsolid(
            diameter=8.0,
            width=13.0,
            height=7.0,
            hole_style="through",
        )
        blind = scad.std.fastener.make_nut_rsolid(
            diameter=8.0,
            width=13.0,
            height=7.0,
            hole_style="blind",
            hole_depth=5.0,
        )

        self.assertGreater(blind.get_volume(), through.get_volume())

    def test_modeled_internal_thread_strict_replay(self):
        cosmetic = scad.std.fastener.make_nut_rsolid(
            diameter=8.0,
            width=13.0,
            height=7.0,
            nut_style="knurled",
            hole_style="blind",
            hole_depth=5.5,
            thread_detail="cosmetic",
            knurl_count=18,
        )
        with scad.GraphSession() as session:
            modeled = scad.std.fastener.make_nut_rsolid(
                diameter=8.0,
                width=13.0,
                height=7.0,
                nut_style="knurled",
                hole_style="blind",
                hole_depth=5.5,
                thread_detail="modeled",
                thread_form="trapezoidal",
                thread_pitch=1.25,
                thread_depth=0.65,
                knurl_count=18,
            )
            model_json = scad.export_model_json(session=session)

        self.assertGreater(modeled.get_volume(), cosmetic.get_volume())
        payload = json.loads(model_json)
        ops = [node["op"] for node in payload["graph"]["nodes"]]
        self.assertIn("make_helix_redge", ops)
        self.assertIn("make_sweep_rsolid", ops)
        self.assertIn("make_union_rsolid", ops)
        self.assertTrue(
            all("topo_delta" not in node for node in payload["graph"]["nodes"])
        )

        replayed = scad.replay_model_json(json_str=model_json, strict=True)
        self.assertEqual(len(replayed), 1)
        self.assertAlmostEqual(replayed[0].get_volume(), modeled.get_volume(), places=5)
        print(
            "modeled_nut: "
            f"volume={modeled.get_volume():.3f} faces={len(modeled.get_faces())}"
        )

    def test_internal_thread_stabilization_records_only_selected_phase(self):
        with scad.GraphSession() as session:
            nut = scad.std.fastener.make_nut_rsolid(
                diameter=6.0,
                width=10.0,
                height=5.0,
                thread_detail="modeled",
                thread_form="trapezoidal",
                thread_pitch=1.0,
                thread_depth=0.45,
            )
            model_json = scad.export_model_json(session=session)

        meta = nut.get_metadata("std.fastener.nut")
        payload = json.loads(model_json)
        ops = [node["op"] for node in payload["graph"]["nodes"]]
        self.assertNotEqual(meta["thread_phase_degrees"], 0.0)
        self.assertEqual(ops.count("make_rotate_rshape"), 1)
        replayed = scad.replay_model_json(json_str=model_json, strict=True)
        self.assertAlmostEqual(replayed[0].get_volume(), nut.get_volume(), places=5)

    def test_invalid_nut_parameters(self):
        invalid_kwargs = (
            {"diameter": 8.0, "width": 8.2, "height": 6.5},
            {
                "diameter": 8.0,
                "width": 13.0,
                "height": 6.5,
                "nut_style": "castle",
            },
            {
                "diameter": 8.0,
                "width": 13.0,
                "height": 6.5,
                "hole_style": "through",
                "hole_depth": 5.0,
            },
            {
                "diameter": 8.0,
                "width": 13.0,
                "height": 6.5,
                "hole_style": "blind",
                "hole_depth": 6.5,
            },
            {
                "diameter": 8.0,
                "width": 13.0,
                "height": 6.5,
                "nut_style": "knurled",
                "knurl_count": 6,
            },
        )
        for kwargs in invalid_kwargs:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                scad.std.fastener.make_nut_rsolid(**kwargs)


if __name__ == "__main__":
    unittest.main()
