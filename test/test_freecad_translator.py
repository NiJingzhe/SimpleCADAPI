"""Tests for FreeCAD script translation layer."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import mock
import unittest

import simplecadapi as scad
from simplecadapi.graph import GraphSession
from simplecadapi.topology import OperationGraph


class TestFreeCADTranslator(unittest.TestCase):
    def _expr_alias(self, expr_id: str) -> str:
        alias = "".join(ch if str(ch).isalnum() else "_" for ch in str(expr_id)).strip(
            "_"
        )
        if not alias:
            alias = "expr"
        if alias[0].isdigit():
            alias = f"expr_{alias}"
        return alias[:64]

    def _sheet_alias(self, node: dict, row: int) -> str:
        expr_id = str(node.get("expr_id", f"expr_{row}"))
        kind = str(node.get("kind", "expr"))
        if kind == "var":
            name = str(node.get("name", "")).strip()
            if name:
                return self._sanitize_alias(f"var_{name}", prefix="var")
        if kind == "const":
            return self._sanitize_alias(
                f"const_{self._const_value_alias_token(node.get('value'))}_{self._expr_short_suffix(expr_id)}",
                prefix="const",
            )
        op = str(node.get("op", "expr")).strip() or "expr"
        return self._sanitize_alias(
            f"expr_{op}_{self._expr_short_suffix(expr_id)}", prefix="expr"
        )

    def _expr_short_suffix(self, expr_id: str) -> str:
        raw = str(expr_id).rsplit("_", 1)[-1]
        alias = "".join(ch if str(ch).isalnum() else "_" for ch in str(raw)).strip("_")
        return alias[:8] if alias else "id"

    def _const_value_alias_token(self, value: object) -> str:
        try:
            number = float(value)
        except Exception:
            return "value"
        alias = f"{number:.6g}".replace("-", "neg_").replace(".", "_")
        alias = "".join(ch if str(ch).isalnum() else "_" for ch in str(alias)).strip(
            "_"
        )
        return alias or "value"

    def _sanitize_alias(self, raw: str, prefix: str = "expr") -> str:
        alias = "".join(ch if str(ch).isalnum() else "_" for ch in str(raw)).strip("_")
        if not alias:
            alias = prefix
        if alias[0].isdigit():
            alias = f"{prefix}_{alias}"
        return alias[:64]

    def _discover_freecadcmd(self) -> str | None:
        return (
            shutil.which("FreeCADCmd")
            or shutil.which("freecadcmd")
            or (
                "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
                if os.path.exists(
                    "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
                )
                else None
            )
        )

    def _inspect_fcstd_json(self, payload: str, probe_source: str) -> dict:
        freecad_cmd = self._discover_freecadcmd()
        if not freecad_cmd:
            self.skipTest("freecadcmd not available")

        with tempfile.TemporaryDirectory() as tmp_dir:
            fcstd_path = os.path.join(tmp_dir, "model.FCStd")
            probe_path = os.path.join(tmp_dir, "probe.py")
            out_path = os.path.join(tmp_dir, "probe.json")
            scad.translate_model_json_to_fcstd(
                payload, fcstd_path, freecad_cmd=freecad_cmd
            )
            with open(probe_path, "w", encoding="utf-8") as fh:
                fh.write(f"FCSTD_PATH = {json.dumps(fcstd_path)}\n")
                fh.write(f"OUT_PATH = {json.dumps(out_path)}\n")
                fh.write(probe_source)
            subprocess.run(
                [freecad_cmd, probe_path],
                check=True,
                text=True,
                capture_output=True,
            )
            with open(out_path, "r", encoding="utf-8") as fh:
                return json.load(fh)

    def _expression_payload(self, payload: str) -> dict:
        payload_obj = json.loads(payload)
        payload_obj["expression_graph"] = {"nodes": []}
        return payload_obj

    def test_translate_model_json_emits_freecad_api_script_for_steps(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(2.0, 3.0, 4.0)
            scad.translate_shape(box, (1.0, 2.0, 3.0))

        script = scad.translate_model_json_to_freecad_script(
            scad.export_model_json(session)
        )

        self.assertIn("import FreeCAD as App", script)
        self.assertIn("Sketcher::SketchObject", script)
        self.assertIn("Part::Extrusion", script)
        self.assertIn("_register_graph_folded_alias", script)
        self.assertNotIn("doc.addObject('App::Link'", script)
        self.assertIn("SimpleCADNodeId", script)
        self.assertIn("EXPRESSION_GRAPH_META", script)
        self.assertIn("# Step", script)

    def test_translate_model_json_folds_single_use_translate_into_extrusion_fcstd(self):
        tx = scad.var("fold_tx", 1.0)
        ty = scad.var("fold_ty", 2.0)
        tz = scad.var("fold_tz", 3.0)
        with GraphSession() as session:
            profile = scad.make_circle_rface((0.0, 0.0, 0.0), 1.0)
            solid = scad.extrude_rsolid(profile, (0.0, 0.0, 1.0), 2.0)
            scad.translate_shape(solid, (tx, ty, tz))
        payload = scad.export_model_json(session)
        script = scad.translate_model_json_to_freecad_script(payload)
        self.assertIn("_register_graph_folded_alias", script)
        self.assertNotIn("doc.addObject('App::Link'", script)
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
extrusions = [obj for obj in doc.Objects if getattr(obj, 'SimpleCADOp', '') == 'make_extrude_rsolid']
links = [obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'App::Link']
extrusion = extrusions[-1]
folded = json.loads(getattr(extrusion, 'SimpleCADFoldedOps', '[]') or '[]')
exprs = list(getattr(extrusion, 'ExpressionEngine', []))
shape = extrusion.Shape
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'extrusion_count': len(extrusions),
        'link_count': len(links),
        'placement': [float(extrusion.Placement.Base.x), float(extrusion.Placement.Base.y), float(extrusion.Placement.Base.z)],
        'folded_ops': [item.get('op') for item in folded],
        'folded_count': len(folded),
        'exprs': exprs,
        'solid_count': 0 if shape.isNull() else len(shape.Solids),
        'volume': 0.0 if shape.isNull() else float(shape.Volume),
    }, fh)
"""
        result = self._inspect_fcstd_json(payload, probe)

        self.assertEqual(result["extrusion_count"], 1)
        self.assertEqual(result["link_count"], 0)
        self.assertEqual(result["placement"], [1.0, 2.0, 3.0])
        self.assertEqual(result["folded_ops"], ["make_translate_rshape"])
        self.assertEqual(result["folded_count"], 1)
        self.assertEqual(result["solid_count"], 1)
        self.assertAlmostEqual(result["volume"], 2.0 * 3.141592653589793, places=5)
        expr_map = {prop: expr for prop, expr in result["exprs"]}
        normalized_expr_map = {prop.lstrip("."): expr for prop, expr in result["exprs"]}
        self.assertIn("Placement.Base.x", normalized_expr_map)
        self.assertIn("Placement.Base.y", normalized_expr_map)
        self.assertIn("Placement.Base.z", normalized_expr_map)
        self.assertIn("var_fold_tx", normalized_expr_map["Placement.Base.x"])
        self.assertIn("var_fold_ty", normalized_expr_map["Placement.Base.y"])
        self.assertIn("var_fold_tz", normalized_expr_map["Placement.Base.z"])

    def test_translate_model_json_keeps_link_when_translate_input_is_shared(self):
        with GraphSession() as session:
            profile = scad.make_circle_rface((0.0, 0.0, 0.0), 1.0)
            solid = scad.extrude_rsolid(profile, (0.0, 0.0, 1.0), 2.0)
            scad.translate_shape(solid, (1.0, 0.0, 0.0))
            scad.translate_shape(solid, (0.0, 1.0, 0.0))
        payload = scad.export_model_json(session)
        script = scad.translate_model_json_to_freecad_script(payload)
        self.assertIn("doc.addObject('App::Link'", script)
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
links = [obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'App::Link']
extrusions = [obj for obj in doc.Objects if getattr(obj, 'SimpleCADOp', '') == 'make_extrude_rsolid']
folded_counts = [len(json.loads(getattr(obj, 'SimpleCADFoldedOps', '[]') or '[]')) for obj in extrusions]
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'link_count': len(links),
        'link_ops': [getattr(obj, 'SimpleCADOp', '') for obj in links],
        'linked_ops': [getattr(getattr(obj, 'LinkedObject', None), 'SimpleCADOp', '') for obj in links],
        'folded_counts': folded_counts,
    }, fh)
