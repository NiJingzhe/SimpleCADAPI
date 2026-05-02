"""OCP-native export helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from OCP.BRep import BRep_Builder
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.StlAPI import StlAPI_Writer
from OCP.TopoDS import TopoDS_Compound, TopoDS_Shape
from OCP.IFSelect import IFSelect_RetDone


def make_compound(shapes: Sequence[TopoDS_Shape]) -> TopoDS_Shape:
    if not shapes:
        raise ValueError("No shapes to export")
    if len(shapes) == 1:
        return shapes[0]
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for shape in shapes:
        builder.Add(compound, shape)
    return compound


def export_step_shapes(shapes: Sequence[TopoDS_Shape], filename: str) -> None:
    writer = STEPControl_Writer()
    compound = make_compound(shapes)
    status = writer.Transfer(compound, STEPControl_AsIs)
    # Some OCP builds return int-like statuses; keep failure detection conservative.
    if status != IFSelect_RetDone and int(status) != int(IFSelect_RetDone):
        raise ValueError(f"STEP transfer failed: {status}")
    path = str(Path(filename))
    write_status = writer.Write(path)
    if write_status != IFSelect_RetDone and int(write_status) != int(IFSelect_RetDone):
        raise ValueError(f"STEP write failed: {write_status}")


def export_stl_shape(shape: TopoDS_Shape, filename: str) -> None:
    BRepMesh_IncrementalMesh(shape, 0.1).Perform()
    writer = StlAPI_Writer()
    ok = writer.Write(shape, str(Path(filename)))
    if ok is False:
        raise ValueError("STL write failed")
