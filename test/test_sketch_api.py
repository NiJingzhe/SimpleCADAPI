"""Focused tests for declarative sketch construction and constraints."""

from __future__ import annotations

import json
import unittest

import simplecadapi as scad
from simplecadapi import ql as Q


class TestSketchApi(unittest.TestCase):
    def test_sketch_accepts_wire_and_can_build_profile_faces(self):
        wire = scad.make_rectangle_rwire(2.0, 1.0)
        sketch = scad.Sketch([wire])

        self.assertEqual(len(sketch.curves()), 1)
        self.assertEqual(len(sketch.closed_wires()), 1)
        faces = sketch.to_faces()
        self.assertEqual(len(faces), 1)
        self.assertIsInstance(faces[0], scad.Face)

    def _make_constrained_rectangle(self):
        width = scad.var("sketch_width", 2.0)
        height = scad.var("sketch_height", 1.0)
        sketch = scad.make_sketch_rsketch("rect")
        sketch = scad.add_point_rsketch(sketch, "p0", 0.0, 0.0)
        sketch = scad.add_point_rsketch(sketch, "p1", 2.0, 0.0)
        sketch = scad.add_point_rsketch(sketch, "p2", 2.0, 1.0)
        sketch = scad.add_point_rsketch(sketch, "p3", 0.0, 1.0)
        sketch = scad.add_line_rsketch(sketch, "bottom", "p0", "p1")
        sketch = scad.add_line_rsketch(sketch, "right", "p1", "p2")
        sketch = scad.add_line_rsketch(sketch, "top", "p2", "p3")
        sketch = scad.add_line_rsketch(sketch, "left", "p3", "p0")
        sketch = scad.constrain_horizontal_rsketch(sketch, "bottom")
        sketch = scad.constrain_vertical_rsketch(sketch, "right")
        sketch = scad.constrain_parallel_rsketch(sketch, "bottom", "top")
        sketch = scad.constrain_parallel_rsketch(sketch, "left", "right")
        sketch = scad.constrain_perpendicular_rsketch(sketch, "bottom", "right")
        sketch = scad.constrain_equal_length_rsketch(sketch, "bottom", "top")
        sketch = scad.constrain_equal_length_rsketch(sketch, "left", "right")
        sketch = scad.constrain_distance_rsketch(sketch, "p0", "p1", width)
        sketch = scad.constrain_distance_rsketch(sketch, "p0", "p3", height)
        sketch = scad.constrain_fix_rsketch(sketch, "p0")
        return sketch

    def test_sketch_document_updates_are_functional(self):
        original = scad.make_sketch_rsketch("functional")
        with_point = scad.add_point_rsketch(original, "p0", 0.0, 0.0)

        self.assertNotIn("p0", original.entities)
        self.assertIn("p0", with_point.entities)
        self.assertIsNot(original, with_point)

    def test_isomorphic_sketch_api_solves_rectangle_and_builds_face(self):
        sketch = self._make_constrained_rectangle()

        result = scad.inspect_sketch_rsketchresult(
            sketch, require_fully_constrained=True
        )
        self.assertEqual(result.status, "solved")
        self.assertEqual(result.dof, 0)
        self.assertAlmostEqual(result.residual_norm, 0.0, places=7)

        face = scad.make_face_from_sketch_rface(sketch, require_fully_constrained=True)
        self.assertIsInstance(face, scad.Face)
        self.assertAlmostEqual(face.get_area(), 2.0, places=6)
        self.assertEqual(face.get_metadata("sketch_solve")["status"], "solved")
        self.assertEqual(face.get_metadata("source_sketch")["name"], "rect")

        edge_tags = set()
        for edge in face.get_edges():
            edge_tags.update(scad.list_tags(edge))
        self.assertIn("sketch.rect", scad.list_tags(face))
        self.assertIn("sketch_entity.bottom", edge_tags)
        self.assertIn("sketch_entity.right", edge_tags)
        self.assertIn("sketch_entity.top", edge_tags)
        self.assertIn("sketch_entity.left", edge_tags)

    def test_circle_sketch_constraints_build_circular_face(self):
        sketch = scad.make_sketch_rsketch("circle")
        sketch = scad.add_point_rsketch(sketch, "center", 0.0, 0.0)
        sketch = scad.add_circle_rsketch(sketch, "outer", "center", 1.5)
        circle = scad.get_sketch_entity_rsketchref(sketch, "outer")
        sketch = scad.constrain_fix_rsketch(sketch, "center")
        sketch = scad.constrain_radius_rsketch(sketch, circle, 1.5)

        result = scad.inspect_sketch_rsketchresult(
            sketch, require_fully_constrained=True
        )
        self.assertEqual(result.status, "solved")
        face = scad.make_face_from_sketch_rface(sketch, require_fully_constrained=True)
        self.assertAlmostEqual(face.get_area(), 3.141592653589793 * 2.25, places=5)
        self.assertIn("sketch_entity.outer", scad.list_tags(face.get_edges(0)))

    def test_constrained_sketch_promotion_has_topology_identity_tags(self):
        sketch = self._make_constrained_rectangle()
        face = scad.make_face_from_sketch_rface(
            sketch, require_fully_constrained=True
        )

        self.assertEqual(
            len(Q.faces().where(Q.tag("sketch.rect.profile.bottom")).resolve(face)),
            1,
        )
        for entity_id in ("bottom", "right", "top", "left"):
            edges = Q.edges().where(
                Q.tag(f"sketch.rect.entity.{entity_id}")
            ).resolve(face)
            self.assertEqual(len(edges), 1)
            evidence = scad.explain_tag(
                edges[0], f"sketch.rect.entity.{entity_id}", scope="local"
            )[0]["binding"]["evidence"]
            self.assertEqual(evidence["evidence_method"], "SketchPromotionMap")
            self.assertEqual(
                evidence["sketch_promotion"]["entity_id"], entity_id
            )
            self.assertEqual(evidence["topology_name"]["kind"], "edge")

    def test_constrained_sketch_wire_promotion_has_topology_identity_tags(self):
        sketch = self._make_constrained_rectangle()
        wire = scad.make_wire_from_sketch_rwire(
            sketch, require_fully_constrained=True
        )

        self.assertEqual(
            len(Q.wires().where(Q.tag("sketch.rect.profile.bottom")).resolve(wire)),
            1,
        )
        for entity_id in ("bottom", "right", "top", "left"):
            edges = Q.edges().where(
                Q.tag(f"sketch.rect.entity.{entity_id}")
            ).resolve(wire)
            self.assertEqual(len(edges), 1)
            evidence = scad.explain_tag(
                edges[0], f"sketch.rect.entity.{entity_id}", scope="local"
            )[0]["binding"]["evidence"]
            self.assertEqual(evidence["evidence_method"], "SketchPromotionMap")
            self.assertEqual(
                evidence["sketch_promotion"]["entity_id"], entity_id
            )
            self.assertEqual(evidence["topology_name"]["kind"], "edge")

    def test_constrained_sketch_topology_tags_project_and_replay(self):
        with scad.GraphSession() as session:
            sketch = self._make_constrained_rectangle()
            profile = scad.make_face_from_sketch_rface(sketch)
            body = scad.extrude_rsolid(
                profile, (0, 0, 1), 2.0, tag_prefix="body"
            )

        expected_tags = {
            "body.face.side.bottom",
            "body.face.side.right",
            "body.face.side.top",
            "body.face.side.left",
        }
        self.assertEqual(
            {
                tag
                for face in body.get_faces()
                for tag in scad.list_tags(face, scope="local")
                if tag.startswith("body.face.side.")
            },
            expected_tags,
        )

        payload = json.loads(scad.export_model_json(session))
        promotion = next(
            node
            for node in payload["graph"]["nodes"]
            if node["op"] == "make_face_from_sketch_rface"
        )
        self.assertEqual(
            promotion["params"]["promotion_map"]["topology_name"]["kind"],
            "face",
        )
        self.assertEqual(
            [
                edge["topology_name"]["local_name"]
                for edge in promotion["params"]["promotion_map"]["edges"]
            ],
            ["bottom", "right", "top", "left"],
        )

        replayed = scad.replay_model_json(json.dumps(payload))
        rebuilt = next(shape for shape in replayed if isinstance(shape, scad.Solid))
        self.assertEqual(
            {
                tag
                for face in rebuilt.get_faces()
                for tag in scad.list_tags(face, scope="local")
                if tag.startswith("body.face.side.")
            },
            expected_tags,
        )

    def test_underconstrained_and_conflicting_sketches_report_diagnostics(self):
        sketch = scad.make_sketch_rsketch("open")
        sketch = scad.add_point_rsketch(sketch, "p0", 0.0, 0.0)
        sketch = scad.add_point_rsketch(sketch, "p1", 1.0, 0.0)
        sketch = scad.add_line_rsketch(sketch, "line", "p0", "p1")
        result = scad.inspect_sketch_rsketchresult(sketch, strict=False)
        self.assertEqual(result.status, "underconstrained")
        self.assertGreater(result.dof, 0)

        bad = scad.make_sketch_rsketch("bad")
        bad = scad.add_point_rsketch(bad, "a", 0.0, 0.0)
        bad = scad.add_point_rsketch(bad, "b", 1.0, 0.0)
        bad = scad.add_line_rsketch(bad, "line", "a", "b")
        bad = scad.constrain_distance_rsketch(bad, "a", "b", 1.0)
        bad = scad.constrain_distance_rsketch(bad, "a", "b", 2.0)
        bad = scad.constrain_fix_rsketch(bad, "a")
        bad_result = scad.inspect_sketch_rsketchresult(bad, strict=False)
        self.assertEqual(bad_result.status, "conflicting")
        self.assertTrue(any(diag.code == "residual_too_large" for diag in bad_result.diagnostics))

    def test_sketch_refs_are_scoped_to_their_sketch(self):
        first = scad.make_sketch_rsketch("first")
        second = scad.make_sketch_rsketch("second")
        first = scad.add_point_rsketch(first, "p0", 0.0, 0.0)
        second = scad.add_point_rsketch(second, "p1", 1.0, 0.0)
        p0 = scad.get_sketch_point_rsketchref(first, "p0")
        p1 = scad.get_sketch_point_rsketchref(second, "p1")

        with self.assertRaises(Exception):
            scad.add_line_rsketch(first, "bad", p0, p1)

    def test_graph_replay_preserves_sketch_to_face_result(self):
        with scad.GraphSession() as session:
            sketch = self._make_constrained_rectangle()
            face = scad.make_face_from_sketch_rface(sketch)

        ops = [node.op for node in session.graph.nodes]
        self.assertIn("make_sketch_rsketch", ops)
        self.assertIn("make_add_point_rsketch", ops)
        self.assertIn("make_constrain_parallel_rsketch", ops)
        self.assertIn("make_face_from_sketch_rface", ops)
        self.assertNotIn("make_sketch_point_rsketchref", ops)
        self.assertNotIn("make_solve_sketch_rsketchresult", ops)

        payload = json.loads(scad.export_model_json(session))
        promotion = next(
            node for node in payload["graph"]["nodes"] if node["op"] == "make_face_from_sketch_rface"
        )
        self.assertEqual(promotion["params"]["solve_snapshot"]["status"], "solved")
        self.assertIn("promotion_map", promotion["params"])

        replayed = scad.replay_model_json(json.dumps(payload))
        self.assertEqual(len(replayed), 1)
        self.assertIsInstance(replayed[0], scad.Face)
        self.assertAlmostEqual(replayed[0].get_area(), face.get_area(), places=6)

    def test_graph_replay_preserves_sketch_bspline_definition(self):
        with scad.GraphSession() as session:
            sketch = scad.make_sketch_rsketch("spline")
            sketch = scad.add_point_rsketch(sketch, "p0", 0.0, 0.0)
            sketch = scad.add_point_rsketch(sketch, "p1", 4.0, 0.0)
            sketch = scad.add_bspline_rsketch(
                sketch,
                "curve",
                "p0",
                "p1",
                control_points=[
                    [0.0, 0.0],
                    [1.0, 1.5],
                    [3.0, 1.5],
                    [4.0, 0.0],
                ],
                degree=3,
                knots=[0.0, 1.0],
                multiplicities=[4, 4],
            )

        payload = json.loads(scad.export_model_json(session))
        spline_node = next(
            node for node in payload["graph"]["nodes"] if node["op"] == "make_add_bspline_rsketch"
        )
        self.assertEqual(len(spline_node["params"]["control_points"]), 4)
        self.assertEqual(spline_node["params"]["knots"], [0.0, 1.0])
        self.assertEqual(spline_node["params"]["multiplicities"], [4, 4])

        replayed = scad.replay_model_json(json.dumps(payload))
        self.assertEqual(len(replayed), 1)
        self.assertIsInstance(replayed[0], scad.Sketch)
        self.assertEqual(
            replayed[0].entities["curve"].data["control_points"],
            sketch.entities["curve"].data["control_points"],
        )

    def test_strict_replay_requires_sketch_solve_snapshot(self):
        with scad.GraphSession() as session:
            sketch = self._make_constrained_rectangle()
            scad.make_face_from_sketch_rface(sketch)

        payload = json.loads(scad.export_model_json(session))
        promotion = next(
            node for node in payload["graph"]["nodes"] if node["op"] == "make_face_from_sketch_rface"
        )
        del promotion["params"]["solve_snapshot"]

        with self.assertRaises(Exception):
            scad.replay_model_json(json.dumps(payload))

        replayed = scad.replay_model_json(json.dumps(payload), strict=False)
        self.assertEqual(len(replayed), 1)
        self.assertIsInstance(replayed[0], scad.Face)

    def test_strict_snapshot_comparison_rejects_changed_solved_entity(self):
        from simplecadapi.operations import _assert_sketch_solve_snapshot_dict_matches

        recorded = {
            "status": "solved",
            "dof": 0,
            "residual_norm": 0.0,
            "solved_points": {},
            "solved_scalars": {},
            "solved_entities": {
                "circle": {"kind": "circle", "center": [0.0, 0.0], "radius": 1.0}
            },
        }
        changed = json.loads(json.dumps(recorded))
        changed["solved_entities"]["circle"]["radius"] = 1.5

        with self.assertRaisesRegex(ValueError, "circle.*radius"):
            _assert_sketch_solve_snapshot_dict_matches(changed, recorded)

    def test_default_solver_backend_is_py_slvs_and_persisted_in_snapshot(self):
        result = scad.inspect_sketch_rsketchresult(
            self._make_constrained_rectangle(),
            require_fully_constrained=True,
        )

        self.assertEqual(scad.get_default_sketch_solver_backend().name, "py-slvs")
        self.assertEqual(result.backend, "py-slvs")
        self.assertEqual(result.backend_version, "1.0.6")
        self.assertEqual(result.backend_status_code, 5)
        self.assertEqual(result.to_dict()["backend"], "py-slvs")

    def test_custom_solver_backend_can_be_selected_without_changing_sketch(self):
        class OffsetBackend:
            name = "test-offset"
            version = "1"

            def solve(self, sketch, *, options):
                self.options = options
                return scad.SketchSolveResult(
                    sketch_id=sketch.sketch_id,
                    status="underconstrained",
                    dof=2,
                    residual_norm=0.0,
                    iterations=0,
                    solved_points={"p": (3.0, 4.0)},
                    solved_scalars={},
                    backend=self.name,
                    backend_version=self.version,
                )

        sketch = scad.make_sketch_rsketch("custom")
        sketch = scad.add_point_rsketch(sketch, "p", 0.0, 0.0)
        backend = OffsetBackend()
        scad.register_sketch_solver_backend(backend)

        result = sketch.solve(backend="test-offset", strict=False)

        self.assertEqual(result.solved_points["p"], (3.0, 4.0))
        self.assertEqual(result.backend, "test-offset")
        self.assertEqual(backend.options.tolerance, 1e-7)
        self.assertEqual(sketch.entities["p"].data, {"x": 0.0, "y": 0.0})

    def test_reference_dimension_is_measured_without_driving_geometry(self):
        sketch = scad.make_sketch_rsketch("reference")
        sketch = scad.add_point_rsketch(sketch, "a", 0.0, 0.0)
        sketch = scad.add_point_rsketch(sketch, "b", 3.0, 4.0)
        sketch = scad.constrain_fix_rsketch(sketch, "a")
        sketch = scad.constrain_fix_rsketch(sketch, "b")
        sketch = scad.constrain_distance_rsketch(
            sketch,
            "a",
            "b",
            99.0,
            constraint_id="measured",
            driving=False,
        )

        result = scad.inspect_sketch_rsketchresult(
            sketch,
            require_fully_constrained=True,
        )

        self.assertEqual(result.status, "solved")
        self.assertEqual(result.solved_scalars["constraint:measured:value"], 5.0)


    def test_arc_and_bspline_solve_results_cover_non_point_entities(self):
        sketch = scad.make_sketch_rsketch("curves")
        for point_id, point in {
            "center": (0.0, 0.0),
            "arc_start": (1.0, 0.0),
            "arc_end": (0.0, 1.0),
            "spline_start": (1.0, 0.0),
            "spline_end": (3.0, 0.0),
        }.items():
            sketch = scad.add_point_rsketch(sketch, point_id, *point)
        sketch = scad.add_arc_rsketch(sketch, "arc", "arc_start", "arc_end", "center")
        sketch = scad.add_bspline_rsketch(
            sketch,
            "spline",
            "spline_start",
            "spline_end",
            [(1.0, 0.0), (1.5, 1.0), (2.5, 1.0), (3.0, 0.0)],
            knots=[0.0, 1.0],
            multiplicities=[4, 4],
        )
        result = scad.inspect_sketch_rsketchresult(sketch, strict=False)

        self.assertEqual(result.solved_entities["arc"]["kind"], "arc")
        self.assertAlmostEqual(result.solved_entities["arc"]["radius"], 1.0)
        self.assertEqual(result.solved_entities["spline"]["kind"], "bspline")
        self.assertEqual(result.solved_entities["spline"]["solver_representation"], "cubic_bezier")
        self.assertEqual(len(result.solved_entities["spline"]["control_points"]), 4)

    def test_tangent_modes_and_curve_endpoint_selectors_are_serializable(self):
        sketch = scad.make_sketch_rsketch("tangent_modes")
        sketch = scad.add_point_rsketch(sketch, "a", 0.0, 0.0)
        sketch = scad.add_point_rsketch(sketch, "b", 5.0, 0.0)
        sketch = scad.add_circle_rsketch(sketch, "left", "a", 2.0)
        sketch = scad.add_circle_rsketch(sketch, "right", "b", 1.0)
        sketch = scad.constrain_tangent_rsketch(
            sketch, "left", "right", mode="internal", constraint_id="internal"
        )
        tangent = sketch.constraints[-1]

        self.assertEqual(tangent.metadata["mode"], "internal")
        payload = sketch.to_dict()
        self.assertEqual(payload["constraints"][-1]["metadata"]["mode"], "internal")

        for mode, distance in (("external", 3.0), ("internal", 1.0)):
            solved = scad.make_sketch_rsketch(f"{mode}_tangent")
            solved = scad.add_point_rsketch(solved, "a", 0.0, 0.0)
            solved = scad.add_point_rsketch(solved, "b", distance, 0.0)
            solved = scad.add_circle_rsketch(solved, "left", "a", 2.0)
            solved = scad.add_circle_rsketch(solved, "right", "b", 1.0)
            solved = scad.constrain_fix_rsketch(solved, "left")
            solved = scad.constrain_fix_rsketch(solved, "right")
            solved = scad.constrain_tangent_rsketch(
                solved, "left", "right", mode=mode, constraint_id="tangent"
            )
            result = scad.inspect_sketch_rsketchresult(
                solved, require_fully_constrained=True
            )
            self.assertEqual(result.status, "solved")

    def test_reference_length_measurement_supports_bspline(self):
        sketch = scad.make_sketch_rsketch("spline_measure")
        sketch = scad.add_point_rsketch(sketch, "a", 0.0, 0.0)
        sketch = scad.add_point_rsketch(sketch, "b", 3.0, 0.0)
        sketch = scad.add_bspline_rsketch(
            sketch,
            "curve",
            "a",
            "b",
            [(0.0, 0.0), (1.0, 1.0), (2.0, 1.0), (3.0, 0.0)],
            knots=[0.0, 1.0],
            multiplicities=[4, 4],
        )
        sketch = scad.constrain_fix_rsketch(sketch, "curve")
        sketch = scad.constrain_length_rsketch(
            sketch, "curve", 0.0, driving=False, constraint_id="curve_length"
        )
        result = scad.inspect_sketch_rsketchresult(sketch, require_fully_constrained=True)

        self.assertGreater(result.solved_scalars["constraint:curve_length:value"], 3.0)

    def test_reference_arc_length_uses_radius_and_sweep(self):
        sketch = scad.make_sketch_rsketch("arc_measure")
        sketch = scad.add_point_rsketch(sketch, "center", 0.0, 0.0)
        sketch = scad.add_point_rsketch(sketch, "start", 1.0, 0.0)
        sketch = scad.add_point_rsketch(sketch, "end", 0.0, 1.0)
        sketch = scad.add_arc_rsketch(sketch, "arc", "start", "end", "center")
        sketch = scad.constrain_fix_rsketch(sketch, "arc")
        sketch = scad.constrain_length_rsketch(
            sketch, "arc", 0.0, driving=False, constraint_id="arc_length"
        )
        result = scad.inspect_sketch_rsketchresult(sketch, require_fully_constrained=True)

        self.assertAlmostEqual(
            result.solved_scalars["constraint:arc_length:value"],
            result.solved_entities["arc"]["length"],
        )

    def test_driving_curve_length_is_rejected_instead_of_using_chord_length(self):
        sketch = scad.make_sketch_rsketch("arc_driving_length")
        sketch = scad.add_point_rsketch(sketch, "center", 0.0, 0.0)
        sketch = scad.add_point_rsketch(sketch, "start", 1.0, 0.0)
        sketch = scad.add_point_rsketch(sketch, "end", 0.0, 1.0)
        sketch = scad.add_arc_rsketch(sketch, "arc", "start", "end", "center")
        sketch = scad.constrain_length_rsketch(sketch, "arc", 2.0)

        with self.assertRaisesRegex(ValueError, "Driving length constraints.*only for lines"):
            scad.inspect_sketch_rsketchresult(sketch)

    def test_reference_rational_bspline_length_uses_weights(self):
        sketch = scad.make_sketch_rsketch("rational_spline_measure")
        sketch = scad.add_point_rsketch(sketch, "a", 1.0, 0.0)
        sketch = scad.add_point_rsketch(sketch, "b", 0.0, 1.0)
        sketch = scad.add_bspline_rsketch(
            sketch,
            "curve",
            "a",
            "b",
            [(1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
            degree=2,
            knots=[0.0, 1.0],
            multiplicities=[3, 3],
            weights=[1.0, 2.0**-0.5, 1.0],
        )
        sketch = scad.constrain_fix_rsketch(sketch, "curve")
        sketch = scad.constrain_length_rsketch(
            sketch, "curve", 0.0, driving=False, constraint_id="curve_length"
        )
        result = scad.inspect_sketch_rsketchresult(sketch, require_fully_constrained=True)

        self.assertAlmostEqual(
            result.solved_scalars["constraint:curve_length:value"],
            0.5 * 3.141592653589793,
            places=3,
        )

if __name__ == "__main__":
    unittest.main()
