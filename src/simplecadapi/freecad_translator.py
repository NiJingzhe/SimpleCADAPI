"""Translate SimpleCAD model/graph payloads into FreeCAD Python API scripts.

This module intentionally targets FreeCAD's Python API, not raw `.FCStd`
internals. Generated scripts can be executed inside FreeCAD/FreeCADCmd and then
saved as `.FCStd` by FreeCAD itself.
"""

from __future__ import annotations

import json
import os
import pprint
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .errors import raise_harness_error
from .serializer import import_model_json
from .topology import OperationGraph, OperationNode


def _json_ascii(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _py_literal(value: Any) -> str:
    return pprint.pformat(value, compact=True, sort_dicts=True, width=120)


def _safe_name(raw: str, *, prefix: str = "obj") -> str:
    token = "".join(ch if ch.isalnum() else "_" for ch in raw)
    token = token.strip("_")
    if not token:
        token = prefix
    if token[0].isdigit():
        token = f"{prefix}_{token}"
    return token


def _discover_freecad_executable() -> Optional[str]:
    candidates = [
        shutil.which("FreeCADCmd"),
        shutil.which("freecadcmd"),
        shutil.which("FreeCAD"),
        "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd",
        "/Applications/FreeCAD.app/Contents/MacOS/FreeCAD",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


_OP_EXPRESSION_BINDINGS: Dict[str, Tuple[Tuple[str, Tuple[Any, ...]], ...]] = {
    "make_line_redge": (),
    "make_circle_redge": (),
    "make_angle_arc_redge": (),
    "make_three_point_arc_redge": (),
    "make_spline_redge": (),
    "make_wire_from_edges_rwire": (),
    "make_helix_redge": (
        ("Pitch", ("pitch",)),
        ("Height", ("height",)),
        ("Radius", ("radius",)),
        ("Placement.Base.x", ("center", 0)),
        ("Placement.Base.y", ("center", 1)),
        ("Placement.Base.z", ("center", 2)),
    ),
    "make_face_from_wire_rface": (),
    "make_extrude_rsolid": (
        ("LengthFwd", ("distance",)),
        ("Dir.x", ("direction", 0)),
        ("Dir.y", ("direction", 1)),
        ("Dir.z", ("direction", 2)),
    ),
    "make_revolve_rsolid": (
        ("Angle", ("angle",)),
        ("Axis.x", ("axis", 0)),
        ("Axis.y", ("axis", 1)),
        ("Axis.z", ("axis", 2)),
        ("Base.x", ("origin", 0)),
        ("Base.y", ("origin", 1)),
        ("Base.z", ("origin", 2)),
    ),
    "make_loft_rsolid": (("Ruled", ("ruled",)),),
    "make_sweep_rsolid": (("Frenet", ("is_frenet",)),),
    "make_cut_rsolid": (),
    "make_union_rsolid": (),
    "make_intersect_rsolid": (),
    "make_fillet_rsolid": (),
    "make_chamfer_rsolid": (),
    "make_shell_rsolid": (("Value", ("thickness",)),),
    "make_mirror_rshape": (
        ("Base.x", ("plane_origin", 0)),
        ("Base.y", ("plane_origin", 1)),
        ("Base.z", ("plane_origin", 2)),
        ("Normal.x", ("plane_normal", 0)),
        ("Normal.y", ("plane_normal", 1)),
        ("Normal.z", ("plane_normal", 2)),
    ),
    "make_translate_rshape": (
        ("Placement.Base.x", ("vector", 0)),
        ("Placement.Base.y", ("vector", 1)),
        ("Placement.Base.z", ("vector", 2)),
    ),
    "make_rotate_rshape": (
        ("Placement.Base.x", ("origin", 0)),
        ("Placement.Base.y", ("origin", 1)),
        ("Placement.Base.z", ("origin", 2)),
        ("Placement.Rotation.Axis.x", ("axis", 0)),
        ("Placement.Rotation.Axis.y", ("axis", 1)),
        ("Placement.Rotation.Axis.z", ("axis", 2)),
        ("Placement.Rotation.Angle", ("angle",)),
    ),
}


_OP_EXPRESSION_LIMITATIONS: Dict[str, str] = {
    "make_spline_redge": (
        "Exact B-spline pole/weight expressions have no stable equivalent native "
        "FreeCAD Sketcher BSpline parameter host. The translator exports exact "
        "B-spline geometry, but does not map make_spline_redge param_exprs into "
        "FreeCAD ExpressionEngine."
    ),
}


def _contains_expr_refs(value: Any) -> bool:
    if isinstance(value, dict):
        if isinstance(value.get("expr_id"), str) and value["expr_id"]:
            return True
        return any(_contains_expr_refs(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_expr_refs(v) for v in value)
    return False


def _expression_limitation_payload(
    op: str, param_exprs: Any
) -> Optional[Dict[str, str]]:
    if not _contains_expr_refs(param_exprs or {}):
        return None
    reason = _OP_EXPRESSION_LIMITATIONS.get(str(op))
    if not reason:
        return None
    return {"op": str(op), "reason": str(reason)}


def _node_expression_limitation(
    node: Optional[OperationNode],
) -> Optional[Dict[str, str]]:
    if node is None:
        return None
    payload = _expression_limitation_payload(str(node.op), dict(node.param_exprs))
    if payload is None:
        return None
    return {"node_id": str(node.node_id), **payload}


def _sanitize_expr_alias(alias: str, *, prefix: str = "expr") -> str:
    token = "".join(ch if str(ch).isalnum() else "_" for ch in str(alias)).strip("_")
    if not token:
        token = prefix
    if token[0].isdigit():
        token = f"{prefix}_{token}"
    return token[:64]


def _expr_short_suffix(expr_id: str) -> str:
    raw = str(expr_id).rsplit("_", 1)[-1]
    token = "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_")
    return token[:8] if token else "id"


def _const_value_alias_token(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return "value"
    text = f"{number:.6g}".replace("-", "neg_").replace(".", "_")
    token = "".join(ch if ch.isalnum() else "_" for ch in text).strip("_")
    return token or "value"


def _spreadsheet_expr_alias(expr_node: Dict[str, Any], row: int) -> str:
    expr_id = str(expr_node.get("expr_id", f"expr_{row}"))
    kind = str(expr_node.get("kind", "expr"))
    if kind == "var":
        name = str(expr_node.get("name", "")).strip()
        if name:
            return _sanitize_expr_alias(f"var_{name}", prefix="var")
    if kind == "const":
        return _sanitize_expr_alias(
            f"const_{_const_value_alias_token(expr_node.get('value'))}_{_expr_short_suffix(expr_id)}",
            prefix="const",
        )
    op = str(expr_node.get("op", "expr")).strip() or "expr"
    return _sanitize_expr_alias(
        f"expr_{op}_{_expr_short_suffix(expr_id)}", prefix="expr"
    )


def _coincident_constraint_pairs(
    input_nodes: Sequence[Optional[OperationNode]],
) -> List[Tuple[int, int, int, int]]:
    pairs: List[Tuple[int, int, int, int]] = []
    if len(input_nodes) < 2:
        return pairs
    for idx in range(len(input_nodes) - 1):
        left = input_nodes[idx]
        right = input_nodes[idx + 1]
        if left is None or right is None:
            continue
        if left.op == "make_circle_redge" or right.op == "make_circle_redge":
            continue
        pairs.append((idx, 2, idx + 1, 1))
    first = input_nodes[0]
    last = input_nodes[-1]
    if (
        first is not None
        and last is not None
        and first.op != "make_circle_redge"
        and last.op != "make_circle_redge"
    ):
        try:
            first_start = first.params.get("start")
            last_end = last.params.get("end")
            if isinstance(first_start, (list, tuple)) and isinstance(
                last_end, (list, tuple)
            ):
                if all(
                    abs(float(a) - float(b)) <= 1e-7
                    for a, b in zip(first_start, last_end)
                ):
                    pairs.append((len(input_nodes) - 1, 2, 0, 1))
        except Exception:
            pass
    return pairs


def _compile_time_nested_expr_ref(expr_meta: Any, *path: Any) -> Any:
    value = expr_meta
    for key in path:
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and isinstance(key, int) and 0 <= key < len(value):
            value = value[key]
        else:
            return None
    return value


class FreeCADScriptTranslator:
    """Compile a SimpleCAD model payload into a FreeCAD Python script.

    Current design goals:

    - Translate only from the canonical low-level `graph` IR
    - Preserve node metadata and graph lineage as FreeCAD custom properties
    - Preserve `expression_graph` as explicit translator metadata
    - Preserve exported assembly constraints as document metadata objects
    - Keep assembly metadata from the full model payload alongside the IR-driven
      geometry translation

    The generated script focuses on `Part`-workbench-style objects and shape
    construction, which is a better first target for the current canonical graph
    than a full `Sketcher/PartDesign` mapping.
    """

    def __init__(self, document_name: str = "SimpleCADModel") -> None:
        self.document_name = document_name
        self._source_graph: Optional[OperationGraph] = None
        self._expr_alias_by_id: Dict[str, str] = {}
        self._result_node_ids: Set[str] = set()
        self._result_node_id_list: List[str] = []
        self._suppressed_profile_node_ids: Set[str] = set()

    def _compile_time_expr_formula(self, expr_ref: Any) -> Optional[str]:
        if not isinstance(expr_ref, dict):
            return None
        expr_id = str(expr_ref.get("expr_id") or "")
        if not expr_id:
            return None
        alias = self._expr_alias_by_id.get(expr_id)
        if not alias:
            alias = _sanitize_expr_alias(expr_id, prefix="expr")
        return f"<<SimpleCADExpressions>>.{alias}"

    def _angle_arc_span_formula(self, param_exprs: Dict[str, Any]) -> Optional[str]:
        start_expr = self._compile_time_expr_formula(
            _compile_time_nested_expr_ref(param_exprs, "start_angle")
        )
        end_expr = self._compile_time_expr_formula(
            _compile_time_nested_expr_ref(param_exprs, "end_angle")
        )
        if start_expr is None and end_expr is None:
            return None
        if start_expr is None:
            return end_expr
        if end_expr is None:
            return f"0 - ({start_expr})"
        return f"({end_expr}) - ({start_expr})"

    def _line_delta_formula(
        self, param_exprs: Dict[str, Any], axis: int
    ) -> Optional[str]:
        start_expr = self._compile_time_expr_formula(
            _compile_time_nested_expr_ref(param_exprs, "start", axis)
        )
        end_expr = self._compile_time_expr_formula(
            _compile_time_nested_expr_ref(param_exprs, "end", axis)
        )
        if start_expr is None and end_expr is None:
            return None
        if start_expr is None:
            return end_expr
        if end_expr is None:
            return f"0 - ({start_expr})"
        return f"({end_expr}) - ({start_expr})"

    def translate_model_json_to_script(self, json_str: str) -> str:
        payload = import_model_json(json_str)
        graph = payload.get("graph")
        if not isinstance(graph, OperationGraph):
            raise ValueError(
                "FreeCAD translation requires model JSON with a canonical low-level graph"
            )
        if graph.node_count == 0:
            raise ValueError(
                "FreeCAD translation requires model JSON with a non-empty canonical low-level graph"
            )
        return self.translate_model_payload_to_script(payload, graph=graph)

    def translate_model_payload_to_script(
        self,
        payload: Dict[str, Any],
        *,
        graph: Optional[OperationGraph] = None,
    ) -> str:
        source_graph = graph or payload.get("graph")
        if not isinstance(source_graph, OperationGraph):
            raise ValueError(
                "FreeCAD translation requires payload to contain a canonical low-level graph"
            )
        if source_graph.node_count == 0:
            raise ValueError(
                "FreeCAD translation requires payload to contain a non-empty canonical low-level graph"
            )
        self._source_graph = source_graph
        leaf_ids = payload.get("leaf_ids")
        if isinstance(leaf_ids, list) and leaf_ids:
            self._result_node_id_list = [str(v) for v in leaf_ids]
        else:
            self._result_node_id_list = [leaf.node_id for leaf in source_graph.leaf_nodes()]
        self._result_node_ids = set(self._result_node_id_list)
        self._suppressed_profile_node_ids = self._find_cylinder_profile_nodes(source_graph)

        lines: List[str] = []
        emit = lines.append

        emit("import json")
        emit("import math")
        emit("import FreeCAD as App")
        emit("import Part")
        emit("try:")
        emit("    import Sketcher")
        emit("except Exception:")
        emit("    Sketcher = None")
        emit("try:")
        emit("    import Assembly")
        emit("except Exception:")
        emit("    Assembly = None")
        emit("try:")
        emit("    import JointObject")
        emit("except Exception:")
        emit("    JointObject = None")
        emit("try:")
        emit("    import Spreadsheet")
        emit("except Exception:")
        emit("    Spreadsheet = None")
        emit("import os")
        emit("import zipfile")
        emit("")
        emit(f"DOC_NAME = {_json_ascii(self.document_name)}")
        emit(
            "doc = App.getDocument(DOC_NAME) if DOC_NAME in App.listDocuments() else App.newDocument(DOC_NAME)"
        )
        emit("GRAPH_NODES = {}")
        emit("GRAPH_OUTPUTS = {}")
        emit("GRAPH_METADATA = {}")
        emit("GRAPH_SELECTIONS = {}")
        emit("GRAPH_SPINE_OBJECTS = {}")
        emit("GRAPH_LIMITATIONS = {}")
        emit("PRODUCT_VALUES = {}")
        emit("ASSEMBLY_PROJECTION_INPUTS = {}")
        emit("GUI_VISIBILITY_BY_NAME = {}")
        emit("GUI_EXPANDED_BY_NAME = {}")
        emit("SIMPLECAD_JOINT_OBJECTS = {}")
        emit("SKETCH_REGISTRY = []")
        expression_graph_payload = payload.get("expression_graph", {})
        if hasattr(expression_graph_payload, "to_dict"):
            expression_graph_payload = expression_graph_payload.to_dict()
        self._expr_alias_by_id = {}
        nodes = (
            expression_graph_payload.get("nodes", [])
            if isinstance(expression_graph_payload, dict)
            else []
        )
        if isinstance(nodes, list):
            row = 1
            for node in nodes:
                if isinstance(node, dict):
                    expr_id = str(node.get("expr_id", f"expr_{row}"))
                    self._expr_alias_by_id[expr_id] = _spreadsheet_expr_alias(node, row)
                    row += 1
        emit(f"EXPRESSION_GRAPH = {_py_literal(expression_graph_payload)}")
        emit(f"OP_EXPRESSION_BINDINGS = {_py_literal(_OP_EXPRESSION_BINDINGS)}")
        emit(f"OP_EXPRESSION_LIMITATIONS = {_py_literal(_OP_EXPRESSION_LIMITATIONS)}")
        emit("")
        emit(self._script_helpers())
        emit("")

        for line in self._emit_expression_graph(expression_graph_payload):
            emit(line)
        emit("")

        emit("EXPRESSION_GRAPH_META = EXPRESSION_GRAPH")
        emit("")

        for node in source_graph.topological_order():
            emit(f"# Step {node.node_id}: {node.op}")
            for line in self._emit_node(node):
                emit(line)
            emit("")

        emit("if GRAPH_LIMITATIONS:")
        emit(
            "    _make_metadata_note('simplecad_expression_limitations', 'SimpleCAD Expression Limitations', GRAPH_LIMITATIONS)"
        )
        emit("")

        emit("doc.recompute()")
        emit("")
        emit("# Leaf/result metadata")
        emit(f"RESULT_NODE_IDS = {_py_literal(self._result_node_id_list)}")
        emit(
            "RESULT_OBJECTS = [obj for node_id in RESULT_NODE_IDS for obj in GRAPH_OUTPUTS.get(node_id, [])]"
        )
        emit("_apply_result_visibility(RESULT_NODE_IDS)")
        emit("_set_active_result_object(RESULT_NODE_IDS)")
        emit("doc.TransientDir = getattr(doc, 'TransientDir', '')")
        return "\n".join(lines).rstrip() + "\n"

    def _find_cylinder_profile_nodes(self, graph: OperationGraph) -> Set[str]:
        use_counts: Dict[str, int] = {}
        for graph_node in graph.topological_order():
            for input_ref in graph_node.inputs:
                use_counts[input_ref.node_id] = use_counts.get(input_ref.node_id, 0) + 1

        suppressed: Set[str] = set()
        for graph_node in graph.topological_order():
            if graph_node.op != "make_extrude_rsolid" or len(graph_node.inputs) != 1:
                continue
            profile_node = graph.get_node(graph_node.inputs[0].node_id)
            face_node = None
            if (
                profile_node is not None
                and profile_node.op == "make_face_from_wire_rface"
                and len(profile_node.inputs) == 1
            ):
                face_node = profile_node
                profile_node = graph.get_node(profile_node.inputs[0].node_id)
            if (
                profile_node is None
                or profile_node.op != "make_wire_from_edges_rwire"
                or len(profile_node.inputs) != 1
            ):
                continue
            edge_node = graph.get_node(profile_node.inputs[0].node_id)
            if edge_node is None or edge_node.op != "make_circle_redge":
                continue
            profile_ids = [profile_node.node_id]
            if face_node is not None:
                profile_ids.append(face_node.node_id)
            if any(node_id in self._result_node_ids for node_id in profile_ids):
                continue
            if any(use_counts.get(node_id, 0) != 1 for node_id in profile_ids):
                continue
            suppressed.update(profile_ids)
        return suppressed

    def _emit_expression_graph(self, expression_graph_payload: Any) -> List[str]:
        if not isinstance(expression_graph_payload, dict):
            return []
        nodes = expression_graph_payload.get("nodes", [])
        if not isinstance(nodes, list) or not nodes:
            return []

        lines: List[str] = ["# Expression graph -> Spreadsheet"]
        lines.append("EXPR_CELL_BY_ID = {}")
        lines.append("EXPR_ALIAS_BY_ID = {}")
        lines.append("if Spreadsheet is not None:")
        lines.append(
            "    expr_sheet = doc.addObject('Spreadsheet::Sheet', 'SimpleCADExpressions')"
        )
        alias_by_id: Dict[str, str] = {}
        row = 1
        for node in nodes:
            if not isinstance(node, dict):
                continue
            expr_id = str(node.get("expr_id", f"expr_{row}"))
            alias_by_id[expr_id] = _spreadsheet_expr_alias(node, row)
            row += 1
        row = 1
        for node in nodes:
            if not isinstance(node, dict):
                continue
            expr_id = str(node.get("expr_id", f"expr_{row}"))
            alias = alias_by_id[expr_id]
            cell = f"B{row}"
            lines.append(
                f"    EXPR_CELL_BY_ID[{_json_ascii(expr_id)}] = {_json_ascii(cell)}"
            )
            lines.append(
                f"    EXPR_ALIAS_BY_ID[{_json_ascii(expr_id)}] = {_json_ascii(alias)}"
            )
            lines.append(f"    expr_sheet.set('A{row}', {_json_ascii(alias)})")
            lines.append(f"    expr_sheet.set('C{row}', {_json_ascii(expr_id)})")
            comment = (
                str(node.get("comment", "") or "")
                if str(node.get("kind", "")) == "var"
                else ""
            )
            lines.append(f"    expr_sheet.set('D{row}', {_json_ascii(comment)})")
            formula = self._freecad_expr_formula(node, alias_by_id)
            if formula is None:
                lines.append(
                    f"    expr_sheet.set({_json_ascii(cell)}, {_json_ascii('')})"
                )
            else:
                lines.append(
                    f"    expr_sheet.set({_json_ascii(cell)}, {_json_ascii(formula)})"
                )
            lines.append(
                f"    expr_sheet.setAlias({_json_ascii(cell)}, {_json_ascii(alias)})"
            )
            row += 1
        lines.append("else:")
        lines.append("    expr_sheet = None")
        return lines

    def _freecad_expr_formula(
        self, node: Dict[str, Any], alias_by_id: Dict[str, str]
    ) -> Optional[str]:
        kind = str(node.get("kind", ""))
        if kind == "const":
            return str(float(node.get("value", 0.0)))
        if kind == "var":
            return str(float(node.get("default", 0.0)))
        if kind != "expr":
            return None

        op = str(node.get("op", ""))
        args: List[str] = []
        for arg in node.get("args", []):
            alias = alias_by_id.get(str(arg))
            if not alias:
                return None
            args.append(f"<<SimpleCADExpressions>>.{alias}")
        if op == "add" and len(args) == 2:
            return f"={args[0]} + {args[1]}"
        if op == "sub" and len(args) == 2:
            return f"={args[0]} - {args[1]}"
        if op == "mul" and len(args) == 2:
            return f"={args[0]} * {args[1]}"
        if op == "div" and len(args) == 2:
            return f"={args[0]} / {args[1]}"
        if op == "pow" and len(args) == 2:
            return f"=pow({args[0]}, {args[1]})"
        if op == "neg" and len(args) == 1:
            return f"=-({args[0]})"
        if op == "abs" and len(args) == 1:
            return f"=abs({args[0]})"
        if op == "sin" and len(args) == 1:
            return f"=sin(({args[0]}) * 180 / pi)"
        if op == "cos" and len(args) == 1:
            return f"=cos(({args[0]}) * 180 / pi)"
        if op == "tan" and len(args) == 1:
            return f"=tan(({args[0]}) * 180 / pi)"
        if op == "sqrt" and len(args) == 1:
            return f"=sqrt({args[0]})"
        if op == "acos" and len(args) == 1:
            return f"=acos({args[0]}) * pi / 180"
        if op == "asin" and len(args) == 1:
            return f"=asin({args[0]}) * pi / 180"
        if op == "atan" and len(args) == 1:
            return f"=atan({args[0]}) * pi / 180"
        if op == "atan2" and len(args) == 2:
            return f"=atan2({args[0]}; {args[1]}) * pi / 180"
        return None

    def _can_fold_transform_into_input(self, node: OperationNode) -> bool:
        graph = self._source_graph
        if graph is None or node.op not in {"make_translate_rshape", "make_rotate_rshape"} or len(node.inputs) != 1:
            return False
        source = node.inputs[0]
        if source.op not in {
            "make_extrude_rsolid",
            "make_wire_from_edges_rwire",
            "make_face_from_wire_rface",
            "make_wire_from_sketch_rwire",
            "make_face_from_sketch_rface",
            "make_translate_rshape",
            "make_rotate_rshape",
        }:
            return False
        if source.node_id in self._result_node_ids:
            return False
        if graph.downstream_nodes(source.node_id) != [node.node_id]:
            return False
        return True

    def _script_helpers(self) -> str:
        return """
class SimpleCADUnsupportedOpError(RuntimeError):
    pass


def _ensure_string_property(obj, prop_name, group='SimpleCAD'):
    if prop_name not in list(getattr(obj, 'PropertiesList', []) or []):
        obj.addProperty('App::PropertyString', prop_name, group)


def _ensure_string_list_property(obj, prop_name, group='SimpleCAD'):
    if prop_name not in list(getattr(obj, 'PropertiesList', []) or []):
        obj.addProperty('App::PropertyStringList', prop_name, group)


def _ensure_string_map_property(obj, prop_name, group='SimpleCAD'):
    if prop_name not in list(getattr(obj, 'PropertiesList', []) or []):
        obj.addProperty('App::PropertyMap', prop_name, group)


def _contains_expr_refs(value):
    if isinstance(value, dict):
        if isinstance(value.get('expr_id'), str) and value['expr_id']:
            return True
        return any(_contains_expr_refs(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_expr_refs(v) for v in value)
    return False


def _expression_limitation_payload(op, param_exprs):
    if not _contains_expr_refs(param_exprs or {}):
        return None
    reason = OP_EXPRESSION_LIMITATIONS.get(str(op))
    if not reason:
        return None
    return {'op': str(op), 'reason': str(reason)}


def _record_graph_limitation(node_id, op, param_exprs):
    limitation = _expression_limitation_payload(op, param_exprs)
    if limitation:
        GRAPH_LIMITATIONS[str(node_id)] = limitation
    return limitation


def _attach_simplecad_metadata(obj, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    _ensure_string_property(obj, 'SimpleCADNodeId')
    _ensure_string_property(obj, 'SimpleCADOp')
    _ensure_string_property(obj, 'SimpleCADParams')
    _ensure_string_property(obj, 'SimpleCADInputs')
    _ensure_string_property(obj, 'SimpleCADContext')
    _ensure_string_property(obj, 'SimpleCADParamExprs')
    _ensure_string_property(obj, 'SimpleCADSemanticDelta')
    _ensure_string_property(obj, 'SimpleCADTopoDelta')
    _ensure_string_property(obj, 'SimpleCADOutputCount')
    _ensure_string_property(obj, 'SimpleCADExprSupport')
    _ensure_string_property(obj, 'SimpleCADExprLimitation')
    _ensure_string_list_property(obj, 'SimpleCADTags')
    obj.SimpleCADNodeId = str(node_id)
    obj.SimpleCADOp = str(op)
    obj.SimpleCADParams = json.dumps(params, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADInputs = json.dumps(inputs, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADContext = json.dumps(context or {}, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADParamExprs = json.dumps(param_exprs or {}, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADSemanticDelta = json.dumps(semantic_delta or {}, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADTopoDelta = json.dumps(topo_delta or {}, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADOutputCount = str(int(output_count))
    limitation = _expression_limitation_payload(op, param_exprs)
    obj.SimpleCADExprSupport = 'limited' if limitation else 'mapped_or_not_requested'
    obj.SimpleCADExprLimitation = limitation['reason'] if limitation else ''
    obj.SimpleCADTags = [str(tag) for tag in (tags or [])]


def _append_folded_op_metadata(obj, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    _ensure_string_property(obj, 'SimpleCADFoldedOps')
    try:
        folded = json.loads(obj.SimpleCADFoldedOps) if obj.SimpleCADFoldedOps else []
    except Exception:
        folded = []
    if not isinstance(folded, list):
        folded = []
    folded.append({
        'node_id': str(node_id),
        'op': str(op),
        'params': params or {},
        'inputs': list(inputs or []),
        'tags': list(tags or []),
        'context': context or {},
        'output_count': int(output_count),
        'param_exprs': param_exprs or {},
        'semantic_delta': semantic_delta or {},
        'topo_delta': topo_delta or {},
    })
    obj.SimpleCADFoldedOps = json.dumps(folded, ensure_ascii=True, sort_keys=True)
    existing_tags = list(getattr(obj, 'SimpleCADTags', []) or [])
    merged_tags = sorted({str(tag) for tag in existing_tags + list(tags or [])})
    try:
        obj.SimpleCADTags = merged_tags
    except Exception:
        pass


def _record_graph_output(node_id, obj):
    GRAPH_OUTPUTS.setdefault(node_id, []).append(obj)


def _register_graph_object(obj, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    _attach_simplecad_metadata(
        obj,
        node_id=node_id,
        op=op,
        params=params,
        inputs=inputs,
        tags=tags,
        context=context,
        output_count=output_count,
        param_exprs=param_exprs,
        semantic_delta=semantic_delta,
        topo_delta=topo_delta,
    )
    GRAPH_NODES[node_id] = obj
    GRAPH_METADATA[node_id] = {
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
    }
    _record_graph_limitation(node_id, op, param_exprs)
    _record_graph_output(node_id, obj)
    return obj


def _register_graph_metadata_only(*, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    GRAPH_NODES[node_id] = {
        'node_id': node_id,
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
        'output_count': int(output_count),
        'param_exprs': param_exprs or {},
        'semantic_delta': semantic_delta or {},
        'topo_delta': topo_delta or {},
    }
    GRAPH_METADATA[node_id] = {
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
    }
    _record_graph_limitation(node_id, op, param_exprs)
    GRAPH_OUTPUTS.setdefault(node_id, [])
    return GRAPH_NODES[node_id]


def _register_graph_alias(*, node_id, source_node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    source_obj = _node_object(source_node_id)
    GRAPH_NODES[node_id] = source_obj
    GRAPH_METADATA[node_id] = {
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
    }
    GRAPH_OUTPUTS[node_id] = list(GRAPH_OUTPUTS.get(source_node_id, []))
    return source_obj


def _register_graph_folded_alias(*, node_id, source_node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    source_obj = _node_object(source_node_id)
    _append_folded_op_metadata(
        source_obj,
        node_id=node_id,
        op=op,
        params=params,
        inputs=inputs,
        tags=tags,
        context=context,
        output_count=output_count,
        param_exprs=param_exprs,
        semantic_delta=semantic_delta,
        topo_delta=topo_delta,
    )
    GRAPH_NODES[node_id] = source_obj
    GRAPH_METADATA[node_id] = {
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
        'folded_into': str(source_node_id),
    }
    _record_graph_limitation(node_id, op, param_exprs)
    GRAPH_OUTPUTS[node_id] = [source_obj]
    return source_obj


def _register_graph_value(value, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    GRAPH_NODES[node_id] = value
    GRAPH_METADATA[node_id] = {
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
    }
    _record_graph_limitation(node_id, op, param_exprs)
    GRAPH_OUTPUTS[node_id] = []
    return value


def _make_feature(name, shape, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    obj = doc.addObject('Part::Feature', name)
    obj.Shape = shape
    return _register_graph_object(
        obj,
        node_id=node_id,
        op=op,
        params=params,
        inputs=inputs,
        tags=tags,
        context=context,
        output_count=output_count,
        param_exprs=param_exprs,
        semantic_delta=semantic_delta,
        topo_delta=topo_delta,
    )


def _make_native_object(type_id, name, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    obj = doc.addObject(type_id, name)
    return _register_graph_object(
        obj,
        node_id=node_id,
        op=op,
        params=params,
        inputs=inputs,
        tags=tags,
        context=context,
        output_count=output_count,
        param_exprs=param_exprs,
        semantic_delta=semantic_delta,
        topo_delta=topo_delta,
    )


def _make_native_assembly(name, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    if Assembly is None:
        raise RuntimeError('FreeCAD Assembly workbench module is required for SimpleCAD Assembly translation')
    obj = doc.addObject('Assembly::AssemblyObject', name)
    obj.Type = 'Assembly'
    try:
        obj.newObject('Assembly::JointGroup', 'Joints')
    except Exception:
        pass
    return _register_graph_object(
        obj,
        node_id=node_id,
        op=op,
        params=params,
        inputs=inputs,
        tags=tags,
        context=context,
        output_count=output_count,
        param_exprs=param_exprs,
        semantic_delta=semantic_delta,
        topo_delta=topo_delta,
    )


def _joint_group_for(assembly_container):
    for child in list(getattr(assembly_container, 'OutList', []) or []):
        if getattr(child, 'TypeId', '') == 'Assembly::JointGroup':
            return child
    return assembly_container.newObject('Assembly::JointGroup', 'Joints')


def _find_component_entry(assembly_value, component_id):
    for component in list(assembly_value.get('components', []) or []):
        if str(component.get('component_id')) == str(component_id):
            return component
    raise RuntimeError(f'Missing assembly component {component_id!r}')


def _connector_payload_for(component_entry, connector_id):
    item = component_entry.get('item') or {}
    for connector in list(item.get('connectors', []) or []):
        if str(connector.get('connector_id')) == str(connector_id):
            return connector
    raise RuntimeError(f'Missing connector {connector_id!r} on component {component_entry.get("component_id")!r}')


def _freecad_subname_for_kind(kind, index):
    # Convert a 0-based index into a FreeCAD sub-element name string.
    kind_lower = str(kind).lower()
    prefix_map = {'vertex': 'Vertex', 'edge': 'Edge', 'wire': 'Wire', 'face': 'Face', 'solid': 'Solid'}
    prefix = prefix_map.get(kind_lower, 'Face')
    return f'{prefix}{index + 1}'


def _resolve_connector_subname(component_entry, connector_payload):
    # Resolve the FreeCAD sub-element name (e.g. Face3) for a connector geometry_ref.
    # Uses the geo_selector to match against the component link shape.
    # Returns a tuple (subname1, subname2) suitable for FreeCAD Reference1/Reference2.
    geometry_ref = connector_payload.get('geometry_ref') or {}
    geo_selector = geometry_ref.get('geo_selector') or {}
    kind = str(geometry_ref.get('kind') or geo_selector.get('kind') or '').lower()
    if not kind:
        return '', ''
    link = component_entry.get('link')
    if link is None:
        return '', ''
    linked_obj = getattr(link, 'LinkedObject', None) or link
    shape = getattr(linked_obj, 'Shape', None)
    if shape is None:
        return '', ''
    try:
        index = _selection_index_for_selector(shape, geo_selector)
        subname = _freecad_subname_for_kind(kind, index)
        return subname, subname
    except Exception:
        return '', ''


def _make_simplecad_joint(assembly_value, constraint_payload, object_name, label):
    assembly_container = assembly_value.get('container')
    if assembly_container is None:
        raise RuntimeError('Assembly value has no container for constraint translation')
    connector_a = constraint_payload.get('connector_a') or {}
    connector_b = constraint_payload.get('connector_b') or {}
    component_a = _find_component_entry(assembly_value, connector_a.get('component_id'))
    component_b = _find_component_entry(assembly_value, connector_b.get('component_id'))
    connector_a_payload = _connector_payload_for(component_a, connector_a.get('connector_id'))
    connector_b_payload = _connector_payload_for(component_b, connector_b.get('connector_id'))
    joint_type = {'fixed': 'Fixed', 'revolute': 'Revolute', 'prismatic': 'Slider'}.get(str(constraint_payload.get('constraint_kind')))
    if not joint_type:
        raise RuntimeError(f"Unsupported SimpleCAD constraint kind {constraint_payload.get('constraint_kind')!r}")
    joint_group = _joint_group_for(assembly_container)
    joint = joint_group.newObject('App::FeaturePython', object_name)
    joint.Label = str(label or constraint_payload.get('constraint_id') or object_name)
    type_index = {'Fixed': 0, 'Revolute': 1, 'Slider': 3}[joint_type]
    native_status = 'metadata_only'
    if JointObject is not None:
        JointObject.Joint(joint, type_index)
        native_status = 'native_equivalent'
        if getattr(App, 'GuiUp', False) and hasattr(joint, 'ViewObject') and joint.ViewObject is not None:
            try:
                JointObject.ViewProviderJoint(joint.ViewObject)
            except Exception:
                pass
    else:
        _ensure_string_property(joint, 'JointType')
        joint.JointType = joint_type
    try:
        link_a = component_a.get('link')
        link_b = component_b.get('link')
        sub_a1, sub_a2 = _resolve_connector_subname(component_a, connector_a_payload)
        sub_b1, sub_b2 = _resolve_connector_subname(component_b, connector_b_payload)
        if hasattr(joint, 'Reference1'):
            joint.Reference1 = (link_a, [sub_a1, sub_a2])
            joint.Reference2 = (link_b, [sub_b1, sub_b2])
            joint.Detach1 = False
            joint.Detach2 = False
    except Exception:
        native_status = 'native_partial'
    if joint_type == 'Revolute' and constraint_payload.get('drive_angle_degrees') is not None:
        try:
            joint.Angle = float(constraint_payload.get('drive_angle_degrees'))
        except Exception:
            native_status = 'native_partial'
    if joint_type == 'Slider' and constraint_payload.get('drive_distance') is not None:
        try:
            joint.Distance = float(constraint_payload.get('drive_distance'))
        except Exception:
            native_status = 'native_partial'
    angle_limit = constraint_payload.get('angle_limit')
    if angle_limit:
        try:
            joint.EnableAngleMin = True
            joint.EnableAngleMax = True
            joint.AngleMin = float(angle_limit.get('lower_value'))
            joint.AngleMax = float(angle_limit.get('upper_value'))
        except Exception:
            native_status = 'native_partial'
    distance_limit = constraint_payload.get('distance_limit')
    if distance_limit:
        try:
            joint.EnableLengthMin = True
            joint.EnableLengthMax = True
            joint.LengthMin = float(distance_limit.get('lower_value'))
            joint.LengthMax = float(distance_limit.get('upper_value'))
        except Exception:
            native_status = 'native_partial'
    _ensure_string_property(joint, 'SimpleCADConstraint')
    _ensure_string_property(joint, 'SimpleCADConstraintTranslationStatus')
    joint.SimpleCADConstraint = json.dumps(constraint_payload, ensure_ascii=True, sort_keys=True)
    joint.SimpleCADConstraintTranslationStatus = native_status
    _set_visibility(joint, True)
    try:
        SIMPLECAD_JOINT_OBJECTS[str(joint.Name)] = joint_type
    except Exception:
        pass
    return joint


def _make_simplecad_grounded_joint(assembly_value, component_id):
    assembly_container = assembly_value.get('container')
    if assembly_container is None:
        raise RuntimeError('Assembly value has no container for grounded joint translation')
    component_entry = _find_component_entry(assembly_value, component_id)
    link = component_entry.get('link')
    if link is None:
        raise RuntimeError(f'Missing component link for grounded component {component_id!r}')
    joint_group = _joint_group_for(assembly_container)
    ground = joint_group.newObject('App::FeaturePython', 'GroundedJoint_' + str(component_id))
    ground.Label = 'GroundedJoint_' + str(component_id)
    native_status = 'metadata_only'
    if JointObject is not None:
        JointObject.GroundedJoint(ground, link)
        native_status = 'native_equivalent'
    else:
        _ensure_string_property(ground, 'ObjectToGround')
    _ensure_string_property(ground, 'SimpleCADGroundedComponent')
    ground.SimpleCADGroundedComponent = str(component_id)
    _set_visibility(ground, True)
    try:
        SIMPLECAD_JOINT_OBJECTS[str(ground.Name)] = 'Grounded'
    except Exception:
        pass
    return ground


PRODUCT_LIBRARY_GROUP = None
CONSTRUCTION_GROUP = None


def _named_document_group(name, label):
    existing = doc.getObject(name)
    if existing is not None:
        return existing
    group = doc.addObject('App::DocumentObjectGroup', name)
    group.Label = label
    _set_visibility(group, False)
    return group


def _product_library_group():
    global PRODUCT_LIBRARY_GROUP
    if PRODUCT_LIBRARY_GROUP is None:
        PRODUCT_LIBRARY_GROUP = _named_document_group('SimpleCADProductLibrary', 'SimpleCAD Product Library')
    return PRODUCT_LIBRARY_GROUP


def _construction_group():
    global CONSTRUCTION_GROUP
    if CONSTRUCTION_GROUP is None:
        CONSTRUCTION_GROUP = _named_document_group('SimpleCADConstruction', 'SimpleCAD Construction')
    return CONSTRUCTION_GROUP


def _group_contains(group, obj):
    return obj in list(getattr(group, 'Group', []) or [])


def _add_to_group(group, obj):
    if obj is None or obj is group:
        return
    if not _group_contains(group, obj):
        try:
            group.addObject(obj)
        except Exception:
            pass


def _hide_origin_tree(container):
    for child in list(getattr(container, 'Group', []) or []):
        if getattr(child, 'TypeId', '') == 'App::Origin' or str(getattr(child, 'Name', '')).startswith('Origin'):
            _set_visibility(child, False)
            for nested in list(getattr(child, 'OutListRecursive', []) or []):
                _set_visibility(nested, False)


def _move_to_construction_group(obj):
    group = _construction_group()
    for candidate in [obj] + list(getattr(obj, 'OutListRecursive', []) or []):
        if candidate is None:
            continue
        if getattr(candidate, 'TypeId', '') in {'App::Origin', 'App::Line', 'App::Plane', 'App::Point'}:
            continue
        _add_to_group(group, candidate)
        _set_visibility(candidate, False)
    _set_visibility(group, False)


def _move_product_source_to_library(product_item):
    container = product_item.get('container') if isinstance(product_item, dict) else None
    if container is None:
        return
    group = _product_library_group()
    _add_to_group(group, container)
    _set_visibility(container, False)
    _hide_origin_tree(container)
    _set_visibility(group, False)


def _make_part_body_copy(part_container, source_obj, source_node_id):
    doc.recompute()
    if source_obj is None or not hasattr(source_obj, 'Shape'):
        raise RuntimeError('Part body source has no shape')
    body = part_container.newObject('Part::Feature', 'Body')
    body.Label = 'Body'
    body.Shape = source_obj.Shape.copy()
    _ensure_string_property(body, 'SimpleCADSourceBodyNodeId')
    body.SimpleCADSourceBodyNodeId = str(source_node_id)
    _set_visibility(body, True)
    _move_to_construction_group(source_obj)
    return body


def _make_assembly_component_link(assembly_container, product_item, name, label, placement):
    link_type = 'Assembly::AssemblyLink' if product_item.get('kind') == 'assembly' else 'App::Link'
    link = assembly_container.newObject(link_type, name)
    link.Label = str(label)
    _move_product_source_to_library(product_item)
    link.LinkedObject = product_item.get('container')
    if product_item.get('kind') == 'part':
        link.LinkedObject = product_item.get('container') or product_item.get('body')
    link.Placement = _placement_from_axes_payload(placement)
    if link_type == 'Assembly::AssemblyLink':
        try:
            link.Rigid = True
        except Exception:
            pass
    return link


def _node_object(node_id, index=0):
    outputs = GRAPH_OUTPUTS.get(node_id, [])
    if not outputs:
        raise RuntimeError(f'Missing graph output object for node {node_id!r}')
    idx = int(index)
    if idx < 0 or idx >= len(outputs):
        raise RuntimeError(f'Output object slot {idx} missing for node {node_id!r}')
    return outputs[idx]


def _set_visibility(obj, visible):
    if obj is not None:
        try:
            GUI_VISIBILITY_BY_NAME[str(obj.Name)] = bool(visible)
        except Exception:
            pass
    try:
        view = getattr(obj, 'ViewObject', None)
        if view is not None and hasattr(view, 'Visibility'):
            view.Visibility = bool(visible)
    except Exception:
        pass
    try:
        if hasattr(obj, 'Visibility'):
            obj.Visibility = bool(visible)
    except Exception:
        pass


def _set_expanded(obj, expanded=True):
    try:
        GUI_EXPANDED_BY_NAME[str(obj.Name)] = bool(expanded)
    except Exception:
        pass


def _xml_attr(value):
    return str(value).replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def _visibility_for_gui(obj):
    try:
        name = str(obj.Name)
    except Exception:
        return False
    if name in GUI_VISIBILITY_BY_NAME:
        return bool(GUI_VISIBILITY_BY_NAME[name])
    try:
        return bool(obj.Visibility)
    except Exception:
        return False


def _write_gui_document_xml(fcstd_path):
    object_rows = []
    for obj in list(getattr(doc, 'Objects', []) or []):
        try:
            name = str(obj.Name)
        except Exception:
            continue
        object_rows.append((name, _visibility_for_gui(obj), bool(GUI_EXPANDED_BY_NAME.get(name, False))))
    lines = [
        "<?xml version='1.0' encoding='utf-8'?>",
        '<!--',
        ' FreeCAD Document, see https://www.freecad.org for more information...',
        '-->',
        '<Document SchemaVersion="1">',
        f'    <ViewProviderData Count="{len(object_rows)}">',
    ]
    for name, visible, expanded in object_rows:
        joint_type = SIMPLECAD_JOINT_OBJECTS.get(name)
        if joint_type is not None:
            vp_class = 'ViewProviderGroundedJoint' if joint_type == 'Grounded' else 'ViewProviderJoint'
            lines.extend([
                f'        <ViewProvider name="{_xml_attr(name)}" expanded="{1 if expanded else 0}">',
                '            <Properties Count="2">',
                '                <Property name="Visibility" type="App::PropertyBool">',
                f'                    <Bool value="{str(bool(visible)).lower()}"/>',
                '                </Property>',
                '                <Property name="Proxy" type="App::PropertyPythonObject" status="67108864">',
                f'                    <Python value="bnVsbA==" encoded="yes" module="JointObject" class="{vp_class}"/>',
                '                </Property>',
                '            </Properties>',
                '        </ViewProvider>',
            ])
        else:
            lines.extend([
                f'        <ViewProvider name="{_xml_attr(name)}" expanded="{1 if expanded else 0}">',
                '            <Properties Count="1">',
                '                <Property name="Visibility" type="App::PropertyBool">',
                f'                    <Bool value="{str(bool(visible)).lower()}"/>',
                '                </Property>',
                '            </Properties>',
                '        </ViewProvider>',
            ])
    lines.extend([
        '    </ViewProviderData>',
        '    <Camera settings="  OrthographicCamera { viewportMapping ADJUST_CAMERA position 0 -0 20000 orientation 0 0 1 0 nearDistance 1 farDistance 100000 aspectRatio 1 focalDistance 20000 height 1000 } "/>',
        '</Document>',
        '',
    ])
    gui_document = '\\n'.join(lines).encode('utf-8')
    tmp_path = str(fcstd_path) + '.simplecad_tmp'
    with zipfile.ZipFile(fcstd_path, 'r') as source:
        infos = source.infolist()
        with zipfile.ZipFile(tmp_path, 'w', compression=zipfile.ZIP_DEFLATED) as target:
            wrote_gui = False
            for info in infos:
                if info.filename == 'GuiDocument.xml':
                    target.writestr(info, gui_document)
                    wrote_gui = True
                else:
                    target.writestr(info, source.read(info.filename))
            if not wrote_gui:
                target.writestr('GuiDocument.xml', gui_document)
    os.replace(tmp_path, fcstd_path)


def _save_fcstd_with_gui_visibility(output_path):
    doc.recompute()
    doc.saveAs(output_path)
    _write_gui_document_xml(output_path)


def _placement_for_rotation(origin, axis, angle_degrees):
    center = _vec(origin)
    rotation = App.Rotation(_vec(axis), float(angle_degrees))
    to_center = App.Placement(center, rotation)
    from_center = App.Placement(App.Vector(-center.x, -center.y, -center.z), App.Rotation())
    return to_center.multiply(from_center)


def _fold_object_placement(obj, placement):
    obj.Placement = placement.multiply(obj.Placement)
    return obj


def _set_part_body_visibility(product_value, visible):
    container = product_value.get('container') if isinstance(product_value, dict) else None
    if container is None:
        return
    for child in list(getattr(container, 'Group', []) or []):
        if getattr(child, 'TypeId', '') == 'App::Origin' or str(getattr(child, 'Name', '')).startswith('Origin'):
            _set_visibility(child, False)
            continue
        _set_visibility(child, visible)


def _set_product_tree_visibility(product_value, visible, *, show_source_container=True):
    if not isinstance(product_value, dict):
        return
    kind = product_value.get('kind')
    container = product_value.get('container')
    if kind == 'part':
        if container is not None:
            _set_visibility(container, visible if show_source_container else False)
            _set_expanded(container, bool(visible and show_source_container))
            _hide_origin_tree(container)
        _set_part_body_visibility(product_value, visible)
        return
    if kind == 'assembly':
        if container is not None:
            _set_visibility(container, visible if show_source_container else False)
            _set_expanded(container, bool(visible and show_source_container))
            _hide_origin_tree(container)
        for component in product_value.get('components', []):
            link = component.get('link')
            if link is not None:
                _set_visibility(link, visible)
                _set_expanded(link, bool(visible))
            item = component.get('item')
            _set_product_tree_visibility(item, visible, show_source_container=False)


def _apply_product_result_visibility(visible_ids):
    product_ids = set()
    product_ids.update(str(node_id) for node_id in visible_ids if str(node_id) in PRODUCT_VALUES)
    product_ids.update(
        str(source_id)
        for node_id, source_id in ASSEMBLY_PROJECTION_INPUTS.items()
        if str(node_id) in visible_ids
    )
    for node_id in product_ids:
        _set_product_tree_visibility(PRODUCT_VALUES.get(node_id), True)
    if PRODUCT_LIBRARY_GROUP is not None:
        _set_visibility(PRODUCT_LIBRARY_GROUP, False)
    if CONSTRUCTION_GROUP is not None:
        _set_visibility(CONSTRUCTION_GROUP, False)


def _result_product_container(result_node_ids):
    for node_id in result_node_ids or []:
        product_value = PRODUCT_VALUES.get(str(node_id))
        if isinstance(product_value, dict) and product_value.get('container') is not None:
            return product_value.get('container')
        source_id = ASSEMBLY_PROJECTION_INPUTS.get(str(node_id))
        product_value = PRODUCT_VALUES.get(str(source_id))
        if isinstance(product_value, dict) and product_value.get('container') is not None:
            return product_value.get('container')
    return None


def _set_active_result_object(result_node_ids):
    obj = _result_product_container(result_node_ids)
    if obj is None:
        result_objects = [candidate for node_id in (result_node_ids or []) for candidate in GRAPH_OUTPUTS.get(str(node_id), [])]
        obj = result_objects[0] if result_objects else None
    if obj is None:
        return
    try:
        doc.ActiveObject = obj
    except Exception:
        pass
    try:
        import FreeCADGui as Gui
        if getattr(App, 'GuiUp', False) and Gui.ActiveDocument is not None:
            Gui.ActiveDocument.ActiveView.setActiveObject('part', obj)
    except Exception:
        pass


def _apply_result_visibility(result_node_ids):
    visible_ids = {str(node_id) for node_id in (result_node_ids or [])}
    projection_visible_ids = {str(source_id) for node_id, source_id in ASSEMBLY_PROJECTION_INPUTS.items() if str(node_id) in visible_ids}
    for node_id, outputs in GRAPH_OUTPUTS.items():
        is_visible = str(node_id) in visible_ids or str(node_id) in projection_visible_ids
        if str(node_id) in ASSEMBLY_PROJECTION_INPUTS:
            is_visible = False
        for obj in outputs:
            _set_visibility(obj, is_visible)
    _apply_product_result_visibility(visible_ids)


def _vec(v):
    return App.Vector(float(v[0]), float(v[1]), float(v[2]))


def _placement_from_axes_payload(payload):
    origin = payload.get('origin', (0.0, 0.0, 0.0))
    x_axis = payload.get('x_axis', (1.0, 0.0, 0.0))
    y_axis = payload.get('y_axis', (0.0, 1.0, 0.0))
    z_axis = payload.get('z_axis')
    if z_axis is None:
        x = _vec(x_axis)
        y = _vec(y_axis)
        z = x.cross(y)
        length = float(getattr(z, 'Length', 0.0))
        if length == 0.0:
            raise RuntimeError('Placement axes do not form a frame')
        z_axis = (z.x / length, z.y / length, z.z / length)
    matrix = App.Matrix()
    matrix.A11 = float(x_axis[0]); matrix.A12 = float(y_axis[0]); matrix.A13 = float(z_axis[0]); matrix.A14 = float(origin[0])
    matrix.A21 = float(x_axis[1]); matrix.A22 = float(y_axis[1]); matrix.A23 = float(z_axis[1]); matrix.A24 = float(origin[1])
    matrix.A31 = float(x_axis[2]); matrix.A32 = float(y_axis[2]); matrix.A33 = float(z_axis[2]); matrix.A34 = float(origin[2])
    return App.Placement(matrix)


def _shape_from_component_link(link):
    source = getattr(link, 'LinkedObject', None)
    if source is None or not hasattr(source, 'Shape'):
        raise RuntimeError('Component link has no shape-bearing linked object')
    shape = source.Shape.copy()
    try:
        shape.Placement = link.Placement.multiply(shape.Placement)
    except Exception:
        pass
    return shape


def _placed_shape_from_body(body, placement):
    if body is None or not hasattr(body, 'Shape'):
        raise RuntimeError('Part product value has no shape-bearing body')
    shape = body.Shape.copy()
    try:
        shape.Placement = placement.multiply(shape.Placement)
    except Exception:
        pass
    return shape


def _shapes_from_product_value(value, placement=None):
    placement = placement or App.Placement()
    if value.get('kind') == 'part':
        return [_placed_shape_from_body(value.get('body'), placement)]
    if value.get('kind') == 'assembly':
        shapes = []
        for component in value.get('components', []):
            component_placement = component.get('link').Placement if component.get('link') is not None else _placement_from_axes_payload(component.get('placement') or {})
            shapes.extend(_shapes_from_product_value(component.get('item'), placement.multiply(component_placement)))
        return shapes
    raise RuntimeError('Unsupported product value for shape projection')


def _normalized_vec(v):
    vec = _vec(v)
    length = float(getattr(vec, 'Length', 0.0))
    if length == 0.0:
        raise RuntimeError('Expected a non-zero vector')
    return App.Vector(vec.x / length, vec.y / length, vec.z / length)


def _scaled_direction(direction, distance):
    unit = _normalized_vec(direction)
    dist = float(distance)
    return App.Vector(unit.x * dist, unit.y * dist, unit.z * dist)


def _placement_from_context(context):
    origin = context.get('origin') if isinstance(context, dict) else None
    if isinstance(origin, (list, tuple)) and len(origin) == 3:
        return App.Placement(_vec(origin), App.Rotation())
    return App.Placement()


def _rotation_from_context_axes(context):
    if not isinstance(context, dict):
        return App.Rotation()
    x_axis = context.get('x_axis')
    y_axis = context.get('y_axis')
    z_axis = context.get('z_axis')
    if not (
        isinstance(x_axis, (list, tuple)) and len(x_axis) == 3 and
        isinstance(y_axis, (list, tuple)) and len(y_axis) == 3 and
        isinstance(z_axis, (list, tuple)) and len(z_axis) == 3
    ):
        return App.Rotation()
    m = App.Matrix()
    m.A11, m.A21, m.A31 = float(x_axis[0]), float(x_axis[1]), float(x_axis[2])
    m.A12, m.A22, m.A32 = float(y_axis[0]), float(y_axis[1]), float(y_axis[2])
    m.A13, m.A23, m.A33 = float(z_axis[0]), float(z_axis[1]), float(z_axis[2])
    return App.Rotation(m)


def _sketch_placement_from_context(context):
    origin = context.get('origin') if isinstance(context, dict) else None
    base = _vec(origin) if isinstance(origin, (list, tuple)) and len(origin) == 3 else App.Vector(0.0, 0.0, 0.0)
    return App.Placement(base, _rotation_from_context_axes(context))


def _line_sketch_placement(start, end):
    start_v = _vec(start)
    end_v = _vec(end)
    delta = App.Vector(end_v.x - start_v.x, end_v.y - start_v.y, end_v.z - start_v.z)
    x_axis = _normalized_vec((delta.x, delta.y, delta.z))
    ref = App.Vector(0.0, 0.0, 1.0)
    dot = abs(float(x_axis.x * ref.x + x_axis.y * ref.y + x_axis.z * ref.z))
    if dot > 0.95:
        ref = App.Vector(0.0, 1.0, 0.0)
    z_axis = x_axis.cross(ref)
    z_len = float(getattr(z_axis, 'Length', 0.0))
    if z_len == 0.0:
        ref = App.Vector(1.0, 0.0, 0.0)
        z_axis = x_axis.cross(ref)
        z_len = float(getattr(z_axis, 'Length', 0.0))
    z_axis = App.Vector(z_axis.x / z_len, z_axis.y / z_len, z_axis.z / z_len)
    y_axis = z_axis.cross(x_axis)
    y_len = float(getattr(y_axis, 'Length', 0.0))
    y_axis = App.Vector(y_axis.x / y_len, y_axis.y / y_len, y_axis.z / y_len)
    m = App.Matrix()
    m.A11, m.A21, m.A31 = x_axis.x, x_axis.y, x_axis.z
    m.A12, m.A22, m.A32 = y_axis.x, y_axis.y, y_axis.z
    m.A13, m.A23, m.A33 = z_axis.x, z_axis.y, z_axis.z
    rotation = App.Rotation(m)
    return App.Placement(start_v, rotation), float(getattr(delta, 'Length', 0.0))


def _pick_perpendicular_axis(vec):
    ref = App.Vector(0.0, 0.0, 1.0)
    dot = abs(float(vec.x * ref.x + vec.y * ref.y + vec.z * ref.z))
    if dot > 0.95:
        ref = App.Vector(0.0, 1.0, 0.0)
    perp = vec.cross(ref)
    length = float(getattr(perp, 'Length', 0.0))
    if length == 0.0:
        ref = App.Vector(1.0, 0.0, 0.0)
        perp = vec.cross(ref)
        length = float(getattr(perp, 'Length', 0.0))
    return App.Vector(perp.x / length, perp.y / length, perp.z / length)


def _frame_from_points(points, fallback_context=None):
    if not points:
        raise RuntimeError('Expected at least one point for sketch frame')
    origin = _vec(points[0])
    fallback_x = None
    fallback_y = None
    fallback_z = None
    if isinstance(fallback_context, dict):
        raw_x = fallback_context.get('x_axis')
        raw_y = fallback_context.get('y_axis')
        raw_z = fallback_context.get('z_axis')
        if isinstance(raw_x, (list, tuple)) and len(raw_x) == 3:
            try:
                fallback_x = _normalized_vec(raw_x)
            except Exception:
                fallback_x = None
        if isinstance(raw_y, (list, tuple)) and len(raw_y) == 3:
            try:
                fallback_y = _normalized_vec(raw_y)
            except Exception:
                fallback_y = None
        if isinstance(raw_z, (list, tuple)) and len(raw_z) == 3:
            try:
                fallback_z = _normalized_vec(raw_z)
            except Exception:
                fallback_z = None

    if fallback_x is not None and fallback_y is not None and fallback_z is not None:
        m = App.Matrix()
        m.A11, m.A21, m.A31 = fallback_x.x, fallback_x.y, fallback_x.z
        m.A12, m.A22, m.A32 = fallback_y.x, fallback_y.y, fallback_y.z
        m.A13, m.A23, m.A33 = fallback_z.x, fallback_z.y, fallback_z.z
        placement = App.Placement(origin, App.Rotation(m))
        return placement, origin, fallback_x, fallback_y

    x_axis = None
    for point in points[1:]:
        delta = App.Vector(float(point[0]) - origin.x, float(point[1]) - origin.y, float(point[2]) - origin.z)
        length = float(getattr(delta, 'Length', 0.0))
        if length > 1e-9:
            x_axis = App.Vector(delta.x / length, delta.y / length, delta.z / length)
            break
    if x_axis is None:
        x_axis = fallback_x if fallback_x is not None else App.Vector(1.0, 0.0, 0.0)

    z_axis = None
    for point in points[1:]:
        delta = App.Vector(float(point[0]) - origin.x, float(point[1]) - origin.y, float(point[2]) - origin.z)
        candidate = x_axis.cross(delta)
        length = float(getattr(candidate, 'Length', 0.0))
        if length > 1e-9:
            z_axis = App.Vector(candidate.x / length, candidate.y / length, candidate.z / length)
            break

    if z_axis is None and fallback_z is not None:
        z_axis = fallback_z

    if z_axis is None:
        z_axis = _pick_perpendicular_axis(x_axis)

    y_axis = z_axis.cross(x_axis)
    y_len = float(getattr(y_axis, 'Length', 0.0))
    if y_len == 0.0:
        y_axis = _pick_perpendicular_axis(z_axis)
        y_len = float(getattr(y_axis, 'Length', 0.0))
    y_axis = App.Vector(y_axis.x / y_len, y_axis.y / y_len, y_axis.z / y_len)

    m = App.Matrix()
    m.A11, m.A21, m.A31 = x_axis.x, x_axis.y, x_axis.z
    m.A12, m.A22, m.A32 = y_axis.x, y_axis.y, y_axis.z
    m.A13, m.A23, m.A33 = z_axis.x, z_axis.y, z_axis.z
    placement = App.Placement(origin, App.Rotation(m))
    return placement, origin, x_axis, y_axis


def _local_point_on_frame(point, origin, x_axis, y_axis):
    p = _vec(point)
    dx = p.x - origin.x
    dy = p.y - origin.y
    dz = p.z - origin.z
    return App.Vector(
        dx * x_axis.x + dy * x_axis.y + dz * x_axis.z,
        dx * y_axis.x + dy * y_axis.y + dz * y_axis.z,
        0.0,
    )


def _vec_tuple(vec):
    return (float(vec.x), float(vec.y), float(vec.z))


def _first_edge(obj):
    shape = getattr(obj, 'Shape', None) if hasattr(obj, 'Shape') else obj
    if shape is None or shape.isNull():
        raise RuntimeError(f'Object {getattr(obj, "Name", "<unknown>")} has no valid shape')
    edges = list(getattr(shape, 'Edges', []))
    if not edges:
        raise RuntimeError(f'Object {getattr(obj, "Name", "<unknown>")} has no edges')
    return edges[0]


def _edge_start_point(obj):
    edge = _first_edge(obj)
    return _vec_tuple(edge.Vertexes[0].Point)


def _edge_end_point(obj):
    edge = _first_edge(obj)
    return _vec_tuple(edge.Vertexes[-1].Point)


def _edge_mid_point(obj):
    edge = _first_edge(obj)
    point = edge.valueAt(0.5 * (float(edge.FirstParameter) + float(edge.LastParameter)))
    return _vec_tuple(point)


def _arc_from_edge(obj):
    return Part.Arc(_vec(_edge_start_point(obj)), _vec(_edge_mid_point(obj)), _vec(_edge_end_point(obj)))


def _shape_from_graph_node(node_id):
    value = GRAPH_NODES.get(node_id)
    if value is None:
        raise RuntimeError(f'Missing graph node {node_id!r}')
    if isinstance(value, dict) and 'shape' in value:
        return value['shape']
    if hasattr(value, 'Shape'):
        shape = getattr(value, 'Shape', None)
    else:
        shape = value
    try:
        shape_invalid = shape is None or shape.isNull()
    except Exception:
        shape_invalid = shape is None
    if shape_invalid:
        try:
            doc.recompute()
        except Exception:
            pass
        if hasattr(value, 'Shape'):
            shape = getattr(value, 'Shape', None)
    if shape is None or shape.isNull():
        raise RuntimeError(f'Graph node {node_id!r} has no valid shape')
    return shape


def _subshape_candidates_for_kind(shape, kind):
    kind = str(kind).lower()
    if kind == 'solid':
        return list(getattr(shape, 'Solids', []) or [shape])
    if kind == 'face':
        return list(getattr(shape, 'Faces', []) or [])
    if kind == 'edge':
        return list(getattr(shape, 'Edges', []) or [])
    if kind == 'wire':
        return list(getattr(shape, 'Wires', []) or [])
    if kind == 'vertex':
        return list(getattr(shape, 'Vertexes', []) or [])
    return []


def _point_tuple(point):
    return (float(point.x), float(point.y), float(point.z))


def _candidate_center(candidate):
    center = getattr(candidate, 'CenterOfMass', None)
    if center is not None:
        return _point_tuple(center)
    bound_box = getattr(candidate, 'BoundBox', None)
    if bound_box is not None:
        return (
            (float(bound_box.XMin) + float(bound_box.XMax)) / 2.0,
            (float(bound_box.YMin) + float(bound_box.YMax)) / 2.0,
            (float(bound_box.ZMin) + float(bound_box.ZMax)) / 2.0,
        )
    return None


def _tuple3(value):
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    return None


def _dist3(a, b):
    if a is None or b is None:
        return 1e6
    return math.dist(a, b)


def _bbox_selector_score(candidate, selector):
    bbox = selector.get('bbox') if isinstance(selector, dict) else None
    bound_box = getattr(candidate, 'BoundBox', None)
    if not isinstance(bbox, dict) or bound_box is None:
        return 0.0
    expected_min = _tuple3(bbox.get('min'))
    expected_max = _tuple3(bbox.get('max'))
    if expected_min is None or expected_max is None:
        return 1e6
    actual_min = (float(bound_box.XMin), float(bound_box.YMin), float(bound_box.ZMin))
    actual_max = (float(bound_box.XMax), float(bound_box.YMax), float(bound_box.ZMax))
    return _dist3(actual_min, expected_min) + _dist3(actual_max, expected_max)


def _geo_selector_score(candidate, selector, candidate_index):
    score = _bbox_selector_score(candidate, selector) * 10.0
    kind = str(selector.get('kind', '')).lower()
    if kind == 'edge':
        if 'length' in selector and hasattr(candidate, 'Length'):
            score += abs(float(candidate.Length) - float(selector['length'])) * 10.0
        score += _dist3(_candidate_center(candidate), _tuple3(selector.get('center'))) * 10.0
        vertices = list(getattr(candidate, 'Vertexes', []) or [])
        if len(vertices) >= 2:
            start = _point_tuple(vertices[0].Point)
            end = _point_tuple(vertices[-1].Point)
            expected_start = _tuple3(selector.get('start'))
            expected_end = _tuple3(selector.get('end'))
            if expected_start is not None and expected_end is not None:
                direct = _dist3(start, expected_start) + _dist3(end, expected_end)
                reverse = _dist3(start, expected_end) + _dist3(end, expected_start)
                score += min(direct, reverse)
    elif kind == 'face':
        if 'area' in selector and hasattr(candidate, 'Area'):
            score += abs(float(candidate.Area) - float(selector['area']))
        score += _dist3(_candidate_center(candidate), _tuple3(selector.get('center'))) * 10.0
    elif kind == 'vertex':
        point = getattr(candidate, 'Point', None)
        if point is not None:
            score += _dist3(_point_tuple(point), _tuple3(selector.get('coordinates'))) * 10.0
    elif kind == 'wire':
        edges = list(getattr(candidate, 'Edges', []) or [])
        if 'edge_count' in selector:
            score += abs(len(edges) - int(selector['edge_count'])) * 10.0
    elif kind == 'solid':
        if 'volume' in selector and hasattr(candidate, 'Volume'):
            score += abs(float(candidate.Volume) - float(selector['volume']))
    return score


def _selection_index_for_selector(source_shape, selector):
    kind = str(selector.get('kind') or selector.get('target_kind') or '').lower()
    candidates = _subshape_candidates_for_kind(source_shape, kind)
    if not candidates:
        raise RuntimeError(f'No {kind} candidates available for geo selection')
    ranked = sorted(
        enumerate(candidates),
        key=lambda item: _geo_selector_score(item[1], selector, item[0]),
    )
    best_index, best_candidate = ranked[0]
    best_score = _geo_selector_score(best_candidate, selector, best_index)
    if best_score > 1e-4:
        raise RuntimeError(f'Geo selector did not match a stable {kind} candidate; best score={best_score:.6g}')
    return int(best_index)


def _register_geo_selection_node(*, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    if not inputs:
        raise RuntimeError(f'Selection node {node_id!r} is missing its source input')
    selector = dict(params.get('geo_selector') or {})
    source_node_id = str(inputs[0])
    source_shape = _shape_from_graph_node(source_node_id)
    index = _selection_index_for_selector(source_shape, selector)
    candidates = _subshape_candidates_for_kind(source_shape, selector.get('kind'))
    selected_shape = candidates[index]
    payload = {
        'node_id': node_id,
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
        'output_count': int(output_count),
        'selector': selector,
        'index': int(index),
        'kind': str(selector.get('kind', '')),
        'shape': selected_shape,
    }
    obj = doc.addObject('Part::Feature', f'{str(op)}_{str(node_id)}')
    obj.Shape = selected_shape
    registered = _register_graph_object(
        obj,
        node_id=node_id,
        op=op,
        params=params,
        inputs=inputs,
        tags=tags,
        context=context,
        output_count=output_count,
        param_exprs=param_exprs,
        semantic_delta=semantic_delta,
        topo_delta=topo_delta,
    )
    GRAPH_SELECTIONS[node_id] = payload
    return registered


def _selected_indices_from_nodes(node_ids, fallback_indices, base_shape=None, kind=None):
    indices = []
    for node_id in node_ids or []:
        payload = GRAPH_SELECTIONS.get(str(node_id)) or GRAPH_NODES.get(str(node_id))
        if isinstance(payload, dict) and base_shape is not None:
            selector = dict(payload.get('selector') or payload.get('params', {}).get('geo_selector') or {})
            if kind is not None:
                selector['kind'] = str(kind)
            if selector:
                indices.append(_selection_index_for_selector(base_shape, selector))
                continue
        if isinstance(payload, dict) and 'index' in payload:
            indices.append(int(payload['index']))
    if indices:
        return indices
    return [int(idx) for idx in (fallback_indices or [])]


def _local_line_from_edge(obj, origin, x_axis, y_axis):
    return Part.LineSegment(
        _local_point_on_frame(_edge_start_point(obj), origin, x_axis, y_axis),
        _local_point_on_frame(_edge_end_point(obj), origin, x_axis, y_axis),
    )


def _local_arc_from_edge(obj, origin, x_axis, y_axis):
    return Part.Arc(
        _local_point_on_frame(_edge_start_point(obj), origin, x_axis, y_axis),
        _local_point_on_frame(_edge_mid_point(obj), origin, x_axis, y_axis),
        _local_point_on_frame(_edge_end_point(obj), origin, x_axis, y_axis),
    )


def _angle_arc_axes(normal):
    normal_vec = _normalized_vec(normal)
    ref_vec = App.Vector(1.0, 0.0, 0.0) if abs(normal_vec.z) > 0.9 else App.Vector(0.0, 0.0, 1.0)
    local_x = normal_vec.cross(ref_vec)
    x_len = float(getattr(local_x, 'Length', 0.0))
    if x_len == 0.0:
        ref_vec = App.Vector(0.0, 1.0, 0.0)
        local_x = normal_vec.cross(ref_vec)
        x_len = float(getattr(local_x, 'Length', 0.0))
    local_x = App.Vector(local_x.x / x_len, local_x.y / x_len, local_x.z / x_len)
    local_y = normal_vec.cross(local_x)
    y_len = float(getattr(local_y, 'Length', 0.0))
    local_y = App.Vector(local_y.x / y_len, local_y.y / y_len, local_y.z / y_len)
    return local_x, local_y


def _angle_arc_world_point(circle_center, radius, angle, normal):
    center = _vec(circle_center)
    local_x, local_y = _angle_arc_axes(normal)
    r = float(radius)
    theta = float(angle)
    return App.Vector(
        center.x + r * math.cos(theta) * local_x.x + r * math.sin(theta) * local_y.x,
        center.y + r * math.cos(theta) * local_x.y + r * math.sin(theta) * local_y.y,
        center.z + r * math.cos(theta) * local_x.z + r * math.sin(theta) * local_y.z,
    )


def _angle_arc_curve(circle_center, radius, start_angle, end_angle, normal):
    sa = float(start_angle)
    ea = float(end_angle)
    mid_angle = 0.5 * (sa + ea)
    start_world = _angle_arc_world_point(circle_center, radius, sa, normal)
    mid_world = _angle_arc_world_point(circle_center, radius, mid_angle, normal)
    end_world = _angle_arc_world_point(circle_center, radius, ea, normal)
    return Part.Arc(start_world, mid_world, end_world)


def _local_angle_arc(circle_center, radius, start_angle, end_angle, normal, origin, x_axis, y_axis):
    sa = float(start_angle)
    ea = float(end_angle)
    mid_angle = 0.5 * (sa + ea)
    start_local = _local_point_on_frame(
        _vec_tuple(_angle_arc_world_point(circle_center, radius, sa, normal)),
        origin,
        x_axis,
        y_axis,
    )
    mid_local = _local_point_on_frame(
        _vec_tuple(_angle_arc_world_point(circle_center, radius, mid_angle, normal)),
        origin,
        x_axis,
        y_axis,
    )
    end_local = _local_point_on_frame(
        _vec_tuple(_angle_arc_world_point(circle_center, radius, ea, normal)),
        origin,
        x_axis,
        y_axis,
    )
    return Part.Arc(start_local, mid_local, end_local)


def _bspline_curve_from_params(params, transform_point=None):
    poles = []
    for point in params.get('control_points') or []:
        point3 = tuple(point) + (0.0,) if len(tuple(point)) == 2 else tuple(point)
        pole = transform_point(point3) if transform_point is not None else _vec(point3)
        poles.append(pole)
    if not poles:
        raise RuntimeError('B-spline has no control points')
    mults = tuple(int(value) for value in (params.get('multiplicities') or []))
    knots = tuple(float(value) for value in (params.get('knots') or []))
    degree = int(params.get('degree', 3))
    periodic = bool(params.get('periodic', False))
    weights = params.get('weights')
    curve = Part.BSplineCurve()
    if weights is None:
        curve.buildFromPolesMultsKnots(poles, mults, knots, periodic, degree)
    else:
        curve.buildFromPolesMultsKnots(poles, mults, knots, periodic, degree, tuple(float(value) for value in weights))
    return curve


def _wire_shape_from_edge_objects(node_ids):
    shapes = []
    for node_id in node_ids:
        shape = _shape_from_graph_node(node_id)
        shapes.append(shape)
    return Part.Wire(shapes)


def _shape_is_null(shape):
    try:
        return shape is None or shape.isNull()
    except Exception:
        return shape is None


def _spine_object(node_id):
    node_id = str(node_id)
    cached = GRAPH_SPINE_OBJECTS.get(node_id)
    if cached is not None:
        return cached
    obj = GRAPH_NODES[node_id]
    try:
        shape = getattr(obj, 'Shape', None)
    except Exception:
        shape = None
    if not _shape_is_null(shape):
        return obj
    meta = GRAPH_METADATA.get(node_id, {})
    if str(meta.get('op', '')) == 'make_wire_from_edges_rwire':
        edge_ids = list(meta.get('inputs') or [])
        if edge_ids:
            fallback = doc.addObject('Part::Feature', f'make_spine_wire_{node_id}')
            fallback.Shape = _wire_shape_from_edge_objects(edge_ids)
            _set_visibility(fallback, False)
            GRAPH_SPINE_OBJECTS[node_id] = fallback
            return fallback
    return obj


def _build_face_from_source(source_obj, name):
    face_obj = doc.addObject('Part::Face', name)
    face_obj.Sources = [source_obj]
    return face_obj


def _make_metadata_note(name, title, payload):
    obj = doc.addObject('App::FeaturePython', name)
    _ensure_string_property(obj, 'Title')
    _ensure_string_property(obj, 'Payload')
    obj.Title = title
    obj.Payload = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    return obj


def _register_ir_node(name, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    return _register_graph_metadata_only(
        node_id=node_id,
        op=op,
        params=params,
        inputs=inputs,
        tags=tags,
        context=context,
        output_count=output_count,
        param_exprs=param_exprs,
        semantic_delta=semantic_delta,
        topo_delta=topo_delta,
    )


def _placement_from_frame(origin, x_axis, y_axis, z_axis):
    m = App.Matrix()
    m.A11, m.A21, m.A31 = x_axis.x, x_axis.y, x_axis.z
    m.A12, m.A22, m.A32 = y_axis.x, y_axis.y, y_axis.z
    m.A13, m.A23, m.A33 = z_axis.x, z_axis.y, z_axis.z
    return App.Placement(origin, App.Rotation(m))


def _sketch_plane_frame(plane):
    if isinstance(plane, str):
        token = plane.upper()
        if token == 'XY':
            origin = App.Vector(0.0, 0.0, 0.0)
            x_axis = App.Vector(1.0, 0.0, 0.0)
            y_axis = App.Vector(0.0, 1.0, 0.0)
            z_axis = App.Vector(0.0, 0.0, 1.0)
            return origin, x_axis, y_axis, z_axis
        if token == 'XZ':
            origin = App.Vector(0.0, 0.0, 0.0)
            x_axis = App.Vector(1.0, 0.0, 0.0)
            y_axis = App.Vector(0.0, 0.0, 1.0)
            z_axis = App.Vector(0.0, -1.0, 0.0)
            return origin, x_axis, y_axis, z_axis
        if token == 'YZ':
            origin = App.Vector(0.0, 0.0, 0.0)
            x_axis = App.Vector(0.0, 1.0, 0.0)
            y_axis = App.Vector(0.0, 0.0, 1.0)
            z_axis = App.Vector(1.0, 0.0, 0.0)
            return origin, x_axis, y_axis, z_axis
    if isinstance(plane, dict):
        origin = _vec(plane.get('origin', (0.0, 0.0, 0.0)))
        x_axis = _normalized_vec(plane.get('x_axis', (1.0, 0.0, 0.0)))
        y_axis = _normalized_vec(plane.get('y_axis', (0.0, 1.0, 0.0)))
        z_axis = x_axis.cross(y_axis)
        z_len = float(getattr(z_axis, 'Length', 0.0))
        if z_len == 0.0:
            raise RuntimeError('Sketch plane x_axis and y_axis must not be parallel')
        z_axis = App.Vector(z_axis.x / z_len, z_axis.y / z_len, z_axis.z / z_len)
        y_axis = z_axis.cross(x_axis)
        y_len = float(getattr(y_axis, 'Length', 0.0))
        y_axis = App.Vector(y_axis.x / y_len, y_axis.y / y_len, y_axis.z / y_len)
        return origin, x_axis, y_axis, z_axis
    raise RuntimeError(f'Unsupported sketch plane payload: {plane!r}')


def _sketch_entity_maps(sketch_payload):
    entities = list(sketch_payload.get('entities') or []) if isinstance(sketch_payload, dict) else []
    return entities, {str(entity.get('id')): entity for entity in entities if isinstance(entity, dict) and entity.get('id') is not None}


def _sketch_solved_point(point_id, sketch_payload, solve_snapshot):
    solved = (solve_snapshot or {}).get('solved_points', {}) if isinstance(solve_snapshot, dict) else {}
    if point_id in solved:
        point = solved[point_id]
        return (float(point[0]), float(point[1]))
    _entities, by_id = _sketch_entity_maps(sketch_payload)
    entity = by_id.get(str(point_id))
    if isinstance(entity, dict) and entity.get('kind') == 'point':
        return (float(entity.get('x', 0.0)), float(entity.get('y', 0.0)))
    raise RuntimeError(f'Missing solved sketch point {point_id!r}')


def _sketch_solved_radius(entity_id, entity, solve_snapshot):
    key = f'circle:{entity_id}:radius'
    scalars = (solve_snapshot or {}).get('solved_scalars', {}) if isinstance(solve_snapshot, dict) else {}
    if key in scalars:
        return float(scalars[key])
    return float(entity.get('radius', 0.0))


def _sketch_profile_entity_ids(params, sketch_payload):
    promotion_map = params.get('promotion_map') if isinstance(params, dict) else None
    if isinstance(promotion_map, dict):
        edges = promotion_map.get('edges') or []
        ids = [str(edge.get('entity_id')) for edge in edges if isinstance(edge, dict) and edge.get('entity_id') is not None]
        if ids:
            return ids
    entities, _by_id = _sketch_entity_maps(sketch_payload)
    return [
        str(entity.get('id'))
        for entity in entities
        if entity.get('kind') in {'line', 'circle'} and not bool(entity.get('construction', False))
    ]


def _sketch_world_point(point_id, sketch_payload, solve_snapshot, origin, x_axis, y_axis):
    x, y = _sketch_solved_point(point_id, sketch_payload, solve_snapshot)
    return App.Vector(
        origin.x + x * x_axis.x + y * y_axis.x,
        origin.y + x * x_axis.y + y * y_axis.y,
        origin.z + x * x_axis.z + y * y_axis.z,
    )


def _sketch_local_point(point_id, sketch_payload, solve_snapshot):
    x, y = _sketch_solved_point(point_id, sketch_payload, solve_snapshot)
    return App.Vector(x, y, 0.0)


def _sketch_wire_shape_from_promotion(params):
    sketch_payload = params.get('sketch') or {}
    solve_snapshot = params.get('solve_snapshot') or {}
    origin, x_axis, y_axis, z_axis = _sketch_plane_frame(sketch_payload.get('plane', 'XY'))
    _entities, by_id = _sketch_entity_maps(sketch_payload)
    edge_shapes = []
    for entity_id in _sketch_profile_entity_ids(params, sketch_payload):
        entity = by_id.get(str(entity_id))
        if not isinstance(entity, dict):
            continue
        kind = str(entity.get('kind'))
        if kind == 'line':
            start = _sketch_world_point(str(entity.get('start')), sketch_payload, solve_snapshot, origin, x_axis, y_axis)
            end = _sketch_world_point(str(entity.get('end')), sketch_payload, solve_snapshot, origin, x_axis, y_axis)
            edge_shapes.append(Part.LineSegment(start, end).toShape())
        elif kind == 'circle':
            center = _sketch_world_point(str(entity.get('center')), sketch_payload, solve_snapshot, origin, x_axis, y_axis)
            edge_shapes.append(Part.Circle(center, z_axis, _sketch_solved_radius(str(entity_id), entity, solve_snapshot)).toShape())
    if not edge_shapes:
        raise RuntimeError('Sketch promotion has no profile geometry to materialize')
    return Part.Wire(edge_shapes)


def _sketch_entity_expr(param_exprs, entity_index, *path):
    expr_meta = _nested_expr_ref(param_exprs or {}, 'sketch', 'entities', int(entity_index))
    if expr_meta is None:
        return None
    return _nested_expr_ref(expr_meta, *path)


def _sketch_constraint_value_expr(param_exprs, constraint_index):
    return _nested_expr_ref(param_exprs or {}, 'sketch', 'constraints', int(constraint_index), 'value')


def _sketch_constraint_status_append(status, source, mapped, **payload):
    entry = {'id': source.get('id') if isinstance(source, dict) else None, 'kind': source.get('kind') if isinstance(source, dict) else None}
    entry.update(payload)
    status['mapped' if mapped else 'skipped'].append(entry)


def _sketch_constraint_priority(item):
    _index, constraint = item
    kind = str(constraint.get('kind')) if isinstance(constraint, dict) else ''
    priorities = {
        'coincident': 0,
        'connect': 0,
        'point_on': 1,
        'fix': 2,
        'horizontal': 3,
        'vertical': 3,
        'distance': 4,
        'distance_x': 4,
        'distance_y': 4,
        'length': 4,
        'radius': 4,
        'diameter': 4,
        'angle': 4,
        'parallel': 5,
        'perpendicular': 5,
        'collinear': 5,
        'tangent': 5,
        'concentric': 5,
        'equal_length': 5,
        'equal_radius': 5,
        'midpoint': 6,
        'symmetric': 6,
    }
    return priorities.get(kind, 9), int(_index)


def _validate_sketch_constraint(sketch_obj, idx):
    try:
        result = sketch_obj.solve()
    except Exception as exc:
        return False, f'FreeCAD Sketcher solver raised {exc!r}'
    try:
        result_int = int(result)
    except Exception:
        return True, ''
    if result_int < 0:
        return False, f'FreeCAD Sketcher solver rejected constraint with result {result_int}'
    return True, ''


def _remove_sketch_constraint(sketch_obj, idx):
    try:
        if hasattr(sketch_obj, 'setExpression'):
            sketch_obj.setExpression(f'Constraints[{int(idx)}]', None)
    except Exception:
        pass
    try:
        sketch_obj.delConstraint(int(idx))
    except Exception:
        pass


def _safe_add_sketch_constraint(sketch_obj, status, source, freecad_kind, *args, expr_ref=None, synthetic=False):
    if Sketcher is None:
        _sketch_constraint_status_append(status, source, False, freecad_kind=freecad_kind, reason='Sketcher module is unavailable', synthetic=bool(synthetic))
        return None
    try:
        idx = sketch_obj.addConstraint(Sketcher.Constraint(freecad_kind, *args))
    except Exception as exc:
        _sketch_constraint_status_append(status, source, False, freecad_kind=freecad_kind, reason=str(exc), synthetic=bool(synthetic))
        return None
    if expr_ref is not None:
        _bind_expression(sketch_obj, f'Constraints[{int(idx)}]', expr_ref)
    ok, reason = _validate_sketch_constraint(sketch_obj, idx)
    if not ok:
        _remove_sketch_constraint(sketch_obj, idx)
        _sketch_constraint_status_append(status, source, False, freecad_kind=freecad_kind, reason=reason, synthetic=bool(synthetic))
        return None
    serializable_args = [int(arg) if isinstance(arg, int) and not isinstance(arg, bool) else arg for arg in args]
    _sketch_constraint_status_append(status, source, True, freecad_kind=freecad_kind, index=int(idx), args=serializable_args, synthetic=bool(synthetic))
    return int(idx)


def _target_point_id(target, by_id):
    if not isinstance(target, dict):
        return None
    entity_id = str(target.get('entity_id'))
    subentity = str(target.get('subentity', 'geometry'))
    entity = by_id.get(entity_id)
    if not isinstance(entity, dict):
        return None
    kind = str(entity.get('kind'))
    if kind == 'point':
        return entity_id
    if kind == 'line' and subentity in {'start', 'end'}:
        return str(entity.get(subentity))
    if kind == 'circle' and subentity == 'center':
        return str(entity.get('center'))
    return None


def _target_point_ref(target, by_id, point_refs):
    point_id = _target_point_id(target, by_id)
    if point_id is None:
        return None
    refs = point_refs.get(point_id) or []
    return refs[0] if refs else None


def _target_entity_ref(target, by_id, geom_by_entity):
    if not isinstance(target, dict):
        return None
    entity_id = str(target.get('entity_id'))
    entity = by_id.get(entity_id)
    if not isinstance(entity, dict):
        return None
    geom_index = geom_by_entity.get(entity_id)
    if geom_index is None:
        return None
    return int(geom_index), str(entity.get('kind'))


def _fix_point_constraint(sketch_obj, status, source, point_ref, x_value, y_value, x_expr=None, y_expr=None):
    if point_ref is None:
        _sketch_constraint_status_append(status, source, False, reason='Target point is not represented by safe Sketcher geometry')
        return
    geom_index, pos = point_ref
    _safe_add_sketch_constraint(sketch_obj, status, source, 'DistanceX', int(geom_index), int(pos), float(x_value), expr_ref=x_expr)
    _safe_add_sketch_constraint(sketch_obj, status, source, 'DistanceY', int(geom_index), int(pos), float(y_value), expr_ref=y_expr)


def _materialize_sketch_constraints(sketch_obj, sketch_payload, params, param_exprs, geom_by_entity, point_refs):
    status = {'mapped': [], 'skipped': []}
    entities, by_id = _sketch_entity_maps(sketch_payload)
    entity_index_by_id = {str(entity.get('id')): idx for idx, entity in enumerate(entities)}
    solve_snapshot = params.get('solve_snapshot') or {}

    for point_id, refs in sorted(point_refs.items()):
        if len(refs) < 2:
            continue
        first_geom, first_pos = refs[0]
        for geom_index, pos in refs[1:]:
            _safe_add_sketch_constraint(
                sketch_obj,
                status,
                {'id': f'point_identity:{point_id}', 'kind': 'coincident'},
                'Coincident',
                int(first_geom),
                int(first_pos),
                int(geom_index),
                int(pos),
                synthetic=True,
            )

    constraints = list(sketch_payload.get('constraints') or []) if isinstance(sketch_payload, dict) else []
    for constraint_index, constraint in sorted(enumerate(constraints), key=_sketch_constraint_priority):
        if not isinstance(constraint, dict):
            continue
        kind = str(constraint.get('kind'))
        targets = list(constraint.get('targets') or [])
        value = constraint.get('value')
        value_expr = _sketch_constraint_value_expr(param_exprs, constraint_index)

        if kind in {'coincident', 'connect'} and len(targets) == 2:
            a = _target_point_ref(targets[0], by_id, point_refs)
            b = _target_point_ref(targets[1], by_id, point_refs)
            if a is None or b is None:
                _sketch_constraint_status_append(status, constraint, False, reason='Coincident target is not represented by safe Sketcher geometry')
                continue
            _safe_add_sketch_constraint(sketch_obj, status, constraint, 'Coincident', int(a[0]), int(a[1]), int(b[0]), int(b[1]))
            continue

        if kind == 'point_on' and len(targets) == 2:
            point_ref = _target_point_ref(targets[0], by_id, point_refs)
            entity_ref = _target_entity_ref(targets[1], by_id, geom_by_entity)
            if point_ref is None or entity_ref is None:
                _sketch_constraint_status_append(status, constraint, False, reason='Point-on target is not represented by safe Sketcher geometry')
                continue
            _safe_add_sketch_constraint(sketch_obj, status, constraint, 'PointOnObject', int(point_ref[0]), int(point_ref[1]), int(entity_ref[0]))
            continue

        if kind in {'horizontal', 'vertical'} and len(targets) == 1:
            entity_ref = _target_entity_ref(targets[0], by_id, geom_by_entity)
            if entity_ref is None or entity_ref[1] != 'line':
                _sketch_constraint_status_append(status, constraint, False, reason=f'{kind} requires a materialized line')
                continue
            _safe_add_sketch_constraint(sketch_obj, status, constraint, 'Horizontal' if kind == 'horizontal' else 'Vertical', int(entity_ref[0]))
            continue

        if kind in {'parallel', 'perpendicular', 'equal_length', 'angle'} and len(targets) == 2:
            a = _target_entity_ref(targets[0], by_id, geom_by_entity)
            b = _target_entity_ref(targets[1], by_id, geom_by_entity)
            if a is None or b is None or a[1] != 'line' or b[1] != 'line':
                _sketch_constraint_status_append(status, constraint, False, reason=f'{kind} requires two materialized lines')
                continue
            if kind == 'parallel':
                _safe_add_sketch_constraint(sketch_obj, status, constraint, 'Parallel', int(a[0]), int(b[0]))
            elif kind == 'perpendicular':
                _safe_add_sketch_constraint(sketch_obj, status, constraint, 'Perpendicular', int(a[0]), int(b[0]))
            elif kind == 'equal_length':
                _safe_add_sketch_constraint(sketch_obj, status, constraint, 'Equal', int(a[0]), int(b[0]))
            else:
                _safe_add_sketch_constraint(sketch_obj, status, constraint, 'Angle', int(a[0]), int(b[0]), float(value), expr_ref=value_expr)
            continue

        if kind == 'collinear' and len(targets) == 2:
            a = _target_entity_ref(targets[0], by_id, geom_by_entity)
            b_target = targets[1]
            b = _target_entity_ref(b_target, by_id, geom_by_entity)
            if a is None or b is None or a[1] != 'line' or b[1] != 'line':
                _sketch_constraint_status_append(status, constraint, False, reason='collinear requires two materialized lines')
                continue
            _safe_add_sketch_constraint(sketch_obj, status, constraint, 'Parallel', int(a[0]), int(b[0]))
            b_entity = by_id.get(str(b_target.get('entity_id')))
            if isinstance(b_entity, dict):
                for point_id in (str(b_entity.get('start')), str(b_entity.get('end'))):
                    refs = point_refs.get(point_id) or []
                    if refs:
                        _safe_add_sketch_constraint(sketch_obj, status, constraint, 'PointOnObject', int(refs[0][0]), int(refs[0][1]), int(a[0]))
            continue

        if kind in {'equal_radius', 'concentric'} and len(targets) == 2:
            a = _target_entity_ref(targets[0], by_id, geom_by_entity)
            b = _target_entity_ref(targets[1], by_id, geom_by_entity)
            if a is None or b is None or a[1] != 'circle' or b[1] != 'circle':
                _sketch_constraint_status_append(status, constraint, False, reason=f'{kind} requires two materialized circles')
                continue
            if kind == 'equal_radius':
                _safe_add_sketch_constraint(sketch_obj, status, constraint, 'Equal', int(a[0]), int(b[0]))
            else:
                _safe_add_sketch_constraint(sketch_obj, status, constraint, 'Coincident', int(a[0]), 3, int(b[0]), 3)
            continue

        if kind == 'tangent' and len(targets) == 2:
            a = _target_entity_ref(targets[0], by_id, geom_by_entity)
            b = _target_entity_ref(targets[1], by_id, geom_by_entity)
            if a is None or b is None or a[1] not in {'line', 'circle'} or b[1] not in {'line', 'circle'}:
                _sketch_constraint_status_append(status, constraint, False, reason='tangent requires two materialized line/circle entities')
                continue
            _safe_add_sketch_constraint(sketch_obj, status, constraint, 'Tangent', int(a[0]), int(b[0]))
            continue

        if kind in {'distance', 'distance_x', 'distance_y'} and len(targets) == 2:
            a = _target_point_ref(targets[0], by_id, point_refs)
            b = _target_point_ref(targets[1], by_id, point_refs)
            if a is None or b is None:
                _sketch_constraint_status_append(status, constraint, False, reason=f'{kind} target is not represented by safe Sketcher geometry')
                continue
            fc_kind = {'distance': 'Distance', 'distance_x': 'DistanceX', 'distance_y': 'DistanceY'}[kind]
            _safe_add_sketch_constraint(sketch_obj, status, constraint, fc_kind, int(a[0]), int(a[1]), int(b[0]), int(b[1]), float(value), expr_ref=value_expr)
            continue

        if kind == 'length' and len(targets) == 1:
            entity_ref = _target_entity_ref(targets[0], by_id, geom_by_entity)
            if entity_ref is None or entity_ref[1] != 'line':
                _sketch_constraint_status_append(status, constraint, False, reason='length requires a materialized line')
                continue
            _safe_add_sketch_constraint(sketch_obj, status, constraint, 'Distance', int(entity_ref[0]), float(value), expr_ref=value_expr)
            continue

        if kind in {'radius', 'diameter'} and len(targets) == 1:
            entity_ref = _target_entity_ref(targets[0], by_id, geom_by_entity)
            if entity_ref is None or entity_ref[1] != 'circle':
                _sketch_constraint_status_append(status, constraint, False, reason=f'{kind} requires a materialized circle')
                continue
            _safe_add_sketch_constraint(sketch_obj, status, constraint, 'Radius' if kind == 'radius' else 'Diameter', int(entity_ref[0]), float(value), expr_ref=value_expr)
            continue

        if kind == 'fix' and len(targets) == 1:
            target = targets[0]
            entity_id = str(target.get('entity_id')) if isinstance(target, dict) else ''
            entity = by_id.get(entity_id)
            if not isinstance(entity, dict):
                _sketch_constraint_status_append(status, constraint, False, reason='fix target entity is missing')
                continue
            entity_kind = str(entity.get('kind'))
            if entity_kind == 'point':
                point_id = entity_id
                x_value, y_value = _sketch_solved_point(point_id, sketch_payload, solve_snapshot)
                expr_meta = _sketch_entity_expr(param_exprs, entity_index_by_id[point_id])
                _fix_point_constraint(sketch_obj, status, constraint, _target_point_ref(target, by_id, point_refs), x_value, y_value, _nested_expr_ref(expr_meta, 'x'), _nested_expr_ref(expr_meta, 'y'))
            elif entity_kind == 'line':
                for point_key in ('start', 'end'):
                    point_id = str(entity.get(point_key))
                    x_value, y_value = _sketch_solved_point(point_id, sketch_payload, solve_snapshot)
                    point_entity_index = entity_index_by_id.get(point_id)
                    expr_meta = _sketch_entity_expr(param_exprs, point_entity_index) if point_entity_index is not None else None
                    refs = point_refs.get(point_id) or []
                    _fix_point_constraint(sketch_obj, status, constraint, refs[0] if refs else None, x_value, y_value, _nested_expr_ref(expr_meta, 'x'), _nested_expr_ref(expr_meta, 'y'))
            elif entity_kind == 'circle':
                center_id = str(entity.get('center'))
                x_value, y_value = _sketch_solved_point(center_id, sketch_payload, solve_snapshot)
                center_entity_index = entity_index_by_id.get(center_id)
                expr_meta = _sketch_entity_expr(param_exprs, center_entity_index) if center_entity_index is not None else None
                refs = point_refs.get(center_id) or []
                _fix_point_constraint(sketch_obj, status, constraint, refs[0] if refs else None, x_value, y_value, _nested_expr_ref(expr_meta, 'x'), _nested_expr_ref(expr_meta, 'y'))
                entity_ref = _target_entity_ref(target, by_id, geom_by_entity)
                if entity_ref is not None:
                    circle_index = entity_index_by_id.get(entity_id)
                    radius_expr = _nested_expr_ref(_sketch_entity_expr(param_exprs, circle_index) if circle_index is not None else None, 'radius')
                    _safe_add_sketch_constraint(sketch_obj, status, constraint, 'Radius', int(entity_ref[0]), _sketch_solved_radius(entity_id, entity, solve_snapshot), expr_ref=radius_expr)
            else:
                _sketch_constraint_status_append(status, constraint, False, reason=f'Cannot fix unsupported sketch entity kind {entity_kind!r}')
            continue

        if kind in {'midpoint', 'symmetric'}:
            _sketch_constraint_status_append(status, constraint, False, reason=f'{kind} has no crash-safe FreeCAD Sketcher mapping in this translator')
            continue

        _sketch_constraint_status_append(status, constraint, False, reason=f'Unsupported sketch constraint kind {kind!r}')
    return status


def _attach_sketch_promotion_metadata(obj, params, constraint_status):
    _ensure_string_property(obj, 'SimpleCADSketch')
    _ensure_string_property(obj, 'SimpleCADSketchSolve')
    _ensure_string_property(obj, 'SimpleCADSketchPromotion')
    _ensure_string_property(obj, 'SimpleCADSketchConstraints')
    obj.SimpleCADSketch = json.dumps(params.get('sketch') or {}, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADSketchSolve = json.dumps(params.get('solve_snapshot') or {}, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADSketchPromotion = json.dumps(params.get('promotion_map') or {}, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADSketchConstraints = json.dumps(constraint_status or {}, ensure_ascii=True, sort_keys=True)


def _make_sketch_promotion_object(name, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    sketch_payload = params.get('sketch') or {}
    solve_snapshot = params.get('solve_snapshot') or {}
    if Sketcher is None:
        obj = doc.addObject('Part::Feature', name)
        obj.Shape = _sketch_wire_shape_from_promotion(params)
        constraint_status = {'mapped': [], 'skipped': [{'reason': 'Sketcher module is unavailable'}]}
        _attach_sketch_promotion_metadata(obj, params, constraint_status)
        return _register_graph_object(
            obj,
            node_id=node_id,
            op=op,
            params=params,
            inputs=inputs,
            tags=tags,
            context=context,
            output_count=output_count,
            param_exprs=param_exprs,
            semantic_delta=semantic_delta,
            topo_delta=topo_delta,
        )

    obj = doc.addObject('Sketcher::SketchObject', name)
    origin, x_axis, y_axis, z_axis = _sketch_plane_frame(sketch_payload.get('plane', 'XY'))
    obj.Placement = _placement_from_frame(origin, x_axis, y_axis, z_axis)
    profile_ids = set(_sketch_profile_entity_ids(params, sketch_payload))
    entities, _by_id = _sketch_entity_maps(sketch_payload)
    geom_by_entity = {}
    point_refs = {}

    for entity in entities:
        entity_id = str(entity.get('id'))
        kind = str(entity.get('kind'))
        construction = bool(entity.get('construction', False)) or (kind in {'line', 'circle'} and entity_id not in profile_ids)
        if kind == 'line':
            start_id = str(entity.get('start'))
            end_id = str(entity.get('end'))
            start = _sketch_local_point(start_id, sketch_payload, solve_snapshot)
            end = _sketch_local_point(end_id, sketch_payload, solve_snapshot)
            geom_index = int(obj.addGeometry(Part.LineSegment(start, end), construction))
            geom_by_entity[entity_id] = geom_index
            point_refs.setdefault(start_id, []).append((geom_index, 1))
            point_refs.setdefault(end_id, []).append((geom_index, 2))
        elif kind == 'circle':
            center_id = str(entity.get('center'))
            center = _sketch_local_point(center_id, sketch_payload, solve_snapshot)
            radius = _sketch_solved_radius(entity_id, entity, solve_snapshot)
            geom_index = int(obj.addGeometry(Part.Circle(center, App.Vector(0.0, 0.0, 1.0), radius), construction))
            geom_by_entity[entity_id] = geom_index
            point_refs.setdefault(center_id, []).append((geom_index, 3))

    if not geom_by_entity:
        raise RuntimeError('Sketch promotion contains no materialized line or circle geometry')
    constraint_status = _materialize_sketch_constraints(obj, sketch_payload, params, param_exprs or {}, geom_by_entity, point_refs)
    try:
        obj.solve()
    except Exception:
        pass
    try:
        doc.recompute()
    except Exception:
        pass
    _attach_sketch_promotion_metadata(obj, params, constraint_status)
    _attach_simplecad_metadata(
        obj,
        node_id=node_id,
        op=op,
        params=params,
        inputs=inputs,
        tags=tags,
        context=context,
        output_count=output_count,
        param_exprs=param_exprs,
        semantic_delta=semantic_delta,
        topo_delta=topo_delta,
    )
    SKETCH_REGISTRY.append({'node_id': node_id, 'op': op, 'object': obj.Name, 'constraint_status': constraint_status})
    registered = _register_graph_object(
        obj,
        node_id=node_id,
        op=op,
        params=params,
        inputs=inputs,
        tags=tags,
        context=context,
        output_count=output_count,
        param_exprs=param_exprs,
        semantic_delta=semantic_delta,
        topo_delta=topo_delta,
    )
    return registered


def _sanitize_expr_alias(expr_id, prefix='expr'):
    alias = ''.join(ch if str(ch).isalnum() else '_' for ch in str(expr_id)).strip('_')
    if not alias:
        alias = prefix
    if alias[0].isdigit():
        alias = prefix + '_' + alias
    return alias[:64]


def _expr_alias(expr_id):
    alias = EXPR_ALIAS_BY_ID.get(expr_id)
    if alias:
        return alias
    return _sanitize_expr_alias(expr_id)


def _resolve_expr_ref(expr_ref):
    if not isinstance(expr_ref, dict):
        return None
    expr_id = expr_ref.get('expr_id')
    if not expr_id or 'expr_sheet' not in globals() or expr_sheet is None:
        return None
    alias = _expr_alias(expr_id)
    try:
        return float(expr_sheet.get(alias))
    except Exception:
        cell = EXPR_CELL_BY_ID.get(expr_id)
        if not cell:
            return None
        try:
            return float(expr_sheet.get(cell))
        except Exception:
            return None


def _expr_ref_to_freecad_expr(expr_ref):
    if not isinstance(expr_ref, dict):
        return None
    expr_id = expr_ref.get('expr_id')
    if not expr_id or 'expr_sheet' not in globals() or expr_sheet is None:
        return None
    if expr_id not in EXPR_CELL_BY_ID:
        return None
    return f"<<SimpleCADExpressions>>.{_expr_alias(expr_id)}"


def _nested_expr_ref(expr_meta, *path):
    value = expr_meta
    for key in path:
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and isinstance(key, int) and 0 <= key < len(value):
            value = value[key]
        else:
            return None
    return value


def _bind_expression(obj, prop_name, expr_ref):
    if isinstance(expr_ref, str):
        expr = expr_ref
    else:
        expr = _expr_ref_to_freecad_expr(expr_ref)
    if not expr or not hasattr(obj, 'setExpression'):
        return False
    try:
        obj.setExpression(prop_name, expr)
        return True
    except Exception:
        return False


def _bind_expression_from_param(obj, prop_name, param_exprs, *path):
    return _bind_expression(obj, prop_name, _nested_expr_ref(param_exprs, *path))


def _apply_op_expression_bindings(obj, op_name, param_exprs):
    for prop_name, path in OP_EXPRESSION_BINDINGS.get(str(op_name), ()):
        _bind_expression_from_param(obj, prop_name, param_exprs, *path)


def _apply_sketch_expression_bindings(obj, bindings):
    for prop_name, expr_ref in bindings or []:
        _bind_expression(obj, prop_name, expr_ref)


def _expr_formula_from_ref(expr_ref):
    expr = _expr_ref_to_freecad_expr(expr_ref)
    return expr if expr else None


def _formula_nested_value(params, param_exprs, *path):
    expr = _expr_formula_from_ref(_nested_expr_ref(param_exprs, *path))
    if expr is not None:
        return expr
    try:
        value = params
        for key in path:
            value = value[key]
        return repr(float(value))
    except Exception:
        return None


def _formula_scale(expr, coeff):
    coeff_value = float(coeff)
    if abs(coeff_value) <= 1e-12:
        return None
    if abs(coeff_value - 1.0) <= 1e-12:
        return expr
    if abs(coeff_value + 1.0) <= 1e-12:
        return f'-({expr})'
    return f'({expr}) * ({repr(coeff_value)})'


def _formula_mul(left, right):
    if left is None or right is None:
        return None
    return f'({left}) * ({right})'


def _formula_join_terms(*terms):
    filtered = [term for term in terms if term is not None]
    if not filtered:
        return None
    return ' + '.join(filtered)


def _formula_centered(expr, offset):
    offset_value = float(offset)
    if abs(offset_value) <= 1e-12:
        return expr
    return f'({expr}) - ({repr(offset_value)})'


def _formula_square(expr):
    return f'pow(({expr}); 2)'


def _formula_cos_radians(expr):
    return f'cos(({expr}) * 180 / pi)'


def _formula_sin_radians(expr):
    return f'sin(({expr}) * 180 / pi)'


def _local_point_component_formula(params, param_exprs, point_path, origin, axis_vec):
    path = tuple(point_path) if isinstance(point_path, (list, tuple)) else (point_path,)
    offsets = (float(origin.x), float(origin.y), float(origin.z))
    axis = (float(axis_vec.x), float(axis_vec.y), float(axis_vec.z))
    terms = []
    for idx, (offset, coeff) in enumerate(zip(offsets, axis)):
        value = _formula_nested_value(params, param_exprs, *(path + (idx,)))
        if value is None:
            return None
        term = _formula_scale(_formula_centered(value, offset), coeff)
        if term is not None:
            terms.append(term)
    if not terms:
        return '0.0'
    return ' + '.join(terms)


def _formula_value(params, param_exprs, key, index):
    return _formula_nested_value(params, param_exprs, key, index)


def _line_length_formula(params, param_exprs):
    sx = _formula_value(params, param_exprs, 'start', 0)
    sy = _formula_value(params, param_exprs, 'start', 1)
    sz = _formula_value(params, param_exprs, 'start', 2)
    ex = _formula_value(params, param_exprs, 'end', 0)
    ey = _formula_value(params, param_exprs, 'end', 1)
    ez = _formula_value(params, param_exprs, 'end', 2)
    terms = []
    for a, b in ((ex, sx), (ey, sy), (ez, sz)):
        if a is None or b is None:
            return None
        terms.append(f"pow(({a}) - ({b}); 2)")
    return f"sqrt({' + '.join(terms)})"


def _build_line_sketch_bindings(param_exprs, geom_index=0, use_local_line=False):
    bindings = []
    for point_name, point_index in (("start", 1), ("end", 2)):
        expr_ref = _nested_expr_ref(param_exprs, point_name)
        if not isinstance(expr_ref, list):
            continue
        for axis_name, axis_index in (("x", 0), ("y", 1), ("z", 2)):
            axis_expr = _nested_expr_ref(param_exprs, point_name, axis_index)
            if axis_expr is None:
                continue
            prop = f"Geometry[{int(geom_index)}].{'StartPoint' if point_name == 'start' else 'EndPoint'}.{axis_name}"
            if use_local_line and axis_name in {'x', 'y', 'z'}:
                continue
            bindings.append((prop, axis_expr))
    return bindings


def _build_circle_sketch_bindings(param_exprs, geom_index=0, local=False):
    bindings = []
    for axis_name, axis_index in (("x", 0), ("y", 1), ("z", 2)):
        axis_expr = _nested_expr_ref(param_exprs, 'center', axis_index)
        if axis_expr is None:
            continue
        if local and axis_name == 'z':
            continue
        bindings.append((f"Geometry[{int(geom_index)}].Center.{axis_name}", axis_expr))
    radius_expr = _nested_expr_ref(param_exprs, 'radius')
    if radius_expr is not None:
        bindings.append((f"Geometry[{int(geom_index)}].Radius", radius_expr))
    return bindings


def _build_local_point_sketch_bindings(params, param_exprs, point_path, prop_prefix, geom_index=0, origin=None, x_axis=None, y_axis=None):
    bindings = []
    if origin is None or x_axis is None or y_axis is None:
        return bindings
    x_expr = _local_point_component_formula(params, param_exprs, point_path, origin, x_axis)
    if x_expr is not None:
        bindings.append((f"Geometry[{int(geom_index)}].{prop_prefix}.x", x_expr))
    y_expr = _local_point_component_formula(params, param_exprs, point_path, origin, y_axis)
    if y_expr is not None:
        bindings.append((f"Geometry[{int(geom_index)}].{prop_prefix}.y", y_expr))
    return bindings


def _build_local_line_sketch_bindings(params, param_exprs, geom_index=0, origin=None, x_axis=None, y_axis=None):
    bindings = []
    bindings.extend(
        _build_local_point_sketch_bindings(
            params,
            param_exprs,
            'start',
            'StartPoint',
            geom_index=geom_index,
            origin=origin,
            x_axis=x_axis,
            y_axis=y_axis,
        )
    )
    bindings.extend(
        _build_local_point_sketch_bindings(
            params,
            param_exprs,
            'end',
            'EndPoint',
            geom_index=geom_index,
            origin=origin,
            x_axis=x_axis,
            y_axis=y_axis,
        )
    )
    return bindings


def _build_local_circle_sketch_bindings(params, param_exprs, geom_index=0, origin=None, x_axis=None, y_axis=None):
    bindings = []
    bindings.extend(
        _build_local_point_sketch_bindings(
            params,
            param_exprs,
            'center',
            'Center',
            geom_index=geom_index,
            origin=origin,
            x_axis=x_axis,
            y_axis=y_axis,
        )
    )
    radius_expr = _nested_expr_ref(param_exprs, 'radius')
    if radius_expr is not None:
        bindings.append((f"Geometry[{int(geom_index)}].Radius", radius_expr))
    return bindings


def _angle_arc_local_point_formula(params, param_exprs, angle_key, origin, sketch_axis):
    if origin is None or sketch_axis is None:
        return None
    center_component = _local_point_component_formula(params, param_exprs, 'center', origin, sketch_axis)
    radius_expr = _formula_nested_value(params, param_exprs, 'radius')
    angle_expr = _formula_nested_value(params, param_exprs, angle_key)
    if center_component is None or radius_expr is None or angle_expr is None:
        return None
    normal = params.get('normal', (0.0, 0.0, 1.0))
    try:
        arc_x, arc_y = _angle_arc_axes(normal)
    except Exception:
        return None
    cos_term = _formula_scale(
        _formula_mul(radius_expr, _formula_cos_radians(angle_expr)),
        float(arc_x.x * sketch_axis.x + arc_x.y * sketch_axis.y + arc_x.z * sketch_axis.z),
    )
    sin_term = _formula_scale(
        _formula_mul(radius_expr, _formula_sin_radians(angle_expr)),
        float(arc_y.x * sketch_axis.x + arc_y.y * sketch_axis.y + arc_y.z * sketch_axis.z),
    )
    return _formula_join_terms(center_component, cos_term, sin_term)


def _build_local_angle_arc_sketch_bindings(params, param_exprs, geom_index=0, origin=None, x_axis=None, y_axis=None):
    bindings = []
    bindings.extend(
        _build_local_circle_sketch_bindings(
            params,
            param_exprs,
            geom_index=geom_index,
            origin=origin,
            x_axis=x_axis,
            y_axis=y_axis,
        )
    )
    start_x = _angle_arc_local_point_formula(params, param_exprs, 'start_angle', origin, x_axis)
    start_y = _angle_arc_local_point_formula(params, param_exprs, 'start_angle', origin, y_axis)
    end_x = _angle_arc_local_point_formula(params, param_exprs, 'end_angle', origin, x_axis)
    end_y = _angle_arc_local_point_formula(params, param_exprs, 'end_angle', origin, y_axis)
    if start_x is not None:
        bindings.append((f"Geometry[{int(geom_index)}].StartPoint.x", start_x))
    if start_y is not None:
        bindings.append((f"Geometry[{int(geom_index)}].StartPoint.y", start_y))
    if end_x is not None:
        bindings.append((f"Geometry[{int(geom_index)}].EndPoint.x", end_x))
    if end_y is not None:
        bindings.append((f"Geometry[{int(geom_index)}].EndPoint.y", end_y))
    return bindings


def _three_point_arc_local_coordinate_formulas(params, param_exprs, origin, x_axis, y_axis):
    return {
        'sx': _local_point_component_formula(params, param_exprs, 'start', origin, x_axis),
        'sy': _local_point_component_formula(params, param_exprs, 'start', origin, y_axis),
        'mx': _local_point_component_formula(params, param_exprs, 'middle', origin, x_axis),
        'my': _local_point_component_formula(params, param_exprs, 'middle', origin, y_axis),
        'ex': _local_point_component_formula(params, param_exprs, 'end', origin, x_axis),
        'ey': _local_point_component_formula(params, param_exprs, 'end', origin, y_axis),
    }


def _three_point_arc_center_formula(params, param_exprs, origin, x_axis, y_axis, axis_name):
    coords = _three_point_arc_local_coordinate_formulas(params, param_exprs, origin, x_axis, y_axis)
    if any(value is None for value in coords.values()):
        return None
    sx = coords['sx']
    sy = coords['sy']
    mx = coords['mx']
    my = coords['my']
    ex = coords['ex']
    ey = coords['ey']
    denom = (
        f"2 * ((({sx}) * (({my}) - ({ey}))) + (({mx}) * (({ey}) - ({sy}))) + (({ex}) * (({sy}) - ({my}))))"
    )
    start_sq = f"({_formula_square(sx)} + {_formula_square(sy)})"
    mid_sq = f"({_formula_square(mx)} + {_formula_square(my)})"
    end_sq = f"({_formula_square(ex)} + {_formula_square(ey)})"
    if axis_name == 'x':
        numer = (
            f"(({start_sq}) * (({my}) - ({ey}))) + (({mid_sq}) * (({ey}) - ({sy}))) + (({end_sq}) * (({sy}) - ({my})))"
        )
    elif axis_name == 'y':
        numer = (
            f"(({start_sq}) * (({ex}) - ({mx}))) + (({mid_sq}) * (({sx}) - ({ex}))) + (({end_sq}) * (({mx}) - ({sx})))"
        )
    else:
        return None
    return f"(({numer})) / ({denom})"


def _three_point_arc_radius_formula(params, param_exprs, origin, x_axis, y_axis):
    coords = _three_point_arc_local_coordinate_formulas(params, param_exprs, origin, x_axis, y_axis)
    sx = coords.get('sx')
    sy = coords.get('sy')
    cx = _three_point_arc_center_formula(params, param_exprs, origin, x_axis, y_axis, 'x')
    cy = _three_point_arc_center_formula(params, param_exprs, origin, x_axis, y_axis, 'y')
    if sx is None or sy is None or cx is None or cy is None:
        return None
    return f"sqrt({_formula_square(f'({cx}) - ({sx})')} + {_formula_square(f'({cy}) - ({sy})')})"


def _build_local_three_point_arc_sketch_bindings(params, param_exprs, geom_index=0, origin=None, x_axis=None, y_axis=None):
    bindings = []
    bindings.extend(
        _build_local_point_sketch_bindings(
            params,
            param_exprs,
            'start',
            'StartPoint',
            geom_index=geom_index,
            origin=origin,
            x_axis=x_axis,
            y_axis=y_axis,
        )
    )
    bindings.extend(
        _build_local_point_sketch_bindings(
            params,
            param_exprs,
            'end',
            'EndPoint',
            geom_index=geom_index,
            origin=origin,
            x_axis=x_axis,
            y_axis=y_axis,
        )
    )
    if origin is None or x_axis is None or y_axis is None:
        return bindings
    center_x = _three_point_arc_center_formula(params, param_exprs, origin, x_axis, y_axis, 'x')
    center_y = _three_point_arc_center_formula(params, param_exprs, origin, x_axis, y_axis, 'y')
    radius = _three_point_arc_radius_formula(params, param_exprs, origin, x_axis, y_axis)
    if center_x is not None:
        bindings.append((f"Geometry[{int(geom_index)}].Center.x", center_x))
    if center_y is not None:
        bindings.append((f"Geometry[{int(geom_index)}].Center.y", center_y))
    if radius is not None:
        bindings.append((f"Geometry[{int(geom_index)}].Radius", radius))
    return bindings


def _build_arc_sketch_bindings(param_exprs, geom_index=0, *, prefer_local=False):
    bindings = []
    if prefer_local:
        for axis_name, axis_index in (("x", 0), ("y", 1)):
            start_expr = _nested_expr_ref(param_exprs, 'start', axis_index)
            if start_expr is not None:
                bindings.append((f"Geometry[{int(geom_index)}].StartPoint.{axis_name}", start_expr))
            end_expr = _nested_expr_ref(param_exprs, 'end', axis_index)
            if end_expr is not None:
                bindings.append((f"Geometry[{int(geom_index)}].EndPoint.{axis_name}", end_expr))
        return bindings
    bindings.extend(_build_circle_sketch_bindings(param_exprs, geom_index=geom_index, local=False))
    start_angle_expr = _nested_expr_ref(param_exprs, 'start_angle')
    if start_angle_expr is not None:
        bindings.append((f"Geometry[{int(geom_index)}].FirstParameter", start_angle_expr))
    end_angle_expr = _nested_expr_ref(param_exprs, 'end_angle')
    if end_angle_expr is not None:
        bindings.append((f"Geometry[{int(geom_index)}].LastParameter", end_angle_expr))
    return bindings


def _detail_edge_binding_expr(param_exprs, key):
    edge_indices = []
    radius_expr = None
    if key == 'radius':
        radius_expr = _nested_expr_ref(param_exprs, 'radius')
    elif key == 'distance':
        radius_expr = _nested_expr_ref(param_exprs, 'distance')
    if radius_expr is None:
        return None
    return radius_expr


def _apply_detail_feature_bindings(obj, param_exprs, key):
    expr_ref = _detail_edge_binding_expr(param_exprs, key)
    if expr_ref is None:
        return False
    selected = []
    if key == 'radius':
        selected = list(getattr(obj, 'Edges', []) or [])
    else:
        selected = list(getattr(obj, 'Edges', []) or [])
    applied = False
    for idx in range(len(selected)):
        applied = _bind_expression(obj, f'Edges[{idx}]', expr_ref) or applied
    return applied


def _resolve_param_value(params, param_exprs, key):
    if isinstance(param_exprs, dict) and key in param_exprs:
        value = _resolve_expr_ref(param_exprs[key])
        if value is not None:
            return value
    return params[key]


def _resolve_nested_param_value(params, param_exprs, *path):
    value = params
    expr_meta = param_exprs if isinstance(param_exprs, dict) else {}
    for key in path:
        value = value[key]
        if isinstance(expr_meta, dict) and key in expr_meta:
            expr_meta = expr_meta[key]
        elif isinstance(expr_meta, list) and isinstance(key, int) and 0 <= key < len(expr_meta):
            expr_meta = expr_meta[key]
        else:
            expr_meta = None
    expr_value = _resolve_expr_ref(expr_meta)
    if expr_value is not None:
        return expr_value
    return value


def _resolve_vec3_param(params, param_exprs, key):
    return (
        float(_resolve_nested_param_value(params, param_exprs, key, 0)),
        float(_resolve_nested_param_value(params, param_exprs, key, 1)),
        float(_resolve_nested_param_value(params, param_exprs, key, 2)),
    )


""".strip()

    def _emit_node(self, node: OperationNode) -> List[str]:
        params_literal = _py_literal(dict(node.params))
        inputs_literal = _py_literal([inp.node_id for inp in node.inputs])
        tags_literal = _py_literal(sorted(node.tags))
        context_literal = _py_literal(node.context or {})
        param_exprs_literal = _py_literal(dict(node.param_exprs))
        semantic_delta_literal = _py_literal(
            self._node_optional_payload(node, "semantic_delta")
        )
        topo_delta_literal = _py_literal(
            self._node_optional_payload(node, "topo_delta")
        )

        var_name = _safe_name(node.node_id)
        object_name = _safe_name(f"{node.op}_{node.node_id}", prefix="step")
        lines = [
            f"{var_name}_params = {params_literal}",
            f"{var_name}_inputs = {inputs_literal}",
            f"{var_name}_param_exprs = {param_exprs_literal}",
        ]

        native_lines = self._emit_native_node(
            node,
            var_name=var_name,
            object_name=object_name,
            tags_literal=tags_literal,
            context_literal=context_literal,
            param_exprs_literal=param_exprs_literal,
            semantic_delta_literal=semantic_delta_literal,
            topo_delta_literal=topo_delta_literal,
        )
        if native_lines is not None:
            lines.extend(native_lines)
            return lines
        raise ValueError(f"Unsupported FreeCAD native graph translation op: {node.op}")

    def _emit_native_node(
        self,
        node: OperationNode,
        *,
        var_name: str,
        object_name: str,
        tags_literal: str,
        context_literal: str,
        param_exprs_literal: str,
        semantic_delta_literal: str,
        topo_delta_literal: str,
    ) -> Optional[List[str]]:
        native_expr = self._compile_native_feature_expr(
            node,
            var_name=var_name,
            object_name=object_name,
            tags_literal=tags_literal,
            context_literal=context_literal,
            param_exprs_literal=param_exprs_literal,
            semantic_delta_literal=semantic_delta_literal,
            topo_delta_literal=topo_delta_literal,
        )
        if native_expr is None:
            return None
        return native_expr

    def _compile_native_feature_expr(
        self,
        node: OperationNode,
        *,
        var_name: str,
        object_name: str,
        tags_literal: str,
        context_literal: str,
        param_exprs_literal: str,
        semantic_delta_literal: str,
        topo_delta_literal: str,
    ) -> Optional[List[str]]:
        graph = self._source_graph
        if graph is None:
            return None

        rp = f"{var_name}_params"
        re = f"{var_name}_param_exprs"
        inputs = [inp.node_id for inp in node.inputs]

        def finish() -> List[str]:
            return [
                f"_attach_simplecad_metadata({var_name}, node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
                f"GRAPH_NODES[{_json_ascii(node.node_id)}] = {var_name}",
                f"GRAPH_METADATA[{_json_ascii(node.node_id)}] = {{'op': {_json_ascii(node.op)}, 'params': {rp}, 'inputs': {var_name}_inputs, 'context': {context_literal}, 'tags': {tags_literal}}}",
                f"GRAPH_OUTPUTS[{_json_ascii(node.node_id)}] = [{var_name}]",
            ]

        def finish_ir() -> List[str]:
            return [
                f"{var_name} = _register_ir_node({_json_ascii(object_name)}, node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
            ]

        def finish_alias(source_node_id: str) -> List[str]:
            return [
                f"{var_name} = _register_graph_alias(node_id={_json_ascii(node.node_id)}, source_node_id={_json_ascii(source_node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
            ]

        if node.op == "make_material_rmaterial":
            return [
                f"{var_name} = dict({rp})",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = {{'kind': 'material', 'material': {var_name}}}",
                f"{var_name} = _register_graph_value({var_name}, node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
            ]

        if node.op in {"make_placement_rplacement", "make_identity_placement_rplacement"}:
            return [
                f"{var_name} = dict({rp})",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = {{'kind': 'placement', 'placement': {var_name}}}",
                f"{var_name} = _register_graph_value({var_name}, node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
            ]

        if node.op == "make_part_rpart" and len(inputs) == 1:
            lines = [
                f"{var_name} = doc.addObject('App::Part', {_json_ascii(object_name)})",
                f"{var_name}.Label = str({rp}.get('name') or {rp}.get('part_id') or {_json_ascii(object_name)})",
                f"{var_name}_source_body = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                f"{var_name}_body = _make_part_body_copy({var_name}, {var_name}_source_body, {_json_ascii(inputs[0])})",
                f"{var_name}.addObject({var_name}_body)",
                f"_ensure_string_property({var_name}, 'SimpleCADPartId')",
                f"{var_name}.SimpleCADPartId = str({rp}.get('part_id', ''))",
                f"_hide_origin_tree({var_name})",
            ]
            lines.extend(finish())
            lines.append(
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = {{'kind': 'part', 'part_id': str({rp}.get('part_id', '')), 'body': {var_name}_body, 'container': {var_name}, 'material': None, 'connectors': []}}"
            )
            return lines

        if node.op == "make_assign_material_rpart" and len(inputs) >= 2:
            lines = [
                f"{var_name}_part = PRODUCT_VALUES[{_json_ascii(inputs[0])}]",
                f"{var_name}_material = PRODUCT_VALUES[{_json_ascii(inputs[1])}]['material']",
                f"{var_name} = {var_name}_part['container']",
                f"_ensure_string_property({var_name}, 'SimpleCADMaterial')",
                f"{var_name}.SimpleCADMaterial = json.dumps({var_name}_material, ensure_ascii=True, sort_keys=True)",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = dict({var_name}_part)",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}]['material'] = {var_name}_material",
                f"{var_name} = _register_graph_folded_alias(node_id={_json_ascii(node.node_id)}, source_node_id={_json_ascii(inputs[0])}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
            ]
            return lines

        if node.op == "make_assembly_rassembly":
            lines = [
                f"{var_name} = _make_native_assembly({_json_ascii(object_name)}, node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
                f"{var_name}.Label = str({rp}.get('name') or {rp}.get('assembly_id') or {_json_ascii(object_name)})",
                f"_ensure_string_property({var_name}, 'SimpleCADAssemblyId')",
                f"{var_name}.SimpleCADAssemblyId = str({rp}.get('assembly_id', ''))",
            ]
            lines.append(
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = {{'kind': 'assembly', 'assembly_id': str({rp}.get('assembly_id', '')), 'container': {var_name}, 'components': [], 'connectors': [], 'constraints': [], 'grounded_component_ids': []}}"
            )
            return lines

        if node.op == "make_add_component_rassembly" and len(inputs) >= 3:
            lines = [
                f"{var_name}_assembly = PRODUCT_VALUES[{_json_ascii(inputs[0])}]",
                f"{var_name}_item = PRODUCT_VALUES[{_json_ascii(inputs[1])}]",
                f"{var_name}_placement = PRODUCT_VALUES[{_json_ascii(inputs[2])}]['placement']",
                f"{var_name} = {var_name}_assembly['container']",
                f"{var_name}_link_label = str({rp}.get('name') or {rp}.get('component_id') or {_json_ascii(object_name)})",
                f"{var_name}_link = _make_assembly_component_link({var_name}, {var_name}_item, {_json_ascii(object_name + '_component')}, {var_name}_link_label, {var_name}_placement)",
                f"_ensure_string_property({var_name}_link, 'SimpleCADComponentId')",
                f"{var_name}_link.SimpleCADComponentId = str({rp}.get('component_id', ''))",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = dict({var_name}_assembly)",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}]['components'] = list({var_name}_assembly.get('components', [])) + [{{'component_id': str({rp}.get('component_id', '')), 'link': {var_name}_link, 'placement': {var_name}_placement, 'item': {var_name}_item}}]",
                f"{var_name} = _register_graph_folded_alias(node_id={_json_ascii(node.node_id)}, source_node_id={_json_ascii(inputs[0])}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
            ]
            return lines

        if node.op == "make_place_component_rassembly" and len(inputs) >= 2:
            lines = [
                f"{var_name}_assembly = PRODUCT_VALUES[{_json_ascii(inputs[0])}]",
                f"{var_name}_placement = PRODUCT_VALUES[{_json_ascii(inputs[1])}]['placement']",
                f"{var_name} = {var_name}_assembly['container']",
                f"{var_name}_components = []",
                f"for _component in {var_name}_assembly.get('components', []):",
                f"    if str(_component.get('component_id')) == str({rp}.get('component_id')):",
                f"        _component = dict(_component)",
                f"        _component['placement'] = {var_name}_placement",
                f"        _component['link'].Placement = _placement_from_axes_payload({var_name}_placement)",
                f"    {var_name}_components.append(_component)",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = dict({var_name}_assembly)",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}]['components'] = {var_name}_components",
                f"{var_name} = _register_graph_folded_alias(node_id={_json_ascii(node.node_id)}, source_node_id={_json_ascii(inputs[0])}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
            ]
            return lines

        if node.op in {"make_face_connector_rconnector", "make_edge_connector_rconnector", "make_vertex_connector_rconnector"}:
            return [
                f"{var_name} = dict({rp})",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = {{'kind': 'connector', 'connector': {var_name}}}",
                f"{var_name} = _register_graph_value({var_name}, node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
            ]

        if node.op == "make_add_connector_rpart" and len(inputs) >= 2:
            return [
                f"{var_name}_part = PRODUCT_VALUES[{_json_ascii(inputs[0])}]",
                f"{var_name}_connector = PRODUCT_VALUES[{_json_ascii(inputs[1])}]['connector']",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = dict({var_name}_part)",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}]['connectors'] = list({var_name}_part.get('connectors', [])) + [{var_name}_connector]",
                f"{var_name} = _register_graph_folded_alias(node_id={_json_ascii(node.node_id)}, source_node_id={_json_ascii(inputs[0])}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
            ]

        if node.op == "make_add_connector_rassembly" and len(inputs) >= 2:
            return [
                f"{var_name}_assembly = PRODUCT_VALUES[{_json_ascii(inputs[0])}]",
                f"{var_name}_connector = PRODUCT_VALUES[{_json_ascii(inputs[1])}]['connector']",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = dict({var_name}_assembly)",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}]['connectors'] = list({var_name}_assembly.get('connectors', [])) + [{var_name}_connector]",
                f"{var_name} = _register_graph_folded_alias(node_id={_json_ascii(node.node_id)}, source_node_id={_json_ascii(inputs[0])}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
            ]

        if node.op == "make_connector_ref_rconnectorref":
            return [
                f"{var_name} = dict({rp})",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = {{'kind': 'connector_ref', 'connector_ref': {var_name}}}",
                f"{var_name} = _register_graph_value({var_name}, node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
            ]

        if node.op == "make_scalar_limit_rscalarlimit":
            return [
                f"{var_name} = dict({rp})",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = {{'kind': 'scalar_limit', 'scalar_limit': {var_name}}}",
                f"{var_name} = _register_graph_value({var_name}, node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
            ]

        if node.op in {"make_ground_component_rassembly", "make_unground_component_rassembly"} and len(inputs) >= 1:
            action = "add" if node.op == "make_ground_component_rassembly" else "remove"
            return [
                f"{var_name}_assembly = PRODUCT_VALUES[{_json_ascii(inputs[0])}]",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = dict({var_name}_assembly)",
                f"{var_name}_grounded = list({var_name}_assembly.get('grounded_component_ids', []))",
                f"{var_name}_component_id = str({rp}.get('component_id', ''))",
                f"{var_name}_grounded = (list({var_name}_grounded) if {_json_ascii(action)} == 'add' else [component_id for component_id in {var_name}_grounded if component_id != {var_name}_component_id])",
                f"if {_json_ascii(action)} == 'add' and {var_name}_component_id not in {var_name}_grounded: {var_name}_grounded.append({var_name}_component_id)",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}]['grounded_component_ids'] = {var_name}_grounded",
                f"if {_json_ascii(action)} == 'add': _make_simplecad_grounded_joint({var_name}_assembly, {var_name}_component_id)",
                f"{var_name} = _register_graph_folded_alias(node_id={_json_ascii(node.node_id)}, source_node_id={_json_ascii(inputs[0])}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
            ]

        if node.op in {"make_fixed_constraint_rassembly", "make_revolute_constraint_rassembly", "make_prismatic_constraint_rassembly"} and len(inputs) >= 3:
            return [
                f"{var_name}_assembly = PRODUCT_VALUES[{_json_ascii(inputs[0])}]",
                f"{var_name}_constraint = dict({rp})",
                f"{var_name}_constraint['connector_a'] = PRODUCT_VALUES[{_json_ascii(inputs[1])}]['connector_ref']",
                f"{var_name}_constraint['connector_b'] = PRODUCT_VALUES[{_json_ascii(inputs[2])}]['connector_ref']",
                f"{var_name}_joint = _make_simplecad_joint({var_name}_assembly, {var_name}_constraint, {_json_ascii(object_name)}, str({rp}.get('name') or {rp}.get('constraint_id') or {_json_ascii(object_name)}))",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = dict({var_name}_assembly)",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}]['constraints'] = list({var_name}_assembly.get('constraints', [])) + [{var_name}_constraint]",
                f"{var_name} = _register_graph_folded_alias(node_id={_json_ascii(node.node_id)}, source_node_id={_json_ascii(inputs[0])}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
            ]

        if node.op == "make_solve_assembly_constraints_rassembly" and len(inputs) >= 1:
            return [
                f"{var_name}_assembly = PRODUCT_VALUES[{_json_ascii(inputs[0])}]",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}] = dict({var_name}_assembly)",
                f"{var_name}_placements = dict({rp}.get('component_placements') or {{}})",
                f"{var_name}_components = []",
                f"for _component in {var_name}_assembly.get('components', []):",
                f"    _component = dict(_component)",
                f"    _component_id = str(_component.get('component_id'))",
                f"    if _component_id in {var_name}_placements:",
                f"        _component['placement'] = {var_name}_placements[_component_id]",
                f"        _component['link'].Placement = _placement_from_axes_payload(_component['placement'])",
                f"    {var_name}_components.append(_component)",
                f"PRODUCT_VALUES[{_json_ascii(node.node_id)}]['components'] = {var_name}_components",
                f"{var_name} = _register_graph_folded_alias(node_id={_json_ascii(node.node_id)}, source_node_id={_json_ascii(inputs[0])}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
            ]

        if node.op == "make_compound_from_assembly_rcompound" and len(inputs) == 1:
            return [
                f"{var_name}_assembly = PRODUCT_VALUES[{_json_ascii(inputs[0])}]",
                f"ASSEMBLY_PROJECTION_INPUTS[{_json_ascii(node.node_id)}] = {_json_ascii(inputs[0])}",
                "doc.recompute()",
                f"{var_name}_shapes = _shapes_from_product_value({var_name}_assembly)",
                f"{var_name} = _make_feature({_json_ascii(object_name)}, Part.makeCompound({var_name}_shapes), node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
            ]

        if node.op in {
            "make_select_rvertex",
            "make_select_redge",
            "make_select_rwire",
            "make_select_rface",
            "make_select_rsolid",
        } and len(inputs) == 1:
            return [
                f"{var_name} = _register_geo_selection_node(node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
            ]

        if node.op in {
            "make_sketch_rsketch",
            "make_add_point_rsketch",
            "make_add_line_rsketch",
            "make_add_circle_rsketch",
            "make_constrain_coincident_rsketch",
            "make_constrain_point_on_rsketch",
            "make_constrain_horizontal_rsketch",
            "make_constrain_vertical_rsketch",
            "make_constrain_parallel_rsketch",
            "make_constrain_perpendicular_rsketch",
            "make_constrain_collinear_rsketch",
            "make_constrain_tangent_rsketch",
            "make_constrain_concentric_rsketch",
            "make_constrain_midpoint_rsketch",
            "make_constrain_symmetric_rsketch",
            "make_constrain_equal_length_rsketch",
            "make_constrain_equal_radius_rsketch",
            "make_constrain_distance_rsketch",
            "make_constrain_distance_x_rsketch",
            "make_constrain_distance_y_rsketch",
            "make_constrain_length_rsketch",
            "make_constrain_angle_rsketch",
            "make_constrain_radius_rsketch",
            "make_constrain_diameter_rsketch",
            "make_constrain_fix_rsketch",
        }:
            return finish_ir()

        if node.op in {"make_wire_from_sketch_rwire", "make_face_from_sketch_rface"}:
            return [
                f"{var_name} = _make_sketch_promotion_object({_json_ascii(object_name)}, node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
            ]

        if node.node_id in self._suppressed_profile_node_ids:
            return finish_ir()

        if node.op == "make_line_redge":
            lines = [
                f"{var_name} = _register_graph_value(Part.makeLine(_vec(_resolve_vec3_param({rp}, {re}, 'start')), _vec(_resolve_vec3_param({rp}, {re}, 'end'))), node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
            ]
            return lines

        if node.op == "make_circle_redge":
            lines = [
                f"{var_name} = _register_graph_value(Part.Circle(_vec(_resolve_vec3_param({rp}, {re}, 'center')), _vec(_resolve_vec3_param({rp}, {re}, 'normal') if 'normal' in {rp} else (0.0, 0.0, 1.0)), float(_resolve_param_value({rp}, {re}, 'radius'))).toShape(), node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
            ]
            return lines

        if node.op == "make_angle_arc_redge":
            lines = [
                f"{var_name} = _register_graph_value(Part.ArcOfCircle(Part.Circle(_vec(_resolve_vec3_param({rp}, {re}, 'center')), _vec(_resolve_vec3_param({rp}, {re}, 'normal') if 'normal' in {rp} else (0.0, 0.0, 1.0)), float(_resolve_param_value({rp}, {re}, 'radius'))), float(_resolve_param_value({rp}, {re}, 'start_angle')), float(_resolve_param_value({rp}, {re}, 'end_angle'))).toShape(), node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
            ]
            return lines

        if node.op == "make_three_point_arc_redge":
            arc_expr = f"Part.Arc(_vec(_resolve_vec3_param({rp}, {re}, 'start')), _vec(_resolve_vec3_param({rp}, {re}, 'middle')), _vec(_resolve_vec3_param({rp}, {re}, 'end'))).toShape()"
            lines = [
                f"{var_name} = _register_graph_value({arc_expr}, node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
            ]
            return lines

        if node.op == "make_spline_redge":
            lines = [
                f"{var_name} = _register_graph_value(_bspline_curve_from_params({rp}).toShape(), node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
            ]
            return lines

        if node.op == "make_wire_from_edges_rwire":
            input_nodes = [graph.get_node(node_id) for node_id in inputs]
            if len(inputs) == 1:
                single = input_nodes[0]
                if single is not None and single.op == "make_helix_redge":
                    return finish_alias(inputs[0])
            if input_nodes and all(
                inp is not None
                and inp.op
                in {
                    "make_line_redge",
                    "make_circle_redge",
                    "make_angle_arc_redge",
                    "make_three_point_arc_redge",
                    "make_spline_redge",
                }
                for inp in input_nodes
            ):
                lines = [
                    f"{var_name} = doc.addObject('Sketcher::SketchObject', {_json_ascii(object_name)})",
                    f"{var_name}_sketch_bindings = []",
                    f"{var_name}_expr_limitations = []",
                    f"{var_name}_constraint_bindings = []",
                ]
                point_exprs: List[str] = []
                for geom_index, input_node in enumerate(input_nodes):
                    assert input_node is not None
                    edge_var = _safe_name(input_node.node_id)
                    edge_obj_expr = f"GRAPH_NODES[{_json_ascii(input_node.node_id)}]"
                    if input_node.op == "make_line_redge":
                        point_exprs.append(f"_edge_start_point({edge_obj_expr})")
                        point_exprs.append(f"_edge_end_point({edge_obj_expr})")
                    elif input_node.op == "make_three_point_arc_redge":
                        point_exprs.append(f"_edge_start_point({edge_obj_expr})")
                        point_exprs.append(
                            f"_resolve_vec3_param({edge_var}_params, {edge_var}_param_exprs, 'middle')"
                        )
                        point_exprs.append(f"_edge_end_point({edge_obj_expr})")
                    elif input_node.op == "make_circle_redge":
                        point_exprs.append(
                            f"_resolve_vec3_param({edge_var}_params, {edge_var}_param_exprs, 'center')"
                        )
                    elif input_node.op == "make_angle_arc_redge":
                        point_exprs.append(f"_edge_start_point({edge_obj_expr})")
                        point_exprs.append(f"_edge_mid_point({edge_obj_expr})")
                        point_exprs.append(f"_edge_end_point({edge_obj_expr})")
                    elif input_node.op == "make_spline_redge":
                        point_exprs.append(f"_edge_start_point({edge_obj_expr})")
                        point_exprs.append(f"_edge_mid_point({edge_obj_expr})")
                        point_exprs.append(f"_edge_end_point({edge_obj_expr})")
                    limitation_payload = _node_expression_limitation(input_node)
                    if limitation_payload is not None:
                        lines.append(
                            f"{var_name}_expr_limitations.append({_py_literal(limitation_payload)})"
                        )
                if (
                    len(input_nodes) == 1
                    and input_nodes[0] is not None
                    and input_nodes[0].op == "make_line_redge"
                ):
                    edge_var = _safe_name(input_nodes[0].node_id)
                    lines.append(
                        f"{var_name}_placement, {var_name}_length = _line_sketch_placement(_resolve_vec3_param({edge_var}_params, {edge_var}_param_exprs, 'start'), _resolve_vec3_param({edge_var}_params, {edge_var}_param_exprs, 'end'))"
                    )
                    lines.append(f"{var_name}.Placement = {var_name}_placement")
                else:
                    frame_points = "[" + ", ".join(point_exprs) + "]"
                    lines.append(
                        f"{var_name}_placement, {var_name}_origin, {var_name}_xaxis, {var_name}_yaxis = _frame_from_points({frame_points}, {context_literal})"
                    )
                    lines.append(f"{var_name}.Placement = {var_name}_placement")
                for geom_index, input_node in enumerate(input_nodes):
                    assert input_node is not None
                    edge_var = _safe_name(input_node.node_id)
                    edge_obj_expr = f"GRAPH_NODES[{_json_ascii(input_node.node_id)}]"
                    if input_node.op == "make_line_redge":
                        if len(input_nodes) == 1:
                            lines.append(
                                f"{var_name}_placement, {var_name}_length = _line_sketch_placement(_resolve_vec3_param({edge_var}_params, {edge_var}_param_exprs, 'start'), _resolve_vec3_param({edge_var}_params, {edge_var}_param_exprs, 'end'))"
                            )
                            lines.append(f"{var_name}.Placement = {var_name}_placement")
                            lines.append(
                                f"{var_name}.addGeometry(Part.LineSegment(App.Vector(0.0, 0.0, 0.0), App.Vector({var_name}_length, 0.0, 0.0)), False)"
                            )
                            lines.append(
                                f"{var_name}_length_constraint_{geom_index} = {var_name}.addConstraint(Sketcher.Constraint('Distance', {geom_index}, float({var_name}_length)))"
                            )
                            lines.append(
                                f"{var_name}_dx_constraint_{geom_index} = {var_name}.addConstraint(Sketcher.Constraint('DistanceX', {geom_index}, 1, {geom_index}, 2, float(_resolve_nested_param_value({edge_var}_params, {edge_var}_param_exprs, 'end', 0)) - float(_resolve_nested_param_value({edge_var}_params, {edge_var}_param_exprs, 'start', 0))))"
                            )
                            lines.append(
                                f"{var_name}_dy_constraint_{geom_index} = {var_name}.addConstraint(Sketcher.Constraint('DistanceY', {geom_index}, 1, {geom_index}, 2, float(_resolve_nested_param_value({edge_var}_params, {edge_var}_param_exprs, 'end', 1)) - float(_resolve_nested_param_value({edge_var}_params, {edge_var}_param_exprs, 'start', 1))))"
                            )
                            lines.append(
                                f"{var_name}_sketch_bindings.append(('Placement.Base.x', _nested_expr_ref({edge_var}_param_exprs, 'start', 0)))"
                            )
                            lines.append(
                                f"{var_name}_sketch_bindings.append(('Placement.Base.y', _nested_expr_ref({edge_var}_param_exprs, 'start', 1)))"
                            )
                            lines.append(
                                f"{var_name}_sketch_bindings.append(('Placement.Base.z', _nested_expr_ref({edge_var}_param_exprs, 'start', 2)))"
                            )
                            lines.append(
                                f"{var_name}_length_formula = _line_length_formula({edge_var}_params, {edge_var}_param_exprs)"
                            )
                            lines.append(
                                f"{var_name}.setExpression('Geometry[{geom_index}].EndPoint.x', {var_name}_length_formula) if {var_name}_length_formula else None"
                            )
                            lines.append(
                                f"{var_name}_constraint_bindings.append((f'Constraints[{{{var_name}_length_constraint_{geom_index}}}]', {var_name}_length_formula))"
                            )
                            lines.append(
                                f"{var_name}_constraint_bindings.append((f'Constraints[{{{var_name}_dx_constraint_{geom_index}}}]', {_json_ascii(self._line_delta_formula(dict(input_node.param_exprs), 0)) if self._line_delta_formula(dict(input_node.param_exprs), 0) is not None else 'None'}))"
                            )
                            lines.append(
                                f"{var_name}_constraint_bindings.append((f'Constraints[{{{var_name}_dy_constraint_{geom_index}}}]', {_json_ascii(self._line_delta_formula(dict(input_node.param_exprs), 1)) if self._line_delta_formula(dict(input_node.param_exprs), 1) is not None else 'None'}))"
                            )
                        else:
                            lines.append(
                                f"{var_name}.addGeometry(_local_line_from_edge({edge_obj_expr}, {var_name}_origin, {var_name}_xaxis, {var_name}_yaxis), False)"
                            )
                            lines.append(
                                f"{var_name}_length_formula_{geom_index} = _line_length_formula({edge_var}_params, {edge_var}_param_exprs)"
                            )
                            lines.append(
                                f"{var_name}_length_value_{geom_index} = _resolve_param_value({edge_var}_params, {edge_var}_param_exprs, 'length') if 'length' in {edge_var}_params else {var_name}.Geometry[{geom_index}].length()"
                            )
                            lines.append(
                                f"{var_name}_length_constraint_{geom_index} = {var_name}.addConstraint(Sketcher.Constraint('Distance', {geom_index}, float({var_name}_length_value_{geom_index})))"
                            )
                            lines.append(
                                f"{var_name}_sketch_bindings.extend(_build_local_line_sketch_bindings({edge_var}_params, {edge_var}_param_exprs, geom_index={geom_index}, origin={var_name}_origin, x_axis={var_name}_xaxis, y_axis={var_name}_yaxis))"
                            )
                            lines.append(
                                f"{var_name}_constraint_bindings.append((f'Constraints[{{{var_name}_length_constraint_{geom_index}}}]', {var_name}_length_formula_{geom_index}))"
                            )
                    elif input_node.op == "make_circle_redge":
                        lines.append(
                            f"{var_name}.addGeometry(Part.Circle(_local_point_on_frame(_resolve_vec3_param({edge_var}_params, {edge_var}_param_exprs, 'center'), {var_name}_origin, {var_name}_xaxis, {var_name}_yaxis), App.Vector(0.0, 0.0, 1.0), float(_resolve_param_value({edge_var}_params, {edge_var}_param_exprs, 'radius'))), False)"
                        )
                        lines.append(
                            f"{var_name}_diameter_constraint_{geom_index} = {var_name}.addConstraint(Sketcher.Constraint('Diameter', {geom_index}, 2.0 * float(_resolve_param_value({edge_var}_params, {edge_var}_param_exprs, 'radius'))))"
                        )
                        if len(input_nodes) == 1:
                            lines.append(
                                f"{var_name}_sketch_bindings.append(('Placement.Base.x', _nested_expr_ref({edge_var}_param_exprs, 'center', 0)))"
                            )
                            lines.append(
                                f"{var_name}_sketch_bindings.append(('Placement.Base.y', _nested_expr_ref({edge_var}_param_exprs, 'center', 1)))"
                            )
                            lines.append(
                                f"{var_name}_sketch_bindings.append(('Placement.Base.z', _nested_expr_ref({edge_var}_param_exprs, 'center', 2)))"
                            )
                            lines.append(
                                f"{var_name}_radius_expr_{geom_index} = _expr_formula_from_ref(_nested_expr_ref({edge_var}_param_exprs, 'radius'))"
                            )
                            lines.append(
                                f"{var_name}_constraint_bindings.append((f'Constraints[{{{var_name}_diameter_constraint_{geom_index}}}]', f'2 * ({{{var_name}_radius_expr_{geom_index}}})' if {var_name}_radius_expr_{geom_index} else None))"
                            )
                        else:
                            lines.append(
                                f"{var_name}_sketch_bindings.extend(_build_local_circle_sketch_bindings({edge_var}_params, {edge_var}_param_exprs, geom_index={geom_index}, origin={var_name}_origin, x_axis={var_name}_xaxis, y_axis={var_name}_yaxis))"
                            )
                            lines.append(
                                f"{var_name}_radius_expr_{geom_index} = _expr_formula_from_ref(_nested_expr_ref({edge_var}_param_exprs, 'radius'))"
                            )
                            lines.append(
                                f"{var_name}_constraint_bindings.append((f'Constraints[{{{var_name}_diameter_constraint_{geom_index}}}]', f'2 * ({{{var_name}_radius_expr_{geom_index}}})' if {var_name}_radius_expr_{geom_index} else None))"
                            )
                    elif input_node.op == "make_angle_arc_redge":
                        arc_span_formula = self._angle_arc_span_formula(
                            dict(input_node.param_exprs)
                        )
                        arc_radius_formula = self._compile_time_expr_formula(
                            _compile_time_nested_expr_ref(
                                dict(input_node.param_exprs), "radius"
                            )
                        )
                        lines.append(
                            f"{var_name}.addGeometry(_local_arc_from_edge({edge_obj_expr}, {var_name}_origin, {var_name}_xaxis, {var_name}_yaxis), False)"
                        )
                        lines.append(
                            f"{var_name}_radius_constraint_{geom_index} = {var_name}.addConstraint(Sketcher.Constraint('Radius', {geom_index}, float(_resolve_param_value({edge_var}_params, {edge_var}_param_exprs, 'radius'))))"
                        )
                        lines.append(
                            f"{var_name}_angle_constraint_{geom_index} = {var_name}.addConstraint(Sketcher.Constraint('Angle', {geom_index}, float(_resolve_param_value({edge_var}_params, {edge_var}_param_exprs, 'end_angle')) - float(_resolve_param_value({edge_var}_params, {edge_var}_param_exprs, 'start_angle'))))"
                        )
                        lines.append(
                            f"{var_name}_sketch_bindings.extend(_build_local_angle_arc_sketch_bindings({edge_var}_params, {edge_var}_param_exprs, geom_index={geom_index}, origin={var_name}_origin, x_axis={var_name}_xaxis, y_axis={var_name}_yaxis))"
                        )
                        lines.append(
                            f"{var_name}_constraint_bindings.append((f'Constraints[{{{var_name}_radius_constraint_{geom_index}}}]', {_json_ascii(arc_radius_formula) if arc_radius_formula is not None else 'None'}))"
                        )
                        lines.append(
                            f"{var_name}_constraint_bindings.append((f'Constraints[{{{var_name}_angle_constraint_{geom_index}}}]', {_json_ascii(arc_span_formula) if arc_span_formula is not None else 'None'}))"
                        )
                    elif input_node.op == "make_spline_redge":
                        lines.append(
                            f"{var_name}.addGeometry(_bspline_curve_from_params({edge_var}_params, transform_point=lambda point: _local_point_on_frame(point, {var_name}_origin, {var_name}_xaxis, {var_name}_yaxis)), False)"
                        )
                    elif input_node.op == "make_three_point_arc_redge":
                        lines.append(
                            f"{var_name}.addGeometry(_local_arc_from_edge({edge_obj_expr}, {var_name}_origin, {var_name}_xaxis, {var_name}_yaxis), False)"
                        )
                        lines.append(
                            f"{var_name}_sketch_bindings.extend(_build_local_three_point_arc_sketch_bindings({edge_var}_params, {edge_var}_param_exprs, geom_index={geom_index}, origin={var_name}_origin, x_axis={var_name}_xaxis, y_axis={var_name}_yaxis))"
                        )
                lines.append(
                    f"_apply_sketch_expression_bindings({var_name}, {var_name}_sketch_bindings)"
                )
                for pair in _coincident_constraint_pairs(input_nodes):
                    lines.append(
                        f"{var_name}.addConstraint(Sketcher.Constraint('Coincident', {pair[0]}, {pair[1]}, {pair[2]}, {pair[3]}))"
                    )
                lines.append(
                    f"[_bind_expression({var_name}, prop, expr) for prop, expr in {var_name}_constraint_bindings if expr]"
                )
                lines.extend(finish())
                lines.append(
                    f"{var_name}.SimpleCADExprSupport = 'limited' if {var_name}_expr_limitations else {var_name}.SimpleCADExprSupport"
                )
                lines.append(
                    f"{var_name}.SimpleCADExprLimitation = json.dumps({var_name}_expr_limitations, ensure_ascii=True, sort_keys=True) if {var_name}_expr_limitations else {var_name}.SimpleCADExprLimitation"
                )
                lines.append(f"if {var_name}_expr_limitations:")
                lines.append(
                    f"    GRAPH_LIMITATIONS[{_json_ascii(node.node_id)}] = {{'op': {_json_ascii(node.op)}, 'reason': json.dumps({var_name}_expr_limitations, ensure_ascii=True, sort_keys=True)}}"
                )
                return lines
            lines = [
                f"{var_name} = _make_feature({_json_ascii(object_name)}, _wire_shape_from_edge_objects({var_name}_inputs), node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
            ]
            return lines

        if node.op == "make_helix_redge":
            lines = [
                f"{var_name} = _make_native_object('Part::Helix', {_json_ascii(object_name)}, node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
                f"{var_name}.Pitch = float(_resolve_param_value({rp}, {re}, 'pitch'))",
                f"{var_name}.Height = float(_resolve_param_value({rp}, {re}, 'height'))",
                f"{var_name}.Radius = float(_resolve_param_value({rp}, {re}, 'radius'))",
                f"{var_name}.Placement = App.Placement(_vec(_resolve_vec3_param({rp}, {re}, 'center') if 'center' in {rp} else (0.0, 0.0, 0.0)), App.Rotation(App.Vector(0.0, 0.0, 1.0), _vec(_resolve_vec3_param({rp}, {re}, 'dir') if 'dir' in {rp} else (0.0, 0.0, 1.0))))",
            ]
            lines.append(
                f"_apply_op_expression_bindings({var_name}, {_json_ascii(node.op)}, {re})"
            )
            return lines

        if node.op == "make_face_from_wire_rface":
            input_node = graph.get_node(inputs[0]) if inputs else None
            if input_node is not None and input_node.op == "make_wire_from_edges_rwire":
                return finish_alias(inputs[0])
                edge_nodes = [graph.get_node(inp.node_id) for inp in input_node.inputs]
                if edge_nodes and all(
                    ed is not None and ed.op == "make_line_redge" for ed in edge_nodes
                ):
                    lines = [
                        f"{var_name} = doc.addObject('Sketcher::SketchObject', {_json_ascii(object_name)})"
                    ]
                    for edge_node in edge_nodes:
                        assert edge_node is not None
                        edge_var = _safe_name(edge_node.node_id)
                        lines.append(
                            f"{var_name}.addGeometry(Part.LineSegment(_vec(_resolve_vec3_param({edge_var}_params, {edge_var}_param_exprs, 'start')), _vec(_resolve_vec3_param({edge_var}_params, {edge_var}_param_exprs, 'end'))), False)"
                        )
                    lines.extend(finish())
                    return lines
                if edge_nodes and all(
                    ed is not None and ed.op == "make_circle_redge" for ed in edge_nodes
                ):
                    circle_node = edge_nodes[0]
                    assert circle_node is not None
                    circle_var = _safe_name(circle_node.node_id)
                    lines = [
                        f"{var_name} = doc.addObject('Sketcher::SketchObject', {_json_ascii(object_name)})",
                        f"{var_name}.addGeometry(Part.Circle(_vec(_resolve_vec3_param({circle_var}_params, {circle_var}_param_exprs, 'center')), _vec(_resolve_vec3_param({circle_var}_params, {circle_var}_param_exprs, 'normal') if 'normal' in {circle_var}_params else (0.0, 0.0, 1.0)), float(_resolve_param_value({circle_var}_params, {circle_var}_param_exprs, 'radius'))), False)",
                        f"_apply_sketch_expression_bindings({var_name}, _build_circle_sketch_bindings({circle_var}_param_exprs, geom_index=0, local=False))",
                    ]
                    lines.extend(finish())
                    return lines
                if edge_nodes and all(
                    ed is not None and ed.op == "make_angle_arc_redge"
                    for ed in edge_nodes
                ):
                    arc_node = edge_nodes[0]
                    assert arc_node is not None
                    lines = [
                        f"{var_name} = doc.addObject('Sketcher::SketchObject', {_json_ascii(object_name)})",
                        f"{var_name}.addGeometry(_arc_from_edge(GRAPH_NODES[{_json_ascii(arc_node.node_id)}]), False)",
                        f"_apply_sketch_expression_bindings({var_name}, _build_arc_sketch_bindings({_safe_name(arc_node.node_id)}_param_exprs, geom_index=0, prefer_local=False))",
                    ]
                    lines.extend(finish())
                    return lines
                if edge_nodes and all(
                    ed is not None and ed.op == "make_spline_redge" for ed in edge_nodes
                ):
                    spline_node = edge_nodes[0]
                    assert spline_node is not None
                    spline_var = _safe_name(spline_node.node_id)
                    lines = [
                        f"{var_name} = doc.addObject('Sketcher::SketchObject', {_json_ascii(object_name)})",
                        f"{var_name}.addGeometry(_bspline_curve_from_params({spline_var}_params), False)",
                    ]
                    lines.extend(finish())
                    return lines
                if edge_nodes and all(
                    ed is not None and ed.op == "make_three_point_arc_redge"
                    for ed in edge_nodes
                ):
                    arc_node = edge_nodes[0]
                    assert arc_node is not None
                    arc_var = _safe_name(arc_node.node_id)
                    lines = [
                        f"{var_name} = doc.addObject('Sketcher::SketchObject', {_json_ascii(object_name)})",
                        f"{var_name}.addGeometry(Part.ArcOfCircle(Part.Circle(Part.Arc(_vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'start')), _vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'middle')), _vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'end'))).toShape().Curve.Center, Part.Arc(_vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'start')), _vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'middle')), _vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'end'))).toShape().Curve.Axis, Part.Arc(_vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'start')), _vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'middle')), _vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'end'))).toShape().Curve.Radius), Part.Arc(_vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'start')), _vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'middle')), _vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'end'))).FirstParameter, Part.Arc(_vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'start')), _vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'middle')), _vec(_resolve_vec3_param({arc_var}_params, {arc_var}_param_exprs, 'end'))).LastParameter), False)",
                    ]
                    lines.extend(finish())
                    return lines

        if node.op == "make_extrude_rsolid" and len(inputs) == 1:
            base_node = graph.get_node(inputs[0])
            profile_node = base_node
            if (
                profile_node is not None
                and profile_node.op == "make_face_from_wire_rface"
                and profile_node.inputs
            ):
                profile_node = graph.get_node(profile_node.inputs[0].node_id)
            circle_node = None
            if (
                profile_node is not None
                and profile_node.op == "make_wire_from_edges_rwire"
                and len(profile_node.inputs) == 1
            ):
                edge_node = graph.get_node(profile_node.inputs[0].node_id)
                if edge_node is not None and edge_node.op == "make_circle_redge":
                    circle_node = edge_node
            if circle_node is not None:
                circle_var = _safe_name(circle_node.node_id)
                lines = [
                    f"{var_name} = doc.addObject('Part::Cylinder', {_json_ascii(object_name)})",
                    f"{var_name}.Radius = float(_resolve_param_value({circle_var}_params, {circle_var}_param_exprs, 'radius'))",
                    f"{var_name}.Height = float(_resolve_param_value({rp}, {re}, 'distance'))",
                    f"{var_name}.Placement = App.Placement(_vec(_resolve_vec3_param({circle_var}_params, {circle_var}_param_exprs, 'center')), App.Rotation(App.Vector(0.0, 0.0, 1.0), _normalized_vec(_resolve_vec3_param({rp}, {re}, 'direction'))))",
                ]
                lines.extend(finish())
                return lines
            if base_node is not None and base_node.op in {
                "make_face_from_wire_rface",
                "make_wire_from_edges_rwire",
                "make_face_from_sketch_rface",
                "make_wire_from_sketch_rwire",
            }:
                sketch_node_id = inputs[0]
                if base_node.op == "make_face_from_wire_rface" and base_node.inputs:
                    sketch_node_id = base_node.inputs[0].node_id
                base_expr = f"GRAPH_NODES[{_json_ascii(sketch_node_id)}]"
                lines: List[str] = []
                lines.extend(
                    [
                        f"{var_name} = doc.addObject('Part::Extrusion', {_json_ascii(object_name)})",
                        f"{var_name}.Base = {base_expr}",
                        f"{var_name}.DirMode = 'Custom'",
                        f"{var_name}.Dir = _vec(_resolve_vec3_param({rp}, {re}, 'direction'))",
                        f"{var_name}.LengthFwd = float(_resolve_param_value({rp}, {re}, 'distance'))",
                        f"{var_name}.LengthRev = 0.0",
                        f"{var_name}.Solid = True",
                    ]
                )
                lines.append(
                    f"_apply_op_expression_bindings({var_name}, {_json_ascii(node.op)}, {re})"
                )
                lines.extend(finish())
                return lines

        if node.op == "make_revolve_rsolid" and len(inputs) == 1:
            base_node = graph.get_node(inputs[0])
            if base_node is not None and base_node.op == "make_face_from_wire_rface":
                lines = [
                    f"{var_name} = doc.addObject('Part::Revolution', {_json_ascii(object_name)})",
                    f"{var_name}.Source = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                    f"{var_name}.Axis = _vec(_resolve_vec3_param({rp}, {re}, 'axis') if 'axis' in {rp} else (0.0, 0.0, 1.0))",
                    f"{var_name}.Base = _vec(_resolve_vec3_param({rp}, {re}, 'origin') if 'origin' in {rp} else (0.0, 0.0, 0.0))",
                    f"{var_name}.Angle = float(_resolve_param_value({rp}, {re}, 'angle') if 'angle' in {rp} else 360.0)",
                    f"{var_name}.Solid = True",
                ]
                lines.append(
                    f"_apply_op_expression_bindings({var_name}, {_json_ascii(node.op)}, {re})"
                )
                lines.extend(finish())
                return lines

        if node.op == "make_loft_rsolid" and len(inputs) >= 2:
            lines = [
                f"{var_name} = doc.addObject('Part::Loft', {_json_ascii(object_name)})",
                f"{var_name}.Sections = [GRAPH_NODES[node_id] for node_id in {var_name}_inputs]",
                f"{var_name}.Solid = True",
                f"{var_name}.Ruled = bool(_resolve_param_value({rp}, {re}, 'ruled') if 'ruled' in {rp} else False)",
            ]
            lines.append(
                f"_apply_op_expression_bindings({var_name}, {_json_ascii(node.op)}, {re})"
            )
            lines.extend(finish())
            return lines

        if node.op == "make_sweep_rsolid" and len(inputs) == 2:
            lines = [
                f"{var_name} = doc.addObject('Part::Sweep', {_json_ascii(object_name)})",
                f"{var_name}.Sections = [GRAPH_NODES[{_json_ascii(inputs[0])}]]",
                f"{var_name}.Spine = _spine_object({_json_ascii(inputs[1])})",
                f"{var_name}.Solid = True",
                f"{var_name}.Frenet = bool(_resolve_param_value({rp}, {re}, 'is_frenet') if 'is_frenet' in {rp} else False)",
            ]
            lines.append(
                f"_apply_op_expression_bindings({var_name}, {_json_ascii(node.op)}, {re})"
            )
            lines.extend(finish())
            return lines

        if node.op == "make_cut_rsolid" and len(inputs) >= 2:
            if len(inputs) == 2:
                lines = [
                    "doc.recompute()",
                    f"{var_name} = doc.addObject('Part::Cut', {_json_ascii(object_name)})",
                    f"{var_name}.Base = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                    f"{var_name}.Tool = GRAPH_NODES[{_json_ascii(inputs[1])}]",
                ]
            else:
                lines = ["doc.recompute()"]
                previous_expr = f"GRAPH_NODES[{_json_ascii(inputs[0])}]"
                for index, tool_node_id in enumerate(inputs[1:], start=1):
                    is_last = index == len(inputs) - 1
                    step_var = var_name if is_last else f"{var_name}_step_{index}"
                    step_name = object_name if is_last else _safe_name(
                        f"{object_name}_step_{index}", prefix="step"
                    )
                    lines.extend(
                        [
                            f"{step_var} = doc.addObject('Part::Cut', {_json_ascii(step_name)})",
                            f"{step_var}.Base = {previous_expr}",
                            f"{step_var}.Tool = GRAPH_NODES[{_json_ascii(tool_node_id)}]",
                        ]
                    )
                    if not is_last:
                        lines.append(f"_set_visibility({step_var}, False)")
                        lines.append("doc.recompute()")
                    previous_expr = step_var
            lines.extend(finish())
            return lines

        if node.op == "make_union_rsolid" and len(inputs) >= 2:
            if len(inputs) == 2:
                lines = [
                    "doc.recompute()",
                    f"{var_name} = doc.addObject('Part::Fuse', {_json_ascii(object_name)})",
                    f"{var_name}.Base = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                    f"{var_name}.Tool = GRAPH_NODES[{_json_ascii(inputs[1])}]",
                ]
            else:
                lines = ["doc.recompute()"]
                previous_expr = f"GRAPH_NODES[{_json_ascii(inputs[0])}]"
                for index, tool_node_id in enumerate(inputs[1:], start=1):
                    is_last = index == len(inputs) - 1
                    step_var = var_name if is_last else f"{var_name}_step_{index}"
                    step_name = object_name if is_last else _safe_name(
                        f"{object_name}_step_{index}", prefix="step"
                    )
                    lines.extend(
                        [
                            f"{step_var} = doc.addObject('Part::Fuse', {_json_ascii(step_name)})",
                            f"{step_var}.Base = {previous_expr}",
                            f"{step_var}.Tool = GRAPH_NODES[{_json_ascii(tool_node_id)}]",
                        ]
                    )
                    if not is_last:
                        lines.append(f"_set_visibility({step_var}, False)")
                        lines.append("doc.recompute()")
                    previous_expr = step_var
            lines.extend(finish())
            return lines

        if node.op == "make_intersect_rsolid" and len(inputs) >= 2:
            if len(inputs) == 2:
                lines = [
                    f"{var_name} = doc.addObject('Part::Common', {_json_ascii(object_name)})",
                    f"{var_name}.Base = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                    f"{var_name}.Tool = GRAPH_NODES[{_json_ascii(inputs[1])}]",
                ]
            else:
                lines = [
                    f"{var_name} = doc.addObject('Part::MultiCommon', {_json_ascii(object_name)})",
                    f"{var_name}.Shapes = [GRAPH_NODES[node_id] for node_id in {var_name}_inputs]",
                ]
            lines.extend(finish())
            return lines

        if node.op == "make_fillet_rsolid" and len(inputs) >= 1:
            lines = [
                f"{var_name} = doc.addObject('Part::Fillet', {_json_ascii(object_name)})",
                f"{var_name}.Base = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                f"{var_name}.Edges = [(int(idx) + 1, float(_resolve_param_value({rp}, {re}, 'radius')), float(_resolve_param_value({rp}, {re}, 'radius'))) for idx in _selected_indices_from_nodes({rp}.get('selected_edge_node_ids', []), {rp}.get('selected_edge_indices', []), _shape_from_graph_node({_json_ascii(inputs[0])}), 'edge')]",
            ]
            lines.append(f"_apply_detail_feature_bindings({var_name}, {re}, 'radius')")
            lines.extend(finish())
            return lines

        if node.op == "make_chamfer_rsolid" and len(inputs) >= 1:
            lines = [
                f"{var_name} = doc.addObject('Part::Chamfer', {_json_ascii(object_name)})",
                f"{var_name}.Base = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                f"{var_name}.Edges = [(int(idx) + 1, float(_resolve_param_value({rp}, {re}, 'distance')), float(_resolve_param_value({rp}, {re}, 'distance'))) for idx in _selected_indices_from_nodes({rp}.get('selected_edge_node_ids', []), {rp}.get('selected_edge_indices', []), _shape_from_graph_node({_json_ascii(inputs[0])}), 'edge')]",
            ]
            lines.append(
                f"_apply_detail_feature_bindings({var_name}, {re}, 'distance')"
            )
            lines.extend(finish())
            return lines

        if node.op == "make_shell_rsolid" and len(inputs) >= 1:
            lines = [
                f"{var_name} = doc.addObject('Part::Thickness', {_json_ascii(object_name)})",
                f"{var_name}.Value = float(_resolve_param_value({rp}, {re}, 'thickness'))",
            ]
            lines.append(
                f"_apply_op_expression_bindings({var_name}, {_json_ascii(node.op)}, {re})"
            )
            if node.params.get("selected_face_indices") or node.params.get("selected_face_node_ids"):
                face_name_expr = f"['Face' + str(int(i) + 1) for i in _selected_indices_from_nodes({rp}.get('selected_face_node_ids', []), {rp}.get('selected_face_indices', []), _shape_from_graph_node({_json_ascii(inputs[0])}), 'face')]"
                lines.append(
                    f"{var_name}.Faces = (GRAPH_NODES[{_json_ascii(inputs[0])}], {face_name_expr})"
                )
            lines.extend(finish())
            return lines

        if node.op == "make_mirror_rshape" and len(inputs) == 1:
            lines = [
                f"{var_name} = doc.addObject('Part::Mirroring', {_json_ascii(object_name)})",
                f"{var_name}.Source = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                f"{var_name}.Base = _vec(_resolve_vec3_param({rp}, {re}, 'plane_origin') if 'plane_origin' in {rp} else (0.0, 0.0, 0.0))",
                f"{var_name}.Normal = _vec(_resolve_vec3_param({rp}, {re}, 'plane_normal') if 'plane_normal' in {rp} else (0.0, 0.0, 1.0))",
            ]
            lines.append(
                f"_apply_op_expression_bindings({var_name}, {_json_ascii(node.op)}, {re})"
            )
            lines.extend(finish())
            return lines

        if node.op == "make_translate_rshape" and len(inputs) == 1:
            vector = node.params.get("vector")
            if isinstance(vector, (list, tuple)) and len(vector) == 3:
                try:
                    if all(abs(float(v)) <= 1e-12 for v in vector) and not _contains_expr_refs(dict(node.param_exprs)):
                        return finish_alias(inputs[0])
                except Exception:
                    pass
            if self._can_fold_transform_into_input(node):
                lines = [
                    f"{var_name} = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                    f"_fold_object_placement({var_name}, App.Placement(_vec(_resolve_vec3_param({rp}, {re}, 'vector')), App.Rotation()))",
                ]
                lines.append(
                    f"_apply_op_expression_bindings({var_name}, {_json_ascii(node.op)}, {re})"
                )
                lines.append(
                    f"{var_name} = _register_graph_folded_alias(node_id={_json_ascii(node.node_id)}, source_node_id={_json_ascii(inputs[0])}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
                )
                return lines
            lines = [
                f"{var_name} = doc.addObject('App::Link', {_json_ascii(object_name)})",
                f"{var_name}.LinkedObject = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                f"{var_name}.Placement = App.Placement(_vec(_resolve_vec3_param({rp}, {re}, 'vector')), App.Rotation())",
            ]
            lines.append(
                f"_apply_op_expression_bindings({var_name}, {_json_ascii(node.op)}, {re})"
            )
            lines.extend(finish())
            return lines

        if node.op == "make_rotate_rshape" and len(inputs) == 1:
            if self._can_fold_transform_into_input(node):
                lines = [
                    f"{var_name} = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                    f"_fold_object_placement({var_name}, _placement_for_rotation(_resolve_vec3_param({rp}, {re}, 'origin') if 'origin' in {rp} else (0.0, 0.0, 0.0), _resolve_vec3_param({rp}, {re}, 'axis') if 'axis' in {rp} else (0.0, 0.0, 1.0), _resolve_param_value({rp}, {re}, 'angle')))",
                ]
                lines.append(
                    f"_apply_op_expression_bindings({var_name}, {_json_ascii(node.op)}, {re})"
                )
                lines.append(
                    f"{var_name} = _register_graph_folded_alias(node_id={_json_ascii(node.node_id)}, source_node_id={_json_ascii(inputs[0])}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
                )
                return lines
            lines = [
                f"{var_name} = doc.addObject('App::Link', {_json_ascii(object_name)})",
                f"{var_name}.LinkedObject = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                f"{var_name}.Placement = App.Placement(_vec(_resolve_vec3_param({rp}, {re}, 'origin') if 'origin' in {rp} else (0.0, 0.0, 0.0)), App.Rotation(_vec(_resolve_vec3_param({rp}, {re}, 'axis') if 'axis' in {rp} else (0.0, 0.0, 1.0)), float(_resolve_param_value({rp}, {re}, 'angle'))))",
            ]
            lines.append(
                f"_apply_op_expression_bindings({var_name}, {_json_ascii(node.op)}, {re})"
            )
            lines.extend(finish())
            return lines

        return None

    def _node_optional_payload(self, node: OperationNode, attr: str) -> Dict[str, Any]:
        value = getattr(node, attr)
        if value is None:
            return {}
        if hasattr(value, "created"):
            return {
                "created": [self._dataclass_ref_dict(ref) for ref in value.created],
                "modified": [self._dataclass_ref_dict(ref) for ref in value.modified],
                "deleted": [self._dataclass_ref_dict(ref) for ref in value.deleted],
                "metadata": dict(value.metadata),
            }
        return {
            "preserved": [self._dataclass_ref_dict(ref) for ref in value.preserved],
            "modified": [self._dataclass_ref_dict(ref) for ref in value.modified],
            "generated": [self._dataclass_ref_dict(ref) for ref in value.generated],
            "deleted": [self._dataclass_ref_dict(ref) for ref in value.deleted],
            "section_edges": [
                self._dataclass_ref_dict(ref) for ref in value.section_edges
            ],
            "entries": [
                {
                    "ref": self._dataclass_ref_dict(entry.ref),
                    "event": getattr(entry.event, "name", str(entry.event)),
                    "origin_role": entry.origin_role,
                    "parent_refs": [
                        self._dataclass_ref_dict(ref) for ref in entry.parent_refs
                    ],
                    "metadata": dict(entry.metadata),
                }
                for entry in value.entries
            ],
            "raw_event": dict(value.raw_event),
        }

    def _dataclass_ref_dict(self, ref: Any) -> Dict[str, Any]:
        payload = dict(ref.__dict__)
        if "kind" in payload and hasattr(payload["kind"], "name"):
            payload["kind"] = payload["kind"].name
        return payload

