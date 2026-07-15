"""Kernel-backed feature output roles, tagging, projection, and replay."""

import json
import unittest
from copy import deepcopy

import simplecadapi as scad
from simplecadapi import ql as Q


def _role_count(shape, role):
    candidates = shape.get_edges() if role == "shell.wall" else shape.get_faces()
    return sum(Q.output_role(role)(item) for item in candidates)


class TestOperationOutputRoles(unittest.TestCase):
    def test_feature_role_matrix_is_kernel_backed(self):
        profile = scad.make_rectangle_rface(2.0, 1.0)
        extruded = scad.extrude_rsolid(profile, (0, 0, 1), 2.0)
        self.assertEqual(_role_count(extruded, "extrusion.start"), 1)
        self.assertEqual(_role_count(extruded, "extrusion.end"), 1)
        self.assertEqual(_role_count(extruded, "extrusion.side"), 4)

        revolve_profile = scad.make_rectangle_rface(2.0, 1.0, center=(3, 0, 0))
        revolved = scad.revolve_rsolid(
            revolve_profile, (0, 1, 0), 180.0, (0, 0, 0)
        )
        self.assertEqual(_role_count(revolved, "revolution.start"), 1)
        self.assertEqual(_role_count(revolved, "revolution.end"), 1)
        self.assertEqual(_role_count(revolved, "revolution.side"), 4)

        first = scad.make_rectangle_rwire(2.0, 2.0)
        last = scad.make_rectangle_rwire(1.0, 1.0, center=(0, 0, 2))
        lofted = scad.loft_rsolid([first, last])
        self.assertEqual(_role_count(lofted, "loft.start"), 1)
        self.assertEqual(_role_count(lofted, "loft.end"), 1)
        self.assertEqual(_role_count(lofted, "loft.side"), 4)

        sweep_profile = scad.make_rectangle_rface(1.0, 1.0)
        path = scad.make_segment_rwire((0, 0, 0), (0, 0, 3))
        swept = scad.sweep_rsolid(sweep_profile, path)
        self.assertEqual(_role_count(swept, "sweep.start"), 1)
        self.assertEqual(_role_count(swept, "sweep.end"), 1)
        self.assertEqual(_role_count(swept, "sweep.side"), 4)

    def test_detail_feature_role_matrix_is_kernel_backed(self):
        box = scad.make_box_rsolid(4.0, 4.0, 4.0)
        edge = box.get_edges(0)
        filleted = scad.fillet_rsolid(box, [edge], 0.2)
        chamfered = scad.chamfer_rsolid(box, [edge], 0.2)
        self.assertGreaterEqual(_role_count(filleted, "fillet.patch"), 1)
        self.assertGreaterEqual(_role_count(chamfered, "chamfer.patch"), 1)

        shelled = scad.shell_rsolid(box, [box.get_faces(0)], 0.2)
        self.assertEqual(_role_count(shelled, "shell.offset_face"), 5)
        self.assertEqual(_role_count(shelled, "shell.closing_descendant"), 1)
        self.assertEqual(_role_count(shelled, "shell.wall"), 4)

    def test_full_revolve_has_no_cap_roles_and_rejects_cap_tag(self):
        profile = scad.make_rectangle_rface(2.0, 1.0, center=(3, 0, 0))
        revolved = scad.revolve_rsolid(
            profile, (0, 1, 0), 360.0, (0, 0, 0)
        )
        self.assertEqual(_role_count(revolved, "revolution.start"), 0)
        self.assertEqual(_role_count(revolved, "revolution.end"), 0)

        with self.assertRaisesRegex(
            scad.SimpleCADError, "requires exactly one kernel-proven result, got 0"
        ):
            scad.revolve_rsolid(
                profile,
                (0, 1, 0),
                360.0,
                (0, 0, 0),
                start_face_tag="role.start",
            )

    def test_unavailable_shell_role_fails_instead_of_guessing(self):
        box = scad.make_box_rsolid(4.0, 4.0, 4.0)
        with self.assertRaisesRegex(
            scad.SimpleCADError, "shell.body_face.*kernel-proven"
        ):
            scad.shell_rsolid(
                box,
                [box.get_faces(0)],
                0.2,
                body_faces_tag="group.body",
            )

    def test_sweep_rejects_profiles_with_inner_wires(self):
        outer = scad.make_rectangle_rwire(3.0, 3.0)
        inner = scad.make_rectangle_rwire(1.0, 1.0, center=(1.0, 1.0, 0.0))
        profile = scad.make_face_from_wires_rface(outer, [inner])
        path = scad.make_segment_rwire((0, 0, 0), (0, 0, 3))

        with self.assertRaisesRegex(scad.SimpleCADError, "inner wires are unsupported"):
            scad.sweep_rsolid(profile, path)


