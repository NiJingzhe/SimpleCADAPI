"""Contract tests for the SimpleCADAPI 2.0 rearchitecture.

These tests intentionally focus on stable public behavior and on a small number
of future-facing expression contracts. The future-facing tests are skipped until
the corresponding 2.0 APIs exist.
"""

from __future__ import annotations

import unittest

import simplecadapi as scad
from simplecadapi.graph import GraphSession


REQUIRED_GEOMETRY_TYPES = (
    "Vertex",
    "Edge",
    "Wire",
    "Face",
    "Solid",
)


REQUIRED_RSTYLE_APIS = (
    "make_point_rvertex",
    "make_line_redge",
    "make_rectangle_rface",
    "make_box_rsolid",
    "make_cylinder_rsolid",
    "extrude_rsolid",
    "revolve_rsolid",
    "fillet_rsolid",
    "chamfer_rsolid",
    "shell_rsolid",
    "cut_rsolidlist",
    "union_rsolid",
    "intersect_rsolidlist",
)


class TestRearchitecture20ApiContracts(unittest.TestCase):
    """Contracts derived from REQ-API-* in the 2.0 requirements doc."""

    def test_shape_first_geometry_types_remain_public(self):
        for type_name in REQUIRED_GEOMETRY_TYPES:
            with self.subTest(type_name=type_name):
                self.assertTrue(hasattr(scad, type_name))

    def test_rstyle_modeling_api_remains_public(self):
        for name in REQUIRED_RSTYLE_APIS:
            with self.subTest(name=name):
                self.assertTrue(hasattr(scad, name))

    def test_constant_only_modeling_requires_no_expression_wrapper(self):
        box = scad.make_box_rsolid(4.0, 5.0, 6.0)
        self.assertIsInstance(box, scad.Solid)
        self.assertGreater(box.get_volume(), 0.0)

    def test_shape_operations_remain_type_closed_for_core_workflow(self):
        face = scad.make_rectangle_rface(2.0, 1.0)
        self.assertIsInstance(face, scad.Face)

        solid = scad.extrude_rsolid(face, (0, 0, 1), 3.0)
        self.assertIsInstance(solid, scad.Solid)

        moved = scad.translate_shape(solid, (1.0, 2.0, 3.0))
        self.assertIsInstance(moved, scad.Solid)

        rotated = scad.rotate_shape(moved, 30.0, (0, 0, 1))
        self.assertIsInstance(rotated, scad.Solid)

    def test_boolean_pipeline_keeps_returning_solids(self):
        body = scad.make_box_rsolid(4.0, 4.0, 4.0)
        tool = scad.make_cylinder_rsolid(0.75, 6.0, bottom_face_center=(0.0, 0.0, -1.0))

        result = scad.cut_rsolidlist(body, tool)
        self.assertIsInstance(result, scad.Solid)


