"""Tests for roller-chain standard parts."""

import json
import math
import unittest

import simplecadapi as scad


class TestRollerChainSprocket(unittest.TestCase):
    def test_iso_606_12b_candidate_geometry(self):
        sprocket = scad.std.chain.make_roller_chain_sprocket_rsolid(
            n_teeth=18,
            chain_pitch=19.05,
            roller_diameter=12.07,
            sprocket_thickness=11.1,
            bore_radius=10.2,
        )

        self.assertGreater(sprocket.get_volume(), 0.0)
        meta = sprocket.get_metadata("std.chain.roller_sprocket")
        self.assertEqual(meta["n_teeth"], 18)
        self.assertAlmostEqual(
            meta["pitch_radius"],
            19.05 / (2.0 * math.sin(math.pi / 18)),
        )
        self.assertLess(meta["root_radius"], meta["pitch_radius"])
        self.assertGreater(meta["outside_radius"], meta["pitch_radius"])
        print(
            "roller_chain_sprocket: "
            f"volume={sprocket.get_volume():.3f} "
            f"pitch_radius={meta['pitch_radius']:.6f}"
        )

    def test_roller_seats_are_recorded_as_strict_cuts(self):
        with scad.GraphSession() as session:
            sprocket = scad.std.chain.make_roller_chain_sprocket_rsolid(
                n_teeth=18,
                chain_pitch=19.05,
                roller_diameter=12.07,
                sprocket_thickness=11.1,
                bore_radius=10.2,
            )
            model_json = scad.export_model_json(session=session)

        payload = json.loads(model_json)
        cut_nodes = [
            node
            for node in payload["graph"]["nodes"]
            if node["op"] == "make_cut_rsolid"
        ]
        self.assertEqual(len(cut_nodes), 1)
        self.assertEqual(cut_nodes[0]["params"]["tool_count"], 19)
        self.assertFalse(cut_nodes[0]["params"]["skip_non_intersecting"])
        self.assertEqual(cut_nodes[0]["params"]["tracking_policy"], "graph")
        self.assertTrue(
            all("topo_delta" not in node for node in payload["graph"]["nodes"])
        )

        replayed = scad.replay_model_json(json_str=model_json, strict=True)
        self.assertEqual(len(replayed), 1)
        self.assertAlmostEqual(
            replayed[0].get_volume(), sprocket.get_volume(), places=5
        )

    def test_invalid_sprocket_parameters(self):
        invalid_kwargs = (
            {
                "n_teeth": 5,
                "chain_pitch": 19.05,
                "roller_diameter": 12.07,
                "sprocket_thickness": 11.1,
            },
            {
                "n_teeth": 18,
                "chain_pitch": 0.0,
                "roller_diameter": 12.07,
                "sprocket_thickness": 11.1,
            },
            {
                "n_teeth": 18,
                "chain_pitch": 19.05,
                "roller_diameter": 19.05,
                "sprocket_thickness": 11.1,
            },
            {
                "n_teeth": 18,
                "chain_pitch": 19.05,
                "roller_diameter": 12.07,
                "sprocket_thickness": 0.0,
            },
            {
                "n_teeth": 18,
                "chain_pitch": 19.05,
                "roller_diameter": 12.07,
                "sprocket_thickness": 11.1,
                "bore_radius": 60.0,
            },
        )
        for kwargs in invalid_kwargs:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                scad.std.chain.make_roller_chain_sprocket_rsolid(**kwargs)


if __name__ == "__main__":
    unittest.main()