"""
        result = self._inspect_fcstd_json(payload, probe)

        self.assertEqual(result["link_count"], 2)
        self.assertEqual(result["link_ops"], ["make_translate_rshape", "make_translate_rshape"])
        self.assertEqual(result["linked_ops"], ["make_extrude_rsolid", "make_extrude_rsolid"])
        self.assertEqual(result["folded_counts"], [0])

    def test_translate_model_json_uses_single_low_level_graph(self):
        with GraphSession() as session:
            scad.make_box_rsolid(2.0, 3.0, 4.0)

        script = scad.translate_model_json_to_freecad_script(
            scad.export_model_json(session)
        )

        self.assertIn("Sketcher::SketchObject", script)
        self.assertIn("Part::Extrusion", script)

    def test_translate_model_json_requires_graph(self):
        payload = {
            "schema_version": "2.0",
            "canonical_contract": {"contract_version": "2.0"},
            "expression_graph": {"nodes": []},
            "frame_graph": {"nodes": []},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
        }

        with self.assertRaises(ValueError):
            scad.translate_model_json_to_freecad_script(json.dumps(payload))

    def test_translate_model_json_emits_expression_formulas_for_ir(self):
        r = scad.var("r", 5.0)
        with GraphSession() as session:
            face = scad.make_circle_rface((0.0, 0.0, 0.0), r)
            scad.extrude_rsolid(face, (0.0, 0.0, 1.0), r * 2)

        script = scad.translate_model_json_to_freecad_script(
            scad.export_model_json(session)
        )

        self.assertIn("SimpleCADExpressions", script)
        self.assertIn("setAlias", script)
        self.assertIn("<<SimpleCADExpressions>>", script)
        self.assertIn("LengthFwd", script)
        self.assertIn("OP_EXPRESSION_BINDINGS", script)
        self.assertIn("_apply_op_expression_bindings", script)
        self.assertIn("'make_extrude_rsolid'", script)
        self.assertIn("var_r", script)
        self.assertIn(
            "=<<SimpleCADExpressions>>.var_r * <<SimpleCADExpressions>>.const_", script
        )

    def test_translate_model_json_uses_semantic_spreadsheet_aliases_and_formulas(self):
        x = scad.var("hub_radius", 6.5, comment="Hub outer radius")
        expr = x + 2.0
        with GraphSession() as session:
            face = scad.make_circle_rface((0.0, 0.0, 0.0), x)
            scad.extrude_rsolid(face, (0.0, 0.0, 1.0), expr)

        payload = json.loads(scad.export_model_json(session))
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
ss = doc.getObject('SimpleCADExpressions')
data = {}
for cell in ss.getNonEmptyCells():
    data[cell] = {
        'alias': ss.getAlias(cell),
        'contents': ss.getContents(cell),
        'value': ss.get(cell),
    }
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump(data, fh)
"""
        result = self._inspect_fcstd_json(json.dumps(payload), probe)
        self.assertEqual(result["A1"]["contents"].lstrip("'"), "var_hub_radius")
        self.assertEqual(result["B1"]["alias"], "var_hub_radius")
        self.assertEqual(result["B1"]["contents"], "6.5")
        self.assertTrue(result["C1"]["contents"].lstrip("'").startswith("var_"))
        self.assertEqual(result["D1"]["contents"].lstrip("'"), "Hub outer radius")
        expr_row = next(
            row
            for row, entry in result.items()
            if row.startswith("B") and entry["alias"].startswith("expr_")
        )
        self.assertIn("var_hub_radius", result[expr_row]["contents"])
        self.assertIn("const_", result[expr_row]["contents"])

    def test_translate_model_json_resolves_detail_feature_expressions(self):
        radius = scad.var("fillet_r", 0.25)
        with GraphSession() as session:
            box = scad.make_box_rsolid(4.0, 4.0, 4.0)
            scad.fillet_rsolid(box, [box.get_edges(i) for i in range(2)], radius)

        script = scad.translate_model_json_to_freecad_script(
            scad.export_model_json(session)
        )

        self.assertIn("Part::Fillet", script)
        self.assertIn("_resolve_param_value", script)

    def test_translate_model_json_resolves_pattern_expressions(self):
        graph = OperationGraph(graph_id="graph_pattern")
        seed = graph.add_node(
            op="make_line_redge",
            params={"start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]},
        )
        graph.add_node(
            op="make_translate_rshape",
            params={
                "vector": [2.0, 0.0, 0.0],
            },
            param_exprs={"vector": [{"expr_id": "var_spacing"}, None, None]},
            inputs=[seed],
        )
        payload = {
            "schema_version": "2.0",
            "canonical_contract": {"contract_version": "2.0"},
            "graph": graph.to_dict(),
            "leaf_ids": [leaf.node_id for leaf in graph.leaf_nodes()],
            "expression_graph": {
                "nodes": [
                    {
                        "expr_id": "var_spacing",
                        "kind": "var",
                        "name": "spacing",
                        "default": 2.0,
                    }
                ]
            },
            "frame_graph": {"nodes": []},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
        }

        script = scad.translate_model_json_to_freecad_script(json.dumps(payload))

        self.assertIn("_resolve_nested_param_value", script)
        self.assertIn("_resolve_param_value", script)

    def test_translate_model_json_resolves_helix_and_arc_expressions(self):
        pitch = scad.var("pitch", 1.0)
        radius = scad.var("radius", 2.0)
        angle = scad.var("angle", 1.57)
        with GraphSession() as session:
            scad.make_helix_rwire(pitch, 3.0, radius)
            scad.make_angle_arc_rwire((0.0, 0.0, 0.0), radius, 0.0, angle)

        script = scad.translate_model_json_to_freecad_script(
            scad.export_model_json(session)
        )

        self.assertIn("Part::Helix", script)
        self.assertIn("make_angle_arc_redge", script)
        self.assertIn("_apply_op_expression_bindings", script)
        self.assertIn("'Pitch'", script)
        self.assertIn("'Radius'", script)

    def test_translate_model_json_converts_trig_expressions_to_freecad_semantics(self):
        theta = scad.var("theta", 0.5)
        expr = scad.sin(theta) + scad.acos(theta)
        with GraphSession() as session:
            face = scad.make_circle_rface((0.0, 0.0, 0.0), 1.0)
            scad.extrude_rsolid(face, (0.0, 0.0, 1.0), expr)

        script = scad.translate_model_json_to_freecad_script(
            scad.export_model_json(session)
        )

        self.assertIn("sin((<<SimpleCADExpressions>>.", script)
        self.assertIn("* 180 / pi)", script)
        self.assertIn("=acos(<<SimpleCADExpressions>>.", script)
        self.assertIn("* pi / 180", script)

    def test_translate_model_json_preserves_helix_center_and_direction(self):
        with GraphSession() as session:
            scad.make_helix_rwire(
                1.0,
                3.0,
                2.0,
                center=(1.0, 2.0, 3.0),
                dir=(0.0, 1.0, 0.0),
            )

        script = scad.translate_model_json_to_freecad_script(
            scad.export_model_json(session)
        )

        self.assertIn("Part::Helix", script)
        self.assertIn("Placement = App.Placement", script)

    def test_translate_model_json_uses_freecad_revolve_signature(self):
        with GraphSession() as session:
            profile = scad.make_circle_rface((2.0, 0.0, 0.0), 0.5)
            scad.revolve_rsolid(
                profile,
                axis=(0.0, 1.0, 0.0),
                angle=180.0,
                origin=(1.0, 0.0, 0.0),
            )

        script = scad.translate_model_json_to_freecad_script(
            scad.export_model_json(session)
        )

        self.assertIn("Part::Revolution", script)
        self.assertIn(".Axis = _vec(", script)
        self.assertIn(".Angle = float(", script)
        self.assertIn("'Angle'", script)

    def test_translate_model_json_uses_single_graph_sweep_helper(self):
        with GraphSession() as session:
            profile = scad.make_circle_rface((0.0, 0.0, 0.0), 0.5)
            path = scad.make_helix_rwire(1.0, 3.0, 2.0)
            scad.sweep_rsolid(profile, path, is_frenet=True)

        payload_obj = self._expression_payload(scad.export_model_json(session))
        payload_obj["expression_graph"]["nodes"] = [
            {"expr_id": "var_frenet", "kind": "var", "name": "frenet", "default": 1.0}
        ]
        for node in payload_obj["graph"]["nodes"]:
            if node["op"] == "make_sweep_rsolid":
                node["param_exprs"] = {"is_frenet": {"expr_id": "var_frenet"}}
        script = scad.translate_model_json_to_freecad_script(json.dumps(payload_obj))

        self.assertIn("Part::Sweep", script)
        self.assertIn(".Spine = _spine_object", script)
        self.assertIn(".Frenet = bool(", script)
        self.assertIn("'Frenet'", script)

    def test_translate_model_json_materializes_ql_selected_face_profile_for_sweep(self):
        with GraphSession() as session:
            base = scad.make_circle_rface((0.0, 0.0, 0.0), 0.25)
            body = scad.extrude_rsolid(base, (0.0, 0.0, 1.0), 1.0)
            profile = (
                scad.ql.faces()
                .where(scad.ql.tag("face.extrusion.end"))
                .exactly(1)
                .resolve(body)[0]
            )
            path = scad.make_segment_rwire((0.0, 0.0, 1.0), (0.0, 0.0, 2.0))
            scad.sweep_rsolid(profile, path)

        payload = scad.export_model_json(session)
        payload_obj = json.loads(payload)
        select_node = next(
            node
            for node in payload_obj["graph"]["nodes"]
            if node["op"] == "make_select_rface"
        )
        sweep_node = next(
            node
            for node in payload_obj["graph"]["nodes"]
            if node["op"] == "make_sweep_rsolid"
        )
        script = scad.translate_model_json_to_freecad_script(payload)

        self.assertEqual(sweep_node["inputs"][0], select_node["node_id"])
        self.assertIn("GRAPH_SELECTIONS = {}", script)
        self.assertIn("GRAPH_SELECTIONS[node_id] = payload", script)
        self.assertIn("GRAPH_SPINE_OBJECTS = {}", script)
        self.assertIn("doc.addObject('Part::Feature', f'{str(op)}_{str(node_id)}')", script)
        self.assertIn("obj.Shape = selected_shape", script)
        self.assertIn(
            f"_register_geo_selection_node(node_id={json.dumps(select_node['node_id'])}, op=\"make_select_rface\"",
            script,
        )
        self.assertIn(
            f".Sections = [GRAPH_NODES[{json.dumps(select_node['node_id'])}]]",
            script,
        )
        self.assertIn(".Spine = _spine_object", script)

    def test_translate_model_json_ql_selected_face_profile_sweep_fcstd_valid(self):
        with GraphSession() as session:
            base = scad.make_circle_rface((0.0, 0.0, 0.0), 0.25)
            body = scad.extrude_rsolid(base, (0.0, 0.0, 1.0), 1.0)
            profile = (
                scad.ql.faces()
                .where(scad.ql.tag("face.extrusion.end"))
                .exactly(1)
                .resolve(body)[0]
            )
            path = scad.make_segment_rwire((0.0, 0.0, 1.0), (0.0, 0.0, 2.0))
            scad.sweep_rsolid(profile, path)

        payload = scad.export_model_json(session)
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
select_objs = [obj for obj in doc.Objects if getattr(obj, 'SimpleCADOp', '') == 'make_select_rface']
sweep_objs = [obj for obj in doc.Objects if getattr(obj, 'SimpleCADOp', '') == 'make_sweep_rsolid']
selected = select_objs[-1]
sweep = sweep_objs[-1]
sweep_shape = sweep.Shape
sweep_null = sweep_shape.isNull()
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'selected_count': len(select_objs),
        'sweep_count': len(sweep_objs),
        'selected_shape_type': selected.Shape.ShapeType,
        'selected_valid': selected.Shape.isValid(),
        'sweep_null': sweep_null,
        'sweep_valid': False if sweep_null else sweep_shape.isValid(),
        'sweep_solid_count': 0 if sweep_null else len(sweep_shape.Solids),
        'sweep_volume': 0.0 if sweep_null else float(sweep_shape.Volume),
    }, fh)
"""
        result = self._inspect_fcstd_json(payload, probe)

        self.assertEqual(result["selected_count"], 1)
        self.assertEqual(result["sweep_count"], 1)
        self.assertEqual(result["selected_shape_type"], "Face")
        self.assertTrue(result["selected_valid"])
        self.assertFalse(result["sweep_null"])
        self.assertTrue(result["sweep_valid"])
        self.assertEqual(result["sweep_solid_count"], 1)
        self.assertGreater(result["sweep_volume"], 0.0)

    def test_translate_model_json_uses_single_result_union_helper(self):
        graph = OperationGraph(graph_id="graph_union_single")
        a = graph.add_node(
            op="make_line_redge",
            node_id="edge_a",
            params={"start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]},
        )
        b = graph.add_node(
            op="make_line_redge",
            node_id="edge_b",
            params={"start": [0.0, 1.0, 0.0], "end": [1.0, 1.0, 0.0]},
        )
        graph.add_node(
            op="make_union_rsolid",
            node_id="union_out",
            params={"input_count": 2},
            inputs=[a, b],
        )
        payload = {
            "schema_version": "2.0",
            "canonical_contract": {"contract_version": "2.0"},
            "graph": graph.to_dict(),
            "leaf_ids": ["union_out"],
            "expression_graph": {"nodes": []},
            "frame_graph": {"nodes": []},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
        }

        script = scad.translate_model_json_to_freecad_script(json.dumps(payload))

        self.assertIn("Part::Fuse", script)

    def test_translate_model_json_uses_multifuse_for_multi_tool_cut(self):
        graph = OperationGraph(graph_id="graph_cut_multi")
        base = graph.add_node(
            op="make_line_redge",
            node_id="base_obj",
            params={"start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]},
        )
        tool_a = graph.add_node(
            op="make_line_redge",
            node_id="tool_a",
            params={"start": [0.0, 1.0, 0.0], "end": [1.0, 1.0, 0.0]},
        )
        tool_b = graph.add_node(
            op="make_line_redge",
            node_id="tool_b",
            params={"start": [0.0, 2.0, 0.0], "end": [1.0, 2.0, 0.0]},
        )
        tool_c = graph.add_node(
            op="make_line_redge",
            node_id="tool_c",
            params={"start": [0.0, 3.0, 0.0], "end": [1.0, 3.0, 0.0]},
        )
        graph.add_node(
            op="make_cut_rsolid",
            node_id="cut_out",
            params={"tool_count": 3},
            inputs=[base, tool_a, tool_b, tool_c],
        )
        payload = {
            "schema_version": "2.0",
            "canonical_contract": {"contract_version": "2.0"},
            "graph": graph.to_dict(),
            "leaf_ids": ["cut_out"],
            "expression_graph": {"nodes": []},
            "frame_graph": {"nodes": []},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
        }

        script = scad.translate_model_json_to_freecad_script(json.dumps(payload))

        self.assertIn("Part::MultiFuse", script)
        self.assertIn("cut_out_inputs[1:]", script)
        self.assertIn("cut_out.Tool = cut_out_tools", script)

    def test_translate_model_json_mixed_curve_sketch_closes_in_fcstd(self):
        with GraphSession() as session:
            edges = [
                scad.make_line_redge((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
                scad.make_three_point_arc_redge(
                    (1.0, 0.0, 0.0),
                    (1.5, 0.5, 0.0),
                    (1.0, 1.0, 0.0),
                ),
                scad.make_spline_redge(
                    control_points=[
                        (1.0, 1.0, 0.0),
                        (0.6, 1.25, 0.0),
                        (0.2, 1.15, 0.0),
                        (0.0, 1.0, 0.0),
                    ]
                ),
                scad.make_line_redge((0.0, 1.0, 0.0), (0.0, 0.0, 0.0)),
            ]
            wire = scad.make_wire_from_edges_rwire(edges)
            face = scad.make_face_from_wire_rface(wire)
            scad.extrude_rsolid(face, (0.0, 0.0, 1.0), 2.0)

        payload = scad.export_model_json(session)
        probe = """
import json
import FreeCAD as App
import Part