class TestRearchitecture20ExpressionContracts(unittest.TestCase):
    """Future contracts derived from REQ-EXPR-* in the 2.0 requirements doc."""

    def test_explicit_variable_api_exists(self):
        var = scad.var("r", 10.0)
        self.assertIsNotNone(var)
        self.assertIsInstance(var, scad.Var)

    def test_variable_name_is_explicit_and_preserved(self):
        var = scad.var("radius", 10.0)
        self.assertEqual(var.name, "radius")

    def test_expression_supports_standard_arithmetic(self):
        r = scad.var("r", 10.0)
        expr = ((r + 2) * 3 - 4) / 2
        self.assertIsInstance(expr, scad.Expr)
        self.assertAlmostEqual(float(expr), 16.0)

    def test_expression_system_is_unitless_phase_one(self):
        r = scad.var("r", 10.0)
        self.assertFalse(hasattr(r, "unit"))

    def test_expression_values_can_flow_into_public_modeling_apis(self):
        r = scad.var("r", 10.0)
        face = scad.make_circle_rface((0, 0, 0), r)
        self.assertIsInstance(face, scad.Face)

        solid = scad.extrude_rsolid(face, (0, 0, 1), r * 2)
        self.assertIsInstance(solid, scad.Solid)

    def test_expression_graph_is_public_and_round_trippable(self):
        graph = scad.ExpressionGraph()
        r = scad.var("r", 10.0)
        graph.register(r * 2 + 1)

        payload = graph.to_dict()
        rebuilt = scad.ExpressionGraph.from_dict(payload)

        self.assertGreaterEqual(rebuilt.node_count, 4)
        expr_nodes = [node for node in payload["nodes"] if node["kind"] == "expr"]
        self.assertGreaterEqual(len(expr_nodes), 2)

    def test_graph_session_tracks_expression_graph_separately(self):
        r = scad.var("r", 5.0)
        with GraphSession() as session:
            face = scad.make_circle_rface((0, 0, 0), r)
            solid = scad.extrude_rsolid(face, (0, 0, 1), r * 2)

        self.assertIsInstance(solid, scad.Solid)
        self.assertGreaterEqual(session.graph.node_count, 2)
        self.assertGreaterEqual(session.expression_graph.node_count, 3)

        leaf = session.graph.leaf_nodes()[0]
        self.assertIn("distance", leaf.param_exprs)
        self.assertIn("expr_id", leaf.param_exprs["distance"])

    def test_session_export_includes_expression_graph(self):
        r = scad.var("r", 3.0)
        with GraphSession() as session:
            scad.make_circle_rface((0, 0, 0), r)

        payload = scad.import_session_json(scad.export_session_json(session))
        self.assertIn("graph", payload)
        self.assertIn("expression_graph", payload)
        self.assertGreaterEqual(payload["expression_graph"].node_count, 1)


class TestRearchitecture20GeometryContracts(unittest.TestCase):
    def test_geometry_layer_remains_shape_first_not_scene_graph_first(self):
        box = scad.make_box_rsolid(1.0, 2.0, 3.0)
        self.assertFalse(hasattr(box, "children_nodes"))
        self.assertFalse(hasattr(box, "scene_transform"))

    def test_sketch_can_exist_without_replacing_shape_hierarchy(self):
        self.assertTrue(hasattr(scad, "Sketch"))
        self.assertTrue(hasattr(scad, "Face"))
        self.assertTrue(hasattr(scad, "Solid"))
        sketch = scad.Sketch()
        self.assertIsInstance(sketch, scad.Sketch)


class TestRearchitecture20KernelContracts(unittest.TestCase):
    def test_geometry_wrappers_accept_raw_occ_shapes_and_expose_wrapped_storage(self):
        solid = scad.make_box_rsolid(1.0, 2.0, 3.0)
        clone = scad.Solid(solid.wrapped)
        self.assertIsInstance(clone, scad.Solid)
        self.assertTrue(hasattr(clone, "wrapped"))
        self.assertFalse(hasattr(clone, "cq_solid"))

    def test_public_modeling_path_produces_wrapped_storage_on_shapes(self):
        face = scad.make_circle_rface((0, 0, 0), 2.0)
        solid = scad.extrude_rsolid(face, (0, 0, 1), 3.0)
        self.assertTrue(hasattr(face, "wrapped"))
        self.assertTrue(hasattr(solid, "wrapped"))


