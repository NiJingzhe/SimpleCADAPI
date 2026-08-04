"""Strict geometric-set and geometry-labelled topology comparison."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopTools import TopTools_IndexedMapOfShape, TopTools_ListOfShape
from OCP.TopoDS import TopoDS, TopoDS_Shape

from .inspect import BRepInspection
from .io import load_step_rshape, measure_shape_mass_rtuple


@dataclass(frozen=True)
class BRepComparison:
    """Hard-gate comparison facts for two solid BREPs."""

    target: str | None
    candidate: str | None
    target_minus_candidate_volume: float
    candidate_minus_target_volume: float
    same_geometric_point_set: bool
    geometry_labelled_incidence_graph_isomorphic: bool
    target_graph_nodes_edges: tuple[int, int]
    candidate_graph_nodes_edges: tuple[int, int]
    geometric_tolerance: float
    boolean_volume_tolerance: float

    @property
    def hard_gate_passed(self) -> bool:
        return (
            self.same_geometric_point_set
            and self.geometry_labelled_incidence_graph_isomorphic
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["hard_gate_passed"] = self.hard_gate_passed
        return result

    def write_json(self, path: str | Path, *, indent: int = 2) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_dict(), indent=indent), encoding="utf-8")
        return output


@dataclass(frozen=True)
class InspectionSummaryComparison:
    """Fast report-level diagnostics; not a geometric acceptance result."""

    volume_delta: float
    surface_area_delta: float
    bounding_box_delta: tuple[float, ...]
    counts_equal: bool
    surface_type_counts_equal: bool
    edge_type_counts_equal: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compare_inspections_rinspectionsummarycomparison(
    target: BRepInspection, candidate: BRepInspection
) -> InspectionSummaryComparison:
    """Compare inexpensive inspection summaries without claiming BREP equality."""
    return InspectionSummaryComparison(
        volume_delta=candidate.volume - target.volume,
        surface_area_delta=candidate.surface_area - target.surface_area,
        bounding_box_delta=tuple(
            candidate_value - target_value
            for target_value, candidate_value in zip(
                target.bounding_box, candidate.bounding_box
            )
        ),
        counts_equal=target.counts == candidate.counts,
        surface_type_counts_equal=target.surface_type_counts
        == candidate.surface_type_counts,
        edge_type_counts_equal=target.edge_type_counts == candidate.edge_type_counts,
    )


def _canonical_direction(values, tolerance: float) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    norm = np.linalg.norm(vector)
    if norm <= tolerance:
        raise ValueError("Cannot canonicalize a zero direction")
    vector /= norm
    for value in vector:
        if abs(value) > tolerance:
            if value < 0.0:
                vector = -vector
            break
    return vector


def _quantize(values, tolerance: float) -> tuple[int, ...]:
    return tuple(
        int(round(value / tolerance))
        for value in np.atleast_1d(np.asarray(values, dtype=float))
    )


def _canonical_axis(
    location, direction, tolerance: float
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    axis = _canonical_direction(direction, tolerance)
    point = np.asarray(location, dtype=float)
    closest_to_origin = point - axis * np.dot(point, axis)
    return _quantize(closest_to_origin, tolerance), _quantize(axis, tolerance)


def _surface_label(face, tolerance: float) -> tuple[Any, ...]:
    adaptor = BRepAdaptor_Surface(face, True)
    kind = str(adaptor.GetType()).split(".")[-1].removeprefix("GeomAbs_")
    area, center = measure_shape_mass_rtuple(face, "area")
    label: list[Any] = [
        kind,
        int(round(area / tolerance)),
        _quantize(center, tolerance),
    ]
    if kind == "Plane":
        plane = adaptor.Plane()
        normal = _canonical_direction(plane.Axis().Direction().Coord(), tolerance)
        distance = float(
            np.dot(normal, np.asarray(plane.Location().Coord(), dtype=float))
        )
        if distance < -tolerance:
            normal, distance = -normal, -distance
        label += [_quantize(normal, tolerance), int(round(distance / tolerance))]
    elif kind == "Cylinder":
        cylinder = adaptor.Cylinder()
        label += [
            int(round(cylinder.Radius() / tolerance)),
            _canonical_axis(
                cylinder.Location().Coord(),
                cylinder.Axis().Direction().Coord(),
                tolerance,
            ),
        ]
    elif kind == "Cone":
        cone = adaptor.Cone()
        label += [
            int(round(cone.RefRadius() / tolerance)),
            int(round(cone.SemiAngle() / tolerance)),
            _canonical_axis(
                cone.Location().Coord(), cone.Axis().Direction().Coord(), tolerance
            ),
            _quantize(cone.Apex().Coord(), tolerance),
        ]
    elif kind == "Sphere":
        sphere = adaptor.Sphere()
        label += [
            int(round(sphere.Radius() / tolerance)),
            _quantize(sphere.Location().Coord(), tolerance),
        ]
    elif kind == "Torus":
        torus = adaptor.Torus()
        label += [
            int(round(torus.MajorRadius() / tolerance)),
            int(round(torus.MinorRadius() / tolerance)),
            _canonical_axis(
                torus.Location().Coord(), torus.Axis().Direction().Coord(), tolerance
            ),
        ]
    elif kind == "BSplineSurface":
        surface = adaptor.BSpline()
        label += [
            int(surface.UDegree()),
            int(surface.VDegree()),
            int(surface.NbUPoles()),
            int(surface.NbVPoles()),
            int(surface.NbUKnots()),
            int(surface.NbVKnots()),
            bool(surface.IsUPeriodic()),
            bool(surface.IsVPeriodic()),
        ]
    return tuple(label)


def _edge_label(edge, tolerance: float) -> tuple[Any, ...]:
    adaptor = BRepAdaptor_Curve(edge)
    kind = str(adaptor.GetType()).split(".")[-1].removeprefix("GeomAbs_")
    length, center = measure_shape_mass_rtuple(edge, "length")
    label: list[Any] = [
        kind,
        int(round(length / tolerance)),
        _quantize(center, tolerance),
    ]
    if kind == "Line":
        line = adaptor.Line()
        label += [
            _canonical_axis(
                line.Location().Coord(), line.Direction().Coord(), tolerance
            )
        ]
    elif kind == "Circle":
        circle = adaptor.Circle()
        label += [
            int(round(circle.Radius() / tolerance)),
            _quantize(circle.Location().Coord(), tolerance),
            _quantize(
                _canonical_direction(circle.Axis().Direction().Coord(), tolerance),
                tolerance,
            ),
        ]
    elif kind == "BSplineCurve":
        curve = adaptor.BSpline()
        label += [
            int(curve.Degree()),
            int(curve.NbPoles()),
            int(curve.NbKnots()),
            bool(curve.IsPeriodic()),
            bool(curve.IsRational()),
        ]
    return tuple(label)


def _vertex_label(vertex, tolerance: float) -> tuple[Any, ...]:
    return "Vertex", _quantize(BRep_Tool.Pnt_s(vertex).Coord(), tolerance)


def _incidence_graph(shape: TopoDS_Shape, tolerance: float):
    faces = TopTools_IndexedMapOfShape()
    edges = TopTools_IndexedMapOfShape()
    vertices = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_FACE, faces)
    TopExp.MapShapes_s(shape, TopAbs_EDGE, edges)
    TopExp.MapShapes_s(shape, TopAbs_VERTEX, vertices)

    labels: dict[tuple[str, int], tuple[Any, ...]] = {}
    adjacency: dict[tuple[str, int], set[tuple[str, int]]] = {}

    def add_node(node, label):
        labels[node] = label
        adjacency.setdefault(node, set())

    def add_edge(first, second):
        adjacency.setdefault(first, set()).add(second)
        adjacency.setdefault(second, set()).add(first)

    for index in range(1, faces.Extent() + 1):
        face = TopoDS.Face_s(faces.FindKey(index))
        node = ("f", index)
        add_node(node, _surface_label(face, tolerance))
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            add_edge(node, ("e", edges.FindIndex(explorer.Current())))
            explorer.Next()
    for index in range(1, edges.Extent() + 1):
        edge = TopoDS.Edge_s(edges.FindKey(index))
        node = ("e", index)
        add_node(node, _edge_label(edge, tolerance))
        explorer = TopExp_Explorer(edge, TopAbs_VERTEX)
        while explorer.More():
            add_edge(node, ("v", vertices.FindIndex(explorer.Current())))
            explorer.Next()
    for index in range(1, vertices.Extent() + 1):
        vertex = TopoDS.Vertex_s(vertices.FindKey(index))
        add_node(("v", index), _vertex_label(vertex, tolerance))
    return labels, adjacency


def _same_partition(before: dict[Any, int], after: dict[Any, int]) -> bool:
    nodes = list(before)
    return all(
        (before[first] == before[second]) == (after[first] == after[second])
        for first in nodes
        for second in nodes
    )


def _labelled_graph_isomorphic(graph_a, graph_b) -> bool:
    labels_a, adjacency_a = graph_a
    labels_b, adjacency_b = graph_b
    if len(labels_a) != len(labels_b):
        return False

    all_labels = sorted(set(labels_a.values()) | set(labels_b.values()), key=repr)
    label_colors = {label: index for index, label in enumerate(all_labels)}
    colors_a = {node: label_colors[label] for node, label in labels_a.items()}
    colors_b = {node: label_colors[label] for node, label in labels_b.items()}

    while True:
        signatures_a = {
            node: (
                colors_a[node],
                tuple(sorted(colors_a[neighbor] for neighbor in adjacency_a[node])),
            )
            for node in labels_a
        }
        signatures_b = {
            node: (
                colors_b[node],
                tuple(sorted(colors_b[neighbor] for neighbor in adjacency_b[node])),
            )
            for node in labels_b
        }
        signatures = sorted(
            set(signatures_a.values()) | set(signatures_b.values()), key=repr
        )
        signature_colors = {
            signature: index for index, signature in enumerate(signatures)
        }
        refined_a = {
            node: signature_colors[signature]
            for node, signature in signatures_a.items()
        }
        refined_b = {
            node: signature_colors[signature]
            for node, signature in signatures_b.items()
        }
        stable = _same_partition(colors_a, refined_a) and _same_partition(
            colors_b, refined_b
        )
        colors_a, colors_b = refined_a, refined_b
        if stable:
            break

    if Counter(colors_a.values()) != Counter(colors_b.values()):
        return False

    candidates_b: dict[int, list[Any]] = defaultdict(list)
    for node, color in colors_b.items():
        candidates_b[color].append(node)
    order = sorted(
        labels_a,
        key=lambda node: (len(candidates_b[colors_a[node]]), -len(adjacency_a[node])),
    )
    mapping: dict[Any, Any] = {}
    used: set[Any] = set()

    def search(index: int) -> bool:
        if index == len(order):
            return True
        node_a = order[index]
        for node_b in candidates_b[colors_a[node_a]]:
            if node_b in used or len(adjacency_a[node_a]) != len(adjacency_b[node_b]):
                continue
            if any(
                (mapped_a in adjacency_a[node_a]) != (mapped_b in adjacency_b[node_b])
                for mapped_a, mapped_b in mapping.items()
            ):
                continue
            mapping[node_a] = node_b
            used.add(node_b)
            if search(index + 1):
                return True
            used.remove(node_b)
            del mapping[node_a]
        return False

    return search(0)


def _cut_volume(
    first: TopoDS_Shape, second: TopoDS_Shape, fuzzy_tolerance: float | None
) -> float:
    arguments = TopTools_ListOfShape()
    arguments.Append(first)
    tools = TopTools_ListOfShape()
    tools.Append(second)
    operation = BRepAlgoAPI_Cut()
    operation.SetArguments(arguments)
    operation.SetTools(tools)
    operation.SetRunParallel(True)
    operation.SetUseOBB(True)
    operation.SetToFillHistory(False)
    operation.SetNonDestructive(True)
    if fuzzy_tolerance is not None:
        operation.SetFuzzyValue(fuzzy_tolerance)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError("BREP boolean difference failed")
    volume = measure_shape_mass_rtuple(operation.Shape(), "volume")[0]
    if not math.isfinite(volume):
        raise RuntimeError("BREP boolean difference produced a non-finite volume")
    if volume < 0.0:
        raise RuntimeError("BREP boolean difference produced a negative signed volume")
    return volume


def _shape_volume(shape: TopoDS_Shape, description: str) -> float:
    volume = measure_shape_mass_rtuple(shape, "volume")[0]
    if not math.isfinite(volume):
        raise RuntimeError(f"{description} has a non-finite volume")
    if volume < 0.0:
        raise RuntimeError(f"{description} has a negative signed volume")
    return volume


def _material_operand(shape: TopoDS_Shape, description: str) -> TopoDS_Shape:
    from .model import index_shape_rbrepmodel

    model = index_shape_rbrepmodel(shape)
    if not model.bodies:
        raise RuntimeError(f"{description} has no solid material")
    return model._material_union()


def compare_shapes_rbrepcomparison(
    target: TopoDS_Shape,
    candidate: TopoDS_Shape,
    *,
    target_name: str | None = None,
    candidate_name: str | None = None,
    geometric_tolerance: float = 1.0e-7,
    boolean_volume_tolerance: float = 1.0e-9,
    boolean_fuzzy_tolerance: float | None = None,
    material_difference_volumes: Sequence[float] | None = None,
) -> BRepComparison:
    """Compare material point sets and geometry-labelled incidence graphs.

    Optional precomputed volumes are validated for compatibility but never used
    as equality evidence; strict directional cuts are always recomputed.
    """
    if boolean_fuzzy_tolerance is not None and boolean_fuzzy_tolerance <= 0.0:
        raise ValueError("boolean_fuzzy_tolerance must be greater than zero")
    if material_difference_volumes is not None:
        if len(material_difference_volumes) != 2:
            raise ValueError("material_difference_volumes must contain two values")
        precomputed_volumes = tuple(
            float(value) for value in material_difference_volumes
        )
        if not all(
            math.isfinite(value) and value >= 0.0 for value in precomputed_volumes
        ):
            raise ValueError(
                "material difference volumes must be finite and non-negative"
            )
    target_graph = _incidence_graph(target, geometric_tolerance)
    candidate_graph = _incidence_graph(candidate, geometric_tolerance)
    target_material = _material_operand(target, "Target BREP")
    candidate_material = _material_operand(candidate, "Candidate BREP")
    target_minus_candidate = _cut_volume(
        target_material,
        candidate_material,
        boolean_fuzzy_tolerance,
    )
    candidate_minus_target = _cut_volume(
        candidate_material,
        target_material,
        boolean_fuzzy_tolerance,
    )
    if (
        boolean_fuzzy_tolerance is not None
        and target_minus_candidate < boolean_volume_tolerance
        and candidate_minus_target < boolean_volume_tolerance
    ):
        # A fuzzy Boolean can erase a real narrow residual. Recompute apparent
        # equality without fuzz before using it as strict evidence.
        target_minus_candidate = _cut_volume(
            target_material,
            candidate_material,
            None,
        )
        candidate_minus_target = _cut_volume(
            candidate_material,
            target_material,
            None,
        )
    target_volume = _shape_volume(target_material, "Target BREP material")
    candidate_volume = _shape_volume(candidate_material, "Candidate BREP material")
    volume_delta = abs(target_volume - candidate_volume)
    volume_balance_error = abs(
        (target_minus_candidate - candidate_minus_target)
        - (target_volume - candidate_volume)
    )
    volume_balance_tolerance = max(
        boolean_volume_tolerance,
        max(target_volume, candidate_volume, 1.0) * 1.0e-12,
    )
    return BRepComparison(
        target=target_name,
        candidate=candidate_name,
        target_minus_candidate_volume=target_minus_candidate,
        candidate_minus_target_volume=candidate_minus_target,
        same_geometric_point_set=(
            target_minus_candidate < boolean_volume_tolerance
            and candidate_minus_target < boolean_volume_tolerance
            and volume_delta < boolean_volume_tolerance
            and volume_balance_error <= volume_balance_tolerance
        ),
        geometry_labelled_incidence_graph_isomorphic=_labelled_graph_isomorphic(
            target_graph, candidate_graph
        ),
        target_graph_nodes_edges=(
            len(target_graph[0]),
            sum(len(neighbors) for neighbors in target_graph[1].values()) // 2,
        ),
        candidate_graph_nodes_edges=(
            len(candidate_graph[0]),
            sum(len(neighbors) for neighbors in candidate_graph[1].values()) // 2,
        ),
        geometric_tolerance=geometric_tolerance,
        boolean_volume_tolerance=boolean_volume_tolerance,
    )


def compare_steps_rbrepcomparison(
    target_path: str | Path,
    candidate_path: str | Path,
    **kwargs,
) -> BRepComparison:
    """Load two STEP files and run the strict BREP comparison."""
    target_source = Path(target_path)
    candidate_source = Path(candidate_path)
    return compare_shapes_rbrepcomparison(
        load_step_rshape(target_source),
        load_step_rshape(candidate_source),
        target_name=str(target_source),
        candidate_name=str(candidate_source),
        **kwargs,
    )