doc = App.openDocument(FCSTD_PATH)
target = max(
    (obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject'),
    key=lambda obj: len(list(getattr(obj, 'Geometry', []))),
)
shape = target.Shape
wire = shape.Wires[0]
face = Part.Face(wire)
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'shape_type': shape.ShapeType,
        'wire_count': len(shape.Wires),
        'edge_count': len(shape.Edges),
        'wire_closed': wire.isClosed(),
        'wire_valid': wire.isValid(),
        'face_valid': face.isValid(),
    }, fh)
"""
        result = self._inspect_fcstd_json(payload, probe)

        self.assertEqual(result["shape_type"], "Wire")
        self.assertEqual(result["wire_count"], 1)
        self.assertEqual(result["edge_count"], 4)
        self.assertTrue(result["wire_closed"])
        self.assertTrue(result["wire_valid"])
        self.assertTrue(result["face_valid"])

    def test_translate_model_json_multi_tool_cut_affects_fcstd_result(self):
        with GraphSession() as session:
            body = scad.make_cylinder_rsolid(10.0, 4.0)
            hole = scad.make_cylinder_rsolid(12.0, 0.75)
            hole = scad.translate_shape(hole, (2.0, 0.0, -1.0))
            hole_b = scad.rotate_shape(hole, 120.0, axis=(0.0, 0.0, 1.0))
            hole_c = scad.rotate_shape(hole, 240.0, axis=(0.0, 0.0, 1.0))
            scad.cut_rsolid(body, hole, hole_b, hole_c)

        payload = scad.export_model_json(session)
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
cut_objs = [obj for obj in doc.Objects if getattr(obj, 'SimpleCADOp', '') == 'make_cut_rsolid']
final_cut = cut_objs[-1]
shape = final_cut.Shape
tools = doc.getObject('make_cut_rsolid_node_' + final_cut.Name.split('_node_')[-1] + '_tools')
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'cut_count': len(cut_objs),
        'final_valid': shape.isValid(),
        'solid_count': len(shape.Solids),
        'volume': float(shape.Volume),
        'has_tools_fuse': tools is not None,
        'tool_shape_count': len(getattr(tools, 'Shapes', [])) if tools is not None else 0,
    }, fh)
"""
        result = self._inspect_fcstd_json(payload, probe)

        self.assertGreaterEqual(result["cut_count"], 1)
        self.assertTrue(result["final_valid"])
        self.assertEqual(result["solid_count"], 1)
        self.assertTrue(result["has_tools_fuse"])
        self.assertEqual(result["tool_shape_count"], 3)

    def test_translate_model_json_emits_native_loft_feature(self):
        with GraphSession() as session:
            base = scad.make_rectangle_rwire(2.0, 2.0, center=(0.0, 0.0, 0.0))
            top = scad.make_rectangle_rwire(1.0, 1.0, center=(0.0, 0.0, 3.0))
            scad.loft_rsolid([base, top], ruled=True)

        payload_obj = self._expression_payload(scad.export_model_json(session))
        payload_obj["expression_graph"]["nodes"] = [
            {"expr_id": "var_ruled", "kind": "var", "name": "ruled", "default": 1.0}
        ]
        for node in payload_obj["graph"]["nodes"]:
            if node["op"] == "make_loft_rsolid":
                node["param_exprs"] = {"ruled": {"expr_id": "var_ruled"}}
        script = scad.translate_model_json_to_freecad_script(json.dumps(payload_obj))

        self.assertIn("Part::Loft", script)
        self.assertIn(".Sections = [GRAPH_NODES", script)
        self.assertIn(".Ruled = bool(", script)
        self.assertIn("'Ruled'", script)

    def test_translate_model_json_binds_feature_properties_to_freecad_expressions(self):
        with GraphSession() as session:
            helix = scad.make_helix_rwire(1.0, 3.0, 2.0)
            face = scad.make_circle_rface((0.0, 0.0, 0.0), 1.0)
            scad.extrude_rsolid(face, (0.0, 0.0, 1.0), 2.0)
            rev_wire = scad.make_rectangle_rwire(1.0, 2.0, center=(2.0, 0.0, 0.0))
            rev_face = scad.make_face_from_wire_rface(rev_wire)
            scad.revolve_rsolid(rev_face, axis=(0.0, 0.0, 1.0), angle=180.0)
            scad.sweep_rsolid(face, helix, is_frenet=True)
            box = scad.make_box_rsolid(2.0, 2.0, 2.0)
            scad.shell_rsolid(box, [box.get_faces(0)], 0.25)

        payload = scad.export_model_json(session)
        payload_obj = self._expression_payload(payload)
        payload_obj["expression_graph"]["nodes"] = [
            {"expr_id": "var_pitch", "kind": "var", "name": "pitch", "default": 1.0},
            {"expr_id": "var_radius", "kind": "var", "name": "radius", "default": 2.0},
            {"expr_id": "var_angle", "kind": "var", "name": "angle", "default": 180.0},
            {"expr_id": "var_frenet", "kind": "var", "name": "frenet", "default": 1.0},
            {
                "expr_id": "var_thickness",
                "kind": "var",
                "name": "thickness",
                "default": 0.25,
            },
        ]
        graph_nodes = payload_obj["graph"]["nodes"]
        for node in graph_nodes:
            if node["op"] == "make_helix_redge":
                node["param_exprs"] = {
                    "pitch": {"expr_id": "var_pitch"},
                    "radius": {"expr_id": "var_radius"},
                }
            elif node["op"] == "make_extrude_rsolid":
                node["param_exprs"] = {"distance": {"expr_id": "var_radius"}}
            elif node["op"] == "make_revolve_rsolid":
                node["param_exprs"] = {"angle": {"expr_id": "var_angle"}}
            elif node["op"] == "make_sweep_rsolid":
                node["param_exprs"] = {"is_frenet": {"expr_id": "var_frenet"}}
            elif node["op"] == "make_shell_rsolid":
                node["param_exprs"] = {"thickness": {"expr_id": "var_thickness"}}
        expr_aliases = {
            node["name"]
            if node.get("kind") == "var"
            else node.get("op"): self._expr_alias(node["expr_id"])
            for node in payload_obj["expression_graph"]["nodes"]
            if isinstance(node, dict) and node.get("expr_id")
        }
        payload = json.dumps(payload_obj)
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
targets = {
    'Part::Extrusion': ['LengthFwd'],
    'Part::Revolution': ['Angle'],
    'Part::Helix': ['Pitch', 'Radius'],
    'Part::Sweep': ['Frenet'],
    'Part::Thickness': ['Value'],
}
result = {}
for obj in doc.Objects:
    props = targets.get(getattr(obj, 'TypeId', ''))
    if not props:
        continue
    result[obj.TypeId] = list(getattr(obj, 'ExpressionEngine', []))
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump(result, fh)
"""
        result = self._inspect_fcstd_json(payload, probe)

        self.assertIn(
            ["LengthFwd", f"<<SimpleCADExpressions>>.{expr_aliases['radius']}"],
            result["Part::Extrusion"],
        )
        self.assertIn(
            ["Angle", f"<<SimpleCADExpressions>>.{expr_aliases['angle']}"],
            result["Part::Revolution"],
        )
        self.assertIn(
            ["Pitch", f"<<SimpleCADExpressions>>.{expr_aliases['pitch']}"],
            result["Part::Helix"],
        )
        self.assertIn(
            ["Radius", f"<<SimpleCADExpressions>>.{expr_aliases['radius']}"],
            result["Part::Helix"],
        )
        self.assertIn(
            ["Frenet", f"<<SimpleCADExpressions>>.{expr_aliases['frenet']}"],
            result["Part::Sweep"],
        )
        self.assertIn(
            ["Value", f"<<SimpleCADExpressions>>.{expr_aliases['thickness']}"],
            result["Part::Thickness"],
        )

    def test_translate_model_json_binds_transform_and_detail_expressions(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(2.0, 2.0, 2.0)
            scad.translate_shape(box, (1.0, 2.0, 3.0))
            scad.rotate_shape(box, 30.0, axis=(0.0, 0.0, 1.0), origin=(1.0, 0.0, 0.0))
            scad.mirror_shape(
                box, plane_origin=(0.0, 0.0, 0.0), plane_normal=(0.0, 0.0, 1.0)
            )
            scad.fillet_rsolid(box, [box.get_edges(0)], 0.2)
            scad.chamfer_rsolid(box, [box.get_edges(0)], 0.3)

        payload_obj = self._expression_payload(scad.export_model_json(session))
        payload_obj["expression_graph"]["nodes"] = [
            {"expr_id": "var_tx", "kind": "var", "name": "tx", "default": 1.0},
            {"expr_id": "var_ty", "kind": "var", "name": "ty", "default": 2.0},
            {"expr_id": "var_tz", "kind": "var", "name": "tz", "default": 3.0},
            {"expr_id": "var_angle", "kind": "var", "name": "angle", "default": 30.0},
            {"expr_id": "var_ox", "kind": "var", "name": "ox", "default": 1.0},
            {"expr_id": "var_nz", "kind": "var", "name": "nz", "default": 1.0},
            {"expr_id": "var_fillet", "kind": "var", "name": "fillet", "default": 0.2},
            {
                "expr_id": "var_chamfer",
                "kind": "var",
                "name": "chamfer",
                "default": 0.3,
            },
        ]
        for node in payload_obj["graph"]["nodes"]:
            if node["op"] == "make_translate_rshape":
                node["param_exprs"] = {
                    "vector": [
                        {"expr_id": "var_tx"},
                        {"expr_id": "var_ty"},
                        {"expr_id": "var_tz"},
                    ]
                }
            elif node["op"] == "make_rotate_rshape":
                node["param_exprs"] = {
                    "origin": [{"expr_id": "var_ox"}, None, None],
                    "axis": [None, None, {"expr_id": "var_nz"}],
                    "angle": {"expr_id": "var_angle"},
                }
            elif node["op"] == "make_mirror_rshape":
                node["param_exprs"] = {
                    "plane_origin": [{"expr_id": "var_ox"}, None, None],
                    "plane_normal": [None, None, {"expr_id": "var_nz"}],
                }
            elif node["op"] == "make_fillet_rsolid":
                node["param_exprs"] = {"radius": {"expr_id": "var_fillet"}}
            elif node["op"] == "make_chamfer_rsolid":
                node["param_exprs"] = {"distance": {"expr_id": "var_chamfer"}}
        expr_aliases = {
            node["name"]: self._expr_alias(node["expr_id"])
            for node in payload_obj["expression_graph"]["nodes"]
        }
        payload = json.dumps(payload_obj)
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
result = {}
for obj in doc.Objects:
    if getattr(obj, 'TypeId', '') in {'App::Link', 'Part::Mirroring', 'Part::Fillet', 'Part::Chamfer'}:
        result.setdefault(obj.TypeId, []).append(list(getattr(obj, 'ExpressionEngine', [])))
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump(result, fh)
"""
        result = self._inspect_fcstd_json(payload, probe)

        link_engines = [item for group in result["App::Link"] for item in group]
        mirror_engines = [item for group in result["Part::Mirroring"] for item in group]
        fillet_engines = [item for group in result["Part::Fillet"] for item in group]
        chamfer_engines = [item for group in result["Part::Chamfer"] for item in group]

        self.assertIn(
            [".Placement.Base.x", f"<<SimpleCADExpressions>>.{expr_aliases['tx']}"],
            link_engines,
        )
        self.assertIn(
            [".Placement.Base.y", f"<<SimpleCADExpressions>>.{expr_aliases['ty']}"],
            link_engines,
        )
        self.assertIn(
            [".Placement.Base.z", f"<<SimpleCADExpressions>>.{expr_aliases['tz']}"],
            link_engines,
        )
        self.assertIn(
            [
                ".Placement.Rotation.Angle",
                f"<<SimpleCADExpressions>>.{expr_aliases['angle']}",
            ],
            link_engines,
        )
        self.assertIn(
            [".Base.x", f"<<SimpleCADExpressions>>.{expr_aliases['ox']}"],
            mirror_engines,
        )
        self.assertIn(
            [".Normal.z", f"<<SimpleCADExpressions>>.{expr_aliases['nz']}"],
            mirror_engines,
        )
        self.assertIn(
            ["Edges[0]", f"<<SimpleCADExpressions>>.{expr_aliases['fillet']}"],
            fillet_engines,
        )
        self.assertIn(
            ["Edges[0]", f"<<SimpleCADExpressions>>.{expr_aliases['chamfer']}"],
            chamfer_engines,
        )

    def test_translate_model_json_binds_sketch_primitive_expressions(self):
        graph = OperationGraph(graph_id="graph_sketch_exprs")
        line = graph.add_node(
            op="make_line_redge",
            node_id="line_expr",
            params={"start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]},
            param_exprs={
                "start": [{"expr_id": "var_lsx"}, {"expr_id": "var_lsy"}, None],
                "end": [{"expr_id": "var_lex"}, {"expr_id": "var_ley"}, None],
            },
        )
        circle = graph.add_node(
            op="make_circle_redge",
            node_id="circle_expr",
            params={"center": [2.0, 3.0, 0.0], "radius": 4.0},
            param_exprs={
                "center": [
                    {"expr_id": "var_cx"},
                    {"expr_id": "var_cy"},
                    {"expr_id": "var_cz"},
                ],
                "radius": {"expr_id": "var_cr"},
            },
        )
        wire_line = graph.add_node(
            op="make_wire_from_edges_rwire",
            node_id="wire_line",
            params={"edge_count": 1},
            inputs=[line],
        )
        face_circle = graph.add_node(
            op="make_face_from_wire_rface",
            node_id="face_circle",
            params={"edge_count": 1},
            inputs=[
                graph.add_node(
                    op="make_wire_from_edges_rwire",
                    node_id="wire_circle",
                    params={"edge_count": 1},
                    inputs=[circle],
                )
            ],
        )
        payload = {
            "schema_version": "2.0",
            "canonical_contract": {"contract_version": "2.0"},
            "graph": graph.to_dict(),
            "leaf_ids": [wire_line.node_id, face_circle.node_id],
            "expression_graph": {
                "nodes": [
                    {
                        "expr_id": "var_lsx",
                        "kind": "var",
                        "name": "lsx",
                        "default": 0.0,
                    },
                    {
                        "expr_id": "var_lsy",
                        "kind": "var",
                        "name": "lsy",
                        "default": 0.0,
                    },
                    {
                        "expr_id": "var_lex",
                        "kind": "var",
                        "name": "lex",
                        "default": 1.0,
                    },
                    {
                        "expr_id": "var_ley",
                        "kind": "var",
                        "name": "ley",
                        "default": 0.0,
                    },
                    {"expr_id": "var_cx", "kind": "var", "name": "cx", "default": 2.0},
                    {"expr_id": "var_cy", "kind": "var", "name": "cy", "default": 3.0},
                    {"expr_id": "var_cz", "kind": "var", "name": "cz", "default": 0.0},
                    {"expr_id": "var_cr", "kind": "var", "name": "cr", "default": 4.0},
                ]
            },
            "frame_graph": {"nodes": []},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
        }
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
result = {}
for obj in doc.Objects:
    if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject':
        result[obj.Name] = list(getattr(obj, 'ExpressionEngine', []))
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump(result, fh)
"""
        result = self._inspect_fcstd_json(json.dumps(payload), probe)
        all_entries = [entry for entries in result.values() for entry in entries]
        self.assertTrue(all_entries)
        self.assertIn(
            [".Placement.Base.x", "<<SimpleCADExpressions>>.var_lsx"],
            all_entries,
        )
        self.assertIn(
            [
                "Constraints[0]",
                "sqrt(pow(<<SimpleCADExpressions>>.var_lex - <<SimpleCADExpressions>>.var_lsx; 2) + pow(<<SimpleCADExpressions>>.var_ley - <<SimpleCADExpressions>>.var_lsy; 2) + pow(0 - 0; 2))",
            ],
            all_entries,
        )
        self.assertIn(
            [
                "Constraints[1]",
                "<<SimpleCADExpressions>>.var_lex - <<SimpleCADExpressions>>.var_lsx",
            ],
            all_entries,
        )
        self.assertIn(
            [
                "Constraints[2]",
                "<<SimpleCADExpressions>>.var_ley - <<SimpleCADExpressions>>.var_lsy",
            ],
            all_entries,
        )
        self.assertIn(
            [
                "Geometry[0].EndPoint.x",
                "sqrt(pow(<<SimpleCADExpressions>>.var_lex - <<SimpleCADExpressions>>.var_lsx; 2) + pow(<<SimpleCADExpressions>>.var_ley - <<SimpleCADExpressions>>.var_lsy; 2) + pow(0 - 0; 2))",
            ],
            all_entries,
        )
        self.assertIn(
            [".Placement.Base.x", "<<SimpleCADExpressions>>.var_cx"], all_entries
        )
        self.assertIn(
            ["Constraints[0]", "2 * <<SimpleCADExpressions>>.var_cr"], all_entries
        )

    def test_translate_model_json_binds_mixed_sketch_arc_radius_expressions(self):
        graph = OperationGraph(graph_id="graph_mixed_arc_expr")
        line = graph.add_node(
            op="make_line_redge",
            node_id="line_expr",
            params={"start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]},
        )
        arc = graph.add_node(
            op="make_angle_arc_redge",
            node_id="arc_expr",
            params={
                "center": [1.0, 1.0, 0.0],
                "radius": 1.0,
                "start_angle": -1.5707963267948966,
                "end_angle": 0.0,
            },
            param_exprs={"radius": {"expr_id": "var_r"}},
        )
        wire = graph.add_node(
            op="make_wire_from_edges_rwire",
            node_id="wire_expr",
            params={"edge_count": 2},
            inputs=[line, arc],
        )
        payload = {
            "schema_version": "2.0",
            "canonical_contract": {"contract_version": "2.0"},
            "graph": graph.to_dict(),
            "leaf_ids": [wire.node_id],
            "expression_graph": {
                "nodes": [
                    {"expr_id": "var_r", "kind": "var", "name": "r", "default": 1.0}
                ]
            },
            "frame_graph": {"nodes": []},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
        }
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
result = {}
for obj in doc.Objects:
    if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject':
        result[obj.Name] = list(getattr(obj, 'ExpressionEngine', []))
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump(result, fh)
"""
        result = self._inspect_fcstd_json(json.dumps(payload), probe)
        all_entries = [entry for entries in result.values() for entry in entries]
        self.assertIn(
            ["Geometry[1].Radius", "<<SimpleCADExpressions>>.var_r"], all_entries
        )

    def test_translate_model_json_binds_mixed_sketch_angle_arc_endpoint_expressions(
        self,
    ):
        graph = OperationGraph(graph_id="graph_mixed_angle_arc_expr")
        line = graph.add_node(
            op="make_line_redge",
            node_id="line_expr",
            params={"start": [0.0, 0.0, 0.0], "end": [2.0, 0.0, 0.0]},
        )
        arc = graph.add_node(
            op="make_angle_arc_redge",
            node_id="arc_expr",
            params={
                "center": [2.0, 2.0, 0.0],
                "radius": 2.0,
                "start_angle": -1.5707963267948966,
                "end_angle": 0.0,
                "normal": [0.0, 0.0, 1.0],
            },
            param_exprs={
                "center": [{"expr_id": "var_cx"}, {"expr_id": "var_cy"}, None],
                "radius": {"expr_id": "var_r"},
                "start_angle": {"expr_id": "var_a0"},
                "end_angle": {"expr_id": "var_a1"},
            },
        )
        wire = graph.add_node(
            op="make_wire_from_edges_rwire",
            node_id="wire_expr",
            params={"edge_count": 2},
            inputs=[line, arc],
        )
        payload = {
            "schema_version": "2.0",
            "canonical_contract": {"contract_version": "2.0"},
            "graph": graph.to_dict(),
            "leaf_ids": [wire.node_id],
            "expression_graph": {
                "nodes": [
                    {"expr_id": "var_cx", "kind": "var", "name": "cx", "default": 2.0},
                    {"expr_id": "var_cy", "kind": "var", "name": "cy", "default": 2.0},
                    {"expr_id": "var_r", "kind": "var", "name": "r", "default": 2.0},
                    {
                        "expr_id": "var_a0",
                        "kind": "var",
                        "name": "a0",
                        "default": -1.5707963267948966,
                    },
                    {"expr_id": "var_a1", "kind": "var", "name": "a1", "default": 0.0},
                ]
            },
            "frame_graph": {"nodes": []},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
        }
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
result = {}
for obj in doc.Objects:
    if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject':
        result[obj.Name] = list(getattr(obj, 'ExpressionEngine', []))
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump(result, fh)
"""
        result = self._inspect_fcstd_json(json.dumps(payload), probe)
        expr_map = {prop: expr for entries in result.values() for prop, expr in entries}
        self.assertIn("Geometry[1].Center.x", expr_map)
        self.assertIn("Geometry[1].Center.y", expr_map)
        self.assertIn("Geometry[1].Radius", expr_map)
        self.assertIn("Geometry[1].StartPoint.x", expr_map)
        self.assertIn("Geometry[1].StartPoint.y", expr_map)
        self.assertIn("Geometry[1].EndPoint.x", expr_map)
        self.assertIn("Geometry[1].EndPoint.y", expr_map)
        self.assertIn("<<SimpleCADExpressions>>.var_r", expr_map["Geometry[1].Radius"])
        radius_constraint = next(
            expr
            for prop, expr in expr_map.items()
            if prop.startswith("Constraints[")
            and expr == "<<SimpleCADExpressions>>.var_r"
        )
        angle_constraint = next(
            expr
            for prop, expr in expr_map.items()
            if prop.startswith("Constraints[")
            and "<<SimpleCADExpressions>>.var_a1" in expr
            and "<<SimpleCADExpressions>>.var_a0" in expr
        )
        self.assertEqual(radius_constraint, "<<SimpleCADExpressions>>.var_r")
        self.assertIn("<<SimpleCADExpressions>>.var_a1", angle_constraint)
        self.assertIn("<<SimpleCADExpressions>>.var_a0", angle_constraint)
        self.assertIn(
            "<<SimpleCADExpressions>>.var_a0", expr_map["Geometry[1].StartPoint.x"]
        )
        self.assertIn(
            "<<SimpleCADExpressions>>.var_a0", expr_map["Geometry[1].StartPoint.y"]
        )
        self.assertIn(
            "<<SimpleCADExpressions>>.var_a1", expr_map["Geometry[1].EndPoint.x"]
        )
        self.assertIn(
            "<<SimpleCADExpressions>>.var_a1", expr_map["Geometry[1].EndPoint.y"]
        )
        self.assertTrue(
            any(
                token in expr_map["Geometry[1].StartPoint.x"]
                for token in ("sin(", "cos(")
            )
        )
        self.assertTrue(
            any(
                token in expr_map["Geometry[1].StartPoint.y"]
                for token in ("sin(", "cos(")
            )
        )
        self.assertTrue(
            any(
                token in expr_map["Geometry[1].EndPoint.x"]
                for token in ("sin(", "cos(")
            )
        )
        self.assertTrue(
            any(
                token in expr_map["Geometry[1].EndPoint.y"]
                for token in ("sin(", "cos(")
            )
        )

    def test_translate_model_json_exports_single_angle_arc_sketch_with_endpoint_expressions(
        self,
    ):
        graph = OperationGraph(graph_id="graph_single_angle_arc_expr")
        arc = graph.add_node(
            op="make_angle_arc_redge",
            node_id="arc_expr",
            params={
                "center": [0.0, 0.0, 0.0],
                "radius": 2.0,
                "start_angle": 0.0,
                "end_angle": 1.5707963267948966,
                "normal": [0.0, 0.0, 1.0],
            },
            param_exprs={
                "center": [{"expr_id": "var_cx"}, {"expr_id": "var_cy"}, None],
                "radius": {"expr_id": "var_r"},
                "start_angle": {"expr_id": "var_a0"},
                "end_angle": {"expr_id": "var_a1"},
            },
        )
        wire = graph.add_node(
            op="make_wire_from_edges_rwire",
            node_id="wire_expr",
            params={"edge_count": 1},
            inputs=[arc],
        )
        payload = {
            "schema_version": "2.0",
            "canonical_contract": {"contract_version": "2.0"},
            "graph": graph.to_dict(),
            "leaf_ids": [wire.node_id],
            "expression_graph": {
                "nodes": [
                    {"expr_id": "var_cx", "kind": "var", "name": "cx", "default": 0.0},
                    {"expr_id": "var_cy", "kind": "var", "name": "cy", "default": 0.0},
                    {"expr_id": "var_r", "kind": "var", "name": "r", "default": 2.0},
                    {"expr_id": "var_a0", "kind": "var", "name": "a0", "default": 0.0},
                    {
                        "expr_id": "var_a1",
                        "kind": "var",
                        "name": "a1",
                        "default": 1.5707963267948966,
                    },
                ]
            },
            "frame_graph": {"nodes": []},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
        }
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
sketches = [obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject']
target = sketches[0]
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'sketch_count': len(sketches),
        'exprs': list(getattr(target, 'ExpressionEngine', [])),
        'geom_count': len(list(getattr(target, 'Geometry', []))),
        'shape_type': target.Shape.ShapeType,
        'edge_count': len(target.Shape.Edges),
    }, fh)
"""
        result = self._inspect_fcstd_json(json.dumps(payload), probe)
        self.assertEqual(result["sketch_count"], 1)
        self.assertEqual(result["geom_count"], 1)
        self.assertEqual(result["shape_type"], "Wire")
        self.assertEqual(result["edge_count"], 1)
        expr_map = {prop: expr for prop, expr in result["exprs"]}
        self.assertIn("Geometry[0].Center.x", expr_map)
        self.assertIn("Geometry[0].Center.y", expr_map)
        self.assertIn("Geometry[0].Radius", expr_map)
        self.assertIn("Geometry[0].StartPoint.x", expr_map)
        self.assertIn("Geometry[0].StartPoint.y", expr_map)
        self.assertIn("Geometry[0].EndPoint.x", expr_map)
        self.assertIn("Geometry[0].EndPoint.y", expr_map)
        self.assertEqual(
            expr_map["Geometry[0].Radius"], "<<SimpleCADExpressions>>.var_r"
        )
        self.assertIn(
            "<<SimpleCADExpressions>>.var_a0", expr_map["Geometry[0].StartPoint.x"]
        )
        self.assertIn(
            "<<SimpleCADExpressions>>.var_a0", expr_map["Geometry[0].StartPoint.y"]
        )
        self.assertIn(
            "<<SimpleCADExpressions>>.var_a1", expr_map["Geometry[0].EndPoint.x"]
        )
        self.assertIn(
            "<<SimpleCADExpressions>>.var_a1", expr_map["Geometry[0].EndPoint.y"]
        )

    def test_translate_model_json_marks_spline_expression_mapping_as_unsupported(
        self,
    ):
        graph = OperationGraph(graph_id="graph_spline_expr_limit")
        spline = graph.add_node(
            op="make_spline_redge",
            node_id="spline_expr",
            params={
                "control_points": [
                    [0.0, 0.0, 0.0],
                    [0.6, 1.0, 0.0],
                    [1.4, 1.0, 0.0],
                    [2.0, 0.0, 0.0],
                ],
                "degree": 3,
                "knots": [0.0, 1.0],
                "multiplicities": [4, 4],
                "weights": None,
                "periodic": False,
            },
            param_exprs={
                "control_points": [
                    [None, None, None],
                    [None, {"expr_id": "var_sy"}, None],
                    [None, {"expr_id": "var_sy"}, None],
                    [None, None, None],
                ]
            },
        )
        wire = graph.add_node(
            op="make_wire_from_edges_rwire",
            node_id="wire_expr",
            params={"edge_count": 1},
            inputs=[spline],
        )
        payload = {
            "schema_version": "2.0",
            "canonical_contract": {"contract_version": "2.0"},
            "graph": graph.to_dict(),
            "leaf_ids": [wire.node_id],
            "expression_graph": {
                "nodes": [
                    {"expr_id": "var_sy", "kind": "var", "name": "sy", "default": 1.0}
                ]
            },
            "frame_graph": {"nodes": []},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
        }
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
sketch = next(obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject')
note = doc.getObject('simplecad_expression_limitations')
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'exprs': list(getattr(sketch, 'ExpressionEngine', [])),
        'expr_support': getattr(sketch, 'SimpleCADExprSupport', ''),
        'expr_limitation': getattr(sketch, 'SimpleCADExprLimitation', ''),
        'note_payload': getattr(note, 'Payload', '') if note is not None else '',
        'geom_count': len(list(getattr(sketch, 'Geometry', []))),
        'edge_count': len(sketch.Shape.Edges),
    }, fh)
