"""Thin OCP-native primitive builders used by the public API layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

from OCP.BRepPrimAPI import (
    BRepPrimAPI_MakeBox,
    BRepPrimAPI_MakeCone,
    BRepPrimAPI_MakeCylinder,
    BRepPrimAPI_MakeSphere,
)
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt


@dataclass(frozen=True)
class PrimitiveRoleWitness:
    role: str
    shape: Any
    evidence_method: str


@dataclass(frozen=True)
class PrimitiveBuildResult:
    solid: Any
    roles: Tuple[PrimitiveRoleWitness, ...]


def _point(value: tuple[float, float, float]) -> gp_Pnt:
    return gp_Pnt(float(value[0]), float(value[1]), float(value[2]))


def _axis2(
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    x_direction: tuple[float, float, float] | None = None,
) -> gp_Ax2:
    if x_direction is None:
        return gp_Ax2(
            _point(origin),
            gp_Dir(float(direction[0]), float(direction[1]), float(direction[2])),
        )
    return gp_Ax2(
        _point(origin),
        gp_Dir(float(direction[0]), float(direction[1]), float(direction[2])),
        gp_Dir(float(x_direction[0]), float(x_direction[1]), float(x_direction[2])),
    )


def make_box_solid(corner: tuple[float, float, float], dx: float, dy: float, dz: float):
    return build_box_primitive(corner, dx, dy, dz).solid


def build_box_primitive(
    corner: tuple[float, float, float],
    dx: float,
    dy: float,
    dz: float,
    *,
    x_axis: tuple[float, float, float] | None = None,
    y_axis: tuple[float, float, float] | None = None,
    z_axis: tuple[float, float, float] | None = None,
) -> PrimitiveBuildResult:
    if (x_axis is None) != (y_axis is None) or (x_axis is None) != (z_axis is None):
        raise ValueError("box axes must be provided together")
    axis = (
        _axis2(corner, z_axis, x_axis)
        if x_axis is not None and z_axis is not None
        else None
    )
    builder = (
        BRepPrimAPI_MakeBox(axis, float(dx), float(dy), float(dz))
        if axis is not None
        else BRepPrimAPI_MakeBox(_point(corner), float(dx), float(dy), float(dz))
    )
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP box builder failed")
    return PrimitiveBuildResult(
        solid=builder.Solid(),
        roles=(
            PrimitiveRoleWitness("box.bottom", builder.BottomFace(), "Box.BottomFace"),
            PrimitiveRoleWitness("box.top", builder.TopFace(), "Box.TopFace"),
            PrimitiveRoleWitness("box.front", builder.FrontFace(), "Box.FrontFace"),
            PrimitiveRoleWitness("box.back", builder.BackFace(), "Box.BackFace"),
            PrimitiveRoleWitness("box.left", builder.LeftFace(), "Box.LeftFace"),
            PrimitiveRoleWitness("box.right", builder.RightFace(), "Box.RightFace"),
        ),
    )


def make_cylinder_solid(
    origin: tuple[float, float, float],
    axis: tuple[float, float, float],
    radius: float,
    height: float,
):
    return build_cylinder_primitive(origin, axis, radius, height).solid


def build_cylinder_primitive(
    origin: tuple[float, float, float],
    axis: tuple[float, float, float],
    radius: float,
    height: float,
) -> PrimitiveBuildResult:
    builder = BRepPrimAPI_MakeCylinder(
        _axis2(origin, axis), float(radius), float(height)
    )
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP cylinder builder failed")
    primitive = builder.Cylinder()
    return PrimitiveBuildResult(
        solid=builder.Solid(),
        roles=(
            PrimitiveRoleWitness(
                "cylinder.start", primitive.BottomFace(), "Cylinder.BottomFace"
            ),
            PrimitiveRoleWitness(
                "cylinder.end", primitive.TopFace(), "Cylinder.TopFace"
            ),
            PrimitiveRoleWitness(
                "cylinder.side", primitive.LateralFace(), "Cylinder.LateralFace"
            ),
            PrimitiveRoleWitness(
                "cylinder.start_boundary",
                primitive.BottomEdge(),
                "Cylinder.BottomEdge",
            ),
            PrimitiveRoleWitness(
                "cylinder.end_boundary", primitive.TopEdge(), "Cylinder.TopEdge"
            ),
            PrimitiveRoleWitness(
                "cylinder.seam", primitive.StartEdge(), "Cylinder.StartEdge"
            ),
        ),
    )


def make_cone_solid(
    origin: tuple[float, float, float],
    axis: tuple[float, float, float],
    bottom_radius: float,
    top_radius: float,
    height: float,
):
    return build_cone_primitive(
        origin, axis, bottom_radius, top_radius, height
    ).solid


def build_cone_primitive(
    origin: tuple[float, float, float],
    axis: tuple[float, float, float],
    bottom_radius: float,
    top_radius: float,
    height: float,
) -> PrimitiveBuildResult:
    builder = BRepPrimAPI_MakeCone(
        _axis2(origin, axis),
        float(bottom_radius),
        float(top_radius),
        float(height),
    )
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP cone builder failed")
    primitive = builder.Cone()
    roles = [
        PrimitiveRoleWitness(
            "cone.start", primitive.BottomFace(), "Cone.BottomFace"
        ),
        PrimitiveRoleWitness(
            "cone.side", primitive.LateralFace(), "Cone.LateralFace"
        ),
        PrimitiveRoleWitness(
            "cone.start_boundary", primitive.BottomEdge(), "Cone.BottomEdge"
        ),
        PrimitiveRoleWitness(
            "cone.end_boundary", primitive.TopEdge(), "Cone.TopEdge"
        ),
        PrimitiveRoleWitness(
            "cone.seam", primitive.StartEdge(), "Cone.StartEdge"
        ),
    ]
    if float(top_radius) > 0.0:
        roles.insert(
            1,
            PrimitiveRoleWitness(
                "cone.end", primitive.TopFace(), "Cone.TopFace"
            ),
        )
    return PrimitiveBuildResult(solid=builder.Solid(), roles=tuple(roles))


def make_sphere_solid(center: tuple[float, float, float], radius: float):
    builder = BRepPrimAPI_MakeSphere(_point(center), float(radius))
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP sphere builder failed")
    return builder.Solid()
