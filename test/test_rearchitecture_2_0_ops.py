"""Focused 2.0 operation-level tests for remaining core operations."""

from __future__ import annotations

import unittest
from unittest import mock

import simplecadapi as scad
from simplecadapi import operations
from simplecadapi.graph import GraphSession


class TestRearchitecture20CoreOps(unittest.TestCase):
    def test_cylinder_accepts_expression_parameters(self):
        r = scad.var("r", 1.5)
        h = scad.var("h", 4.0)
        solid = scad.make_cylinder_rsolid(r, h, bottom_face_center=(0, 0, 0))
        self.assertIsInstance(solid, scad.Solid)
        self.assertGreater(solid.get_volume(), 0.0)

    def test_revolve_accepts_expression_angle(self):
        angle = scad.var("angle", 180.0)
        face = scad.make_rectangle_rface(1.0, 2.0, center=(1.0, 0.0, 0.0))
        solid = scad.revolve_rsolid(face, axis=(0, 1, 0), angle=angle, origin=(0, 0, 0))
        self.assertIsInstance(solid, scad.Solid)

    def test_revolve_produces_topology_delta_at_runtime(self):
        face = scad.make_rectangle_rface(1.0, 2.0, center=(1.0, 0.0, 0.0))
        with GraphSession() as session:
            solid = scad.revolve_rsolid(
                face, axis=(0, 1, 0), angle=180.0, origin=(0, 0, 0)
            )

        self.assertIsInstance(solid, scad.Solid)
        leaf = session.graph.leaf_nodes()[0]
        self.assertEqual(leaf.op, "make_revolve_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_revolve_topology_delta_survives_graph_json_roundtrip(self):
        face = scad.make_rectangle_rface(1.0, 2.0, center=(1.0, 0.0, 0.0))
        with GraphSession() as session:
            scad.revolve_rsolid(face, axis=(0, 1, 0), angle=180.0, origin=(0, 0, 0))

        restored = scad.import_graph_json(scad.export_graph_json(session.graph))
        leaf = restored.leaf_nodes()[0]

        self.assertEqual(leaf.op, "make_revolve_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_loft_produces_topology_delta_at_runtime(self):
        a = scad.make_rectangle_rwire(2.0, 2.0, center=(0.0, 0.0, 0.0))
        b = scad.make_rectangle_rwire(1.0, 1.0, center=(0.0, 0.0, 2.0))
        with GraphSession() as session:
            solid = scad.loft_rsolid([a, b])

        self.assertIsInstance(solid, scad.Solid)
        leaf = session.graph.leaf_nodes()[0]
        self.assertEqual(leaf.op, "make_loft_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_loft_topology_delta_survives_graph_json_roundtrip(self):
        a = scad.make_rectangle_rwire(2.0, 2.0, center=(0.0, 0.0, 0.0))
        b = scad.make_rectangle_rwire(1.0, 1.0, center=(0.0, 0.0, 2.0))
        with GraphSession() as session:
            scad.loft_rsolid([a, b])

        restored = scad.import_graph_json(scad.export_graph_json(session.graph))
        leaf = restored.leaf_nodes()[0]

        self.assertEqual(leaf.op, "make_loft_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_point_profile_loft_replays_with_existing_endpoint_roles(self):
        with GraphSession() as session:
            base = scad.make_circle_rwire((0.0, 0.0, 0.0), 2.0)
            tip = scad.make_point_rvertex(0.0, 0.0, 5.0)
            solid = scad.loft_rsolid(
                [base, tip],
                tag_prefix="cone",
                start_face_tag="anchor.base",
                side_faces_tag="group.side",
            )
            session.capture_result(value=solid)

        replayed = scad.replay_model_json(scad.export_model_json(session), strict=True)[0]
        self.assertIsInstance(replayed, scad.Solid)
        self.assertAlmostEqual(replayed.get_volume(), solid.get_volume(), places=6)
        self.assertEqual(
            len(scad.ql.faces().where(scad.ql.tag("anchor.base")).resolve(replayed)),
            1,
        )
        self.assertEqual(
            len(scad.ql.faces().where(scad.ql.tag("group.side")).resolve(replayed)),
            1,
        )
        self.assertEqual(
            len(scad.ql.faces().where(scad.ql.tag("cone.face.start")).resolve(replayed)),
            1,
        )


    def test_loft_graph_tracking_records_replayable_node_without_topology_delta(self):
        with GraphSession() as session:
            a = scad.make_rectangle_rwire(2.0, 2.0, center=(0.0, 0.0, 0.0))
            b = scad.make_rectangle_rwire(1.0, 1.0, center=(0.0, 0.0, 2.0))
            solid = scad.loft_rsolid(
                [a, b], tracking_policy=scad.TrackingPolicy.GRAPH
            )
            session.capture_result(value=solid)

        loft = next(
            node for node in session.graph.nodes if node.op == "make_loft_rsolid"
        )
        self.assertIsNone(loft.topo_delta)
        self.assertEqual(loft.params["tracking_policy"], "graph")
        self.assertEqual(len(loft.inputs), 2)

        replayed = scad.replay_model_json(scad.export_model_json(session))[0]
        self.assertIsInstance(replayed, scad.Solid)
        self.assertAlmostEqual(replayed.get_volume(), solid.get_volume(), places=6)

    def test_loft_graph_tracking_rejects_topology_role_tags(self):
        a = scad.make_rectangle_rwire(2.0, 2.0, center=(0.0, 0.0, 0.0))
        b = scad.make_rectangle_rwire(1.0, 1.0, center=(0.0, 0.0, 2.0))

        with self.assertRaisesRegex(
            scad.SimpleCADError, "GRAPH tracking does not provide loft face-role evidence"
        ):
            scad.loft_rsolid(
                [a, b],
                tracking_policy=scad.TrackingPolicy.GRAPH,
                side_faces_tag="face.loft.side",
            )

    def test_union_graph_tracking_records_replayable_node_without_topology_delta(self):
        with GraphSession() as session:
            a = scad.make_box_rsolid(2.0, 2.0, 2.0)
            b = scad.make_box_rsolid(
                2.0,
                2.0,
                2.0,
                bottom_face_center=(1.0, 0.0, 0.0),
            )
            solid = scad.union_rsolid(
                a,
                b,
                glue=False,
                tracking_policy=scad.TrackingPolicy.GRAPH,
            )
            session.capture_result(value=solid)

        union = next(
            node for node in session.graph.nodes if node.op == "make_union_rsolid"
        )
        self.assertIsNone(union.topo_delta)
        self.assertIsNotNone(union.semantic_delta)
        self.assertEqual(union.params["tracking_policy"], "graph")
        self.assertEqual(len(union.inputs), 2)
        self.assertNotIn("has_delta", solid.get_metadata("track"))

        replayed = scad.replay_model_json(scad.export_model_json(session))[0]
        self.assertIsInstance(replayed, scad.Solid)
        self.assertAlmostEqual(replayed.get_volume(), solid.get_volume(), places=6)

    def test_cut_graph_tracking_records_replayable_node_without_topology_delta(self):
        with GraphSession() as session:
            body = scad.make_box_rsolid(4.0, 4.0, 4.0)
            tool = scad.make_cylinder_rsolid(
                0.75,
                6.0,
                bottom_face_center=(0.0, 0.0, -1.0),
            )
            solid = scad.cut_rsolid(
                body,
                tool,
                skip_non_intersecting=False,
                tracking_policy=scad.TrackingPolicy.GRAPH,
            )
            session.capture_result(value=solid)

        cut = next(
            node for node in session.graph.nodes if node.op == "make_cut_rsolid"
        )
        self.assertIsNone(cut.topo_delta)
        self.assertIsNotNone(cut.semantic_delta)
        self.assertEqual(cut.params["tracking_policy"], "graph")
        self.assertEqual(len(cut.inputs), 2)
        self.assertNotIn("has_delta", solid.get_metadata("track"))
        self.assertIn("solid.boolean.cut", scad.list_tags(solid, scope="local"))

        replayed = scad.replay_model_json(scad.export_model_json(session))[0]
        self.assertIsInstance(replayed, scad.Solid)
        self.assertAlmostEqual(replayed.get_volume(), solid.get_volume(), places=6)

    def test_graph_booleans_do_not_call_topology_history_helpers(self):
        body = scad.make_box_rsolid(4.0, 4.0, 4.0)
        cutter = scad.make_cylinder_rsolid(
            0.75,
            6.0,
            bottom_face_center=(0.0, 0.0, -1.0),
        )
        rib = scad.make_box_rsolid(
            2.0,
            2.0,
            2.0,
            bottom_face_center=(1.5, 0.0, 0.0),
        )

        with mock.patch.object(
            operations,
            "tracked_cut",
            side_effect=AssertionError("GRAPH cut queried topology history"),
        ):
            cut = scad.cut_rsolid(
                body,
                cutter,
                tracking_policy=scad.TrackingPolicy.GRAPH,
            )

        with mock.patch.object(
            operations,
            "fuse_shapes_with_history",
            side_effect=AssertionError("GRAPH union requested topology history"),
        ), mock.patch.object(
            operations,
            "track_union_history",
            side_effect=AssertionError("GRAPH union queried topology history"),
        ):
            fused = scad.union_rsolid(
                body,
                rib,
                glue=False,
                tracking_policy=scad.TrackingPolicy.GRAPH,
            )

        self.assertLess(cut.get_volume(), body.get_volume())
        self.assertGreater(fused.get_volume(), body.get_volume())

    def test_sweep_produces_topology_delta_at_runtime(self):
        profile = scad.make_circle_rface((0.0, 0.0, 0.0), 0.5)
        path = scad.make_segment_rwire((0.0, 0.0, 0.0), (0.0, 0.0, 3.0))
        with GraphSession() as session:
            solid = scad.sweep_rsolid(profile, path)

        self.assertIsInstance(solid, scad.Solid)
        leaf = session.graph.leaf_nodes()[0]
        self.assertEqual(leaf.op, "make_sweep_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_sweep_topology_delta_survives_graph_json_roundtrip(self):
        profile = scad.make_circle_rface((0.0, 0.0, 0.0), 0.5)
        path = scad.make_segment_rwire((0.0, 0.0, 0.0), (0.0, 0.0, 3.0))
        with GraphSession() as session:
            scad.sweep_rsolid(profile, path)

        restored = scad.import_graph_json(scad.export_graph_json(session.graph))
        leaf = restored.leaf_nodes()[0]

        self.assertEqual(leaf.op, "make_sweep_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_twisted_sweep_produces_replayable_topology_delta(self):
        with GraphSession() as session:
            profile = scad.make_rectangle_rface(width=2.0, height=1.0)
            solid = scad.twisted_sweep_rsolid(
                profile=profile,
                distance=5.0,
                twist_angle=-45.0,
            )
            session.capture_result(value=solid)

        node = next(
            item
            for item in session.graph.nodes
            if item.op == "make_twisted_sweep_rsolid"
        )
        self.assertIsNotNone(node.topo_delta)
        self.assertEqual(len(solid.get_faces()), 6)

        replayed = scad.replay_model_json(
            scad.export_model_json(session), strict=True
        )[0]
        self.assertEqual(len(replayed.get_faces()), 6)
        self.assertAlmostEqual(replayed.get_volume(), solid.get_volume(), places=8)

    def test_twisted_sweep_supports_expression_parameters_and_arbitrary_axis(self):
        distance = scad.var("twisted_distance", 5.0)
        angle = scad.var("twisted_angle", 45.0)
        with GraphSession() as session:
            profile = scad.make_rectangle_rface(
                width=2.0,
                height=1.0,
                normal=(1.0, 1.0, 1.0),
            )
            solid = scad.twisted_sweep_rsolid(
                profile=profile,
                distance=distance,
                twist_angle=angle,
                axis=(1.0, 1.0, 1.0),
            )
            session.capture_result(value=solid)

        node = next(
            item
            for item in session.graph.nodes
            if item.op == "make_twisted_sweep_rsolid"
        )
        self.assertEqual(set(node.param_exprs), {"distance", "twist_angle"})
        self.assertEqual(len(solid.get_faces()), 6)

        replayed = scad.replay_model_json(
            scad.export_model_json(session), strict=True
        )[0]
        self.assertAlmostEqual(replayed.get_volume(), solid.get_volume(), places=8)

    def test_twisted_sweep_rejects_inner_wires_and_invalid_axis(self):
        outer = scad.make_circle_rface(center=(0.0, 0.0, 0.0), radius=2.0)
        inner = scad.make_circle_rface(center=(0.0, 0.0, 0.0), radius=1.0)
        ring = scad.make_2d_cut_rface(body=outer, tool=inner)

        with self.assertRaises(scad.SimpleCADError):
            scad.twisted_sweep_rsolid(
                profile=ring,
                distance=2.0,
                twist_angle=20.0,
            )
        with self.assertRaises(scad.SimpleCADError):
            scad.twisted_sweep_rsolid(
                profile=outer,
                distance=2.0,
                twist_angle=20.0,
                axis=(0.0, 0.0, 0.0),
            )
        with self.assertRaises(scad.SimpleCADError):
            scad.twisted_sweep_rsolid(
                profile=outer,
                distance=2.0,
                twist_angle=20.0,
                axis=(1.0, 0.0, 0.0),
            )
        offset = scad.translate_shape(outer, vector=(0.0, 0.0, 1.0))
        with self.assertRaises(scad.SimpleCADError):
            scad.twisted_sweep_rsolid(
                profile=offset,
                distance=2.0,
                twist_angle=20.0,
            )

    def test_fillet_accepts_expression_radius_and_records_param_expr(self):
        radius = scad.var("fillet_r", 0.2)
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            result = scad.fillet_rsolid(box, [box.get_edges(i) for i in range(4)], radius)

        self.assertIsInstance(result, scad.Solid)
        leaf = session.graph.leaf_nodes()[0]
        self.assertEqual(leaf.op, "make_fillet_rsolid")
        self.assertIn("radius", leaf.param_exprs)

    def test_chamfer_accepts_expression_distance_and_records_param_expr(self):
        distance = scad.var("chamfer_d", 0.2)
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            result = scad.chamfer_rsolid(box, [box.get_edges(i) for i in range(4)], distance)

        self.assertIsInstance(result, scad.Solid)
        leaf = session.graph.leaf_nodes()[0]
        self.assertEqual(leaf.op, "make_chamfer_rsolid")
        self.assertIn("distance", leaf.param_exprs)

    def test_shell_accepts_expression_thickness_and_records_param_expr(self):
        thickness = scad.var("shell_t", 0.2)
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            result = scad.shell_rsolid(box, [box.get_faces(0)], thickness)

        self.assertIsInstance(result, scad.Solid)
        leaf = session.graph.leaf_nodes()[0]
        self.assertEqual(leaf.op, "make_shell_rsolid")
        self.assertIn("thickness", leaf.param_exprs)

    def test_shell_produces_topology_delta_at_runtime(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            result = scad.shell_rsolid(box, [box.get_faces(0)], 0.2)

        self.assertIsInstance(result, scad.Solid)
        leaf = session.graph.leaf_nodes()[0]
        self.assertEqual(leaf.op, "make_shell_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )

    def test_shell_topology_delta_survives_graph_json_roundtrip(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            scad.shell_rsolid(box, [box.get_faces(0)], 0.2)

        restored = scad.import_graph_json(scad.export_graph_json(session.graph))
        leaf = restored.leaf_nodes()[0]

        self.assertEqual(leaf.op, "make_shell_rsolid")
        self.assertIsNotNone(leaf.topo_delta)
        self.assertGreaterEqual(
            len(leaf.topo_delta.modified)
            + len(leaf.topo_delta.generated)
            + len(leaf.topo_delta.deleted),
            1,
        )


if __name__ == "__main__":
    unittest.main()