"""
        result = self._inspect_fcstd_json(json.dumps(payload), probe)
        self.assertEqual(result["geom_count"], 1)
        self.assertEqual(result["edge_count"], 1)
        self.assertEqual(result["exprs"], [])
        self.assertEqual(result["expr_support"], "limited")
        self.assertIn(
            "make_spline_redge",
            result["expr_limitation"],
        )
        self.assertIn(
            "no stable equivalent native FreeCAD Sketcher BSpline parameter host",
            result["expr_limitation"],
        )
        payload_obj = json.loads(result["note_payload"])
        self.assertIn("spline_expr", payload_obj)
        self.assertEqual(payload_obj["spline_expr"]["op"], "make_spline_redge")
        self.assertIn(
            "no stable equivalent native FreeCAD Sketcher BSpline parameter host",
            payload_obj["spline_expr"]["reason"],
        )

    def test_single_gear_model_has_single_leaf_after_parametric_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "examples/06_parametric_gear_model.py",
                    "--output-dir",
                    str(output_dir),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            payload = json.loads(
                (output_dir / "parametric_gear.model.json").read_text(
                    encoding="utf-8"
                )
            )
        self.assertEqual(len(payload["leaf_ids"]), 1)
        var_names = [
            node.get("name")
            for node in payload["expression_graph"]["nodes"]
            if node.get("kind") == "var"
        ]
        self.assertNotIn("pitch_radius", var_names)

    def test_naca0016_blade_example_translates_bspline_sections_to_fcstd(self):
        freecad_cmd = self._discover_freecadcmd()
        if not freecad_cmd:
            self.skipTest("freecadcmd not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "examples/09_naca0016_blade_freecad.py",
                    "--output-dir",
                    str(output_dir),
                    "--freecad-cmd",
                    freecad_cmd,
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            model_path = output_dir / "naca0016_blade.model.json"
            fcstd_path = output_dir / "naca0016_blade.fcstd"
            probe_path = output_dir / "probe_blade.py"
            out_path = output_dir / "probe_blade.json"
            payload = json.loads(model_path.read_text(encoding="utf-8"))
            probe_path.write_text(
                f"FCSTD_PATH = {json.dumps(str(fcstd_path))}\n"
                f"OUT_PATH = {json.dumps(str(out_path))}\n"
                """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
