"""Thin OCP-native feature builders for loft/sweep/helical sweep."""

from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_Transform
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell, BRepOffsetAPI_ThruSections
from OCP.gp import gp_Trsf, gp_Vec
from OCP.TopoDS import TopoDS

from .ocp_curves import make_helix_wire


def make_face_from_wire(wire):
    builder = BRepBuilderAPI_MakeFace(wire, True)
    if not builder.IsDone():
        raise ValueError("OCP face builder failed")
    return builder.Face()


def make_face_from_wires(outer_wire, inner_wires: Sequence[Any]):
    builder = BRepBuilderAPI_MakeFace(outer_wire, True)
    if not builder.IsDone():
        raise ValueError("OCP face builder failed for outer wire")
    for inner_wire in inner_wires:
        builder.Add(TopoDS.Wire_s(inner_wire.Reversed()))
        if not builder.IsDone():
            raise ValueError("OCP face builder failed while adding inner wire")
    return builder.Face()


def make_loft_solid(wires: Iterable[Any], ruled: bool = False):
    builder = BRepOffsetAPI_ThruSections(True, bool(ruled))
    builder.CheckCompatibility(True)
    for wire in wires:
        builder.AddWire(wire)
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP loft builder failed")
    return builder.Shape()


def make_sweep_solid(profile_wire, path_wire, is_frenet: bool = False):
    builder = BRepOffsetAPI_MakePipeShell(path_wire)
    builder.SetMode(bool(is_frenet))
    builder.Add(profile_wire, False, False)
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP sweep builder failed")
    if not builder.MakeSolid():
        raise ValueError("OCP sweep solid conversion failed")
    return builder.Shape()


def translate_shape(shape, vector: Sequence[float]):
    trsf = gp_Trsf()
    trsf.SetTranslation(gp_Vec(float(vector[0]), float(vector[1]), float(vector[2])))
    builder = BRepBuilderAPI_Transform(shape, trsf, True)
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP feature translation failed")
    return builder.Shape()


def make_helical_sweep_solid(
    profile_wire,
    pitch: float,
    height: float,
    radius: float,
    center: Sequence[float],
    direction: Sequence[float],
    x_direction: Optional[Sequence[float]] = None,
):
    helix = make_helix_wire(
        pitch,
        height,
        radius,
        center,
        direction,
        x_direction=x_direction,
    )
    radial_direction = x_direction if x_direction is not None else (1.0, 0.0, 0.0)
    moved_profile = translate_shape(
        profile_wire,
        tuple(float(radius) * float(component) for component in radial_direction),
    )
    return make_sweep_solid(moved_profile, helix, is_frenet=True)
