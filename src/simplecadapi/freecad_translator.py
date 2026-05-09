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
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
    "make_cut_rsolidlist": (),
    "make_union_rsolid": (),
    "make_intersect_rsolidlist": (),
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
        "Canonical function-fit spline expressions have no stable equivalent native "
        "FreeCAD BSpline parameter host. The translator exports spline geometry, but "
        "does not map make_spline_redge param_exprs into FreeCAD ExpressionEngine."
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
        emit("")
        emit(f"DOC_NAME = {_json_ascii(self.document_name)}")
        emit(
            "doc = App.getDocument(DOC_NAME) if DOC_NAME in App.listDocuments() else App.newDocument(DOC_NAME)"
        )
        emit("GRAPH_NODES = {}")
        emit("GRAPH_OUTPUTS = {}")
        emit("GRAPH_METADATA = {}")
        emit("GRAPH_LIMITATIONS = {}")
        emit("PART_REGISTRY = {}")
        emit("SKETCH_REGISTRY = []")
        emit("CONSTRAINT_REGISTRY = []")
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

        assembly_payload = payload.get("assembly")
        if isinstance(assembly_payload, dict):
            for line in self._emit_assembly(assembly_payload, payload):
                emit(line)
            emit("")

        emit("doc.recompute()")
        emit("")
        emit("# Leaf/result metadata")
        leaf_ids = payload.get("leaf_ids")
        if isinstance(leaf_ids, list) and leaf_ids:
            emit(f"RESULT_NODE_IDS = {_py_literal([str(v) for v in leaf_ids])}")
        else:
            emit(
                f"RESULT_NODE_IDS = {_py_literal([leaf.node_id for leaf in source_graph.leaf_nodes()])}"
            )
        emit(
            "RESULT_OBJECTS = [obj for node_id in RESULT_NODE_IDS for obj in GRAPH_OUTPUTS.get(node_id, [])]"
        )
        emit("_apply_result_visibility(RESULT_NODE_IDS)")
        emit("doc.TransientDir = getattr(doc, 'TransientDir', '')")
        return "\n".join(lines).rstrip() + "\n"

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

    def _script_helpers(self) -> str:
        return """
class SimpleCADUnsupportedOpError(RuntimeError):
    pass


def _ensure_string_property(obj, prop_name, group='SimpleCAD'):
    if not hasattr(obj, prop_name):
        obj.addProperty('App::PropertyString', prop_name, group)


def _ensure_string_list_property(obj, prop_name, group='SimpleCAD'):
    if not hasattr(obj, prop_name):
        obj.addProperty('App::PropertyStringList', prop_name, group)


def _ensure_string_map_property(obj, prop_name, group='SimpleCAD'):
    if not hasattr(obj, prop_name):
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


def _node_object(node_id, index=0):
    node_value = GRAPH_NODES.get(node_id)
    if node_value is not None and not hasattr(node_value, 'Shape'):
        raise RuntimeError(f'Graph node {node_id!r} stores a non-document value, not a FreeCAD object')
    outputs = GRAPH_OUTPUTS.get(node_id, [])
    if not outputs:
        raise RuntimeError(f'Missing graph output object for node {node_id!r}')
    idx = int(index)
    if idx < 0 or idx >= len(outputs):
        raise RuntimeError(f'Output object slot {idx} missing for node {node_id!r}')
    return outputs[idx]


def _set_visibility(obj, visible):
    try:
        view = getattr(obj, 'ViewObject', None)
        if view is not None and hasattr(view, 'Visibility'):
            view.Visibility = bool(visible)
            return
    except Exception:
        pass
    try:
        if hasattr(obj, 'Visibility'):
            obj.Visibility = bool(visible)
    except Exception:
        pass


def _apply_result_visibility(result_node_ids):
    visible_ids = {str(node_id) for node_id in (result_node_ids or [])}
    for node_id, outputs in GRAPH_OUTPUTS.items():
        is_visible = str(node_id) in visible_ids
        for obj in outputs:
            _set_visibility(obj, is_visible)


def _vec(v):
    return App.Vector(float(v[0]), float(v[1]), float(v[2]))


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
    if hasattr(value, 'Shape'):
        shape = getattr(value, 'Shape', None)
    else:
        shape = value
    if shape is None or shape.isNull():
        raise RuntimeError(f'Graph node {node_id!r} has no valid shape')
    return shape


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


def _select_fit_samples(points, target_count=6):
    pts = [tuple(float(v) for v in point) for point in points]
    if len(pts) <= 2 or target_count <= 2 or len(pts) <= target_count:
        return pts
    result = [pts[0]]
    interior_count = int(target_count) - 2
    last_index = len(pts) - 1
    for i in range(1, interior_count + 1):
        idx = round(i * last_index / (interior_count + 1))
        idx = max(1, min(last_index - 1, int(idx)))
        result.append(pts[idx])
    result.append(pts[-1])
    deduped = []
    for point in result:
        if not deduped or point != deduped[-1]:
            deduped.append(point)
    return deduped if len(deduped) >= 2 else pts[:2]


def _fit_bspline_curve(points, target_count=6):
    selected = _select_fit_samples(points, target_count)
    return Part.BSplineCurve([_vec(point) for point in selected])


def _interpolate_bspline_curve(points, target_count=6):
    selected = _select_fit_samples(points, target_count)
    curve = Part.BSplineCurve()
    curve.interpolate([_vec(point) for point in selected])
    return curve


def _wire_shape_from_edge_objects(node_ids):
    shapes = []
    for node_id in node_ids:
        shape = _shape_from_graph_node(node_id)
        shapes.append(shape)
    return Part.Wire(shapes)


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


def _make_native_assembly(name):
    if Assembly is None:
        return None
    assembly = doc.addObject('Assembly::AssemblyObject', name)
    if hasattr(assembly, 'Type'):
        assembly.Type = 'Assembly'
    assembly.newObject('Assembly::JointGroup', 'Joints')
    return assembly


def _make_native_joint(assembly, joint_name, joint_kind, payload):
    if assembly is None or JointObject is None:
        return None
    joint_group = None
    for obj in getattr(assembly, 'OutList', []):
        if getattr(obj, 'TypeId', '') == 'Assembly::JointGroup':
            joint_group = obj
            break
    if joint_group is None:
        joint_group = assembly.newObject('Assembly::JointGroup', 'Joints')
    joint = joint_group.newObject('App::FeaturePython', joint_name)
    joint_type_index = {
        'coincident': 0,
        'concentric': 1,
        'offset': 5,
        'distance': 5,
    }.get(str(joint_kind).lower(), 0)
    JointObject.Joint(joint, joint_type_index)
    if hasattr(joint, 'Distance') and 'distance' in payload:
        try:
            joint.Distance = float(payload['distance'])
        except Exception:
            pass
        _bind_expression(joint, 'Distance', payload.get('distance_expr'))
    if hasattr(joint, 'Angle') and 'angle' in payload:
        try:
            joint.Angle = float(payload['angle'])
        except Exception:
            pass
        _bind_expression(joint, 'Angle', payload.get('angle_expr'))
    return joint


def _point_anchor_placement(anchor):
    point = anchor.get('local_point', [0.0, 0.0, 0.0])
    return App.Placement(_vec(point), App.Rotation())


def _axis_anchor_placement(anchor):
    point = anchor.get('local_point', [0.0, 0.0, 0.0])
    direction = anchor.get('local_direction', [0.0, 0.0, 1.0])
    z_axis = App.Vector(float(direction[0]), float(direction[1]), float(direction[2]))
    rotation = App.Rotation(App.Vector(0.0, 0.0, 1.0), z_axis)
    return App.Placement(_vec(point), rotation)


def _joint_reference_from_anchor(anchor):
    if not isinstance(anchor, dict):
        return None
    part_name = anchor.get('part')
    if not part_name:
        return None
    part_obj = PART_REGISTRY.get(str(part_name))
    if part_obj is None:
        return None
    return (part_obj, [])
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
                f"{var_name} = _register_graph_value(Part.BSplineCurve([_vec(point) for point in _select_fit_samples({rp}['points'], 6)]).toShape(), node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
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
                            f"{var_name}.addGeometry(_fit_bspline_curve([tuple(_local_point_on_frame(point, {var_name}_origin, {var_name}_xaxis, {var_name}_yaxis)) for point in {edge_var}_params['points']], 6), False)"
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
                lines.append(
                    f"GRAPH_LIMITATIONS[{_json_ascii(node.node_id)}] = {{'op': {_json_ascii(node.op)}, 'reason': json.dumps({var_name}_expr_limitations, ensure_ascii=True, sort_keys=True)}} if {var_name}_expr_limitations else GRAPH_LIMITATIONS.get({_json_ascii(node.node_id)})"
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
                        f"{var_name}.addGeometry(_fit_bspline_curve({spline_var}_params['points'], 6), False)",
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
            if base_node is not None and base_node.op in {
                "make_face_from_wire_rface",
                "make_wire_from_edges_rwire",
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
                f"{var_name}.Spine = GRAPH_NODES[{_json_ascii(inputs[1])}]",
                f"{var_name}.Solid = True",
                f"{var_name}.Frenet = bool(_resolve_param_value({rp}, {re}, 'is_frenet') if 'is_frenet' in {rp} else False)",
            ]
            lines.append(
                f"_apply_op_expression_bindings({var_name}, {_json_ascii(node.op)}, {re})"
            )
            lines.extend(finish())
            return lines

        if node.op == "make_cut_rsolidlist" and len(inputs) >= 2:
            lines: List[str]
            if len(inputs) == 2:
                lines = [
                    f"{var_name} = doc.addObject('Part::Cut', {_json_ascii(object_name)})",
                    f"{var_name}.Base = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                    f"{var_name}.Tool = GRAPH_NODES[{_json_ascii(inputs[1])}]",
                ]
            else:
                tool_var = f"{var_name}_tools"
                lines = [
                    f"{tool_var} = doc.addObject('Part::MultiFuse', {_json_ascii(_safe_name(f'{object_name}_tools', prefix='tools'))})",
                    f"{tool_var}.Shapes = [GRAPH_NODES[node_id] for node_id in {var_name}_inputs[1:]]",
                    f"_set_visibility({tool_var}, False)",
                    f"{var_name} = doc.addObject('Part::Cut', {_json_ascii(object_name)})",
                    f"{var_name}.Base = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                    f"{var_name}.Tool = {tool_var}",
                ]
            lines.extend(finish())
            return lines

        if node.op == "make_union_rsolid" and len(inputs) >= 2:
            if len(inputs) == 2:
                lines = [
                    f"{var_name} = doc.addObject('Part::Fuse', {_json_ascii(object_name)})",
                    f"{var_name}.Base = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                    f"{var_name}.Tool = GRAPH_NODES[{_json_ascii(inputs[1])}]",
                ]
            else:
                lines = [
                    f"{var_name} = doc.addObject('Part::MultiFuse', {_json_ascii(object_name)})",
                    f"{var_name}.Shapes = [GRAPH_NODES[node_id] for node_id in {var_name}_inputs]",
                ]
            lines.extend(finish())
            return lines

        if node.op == "make_intersect_rsolidlist" and len(inputs) >= 2:
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

        if node.op == "make_fillet_rsolid" and len(inputs) == 1:
            lines = [
                f"{var_name} = doc.addObject('Part::Fillet', {_json_ascii(object_name)})",
                f"{var_name}.Base = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                f"{var_name}.Edges = [(int(idx) + 1, float(_resolve_param_value({rp}, {re}, 'radius')), float(_resolve_param_value({rp}, {re}, 'radius'))) for idx in {rp}.get('selected_edge_indices', [])]",
            ]
            lines.append(f"_apply_detail_feature_bindings({var_name}, {re}, 'radius')")
            lines.extend(finish())
            return lines

        if node.op == "make_chamfer_rsolid" and len(inputs) == 1:
            lines = [
                f"{var_name} = doc.addObject('Part::Chamfer', {_json_ascii(object_name)})",
                f"{var_name}.Base = GRAPH_NODES[{_json_ascii(inputs[0])}]",
                f"{var_name}.Edges = [(int(idx) + 1, float(_resolve_param_value({rp}, {re}, 'distance')), float(_resolve_param_value({rp}, {re}, 'distance'))) for idx in {rp}.get('selected_edge_indices', [])]",
            ]
            lines.append(
                f"_apply_detail_feature_bindings({var_name}, {re}, 'distance')"
            )
            lines.extend(finish())
            return lines

        if node.op == "make_shell_rsolid" and len(inputs) == 1:
            lines = [
                f"{var_name} = doc.addObject('Part::Thickness', {_json_ascii(object_name)})",
                f"{var_name}.Value = float(_resolve_param_value({rp}, {re}, 'thickness'))",
            ]
            lines.append(
                f"_apply_op_expression_bindings({var_name}, {_json_ascii(node.op)}, {re})"
            )
            if node.params.get("selected_face_indices"):
                face_name_expr = f"['Face' + str(int(i) + 1) for i in {rp}.get('selected_face_indices', [])]"
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
                    if all(abs(float(v)) <= 1e-12 for v in vector):
                        return finish_alias(inputs[0])
                except Exception:
                    pass
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

    def _emit_assembly(
        self, assembly_payload: Dict[str, Any], payload: Dict[str, Any]
    ) -> List[str]:
        lines: List[str] = ["# Assembly + constraint metadata"]
        asm_name = str(assembly_payload.get("name", "assembly"))
        parts = assembly_payload.get("parts", [])
        constraints = assembly_payload.get("constraints") or assembly_payload.get(
            "constraint_param_exprs", []
        )
        lines.append(
            f"native_assembly = _make_native_assembly({_json_ascii(_safe_name(f'assembly_{asm_name}', prefix='asm'))})"
        )
        lines.append(
            f"assembly_meta = _make_metadata_note({_json_ascii(_safe_name(f'assembly_{asm_name}_meta', prefix='asm'))}, {_json_ascii('SimpleCAD Assembly')}, {_py_literal({'name': asm_name, 'parts': parts})})"
        )
        lines.append("_ensure_string_list_property(assembly_meta, 'PartNames')")
        lines.append(
            f"assembly_meta.PartNames = {[str(part.get('name')) for part in parts]!r}"
        )

        for idx, part in enumerate(parts):
            part_name = str(part.get("name", f"part_{idx}"))
            note_name = _safe_name(
                f"assembly_part_{asm_name}_{part_name}", prefix="part"
            )
            lines.append(
                f"assembly_part_{idx} = native_assembly.newObject('App::Part', {_json_ascii(_safe_name(part_name, prefix='part'))}) if native_assembly is not None else None"
            )
            lines.append(
                f"PART_REGISTRY[{_json_ascii(part_name)}] = assembly_part_{idx}"
            )
            lines.append(
                f"_make_metadata_note({_json_ascii(note_name)}, {_json_ascii('SimpleCAD Assembly Part')}, {_py_literal(part)})"
            )

        for idx, constraint in enumerate(
            constraints if isinstance(constraints, list) else []
        ):
            note_name = _safe_name(f"constraint_{asm_name}_{idx}", prefix="constraint")
            lines.append(
                f"constraint_note_{idx} = _make_metadata_note({_json_ascii(note_name)}, {_json_ascii('SimpleCAD Constraint')}, {_py_literal(constraint)})"
            )
            lines.append(
                "_ensure_string_property(constraint_note_{0}, 'ConstraintType')".format(
                    idx
                )
            )
            lines.append(
                f"constraint_note_{idx}.ConstraintType = {_json_ascii(str(constraint.get('type', 'constraint')))}"
            )
            lines.append(
                f"native_joint_{idx} = _make_native_joint(native_assembly, {_json_ascii(f'Joint_{idx}')}, {_json_ascii(str(constraint.get('type', 'constraint')))}, {_py_literal(constraint)})"
            )
            reference = (
                constraint.get("reference") if isinstance(constraint, dict) else None
            )
            moving = constraint.get("moving") if isinstance(constraint, dict) else None
            if isinstance(reference, dict):
                lines.append(
                    f"native_joint_{idx}.Reference1 = _joint_reference_from_anchor({_py_literal(reference)}) if native_joint_{idx} is not None and hasattr(native_joint_{idx}, 'Reference1') else None"
                )
                if reference.get("kind") == "axis":
                    lines.append(
                        f"native_joint_{idx}.Placement1 = _axis_anchor_placement({_py_literal(reference)}) if native_joint_{idx} is not None and hasattr(native_joint_{idx}, 'Placement1') else None"
                    )
                else:
                    lines.append(
                        f"native_joint_{idx}.Placement1 = _point_anchor_placement({_py_literal(reference)}) if native_joint_{idx} is not None and hasattr(native_joint_{idx}, 'Placement1') else None"
                    )
            if isinstance(moving, dict):
                lines.append(
                    f"native_joint_{idx}.Reference2 = _joint_reference_from_anchor({_py_literal(moving)}) if native_joint_{idx} is not None and hasattr(native_joint_{idx}, 'Reference2') else None"
                )
                if moving.get("kind") == "axis":
                    lines.append(
                        f"native_joint_{idx}.Placement2 = _axis_anchor_placement({_py_literal(moving)}) if native_joint_{idx} is not None and hasattr(native_joint_{idx}, 'Placement2') else None"
                    )
                else:
                    lines.append(
                        f"native_joint_{idx}.Placement2 = _point_anchor_placement({_py_literal(moving)}) if native_joint_{idx} is not None and hasattr(native_joint_{idx}, 'Placement2') else None"
                    )
            lines.append(f"CONSTRAINT_REGISTRY.append(constraint_note_{idx})")

        expr_graph = assembly_payload.get("expression_graph")
        if isinstance(expr_graph, dict):
            lines.append(
                f"_make_metadata_note({_json_ascii(_safe_name(f'assembly_expr_{asm_name}', prefix='expr'))}, {_json_ascii('SimpleCAD Assembly Expression Graph')}, {_py_literal(expr_graph)})"
            )
        return lines


def translate_model_json_to_freecad_script(
    json_str: str,
    document_name: str = "SimpleCADModel",
) -> str:
    """Translate exported model JSON into a FreeCAD Python script."""

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
    """Translate canonical model JSON to `.FCStd` via FreeCADCmd/FreeCAD."""

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
    save_tail = (
        f"\nOUTPUT_PATH = {_json_ascii(output_path)}\n"
        "doc.recompute()\n"
        "doc.saveAs(OUTPUT_PATH)\n"
        "print(OUTPUT_PATH)\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_simplecad_freecad_export.py", delete=False
    ) as handle:
        temp_script_path = handle.name
        handle.write(script)
        handle.write(save_tail)

    try:
        subprocess.run(
            [freecad_exe, temp_script_path],
            check=True,
            text=True,
            capture_output=True,
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
