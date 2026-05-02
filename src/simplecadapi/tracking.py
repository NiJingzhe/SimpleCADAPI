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
import math
from typing import Any, Dict, List, Optional, Tuple

from OCP.BRepAlgoAPI import (
    BRepAlgoAPI_Cut,
    BRepAlgoAPI_Fuse,
    BRepAlgoAPI_Common,
    BRepAlgoAPI_BooleanOperation,
)
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_Transform,
    BRepBuilderAPI_MakeShape,
)
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
from OCP.GeomAbs import GeomAbs_Arc
from OCP.gp import gp_Vec
from OCP.TopTools import TopTools_ListOfShape
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX
from OCP.TopoDS import TopoDS

from .core import Solid, Face, Edge, Vertex
from .topology import (
    TopoKind,
    TopoEvent,
    TopoRef,
    TopoDelta,
    _make_id,
)


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


def _tolist_oftools(shapes) -> TopTools_ListOfShape:
    """Convert a Python list of TopoDS_Shape to TopTools_ListOfShape."""
    tl = TopTools_ListOfShape()
    for s in shapes:
        tl.Append(s)
    return tl


def _query_history(
    builder: BRepAlgoAPI_BooleanOperation,
    input_solid,
    graph_id: str,
    node_id: str,
    origin_role: str,
    kind: TopoKind,
    shape_type: int,
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

    for sub in _iter_subshapes(input_solid, shape_type):
        input_id = _topo_id(sub)

        if builder.IsDeleted(sub):
            ref = TopoRef(graph_id, node_id, 0, kind, input_id)
            deleted.append(ref)
            entries.append(
                {
                    "topo_id": input_id,
                    "event": "deleted",
                    "origin_role": origin_role,
                    "input_topo_id": input_id,
                }
            )
            continue

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
        if mod_size == 0 and gen_size == 0:
            ref = TopoRef(graph_id, node_id, 0, kind, input_id)
            preserved.append(ref)
            entries.append(
                {
                    "topo_id": input_id,
                    "event": "preserved",
                    "origin_role": origin_role,
                    "input_topo_id": input_id,
                }
            )
            continue

        # Case 2: Modified returns the same shape and no generations -> PRESERVED
        if same_shape_in_mod and gen_size == 0:
            ref = TopoRef(graph_id, node_id, 0, kind, input_id)
            preserved.append(ref)
            entries.append(
                {
                    "topo_id": input_id,
                    "event": "preserved",
                    "origin_role": origin_role,
                    "input_topo_id": input_id,
                }
            )
            continue

        # Case 3: Has modifications (different or multiple shapes) -> MODIFIED
        if mod_size > 0 and not same_shape_in_mod:
            for mod_shape in mod_list:
                mod_id = _topo_id(mod_shape)
                ref = TopoRef(graph_id, node_id, 0, kind, mod_id)
                modified.append(ref)
                entries.append(
                    {
                        "topo_id": mod_id,
                        "event": "modified",
                        "origin_role": origin_role,
                        "input_topo_id": input_id,
                    }
                )

        # Case 4: Has generated new shapes -> GENERATED
        if gen_size > 0:
            for gen_shape in gen_list:
                gen_id = _topo_id(gen_shape)
                ref = TopoRef(graph_id, node_id, 0, kind, gen_id)
                generated.append(ref)
                entries.append(
                    {
                        "topo_id": gen_id,
                        "event": "generated",
                        "origin_role": origin_role,
                        "input_topo_id": input_id,
                    }
                )

    return preserved, modified, generated, deleted, entries


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
    )

    # Section edges
    section_edges = _collect_section_edges(builder, graph_id, node_id)

    delta = TopoDelta(
        preserved=tuple(b_pres + t_pres),
        modified=tuple(b_mod + t_mod),
        generated=tuple(b_gen + t_gen),
        deleted=tuple(b_del + t_del),
        section_edges=tuple(section_edges),
    )

    # Build per-entity metadata
    all_entries: Dict[str, Dict[str, Any]] = {}
    for e in b_entries + t_entries:
        all_entries[e["topo_id"]] = e

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
    fuse_op = BRepAlgoAPI_Fuse()
    fuse_op.SetRunParallel(True)
    fuse_op.SetUseOBB(True)
    fuse_op.SetToFillHistory(True)

    args = TopTools_ListOfShape()
    args.Append(body.wrapped)
    tools = TopTools_ListOfShape()
    tools.Append(tool.wrapped)

    fuse_op.SetArguments(args)
    fuse_op.SetTools(tools)
    fuse_op.Build()

    if not fuse_op.IsDone():
        raise ValueError("Boolean union failed: OCC build did not complete")

    result = _build_boolean_result(fuse_op, body, tool, "union")
    # Add section edges from the builder
    return result


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
    force_preserved: bool = False,
) -> Tuple[TopoDelta, Dict[str, Dict[str, Any]]]:
    """Query history for a single-input operation (transforms, extrude, fillet…).

    Args:
        force_preserved: If True, treat all input faces as PRESERVED regardless
            of what OCC reports.  Useful for pure transforms that create new
            TShape copies but don't actually change topology.
    """
    if force_preserved:
        pres: List[TopoRef] = []
        entries: List[Dict[str, Any]] = []
        for sub in _iter_subshapes(input_solid, TopAbs_FACE):
            input_id = _topo_id(sub)
            ref = TopoRef(graph_id, node_id, 0, TopoKind.FACE, input_id)
            pres.append(ref)
            entries.append(
                {
                    "topo_id": input_id,
                    "event": "preserved",
                    "origin_role": "body",
                    "input_topo_id": input_id,
                }
            )
        delta = TopoDelta(preserved=tuple(pres))
        all_entries: Dict[str, Dict[str, Any]] = {e["topo_id"]: e for e in entries}
        return delta, all_entries

    pres, mod, gen, del_, entries = _query_history(
        builder, input_solid, graph_id, node_id, "body", TopoKind.FACE, TopAbs_FACE
    )
    delta = TopoDelta(
        preserved=tuple(pres),
        modified=tuple(mod),
        generated=tuple(gen),
        deleted=tuple(del_),
    )
    all_entries: Dict[str, Dict[str, Any]] = {}
    for e in entries:
        all_entries[e["topo_id"]] = e
    return delta, all_entries


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
        force_preserved=True,
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
        force_preserved=True,
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
        force_preserved=True,
    )

    return TrackedResult(shape=result_solid, delta=delta, delta_entries=entries)