sketches = [obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject']
bspline_counts = []
placements = []
for sketch in sketches:
    bspline_counts.append(sum(1 for geom in getattr(sketch, 'Geometry', []) if type(geom).__name__ == 'BSplineCurve'))
    placements.append({
        'z': float(sketch.Placement.Base.z),
        'angle': float(sketch.Placement.Rotation.Angle),
        'axis': [float(sketch.Placement.Rotation.Axis.x), float(sketch.Placement.Rotation.Axis.y), float(sketch.Placement.Rotation.Axis.z)],
    })
lofts = [obj for obj in doc.Objects if getattr(obj, 'SimpleCADOp', '') == 'make_loft_rsolid']
links = [obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'App::Link']
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'sketch_count': len(sketches),
        'bspline_counts': bspline_counts,
        'total_bspline_geometry': sum(bspline_counts),
        'placements': placements,
        'link_count': len(links),
        'loft_count': len(lofts),
        'loft_solid_count': 0 if not lofts else len(lofts[-1].Shape.Solids),
        'loft_volume': 0.0 if not lofts else float(lofts[-1].Shape.Volume),
    }, fh)
""",
                encoding="utf-8",
            )
            subprocess.run(
                [freecad_cmd, str(probe_path)],
                check=True,
                text=True,
                capture_output=True,
            )
            result = json.loads(out_path.read_text(encoding="utf-8"))

        bspline_nodes = [
            node for node in payload["graph"]["nodes"] if node.get("op") == "make_spline_redge"
        ]
        self.assertEqual(len(bspline_nodes), 6)
        self.assertEqual(result["sketch_count"], 6)
        self.assertEqual(result["total_bspline_geometry"], 6)
        self.assertTrue(all(count == 1 for count in result["bspline_counts"]))
        self.assertEqual(result["link_count"], 0)
        self.assertEqual(
            [round(item["z"], 3) for item in result["placements"]],
            [0.0, 0.8, 1.6, 2.4, 3.2, 4.0],
        )
        self.assertEqual(
            [round(item["angle"], 6) for item in result["placements"]],
            [0.0, 0.125664, 0.251327, 0.376991, 0.502655, 0.628319],
        )
        self.assertEqual(result["loft_count"], 1)
        self.assertEqual(result["loft_solid_count"], 1)
        self.assertGreater(result["loft_volume"], 0.0)

    def test_translate_model_json_adds_coincident_constraints_for_polyline_wire(self):
        graph = OperationGraph(graph_id="graph_polyline_constraints")
        e1 = graph.add_node(
            op="make_line_redge",
            node_id="e1",
            params={"start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]},
        )
        e2 = graph.add_node(
            op="make_line_redge",
            node_id="e2",
            params={"start": [1.0, 0.0, 0.0], "end": [1.0, 1.0, 0.0]},
        )
        e3 = graph.add_node(
            op="make_line_redge",
            node_id="e3",
            params={"start": [1.0, 1.0, 0.0], "end": [0.0, 0.0, 0.0]},
        )
        wire = graph.add_node(
            op="make_wire_from_edges_rwire",
            node_id="wire",
            params={"edge_count": 3},
            inputs=[e1, e2, e3],
        )
        payload = {
            "schema_version": "2.0",
            "canonical_contract": {"contract_version": "2.0"},
            "graph": graph.to_dict(),
            "leaf_ids": [wire.node_id],
            "expression_graph": {"nodes": []},
            "frame_graph": {"nodes": []},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
        }
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
sketch = next(obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject')
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'constraints': [str(c) for c in sketch.Constraints],
        'constraint_count': len(sketch.Constraints),
    }, fh)
"""
        result = self._inspect_fcstd_json(json.dumps(payload), probe)
        self.assertGreaterEqual(result["constraint_count"], 3)
        self.assertGreaterEqual(
            sum(1 for item in result["constraints"] if "Coincident" in item), 3
        )

    def _functional_rectangle_sketch_model_json(self) -> str:
        width = scad.var("fcstd_sketch_width", 2.0)
        height = scad.var("fcstd_sketch_height", 1.0)
        thickness = scad.var("fcstd_sketch_thickness", 0.5)
        with GraphSession() as session:
            sketch = scad.make_sketch_rsketch("fcstd_rect")
            sketch = scad.add_point_rsketch(sketch, "p0", 0.0, 0.0)
            sketch = scad.add_point_rsketch(sketch, "p1", width, 0.0)
            sketch = scad.add_point_rsketch(sketch, "p2", width, height)
            sketch = scad.add_point_rsketch(sketch, "p3", 0.0, height)
            sketch = scad.add_line_rsketch(sketch, "bottom", "p0", "p1")
            sketch = scad.add_line_rsketch(sketch, "right", "p1", "p2")
            sketch = scad.add_line_rsketch(sketch, "top", "p2", "p3")
            sketch = scad.add_line_rsketch(sketch, "left", "p3", "p0")
            sketch = scad.constrain_fix_rsketch(sketch, "p0")
            sketch = scad.constrain_horizontal_rsketch(sketch, "bottom")
            sketch = scad.constrain_vertical_rsketch(sketch, "right")
            sketch = scad.constrain_parallel_rsketch(sketch, "bottom", "top")
            sketch = scad.constrain_parallel_rsketch(sketch, "left", "right")
            sketch = scad.constrain_perpendicular_rsketch(sketch, "bottom", "right")
            sketch = scad.constrain_distance_rsketch(sketch, "p0", "p1", width)
            sketch = scad.constrain_distance_rsketch(sketch, "p0", "p3", height)
            face = scad.make_face_from_sketch_rface(
                sketch,
                require_fully_constrained=True,
            )
            scad.extrude_rsolid(face, (0.0, 0.0, 1.0), thickness)
        return scad.export_model_json(session)

    def test_translate_model_json_supports_functional_sketch_promotion_script(self):
        payload = self._functional_rectangle_sketch_model_json()

        script = scad.translate_model_json_to_freecad_script(payload)

        self.assertIn("_make_sketch_promotion_object", script)
        self.assertIn("make_face_from_sketch_rface", script)
        self.assertIn("make_add_point_rsketch", script)
        self.assertIn("make_constrain_distance_rsketch", script)
        self.assertIn("SimpleCADSketchSolve", script)
        self.assertIn("SimpleCADSketchConstraints", script)
        self.assertIn("Part::Extrusion", script)
        self.assertNotIn("make_solve_sketch_rsketchresult", script)

    def test_translate_model_json_functional_sketch_promotion_fcstd_valid(self):
        payload = self._functional_rectangle_sketch_model_json()
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
op_objects = [obj for obj in doc.Objects if getattr(obj, 'SimpleCADOp', '') == 'make_face_from_sketch_rface']
sketches = [obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject' and getattr(obj, 'SimpleCADOp', '') == 'make_face_from_sketch_rface']
bridge_features = [obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'Part::Feature' and getattr(obj, 'SimpleCADOp', '') == 'make_face_from_sketch_rface']
extrusions = [obj for obj in doc.Objects if getattr(obj, 'SimpleCADOp', '') == 'make_extrude_rsolid']
sketch = sketches[-1]
extrusion = extrusions[-1]
solve = json.loads(sketch.SimpleCADSketchSolve)
constraint_status = json.loads(sketch.SimpleCADSketchConstraints)
exprs = list(getattr(sketch, 'ExpressionEngine', []))
shape = extrusion.Shape
base = extrusion.Base
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'op_object_count': len(op_objects),
        'sketch_count': len(sketches),
        'bridge_feature_count': len(bridge_features),
        'extrusion_count': len(extrusions),
        'extrusion_base_name': getattr(base, 'Name', ''),
        'extrusion_base_type': getattr(base, 'TypeId', ''),
        'sketch_name': sketch.Name,
        'geom_count': len(list(sketch.Geometry)),
        'constraint_count': len(sketch.Constraints),
        'mapped_count': len(constraint_status.get('mapped', [])),
        'skipped_count': len(constraint_status.get('skipped', [])),
        'solve_status': solve.get('status'),
        'solve_dof': int(solve.get('dof', -1)),
        'exprs': exprs,
        'solid_count': 0 if shape.isNull() else len(shape.Solids),
        'volume': 0.0 if shape.isNull() else float(shape.Volume),
    }, fh)