def translate_model_json_to_freecad_script(
    json_str: str,
    document_name: str = "SimpleCADModel",
) -> str:
    """Translate exported model JSON into a FreeCAD Python script.

    Part/Assembly product nodes are emitted as editable FreeCAD document
    structure: parts use `App::Part`, assemblies use native
    `Assembly::AssemblyObject`, part components use `App::Link`, and
    subassembly components use `Assembly::AssemblyLink` when the Assembly
    workbench module is available.
    """

    return FreeCADScriptTranslator(
        document_name=document_name
    ).translate_model_json_to_script(json_str)


def translate_model_json_to_fcstd(
    json_str: str,
    output_path: str,
    *,
    document_name: str = "SimpleCADModel",
    freecad_cmd: Optional[str] = None,
) -> str:
    """Translate canonical model JSON to `.FCStd` via FreeCADCmd/FreeCAD.

    Functional sketch promotions are written as visible `Sketcher::SketchObject`
    nodes with mapped/skipped constraint evidence. Exact B-spline edges are
    exported to FreeCAD using `Part.BSplineCurve().buildFromPolesMultsKnots(...)`.
    Safe single-use profile transforms such as section rotate/translate chains are
    folded into the section object's placement so downstream `Part::Loft` receives
    already-positioned sections instead of placement-bearing `App::Link` proxies.
    Part/Assembly product nodes are written as editable FreeCAD assembly structure:
    parts use `App::Part`, assemblies use native `Assembly::AssemblyObject`, part
    components use `App::Link`, and nested assembly components use
    `Assembly::AssemblyLink`. Explicit assembly-to-compound projections remain in
    the document for geometry workflows but do not replace the visible assembly
    tree.
    """

    import subprocess

    freecad_exe = freecad_cmd or _discover_freecad_executable()
    if not freecad_exe:
        raise_harness_error(
            operation="translate_model_json_to_fcstd",
            what_happened="Could not locate a FreeCAD command-line executable.",
            possible_causes=[
                "FreeCADCmd is not installed or not available on PATH.",
                "Only the GUI app is installed and no CLI entrypoint is reachable.",
            ],
            how_to_fix=[
                "Install FreeCAD with FreeCADCmd, or pass freecad_cmd=... explicitly.",
                "Make sure FreeCADCmd or FreeCAD is on PATH.",
            ],
            error=FileNotFoundError("FreeCADCmd/FreeCAD not found"),
        )

    script = translate_model_json_to_freecad_script(
        json_str, document_name=document_name
    )
    resolved_output_path = os.path.abspath(output_path)
    save_tail = (
        f"\nOUTPUT_PATH = {_json_ascii(resolved_output_path)}\n"
        "_apply_result_visibility(RESULT_NODE_IDS)\n"
        "_set_active_result_object(RESULT_NODE_IDS)\n"
        "_save_fcstd_with_gui_visibility(OUTPUT_PATH)\n"
        "print(OUTPUT_PATH)\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_simplecad_freecad_export.py", delete=False
    ) as handle:
        temp_script_path = handle.name
        handle.write(script)
        handle.write(save_tail)

    try:
        completed = subprocess.run(
            [freecad_exe, temp_script_path],
            check=True,
            text=True,
            capture_output=True,
        )
        if not os.path.exists(resolved_output_path) or os.path.getsize(resolved_output_path) <= 0:
            raise RuntimeError(
                "FreeCAD export completed without creating a non-empty .FCStd file. "
                f"stderr={completed.stderr.strip()!r}"
            )
        return output_path
    except Exception as e:
        raise_harness_error(
            operation="translate_model_json_to_fcstd",
            what_happened="Failed to execute the generated FreeCAD export script.",
            possible_causes=[
                "FreeCADCmd started but the generated script hit an unsupported API call.",
                "The output path is invalid or not writable.",
                "The installed FreeCAD build lacks Part or Spreadsheet support needed by the translator.",
            ],
            how_to_fix=[
                "Inspect the generated script first with translate_model_json_to_freecad_script().",
                "Use a writable .FCStd output path.",
                "Run the same script manually inside a matching FreeCAD environment to isolate runtime differences.",
            ],
            error=e,
        )
