"""Thin OCP-native primitive builders used by the public API layer."""

from __future__ import annotations

from OCP.BRepPrimAPI import (
    BRepPrimAPI_MakeBox,
    BRepPrimAPI_MakeCone,
    BRepPrimAPI_MakeCylinder,
    BRepPrimAPI_MakeSphere,
)
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt


def _point(value: tuple[float, float, float]) -> gp_Pnt:
    return gp_Pnt(float(value[0]), float(value[1]), float(value[2]))


def _axis2(
    origin: tuple[float, float, float], direction: tuple[float, float, float]
) -> gp_Ax2:
    return gp_Ax2(
        _point(origin),
        gp_Dir(float(direction[0]), float(direction[1]), float(direction[2])),
    )


def make_box_solid(corner: tuple[float, float, float], dx: float, dy: float, dz: float):
    builder = BRepPrimAPI_MakeBox(_point(corner), float(dx), float(dy), float(dz))
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP box builder failed")
    return builder.Solid()


def make_cylinder_solid(
    origin: tuple[float, float, float],
    axis: tuple[float, float, float],
    radius: float,
    height: float,
):
    builder = BRepPrimAPI_MakeCylinder(
        _axis2(origin, axis), float(radius), float(height)
    )
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP cylinder builder failed")
    return builder.Solid()


def make_cone_solid(
    origin: tuple[float, float, float],
    axis: tuple[float, float, float],
    bottom_radius: float,
    top_radius: float,
    height: float,
):
    builder = BRepPrimAPI_MakeCone(
        _axis2(origin, axis),
        float(bottom_radius),
        float(top_radius),
        float(height),
    )
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP cone builder failed")
    return builder.Solid()


def make_sphere_solid(center: tuple[float, float, float], radius: float):
    builder = BRepPrimAPI_MakeSphere(_point(center), float(radius))
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP sphere builder failed")
    return builder.Solid()