"""
        result = self._inspect_fcstd_json(payload, probe)

        self.assertEqual(result["op_object_count"], 1)
        self.assertEqual(result["sketch_count"], 1)
        self.assertEqual(result["bridge_feature_count"], 0)
        self.assertEqual(result["extrusion_count"], 1)
        self.assertEqual(result["extrusion_base_name"], result["sketch_name"])
        self.assertEqual(result["extrusion_base_type"], "Sketcher::SketchObject")
        self.assertEqual(result["geom_count"], 4)
        self.assertGreaterEqual(result["constraint_count"], 10)
        self.assertEqual(result["mapped_count"], result["constraint_count"])
        self.assertGreaterEqual(result["mapped_count"] + result["skipped_count"], 13)
        self.assertEqual(result["solve_status"], "solved")
        self.assertEqual(result["solve_dof"], 0)
        self.assertEqual(result["solid_count"], 1)
        self.assertAlmostEqual(result["volume"], 1.0, places=6)
        expr_map = {prop: expr for prop, expr in result["exprs"]}
        self.assertTrue(
            any(
                prop.startswith("Constraints[")
                and "var_fcstd_sketch_width" in expr
                for prop, expr in expr_map.items()
            )
        )
        self.assertTrue(
            any(
                prop.startswith("Constraints[")
                and "var_fcstd_sketch_height" in expr
                for prop, expr in expr_map.items()
            )
        )

    def test_translate_model_json_functional_circle_sketch_promotion_fcstd_valid(self):
        radius = scad.var("fcstd_circle_radius", 1.5)
        thickness = scad.var("fcstd_circle_thickness", 0.5)
        with GraphSession() as session:
            sketch = scad.make_sketch_rsketch("fcstd_circle")
            sketch = scad.add_point_rsketch(sketch, "center", 0.0, 0.0)
            sketch = scad.add_circle_rsketch(sketch, "outer", "center", radius)
            sketch = scad.constrain_fix_rsketch(sketch, "center")
            sketch = scad.constrain_radius_rsketch(sketch, "outer", radius)
            face = scad.make_face_from_sketch_rface(
                sketch,
                require_fully_constrained=True,
            )
            scad.extrude_rsolid(face, (0.0, 0.0, 1.0), thickness)
        payload = scad.export_model_json(session)
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
sketch = next(obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject' and getattr(obj, 'SimpleCADOp', '') == 'make_face_from_sketch_rface')
extrusion = next(obj for obj in doc.Objects if getattr(obj, 'SimpleCADOp', '') == 'make_extrude_rsolid')
constraint_status = json.loads(sketch.SimpleCADSketchConstraints)
solve = json.loads(sketch.SimpleCADSketchSolve)
exprs = list(getattr(sketch, 'ExpressionEngine', []))
shape = extrusion.Shape
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'geom_count': len(list(sketch.Geometry)),
        'constraint_count': len(sketch.Constraints),
        'mapped_count': len(constraint_status.get('mapped', [])),
        'skipped_count': len(constraint_status.get('skipped', [])),
        'solve_status': solve.get('status'),
        'solve_dof': int(solve.get('dof', -1)),
        'exprs': exprs,
        'solid_count': 0 if shape.isNull() else len(shape.Solids),
        'volume': 0.0 if shape.isNull() else float(shape.Volume),
    }, fh)
"""
        result = self._inspect_fcstd_json(payload, probe)

        self.assertEqual(result["geom_count"], 1)
        self.assertGreaterEqual(result["constraint_count"], 3)
        self.assertEqual(result["mapped_count"], result["constraint_count"])
        self.assertEqual(result["skipped_count"], 0)
        self.assertEqual(result["solve_status"], "solved")
        self.assertEqual(result["solve_dof"], 0)
        self.assertEqual(result["solid_count"], 1)
        self.assertAlmostEqual(result["volume"], 3.141592653589793 * 1.5 * 1.5 * 0.5, places=5)
        expr_map = {prop: expr for prop, expr in result["exprs"]}
        self.assertTrue(
            any(
                prop.startswith("Constraints[")
                and "var_fcstd_circle_radius" in expr
                for prop, expr in expr_map.items()
            )
        )

    def test_translate_model_json_complex_guided_sketch_constraints_fcstd_valid(self):
        with GraphSession() as session:
            sketch = scad.make_sketch_rsketch("fcstd_guided_diamond")
            sketch = scad.add_point_rsketch(sketch, "center", 10.0, 8.0)
            sketch = scad.add_point_rsketch(sketch, "left", 3.0, 8.0)
            sketch = scad.add_point_rsketch(sketch, "top", 10.0, 12.0)
            sketch = scad.add_point_rsketch(sketch, "right", 17.0, 8.0)
            sketch = scad.add_point_rsketch(sketch, "bottom", 10.0, 4.0)
            sketch = scad.add_point_rsketch(sketch, "guide_upper_start", 3.0, 13.0)
            sketch = scad.add_point_rsketch(sketch, "guide_upper_end", 10.0, 17.0)
            sketch = scad.add_point_rsketch(sketch, "guide_lower_start", 17.0, 3.0)
            sketch = scad.add_point_rsketch(sketch, "guide_lower_end", 10.0, -1.0)
            sketch = scad.add_line_rsketch(sketch, "bottom_left", "left", "bottom")
            sketch = scad.add_line_rsketch(sketch, "right_bottom", "bottom", "right")
            sketch = scad.add_line_rsketch(sketch, "top_right", "right", "top")
            sketch = scad.add_line_rsketch(sketch, "left_top", "top", "left")
            sketch = scad.add_line_rsketch(sketch, "guide_upper", "guide_upper_start", "guide_upper_end", construction=True)
            sketch = scad.add_line_rsketch(sketch, "guide_lower", "guide_lower_start", "guide_lower_end", construction=True)
            sketch = scad.constrain_fix_rsketch(sketch, "center")
            sketch = scad.constrain_distance_x_rsketch(sketch, "left", "center", 7.0)
            sketch = scad.constrain_distance_y_rsketch(sketch, "left", "center", 0.0)
            sketch = scad.constrain_distance_x_rsketch(sketch, "center", "right", 7.0)
            sketch = scad.constrain_distance_y_rsketch(sketch, "center", "right", 0.0)
            sketch = scad.constrain_distance_x_rsketch(sketch, "center", "top", 0.0)
            sketch = scad.constrain_distance_y_rsketch(sketch, "center", "top", 4.0)
            sketch = scad.constrain_distance_x_rsketch(sketch, "bottom", "center", 0.0)
            sketch = scad.constrain_distance_y_rsketch(sketch, "bottom", "center", 4.0)
            sketch = scad.constrain_parallel_rsketch(sketch, "bottom_left", "top_right")
            sketch = scad.constrain_parallel_rsketch(sketch, "right_bottom", "left_top")
            sketch = scad.constrain_equal_length_rsketch(sketch, "bottom_left", "right_bottom")
            sketch = scad.constrain_equal_length_rsketch(sketch, "right_bottom", "top_right")
            sketch = scad.constrain_equal_length_rsketch(sketch, "top_right", "left_top")
            sketch = scad.constrain_distance_x_rsketch(sketch, "left", "guide_upper_start", 0.0)
            sketch = scad.constrain_distance_y_rsketch(sketch, "left", "guide_upper_start", 5.0)
            sketch = scad.constrain_distance_x_rsketch(sketch, "top", "guide_upper_end", 0.0)
            sketch = scad.constrain_distance_y_rsketch(sketch, "top", "guide_upper_end", 5.0)
            sketch = scad.constrain_distance_x_rsketch(sketch, "guide_lower_start", "right", 0.0)
            sketch = scad.constrain_distance_y_rsketch(sketch, "guide_lower_start", "right", 5.0)
            sketch = scad.constrain_distance_x_rsketch(sketch, "guide_lower_end", "bottom", 0.0)
            sketch = scad.constrain_distance_y_rsketch(sketch, "guide_lower_end", "bottom", 5.0)
            sketch = scad.constrain_parallel_rsketch(sketch, "guide_upper", "guide_lower")
            sketch = scad.constrain_parallel_rsketch(sketch, "guide_upper", "right_bottom")
            sketch = scad.constrain_parallel_rsketch(sketch, "guide_lower", "left_top")
            sketch = scad.constrain_equal_length_rsketch(sketch, "guide_upper", "right_bottom")
            sketch = scad.constrain_equal_length_rsketch(sketch, "guide_lower", "left_top")
            face = scad.make_face_from_sketch_rface(
                sketch,
                require_fully_constrained=True,
            )
            scad.extrude_rsolid(face, (0.0, 0.0, 1.0), 1.0)
        payload = scad.export_model_json(session)
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
sketch = next(obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject' and getattr(obj, 'SimpleCADOp', '') == 'make_face_from_sketch_rface')
extrusion = next(obj for obj in doc.Objects if getattr(obj, 'SimpleCADOp', '') == 'make_extrude_rsolid')
constraint_status = json.loads(sketch.SimpleCADSketchConstraints)
solve = json.loads(sketch.SimpleCADSketchSolve)
promotion = json.loads(sketch.SimpleCADSketchPromotion)
shape = extrusion.Shape
construction_count = 0
for idx, _geo in enumerate(sketch.Geometry):
    try:
        construction_count += 1 if sketch.getConstruction(idx) else 0
    except Exception:
        pass
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'geom_count': len(list(sketch.Geometry)),
        'construction_count': construction_count,
        'constraint_count': len(sketch.Constraints),
        'mapped_count': len(constraint_status.get('mapped', [])),
        'skipped_count': len(constraint_status.get('skipped', [])),
        'solve_status': solve.get('status'),
        'solve_dof': int(solve.get('dof', -1)),
        'promotion_edges': [edge.get('entity_id') for edge in promotion.get('edges', [])],
        'solid_count': 0 if shape.isNull() else len(shape.Solids),
        'volume': 0.0 if shape.isNull() else float(shape.Volume),
    }, fh)
