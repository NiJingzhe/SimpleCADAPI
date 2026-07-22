"""BRep tracking layer for capturing operation history via OCC Modified/Generated/IsDeleted.

This module wraps OCC builders directly (not through CadQuery's ``_bool_op`` which
discards the builder).  It preserves the builder object so that ``Modified()``,
``Generated()``, ``IsDeleted()``, and ``SectionEdges()`` can be queried for each
input subshape, producing a :class:`TopoDelta` that records exactly what happened
topologically.

Supported operations:
- Boolean: cut, union (fuse), intersect (common)
- Transforms: translate, rotate
- Features: extrude, fillet, chamfer
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

from OCP.BRepAlgoAPI import (
    BRepAlgoAPI_Cut,
    BRepAlgoAPI_Common,
    BRepAlgoAPI_BooleanOperation,
)
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_Transform,
    BRepBuilderAPI_MakeShape,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepFill import BRepFill_TypeOfContact
from OCP.BRepLib import BRepLib
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
from OCP.BRepFilletAPI import (
    BRepFilletAPI_MakeFillet,
    BRepFilletAPI_MakeChamfer,
)
from OCP.BRepOffsetAPI import (
    BRepOffsetAPI_MakePipeShell,
    BRepOffsetAPI_MakeThickSolid,
    BRepOffsetAPI_ThruSections,
)
from OCP.BRepOffset import BRepOffset_Skin
from OCP.GeomAbs import GeomAbs_Arc, GeomAbs_Plane
from OCP.GCE2d import GCE2d_MakeSegment
from OCP.Geom import Geom_CylindricalSurface
from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt, gp_Pnt2d, gp_Vec
from OCP.TopTools import TopTools_ListOfShape
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopAbs import (
    TopAbs_COMPOUND,
    TopAbs_EDGE,
    TopAbs_FACE,
    TopAbs_SOLID,
    TopAbs_VERTEX,
    TopAbs_WIRE,
)
from OCP.TopoDS import TopoDS

from .core import Solid, Face, Edge, Vertex
from .kernel.ocp_booleans import fuse_shapes_with_history, solids_of
from .kernel.ocp_builders import (
    build_box_primitive,
    build_cone_primitive,
    build_cylinder_primitive,
)
from .topology import (
    TopoKind,
    TopoEvent,
    TopoRef,
    TopoDelta,
    TopoEntry,
    TopoRoleEntry,
    _make_id,
)


class TrackingPolicy(str, Enum):
    """Controls how much topology provenance an operation computes."""

    FULL = "full"
    GRAPH = "graph"


@dataclass
class TrackedBooleanResult:
    """Result of a tracked boolean operation.

    Attributes:
        solid:        The resulting SimpleCADAPI Solid (or ``None`` on failure).
        delta:        Complete topological change set.
        delta_entries: Per-entity metadata dict keyed by ``topo_id``.
    """

    solid: Optional[Solid]
    delta: TopoDelta
    delta_entries: Dict[str, Dict[str, Any]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _topo_id(shape) -> str:
    """Stable-ish string identifier for an OCC TopoDS_Shape.

    Uses TShape pointer + Location hash for uniqueness within a single build.
    """
    try:
        return f"{shape.HashCode(1000000)}"
    except AttributeError:
        return f"{hash(shape)}"


def _iter_subshapes(shape, shape_type: int):
    """Yield all subshapes of a given type from an OCC shape."""
    explorer = TopExp_Explorer(shape, shape_type)
    while explorer.More():
        yield explorer.Current()
        explorer.Next()


def _shape_kind(shape, fallback: TopoKind) -> TopoKind:
    """Return the actual topology kind of a kernel history output."""

    try:
        return {
            TopAbs_VERTEX: TopoKind.VERTEX,
            TopAbs_EDGE: TopoKind.EDGE,
            TopAbs_WIRE: TopoKind.WIRE,
            TopAbs_FACE: TopoKind.FACE,
            TopAbs_SOLID: TopoKind.SOLID,
            TopAbs_COMPOUND: TopoKind.COMPOUND,
        }.get(shape.ShapeType(), fallback)
    except Exception:
        return fallback


def _tolist_oftools(shapes) -> TopTools_ListOfShape:
    """Convert a Python list of TopoDS_Shape to TopTools_ListOfShape."""
    tl = TopTools_ListOfShape()
    for s in shapes:
        tl.Append(s)
    return tl


def _is_same_shape(left: Any, right: Any) -> bool:
    try:
        return bool(left.IsSame(right))
    except Exception:
        return False


def _is_result_member(result_shape: Any, candidate: Any) -> bool:
    """Return whether ``candidate`` is an exact subshape of ``result_shape``."""

    try:
        if candidate.IsNull():
            return False
    except Exception:
        return False
    if _is_same_shape(result_shape, candidate):
        return True
    try:
        shape_type = candidate.ShapeType()
    except Exception:
        return False
    return any(_is_same_shape(item, candidate) for item in _iter_subshapes(result_shape, shape_type))


def _dedupe_shapes(shapes: Iterable[Any]) -> List[Any]:
    result: List[Any] = []
    for shape in shapes:
        if not any(_is_same_shape(shape, existing) for existing in result):
            result.append(shape)
    return result


def _query_exact_history(
    builder: Any,
    input_shapes: Iterable[Any],
    graph_id: str,
    node_id: str,
    origin_role: str,
    kind: TopoKind,
    *,
    modified_derivation: str = "fragment",
    generated_derivation: str = "boundary",
    result_shape: Any = None,
    result_role: Optional[str] = None,
    preserved_result_role: Optional[str] = None,
    modified_result_role: Optional[str] = None,
    generated_result_role: Optional[str] = None,
    project_source_tags: bool = False,
) -> Tuple[
    List[TopoRef], List[TopoRef], List[TopoRef], List[TopoRef], List[Dict[str, Any]]
]:
    """Query Modified/Generated/IsDeleted for every subshape of ``input_solid``.

    Returns five lists: ``preserved, modified, generated, deleted`` as ``TopoRef``
    lists, plus a list of per-entity metadata dicts.
    """
    preserved: List[TopoRef] = []
    modified: List[TopoRef] = []
    generated: List[TopoRef] = []
    deleted: List[TopoRef] = []
    entries: List[Dict[str, Any]] = []

    for sub in _dedupe_shapes(input_shapes):
        input_id = _topo_id(sub)

        if hasattr(builder, "IsDeleted"):
            is_deleted = bool(builder.IsDeleted(sub))
        else:
            is_deleted = bool(builder.IsRemoved(sub))
        if is_deleted:
            ref = TopoRef(graph_id, node_id, 0, kind, input_id)
            deleted.append(ref)
            entries.append(
                {
                    "topo_id": input_id,
                    "event": "deleted",
                    "kind": kind.name,
                    "source_kind": kind.name,
                    "origin_role": origin_role,
                    "input_topo_id": input_id,
                    "derivation": "replacement",
                    "coverage": "complete",
                    "status": "proven",
                }
            )
        mod_list = builder.Modified(sub)
        gen_list = builder.Generated(sub)

        mod_size = mod_list.Size() if hasattr(mod_list, "Size") else 0
        gen_size = gen_list.Size() if hasattr(gen_list, "Size") else 0

        # Check if Modified returns the exact same shape (no actual change)
        same_shape_in_mod = False
        if mod_size == 1:
            try:
                first_mod = mod_list.First()
                same_shape_in_mod = first_mod.IsSame(sub)
            except Exception:
                pass

        # Case 1: No modifications, no generations -> PRESERVED
        source_survives = result_shape is None or _is_result_member(result_shape, sub)
        if not is_deleted and mod_size == 0 and gen_size == 0 and source_survives:
            ref = TopoRef(graph_id, node_id, 0, kind, input_id)
            preserved.append(ref)
            entry = {
                "topo_id": input_id,
                "event": "preserved",
                "kind": kind.name,
                "source_kind": kind.name,
                "origin_role": origin_role,
                "input_topo_id": input_id,
                "derivation": "continuation",
                "coverage": "complete",
                "status": "proven",
            }
            role = preserved_result_role or result_role
            if role is not None:
                entry["result_role"] = role
            if project_source_tags:
                entry["project_source_tags"] = True
            entries.append(entry)
            continue

        # Case 2: Modified returns the same shape and no generations -> PRESERVED
        if not is_deleted and same_shape_in_mod and gen_size == 0:
            ref = TopoRef(graph_id, node_id, 0, kind, input_id)
            preserved.append(ref)
            entry = {
                "topo_id": input_id,
                "event": "preserved",
                "kind": kind.name,
                "source_kind": kind.name,
                "origin_role": origin_role,
                "input_topo_id": input_id,
                "derivation": "continuation",
                "coverage": "complete",
                "status": "proven",
            }
            role = preserved_result_role or result_role
            if role is not None:
                entry["result_role"] = role
            if project_source_tags:
                entry["project_source_tags"] = True
            entries.append(entry)
            continue

        # Case 3: Has modifications (different or multiple shapes) -> MODIFIED
        if mod_size > 0 and not same_shape_in_mod:
            for mod_shape in mod_list:
                if result_shape is not None and not _is_result_member(
                    result_shape, mod_shape
                ):
                    continue
                mod_id = _topo_id(mod_shape)
                output_kind = _shape_kind(mod_shape, kind)
                ref = TopoRef(graph_id, node_id, 0, output_kind, mod_id)
                modified.append(ref)
                entry = {
                        "topo_id": mod_id,
                        "event": "modified",
                        "kind": output_kind.name,
                        "source_kind": kind.name,
                        "origin_role": origin_role,
                        "input_topo_id": input_id,
                        "derivation": modified_derivation,
                        "coverage": "complete",
                        "status": "proven",
                    }
                role = modified_result_role or result_role
                if role is not None:
                    entry["result_role"] = role
                if project_source_tags:
                    entry["project_source_tags"] = True
                entries.append(entry)

        # Case 4: Has generated new shapes -> GENERATED
        if gen_size > 0:
            for gen_shape in gen_list:
                if result_shape is not None and not _is_result_member(
                    result_shape, gen_shape
                ):
                    continue
                gen_id = _topo_id(gen_shape)
                output_kind = _shape_kind(gen_shape, kind)
                ref = TopoRef(graph_id, node_id, 0, output_kind, gen_id)
                generated.append(ref)
                entry = {
                        "topo_id": gen_id,
                        "event": "generated",
                        "kind": output_kind.name,
                        "source_kind": kind.name,
                        "origin_role": origin_role,
                        "input_topo_id": input_id,
                        "derivation": generated_derivation,
                        "coverage": "complete",
                        "status": "proven",
                    }
                role = generated_result_role or result_role
                if role is not None:
                    entry["result_role"] = role
                if project_source_tags:
                    entry["project_source_tags"] = True
                entries.append(entry)

    return preserved, modified, generated, deleted, entries


def _query_history(
    builder: Any,
    input_solid,
    graph_id: str,
    node_id: str,
    origin_role: str,
    kind: TopoKind,
    shape_type: int,
    **kwargs: Any,
) -> Tuple[
    List[TopoRef], List[TopoRef], List[TopoRef], List[TopoRef], List[Dict[str, Any]]
]:
    return _query_exact_history(
        builder,
        _iter_subshapes(input_solid, shape_type),
        graph_id,
        node_id,
        origin_role,
        kind,
        **kwargs,
    )


def _query_shape_list_history(
    builder: BRepBuilderAPI_MakeShape,
    shapes: Iterable[Any],
    graph_id: str,
    node_id: str,
    origin_role: str,
    kind: TopoKind,
    *,
    result_shape: Any,
    modified_derivation: str = "fragment",
    generated_derivation: str = "boundary",
    result_role: Optional[str] = None,
    project_source_tags: bool = False,
) -> Tuple[
    List[TopoRef], List[TopoRef], List[TopoRef], List[TopoRef], List[Dict[str, Any]]
]:
    """Query history for an exact shape list without topology traversal."""

    return _query_exact_history(
        builder,
        shapes,
        graph_id,
        node_id,
        origin_role,
        kind,
        modified_derivation=modified_derivation,
        generated_derivation=generated_derivation,
        result_shape=result_shape,
        result_role=result_role,
        project_source_tags=project_source_tags,
    )


def kind_to_topabs(kind: TopoKind) -> int:
    return {
        TopoKind.VERTEX: TopAbs_VERTEX,
        TopoKind.EDGE: TopAbs_EDGE,
        TopoKind.WIRE: TopAbs_WIRE,
        TopoKind.FACE: TopAbs_FACE,
        TopoKind.SOLID: TopAbs_SOLID,
        TopoKind.COMPOUND: TopAbs_COMPOUND,
    }[kind]


def _operation_role(
    candidate: Any,
    *,
    result_shape: Any,
    graph_id: str,
    node_id: str,
    role: str,
    evidence_method: str,
    origin_role: Optional[str] = None,
    source_shape: Any = None,
    source_kind: Optional[TopoKind] = None,
) -> Optional[Dict[str, Any]]:
    if not _is_result_member(result_shape, candidate):
        return None
    output_kind = _shape_kind(candidate, TopoKind.FACE)
    payload: Dict[str, Any] = {
        "topo_id": _topo_id(candidate),
        "kind": output_kind.name,
        "role": role,
        "origin_role": origin_role,
        "coverage": "complete",
        "status": "proven",
        "evidence_kind": "kernel_operation_role",
        "evidence_method": evidence_method,
    }
    if source_shape is not None:
        payload["input_topo_id"] = _topo_id(source_shape)
        payload["source_kind"] = (source_kind or _shape_kind(source_shape, output_kind)).name
    return payload


def _canonical_topo_roles(
    roles: List[Dict[str, Any]], *, graph_id: str, node_id: str
) -> Tuple[TopoRoleEntry, ...]:
    result: List[TopoRoleEntry] = []
    seen = set()
    for item in roles:
        try:
            output_kind = TopoKind[str(item["kind"]).upper()]
            output_id = str(item["topo_id"])
            role = str(item["role"])
        except (KeyError, TypeError, ValueError):
            continue
        source_kind_name = item.get("source_kind")
        source_id = item.get("input_topo_id")
        parents: Tuple[TopoRef, ...] = ()
        if source_id is not None and source_kind_name is not None:
            try:
                source_kind = TopoKind[str(source_kind_name).upper()]
            except KeyError:
                continue
            parents = (
                TopoRef(graph_id, node_id, 0, source_kind, str(source_id)),
            )
        marker = (output_kind, output_id, role, parents)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(
            TopoRoleEntry(
                ref=TopoRef(graph_id, node_id, 0, output_kind, output_id),
                role=role,
                origin_role=(
                    str(item["origin_role"])
                    if item.get("origin_role") is not None
                    else None
                ),
                parent_refs=parents,
                metadata={
                    "coverage": str(item.get("coverage", "complete")),
                    "status": str(item.get("status", "proven")),
                    "evidence_kind": str(
                        item.get("evidence_kind", "kernel_operation_role")
                    ),
                    "evidence_method": str(item.get("evidence_method", "unknown")),
                    **(
                        {"source_kind": str(source_kind_name).upper()}
                        if source_kind_name is not None
                        else {}
                    ),
                },
            )
        )
    return tuple(result)


def _roles_from_history(
    entries: Iterable[Dict[str, Any]], *, evidence_method: str
) -> List[Dict[str, Any]]:
    roles: List[Dict[str, Any]] = []
    for item in entries:
        role = item.get("result_role")
        if role is None:
            continue
        roles.append(
            {
                "topo_id": item["topo_id"],
                "kind": item["kind"],
                "role": role,
                "origin_role": item.get("origin_role"),
                "input_topo_id": item.get("input_topo_id"),
                "source_kind": item.get("source_kind"),
                "coverage": item.get("coverage", "complete"),
                "status": item.get("status", "proven"),
                "evidence_kind": "kernel_operation_role",
                "evidence_method": evidence_method,
            }
        )
    return roles


def _actual_contour_edges(builder: Any, seeds: Iterable[Edge]) -> List[Any]:
    """Expand fillet/chamfer seed edges to the contours OCC actually used."""

    result: List[Any] = []
    seen_contours = set()
    for seed in seeds:
        contour = int(builder.Contour(seed.wrapped))
        if contour <= 0 or contour in seen_contours:
            continue
        seen_contours.add(contour)
        for index in range(1, int(builder.NbEdges(contour)) + 1):
            result.append(builder.Edge(contour, index))
    return _dedupe_shapes(result)


def _canonical_topo_entries(
    entries: List[Dict[str, Any]], *, graph_id: str, node_id: str
) -> Tuple[TopoEntry, ...]:
    """Convert kernel-history witnesses into the canonical typed delta model."""

    event_map = {
        "preserved": TopoEvent.PRESERVED,
        "modified": TopoEvent.MODIFIED,
        "generated": TopoEvent.GENERATED,
        "deleted": TopoEvent.DELETED,
    }
    result: List[TopoEntry] = []
    for item in entries:
        event = event_map.get(str(item.get("event", "")).lower())
        if event is None:
            continue
        try:
            output_kind = TopoKind[str(item.get("kind", "FACE")).upper()]
            source_kind = TopoKind[
                str(item.get("source_kind", output_kind.name)).upper()
            ]
            output_id = str(item["topo_id"])
        except (KeyError, TypeError, ValueError):
            continue

        input_id = item.get("input_topo_id")
        parents = (
            (
                TopoRef(
                    graph_id=graph_id,
                    node_id=node_id,
                    output_slot=0,
                    kind=source_kind,
                    topo_id=str(input_id),
                ),
            )
            if input_id is not None
            else ()
        )
        result.append(
            TopoEntry(
                ref=TopoRef(graph_id, node_id, 0, output_kind, output_id),
                event=event,
                origin_role=(
                    str(item["origin_role"])
                    if item.get("origin_role") is not None
                    else None
                ),
                parent_refs=parents,
                metadata={
                    "derivation": str(item.get("derivation", "unknown")),
                    "coverage": str(item.get("coverage", "complete")),
                    "status": str(item.get("status", "proven")),
                    "evidence_kind": "kernel_history",
                    "source_kind": source_kind.name,
                    **(
                        {"result_role": str(item["result_role"])}
                        if item.get("result_role") is not None
                        else {}
                    ),
                    **(
                        {"project_source_tags": True}
                        if item.get("project_source_tags")
                        else {}
                    ),
                },
            )
        )
    return tuple(result)


def _aggregate_delta_entries(
    entries: List[Dict[str, Any]],
    roles: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Build the compatibility lookup without discarding multi-source witnesses."""

    result: Dict[str, Dict[str, Any]] = {}
    for item in entries:
        topo_id = str(item["topo_id"])
        witness = dict(item)
        aggregate = result.setdefault(
            topo_id,
            {
                "topo_id": topo_id,
                "kind": item.get("kind"),
                "event": item.get("event"),
                "origin_role": item.get("origin_role"),
                "input_topo_id": item.get("input_topo_id"),
                "derivation": item.get("derivation", "unknown"),
                "coverage": item.get("coverage", "complete"),
                "status": item.get("status", "proven"),
                "witnesses": [],
            },
        )
        aggregate["witnesses"].append(witness)
        aggregate["events"] = sorted(
            {
                str(entry["event"])
                for entry in aggregate["witnesses"]
                if entry.get("event") is not None
            }
        )
        aggregate["origin_roles"] = sorted(
            {
                str(entry["origin_role"])
                for entry in aggregate["witnesses"]
                if entry.get("origin_role") is not None
            }
        )
        if any(
            str(entry.get("coverage", "complete")) != "complete"
            for entry in aggregate["witnesses"]
        ):
            aggregate["coverage"] = "partial"
        if any(
            str(entry.get("status", "proven")) != "proven"
            for entry in aggregate["witnesses"]
        ):
            aggregate["status"] = "unknown"
    for item in roles or []:
        topo_id = str(item["topo_id"])
        role_witness = {
            "kind": item.get("kind"),
            "result_role": item.get("role"),
            "origin_role": item.get("origin_role"),
            "input_topo_id": item.get("input_topo_id"),
            "source_kind": item.get("source_kind"),
            "coverage": item.get("coverage", "complete"),
            "status": item.get("status", "proven"),
            "evidence_kind": item.get("evidence_kind", "kernel_operation_role"),
            "evidence_method": item.get("evidence_method"),
        }
        aggregate = result.setdefault(
            topo_id,
            {
                "topo_id": topo_id,
                "kind": item.get("kind"),
                "event": None,
                "origin_role": item.get("origin_role"),
                "input_topo_id": item.get("input_topo_id"),
                "derivation": "unknown",
                "coverage": item.get("coverage", "complete"),
                "status": item.get("status", "proven"),
                "witnesses": [],
            },
        )
        aggregate["witnesses"].append(role_witness)
        aggregate["result_roles"] = sorted(
            {
                str(witness["result_role"])
                for witness in aggregate["witnesses"]
                if witness.get("result_role") is not None
            }
        )
    return result


