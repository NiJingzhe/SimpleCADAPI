"""Deterministic OpenCascade BRep encoding and exact-solid validation."""

from __future__ import annotations

import io
from typing import Any

from OCP.BRep import BRep_Builder
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepTools import BRepTools
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.TopoDS import TopoDS, TopoDS_Shape

from ..core import Solid
from .canonical import ArtifactValidationError, sha256_bytes

BRepLike = Solid | TopoDS_Shape


def _shape(value: BRepLike) -> TopoDS_Shape:
    if isinstance(value, Solid):
        return value.wrapped
    if isinstance(value, TopoDS_Shape):
        return value
    raise TypeError("value must be a Solid or TopoDS_Shape")


def write_brep_bytes(value: BRepLike) -> bytes:
    stream = io.BytesIO()
    BRepTools.Write_s(_shape(value), stream)
    payload = stream.getvalue()
    if not payload:
        raise ArtifactValidationError("brep_invalid", "/body", "BRep writer returned empty bytes")
    return payload


def brep_hash(value: BRepLike) -> str:
    return sha256_bytes(write_brep_bytes(value))


def read_brep_shape(payload: bytes | bytearray | memoryview) -> TopoDS_Shape:
    raw = bytes(payload)
    if not raw:
        raise ArtifactValidationError("brep_invalid", "/body", "BRep bytes are empty")
    shape = TopoDS_Shape()
    try:
        BRepTools.Read_s(shape, io.BytesIO(raw), BRep_Builder())
    except Exception as exc:
        raise ArtifactValidationError("brep_invalid", "/body", str(exc)) from exc
    if shape.IsNull():
        raise ArtifactValidationError("brep_invalid", "/body", "OpenCascade could not read BRep")
    if not BRepCheck_Analyzer(shape).IsValid():
        raise ArtifactValidationError("brep_invalid", "/body", "OpenCascade reports invalid topology")
    return shape


def read_brep_solid(payload: bytes | bytearray | memoryview) -> Solid:
    shape = read_brep_shape(payload)
    solids = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_SOLID, solids)
    if solids.Extent() != 1 or shape.ShapeType() != TopAbs_SOLID:
        raise ArtifactValidationError(
            "solid_cardinality_invalid", "/body", "BRep root must be exactly one Solid"
        )
    try:
        return Solid(TopoDS.Solid_s(shape))
    except Exception as exc:
        raise ArtifactValidationError("solid_cardinality_invalid", "/body", str(exc)) from exc


__all__ = ["brep_hash", "read_brep_shape", "read_brep_solid", "write_brep_bytes"]