"""
        result = self._inspect_fcstd_json(payload, probe)

        self.assertEqual(result["geom_count"], 6)
        self.assertEqual(result["construction_count"], 2)
        self.assertGreaterEqual(result["constraint_count"], 12)
        self.assertGreaterEqual(result["mapped_count"], 12)
        self.assertGreaterEqual(result["mapped_count"] + result["skipped_count"], 31)
        self.assertEqual(result["solve_status"], "solved")
        self.assertEqual(result["solve_dof"], 0)
        self.assertEqual(
            result["promotion_edges"],
            ["bottom_left", "right_bottom", "top_right", "left_top"],
        )
        self.assertEqual(result["solid_count"], 1)
        self.assertAlmostEqual(result["volume"], 56.0, places=5)

    def test_translate_model_json_curve_guided_sketch_constraints_fcstd_valid(self):
        with GraphSession() as session:
            sketch = scad.make_sketch_rsketch("fcstd_curve_guided")
            sketch = scad.add_point_rsketch(sketch, "center", 32.0, 42.0)
            sketch = scad.add_point_rsketch(sketch, "rim", 36.0, 42.0)
            sketch = scad.add_point_rsketch(sketch, "clearance_center", 32.0, 42.0)
            sketch = scad.add_point_rsketch(sketch, "upper_left", 23.0, 46.0)
            sketch = scad.add_point_rsketch(sketch, "upper_right", 41.0, 46.0)
            sketch = scad.add_point_rsketch(sketch, "lower_left", 23.0, 38.0)
            sketch = scad.add_point_rsketch(sketch, "lower_right", 41.0, 38.0)
            sketch = scad.add_circle_rsketch(sketch, "relief", "center", 4.0)
            sketch = scad.add_circle_rsketch(sketch, "clearance", "clearance_center", 4.0, construction=True)
            sketch = scad.add_line_rsketch(sketch, "radius_probe", "center", "rim", construction=True)
            sketch = scad.add_line_rsketch(sketch, "upper_rail", "upper_left", "upper_right", construction=True)
            sketch = scad.add_line_rsketch(sketch, "lower_rail", "lower_left", "lower_right", construction=True)
            sketch = scad.constrain_fix_rsketch(sketch, "center")
            sketch = scad.constrain_radius_rsketch(sketch, "relief", 4.0)
            sketch = scad.constrain_point_on_rsketch(sketch, "rim", "relief")
            sketch = scad.constrain_horizontal_rsketch(sketch, "radius_probe")
            sketch = scad.constrain_length_rsketch(sketch, "radius_probe", 4.0)
            sketch = scad.constrain_concentric_rsketch(sketch, "relief", "clearance")
            sketch = scad.constrain_equal_radius_rsketch(sketch, "relief", "clearance")
            sketch = scad.constrain_horizontal_rsketch(sketch, "upper_rail")
            sketch = scad.constrain_horizontal_rsketch(sketch, "lower_rail")
            sketch = scad.constrain_tangent_rsketch(sketch, "upper_rail", "relief")
            sketch = scad.constrain_tangent_rsketch(sketch, "lower_rail", "relief")
            sketch = scad.constrain_distance_x_rsketch(sketch, "center", "upper_left", -9.0)
            sketch = scad.constrain_distance_x_rsketch(sketch, "center", "upper_right", 9.0)
            sketch = scad.constrain_distance_x_rsketch(sketch, "center", "lower_left", -9.0)
            sketch = scad.constrain_distance_x_rsketch(sketch, "center", "lower_right", 9.0)
            face = scad.make_face_from_sketch_rface(
                sketch,
                require_fully_constrained=True,
            )
            scad.extrude_rsolid(face, (0.0, 0.0, 1.0), 1.0)
        payload = scad.export_model_json(session)
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
sketch = next(obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject' and getattr(obj, 'SimpleCADOp', '') == 'make_face_from_sketch_rface')
extrusion = next(obj for obj in doc.Objects if getattr(obj, 'SimpleCADOp', '') == 'make_extrude_rsolid')
constraint_status = json.loads(sketch.SimpleCADSketchConstraints)
solve = json.loads(sketch.SimpleCADSketchSolve)
promotion = json.loads(sketch.SimpleCADSketchPromotion)
shape = extrusion.Shape
geometry_type_names = [geo.__class__.__name__ for geo in sketch.Geometry]
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'geom_count': len(list(sketch.Geometry)),
        'circle_count': sum(1 for item in geometry_type_names if item == 'Circle'),
        'line_count': sum(1 for item in geometry_type_names if item == 'LineSegment'),
        'constraint_count': len(sketch.Constraints),
        'mapped_kinds': [item.get('kind') for item in constraint_status.get('mapped', [])],
        'skipped_count': len(constraint_status.get('skipped', [])),
        'solve_status': solve.get('status'),
        'solve_dof': int(solve.get('dof', -1)),
        'promotion_edges': [edge.get('entity_id') for edge in promotion.get('edges', [])],
        'solid_count': 0 if shape.isNull() else len(shape.Solids),
        'volume': 0.0 if shape.isNull() else float(shape.Volume),
    }, fh)
"""
        result = self._inspect_fcstd_json(payload, probe)

        self.assertEqual(result["geom_count"], 5)
        self.assertEqual(result["circle_count"], 2)
        self.assertEqual(result["line_count"], 3)
        self.assertGreaterEqual(result["constraint_count"], 15)
        self.assertGreaterEqual(result["mapped_kinds"].count("tangent"), 2)
        self.assertIn("point_on", result["mapped_kinds"])
        self.assertIn("equal_radius", result["mapped_kinds"])
        self.assertIn("concentric", result["mapped_kinds"])
        self.assertLessEqual(result["skipped_count"], 1)
        self.assertEqual(result["solve_status"], "solved")
        self.assertEqual(result["solve_dof"], 0)
        self.assertEqual(result["promotion_edges"], ["relief"])
        self.assertEqual(result["solid_count"], 1)
        self.assertAlmostEqual(result["volume"], 16.0 * 3.141592653589793, places=5)

    def test_translate_model_json_records_unsupported_functional_sketch_constraints(self):
        with GraphSession() as session:
            sketch = scad.make_sketch_rsketch("fcstd_midpoint_record")
            sketch = scad.add_point_rsketch(sketch, "p0", 0.0, 0.0)
            sketch = scad.add_point_rsketch(sketch, "p1", 2.0, 0.0)
            sketch = scad.add_point_rsketch(sketch, "p2", 2.0, 1.0)
            sketch = scad.add_point_rsketch(sketch, "p3", 0.0, 1.0)
            sketch = scad.add_point_rsketch(sketch, "mid", 1.0, 0.0)
            sketch = scad.add_line_rsketch(sketch, "bottom", "p0", "p1")
            sketch = scad.add_line_rsketch(sketch, "right", "p1", "p2")
            sketch = scad.add_line_rsketch(sketch, "top", "p2", "p3")
            sketch = scad.add_line_rsketch(sketch, "left", "p3", "p0")
            sketch = scad.constrain_fix_rsketch(sketch, "p0")
            sketch = scad.constrain_horizontal_rsketch(sketch, "bottom")
            sketch = scad.constrain_vertical_rsketch(sketch, "right")
            sketch = scad.constrain_parallel_rsketch(sketch, "bottom", "top")
            sketch = scad.constrain_parallel_rsketch(sketch, "left", "right")
            sketch = scad.constrain_distance_rsketch(sketch, "p0", "p1", 2.0)
            sketch = scad.constrain_distance_rsketch(sketch, "p0", "p3", 1.0)
            sketch = scad.constrain_midpoint_rsketch(sketch, "mid", "bottom")
            scad.make_face_from_sketch_rface(sketch)
        payload = scad.export_model_json(session)
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
sketch = next(obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject' and getattr(obj, 'SimpleCADOp', '') == 'make_face_from_sketch_rface')
constraint_status = json.loads(sketch.SimpleCADSketchConstraints)
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'mapped_kinds': [item.get('kind') for item in constraint_status.get('mapped', [])],
        'skipped': constraint_status.get('skipped', []),
        'shape_edges': len(sketch.Shape.Edges),
    }, fh)
