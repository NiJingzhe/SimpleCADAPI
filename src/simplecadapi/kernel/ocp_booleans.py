"""OCP-native boolean helpers."""

from __future__ import annotations

from typing import List, Optional, Sequence

from OCP.BOPAlgo import BOPAlgo_GlueOff, BOPAlgo_GlueShift
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
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


def fuse_shapes(shapes: Sequence[TopoDS_Shape], *, glue: bool = True, tol: Optional[float] = None, clean: bool = True) -> TopoDS_Shape:
    if not shapes:
        raise ValueError("fuse_shapes requires at least one shape")
    if len(shapes) == 1:
        return shapes[0]
    builder = BRepAlgoAPI_Fuse()
    builder.SetRunParallel(True)
    builder.SetUseOBB(True)
    builder.SetArguments(_list_of([shapes[0]]))
    builder.SetTools(_list_of(list(shapes[1:])))
    if tol is not None:
        builder.SetFuzzyValue(float(tol))
    # Match CadQuery's Shape.fuse(glue=True) behavior: CadQuery maps glue=True
    # to OCC's GlueShift, not GlueFull. GlueFull can leave overlapping solids
    # separate in cases where CQ would return one fused solid.
    builder.SetGlue(BOPAlgo_GlueShift if glue else BOPAlgo_GlueOff)
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP fuse failed")
    result = builder.Shape()
    return clean_shape(result) if clean else result


def cut_shapes(body: TopoDS_Shape, tools: Sequence[TopoDS_Shape]) -> TopoDS_Shape:
    if not tools:
        return body
    builder = BRepAlgoAPI_Cut()
    builder.SetRunParallel(True)
    builder.SetUseOBB(True)
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
        builder.SetArguments(_list_of([result]))
        builder.SetTools(_list_of([tool]))
        builder.Build()
        if not builder.IsDone():
            raise ValueError("OCP common failed")
        result = builder.Shape()
    return result