# ---------------------------------------------------------------------------
# Feature tracking
# ---------------------------------------------------------------------------


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

    delta, entries = _query_single_shape_history(
        prism, profile.wrapped, graph_id, node_id, "extrude"
    )

    return TrackedResult(shape=result_solid, delta=delta, delta_entries=entries)


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

    delta, entries = _query_single_shape_history(
        revolve_op, profile.wrapped, graph_id, node_id, "revolve"
    )

    return TrackedResult(shape=result_solid, delta=delta, delta_entries=entries)


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

    delta, entries = _query_single_shape_history(
        fillet_op, solid.wrapped, graph_id, node_id, "fillet"
    )

    return TrackedResult(shape=result_solid, delta=delta, delta_entries=entries)


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

    delta, entries = _query_single_shape_history(
        chamfer_op, solid.wrapped, graph_id, node_id, "chamfer"
    )

    return TrackedResult(shape=result_solid, delta=delta, delta_entries=entries)


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

    delta, entries = _query_single_shape_history(
        shell_op, solid.wrapped, graph_id, node_id, "shell"
    )

    return TrackedResult(shape=result_solid, delta=delta, delta_entries=entries)


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
    entries: Dict[str, Dict[str, Any]] = {}

    for idx, profile in enumerate(profiles):
        pres, mod, gen, del_, profile_entries = _query_history(
            loft_op,
            profile.wrapped,
            graph_id,
            node_id,
            f"profile_{idx}",
            TopoKind.EDGE,
            TopAbs_EDGE,
        )
        preserved.extend(pres)
        modified.extend(mod)
        generated.extend(gen)
        deleted.extend(del_)
        for item in profile_entries:
            entries[item["topo_id"]] = item

    delta = TopoDelta(
        preserved=tuple(preserved),
        modified=tuple(modified),
        generated=tuple(generated),
        deleted=tuple(deleted),
    )
    return TrackedResult(shape=result_solid, delta=delta, delta_entries=entries)


def tracked_sweep(profile: Face, path: Wire, is_frenet: bool = False) -> TrackedResult:
    """Sweep a profile face along a wire path with history tracking."""

    graph_id = _make_id("g")
    node_id = _make_id("n")

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
    )
    path_pres, path_mod, path_gen, path_del, path_entries = _query_history(
        sweep_op,
        path.wrapped,
        graph_id,
        node_id,
        "path",
        TopoKind.EDGE,
        TopAbs_EDGE,
    )

    delta = TopoDelta(
        preserved=tuple(p_pres + path_pres),
        modified=tuple(p_mod + path_mod),
        generated=tuple(p_gen + path_gen),
        deleted=tuple(p_del + path_del),
    )
    entries: Dict[str, Dict[str, Any]] = {}
    for item in p_entries + path_entries:
        entries[item["topo_id"]] = item
    return TrackedResult(shape=result_solid, delta=delta, delta_entries=entries)