"""
        result = self._inspect_fcstd_json(payload, probe)

        self.assertEqual(result["shape_edges"], 4)
        self.assertIn("midpoint", [item.get("kind") for item in result["skipped"]])
        self.assertTrue(
            any(
                "no crash-safe FreeCAD Sketcher mapping" in str(item.get("reason"))
                for item in result["skipped"]
            )
        )

    def test_translate_model_json_binds_mixed_sketch_local_line_and_arc_center_expressions(
        self,
    ):
        graph = OperationGraph(graph_id="graph_mixed_local_expr")
        line = graph.add_node(
            op="make_line_redge",
            node_id="line_expr",
            params={"start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]},
            param_exprs={"end": [{"expr_id": "var_lx"}, {"expr_id": "var_ly"}, None]},
        )
        arc = graph.add_node(
            op="make_angle_arc_redge",
            node_id="arc_expr",
            params={
                "center": [1.0, 1.0, 0.0],
                "radius": 1.0,
                "start_angle": -1.5707963267948966,
                "end_angle": 0.0,
            },
            param_exprs={
                "center": [{"expr_id": "var_cx"}, {"expr_id": "var_cy"}, None],
                "radius": {"expr_id": "var_r"},
            },
        )
        wire = graph.add_node(
            op="make_wire_from_edges_rwire",
            node_id="wire_expr",
            params={"edge_count": 2},
            inputs=[line, arc],
        )
        payload = {
            "schema_version": "2.0",
            "canonical_contract": {"contract_version": "2.0"},
            "graph": graph.to_dict(),
            "leaf_ids": [wire.node_id],
            "expression_graph": {
                "nodes": [
                    {"expr_id": "var_lx", "kind": "var", "name": "lx", "default": 1.0},
                    {"expr_id": "var_ly", "kind": "var", "name": "ly", "default": 0.0},
                    {"expr_id": "var_cx", "kind": "var", "name": "cx", "default": 1.0},
                    {"expr_id": "var_cy", "kind": "var", "name": "cy", "default": 1.0},
                    {"expr_id": "var_r", "kind": "var", "name": "r", "default": 1.0},
                ]
            },
            "frame_graph": {"nodes": []},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
        }
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
result = {}
for obj in doc.Objects:
    if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject':
        result[obj.Name] = list(getattr(obj, 'ExpressionEngine', []))
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump(result, fh)
"""
        result = self._inspect_fcstd_json(json.dumps(payload), probe)
        all_entries = [entry for entries in result.values() for entry in entries]
        self.assertIn(
            ["Geometry[0].EndPoint.x", "<<SimpleCADExpressions>>.var_lx"],
            all_entries,
        )
        self.assertIn(
            ["Geometry[0].EndPoint.y", "<<SimpleCADExpressions>>.var_ly"],
            all_entries,
        )
        self.assertIn(
            ["Geometry[1].Center.x", "<<SimpleCADExpressions>>.var_cx"],
            all_entries,
        )
        self.assertIn(
            ["Geometry[1].Center.y", "<<SimpleCADExpressions>>.var_cy"],
            all_entries,
        )
        self.assertIn(
            ["Geometry[1].Radius", "<<SimpleCADExpressions>>.var_r"],
            all_entries,
        )

    def test_translate_model_json_binds_mixed_sketch_three_point_arc_expressions(
        self,
    ):
        graph = OperationGraph(graph_id="graph_mixed_three_point_expr")
        line = graph.add_node(
            op="make_line_redge",
            node_id="line_expr",
            params={"start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]},
        )
        arc = graph.add_node(
            op="make_three_point_arc_redge",
            node_id="arc_expr",
            params={
                "start": [1.0, 0.0, 0.0],
                "middle": [1.5, 0.5, 0.0],
                "end": [1.0, 1.0, 0.0],
            },
            param_exprs={
                "start": [{"expr_id": "var_sx"}, {"expr_id": "var_sy"}, None],
                "middle": [{"expr_id": "var_mx"}, {"expr_id": "var_my"}, None],
                "end": [{"expr_id": "var_ex"}, {"expr_id": "var_ey"}, None],
            },
        )
        wire = graph.add_node(
            op="make_wire_from_edges_rwire",
            node_id="wire_expr",
            params={"edge_count": 2},
            inputs=[line, arc],
        )
        payload = {
            "schema_version": "2.0",
            "canonical_contract": {"contract_version": "2.0"},
            "graph": graph.to_dict(),
            "leaf_ids": [wire.node_id],
            "expression_graph": {
                "nodes": [
                    {"expr_id": "var_sx", "kind": "var", "name": "sx", "default": 1.0},
                    {"expr_id": "var_sy", "kind": "var", "name": "sy", "default": 0.0},
                    {"expr_id": "var_mx", "kind": "var", "name": "mx", "default": 1.5},
                    {"expr_id": "var_my", "kind": "var", "name": "my", "default": 0.5},
                    {"expr_id": "var_ex", "kind": "var", "name": "ex", "default": 1.0},
                    {"expr_id": "var_ey", "kind": "var", "name": "ey", "default": 1.0},
                ]
            },
            "frame_graph": {"nodes": []},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
        }
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
result = {}
for obj in doc.Objects:
    if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject':
        result[obj.Name] = list(getattr(obj, 'ExpressionEngine', []))
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump(result, fh)
"""
        result = self._inspect_fcstd_json(json.dumps(payload), probe)
        all_entries = [entry for entries in result.values() for entry in entries]
        self.assertIn(
            ["Geometry[1].StartPoint.x", "<<SimpleCADExpressions>>.var_sx"],
            all_entries,
        )
        self.assertIn(
            ["Geometry[1].StartPoint.y", "<<SimpleCADExpressions>>.var_sy"],
            all_entries,
        )
        self.assertIn(
            ["Geometry[1].EndPoint.x", "<<SimpleCADExpressions>>.var_ex"],
            all_entries,
        )
        self.assertIn(
            ["Geometry[1].EndPoint.y", "<<SimpleCADExpressions>>.var_ey"],
            all_entries,
        )
        center_x = next(
            expr for prop, expr in all_entries if prop == "Geometry[1].Center.x"
        )
        center_y = next(
            expr for prop, expr in all_entries if prop == "Geometry[1].Center.y"
        )
        radius = next(
            expr for prop, expr in all_entries if prop == "Geometry[1].Radius"
        )
        self.assertIn("<<SimpleCADExpressions>>.var_sx", center_x)
        self.assertIn("<<SimpleCADExpressions>>.var_mx", center_x)
        self.assertIn("<<SimpleCADExpressions>>.var_ex", center_x)
        self.assertIn("<<SimpleCADExpressions>>.var_sy", center_y)
        self.assertIn("<<SimpleCADExpressions>>.var_my", center_y)
        self.assertIn("<<SimpleCADExpressions>>.var_ey", center_y)
        self.assertIn("Geometry[1].Center.x", [prop for prop, _ in all_entries])
        self.assertIn("Geometry[1].Center.y", [prop for prop, _ in all_entries])
        self.assertIn("pow(", radius)
        self.assertIn("<<SimpleCADExpressions>>.var_sx", radius)
        self.assertIn("<<SimpleCADExpressions>>.var_sy", radius)
        self.assertIn("<<SimpleCADExpressions>>.var_mx", radius)
        self.assertIn("<<SimpleCADExpressions>>.var_my", radius)
        self.assertIn("<<SimpleCADExpressions>>.var_ex", radius)
        self.assertIn("<<SimpleCADExpressions>>.var_ey", radius)

    def test_translate_model_json_exports_single_three_point_arc_sketch_with_expressions(
        self,
    ):
        graph = OperationGraph(graph_id="graph_single_three_point_expr")
        arc = graph.add_node(
            op="make_three_point_arc_redge",
            node_id="arc_expr",
            params={
                "start": [0.0, 0.0, 0.0],
                "middle": [1.0, 1.0, 0.0],
                "end": [2.0, 0.0, 0.0],
            },
            param_exprs={
                "start": [{"expr_id": "var_sx"}, {"expr_id": "var_sy"}, None],
                "middle": [{"expr_id": "var_mx"}, {"expr_id": "var_my"}, None],
                "end": [{"expr_id": "var_ex"}, {"expr_id": "var_ey"}, None],
            },
        )
        wire = graph.add_node(
            op="make_wire_from_edges_rwire",
            node_id="wire_expr",
            params={"edge_count": 1},
            inputs=[arc],
        )
        payload = {
            "schema_version": "2.0",
            "canonical_contract": {"contract_version": "2.0"},
            "graph": graph.to_dict(),
            "leaf_ids": [wire.node_id],
            "expression_graph": {
                "nodes": [
                    {"expr_id": "var_sx", "kind": "var", "name": "sx", "default": 0.0},
                    {"expr_id": "var_sy", "kind": "var", "name": "sy", "default": 0.0},
                    {"expr_id": "var_mx", "kind": "var", "name": "mx", "default": 1.0},
                    {"expr_id": "var_my", "kind": "var", "name": "my", "default": 1.0},
                    {"expr_id": "var_ex", "kind": "var", "name": "ex", "default": 2.0},
                    {"expr_id": "var_ey", "kind": "var", "name": "ey", "default": 0.0},
                ]
            },
            "frame_graph": {"nodes": []},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
        }
        probe = """
import json
import FreeCAD as App

doc = App.openDocument(FCSTD_PATH)
sketches = [obj for obj in doc.Objects if getattr(obj, 'TypeId', '') == 'Sketcher::SketchObject']
target = sketches[0]
with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    json.dump({
        'sketch_count': len(sketches),
        'exprs': list(getattr(target, 'ExpressionEngine', [])),
        'geom_count': len(list(getattr(target, 'Geometry', []))),
        'shape_type': target.Shape.ShapeType,
        'edge_count': len(target.Shape.Edges),
    }, fh)
"""
        result = self._inspect_fcstd_json(json.dumps(payload), probe)
        self.assertEqual(result["sketch_count"], 1)
        self.assertEqual(result["geom_count"], 1)
        self.assertEqual(result["shape_type"], "Wire")
        self.assertEqual(result["edge_count"], 1)
        expr_map = {prop: expr for prop, expr in result["exprs"]}
        self.assertIn("Geometry[0].StartPoint.x", expr_map)
        self.assertIn("Geometry[0].StartPoint.y", expr_map)
        self.assertIn("Geometry[0].EndPoint.x", expr_map)
        self.assertIn("Geometry[0].EndPoint.y", expr_map)
        self.assertIn("Geometry[0].Center.x", expr_map)
        self.assertIn("Geometry[0].Center.y", expr_map)
        self.assertIn("Geometry[0].Radius", expr_map)
        self.assertIn(
            "<<SimpleCADExpressions>>.var_sx", expr_map["Geometry[0].StartPoint.x"]
        )
        self.assertIn(
            "<<SimpleCADExpressions>>.var_sy", expr_map["Geometry[0].StartPoint.x"]
        )
        self.assertIn(
            "<<SimpleCADExpressions>>.var_sx", expr_map["Geometry[0].StartPoint.y"]
        )
        self.assertIn(
            "<<SimpleCADExpressions>>.var_sy", expr_map["Geometry[0].StartPoint.y"]
        )
        self.assertIn(
            "<<SimpleCADExpressions>>.var_ex", expr_map["Geometry[0].EndPoint.x"]
        )
        self.assertIn(
            "<<SimpleCADExpressions>>.var_ey", expr_map["Geometry[0].EndPoint.x"]
        )
        self.assertIn(
            "<<SimpleCADExpressions>>.var_ex", expr_map["Geometry[0].EndPoint.y"]
        )
        self.assertIn(
            "<<SimpleCADExpressions>>.var_ey", expr_map["Geometry[0].EndPoint.y"]
        )

    def test_translate_model_json_uses_selector_index_fallback_for_detail_features(
        self,
    ):
        with GraphSession() as session:
            box = scad.make_box_rsolid(2.0, 2.0, 2.0)
            scad.chamfer_rsolid(box, [box.get_edges(0)], 0.2)
            scad.shell_rsolid(box, [box.get_faces(0)], 0.1)

        script = scad.translate_model_json_to_freecad_script(
            scad.export_model_json(session)
        )

        self.assertIn("Part::Chamfer", script)
        self.assertIn("Part::Thickness", script)
        self.assertIn("selected_edge_indices", script)
        self.assertIn("selected_face_indices", script)

    def test_translate_model_json_does_not_emit_assembly_scaffold(self):
        with GraphSession() as session:
            scad.make_box_rsolid(1.0, 1.0, 1.0)

        script = scad.translate_model_json_to_freecad_script(
            scad.export_model_json(session)
        )

        self.assertNotIn("Assembly::AssemblyObject", script)
        self.assertNotIn("Assembly::JointGroup", script)
        self.assertNotIn("PART_REGISTRY", script)
        self.assertNotIn("CONSTRAINT_REGISTRY", script)
        self.assertNotIn("SimpleCAD Constraint", script)

    def test_translate_model_json_preserves_pattern_multi_output_structure(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(1.0, 1.0, 1.0)
            scad.linear_pattern_rsolidlist(box, (1.0, 0.0, 0.0), 3, 2.0)

        script = scad.translate_model_json_to_freecad_script(
            scad.export_model_json(session)
        )

        self.assertIn("GRAPH_OUTPUTS", script)
        self.assertIn("App::Link", script)
        self.assertNotIn("linear_pattern", script)
        self.assertIn("RESULT_NODE_IDS", script)

    def test_translate_model_json_hides_non_leaf_graph_objects(self):
        with GraphSession() as session:
            box = scad.make_box_rsolid(2.0, 3.0, 4.0)
            scad.translate_shape(box, (1.0, 2.0, 3.0))

        script = scad.translate_model_json_to_freecad_script(
            scad.export_model_json(session)
        )

        self.assertIn("_apply_result_visibility(RESULT_NODE_IDS)", script)
        self.assertIn("def _set_visibility", script)
        self.assertIn("def _apply_result_visibility", script)

    def test_translate_model_json_rejects_field_surface_ops(self):
        graph = OperationGraph(graph_id="graph_field")
        graph.add_node(
            op="make_field_surface_rsolid",
            params={
                "bounds": {"min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 1.0]},
                "resolution": [8, 8, 8],
                "iso": 0.0,
                "cap_bounds": True,
                "field_serialization_mode": "scalar_field",
                "field_tree": {
                    "op": "box",
                    "params": {"center": [0.0, 0.0, 0.0], "size": [1.0, 1.0, 1.0]},
                    "children": [],
                },
            },
        )
        payload = {
            "schema_version": "2.0",
            "canonical_contract": {"contract_version": "2.0"},
            "graph": graph.to_dict(),
            "leaf_ids": [graph.leaf_nodes()[0].node_id],
            "expression_graph": {"nodes": []},
            "frame_graph": {"nodes": []},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
        }

        with self.assertRaises(ValueError):
            scad.translate_model_json_to_freecad_script(json.dumps(payload))

    def test_translate_model_json_to_fcstd_invokes_freecadcmd(self):
        with GraphSession() as session:
            scad.make_box_rsolid(1.0, 1.0, 1.0)

        payload = scad.export_model_json(session)

        with (
            mock.patch(
                "shutil.which",
                side_effect=lambda name: (
                    "/usr/bin/FreeCADCmd" if name == "FreeCADCmd" else None
                ),
            ),
            mock.patch("subprocess.run") as run_mock,
        ):
            run_mock.return_value = mock.Mock(
                returncode=0, stdout="/tmp/out.FCStd\n", stderr=""
            )
            out = scad.translate_model_json_to_fcstd(payload, "/tmp/out.FCStd")

        self.assertEqual(out, "/tmp/out.FCStd")
        run_mock.assert_called_once()

    def test_translate_model_json_to_fcstd_requires_freecadcmd(self):
        with GraphSession() as session:
            scad.make_box_rsolid(1.0, 1.0, 1.0)

        payload = scad.export_model_json(session)

        with (
            mock.patch("shutil.which", return_value=None),
            mock.patch("os.path.exists", return_value=False),
        ):
            with self.assertRaises(scad.SimpleCADError):
                scad.translate_model_json_to_fcstd(payload, "/tmp/out.FCStd")

    def test_translate_model_json_to_fcstd_discovers_macos_bundle_freecadcmd(self):
        with GraphSession() as session:
            scad.make_box_rsolid(1.0, 1.0, 1.0)

        payload = scad.export_model_json(session)

        def fake_exists(path: str) -> bool:
            return path == "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"

        with (
            mock.patch("shutil.which", return_value=None),
            mock.patch("os.path.exists", side_effect=fake_exists),
            mock.patch("subprocess.run") as run_mock,
        ):
            run_mock.return_value = mock.Mock(
                returncode=0, stdout="/tmp/out.FCStd\n", stderr=""
            )
            out = scad.translate_model_json_to_fcstd(payload, "/tmp/out.FCStd")

        self.assertEqual(out, "/tmp/out.FCStd")
        args, _kwargs = run_mock.call_args
        self.assertEqual(
            args[0][0], "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
        )


if __name__ == "__main__":
    unittest.main()