class TestOperationOutputTags(unittest.TestCase):
    @staticmethod
    def _binding_nodes(payload):
        return [
            node
            for node in payload["graph"]["nodes"]
            if node["op"] == "apply_tag_rselection"
        ]

    def test_extrude_output_tags_lower_to_role_aware_semantic_nodes(self):
        with scad.GraphSession() as session:
            profile = scad.make_rectangle_rface(5.0, 3.0)
            result = scad.extrude_rsolid(
                profile,
                (0, 0, 1),
                2.0,
                start_face_tag="anchor.base",
                end_face_tag="role.mounting_surface",
                side_faces_tag="group.outer_walls",
                result_tag="part.body",
            )

        self.assertEqual(
            len(scad.select_faces_by_tag(result, "anchor.base", scope="local")), 1
        )
        self.assertEqual(
            len(
                scad.select_faces_by_tag(
                    result, "role.mounting_surface", scope="local"
                )
            ),
            1,
        )
        self.assertEqual(
            len(
                scad.select_faces_by_tag(
                    result, "group.outer_walls", scope="local"
                )
            ),
            4,
        )
        self.assertIn("part.body", scad.list_tags(result, scope="local"))

        payload = json.loads(scad.export_model_json(session))
        feature = next(
            node
            for node in payload["graph"]["nodes"]
            if node["op"] == "make_extrude_rsolid"
        )
        self.assertNotIn("output_tags", feature["params"])
        self.assertNotIn("result_tag", feature["params"])

        binding_nodes = self._binding_nodes(payload)
        self.assertEqual(len(binding_nodes), 4)
        role_evidence = [
            node["params"]["tag_binding"]["evidence"].get(
                "operation_output_role"
            )
            for node in binding_nodes
        ]
        self.assertEqual(
            [item["role"] for item in role_evidence if item is not None],
            ["extrusion.start", "extrusion.end", "extrusion.side"],
        )
        self.assertTrue(
            all(
                node["params"]["tag_binding"]["producer"]["kind"]
                == "user_operation"
                for node in binding_nodes
            )
        )
        expected_binding_ids = {
            node["params"]["tag_binding"]["binding_id"] for node in binding_nodes
        }

        replayed = scad.replay_model_json(json.dumps(payload))[0]
        self.assertEqual(
            len(
                scad.select_faces_by_tag(
                    replayed, "group.outer_walls", scope="local"
                )
            ),
            4,
        )
        actual_binding_ids = {
            explanation["binding_id"]
            for shape, tag in [
                (replayed, "part.body"),
                *[
                    (face, tag)
                    for tag in (
                        "anchor.base",
                        "role.mounting_surface",
                        "group.outer_walls",
                    )
                    for face in scad.select_faces_by_tag(replayed, tag, scope="local")
                ],
            ]
            for explanation in scad.explain_tag(shape, tag, scope="local")
        }
        self.assertEqual(actual_binding_ids, expected_binding_ids)

    def test_shell_tags_face_and_edge_roles_and_replays(self):
        with scad.GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            result = scad.shell_rsolid(
                box,
                [box.get_faces(0)],
                0.2,
                offset_faces_tag="group.offset",
                closing_faces_tag="group.closing",
                wall_edges_tag="group.wall",
            )

        self.assertEqual(
            len(scad.select_faces_by_tag(result, "group.offset", scope="local")), 5
        )
        self.assertEqual(
            len(scad.select_faces_by_tag(result, "group.closing", scope="local")),
            1,
        )
        self.assertEqual(
            len(Q.edges().where(Q.tag("group.wall", scope="local")).resolve(result)),
            4,
        )

        replayed = scad.replay_model_json(scad.export_model_json(session))[0]
        self.assertEqual(
            len(Q.edges().where(Q.tag("group.wall", scope="local")).resolve(replayed)),
            4,
        )

    def test_remaining_feature_output_tag_surfaces_replay(self):
        cases = []

        with scad.GraphSession() as session:
            profile = scad.make_rectangle_rface(2.0, 1.0, center=(3, 0, 0))
            result = scad.revolve_rsolid(
                profile,
                (0, 1, 0),
                180.0,
                (0, 0, 0),
                start_face_tag="test.revolve.start",
                end_face_tag="test.revolve.end",
                side_faces_tag="test.revolve.side",
            )
        cases.append(
            (
                "revolve",
                result,
                scad.export_model_json(session),
                {
                    "test.revolve.start": 1,
                    "test.revolve.end": 1,
                    "test.revolve.side": 4,
                },
            )
        )

        with scad.GraphSession() as session:
            first = scad.make_rectangle_rwire(2.0, 2.0)
            last = scad.make_rectangle_rwire(1.0, 1.0, center=(0, 0, 2))
            result = scad.loft_rsolid(
                [first, last],
                start_face_tag="test.loft.start",
                end_face_tag="test.loft.end",
                side_faces_tag="test.loft.side",
            )
        cases.append(
            (
                "loft",
                result,
                scad.export_model_json(session),
                {
                    "test.loft.start": 1,
                    "test.loft.end": 1,
                    "test.loft.side": 4,
                },
            )
        )

        with scad.GraphSession() as session:
            profile = scad.make_rectangle_rface(1.0, 1.0)
            path = scad.make_segment_rwire((0, 0, 0), (0, 0, 3))
            result = scad.sweep_rsolid(
                profile,
                path,
                start_face_tag="test.sweep.start",
                end_face_tag="test.sweep.end",
                side_faces_tag="test.sweep.side",
            )
        cases.append(
            (
                "sweep",
                result,
                scad.export_model_json(session),
                {
                    "test.sweep.start": 1,
                    "test.sweep.end": 1,
                    "test.sweep.side": 4,
                },
            )
        )

        for operation, feature, payload, expected in cases:
            replayed = scad.replay_model_json(payload)[0]
            for tag, count in expected.items():
                with self.subTest(operation=operation, tag=tag):
                    authored = scad.select_faces_by_tag(feature, tag, scope="local")
                    rebuilt = scad.select_faces_by_tag(replayed, tag, scope="local")
                    self.assertEqual(len(authored), count)
                    self.assertEqual(len(rebuilt), count)
                    self.assertEqual(
                        {
                            item["binding_id"]
                            for face in authored
                            for item in scad.explain_tag(face, tag, scope="local")
                        },
                        {
                            item["binding_id"]
                            for face in rebuilt
                            for item in scad.explain_tag(face, tag, scope="local")
                        },
                    )

    def test_fillet_and_chamfer_patch_tags_replay(self):
        for operation in ("fillet", "chamfer"):
            with self.subTest(operation=operation):
                with scad.GraphSession() as session:
                    box = scad.make_box_rsolid(4.0, 4.0, 4.0)
                    edge = box.get_edges(0)
                    if operation == "fillet":
                        result = scad.fillet_rsolid(
                            box,
                            [edge],
                            0.2,
                            generated_faces_tag="test.fillet.patch",
                        )
                        tag = "test.fillet.patch"
                    else:
                        result = scad.chamfer_rsolid(
                            box,
                            [edge],
                            0.2,
                            generated_faces_tag="test.chamfer.patch",
                        )
                        tag = "test.chamfer.patch"

                authored = scad.select_faces_by_tag(result, tag, scope="local")
                replayed = scad.replay_model_json(scad.export_model_json(session))[0]
                rebuilt = scad.select_faces_by_tag(replayed, tag, scope="local")
                self.assertGreaterEqual(len(authored), 1)
                self.assertEqual(len(rebuilt), len(authored))
                self.assertEqual(
                    {
                        item["binding_id"]
                        for face in authored
                        for item in scad.explain_tag(face, tag, scope="local")
                    },
                    {
                        item["binding_id"]
                        for face in rebuilt
                        for item in scad.explain_tag(face, tag, scope="local")
                    },
                )

    def test_output_tag_validation_is_strict_and_deterministic(self):
        profile = scad.make_rectangle_rface(2.0, 1.0)
        with self.assertRaisesRegex(scad.SimpleCADError, "unsupported output role"):
            scad.extrude_rsolid(
                profile,
                (0, 0, 1),
                1.0,
                output_tags={"extrusion.guessed": "role.bad"},
            )
        with self.assertRaisesRegex(scad.SimpleCADError, "supplied through both"):
            scad.extrude_rsolid(
                profile,
                (0, 0, 1),
                1.0,
                output_tags={"extrusion.end": "role.end"},
                end_face_tag="role.other",
            )
        with self.assertRaisesRegex(scad.SimpleCADError, "is not normalized"):
            scad.extrude_rsolid(
                profile,
                (0, 0, 1),
                1.0,
                end_face_tag="Not Normalized",
            )

    def test_profile_edge_binding_projects_with_exact_source_identity(self):
        with scad.GraphSession() as session:
            profile = scad.make_rectangle_rface(5.0, 3.0)
            source_edge = profile.get_edges(0)
            profile = scad.apply_tag_rselection(
                profile, [source_edge], "role.source_edge"
            )
            tagged_source = scad.select_edges_by_tag(
                profile, "role.source_edge", scope="local"
            )[0]
            source_explanation = scad.explain_tag(
                tagged_source, "role.source_edge", scope="local"
            )[0]
            source_binding_id = source_explanation["binding_id"]
            source_topo_id = tagged_source.topo_id
            result = scad.extrude_rsolid(profile, (0, 0, 1), 2.0)

        projected = (
            Q.faces()
            .where(Q.source_binding(source_binding_id))
            .exactly(1)
            .resolve(result)
        )
        self.assertTrue(Q.source_topology(source_topo_id)(projected[0]))
        projected_explanation = scad.explain_tag(
            projected[0], "role.source_edge", scope="local"
        )[0]
        self.assertEqual(
            projected_explanation["binding"]["evidence"]["source_binding_id"],
            source_binding_id,
        )

        replayed = next(
            shape
            for shape in scad.replay_model_json(scad.export_model_json(session))
            if isinstance(shape, scad.Solid)
        )
        replayed_projected = (
            Q.faces()
            .where(Q.source_binding(source_binding_id))
            .exactly(1)
            .resolve(replayed)
        )
        self.assertTrue(Q.source_topology(source_topo_id)(replayed_projected[0]))

    def test_replay_rejects_role_binding_and_topology_role_tampering(self):
        with scad.GraphSession() as session:
            profile = scad.make_rectangle_rface(5.0, 3.0)
            scad.extrude_rsolid(
                profile, (0, 0, 1), 2.0, start_face_tag="anchor.base"
            )

        raw = json.loads(scad.export_model_json(session))
        binding_node = self._binding_nodes(raw)[0]

        damaged = deepcopy(raw)
        damaged_binding_node = next(
            node
            for node in damaged["graph"]["nodes"]
            if node["node_id"] == binding_node["node_id"]
        )
        binding = damaged_binding_node["params"]["tag_binding"]
        binding["evidence"]["operation_output_role"]["role"] = "extrusion.end"
        damaged["semantic_bindings"] = [binding]
        with self.assertRaisesRegex(
            scad.SimpleCADError, "binding targets do not match"
        ):
            scad.replay_model_json(json.dumps(damaged))

        damaged = deepcopy(raw)
        feature = next(
            node
            for node in damaged["graph"]["nodes"]
            if node["op"] == "make_extrude_rsolid"
        )
        feature["topo_delta"]["roles"].pop()
        with self.assertRaisesRegex(scad.SimpleCADError, "output-role evidence drifted"):
            scad.replay_model_json(json.dumps(damaged))


class TestOperationRoleQL(unittest.TestCase):
    def test_role_and_source_predicates_roundtrip(self):
        predicates = (
            Q.output_role("Extrusion.End"),
            Q.source_binding("tag_binding_source"),
            Q.source_topology("edge_0"),
        )
        for predicate in predicates:
            with self.subTest(kind=predicate.kind):
                self.assertEqual(
                    Q.SerializablePredicate.from_dict(predicate.to_dict()).to_dict(),
                    predicate.to_dict(),
                )

    def test_predicate_deserialization_rejects_invalid_payloads(self):
        invalid = (
            {"kind": "unknown", "data": {}, "children": []},
            {"kind": "output_role", "data": {}, "children": []},
            {
                "kind": "source_binding",
                "data": {"source_binding_id": "x", "extra": True},
                "children": [],
            },
            {"kind": "not", "data": {}, "children": []},
        )
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    Q.SerializablePredicate.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
