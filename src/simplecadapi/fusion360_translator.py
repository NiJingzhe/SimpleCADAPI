"""Translate SimpleCAD model/graph payloads into Autodesk Fusion 360 scripts.

Generated scripts are intended to run inside Fusion 360's Python environment.
They interpret the same canonical low-level graph consumed by
``freecad_translator.py`` and intentionally select detail-feature edges/faces by
geometry signatures instead of topology indices.
"""

from __future__ import annotations

import json
import pprint
from typing import Any, Dict, List, Optional, Sequence, Set

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


class Fusion360ScriptTranslator:
    """Compile a SimpleCAD model payload into a Fusion 360 Python script."""

    def __init__(self, document_name: str = "SimpleCADModel") -> None:
        self.document_name = document_name
        self._source_graph: Optional[OperationGraph] = None
        self._result_node_ids: Set[str] = set()
        self._result_node_id_list: List[str] = []

    def translate_model_json_to_script(self, json_str: str) -> str:
        payload = import_model_json(json_str)
        graph = payload.get("graph")
        if not isinstance(graph, OperationGraph):
            raise ValueError(
                "Fusion 360 translation requires model JSON with a canonical low-level graph"
            )
        if graph.node_count == 0:
            raise ValueError(
                "Fusion 360 translation requires model JSON with a non-empty canonical low-level graph"
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
                "Fusion 360 translation requires payload to contain a canonical low-level graph"
            )
        if source_graph.node_count == 0:
            raise ValueError(
                "Fusion 360 translation requires payload to contain a non-empty canonical low-level graph"
            )
        self._source_graph = source_graph
        leaf_ids = payload.get("leaf_ids")
        if isinstance(leaf_ids, list) and leaf_ids:
            self._result_node_id_list = [str(v) for v in leaf_ids]
        else:
            self._result_node_id_list = [leaf.node_id for leaf in source_graph.leaf_nodes()]
        self._result_node_ids = set(self._result_node_id_list)

        payload_dict = self._payload_to_jsonable(payload, source_graph)
        lines: List[str] = []
        emit = lines.append
        emit("import json")
        emit("import math")
        emit("import traceback")
        emit("import adsk.core")
        emit("import adsk.fusion")
        emit("")
        emit(f"DOC_NAME = {_json_ascii(self.document_name)}")
        emit(f"MODEL_PAYLOAD = {_py_literal(payload_dict)}")
        emit(f"RESULT_NODE_IDS = {_py_literal(self._result_node_id_list)}")
        emit("")
        emit(self._script_helpers())
        emit("")
        emit("def run(context):")
        emit("    app = adsk.core.Application.get()")
        emit("    ui = app.userInterface if app else None")
        emit("    try:")
        emit("        translator = SimpleCADFusionRuntime(MODEL_PAYLOAD, DOC_NAME, RESULT_NODE_IDS)")
        emit("        translator.run()")
        emit("    except Exception:")
        emit("        message = traceback.format_exc()")
        emit("        if ui:")
        emit("            ui.messageBox(message)")
        emit("        else:")
        emit("            print(message)")
        emit("        raise")
        emit("")
        emit("if __name__ == '__main__':")
        emit("    run(None)")
        return "\n".join(lines).rstrip() + "\n"

    def _payload_to_jsonable(
        self, payload: Dict[str, Any], source_graph: OperationGraph
    ) -> Dict[str, Any]:
        # Fusion scripts do not need the full model payload. Keeping only the
        # executable graph surface also prevents stale topology-index hints from
        # appearing in generated Fusion scripts.
        nodes: List[Dict[str, Any]] = []
        for node in source_graph.topological_order():
            nodes.append(
                {
                    "node_id": str(node.node_id),
                    "op": str(node.op),
                    "params": self._sanitize_payload_for_fusion(dict(node.params)),
                    "inputs": [
                        {"node_id": str(input_ref.node_id)}
                        for input_ref in node.inputs
                    ],
                }
            )
        return {
            "schema_version": str(payload.get("schema_version", "2.0")),
            "graph": {
                "graph_id": str(getattr(source_graph, "graph_id", "graph")),
                "nodes": nodes,
            },
            "leaf_ids": [str(v) for v in payload.get("leaf_ids", [])],
        }

    def _sanitize_payload_for_fusion(self, value: Any) -> Any:
        if isinstance(value, dict):
            cleaned: Dict[str, Any] = {}
            for key, child in value.items():
                if key in {
                    "selected_edge_indices",
                    "selected_face_indices",
                    "edge_index_param",
                    "face_index_param",
                    "topo_id",
                }:
                    continue
                if key == "metadata_geo":
                    child_cleaned = self._sanitize_payload_for_fusion(child)
                    if isinstance(child_cleaned, dict):
                        child_cleaned = {
                            k: v for k, v in child_cleaned.items() if k != "edge_index"
                        }
                    if child_cleaned:
                        cleaned[key] = child_cleaned
                    continue
                cleaned[key] = self._sanitize_payload_for_fusion(child)
            return cleaned
        if isinstance(value, (list, tuple)):
            return [self._sanitize_payload_for_fusion(item) for item in value]
        return value

    def _script_helpers(self) -> str:
        return r'''
SCALE = 0.1  # SimpleCAD model JSON is in mm; Fusion API geometry units are cm.
TOL = 1.0e-5


class SimpleCADUnsupportedOpError(RuntimeError):
    pass


def _flatten(values):
    for value in values:
        if isinstance(value, (list, tuple)):
            yield from _flatten(value)
        else:
            yield value


def _v3(value, default=(0.0, 0.0, 0.0)):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        value = default
    return (float(value[0]), float(value[1]), float(value[2]))


def _scaled(value):
    x, y, z = _v3(value)
    return (x * SCALE, y * SCALE, z * SCALE)


def _pt(value):
    x, y, z = _scaled(value)
    return adsk.core.Point3D.create(x, y, z)


def _vec(value):
    x, y, z = _v3(value)
    return adsk.core.Vector3D.create(x, y, z)


def _vec_scaled(value):
    x, y, z = _scaled(value)
    return adsk.core.Vector3D.create(x, y, z)


def _distance(a, b):
    ax, ay, az = _v3(a)
    bx, by, bz = _v3(b)
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)


def _dot(a, b):
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _cross(a, b):
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a, fallback=(0.0, 0.0, 1.0)):
    length = _norm(a)
    if length <= 1.0e-12:
        return _v3(fallback)
    return (float(a[0]) / length, float(a[1]) / length, float(a[2]) / length)


def _add(a, b):
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


def _sub(a, b):
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _mul(a, scalar):
    return (float(a[0]) * scalar, float(a[1]) * scalar, float(a[2]) * scalar)


def _bbox_tuple(box):
    return {
        'min': (box.minPoint.x / SCALE, box.minPoint.y / SCALE, box.minPoint.z / SCALE),
        'max': (box.maxPoint.x / SCALE, box.maxPoint.y / SCALE, box.maxPoint.z / SCALE),
    }


def _bbox_center(bbox):
    return tuple((float(bbox['min'][i]) + float(bbox['max'][i])) * 0.5 for i in range(3))


def _bbox_score(candidate_bbox, selector_bbox):
    if not isinstance(selector_bbox, dict):
        return 0.0
    score = 0.0
    for key in ('min', 'max'):
        if key not in selector_bbox:
            continue
        target = selector_bbox[key]
        actual = candidate_bbox[key]
        score += sum((float(actual[i]) - float(target[i])) ** 2 for i in range(3))
    return score


def _object_collection(items=None):
    collection = adsk.core.ObjectCollection.create()
    for item in items or []:
        collection.add(item)
    return collection


def _iter_collection(collection):
    for item in collection:
        yield item


def _first_entity(collection, label):
    for item in _iter_collection(collection):
        return item
    raise RuntimeError(f'Expected at least one {label}')


def _value_cm(mm_value):
    return adsk.core.ValueInput.createByReal(float(mm_value) * SCALE)


def _value_deg(degrees):
    return adsk.core.ValueInput.createByReal(math.radians(float(degrees)))


def _curve_points_on_edge(edge):
    ev = edge.evaluator
    ok, start_param, end_param = ev.getParameterExtents()
    if not ok:
        return None
    ok, start_pt = ev.getPointAtParameter(start_param)
    if not ok:
        return None
    ok, end_pt = ev.getPointAtParameter(end_param)
    if not ok:
        return None
    ok, mid_pt = ev.getPointAtParameter((start_param + end_param) * 0.5)
    if not ok:
        mid_pt = start_pt
    return (
        (start_pt.x / SCALE, start_pt.y / SCALE, start_pt.z / SCALE),
        (mid_pt.x / SCALE, mid_pt.y / SCALE, mid_pt.z / SCALE),
        (end_pt.x / SCALE, end_pt.y / SCALE, end_pt.z / SCALE),
    )


def _edge_length(edge):
    try:
        ok, length = edge.evaluator.getLengthAtParameter(
            edge.evaluator.getParameterExtents()[1],
            edge.evaluator.getParameterExtents()[2],
        )
        if ok:
            return float(length) / SCALE
    except Exception:
        pass
    pts = _curve_points_on_edge(edge)
    if not pts:
        return 0.0
    return _distance(pts[0], pts[2])


def _edge_signature(edge):
    bbox = _bbox_tuple(edge.boundingBox)
    pts = _curve_points_on_edge(edge)
    center = _bbox_center(bbox)
    geom_type = str(getattr(edge.geometry, 'objectType', '')).upper()
    return {
        'bbox': bbox,
        'center': center,
        'start': pts[0] if pts else center,
        'end': pts[2] if pts else center,
        'length': _edge_length(edge),
        'geom_type': geom_type,
    }


def _face_signature(face):
    bbox = _bbox_tuple(face.boundingBox)
    center = _bbox_center(bbox)
    geom_type = str(getattr(face.geometry, 'objectType', '')).upper()
    return {
        'bbox': bbox,
        'center': center,
        'area': float(getattr(face, 'area', 0.0)) / (SCALE * SCALE),
        'geom_type': geom_type,
    }


def _face_normal_tuple(face):
    try:
        geometry = face.geometry
        normal = getattr(geometry, 'normal', None)
        if normal is not None:
            return _unit((normal.x, normal.y, normal.z))
    except Exception:
        pass
    try:
        evaluator = face.evaluator
        point = face.pointOnFace
        ok, parameter = evaluator.getParameterAtPoint(point)
        if ok:
            ok, normal = evaluator.getNormalAtParameter(parameter)
            if ok:
                return _unit((normal.x, normal.y, normal.z))
    except Exception:
        pass
    return None


def _geom_score(sig, selector):
    params = selector.get('params') if isinstance(selector, dict) else None
    if isinstance(params, dict):
        selector = params
    score = 0.0
    geo_selector = selector.get('geo_selector') if isinstance(selector, dict) else None
    if isinstance(geo_selector, dict):
        score += _bbox_score(sig.get('bbox', {}), geo_selector.get('bbox')) * 20.0
    if isinstance(selector.get('bbox'), dict):
        score += _bbox_score(sig.get('bbox', {}), selector.get('bbox')) * 20.0
    if isinstance(selector.get('center'), (list, tuple)):
        score += _distance(sig.get('center', (0, 0, 0)), selector['center']) ** 2
    if isinstance(selector.get('start'), (list, tuple)) and isinstance(selector.get('end'), (list, tuple)):
        c_start = sig.get('start', (0, 0, 0))
        c_end = sig.get('end', (0, 0, 0))
        same = _distance(c_start, selector['start']) + _distance(c_end, selector['end'])
        reverse = _distance(c_start, selector['end']) + _distance(c_end, selector['start'])
        score += min(same, reverse) ** 2
    if selector.get('length') is not None and sig.get('length') is not None:
        score += (float(sig['length']) - float(selector['length'])) ** 2
    if selector.get('area') is not None and sig.get('area') is not None:
        score += (float(sig['area']) - float(selector['area'])) ** 2
    target_type = str(selector.get('geom_type') or selector.get('surface_type') or '').upper()
    if target_type and target_type not in str(sig.get('geom_type', '')).upper():
        score += 1.0e6
    return score


def _best_by_geometry(candidates, selector, signature_fn, label):
    if not candidates:
        raise RuntimeError(f'No {label} candidates available for geometry selection')
    ranked = sorted(((candidate, _geom_score(signature_fn(candidate), selector)) for candidate in candidates), key=lambda item: item[1])
    best, score = ranked[0]
    # The threshold is intentionally loose enough to tolerate Fusion kernel edge splitting
    # while still rejecting wildly different topology.
    if score > 1.0e5:
        raise RuntimeError(f'Geometry selector did not match a stable {label}; best score={score}')
    return best


def _matrix_translate(vector):
    matrix = adsk.core.Matrix3D.create()
    matrix.translation = _vec_scaled(vector)
    return matrix


def _matrix_rotate(origin, axis, angle_degrees):
    matrix = adsk.core.Matrix3D.create()
    matrix.setToRotation(math.radians(float(angle_degrees)), _vec(axis), _pt(origin))
    return matrix


def _matrix_mirror(plane_origin, plane_normal):
    normal = _unit(_v3(plane_normal))
    nx, ny, nz = normal
    px, py, pz = _scaled(plane_origin)
    d = -(nx * px + ny * py + nz * pz)
    cells = [
        1 - 2 * nx * nx, -2 * nx * ny, -2 * nx * nz, -2 * d * nx,
        -2 * ny * nx, 1 - 2 * ny * ny, -2 * ny * nz, -2 * d * ny,
        -2 * nz * nx, -2 * nz * ny, 1 - 2 * nz * nz, -2 * d * nz,
        0, 0, 0, 1,
    ]
    matrix = adsk.core.Matrix3D.create()
    matrix.setWithArray(cells)
    return matrix


def _arc_midpoint(center, radius, start_angle, end_angle, normal=(0.0, 0.0, 1.0)):
    # SimpleCAD's angle arcs are authored in the XY plane, then oriented by normal.
    angle = (float(start_angle) + float(end_angle)) * 0.5
    return (float(center[0]) + float(radius) * math.cos(angle), float(center[1]) + float(radius) * math.sin(angle), float(center[2]))


def _arc_endpoint(center, radius, angle):
    return (float(center[0]) + float(radius) * math.cos(float(angle)), float(center[1]) + float(radius) * math.sin(float(angle)), float(center[2]))


def _three_point_circle(start, middle, end):
    ax, ay, az = _v3(start)
    bx, by, bz = _v3(middle)
    cx, cy, cz = _v3(end)
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) <= 1.0e-12:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    center = (ux, uy, az)
    return center, _distance(center, start)


def _placement_payload_origin(payload):
    if not isinstance(payload, dict):
        return (0.0, 0.0, 0.0)
    return _v3(payload.get('origin') or payload.get('base') or (0.0, 0.0, 0.0))


def _apply_name(entity, name):
    try:
        entity.name = str(name)
    except Exception:
        pass
    return entity


class SimpleCADFusionRuntime:
    def __init__(self, payload, document_name, result_node_ids):
        self.payload = payload
        self.graph = payload.get('graph') or {}
        self.nodes = self.graph.get('nodes') or []
        self.node_by_id = {str(node.get('node_id')): node for node in self.nodes}
        self.document_name = document_name
        self.result_node_ids = [str(v) for v in (result_node_ids or [])]
        self.outputs = {}
        self.product_values = {}
        self.selection_payloads = {}
        self.tmp = adsk.fusion.TemporaryBRepManager.get()
        self.app = adsk.core.Application.get()
        self.design = None
        self.root = None
        self.base_feature = None
        self.logs = []

    def run(self):
        self._prepare_document()
        for node in self.nodes:
            self._emit_node(node)
        self._materialize_results()
        print('SimpleCAD Fusion translation complete', self.document_name, 'nodes', len(self.nodes))
        if self.logs:
            print('\n'.join(self.logs))

    def _prepare_document(self):
        documents = self.app.documents
        doc = documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        try:
            doc.name = self.document_name
        except Exception:
            pass
        self.design = adsk.fusion.Design.cast(self.app.activeProduct)
        if self.design is None:
            raise RuntimeError('Active Fusion product is not a Design')
        try:
            self.design.designType = adsk.fusion.DesignTypes.DirectDesignType
        except Exception:
            pass
        self.root = self.design.rootComponent

    def _input_ids(self, node):
        return [str(ref.get('node_id')) for ref in (node.get('inputs') or []) if isinstance(ref, dict)]

    def _first_output(self, node_id):
        outputs = self.outputs.get(str(node_id)) or []
        if not outputs:
            raise RuntimeError(f'Missing graph output for {node_id}')
        return outputs[0]

    def _body_copy(self, body):
        return self.tmp.copy(body)

    def _delete_entity(self, entity):
        if entity is None:
            return
        try:
            if hasattr(entity, 'isValid') and not entity.isValid:
                return
        except Exception:
            pass
        try:
            entity.deleteMe()
        except Exception:
            pass

    def _copy_first_feature_body_and_cleanup(self, feature, label, cleanup=None):
        feature_bodies = []
        try:
            feature_bodies = [body for body in feature.bodies]
        except Exception:
            feature_bodies = []
        if not feature_bodies:
            raise RuntimeError(f'Expected at least one {label}')
        body = self.tmp.copy(feature_bodies[0])
        for old in feature_bodies:
            self._delete_entity(old)
        for old in cleanup or []:
            self._delete_entity(old)
        return body

    def _set_output(self, node, values):
        node_id = str(node.get('node_id'))
        if not isinstance(values, list):
            values = [values]
        self.outputs[node_id] = values
        return values

    def _emit_node(self, node):
        op = str(node.get('op'))
        params = node.get('params') or {}
        node_id = str(node.get('node_id'))
        inputs = self._input_ids(node)
        name = _safe_label(op, node_id)
        if op == 'make_line_redge':
            curve = adsk.core.Line3D.create(_pt(params.get('start')), _pt(params.get('end')))
            return self._set_output(node, curve)
        if op == 'make_circle_redge':
            center = _pt(params.get('center'))
            normal = _vec(params.get('normal') or (0.0, 0.0, 1.0))
            curve = adsk.core.Circle3D.createByCenter(center, normal, float(params.get('radius', 0.0)) * SCALE)
            return self._set_output(node, curve)
        if op == 'make_angle_arc_redge':
            center = params.get('center') or (0.0, 0.0, 0.0)
            radius = float(params.get('radius', 0.0))
            start = _arc_endpoint(center, radius, params.get('start_angle', 0.0))
            middle = _arc_midpoint(center, radius, params.get('start_angle', 0.0), params.get('end_angle', 0.0), params.get('normal') or (0, 0, 1))
            end = _arc_endpoint(center, radius, params.get('end_angle', 0.0))
            curve = adsk.core.Arc3D.createByThreePoints(_pt(start), _pt(middle), _pt(end))
            return self._set_output(node, curve)
        if op == 'make_three_point_arc_redge':
            curve = adsk.core.Arc3D.createByThreePoints(_pt(params.get('start')), _pt(params.get('middle')), _pt(params.get('end')))
            return self._set_output(node, curve)
        if op == 'make_spline_redge':
            points = params.get('points') or params.get('poles') or params.get('control_points') or []
            if len(points) < 2:
                raise RuntimeError('make_spline_redge requires at least two control points')
            degree = int(params.get('degree') or min(3, len(points) - 1))
            knots = params.get('knots')
            if not isinstance(knots, list) or len(knots) < degree + len(points) + 1:
                internal_count = max(0, len(points) - degree - 1)
                internal = [(i + 1) / (internal_count + 1) for i in range(internal_count)]
                knots = [0.0] * (degree + 1) + internal + [1.0] * (degree + 1)
            control_points = [_pt(p) for p in points]
            weights = params.get('weights')
            if isinstance(weights, list) and len(weights) == len(points):
                curve = adsk.core.NurbsCurve3D.createRational(control_points, degree, [float(k) for k in knots], [float(w) for w in weights], bool(params.get('periodic', False)))
            else:
                curve = adsk.core.NurbsCurve3D.createNonRational(control_points, degree, [float(k) for k in knots], bool(params.get('periodic', False)))
            return self._set_output(node, curve)
        if op == 'make_helix_redge':
            axis = _unit(params.get('axis') or (0.0, 0.0, 1.0))
            center = _v3(params.get('center') or (0.0, 0.0, 0.0))
            radius = float(params.get('radius', 1.0))
            height = float(params.get('height', 1.0))
            pitch = float(params.get('pitch', height))
            start = _add(center, (radius, 0.0, 0.0))
            turns = height / pitch if abs(pitch) > 1e-12 else 1.0
            wire = self.tmp.createHelixWire(_pt(center), _vec(axis), _pt(start), pitch * SCALE, turns, 0.0)
            return self._set_output(node, wire)
        if op == 'make_wire_from_edges_rwire':
            curves = []
            for input_id in inputs:
                item = self._first_output(input_id)
                if hasattr(item, 'edges'):
                    for edge in item.edges:
                        curves.append(edge.geometry)
                else:
                    curves.append(item)
            wire, _edges = self.tmp.createWireFromCurves(curves, False)
            if wire is None:
                raise RuntimeError('createWireFromCurves failed')
            return self._set_output(node, wire)
        if op == 'make_face_from_wire_rface':
            wire = self._first_output(inputs[0])
            face = self.tmp.createFaceFromPlanarWires([wire])
            if face is None:
                raise RuntimeError('createFaceFromPlanarWires failed')
            return self._set_output(node, face)
        if op == 'make_face_from_wires_rface':
            wires = [self._first_output(input_id) for input_id in inputs]
            face = self.tmp.createFaceFromPlanarWires(wires)
            if face is None:
                raise RuntimeError('createFaceFromPlanarWires failed for multi-loop face')
            return self._set_output(node, face)
        if op in {'make_wire_from_sketch_rwire', 'make_face_from_sketch_rface'}:
            raise SimpleCADUnsupportedOpError(f'{op} is not yet supported by the Fusion translator')
        if op == 'make_extrude_rsolid':
            profile = self._first_output(inputs[0])
            direction = _unit(params.get('direction') or (0.0, 0.0, 1.0))
            distance = float(params.get('distance', 0.0))
            vector = _mul(direction, distance)
            body = self._extrude(profile, vector)
            return self._set_output(node, body)
        if op == 'make_revolve_rsolid':
            profile = self._first_output(inputs[0])
            body = self._revolve_by_sampling(profile, params)
            return self._set_output(node, body)
        if op == 'make_loft_rsolid':
            sections = [self._first_output(input_id) for input_id in inputs]
            body = self._loft_by_features(sections, bool(params.get('ruled', False)))
            return self._set_output(node, body)
        if op == 'make_sweep_rsolid':
            profile = self._first_output(inputs[0])
            path = self._first_output(inputs[1])
            body = self._sweep_by_features(profile, path)
            return self._set_output(node, body)
        if op == 'make_cut_rsolid':
            body = self._body_copy(self._first_output(inputs[0]))
            for input_id in inputs[1:]:
                tool = self._first_output(input_id)
                ok = self.tmp.booleanOperation(body, self._body_copy(tool), adsk.fusion.BooleanTypes.DifferenceBooleanType)
                if not ok:
                    self.logs.append(f'cut boolean failed for {node_id} tool {input_id}')
            return self._set_output(node, body)
        if op == 'make_union_rsolid':
            body = self._body_copy(self._first_output(inputs[0]))
            for input_id in inputs[1:]:
                tool = self._first_output(input_id)
                ok = self.tmp.booleanOperation(body, self._body_copy(tool), adsk.fusion.BooleanTypes.UnionBooleanType)
                if not ok:
                    self.logs.append(f'union boolean failed for {node_id} tool {input_id}')
            return self._set_output(node, body)
        if op == 'make_intersect_rsolid':
            body = self._body_copy(self._first_output(inputs[0]))
            for input_id in inputs[1:]:
                tool = self._first_output(input_id)
                ok = self.tmp.booleanOperation(body, self._body_copy(tool), adsk.fusion.BooleanTypes.IntersectionBooleanType)
                if not ok:
                    self.logs.append(f'intersection boolean failed for {node_id} tool {input_id}')
            return self._set_output(node, body)
        if op == 'make_select_redge':
            self.selection_payloads[node_id] = {'kind': 'edge', 'params': params, 'input': inputs[0] if inputs else None}
            return self._set_output(node, self.selection_payloads[node_id])
        if op == 'make_select_rface':
            self.selection_payloads[node_id] = {'kind': 'face', 'params': params, 'input': inputs[0] if inputs else None}
            return self._set_output(node, self.selection_payloads[node_id])
        if op == 'make_fillet_rsolid':
            body = self._feature_detail_edges(node, params, inputs, 'fillet')
            return self._set_output(node, body)
        if op == 'make_chamfer_rsolid':
            body = self._feature_detail_edges(node, params, inputs, 'chamfer')
            return self._set_output(node, body)
        if op == 'make_shell_rsolid':
            body = self._feature_shell(node, params, inputs)
            return self._set_output(node, body)
        if op == 'make_translate_rshape':
            body = self._body_copy(self._first_output(inputs[0]))
            self.tmp.transform(body, _matrix_translate(params.get('vector') or (0.0, 0.0, 0.0)))
            return self._set_output(node, body)
        if op == 'make_rotate_rshape':
            body = self._body_copy(self._first_output(inputs[0]))
            self.tmp.transform(body, _matrix_rotate(params.get('origin') or (0.0, 0.0, 0.0), params.get('axis') or (0.0, 0.0, 1.0), params.get('angle', 0.0)))
            return self._set_output(node, body)
        if op == 'make_mirror_rshape':
            body = self._body_copy(self._first_output(inputs[0]))
            self.tmp.transform(body, _matrix_mirror(params.get('plane_origin') or (0, 0, 0), params.get('plane_normal') or (0, 0, 1)))
            return self._set_output(node, body)
        if op == 'make_material_rmaterial':
            return self._set_output(node, {'kind': 'material', 'params': params})
        if op in {'make_placement_rplacement', 'make_identity_placement_rplacement'}:
            return self._set_output(node, {'kind': 'placement', 'params': params})
        if op == 'make_part_rpart':
            value = {'kind': 'part', 'params': params, 'body_node': inputs[0], 'body': self._first_output(inputs[0])}
            self.product_values[node_id] = value
            return self._set_output(node, value)
        if op == 'make_assign_material_rpart':
            value = dict(self._first_output(inputs[0]))
            value['material'] = self._first_output(inputs[1])
            self.product_values[node_id] = value
            return self._set_output(node, value)
        if op == 'make_assembly_rassembly':
            value = {'kind': 'assembly', 'params': params, 'components': []}
            self.product_values[node_id] = value
            return self._set_output(node, value)
        if op == 'make_add_component_rassembly':
            assembly = dict(self._first_output(inputs[0]))
            components = list(assembly.get('components') or [])
            components.append({
                'item': self._first_output(inputs[1]),
                'placement': self._first_output(inputs[2]) if len(inputs) > 2 else {'kind': 'placement', 'params': {}},
                'params': params,
            })
            assembly['components'] = components
            self.product_values[node_id] = assembly
            return self._set_output(node, assembly)
        if op == 'make_place_component_rassembly':
            return self._set_output(node, self._first_output(inputs[0]))
        if op == 'make_compound_from_assembly_rcompound':
            assembly = self._first_output(inputs[0])
            bodies = self._bodies_from_product(assembly)
            if not bodies:
                raise RuntimeError('assembly compound has no bodies')
            body = self._body_copy(bodies[0])
            for tool in bodies[1:]:
                ok = self.tmp.booleanOperation(body, self._body_copy(tool), adsk.fusion.BooleanTypes.UnionBooleanType)
                if not ok:
                    self.logs.append(f'assembly compound union failed for {node_id}')
            return self._set_output(node, body)
        if op.startswith('make_') and op.endswith('_rconnector'):
            return self._set_output(node, {'kind': 'connector', 'params': params})
        if op in {
            'make_add_connector_rpart', 'make_add_connector_rassembly',
            'make_connector_ref_rconnectorref', 'make_scalar_limit_rscalarlimit',
            'make_ground_component_rassembly', 'make_unground_component_rassembly',
            'make_fixed_constraint_rassembly', 'make_revolute_constraint_rassembly',
            'make_prismatic_constraint_rassembly', 'make_solve_assembly_constraints_rassembly',
        }:
            value = self._first_output(inputs[0]) if inputs else {'kind': op, 'params': params}
            return self._set_output(node, value)
        raise SimpleCADUnsupportedOpError(f'Unsupported SimpleCAD op for Fusion 360 translation: {op}')

    def _extrude(self, profile, vector):
        if isinstance(profile, adsk.fusion.BRepBody) and profile.faces.count > 0:
            distance = _norm(vector)
            if distance <= 1.0e-12:
                raise RuntimeError('Extrude distance is zero')
            persistent_face_body = self.root.bRepBodies.add(profile)
            face = _first_entity(persistent_face_body.faces, 'profile face')
            features = self.root.features.extrudeFeatures
            face_normal = _face_normal_tuple(face)
            feature = None
            if face_normal is not None:
                target = _unit(vector)
                direction = adsk.fusion.ExtentDirections.PositiveExtentDirection
                if _dot(face_normal, target) < 0.0:
                    direction = adsk.fusion.ExtentDirections.NegativeExtentDirection
                try:
                    input_obj = features.createInput(face, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
                    extent = adsk.fusion.DistanceExtentDefinition.create(_value_cm(distance))
                    input_obj.setOneSideExtent(extent, direction)
                    feature = features.add(input_obj)
                except Exception as exc:
                    self.logs.append(f'extrude directional API fallback: {exc}')
            if feature is None:
                feature = features.addSimple(face, _value_cm(distance), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            return self._copy_first_feature_body_and_cleanup(feature, 'extrude result body', [persistent_face_body])
        raise RuntimeError('Extrude profile is not a planar face body')

    def _revolve_by_sampling(self, profile, params):
        # Fusion temporary BRep has no direct revolve primitive. Use Fusion's feature
        # API so the kernel owns the exact revolve result.
        persistent_face_body = self.root.bRepBodies.add(profile)
        face = _first_entity(persistent_face_body.faces, 'revolve profile face')
        origin = params.get('origin') or (0.0, 0.0, 0.0)
        axis = _unit(params.get('axis') or (0.0, 0.0, 1.0))
        line = adsk.core.Line3D.create(_pt(origin), _pt(_add(origin, axis)))
        axis_body, _edges = self.tmp.createWireFromCurves([line], False)
        axis_persistent = self.root.bRepBodies.add(axis_body)
        axis_edge = _first_entity(axis_persistent.edges, 'revolve axis edge')
        input_obj = self.root.features.revolveFeatures.createInput(face, axis_edge, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        input_obj.setAngleExtent(False, _value_deg(params.get('angle', 360.0)))
        feature = self.root.features.revolveFeatures.add(input_obj)
        return self._copy_first_feature_body_and_cleanup(feature, 'revolve result body', [persistent_face_body, axis_persistent])

    def _loft_by_features(self, sections, ruled):
        input_obj = self.root.features.loftFeatures.createInput(adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        persisted = []
        for section in sections:
            if section.faces.count > 0:
                body = self.root.bRepBodies.add(section)
                persisted.append(body)
                input_obj.loftSections.add(_first_entity(body.faces, 'loft section face'))
            elif section.wires.count > 0 or section.edges.count > 0:
                face_section = None
                if section.wires.count > 0:
                    face_section = self.tmp.createFaceFromPlanarWires([_first_entity(section.wires, 'loft section wire')])
                if face_section is None and section.edges.count > 0:
                    curves = [edge.geometry for edge in section.edges]
                    wire_section, _edges = self.tmp.createWireFromCurves(curves, False)
                    if wire_section is not None and wire_section.wires.count > 0:
                        face_section = self.tmp.createFaceFromPlanarWires([_first_entity(wire_section.wires, 'loft section wire')])
                if face_section is None or face_section.faces.count <= 0:
                    raise RuntimeError('Loft wire section could not be converted to a planar profile face')
                body = self.root.bRepBodies.add(face_section)
                persisted.append(body)
                input_obj.loftSections.add(_first_entity(body.faces, 'loft section face'))
            else:
                raise RuntimeError('Loft section has no usable face or edge')
        try:
            input_obj.isSolid = True
            input_obj.isClosed = False
            input_obj.isTangentEdgesMerged = False
            if hasattr(input_obj, 'isRuled'):
                input_obj.isRuled = bool(ruled)
        except Exception:
            pass
        feature = self.root.features.loftFeatures.add(input_obj)
        return self._copy_first_feature_body_and_cleanup(feature, 'loft result body', persisted)

    def _sweep_by_features(self, profile, path):
        profile_body = self.root.bRepBodies.add(profile)
        path_body = self.root.bRepBodies.add(path)
        sweep_features = self.root.features.sweepFeatures
        path_obj = adsk.fusion.Path.create(path_body.edges, adsk.fusion.ChainedCurveOptions.connectedChainedCurves)
        input_obj = sweep_features.createInput(_first_entity(profile_body.faces, 'sweep profile face'), path_obj, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        feature = sweep_features.add(input_obj)
        return self._copy_first_feature_body_and_cleanup(feature, 'sweep result body', [profile_body, path_body])

    def _feature_detail_edges(self, node, params, inputs, kind):
        source = self.root.bRepBodies.add(self._first_output(inputs[0]))
        selected = []
        selectors = []
        for selector_id in params.get('selected_edge_node_ids') or []:
            payload = self.selection_payloads.get(str(selector_id))
            if payload:
                selectors.append(payload.get('params') or {})
        if not selectors:
            for item in params.get('selected_edges') or []:
                if isinstance(item, dict):
                    selectors.append(item.get('selector_hint') or item)
        for selector in selectors:
            edge = _best_by_geometry(list(source.edges), selector, _edge_signature, 'edge')
            selected.append(edge)
        if not selected:
            raise RuntimeError(f'{kind} requires at least one geometrically selected edge')
        if kind == 'fillet':
            input_obj = self.root.features.filletFeatures.createInput()
            input_obj.addConstantRadiusEdgeSet(_object_collection(selected), _value_cm(params.get('radius', 0.0)), True)
            feature = self.root.features.filletFeatures.add(input_obj)
        else:
            input_obj = self.root.features.chamferFeatures.createInput2()
            input_obj.chamferEdgeSets.addEqualDistanceChamferEdgeSet(_object_collection(selected), _value_cm(params.get('distance', params.get('radius', 0.0))), True)
            feature = self.root.features.chamferFeatures.add(input_obj)
        return self._copy_first_feature_body_and_cleanup(feature, f'{kind} result body', [source])

    def _feature_shell(self, node, params, inputs):
        source = self.root.bRepBodies.add(self._first_output(inputs[0]))
        selectors = []
        for selector_id in params.get('selected_face_node_ids') or []:
            payload = self.selection_payloads.get(str(selector_id))
            if payload:
                selectors.append(payload.get('params') or {})
        for item in params.get('selected_faces') or []:
            if isinstance(item, dict):
                selectors.append(item.get('selector_hint') or item)
        faces = []
        for selector in selectors:
            faces.append(_best_by_geometry(list(source.faces), selector, _face_signature, 'face'))
        input_obj = self.root.features.shellFeatures.createInput(faces, False)
        input_obj.insideThickness = _value_cm(params.get('thickness', 0.0))
        feature = self.root.features.shellFeatures.add(input_obj)
        return self._copy_first_feature_body_and_cleanup(feature, 'shell result body', [source])

    def _bodies_from_product(self, value):
        if not isinstance(value, dict):
            return []
        if value.get('kind') == 'part':
            return [value.get('body')]
        if value.get('kind') == 'assembly':
            bodies = []
            for component in value.get('components') or []:
                bodies.extend(self._bodies_from_product(component.get('item')))
            return [body for body in bodies if body is not None]
        return []

    def _materialize_results(self):
        if not self.result_node_ids:
            self.result_node_ids = [str(node.get('node_id')) for node in self.nodes[-1:]]
        emitted = 0
        for node_id in self.result_node_ids:
            for value in self.outputs.get(node_id, []):
                emitted += self._materialize_value(value, node_id)
        if emitted == 0:
            for node_id, outputs in self.outputs.items():
                for value in outputs:
                    emitted += self._materialize_value(value, node_id)
        if emitted == 0:
            raise RuntimeError('Fusion translator produced no materialized bodies')

    def _materialize_value(self, value, node_id):
        count = 0
        if isinstance(value, adsk.fusion.BRepBody):
            body = self.root.bRepBodies.add(value)
            _apply_name(body, f'SimpleCAD_{node_id}')
            return 1
        if isinstance(value, dict) and value.get('kind') in {'part', 'assembly'}:
            for body in self._bodies_from_product(value):
                if body is not None:
                    persisted = self.root.bRepBodies.add(body)
                    _apply_name(persisted, f'SimpleCAD_{node_id}_{count}')
                    count += 1
        return count


def _safe_label(op, node_id):
    raw = f'{op}_{node_id}'
    token = ''.join(ch if ch.isalnum() else '_' for ch in raw).strip('_')
    if not token:
        token = 'simplecad'
    if token[0].isdigit():
        token = 'simplecad_' + token
    return token[:80]
'''


def translate_model_json_to_fusion360_script(
    json_str: str,
    document_name: str = "SimpleCADModel",
) -> str:
    """Translate exported model JSON into a Fusion 360 Python script."""

    return Fusion360ScriptTranslator(
        document_name=document_name
    ).translate_model_json_to_script(json_str)
