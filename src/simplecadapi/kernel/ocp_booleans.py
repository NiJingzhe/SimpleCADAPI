"""OCP-native boolean helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from OCP.BOPAlgo import BOPAlgo_GlueOff, BOPAlgo_GlueShift
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepTools import BRepTools_History
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape, TopoDS_Solid
from OCP.TopTools import TopTools_ListOfShape


def _list_of(shapes: Sequence[TopoDS_Shape]) -> TopTools_ListOfShape:
    out = TopTools_ListOfShape()
    for shape in shapes:
        out.Append(shape)
    return out


def solids_of(shape: TopoDS_Shape) -> List[TopoDS_Solid]:
    out: List[TopoDS_Solid] = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        out.append(TopoDS.Solid_s(explorer.Current()))
        explorer.Next()
    if not out and shape.ShapeType() == TopAbs_SOLID:
        out.append(TopoDS.Solid_s(shape))
    return out


def clean_shape(shape: TopoDS_Shape) -> TopoDS_Shape:
    unifier = ShapeUpgrade_UnifySameDomain(shape, True, True, True)
    unifier.Build()
    return unifier.Shape()


@dataclass(frozen=True)
class FuseHistoryResult:
    shape: TopoDS_Shape
    history: BRepTools_History
    section_edges: Tuple[TopoDS_Shape, ...] = ()


def _is_result_member(result_shape: TopoDS_Shape, candidate: TopoDS_Shape) -> bool:
    if result_shape.IsSame(candidate):
        return True
    explorer = TopExp_Explorer(result_shape, candidate.ShapeType())
    while explorer.More():
        if explorer.Current().IsSame(candidate):
            return True
        explorer.Next()
    return False


def _prefer_normal_fuse_for_glue_result(
    shapes: Sequence[TopoDS_Shape],
    result: TopoDS_Shape,
) -> bool:
    """Return whether glue mode should retry the normal fuse algorithm.

    OCC glue is an optimization, not a stronger boolean operation.  In some
    intersecting curved or N-ary cases it returns a compound of the original
    solids without doing the expected intersection.  Retrying with GlueOff is
    safe because the public union contract still rejects genuinely separated
    or lower-dimensional contacts as multiple solids.
    """

    return len(solids_of(result)) != 1 and len(shapes) > 1


def fuse_shapes_with_history(
    shapes: Sequence[TopoDS_Shape],
    *,
    glue: bool = False,
    tol: Optional[float] = None,
    clean: bool = True,
) -> FuseHistoryResult:
    """Fuse shapes once and retain history through optional same-domain cleanup."""

    if not shapes:
        raise ValueError("fuse_shapes requires at least one shape")
    if len(shapes) == 1:
        return FuseHistoryResult(shape=shapes[0], history=BRepTools_History())

    builder = BRepAlgoAPI_Fuse()
    builder.SetRunParallel(True)
    builder.SetUseOBB(True)
    builder.SetToFillHistory(True)
    builder.SetArguments(_list_of([shapes[0]]))
    builder.SetTools(_list_of(list(shapes[1:])))
    if tol is not None:
        builder.SetFuzzyValue(float(tol))
    builder.SetGlue(BOPAlgo_GlueShift if glue else BOPAlgo_GlueOff)
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP fuse failed")

    result = builder.Shape()
    history = BRepTools_History()
    history.Merge(builder.History())
    section_edges = tuple(builder.SectionEdges())

    if glue and _prefer_normal_fuse_for_glue_result(shapes, result):
        fallback = fuse_shapes_with_history(
            shapes,
            glue=False,
            tol=tol,
            clean=clean,
        )
        return fallback

    if clean:
        unifier = ShapeUpgrade_UnifySameDomain(result, True, True, True)
        unifier.Build()
        result = unifier.Shape()
        clean_history = unifier.History()
        history.Merge(clean_history)

        final_section_edges: List[TopoDS_Shape] = []
        for edge in section_edges:
            candidates = [*clean_history.Modified(edge), *clean_history.Generated(edge)]
            if not candidates and not clean_history.IsRemoved(edge):
                candidates = [edge]
            for candidate in candidates:
                if _is_result_member(result, candidate) and not any(
                    existing.IsSame(candidate) for existing in final_section_edges
                ):
                    final_section_edges.append(candidate)
        section_edges = tuple(final_section_edges)

    return FuseHistoryResult(
        shape=result,
        history=history,
        section_edges=section_edges,
    )


def fuse_shapes(
    shapes: Sequence[TopoDS_Shape],
    *,
    glue: bool = False,
    tol: Optional[float] = None,
    clean: bool = True,
) -> TopoDS_Shape:
    """Fuse shapes without collecting topology history."""

    if not shapes:
        raise ValueError("fuse_shapes requires at least one shape")
    if len(shapes) == 1:
        return shapes[0]

    builder = BRepAlgoAPI_Fuse()
    builder.SetRunParallel(True)
    builder.SetUseOBB(True)
    builder.SetToFillHistory(False)
    builder.SetArguments(_list_of([shapes[0]]))
    builder.SetTools(_list_of(list(shapes[1:])))
    if tol is not None:
        builder.SetFuzzyValue(float(tol))
    builder.SetGlue(BOPAlgo_GlueShift if glue else BOPAlgo_GlueOff)
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP fuse failed")

    result = builder.Shape()
    if glue and _prefer_normal_fuse_for_glue_result(shapes, result):
        return fuse_shapes(
            shapes,
            glue=False,
            tol=tol,
            clean=clean,
        )
    return clean_shape(result) if clean else result


def cut_shapes(body: TopoDS_Shape, tools: Sequence[TopoDS_Shape]) -> TopoDS_Shape:
    if not tools:
        return body
    builder = BRepAlgoAPI_Cut()
    builder.SetRunParallel(True)
    builder.SetUseOBB(True)
    builder.SetToFillHistory(False)
    builder.SetArguments(_list_of([body]))
    builder.SetTools(_list_of(tools))
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP cut failed")
    return builder.Shape()


def common_shapes(shapes: Sequence[TopoDS_Shape]) -> TopoDS_Shape:
    if not shapes:
        raise ValueError("common_shapes requires at least one shape")
    if len(shapes) == 1:
        return shapes[0]
    result = shapes[0]
    for tool in shapes[1:]:
        builder = BRepAlgoAPI_Common()
        builder.SetRunParallel(True)
        builder.SetUseOBB(True)
        builder.SetToFillHistory(False)
        builder.SetArguments(_list_of([result]))
        builder.SetTools(_list_of([tool]))
        builder.Build()
        if not builder.IsDone():
            raise ValueError("OCP common failed")
        result = builder.Shape()
    return result
