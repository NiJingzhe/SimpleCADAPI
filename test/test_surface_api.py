from __future__ import annotations

import json
import unittest
from copy import deepcopy

import simplecadapi as scad


class TestSurfaceApi(unittest.TestCase):
    @staticmethod
    def _line_wire(start, end):
        return scad.make_wire_from_edges_rwire([scad.make_line_redge(start, end)])

    def test_public_surface_namespace_and_basic_faces(self):
        self.assertIs(scad.surface.make_bezier_surface_rface, scad.make_bezier_surface_rface)
        self.assertIs(scad.surface.SurfaceBoundary, scad.SurfaceBoundary)

        bezier = scad.make_bezier_surface_rface(
            [[(0, 0, 0), (0, 1, 0)], [(1, 0, 0), (1, 1, 0)]]
        )
        fitted = scad.fit_point_grid_rface(
            [[(0, 0, 0), (0, 1, 0)], [(1, 0, 0), (1, 1, 0)]],
            degree_min=1,
            degree_max=3,
        )

        self.assertIsInstance(bezier, scad.Face)
        self.assertIsInstance(fitted, scad.Face)
        self.assertAlmostEqual(bezier.get_area(), 1.0, places=6)
        self.assertAlmostEqual(fitted.get_area(), 1.0, places=6)

    def test_workplane_bezier_model_replay_preserves_geometry_and_tag(self):
        with scad.GraphSession() as session:
            with scad.Workplane(
                origin=(10.0, 20.0, 30.0),
                normal=(0.0, 1.0, 0.0),
                x_dir=(1.0, 0.0, 0.0),
            ):
                original = scad.make_bezier_surface_rface(
                    [[(0, 0, 0), (0, 1, 0)], [(1, 0, 0), (1, 1, 1)]],
                    tag_prefix="skin",
                )

        replayed = scad.replay_model_json(scad.export_model_json(session))[0]
        original_center = original.get_center()
        replayed_center = replayed.get_center()

        self.assertIsInstance(replayed, scad.Face)
        self.assertAlmostEqual(replayed.get_area(), original.get_area(), places=8)
        self.assertAlmostEqual(replayed_center.x, original_center.x, places=8)
        self.assertAlmostEqual(replayed_center.y, original_center.y, places=8)
        self.assertAlmostEqual(replayed_center.z, original_center.z, places=8)
        self.assertIn("skin.face", scad.list_tags(replayed))

    def test_derived_surface_builders_and_replay(self):
        with scad.GraphSession() as session:
            profile_edges = [
                scad.make_line_redge((0, 0, 0), (1, 0, 0)),
                scad.make_line_redge((0, 1, 0), (1, 1, 0)),
            ]
            guide_edges = [
                scad.make_line_redge((0, 0, 0), (0, 1, 0)),
                scad.make_line_redge((1, 0, 0), (1, 1, 0)),
            ]
            gordon = scad.make_gordon_surface_rface(profile_edges, guide_edges)

            points = [(0, 0, 1), (2, 0, 1), (2, 2, 1), (0, 2, 1)]
            edges = [
                scad.make_line_redge(points[index], points[(index + 1) % 4])
                for index in range(4)
            ]
            patch = scad.make_surface_patch_rface(
                [scad.SurfaceBoundary(edge) for edge in edges],
                tag_prefix="patch",
            )
            scad.capture_result(value=[gordon, patch])

        replayed = scad.replay_model_json(scad.export_model_json(session))
        self.assertEqual(len(replayed), 2)
        self.assertAlmostEqual(replayed[0].get_area(), gordon.get_area(), places=7)
        self.assertAlmostEqual(replayed[1].get_area(), patch.get_area(), places=7)
        self.assertEqual(len(replayed[1].get_edges()), 4)
        self.assertIn("patch.face", scad.list_tags(replayed[1]))

    def test_shell_loft_roles_names_point_profiles_and_replay(self):
        with scad.GraphSession() as session:
            lower = scad.make_circle_rwire((0, 0, 0), 2.0)
            upper = scad.make_circle_rwire((0, 0, 2), 1.0)
            open_shell = scad.loft_rshell(
                [lower, upper],
                tag_prefix="skin",
                result_tag="part.skin",
                start_wire_tag="anchor.inlet",
                end_wire_tag="anchor.outlet",
                side_faces_tag="group.side",
            )
            scad.capture_result(value=open_shell)

        replayed = scad.replay_model_json(scad.export_model_json(session), strict=True)[0]
        self.assertIsInstance(replayed, scad.Shell)
        self.assertFalse(replayed.is_closed())
        self.assertEqual(len(replayed.get_wires()), 2)
        self.assertEqual(
            len(scad.ql.wires().where(scad.ql.tag("anchor.inlet")).resolve(replayed)),
            1,
        )
        self.assertEqual(
            len(scad.ql.wires().where(scad.ql.tag("anchor.outlet")).resolve(replayed)),
            1,
        )
        self.assertEqual(
            len(scad.ql.faces().where(scad.ql.tag("group.side")).resolve(replayed)),
            1,
        )
        self.assertIn("part.skin", scad.list_tags(replayed))
        self.assertIn("skin.shell", scad.list_tags(replayed))

        point = scad.make_point_rvertex(0, 0, 4)
        pointed = scad.loft_rshell([upper, point], start_wire_tag="anchor.base")
        self.assertEqual(len(pointed.get_wires()), 1)
        self.assertEqual(
            len(scad.ql.wires().where(scad.ql.tag("anchor.base")).resolve(pointed)),
            1,
        )

    def test_sew_and_free_boundary_multi_output_replay(self):
        with scad.GraphSession() as session:
            face = scad.make_bezier_surface_rface(
                [[(0, 0, 0), (0, 1, 0)], [(1, 0, 0), (1, 1, 0)]]
            )
            shell = scad.sew_faces_rshell([face])
            boundaries = scad.free_boundaries_rwirelist(shell)
            scad.capture_result(value=boundaries)

        replayed = scad.replay_model_json(scad.export_model_json(session))
        self.assertEqual(len(boundaries), 1)
        self.assertEqual(len(replayed), 1)
        original_length = sum(edge.get_length() for edge in boundaries[0].get_edges())
        replayed_length = sum(edge.get_length() for edge in replayed[0].get_edges())
        self.assertAlmostEqual(replayed_length, original_length, places=8)

    def test_closed_shell_free_boundaries_records_zero_outputs(self):
        with scad.GraphSession() as session:
            lower = scad.make_circle_rwire((0, 0, 0), 1.0)
            upper = scad.make_circle_rwire((0, 0, 2), 1.0)
            closed_shell = scad.fill_holes_rshell(scad.loft_rshell([lower, upper]))
            boundaries = scad.free_boundaries_rwirelist(closed_shell)

        node = session.graph.leaf_nodes()[0]
        self.assertEqual(boundaries, [])
        self.assertEqual(node.op, "free_boundaries_rwirelist")
        self.assertEqual(node.output_count, 0)
        self.assertEqual(scad.replay_model_json(scad.export_model_json(session)), [])

    def test_loft_rejects_middle_points_and_missing_endpoint_topology(self):
        lower = scad.make_circle_rwire((0, 0, 0), 2.0)
        middle = scad.make_point_rvertex(0, 0, 2)
        upper = scad.make_circle_rwire((0, 0, 4), 1.0)

        with self.assertRaisesRegex(scad.SimpleCADError, "only at the start or end"):
            scad.loft_rshell([lower, middle, upper])
        with self.assertRaisesRegex(scad.SimpleCADError, "end_wire_tag requires"):
            scad.loft_rshell([lower, middle], end_wire_tag="anchor.end")
        with self.assertRaisesRegex(scad.SimpleCADError, "end_face_tag requires"):
            scad.loft_rsolid([lower, middle], end_face_tag="anchor.end")

    def test_strict_replay_rejects_ordered_input_ref_tampering(self):
        with scad.GraphSession() as session:
            edge_a = scad.make_line_redge((0, 0, 0), (1, 0, 0))
            edge_b = scad.make_line_redge((0, 0, 1), (1, 0, 1))
            scad.make_ruled_surface_rface(edge_a, edge_b)

        payload = json.loads(scad.export_model_json(session))
        damaged = deepcopy(payload)
        ruled_node = next(
            node
            for node in damaged["graph"]["nodes"]
            if node["op"] == "make_ruled_surface_rface"
        )
        ruled_node["params"]["input_refs"][0]["output_slot"] = 99

        with self.assertRaisesRegex(scad.SimpleCADError, "missing output slot 99"):
            scad.replay_model_json(json.dumps(damaged), strict=True)

    def test_invalid_surface_inputs_use_public_error_contract(self):
        with self.assertRaisesRegex(scad.SimpleCADError, "rectangular finite grid"):
            scad.make_bezier_surface_rface([[(0, 0, 0)]])
        with self.assertRaisesRegex(scad.SimpleCADError, "positive tolerance"):
            scad.fit_point_grid_rface(
                [[(0, 0, 0), (0, 1, 0)], [(1, 0, 0), (1, 1, 0)]],
                tolerance=0.0,
            )


if __name__ == "__main__":
    unittest.main()