class TestRearchitecture20HistoryContracts(unittest.TestCase):
    def test_operation_graph_is_still_recorded_for_public_modeling_calls(self):
        with GraphSession() as session:
            body = scad.make_box_rsolid(4.0, 4.0, 4.0)
            tool = scad.make_cylinder_rsolid(
                0.75, 6.0, bottom_face_center=(0.0, 0.0, -1.0)
            )
            result = scad.cut_rsolidlist(body, tool)
            payload = scad.import_model_json(scad.export_model_json(session))

        self.assertIsInstance(result, scad.Solid)
        self.assertGreaterEqual(session.graph.node_count, 3)
        allowed_ops = set(payload["canonical_contract"]["core_op_set"])
        self.assertTrue(all(node.op in allowed_ops for node in session.graph.nodes))

    def test_semantic_delta_exists_alongside_topology_delta(self):
        delta = scad.SemanticDelta()
        self.assertTrue(hasattr(delta, "created"))
        self.assertTrue(hasattr(delta, "modified"))
        self.assertTrue(hasattr(delta, "deleted"))

    def test_topology_delta_types_still_exposed_in_data_model(self):
        from simplecadapi.topology import TopoDelta

        delta = TopoDelta()
        self.assertTrue(hasattr(delta, "preserved"))
        self.assertTrue(hasattr(delta, "modified"))
        self.assertTrue(hasattr(delta, "generated"))
        self.assertTrue(hasattr(delta, "deleted"))

    def test_semantic_ref_exists_beside_topo_ref(self):
        ref = scad.SemanticRef(
            graph_id="g0", node_id="n0", entity_type="Sketch", entity_id="sk0"
        )
        self.assertEqual(ref.entity_type, "Sketch")


class TestRearchitecture20AssemblyContracts(unittest.TestCase):
    def test_existing_assembly_api_still_exists_during_rearchitecture(self):
        self.assertTrue(hasattr(scad, "Assembly"))
        self.assertTrue(hasattr(scad, "make_assembly_rassembly"))

    def test_assembly_constraint_parameters_can_use_expression_graph(self):
        a = scad.make_box_rsolid(1.0, 1.0, 1.0)
        b = scad.make_box_rsolid(1.0, 1.0, 1.0)
        asm = scad.make_assembly_rassembly([("a", a), ("b", b)])
        gap = scad.var("gap", 3.0)
        asm2 = scad.constrain_offset_rassembly(
            asm,
            asm.part("a").anchor("bbox.top"),
            asm.part("b").anchor("bbox.bottom"),
            gap,
            axis="z",
        )
        self.assertGreaterEqual(asm2.expression_graph().node_count, 1)
        self.assertGreaterEqual(len(asm2.constraint_param_exprs()), 1)


class TestRearchitecture20IoContracts(unittest.TestCase):
    def test_session_export_becomes_canonical_json_seed(self):
        r = scad.var("r", 2.0)
        with GraphSession() as session:
            scad.make_circle_rface((0, 0, 0), r)

        payload = scad.import_session_json(scad.export_session_json(session))
        self.assertGreaterEqual(payload["graph"].node_count, 1)
        self.assertGreaterEqual(payload["expression_graph"].node_count, 1)

    def test_step_export_still_exists_as_final_geometry_export(self):
        self.assertTrue(hasattr(scad, "export_step"))
        self.assertTrue(hasattr(scad, "export_stl"))

    def test_model_json_export_exists_as_canonical_seed(self):
        r = scad.var("r", 2.0)
        with GraphSession() as session:
            scad.make_circle_rface((0, 0, 0), r)

        payload = scad.import_model_json(scad.export_model_json(session))
        self.assertIn("graph", payload)
        self.assertIn("expression_graph", payload)

    def test_model_json_declares_final_state_canonical_contract(self):
        with GraphSession() as session:
            scad.make_box_rsolid(1.0, 2.0, 3.0)

        payload = scad.import_model_json(scad.export_model_json(session))

        self.assertIn("canonical_contract", payload)
        contract = payload["canonical_contract"]
        self.assertEqual(contract["contract_version"], "2.0-final-state")
        self.assertEqual(contract["graph_roles"]["graph"], "canonical_low_level_graph")
        self.assertEqual(contract["graph_roles"]["leaf_ids"], "explicit_result_set")
        self.assertEqual(contract["replay_policy"]["preferred_graph"], "graph")

    def test_model_json_declares_selection_ref_resolution_order(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            scad.fillet_rsolid(box, box.get_edges()[:2], 0.2)

        payload = scad.import_model_json(scad.export_model_json(session))
        selection_schema = payload["canonical_contract"]["selection_ref_schema"]

        self.assertEqual(
            selection_schema["replay_resolution_order"],
            [
                "explicit_topo_refs",
                "stable_indices",
                "selection_query",
                "selector_hint",
            ],
        )
