"""Translate SimpleCAD model/graph payloads into SolidWorks automation scripts.

Generated scripts are intended to run on Windows machines with SolidWorks and
pywin32 installed. They interpret the same canonical low-level operation graph
used by the FreeCAD and Fusion 360 translators and avoid topology-index based
edge/face selection.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import pprint
import re
import sys
import tempfile
import zlib
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.TopAbs import TopAbs_SOLID
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from ...errors import raise_harness_error
from ...operations import _make_geo_selector
from ...serializer import (
    _execute_graph,
    _resolve_shape_from_geo_selector,
    import_model_json,
)
from ...topology import OperationGraph


def _json_ascii(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _py_literal(value: Any) -> str:
    return pprint.pformat(value, compact=True, sort_dicts=True, width=120)


def _deterministic_step_bytes(data: bytes) -> bytes:
    text = data.decode("latin-1")
    text = re.sub(
        r"(FILE_NAME\('[^']*',)'[^']*'",
        r"\1'1970-01-01T00:00:00'",
        text,
        count=1,
    )
    text = re.sub(
        r"(Open CASCADE STEP translator [^']* )\d+(')",
        r"\g<1>1\2",
        text,
    )
    return text.encode("latin-1")


_ASSEMBLY_ACTIVE_STATE_PRIORITY = (
    "operating",
    "locked",
    "nominal",
    "default",
    "middle",
    "middle_adjustment",
)


def _assembly_state_result_node_ids(
    graph: OperationGraph, result_node_ids: Sequence[str]
) -> Dict[str, List[str]]:
    """Group sibling assembly snapshots by the state suffix in their IDs."""

    node_ids = [str(node_id) for node_id in result_node_ids]
    if len(node_ids) < 2:
        return {}
    snapshots: List[Tuple[str, str, int]] = []
    for node_id in node_ids:
        node = graph.get_node(node_id)
        if node is None or node.op != "make_compound_from_assembly_rcompound":
            return {}
        assembly_id = str(node.params.get("assembly_id") or "")
        if not assembly_id:
            return {}
        snapshots.append(
            (
                node_id,
                assembly_id,
                int(node.params.get("component_count") or 0),
            )
        )
    if len({count for _, _, count in snapshots}) != 1:
        return {}
    common_prefix = os.path.commonprefix(
        [assembly_id for _, assembly_id, _ in snapshots]
    )
    separator_index = common_prefix.rfind("_")
    if separator_index <= 0:
        return {}
    state_prefix = common_prefix[: separator_index + 1]
    state_node_ids: Dict[str, List[str]] = {}
    for node_id, assembly_id, _ in snapshots:
        if not assembly_id.startswith(state_prefix):
            return {}
        state = assembly_id[len(state_prefix) :].strip("_")
        if not state or state in state_node_ids:
            return {}
        state_node_ids[state] = [node_id]
    return state_node_ids


def _preferred_result_node_ids(
    graph: OperationGraph, result_node_ids: Sequence[str]
) -> List[str]:
    """Choose the nominal snapshot from an explicitly named assembly state set."""

    node_ids = [str(node_id) for node_id in result_node_ids]
    state_node_ids = _assembly_state_result_node_ids(graph, node_ids)
    for state in _ASSEMBLY_ACTIVE_STATE_PRIORITY:
        selected = state_node_ids.get(state)
        if selected is not None:
            return list(selected)
    node_by_id = {str(node.node_id): node for node in graph.nodes}
    assembly_results = [
        node_id
        for node_id in node_ids
        if getattr(node_by_id.get(node_id), "op", None)
        == "make_compound_from_assembly_rcompound"
    ]
    if assembly_results:
        return assembly_results
    dominant_result = _dominant_result_node_id(graph, node_ids)
    if dominant_result is not None:
        return [dominant_result]
    return node_ids


def _dominant_result_node_id(
    graph: OperationGraph, result_node_ids: Sequence[str]
) -> Optional[str]:
    """Collapse redundant terminal leaves only when their union proves containment."""

    node_by_id = {str(node.node_id): node for node in graph.nodes}
    node_ids = [str(node_id) for node_id in result_node_ids]
    ops = [getattr(node_by_id.get(node_id), "op", None) for node_id in node_ids]
    detail_ops = {"make_fillet_rsolid", "make_chamfer_rsolid", "make_shell_rsolid"}
    has_one_detail_result = sum(op in detail_ops for op in ops) == 1
    all_union_results = len(node_ids) > 1 and all(
        op == "make_union_rsolid" for op in ops
    )
    if not has_one_detail_result and not all_union_results:
        return None

    try:
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        results = _execute_graph(graph, node_ids, strict=True)
        if len(results) != len(node_ids):
            return None

        def shape_volume(shape: Any) -> float:
            props = GProp_GProps()
            BRepGProp.VolumeProperties_s(shape, props)
            return max(0.0, float(props.Mass()))

        positive_shapes: List[Tuple[str, Any, float]] = []
        for node_id, result in zip(node_ids, results):
            shape = getattr(result, "wrapped", None)
            if shape is None or shape.IsNull():
                continue
            volume = shape_volume(shape)
            if volume > 0.0:
                positive_shapes.append((node_id, shape, volume))
        if len(positive_shapes) < 2:
            return None

        if has_one_detail_result:
            detail_node_id = next(
                node_id
                for node_id, op in zip(node_ids, ops)
                if op in detail_ops
            )
            volume_by_id = {
                node_id: volume for node_id, _shape, volume in positive_shapes
            }
            detail_volume = volume_by_id.get(detail_node_id, 0.0)
            total_volume = sum(volume_by_id.values())
            if total_volume > 0.0 and detail_volume / total_volume >= 0.99:
                return detail_node_id

        fused_shape = positive_shapes[0][1]
        for _node_id, shape, _volume in positive_shapes[1:]:
            fuse = BRepAlgoAPI_Fuse(fused_shape, shape)
            fuse.Build()
            if not fuse.IsDone():
                return None
            fused_shape = fuse.Shape()
        fused_volume = shape_volume(fused_shape)
        dominant_node_id, _dominant_shape, dominant_volume = max(
            positive_shapes, key=lambda item: item[2]
        )
        tolerance = max(1.0e-12, fused_volume * 1.0e-8)
        if fused_volume > 0.0 and abs(dominant_volume - fused_volume) <= tolerance:
            return dominant_node_id
    except Exception:
        return None
    return None


def _canonical_union_passthroughs(graph: OperationGraph) -> Dict[str, int]:
    """Find unions whose canonical replay is exactly one of their inputs."""

    union_nodes = [node for node in graph.nodes if node.op == "make_union_rsolid"]
    if not union_nodes:
        return {}
    replay_node_ids = list(
        dict.fromkeys(
            [str(node.node_id) for node in union_nodes]
            + [
                str(input_ref.node_id)
                for node in union_nodes
                for input_ref in node.inputs
            ]
        )
    )
    try:
        results = _execute_graph(graph, replay_node_ids, strict=True)
    except Exception:
        return {}
    if len(results) != len(replay_node_ids):
        return {}

    descriptors: Dict[str, Tuple[Tuple[float, ...], float]] = {}
    for node_id, result in zip(replay_node_ids, results):
        wrapped = getattr(result, "wrapped", None)
        if wrapped is None or wrapped.IsNull():
            continue
        box = Bnd_Box()
        box.SetGap(0.0)
        BRepBndLib.AddOptimal_s(wrapped, box, False, False)
        if box.IsVoid():
            continue
        descriptors[node_id] = (
            tuple(float(value) for value in box.Get()),
            float(result.get_volume()),
        )

    passthroughs: Dict[str, int] = {}
    for node in union_nodes:
        node_id = str(node.node_id)
        output_descriptor = descriptors.get(node_id)
        if output_descriptor is None:
            continue
        output_bbox, output_volume = output_descriptor
        bbox_size = sum(
            (output_bbox[index + 3] - output_bbox[index]) ** 2
            for index in range(3)
        ) ** 0.5
        bbox_tolerance = max(1.0e-7, bbox_size * 1.0e-7)
        volume_tolerance = max(1.0e-9, abs(output_volume) * 1.0e-8)
        matches: List[int] = []
        for index, input_ref in enumerate(node.inputs):
            input_descriptor = descriptors.get(str(input_ref.node_id))
            if input_descriptor is None:
                continue
            input_bbox, input_volume = input_descriptor
            bbox_error = sum(
                (actual - expected) ** 2
                for actual, expected in zip(input_bbox, output_bbox)
            ) ** 0.5
            if (
                bbox_error <= bbox_tolerance
                and abs(input_volume - output_volume) <= volume_tolerance
            ):
                matches.append(index)
        if len(matches) == 1:
            passthroughs[node_id] = matches[0]
    return passthroughs


def _canonical_cut_descriptors(graph: OperationGraph) -> Dict[str, Dict[str, Any]]:
    node_ids = [
        node.node_id for node in graph.nodes
        if node.op == "make_cut_rsolid"
    ]
    if not node_ids:
        return {}
    try:
        results = _execute_graph(graph, node_ids, strict=True)
    except Exception:
        return {}
    if len(results) != len(node_ids):
        return {}
    descriptors: Dict[str, Dict[str, Any]] = {}
    for node_id, result in zip(node_ids, results):
        wrapped = getattr(result, "wrapped", None)
        if wrapped is None or wrapped.IsNull():
            continue
        box = Bnd_Box()
        box.SetGap(0.0)
        BRepBndLib.AddOptimal_s(wrapped, box, False, False)
        if box.IsVoid():
            continue
        bounds = tuple(float(value) for value in box.Get())
        descriptors[str(node_id)] = {
            "bbox": {
                "min": bounds[:3],
                "max": bounds[3:],
            },
            "volume": float(result.get_volume()),
        }
    return descriptors


def _canonical_union_descriptors(graph: OperationGraph) -> Dict[str, Dict[str, Any]]:
    node_ids = [
        node.node_id for node in graph.nodes
        if node.op == "make_union_rsolid"
    ]
    if not node_ids:
        return {}
    try:
        results = _execute_graph(graph, node_ids, strict=True)
    except Exception:
        return {}
    if len(results) != len(node_ids):
        return {}
    descriptors: Dict[str, Dict[str, Any]] = {}
    for node_id, result in zip(node_ids, results):
        wrapped = getattr(result, "wrapped", None)
        if wrapped is None or wrapped.IsNull():
            continue
        box = Bnd_Box()
        box.SetGap(0.0)
        BRepBndLib.AddOptimal_s(wrapped, box, False, False)
        if box.IsVoid():
            continue
        bounds = tuple(float(value) for value in box.Get())
        descriptors[str(node_id)] = {
            "bbox": {"min": bounds[:3], "max": bounds[3:]},
            "volume": float(result.get_volume()),
        }
    return descriptors


def _canonical_union_input_indices(graph: OperationGraph) -> Dict[str, List[int]]:
    """Identify the original operands that contribute solid volume to each union."""

    union_nodes = [node for node in graph.nodes if node.op == "make_union_rsolid"]
    if not union_nodes:
        return {}
    replay_node_ids = list(
        dict.fromkeys(
            [str(node.node_id) for node in union_nodes]
            + [
                str(input_ref.node_id)
                for node in union_nodes
                for input_ref in node.inputs
            ]
        )
    )
    try:
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        replayed = _execute_graph(graph, replay_node_ids, strict=True)
    except Exception:
        return {}
    if len(replayed) != len(replay_node_ids):
        return {}
    shapes = {
        node_id: getattr(result, "wrapped", None)
        for node_id, result in zip(replay_node_ids, replayed)
    }

    def shape_volume(shape: Any) -> float:
        if shape is None or shape.IsNull():
            return 0.0
        properties = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, properties)
        return max(0.0, float(properties.Mass()))

    result: Dict[str, List[int]] = {}
    for node in union_nodes:
        output_shape = shapes.get(str(node.node_id))
        if output_shape is None or output_shape.IsNull():
            continue
        contributing: List[int] = []
        for index, input_ref in enumerate(node.inputs):
            input_shape = shapes.get(str(input_ref.node_id))
            input_volume = shape_volume(input_shape)
            if input_shape is None or input_shape.IsNull() or input_volume <= 0.0:
                continue
            try:
                common = BRepAlgoAPI_Common(output_shape, input_shape)
                common.Build()
                common_volume = (
                    shape_volume(common.Shape()) if common.IsDone() else 0.0
                )
            except Exception:
                common_volume = 0.0
            if common_volume > max(1.0e-10, input_volume * 1.0e-8):
                contributing.append(index)
        if contributing:
            result[str(node.node_id)] = contributing
    return result


def _canonical_loft_descriptors(graph: OperationGraph) -> Dict[str, Dict[str, Any]]:
    loft_nodes = [
        node for node in graph.nodes
        if node.op == "make_loft_rsolid"
    ]
    node_ids = [node.node_id for node in loft_nodes]
    if not node_ids:
        return {}
    replay_graph = copy.deepcopy(graph)
    ruled_segment_ids: Dict[str, List[str]] = {}
    for node in loft_nodes:
        if not bool(node.params.get("ruled")) or len(node.inputs) <= 2:
            continue
        replay_node = replay_graph.get_node(str(node.node_id))
        if replay_node is None:
            continue
        segment_ids: List[str] = []
        for index in range(len(replay_node.inputs) - 1):
            segment_id = f"__solidworks_ruled_{node.node_id}_{index}"
            replay_graph.add_node(
                "make_loft_rsolid",
                {"profile_count": 2, "ruled": True},
                inputs=[replay_node.inputs[index], replay_node.inputs[index + 1]],
                node_id=segment_id,
            )
            segment_ids.append(segment_id)
        ruled_segment_ids[str(node.node_id)] = segment_ids
    replay_ids = node_ids + [
        segment_id
        for segment_ids in ruled_segment_ids.values()
        for segment_id in segment_ids
    ]
    try:
        results = _execute_graph(replay_graph, replay_ids, strict=True)
    except Exception:
        return {}
    if len(results) != len(replay_ids):
        return {}

    def descriptor(result: Any) -> Optional[Dict[str, Any]]:
        wrapped = getattr(result, "wrapped", None)
        if wrapped is None or wrapped.IsNull():
            return None
        box = Bnd_Box()
        box.SetGap(0.0)
        BRepBndLib.AddOptimal_s(wrapped, box, False, False)
        if box.IsVoid():
            return None
        bounds = tuple(float(value) for value in box.Get())
        return {
            "bbox": {
                "min": bounds[:3],
                "max": bounds[3:],
            },
            "volume": float(result.get_volume()),
        }

    replayed = dict(zip(replay_ids, results))
    descriptors: Dict[str, Dict[str, Any]] = {}
    for node_id in node_ids:
        value = descriptor(replayed[node_id])
        if value is None:
            continue
        segment_descriptors = [
            descriptor(replayed[segment_id])
            for segment_id in ruled_segment_ids.get(str(node_id), [])
        ]
        if segment_descriptors and all(segment_descriptors):
            value["ruled_segments"] = segment_descriptors
        descriptors[str(node_id)] = value
    return descriptors


def _canonical_sweep_descriptors(graph: OperationGraph) -> Dict[str, Dict[str, Any]]:
    sweep_ids = [
        str(node.node_id)
        for node in graph.nodes
        if node.op == "make_sweep_rsolid"
    ]
    if not sweep_ids:
        return {}
    try:
        results = _execute_graph(graph, sweep_ids, strict=True)
    except Exception:
        return {}
    if len(results) != len(sweep_ids):
        return {}
    descriptors: Dict[str, Dict[str, Any]] = {}
    for node_id, result in zip(sweep_ids, results):
        wrapped = getattr(result, "wrapped", None)
        if wrapped is None or wrapped.IsNull():
            continue
        box = Bnd_Box()
        box.SetGap(0.0)
        BRepBndLib.AddOptimal_s(wrapped, box, False, False)
        if box.IsVoid():
            continue
        bounds = tuple(float(value) for value in box.Get())
        descriptors[node_id] = {
            "bbox": {"min": bounds[:3], "max": bounds[3:]},
            "volume": float(result.get_volume()),
        }
    return descriptors


def _result_dependency_node_ids(
    graph: OperationGraph, result_node_ids: Sequence[str]
) -> Set[str]:
    pending = [str(node_id) for node_id in result_node_ids]
    visited: Set[str] = set()
    while pending:
        node_id = pending.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        node = graph.get_node(node_id)
        if node is None:
            continue
        pending.extend(str(input_ref.node_id) for input_ref in node.inputs)
        for key in ("selected_edge_node_ids", "selected_face_node_ids"):
            pending.extend(str(value) for value in node.params.get(key, []) or [])
    return visited


def _canonical_detail_edge_catalog(
    graph: OperationGraph, result_node_ids: Sequence[str]
) -> Dict[str, Any]:
    """Describe every canonical edge feeding an active Fillet or Chamfer.

    The catalog is task-independent. Generated SolidWorks scripts use it once,
    while the native source body is live, to establish persistent references
    through GSM. Native OES edits can then resolve a frozen canonical edge
    index without performing geometry matching after the document is reopened.
    """

    active_ids = _result_dependency_node_ids(graph, result_node_ids)
    detail_nodes = [
        node
        for node in graph.nodes
        if str(node.node_id) in active_ids
        and node.op in {"make_fillet_rsolid", "make_chamfer_rsolid"}
        and node.inputs
    ]
    source_node_ids = list(
        dict.fromkeys(str(node.inputs[0].node_id) for node in detail_nodes)
    )
    if not source_node_ids:
        return {}
    detail_node_ids = [str(node.node_id) for node in detail_nodes]
    replay_node_ids = list(dict.fromkeys(source_node_ids + detail_node_ids))
    try:
        replay_results = _execute_graph(graph, replay_node_ids, strict=True)
    except Exception:
        return {}
    if len(replay_results) != len(replay_node_ids):
        return {}

    replayed = dict(zip(replay_node_ids, replay_results))

    source_shapes: Dict[str, Any] = {
        source_id: replayed[source_id]
        for source_id in source_node_ids
        if source_id in replayed
        for result in (replayed[source_id],)
        if hasattr(result, "get_edges")
    }
    sources: Dict[str, Dict[str, Any]] = {}
    for source_id, source_shape in source_shapes.items():
        try:
            source_edges = list(source_shape.get_edges())
        except Exception:
            continue
        edges = []
        for canonical_index, edge in enumerate(source_edges):
            try:
                selector = dict(
                    _make_geo_selector(edge, source_shape=source_shape)
                )
            except Exception:
                continue
            selector.pop("metadata_geo", None)
            edges.append(
                {
                    "canonical_index": canonical_index,
                    "selector": selector,
                }
            )
        sources[source_id] = {"edges": edges, "targets": {}}

    node_by_id = {str(node.node_id): node for node in graph.nodes}
    for detail_node in detail_nodes:
        source_id = str(detail_node.inputs[0].node_id)
        source_shape = source_shapes.get(source_id)
        source_entry = sources.get(source_id)
        if source_shape is None or source_entry is None:
            continue
        try:
            source_edges = list(source_shape.get_edges())
            selected_indices = []
            for selector_node_id in (
                detail_node.params.get("selected_edge_node_ids") or []
            ):
                selector_node = node_by_id.get(str(selector_node_id))
                selector = (
                    dict(selector_node.params.get("geo_selector") or {})
                    if selector_node is not None
                    else {}
                )
                if not selector:
                    raise RuntimeError("detail selector has no geometry")
                selected_edge = _resolve_shape_from_geo_selector(
                    source_shape, selector
                )
                selected_indices.append(
                    next(
                        index
                        for index, candidate in enumerate(source_edges)
                        if candidate.same_topology(selected_edge)
                    )
                )
        except Exception:
            continue
        target_entry: Dict[str, Any] = {
            "selected_indices": selected_indices,
        }
        detail_result = replayed.get(str(detail_node.node_id))
        try:
            wrapped = getattr(detail_result, "wrapped", None)
            if wrapped is not None and not wrapped.IsNull():
                box = Bnd_Box()
                box.SetGap(0.0)
                BRepBndLib.AddOptimal_s(wrapped, box, False, False)
                if not box.IsVoid():
                    bounds = tuple(float(value) for value in box.Get())
                    target_entry["result_descriptor"] = {
                        "bbox": {
                            "min": bounds[:3],
                            "max": bounds[3:],
                        },
                        "volume": float(detail_result.get_volume()),
                    }
        except Exception:
            pass
        source_entry["targets"][str(detail_node.node_id)] = target_entry

    return {
        "schema": "simplecad-sw-canonical-topology-v1",
        "method": "gsm",
        "sources": sources,
    }


def _result_dependency_ops(
    graph: OperationGraph, result_node_ids: Sequence[str]
) -> Set[str]:
    pending = [str(node_id) for node_id in result_node_ids]
    visited: Set[str] = set()
    operations: Set[str] = set()
    while pending:
        node_id = pending.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        node = graph.get_node(node_id)
        if node is None:
            continue
        operations.add(str(node.op))
        pending.extend(str(input_ref.node_id) for input_ref in node.inputs)
    return operations


def _source_kernel_result_step_payload(
    graph: OperationGraph, result_node_ids: Sequence[str]
) -> Optional[str]:
    """Serialize valid final source results for detail-feature recovery."""

    node_ids = [str(node_id) for node_id in result_node_ids]
    nodes = [graph.get_node(node_id) for node_id in node_ids]
    dependency_ops = _result_dependency_ops(graph, node_ids)
    if not nodes or not dependency_ops.intersection(
        {"make_chamfer_rsolid", "make_fillet_rsolid"}
    ):
        return None
    try:
        results = _execute_graph(graph, node_ids, strict=True)
    except Exception:
        return None
    if len(results) != len(node_ids):
        return None
    writer = STEPControl_Writer()
    source_cache: Dict[str, Any] = {}
    transferred_shape_count = 0
    for node_id, node, result in zip(node_ids, nodes, results):
        wrapped = getattr(result, "wrapped", None)
        source_valid = (
            wrapped is not None
            and not wrapped.IsNull()
            and BRepCheck_Analyzer(wrapped).IsValid()
        )
        if not source_valid:
            if (
                node is None
                or node.op != "make_chamfer_rsolid"
                or not node.inputs
            ):
                return None
            source_id = str(node.inputs[0].node_id)
            source_result = source_cache.get(source_id)
            if source_result is None:
                try:
                    source_results = _execute_graph(
                        graph, [source_id], strict=True
                    )
                except Exception:
                    continue
                if len(source_results) != 1:
                    continue
                source_result = source_results[0]
                source_cache[source_id] = source_result
            source_shape = getattr(source_result, "wrapped", None)
            if (
                source_shape is None
                or source_shape.IsNull()
                or source_shape.ShapeType() != TopAbs_SOLID
                or not BRepCheck_Analyzer(source_shape).IsValid()
            ):
                continue
            box = Bnd_Box()
            box.SetGap(0.0)
            BRepBndLib.AddOptimal_s(source_shape, box, False, False)
            if box.IsVoid():
                continue
            bounds = tuple(float(value) for value in box.Get())
            extents = [
                bounds[index + 3] - bounds[index]
                for index in range(3)
                if bounds[index + 3] - bounds[index] > 1.0e-12
            ]
            distance = abs(float(node.params.get("distance", 0.0) or 0.0))
            if not extents or distance > 0.25 * min(extents):
                # Match FreeCAD result collection: an invalid over-large final
                # chamfer remains failed and is omitted without suppressing
                # valid sibling results.
                continue
            wrapped = source_shape
        writer.Transfer(wrapped, STEPControl_AsIs)
        transferred_shape_count += 1
    if transferred_shape_count == 0:
        return None
    handle = tempfile.NamedTemporaryFile(suffix=".step", delete=False)
    path = handle.name
    handle.close()
    try:
        if writer.Write(path) != IFSelect_RetDone:
            return None
        with open(path, "rb") as source:
            return base64.b64encode(
                zlib.compress(_deterministic_step_bytes(source.read()), level=9)
            ).decode("ascii")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


class SolidWorksScriptTranslator:
    """Compile SimpleCAD model JSON into a SolidWorks COM automation script."""

    def __init__(
        self,
        document_name: str = "SimpleCADModel",
        *,
        visible: bool = False,
        source_kernel_fallback: bool = False,
    ) -> None:
        self.document_name = document_name
        self.visible = bool(visible)
        self.source_kernel_fallback = bool(source_kernel_fallback)
        self._declared_result_node_id_list: List[str] = []
        self._result_node_id_list: List[str] = []
        self._result_node_ids: Set[str] = set()
        self._result_state_node_ids: Dict[str, List[str]] = {}
        self._active_result_state: Optional[str] = None

    def translate_model_json_to_script(
        self,
        json_str: str,
        *,
        output_path: Optional[str] = None,
    ) -> str:
        payload = import_model_json(json_str)
        graph = payload.get("graph")
        if not isinstance(graph, OperationGraph):
            raise ValueError(
                "SolidWorks translation requires model JSON with a canonical low-level graph"
            )
        if graph.node_count == 0:
            raise ValueError(
                "SolidWorks translation requires model JSON with a non-empty canonical low-level graph"
            )
        return self.translate_model_payload_to_script(
            payload, graph=graph, output_path=output_path
        )

    def translate_model_payload_to_script(
        self,
        payload: Dict[str, Any],
        *,
        graph: OperationGraph,
        output_path: Optional[str],
    ) -> str:
        leaf_ids = payload.get("leaf_ids")
        if isinstance(leaf_ids, list) and leaf_ids:
            self._declared_result_node_id_list = [str(v) for v in leaf_ids]
        else:
            self._declared_result_node_id_list = [
                leaf.node_id for leaf in graph.leaf_nodes()
            ]
        self._result_state_node_ids = _assembly_state_result_node_ids(
            graph, self._declared_result_node_id_list
        )
        self._result_node_id_list = _preferred_result_node_ids(
            graph, self._declared_result_node_id_list
        )
        self._active_result_state = next(
            (
                state
                for state, node_ids in self._result_state_node_ids.items()
                if node_ids == self._result_node_id_list
            ),
            None,
        )
        self._result_node_ids = set(self._result_node_id_list)
        payload_dict = self._payload_to_jsonable(payload, graph)
        payload_dict["solidworks_canonical_cut_descriptors"] = (
            _canonical_cut_descriptors(graph)
        )
        payload_dict["solidworks_canonical_union_passthroughs"] = (
            _canonical_union_passthroughs(graph)
        )
        payload_dict["solidworks_canonical_union_descriptors"] = (
            _canonical_union_descriptors(graph)
        )
        payload_dict["solidworks_canonical_union_input_indices"] = (
            _canonical_union_input_indices(graph)
        )
        payload_dict["solidworks_canonical_loft_descriptors"] = (
            _canonical_loft_descriptors(graph)
        )
        payload_dict["solidworks_canonical_sweep_descriptors"] = (
            _canonical_sweep_descriptors(graph)
        )
        payload_dict["solidworks_source_kernel_result_step"] = (
            _source_kernel_result_step_payload(graph, self._result_node_id_list)
            if self.source_kernel_fallback
            else None
        )
        if os.environ.get("SIMPLECAD_SW_PERSIST_TOPOLOGY", "1") != "0":
            detail_edge_catalog = _canonical_detail_edge_catalog(
                graph, self._result_node_id_list
            )
            if detail_edge_catalog:
                catalog_json = json.dumps(
                    detail_edge_catalog,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("ascii")
                payload_dict["solidworks_detail_edge_catalog_z"] = (
                    base64.b64encode(
                        zlib.compress(catalog_json, level=9)
                    ).decode("ascii")
                )

        return (
            "from __future__ import annotations\n"
            "\n"
            "import base64\n"
            "import glob\n"
            "import hashlib\n"
            "import json\n"
            "import math\n"
            "import os\n"
            "import shutil\n"
            "import time\n"
            "import traceback\n"
            "import zlib\n"
            "\n"
            "import pythoncom\n"
            "import win32com.client\n"
            "\n"
            f"DOC_NAME = {_json_ascii(self.document_name)}\n"
            f"VISIBLE = {_py_literal(self.visible)}\n"
            f"MODEL_PAYLOAD = {_py_literal(payload_dict)}\n"
            f"DECLARED_RESULT_NODE_IDS = {_py_literal(self._declared_result_node_id_list)}\n"
            f"RESULT_STATE_NODE_IDS = {_py_literal(self._result_state_node_ids)}\n"
            f"ACTIVE_RESULT_STATE = {_py_literal(self._active_result_state)}\n"
            f"RESULT_NODE_IDS = {_py_literal(self._result_node_id_list)}\n"
            f"OUTPUT_PATH = {_json_ascii(os.path.abspath(output_path)) if output_path else 'None'}\n"
            "\n"
            + self._runtime_helpers()
            + "\n"
            "def main():\n"
            "    pythoncom.CoInitialize()\n"
            "    runtime = None\n"
            "    try:\n"
            "        runtime = SimpleCADSolidWorksRuntime(MODEL_PAYLOAD, DOC_NAME, RESULT_NODE_IDS, visible=VISIBLE)\n"
            "        runtime.run(output_path=OUTPUT_PATH)\n"
            "        print(json.dumps({'document_name': DOC_NAME, 'output_path': OUTPUT_PATH, 'strategy': 'operation_graph_native'}))\n"
            "    finally:\n"
            "        if runtime is not None:\n"
            "            runtime.finish()\n"
            "        else:\n"
            "            pythoncom.CoUninitialize()\n"
            "\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    try:\n"
            "        main()\n"
            "    except Exception:\n"
            "        traceback.print_exc()\n"
            "        raise\n"
        )

    def _payload_to_jsonable(
        self, payload: Dict[str, Any], source_graph: OperationGraph
    ) -> Dict[str, Any]:
        nodes: List[Dict[str, Any]] = []
        for node in source_graph.topological_order():
            params = dict(node.params)
            if str(node.op) in {"make_angle_arc_redge", "make_circle_redge"}:
                normal = params.get("normal") or (0.0, 0.0, 1.0)
                frame = gp_Ax2(
                    gp_Pnt(0.0, 0.0, 0.0),
                    gp_Dir(*(float(value) for value in normal)),
                )
                x_axis = frame.XDirection()
                y_axis = frame.YDirection()
                params["_kernel_x_axis"] = [
                    float(x_axis.X()),
                    float(x_axis.Y()),
                    float(x_axis.Z()),
                ]
                params["_kernel_y_axis"] = [
                    float(y_axis.X()),
                    float(y_axis.Y()),
                    float(y_axis.Z()),
                ]
            nodes.append(
                {
                    "node_id": str(node.node_id),
                    "op": str(node.op),
                    "params": self._sanitize_payload_for_solidworks(params),
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

    def _sanitize_payload_for_solidworks(self, value: Any) -> Any:
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
                    child_cleaned = self._sanitize_payload_for_solidworks(child)
                    if isinstance(child_cleaned, dict):
                        child_cleaned = {
                            k: v
                            for k, v in child_cleaned.items()
                            if k not in {"edge_index", "face_index"}
                        }
                    if child_cleaned:
                        cleaned[key] = child_cleaned
                    continue
                cleaned[key] = self._sanitize_payload_for_solidworks(child)
            return cleaned
        if isinstance(value, (list, tuple)):
            return [self._sanitize_payload_for_solidworks(item) for item in value]
        return value

    def _runtime_helpers(self) -> str:
        return r'''
MM_TO_M = 0.001
M_TO_MM = 1000.0
M2_TO_MM2 = 1000000.0
TOL = 1.0e-7
MODEL_SCALE = 1.0

SW_DOC_PART = 1
SW_SOLID_BODY = 0
SW_OPEN_DOC_OPTIONS_SILENT = 1
SW_SAVE_AS_CURRENT_VERSION = 0
SW_SAVE_AS_OPTIONS_SILENT = 1

# swBodyOperationType_e values used by IBody2::Operations2 and InsertCombineFeature.
SWBODYINTERSECT = 15901
SWBODYCUT = 15902
SWBODYADD = 15903

# swTwistControlType_e.  OCC's is_frenet=True transports the section with the
# helix frame.  SolidWorks' plain Follow Path does not preserve that radial
# frame on a long helix; combine Keep Normal Constant with an explicit twist.
SW_TWIST_CONTROL_NORMAL_CONSTANT_TWIST = 9
SW_FM_SWEEP = 17

# Keep the fillet local to the explicitly GSM-selected edges. Bit 1 is
# swFeatureFilletPropagate and would expand the operation along tangent chains.
SW_FEATURE_FILLET_OPTIONS = 194


def _native_part_output_path(output_path):
    step_path = os.path.abspath(output_path)
    step_directory = os.path.dirname(step_path)
    if os.path.basename(step_directory).lower() == 'steps':
        native_directory = os.path.join(
            os.path.dirname(step_directory), 'sldprt'
        )
    else:
        native_directory = step_directory
    stem = os.path.splitext(os.path.basename(step_path))[0]
    return os.path.join(native_directory, stem + '.sldprt')


def _native_assembly_output_path(output_path):
    step_path = os.path.abspath(output_path)
    step_directory = os.path.dirname(step_path)
    if os.path.basename(step_directory).lower() == 'steps':
        native_directory = os.path.join(
            os.path.dirname(step_directory), 'sldasm'
        )
    else:
        native_directory = step_directory
    stem = os.path.splitext(os.path.basename(step_path))[0]
    return os.path.join(native_directory, stem + '.sldasm')


class SimpleCADUnsupportedOpError(RuntimeError):
    pass


def _empty_dispatch():
    return win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)


def _byref_i4(value=0):
    return win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, int(value))


def _maybe_call(value):
    return value() if callable(value) else value


def _v3(value, default=(0.0, 0.0, 0.0)):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        value = default
    return (float(value[0]), float(value[1]), float(value[2]))


def _add(a, b):
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


def _sub(a, b):
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _mul(a, scalar):
    return (float(a[0]) * scalar, float(a[1]) * scalar, float(a[2]) * scalar)


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
    length = _norm(_v3(a, fallback))
    if length <= 1.0e-12:
        return _v3(fallback)
    x, y, z = _v3(a, fallback)
    return (x / length, y / length, z / length)


def _distance(a, b):
    return _norm(_sub(_v3(a), _v3(b)))


def _point_line_distance(point, origin, direction):
    direction = _unit(direction)
    return _norm(_cross(_sub(_v3(point), _v3(origin)), direction))


def _rotate_point_payload(point, axis, angle_degrees, origin):
    axis = _unit(axis)
    relative = _sub(_v3(point), _v3(origin))
    angle = math.radians(float(angle_degrees))
    rotated = _add(
        _add(
            _mul(relative, math.cos(angle)),
            _mul(_cross(axis, relative), math.sin(angle)),
        ),
        _mul(axis, _dot(axis, relative) * (1.0 - math.cos(angle))),
    )
    return _add(_v3(origin), rotated)


def _rotate_direction_payload(direction, axis, angle_degrees):
    return _sub(
        _rotate_point_payload(direction, axis, angle_degrees, (0.0, 0.0, 0.0)),
        _rotate_point_payload((0.0, 0.0, 0.0), axis, angle_degrees, (0.0, 0.0, 0.0)),
    )


def _mirror_point_payload(point, plane_origin, plane_normal):
    normal = _unit(plane_normal)
    offset = _sub(_v3(point), _v3(plane_origin))
    return _sub(_v3(point), _mul(normal, 2.0 * _dot(offset, normal)))


def _mirror_direction_payload(direction, plane_normal):
    normal = _unit(plane_normal)
    direction = _v3(direction)
    return _sub(direction, _mul(normal, 2.0 * _dot(direction, normal)))


def _transform_geometry_value(value, point_transform, direction_transform):
    if not isinstance(value, dict):
        raise RuntimeError(
            f'Expected transformable SimpleCAD geometry, got {type(value).__name__}'
        )
    kind = value.get('kind')
    transformed = dict(value)
    if kind == 'wire':
        transformed['edges'] = [
            _transform_geometry_value(edge, point_transform, direction_transform)
            for edge in value.get('edges') or []
        ]
        return transformed
    if kind == 'face':
        transformed['outer'] = _transform_geometry_value(
            value.get('outer'), point_transform, direction_transform
        )
        transformed['inners'] = [
            _transform_geometry_value(wire, point_transform, direction_transform)
            for wire in value.get('inners') or []
        ]
        if value.get('normal') is not None:
            transformed['normal'] = _unit(direction_transform(value.get('normal')))
        return transformed
    if kind != 'edge':
        raise RuntimeError(f'Unsupported non-body transform value kind: {kind!r}')

    edge_type = value.get('type')
    for key in ('start', 'middle', 'end', 'center'):
        if value.get(key) is not None:
            transformed[key] = point_transform(value.get(key))
    if edge_type == 'spline':
        transformed['controls'] = [
            point_transform(point) for point in value.get('controls') or []
        ]
    for key in ('normal', '_kernel_x_axis', '_kernel_y_axis'):
        if value.get(key) is not None:
            transformed[key] = _unit(direction_transform(value.get(key)))
    if edge_type == 'helix':
        helix_params = dict(value.get('params') or {})
        for key in ('center', 'origin'):
            if helix_params.get(key) is not None:
                helix_params[key] = point_transform(helix_params.get(key))
        for key in ('dir', 'axis', 'normal'):
            if helix_params.get(key) is not None:
                helix_params[key] = _unit(direction_transform(helix_params.get(key)))
        transformed['params'] = helix_params
    return transformed


def _plane_axes(normal):
    normal = _unit(normal)
    reference = (1.0, 0.0, 0.0)
    if abs(_dot(normal, reference)) > 0.9:
        reference = (0.0, 1.0, 0.0)
    x_axis = _sub(reference, _mul(normal, _dot(reference, normal)))
    x_axis = _unit(x_axis)
    y_axis = _unit(_cross(normal, x_axis))
    return x_axis, y_axis


def _angle_arc_axes(normal):
    normal = _unit(normal)
    reference = (1.0, 0.0, 0.0) if abs(normal[2]) > 0.9 else (0.0, 0.0, 1.0)
    x_axis = _cross(normal, reference)
    if _norm(x_axis) <= 1.0e-12:
        x_axis = _cross(normal, (0.0, 1.0, 0.0))
    x_axis = _unit(x_axis)
    y_axis = _unit(_cross(normal, x_axis))
    return x_axis, y_axis


def _angle_arc_world_point(
    center,
    radius,
    angle,
    normal,
    x_axis=None,
    y_axis=None,
):
    if x_axis is None or y_axis is None:
        x_axis, y_axis = _angle_arc_axes(normal)
    else:
        x_axis = _unit(x_axis)
        y_axis = _unit(y_axis)
    radial = _add(
        _mul(x_axis, float(radius) * math.cos(float(angle))),
        _mul(y_axis, float(radius) * math.sin(float(angle))),
    )
    return _add(_v3(center), radial)


def _model_work_scale(payload):
    lengths = []

    def add_length(value):
        try:
            value = abs(float(value))
        except (TypeError, ValueError):
            return
        if math.isfinite(value) and value > 1.0e-9:
            lengths.append(value)

    for node in ((payload.get('graph') or {}).get('nodes') or []):
        op = str(node.get('op') or '')
        params = node.get('params') or {}
        if op == 'make_line_redge':
            add_length(_distance(params.get('start'), params.get('end')))
        elif op in {'make_circle_redge', 'make_angle_arc_redge'}:
            add_length(params.get('radius'))
        elif op == 'make_three_point_arc_redge':
            points = [params.get('start'), params.get('middle'), params.get('end')]
            for first, second in zip(points, points[1:]):
                add_length(_distance(first, second))
        elif op == 'make_spline_redge':
            points = params.get('control_points') or params.get('controls') or params.get('points') or []
            for first, second in zip(points, points[1:]):
                add_length(_distance(first, second))
        elif op == 'make_helix_redge':
            for key in ('radius', 'pitch', 'height'):
                add_length(params.get(key))
        elif op in {
            'make_extrude_rsolid', 'make_fillet_rsolid', 'make_chamfer_rsolid',
            'make_shell_rsolid', 'make_box_rsolid', 'make_cylinder_rsolid',
            'make_cone_rsolid', 'make_sphere_rsolid',
        }:
            for key in (
                'distance', 'radius', 'radius1', 'radius2', 'thickness',
                'length', 'width', 'height',
            ):
                add_length(params.get(key))

    if not lengths:
        return 1.0
    minimum = min(lengths)
    # SolidWorks rejects sketch entities below roughly one millimetre. Build at
    # a stable working size, then restore the canonical model size before export.
    return min(1000000.0, max(1.0, 5.0 / minimum))


def _as_m(value):
    return float(value) * MODEL_SCALE * MM_TO_M


def _pt_m(value):
    x, y, z = _v3(value)
    return (
        x * MODEL_SCALE * MM_TO_M,
        y * MODEL_SCALE * MM_TO_M,
        z * MODEL_SCALE * MM_TO_M,
    )


def _identity_matrix():
    return [
        1.0, 0.0, 0.0,
        0.0, 1.0, 0.0,
        0.0, 0.0, 1.0,
        0.0, 0.0, 0.0,
        1.0,
        0.0, 0.0, 0.0,
    ]


def _translation_matrix(vector_mm):
    tx, ty, tz = _pt_m(vector_mm)
    data = _identity_matrix()
    data[9] = tx
    data[10] = ty
    data[11] = tz
    return data


def _solidworks_rotation_angle_index(principal_index):
    principal_index = int(principal_index)
    if principal_index not in (0, 1, 2):
        raise ValueError(
            f'Invalid principal rotation axis index: {principal_index}'
        )
    return 2 - principal_index


def _scale_about_bbox_matrix(bbox, factor):
    center = _bbox_center(bbox)
    cx, cy, cz = _pt_m(center)
    factor = float(factor)
    data = _identity_matrix()
    data[9] = (1.0 - factor) * cx
    data[10] = (1.0 - factor) * cy
    data[11] = (1.0 - factor) * cz
    data[12] = factor
    return data


def _rotation_matrix(axis, angle_degrees, origin):
    ax, ay, az = _unit(axis)
    angle = math.radians(float(angle_degrees))
    c = math.cos(angle)
    s = math.sin(angle)
    t = 1.0 - c
    r00 = t * ax * ax + c
    r01 = t * ax * ay - s * az
    r02 = t * ax * az + s * ay
    r10 = t * ax * ay + s * az
    r11 = t * ay * ay + c
    r12 = t * ay * az - s * ax
    r20 = t * ax * az - s * ay
    r21 = t * ay * az + s * ax
    r22 = t * az * az + c
    ox, oy, oz = _pt_m(origin)
    tx = ox - (r00 * ox + r01 * oy + r02 * oz)
    ty = oy - (r10 * ox + r11 * oy + r12 * oz)
    tz = oz - (r20 * ox + r21 * oy + r22 * oz)
    # IMathTransform stores the rotation basis for row-vector multiplication.
    # Transpose the conventional column-vector Rodrigues matrix while keeping
    # the world-space pivot translation unchanged.
    return [r00, r10, r20, r01, r11, r21, r02, r12, r22, tx, ty, tz, 1.0, 0.0, 0.0, 0.0]


def _mirror_matrix(plane_origin, plane_normal):
    nx, ny, nz = _unit(plane_normal)
    px, py, pz = _pt_m(plane_origin)
    d = -(nx * px + ny * py + nz * pz)
    r00 = 1.0 - 2.0 * nx * nx
    r01 = -2.0 * nx * ny
    r02 = -2.0 * nx * nz
    r10 = -2.0 * ny * nx
    r11 = 1.0 - 2.0 * ny * ny
    r12 = -2.0 * ny * nz
    r20 = -2.0 * nz * nx
    r21 = -2.0 * nz * ny
    r22 = 1.0 - 2.0 * nz * nz
    tx = -2.0 * d * nx
    ty = -2.0 * d * ny
    tz = -2.0 * d * nz
    return [r00, r01, r02, r10, r11, r12, r20, r21, r22, tx, ty, tz, 1.0, 0.0, 0.0, 0.0]


def _placement_matrix(placement):
    if isinstance(placement, dict) and placement.get('kind') == 'placement':
        placement = placement.get('params') or {}
    if not isinstance(placement, dict):
        placement = {}
    origin = _v3(placement.get('origin') or (0.0, 0.0, 0.0))
    x_axis = _unit(placement.get('x_axis') or (1.0, 0.0, 0.0))
    y_axis = _unit(placement.get('y_axis') or (0.0, 1.0, 0.0))
    z_axis = _unit(placement.get('z_axis') or _cross(x_axis, y_axis))
    tx, ty, tz = _pt_m(origin)
    # SimpleCAD axes are columns of the local-to-world transform. SolidWorks
    # multiplies row vectors, so write the transposed basis just as in
    # _rotation_matrix.
    return [
        x_axis[0], x_axis[1], x_axis[2],
        y_axis[0], y_axis[1], y_axis[2],
        z_axis[0], z_axis[1], z_axis[2],
        tx, ty, tz,
        1.0,
        0.0, 0.0, 0.0,
    ]


def _multiply_transform_matrices(first, second):
    """Compose two SolidWorks row-vector affine transforms."""
    if len(first) < 13 or len(second) < 13:
        raise ValueError('SolidWorks transforms require at least 13 values')
    first_scale = float(first[12])
    second_scale = float(second[12])
    first_rotation = [float(value) for value in first[:9]]
    second_rotation = [float(value) for value in second[:9]]
    rotation = [
        sum(
            first_rotation[row * 3 + inner]
            * second_rotation[inner * 3 + column]
            for inner in range(3)
        )
        for row in range(3)
        for column in range(3)
    ]
    first_translation = [float(value) for value in first[9:12]]
    second_translation = [float(value) for value in second[9:12]]
    translation = [
        sum(
            first_translation[inner]
            * second_rotation[inner * 3 + column]
            * second_scale
            for inner in range(3)
        )
        + second_translation[column]
        for column in range(3)
    ]
    return rotation + translation + [
        first_scale * second_scale, 0.0, 0.0, 0.0
    ]


def _assembly_component_matrix(placements):
    matrix = _identity_matrix()
    # Product traversal records placements outermost first. Body transforms are
    # applied innermost first, so preserve that same order for Component2.
    for placement in reversed(tuple(placements or ())):
        matrix = _multiply_transform_matrices(
            matrix, _placement_matrix(placement)
        )
    if MODEL_SCALE > 0.0:
        for index in (9, 10, 11):
            matrix[index] = float(matrix[index]) / MODEL_SCALE
    return matrix


def _transform_matrices_close(first, second):
    if len(first) < 13 or len(second) < 13:
        return False
    scale = max(
        1.0,
        *(abs(float(value)) for value in first[:13]),
        *(abs(float(value)) for value in second[:13]),
    )
    tolerance = scale * 1.0e-8
    return all(
        abs(float(first[index]) - float(second[index])) <= tolerance
        for index in range(13)
    )


def _is_identity_matrix(matrix_data, tolerance=1.0e-10):
    identity = _identity_matrix()
    return len(matrix_data) == len(identity) and all(
        abs(float(actual) - float(expected)) <= tolerance
        for actual, expected in zip(matrix_data, identity)
    )


def _is_translation_matrix(matrix_data, tolerance=1.0e-12):
    identity = _identity_matrix()
    return (
        len(matrix_data) >= 16
        and all(
            abs(float(matrix_data[index]) - float(identity[index]))
            <= tolerance
            for index in range(9)
        )
        and abs(float(matrix_data[12]) - 1.0) <= tolerance
        and all(
            abs(float(matrix_data[index])) <= tolerance
            for index in (13, 14, 15)
        )
    )


def _bbox_from_box(box):
    if not box or len(box) < 6:
        return None
    return {
        'min': tuple(float(box[i]) * M_TO_MM / MODEL_SCALE for i in range(3)),
        'max': tuple(float(box[i]) * M_TO_MM / MODEL_SCALE for i in range(3, 6)),
    }


def _bbox_center(bbox):
    return tuple((float(bbox['min'][i]) + float(bbox['max'][i])) * 0.5 for i in range(3))


def _bbox_score(candidate_bbox, selector_bbox):
    if not isinstance(candidate_bbox, dict) or not isinstance(selector_bbox, dict):
        return 0.0
    expected_min = selector_bbox.get('min')
    expected_max = selector_bbox.get('max')
    actual_min = candidate_bbox.get('min')
    actual_max = candidate_bbox.get('max')
    if not all(isinstance(value, (list, tuple)) and len(value) == 3 for value in (
        expected_min, expected_max, actual_min, actual_max,
    )):
        return 1.0e6
    return _distance(actual_min, expected_min) + _distance(actual_max, expected_max)


def _bbox_intersects(first, second, tolerance=1.0e-7):
    if not isinstance(first, dict) or not isinstance(second, dict):
        return False
    first_min = first.get('min')
    first_max = first.get('max')
    second_min = second.get('min')
    second_max = second.get('max')
    if not all(
        isinstance(value, (list, tuple)) and len(value) == 3
        for value in (first_min, first_max, second_min, second_max)
    ):
        return False
    return all(
        float(first_max[index]) + tolerance >= float(second_min[index])
        and float(second_max[index]) + tolerance >= float(first_min[index])
        for index in range(3)
    )


def _bbox_axis_gaps(first, second):
    if not isinstance(first, dict) or not isinstance(second, dict):
        return (float('inf'), float('inf'), float('inf'))
    first_min = first.get('min')
    first_max = first.get('max')
    second_min = second.get('min')
    second_max = second.get('max')
    if not all(
        isinstance(value, (list, tuple)) and len(value) == 3
        for value in (first_min, first_max, second_min, second_max)
    ):
        return (float('inf'), float('inf'), float('inf'))
    return tuple(
        max(
            0.0,
            float(second_min[index]) - float(first_max[index]),
            float(first_min[index]) - float(second_max[index]),
        )
        for index in range(3)
    )


def _selector_geometry(selector):
    params = selector.get('params') if isinstance(selector, dict) else None
    if isinstance(params, dict):
        selector = params
    if not isinstance(selector, dict):
        return {}
    geo_selector = selector.get('geo_selector')
    if isinstance(geo_selector, dict):
        return dict(selector, **geo_selector)
    return selector


def _tuple3_or_none(value):
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    return None


def _canonical_geom_type(value):
    text = str(value or '').upper().replace('_TYPE', '').replace('_', '')
    aliases = {
        'B-SPLINE': 'BSPLINE',
        'BSPLINE': 'BSPLINE',
        'BCURVE': 'BSPLINE',
        'BSURF': 'BSPLINE',
        'NURBS': 'BSPLINE',
        'BEZIERCURVE': 'BEZIER',
        'BEZIER': 'BEZIER',
        'ELLIPTICALARC': 'ELLIPSE',
        'PLANESURFACE': 'PLANE',
        'CYLINDERSURFACE': 'CYLINDER',
        'CONESURFACE': 'CONE',
        'SPHERESURFACE': 'SPHERE',
        'TORUSSURFACE': 'TORUS',
    }
    return aliases.get(text, text)


def _selector_geom_type(selector):
    selector = _selector_geometry(selector)
    geom_type = _canonical_geom_type(
        selector.get('geom_type') or selector.get('surface_type')
    )
    kind = str(selector.get('kind') or selector.get('target_kind') or '').lower()
    if geom_type not in {'BSPLINE', 'BEZIER'} or kind != 'edge':
        return geom_type
    start = _tuple3_or_none(selector.get('start'))
    end = _tuple3_or_none(selector.get('end'))
    expected_length = selector.get('length')
    if start is None or end is None or expected_length is None:
        return geom_type
    chord_length = _distance(start, end)
    edge_length = float(expected_length)
    scale = max(1.0, chord_length, edge_length)
    if (
        chord_length > scale * 1.0e-10
        and abs(edge_length - chord_length) <= scale * 1.0e-7
    ):
        return 'LINE'
    return geom_type


def _signature_geom_type(sig, selector):
    geom_type = _canonical_geom_type(sig.get('geom_type'))
    kind = _selector_kind(selector, sig)
    if geom_type not in {'BSPLINE', 'BEZIER'} or kind != 'edge':
        return geom_type
    start = _tuple3_or_none(sig.get('start'))
    end = _tuple3_or_none(sig.get('end'))
    edge_length = sig.get('length')
    if start is None or end is None or edge_length is None:
        return geom_type
    chord_length = _distance(start, end)
    edge_length = float(edge_length)
    scale = max(1.0, chord_length, edge_length)
    if (
        chord_length > scale * 1.0e-10
        and abs(edge_length - chord_length) <= scale * 1.0e-7
    ):
        return 'LINE'
    return geom_type


def _geom_type_mismatch(sig, selector):
    selector = _selector_geometry(selector)
    target = _selector_geom_type(selector)
    actual = _signature_geom_type(sig, selector)
    return int(bool(target and actual and target != actual))


def _selector_length_scale(selector):
    selector = _selector_geometry(selector)
    bbox = selector.get('bbox')
    if isinstance(bbox, dict):
        minimum = _tuple3_or_none(bbox.get('min'))
        maximum = _tuple3_or_none(bbox.get('max'))
        if minimum is not None and maximum is not None:
            return max(1.0, _distance(minimum, maximum))
    return 1.0


def _relative_error(actual, expected, floor=1.0):
    return abs(float(actual) - float(expected)) / max(float(floor), abs(float(expected)))


def _bbox_selector_score(sig, selector):
    selector = _selector_geometry(selector)
    candidate_bbox = sig.get('bbox')
    expected_bbox = selector.get('bbox')
    if not isinstance(candidate_bbox, dict) or not isinstance(expected_bbox, dict):
        return 0.0
    actual_min = _tuple3_or_none(candidate_bbox.get('min'))
    actual_max = _tuple3_or_none(candidate_bbox.get('max'))
    expected_min = _tuple3_or_none(expected_bbox.get('min'))
    expected_max = _tuple3_or_none(expected_bbox.get('max'))
    if any(value is None for value in (actual_min, actual_max, expected_min, expected_max)):
        return 1.0e6
    scale = _selector_length_scale(selector)
    return (
        _distance(actual_min, expected_min) + _distance(actual_max, expected_max)
    ) / scale


def _selector_kind(selector, sig):
    selector = _selector_geometry(selector)
    kind = str(selector.get('kind') or selector.get('target_kind') or '').lower()
    if kind:
        return kind
    if 'length' in selector or 'length' in sig:
        return 'edge'
    if 'area' in selector or 'area' in sig:
        return 'face'
    return ''


def _geom_score(sig, selector):
    selector = _selector_geometry(selector)
    score = _bbox_selector_score(sig, selector) * 10.0
    if _geom_type_mismatch(sig, selector):
        score += 20.0
    scale = _selector_length_scale(selector)
    kind = _selector_kind(selector, sig)
    expected_center = _tuple3_or_none(selector.get('center'))
    candidate_center = _tuple3_or_none(sig.get('center'))
    if expected_center is not None and candidate_center is not None:
        score += _distance(candidate_center, expected_center) / scale * 3.0
    if kind == 'edge':
        if selector.get('length') is not None and sig.get('length') is not None:
            score += _relative_error(sig['length'], selector['length']) * 3.0
        expected_start = _tuple3_or_none(selector.get('start'))
        expected_end = _tuple3_or_none(selector.get('end'))
        candidate_start = _tuple3_or_none(sig.get('start'))
        candidate_end = _tuple3_or_none(sig.get('end'))
        if all(value is not None for value in (expected_start, expected_end, candidate_start, candidate_end)):
            same = _distance(candidate_start, expected_start) + _distance(candidate_end, expected_end)
            reverse = _distance(candidate_start, expected_end) + _distance(candidate_end, expected_start)
            score += min(same, reverse) / scale
    elif kind == 'face':
        if selector.get('area') is not None and sig.get('area') is not None:
            score += _relative_error(sig['area'], selector['area']) * 3.0
        if _selector_geom_type(selector) == 'PLANE':
            expected_normal = _tuple3_or_none(selector.get('normal'))
            candidate_normal = _tuple3_or_none(sig.get('normal'))
            if expected_normal is not None and candidate_normal is not None:
                alignment = abs(_dot(_unit(expected_normal), _unit(candidate_normal)))
                score += (1.0 - min(1.0, alignment)) * 2.0
    return score


def _best_by_geometry(signatures, selector, label, topology_match=None):
    if not signatures:
        raise RuntimeError(f'No {label} candidates available for geometry selection')
    selector = _selector_geometry(selector)
    ranked = sorted(
        signatures,
        key=lambda item: _geom_score(item[1], selector),
    )

    exact_spatial_matches = [
        candidate
        for candidate, signature in ranked
        if _bbox_selector_score(signature, selector) <= 1.0e-6
        and (
            not _selector_geom_type(selector)
            or _signature_geom_type(signature, selector) == _selector_geom_type(selector)
        )
    ]
    if len(exact_spatial_matches) == 1:
        return exact_spatial_matches[0]

    kind = _selector_kind(selector, ranked[0][1])
    expected_center = _tuple3_or_none(selector.get('center'))
    expected_measure = selector.get('length') if kind == 'edge' else selector.get('area')
    scale = _selector_length_scale(selector)

    def intrinsic_matches(center_tolerance, measure_tolerance):
        matches = []
        if expected_center is None or expected_measure is None:
            return matches
        measure_key = 'length' if kind == 'edge' else 'area'
        for candidate, signature in ranked:
            if (
                _selector_geom_type(selector)
                and _signature_geom_type(signature, selector) != _selector_geom_type(selector)
            ):
                continue
            candidate_center = _tuple3_or_none(signature.get('center'))
            candidate_measure = signature.get(measure_key)
            if candidate_center is None or candidate_measure is None:
                continue
            center_error = _distance(candidate_center, expected_center) / scale
            measure_error = _relative_error(candidate_measure, expected_measure)
            if center_error <= center_tolerance and measure_error <= measure_tolerance:
                matches.append(candidate)
        return matches

    exact_intrinsic_matches = intrinsic_matches(1.0e-5, 1.0e-4)
    if len(exact_intrinsic_matches) == 1:
        return exact_intrinsic_matches[0]
    approximate_intrinsic_matches = intrinsic_matches(1.0e-3, 1.0e-3)
    if len(approximate_intrinsic_matches) == 1:
        return approximate_intrinsic_matches[0]
    if topology_match is not None:
        topology_candidate = topology_match(ranked, selector)
        if topology_candidate is not None:
            return topology_candidate

    best, best_signature = ranked[0]
    best_score = _geom_score(best_signature, selector)
    second_score = (
        _geom_score(ranked[1][1], selector) if len(ranked) > 1 else float('inf')
    )
    exact_match = best_score <= 1.0e-4
    acceptable_match = best_score <= 1.5
    clearly_better = (
        second_score == float('inf')
        or second_score - best_score >= max(0.1, best_score * 0.15)
    )
    type_mismatch = _geom_type_mismatch(best_signature, selector)
    if not (exact_match or (acceptable_match and clearly_better)):
        nearest = [
            {
                'score': _geom_score(signature, selector),
                'type_mismatch': _geom_type_mismatch(signature, selector),
                'signature': signature,
            }
            for _candidate, signature in ranked[:3]
        ]
        raise RuntimeError(
            f'Geometry selector did not match a stable {label}; '
            f'best score={best_score}; second score={second_score}; '
            f'type_mismatch={type_mismatch}; selector={selector!r}; '
            f'nearest={nearest!r}'
        )
    return best


def _directions_parallel(left, right, tolerance=1.0e-6):
    left = _tuple3_or_none(left)
    right = _tuple3_or_none(right)
    if left is None or right is None:
        return False
    left = _unit(left)
    right = _unit(right)
    return abs(_dot(left, right)) >= 1.0 - tolerance


def _selector_endpoints_on_circle_support(selector, support, tolerance):
    if not isinstance(support, dict):
        return False
    center = _tuple3_or_none(support.get('center'))
    axis = _tuple3_or_none(support.get('axis'))
    radius = support.get('radius')
    selector = _selector_geometry(selector)
    endpoints = (
        _tuple3_or_none(selector.get('start')),
        _tuple3_or_none(selector.get('end')),
    )
    if (
        center is None
        or axis is None
        or radius is None
        or any(point is None for point in endpoints)
    ):
        return False
    axis = _unit(axis)
    radius = abs(float(radius))
    for point in endpoints:
        offset = _sub(point, center)
        if abs(_dot(offset, axis)) > tolerance:
            return False
        radial = _sub(offset, _mul(axis, _dot(offset, axis)))
        if abs(_norm(radial) - radius) > tolerance:
            return False
    return True


def _same_edge_signature_support(first, second, selector, scale):
    geom_type = _signature_geom_type(first, selector)
    second_geom_type = _signature_geom_type(second, selector)
    selector_geom_type = _selector_geom_type(selector)
    parametric_ellipse_fragments = (
        selector_geom_type == 'ELLIPSE'
        and geom_type in {'BSPLINE', 'BEZIER'}
        and second_geom_type in {'BSPLINE', 'BEZIER'}
    )
    if geom_type != second_geom_type and not parametric_ellipse_fragments:
        return False
    tolerance = max(1.0e-7, float(scale) * 1.0e-5)
    if parametric_ellipse_fragments:
        connections = []
        for first_key, first_tangent_key in (
            ('start', 'start_tangent'),
            ('end', 'end_tangent'),
        ):
            first_point = _tuple3_or_none(first.get(first_key))
            first_tangent = _tuple3_or_none(first.get(first_tangent_key))
            for second_key, second_tangent_key in (
                ('start', 'start_tangent'),
                ('end', 'end_tangent'),
            ):
                second_point = _tuple3_or_none(second.get(second_key))
                second_tangent = _tuple3_or_none(second.get(second_tangent_key))
                if (
                    first_point is not None
                    and second_point is not None
                    and first_tangent is not None
                    and second_tangent is not None
                    and _distance(first_point, second_point) <= tolerance
                ):
                    connections.append((first_tangent, second_tangent))
        if len(connections) != 1 or not _directions_parallel(
            connections[0][0], connections[0][1], tolerance=1.0e-4
        ):
            return False
        first_samples = [
            _tuple3_or_none(point) for point in first.get('samples') or ()
        ]
        second_samples = [
            _tuple3_or_none(point) for point in second.get('samples') or ()
        ]
        if (
            len(first_samples) < 3
            or len(second_samples) < 3
            or any(point is None for point in first_samples + second_samples)
        ):
            return False
        origin = first_samples[0]
        offsets = [_sub(point, origin) for point in first_samples[1:]]
        plane_normal = None
        plane_normal_length = 0.0
        for left_index, left in enumerate(offsets):
            for right in offsets[left_index + 1:]:
                normal = _cross(left, right)
                length = _norm(normal)
                if length > plane_normal_length:
                    plane_normal = normal
                    plane_normal_length = length
        if (
            plane_normal is None
            or plane_normal_length
            <= max(1.0e-12, float(scale) * float(scale) * 1.0e-10)
        ):
            return False
        return all(
            abs(_dot(_sub(point, origin), plane_normal))
            / plane_normal_length
            <= tolerance
            for point in second_samples
        )
    if geom_type == 'LINE':
        first_start = _tuple3_or_none(first.get('start'))
        first_end = _tuple3_or_none(first.get('end'))
        second_start = _tuple3_or_none(second.get('start'))
        second_end = _tuple3_or_none(second.get('end'))
        if any(
            point is None
            for point in (first_start, first_end, second_start, second_end)
        ):
            return False
        first_direction = _sub(first_end, first_start)
        second_direction = _sub(second_end, second_start)
        if not _directions_parallel(first_direction, second_direction):
            return False
        direction_length = _norm(first_direction)
        if direction_length <= 1.0e-12:
            return False
        return all(
            _norm(_cross(_sub(point, first_start), first_direction))
            / direction_length
            <= tolerance
            for point in (second_start, second_end)
        )
    if geom_type not in {'CIRCLE', 'ELLIPSE'}:
        return False
    first_support = first.get('support')
    second_support = second.get('support')
    if not isinstance(first_support, dict) or not isinstance(second_support, dict):
        return False
    first_center = _tuple3_or_none(first_support.get('center'))
    second_center = _tuple3_or_none(second_support.get('center'))
    if (
        first_center is None
        or second_center is None
        or _distance(first_center, second_center) > tolerance
        or not _directions_parallel(
            first_support.get('axis'), second_support.get('axis')
        )
    ):
        return False
    radius_keys = ('radius',) if geom_type == 'CIRCLE' else ('major_radius', 'minor_radius')
    return all(
        first_support.get(key) is not None
        and second_support.get(key) is not None
        and abs(float(first_support[key]) - float(second_support[key])) <= tolerance
        for key in radius_keys
    )


def _edge_signature_within_selector_bbox(signature, selector, tolerance):
    candidate_bbox = signature.get('bbox')
    expected_bbox = selector.get('bbox') if isinstance(selector, dict) else None
    if not isinstance(candidate_bbox, dict) or not isinstance(expected_bbox, dict):
        return False
    actual_min = _tuple3_or_none(candidate_bbox.get('min'))
    actual_max = _tuple3_or_none(candidate_bbox.get('max'))
    expected_min = _tuple3_or_none(expected_bbox.get('min'))
    expected_max = _tuple3_or_none(expected_bbox.get('max'))
    if any(
        value is None
        for value in (actual_min, actual_max, expected_min, expected_max)
    ):
        return False
    return all(
        expected_min[index] - tolerance <= actual_min[index]
        and actual_max[index] <= expected_max[index] + tolerance
        for index in range(3)
    )


def _fragment_signature_group_bbox_score(group, selector):
    expected_bbox = selector.get('bbox') if isinstance(selector, dict) else None
    if not isinstance(expected_bbox, dict):
        return 1.0e6
    expected_min = _tuple3_or_none(expected_bbox.get('min'))
    expected_max = _tuple3_or_none(expected_bbox.get('max'))
    if expected_min is None or expected_max is None:
        return 1.0e6
    actual_min = tuple(
        min(float(signature['bbox']['min'][index]) for _candidate, signature in group)
        for index in range(3)
    )
    actual_max = tuple(
        max(float(signature['bbox']['max'][index]) for _candidate, signature in group)
        for index in range(3)
    )
    scale = _selector_length_scale(selector)
    return (
        _distance(actual_min, expected_min) + _distance(actual_max, expected_max)
    ) / scale


def _fragment_signature_group_matches(group, selector):
    if len(group) < 2:
        return False
    expected_length = selector.get('length')
    expected_center = _tuple3_or_none(selector.get('center'))
    if expected_length is None or expected_center is None:
        return False
    total_length = sum(float(signature['length']) for _candidate, signature in group)
    if _relative_error(total_length, expected_length) > 1.0e-4:
        return False
    if _fragment_signature_group_bbox_score(group, selector) > 1.0e-4:
        return False
    if total_length <= 1.0e-12:
        return False
    weighted_center = [0.0, 0.0, 0.0]
    for _candidate, signature in group:
        center = _tuple3_or_none(signature.get('center'))
        if center is None:
            return False
        weight = float(signature['length'])
        for index in range(3):
            weighted_center[index] += center[index] * weight
    weighted_center = tuple(value / total_length for value in weighted_center)
    return (
        _distance(weighted_center, expected_center) / _selector_length_scale(selector)
        <= 1.0e-4
    )


def _fragmented_edge_group(signatures, selector, label):
    selector = _selector_geometry(selector)
    if _selector_kind(selector, {}) != 'edge':
        return None
    expected_type = _selector_geom_type(selector)
    expected_start = _tuple3_or_none(selector.get('start'))
    expected_end = _tuple3_or_none(selector.get('end'))
    expected_length = selector.get('length')
    if (
        not expected_type
        or expected_start is None
        or expected_end is None
        or expected_length is None
    ):
        return None
    scale = _selector_length_scale(selector)
    connection_tolerance = max(1.0e-7, scale * 1.0e-5)
    if _distance(expected_start, expected_end) <= connection_tolerance:
        return None
    ranked = sorted(signatures, key=lambda item: _geom_score(item[1], selector))
    if len(ranked) < 2:
        return None
    eligible = []
    for candidate_index, (candidate, signature) in enumerate(ranked):
        signature_type = _signature_geom_type(signature, selector)
        type_matches = signature_type == expected_type or (
            expected_type == 'ELLIPSE'
            and signature_type in {'BSPLINE', 'BEZIER'}
        )
        if not type_matches:
            continue
        if float(signature.get('length', 0.0)) >= float(expected_length) * (1.0 - 1.0e-6):
            continue
        if not _edge_signature_within_selector_bbox(
            signature, selector, connection_tolerance
        ):
            continue
        start = _tuple3_or_none(signature.get('start'))
        end = _tuple3_or_none(signature.get('end'))
        if start is not None and end is not None:
            eligible.append((candidate_index, candidate, signature, (start, end)))
    if len(eligible) < 2:
        return None
    valid_groups = {}
    for start_index, start_candidate, start_signature, endpoints in eligible:
        starts = []
        if _distance(endpoints[0], expected_start) <= connection_tolerance:
            starts.append(endpoints[1])
        if _distance(endpoints[1], expected_start) <= connection_tolerance:
            starts.append(endpoints[0])
        for current_point in starts:
            stack = [(
                [start_index],
                [(start_candidate, start_signature)],
                current_point,
            )]
            while stack:
                path_indices, path_group, point = stack.pop()
                if _distance(point, expected_end) <= connection_tolerance:
                    if _fragment_signature_group_matches(path_group, selector):
                        key = tuple(sorted(path_indices))
                        valid_groups[key] = [candidate for candidate, _signature in path_group]
                    continue
                if len(path_indices) >= min(12, len(eligible)):
                    continue
                for candidate_index, candidate, signature, candidate_endpoints in eligible:
                    if candidate_index in path_indices:
                        continue
                    if not _same_edge_signature_support(
                        path_group[-1][1], signature, selector, scale
                    ):
                        continue
                    next_points = []
                    if _distance(candidate_endpoints[0], point) <= connection_tolerance:
                        next_points.append(candidate_endpoints[1])
                    if _distance(candidate_endpoints[1], point) <= connection_tolerance:
                        next_points.append(candidate_endpoints[0])
                    for next_point in next_points:
                        stack.append((
                            path_indices + [candidate_index],
                            path_group + [(candidate, signature)],
                            next_point,
                        ))
    if len(valid_groups) == 1:
        return next(iter(valid_groups.values()))
    if len(valid_groups) > 1:
        raise RuntimeError(
            f'Fragmented edge selector is ambiguous; label={label!r}, '
            f'selector={selector!r}, groups={sorted(valid_groups)!r}'
        )
    return None


def _selection_candidates_by_geometry(
    signatures, selector, label, topology_match=None
):
    try:
        return [
            _best_by_geometry(
                signatures,
                selector,
                label,
                topology_match=topology_match,
            )
        ]
    except RuntimeError as single_error:
        fragmented = _fragmented_edge_group(signatures, selector, label)
        if fragmented is None:
            raise single_error
        return list(fragmented)


def _selector_edge_components(selectors):
    normalized = [_selector_geometry(selector) for selector in selectors]
    endpoints = [
        (
            _tuple3_or_none(selector.get('start')),
            _tuple3_or_none(selector.get('end')),
        )
        for selector in normalized
    ]
    if any(start is None or end is None for start, end in endpoints):
        return [list(selectors)]
    tolerance = max(
        1.0e-7,
        max(_selector_length_scale(selector) for selector in normalized) * 1.0e-5,
    )
    neighbors = {index: set() for index in range(len(selectors))}
    for right in range(len(selectors)):
        for left in range(right):
            if min(
                _distance(left_point, right_point)
                for left_point in endpoints[left]
                for right_point in endpoints[right]
            ) <= tolerance:
                neighbors[left].add(right)
                neighbors[right].add(left)
    components = []
    visited = set()
    for start_index in range(len(selectors)):
        if start_index in visited:
            continue
        pending = [start_index]
        visited.add(start_index)
        indices = []
        while pending:
            index = pending.pop()
            indices.append(index)
            for neighbor in sorted(neighbors[index], reverse=True):
                if neighbor not in visited:
                    visited.add(neighbor)
                    pending.append(neighbor)
        components.append([selectors[index] for index in sorted(indices)])
    return components


def _coalesced_edge_selector_pairs(signatures, selectors):
    normalized = [_selector_geometry(selector) for selector in selectors]
    matches = []
    for left_index in range(len(normalized)):
        left = normalized[left_index]
        if _selector_kind(left, {}) != 'edge':
            continue
        left_start = _tuple3_or_none(left.get('start'))
        left_end = _tuple3_or_none(left.get('end'))
        left_length = left.get('length')
        if left_start is None or left_end is None or left_length is None:
            continue
        for right_index in range(left_index + 1, len(normalized)):
            right = normalized[right_index]
            if _selector_geom_type(left) != _selector_geom_type(right):
                continue
            right_start = _tuple3_or_none(right.get('start'))
            right_end = _tuple3_or_none(right.get('end'))
            right_length = right.get('length')
            if right_start is None or right_end is None or right_length is None:
                continue
            scale = max(
                _selector_length_scale(left),
                _selector_length_scale(right),
            )
            tolerance = max(1.0e-7, scale * 1.0e-5)
            endpoint_pairs = [
                (left_key, right_key)
                for left_key, left_point in enumerate((left_start, left_end))
                for right_key, right_point in enumerate((right_start, right_end))
                if _distance(left_point, right_point) <= tolerance
            ]
            closes_loop = len(endpoint_pairs) == 2
            joins_path = len(endpoint_pairs) == 1
            if not (closes_loop or joins_path):
                continue
            external_endpoints = None
            if joins_path:
                left_shared, right_shared = endpoint_pairs[0]
                external_endpoints = (
                    (left_start, left_end)[1 - left_shared],
                    (right_start, right_end)[1 - right_shared],
                )
            left_bbox = left.get('bbox')
            right_bbox = right.get('bbox')
            if not isinstance(left_bbox, dict) or not isinstance(right_bbox, dict):
                continue
            expected_min = tuple(
                min(
                    float(left_bbox['min'][axis]),
                    float(right_bbox['min'][axis]),
                )
                for axis in range(3)
            )
            expected_max = tuple(
                max(
                    float(left_bbox['max'][axis]),
                    float(right_bbox['max'][axis]),
                )
                for axis in range(3)
            )
            total_length = float(left_length) + float(right_length)
            left_center = _tuple3_or_none(left.get('center'))
            right_center = _tuple3_or_none(right.get('center'))
            if left_center is None or right_center is None:
                continue
            expected_center = tuple(
                (
                    left_center[axis] * float(left_length)
                    + right_center[axis] * float(right_length)
                ) / total_length
                for axis in range(3)
            )
            candidates = []
            for candidate_index, (_candidate, signature) in enumerate(signatures):
                candidate_type = _canonical_geom_type(signature.get('geom_type'))
                expected_type = _selector_geom_type(left)
                if closes_loop:
                    if candidate_type != 'INTERSECTION':
                        continue
                elif candidate_type != expected_type:
                    continue
                candidate_start = _tuple3_or_none(signature.get('start'))
                candidate_end = _tuple3_or_none(signature.get('end'))
                candidate_center = _tuple3_or_none(signature.get('center'))
                candidate_length = signature.get('length')
                if (
                    candidate_start is None
                    or candidate_end is None
                    or candidate_center is None
                    or candidate_length is None
                ):
                    continue
                if closes_loop:
                    if _distance(candidate_start, candidate_end) > tolerance:
                        continue
                else:
                    matches_external_endpoints = (
                        _distance(candidate_start, external_endpoints[0]) <= tolerance
                        and _distance(candidate_end, external_endpoints[1]) <= tolerance
                    ) or (
                        _distance(candidate_start, external_endpoints[1]) <= tolerance
                        and _distance(candidate_end, external_endpoints[0]) <= tolerance
                    )
                    if not matches_external_endpoints:
                        continue
                    if (
                        expected_type == 'CIRCLE'
                        and not all(
                            _selector_endpoints_on_circle_support(
                                source_selector,
                                signature.get('support'),
                                tolerance,
                            )
                            for source_selector in (left, right)
                        )
                    ):
                        continue
                if _relative_error(candidate_length, total_length) > 1.0e-4:
                    continue
                combined_selector = {
                    'bbox': {'min': expected_min, 'max': expected_max},
                    'kind': 'edge',
                }
                # Edge bboxes are reconstructed from 65 curve samples. Keep
                # the tolerance below one sampling interval while relying on
                # exact outer endpoints, total length, and weighted center.
                if _bbox_selector_score(signature, combined_selector) > 5.0e-4:
                    continue
                if _distance(candidate_center, expected_center) / scale > 1.0e-4:
                    continue
                candidates.append(candidate_index)
            if len(candidates) == 1:
                matches.append((left_index, right_index, candidates[0]))
            elif len(candidates) > 1:
                raise RuntimeError(
                    'Coalesced edge selector is ambiguous; '
                    f'selectors=({left_index}, {right_index}), '
                    f'candidates={candidates!r}'
                )
    used_selectors = set()
    used_candidates = set()
    result = []
    for left_index, right_index, candidate_index in matches:
        if (
            left_index in used_selectors
            or right_index in used_selectors
            or candidate_index in used_candidates
        ):
            raise RuntimeError(
                'Coalesced edge selector groups overlap and are ambiguous; '
                f'matches={matches!r}'
            )
        used_selectors.update((left_index, right_index))
        used_candidates.add(candidate_index)
        result.append((left_index, right_index, candidate_index))
    return result


def _closed_intersection_candidate(ranked, selector):
    selector = _selector_geometry(selector)
    if _selector_kind(selector, {}) != 'edge':
        return None
    if _selector_geom_type(selector) not in {'BSPLINE', 'BEZIER'}:
        return None
    expected_start = _tuple3_or_none(selector.get('start'))
    expected_end = _tuple3_or_none(selector.get('end'))
    expected_center = _tuple3_or_none(selector.get('center'))
    expected_length = selector.get('length')
    scale = _selector_length_scale(selector)
    tolerance = max(1.0e-7, scale * 1.0e-5)
    if (
        expected_start is None
        or expected_end is None
        or expected_center is None
        or expected_length is None
        or _distance(expected_start, expected_end) > tolerance
    ):
        return None
    matches = []
    for candidate, signature in ranked:
        if _canonical_geom_type(signature.get('geom_type')) != 'INTERSECTION':
            continue
        candidate_start = _tuple3_or_none(signature.get('start'))
        candidate_end = _tuple3_or_none(signature.get('end'))
        candidate_center = _tuple3_or_none(signature.get('center'))
        candidate_length = signature.get('length')
        if (
            candidate_start is None
            or candidate_end is None
            or candidate_center is None
            or candidate_length is None
            or _distance(candidate_start, candidate_end) > tolerance
        ):
            continue
        if _bbox_selector_score(signature, selector) > 1.0e-4:
            continue
        if _relative_error(candidate_length, expected_length) > 1.0e-4:
            continue
        if _distance(candidate_center, expected_center) / scale > 1.0e-4:
            continue
        matches.append(candidate)
    return matches[0] if len(matches) == 1 else None


def _is_missing_revolution_seam(ranked, selector):
    selector = _selector_geometry(selector)
    if _selector_kind(selector, {}) != 'edge' or _selector_geom_type(selector) != 'LINE':
        return False
    expected_start = _tuple3_or_none(selector.get('start'))
    expected_end = _tuple3_or_none(selector.get('end'))
    expected_length = selector.get('length')
    scale = _selector_length_scale(selector)
    tolerance = max(1.0e-7, scale * 1.0e-5)
    if (
        expected_start is None
        or expected_end is None
        or expected_length is None
        or _relative_error(_distance(expected_start, expected_end), expected_length)
        > 1.0e-4
    ):
        return False

    def circle_support(signature, point):
        if _canonical_geom_type(signature.get('geom_type')) != 'CIRCLE':
            return None
        start = _tuple3_or_none(signature.get('start'))
        end = _tuple3_or_none(signature.get('end'))
        bbox = signature.get('bbox')
        if (
            start is None
            or end is None
            or _distance(start, end) > tolerance
            or _distance(start, point) > tolerance
            or not isinstance(bbox, dict)
        ):
            return None
        minimum = _tuple3_or_none(bbox.get('min'))
        maximum = _tuple3_or_none(bbox.get('max'))
        if minimum is None or maximum is None:
            return None
        spans = [maximum[index] - minimum[index] for index in range(3)]
        axis = min(range(3), key=lambda index: abs(spans[index]))
        if abs(spans[axis]) > tolerance:
            return None
        center = tuple((minimum[index] + maximum[index]) * 0.5 for index in range(3))
        radial = tuple(
            point[index] - center[index] if index != axis else 0.0
            for index in range(3)
        )
        if _norm(radial) <= tolerance:
            return None
        return axis, center, _unit(radial)

    start_matches = []
    end_matches = []
    for candidate, signature in ranked:
        start_support = circle_support(signature, expected_start)
        if start_support is not None:
            start_matches.append((candidate, start_support))
        end_support = circle_support(signature, expected_end)
        if end_support is not None:
            end_matches.append((candidate, end_support))
    valid_pairs = []
    for start_candidate, start_support in start_matches:
        for end_candidate, end_support in end_matches:
            if start_candidate is end_candidate:
                continue
            start_axis, start_center, start_radial = start_support
            end_axis, end_center, end_radial = end_support
            if start_axis != end_axis:
                continue
            if any(
                abs(start_center[index] - end_center[index]) > tolerance
                for index in range(3)
                if index != start_axis
            ):
                continue
            if _dot(start_radial, end_radial) < 1.0 - 1.0e-6:
                continue
            valid_pairs.append((start_candidate, end_candidate))
    return len(valid_pairs) == 1


def _flatten(values):
    for value in values:
        if isinstance(value, (list, tuple)):
            yield from _flatten(value)
        else:
            yield value


class SimpleCADSolidWorksRuntime:
    def __init__(self, payload, document_name, result_node_ids, *, visible=True):
        global MODEL_SCALE
        self.payload = payload
        self.graph = payload.get('graph') or {}
        self.nodes = self.graph.get('nodes') or []
        self.node_by_id = {str(node.get('node_id')): node for node in self.nodes}
        self.child_nodes = {}
        for child in self.nodes:
            for input_ref in child.get('inputs') or []:
                input_id = str(
                    input_ref.get('node_id')
                    if isinstance(input_ref, dict)
                    else input_ref
                )
                self.child_nodes.setdefault(input_id, []).append(child)
        self.canonical_cut_descriptors = dict(
            payload.get('solidworks_canonical_cut_descriptors') or {}
        )
        self.canonical_union_passthroughs = dict(
            payload.get('solidworks_canonical_union_passthroughs') or {}
        )
        self.canonical_union_descriptors = dict(
            payload.get('solidworks_canonical_union_descriptors') or {}
        )
        self.canonical_union_input_indices = dict(
            payload.get('solidworks_canonical_union_input_indices') or {}
        )
        self.canonical_loft_descriptors = dict(
            payload.get('solidworks_canonical_loft_descriptors') or {}
        )
        self.canonical_sweep_descriptors = dict(
            payload.get('solidworks_canonical_sweep_descriptors') or {}
        )
        self.source_kernel_result_step = payload.get(
            'solidworks_source_kernel_result_step'
        )
        self.detail_edge_catalog = {}
        encoded_detail_catalog = payload.get(
            'solidworks_detail_edge_catalog_z'
        )
        if isinstance(encoded_detail_catalog, str) and encoded_detail_catalog:
            try:
                decoded_detail_catalog = json.loads(
                    zlib.decompress(
                        base64.b64decode(encoded_detail_catalog.encode('ascii'))
                    ).decode('ascii')
                )
                if (
                    isinstance(decoded_detail_catalog, dict)
                    and decoded_detail_catalog.get('method') == 'gsm'
                ):
                    self.detail_edge_catalog = dict(
                        decoded_detail_catalog.get('sources') or {}
                    )
            except Exception:
                self.detail_edge_catalog = {}
        self.document_name = document_name
        self.result_node_ids = [str(v) for v in (result_node_ids or [])]
        self.outputs = {}
        self.product_values = {}
        self.selection_payloads = {}
        self.sketch_segments = {}
        self.materialized_source_body_keys = set()
        self.component_instance_counter = 0
        self.assembly_occurrences = []
        self.degraded_features = []
        self.persisted_topology_maps = {}
        self.captured_topology_source_ids = set()
        self.pending_detail_topology = []
        self.logs = []
        self.visible = bool(visible)
        MODEL_SCALE = _model_work_scale(payload)
        self.logs.append(f'SolidWorks working geometry scale: {MODEL_SCALE:.9g}')

        self.sw = None
        self.model = None
        try:
            dispatch = win32com.client.DispatchEx if not visible else win32com.client.Dispatch
            self.sw = dispatch('SldWorks.Application')
            self.sw.Visible = self.visible
            try:
                self.sw.CommandInProgress = True
            except Exception:
                pass
            self.model = self._new_part()
            self._set_document_title(document_name)
            self._set_mmgs_units()
        except Exception:
            try:
                if self.sw is not None:
                    self.sw.CommandInProgress = False
            except Exception:
                pass
            try:
                if self.sw is not None and self.model is not None:
                    self.sw.CloseDoc(str(_maybe_call(self.model.GetTitle)))
            except Exception:
                pass
            if not self.visible:
                try:
                    if self.sw is not None:
                        self.sw.ExitApp()
                except Exception:
                    pass
            raise

    def _result_dependency_ids(self, result_node_ids):
        needed = set()
        pending = [str(node_id) for node_id in (result_node_ids or [])]
        while pending:
            node_id = pending.pop()
            if node_id in needed:
                continue
            node = self.node_by_id.get(node_id)
            if not isinstance(node, dict):
                continue
            needed.add(node_id)
            for ref in node.get('inputs') or []:
                if isinstance(ref, dict) and ref.get('node_id') is not None:
                    pending.append(str(ref.get('node_id')))
            params = node.get('params') or {}
            for key in ('selected_edge_node_ids', 'selected_face_node_ids'):
                pending.extend(str(value) for value in (params.get(key) or []))
        return needed

    def finish(self):
        try:
            if self.sw is not None:
                self.sw.CommandInProgress = False
        except Exception:
            pass
        try:
            if self.sw is not None and self.model is not None:
                self.sw.CloseDoc(str(_maybe_call(self.model.GetTitle)))
        except Exception:
            pass
        if not self.visible:
            try:
                if self.sw is not None:
                    self.sw.ExitApp()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

    def run(self, output_path=None):
        if not self.result_node_ids:
            self.result_node_ids = [str(node.get('node_id')) for node in self.nodes[-1:]]
        active_node_ids = self._result_dependency_ids(self.result_node_ids)
        processed = 0
        total = len(active_node_ids) or len(self.nodes)
        for node in self.nodes:
            if active_node_ids and str(node.get('node_id')) not in active_node_ids:
                continue
            if processed % 25 == 0:
                print(
                    f'SIMPLECAD_SW_PROGRESS={processed}/{total}:'
                    f'{node.get("node_id")}:{node.get("op")}',
                    flush=True,
                )
            node_started = time.perf_counter()
            try:
                self._emit_node(node)
            except Exception as exc:
                if self._write_source_kernel_result_step(
                    output_path, node, exc
                ):
                    return
                raise
            node_elapsed = time.perf_counter() - node_started
            if node_elapsed >= 5.0:
                print(
                    f'SIMPLECAD_SW_SLOW_NODE={node.get("node_id")}:'
                    f'{node.get("op")}:{node_elapsed:.3f}',
                    flush=True,
                )
            processed += 1
        final_bodies = self._result_bodies()
        if not final_bodies:
            raise RuntimeError('SolidWorks translator produced no final solid bodies')
        retained_source_bodies = [
            occurrence.get('source_body')
            for occurrence in self.assembly_occurrences
            if occurrence.get('source_body') is not None
        ]
        final_bodies = self._prune_to_bodies(
            final_bodies, retained_bodies=retained_source_bodies
        )
        final_bodies = self._restore_model_scale(
            final_bodies, retained_bodies=retained_source_bodies
        )
        if (
            self.assembly_occurrences
            and len(self.assembly_occurrences) == len(final_bodies)
        ):
            for occurrence, final_body in zip(
                self.assembly_occurrences, final_bodies
            ):
                occurrence['body'] = final_body
                occurrence['expected_bbox'] = self._box_from_entity(
                    final_body
                )
                # The unplaced source snapshot was captured when the terminal
                # part branch was materialized. By this point Keep Bodies may
                # have consumed both final and source Body2 proxies.
        try:
            self.model.ForceRebuild3(False)
        except Exception:
            pass
        self._persist_document_metadata()
        if output_path:
            native_part_path = _native_part_output_path(output_path)
            self._save_native_part(native_part_path)
            if self.pending_detail_topology and not self.assembly_occurrences:
                self._reopen_native_part(native_part_path)
                self._retry_pending_detail_topology()
                self._persist_document_metadata()
                self._save_native_part(native_part_path)
            self._save_step(output_path)
            if self.assembly_occurrences:
                self._save_native_assembly(
                    output_path,
                    _native_assembly_output_path(output_path),
                )
        if self.logs:
            print('\n'.join(self.logs))

    def _write_source_kernel_result_step(self, output_path, node, error):
        payload = self.source_kernel_result_step
        if not output_path or not isinstance(payload, str) or not payload:
            return False
        try:
            step_bytes = zlib.decompress(base64.b64decode(payload.encode('ascii')))
            if not step_bytes:
                return False
            output_directory = os.path.dirname(os.path.abspath(output_path))
            if output_directory:
                os.makedirs(output_directory, exist_ok=True)
            with open(output_path, 'wb') as output:
                output.write(step_bytes)
            marker = {
                'node_id': str(node.get('node_id')),
                'op': str(node.get('op')),
                'error': f'{type(error).__name__}: {error}',
                'output_path': os.path.abspath(output_path),
            }
            self.logs.append(
                'SolidWorks native reconstruction used validated source-kernel '
                f'result fallback after {marker["node_id"]}:{marker["op"]}'
            )
            self.logs.append(
                'SolidWorks native part was not saved because source-kernel '
                'fallback replaced an incomplete native reconstruction'
            )
            print(
                'SIMPLECAD_SW_SOURCE_KERNEL_FALLBACK='
                + json.dumps(marker, ensure_ascii=True, sort_keys=True),
                flush=True,
            )
            if self.logs:
                print('\n'.join(self.logs))
            return True
        except Exception as fallback_error:
            self.logs.append(
                f'source-kernel result fallback failed: {fallback_error}'
            )
            return False

    def _new_part(self):
        template = self._part_template()
        if template:
            model = self.sw.NewDocument(template, 0, 0.0, 0.0)
            if model is not None:
                return model
        else:
            try:
                new_part = getattr(self.sw, 'NewPart')
                if callable(new_part):
                    new_part()
            except Exception:
                pass
        model = self.sw.ActiveDoc
        if model is None:
            raise RuntimeError('SolidWorks did not create an active part document')
        return model

    def _part_template(self):
        try:
            template = str(self.sw.GetUserPreferenceStringValue(8) or '')
            if template and os.path.exists(template):
                return template
        except Exception:
            pass
        candidates = glob.glob(r'C:\ProgramData\SolidWorks\SOLIDWORKS *\templates\*.prtdot')
        candidates += glob.glob(r'C:\ProgramData\SOLIDWORKS\SOLIDWORKS *\templates\*.prtdot')
        candidates += glob.glob(r'C:\ProgramData\SOLIDWORKS\templates\*.prtdot')
        for candidate in sorted(candidates, reverse=True):
            if os.path.exists(candidate):
                return candidate
        return ''

    def _assembly_template(self):
        try:
            template = str(self.sw.GetUserPreferenceStringValue(9) or '')
            if template and os.path.exists(template):
                return template
        except Exception:
            pass
        candidates = glob.glob(
            r'C:\ProgramData\SolidWorks\SOLIDWORKS *\templates\*.asmdot'
        )
        candidates += glob.glob(
            r'C:\ProgramData\SOLIDWORKS\SOLIDWORKS *\templates\*.asmdot'
        )
        candidates += glob.glob(
            r'C:\ProgramData\SOLIDWORKS\templates\*.asmdot'
        )
        for candidate in sorted(candidates, reverse=True):
            if os.path.exists(candidate):
                return candidate
        return ''

    def _set_document_title(self, document_name):
        try:
            self.model.SetTitle2(str(document_name))
        except Exception:
            pass

    def _set_mmgs_units(self):
        try:
            self.model.SetUnits(0, 0, 0, 3, False)
        except Exception:
            pass

    def _modeler(self):
        # The SolidWorks application object does not expose type information to
        # late-bound pywin32 clients, so GetModeler is unavailable by name even
        # though it is part of ISldWorks. DISP ID 34 is the documented
        # ISldWorks::GetModeler entry in the installed type library.
        raw_modeler = self.sw._oleobj_.InvokeTypes(
            34,
            0,
            pythoncom.DISPATCH_METHOD,
            (pythoncom.VT_DISPATCH, 0),
            (),
        )
        if raw_modeler is None:
            raise RuntimeError('SolidWorks did not provide the geometry modeler')
        return win32com.client.Dispatch(
            raw_modeler,
            resultCLSID='{83A33D73-27C5-11CE-BFD4-00400513BB57}',
        )

    def _create_loft_temp_body(self, sketches, args, *, use_legacy=True):
        modeler = self._modeler()
        # CreateLoftBody consumes the currently selected section sketches and
        # is available on older SolidWorks versions where the FeatureManager
        # loft signatures return None for the same selection.
        raw_body = None
        if use_legacy:
            raw_body = modeler._oleobj_.InvokeTypes(
                115,
                0,
                pythoncom.DISPATCH_METHOD,
                (pythoncom.VT_DISPATCH, 0),
                (
                    (pythoncom.VT_DISPATCH, pythoncom.PARAMFLAG_FIN),
                    (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                    (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                    (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                    (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                    (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                    (pythoncom.VT_I2, pythoncom.PARAMFLAG_FIN),
                    (pythoncom.VT_I2, pythoncom.PARAMFLAG_FIN),
                ),
                self.model,
                False,
                False,
                False,
                True,
                1.0,
                0,
                0,
            )
        if raw_body is not None:
            return win32com.client.Dispatch(raw_body)
        raw_body = modeler._oleobj_.InvokeTypes(
            122,
            0,
            pythoncom.DISPATCH_METHOD,
            (pythoncom.VT_DISPATCH, 0),
            (
                (pythoncom.VT_DISPATCH, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_DISPATCH, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I4, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I4, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I4, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
            ),
            self.model,
            tuple(sketches),
            None,
            None,
            *args,
        )
        return win32com.client.Dispatch(raw_body) if raw_body is not None else None

    def _create_swept_temp_body(self, args):
        modeler = self._modeler()
        raw_body = modeler._oleobj_.InvokeTypes(
            102,
            0,
            pythoncom.DISPATCH_METHOD,
            (pythoncom.VT_DISPATCH, 0),
            (
                (pythoncom.VT_DISPATCH, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I2, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I2, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I2, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I2, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I2, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
            ),
            self.model,
            *args,
        )
        return win32com.client.Dispatch(raw_body) if raw_body is not None else None

    def _save_step(self, output_path):
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        if os.path.exists(output_path):
            os.remove(output_path)
        errors = _byref_i4()
        warnings = _byref_i4()
        ok = self.model.Extension.SaveAs(
            output_path,
            SW_SAVE_AS_CURRENT_VERSION,
            SW_SAVE_AS_OPTIONS_SILENT,
            _empty_dispatch(),
            errors,
            warnings,
        )
        if not ok or not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
            raise RuntimeError(
                f'SolidWorks SaveAs STEP failed: ok={ok!r}, errors={errors.value}, warnings={warnings.value}'
            )

    def _save_native_part(self, output_path):
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        errors = _byref_i4()
        warnings = _byref_i4()
        try:
            current_path = os.path.abspath(
                str(_maybe_call(self.model.GetPathName) or '')
            )
        except Exception:
            current_path = ''
        if current_path and os.path.normcase(current_path) == os.path.normcase(
            output_path
        ):
            ok = self.model.Save3(
                SW_SAVE_AS_OPTIONS_SILENT, errors, warnings
            )
        else:
            if os.path.exists(output_path):
                os.remove(output_path)
            ok = self.model.Extension.SaveAs(
                output_path,
                SW_SAVE_AS_CURRENT_VERSION,
                SW_SAVE_AS_OPTIONS_SILENT,
                _empty_dispatch(),
                errors,
                warnings,
            )
        if not ok or not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
            raise RuntimeError(
                f'SolidWorks SaveAs SLDPRT failed: ok={ok!r}, errors={errors.value}, warnings={warnings.value}'
            )
        print(
            'SIMPLECAD_SW_NATIVE_PART=' + os.path.abspath(output_path),
            flush=True,
        )

    def _reopen_native_part(self, output_path):
        output_path = os.path.abspath(output_path)
        try:
            title = str(_maybe_call(self.model.GetTitle) or '')
        except Exception:
            title = ''
        if title:
            self.sw.CloseDoc(title)
        try:
            self.sw.CommandInProgress = False
        except Exception:
            pass
        try:
            self.sw.ExitApp()
        except Exception:
            pass
        self.sw = win32com.client.DispatchEx('SldWorks.Application')
        self.sw.Visible = self.visible
        errors = _byref_i4()
        warnings = _byref_i4()
        reopened = self.sw.OpenDoc6(
            output_path,
            SW_DOC_PART,
            SW_OPEN_DOC_OPTIONS_SILENT,
            '',
            errors,
            warnings,
        )
        if reopened is None or int(errors.value) != 0:
            raise RuntimeError(
                f'SolidWorks could not reopen native baseline; '
                f'errors={errors.value} warnings={warnings.value}'
            )
        self.model = reopened
        self.logs.append(
            f'reopened native baseline for topology persistence: '
            f'{output_path}'
        )

    def _save_native_assembly(self, step_path, assembly_path):
        master_model = self.model
        master_title = str(_maybe_call(master_model.GetTitle))
        assembly_path = os.path.abspath(assembly_path)
        assembly_directory = os.path.dirname(assembly_path)
        component_directory = os.path.join(
            assembly_directory,
            os.path.splitext(os.path.basename(assembly_path))[0]
            + '_components',
        )
        os.makedirs(component_directory, exist_ok=True)
        master_part_path = _native_part_output_path(step_path)
        package_master_path = os.path.join(
            component_directory, '_SimpleCADMaster.sldprt'
        )
        shutil.copy2(master_part_path, package_master_path)
        component_records = []
        prepared_occurrences = []
        self.model = master_model
        for occurrence in self.assembly_occurrences:
            prepared_occurrences.append((
                occurrence,
                occurrence.get('prepared_source_body')
                or self._copy_temp_body(
                    occurrence.get('source_body') or occurrence.get('body')
                ),
            ))

        for index, (occurrence, temp_body) in enumerate(prepared_occurrences):
            component_id = str(
                occurrence.get('component_id') or f'component_{index + 1}'
            )
            source_node_id = str(
                occurrence.get('source_node_id') or ''
            )
            token = ''.join(
                character if character.isalnum() or character in '._-'
                else '_'
                for character in component_id
            ) or f'component_{index + 1}'
            if any(record['component_id'] == component_id for record in component_records):
                token += f'_{index + 1}'
            component_path = os.path.join(
                component_directory, token + '.sldprt'
            )
            component_model = self.sw.NewDocument(
                self._part_template(), 0, 0.0, 0.0
            )
            if component_model is None:
                component_model = self.sw.ActiveDoc
            if component_model is None:
                raise RuntimeError(
                    f'Could not create component part for {component_id}'
                )
            feature = None
            derived_component = False
            self.model = component_model
            try:
                try:
                    part_doc = win32com.client.CastTo(
                        component_model, 'IPartDoc'
                    )
                except Exception:
                    part_doc = component_model
                derived_feature = None
                for api_name, call in (
                    (
                        'InsertPart3',
                        lambda: part_doc.InsertPart3(
                            package_master_path, 1, ''
                        ),
                    ),
                    (
                        'InsertPart2',
                        lambda: part_doc.InsertPart2(
                            package_master_path, 1
                        ),
                    ),
                    (
                        'InsertPart',
                        lambda: part_doc.InsertPart(
                            package_master_path, False, False, False
                        ),
                    ),
                ):
                    try:
                        derived_feature = call()
                        if derived_feature is not None:
                            self.logs.append(
                                f'{component_id} derived part uses '
                                f'{api_name}'
                            )
                            break
                    except Exception as exc:
                        self.logs.append(
                            f'{component_id} {api_name} failed: {exc}'
                        )
                if derived_feature is not None:
                    derived_feature.Name = (
                        f'SimpleCADDerived_{token}'
                    )
                    component_model.ForceRebuild3(False)
                    candidates = self._solid_bodies()
                    expected_bbox = occurrence.get('source_expected_bbox')
                    if not candidates or not isinstance(expected_bbox, dict):
                        raise RuntimeError(
                            'derived component has no selectable result bodies'
                        )
                    source_node_id = str(
                        occurrence.get('source_node_id') or ''
                    )
                    source_body_name = str(
                        occurrence.get('source_body_name') or ''
                    )
                    source_owner = str(
                        occurrence.get('source_owner') or ''
                    )

                    def candidate_labels(candidate):
                        labels = [self._body_name(candidate)]
                        for getter_name in ('GetFeature', 'IGetFeature'):
                            try:
                                owner = _maybe_call(
                                    getattr(candidate, getter_name)
                                )
                                owner_name = str(
                                    _maybe_call(owner.Name) if owner else ''
                                )
                                if owner_name:
                                    labels.append(owner_name)
                                    break
                            except Exception:
                                pass
                        return labels

                    exact_candidates = []
                    node_candidates = []
                    for candidate in candidates:
                        labels = candidate_labels(candidate)
                        if any(
                            expected and expected in labels
                            for expected in (source_body_name, source_owner)
                        ):
                            exact_candidates.append(candidate)
                        elif source_node_id and any(
                            source_node_id in label for label in labels
                        ):
                            node_candidates.append(candidate)
                    preferred = exact_candidates or node_candidates or candidates
                    ranked = sorted(
                        [
                            [
                                _bbox_score(
                                    self._box_from_entity(candidate),
                                    expected_bbox,
                                ),
                                candidate,
                            ]
                            for candidate in preferred
                        ],
                        key=lambda item: item[0],
                    )
                    best_score, selected_body = ranked[0]
                    expected_size = _distance(
                        expected_bbox.get('min'), expected_bbox.get('max')
                    )
                    match_tolerance = max(
                        1.0e-7, expected_size * 1.0e-6
                    )
                    matching = [
                        candidate for score, candidate in ranked
                        if score <= match_tolerance
                    ]
                    if best_score > match_tolerance:
                        raise RuntimeError(
                            f'derived component body mismatch: {best_score}'
                        )
                    if len(matching) != 1:
                        raise RuntimeError(
                            f'derived component body match is ambiguous: '
                            f'{len(matching)} candidates'
                        )
                    if len(candidates) > 1:
                        self._clear_selection()
                        if not self._select_entity(selected_body):
                            raise RuntimeError(
                                'could not select derived component body'
                            )
                        keep_feature = (
                            component_model.FeatureManager.InsertDeleteBody2(
                                True
                            )
                        )
                        self._clear_selection()
                        if keep_feature is None:
                            raise RuntimeError(
                                'could not keep derived component body'
                            )
                        keep_feature.Name = (
                            f'SimpleCADKeep_{token}'
                        )
                        feature = keep_feature
                    else:
                        feature = derived_feature
                    component_model.ForceRebuild3(False)
                    if len(self._solid_bodies()) != 1:
                        raise RuntimeError(
                            'derived component did not resolve to one body'
                        )
                    if MODEL_SCALE > 1.0 + 1.0e-12:
                        scaled_body = self._solid_bodies()[0]
                        self._clear_selection()
                        if not self._select_solid_body(
                            scaled_body, append=False, mark=1
                        ):
                            raise RuntimeError(
                                'could not select derived component for scale'
                            )
                        factor = 1.0 / MODEL_SCALE
                        scale_feature = (
                            component_model.FeatureManager.InsertScale(
                                1, True, factor, factor, factor
                            )
                        )
                        self._clear_selection()
                        if scale_feature is None:
                            raise RuntimeError(
                                'could not restore derived component scale'
                            )
                        scale_feature.Name = (
                            f'SimpleCADScale_{token}'
                        )
                        feature = scale_feature
                        component_model.ForceRebuild3(False)
                        if len(self._solid_bodies()) != 1:
                            raise RuntimeError(
                                'scaled derived component did not resolve '
                                'to one body'
                            )
                    derived_component = True
            except Exception as exc:
                self.logs.append(
                    f'live derived component failed for {component_id}: '
                    f'{exc}'
                )
            finally:
                self.model = master_model
            if not derived_component:
                component_title = str(_maybe_call(component_model.GetTitle))
                self.sw.CloseDoc(component_title)
                component_model = self.sw.NewDocument(
                    self._part_template(), 0, 0.0, 0.0
                )
                if component_model is None:
                    component_model = self.sw.ActiveDoc
                feature = None
                if MODEL_SCALE > 1.0 + 1.0e-12:
                    scale_matrix = _identity_matrix()
                    scale_matrix[12] = 1.0 / MODEL_SCALE
                    self._apply_transform_to_temp_body(
                        temp_body, scale_matrix
                    )
                self._mark_degraded(
                    f'SimpleCADComponent_{token}',
                    'static_component_body',
                )
                for call in (
                    lambda: component_model.CreateFeatureFromBody3(
                        temp_body, False, 0
                    ),
                    lambda: component_model.CreateFeatureFromBody2(
                        temp_body, False, 0
                    ),
                    lambda: component_model.CreateFeatureFromBody(temp_body),
                ):
                    try:
                        feature = call()
                        if feature is not None:
                            break
                    except Exception:
                        pass
            if feature is None:
                raise RuntimeError(
                    f'Could not materialize component part for {component_id}'
                )
            try:
                feature.Name = f'SimpleCADComponent_{token}'
            except Exception:
                pass
            properties = component_model.Extension.CustomPropertyManager('')
            component_properties = {
                'SimpleCADComponentId': component_id,
                'SimpleCADSourceNodeId': source_node_id,
                'SimpleCADDegradedStaticComponent': (
                    'false' if derived_component else 'true'
                ),
                'SimpleCADMasterPartPath': package_master_path,
            }
            for property_name, property_value in component_properties.items():
                self._set_document_custom_property(
                    properties, property_name, property_value
                )
                if self._document_custom_property_value(
                    properties, property_name
                ) != str(property_value):
                    raise RuntimeError(
                        f'component property readback mismatch for '
                        f'{component_id}:{property_name}'
                    )
            dependency_node_ids = list(
                occurrence.get('dependency_node_ids') or []
            )
            self._persist_chunked_json_property(
                properties,
                'SimpleCADDependencies',
                {
                    'component_id': component_id,
                    'source_node_id': source_node_id,
                    'dependency_node_ids': dependency_node_ids,
                },
                'simplecad-sw-component-dependencies-v1',
            )
            errors = _byref_i4()
            warnings = _byref_i4()
            ok = component_model.Extension.SaveAs(
                component_path,
                SW_SAVE_AS_CURRENT_VERSION,
                SW_SAVE_AS_OPTIONS_SILENT,
                _empty_dispatch(),
                errors,
                warnings,
            )
            if not ok or not os.path.exists(component_path):
                raise RuntimeError(
                    f'Could not save component part for {component_id}; '
                    f'errors={errors.value} warnings={warnings.value}'
                )
            component_title = str(_maybe_call(component_model.GetTitle))
            self.sw.CloseDoc(component_title)
            activate_errors = _byref_i4()
            try:
                self.sw.ActivateDoc3(
                    master_title, False, 1, activate_errors
                )
            except Exception:
                self.sw.ActivateDoc2(master_title, False, activate_errors)
            component_records.append({
                'component_id': component_id,
                'path': component_path,
                'graph_path': list(occurrence.get('path') or ()),
                'derived_component': derived_component,
                'source_node_id': source_node_id,
                'dependency_node_ids': dependency_node_ids,
                'transform': _assembly_component_matrix(
                    occurrence.get('placements') or ()
                ),
            })
            print(
                f'SIMPLECAD_SW_ASSEMBLY_PARTS={index + 1}/'
                f'{len(prepared_occurrences)}:{component_id}',
                flush=True,
            )

        assembly_model = self.sw.NewDocument(
            self._assembly_template(), 0, 0.0, 0.0
        )
        if assembly_model is None:
            assembly_model = self.sw.ActiveDoc
        if assembly_model is None:
            raise RuntimeError('Could not create SolidWorks assembly document')
        try:
            assembly_doc = win32com.client.CastTo(
                assembly_model, 'IAssemblyDoc'
            )
        except Exception:
            assembly_doc = assembly_model
        assembly_title = str(_maybe_call(assembly_model.GetTitle))
        inserted = []
        for insertion_index, record in enumerate(component_records):
            open_errors = _byref_i4()
            open_warnings = _byref_i4()
            component_model = self.sw.OpenDoc6(
                record['path'],
                1,
                SW_OPEN_DOC_OPTIONS_SILENT,
                '',
                open_errors,
                open_warnings,
            )
            if component_model is None:
                raise RuntimeError(
                    f"Could not load assembly component "
                    f"{record['component_id']}; errors={open_errors.value} "
                    f"warnings={open_warnings.value}"
                )
            activate_errors = _byref_i4()
            try:
                self.sw.ActivateDoc3(
                    assembly_title, False, 1, activate_errors
                )
            except Exception:
                self.sw.ActivateDoc2(
                    assembly_title, False, activate_errors
                )
            component = assembly_doc.AddComponent5(
                record['path'], 0, '', False, '', 0.0, 0.0, 0.0
            )
            if component is None:
                raise RuntimeError(
                    f"Could not insert assembly component "
                    f"{record['component_id']}"
                )
            # AddComponent5 requires the part to be loaded first, but the
            # assembly owns that loaded reference after insertion. Keeping
            # every OpenDoc6 result open as a top-level document exhausts the
            # COM server on large assemblies (069 has 60 unique parts).
            component_title = str(_maybe_call(component_model.GetTitle))
            try:
                self.sw.CloseDoc(component_title)
            except Exception as exc:
                self.logs.append(
                    f"could not close inserted component document "
                    f"{record['component_id']}: {exc}"
                )
            component_model = None
            graph_path_json = json.dumps(
                record.get('graph_path') or [],
                ensure_ascii=True,
                separators=(',', ':'),
            )
            graph_path_digest = hashlib.sha256(
                graph_path_json.encode('ascii')
            ).hexdigest()[:16]
            expected_reference = (
                f"{record['component_id']}|"
                f"{record.get('source_node_id') or ''}|"
                f"{graph_path_digest}"
            )
            try:
                component.ComponentReference = expected_reference
                actual_reference = str(
                    _maybe_call(component.ComponentReference) or ''
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Could not persist component reference for "
                    f"{record['component_id']}: {exc}"
                ) from exc
            if actual_reference != expected_reference:
                raise RuntimeError(
                    f"Component reference readback mismatch for "
                    f"{record['component_id']}: expected="
                    f"{expected_reference!r} actual={actual_reference!r}"
                )
            record['component_reference'] = expected_reference
            try:
                component.Name2 = (
                    f"{record['component_id']}__"
                    f"{record['source_node_id']}"
                    if record.get('source_node_id')
                    else record['component_id']
                )
            except Exception:
                pass
            try:
                component.Select4(False, _empty_dispatch(), False)
                assembly_doc.UnfixComponent()
                assembly_model.ClearSelection2(True)
            except Exception:
                pass
            expected_transform = [
                float(value) for value in record.get('transform')
                or _identity_matrix()
            ]
            transform = None
            try:
                math_utility = self.sw.GetMathUtility
                array_data = win32com.client.VARIANT(
                    pythoncom.VT_ARRAY | pythoncom.VT_R8,
                    expected_transform,
                )
                raw_transform = math_utility._oleobj_.InvokeTypes(
                    1,
                    0,
                    pythoncom.DISPATCH_METHOD,
                    (pythoncom.VT_DISPATCH, 0),
                    ((pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),),
                    array_data,
                )
                if raw_transform is not None:
                    transform = win32com.client.Dispatch(raw_transform)
            except Exception as exc:
                raise RuntimeError(
                    f"Could not create component transform for "
                    f"{record['component_id']}: {exc}"
                ) from exc
            if transform is None:
                raise RuntimeError(
                    f"Could not create component transform for "
                    f"{record['component_id']}"
                )
            try:
                component.Transform2 = transform
            except Exception as exc:
                raise RuntimeError(
                    f"Could not set component transform for "
                    f"{record['component_id']}: {exc}"
                ) from exc
            try:
                actual_transform = component.Transform2
                actual_data = [
                    float(value) for value in actual_transform.ArrayData
                ]
            except Exception as exc:
                raise RuntimeError(
                    f"Could not read component transform for "
                    f"{record['component_id']}: {exc}"
                ) from exc
            if not _transform_matrices_close(
                actual_data, expected_transform
            ):
                raise RuntimeError(
                    f"Component transform readback mismatch for "
                    f"{record['component_id']}: expected="
                    f"{expected_transform[:13]!r} actual="
                    f"{actual_data[:13]!r}"
                )
            inserted.append(component)
            print(
                f'SIMPLECAD_SW_ASSEMBLY_INSERT={insertion_index + 1}/'
                f'{len(component_records)}:{record["component_id"]}',
                flush=True,
            )
        if len(inserted) != len(component_records):
            raise RuntimeError('SolidWorks assembly component count mismatch')
        rebuild_ok = assembly_model.ForceRebuild3(False)
        if rebuild_ok is False:
            raise RuntimeError(
                'Assembly rebuild failed after inserting native components'
            )
        properties = assembly_model.Extension.CustomPropertyManager('')
        self._persist_chunked_json_property(
            properties,
            'SimpleCADComponentMap',
            component_records,
            'simplecad-sw-component-map-v1',
        )
        self._set_document_custom_property(
            properties, 'SimpleCADMasterPartPath', package_master_path
        )
        if self._document_custom_property_value(
            properties, 'SimpleCADMasterPartPath'
        ) != package_master_path:
            raise RuntimeError(
                'assembly master-part property readback mismatch'
            )
        rebuild_ok = assembly_model.ForceRebuild3(False)
        if rebuild_ok is False:
            raise RuntimeError(
                'Assembly rebuild failed after persisting component metadata'
            )
        os.makedirs(assembly_directory, exist_ok=True)
        if os.path.exists(assembly_path):
            os.remove(assembly_path)
        errors = _byref_i4()
        warnings = _byref_i4()
        ok = assembly_model.Extension.SaveAs(
            assembly_path,
            SW_SAVE_AS_CURRENT_VERSION,
            SW_SAVE_AS_OPTIONS_SILENT,
            _empty_dispatch(),
            errors,
            warnings,
        )
        if not ok or not os.path.exists(assembly_path):
            raise RuntimeError(
                f'SolidWorks SaveAs SLDASM failed: ok={ok!r}, '
                f'errors={errors.value}, warnings={warnings.value}'
            )
        self.model = assembly_model
        self._save_step(step_path)
        try:
            self.sw.CloseDoc(master_title)
        except Exception:
            pass
        print(
            'SIMPLECAD_SW_NATIVE_ASSEMBLY=' + assembly_path,
            flush=True,
        )

    def _input_ids(self, node):
        return [str(ref.get('node_id')) for ref in (node.get('inputs') or []) if isinstance(ref, dict)]

    def _is_terminal_part_feature(self, node_id):
        if str(node_id) in self.result_node_ids:
            return True
        children = self.child_nodes.get(str(node_id)) or []
        return bool(children) and all(
            str(child.get('op') or '') in {
                'make_part_rpart',
                'make_assign_material_rpart',
            }
            for child in children
        )

    def _mark_degraded(self, feature_name, reason):
        marker = {
            'feature': str(feature_name),
            'reason': str(reason),
        }
        if marker not in self.degraded_features:
            self.degraded_features.append(marker)
        self.logs.append(
            'SIMPLECAD_SW_DEGRADED=' + json.dumps(
                marker, ensure_ascii=True, sort_keys=True
            )
        )

    def _persistent_reference_bytes(self, entity):
        def coerce(value):
            if value is None:
                return None
            if isinstance(value, bytes):
                return value
            if isinstance(value, bytearray):
                return bytes(value)
            if isinstance(value, memoryview):
                return value.tobytes()
            if hasattr(value, 'value'):
                nested = coerce(value.value)
                if nested:
                    return nested
            if isinstance(value, (list, tuple)):
                if value and all(
                    isinstance(item, int) and 0 <= item <= 255
                    for item in value
                ):
                    return bytes(value)
                for item in value:
                    nested = coerce(item)
                    if nested:
                        return nested
            return None

        extension = self.model.Extension
        for call in (
            lambda: extension.GetPersistReference3(entity),
            lambda: extension.GetPersistReference(entity),
        ):
            try:
                reference = coerce(call())
                if reference:
                    return reference
            except Exception:
                pass
        return None

    def _resolve_persistent_reference_bytes(self, reference):
        if not reference:
            return None
        try:
            value = win32com.client.VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_UI1,
                tuple(bytes(reference)),
            )
            error = win32com.client.VARIANT(
                pythoncom.VT_BYREF | pythoncom.VT_I4, 0
            )
            entity = self.model.Extension.GetObjectByPersistReference3(
                value, error
            )
            if entity is not None and int(error.value) == 0:
                return entity
        except Exception:
            pass
        return None

    def _detail_result_descriptor(self, source_node_id, detail_node_id):
        source_catalog = self.detail_edge_catalog.get(str(source_node_id))
        if not isinstance(source_catalog, dict):
            return None
        target = (source_catalog.get('targets') or {}).get(
            str(detail_node_id)
        )
        if not isinstance(target, dict):
            return None
        descriptor = target.get('result_descriptor')
        return descriptor if isinstance(descriptor, dict) else None

    def _validate_detail_result(
        self, bodies, canonical_result, kind, node_id
    ):
        if not isinstance(canonical_result, dict):
            self.logs.append(
                f'{kind} {node_id} has no canonical result descriptor'
            )
            return
        values = [body for body in self._bodies_from_value(bodies) if body]
        matches = (
            self._body_matches_canonical(
                values[0], canonical_result,
                volume_relative_tolerance=3.0e-5,
            )
            if len(values) == 1
            else self._body_set_matches_canonical(
                values, canonical_result,
                volume_relative_tolerance=3.0e-5,
            )
        )
        if matches:
            self.logs.append(
                f'{kind} {node_id} matched canonical result bbox/volume'
            )
            return
        actual_bboxes = [self._box_from_entity(body) for body in values]
        actual_volumes = [self._body_volume(body) for body in values]
        raise RuntimeError(
            f'SolidWorks {kind} feature {node_id} did not change the live '
            f'body to the canonical result; actual_bboxes={actual_bboxes!r}; '
            f'actual_volumes={actual_volumes!r}; '
            f'canonical={canonical_result!r}; logs={self.logs[-20:]!r}'
        )

    def _capture_detail_source_topology(self, source_node_id, sources):
        source_node_id = str(source_node_id)
        if source_node_id in self.captured_topology_source_ids:
            return
        self.captured_topology_source_ids.add(source_node_id)
        catalog = self.detail_edge_catalog.get(source_node_id)
        if not isinstance(catalog, dict):
            return
        edge_catalog = catalog.get('edges') or []
        targets = dict(catalog.get('targets') or {})
        source_bodies = (
            list(sources)
            if isinstance(sources, (list, tuple))
            else [sources]
        )
        native_signatures = [
            (edge, self._edge_signature(edge))
            for source in source_bodies
            if source is not None
            for edge in self._body_edges(source)
        ]
        references_to_indices = {}
        failed = 0
        failure_details = []
        for entry in edge_catalog:
            if not isinstance(entry, dict):
                failed += 1
                failure_details.append({'index': None, 'reason': 'invalid_entry'})
                continue
            canonical_index = entry.get('canonical_index')
            try:
                canonical_index = int(canonical_index)
                selector = dict(entry.get('selector') or {})
                candidates = _selection_candidates_by_geometry(
                    native_signatures,
                    selector,
                    f'persisted edge {source_node_id}:{canonical_index}',
                )
                if len(candidates) != 1:
                    failed += 1
                    failure_details.append({
                        'index': canonical_index,
                        'reason': f'native_candidate_count={len(candidates)}',
                    })
                    continue
                reference = self._persistent_reference_bytes(candidates[0])
                if not reference:
                    failed += 1
                    failure_details.append({
                        'index': canonical_index,
                        'reason': 'empty_persistent_reference',
                    })
                    continue
                encoded = base64.b64encode(reference).decode('ascii')
                references_to_indices.setdefault(encoded, []).append(
                    canonical_index
                )
            except Exception as exc:
                failed += 1
                failure_details.append({
                    'index': canonical_index,
                    'reason': f'{type(exc).__name__}: {exc}',
                })
        mappings = {
            str(indices[0]): [reference]
            for reference, indices in references_to_indices.items()
            if len(indices) == 1
        }
        collapsed = sum(
            len(indices)
            for indices in references_to_indices.values()
            if len(indices) > 1
        )
        self.persisted_topology_maps[source_node_id] = {
            'source_node_id': source_node_id,
            'mappings': mappings,
            'targets': targets,
        }
        self.logs.append(
            f'persisted GSM topology map prepared for {source_node_id}: '
            f'bodies={len(source_bodies)} mapped={len(mappings)} '
            f'failed={failed} collapsed={collapsed}'
        )
        if failure_details:
            self.logs.append(
                f'persisted GSM topology failures for {source_node_id}: '
                f'{failure_details[:12]!r}'
            )

    def _capture_detail_feature_topology(
        self, feature, result_body, source_node_id, detail_node_id
    ):
        stage = 'resolve_feature'
        source_map = self.persisted_topology_maps.get(str(source_node_id))
        if not isinstance(source_map, dict):
            return
        target = (source_map.get('targets') or {}).get(str(detail_node_id))
        if not isinstance(target, dict):
            return
        canonical_indices = [
            int(value) for value in target.get('selected_indices') or []
        ]
        if not canonical_indices:
            return
        definition = None
        accessed = False
        try:
            feature_name = (
                str(feature)
                if isinstance(feature, str)
                else str(_maybe_call(feature.Name) or '')
            )
            persistent_features = [
                candidate
                for candidate in self._features({'Fillet', 'Chamfer'})
                if str(_maybe_call(candidate.Name) or '') == feature_name
            ]
            if len(persistent_features) == 1:
                feature = persistent_features[0]
                self.logs.append(
                    f'rebound persistent detail feature {feature_name}'
                )
            if result_body is None:
                reopened_bodies = self._solid_bodies()
                if len(reopened_bodies) == 1:
                    result_body = reopened_bodies[0]
            stage = 'get_definition'
            definition_value = feature.GetDefinition
            definition = (
                definition_value
                if hasattr(definition_value, '_oleobj_')
                else _maybe_call(definition_value)
            )
            if definition is None:
                return
            stage = 'access_selections'
            for call in (
                lambda: definition.AccessSelections(
                    self.model, _empty_dispatch()
                ),
                lambda: definition.AccessSelections(self.model, None),
            ):
                try:
                    accessed = bool(call())
                    if accessed:
                        break
                except Exception:
                    pass
            stage = 'query_detail_interface'
            edge_definition = definition
            edge_dispids = (21, 17)
            for interface_iid, edges_dispid in (
                ('{9FE7C8DB-8A4C-41BB-8E3B-7600692DBC92}', 21),
                ('{8427D092-A1FC-49C9-B1ED-EC52D2389E9A}', 17),
            ):
                try:
                    interface = definition._oleobj_.QueryInterface(
                        pythoncom.MakeIID(interface_iid),
                        pythoncom.IID_IDispatch,
                    )
                    edge_definition = win32com.client.Dispatch(interface)
                    edge_dispids = (edges_dispid,)
                    break
                except Exception:
                    pass
            stage = 'read_feature_edges'
            try:
                edges = _maybe_call(edge_definition.Edges)
            except Exception:
                edges = None
                for dispid in edge_dispids:
                    try:
                        edges = edge_definition._oleobj_.InvokeTypes(
                            dispid,
                            0,
                            pythoncom.DISPATCH_PROPERTYGET,
                            (pythoncom.VT_VARIANT, 0),
                            (),
                        )
                        break
                    except Exception:
                        pass
            edges = (
                list(edges)
                if isinstance(edges, (list, tuple))
                else ([edges] if edges is not None else [])
            )
            source_catalog = self.detail_edge_catalog.get(
                str(source_node_id)
            ) or {}
            edge_catalog = source_catalog.get('edges') or []
            feature_mappings = {}
            if len(edges) == len(canonical_indices):
                stage = 'persist_feature_edges'
                for canonical_index, edge in zip(canonical_indices, edges):
                    reference = self._persistent_reference_bytes(edge)
                    if not reference:
                        raise RuntimeError(
                            f'empty FeatureData reference for canonical edge '
                            f'{canonical_index}'
                        )
                    feature_mappings[str(canonical_index)] = [
                        base64.b64encode(reference).decode('ascii')
                    ]
            else:
                self.logs.append(
                    f'native detail seed count differs for '
                    f'{detail_node_id}: FeatureData edges={len(edges)} '
                    f'canonical={len(canonical_indices)}; applying strict '
                    'reconstruction-stage geometry mapping'
                )
                entries_by_index = {
                    int(entry.get('canonical_index')): entry
                    for entry in edge_catalog
                    if isinstance(entry, dict)
                    and entry.get('canonical_index') is not None
                }
                selected_entries = [
                    entries_by_index.get(canonical_index)
                    for canonical_index in canonical_indices
                ]
                if any(entry is None for entry in selected_entries):
                    raise RuntimeError(
                        'canonical detail seed catalog is incomplete'
                    )
                selectors = [
                    dict(entry.get('selector') or {})
                    for entry in selected_entries
                ]
                feature_signatures = [
                    (edge, self._edge_signature(edge)) for edge in edges
                ]
                individual_candidates = {}
                individual_errors = {}
                for selector_index, selector in enumerate(selectors):
                    try:
                        individual_candidates[selector_index] = (
                            _selection_candidates_by_geometry(
                                feature_signatures,
                                selector,
                                f'FeatureData edge {detail_node_id}:'
                                f'{canonical_indices[selector_index]}',
                            )
                        )
                    except RuntimeError as exc:
                        individual_errors[selector_index] = exc
                coalesced_pairs = _coalesced_edge_selector_pairs(
                    feature_signatures, selectors
                )
                coalesced_pairs = [
                    pair for pair in coalesced_pairs
                    if pair[0] in individual_errors
                    or pair[1] in individual_errors
                ]
                coalesced_candidates = {}
                for left_index, right_index, candidate_index in coalesced_pairs:
                    candidate = feature_signatures[candidate_index][0]
                    coalesced_candidates[left_index] = [candidate]
                    coalesced_candidates[right_index] = [candidate]
                for selector_index, canonical_index in enumerate(
                    canonical_indices
                ):
                    candidates = coalesced_candidates.get(selector_index)
                    if candidates is None:
                        candidates = individual_candidates.get(selector_index)
                    if not candidates:
                        continue
                    references = []
                    for edge in candidates:
                        reference = self._persistent_reference_bytes(edge)
                        if not reference:
                            references = []
                            break
                        encoded = base64.b64encode(reference).decode('ascii')
                        if encoded not in references:
                            references.append(encoded)
                    if references:
                        feature_mappings[str(canonical_index)] = references
            target['feature_mappings'] = feature_mappings
            feature_reference_owners = {}
            for canonical_index, references in feature_mappings.items():
                for reference in references:
                    feature_reference_owners.setdefault(reference, []).append(
                        int(canonical_index)
                    )
            target['feature_reference_owners'] = {
                reference: sorted(indices)
                for reference, indices in feature_reference_owners.items()
            }
            target['feature_seed_count'] = len(edges)
            self.logs.append(
                f'persisted native detail seed mapping for {detail_node_id}: '
                f'entries={len(feature_mappings)} '
                f'canonical={len(canonical_indices)}'
            )

            stage = 'persist_post_feature_edges'
            selected_set = set(canonical_indices)
            result_signatures = [
                (edge, self._edge_signature(edge))
                for edge in self._body_edges(result_body)
            ]
            post_references_to_indices = {}
            post_failures = 0
            for entry in edge_catalog:
                try:
                    canonical_index = int(entry.get('canonical_index'))
                    if canonical_index in selected_set:
                        continue
                    candidates = _selection_candidates_by_geometry(
                        result_signatures,
                        dict(entry.get('selector') or {}),
                        f'post-detail edge {detail_node_id}:'
                        f'{canonical_index}',
                    )
                    if len(candidates) != 1:
                        post_failures += 1
                        continue
                    reference = self._persistent_reference_bytes(
                        candidates[0]
                    )
                    if not reference:
                        post_failures += 1
                        continue
                    encoded = base64.b64encode(reference).decode('ascii')
                    post_references_to_indices.setdefault(
                        encoded, []
                    ).append(canonical_index)
                except Exception:
                    post_failures += 1
            post_feature_mappings = {
                str(indices[0]): [reference]
                for reference, indices in post_references_to_indices.items()
                if len(indices) == 1
            }
            target['post_feature_mappings'] = post_feature_mappings
            self.logs.append(
                f'persisted post-detail replacement mapping for '
                f'{detail_node_id}: entries={len(post_feature_mappings)} '
                f'failed={post_failures}'
            )
        except Exception as exc:
            self.logs.append(
                f'could not persist native detail seed mapping for '
                f'{detail_node_id} at {stage}: {exc}'
            )
        finally:
            if definition is not None and accessed:
                try:
                    definition.ReleaseSelectionAccess()
                except Exception:
                    pass

    def _retry_pending_detail_topology(self):
        for record in self.pending_detail_topology:
            source_id = str(record.get('source_node_id') or '')
            target_id = str(record.get('detail_node_id') or '')
            source_map = self.persisted_topology_maps.get(source_id) or {}
            target = (source_map.get('targets') or {}).get(target_id) or {}
            if target.get('feature_mappings'):
                continue
            self._capture_detail_feature_topology(
                record.get('feature_name') or record.get('feature'),
                None,
                source_id,
                target_id,
            )

    def _set_document_custom_property(self, manager, name, value):
        errors = []
        for call in (
            lambda: manager.Add3(str(name), 30, str(value), 2),
            lambda: manager.Set2(str(name), str(value)),
        ):
            try:
                call()
                return
            except Exception as exc:
                errors.append(str(exc))
        raise RuntimeError(
            f'could not write custom property {name!r}: {errors!r}'
        )

    def _document_custom_property_value(self, manager, name):
        try:
            return str(_maybe_call(manager.Get(str(name))) or '')
        except Exception as exc:
            raise RuntimeError(
                f'could not read custom property {name!r}: {exc}'
            ) from exc

    def _persist_chunked_json_property(
        self, manager, prefix, payload, schema
    ):
        raw = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(',', ':'),
            sort_keys=True,
        ).encode('ascii')
        encoded = base64.b64encode(
            zlib.compress(raw, level=9)
        ).decode('ascii')
        chunk_size = 900
        chunks = [
            encoded[index:index + chunk_size]
            for index in range(0, len(encoded), chunk_size)
        ] or ['']
        metadata = json.dumps(
            {
                'schema': str(schema),
                'chunks': len(chunks),
                'sha256': hashlib.sha256(raw).hexdigest(),
            },
            ensure_ascii=True,
            separators=(',', ':'),
            sort_keys=True,
        )
        for index, chunk in enumerate(chunks):
            self._set_document_custom_property(
                manager, f'{prefix}.{index:04d}', chunk
            )
        self._set_document_custom_property(
            manager, f'{prefix}.Meta', metadata
        )

        persisted_meta = json.loads(
            self._document_custom_property_value(
                manager, f'{prefix}.Meta'
            )
        )
        persisted_encoded = ''.join(
            self._document_custom_property_value(
                manager, f'{prefix}.{index:04d}'
            )
            for index in range(int(persisted_meta.get('chunks', 0)))
        )
        persisted_raw = zlib.decompress(
            base64.b64decode(persisted_encoded.encode('ascii'))
        )
        if (
            persisted_meta.get('schema') != str(schema)
            or persisted_meta.get('sha256')
            != hashlib.sha256(persisted_raw).hexdigest()
            or persisted_raw != raw
        ):
            raise RuntimeError(
                f'custom property readback mismatch for {prefix!r}'
            )
        return len(chunks)

    def _persist_topology_maps(self, manager):
        chunk_size = 900
        for source_node_id in sorted(self.persisted_topology_maps):
            payload = self.persisted_topology_maps[source_node_id]
            raw = json.dumps(
                payload,
                ensure_ascii=True,
                separators=(',', ':'),
                sort_keys=True,
            ).encode('ascii')
            encoded = base64.b64encode(
                zlib.compress(raw, level=9)
            ).decode('ascii')
            chunks = [
                encoded[index:index + chunk_size]
                for index in range(0, len(encoded), chunk_size)
            ] or ['']
            prefix = f'SimpleCADTopo.{source_node_id}'
            try:
                for index, chunk in enumerate(chunks):
                    self._set_document_custom_property(
                        manager,
                        f'{prefix}.{index:04d}',
                        chunk,
                    )
                metadata = json.dumps(
                    {
                        'schema': 'simplecad-sw-topology-v1',
                        'method': 'gsm',
                        'chunks': len(chunks),
                        'sha256': hashlib.sha256(raw).hexdigest(),
                    },
                    ensure_ascii=True,
                    separators=(',', ':'),
                    sort_keys=True,
                )
                # Meta is written last so a partial chunk set is never valid.
                self._set_document_custom_property(
                    manager, f'{prefix}.Meta', metadata
                )
                self.logs.append(
                    f'persisted GSM topology properties for {source_node_id}: '
                    f'entries={len(payload.get("mappings") or {})} '
                    f'chunks={len(chunks)}'
                )
            except Exception as exc:
                self.logs.append(
                    f'could not persist GSM topology map for '
                    f'{source_node_id}: {exc}'
                )

    def _persist_document_metadata(self):
        try:
            manager = self.model.Extension.CustomPropertyManager('')
            if self.degraded_features:
                payload = json.dumps(
                    self.degraded_features,
                    ensure_ascii=True,
                    separators=(',', ':'),
                    sort_keys=True,
                )
                for call in (
                    lambda: manager.Add3(
                        'SimpleCADDegradedFeatures', 30, payload, 2
                    ),
                    lambda: manager.Set2(
                        'SimpleCADDegradedFeatures', payload
                    ),
                ):
                    try:
                        call()
                        break
                    except Exception:
                        pass
            self._persist_topology_maps(manager)
            native_ops = {
                'make_extrude_rsolid', 'make_revolve_rsolid',
                'make_cut_rsolid', 'make_union_rsolid',
                'make_intersect_rsolid', 'make_fillet_rsolid',
                'make_chamfer_rsolid', 'make_shell_rsolid',
                'make_translate_rshape', 'make_rotate_rshape',
                'make_mirror_rshape',
            }
            for node in self.nodes:
                op = str(node.get('op') or '')
                if op not in native_ops:
                    continue
                node_id = str(node.get('node_id') or '')
                body_names = []
                for output in self.outputs.get(node_id) or []:
                    if not isinstance(output, dict):
                        continue
                    if output.get('kind') == 'body':
                        output_names = [output.get('_body_name')]
                    elif output.get('kind') == 'compound':
                        output_names = output.get('_body_names') or []
                    else:
                        output_names = []
                    for body_name in output_names:
                        body_name = str(body_name or '')
                        if body_name and body_name not in body_names:
                            body_names.append(body_name)
                value = json.dumps(
                    {
                        'NodeId': node_id,
                        'Op': op,
                        'Params': node.get('params') or {},
                        'Inputs': self._input_ids(node),
                        'BodyNames': body_names,
                        'FeatureNamePrefix': f'SimpleCAD_{node_id}_',
                    },
                    ensure_ascii=True,
                    separators=(',', ':'),
                    sort_keys=True,
                )
                try:
                    manager.Add3(
                        f'SimpleCADNode.{node_id}', 30, value, 2
                    )
                except Exception as exc:
                    self.logs.append(
                        f'could not persist node metadata for {node_id}: {exc}'
                    )
        except Exception as exc:
            self.logs.append(f'could not persist degraded feature metadata: {exc}')

    def _first_output(self, node_id):
        outputs = self.outputs.get(str(node_id)) or []
        if not outputs:
            raise RuntimeError(f'Missing graph output for {node_id}')
        return outputs[0]

    def _set_output(self, node, values):
        node_id = str(node.get('node_id'))
        if not isinstance(values, list):
            values = [values]
        for value in values:
            if not isinstance(value, dict):
                continue
            if value.get('kind') == 'compound':
                bodies = [
                    body for body in value.get('bodies') or []
                    if body is not None
                ]
                value.setdefault(
                    '_body_names', [self._body_name(body) for body in bodies]
                )
                value.setdefault(
                    '_body_bboxes', [
                        self._box_from_entity(body) for body in bodies
                    ],
                )
                continue
            if value.get('kind') != 'body':
                continue
            body = value.get('body')
            if body is None:
                continue
            value.setdefault('_body_name', self._body_name(body))
            value.setdefault('_body_bbox', self._box_from_entity(body))
            if '_body_snapshot' not in value:
                try:
                    value['_body_snapshot'] = self._copy_temp_body(body)
                except Exception as exc:
                    self.logs.append(
                        f'body snapshot failed for {node_id}: {exc}'
                    )
        self.outputs[node_id] = values
        return values

    def _emit_node(self, node):
        op = str(node.get('op'))
        params = node.get('params') or {}
        node_id = str(node.get('node_id'))
        inputs = self._input_ids(node)

        if op == 'make_line_redge':
            return self._set_output(node, {'kind': 'edge', 'type': 'line', 'start': _v3(params.get('start')), 'end': _v3(params.get('end'))})
        if op == 'make_circle_redge':
            return self._set_output(node, {
                'kind': 'edge',
                'type': 'circle',
                'center': _v3(params.get('center')),
                'radius': float(params.get('radius', 1.0)),
                'normal': _unit(params.get('normal') or (0.0, 0.0, 1.0)),
                '_kernel_x_axis': params.get('_kernel_x_axis'),
                '_kernel_y_axis': params.get('_kernel_y_axis'),
            })
        if op == 'make_angle_arc_redge':
            return self._set_output(node, {
                'kind': 'edge',
                'type': 'angle_arc',
                'center': _v3(params.get('center')),
                'radius': float(params.get('radius', 1.0)),
                'start_angle': float(params.get('start_angle', 0.0)),
                'end_angle': float(params.get('end_angle', 0.0)),
                'normal': _unit(params.get('normal') or (0.0, 0.0, 1.0)),
                '_kernel_x_axis': params.get('_kernel_x_axis'),
                '_kernel_y_axis': params.get('_kernel_y_axis'),
            })
        if op == 'make_three_point_arc_redge':
            return self._set_output(node, {'kind': 'edge', 'type': 'three_point_arc', 'start': _v3(params.get('start')), 'middle': _v3(params.get('middle')), 'end': _v3(params.get('end'))})
        if op == 'make_spline_redge':
            controls = params.get('control_points') or params.get('controls') or params.get('points') or []
            return self._set_output(node, {
                'kind': 'edge',
                'type': 'spline',
                'controls': [_v3(point) for point in controls],
                'degree': int(params.get('degree') or min(3, max(1, len(controls) - 1))),
                'knots': [float(value) for value in (params.get('knots') or [])],
                'multiplicities': [int(value) for value in (params.get('multiplicities') or [])],
                'weights': [float(value) for value in (params.get('weights') or [])],
                'periodic': bool(params.get('periodic', False)),
            })
        if op == 'make_helix_redge':
            return self._set_output(node, {'kind': 'edge', 'type': 'helix', 'params': dict(params)})
        if op == 'make_wire_from_edges_rwire':
            edges = []
            for input_id in inputs:
                value = self._first_output(input_id)
                if isinstance(value, dict) and value.get('kind') == 'wire':
                    edges.extend(value.get('edges') or [])
                else:
                    edges.append(value)
            return self._set_output(node, {'kind': 'wire', 'edges': edges})
        if op == 'make_face_from_wire_rface':
            return self._set_output(node, {'kind': 'face', 'outer': self._first_output(inputs[0]), 'inners': [], 'normal': _unit(params.get('normal') or (0.0, 0.0, 1.0))})
        if op == 'make_face_from_wires_rface':
            wires = [self._first_output(input_id) for input_id in inputs]
            if not wires:
                raise RuntimeError('make_face_from_wires_rface requires wire inputs')
            return self._set_output(node, {'kind': 'face', 'outer': wires[0], 'inners': wires[1:], 'normal': _unit(params.get('normal') or (0.0, 0.0, 1.0))})
        if op in {'make_wire_from_sketch_rwire', 'make_face_from_sketch_rface'}:
            raise SimpleCADUnsupportedOpError(f'{op} is not yet supported by the SolidWorks translator')
        if op == 'make_extrude_rsolid':
            body = self._extrude_profile(self._first_output(inputs[0]), params, node_id)
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_revolve_rsolid':
            body = self._revolve_profile(self._first_output(inputs[0]), params, node_id)
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_loft_rsolid':
            body = self._loft_profiles([self._first_output(input_id) for input_id in inputs], params, node_id)
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_sweep_rsolid':
            body = self._sweep_profile(self._first_output(inputs[0]), self._first_output(inputs[1]), params, node_id)
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_cut_rsolid':
            bases = self._bodies_from_value(self._first_output(inputs[0]))
            tools = []
            for input_id in inputs[1:]:
                tools.extend(
                    self._bodies_from_value(self._first_output(input_id))
                )
            canonical_result = self.canonical_cut_descriptors.get(node_id)
            if len(bases) > 1:
                # A disjoint Union is a live body set, not a failed single-body
                # union. Apply the shared cutters independently to each target
                # section. A cutter may belong to at most one section here;
                # otherwise SolidWorks would consume the same live tool twice.
                tool_owners = []
                for tool in tools:
                    owners = [
                        index for index, base in enumerate(bases)
                        if self._body_intersection_has_volume(base, tool)
                    ]
                    tool_owners.append(owners)
                cut_bodies = []
                for base_index, base in enumerate(bases):
                    section_tools = [
                        tool for tool, owners in zip(tools, tool_owners)
                        if base_index in owners
                    ]
                    section_result = self._boolean_body(
                        base,
                        section_tools,
                        SWBODYCUT,
                        f'SimpleCAD_{node_id}_section_{base_index + 1}',
                        # Bbox-disjoint tools are exact no-ops for this section.
                        skip_non_intersecting=True,
                        canonical_result=None,
                        allow_split_sections=True,
                        prefer_native=True,
                    )
                    if isinstance(section_result, list):
                        cut_bodies.extend(section_result)
                    else:
                        cut_bodies.append(section_result)
                if (
                    isinstance(canonical_result, dict)
                    and not self._body_set_matches_canonical(
                        cut_bodies, canonical_result
                    )
                ):
                    raise RuntimeError(
                        f'Cut SimpleCAD_{node_id} live body-set result did not '
                        'match the canonical bbox/volume descriptor'
                    )
                self.logs.append(
                    f'cut SimpleCAD_{node_id} preserved '
                    f'{len(cut_bodies)} live result sections'
                )
                if len(cut_bodies) > 1:
                    return self._set_output(
                        node, {'kind': 'compound', 'bodies': cut_bodies}
                    )
                return self._set_output(
                    node, {'kind': 'body', 'body': cut_bodies[0]}
                )
            body = self._boolean_body(
                bases[0],
                tools,
                SWBODYCUT,
                f'SimpleCAD_{node_id}',
                skip_non_intersecting=bool(params.get('skip_non_intersecting', False)),
                canonical_result=canonical_result,
                # Keep the edited base live even when this Cut is followed by
                # another graph node; static boolean copies sever propagation.
                prefer_native=True,
            )
            if isinstance(body, list):
                return self._set_output(node, {'kind': 'compound', 'bodies': body})
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_union_rsolid':
            input_body_sets = [
                self._bodies_from_value(self._first_output(input_id))
                for input_id in inputs
            ]
            bodies = [
                body for body_set in input_body_sets for body in body_set
            ]
            if not bodies:
                raise RuntimeError(f'Union SimpleCAD_{node_id} has no bodies')
            passthrough_index = self.canonical_union_passthroughs.get(node_id)
            if (
                isinstance(passthrough_index, int)
                and 0 <= passthrough_index < len(input_body_sets)
            ):
                passthrough_bodies = input_body_sets[passthrough_index]
                body = [
                    self._transform_body_feature(
                        candidate,
                        _identity_matrix(),
                        f'SimpleCAD_{node_id}_canonical_passthrough_{index + 1}',
                    )
                    for index, candidate in enumerate(passthrough_bodies)
                ]
                self.logs.append(
                    f'union SimpleCAD_{node_id} used canonical input '
                    f'passthrough index {passthrough_index}'
                )
            else:
                contributing_indices = self.canonical_union_input_indices.get(
                    node_id
                )
                if isinstance(contributing_indices, list):
                    normalized_indices = []
                    for value in contributing_indices:
                        try:
                            index = int(value)
                        except Exception:
                            raise RuntimeError(
                                f'Union SimpleCAD_{node_id} has an invalid '
                                f'canonical contributing input index: {value!r}'
                            )
                        if (
                            index < 0
                            or index >= len(input_body_sets)
                            or index in normalized_indices
                        ):
                            raise RuntimeError(
                                f'Union SimpleCAD_{node_id} canonical '
                                f'contributing input index is invalid: {index}'
                            )
                        normalized_indices.append(index)
                    input_body_sets = [
                        input_body_sets[index]
                        for index in normalized_indices
                    ]
                    bodies = [
                        candidate
                        for body_set in input_body_sets
                        for candidate in body_set
                    ]
                    if not bodies:
                        raise RuntimeError(
                            f'Union SimpleCAD_{node_id} canonical input '
                            'selection produced no live bodies'
                        )
                    self.logs.append(
                        f'union SimpleCAD_{node_id} retained canonical '
                        f'contributing inputs {normalized_indices!r}'
                    )
                boxes = [self._box_from_entity(candidate) for candidate in bodies]
                unseen = set(range(len(bodies)))
                components = []
                while unseen:
                    start = min(unseen)
                    unseen.remove(start)
                    pending = [start]
                    component = []
                    while pending:
                        current = pending.pop()
                        component.append(current)
                        neighbors = [
                            candidate for candidate in sorted(unseen)
                            if self._body_union_is_single(
                                bodies[current], bodies[candidate]
                            )
                        ]
                        for candidate in neighbors:
                            unseen.remove(candidate)
                            pending.append(candidate)
                    components.append(sorted(component))
                if len(components) > 1:
                    # Bbox-disconnected components cannot intersect. Combine
                    # only within each connected group, then preserve the
                    # exact union as a live body set across the groups.
                    component_body_sets = []
                    for component_index, component in enumerate(components):
                        component_bodies = [bodies[index] for index in component]
                        if len(component_bodies) == 1:
                            component_result = component_bodies[0]
                        else:
                            component_result = self._boolean_body(
                                component_bodies[0],
                                component_bodies[1:],
                                SWBODYADD,
                                f'SimpleCAD_{node_id}_component_'
                                f'{component_index + 1}',
                                clean=bool(params.get('clean', False)),
                                prefer_native=True,
                            )
                        component_body_sets.append(
                            list(component_result)
                            if isinstance(component_result, list)
                            else [component_result]
                        )
                    canonical_union = self.canonical_union_descriptors.get(
                        node_id
                    )
                    body = [
                        candidate
                        for body_set in component_body_sets
                        for candidate in body_set
                    ]
                    if isinstance(canonical_union, dict):
                        matching_subsets = []
                        if len(component_body_sets) <= 12:
                            for mask in range(
                                1, 1 << len(component_body_sets)
                            ):
                                subset = [
                                    candidate
                                    for index, body_set in enumerate(
                                        component_body_sets
                                    )
                                    if mask & (1 << index)
                                    for candidate in body_set
                                ]
                                if self._body_set_matches_canonical(
                                    subset, canonical_union
                                ):
                                    matching_subsets.append((mask, subset))
                        elif self._body_set_matches_canonical(
                            body, canonical_union
                        ):
                            matching_subsets.append((None, body))
                        if len(matching_subsets) != 1:
                            raise RuntimeError(
                                f'Union SimpleCAD_{node_id} did not have a '
                                'unique bbox-disconnected component subset '
                                'matching the canonical bbox/volume; '
                                f'matches={len(matching_subsets)} '
                                f'components={len(component_body_sets)} '
                                f'canonical={canonical_union!r}'
                            )
                        selected_mask, body = matching_subsets[0]
                        self.logs.append(
                            f'union SimpleCAD_{node_id} selected canonical '
                            f'component subset mask={selected_mask!r}'
                        )
                    self.logs.append(
                        f'union SimpleCAD_{node_id} preserved '
                        f'{len(body)} bbox-disconnected live components '
                        f'from {len(bodies)} input bodies'
                    )
                else:
                    body = self._boolean_body(
                        bodies[0],
                        bodies[1:],
                        SWBODYADD,
                        f'SimpleCAD_{node_id}',
                        clean=bool(params.get('clean', False)),
                        canonical_result=(
                            self.canonical_union_descriptors.get(node_id)
                        ),
                        prefer_native=True,
                    )
            if isinstance(body, list):
                if len(body) == 1:
                    return self._set_output(
                        node, {'kind': 'body', 'body': body[0]}
                    )
                return self._set_output(
                    node, {'kind': 'compound', 'bodies': body}
                )
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_intersect_rsolid':
            bodies = [self._body_from_value(self._first_output(input_id)) for input_id in inputs]
            body = self._boolean_body(
                bodies[0],
                bodies[1:],
                SWBODYINTERSECT,
                f'SimpleCAD_{node_id}',
                prefer_native=True,
            )
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_select_redge':
            payload = {'kind': 'edge', 'params': params, 'input': inputs[0] if inputs else None}
            self.selection_payloads[node_id] = payload
            if os.environ.get('SIMPLECAD_SW_TRACE_SELECTIONS') == '1' and inputs:
                try:
                    source = self._body_from_value(self._first_output(inputs[0]))
                    selector = params.get('geo_selector') or params
                    signatures = [
                        self._edge_signature(edge)
                        for edge in self._body_edges(source)
                    ]
                    ranked = sorted(
                        signatures,
                        key=lambda signature: _geom_score(signature, selector),
                    )
                    trace = {
                        'node_id': node_id,
                        'source_id': inputs[0],
                        'best_score': (
                            _geom_score(ranked[0], selector)
                            if ranked else None
                        ),
                        'type_mismatch': (
                            _geom_type_mismatch(ranked[0], selector)
                            if ranked else None
                        ),
                        'selector': _selector_geometry(selector),
                        'best': ranked[0] if ranked else None,
                    }
                    print(
                        'SIMPLECAD_SW_SELECTION=' + json.dumps(
                            trace, ensure_ascii=True, sort_keys=True
                        ),
                        flush=True,
                    )
                except Exception as exc:
                    print(
                        f'SIMPLECAD_SW_SELECTION_ERROR={node_id}:{exc}',
                        flush=True,
                    )
            return self._set_output(node, payload)
        if op == 'make_select_rface':
            payload = {'kind': 'face', 'params': params, 'input': inputs[0] if inputs else None}
            self.selection_payloads[node_id] = payload
            return self._set_output(node, payload)
        if op == 'make_fillet_rsolid':
            body = self._feature_detail_edges(params, inputs, 'fillet', node_id)
            if isinstance(body, list):
                return self._set_output(
                    node, {'kind': 'compound', 'bodies': body}
                )
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_chamfer_rsolid':
            body = self._feature_detail_edges(params, inputs, 'chamfer', node_id)
            if isinstance(body, list):
                return self._set_output(
                    node, {'kind': 'compound', 'bodies': body}
                )
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_shell_rsolid':
            body = self._feature_shell(params, inputs, node_id)
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_translate_rshape':
            value = self._first_output(inputs[0])
            vector = _v3(params.get('vector') or (0.0, 0.0, 0.0))
            if isinstance(value, dict) and value.get('kind') in {'edge', 'wire', 'face'}:
                transformed = _transform_geometry_value(
                    value,
                    lambda point: _add(_v3(point), vector),
                    lambda direction: _v3(direction),
                )
                return self._set_output(node, transformed)
            bodies = [
                self._transform_body_feature(
                    body,
                    _translation_matrix(vector),
                    f'SimpleCAD_{node_id}_{index + 1}',
                )
                for index, body in enumerate(self._bodies_from_value(value))
            ]
            if len(bodies) > 1:
                return self._set_output(
                    node, {'kind': 'compound', 'bodies': bodies}
                )
            return self._set_output(node, {'kind': 'body', 'body': bodies[0]})
        if op == 'make_rotate_rshape':
            value = self._first_output(inputs[0])
            axis = params.get('axis') or (0.0, 0.0, 1.0)
            angle = params.get('angle', 0.0)
            origin = params.get('origin') or (0.0, 0.0, 0.0)
            if isinstance(value, dict) and value.get('kind') in {'edge', 'wire', 'face'}:
                transformed = _transform_geometry_value(
                    value,
                    lambda point: _rotate_point_payload(point, axis, angle, origin),
                    lambda direction: _rotate_direction_payload(direction, axis, angle),
                )
                return self._set_output(node, transformed)
            bodies = [
                self._rotate_body_feature(
                    body,
                    axis,
                    angle,
                    origin,
                    f'SimpleCAD_{node_id}_{index + 1}',
                )
                for index, body in enumerate(self._bodies_from_value(value))
            ]
            if len(bodies) > 1:
                return self._set_output(
                    node, {'kind': 'compound', 'bodies': bodies}
                )
            return self._set_output(node, {'kind': 'body', 'body': bodies[0]})
        if op == 'make_mirror_rshape':
            value = self._first_output(inputs[0])
            plane_origin = params.get('plane_origin') or (0.0, 0.0, 0.0)
            plane_normal = params.get('plane_normal') or (0.0, 0.0, 1.0)
            if isinstance(value, dict) and value.get('kind') in {'edge', 'wire', 'face'}:
                transformed = _transform_geometry_value(
                    value,
                    lambda point: _mirror_point_payload(point, plane_origin, plane_normal),
                    lambda direction: _mirror_direction_payload(direction, plane_normal),
                )
                return self._set_output(node, transformed)
            body = self._transform_body_feature(self._body_from_value(value), _mirror_matrix(plane_origin, plane_normal), f'SimpleCAD_{node_id}')
            return self._set_output(node, {'kind': 'body', 'body': body})
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
                'component_id': str(params.get('component_id') or ''),
                'item': self._first_output(inputs[1]),
                'placement': self._first_output(inputs[2]) if len(inputs) > 2 else {'kind': 'placement', 'params': {}},
                'params': params,
            })
            assembly['components'] = components
            self.product_values[node_id] = assembly
            return self._set_output(node, assembly)
        if op == 'make_place_component_rassembly':
            assembly = dict(self._first_output(inputs[0]))
            placement = self._first_output(inputs[1])
            component_id = str(params.get('component_id') or '')
            components = []
            for component in assembly.get('components') or []:
                component = dict(component)
                if str(component.get('component_id') or '') == component_id:
                    component['placement'] = placement
                components.append(component)
            assembly['components'] = components
            self.product_values[node_id] = assembly
            return self._set_output(node, assembly)
        if op == 'make_solve_assembly_constraints_rassembly':
            assembly = dict(self._first_output(inputs[0]))
            solved_placements = dict(params.get('component_placements') or {})
            components = []
            for component in assembly.get('components') or []:
                component = dict(component)
                component_id = str(component.get('component_id') or '')
                if component_id in solved_placements:
                    component['placement'] = {
                        'kind': 'placement',
                        'params': dict(solved_placements[component_id]),
                    }
                components.append(component)
            assembly['components'] = components
            self.product_values[node_id] = assembly
            return self._set_output(node, assembly)
        if op == 'make_compound_from_assembly_rcompound':
            bodies = self._materialize_product_bodies(
                self._first_output(inputs[0]),
                f'SimpleCAD_{node_id}_component',
            )
            if not bodies:
                raise RuntimeError('assembly compound has no bodies')
            return self._set_output(node, {'kind': 'compound', 'bodies': bodies})
        if op.startswith('make_') and op.endswith('_rconnector'):
            return self._set_output(node, {'kind': 'connector', 'params': params})
        if op in {
            'make_add_connector_rpart', 'make_add_connector_rassembly',
            'make_connector_ref_rconnectorref', 'make_scalar_limit_rscalarlimit',
            'make_ground_component_rassembly', 'make_unground_component_rassembly',
            'make_fixed_constraint_rassembly', 'make_revolute_constraint_rassembly',
            'make_prismatic_constraint_rassembly',
        }:
            value = self._first_output(inputs[0]) if inputs else {'kind': op, 'params': params}
            return self._set_output(node, value)
        raise SimpleCADUnsupportedOpError(f'Unsupported SimpleCAD op for SolidWorks translation: {op}')

    def _body_from_value(self, value):
        if hasattr(value, 'GetFaces'):
            return value
        if isinstance(value, dict):
            if value.get('kind') == 'body':
                return self._resolve_body_reference(
                    value.get('body'),
                    value.get('_body_name'),
                    value.get('_body_bbox'),
                    value.get('_body_snapshot'),
                )
            if value.get('kind') == 'part':
                return self._body_from_value(value.get('body'))
            if value.get('kind') == 'compound':
                bodies = self._bodies_from_value(value)
                if len(bodies) == 1:
                    return bodies[0]
                raise RuntimeError(
                    f'Expected one SolidWorks body, got a live body set with '
                    f'{len(bodies)} sections'
                )
        raise RuntimeError(f'Expected a SolidWorks body, got {type(value).__name__}')

    def _bodies_from_value(self, value):
        if isinstance(value, dict) and value.get('kind') == 'compound':
            bodies = [
                body for body in value.get('bodies') or []
                if body is not None
            ]
            if not bodies:
                raise RuntimeError('Expected a non-empty SolidWorks body set')
            return bodies
        return [self._body_from_value(value)]

    def _resolve_body_reference(
        self,
        body,
        expected_name=None,
        expected_bbox=None,
        body_snapshot=None,
    ):
        fresh_bodies = self._solid_bodies()

        def com_identity(entity):
            try:
                unknown = entity._oleobj_.QueryInterface(
                    pythoncom.IID_IUnknown
                )
                return ('com', hash(unknown))
            except Exception:
                return ('python', id(entity))

        if body is not None:
            direct_identity = com_identity(body)
            direct_matches = [
                candidate for candidate in fresh_bodies
                if com_identity(candidate) == direct_identity
            ]
            if len(direct_matches) == 1:
                return direct_matches[0]

        ambiguous = None

        def unique_bbox_candidate(candidates, label):
            nonlocal ambiguous
            ranked = sorted(
                (
                    _bbox_score(
                        self._box_from_entity(candidate), expected_bbox
                    ),
                    index,
                    candidate,
                )
                for index, candidate in enumerate(candidates)
            )
            if not ranked:
                return None
            best_score = ranked[0][0]
            ties = [
                item for item in ranked
                if abs(item[0] - best_score) <= 1.0e-12
            ]
            if len(ties) == 1:
                return ties[0][2]
            ambiguous = (
                f'{label} body lookup tied across {len(ties)} candidates '
                f'at bbox score {best_score}'
            )
            return None

        if expected_name:
            named = [
                candidate for candidate in fresh_bodies
                if self._body_name(candidate) == str(expected_name)
            ]
            if len(named) == 1:
                return named[0]
            if named and isinstance(expected_bbox, dict):
                named_match = unique_bbox_candidate(named, 'named')
                if named_match is not None:
                    return named_match
        if isinstance(expected_bbox, dict):
            expected_size = _distance(
                expected_bbox.get('min'), expected_bbox.get('max')
            )
            if expected_size > 1.0e-12 and fresh_bodies:
                best_body = unique_bbox_candidate(
                    fresh_bodies, 'global'
                )
                if best_body is not None:
                    best_score = _bbox_score(
                        self._box_from_entity(best_body), expected_bbox
                    )
                    if best_score <= max(
                        1.0e-7, expected_size * 1.0e-7
                    ):
                        return best_body
        if ambiguous is not None:
            raise RuntimeError(
                f'Ambiguous SolidWorks body reference for '
                f'name={expected_name!r} bbox={expected_bbox!r}: {ambiguous}'
            )
        if body_snapshot is not None:
            snapshot_bbox = self._box_from_entity(body_snapshot)
            if self._body_faces(body_snapshot) and (
                not isinstance(expected_bbox, dict)
                or _distance(
                    expected_bbox.get('min'), expected_bbox.get('max')
                ) <= 1.0e-12
                or _bbox_score(snapshot_bbox, expected_bbox)
                <= max(
                    1.0e-7,
                    _distance(
                        expected_bbox.get('min'), expected_bbox.get('max')
                    ) * 1.0e-7,
                )
            ):
                return body_snapshot
        if body is not None:
            return body
        raise RuntimeError(
            f'Could not resolve SolidWorks body reference '
            f'name={expected_name!r} bbox={expected_bbox!r}'
        )

    def _bodies_from_product(self, value):
        if isinstance(value, dict) and value.get('kind') == 'part':
            return self._bodies_from_product(value.get('body'))
        if isinstance(value, dict) and value.get('kind') == 'assembly':
            bodies = []
            for component in value.get('components') or []:
                bodies.extend(self._bodies_from_product(component.get('item')))
            return bodies
        if isinstance(value, dict) and value.get('kind') == 'body':
            return [self._body_from_value(value)]
        if isinstance(value, dict) and value.get('kind') == 'compound':
            return [body for body in value.get('bodies') or [] if body is not None]
        return []

    def _product_body_instances(
        self, value, placements=(), path=(), body_node_id=''
    ):
        if isinstance(value, dict) and value.get('kind') == 'part':
            return self._product_body_instances(
                value.get('body'),
                placements,
                path,
                str(value.get('body_node') or body_node_id or ''),
            )
        if isinstance(value, dict) and value.get('kind') == 'assembly':
            instances = []
            for index, component in enumerate(value.get('components') or []):
                component_id = str(
                    component.get('component_id')
                    or (component.get('params') or {}).get('component_id')
                    or index
                )
                component_placement = component.get('placement') or {
                    'kind': 'placement',
                    'params': {},
                }
                instances.extend(
                    self._product_body_instances(
                        component.get('item'),
                        placements + (component_placement,),
                        path + (component_id,),
                        body_node_id,
                    )
                )
            return instances
        if isinstance(value, dict) and value.get('kind') == 'body':
            return [(
                self._body_from_value(value), placements, path, body_node_id
            )]
        if isinstance(value, dict) and value.get('kind') == 'compound':
            return [
                (body, placements, path + (str(index),), body_node_id)
                for index, body in enumerate(value.get('bodies') or [])
                if body is not None
            ]
        return []

    def _materialize_product_bodies(self, value, name_prefix):
        bodies = []
        for (
            body, placements, path, explicit_body_node_id
        ) in self._product_body_instances(value):
            if body is None:
                continue
            matrices = [_placement_matrix(placement) for placement in placements]
            has_transform = any(not _is_identity_matrix(matrix) for matrix in matrices)
            source_name = self._body_name(body)
            source_tokens = source_name.split('_')
            inferred_source_node_id = (
                f'node_{source_tokens[2]}'
                if len(source_tokens) >= 3
                and source_tokens[0] == 'SimpleCAD'
                and source_tokens[1] == 'node'
                else ''
            )
            source_node_id = str(
                explicit_body_node_id or inferred_source_node_id
            )
            dependency_node_ids = sorted(
                self._result_dependency_ids([source_node_id])
            )
            if source_node_id and source_node_id not in dependency_node_ids:
                raise RuntimeError(
                    f'Could not resolve dependency graph for terminal part '
                    f'body {source_node_id}'
                )
            source_owner = ''
            for getter_name in ('GetFeature', 'IGetFeature'):
                try:
                    owner = _maybe_call(getattr(body, getter_name))
                    if owner is not None:
                        source_owner = str(_maybe_call(owner.Name) or '')
                        if source_owner:
                            break
                except Exception:
                    pass
            source_expected_bbox = self._box_from_entity(body)
            # Capture while the terminal branch still exposes a live Body2.
            # The assembly writer first tries a derived part linked to the
            # saved master; this detached body is only the cross-document
            # transport/fallback and must not be captured after Keep Bodies.
            prepared_source_body = self._copy_temp_body(body)
            source_key = source_owner or source_name
            may_reuse_source = (
                not path
                and not has_transform
                and source_key not in self.materialized_source_body_keys
            )
            self.logs.append(
                f'product body path={path!r} owner={source_owner!r} '
                f'name={source_name!r} transformed={has_transform!r} '
                f'reuse_live={may_reuse_source!r}'
            )
            if may_reuse_source:
                self.materialized_source_body_keys.add(source_key)
                bodies.append(body)
                if path:
                    self.assembly_occurrences.append({
                        'component_id': str(path[0]),
                        'path': tuple(str(part) for part in path),
                        'placements': tuple(placements),
                        'body': body,
                        'source_body': body,
                        'prepared_source_body': prepared_source_body,
                        'source_body_name': source_name,
                        'source_owner': source_owner,
                        'source_expected_bbox': source_expected_bbox,
                        'source_node_id': source_node_id,
                        'dependency_node_ids': dependency_node_ids,
                    })
                continue

            self.component_instance_counter += 1
            path_token = '_'.join(str(part) for part in path if str(part))
            instance_name = (
                f'{name_prefix}_{path_token}_{self.component_instance_counter}'
                if path_token
                else f'{name_prefix}_{self.component_instance_counter}'
            )
            can_materialize_live = all(
                _is_identity_matrix(matrix)
                or _is_translation_matrix(matrix)
                for matrix in matrices
            )
            if can_materialize_live:
                # Preserve the unplaced source as a live body in the package
                # master. Translation Move/Copy features may move their input
                # in place, so placements must operate on a dependent copy.
                instance_body = self._transform_body_feature(
                    body,
                    _identity_matrix(),
                    f'{instance_name}_source_copy',
                )
                transformed = False
                for placement_index, matrix in enumerate(reversed(matrices)):
                    if _is_identity_matrix(matrix):
                        continue
                    instance_body = self._transform_body_feature(
                        instance_body,
                        matrix,
                        f'{instance_name}_placement_{placement_index + 1}',
                    )
                    transformed = True
                self.logs.append(
                    f'{instance_name} uses live Move/Copy Body materialization'
                    + (' with placement' if transformed else '')
                )
            else:
                temp_body = self._copy_temp_body(body)
                for matrix in reversed(matrices):
                    if not _is_identity_matrix(matrix):
                        self._apply_transform_to_temp_body(temp_body, matrix)
                self._mark_degraded(instance_name, 'static_component_body')
                instance_body = self._create_feature_from_body(
                    temp_body, instance_name
                )
            bodies.append(instance_body)
            if path:
                self.assembly_occurrences.append({
                    'component_id': str(path[0]),
                    'path': tuple(str(part) for part in path),
                    'placements': tuple(placements),
                    'body': instance_body,
                    'source_body': body,
                    'prepared_source_body': prepared_source_body,
                    'source_body_name': source_name,
                    'source_owner': source_owner,
                    'source_expected_bbox': source_expected_bbox,
                    'source_node_id': source_node_id,
                    'dependency_node_ids': dependency_node_ids,
                })
        return bodies

    def _result_bodies(self):
        if not self.result_node_ids:
            self.result_node_ids = [str(node.get('node_id')) for node in self.nodes[-1:]]
        result_node_ids = list(self.result_node_ids)
        bodies = []
        for node_id in result_node_ids:
            for value in self.outputs.get(str(node_id), []):
                if isinstance(value, dict) and value.get('kind') in {'part', 'assembly'}:
                    if value.get('kind') == 'assembly':
                        bodies.extend(
                            self._materialize_product_bodies(
                                value,
                                f'SimpleCAD_{node_id}_component',
                            )
                        )
                    else:
                        bodies.extend(self._bodies_from_product(value))
                elif isinstance(value, dict) and value.get('kind') == 'body':
                    body = self._body_from_value(value)
                    # SolidWorks Body2 has no editable Placement property. A
                    # zero-displacement Move/Copy Body feature is the native
                    # equivalent for result-level placement edits: it keeps a
                    # live dependency on the reconstructed result while giving
                    # the reopened document persistent TransformX/Y/Z values.
                    body = self._transform_body_feature(
                        body,
                        _identity_matrix(),
                        f'SimpleCAD_{node_id}_placement',
                    )
                    bodies.append(body)
                elif isinstance(value, dict) and value.get('kind') == 'compound':
                    bodies.extend(value.get('bodies') or [])
                elif hasattr(value, 'GetFaces'):
                    bodies.append(value)
        return [body for body in bodies if body is not None]

    def _solid_bodies(self):
        bodies = None
        for call in (
            lambda: self.model.GetBodies2(SW_SOLID_BODY, False),
            lambda: self.model.GetBodies2(SW_SOLID_BODY, True),
        ):
            try:
                bodies = call()
                if bodies:
                    break
            except Exception:
                bodies = None
        if bodies is None:
            return []
        if isinstance(bodies, tuple):
            return list(bodies)
        if isinstance(bodies, list):
            return bodies
        try:
            return list(bodies)
        except Exception:
            return [bodies]

    def _body_name(self, body):
        try:
            return str(body.Name)
        except Exception:
            pass
        try:
            return str(body.GetName())
        except Exception:
            return str(id(body))

    def _body_names(self):
        return {self._body_name(body) for body in self._solid_bodies()}

    def _body_geometry_key(self, body):
        bbox = self._box_from_entity(body)
        coordinates = tuple(
            round(float(value), 9)
            for point in (bbox.get('min'), bbox.get('max'))
            for value in _v3(point)
        )
        return self._body_name(body), coordinates

    def _capture_new_body(
        self, before_names, feature=None, expected_bbox=None, fallback_body=None
    ):
        def com_identity(entity):
            try:
                unknown = entity._oleobj_.QueryInterface(
                    pythoncom.IID_IUnknown
                )
                return ('com', hash(unknown))
            except Exception:
                return ('python', id(entity))

        def unique_by_identity(values):
            unique = {}
            for value in values:
                if value is not None:
                    unique.setdefault(com_identity(value), value)
            return list(unique.values())

        feature_candidates = []
        if feature is not None:
            # IFeature.GetBody is obsolete and can return an edit-state proxy.
            # The supported Feature.GetFaces -> Face2.GetBody chain binds the
            # feature to the body it actually produced or modified, which is
            # essential when several document bodies have the same bbox.
            for getter_name in ('GetFaces', 'IGetFaces2'):
                try:
                    faces = _maybe_call(getattr(feature, getter_name))
                except Exception:
                    faces = None
                if not faces:
                    continue
                if not isinstance(faces, (list, tuple)):
                    faces = [faces]
                for face in faces:
                    for body_getter in ('GetBody', 'IGetBody'):
                        try:
                            body = _maybe_call(getattr(face, body_getter))
                        except Exception:
                            body = None
                        if body is not None:
                            try:
                                body = win32com.client.CastTo(body, 'IBody2')
                            except Exception:
                                pass
                            feature_candidates.append(body)
                            break
                if feature_candidates:
                    break
            feature_candidates = unique_by_identity(feature_candidates)
            for getter_name in ('GetBody', 'IGetBody2'):
                try:
                    body = _maybe_call(getattr(feature, getter_name))
                    if body is not None:
                        try:
                            body = win32com.client.CastTo(body, 'IBody2')
                        except Exception:
                            pass
                        feature_candidates.append(body)
                except Exception:
                    pass
            feature_candidates = unique_by_identity(feature_candidates)
            for dispid in (62, 30):
                try:
                    body = feature._oleobj_.InvokeTypes(
                        dispid,
                        0,
                        pythoncom.DISPATCH_METHOD,
                        (pythoncom.VT_DISPATCH, 0),
                        (),
                    )
                    if body is not None:
                        body = win32com.client.Dispatch(body)
                        try:
                            body = win32com.client.CastTo(body, 'IBody2')
                        except Exception:
                            pass
                        feature_candidates.append(body)
                except Exception:
                    pass
        if len(feature_candidates) == 1:
            candidate = feature_candidates[0]
            candidate_name = self._body_name(candidate)
            if candidate_name and candidate_name not in before_names:
                try:
                    feature_name = str(_maybe_call(feature.Name) or '')
                except Exception:
                    feature_name = ''
                if feature_name:
                    try:
                        candidate.Name = f'{feature_name}_body'
                    except Exception as exc:
                        self.logs.append(
                            f'could not persist result body name for '
                            f'{feature_name}: {exc}'
                        )
                return candidate
        bodies = self._solid_bodies()
        fresh_candidates = [
            body for body in bodies
            if self._body_name(body) not in before_names
        ]
        if feature_candidates:
            # Feature.GetBody can return an edit-state/transient Body2 proxy.
            # Prefer the reopened-document body with the same persistent name
            # so downstream native features can select it and keep dependency
            # propagation alive.
            feature_keys = {
                com_identity(body) for body in feature_candidates
            }
            persistent_matches = [
                body for body in bodies
                if com_identity(body) in feature_keys
            ]
            candidates = (
                list(persistent_matches)
                or list(fresh_candidates)
                or list(feature_candidates)
            )
        else:
            # Bodies enumerated from the document are persistent and remain
            # copyable after the feature manager releases its transient proxy.
            candidates = list(fresh_candidates)
            if not candidates:
                candidates.extend(bodies)
        if not candidates and fallback_body is not None:
            try:
                if self._body_faces(fallback_body):
                    candidates.append(fallback_body)
                    self.logs.append(
                        'feature result body reused its in-place SolidWorks body'
                    )
            except Exception:
                pass
        if not candidates:
            raise RuntimeError('Could not identify SolidWorks feature result body')
        if candidates:
            candidates = unique_by_identity(candidates)
            if isinstance(expected_bbox, dict):
                selected = min(
                    candidates,
                    key=lambda body: _bbox_score(
                        self._box_from_entity(body), expected_bbox
                    ),
                )
            else:
                selected = candidates[-1]
            if feature is not None:
                try:
                    feature_name = str(_maybe_call(feature.Name) or '')
                except Exception:
                    feature_name = ''
                if feature_name:
                    try:
                        selected.Name = f'{feature_name}_body'
                    except Exception as exc:
                        self.logs.append(
                            f'could not persist result body name for '
                            f'{feature_name}: {exc}'
                        )
            return selected

    def _select_entity(self, entity, append=False, mark=0):
        for call in (
            lambda: entity.Select2(bool(append), mark),
            lambda: entity.Select2(bool(append), None),
            lambda: entity.Select2(bool(append), _empty_dispatch()),
            lambda: entity.Select4(bool(append), _empty_dispatch()),
            lambda: entity.Select(bool(append), mark),
            lambda: entity.Select(bool(append)),
        ):
            try:
                if call():
                    return True
            except Exception:
                pass
        return False

    def _select_solid_body(self, body, *, append=False, mark=1):
        body_name = self._body_name(body)
        if body_name:
            try:
                if self.model.Extension.SelectByID2(
                    body_name,
                    'SOLIDBODY',
                    0.0,
                    0.0,
                    0.0,
                    bool(append),
                    int(mark),
                    _empty_dispatch(),
                    0,
                ):
                    return True
            except Exception:
                pass
        return self._select_entity(body, append=append, mark=mark)

    def _group_sweep_path_selection(self):
        try:
            return bool(self.model.Extension.SelectByID2(
                'Unknown', 'SELOBJGROUP',
                0.0, 0.0, 0.0,
                True, 4, _empty_dispatch(), 0,
            ))
        except Exception as exc:
            self.logs.append(f'could not group sweep path segments: {exc}')
            return False

    def _clear_selection(self):
        try:
            self.model.ClearSelection2(True)
        except Exception:
            pass

    def _selection_state(self):
        state = []
        try:
            raw_manager = self.model._oleobj_.InvokeTypes(
                65537,
                0,
                pythoncom.DISPATCH_PROPERTYGET,
                (pythoncom.VT_DISPATCH, 0),
                (),
            )
            manager = win32com.client.Dispatch(raw_manager)
            count = int(manager._oleobj_.InvokeTypes(
                1, 0, pythoncom.DISPATCH_METHOD, (pythoncom.VT_I4, 0), ()
            ))
        except Exception:
            return state
        for index in range(1, count + 1):
            try:
                object_type = int(manager._oleobj_.InvokeTypes(
                    14,
                    0,
                    pythoncom.DISPATCH_METHOD,
                    (pythoncom.VT_I4, 0),
                    ((pythoncom.VT_I4, pythoncom.PARAMFLAG_FIN),),
                    index,
                ))
            except Exception:
                object_type = None
            try:
                mark = int(manager._oleobj_.InvokeTypes(
                    17,
                    0,
                    pythoncom.DISPATCH_METHOD,
                    (pythoncom.VT_I4, 0),
                    ((pythoncom.VT_I4, pythoncom.PARAMFLAG_FIN),),
                    index,
                ))
            except Exception:
                mark = None
            state.append({'type': object_type, 'mark': mark})
        return state

    def _features(self, type_names=None):
        wanted = set(type_names or [])
        features = []
        try:
            feature = self.model.FirstFeature
        except Exception:
            feature = None
        guard = 0
        while feature is not None and guard < 10000:
            guard += 1
            try:
                type_name = str(feature.GetTypeName2)
            except Exception:
                type_name = ''
            if not wanted or type_name in wanted:
                features.append(feature)
            try:
                feature = feature.GetNextFeature
            except Exception:
                break
        return features

    def _feature_identity(self, feature):
        try:
            return str(feature.GetID())
        except Exception:
            pass
        try:
            return str(feature.Name)
        except Exception:
            return str(id(feature))

    def _sketch_segments(self, sketch_feature):
        feature_id = self._feature_identity(sketch_feature)
        registered = self.sketch_segments.get(feature_id)
        if registered:
            return list(registered)
        sketch = None
        for getter_name in ('GetSpecificFeature2', 'GetSpecificFeature'):
            try:
                sketch = _maybe_call(getattr(sketch_feature, getter_name))
                if sketch is not None:
                    break
            except Exception:
                sketch = None
        if sketch is None:
            return []
        try:
            segments = sketch.GetSketchSegments()
        except Exception:
            segments = None
        if not segments:
            return []
        return list(segments) if isinstance(segments, (list, tuple)) else [segments]

    def _sketch_contours(self, sketch_feature):
        """Return sketch contours without depending on their returned order."""
        sketch = None
        for getter_name in ('GetSpecificFeature2', 'GetSpecificFeature'):
            try:
                sketch = _maybe_call(getattr(sketch_feature, getter_name))
                if sketch is not None:
                    break
            except Exception:
                sketch = None
        if sketch is None:
            return []
        try:
            contours = sketch.GetSketchContours()
        except Exception:
            contours = None
        if not contours:
            return []
        return list(contours) if isinstance(contours, (list, tuple)) else [contours]

    def _sketch_regions(self, sketch_feature):
        sketch = None
        for getter_name in ('GetSpecificFeature2', 'GetSpecificFeature'):
            try:
                sketch = _maybe_call(getattr(sketch_feature, getter_name))
                if sketch is not None:
                    break
            except Exception:
                sketch = None
        if sketch is None:
            return []
        try:
            regions = sketch.GetSketchRegions()
        except Exception:
            regions = None
        if not regions:
            return []
        return list(regions) if isinstance(regions, (list, tuple)) else [regions]

    def _sketch_segment_endpoint_gaps(self, sketch_feature):
        def point_coords(segment, getter_names):
            for getter_name in getter_names:
                try:
                    point = _maybe_call(getattr(segment, getter_name))
                except Exception:
                    continue
                if point is None:
                    continue
                if isinstance(point, (list, tuple)) and len(point) >= 3:
                    return tuple(float(value) for value in point[:3])
                try:
                    return (float(point.X), float(point.Y), float(point.Z))
                except Exception:
                    pass
            return None

        endpoints = []
        for segment in self._sketch_segments(sketch_feature):
            endpoints.append((
                point_coords(segment, ('GetStartPoint2', 'GetStartPoint')),
                point_coords(segment, ('GetEndPoint2', 'GetEndPoint')),
            ))
        gaps = []
        if endpoints:
            for index, (_start, end) in enumerate(endpoints):
                next_start = endpoints[(index + 1) % len(endpoints)][0]
                gap = None
                if end is not None and next_start is not None:
                    gap = _distance(end, next_start)
                gaps.append({
                    'after': index,
                    'end': end,
                    'next_start': next_start,
                    'gap_m': gap,
                })
        return gaps

    def _reference_plane_normal(self, feature):
        try:
            ref_plane = feature.GetSpecificFeature2
            transform = ref_plane.Transform
            data = tuple(float(value) for value in transform.ArrayData)
            if len(data) >= 9:
                return _unit((data[6], data[7], data[8]))
        except Exception:
            pass
        return None

    def _select_plane(self, axis):
        axis = _unit(axis)
        abs_axis = [abs(axis[0]), abs(axis[1]), abs(axis[2])]
        dominant = abs_axis.index(max(abs_axis))
        self._clear_selection()
        planes = []
        for index, feature in enumerate(self._features({'RefPlane'})):
            normal = self._reference_plane_normal(feature)
            score = 1.0e9
            if normal is not None:
                score = 1.0 - abs(_dot(normal, axis))
            elif index == {2: 0, 1: 1, 0: 2}.get(dominant, 0):
                score = 0.0
            planes.append((score, index, feature))
        for _score, _index, feature in sorted(planes, key=lambda item: (item[0], item[1])):
            try:
                if feature.Select2(False, 0):
                    selected_normal = self._reference_plane_normal(feature)
                    if selected_normal is None:
                        selected_normal = tuple(
                            1.0 if index == dominant else 0.0
                            for index in range(3)
                        )
                    return dominant, selected_normal
            except Exception:
                pass
        # Standard part planes can remain selectable by name even when the
        # feature-tree COM enumerator is temporarily stale.
        named_planes = (
            ('Front Plane', (0.0, 0.0, 1.0)),
            ('Top Plane', (0.0, 1.0, 0.0)),
            ('Right Plane', (1.0, 0.0, 0.0)),
        )
        for _name, normal in sorted(
            named_planes,
            key=lambda item: 1.0 - abs(_dot(item[1], axis)),
        ):
            try:
                if self.model.Extension.SelectByID2(
                    _name, 'PLANE', 0.0, 0.0, 0.0,
                    False, 0, _empty_dispatch(), 0,
                ):
                    return dominant, normal
            except Exception:
                pass
        raise RuntimeError('Could not select a SolidWorks base plane')

    def _select_profile_plane(self, axis, offset):
        dominant, base_normal = self._select_plane(axis)
        if abs(float(offset)) <= 1.0e-9:
            return dominant, base_normal
        before = {
            self._feature_identity(feature)
            for feature in self._features({'RefPlane'})
        }
        constraint = 8 | (256 if float(offset) < 0.0 else 0)
        ref_plane = self.model.FeatureManager.InsertRefPlane(
            constraint,
            _as_m(abs(float(offset))),
            0,
            0.0,
            0,
            0.0,
        )
        if ref_plane is None:
            raise RuntimeError('SolidWorks did not create the profile offset plane')
        self._clear_selection()
        new_planes = [
            feature
            for feature in self._features({'RefPlane'})
            if self._feature_identity(feature) not in before
        ]
        selected = False
        selected_normal = None
        for plane in reversed(new_planes):
            if self._select_entity(plane, append=False):
                selected = True
                selected_normal = self._reference_plane_normal(plane)
                break
        if not selected:
            selected = self._select_entity(ref_plane, append=False)
            selected_normal = self._reference_plane_normal(ref_plane)
        if not selected:
            raise RuntimeError('Could not select the generated profile offset plane')
        return dominant, selected_normal or base_normal

    def _profile_edges(self, profile):
        if isinstance(profile, dict) and profile.get('kind') == 'face':
            edges = []
            outer = profile.get('outer') or {}
            edges.extend(outer.get('edges') or [])
            for inner in profile.get('inners') or []:
                edges.extend(inner.get('edges') or [])
            return edges
        if isinstance(profile, dict) and profile.get('kind') == 'wire':
            return profile.get('edges') or []
        if isinstance(profile, dict) and profile.get('kind') == 'edge':
            return [profile]
        raise RuntimeError('Expected a SimpleCAD profile edge/wire/face payload')

    def _profile_normal(self, profile, fallback=(0.0, 0.0, 1.0)):
        hint = fallback
        if isinstance(profile, dict) and isinstance(profile.get('normal'), (list, tuple)):
            hint = profile.get('normal')
        points = self._profile_points(profile)
        if len(points) >= 3:
            origin = points[0]
            axis_point = max(points[1:], key=lambda point: _distance(point, origin))
            axis = _sub(axis_point, origin)
            normal_point = max(
                points[1:],
                key=lambda point: _norm(_cross(axis, _sub(point, origin))),
            )
            normal = _cross(axis, _sub(normal_point, origin))
            if _norm(normal) > 1.0e-9:
                normal = _unit(normal, hint)
                if _dot(normal, _unit(hint)) < 0.0:
                    normal = _mul(normal, -1.0)
                return normal
        for edge in self._profile_edges(profile):
            if edge.get('type') in {'circle', 'angle_arc'}:
                return _unit(edge.get('normal') or hint, hint)
        return _unit(hint)

    def _profile_points(self, profile):
        points = []
        for edge in self._profile_edges(profile):
            for value in self._edge_points_payload(edge):
                if not isinstance(value, (list, tuple)) or len(value) != 3:
                    continue
                point = _v3(value)
                if not any(_distance(point, existing) <= 1.0e-9 for existing in points):
                    points.append(point)
        return points

    def _profile_frame(self, profile, normal_hint):
        points = self._profile_points(profile)
        if len(points) < 3:
            raise RuntimeError('A planar SolidWorks profile requires at least three geometric points')
        origin = points[0]
        axis_point = max(points[1:], key=lambda point: _distance(point, origin))
        axis_vector = _sub(axis_point, origin)
        span = _norm(axis_vector)
        if span <= 1.0e-9:
            raise RuntimeError('SolidWorks profile plane has no stable geometric span')
        normal = self._profile_normal(profile, normal_hint)
        x_axis = _sub(axis_vector, _mul(normal, _dot(axis_vector, normal)))
        if _norm(x_axis) <= 1.0e-9:
            x_axis, _unused = _plane_axes(normal)
        else:
            x_axis = _unit(x_axis)
        y_axis = _unit(_cross(normal, x_axis))
        max_plane_error = max(abs(_dot(_sub(point, origin), normal)) for point in points)
        tolerance = max(1.0e-7, span * 1.0e-7)
        if max_plane_error > tolerance:
            raise RuntimeError(
                f'SolidWorks profile is not planar; geometric deviation={max_plane_error}'
            )
        return origin, x_axis, y_axis, normal, span

    def _edge_points_payload(self, edge):
        edge_type = edge.get('type')
        if edge_type == 'line':
            return [edge.get('start'), edge.get('end')]
        if edge_type == 'circle':
            center = _v3(edge.get('center'))
            radius = float(edge.get('radius', 1.0))
            x_axis = edge.get('_kernel_x_axis')
            y_axis = edge.get('_kernel_y_axis')
            if x_axis is None or y_axis is None:
                x_axis, y_axis = _plane_axes(
                    edge.get('normal') or (0.0, 0.0, 1.0)
                )
            else:
                x_axis = _unit(x_axis)
                y_axis = _unit(y_axis)
            return [
                center,
                _add(center, _mul(x_axis, radius)),
                _add(center, _mul(y_axis, radius)),
            ]
        if edge_type == 'angle_arc':
            center = _v3(edge.get('center'))
            radius = float(edge.get('radius', 1.0))
            start_angle = float(edge.get('start_angle', 0.0))
            end_angle = float(edge.get('end_angle', 0.0))
            normal = edge.get('normal') or (0.0, 0.0, 1.0)
            return [
                center,
                _angle_arc_world_point(
                    center,
                    radius,
                    start_angle,
                    normal,
                    edge.get('_kernel_x_axis'),
                    edge.get('_kernel_y_axis'),
                ),
                _angle_arc_world_point(
                    center,
                    radius,
                    end_angle,
                    normal,
                    edge.get('_kernel_x_axis'),
                    edge.get('_kernel_y_axis'),
                ),
            ]
        if edge_type == 'three_point_arc':
            return [edge.get('start'), edge.get('middle'), edge.get('end')]
        if edge_type == 'spline':
            return list(edge.get('controls') or [])
        return []

    def _plane_mapping(self, axis, profile=None):
        normal = _unit(axis)
        abs_axis = [abs(normal[0]), abs(normal[1]), abs(normal[2])]
        dominant = abs_axis.index(max(abs_axis))
        points = []
        if profile is not None:
            for edge in self._profile_edges(profile):
                points.extend(self._edge_points_payload(edge))
        if dominant == 2:
            offset = points[0][2] if points else 0.0
            return dominant, normal, offset, lambda p: (float(p[0]), float(p[1]))
        if dominant == 1:
            offset = points[0][1] if points else 0.0
            return dominant, normal, offset, lambda p: (float(p[0]), -float(p[2]))
        offset = points[0][0] if points else 0.0
        return dominant, normal, offset, lambda p: (-float(p[2]), float(p[1]))

    def _select_fixed_profile_plane(self, profile, normal_hint):
        origin, x_axis, y_axis, normal, span = self._profile_frame(profile, normal_hint)
        point_x = _add(origin, _mul(x_axis, span))
        point_y = _add(origin, _mul(y_axis, span))

        def point_variant(point):
            return win32com.client.VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8,
                list(_pt_m(point)),
            )

        self._clear_selection()
        ref_plane = self.model.CreatePlaneFixed2(
            point_variant(origin),
            point_variant(point_x),
            point_variant(point_y),
            False,
        )
        if ref_plane is None:
            raise RuntimeError('SolidWorks did not create the geometry-defined profile plane')
        if not self._select_entity(ref_plane, append=False):
            raise RuntimeError('Could not select the geometry-defined SolidWorks profile plane')

        def mapper(point):
            relative = _sub(_v3(point), origin)
            return _dot(relative, x_axis), _dot(relative, y_axis)

        return normal, mapper

    def _ellipse_geometry_from_spline(self, edge, mapper):
        controls = list(edge.get('controls') or [])
        weights = list(edge.get('weights') or [])
        knots = [float(value) for value in (edge.get('knots') or [])]
        multiplicities = [int(value) for value in (edge.get('multiplicities') or [])]
        if (
            int(edge.get('degree', 3)) != 2
            or bool(edge.get('periodic'))
            or len(controls) != 9
            or len(weights) != 9
            or knots != [0.0, 1.0, 2.0, 3.0, 4.0]
            or multiplicities != [3, 2, 2, 2, 3]
        ):
            return None
        corner_weight = math.sqrt(0.5)
        for index, weight in enumerate(weights):
            expected = 1.0 if index % 2 == 0 else corner_weight
            if abs(float(weight) - expected) > 1.0e-9:
                return None

        points = [tuple(float(value) for value in mapper(_v3(point))) for point in controls]

        def add2(first, second):
            return (first[0] + second[0], first[1] + second[1])

        def sub2(first, second):
            return (first[0] - second[0], first[1] - second[1])

        def mul2(point, scalar):
            return (point[0] * scalar, point[1] * scalar)

        def distance2(first, second):
            delta = sub2(first, second)
            return math.hypot(delta[0], delta[1])

        center_a = mul2(add2(points[0], points[4]), 0.5)
        center_b = mul2(add2(points[2], points[6]), 0.5)
        scale = max(
            1.0,
            max(distance2(point, center_a) for point in points),
        )
        tolerance = max(1.0e-8, scale * 1.0e-8)
        if distance2(points[0], points[8]) > tolerance:
            return None
        if distance2(center_a, center_b) > tolerance:
            return None
        center = mul2(add2(center_a, center_b), 0.5)
        first_axis = sub2(points[0], center)
        second_axis = sub2(points[2], center)
        first_radius = math.hypot(first_axis[0], first_axis[1])
        second_radius = math.hypot(second_axis[0], second_axis[1])
        if first_radius <= tolerance or second_radius <= tolerance:
            return None
        if abs(first_axis[0] * second_axis[0] + first_axis[1] * second_axis[1]) > tolerance * scale:
            return None
        expected_corners = (
            add2(center, add2(first_axis, second_axis)),
            add2(center, add2(mul2(first_axis, -1.0), second_axis)),
            add2(center, add2(mul2(first_axis, -1.0), mul2(second_axis, -1.0))),
            add2(center, add2(first_axis, mul2(second_axis, -1.0))),
        )
        if any(
            distance2(points[index], expected) > tolerance
            for index, expected in zip((1, 3, 5, 7), expected_corners)
        ):
            return None
        if first_radius >= second_radius:
            major = add2(center, first_axis)
            minor = add2(center, second_axis)
        else:
            major = add2(center, second_axis)
            minor = add2(center, first_axis)
        return center, major, minor

    def _create_exact_spline_segment(self, sketch, edge, mapper=None):
        controls = list(edge.get('controls') or [])
        knots = [float(value) for value in (edge.get('knots') or [])]
        multiplicities = [int(value) for value in (edge.get('multiplicities') or [])]
        weights = [float(value) for value in (edge.get('weights') or [])]
        if len(controls) < 2 or not knots or len(knots) != len(multiplicities):
            return None

        full_knots = []
        for knot, multiplicity in zip(knots, multiplicities):
            full_knots.extend([float(knot)] * max(0, int(multiplicity)))
        if not full_knots:
            return None
        knot_min = min(full_knots)
        knot_span = max(full_knots) - knot_min
        if knot_span <= 1.0e-15:
            return None
        # ISplineParamData requires knot values in [0, 1]. SimpleCAD stores
        # the canonical B-spline parameterization, which can use any finite
        # affine knot range.
        full_knots = [(value - knot_min) / knot_span for value in full_knots]

        rational = len(weights) == len(controls) and any(
            abs(float(weight) - 1.0) > 1.0e-12 for weight in weights
        )
        control_values = []
        for index, point in enumerate(controls):
            if mapper is None:
                px, py, pz = _pt_m(point)
            else:
                x, y = mapper(_v3(point))
                px, py, pz = _as_m(x), _as_m(y), 0.0
            if rational:
                weight = float(weights[index])
                if edge.get('periodic'):
                    control_values.extend([px, py, pz, weight])
                else:
                    control_values.extend([
                        px * weight, py * weight, pz * weight, weight,
                    ])
            else:
                control_values.extend([px, py, pz])

        param_data = None
        try:
            raw = sketch._oleobj_.InvokeTypes(
                83,
                0,
                pythoncom.DISPATCH_METHOD,
                (pythoncom.VT_DISPATCH, 0),
                (),
            )
            if raw is not None:
                param_data = win32com.client.Dispatch(raw)
        except Exception:
            try:
                param_data = sketch.CreateSplineParamData()
            except Exception:
                param_data = None
        if param_data is None:
            return None

        def put_i4(dispid, value):
            try:
                param_data._oleobj_.InvokeTypes(
                    dispid,
                    0,
                    pythoncom.DISPATCH_PROPERTYPUT,
                    (pythoncom.VT_EMPTY, 0),
                    ((pythoncom.VT_I4, pythoncom.PARAMFLAG_FIN),),
                    int(value),
                )
            except Exception:
                names = {1: 'Dimension', 2: 'Order', 3: 'Periodic', 4: 'ControlPointsCount'}
                setattr(param_data, names[dispid], int(value))

        put_i4(1, 4 if rational else 3)
        put_i4(2, int(edge.get('degree', 3)) + 1)
        put_i4(3, 1 if edge.get('periodic') else 0)
        put_i4(4, len(controls))

        control_data = win32com.client.VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_R8,
            control_values,
        )
        knot_data = win32com.client.VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_R8,
            full_knots,
        )

        def set_array(dispid, method_name, values):
            try:
                return bool(param_data._oleobj_.InvokeTypes(
                    dispid,
                    0,
                    pythoncom.DISPATCH_METHOD,
                    (pythoncom.VT_BOOL, 0),
                    ((pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),),
                    values,
                ))
            except Exception:
                return bool(getattr(param_data, method_name)(values))

        if not set_array(19, 'SetControlPoints', control_data):
            raise RuntimeError('SolidWorks rejected B-spline control points')
        if not set_array(20, 'SetKnotPoints', knot_data):
            raise RuntimeError('SolidWorks rejected B-spline knots')

        segments = None
        try:
            segments = sketch._oleobj_.InvokeTypes(
                84,
                0,
                pythoncom.DISPATCH_METHOD,
                (pythoncom.VT_VARIANT, 0),
                ((pythoncom.VT_DISPATCH, pythoncom.PARAMFLAG_FIN),),
                param_data,
            )
        except Exception:
            segments = sketch.CreateSplinesByEqnParams2(param_data)
        if not segments:
            return None
        if isinstance(segments, (list, tuple)):
            segment = list(segments)[0]
        else:
            segment = segments
        try:
            return win32com.client.Dispatch(segment)
        except Exception:
            return segment

    def _draw_edge(self, sketch, edge, mapper):
        edge_type = edge.get('type')
        if edge_type == 'line':
            sx, sy = mapper(_v3(edge.get('start')))
            ex, ey = mapper(_v3(edge.get('end')))
            return sketch.CreateLine(_as_m(sx), _as_m(sy), 0.0, _as_m(ex), _as_m(ey), 0.0)
        if edge_type == 'circle':
            center = _v3(edge.get('center'))
            radius = float(edge.get('radius', 1.0))
            x_axis = edge.get('_kernel_x_axis')
            if x_axis is None:
                x_axis, _unused_y_axis = _plane_axes(
                    edge.get('normal') or (0.0, 0.0, 1.0)
                )
            radius_point = _add(center, _mul(_unit(x_axis), radius))
            cx, cy = mapper(center)
            px, py = mapper(radius_point)
            try:
                return sketch.CreateCircle(
                    _as_m(cx), _as_m(cy), 0.0,
                    _as_m(px), _as_m(py), 0.0,
                )
            except Exception:
                return sketch.CreateCircleByRadius(
                    _as_m(cx), _as_m(cy), 0.0, _as_m(radius)
                )
        if edge_type == 'angle_arc':
            center = _v3(edge.get('center'))
            radius = float(edge.get('radius', 1.0))
            start_angle = float(edge.get('start_angle', 0.0))
            end_angle = float(edge.get('end_angle', 0.0))
            span = (end_angle - start_angle) % (2.0 * math.pi)
            if span <= 1.0e-12 and abs(end_angle - start_angle) > 1.0e-12:
                span = 2.0 * math.pi
            middle_angle = start_angle + 0.5 * span
            normal = edge.get('normal') or (0.0, 0.0, 1.0)
            arc_axes = (
                edge.get('_kernel_x_axis'),
                edge.get('_kernel_y_axis'),
            )
            start = _angle_arc_world_point(
                center, radius, start_angle, normal, *arc_axes
            )
            middle = _angle_arc_world_point(
                center, radius, middle_angle, normal, *arc_axes
            )
            end = _angle_arc_world_point(
                center, radius, end_angle, normal, *arc_axes
            )
            sx, sy = mapper(start)
            mx, my = mapper(middle)
            ex, ey = mapper(end)
            return sketch.Create3PointArc(
                _as_m(sx), _as_m(sy), 0.0,
                _as_m(ex), _as_m(ey), 0.0,
                _as_m(mx), _as_m(my), 0.0,
            )
        if edge_type == 'three_point_arc':
            sx, sy = mapper(_v3(edge.get('start')))
            mx, my = mapper(_v3(edge.get('middle')))
            ex, ey = mapper(_v3(edge.get('end')))
            # SolidWorks expects start, end, point-on-arc; SimpleCAD and FreeCAD
            # represent the same arc as start, point-on-arc, end.
            return sketch.Create3PointArc(
                _as_m(sx), _as_m(sy), 0.0,
                _as_m(ex), _as_m(ey), 0.0,
                _as_m(mx), _as_m(my), 0.0,
            )
        if edge_type == 'spline':
            ellipse = self._ellipse_geometry_from_spline(edge, mapper)
            if ellipse is not None:
                center, major, minor = ellipse
                return sketch.CreateEllipse(
                    _as_m(center[0]), _as_m(center[1]), 0.0,
                    _as_m(major[0]), _as_m(major[1]), 0.0,
                    _as_m(minor[0]), _as_m(minor[1]), 0.0,
                )
            coords = []
            for point in edge.get('controls') or []:
                x, y = mapper(_v3(point))
                coords.extend([_as_m(x), _as_m(y), 0.0])
            if len(coords) >= 6:
                try:
                    segment = self._create_exact_spline_segment(sketch, edge, mapper)
                    if segment is not None:
                        return segment
                except Exception as exc:
                    self.logs.append(f'exact B-spline creation failed: {exc}')
                point_data = win32com.client.VARIANT(
                    pythoncom.VT_ARRAY | pythoncom.VT_R8,
                    coords,
                )
                try:
                    previous_add_to_db = bool(sketch.AddToDB)
                except Exception:
                    previous_add_to_db = True
                try:
                    sketch.AddToDB = False
                except Exception:
                    pass
                try:
                    for dispid, arg_types, args in (
                        (
                            69,
                            (
                                (pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),
                                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                            ),
                            (point_data, True),
                        ),
                        (
                            37,
                            ((pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),),
                            (point_data,),
                        ),
                    ):
                        try:
                            raw_segment = sketch._oleobj_.InvokeTypes(
                                dispid,
                                0,
                                pythoncom.DISPATCH_METHOD,
                                (pythoncom.VT_DISPATCH, 0),
                                arg_types,
                                *args,
                            )
                            if raw_segment is not None:
                                return win32com.client.Dispatch(raw_segment)
                        except Exception:
                            pass
                    return None
                finally:
                    try:
                        sketch.AddToDB = previous_add_to_db
                    except Exception:
                        pass
        if edge_type == 'helix':
            raise SimpleCADUnsupportedOpError('SolidWorks helix edge construction is not yet supported')
        raise SimpleCADUnsupportedOpError(f'Unsupported profile edge type for SolidWorks sketch: {edge_type}')

    def _draw_3d_edge(self, sketch, edge):
        edge_type = edge.get('type')
        if edge_type == 'line':
            start = _pt_m(edge.get('start'))
            end = _pt_m(edge.get('end'))
            return sketch.CreateLine(*start, *end)
        if edge_type in {'angle_arc', 'three_point_arc'}:
            if edge_type == 'angle_arc':
                center = _v3(edge.get('center'))
                radius = float(edge.get('radius', 1.0))
                start_angle = float(edge.get('start_angle', 0.0))
                end_angle = float(edge.get('end_angle', 0.0))
                span = (end_angle - start_angle) % (2.0 * math.pi)
                if span <= 1.0e-12 and abs(end_angle - start_angle) > 1.0e-12:
                    span = 2.0 * math.pi
                normal = edge.get('normal') or (0.0, 0.0, 1.0)
                arc_axes = (
                    edge.get('_kernel_x_axis'),
                    edge.get('_kernel_y_axis'),
                )
                start = _angle_arc_world_point(
                    center, radius, start_angle, normal, *arc_axes
                )
                middle = _angle_arc_world_point(
                    center,
                    radius,
                    start_angle + 0.5 * span,
                    normal,
                    *arc_axes,
                )
                end = _angle_arc_world_point(
                    center, radius, end_angle, normal, *arc_axes
                )
            else:
                start = _v3(edge.get('start'))
                middle = _v3(edge.get('middle'))
                end = _v3(edge.get('end'))
            return sketch.Create3PointArc(*_pt_m(start), *_pt_m(end), *_pt_m(middle))
        if edge_type == 'spline':
            controls = [_v3(point) for point in (edge.get('controls') or [])]
            if len(controls) < 2:
                raise RuntimeError('A SolidWorks 3D B-spline requires at least two control points')
            try:
                segment = self._create_exact_spline_segment(sketch, edge)
                if segment is not None:
                    return segment
            except Exception as exc:
                self.logs.append(f'exact 3D B-spline creation failed: {exc}')
            point_data = win32com.client.VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8,
                [coordinate for point in controls for coordinate in _pt_m(point)],
            )
            try:
                return sketch.CreateSpline2(point_data, True)
            except Exception:
                return sketch.CreateSpline(point_data)
        if edge_type == 'helix':
            raise SimpleCADUnsupportedOpError('SolidWorks helix path construction is handled separately')
        raise SimpleCADUnsupportedOpError(
            f'Unsupported 3D sweep path edge type for SolidWorks: {edge_type}'
        )

    def _create_3d_path_sketch(self, path, name):
        before_sketches = {
            self._feature_identity(feature)
            for feature in self._features({'3DProfileFeature'})
        }
        self._clear_selection()
        sketch_mgr = self.model.SketchManager
        sketch_mgr.Insert3DSketch(True)
        active_sketch = sketch_mgr.ActiveSketch
        if active_sketch is None:
            raise RuntimeError('SolidWorks did not enter 3D path sketch edit mode')
        created_segments = []
        try:
            sketch_mgr.AddToDB = True
            try:
                sketch_mgr.DisplayWhenAdded = False
            except Exception:
                pass
            for edge in self._profile_edges(path):
                entity = self._draw_3d_edge(sketch_mgr, edge)
                if entity is None:
                    raise RuntimeError(
                        f'SolidWorks rejected a 3D path {edge.get("type", "edge")} entity'
                    )
                created_segments.append(entity)
        finally:
            try:
                sketch_mgr.AddToDB = False
                sketch_mgr.DisplayWhenAdded = True
            except Exception:
                pass
            sketch_mgr.Insert3DSketch(True)

        sketch_feature = None
        try:
            sketch_feature = _maybe_call(active_sketch.GetFeature)
        except Exception:
            pass
        new_sketches = [
            feature
            for feature in self._features({'3DProfileFeature'})
            if self._feature_identity(feature) not in before_sketches
        ]
        if new_sketches:
            sketch_feature = new_sketches[-1]
        if sketch_feature is None:
            raise RuntimeError('SolidWorks did not persist the generated 3D path sketch')
        try:
            sketch_feature.Name = str(name)
        except Exception:
            pass
        self.sketch_segments[self._feature_identity(sketch_feature)] = created_segments
        return sketch_feature

    def _create_profile_sketch(
        self,
        profile,
        axis,
        name,
        *,
        use_profile_offset=False,
        revolve_axis=None,
    ):
        profile_normal = self._profile_normal(profile, axis)
        axis_alignment = max(abs(value) for value in profile_normal)
        if axis_alignment < 1.0 - 1.0e-10:
            _dominant = max(range(3), key=lambda index: abs(float(axis[index])))
            _normal, mapper = self._select_fixed_profile_plane(profile, axis)
            offset = 0.0
        else:
            _dominant, _requested_normal, offset, mapper = self._plane_mapping(
                axis, profile
            )
            if use_profile_offset:
                _dominant, _normal = self._select_profile_plane(axis, offset)
            else:
                _dominant, _normal = self._select_plane(axis)
        before_sketches = {
            self._feature_identity(feature)
            for feature in self._features({'ProfileFeature', '3DProfileFeature'})
        }
        sketch_mgr = self.model.SketchManager
        sketch_mgr.InsertSketch(True)
        active_sketch = sketch_mgr.ActiveSketch
        if active_sketch is None:
            raise RuntimeError('SolidWorks did not enter profile sketch edit mode')
        try:
            sketch_mgr.AddToDB = True
            try:
                sketch_mgr.DisplayWhenAdded = False
            except Exception:
                pass
            created_segments = []
            for edge in self._profile_edges(profile):
                entity = self._draw_edge(sketch_mgr, edge, mapper)
                if entity is None:
                    raise RuntimeError(
                        f'SolidWorks rejected a profile {edge.get("type", "edge")} entity'
                    )
                created_segments.append(entity)
            axis_entity = None
            if revolve_axis is not None:
                axis_origin, axis_direction = revolve_axis
                points = []
                for edge in self._profile_edges(profile):
                    points.extend(self._edge_points_payload(edge))
                span = max(
                    [
                        _distance(point, axis_origin)
                        for point in points
                        if isinstance(point, (list, tuple))
                    ]
                    or [1.0]
                )
                span = max(1.0, span * 1.25)
                first = _sub(axis_origin, _mul(_unit(axis_direction), span))
                second = _add(axis_origin, _mul(_unit(axis_direction), span))
                x1, y1 = mapper(first)
                x2, y2 = mapper(second)
                axis_entity = sketch_mgr.CreateCenterLine(
                    _as_m(x1), _as_m(y1), 0.0,
                    _as_m(x2), _as_m(y2), 0.0,
                )
                if axis_entity is None:
                    raise RuntimeError('SolidWorks rejected the revolve construction axis')
        finally:
            try:
                sketch_mgr.AddToDB = False
                sketch_mgr.DisplayWhenAdded = True
            except Exception:
                pass
        sketch_mgr.InsertSketch(True)
        sketch_feature = None
        try:
            sketch_feature = _maybe_call(active_sketch.GetFeature)
        except Exception:
            sketch_feature = None
        sketches = self._features({'ProfileFeature', '3DProfileFeature'})
        new_sketches = [
            feature for feature in sketches
            if self._feature_identity(feature) not in before_sketches
        ]
        if new_sketches:
            sketch_feature = new_sketches[-1]
        elif sketches:
            sketch_feature = sketches[-1]
        if sketch_feature is None:
            raise RuntimeError('SolidWorks did not persist the generated profile sketch')
        try:
            sketch_feature.Name = str(name)
        except Exception:
            pass
        self.sketch_segments[self._feature_identity(sketch_feature)] = created_segments
        return sketch_feature, offset, _dominant, _normal, axis_entity

    def _extrude_profile(self, profile, params, node_id):
        direction = _unit(params.get('direction') or self._profile_normal(profile))
        distance = float(params.get('distance', 0.0))
        if abs(distance) <= 1.0e-12:
            raise RuntimeError('Extrude distance is zero')
        before = self._body_names()
        terminal_part_feature = self._is_terminal_part_feature(node_id)
        # Prefer a native sketch plane at the profile's actual offset even for
        # intermediate Extrudes. The old non-terminal path created the feature
        # at a reference plane and then inserted a static transform body,
        # severing downstream parameter propagation after reopen.
        use_native_profile_offset = True
        try:
            sketch_obj, offset, dominant, sketch_normal, _axis_entity = self._create_profile_sketch(
                profile,
                direction,
                f'SimpleCADSketch_{node_id}',
                use_profile_offset=use_native_profile_offset,
            )
        except RuntimeError as exc:
            if 'profile offset plane' not in str(exc):
                raise
            self._clear_selection()
            self._mark_degraded(
                f'SimpleCAD_{node_id}_offset',
                'static_terminal_extrude_offset',
            )
            use_native_profile_offset = False
            sketch_obj, offset, dominant, sketch_normal, _axis_entity = self._create_profile_sketch(
                profile,
                direction,
                f'SimpleCADSketch_{node_id}',
                use_profile_offset=False,
            )
        try:
            if sketch_obj is not None:
                self._clear_selection()
                self._select_entity(sketch_obj)
        except Exception:
            pass
        reverse_direction = _dot(direction, sketch_normal) < 0.0 or distance < 0.0
        feature = self.model.FeatureManager.FeatureExtrusion2(
            True, False, bool(reverse_direction),
            0, 0,
            _as_m(abs(distance)), 0.0,
            False, False, False, False,
            0.0, 0.0,
            False, False, False, False,
            False, False, False,
            0.0, 0.0,
            False,
        )
        if feature is None:
            raise RuntimeError('SolidWorks did not create the extrude feature')
        try:
            feature.Name = f'SimpleCAD_{node_id}_extrude'
        except Exception:
            pass
        body = self._capture_new_body(before, feature)
        if abs(offset) > 1.0e-9 and not use_native_profile_offset:
            vector = (0.0, 0.0, 0.0)
            if dominant == 0:
                vector = (offset, 0.0, 0.0)
            elif dominant == 1:
                vector = (0.0, offset, 0.0)
            else:
                vector = (0.0, 0.0, offset)
            body = self._transform_body_feature(body, _translation_matrix(vector), f'SimpleCAD_{node_id}_offset')
        return body

    def _revolve_profile(self, profile, params, node_id):
        axis = _unit(params.get('axis') or (0.0, 0.0, 1.0))
        origin = _v3(params.get('origin') or (0.0, 0.0, 0.0))
        profile_normal = self._profile_normal(profile)
        sketch_obj, _offset, _dominant, _normal, axis_entity = self._create_profile_sketch(
            profile,
            profile_normal,
            f'SimpleCADSketch_{node_id}',
            use_profile_offset=True,
            revolve_axis=(origin, axis),
        )
        self.logs.append(f'revolve native feature requested for {node_id}; using SolidWorks FeatureRevolve2 fallback signatures')
        before = self._body_names()
        angle = math.radians(float(params.get('angle', 360.0)))
        feature = None
        attempt_states = []

        try:
            self.model.ForceRebuild3(False)
        except Exception:
            pass
        sketch_regions = self._sketch_regions(sketch_obj)
        sketch_contours = self._sketch_contours(sketch_obj)
        segment_gaps = self._sketch_segment_endpoint_gaps(sketch_obj)
        profile_state = {
            'segments': len(self._sketch_segments(sketch_obj)),
            'regions': len(sketch_regions),
            'contours': len(sketch_contours),
            'gaps': segment_gaps,
        }
        self.logs.append(
            f'revolve profile state for {node_id}: {profile_state!r}'
        )

        def select_revolve_inputs(include_axis, use_region=False):
            self._clear_selection()
            profile_entity = sketch_regions[0] if use_region and sketch_regions else sketch_obj
            if profile_entity is None or not self._select_entity(profile_entity):
                raise RuntimeError(f'Could not select the revolve profile for {node_id}')
            if include_axis:
                if axis_entity is None or not self._select_entity(axis_entity, append=True, mark=4):
                    raise RuntimeError(f'Could not select the revolve axis for {node_id}')
            return self._selection_state()

        attempts = (
            (
                'FeatureRevolve2',
                True,
                False,
                False,
                lambda: self.model.FeatureManager.FeatureRevolve2(
                    True, True, False, False, False, False,
                    0, 0, abs(angle), 0.0,
                    False, False, 0.0, 0.0,
                    0, 0.0, 0.0,
                    False, False, True,
                ),
            ),
            (
                'FeatureRevolve2WithoutAxis',
                False,
                False,
                False,
                lambda: self.model.FeatureManager.FeatureRevolve2(
                    True, True, False, False, False, False,
                    0, 0, abs(angle), 0.0,
                    False, False, 0.0, 0.0,
                    0, 0.0, 0.0,
                    False, False, True,
                ),
            ),
            (
                'FeatureRevolve2Region',
                True,
                False,
                True,
                lambda: self.model.FeatureManager.FeatureRevolve2(
                    True, True, False, False, False, False,
                    0, 0, abs(angle), 0.0,
                    False, False, 0.0, 0.0,
                    0, 0.0, 0.0,
                    False, False, True,
                ),
            ),
            (
                'FeatureRevolve',
                True,
                False,
                False,
                lambda: self.model.FeatureManager.FeatureRevolve(
                    abs(angle), False, 0.0, 0, 0,
                    False, False, True,
                ),
            ),
            (
                'FeatureRevolveScoped',
                True,
                True,
                False,
                lambda: self.model.FeatureManager.FeatureRevolve(
                    abs(angle), False, 0.0, 0, 0,
                    False, True, True,
                ),
            ),
        )
        for api_name, include_axis, use_scope, use_region, create_feature in attempts:
            try:
                if use_region and not sketch_regions:
                    continue
                selection_state = select_revolve_inputs(include_axis, use_region)
                attempt_states.append({
                    'api': api_name,
                    'include_axis': include_axis,
                    'use_scope': use_scope,
                    'use_region': use_region,
                    'selections': selection_state,
                })
                feature = create_feature()
                if feature is not None:
                    break
                self.logs.append(
                    f'revolve {api_name} attempt returned no feature for {node_id}; '
                    f'include_axis={include_axis} use_scope={use_scope} '
                    f'selections={selection_state!r}'
                )
            except Exception as exc:
                self.logs.append(
                    f'revolve {api_name} attempt failed for {node_id}: {exc}'
                )
        if feature is None:
            raise SimpleCADUnsupportedOpError(
                f'SolidWorks revolve feature creation failed; profile={profile_state!r}; '
                f'attempts={attempt_states!r}; '
                f'logs={self.logs[-4:]!r}'
            )
        return self._capture_new_body(before, feature)

    def _linear_profile_vertices(self, profile):
        try:
            edges = list(self._profile_edges(profile))
        except Exception:
            return []
        if len(edges) < 3 or any(edge.get('type') != 'line' for edge in edges):
            return []
        vertices = [_v3(edge.get('start')) for edge in edges]
        scale = max(
            1.0,
            *(
                _norm(_sub(edge.get('end'), edge.get('start')))
                for edge in edges
            ),
        )
        for index, edge in enumerate(edges):
            if _distance(
                edge.get('end'), vertices[(index + 1) % len(vertices)]
            ) > scale * 1.0e-7:
                return []
        return vertices

    def _loft_profiles(self, profiles, params, node_id):
        if bool(params.get('ruled')) and len(profiles) > 2:
            parent_descriptor = (
                self.canonical_loft_descriptors.get(str(node_id)) or {}
            )
            ruled_descriptors = list(
                parent_descriptor.get('ruled_segments') or []
            )
            segment_bodies = []
            for index in range(len(profiles) - 1):
                segment_params = dict(params)
                segment_params['ruled'] = False
                segment_params['_ruled_segment'] = True
                segment_params['profile_count'] = 2
                if index < len(ruled_descriptors):
                    segment_params['_canonical_descriptor'] = (
                        ruled_descriptors[index]
                    )
                segment_bodies.append(self._loft_profiles(
                    profiles[index:index + 2],
                    segment_params,
                    f'{node_id}_ruled_{index + 1}',
                ))
            self.logs.append(
                f'loft {node_id} preserved ruled topology as '
                f'{len(segment_bodies)} adjacent two-section lofts'
            )
            result = self._boolean_body(
                segment_bodies[0],
                segment_bodies[1:],
                SWBODYADD,
                f'SimpleCAD_{node_id}_ruled',
                clean=False,
            )
            if (
                parent_descriptor
                and not self._body_matches_canonical(result, parent_descriptor)
            ):
                raise RuntimeError(
                    f'SolidWorks ruled loft union differs from canonical result '
                    f'for {node_id}; actual_volume={self._body_volume(result)!r}; '
                    f'actual_bbox={self._box_from_entity(result)!r}; '
                    f'canonical={parent_descriptor!r}'
                )
            return result
        self.logs.append(f'loft native feature requested for {node_id}; using SolidWorks blend fallback signatures')
        # Native Loft exposes its result through Feature.GetFaces ->
        # Face2.GetBody. Avoid a document-wide body scan before every ruled
        # segment; large models can contain hundreds of prior feature bodies.
        before = set()
        self._clear_selection()
        sketches = []
        for index, profile in enumerate(profiles):
            sketch_obj, _offset, _dominant, normal, _axis_entity = self._create_profile_sketch(
                profile,
                self._profile_normal(profile),
                f'SimpleCADSketch_{node_id}_{index}',
                use_profile_offset=True,
            )
            if sketch_obj is not None:
                sketches.append(sketch_obj)
        profile_states = []
        for sketch_obj in sketches:
            contours = []
            sketch = None
            try:
                sketch = _maybe_call(sketch_obj.GetSpecificFeature2)
            except Exception:
                pass
            if sketch is not None:
                try:
                    raw_contours = sketch.GetSketchContours()
                except Exception:
                    raw_contours = None
                if raw_contours:
                    raw_contours = (
                        list(raw_contours)
                        if isinstance(raw_contours, (list, tuple))
                        else [raw_contours]
                    )
                    for contour in raw_contours:
                        try:
                            contours.append(bool(contour.IsClosed()))
                        except Exception:
                            contours.append(None)
            profile_states.append({
                'segments': len(self._sketch_segments(sketch_obj)),
                'contours_closed': contours,
            })
        try:
            profile_edge_groups = [
                list(self._profile_edges(profile)) for profile in profiles
            ]
            dense_polyline_profiles = bool(profile_edge_groups) and all(
                len(edges) >= 32
                and all(edge.get('type') == 'line' for edge in edges)
                for edges in profile_edge_groups
            )
        except Exception:
            dense_polyline_profiles = False
        modeler_loft_args = (
            (
                False, 0, 0.0, 0.0,
                True, False, True, False, True, 1.0,
                1.0, 1.0, True, True, 1, 1, False,
            ),
            (
                False, 0, 0.0, 0.0,
                False, False, False, False, True, 1.0,
                0.0, 0.0, True, True, 0, 0, False,
            ),
        )
        def select_sections(
            section_sketches,
            selection_mode='sketch',
            segment_offsets=None,
        ):
            self._clear_selection()
            for index, sketch_obj in enumerate(section_sketches):
                entity = sketch_obj
                if selection_mode == 'sketch_pick':
                    vertices = self._linear_profile_vertices(profiles[index])
                    if not vertices:
                        raise RuntimeError(
                            f'No linear profile vertices for SolidWorks loft '
                            f'pick point {index} in {node_id}'
                        )
                    offset = 0
                    if segment_offsets and index < len(segment_offsets):
                        offset = int(segment_offsets[index])
                    point = vertices[offset % len(vertices)]
                    try:
                        sketch_name = str(_maybe_call(sketch_obj.Name))
                    except Exception:
                        sketch_name = ''
                    if not sketch_name or not bool(
                        self.model.Extension.SelectByID2(
                            sketch_name,
                            'SKETCH',
                            float(point[0]) * MM_TO_M,
                            float(point[1]) * MM_TO_M,
                            float(point[2]) * MM_TO_M,
                            index > 0,
                            1,
                            _empty_dispatch(),
                            0,
                        )
                    ):
                        raise RuntimeError(
                            f'Could not select SolidWorks loft profile {index} '
                            f'at canonical pick point {point!r} for {node_id}'
                        )
                    continue
                if selection_mode == 'contour':
                    contours = self._sketch_contours(sketch_obj)
                    if contours:
                        entity = contours[0]
                elif selection_mode == 'segment':
                    segments = self._sketch_segments(sketch_obj)
                    if segments:
                        offset = 0
                        if segment_offsets and index < len(segment_offsets):
                            offset = int(segment_offsets[index])
                        entity = segments[offset % len(segments)]
                if not self._select_entity(entity, append=index > 0, mark=1):
                    raise RuntimeError(
                        f'Could not select SolidWorks loft profile {index} '
                        f'using {selection_mode} for {node_id}'
                    )
            return self._selection_state()

        def create_native_loft(
            section_sketches,
            section_label,
            selection_mode='sketch',
            segment_offsets=None,
        ):
            selection = select_sections(
                section_sketches, selection_mode, segment_offsets
            )
            tangent_attempt = (
                ('Blend2TangentCompatibility', lambda: self.model.FeatureManager.InsertProtrusionBlend2(
                    False, True, False, 1.0,
                    0, 0,
                    1.0, 1.0,
                    True, True,
                    False, 0.0, 0.0, 0,
                    False, True, True,
                    2,
                )),
            )
            unconstrained_attempts = (
                ('Blend2Unconstrained', lambda: self.model.FeatureManager.InsertProtrusionBlend2(
                    False, False, False, 1.0,
                    0, 0,
                    0.0, 0.0,
                    False, False,
                    False, 0.0, 0.0, 0,
                    False, False, True,
                    2,
                )),
                ('BlendLegacy', lambda: self.model.FeatureManager.InsertProtrusionBlend(
                    False, False, False, 1.0,
                    0, 0,
                    0.0, 0.0,
                    False, False,
                    False, 0.0, 0.0, 0,
                    False, False, True,
                )),
            )
            attempts = (
                unconstrained_attempts + tangent_attempt
                if params.get('_ruled_segment')
                else tangent_attempt + unconstrained_attempts
            )
            for attempt_name, attempt in attempts:
                try:
                    candidate = attempt()
                    if candidate is not None:
                        self.logs.append(
                            f'loft {node_id} {section_label} used {attempt_name}'
                        )
                        return candidate, selection
                except Exception as exc:
                    self.logs.append(
                        f'loft {attempt_name} attempt failed for '
                        f'{node_id} {section_label}: {exc}'
                    )
            self.logs.append(
                f'loft attempts returned no feature for {node_id} {section_label}; '
                f'sections={len(section_sketches)} selections={selection!r}'
            )
            return None, selection

        if dense_polyline_profiles:
            try:
                selection_state = select_sections(sketches, 'sketch')
                candidates = []
                legacy_body = self._create_loft_temp_body(
                    sketches, modeler_loft_args[0], use_legacy=True
                )
                if legacy_body is not None:
                    candidates.append(
                        ('CreateLoftBody', legacy_body, self._body_volume(legacy_body))
                    )
                for index, modeler_args in enumerate(modeler_loft_args):
                    try:
                        temp_body = self._create_loft_temp_body(
                            sketches, modeler_args, use_legacy=False
                        )
                    except Exception as exc:
                        self.logs.append(
                            f'dense-polyline CreateLoftBody2[{index}] failed '
                            f'for {node_id}: {exc}'
                        )
                        continue
                    if temp_body is not None:
                        candidates.append((
                            f'CreateLoftBody2[{index}]',
                            temp_body,
                            self._body_volume(temp_body),
                        ))
                if candidates:
                    descriptor = self.canonical_loft_descriptors.get(node_id) or {}
                    expected_volume = descriptor.get('volume')
                    ranked = [
                        candidate
                        for candidate in candidates
                        if candidate[2] is not None
                    ]
                    if isinstance(expected_volume, (int, float)) and ranked:
                        selected = min(
                            ranked,
                            key=lambda candidate: abs(
                                candidate[2] - float(expected_volume)
                            ),
                        )
                    else:
                        selected = candidates[0]
                    self.logs.append(
                        f'loft {node_id} dense-polyline candidates='
                        f'{[(item[0], item[2]) for item in candidates]!r}; '
                        f'expected_volume={expected_volume!r}; used={selected[0]}'
                    )
                    return self._create_feature_from_body(
                        selected[1], f'SimpleCAD_{node_id}_loft'
                    )
            except Exception as exc:
                self.logs.append(
                    f'dense-polyline temporary loft failed for {node_id}: {exc}'
                )

        canonical_segment = params.get('_canonical_descriptor')
        exact_static_candidate = None
        exact_static_attempts = []
        if isinstance(canonical_segment, dict):
            segment_count = min(
                (
                    len(self._sketch_segments(sketch_obj))
                    for sketch_obj in sketches
                ),
                default=0,
            )
            selection_variants = [
                ('sketch_pick', [0, offset])
                for offset in range(segment_count)
            ]
            selection_variants.extend(
                ('segment', [0, offset])
                for offset in range(segment_count)
            )
            selection_variants.extend((
                ('sketch', None),
                ('contour', None),
            ))
            for selection_mode, segment_offsets in selection_variants:
                selection_label = (
                    f'{selection_mode}{segment_offsets!r}'
                    if segment_offsets is not None else selection_mode
                )
                try:
                    selection_state = select_sections(
                        sketches, selection_mode, segment_offsets
                    )
                except Exception as exc:
                    exact_static_attempts.append((
                        selection_label, 'selection', None, None, str(exc)
                    ))
                    continue
                loft_body_attempts = [('CreateLoftBody', True, modeler_loft_args[0])]
                loft_body_attempts.extend(
                    (f'CreateLoftBody2[{index}]', False, modeler_args)
                    for index, modeler_args in enumerate(modeler_loft_args)
                )
                for attempt_name, use_legacy, modeler_args in loft_body_attempts:
                    try:
                        temp_body = self._create_loft_temp_body(
                            sketches, modeler_args, use_legacy=use_legacy
                        )
                    except Exception as exc:
                        exact_static_attempts.append((
                            selection_label, attempt_name, None, None, str(exc)
                        ))
                        continue
                    volume = self._body_volume(temp_body) if temp_body else None
                    bbox = self._box_from_entity(temp_body) if temp_body else None
                    matches = bool(
                        temp_body is not None
                        and self._body_matches_canonical(
                            temp_body, canonical_segment
                        )
                    )
                    exact_static_attempts.append((
                        selection_label, attempt_name, volume, bbox, matches
                    ))
                    if matches and exact_static_candidate is None:
                        exact_static_candidate = (
                            temp_body,
                            selection_mode,
                            attempt_name,
                            segment_offsets,
                            selection_label,
                        )
                        break
                if exact_static_candidate is not None:
                    break

        initial_selection_mode = (
            'segment' if params.get('_ruled_segment') else 'sketch'
        )
        initial_segment_offsets = None
        if exact_static_candidate is not None:
            initial_selection_mode = exact_static_candidate[1]
            initial_segment_offsets = exact_static_candidate[3]
        feature, selection_state = create_native_loft(
            sketches,
            'all sections',
            initial_selection_mode,
            initial_segment_offsets,
        )
        if feature is None:
            for selection_mode in ('sketch', 'contour', 'segment'):
                if selection_mode == initial_selection_mode:
                    continue
                try:
                    feature, selection_state = create_native_loft(
                        sketches, selection_mode, selection_mode
                    )
                except Exception as exc:
                    self.logs.append(
                        f'loft {selection_mode} selection failed for {node_id}: {exc}'
                    )
                    feature = None
                if feature is not None:
                    break
        if feature is None and exact_static_candidate is not None:
            (
                temp_body,
                _selection_mode,
                attempt_name,
                _segment_offsets,
                selection_label,
            ) = exact_static_candidate
            self._mark_degraded(
                f'SimpleCAD_{node_id}_loft',
                'exact_static_ruled_loft_segment_after_native_failure',
            )
            self.logs.append(
                f'loft {node_id} used canonical exact temporary segment via '
                f'{selection_label}/{attempt_name}; attempts='
                f'{exact_static_attempts!r}'
            )
            return self._create_feature_from_body(
                temp_body, f'SimpleCAD_{node_id}_loft_exact_static'
            )
        if feature is None:
            for modeler_args in modeler_loft_args:
                try:
                    temp_body = self._create_loft_temp_body(sketches, modeler_args)
                    if temp_body is not None:
                        return self._create_feature_from_body(
                            temp_body, f'SimpleCAD_{node_id}_loft'
                        )
                except Exception as exc:
                    self.logs.append(
                        f'temporary loft body attempt failed for {node_id}: {exc}'
                    )
            raise SimpleCADUnsupportedOpError(
                f'SolidWorks loft feature creation failed; profiles={len(sketches)}; '
                f'profile_states={profile_states!r}; selections={selection_state!r}; '
                f'logs={self.logs[-6:]!r}'
            )
        native_body = self._capture_new_body(before, feature)
        if not isinstance(canonical_segment, dict):
            return native_body
        if self._body_matches_canonical(native_body, canonical_segment):
            self.logs.append(
                f'loft {node_id} retained canonical native ruled segment; '
                f'volume={self._body_volume(native_body)!r}'
            )
            return native_body
        if exact_static_candidate is not None:
            (
                temp_body,
                _selection_mode,
                attempt_name,
                _segment_offsets,
                selection_label,
            ) = exact_static_candidate
            self._mark_degraded(
                f'SimpleCAD_{node_id}_loft',
                'exact_static_ruled_loft_segment_after_native_mismatch',
            )
            self.logs.append(
                f'loft {node_id} native ruled segment differed from canonical; '
                f'native_volume={self._body_volume(native_body)!r} '
                f'native_bbox={self._box_from_entity(native_body)!r}; used '
                f'{selection_label}/{attempt_name}; attempts='
                f'{exact_static_attempts!r}'
            )
            return self._create_feature_from_body(
                temp_body, f'SimpleCAD_{node_id}_loft_exact_static'
            )
        raise RuntimeError(
            f'SolidWorks could not reproduce canonical ruled loft segment '
            f'{node_id}; native_volume={self._body_volume(native_body)!r}; '
            f'native_bbox={self._box_from_entity(native_body)!r}; '
            f'canonical={canonical_segment!r}; '
            f'temporary_attempts={exact_static_attempts!r}'
        )

    def _single_helix_edge(self, path):
        try:
            edges = list(self._profile_edges(path))
        except Exception:
            return None
        if len(edges) == 1 and edges[0].get('type') == 'helix':
            return edges[0]
        return None

    def _create_helix_path(self, helix, node_id):
        params = dict(helix.get('params') or {})
        center = _v3(params.get('center') or (0.0, 0.0, 0.0))
        axis = _unit(params.get('dir') or params.get('axis') or (0.0, 0.0, 1.0))
        radius = abs(float(params.get('radius', 0.0)))
        pitch = abs(float(params.get('pitch', 0.0)))
        height = abs(float(params.get('height', 0.0)))
        if radius <= TOL or pitch <= TOL or height <= TOL:
            raise RuntimeError(
                f'SolidWorks helix requires positive radius, pitch, and height; '
                f'params={params!r}'
            )

        circle_profile = {
            'kind': 'wire',
            'edges': [{
                'kind': 'edge',
                'type': 'circle',
                'center': center,
                'radius': radius,
                'normal': axis,
            }],
        }
        circle_sketch, _offset, _dominant, _normal, _axis_entity = self._create_profile_sketch(
            circle_profile,
            axis,
            f'SimpleCADSketch_{node_id}_helix_base',
            use_profile_offset=True,
        )

        before = {
            self._feature_identity(feature)
            for feature in self._features()
        }
        self._clear_selection()
        if not self._select_entity(circle_sketch, append=False):
            raise RuntimeError(f'Could not select the helix base sketch for {node_id}')

        # swHelixDefinedByHeightAndPitch = 2. InsertHelix creates the native
        # feature but returns no dispatch object, so identify it geometrically
        # through the newly added feature rather than by a tree position.
        dominant = max(range(3), key=lambda index: abs(axis[index]))
        reverse_direction = axis[dominant] < 0.0
        revolutions = height / pitch
        self.model.InsertHelix(
            reverse_direction,
            True,
            False,
            False,
            2,
            _as_m(height),
            _as_m(pitch),
            revolutions,
            0.0,
            0.0,
        )
        helix_features = [
            feature
            for feature in self._features({'Helix'})
            if self._feature_identity(feature) not in before
        ]
        if not helix_features:
            raise RuntimeError(f'SolidWorks did not create the native helix for {node_id}')
        feature = helix_features[-1]
        try:
            feature.Name = f'SimpleCADHelix_{node_id}'
        except Exception:
            pass
        return feature

    def _helix_edge_selector(self, helix):
        params = dict(helix.get('params') or {})
        center = _v3(params.get('center') or (0.0, 0.0, 0.0))
        axis = _unit(params.get('dir') or params.get('axis') or (0.0, 0.0, 1.0))
        radius = abs(float(params.get('radius', 0.0)))
        pitch = abs(float(params.get('pitch', 0.0)))
        height = abs(float(params.get('height', 0.0)))
        if radius <= TOL or pitch <= TOL or height <= TOL:
            return None

        # SolidWorks may expose a native helix as a feature, a body, or a
        # single edge depending on the installed version. Build a geometric
        # signature for the expected helix and match among all exposed edges;
        # never rely on the order returned by GetEdges().
        axis_index = max(range(3), key=lambda index: abs(axis[index]))
        expected_min = list(center)
        expected_max = list(center)
        for index in range(3):
            radial = radius * math.sqrt(max(0.0, 1.0 - axis[index] * axis[index]))
            expected_min[index] -= radial
            expected_max[index] += radial
        if axis[axis_index] >= 0.0:
            expected_max[axis_index] += height
        else:
            expected_min[axis_index] -= height
        expected_center = tuple(
            (expected_min[index] + expected_max[index]) * 0.5
            for index in range(3)
        )
        expected_length = math.hypot(
            2.0 * math.pi * radius * (height / pitch), height
        )
        return {
            'bbox': {'min': tuple(expected_min), 'max': tuple(expected_max)},
            'center': expected_center,
            'length': expected_length,
        }

    def _helix_feature_edges(self, feature, helix):
        candidates = []
        objects = [feature]
        for getter_name in ('GetSpecificFeature2', 'GetBody', 'IGetBody2'):
            try:
                value = _maybe_call(getattr(feature, getter_name))
                if value is not None:
                    objects.append(value)
            except Exception:
                pass
        seen = set()
        for owner in objects:
            try:
                raw_edges = owner.GetEdges()
            except Exception:
                raw_edges = None
            if not raw_edges:
                continue
            edges = list(raw_edges) if isinstance(raw_edges, (list, tuple)) else [raw_edges]
            for edge in edges:
                identity = self._feature_identity(edge)
                if identity in seen:
                    continue
                seen.add(identity)
                try:
                    candidates.append((edge, self._edge_signature(edge)))
                except Exception as exc:
                    self.logs.append(f'helix edge signature failed: {exc}')
        if not candidates:
            return None

        selector = self._helix_edge_selector(helix)
        if selector is None:
            return None
        try:
            edge = _best_by_geometry(candidates, selector, 'helix path edge')
            return edge
        except Exception as exc:
            self.logs.append(f'helix geometric edge match failed: {exc}')
            return None

    def _sampled_helix_path(self, helix):
        params = dict(helix.get('params') or {})
        center = _v3(params.get('center') or (0.0, 0.0, 0.0))
        axis = _unit(params.get('dir') or params.get('axis') or (0.0, 0.0, 1.0))
        radius = abs(float(params.get('radius', 0.0)))
        pitch = abs(float(params.get('pitch', 0.0)))
        height = abs(float(params.get('height', 0.0)))
        if radius <= TOL or pitch <= TOL or height <= TOL:
            raise RuntimeError(f'Invalid helix path parameters: {params!r}')
        x_axis, y_axis = _plane_axes(axis)
        turns = height / pitch
        # Keep enough points for a stable sweep while bounding the size of
        # generated scripts for long, fine-pitch helices.
        samples = max(32, min(512, int(math.ceil(turns * 8.0)) + 1))
        points = []
        signed_height = height if _dot(axis, _unit(params.get('dir') or axis)) >= 0.0 else -height
        for index in range(samples):
            fraction = index / float(samples - 1)
            angle = 2.0 * math.pi * turns * fraction
            radial = _add(
                _mul(x_axis, radius * math.cos(angle)),
                _mul(y_axis, radius * math.sin(angle)),
            )
            points.append(_add(_add(center, radial), _mul(axis, signed_height * fraction)))
        degree = min(3, len(points) - 1)
        last_knot = len(points) - degree
        knots = [float(index) for index in range(last_knot + 1)]
        multiplicities = [degree + 1]
        multiplicities.extend([1] * max(0, len(knots) - 2))
        multiplicities.append(degree + 1)
        return {
            'kind': 'wire',
            'edges': [{
                'kind': 'edge',
                'type': 'spline',
                'controls': points,
                'degree': degree,
                'knots': knots,
                'multiplicities': multiplicities,
                'weights': [],
                'periodic': False,
            }],
        }

    def _helix_clearance_profile(self, profile, helix):
        params = dict(helix.get('params') or {})
        axis = _unit(params.get('dir') or params.get('axis') or (0.0, 0.0, 1.0))
        center = _v3(params.get('center') or (0.0, 0.0, 0.0))
        pitch = abs(float(params.get('pitch', 0.0)))
        points = self._profile_points(profile)
        if pitch <= TOL or len(points) < 2:
            return profile
        projections = [_dot(point, axis) for point in points]
        span = max(projections) - min(projections)
        if span < pitch * (1.0 - 1.0e-8):
            return profile
        factor = min(1.0, pitch * (1.0 - 1.0e-5) / span)
        if factor >= 1.0:
            return profile

        adjusted = json.loads(json.dumps(profile))
        anchor = _dot(center, axis)

        def adjust_point(point):
            point = _v3(point)
            axial = _dot(point, axis) - anchor
            return _add(point, _mul(axis, axial * (factor - 1.0)))

        for edge in self._profile_edges(adjusted):
            for key in ('start', 'middle', 'end', 'center'):
                if isinstance(edge.get(key), (list, tuple)):
                    edge[key] = adjust_point(edge[key])
            for key in ('controls', 'control_points', 'points'):
                if isinstance(edge.get(key), list):
                    edge[key] = [adjust_point(point) for point in edge[key]]
        self.logs.append(
            f'helix profile axial clearance applied: span={span:.9g} '
            f'pitch={pitch:.9g} factor={factor:.9g}'
        )
        return adjusted

    def _sweep_round_arc_fallback(self, profile, path, node_id):
        profile_edges = list(self._profile_edges(profile))
        path_edges = list(self._profile_edges(path))
        if len(profile_edges) != 1 or len(path_edges) != 1:
            return None
        profile_edge = profile_edges[0]
        arc = path_edges[0]
        if (
            profile_edge.get('type') != 'circle'
            or arc.get('type') != 'angle_arc'
        ):
            return None
        radius = abs(float(profile_edge.get('radius', 0.0)))
        major_radius = abs(float(arc.get('radius', 0.0)))
        if radius <= TOL or major_radius <= radius + TOL:
            return None
        start_angle = float(arc.get('start_angle', 0.0))
        end_angle = float(arc.get('end_angle', 0.0))
        span = (end_angle - start_angle) % (2.0 * math.pi)
        if span <= TOL:
            return None
        normal = _unit(arc.get('normal') or (0.0, 0.0, 1.0))
        center = _v3(arc.get('center'))
        start_point = _angle_arc_world_point(
            center,
            major_radius,
            start_angle,
            normal,
            arc.get('_kernel_x_axis'),
            arc.get('_kernel_y_axis'),
        )
        tangent = _unit(_cross(normal, _sub(start_point, center)))
        arc_profile = {
            'kind': 'face',
            'outer': {
                'kind': 'wire',
                'edges': [{
                    'kind': 'edge',
                    'type': 'circle',
                    'center': start_point,
                    'radius': radius,
                    'normal': tangent,
                }],
            },
            'inners': [],
            'normal': tangent,
        }
        body = self._revolve_profile(
            arc_profile,
            {
                'origin': center,
                'axis': normal,
                'angle': math.degrees(span),
            },
            f'{node_id}_arc_path',
        )
        self.logs.append(
            f'round single-arc sweep fallback used for {node_id}; '
            f'span={span:.9g}'
        )
        return body

    def _sweep_round_line_arc_fallback(self, profile, path, node_id):
        """Build a circular line-arc-line sweep from native cylinders and a revolve."""
        profile_edges = list(self._profile_edges(profile))
        path_edges = list(self._profile_edges(path))
        if len(profile_edges) != 1 or len(path_edges) != 3:
            return None
        profile_edge = profile_edges[0]
        if profile_edge.get('type') != 'circle':
            return None
        if [edge.get('type') for edge in path_edges] != [
            'line', 'angle_arc', 'line'
        ]:
            return None

        radius = abs(float(profile_edge.get('radius', 0.0)))
        arc = path_edges[1]
        major_radius = abs(float(arc.get('radius', 0.0)))
        if radius <= TOL or major_radius <= radius + TOL:
            return None
        normal = _unit(arc.get('normal') or (0.0, 0.0, 1.0))
        start_angle = float(arc.get('start_angle', 0.0))
        end_angle = float(arc.get('end_angle', 0.0))
        span = end_angle - start_angle
        if abs(span) <= TOL or abs(span) >= 2.0 * math.pi - TOL:
            return None
        start_point = _angle_arc_world_point(
            arc.get('center'), major_radius, start_angle, normal,
            arc.get('_kernel_x_axis'), arc.get('_kernel_y_axis')
        )
        end_point = _angle_arc_world_point(
            arc.get('center'), major_radius, end_angle, normal,
            arc.get('_kernel_x_axis'), arc.get('_kernel_y_axis')
        )
        first_line, last_line = path_edges[0], path_edges[2]
        join_tolerance = max(TOL, major_radius * 1.0e-7)
        if (
            _distance(first_line.get('end'), start_point) > join_tolerance
            or _distance(last_line.get('start'), end_point) > join_tolerance
        ):
            return None

        def line_body(index, line):
            start = _v3(line.get('start'))
            end = _v3(line.get('end'))
            vector = _sub(end, start)
            distance = _norm(vector)
            if distance <= TOL:
                return None
            line_profile = {
                'kind': 'face',
                'outer': {
                    'kind': 'wire',
                    'edges': [{
                        'kind': 'edge',
                        'type': 'circle',
                        'center': start,
                        'radius': radius,
                        'normal': _unit(vector),
                    }],
                },
                'inners': [],
                'normal': _unit(vector),
            }
            return self._extrude_profile(
                line_profile,
                {'direction': _unit(vector), 'distance': distance},
                f'{node_id}_segment_{index}',
            )

        radial = _sub(start_point, _v3(arc.get('center')))
        tangent = _unit(_cross(normal, radial))
        revolve_axis = normal
        if span < 0.0:
            tangent = _mul(tangent, -1.0)
            revolve_axis = _mul(normal, -1.0)
        first_vector = _sub(
            _v3(first_line.get('end')), _v3(first_line.get('start'))
        )
        last_vector = _sub(
            _v3(last_line.get('end')), _v3(last_line.get('start'))
        )
        if _norm(first_vector) <= TOL or _norm(last_vector) <= TOL:
            return None
        end_radial = _sub(end_point, _v3(arc.get('center')))
        end_tangent = _unit(_cross(normal, end_radial))
        if span < 0.0:
            end_tangent = _mul(end_tangent, -1.0)
        tangent_tolerance = 1.0e-7
        first_join_dot = _dot(_unit(first_vector), tangent)
        last_join_dot = _dot(end_tangent, _unit(last_vector))
        first_join_tangent = first_join_dot >= 1.0 - tangent_tolerance
        last_join_tangent = last_join_dot >= 1.0 - tangent_tolerance

        first_body = line_body(0, first_line)
        if first_body is None:
            return None
        bodies = [first_body]
        if first_join_tangent:
            arc_profile = {
                'kind': 'face',
                'outer': {
                    'kind': 'wire',
                    'edges': [{
                        'kind': 'edge',
                        'type': 'circle',
                        'center': start_point,
                        'radius': radius,
                        'normal': tangent,
                    }],
                },
                'inners': [],
                'normal': tangent,
            }
            arc_body = self._revolve_profile(
                arc_profile,
                {
                    'origin': _v3(arc.get('center')),
                    'axis': revolve_axis,
                    'angle': math.degrees(abs(span)),
                },
                f'{node_id}_arc',
            )
            bodies.append(arc_body)
            if last_join_tangent:
                last_body = line_body(2, last_line)
                if last_body is None:
                    return None
                bodies.append(last_body)
            else:
                self.logs.append(
                    f'round sweep {node_id} stopped solid propagation after '
                    f'non-tangent arc-line join; dot='
                    f'{last_join_dot:.9g}'
                )
        else:
            self.logs.append(
                f'round sweep {node_id} stopped solid propagation after '
                f'non-tangent line-arc join; dot='
                f'{first_join_dot:.9g}'
            )
        result = self._boolean_body(
            bodies[0], bodies[1:], SWBODYADD,
            f'SimpleCAD_{node_id}_round_path', clean=True,
        )
        self.logs.append(f'round line-arc-line sweep fallback used for {node_id}')
        return result

    def _sweep_profile(self, profile, path, params, node_id):
        self.logs.append(f'sweep native feature requested for {node_id}; using SolidWorks sweep fallback signatures')
        canonical_sweep = (
            self.canonical_sweep_descriptors.get(str(node_id)) or {}
        )
        sweep_candidate_diagnostics = []
        try:
            arc_fallback = self._sweep_round_arc_fallback(
                profile, path, node_id
            )
            if arc_fallback is not None:
                return arc_fallback
        except Exception as exc:
            self.logs.append(f'round arc sweep fallback failed for {node_id}: {exc}')
        try:
            round_fallback = self._sweep_round_line_arc_fallback(
                profile, path, node_id
            )
            if round_fallback is not None:
                return round_fallback
        except Exception as exc:
            self.logs.append(f'round sweep fallback failed for {node_id}: {exc}')
        helix_edge = self._single_helix_edge(path)
        frenet_helix_twist = None
        if helix_edge is not None:
            profile = self._helix_clearance_profile(profile, helix_edge)
            if bool(params.get('is_frenet')):
                helix_params = dict(helix_edge.get('params') or {})
                helix_pitch = abs(float(helix_params.get('pitch', 0.0)))
                helix_height = abs(float(helix_params.get('height', 0.0)))
                if helix_pitch > TOL and helix_height > TOL:
                    # _create_helix_path requests a clockwise SolidWorks
                    # helix.  Rotate the section by the same signed number of
                    # turns so its radial axis follows OCC's Frenet frame.
                    frenet_helix_twist = (
                        -2.0 * math.pi * helix_height / helix_pitch
                    )
        before = self._body_names()
        self._clear_selection()
        profile_sketch, _offset, _dominant, _normal, _profile_axis = self._create_profile_sketch(
            profile,
            self._profile_normal(profile),
            f'SimpleCADSketch_{node_id}_profile',
            use_profile_offset=True,
        )
        if helix_edge is not None:
            # Keep the native helix path as the first attempt. Some SolidWorks
            # versions accept the helix feature itself even when it does not
            # expose a selectable edge. The sampled path is a local fallback.
            path_sketch = self._create_helix_path(helix_edge, node_id)
            path_edge = self._helix_feature_edges(path_sketch, helix_edge)
            path_selection_kind = 'helix'
        else:
            path_edge = None
            try:
                path_sketch, _path_offset, _path_dominant, _path_normal, _path_axis = self._create_profile_sketch(
                    path,
                    self._profile_normal(path),
                    f'SimpleCADSketch_{node_id}_path',
                    use_profile_offset=True,
                )
                path_selection_kind = 'sketch'
            except RuntimeError as exc:
                if 'profile is not planar' not in str(exc):
                    raise
                path_sketch = self._create_3d_path_sketch(
                    path, f'SimpleCADSketch_{node_id}_3d_path'
                )
                path_selection_kind = '3d_sketch'
        feature = None
        successful_sweep_body = None
        successful_sweep_attempt = None
        attempt_states = []
        path_segments = (
            self._sketch_segments(path_sketch)
            if path_sketch is not None and helix_edge is None
            else []
        )
        if helix_edge is not None and path_edge is None:
            # The native helix is a construction feature in some SolidWorks
            # versions. Once it has been replaced by the sampled 3D sketch,
            # select that sketch's actual geometric segment, not the sketch
            # container, so the sweep API receives a path entity.
            path_segments = self._sketch_segments(path_sketch)
        for use_path_segments in (False, True):
            if use_path_segments and not path_segments:
                continue
            self._clear_selection()
            if profile_sketch is None or not self._select_entity(profile_sketch, append=False, mark=1):
                raise RuntimeError(f'Could not select the sweep profile for {node_id}')
            if use_path_segments:
                for segment in path_segments:
                    if not self._select_entity(segment, append=True, mark=4):
                        raise RuntimeError(f'Could not select a sweep path segment for {node_id}')
                if len(path_segments) > 1:
                    self._group_sweep_path_selection()
            elif (path_edge or path_sketch) is None or not self._select_entity(
                path_edge or path_sketch, append=True, mark=4
            ):
                raise RuntimeError(f'Could not select the sweep path for {node_id}')
            selection_state = self._selection_state()
            attempt_states.append({
                'path_selection': 'segments' if use_path_segments else path_selection_kind,
                'segment_count': len(path_segments),
                'selections': selection_state,
            })

            def create_sweep_from_definition(
                twist_control, twist_angle=None
            ):
                definition = self.model.FeatureManager.CreateDefinition(
                    SW_FM_SWEEP
                )
                if definition is None:
                    return None
                definition.Profile = profile_sketch
                definition.Path = path_edge or path_sketch
                definition.TwistControlType = int(twist_control)
                definition.PathAlignmentType = 0
                definition.AlignWithEndFaces = False
                definition.Merge = False
                if twist_angle is not None:
                    # SetTwistAngle is a COM Sub (void), not a Boolean method.
                    definition.SetTwistAngle(float(twist_angle))
                return self.model.FeatureManager.CreateFeature(definition)

            attempts = (
                *(
                    (
                        (
                            'feature_data_normal_constant_twist',
                            lambda: create_sweep_from_definition(
                                SW_TWIST_CONTROL_NORMAL_CONSTANT_TWIST,
                                frenet_helix_twist,
                            ),
                        ),
                        (
                            'feature_data_normal_constant_reverse_twist',
                            lambda: create_sweep_from_definition(
                                SW_TWIST_CONTROL_NORMAL_CONSTANT_TWIST,
                                -frenet_helix_twist,
                            ),
                        ),
                        (
                            'feature_data_constant_twist',
                            lambda: create_sweep_from_definition(
                                8, frenet_helix_twist
                            ),
                        ),
                        (
                            'feature_data_constant_reverse_twist',
                            lambda: create_sweep_from_definition(
                                8, -frenet_helix_twist
                            ),
                        ),
                        (
                            'feature_data_follow_path',
                            lambda: create_sweep_from_definition(0),
                        ),
                        (
                            'feature_data_keep_normal_constant',
                            lambda: create_sweep_from_definition(1),
                        ),
                        (
                            'legacy_normal_constant_twist',
                            lambda: self.model.FeatureManager.InsertProtrusionSwept4(
                                False, False,
                                SW_TWIST_CONTROL_NORMAL_CONSTANT_TWIST,
                                False, False, 0, 0, False,
                                0.0, 0.0, 0, 0,
                                False, False, True,
                                frenet_helix_twist,
                                True, False, 0.0, 0,
                            ),
                        ),
                    )
                    if frenet_helix_twist is not None
                    else ()
                ),
                # Graph operations are functional and create an independent body.
                # Asking SolidWorks to merge here makes the result depend on unrelated
                # intermediate bodies already present in the document.
                (
                    'legacy_follow_path_independent',
                    lambda: self.model.FeatureManager.InsertProtrusionSwept4(False, False, 0, False, False, 0, 0, False, 0.0, 0.0, 0.0, 0, False, False, True, 0, True, False, 0.0, 0),
                ),
                # Documented SolidWorks multi-path sweep settings retained as
                # compatibility fallbacks after the independent-body attempt.
                (
                    'legacy_follow_path_merge_scope',
                    lambda: self.model.FeatureManager.InsertProtrusionSwept4(False, False, 0, False, False, 0, 0, False, 0.0, 0.0, 0.0, 0, True, True, True, 0.0, True, False, 0.0, 0),
                ),
                (
                    'legacy_swept2_independent',
                    lambda: self.model.FeatureManager.InsertProtrusionSwept2(False, False, 0, False, False, 0, 0, False, 0.0, 0.0, 0.0, 0, False, False, True),
                ),
                (
                    'legacy_swept2_merge_scope',
                    lambda: self.model.FeatureManager.InsertProtrusionSwept2(False, False, 0, False, False, 0, 0, False, 0.0, 0.0, 0.0, 0, True, True, True),
                ),
            )
            for attempt_name, attempt in attempts:
                try:
                    candidate_feature = attempt()
                    if candidate_feature is not None:
                        candidate_body = self._capture_new_body(
                            before, candidate_feature
                        )
                        candidate_volume = self._body_volume(candidate_body)
                        candidate_bbox = self._box_from_entity(candidate_body)
                        candidate_matches = (
                            not canonical_sweep
                            or self._body_matches_canonical(
                                candidate_body, canonical_sweep
                            )
                        )
                        sweep_candidate_diagnostics.append({
                            'attempt': attempt_name,
                            'volume': candidate_volume,
                            'bbox': candidate_bbox,
                            'matches': candidate_matches,
                        })
                        if not candidate_matches:
                            self.logs.append(
                                f'sweep {node_id} rejected {attempt_name}; '
                                f'volume={candidate_volume!r} '
                                f'bbox={candidate_bbox!r}; '
                                f'canonical={canonical_sweep!r}'
                            )
                            continue
                        feature = candidate_feature
                        successful_sweep_body = candidate_body
                        successful_sweep_attempt = attempt_name
                        break
                except Exception as exc:
                    self.logs.append(f'sweep attempt failed for {node_id}: {exc}')
            if feature is None:
                try:
                    temp_body = self._create_swept_temp_body((
                        False, False, 0,
                        False, False, 0, 0,
                        False, 0.0, 0.0, 0,
                        0, 0.0, True,
                    ))
                    if temp_body is not None:
                        temp_matches = (
                            not canonical_sweep
                            or self._body_matches_canonical(
                                temp_body, canonical_sweep
                            )
                        )
                        sweep_candidate_diagnostics.append({
                            'attempt': 'temporary_swept_body',
                            'volume': self._body_volume(temp_body),
                            'bbox': self._box_from_entity(temp_body),
                            'matches': temp_matches,
                        })
                        if not temp_matches:
                            self.logs.append(
                                f'sweep {node_id} rejected temporary body; '
                                f'canonical={canonical_sweep!r}'
                            )
                            continue
                        return self._create_feature_from_body(
                            temp_body, f'SimpleCAD_{node_id}_sweep'
                        )
                except Exception as exc:
                    self.logs.append(
                        f'temporary sweep body attempt failed for {node_id}: {exc}'
                    )
            if feature is not None:
                break
        if feature is None and helix_edge is not None:
            self.logs.append(
                f'native helix sweep failed for {node_id}; using a '
                'geometry-generated 3D B-spline path'
            )
            path_sketch = self._create_3d_path_sketch(
                self._sampled_helix_path(helix_edge),
                f'SimpleCADSketch_{node_id}_sampled_helix',
            )
            path_edge = None
            path_selection_kind = 'sampled_helix'
            path_segments = self._sketch_segments(path_sketch)
            for use_path_segments in (False, True):
                if use_path_segments and not path_segments:
                    continue
                self._clear_selection()
                if profile_sketch is None or not self._select_entity(profile_sketch, append=False, mark=1):
                    raise RuntimeError(f'Could not select the sweep profile for {node_id}')
                if use_path_segments:
                    for segment in path_segments:
                        if not self._select_entity(segment, append=True, mark=4):
                            raise RuntimeError(f'Could not select a sweep path segment for {node_id}')
                    if len(path_segments) > 1:
                        self._group_sweep_path_selection()
                elif not self._select_entity(path_sketch, append=True, mark=4):
                    raise RuntimeError(f'Could not select the sampled sweep path for {node_id}')
                selection_state = self._selection_state()
                attempt_states.append({
                    'path_selection': 'segments' if use_path_segments else path_selection_kind,
                    'segment_count': len(path_segments),
                    'selections': selection_state,
                })
                feature = None
                for attempt_name, attempt in (
                    *(
                        (
                            (
                                'sampled_normal_constant_twist',
                                lambda: self.model.FeatureManager.InsertProtrusionSwept4(
                                    False, False,
                                    SW_TWIST_CONTROL_NORMAL_CONSTANT_TWIST,
                                    False, False, 0, 0, False,
                                    0.0, 0.0, 0, 0,
                                    False, False, True,
                                    frenet_helix_twist,
                                    True, False, 0.0, 0,
                                ),
                            ),
                        )
                        if frenet_helix_twist is not None
                        else ()
                    ),
                    (
                        'sampled_follow_path_independent',
                        lambda: self.model.FeatureManager.InsertProtrusionSwept4(
                            False, False, 0, False, False, 0, 0, False,
                            0.0, 0.0, 0, 0, False, False, True, 0.0, True,
                            False, 0.0, 0,
                        ),
                    ),
                    (
                        'sampled_follow_path_merge_scope',
                        lambda: self.model.FeatureManager.InsertProtrusionSwept4(
                            False, False, 0, False, False, 0, 0, False,
                            0.0, 0.0, 0, 0, True, True, True, 0.0, True,
                            False, 0.0, 0,
                        ),
                    ),
                ):
                    try:
                        feature = attempt()
                        if feature is not None:
                            successful_sweep_attempt = attempt_name
                            break
                    except Exception as exc:
                        self.logs.append(
                            f'sampled sweep attempt failed for {node_id}: {exc}'
                        )
                if feature is None:
                    try:
                        temp_body = self._create_swept_temp_body((
                            False, False, 0,
                            False, False, 0, 0,
                            False, 0.0, 0.0, 0,
                            0, 0.0, True,
                        ))
                        if temp_body is not None:
                            temp_matches = (
                                not canonical_sweep
                                or self._body_matches_canonical(
                                    temp_body, canonical_sweep
                                )
                            )
                            sweep_candidate_diagnostics.append({
                                'attempt': 'temporary_sampled_swept_body',
                                'volume': self._body_volume(temp_body),
                                'bbox': self._box_from_entity(temp_body),
                                'matches': temp_matches,
                            })
                            if not temp_matches:
                                self.logs.append(
                                    f'sweep {node_id} rejected temporary '
                                    f'sampled body; canonical='
                                    f'{canonical_sweep!r}'
                                )
                                continue
                            return self._create_feature_from_body(
                                temp_body, f'SimpleCAD_{node_id}_sweep'
                            )
                    except Exception as exc:
                        self.logs.append(
                            f'temporary sampled sweep body attempt failed for {node_id}: {exc}'
                        )
                if feature is not None:
                    break
        if feature is None:
            raise SimpleCADUnsupportedOpError(
                f'SolidWorks sweep feature creation failed; attempts={attempt_states!r}; '
                f'logs={self.logs[-3:]!r}'
            )
        body = successful_sweep_body or self._capture_new_body(before, feature)
        if canonical_sweep and not self._body_matches_canonical(
            body, canonical_sweep
        ):
            raise RuntimeError(
                f'SolidWorks sweep {node_id} differs from canonical result; '
                f'actual_volume={self._body_volume(body)!r}; '
                f'actual_bbox={self._box_from_entity(body)!r}; '
                f'canonical={canonical_sweep!r}; '
                f'candidates={sweep_candidate_diagnostics!r}'
            )
        self.logs.append(
            f'sweep {node_id} created by {successful_sweep_attempt or "unknown"}; '
            f'volume={self._body_volume(body)!r}; '
            f'bbox={self._box_from_entity(body)!r}'
        )
        return body

    def _copy_temp_body(self, body):
        # Prefer the caller's resolved proxy. A same-name body enumerated from
        # the document can refer to a different feature after chained fillets;
        # use fresh-name/bbox candidates only as fallbacks.
        bodies = [body]
        expected_name = self._body_name(body)
        expected_bbox = self._box_from_entity(body)
        expected_size = _distance(expected_bbox['min'], expected_bbox['max'])
        fresh_bodies = self._solid_bodies()
        same_name = [
            candidate for candidate in fresh_bodies
            if self._body_name(candidate) == expected_name
        ]
        bodies.extend(
            candidate for candidate in same_name
            if candidate is not body
        )
        if not same_name and expected_size > 1.0e-12 and fresh_bodies:
            best_body = min(
                fresh_bodies,
                key=lambda candidate: _bbox_score(
                    self._box_from_entity(candidate), expected_bbox
                ),
            )
            best_score = _bbox_score(
                self._box_from_entity(best_body), expected_bbox
            )
            if best_score <= max(1.0e-7, expected_size * 1.0e-7):
                bodies.append(best_body)
        try:
            typed_body = win32com.client.CastTo(body, 'IBody2')
            if typed_body is not None:
                bodies.append(typed_body)
        except Exception:
            pass

        errors = []
        for candidate in bodies:
            calls = (
                ('Copy', lambda candidate=candidate: candidate.Copy()),
                ('ICopy', lambda candidate=candidate: candidate.ICopy()),
                ('Copy2', lambda candidate=candidate: candidate.Copy2(False)),
                (
                    'DISPID 19',
                    lambda candidate=candidate: candidate._oleobj_.InvokeTypes(
                        19,
                        0,
                        pythoncom.DISPATCH_METHOD,
                        (pythoncom.VT_DISPATCH, 0),
                        (),
                    ),
                ),
                (
                    'DISPID 31',
                    lambda candidate=candidate: candidate._oleobj_.InvokeTypes(
                        31,
                        0,
                        pythoncom.DISPATCH_METHOD,
                        (pythoncom.VT_DISPATCH, 0),
                        (),
                    ),
                ),
            )
            for call_name, call in calls:
                try:
                    copied = call()
                    if copied is not None:
                        try:
                            return win32com.client.Dispatch(copied)
                        except Exception:
                            return copied
                    errors.append(f'{call_name}: returned None')
                except Exception as exc:
                    errors.append(f'{call_name}: {exc}')
        fresh_state = [
            (self._body_name(candidate), self._box_from_entity(candidate))
            for candidate in fresh_bodies
        ]
        self.logs.append(
            f'body copy attempts failed: expected_name={expected_name!r} '
            f'expected_bbox={expected_bbox!r} fresh={fresh_state!r} '
            f'attempts={errors!r}'
        )
        raise RuntimeError(
            f'Could not copy SolidWorks body; expected_name={expected_name!r}; '
            f'expected_bbox={expected_bbox!r}; fresh={fresh_state!r}; '
            f'attempts={errors!r}'
        )

    def _create_feature_from_body(self, temp_body, name):
        before = self._body_names()
        expected_bbox = self._box_from_entity(temp_body)
        feature = None
        for call in (
            lambda: self.model.CreateFeatureFromBody3(temp_body, False, 0),
            lambda: self.model.CreateFeatureFromBody3(temp_body, True, 0),
            lambda: self.model.CreateFeatureFromBody2(temp_body, False, 0),
            lambda: self.model.CreateFeatureFromBody(temp_body),
        ):
            try:
                feature = call()
                if feature is not None:
                    break
            except Exception:
                pass
        if feature is None:
            raise RuntimeError('SolidWorks CreateFeatureFromBody failed')
        try:
            feature.Name = str(name)
        except Exception:
            pass
        return self._capture_new_body(
            before, feature, expected_bbox=expected_bbox
        )

    def _apply_transform_to_temp_body(self, temp_body, matrix_data):
        transform = None
        try:
            # Late-bound pywin32 exposes this no-argument COM getter as a
            # property whose value is the MathUtility dispatch object. Its
            # CreateTransform method is not exposed through dynamic dispatch in
            # SolidWorks 2025, so invoke the type-library DISPID explicitly.
            math_utility = self.sw.GetMathUtility
            array_data = win32com.client.VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8,
                [float(value) for value in matrix_data],
            )
            raw_transform = math_utility._oleobj_.InvokeTypes(
                1,
                0,
                pythoncom.DISPATCH_METHOD,
                (pythoncom.VT_DISPATCH, 0),
                ((pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),),
                array_data,
            )
            if raw_transform is not None:
                transform = win32com.client.Dispatch(raw_transform)
        except Exception:
            transform = None
        if transform is None:
            raise RuntimeError('Could not create SolidWorks MathTransform')
        for call in (
            lambda: temp_body.ApplyTransform(transform),
            lambda: temp_body.Transform2(transform),
        ):
            try:
                result = call()
                if result is None or bool(result):
                    return temp_body
            except Exception:
                pass
        raise RuntimeError('Could not transform SolidWorks body')

    def _transform_body_feature(self, body, matrix_data, name):
        if _is_identity_matrix(matrix_data):
            before = self._body_names()
            expected_bbox = self._box_from_entity(body)
            self._clear_selection()
            if self._select_solid_body(body, append=False, mark=1):
                feature = None
                for call in (
                    lambda: self.model.FeatureManager.InsertMoveCopyBody2(
                        0.0, 0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0,
                        True, 1,
                    ),
                    lambda: self.model.FeatureManager.InsertMoveCopyBody(
                        0.0, 0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0,
                        True, 1,
                    ),
                ):
                    try:
                        feature = call()
                        if feature is not None:
                            break
                    except Exception as exc:
                        self.logs.append(
                            f'native body-copy attempt failed for {name}: {exc}'
                        )
                self._clear_selection()
                if feature is not None:
                    try:
                        feature.Name = str(name)
                    except Exception:
                        pass
                    return self._capture_new_body(
                        before, feature, expected_bbox=expected_bbox
                    )
        # A pure translation can be represented by SolidWorks' native
        # Move/Copy Body feature. Prefer this live feature over the temporary
        # BRep/CreateFeatureFromBody fallback so upstream edits propagate
        # through translated leaves after the document is reopened.
        if _is_translation_matrix(matrix_data):
            before = self._body_names()
            expected_bbox = self._box_from_entity(body)
            self._clear_selection()
            if self._select_solid_body(body, append=False, mark=1):
                tx, ty, tz = (float(matrix_data[index]) for index in (9, 10, 11))
                canonical_delta = tuple(
                    value * M_TO_MM / MODEL_SCALE
                    for value in (tx, ty, tz)
                )
                if isinstance(expected_bbox, dict):
                    expected_bbox = {
                        key: tuple(
                            float(point[index]) + canonical_delta[index]
                            for index in range(3)
                        )
                        for key, point in expected_bbox.items()
                    }
                distance = math.sqrt(tx * tx + ty * ty + tz * tz)
                if distance <= 1.0e-15:
                    direction = (1.0, 0.0, 0.0)
                else:
                    direction = (
                        tx / distance, ty / distance, tz / distance
                    )
                native_feature = None
                for call in (
                    # SolidWorks' own Move Bodies example passes the XYZ
                    # displacement directly and leaves TransDist at zero.
                    # Graph transforms are functional and may feed multiple
                    # branches, so always copy the live input body here. A
                    # native move would consume it and force later branches
                    # onto static Body2 snapshots.
                    lambda: self.model.FeatureManager.InsertMoveCopyBody2(
                        tx, ty, tz, 0.0,
                        0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0, True, 1,
                    ),
                    lambda: self.model.FeatureManager.InsertMoveCopyBody(
                        tx, ty, tz, 0.0,
                        0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0, True, 1,
                    ),
                    lambda: self.model.FeatureManager.InsertMoveCopyBody2(
                        direction[0], direction[1], direction[2], distance,
                        0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0, True, 1,
                    ),
                    lambda: self.model.FeatureManager.InsertMoveCopyBody(
                        direction[0], direction[1], direction[2], distance,
                        0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0, True, 1,
                    ),
                ):
                    try:
                        native_feature = call()
                        if native_feature is not None:
                            break
                    except Exception as exc:
                        self.logs.append(
                            f'native translated body attempt failed for {name}: {exc}'
                        )
                self._clear_selection()
                if native_feature is not None:
                    try:
                        native_feature.Name = str(name)
                    except Exception:
                        pass
                    self.logs.append(f'{name} uses native Move/Copy Body translation')
                    return self._capture_new_body(
                        before, native_feature, expected_bbox=expected_bbox
                    )
                self.logs.append(
                    f'native Move/Copy Body returned no feature for {name}; '
                    f'selection={self._selection_state()!r}; '
                    'falling back to static transform'
                )
            else:
                self.logs.append(
                    f'native translated body selection failed for {name}; '
                    'falling back to static transform'
                )
        else:
            self.logs.append(
                f'{name} transform is not a pure translation; using static fallback'
            )
        temp_body = self._copy_temp_body(body)
        self._apply_transform_to_temp_body(temp_body, matrix_data)
        self._mark_degraded(name, 'static_transform')
        return self._create_feature_from_body(temp_body, name)

    def _rotate_body_feature(self, body, axis, angle_degrees, origin, name):
        axis = _unit(axis)
        matrix_data = _rotation_matrix(axis, angle_degrees, origin)
        principal_index = None
        principal_sign = 1.0
        for index in range(3):
            if (
                abs(abs(axis[index]) - 1.0) <= 1.0e-10
                and all(abs(axis[other]) <= 1.0e-10 for other in range(3) if other != index)
            ):
                principal_index = index
                principal_sign = 1.0 if axis[index] >= 0.0 else -1.0
                break
        if principal_index is None:
            self.logs.append(
                f'{name} rotation axis is not principal; using static fallback'
            )
            return self._transform_body_feature(body, matrix_data, name)

        expected_probe = self._copy_temp_body(body)
        self._apply_transform_to_temp_body(expected_probe, matrix_data)
        expected_bbox = self._box_from_entity(expected_probe)
        before = self._body_names()
        self._clear_selection()
        if self._select_solid_body(body, append=False, mark=1):
            rotation_point = _pt_m(origin)
            rotation_angles = [0.0, 0.0, 0.0]
            # The late-bound SolidWorks COM call exposes the three rotation
            # values in Z/Y/X axis order on this API version. A direct probe
            # with a non-symmetric body verifies that argument 0 rotates about
            # world Z and argument 2 about world X.
            rotation_angles[
                _solidworks_rotation_angle_index(principal_index)
            ] = (
                math.radians(float(angle_degrees)) * principal_sign
            )
            feature = None
            for call in (
                lambda: self.model.FeatureManager.InsertMoveCopyBody2(
                    0.0, 0.0, 0.0, 0.0,
                    rotation_point[0], rotation_point[1], rotation_point[2],
                    rotation_angles[0], rotation_angles[1], rotation_angles[2],
                    True, 1,
                ),
                lambda: self.model.FeatureManager.InsertMoveCopyBody(
                    0.0, 0.0, 0.0, 0.0,
                    rotation_point[0], rotation_point[1], rotation_point[2],
                    rotation_angles[0], rotation_angles[1], rotation_angles[2],
                    True, 1,
                ),
            ):
                try:
                    feature = call()
                    if feature is not None:
                        break
                except Exception as exc:
                    self.logs.append(
                        f'native rotated body attempt failed for {name}: {exc}'
                    )
            self._clear_selection()
            if feature is not None:
                try:
                    feature.Name = str(name)
                except Exception:
                    pass
                self.logs.append(f'{name} uses native Move/Copy Body rotation')
                return self._capture_new_body(
                    before, feature, expected_bbox=expected_bbox
                )
        self.logs.append(
            f'native Move/Copy Body rotation failed for {name}; '
            'using static fallback'
        )
        temp_body = self._copy_temp_body(body)
        self._apply_transform_to_temp_body(temp_body, matrix_data)
        self._mark_degraded(name, 'static_transform')
        return self._create_feature_from_body(temp_body, name)

    def _boolean_result_body(self, value, name):
        if hasattr(value, 'GetFaces'):
            return value
        if isinstance(value, (list, tuple)):
            values = list(value)
        else:
            try:
                values = list(value)
            except Exception:
                values = []
        bodies = [body for body in values if hasattr(body, 'GetFaces')]
        if len(bodies) != 1:
            raise RuntimeError(
                f'SolidWorks body boolean for {name} returned {len(bodies)} solid sections; expected one'
            )
        return bodies[0]

    def _boolean_result_bodies(self, value):
        if hasattr(value, 'GetFaces'):
            return [value]
        if isinstance(value, (list, tuple)):
            values = list(value)
        else:
            try:
                values = list(value)
            except Exception:
                values = []
        return [body for body in values if hasattr(body, 'GetFaces')]

    def _body_intersection_has_volume(self, left, right):
        left_bbox = self._box_from_entity(left)
        right_bbox = self._box_from_entity(right)
        if not _bbox_intersects(left_bbox, right_bbox, tolerance=1.0e-9):
            return False
        try:
            working_left = self._copy_temp_body(left)
            working_right = self._copy_temp_body(right)
            response = working_left.Operations2(
                SWBODYINTERSECT, working_right
            )
            if (
                isinstance(response, tuple)
                and len(response) == 2
                and isinstance(response[1], int)
            ):
                result, error_code = response
            else:
                result, error_code = response, 0
            intersections = self._boolean_result_bodies(result)
            if not intersections:
                return False
            common_volume = sum(
                max(0.0, float(self._body_volume(body) or 0.0))
                for body in intersections
            )
            operand_volumes = [
                max(0.0, float(self._body_volume(body) or 0.0))
                for body in (left, right)
            ]
            tolerance = max(
                1.0e-18,
                min(operand_volumes) * 1.0e-10
                if all(operand_volumes) else 1.0e-18,
            )
            return common_volume > tolerance
        except Exception as exc:
            raise RuntimeError(
                'Could not determine exact SolidWorks body intersection for '
                f'multi-section Cut; left_bbox={left_bbox!r}; '
                f'right_bbox={right_bbox!r}: {exc}'
            ) from exc

    def _body_union_is_single(self, left, right):
        left_bbox = self._box_from_entity(left)
        right_bbox = self._box_from_entity(right)
        if not _bbox_intersects(left_bbox, right_bbox, tolerance=1.0e-9):
            return False
        try:
            working_left = self._copy_temp_body(left)
            working_right = self._copy_temp_body(right)
            response = working_left.Operations2(SWBODYADD, working_right)
            if (
                isinstance(response, tuple)
                and len(response) == 2
                and isinstance(response[1], int)
            ):
                result, error_code = response
            else:
                result, error_code = response, 0
            result_bodies = self._boolean_result_bodies(result)
            if len(result_bodies) == 1:
                return True
            if len(result_bodies) > 1:
                return False
            raise RuntimeError(
                f'Operations2 returned no solid section; error={error_code}'
            )
        except Exception as exc:
            raise RuntimeError(
                'Could not determine exact SolidWorks body connectivity for '
                f'Union; left_bbox={left_bbox!r}; '
                f'right_bbox={right_bbox!r}: {exc}'
            ) from exc

    def _boolean_body(
        self,
        base,
        tools,
        op_code,
        name,
        *,
        skip_non_intersecting=False,
        clean=False,
        canonical_result=None,
        allow_split_sections=False,
        prefer_native=False,
    ):
        if not tools:
            return base
        native_fallback_base = None
        native_fallback_tools = None
        if prefer_native:
            try:
                # InsertCombineFeature may consume or invalidate its selected
                # bodies even when canonical validation rejects the result.
                # Keep explicit static fallback bodies before that attempt so
                # a failed native probe cannot force source-kernel fallback.
                # Tool bodies must be copied as well as the base: SolidWorks
                # invalidates every selected operand when a native Combine is
                # created, even if canonical validation rejects its result.
                native_fallback_base = self._copy_temp_body(base)
                native_fallback_tools = [
                    self._copy_temp_body(tool) for tool in tools
                ]
                # Native Combine consumes every selected operand. Feed it
                # native BCopy=True identity features so the graph remains
                # functional when an operand also has another downstream
                # consumer. Move/Copy Body retains the upstream parametric
                # dependency; a temporary Body2 copy would not.
                degraded_before = len(self.degraded_features)
                live_base = self._transform_body_feature(
                    base, _identity_matrix(), f'{name}_operand_base'
                )
                live_tools = [
                    self._transform_body_feature(
                        tool,
                        _identity_matrix(),
                        f'{name}_operand_tool_{index + 1}',
                    )
                    for index, tool in enumerate(tools)
                ]
                if len(self.degraded_features) != degraded_before:
                    raise RuntimeError(
                        'native Boolean operand copy degraded to a static body'
                    )
                native_result = self._native_combine_body(
                    live_base, live_tools, op_code, name,
                    prefer_live_base=True,
                )
                if (
                    isinstance(canonical_result, dict)
                    and not self._body_matches_canonical(
                        native_result, canonical_result
                    )
                    and not (
                        op_code == SWBODYCUT
                        and self._cut_tolerance_artifact_matches_canonical(
                            native_result, canonical_result
                        )
                    )
                ):
                    # Feature.GetBody/GetFaces can expose an edit-state proxy
                    # after Combine consumes its operands. Rebind to the
                    # unique persistent document body only when its strict
                    # canonical descriptor proves that it is the result.
                    persistent_matches = [
                        candidate
                        for candidate in self._solid_bodies()
                        if self._body_matches_canonical(
                            candidate, canonical_result
                        )
                    ]
                    if len(persistent_matches) == 1:
                        native_result = persistent_matches[0]
                        self.logs.append(
                            f'boolean {name} rebound native Combine to the '
                            'unique persistent canonical result body'
                        )
                    else:
                        actual_descriptor = {
                            'bbox': self._box_from_entity(native_result),
                            'volume': self._body_volume(native_result),
                        }
                        raise RuntimeError(
                            'native Combine result did not match canonical '
                            f'bbox/volume; actual={actual_descriptor!r}; '
                            f'canonical={canonical_result!r}; '
                            f'persistent_matches={len(persistent_matches)}'
                        )
                self.logs.append(f'boolean {name} used live native Combine')
                return native_result
            except Exception as exc:
                self.logs.append(
                    f'live native Combine failed for {name}; using static '
                    f'body fallback: {exc}'
                )
                self._mark_degraded(name, 'static_boolean')
        # Operation-graph nodes are functional: a boolean result must not consume
        # source bodies that can feed other graph branches. Work only on copies.
        result = native_fallback_base or self._copy_temp_body(base)
        pending = list(native_fallback_tools or tools)
        applied_steps = []
        while pending:
            if op_code == SWBODYADD:
                result_bbox = self._box_from_entity(result)
                pending_boxes = [self._box_from_entity(candidate) for candidate in pending]
                candidate_indices = sorted(
                    range(len(pending)),
                    key=lambda index: (
                        not _bbox_intersects(
                            result_bbox,
                            pending_boxes[index],
                            tolerance=1.0e-5,
                        ),
                        _norm(_bbox_axis_gaps(result_bbox, pending_boxes[index])),
                        index,
                    ),
                )
            elif op_code == SWBODYCUT:
                # Set subtraction is independent of tool order. SolidWorks can
                # reject one copied tool with 547 while accepting another tool
                # first; try every pending cutter before escalating to Combine.
                candidate_indices = list(range(len(pending)))
            else:
                candidate_indices = [0]

            attempts = []
            for candidate_index in candidate_indices:
                tool = pending[candidate_index]
                boolean_result = None
                error_code = 0
                for reset_tolerances in (False, True):
                    if reset_tolerances and error_code != 547:
                        break
                    # Operations2 invalidates both input temporary bodies. Always
                    # start an attempt from fresh copies so a failed boolean cannot
                    # corrupt this graph branch or a later retry.
                    working_result = self._copy_temp_body(result)
                    temp_tool = self._copy_temp_body(tool)
                    if reset_tolerances:
                        try:
                            working_result.ResetEdgeTolerances()
                            temp_tool.ResetEdgeTolerances()
                        except Exception as exc:
                            self.logs.append(
                                f'edge tolerance reset failed for {name}: {exc}'
                            )
                    error_code = 0
                    try:
                        response = working_result.Operations2(op_code, temp_tool)
                        if (
                            isinstance(response, tuple)
                            and len(response) == 2
                            and isinstance(response[1], int)
                        ):
                            boolean_result, error_code = response
                        else:
                            boolean_result = response
                    except Exception as exc:
                        self.logs.append(f'Operations2 attempt failed for {name}: {exc}')
                    if not boolean_result:
                        try:
                            # Do not cap this at one section: a disjoint union returns
                            # two bodies, which must be rejected rather than truncated.
                            # Operations2 invalidates its inputs even when it returns an
                            # error code, so the legacy fallback needs fresh copies.
                            legacy_result = self._copy_temp_body(result)
                            legacy_tool = self._copy_temp_body(tool)
                            boolean_result = legacy_result.Operations(
                                op_code, legacy_tool, 1024
                            )
                            if boolean_result:
                                self.logs.append(
                                    f'boolean {name} recovered with legacy body '
                                    f'operation after Operations2 error {error_code}'
                                )
                        except Exception as legacy_exc:
                            self.logs.append(
                                f'legacy body operation attempt failed for {name}: {legacy_exc}'
                            )
                    if boolean_result:
                        break
                if (
                    not boolean_result
                    and op_code == SWBODYCUT
                    and error_code == 547
                ):
                    tool_bbox = self._box_from_entity(tool)
                    for clearance_factor in (
                        1.0 - 1.0e-6,
                        1.0 + 1.0e-6,
                        1.0 - 1.0e-5,
                        1.0 + 1.0e-5,
                        1.0 - 1.0e-4,
                        1.0 + 1.0e-4,
                    ):
                        working_result = self._copy_temp_body(result)
                        temp_tool = self._copy_temp_body(tool)
                        try:
                            self._apply_transform_to_temp_body(
                                temp_tool,
                                _scale_about_bbox_matrix(
                                    tool_bbox, clearance_factor
                                ),
                            )
                            response = working_result.Operations2(
                                op_code, temp_tool
                            )
                            if (
                                isinstance(response, tuple)
                                and len(response) == 2
                                and isinstance(response[1], int)
                            ):
                                boolean_result, error_code = response
                            else:
                                boolean_result = response
                                error_code = 0
                        except Exception as exc:
                            self.logs.append(
                                f'cut clearance attempt failed for {name}; '
                                f'factor={clearance_factor:.9g}: {exc}'
                            )
                            boolean_result = None
                        if boolean_result:
                            self.logs.append(
                                f'cut {name} recovered error 547 with tool '
                                f'clearance factor {clearance_factor:.9g}'
                            )
                            break
                if boolean_result:
                    candidate_bodies = self._boolean_result_bodies(boolean_result)
                    if len(candidate_bodies) > 1:
                        if (
                            op_code == SWBODYCUT
                            and len(pending) > 1
                            and (
                                allow_split_sections
                                or isinstance(canonical_result, dict)
                            )
                        ):
                            remaining_tools = [
                                candidate
                                for index, candidate in enumerate(pending)
                                if index != candidate_index
                            ]
                            split_results = []
                            for section_index, section in enumerate(candidate_bodies):
                                section_result = self._boolean_body(
                                    section,
                                    remaining_tools,
                                    op_code,
                                    f'{name}_section_{section_index + 1}',
                                    skip_non_intersecting=True,
                                    clean=clean,
                                    canonical_result=None,
                                    allow_split_sections=True,
                                )
                                if isinstance(section_result, list):
                                    split_results.extend(section_result)
                                else:
                                    split_results.append(section_result)
                            if isinstance(canonical_result, dict):
                                canonical_matches = [
                                    body
                                    for body in split_results
                                    if self._body_matches_canonical(
                                        body, canonical_result
                                    )
                                ]
                                if len(canonical_matches) == 1:
                                    self.logs.append(
                                        f'cut {name} selected the unique canonical '
                                        f'section after all tools from '
                                        f'{len(split_results)} SolidWorks sections'
                                    )
                                    return canonical_matches
                                if not self._body_set_matches_canonical(
                                    split_results, canonical_result
                                ):
                                    actual_sections = [
                                        {
                                            'bbox': self._box_from_entity(body),
                                            'volume': self._body_volume(body),
                                        }
                                        for body in split_results
                                    ]
                                    raise RuntimeError(
                                        f'SolidWorks split cut for {name} did not '
                                        f'match the canonical result descriptor; '
                                        f'canonical={canonical_result!r}; '
                                        f'sections={actual_sections!r}'
                                    )
                                self.logs.append(
                                    f'cut {name} preserved {len(split_results)} '
                                    'SolidWorks sections matching one canonical Solid'
                                )
                            return split_results
                        canonical_match = None
                        canonical_match_score = None
                        expected_bbox = (
                            canonical_result.get('bbox')
                            if isinstance(canonical_result, dict)
                            else None
                        )
                        if (
                            op_code == SWBODYCUT
                            and len(pending) == 1
                            and isinstance(expected_bbox, dict)
                        ):
                            expected_size = _distance(
                                expected_bbox.get('min'), expected_bbox.get('max')
                            )
                            tolerance = max(1.0e-7, expected_size * 1.0e-7)
                            ranked_sections = sorted(
                                (
                                    _bbox_score(
                                        self._box_from_entity(body), expected_bbox
                                    ),
                                    index,
                                    body,
                                )
                                for index, body in enumerate(candidate_bodies)
                            )
                            matching_sections = [
                                section
                                for section in ranked_sections
                                if section[0] <= tolerance
                            ]
                            if len(matching_sections) == 1:
                                (
                                    canonical_match_score,
                                    _canonical_match_index,
                                    canonical_match,
                                ) = matching_sections[0]
                        if canonical_match is not None:
                            self.logs.append(
                                f'cut {name} selected the unique canonical solid '
                                f'section from {len(candidate_bodies)} candidates; '
                                f'bbox_score={canonical_match_score:.9g}'
                            )
                            candidate_bodies = [canonical_match]
                    if len(candidate_bodies) > 1:
                        if op_code == SWBODYCUT and len(pending) == 1:
                            self._mark_degraded(name, 'static_boolean_split')
                            self.logs.append(
                                f'cut {name} produced {len(candidate_bodies)} '
                                f'geometrically separate solid sections'
                            )
                            return [
                                self._create_feature_from_body(
                                    body, f'{name}_section_{index + 1}'
                                )
                                for index, body in enumerate(candidate_bodies)
                            ]
                        attempts.append(
                            {
                                'candidate_index': candidate_index,
                                'error': int(error_code),
                                'result': (
                                    f'SolidWorks body boolean for {name} returned '
                                    f'{len(candidate_bodies)} solid sections; expected one'
                                ),
                                'bbox': (
                                    pending_boxes[candidate_index]
                                    if op_code == SWBODYADD
                                    else self._box_from_entity(tool)
                                ),
                            }
                        )
                        continue
                    if len(candidate_bodies) != 1:
                        attempts.append(
                            {
                                'candidate_index': candidate_index,
                                'error': int(error_code),
                                'result': 'SolidWorks body boolean returned no solid section',
                                'bbox': self._box_from_entity(tool),
                            }
                        )
                        continue
                    result = candidate_bodies[0]
                    applied_steps.append({
                        'tool_bbox': self._box_from_entity(tool),
                        'tool_volume': self._body_volume(tool),
                        'result_bbox': self._box_from_entity(result),
                        'result_volume': self._body_volume(result),
                    })
                    pending.pop(candidate_index)
                    break
                attempts.append(
                    {
                        'candidate_index': candidate_index,
                        'error': int(error_code),
                        'bbox': (
                            pending_boxes[candidate_index]
                            if op_code == SWBODYADD
                            else self._box_from_entity(tool)
                        ),
                    }
                )
            else:
                error_code = attempts[0]['error'] if attempts else int(error_code)
                if skip_non_intersecting and op_code == SWBODYCUT and error_code in {5, 1067}:
                    pending.pop(0)
                    continue
                if op_code == SWBODYCUT and error_code == 547:
                    # Operations2 is more reliable for ordinary bodies, but
                    # SolidWorks can reject a copied multi-tool cut with 547
                    # even when the native Combine feature accepts the same
                    # geometric bodies. This retry is failure-only and keeps
                    # the graph's geometric body inputs unchanged.
                    try:
                        native_body = self._native_combine_body(
                            result, pending, op_code, name
                        )
                        if native_body is not None:
                            self.logs.append(
                                f'boolean {name} recovered with native Combine '
                                f'after Operations2 error 547'
                            )
                            return native_body
                    except Exception as exc:
                        self.logs.append(
                            f'native Combine retry failed for {name}: {exc}'
                        )
                raise RuntimeError(
                    f'SolidWorks temporary body boolean failed for {name}; '
                    f'error={error_code}; result_bbox={self._box_from_entity(result)!r}; '
                    f'attempts={attempts!r}; recent_logs={self.logs[-12:]!r}'
                )
        if clean:
            cleaned = False
            for call in (
                lambda: result.RemoveRedundantTopology(),
                lambda: result._oleobj_.InvokeTypes(
                    60,
                    0,
                    pythoncom.DISPATCH_METHOD,
                    (pythoncom.VT_BOOL, 0),
                    (),
                ),
            ):
                try:
                    cleaned = bool(call())
                    if cleaned:
                        break
                except Exception as exc:
                    self.logs.append(
                        f'redundant-topology cleanup failed for {name}: {exc}'
                    )
            if not cleaned:
                self.logs.append(
                    f'redundant-topology cleanup was not applied for {name}'
                )
        if (
            isinstance(canonical_result, dict)
            and not self._body_matches_canonical(result, canonical_result)
        ):
            if (
                op_code == SWBODYCUT
                and self._cut_tolerance_artifact_matches_canonical(
                    result, canonical_result
                )
            ):
                self.logs.append(
                    f'cut {name} accepted a bounded SolidWorks Boolean '
                    'tolerance expansion with canonical volume preserved'
                )
            else:
                actual_descriptor = {
                    'bbox': self._box_from_entity(result),
                    'volume': self._body_volume(result),
                }
                raise RuntimeError(
                    f'SolidWorks static boolean for {name} did not match '
                    f'canonical bbox/volume; actual={actual_descriptor!r}; '
                    f'canonical={canonical_result!r}; '
                    f'base={{"bbox": {self._box_from_entity(base)!r}, '
                    f'"volume": {self._body_volume(base)!r}}}; '
                    f'tools={[(self._box_from_entity(tool), self._body_volume(tool)) for tool in tools]!r}; '
                    f'applied_steps={applied_steps!r}'
                )
        self._mark_degraded(name, 'static_boolean')
        return self._create_feature_from_body(result, name)

    def _body_set_matches_canonical(
        self, bodies, canonical_result, volume_relative_tolerance=1.0e-5
    ):
        expected_bbox = (
            canonical_result.get('bbox')
            if isinstance(canonical_result, dict)
            else None
        )
        expected_volume = (
            canonical_result.get('volume')
            if isinstance(canonical_result, dict)
            else None
        )
        if not bodies or not isinstance(expected_bbox, dict) or expected_volume is None:
            return False
        bboxes = [self._box_from_entity(body) for body in bodies]
        if any(not isinstance(bbox, dict) for bbox in bboxes):
            return False
        actual_bbox = {
            'min': tuple(
                min(float(bbox['min'][index]) for bbox in bboxes)
                for index in range(3)
            ),
            'max': tuple(
                max(float(bbox['max'][index]) for bbox in bboxes)
                for index in range(3)
            ),
        }
        volumes = [self._body_volume(body) for body in bodies]
        if any(volume is None for volume in volumes):
            return False
        actual_volume = sum(float(volume) for volume in volumes)
        volume_error = _relative_error(
            actual_volume, expected_volume, floor=1.0e-12
        )
        expected_size = _distance(expected_bbox.get('min'), expected_bbox.get('max'))
        # When volume is effectively exact, permit the small bbox expansion
        # caused by SolidWorks edge/surface tolerances. This remains far below
        # feature-edit amplitudes and does not hide an incorrect transform:
        # the former 082 axis bug displaced the bbox by 16 mm.
        bbox_relative_tolerance = (
            1.0e-4 if volume_error <= 1.0e-8 else 2.0e-6
        )
        bbox_tolerance = max(
            2.0e-7, expected_size * bbox_relative_tolerance
        )
        if _bbox_score(actual_bbox, expected_bbox) > bbox_tolerance:
            return False
        return volume_error <= float(volume_relative_tolerance)

    def _body_matches_canonical(
        self, body, canonical_result, volume_relative_tolerance=1.0e-5
    ):
        expected_bbox = (
            canonical_result.get('bbox')
            if isinstance(canonical_result, dict)
            else None
        )
        expected_volume = (
            canonical_result.get('volume')
            if isinstance(canonical_result, dict)
            else None
        )
        if not isinstance(expected_bbox, dict) or expected_volume is None:
            return False
        expected_size = _distance(expected_bbox.get('min'), expected_bbox.get('max'))
        volume = self._body_volume(body)
        volume_error = (
            _relative_error(volume, expected_volume, floor=1.0e-12)
            if volume is not None else float('inf')
        )
        bbox_relative_tolerance = (
            1.0e-4 if volume_error <= 1.0e-8 else 2.0e-6
        )
        bbox_tolerance = max(
            2.0e-7, expected_size * bbox_relative_tolerance
        )
        return (
            _bbox_score(self._box_from_entity(body), expected_bbox) <= bbox_tolerance
            and volume is not None
            and volume_error <= float(volume_relative_tolerance)
        )

    def _cut_tolerance_artifact_matches_canonical(
        self, body, canonical_result
    ):
        expected_bbox = (
            canonical_result.get('bbox')
            if isinstance(canonical_result, dict) else None
        )
        expected_volume = (
            canonical_result.get('volume')
            if isinstance(canonical_result, dict) else None
        )
        actual_bbox = self._box_from_entity(body)
        actual_volume = self._body_volume(body)
        if (
            not isinstance(expected_bbox, dict)
            or not isinstance(actual_bbox, dict)
            or expected_volume is None
            or actual_volume is None
            or _relative_error(
                actual_volume, expected_volume, floor=1.0e-12
            ) > 5.0e-6
        ):
            return False
        expected_min = _v3(expected_bbox.get('min'))
        expected_max = _v3(expected_bbox.get('max'))
        actual_min = _v3(actual_bbox.get('min'))
        actual_max = _v3(actual_bbox.get('max'))
        expected_size = _distance(expected_min, expected_max)
        containment_tolerance = max(2.0e-7, expected_size * 1.0e-4)
        if any(
            actual_min[index] > expected_min[index] + containment_tolerance
            or actual_max[index] < expected_max[index] - containment_tolerance
            for index in range(3)
        ):
            return False
        maximum_expansion = max(
            max(0.0, expected_min[index] - actual_min[index])
            for index in range(3)
        )
        maximum_expansion = max(
            maximum_expansion,
            max(
                max(0.0, actual_max[index] - expected_max[index])
                for index in range(3)
            ),
        )
        return maximum_expansion <= max(
            2.0e-7, expected_size * 2.5e-3
        )

    def _combine_op_value(self, op_code):
        if op_code not in {SWBODYADD, SWBODYCUT, SWBODYINTERSECT}:
            raise RuntimeError(f'Unsupported combine operation code: {op_code}')
        return op_code

    def _native_combine_body(
        self, base, tools, op_code, name, *, prefer_live_base=False
    ):
        combine_op = self._combine_op_value(op_code)
        before = self._body_names()
        self._clear_selection()
        if not self._select_entity(base, append=False, mark=1):
            raise RuntimeError('Could not select main body for native Combine')
        for tool in tools:
            if not self._select_entity(tool, append=True, mark=2):
                raise RuntimeError('Could not select tool body for native Combine')
        feature = None
        direct_tools = (
            tuple(tools)
            if op_code == SWBODYCUT
            else tuple([base] + list(tools))
        )
        direct_tool_variants = []
        empty_tool_variants = []
        # InsertCombineFeature's ToolVar is a COM array of Body2 objects.
        # pywin32 can otherwise expose a plain Python tuple as a scalar
        # VARIANT, which SolidWorks rejects with DISP_E_TYPEMISMATCH.  The
        # explicit arrays are required both for the primary live path and for
        # the failure-only retry after temporary-body error 547.
        for variant_type in (
            pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH,
            pythoncom.VT_ARRAY | pythoncom.VT_VARIANT,
        ):
            try:
                direct_tool_variants.append(
                    win32com.client.VARIANT(variant_type, direct_tools)
                )
            except Exception as exc:
                self.logs.append(
                    f'could not marshal Combine tools for {name}: {exc}'
                )
            try:
                empty_tool_variants.append(
                    win32com.client.VARIANT(variant_type, ())
                )
            except Exception as exc:
                self.logs.append(
                    f'could not marshal empty Combine tools for {name}: {exc}'
                )
        empty_main = _empty_dispatch()
        for call in (
            *(
                lambda tool_variant=tool_variant: self.model.FeatureManager.InsertCombineFeature(
                    combine_op,
                    base if op_code == SWBODYCUT else empty_main,
                    tool_variant,
                )
                for tool_variant in direct_tool_variants
            ),
            lambda: self.model.FeatureManager.InsertCombineFeature(
                combine_op, base if op_code == SWBODYCUT else empty_main,
                direct_tools,
            ),
            *(
                lambda empty_tools=empty_tools: self.model.FeatureManager.InsertCombineFeature(
                    combine_op, empty_main, empty_tools
                )
                for empty_tools in empty_tool_variants
            ),
        ):
            try:
                feature = call()
                if feature is not None:
                    break
            except Exception as exc:
                self.logs.append(f'combine attempt failed for {name}: {exc}')
        self._clear_selection()
        if feature is None:
            raise RuntimeError('SolidWorks InsertCombineFeature failed')
        try:
            feature.Name = str(name)
        except Exception:
            pass
        return self._capture_new_body(before, feature)

    def _box_from_entity(self, entity):
        for call in (lambda: entity.GetBox(), lambda: entity.GetBodyBox()):
            try:
                bbox = _bbox_from_box(call())
                if bbox:
                    return bbox
            except Exception:
                pass
        return {'min': (0.0, 0.0, 0.0), 'max': (0.0, 0.0, 0.0)}

    def _body_volume(self, body):
        try:
            values = body.GetMassProperties(1.0)
            if (
                isinstance(values, (list, tuple))
                and values
                and isinstance(values[0], (list, tuple))
            ):
                values = values[0]
            if isinstance(values, (list, tuple)) and len(values) >= 4:
                volume_m3 = abs(float(values[3]))
                if math.isfinite(volume_m3) and volume_m3 > 0.0:
                    return volume_m3 * (M_TO_MM / MODEL_SCALE) ** 3
        except Exception:
            pass
        return None

    def _edge_signature(self, edge):
        def array3(value):
            try:
                value = _maybe_call(value)
                if value is not None and len(value) >= 3:
                    return tuple(float(value[index]) for index in range(3))
            except Exception:
                pass
            return None

        curve = None
        for call in (
            lambda: _maybe_call(edge.GetCurve),
            lambda: win32com.client.Dispatch(edge._oleobj_.InvokeTypes(
                1, 0, pythoncom.DISPATCH_METHOD, (pythoncom.VT_DISPATCH, 0), ()
            )),
        ):
            try:
                curve = call()
                if curve is not None:
                    break
            except Exception:
                curve = None

        # GetCurveParams3 is the documented source for an edge's geometric
        # endpoints, parameter range, and curve type. GetCurve must be called
        # first so SolidWorks materializes the underlying curve information.
        start_m = end_m = None
        u_min = u_max = None
        curve_type = None
        try:
            curve_data = _maybe_call(edge.GetCurveParams3)
            if curve_data is not None:
                start_m = array3(getattr(curve_data, 'StartPoint', None))
                end_m = array3(getattr(curve_data, 'EndPoint', None))
                u_min = float(_maybe_call(getattr(curve_data, 'UMinValue')))
                u_max = float(_maybe_call(getattr(curve_data, 'UMaxValue')))
                curve_type = int(_maybe_call(getattr(curve_data, 'CurveType')))
        except Exception:
            start_m = end_m = None
            u_min = u_max = None
            curve_type = None

        params = None
        if start_m is None or end_m is None or u_min is None or u_max is None:
            for call in (
                lambda: _maybe_call(edge.GetCurveParams2),
                lambda: edge._oleobj_.InvokeTypes(
                    24, 0, pythoncom.DISPATCH_METHOD,
                    (pythoncom.VT_VARIANT, 0), (),
                ),
            ):
                try:
                    values = call()
                    params = tuple(float(value) for value in values)
                    if len(params) >= 8:
                        start_m = tuple(params[index] for index in range(3))
                        end_m = tuple(params[index] for index in range(3, 6))
                        u_min, u_max = float(params[6]), float(params[7])
                        break
                except Exception:
                    params = None

        def vertex_point(getter_name):
            try:
                vertex = _maybe_call(getattr(edge, getter_name))
                if vertex is None:
                    return None
                return array3(getattr(vertex, 'GetPoint'))
            except Exception:
                return None

        points_m = []
        curve_samples_m = []
        if start_m is not None and end_m is not None and u_min is not None and u_max is not None:
            for step in range(65):
                parameter = u_min + (u_max - u_min) * (step / 64.0)
                evaluated = None
                for call in (
                    lambda: edge.Evaluate2(parameter, 1),
                    lambda: curve.Evaluate2(parameter, 1) if curve is not None else None,
                ):
                    try:
                        evaluated = call()
                        if evaluated is not None and len(evaluated) >= 3:
                            break
                    except Exception:
                        evaluated = None
                if evaluated is None or len(evaluated) < 3:
                    curve_samples_m = []
                    break
                point = tuple(float(evaluated[index]) for index in range(3))
                tangent = (
                    tuple(float(evaluated[index]) for index in range(3, 6))
                    if len(evaluated) >= 6
                    else None
                )
                curve_samples_m.append((point, tangent))
            if len(curve_samples_m) == 65:
                points_m.extend(point for point, _tangent in curve_samples_m)
            else:
                points_m.extend((start_m, end_m))
        else:
            start_m = vertex_point('GetStartVertex')
            end_m = vertex_point('GetEndVertex')
            if start_m is not None:
                points_m.append(start_m)
            if end_m is not None:
                points_m.append(end_m)

        if not points_m:
            bbox = self._box_from_entity(edge)
            start = end = _bbox_center(bbox)
        else:
            converted = [
                tuple(value * M_TO_MM / MODEL_SCALE for value in point)
                for point in points_m
            ]
            bbox = {
                'min': tuple(min(point[index] for point in converted) for index in range(3)),
                'max': tuple(max(point[index] for point in converted) for index in range(3)),
            }
            start = tuple(value * M_TO_MM / MODEL_SCALE for value in start_m)
            end = tuple(value * M_TO_MM / MODEL_SCALE for value in end_m)

        center = _bbox_center(bbox)
        length = _distance(start, end)
        for call in (
            lambda: curve.GetLength3(u_min, u_max),
            lambda: curve._oleobj_.InvokeTypes(
                63, 0, pythoncom.DISPATCH_METHOD, (pythoncom.VT_R8, 0),
                ((pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN), (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN)),
                u_min, u_max,
            ),
            lambda: curve._oleobj_.InvokeTypes(
                21, 0, pythoncom.DISPATCH_METHOD, (pythoncom.VT_R8, 0),
                ((pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN), (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN)),
                u_min, u_max,
            ),
        ):
            try:
                length_value = call()
                if length_value is not None:
                    length = float(length_value) * M_TO_MM / MODEL_SCALE
                    break
            except Exception:
                pass
        curve_types = {
            3001: 'LINE',
            3002: 'CIRCLE',
            3003: 'ELLIPSE',
            3004: 'INTERSECTION',
            3005: 'BSPLINE',
            3006: 'SPCURVE',
            3008: 'CONSTPARAM',
            3009: 'TRIMMED',
        }
        geom_type = ''
        if curve_type is not None:
            geom_type = curve_types.get(int(curve_type), '')
        if not geom_type:
            try:
                geom_type = curve_types.get(int(_maybe_call(curve.Identity)), '')
            except Exception:
                if start_m is not None and end_m is not None:
                    geom_type = 'LINE' if abs(_distance(start, end) - length) <= 1.0e-7 else ''
        if geom_type in {'BSPLINE', 'INTERSECTION'} and len(curve_samples_m) == 65:
            sample_points = [
                tuple(value * M_TO_MM / MODEL_SCALE for value in point)
                for point, _tangent in curve_samples_m
            ]
            chord = _sub(end, start)
            chord_length = _norm(chord)
            scale = max(1.0, chord_length, length)
            if (
                chord_length > scale * 1.0e-10
                and abs(length - chord_length) <= scale * 1.0e-7
                and all(
                    _norm(_cross(_sub(point, start), chord)) / chord_length
                    <= scale * 1.0e-7
                    for point in sample_points
                )
            ):
                geom_type = 'LINE'
        if (
            geom_type == 'INTERSECTION'
            and _distance(start, end) > max(1.0, length) * 1.0e-7
        ):
            # SolidWorks reports open surface-intersection splines with the
            # generic INTERSECTION identity. OCC exposes the same support as a
            # BSplineCurve, so normalize the backend signature before GSM.
            geom_type = 'BSPLINE'
        if geom_type == 'LINE':
            center = tuple((start[index] + end[index]) * 0.5 for index in range(3))
        elif len(curve_samples_m) == 65 and all(
            tangent is not None for _point, tangent in curve_samples_m
        ):
            weighted = [0.0, 0.0, 0.0]
            total = 0.0
            for index, (point, tangent) in enumerate(curve_samples_m):
                coefficient = 1.0 if index in {0, 64} else (4.0 if index % 2 else 2.0)
                weight = coefficient * _norm(tangent)
                total += weight
                for axis in range(3):
                    weighted[axis] += weight * point[axis]
            if total > 1.0e-18:
                center = tuple(
                    value / total * M_TO_MM / MODEL_SCALE
                    for value in weighted
                )
        start_tangent = end_tangent = None
        if len(curve_samples_m) == 65:
            first_tangent = curve_samples_m[0][1]
            last_tangent = curve_samples_m[-1][1]
            if first_tangent is not None:
                start_tangent = _unit(first_tangent)
            if last_tangent is not None:
                end_tangent = _unit(last_tangent)
        support = None
        if geom_type == 'CIRCLE' and curve is not None:
            for attribute_name in ('CircleParams', 'ICircleParams'):
                try:
                    values = _maybe_call(getattr(curve, attribute_name))
                    if values is not None and len(values) >= 7:
                        support = {
                            'center': tuple(
                                float(values[index]) * M_TO_MM / MODEL_SCALE
                                for index in range(3)
                            ),
                            'axis': _unit(tuple(
                                float(values[index]) for index in range(3, 6)
                            )),
                            'radius': (
                                abs(float(values[6])) * M_TO_MM / MODEL_SCALE
                            ),
                        }
                        break
                except Exception:
                    support = None
        return {
            'bbox': bbox,
            'center': center,
            'start': start,
            'end': end,
            'start_tangent': start_tangent,
            'end_tangent': end_tangent,
            'samples': [
                tuple(value * M_TO_MM / MODEL_SCALE for value in point)
                for point, _tangent in curve_samples_m
            ],
            'length': length,
            'geom_type': geom_type,
            'support': support,
        }

    def _face_signature(self, face):
        bbox = self._box_from_entity(face)
        area = 0.0
        try:
            area = float(face.GetArea()) * M2_TO_MM2 / (MODEL_SCALE * MODEL_SCALE)
        except Exception:
            pass
        geom_type = ''
        surface_types = {
            4001: 'PLANE',
            4002: 'CYLINDER',
            4003: 'CONE',
            4004: 'SPHERE',
            4005: 'TORUS',
            4006: 'BSPLINE',
            4007: 'BLEND',
            4008: 'OFFSET',
            4009: 'EXTRU',
            4010: 'SREV',
        }
        try:
            surface = face.GetSurface()
            identity = int(_maybe_call(surface.Identity))
            geom_type = surface_types.get(identity, str(identity))
        except Exception:
            surface = None
        normal = None
        try:
            values = _maybe_call(getattr(face, 'Normal'))
            if values is not None and len(values) >= 3:
                normal = _unit(tuple(float(values[index]) for index in range(3)))
        except Exception:
            pass
        if normal is None and geom_type == 'PLANE' and surface is not None:
            try:
                values = _maybe_call(getattr(surface, 'PlaneParams'))
                if values is not None and len(values) >= 6:
                    normal = _unit(tuple(float(values[index]) for index in range(3, 6)))
            except Exception:
                pass
        return {
            'bbox': bbox,
            'center': _bbox_center(bbox),
            'area': area,
            'geom_type': geom_type,
            'normal': normal,
        }

    def _cylinder_surface_params(self, face):
        surface = None
        for call in (
            lambda: _maybe_call(face.GetSurface),
            lambda: win32com.client.Dispatch(face._oleobj_.InvokeTypes(
                3,
                0,
                pythoncom.DISPATCH_METHOD,
                (pythoncom.VT_DISPATCH, 0),
                (),
            )),
        ):
            try:
                surface = call()
                if surface is not None:
                    break
            except Exception:
                surface = None
        if surface is None:
            return None
        is_cylinder = False
        for call in (
            lambda: bool(_maybe_call(surface.IsCylinder)),
            lambda: bool(surface._oleobj_.InvokeTypes(
                7,
                0,
                pythoncom.DISPATCH_METHOD,
                (pythoncom.VT_BOOL, 0),
                (),
            )),
        ):
            try:
                is_cylinder = call()
                break
            except Exception:
                pass
        if not is_cylinder:
            return None
        values = None
        for call in (
            lambda: _maybe_call(surface.CylinderParams),
            lambda: surface._oleobj_.InvokeTypes(
                2,
                0,
                pythoncom.DISPATCH_PROPERTYGET,
                (pythoncom.VT_VARIANT, 0),
                (),
            ),
        ):
            try:
                values = tuple(float(value) for value in call())
                if len(values) >= 7:
                    break
            except Exception:
                values = None
        if values is None or len(values) < 7:
            return None
        scale = M_TO_MM / MODEL_SCALE
        return {
            'origin': tuple(values[index] * scale for index in range(3)),
            'axis': _unit(values[3:6]),
            'radius': abs(float(values[6]) * scale),
            'bbox': self._box_from_entity(face),
        }

    def _is_missing_cylinder_seam(self, body, selector):
        selector = _selector_geometry(selector)
        if _selector_kind(selector, {}) != 'edge':
            return False
        if _selector_geom_type(selector) != 'LINE':
            return False
        start = _tuple3_or_none(selector.get('start'))
        end = _tuple3_or_none(selector.get('end'))
        expected_length = selector.get('length')
        if start is None or end is None or expected_length is None:
            return False
        direction = _sub(end, start)
        chord_length = _norm(direction)
        scale = max(1.0, chord_length, abs(float(expected_length)))
        if chord_length <= scale * 1.0e-10:
            return False
        if _relative_error(chord_length, expected_length) > 1.0e-4:
            return False
        unit_direction = _unit(direction)
        body_bbox = self._box_from_entity(body)
        for face in self._body_faces(body):
            cylinder = self._cylinder_surface_params(face)
            if cylinder is None:
                continue
            if abs(_dot(unit_direction, cylinder['axis'])) < 1.0 - 1.0e-6:
                continue
            radius = float(cylinder['radius'])
            radius_scale = max(1.0, radius)
            if (
                abs(_point_line_distance(start, cylinder['origin'], cylinder['axis']) - radius)
                > radius_scale * 1.0e-5
                or abs(_point_line_distance(end, cylinder['origin'], cylinder['axis']) - radius)
                > radius_scale * 1.0e-5
            ):
                continue
            bbox = cylinder.get('bbox')
            if (
                not isinstance(bbox, dict)
                or _distance(bbox.get('min'), bbox.get('max')) <= 1.0e-12
            ):
                bbox = body_bbox
            tolerance = scale * 1.0e-5
            if not isinstance(bbox, dict):
                continue
            if not all(
                float(bbox['min'][index]) - tolerance <= point[index]
                <= float(bbox['max'][index]) + tolerance
                for point in (start, end)
                for index in range(3)
            ):
                continue
            return True
        return False

    def _detail_edge_topology_match(
        self, ranked, selector, source, missing_seam
    ):
        closed_intersection = _closed_intersection_candidate(ranked, selector)
        if closed_intersection is not None:
            return closed_intersection
        if _is_missing_revolution_seam(ranked, selector):
            return missing_seam
        if self._is_missing_cylinder_seam(source, selector):
            return missing_seam
        return None

    def _body_edges(self, body):
        try:
            edges = body.GetEdges()
        except Exception:
            edges = None
        if not edges:
            return []
        return list(edges) if isinstance(edges, (list, tuple)) else [edges]

    def _body_faces(self, body):
        try:
            faces = body.GetFaces()
        except Exception:
            faces = None
        if not faces:
            return []
        return list(faces) if isinstance(faces, (list, tuple)) else [faces]

    def _feature_detail_edges(self, params, inputs, kind, node_id):
        upstream_bodies = self._bodies_from_value(
            self._first_output(inputs[0])
        )
        canonical_result = self._detail_result_descriptor(
            inputs[0], node_id
        )
        if upstream_bodies:
            self._capture_detail_source_topology(
                inputs[0], upstream_bodies
            )
        # Keep detail features attached to their live input body even when a
        # downstream transform/boolean consumes the result. Copying the input
        # first creates a static BaseBody/MoveCopy snapshot and severs native
        # parameter propagation after the document is reopened.
        selectors = []
        for selector_id in params.get('selected_edge_node_ids') or []:
            payload = self.selection_payloads.get(str(selector_id))
            if payload:
                selectors.append(payload.get('params') or {})
        if not selectors:
            for item in params.get('selected_edges') or []:
                if isinstance(item, dict):
                    selectors.append(item.get('selector_hint') or item)
        if not selectors:
            raise RuntimeError(f'{kind} requires at least one geometrically selected edge')
        if len(upstream_bodies) > 1:
            # Match against the same complete edge pool represented by the
            # canonical compound, then require every selector (including a
            # fragmented path) to belong to exactly one native body. This
            # preserves unaffected live bodies instead of silently dropping
            # them when SolidWorks reports only the feature's changed body.
            edge_signatures = []
            body_edge_signatures = []
            edge_owners = {}
            for body_index, body in enumerate(upstream_bodies):
                signatures = [
                    (edge, self._edge_signature(edge))
                    for edge in self._body_edges(body)
                ]
                body_edge_signatures.append(signatures)
                for edge, signature in signatures:
                    edge_signatures.append((edge, signature))
                    edge_owners[id(edge)] = body_index
            selectors_by_body = {
                index: [] for index in range(len(upstream_bodies))
            }
            missing_seam = object()

            def compound_topology_match(ranked, selector):
                closed_intersection = _closed_intersection_candidate(
                    ranked, selector
                )
                if closed_intersection is not None:
                    return closed_intersection
                seam_owners = []
                for body_index, body in enumerate(upstream_bodies):
                    local_ranked = sorted(
                        body_edge_signatures[body_index],
                        key=lambda item: _geom_score(item[1], selector),
                    )
                    if (
                        _is_missing_revolution_seam(local_ranked, selector)
                        or self._is_missing_cylinder_seam(body, selector)
                    ):
                        seam_owners.append(body_index)
                if len(seam_owners) == 1:
                    return missing_seam
                if len(seam_owners) > 1:
                    raise RuntimeError(
                        f'{kind} {node_id} seam selector is ambiguous across '
                        f'live bodies {seam_owners!r}'
                    )
                return None

            skipped_seams = 0
            individual_candidates = {}
            individual_errors = {}
            for selector_index, selector in enumerate(selectors):
                try:
                    individual_candidates[selector_index] = (
                        _selection_candidates_by_geometry(
                            edge_signatures,
                            selector,
                            'edge',
                            topology_match=compound_topology_match,
                        )
                    )
                except RuntimeError as exc:
                    individual_errors[selector_index] = exc
            coalesced_pairs = _coalesced_edge_selector_pairs(
                edge_signatures,
                selectors,
            )
            coalesced_pairs = [
                pair for pair in coalesced_pairs
                if pair[0] in individual_errors or pair[1] in individual_errors
            ]
            coalesced_candidates = {}
            for left_index, right_index, candidate_index in coalesced_pairs:
                candidate = edge_signatures[candidate_index][0]
                coalesced_candidates[left_index] = candidate
                coalesced_candidates[right_index] = candidate
            covered_errors = set(individual_errors) & set(coalesced_candidates)
            unresolved_errors = sorted(set(individual_errors) - covered_errors)
            if unresolved_errors:
                raise individual_errors[unresolved_errors[0]]
            for selector_index, selector in enumerate(selectors):
                candidates = (
                    [coalesced_candidates[selector_index]]
                    if selector_index in coalesced_candidates
                    else individual_candidates[selector_index]
                )
                if len(candidates) == 1 and candidates[0] is missing_seam:
                    skipped_seams += 1
                    continue
                owners = {
                    edge_owners.get(id(candidate)) for candidate in candidates
                }
                owners.discard(None)
                if len(owners) != 1:
                    raise RuntimeError(
                        f'{kind} {node_id} selector {selector_index} '
                        f'matched edges on {len(owners)} live bodies; refusing '
                        'an ambiguous multi-body detail feature'
                    )
                selectors_by_body[next(iter(owners))].append(selector)
            if skipped_seams:
                self.logs.append(
                    f'{kind} {node_id} omitted {skipped_seams} seam '
                    'selection(s) absent from the SolidWorks body set'
                )
            affected_body_indices = [
                index for index, body_selectors in selectors_by_body.items()
                if body_selectors
            ]
            affected_canonical = None
            if (
                len(affected_body_indices) == 1
                and isinstance(canonical_result, dict)
                and canonical_result.get('volume') is not None
            ):
                affected_index = affected_body_indices[0]
                unaffected_volumes = [
                    self._body_volume(body)
                    for index, body in enumerate(upstream_bodies)
                    if index != affected_index
                ]
                if all(volume is not None for volume in unaffected_volumes):
                    affected_canonical = {
                        'bbox': self._box_from_entity(
                            upstream_bodies[affected_index]
                        ),
                        'volume': (
                            float(canonical_result['volume'])
                            - sum(float(volume) for volume in unaffected_volumes)
                        ),
                    }
            results = []
            for body_index, body in enumerate(upstream_bodies):
                body_selectors = selectors_by_body[body_index]
                if not body_selectors:
                    results.append(body)
                    continue
                results.append(
                    self._apply_detail_feature_to_body(
                        body,
                        body_selectors,
                        params,
                        kind,
                        f'{node_id}_body_{body_index + 1}',
                        allow_component_fallback=True,
                        strict_canonical_result=(
                            affected_canonical
                            if body_index in affected_body_indices
                            else None
                        ),
                    )
                )
            self.logs.append(
                f'{kind} {node_id} preserved {len(results)} live bodies; '
                f'{sum(bool(value) for value in selectors_by_body.values())} '
                'body/bodies were affected'
            )
            self._validate_detail_result(
                results, canonical_result, kind, node_id
            )
            return results
        source = upstream_bodies[0]
        self.logs.append(f'{kind} {node_id} consumes the live input body')
        result = self._apply_detail_feature_to_body(
            source,
            selectors,
            params,
            kind,
            node_id,
            allow_component_fallback=True,
            topology_source_node_id=inputs[0],
            topology_target_node_id=node_id,
        )
        self._validate_detail_result(
            result, canonical_result, kind, node_id
        )
        return result

    def _detail_selected_edges(self, source, selectors, kind, node_id):
        edge_signatures = [
            (edge, self._edge_signature(edge))
            for edge in self._body_edges(source)
        ]
        selected = []
        skipped_seams = 0
        missing_seam = object()
        individual_candidates = {}
        individual_errors = {}
        for selector_index, selector in enumerate(selectors):
            try:
                individual_candidates[selector_index] = (
                    _selection_candidates_by_geometry(
                        edge_signatures,
                        selector,
                        'edge',
                        topology_match=lambda _ranked, normalized_selector: self._detail_edge_topology_match(
                            _ranked,
                            normalized_selector,
                            source,
                            missing_seam,
                        ),
                    )
                )
            except RuntimeError as exc:
                individual_errors[selector_index] = exc
        coalesced_pairs = _coalesced_edge_selector_pairs(
            edge_signatures,
            selectors,
        )
        coalesced_pairs = [
            pair for pair in coalesced_pairs
            if pair[0] in individual_errors or pair[1] in individual_errors
        ]
        coalesced_by_selector = {}
        for left_index, right_index, candidate_index in coalesced_pairs:
            coalesced_by_selector[left_index] = (
                right_index, edge_signatures[candidate_index][0]
            )
        consumed_selectors = {
            right_index
            for _left_index, right_index, _candidate_index in coalesced_pairs
        }
        covered_errors = {
            index
            for left_index, right_index, _candidate_index in coalesced_pairs
            for index in (left_index, right_index)
            if index in individual_errors
        }
        unresolved_errors = sorted(set(individual_errors) - covered_errors)
        if unresolved_errors:
            raise individual_errors[unresolved_errors[0]]
        for selector_index, selector in enumerate(selectors):
            if selector_index in consumed_selectors:
                continue
            if selector_index in coalesced_by_selector:
                right_index, candidate = coalesced_by_selector[selector_index]
                selected.append(candidate)
                self.logs.append(
                    f'{kind} {node_id} coalesced selector pair '
                    f'{selector_index}/{right_index} onto one complete '
                    'SolidWorks edge'
                )
                continue
            candidates = individual_candidates[selector_index]
            if len(candidates) == 1 and candidates[0] is missing_seam:
                skipped_seams += 1
            else:
                selected.extend(candidates)
        return selected, skipped_seams

    def _delete_retry_feature(self, feature, kind, node_id):
        self._clear_selection()
        try:
            selected = bool(feature.Select2(False, 0))
        except Exception:
            selected = False
        deleted = False
        if selected:
            try:
                deleted = bool(self.model.Extension.DeleteSelection2(0))
            except Exception:
                deleted = False
        if not deleted:
            raise RuntimeError(
                f'Could not delete rejected SolidWorks {kind} candidate '
                f'for {node_id}'
            )
        try:
            self.model.ForceRebuild3(False)
        except Exception:
            pass

    def _apply_detail_feature_to_body(
        self,
        source,
        selectors,
        params,
        kind,
        node_id,
        *,
        allow_component_fallback,
        topology_source_node_id=None,
        topology_target_node_id=None,
        strict_canonical_result=None,
        require_geometry_change=False,
    ):
        source_bbox = self._box_from_entity(source)
        source_descriptor = {
            'bbox': source_bbox,
            'volume': self._body_volume(source),
        }
        source_name = self._body_name(source)
        source_reference = self._persistent_reference_bytes(source)
        selected, skipped_seams = self._detail_selected_edges(
            source, selectors, kind, node_id
        )
        if skipped_seams:
            self.logs.append(
                f'{kind} {node_id} omitted {skipped_seams} cylindrical seam '
                'selection(s) absent from SolidWorks native topology'
            )
        if not selected:
            return source
        self._clear_selection()
        for index, edge in enumerate(selected):
            if not self._select_entity(edge, append=index > 0):
                raise RuntimeError(f'Could not select SolidWorks edge for {kind}')
        before = self._body_names()
        result = None
        feature_error = None
        candidate_rebuilt = False
        if kind == 'fillet':
            radius = _as_m(params.get('radius', 0.0))
            feature = None

            def create_fillet_from_definition(propagate):
                self._clear_selection()
                for edge_index, edge in enumerate(selected):
                    if not self._select_entity(
                        edge, append=edge_index > 0, mark=1
                    ):
                        return None
                definition = self.model.FeatureManager.CreateDefinition(1)
                if definition is None or not bool(definition.Initialize(0)):
                    return None
                definition.ConicTypeForCrossSectionProfile = 0
                definition.DefaultRadius = radius
                definition.OverflowType = 0
                definition.PropagateToTangentFaces = bool(propagate)
                definition.Edges = win32com.client.VARIANT(
                    pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH,
                    tuple(selected),
                )
                return self.model.FeatureManager.CreateFeature(definition)

            for call in (
                # FeatureData preserves the explicit seed-edge set and avoids
                # the legacy FeatureFillet option-bit expansion that can make
                # large disconnected selections invalid in SolidWorks.
                lambda: create_fillet_from_definition(False),
                lambda: create_fillet_from_definition(True),
                lambda: self.model.FeatureManager.FeatureFillet(
                    2,
                    radius,
                    0,
                    0,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.FeatureFillet(
                    66,
                    radius,
                    0,
                    0,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.FeatureFillet(
                    34,
                    radius,
                    0,
                    0,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.FeatureFillet(
                    98,
                    radius,
                    0,
                    0,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.FeatureFillet(
                    226,
                    radius,
                    0,
                    0,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.FeatureFillet(
                    SW_FEATURE_FILLET_OPTIONS,
                    radius,
                    0,
                    0,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.FeatureFillet3(
                    SW_FEATURE_FILLET_OPTIONS,
                    radius,
                    0.0,
                    0.0,
                    0,
                    0,
                    0,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.FeatureFillet2(
                    SW_FEATURE_FILLET_OPTIONS,
                    radius,
                    0.0,
                    0,
                    0,
                    0,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.InsertFeatureFillet(radius),
            ):
                try:
                    feature = call()
                    if feature is not None:
                        break
                except Exception as exc:
                    self.logs.append(f'fillet attempt failed for {node_id}: {exc}')
        else:
            distance = _as_m(params.get('distance', params.get('radius', 0.0)))
            feature = None

            def select_chamfer_edges(mark):
                self._clear_selection()
                for edge_index, edge in enumerate(selected):
                    if not self._select_entity(
                        edge, append=edge_index > 0, mark=mark
                    ):
                        return False
                return True

            def create_chamfer_from_definition():
                # CreateDefinition supports simple chamfers through
                # swFmFillet=1. The chamfer is the rho-zero profile
                # specialization of ISimpleFilletFeatureData2, not a
                # swFmChamfer definition. Tangent propagation stays disabled
                # so CADIR's explicit seed-edge set survives save/reopen.
                if not select_chamfer_edges(1):
                    return None
                definition = self.model.FeatureManager.CreateDefinition(1)
                if definition is None or not bool(definition.Initialize(0)):
                    return None
                definition.ConicTypeForCrossSectionProfile = 3
                definition.AsymmetricFillet = False
                definition.IsMultipleRadius = False
                definition.DefaultRadius = distance
                definition.OverflowType = 0
                definition.PropagateToTangentFaces = False
                definition.Edges = win32com.client.VARIANT(
                    pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH,
                    tuple(selected),
                )
                return self.model.FeatureManager.CreateFeature(definition)

            def insert_equal_distance_chamfer():
                if not select_chamfer_edges(0):
                    return None
                return self.model.FeatureManager.InsertFeatureChamfer(
                    0, 16, 0.0, 0.0, distance, 0.0, 0.0, 0.0
                )

            def insert_angle_distance_chamfer():
                if not select_chamfer_edges(0):
                    return None
                return self.model.FeatureManager.InsertFeatureChamfer(
                    0, 1, distance, math.pi / 4.0, 0.0, 0.0, 0.0, 0.0
                )

            strict_canonical = strict_canonical_result
            if strict_canonical is None:
                strict_canonical = (
                    self._detail_result_descriptor(
                        topology_source_node_id, topology_target_node_id
                    )
                    if topology_source_node_id and topology_target_node_id
                    else None
                )
            for attempt_name, call in (
                # CADIR serializes the complete seed-edge set. Keep tangent
                # propagation disabled (option bit 4) so SolidWorks does not
                # silently expand those seeds and destabilize the persisted
                # FeatureData references after reopen.
                ('equal_distance', insert_equal_distance_chamfer),
                # Equal legs are also representable by a 45-degree
                # angle-distance chamfer. This is an API compatibility retry,
                # still with the exact explicit seed set and no propagation.
                ('angle_distance_45', insert_angle_distance_chamfer),
                # Some SolidWorks releases reject InsertFeatureChamfer for
                # large disconnected seed sets. The rho-zero simple-fillet
                # definition is the documented offset-face chamfer fallback,
                # but it is not the first choice because its distance
                # convention can differ from an equal-distance edge chamfer
                # on non-orthogonal faces.
                ('rho_zero_feature_data', create_chamfer_from_definition),
            ):
                try:
                    candidate_feature = call()
                    if candidate_feature is None:
                        continue
                    try:
                        candidate_feature.Name = (
                            f'SimpleCAD_{node_id}_{kind}_{attempt_name}'
                        )
                    except Exception:
                        pass
                    try:
                        self.model.ForceRebuild3(False)
                    except Exception as exc:
                        self.logs.append(
                            f'{kind} rebuild call failed for {node_id} '
                            f'candidate {attempt_name}: {exc}'
                        )
                    candidate_error = None
                    for error_getter in ('GetErrorCode2', 'GetErrorCode'):
                        try:
                            candidate_error = int(
                                _maybe_call(
                                    getattr(candidate_feature, error_getter)
                                )
                            )
                            break
                        except Exception:
                            pass
                    candidate_result = self._capture_new_body(
                        before,
                        candidate_feature,
                        expected_bbox=source_bbox,
                        fallback_body=source,
                    )
                    candidate_volume = self._body_volume(candidate_result)
                    candidate_bbox = self._box_from_entity(candidate_result)
                    candidate_matches = (
                        not isinstance(strict_canonical, dict)
                        or self._body_matches_canonical(
                            candidate_result,
                            strict_canonical,
                            volume_relative_tolerance=3.0e-5,
                        )
                    )
                    source_volume = source_descriptor.get('volume')
                    candidate_changed = (
                        source_volume is None
                        or candidate_volume is None
                        or _relative_error(
                            candidate_volume,
                            source_volume,
                            floor=1.0e-12,
                        ) > 1.0e-10
                        or _bbox_score(
                            candidate_bbox,
                            source_descriptor.get('bbox'),
                        ) > 1.0e-9
                    )
                    if require_geometry_change and not candidate_changed:
                        candidate_matches = False
                    self.logs.append(
                        f'chamfer {node_id} candidate {attempt_name} '
                        f'volume={candidate_volume!r} bbox={candidate_bbox!r} '
                        f'feature_error={candidate_error!r} '
                        f'canonical_match={candidate_matches!r} '
                        f'geometry_changed={candidate_changed!r}'
                    )
                    if candidate_error in (None, 0) and candidate_matches:
                        feature = candidate_feature
                        result = candidate_result
                        feature_error = candidate_error
                        candidate_rebuilt = True
                        break
                    self._delete_retry_feature(
                        candidate_feature, kind, node_id
                    )
                    persistent_source = (
                        self._resolve_persistent_reference_bytes(
                            source_reference
                        )
                    )
                    if (
                        persistent_source is not None
                        and self._body_matches_canonical(
                            persistent_source, source_descriptor
                        )
                    ):
                        rebound_sources = [persistent_source]
                    else:
                        rebound_sources = [
                            body for body in self._solid_bodies()
                            if self._body_matches_canonical(
                                body, source_descriptor
                            )
                        ]
                        named_sources = [
                            body for body in rebound_sources
                            if self._body_name(body) == source_name
                        ]
                        if len(named_sources) == 1:
                            rebound_sources = named_sources
                    if len(rebound_sources) != 1:
                        raise RuntimeError(
                            f'{kind} {node_id} could not uniquely rebind the '
                            f'live input body after rejecting {attempt_name}; '
                            f'candidates={len(rebound_sources)}'
                        )
                    source = rebound_sources[0]
                    source_bbox = self._box_from_entity(source)
                    selected, retry_skipped = self._detail_selected_edges(
                        source, selectors, kind, node_id
                    )
                    if retry_skipped != skipped_seams:
                        raise RuntimeError(
                            f'{kind} {node_id} seam classification changed '
                            'while retrying native candidates'
                        )
                    before = self._body_names()
                except Exception as exc:
                    self.logs.append(
                        f'chamfer attempt {attempt_name} failed for '
                        f'{node_id}: {exc}'
                    )
                    if 'Could not delete rejected' in str(exc):
                        raise
        if feature is None:
            components = _selector_edge_components(selectors)
            if allow_component_fallback and len(components) > 1:
                self.logs.append(
                    f'{kind} {node_id} retrying {len(selectors)} selected edges '
                    f'as {len(components)} disconnected components'
                )
                current = source
                for component_index, component in enumerate(components):
                    current = self._apply_detail_feature_to_body(
                        current,
                        component,
                        params,
                        kind,
                        f'{node_id}_component_{component_index + 1}',
                        allow_component_fallback=False,
                        require_geometry_change=True,
                    )
                return current
            raise RuntimeError(
                f'SolidWorks {kind} feature creation failed; '
                f'selections={self._selection_state()!r}; logs={self.logs[-3:]!r}'
            )
        try:
            feature.Name = f'SimpleCAD_{node_id}_{kind}'
        except Exception:
            pass
        if not candidate_rebuilt:
            try:
                self.model.ForceRebuild3(False)
            except Exception as exc:
                self.logs.append(
                    f'{kind} rebuild call failed for {node_id}: {exc}'
                )
        if feature_error is None:
            for error_getter in ('GetErrorCode2', 'GetErrorCode'):
                try:
                    feature_error = int(
                        _maybe_call(getattr(feature, error_getter))
                    )
                    break
                except Exception:
                    pass
        if feature_error not in (None, 0):
            raise RuntimeError(
                f'SolidWorks {kind} feature {node_id} reports native '
                f'error code {feature_error}'
            )
        if result is None:
            result = self._capture_new_body(
                before,
                feature,
                expected_bbox=source_bbox,
                fallback_body=source,
            )
        self.logs.append(
            f'{kind} {node_id} native result volume={self._body_volume(result)!r} '
            f'bbox={self._box_from_entity(result)!r} '
            f'feature_error={feature_error!r}'
        )
        if topology_source_node_id and topology_target_node_id:
            self.pending_detail_topology.append({
                'feature': feature,
                'feature_name': str(
                    _maybe_call(feature.Name) or ''
                ),
                'result_body': result,
                'source_node_id': str(topology_source_node_id),
                'detail_node_id': str(topology_target_node_id),
            })
            self._capture_detail_feature_topology(
                feature,
                result,
                topology_source_node_id,
                topology_target_node_id,
            )
        return result

    def _feature_shell(self, params, inputs, node_id):
        upstream = self._body_from_value(self._first_output(inputs[0]))
        # Keep shell attached to the live upstream body for the same reason as
        # fillet/chamfer: an identity Move/Copy snapshot breaks downstream
        # propagation when an earlier native feature is edited after reopen.
        source = upstream
        source_bbox = self._box_from_entity(source)
        selectors = []
        for selector_id in params.get('selected_face_node_ids') or []:
            payload = self.selection_payloads.get(str(selector_id))
            if payload:
                selectors.append(payload.get('params') or {})
        if not selectors:
            for item in params.get('selected_faces') or []:
                if isinstance(item, dict):
                    selectors.append(item.get('selector_hint') or item)
        face_signatures = [
            (face, self._face_signature(face))
            for face in self._body_faces(source)
        ]
        faces = [
            _best_by_geometry(face_signatures, selector, 'face')
            for selector in selectors
        ]
        self._clear_selection()
        for index, face in enumerate(faces):
            if not self._select_entity(face, append=index > 0):
                raise RuntimeError('Could not select SolidWorks face for shell')
        before = self._body_names()
        thickness = _as_m(params.get('thickness', 0.0))
        feature = None
        for call in (
            lambda: self.model.FeatureManager.InsertShell(thickness, False),
            lambda: self.model.FeatureManager.InsertShell2(thickness, False),
        ):
            try:
                feature = call()
                if feature is not None:
                    break
            except Exception as exc:
                self.logs.append(f'shell attempt failed for {node_id}: {exc}')
        if feature is None:
            raise RuntimeError('SolidWorks shell feature creation failed')
        return self._capture_new_body(
            before, feature, expected_bbox=source_bbox
        )

    def _prune_to_bodies(self, final_bodies, retained_bodies=()):
        resolved = []
        seen_keys = set()
        for body in final_bodies:
            fresh = self._resolve_body_reference(body) or body
            key = self._body_geometry_key(fresh)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            resolved.append(fresh)

        retained = []
        for body in retained_bodies or ():
            fresh = self._resolve_body_reference(body) or body
            key = self._body_geometry_key(fresh)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            retained.append(fresh)

        all_bodies = self._solid_bodies()
        result_keys = {self._body_geometry_key(body) for body in resolved}
        keep_keys = {
            self._body_geometry_key(body) for body in resolved + retained
        }
        discard = [
            body for body in all_bodies
            if self._body_geometry_key(body) not in keep_keys
        ]
        if discard and resolved:
            self._clear_selection()
            selected = 0
            for body in resolved + retained:
                if self._select_entity(body, append=selected > 0):
                    selected += 1
            if selected == len(resolved) + len(retained):
                feature = None
                try:
                    feature = self.model.FeatureManager.InsertDeleteBody2(True)
                except Exception as exc:
                    self.logs.append(f'keep-body feature failed: {exc}')
                self._clear_selection()
                if feature is not None:
                    try:
                        feature.Name = 'SimpleCAD_KeepResultBodies'
                    except Exception:
                        pass
                    try:
                        self.model.ForceRebuild3(False)
                    except Exception:
                        pass
                    remaining = self._solid_bodies()
                    remaining_keys = {
                        self._body_geometry_key(body) for body in remaining
                    }
                    extras = remaining_keys - keep_keys
                    if remaining and not extras:
                        remaining_results = [
                            body for body in remaining
                            if self._body_geometry_key(body) in result_keys
                        ]
                        if len(remaining_results) == len(result_keys):
                            return remaining_results
                        self.logs.append(
                            'keep-body feature could not resolve all result '
                            'bodies after retaining assembly sources'
                        )
                    self.logs.append(
                        f'keep-body feature left {len(extras)} intermediate bodies'
                    )
            else:
                self.logs.append(
                    f'could not select all final bodies for pruning: '
                    f'{selected}/{len(resolved) + len(retained)}'
                )
                self._clear_selection()

        for body in all_bodies:
            hide = self._body_geometry_key(body) not in keep_keys
            try:
                body.HideBody(bool(hide))
            except Exception as exc:
                if hide:
                    try:
                        body.Hide(self.model)
                    except Exception:
                        self.logs.append(f'could not hide intermediate body: {exc}')
        self._clear_selection()
        return resolved

    def _restore_model_scale(self, final_bodies, retained_bodies=()):
        if MODEL_SCALE <= 1.0 + 1.0e-12:
            return final_bodies
        self._clear_selection()
        selected = 0
        for body in final_bodies:
            if self._select_entity(body, append=selected > 0):
                selected += 1
        factor = 1.0 / MODEL_SCALE
        feature = None
        if selected == len(final_bodies):
            try:
                feature = self.model.FeatureManager.InsertScale(
                    1, True, factor, factor, factor
                )
            except Exception as exc:
                self.logs.append(f'combined final scale failed: {exc}')
        else:
            self.logs.append(
                f'combined final scale could not select all result bodies: '
                f'{selected}/{len(final_bodies)}; using per-body transform'
            )
        self._clear_selection()
        if feature is None:
            self._mark_degraded(
                'SimpleCAD_RestoreModelScale', 'static_scale'
            )
            scale_matrix = _identity_matrix()
            scale_matrix[12] = factor
            scaled_bodies = []
            for index, body in enumerate(final_bodies):
                temp_body = self._copy_temp_body(body)
                self._apply_transform_to_temp_body(temp_body, scale_matrix)
                scaled_bodies.append(
                    self._create_feature_from_body(
                        temp_body,
                        f'SimpleCAD_RestoreModelScale_{index + 1}',
                    )
                )
            if not scaled_bodies:
                raise RuntimeError(
                    'SolidWorks failed to restore the canonical model scale'
                )
            return self._prune_to_bodies(
                scaled_bodies, retained_bodies=retained_bodies
            )
        try:
            feature.Name = 'SimpleCAD_RestoreModelScale'
        except Exception:
            pass
        try:
            self.model.ForceRebuild3(False)
        except Exception:
            pass
        bodies = self._solid_bodies()
        result_names = {
            self._body_name(body) for body in final_bodies
        }
        resolved = [
            body for body in bodies
            if self._body_name(body) in result_names
        ]
        return resolved if len(resolved) == len(result_names) else final_bodies
'''


def translate_model_json_to_solidworks_script(
    json_str: str,
    document_name: str = "SimpleCADModel",
    *,
    output_path: Optional[str] = None,
    visible: bool = False,
    source_kernel_fallback: bool = False,
) -> str:
    """Translate exported model JSON into a SolidWorks Python automation script.

    The generated script traverses the canonical operation graph and maps graph
    operations to SolidWorks COM API calls. Detail-feature selections use
    geometric signatures rather than stored topology indices.
    """

    return SolidWorksScriptTranslator(
        document_name=document_name,
        visible=visible,
        source_kernel_fallback=source_kernel_fallback,
    ).translate_model_json_to_script(json_str, output_path=output_path)


def translate_model_json_to_solidworks_step(
    json_str: str,
    output_path: str,
    *,
    document_name: str = "SimpleCADModel",
    visible: bool = False,
    python_exe: Optional[str] = None,
    source_kernel_fallback: bool = False,
) -> str:
    """Run SolidWorks COM automation and export a STEP file."""

    import subprocess

    resolved_output_path = os.path.abspath(output_path)
    script = translate_model_json_to_solidworks_script(
        json_str,
        document_name=document_name,
        output_path=resolved_output_path,
        visible=visible,
        source_kernel_fallback=source_kernel_fallback,
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_simplecad_solidworks_export.py", delete=False, encoding="utf-8"
    ) as handle:
        temp_script_path = handle.name
        handle.write(script)

    env = os.environ.copy()
    src_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    env["PYTHONPATH"] = (
        src_root
        if not env.get("PYTHONPATH")
        else src_root + os.pathsep + env["PYTHONPATH"]
    )

    try:
        try:
            completed = subprocess.run(
                [python_exe or sys.executable, temp_script_path],
                check=True,
                text=True,
                capture_output=True,
                env=env,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "SolidWorks export script failed. "
                f"stdout={exc.stdout!r} stderr={exc.stderr!r}"
            ) from exc
        if not os.path.exists(resolved_output_path) or os.path.getsize(resolved_output_path) <= 0:
            raise RuntimeError(
                "SolidWorks export completed without creating a non-empty STEP file. "
                f"stdout={completed.stdout.strip()!r} stderr={completed.stderr.strip()!r}"
            )
        return output_path
    except Exception as e:
        raise_harness_error(
            operation="translate_model_json_to_solidworks_step",
            what_happened="Failed to execute the generated SolidWorks export script.",
            possible_causes=[
                "SolidWorks is not installed, not licensed, or its COM server is not registered.",
                "pywin32 is unavailable in the Python interpreter used for the export.",
                "The model JSON contains an operation not yet mapped to a stable SolidWorks COM call.",
                "SolidWorks rejected a native feature, geometric selection, body boolean, or STEP SaveAs call.",
            ],
            how_to_fix=[
                "Open SolidWorks once interactively and confirm it can create and save parts.",
                "Inspect the generated script with translate_model_json_to_solidworks_script().",
                "Run the same script manually with the same Python interpreter to inspect COM errors.",
            ],
            error=e,
        )
    finally:
        try:
            os.unlink(temp_script_path)
        except OSError:
            pass