def _collect_section_edges(
    builder: BRepAlgoAPI_BooleanOperation,
    graph_id: str,
    node_id: str,
) -> List[TopoRef]:
    """Collect section (intersection) edges from a boolean builder."""
    section_refs: List[TopoRef] = []
    try:
        sec_list = builder.SectionEdges()
        for edge_shape in sec_list:
            eid = _topo_id(edge_shape)
            section_refs.append(TopoRef(graph_id, node_id, 0, TopoKind.EDGE, eid))
    except Exception:
        pass
    return section_refs


def _build_boolean_result(
    builder: BRepAlgoAPI_BooleanOperation,
    body: Solid,
    tool: Solid,
    op: str,
) -> TrackedBooleanResult:
    """Common post-build logic for boolean operations."""
    graph_id = _make_id("g")
    node_id = _make_id("n")

    result_shape = builder.Shape()

    # Wrap as SimpleCADAPI Solid directly from the OCP TopoDS result.
    try:
        result_solid = Solid(result_shape)
    except Exception:
        if hasattr(result_shape, "Solids") and result_shape.Solids():
            result_solid = Solid(result_shape.Solids()[0])
        else:
            result_solid = None

    # Query face-level history for body
    b_pres, b_mod, b_gen, b_del, b_entries = _query_history(
        builder,
        body.wrapped,
        graph_id,
        node_id,
        "body",
        TopoKind.FACE,
        TopAbs_FACE,
        result_shape=result_shape,
        project_source_tags=True,
    )
    # Query face-level history for tool
    t_pres, t_mod, t_gen, t_del, t_entries = _query_history(
        builder,
        tool.wrapped,
        graph_id,
        node_id,
        "tool",
        TopoKind.FACE,
        TopAbs_FACE,
        result_shape=result_shape,
        project_source_tags=True,
    )

    # Section edges
    section_edges = _collect_section_edges(builder, graph_id, node_id)

    delta = TopoDelta(
        preserved=tuple(b_pres + t_pres),
        modified=tuple(b_mod + t_mod),
        generated=tuple(b_gen + t_gen),
        deleted=tuple(b_del + t_del),
        section_edges=tuple(section_edges),
        entries=_canonical_topo_entries(
            b_entries + t_entries, graph_id=graph_id, node_id=node_id
        ),
    )

    all_entries = _aggregate_delta_entries(b_entries + t_entries)

    return TrackedBooleanResult(
        solid=result_solid,
        delta=delta,
        delta_entries=all_entries,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def tracked_cut(body: Solid, tool: Solid) -> TrackedBooleanResult:
    """Perform a boolean cut with full face-level history tracking.

    Args:
        body: The base solid.
        tool: The solid to subtract.

    Returns:
        :class:`TrackedBooleanResult` with the cut solid and topological delta.
    """
    cut_op = BRepAlgoAPI_Cut()
    cut_op.SetRunParallel(True)
    cut_op.SetUseOBB(True)
    cut_op.SetToFillHistory(True)

    args = TopTools_ListOfShape()
    args.Append(body.wrapped)
    tools = TopTools_ListOfShape()
    tools.Append(tool.wrapped)

    cut_op.SetArguments(args)
    cut_op.SetTools(tools)
    cut_op.Build()

    if not cut_op.IsDone():
        raise ValueError("Boolean cut failed: OCC build did not complete")

    return _build_boolean_result(cut_op, body, tool, "cut")


def tracked_union(
    body: Solid, tool: Solid, glue: bool = True, tol: float = 1e-7
) -> TrackedBooleanResult:
    """Perform a boolean union with full face-level history tracking.

    Args:
        body: First solid.
        tool: Second solid.
        glue: Enable glue mode.
        tol: Fuzzy tolerance.

    Returns:
        :class:`TrackedBooleanResult` with the fused solid and topological delta.
    """
    fused = fuse_shapes_with_history(
        [body.wrapped, tool.wrapped],
        glue=glue,
        tol=tol,
        clean=False,
    )
    result_solids = solids_of(fused.shape)
    if len(result_solids) != 1:
        raise ValueError("Boolean union did not produce exactly one solid")
    return track_union_history(
        [body, tool],
        Solid(result_solids[0]),
        fused.history,
        fused.section_edges,
    )


def track_union_history(
    solids: Iterable[Solid],
    result_solid: Solid,
    history: Any,
    section_edges: Iterable[Any] = (),
) -> TrackedBooleanResult:
    """Build one face-level union delta from retained N-ary OCC history."""

    inputs = list(solids)
    if len(inputs) < 2:
        raise ValueError("Union history tracking requires at least two solids")

    graph_id = _make_id("g")
    node_id = _make_id("n")
    preserved: List[TopoRef] = []
    modified: List[TopoRef] = []
    generated: List[TopoRef] = []
    deleted: List[TopoRef] = []
    history_entries: List[Dict[str, Any]] = []

    for index, solid in enumerate(inputs):
        origin_role = "body" if index == 0 else ("tool" if index == 1 else f"tool_{index}")
        pres, mod, gen, del_, entries = _query_history(
            history,
            solid.wrapped,
            graph_id,
            node_id,
            origin_role,
            TopoKind.FACE,
            TopAbs_FACE,
            result_shape=result_solid.wrapped,
            project_source_tags=True,
        )
        preserved.extend(pres)
        modified.extend(mod)
        generated.extend(gen)
        deleted.extend(del_)
        history_entries.extend(entries)

    section_refs = tuple(
        TopoRef(graph_id, node_id, 0, TopoKind.EDGE, _topo_id(edge))
        for edge in _dedupe_shapes(section_edges)
        if _is_result_member(result_solid.wrapped, edge)
    )
    delta = TopoDelta(
        preserved=tuple(preserved),
        modified=tuple(modified),
        generated=tuple(generated),
        deleted=tuple(deleted),
        section_edges=section_refs,
        entries=_canonical_topo_entries(
            history_entries,
            graph_id=graph_id,
            node_id=node_id,
        ),
    )
    return TrackedBooleanResult(
        solid=result_solid,
        delta=delta,
        delta_entries=_aggregate_delta_entries(history_entries),
    )


def tracked_intersect(body: Solid, tool: Solid) -> TrackedBooleanResult:
    """Perform a boolean intersection with full face-level history tracking.

    Args:
        body: First solid.
        tool: Second solid.

    Returns:
        :class:`TrackedBooleanResult` with the intersection solid and topological delta.
    """
    common_op = BRepAlgoAPI_Common()
    common_op.SetRunParallel(True)
    common_op.SetUseOBB(True)
    common_op.SetToFillHistory(True)

    args = TopTools_ListOfShape()
    args.Append(body.wrapped)
    tools = TopTools_ListOfShape()
    tools.Append(tool.wrapped)

    common_op.SetArguments(args)
    common_op.SetTools(tools)
    common_op.Build()

    if not common_op.IsDone():
        raise ValueError("Boolean intersect failed: OCC build did not complete")

    return _build_boolean_result(common_op, body, tool, "intersect")


# ---------------------------------------------------------------------------
# Generalized result + single-shape history
# ---------------------------------------------------------------------------


@dataclass
class TrackedResult:
    """Result of a tracked single-shape operation (transform, extrude, fillet…).

    Attributes:
        shape:  The resulting SimpleCADAPI shape (``Solid``, ``Face``, etc.) or ``None``.
        delta:  Topological change set.
        delta_entries: Per-entity metadata dict keyed by ``topo_id``.
    """

    shape: Optional[Solid]
    delta: TopoDelta
    delta_entries: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def _query_single_shape_history(
    builder: BRepBuilderAPI_MakeShape,
    input_solid,
    graph_id: str,
    node_id: str,
    op: str,
) -> Tuple[TopoDelta, Dict[str, Dict[str, Any]]]:
    """Query per-face kernel history for a single-input operation."""
    continuation = op in {"translate", "rotate", "mirror"}
    pres, mod, gen, del_, entries = _query_history(
        builder,
        input_solid,
        graph_id,
        node_id,
        "body",
        TopoKind.FACE,
        TopAbs_FACE,
        modified_derivation="continuation" if continuation else "fragment",
        result_shape=builder.Shape(),
    )
    delta = TopoDelta(
        preserved=tuple(pres),
        modified=tuple(mod),
        generated=tuple(gen),
        deleted=tuple(del_),
        entries=_canonical_topo_entries(
            entries, graph_id=graph_id, node_id=node_id
        ),
    )
    return delta, _aggregate_delta_entries(entries)


# ---------------------------------------------------------------------------
# Transform tracking
# ---------------------------------------------------------------------------

import numpy as np


def tracked_translate(
    shape: Solid, vector: Tuple[float, float, float]
) -> TrackedResult:
    """Translate a solid with face-level history tracking.

    Args:
        shape: Solid to translate.
        vector: Translation vector ``(dx, dy, dz)``.

    Returns:
        :class:`TrackedResult` with the translated solid and topological delta.
    """
    graph_id = _make_id("g")
    node_id = _make_id("n")

    gp_vec = gp_Vec(*vector)
    from OCP.gp import gp_Trsf

    trsf = gp_Trsf()
    trsf.SetTranslation(gp_vec)

    xform = BRepBuilderAPI_Transform(shape.wrapped, trsf, True)
    xform.Build()

    if not xform.IsDone():
        raise ValueError("Translate failed: OCC build did not complete")

    result_solid = Solid(xform.Shape())

    delta, entries = _query_single_shape_history(
        xform,
        shape.wrapped,
        graph_id,
        node_id,
        "translate",
    )

    return TrackedResult(shape=result_solid, delta=delta, delta_entries=entries)


def tracked_rotate(
    shape: Solid,
    angle_degrees: float,
    axis: Tuple[float, float, float] = (0, 0, 1),
    origin: Tuple[float, float, float] = (0, 0, 0),
) -> TrackedResult:
    """Rotate a solid with face-level history tracking.

    Args:
        shape: Solid to rotate.
        angle_degrees: Rotation angle in degrees.
        axis: Rotation axis direction.
        origin: Rotation center.

    Returns:
        :class:`TrackedResult` with the rotated solid and topological delta.
    """
    graph_id = _make_id("g")
    node_id = _make_id("n")

    import math

    angle_rad = math.radians(angle_degrees)

    from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir

    trsf = gp_Trsf()
    ax1 = gp_Ax1(gp_Pnt(*origin), gp_Dir(*axis))
    trsf.SetRotation(ax1, angle_rad)

    xform = BRepBuilderAPI_Transform(shape.wrapped, trsf, True)
    xform.Build()

    if not xform.IsDone():
        raise ValueError("Rotate failed: OCC build did not complete")

    result_solid = Solid(xform.Shape())

    delta, entries = _query_single_shape_history(
        xform,
        shape.wrapped,
        graph_id,
        node_id,
        "rotate",
    )

    return TrackedResult(shape=result_solid, delta=delta, delta_entries=entries)


def tracked_mirror(
    shape: Solid,
    plane_origin: Tuple[float, float, float],
    plane_normal: Tuple[float, float, float],
) -> TrackedResult:
    """Mirror a solid with face-level history tracking."""

    graph_id = _make_id("g")
    node_id = _make_id("n")

    from OCP.gp import gp_Trsf, gp_Ax2, gp_Pnt, gp_Dir

    trsf = gp_Trsf()
    trsf.SetMirror(
        gp_Ax2(
            gp_Pnt(*plane_origin),
            gp_Dir(*plane_normal),
        )
    )

    xform = BRepBuilderAPI_Transform(shape.wrapped, trsf, True)
    xform.Build()

    if not xform.IsDone():
        raise ValueError("Mirror failed: OCC build did not complete")

    result_solid = Solid(xform.Shape())

    delta, entries = _query_single_shape_history(
        xform,
        shape.wrapped,
        graph_id,
        node_id,
        "mirror",
    )

    return TrackedResult(shape=result_solid, delta=delta, delta_entries=entries)


# ---------------------------------------------------------------------------
# Feature tracking
# ---------------------------------------------------------------------------


def tracked_box(
    corner: Tuple[float, float, float],
    width: float,
    height: float,
    depth: float,
) -> TrackedResult:
    """Build a box with operation-native Face role witnesses."""

    graph_id = _make_id("g")
    node_id = _make_id("n")
    built = build_box_primitive(corner, width, height, depth)
    result_solid = Solid(built.solid)
    roles: List[Dict[str, Any]] = []
    for witness in built.roles:
        role_entry = _operation_role(
            witness.shape,
            result_shape=result_solid.wrapped,
            graph_id=graph_id,
            node_id=node_id,
            role=witness.role,
            evidence_method=witness.evidence_method,
        )
        if role_entry is not None:
            roles.append(role_entry)

    delta = TopoDelta(
        roles=_canonical_topo_roles(roles, graph_id=graph_id, node_id=node_id)
    )
    return TrackedResult(
        shape=result_solid,
        delta=delta,
        delta_entries=_aggregate_delta_entries([], roles),
    )


def tracked_cylinder(
    origin: Tuple[float, float, float],
    axis: Tuple[float, float, float],
    radius: float,
    height: float,
) -> TrackedResult:
    """Build a cylinder with operation-native Face and Edge role witnesses."""

    graph_id = _make_id("g")
    node_id = _make_id("n")
    built = build_cylinder_primitive(origin, axis, radius, height)
    result_solid = Solid(built.solid)
    roles: List[Dict[str, Any]] = []
    for witness in built.roles:
        role_entry = _operation_role(
            witness.shape,
            result_shape=result_solid.wrapped,
            graph_id=graph_id,
            node_id=node_id,
            role=witness.role,
            evidence_method=witness.evidence_method,
        )
        if role_entry is not None:
            roles.append(role_entry)

    delta = TopoDelta(
        roles=_canonical_topo_roles(roles, graph_id=graph_id, node_id=node_id)
    )
    return TrackedResult(
        shape=result_solid,
        delta=delta,
        delta_entries=_aggregate_delta_entries([], roles),
    )


def tracked_cone(
    origin: Tuple[float, float, float],
    axis: Tuple[float, float, float],
    bottom_radius: float,
    top_radius: float,
    height: float,
) -> TrackedResult:
    """Build a cone with operation-native Face and Edge role witnesses."""

    graph_id = _make_id("g")
    node_id = _make_id("n")
    built = build_cone_primitive(
        origin, axis, bottom_radius, top_radius, height
    )
    result_solid = Solid(built.solid)
    roles: List[Dict[str, Any]] = []
    for witness in built.roles:
        role_entry = _operation_role(
            witness.shape,
            result_shape=result_solid.wrapped,
            graph_id=graph_id,
            node_id=node_id,
            role=witness.role,
            evidence_method=witness.evidence_method,
        )
        if role_entry is not None:
            roles.append(role_entry)

    delta = TopoDelta(
        roles=_canonical_topo_roles(roles, graph_id=graph_id, node_id=node_id)
    )
    return TrackedResult(
        shape=result_solid,
        delta=delta,
        delta_entries=_aggregate_delta_entries([], roles),
    )


def tracked_extrude(
    profile: Face, direction: Tuple[float, float, float], distance: float
) -> TrackedResult:
    """Extrude a profile face into a solid with history tracking.

    Args:
        profile: Face to extrude.
        direction: Extrusion direction.
        distance: Extrusion distance.

    Returns:
        :class:`TrackedResult` with the extruded solid and topological delta.
    """
    graph_id = _make_id("g")
    node_id = _make_id("n")

    arr = np.array(direction, dtype=float)
    norm = float(np.linalg.norm(arr))
    if norm <= 1e-15:
        raise ValueError("Extrude direction cannot be zero-length")
    arr = arr / norm * float(distance)
    gp_vec = gp_Vec(float(arr[0]), float(arr[1]), float(arr[2]))

    prism = BRepPrimAPI_MakePrism(profile.wrapped, gp_vec)
    prism.Build()

    if not prism.IsDone():
        raise ValueError("Extrude failed: OCC build did not complete")

    result_solid = Solid(prism.Shape())

    e_pres, e_mod, e_gen, e_del, edge_entries = _query_history(
        prism,
        profile.wrapped,
        graph_id,
        node_id,
        "profile",
        TopoKind.EDGE,
        TopAbs_EDGE,
        result_shape=result_solid.wrapped,
        generated_result_role="extrusion.side",
        project_source_tags=True,
    )
    roles: List[Dict[str, Any]] = _roles_from_history(
        edge_entries, evidence_method="Generated"
    )
    for candidate, role, method in (
        (prism.FirstShape(profile.wrapped), "extrusion.start", "FirstShape"),
        (prism.LastShape(profile.wrapped), "extrusion.end", "LastShape"),
    ):
        role_entry = _operation_role(
            candidate,
            result_shape=result_solid.wrapped,
            graph_id=graph_id,
            node_id=node_id,
            role=role,
            evidence_method=method,
            origin_role="profile",
        )
        if role_entry is not None:
            roles.append(role_entry)
    delta = TopoDelta(
        preserved=tuple(e_pres),
        modified=tuple(e_mod),
        generated=tuple(e_gen),
        deleted=tuple(e_del),
        entries=_canonical_topo_entries(
            edge_entries, graph_id=graph_id, node_id=node_id
        ),
        roles=_canonical_topo_roles(roles, graph_id=graph_id, node_id=node_id),
    )
    return TrackedResult(
        shape=result_solid,
        delta=delta,
        delta_entries=_aggregate_delta_entries(edge_entries, roles),
    )


def tracked_revolve(
    profile: Face,
    axis: Tuple[float, float, float],
    origin: Tuple[float, float, float],
    angle_degrees: float,
) -> TrackedResult:
    """Revolve a profile face into a solid with history tracking."""

    graph_id = _make_id("g")
    node_id = _make_id("n")

    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt

    angle_rad = math.radians(float(angle_degrees))
    revolve_op = BRepPrimAPI_MakeRevol(
        profile.wrapped,
        gp_Ax1(gp_Pnt(*origin), gp_Dir(*axis)),
        angle_rad,
        True,
    )
    revolve_op.Build()

    if not revolve_op.IsDone():
        raise ValueError("Revolve failed: OCC build did not complete")

    result_solid = Solid(revolve_op.Shape())

    e_pres, e_mod, e_gen, e_del, edge_entries = _query_history(
        revolve_op,
        profile.wrapped,
        graph_id,
        node_id,
        "profile",
        TopoKind.EDGE,
        TopAbs_EDGE,
        result_shape=result_solid.wrapped,
        generated_result_role="revolution.side",
        project_source_tags=True,
    )
    roles = _roles_from_history(edge_entries, evidence_method="Generated")
    for candidate, role, method in (
        (revolve_op.FirstShape(profile.wrapped), "revolution.start", "FirstShape"),
        (revolve_op.LastShape(profile.wrapped), "revolution.end", "LastShape"),
    ):
        role_entry = _operation_role(
            candidate,
            result_shape=result_solid.wrapped,
            graph_id=graph_id,
            node_id=node_id,
            role=role,
            evidence_method=method,
            origin_role="profile",
        )
        if role_entry is not None:
            roles.append(role_entry)
    delta = TopoDelta(
        preserved=tuple(e_pres),
        modified=tuple(e_mod),
        generated=tuple(e_gen),
        deleted=tuple(e_del),
        entries=_canonical_topo_entries(
            edge_entries, graph_id=graph_id, node_id=node_id
        ),
        roles=_canonical_topo_roles(roles, graph_id=graph_id, node_id=node_id),
    )
    return TrackedResult(
        shape=result_solid,
        delta=delta,
        delta_entries=_aggregate_delta_entries(edge_entries, roles),
    )


def tracked_fillet(solid: Solid, edges: List[Edge], radius: float) -> TrackedResult:
    """Apply fillet with face-level history tracking.

    Args:
        solid: Solid to fillet.
        edges: Edges to fillet.
        radius: Fillet radius.

    Returns:
        :class:`TrackedResult` with the filleted solid and topological delta.
    """
    graph_id = _make_id("g")
    node_id = _make_id("n")

    fillet_op = BRepFilletAPI_MakeFillet(solid.wrapped)
    for edge in edges:
        fillet_op.Add(radius, edge.wrapped)
    fillet_op.Build()

    if not fillet_op.IsDone():
        raise ValueError("Fillet failed: OCC build did not complete")

    result_solid = Solid(fillet_op.Shape())

    delta, face_entries = _query_single_shape_history(
        fillet_op, solid.wrapped, graph_id, node_id, "fillet"
    )
    contour_edges = _actual_contour_edges(fillet_op, edges)
    e_pres, e_mod, e_gen, e_del, edge_entries = _query_exact_history(
        fillet_op,
        contour_edges,
        graph_id,
        node_id,
        "contour_edge",
        TopoKind.EDGE,
        result_shape=result_solid.wrapped,
        generated_result_role="fillet.patch",
        project_source_tags=True,
    )
    roles = _roles_from_history(edge_entries, evidence_method="Generated")
    delta = TopoDelta(
        preserved=tuple((*delta.preserved, *e_pres)),
        modified=tuple((*delta.modified, *e_mod)),
        generated=tuple((*delta.generated, *e_gen)),
        deleted=tuple((*delta.deleted, *e_del)),
        entries=tuple(
            (*delta.entries, *_canonical_topo_entries(edge_entries, graph_id=graph_id, node_id=node_id))
        ),
        roles=_canonical_topo_roles(roles, graph_id=graph_id, node_id=node_id),
    )
    aggregate = _aggregate_delta_entries(edge_entries, roles)
    for topo_id, entry in face_entries.items():
        aggregate.setdefault(topo_id, entry)
    return TrackedResult(shape=result_solid, delta=delta, delta_entries=aggregate)


def tracked_chamfer(solid: Solid, edges: List[Edge], distance: float) -> TrackedResult:
    """Apply chamfer with face-level history tracking.

    Args:
        solid: Solid to chamfer.
        edges: Edges to chamfer.
        distance: Chamfer distance.

    Returns:
        :class:`TrackedResult` with the chamfered solid and topological delta.
    """
    graph_id = _make_id("g")
    node_id = _make_id("n")

    chamfer_op = BRepFilletAPI_MakeChamfer(solid.wrapped)
    for edge in edges:
        chamfer_op.Add(distance, edge.wrapped)
    chamfer_op.Build()

    if not chamfer_op.IsDone():
        raise ValueError("Chamfer failed: OCC build did not complete")

    result_solid = Solid(chamfer_op.Shape())

    delta, face_entries = _query_single_shape_history(
        chamfer_op, solid.wrapped, graph_id, node_id, "chamfer"
    )
    contour_edges = _actual_contour_edges(chamfer_op, edges)
    e_pres, e_mod, e_gen, e_del, edge_entries = _query_exact_history(
        chamfer_op,
        contour_edges,
        graph_id,
        node_id,
        "contour_edge",
        TopoKind.EDGE,
        result_shape=result_solid.wrapped,
        generated_result_role="chamfer.patch",
        project_source_tags=True,
    )
    roles = _roles_from_history(edge_entries, evidence_method="Generated")
    delta = TopoDelta(
        preserved=tuple((*delta.preserved, *e_pres)),
        modified=tuple((*delta.modified, *e_mod)),
        generated=tuple((*delta.generated, *e_gen)),
        deleted=tuple((*delta.deleted, *e_del)),
        entries=tuple(
            (*delta.entries, *_canonical_topo_entries(edge_entries, graph_id=graph_id, node_id=node_id))
        ),
        roles=_canonical_topo_roles(roles, graph_id=graph_id, node_id=node_id),
    )
    aggregate = _aggregate_delta_entries(edge_entries, roles)
    for topo_id, entry in face_entries.items():
        aggregate.setdefault(topo_id, entry)
    return TrackedResult(shape=result_solid, delta=delta, delta_entries=aggregate)


def tracked_shell(
    solid: Solid, faces_to_remove: List[Face], thickness: float, tol: float = 1e-6
) -> TrackedResult:
    """Apply shell/thick-solid operation with face-level history tracking."""

    graph_id = _make_id("g")
    node_id = _make_id("n")

    shell_op = BRepOffsetAPI_MakeThickSolid()
    closing_faces = TopTools_ListOfShape()
    for face in faces_to_remove:
        closing_faces.Append(face.wrapped)

    shell_op.MakeThickSolidByJoin(
        solid.wrapped,
        closing_faces,
        -abs(float(thickness)),
        float(tol),
        BRepOffset_Skin,
        False,
        False,
        GeomAbs_Arc,
        False,
    )
    shell_op.Build()

    if not shell_op.IsDone():
        raise ValueError("Shell failed: OCC build did not complete")

    result_solid = Solid(shell_op.Shape())

    all_faces = list(_iter_subshapes(solid.wrapped, TopAbs_FACE))
    selected_faces = [face.wrapped for face in faces_to_remove]
    remaining_faces = [
        face
        for face in all_faces
        if not any(_is_same_shape(face, selected) for selected in selected_faces)
    ]
    body_parts = _query_exact_history(
        shell_op,
        remaining_faces,
        graph_id,
        node_id,
        "body",
        TopoKind.FACE,
        result_shape=result_solid.wrapped,
        preserved_result_role="shell.body_face",
        modified_result_role="shell.body_face",
        generated_result_role="shell.offset_face",
        project_source_tags=True,
    )
    closing_parts = _query_exact_history(
        shell_op,
        selected_faces,
        graph_id,
        node_id,
        "closing_face",
        TopoKind.FACE,
        result_shape=result_solid.wrapped,
        result_role="shell.closing_descendant",
        project_source_tags=True,
    )
    boundary_edges = [
        edge
        for face in selected_faces
        for edge in _iter_subshapes(face, TopAbs_EDGE)
    ]
    boundary_parts = _query_exact_history(
        shell_op,
        boundary_edges,
        graph_id,
        node_id,
        "closing_boundary",
        TopoKind.EDGE,
        result_shape=result_solid.wrapped,
        generated_result_role="shell.wall",
        project_source_tags=True,
    )
    parts = (body_parts, closing_parts, boundary_parts)
    history_entries = [item for part in parts for item in part[4]]
    roles = _roles_from_history(history_entries, evidence_method="GeneratedOrModified")
    delta = TopoDelta(
        preserved=tuple(ref for part in parts for ref in part[0]),
        modified=tuple(ref for part in parts for ref in part[1]),
        generated=tuple(ref for part in parts for ref in part[2]),
        deleted=tuple(ref for part in parts for ref in part[3]),
        entries=_canonical_topo_entries(
            history_entries, graph_id=graph_id, node_id=node_id
        ),
        roles=_canonical_topo_roles(roles, graph_id=graph_id, node_id=node_id),
    )
    return TrackedResult(
        shape=result_solid,
        delta=delta,
        delta_entries=_aggregate_delta_entries(history_entries, roles),
    )


def tracked_loft(profiles: List[Wire], ruled: bool = False) -> TrackedResult:
    """Loft profile wires into a solid with wire-level history tracking."""

    graph_id = _make_id("g")
    node_id = _make_id("n")

    loft_op = BRepOffsetAPI_ThruSections(True, bool(ruled))
    loft_op.CheckCompatibility(True)
    for profile in profiles:
        loft_op.AddWire(profile.wrapped)
    loft_op.Build()

    if not loft_op.IsDone():
        raise ValueError("Loft failed: OCC build did not complete")

    result_solid = Solid(loft_op.Shape())

    preserved: List[TopoRef] = []
    modified: List[TopoRef] = []
    generated: List[TopoRef] = []
    deleted: List[TopoRef] = []
    history_entries: List[Dict[str, Any]] = []

    for idx, profile in enumerate(profiles):
        pres, mod, gen, del_, profile_entries = _query_history(
            loft_op,
            profile.wrapped,
            graph_id,
            node_id,
            f"profile_{idx}",
            TopoKind.EDGE,
            TopAbs_EDGE,
            result_shape=result_solid.wrapped,
            generated_result_role="loft.side",
            project_source_tags=True,
        )
        preserved.extend(pres)
        modified.extend(mod)
        generated.extend(gen)
        deleted.extend(del_)
        history_entries.extend(profile_entries)

    roles = _roles_from_history(history_entries, evidence_method="Generated")
    for candidate, role, method in (
        (loft_op.FirstShape(), "loft.start", "FirstShape"),
        (loft_op.LastShape(), "loft.end", "LastShape"),
    ):
        role_entry = _operation_role(
            candidate,
            result_shape=result_solid.wrapped,
            graph_id=graph_id,
            node_id=node_id,
            role=role,
            evidence_method=method,
        )
        if role_entry is not None:
            roles.append(role_entry)

    delta = TopoDelta(
        preserved=tuple(preserved),
        modified=tuple(modified),
        generated=tuple(generated),
        deleted=tuple(deleted),
        entries=_canonical_topo_entries(
            history_entries,
            graph_id=graph_id,
            node_id=node_id,
        ),
        roles=_canonical_topo_roles(roles, graph_id=graph_id, node_id=node_id),
    )
    return TrackedResult(
        shape=result_solid,
        delta=delta,
        delta_entries=_aggregate_delta_entries(history_entries, roles),
    )


def tracked_sweep(profile: Face, path: Wire, is_frenet: bool = False) -> TrackedResult:
    """Sweep a profile face along a wire path with history tracking."""

    graph_id = _make_id("g")
    node_id = _make_id("n")

    if profile.get_inner_wires():
        raise ValueError(
            "Sweep profiles with inner wires are unsupported because PipeShell only receives the outer profile wire"
        )

    sweep_op = BRepOffsetAPI_MakePipeShell(path.wrapped)
    sweep_op.SetMode(bool(is_frenet))
    sweep_op.Add(profile.get_outer_wire().wrapped, False, False)
    sweep_op.Build()
    if not sweep_op.IsDone():
        raise ValueError("Sweep failed: OCC build did not complete")
    if not sweep_op.MakeSolid():
        raise ValueError("Sweep failed: OCC solid conversion did not complete")

    result_solid = Solid(sweep_op.Shape())

    p_pres, p_mod, p_gen, p_del, p_entries = _query_history(
        sweep_op,
        profile.get_outer_wire().wrapped,
        graph_id,
        node_id,
        "profile",
        TopoKind.EDGE,
        TopAbs_EDGE,
        result_shape=result_solid.wrapped,
        generated_result_role="sweep.side",
        project_source_tags=True,
    )
    history_entries = p_entries
    roles = _roles_from_history(history_entries, evidence_method="Generated")
    for candidate, role, method in (
        (sweep_op.FirstShape(), "sweep.start", "FirstShape"),
        (sweep_op.LastShape(), "sweep.end", "LastShape"),
    ):
        role_entry = _operation_role(
            candidate,
            result_shape=result_solid.wrapped,
            graph_id=graph_id,
            node_id=node_id,
            role=role,
            evidence_method=method,
        )
        if role_entry is not None:
            roles.append(role_entry)

    delta = TopoDelta(
        preserved=tuple(p_pres),
        modified=tuple(p_mod),
        generated=tuple(p_gen),
        deleted=tuple(p_del),
        entries=_canonical_topo_entries(
            history_entries,
            graph_id=graph_id,
            node_id=node_id,
        ),
        roles=_canonical_topo_roles(roles, graph_id=graph_id, node_id=node_id),
    )
    return TrackedResult(
        shape=result_solid,
        delta=delta,
        delta_entries=_aggregate_delta_entries(history_entries, roles),
    )


def tracked_twisted_sweep(
    profile: Face,
    *,
    axis: Tuple[float, float, float],
    origin: Tuple[float, float, float],
    distance: float,
    twist_angle: float,
    guide_radius: float,
) -> TrackedResult:
    """Sweep a profile along a line with a linear axial rotation law."""

    graph_id = _make_id("g")
    node_id = _make_id("n")

    if profile.get_inner_wires():
        raise ValueError("Twisted sweep profiles with inner wires are unsupported")
    if BRepAdaptor_Surface(profile.wrapped, True).GetType() != GeomAbs_Plane:
        raise ValueError("Twisted sweep requires a planar profile")

    normal = profile.get_normal_at()
    normal_array = (float(normal.x), float(normal.y), float(normal.z))
    alignment = abs(sum(normal_array[index] * axis[index] for index in range(3)))
    if alignment < 1.0 - 1.0e-8:
        raise ValueError("Twisted sweep profile must be normal to the sweep axis")
    center = profile.get_center()
    axial_offset = sum(
        (float(value) - origin[index]) * axis[index]
        for index, value in enumerate((center.x, center.y, center.z))
    )
    if abs(axial_offset) > max(1.0e-7, distance * 1.0e-9):
        raise ValueError("Twisted sweep profile must lie at the sweep origin")

    axis_dir = gp_Dir(*axis)
    axis_array = tuple(float(value) for value in axis)
    seed = (1.0, 0.0, 0.0) if abs(axis_array[0]) < 0.9 else (0.0, 1.0, 0.0)
    projection = sum(seed[index] * axis_array[index] for index in range(3))
    reference = tuple(
        seed[index] - projection * axis_array[index] for index in range(3)
    )
    reference_dir = gp_Dir(*reference)

    start = gp_Pnt(*origin)
    end = gp_Pnt(
        origin[0] + axis[0] * distance,
        origin[1] + axis[1] * distance,
        origin[2] + axis[2] * distance,
    )
    spine_edge_builder = BRepBuilderAPI_MakeEdge(start, end)
    if not spine_edge_builder.IsDone():
        raise ValueError("Twisted sweep failed to build its straight spine")
    spine_edge = spine_edge_builder.Edge()
    spine_builder = BRepBuilderAPI_MakeWire(spine_edge)
    if not spine_builder.IsDone():
        raise ValueError("Twisted sweep failed to build its spine wire")
    spine = spine_builder.Wire()

    cylinder = Geom_CylindricalSurface(
        gp_Ax3(start, axis_dir, reference_dir), float(guide_radius)
    )
    guide_curve = GCE2d_MakeSegment(
        gp_Pnt2d(0.0, 0.0),
        gp_Pnt2d(math.radians(twist_angle), float(distance)),
    ).Value()
    guide_edge_builder = BRepBuilderAPI_MakeEdge(guide_curve, cylinder)
    if not guide_edge_builder.IsDone():
        raise ValueError("Twisted sweep failed to build its rotation guide")
    guide_builder = BRepBuilderAPI_MakeWire(guide_edge_builder.Edge())
    if not guide_builder.IsDone():
        raise ValueError("Twisted sweep failed to build its rotation guide wire")
    guide = guide_builder.Wire()
    BRepLib.BuildCurves3d_s(guide, 1.0e-7, MaxSegment=2000)

    sweep_op = BRepOffsetAPI_MakePipeShell(spine)
    sweep_op.SetTolerance(1.0e-6, 1.0e-6, 1.0e-4)
    sweep_op.SetMaxDegree(11)
    sweep_op.SetMaxSegments(200)
    sweep_op.SetMode(
        guide,
        True,
        BRepFill_TypeOfContact.BRepFill_NoContact,
    )
    sweep_op.Add(
        profile.get_outer_wire().wrapped,
        TopExp.FirstVertex_s(spine_edge, True),
        False,
        False,
    )
    if not sweep_op.IsReady():
        raise ValueError("Twisted sweep is not ready after adding the profile")
    sweep_op.Build()
    if not sweep_op.IsDone():
        raise ValueError(f"Twisted sweep failed: {sweep_op.GetStatus().name}")
    approximation_error = float(sweep_op.ErrorOnSurface())
    if not sweep_op.MakeSolid():
        raise ValueError("Twisted sweep failed to convert its shell into a solid")

    result_solid = Solid(sweep_op.Shape())
    if not BRepCheck_Analyzer(result_solid.wrapped, True).IsValid():
        raise ValueError("Twisted sweep produced an invalid solid")
    result_solid.set_metadata(
        "twisted_sweep.kernel",
        {"surface_error": approximation_error},
    )

    p_pres, p_mod, p_gen, p_del, history_entries = _query_history(
        sweep_op,
        profile.get_outer_wire().wrapped,
        graph_id,
        node_id,
        "profile",
        TopoKind.EDGE,
        TopAbs_EDGE,
        result_shape=result_solid.wrapped,
        generated_result_role="twisted_sweep.side",
        project_source_tags=True,
    )
    roles = _roles_from_history(history_entries, evidence_method="Generated")
    for candidate, role, method in (
        (sweep_op.FirstShape(), "twisted_sweep.start", "FirstShape"),
        (sweep_op.LastShape(), "twisted_sweep.end", "LastShape"),
    ):
        role_entry = _operation_role(
            candidate,
            result_shape=result_solid.wrapped,
            graph_id=graph_id,
            node_id=node_id,
            role=role,
            evidence_method=method,
        )
        if role_entry is not None:
            roles.append(role_entry)

    delta = TopoDelta(
        preserved=tuple(p_pres),
        modified=tuple(p_mod),
        generated=tuple(p_gen),
        deleted=tuple(p_del),
        entries=_canonical_topo_entries(
            history_entries,
            graph_id=graph_id,
            node_id=node_id,
        ),
        roles=_canonical_topo_roles(roles, graph_id=graph_id, node_id=node_id),
    )
    return TrackedResult(
        shape=result_solid,
        delta=delta,
        delta_entries=_aggregate_delta_entries(history_entries, roles),
    )
