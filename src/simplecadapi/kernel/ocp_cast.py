"""OCP shape casting and type helpers."""

from __future__ import annotations

from typing import Any

from OCP.TopAbs import (
    TopAbs_COMPOUND,
    TopAbs_EDGE,
    TopAbs_FACE,
    TopAbs_SOLID,
    TopAbs_VERTEX,
    TopAbs_WIRE,
)
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape


def shape_type_name(shape: TopoDS_Shape) -> str:
    st = shape.ShapeType()
    if st == TopAbs_VERTEX:
        return "vertex"
    if st == TopAbs_EDGE:
        return "edge"
    if st == TopAbs_WIRE:
        return "wire"
    if st == TopAbs_FACE:
        return "face"
    if st == TopAbs_SOLID:
        return "solid"
    if st == TopAbs_COMPOUND:
        return "compound"
    return str(st)


def as_vertex(shape: TopoDS_Shape):
    return TopoDS.Vertex_s(shape)


def as_edge(shape: TopoDS_Shape):
    return TopoDS.Edge_s(shape)


def as_wire(shape: TopoDS_Shape):
    return TopoDS.Wire_s(shape)


def as_face(shape: TopoDS_Shape):
    return TopoDS.Face_s(shape)


def as_solid(shape: TopoDS_Shape):
    st = shape.ShapeType()
    if st == TopAbs_SOLID:
        return TopoDS.Solid_s(shape)
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    if explorer.More():
        return TopoDS.Solid_s(explorer.Current())
    raise ValueError(f"Expected a solid-compatible OCP shape, got {shape_type_name(shape)}")


def require_shape(value: Any) -> TopoDS_Shape:
    if isinstance(value, TopoDS_Shape):
        return value
    raise TypeError(f"Expected an OCP TopoDS_Shape, got {type(value).__name__}")
