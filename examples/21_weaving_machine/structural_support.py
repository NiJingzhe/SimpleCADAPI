"""Geometry-based support-path audit from every visible part to the main frame."""

from __future__ import annotations

import math
from dataclasses import dataclass

import simplecadapi as scad
from simplecadapi.kernel.ocp_properties import bounding_box, distance
from simplecadapi.kernel.ocp_transforms import place_shape_ocp


ComponentPath = tuple[str, ...]


@dataclass(frozen=True)
class UnsupportedPart:
    path: ComponentPath
    nearest_supported_path: ComponentPath | None
    nearest_gap: float | None


@dataclass(frozen=True)
class SupportLink:
    path: ComponentPath
    supported_by: ComponentPath | None
    contact_gap: float


@dataclass(frozen=True)
class StructuralSupportReport:
    total_parts: int
    supported_parts: int
    contact_pair_count: int
    unsupported: tuple[UnsupportedPart, ...]
    support_links: tuple[SupportLink, ...]
    contact_tolerance: float

    @property
    def passed(self) -> bool:
        return not self.unsupported and self.supported_parts == self.total_parts


@dataclass(frozen=True)
class _PlacedPart:
    path: ComponentPath
    shape: scad.Solid
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]]


def _collect_parts(
    item: scad.Part | scad.Assembly,
    *,
    placement: scad.Placement,
    path: ComponentPath,
) -> list[_PlacedPart]:
    if isinstance(item, scad.Part):
        shape = place_shape_ocp(
            item.body,
            placement.origin,
            placement.x_axis,
            placement.y_axis,
            placement.z_axis,
        )
        box = bounding_box(shape.wrapped)
        return [
            _PlacedPart(
                path=path,
                shape=shape,
                bounds=(
                    (box.xmin, box.ymin, box.zmin),
                    (box.xmax, box.ymax, box.zmax),
                ),
            )
        ]

    parts: list[_PlacedPart] = []
    for component in item.components:
        parts.extend(
            _collect_parts(
                component.item,
                placement=placement.compose(component.placement),
                path=(*path, component.component_id),
            )
        )
    return parts


def _aabb_gap(
    first: tuple[tuple[float, float, float], tuple[float, float, float]],
    second: tuple[tuple[float, float, float], tuple[float, float, float]],
) -> float:
    first_min, first_max = first
    second_min, second_max = second
    squared = 0.0
    for axis in range(3):
        axis_gap = max(
            first_min[axis] - second_max[axis],
            second_min[axis] - first_max[axis],
            0.0,
        )
        squared += axis_gap * axis_gap
    return math.sqrt(squared)


def _support_edge_allowed(first: ComponentPath, second: ComponentPath) -> bool:
    if not first or not second:
        return False
    return (
        first[0] == second[0]
        or first[0] == "a10_main_frame"
        or second[0] == "a10_main_frame"
    )


def audit_structural_support(
    *,
    machine: scad.Assembly,
    contact_tolerance: float = 0.25,
) -> StructuralSupportReport:
    """Require every leaf Part to have a contact chain to an A10 datum rail."""

    if contact_tolerance < 0.0 or not math.isfinite(contact_tolerance):
        raise ValueError("contact_tolerance must be finite and non-negative")
    parts = _collect_parts(
        machine,
        placement=scad.Placement((0.0, 0.0, 0.0)),
        path=(),
    )
    roots = {
        index
        for index, part in enumerate(parts)
        if part.path
        in {
            ("a10_main_frame", "datum_rail_left"),
            ("a10_main_frame", "datum_rail_right"),
        }
    }
    if len(roots) != 2:
        raise ValueError("support audit requires both A10 longitudinal datum rails")

    adjacency: list[dict[int, float]] = [dict() for _ in parts]
    contact_pair_count = 0
    for first_index, first in enumerate(parts):
        for second_index in range(first_index + 1, len(parts)):
            second = parts[second_index]
            if not _support_edge_allowed(first.path, second.path):
                continue
            if _aabb_gap(first.bounds, second.bounds) > contact_tolerance:
                continue
            contact_gap = distance(first.shape.wrapped, second.shape.wrapped)
            if contact_gap > contact_tolerance:
                continue
            adjacency[first_index][second_index] = contact_gap
            adjacency[second_index][first_index] = contact_gap
            contact_pair_count += 1

    supported = set(roots)
    parent: dict[int, tuple[int | None, float]] = {root: (None, 0.0) for root in roots}
    frontier = sorted(roots)
    while frontier:
        current = frontier.pop()
        for neighbor in sorted(adjacency[current]):
            if neighbor in supported:
                continue
            supported.add(neighbor)
            parent[neighbor] = (current, adjacency[current][neighbor])
            frontier.append(neighbor)

    unsupported: list[UnsupportedPart] = []
    for index, part in enumerate(parts):
        if index in supported:
            continue
        nearest_index: int | None = None
        nearest_gap: float | None = None
        for supported_index in supported:
            if not _support_edge_allowed(part.path, parts[supported_index].path):
                continue
            candidate_gap = _aabb_gap(part.bounds, parts[supported_index].bounds)
            if nearest_gap is None or candidate_gap < nearest_gap:
                nearest_index = supported_index
                nearest_gap = candidate_gap
        unsupported.append(
            UnsupportedPart(
                path=part.path,
                nearest_supported_path=(
                    parts[nearest_index].path if nearest_index is not None else None
                ),
                nearest_gap=nearest_gap,
            )
        )

    support_links = tuple(
        SupportLink(
            path=parts[index].path,
            supported_by=(
                parts[parent[index][0]].path if parent[index][0] is not None else None
            ),
            contact_gap=parent[index][1],
        )
        for index in sorted(supported, key=lambda item: parts[item].path)
    )
    report = StructuralSupportReport(
        total_parts=len(parts),
        supported_parts=len(supported),
        contact_pair_count=contact_pair_count,
        unsupported=tuple(unsupported),
        support_links=support_links,
        contact_tolerance=contact_tolerance,
    )
    print(
        "structural_support: "
        f"passed={report.passed} supported={report.supported_parts}/{report.total_parts} "
        f"contact_pairs={report.contact_pair_count} tolerance={contact_tolerance:g}"
    )
    return report


def require_structural_support(
    *,
    machine: scad.Assembly,
    contact_tolerance: float = 0.25,
) -> StructuralSupportReport:
    report = audit_structural_support(
        machine=machine,
        contact_tolerance=contact_tolerance,
    )
    if report.passed:
        return report
    groups: dict[str, list[UnsupportedPart]] = {}
    for item in report.unsupported:
        groups.setdefault(item.path[0], []).append(item)
    details = "; ".join(
        subsystem
        + f"={len(items)} ["
        + ", ".join(
            "/".join(item.path[1:])
            + (f" gap={item.nearest_gap:.3f}" if item.nearest_gap is not None else "")
            for item in items[:4]
        )
        + (", ..." if len(items) > 4 else "")
        + "]"
        for subsystem, items in sorted(groups.items())
    )
    raise ValueError("unsupported machine components by subsystem: " + details)
