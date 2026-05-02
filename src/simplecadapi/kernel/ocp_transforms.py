"""Thin OCP-native transform helpers for public geometry wrappers."""

from __future__ import annotations

import math
from typing import Tuple

from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.TopAbs import (
    TopAbs_EDGE,
    TopAbs_FACE,
    TopAbs_SOLID,
    TopAbs_VERTEX,
    TopAbs_WIRE,
)
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

from ..core import AnyShape, Edge, Face, Solid, Vertex, Wire


def _shape_from_transformed(shape: AnyShape, transformed) -> AnyShape:
    shape_type = transformed.ShapeType()
    if shape_type == TopAbs_VERTEX:
        return Vertex(TopoDS.Vertex_s(transformed))
    if shape_type == TopAbs_EDGE:
        return Edge(TopoDS.Edge_s(transformed))
    if shape_type == TopAbs_WIRE:
        return Wire(TopoDS.Wire_s(transformed))
    if shape_type == TopAbs_FACE:
        return Face(TopoDS.Face_s(transformed))
    if shape_type == TopAbs_SOLID:
        return Solid(TopoDS.Solid_s(transformed))
    raise ValueError(f"Unsupported transformed shape type: {shape_type}")


def apply_transform(shape: AnyShape, trsf: gp_Trsf) -> AnyShape:
    xform = BRepBuilderAPI_Transform(shape.wrapped, trsf, True)
    xform.Build()
    if not xform.IsDone():
        raise ValueError("OCP transform build failed")
    return _shape_from_transformed(shape, xform.Shape())


def translate_shape_ocp(
    shape: AnyShape, vector: Tuple[float, float, float]
) -> AnyShape:
    trsf = gp_Trsf()
    trsf.SetTranslation(gp_Vec(float(vector[0]), float(vector[1]), float(vector[2])))
    return apply_transform(shape, trsf)


def rotate_shape_ocp(
    shape: AnyShape,
    angle_degrees: float,
    axis: Tuple[float, float, float],
    origin: Tuple[float, float, float],
) -> AnyShape:
    trsf = gp_Trsf()
    trsf.SetRotation(
        gp_Ax1(
            gp_Pnt(float(origin[0]), float(origin[1]), float(origin[2])),
            gp_Dir(float(axis[0]), float(axis[1]), float(axis[2])),
        ),
        math.radians(float(angle_degrees)),
    )
    return apply_transform(shape, trsf)


def mirror_shape_ocp(
    shape: AnyShape,
    plane_origin: Tuple[float, float, float],
    plane_normal: Tuple[float, float, float],
) -> AnyShape:
    trsf = gp_Trsf()
    trsf.SetMirror(
        gp_Ax2(
            gp_Pnt(
                float(plane_origin[0]), float(plane_origin[1]), float(plane_origin[2])
            ),
            gp_Dir(
                float(plane_normal[0]),
                float(plane_normal[1]),
                float(plane_normal[2]),
            ),
        )
    )
    return apply_transform(shape, trsf)
