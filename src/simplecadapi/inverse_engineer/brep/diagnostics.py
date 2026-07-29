"""OCP-native global and local diagnostics for reconstructed BREP models."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Section
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_Copy,
    BRepBuilderAPI_MakeVertex,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Shape
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

from ...kernel.ocp_export import export_step_shapes
from ...kernel.ocp_mesh import tessellate_face
from .compare import compare_shapes
from .io import shape_mass, xyz
from .model import (
    BRepEntityError,
    BRepModel,
    ENTITY_KINDS,
    _bounding_box,
    _describe_geometry,
    _entity_sort_key,
    index_shape,
    load_step_model,
)


ModelInput = BRepModel | TopoDS_Shape | str | Path


def _model(value: ModelInput) -> BRepModel:
    if isinstance(value, BRepModel):
        return value
    if isinstance(value, TopoDS_Shape):
        return index_shape(value)
    if isinstance(value, (str, Path)):
        return load_step_model(value)
    raise TypeError("Expected a BRepModel, TopoDS_Shape, or STEP path")


def _require_positive(value: float, name: str) -> None:
    if value <= 0.0:
        raise ValueError(f"{name} must be greater than zero")


def _make_compound(shapes: Sequence[TopoDS_Shape]) -> TopoDS_Shape:
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    for shape in shapes:
        builder.Add(compound, shape)
    return compound


def _mapped_shapes(shape: TopoDS_Shape, kind: Any) -> list[TopoDS_Shape]:
    indexed = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, kind, indexed)
    return [indexed.FindKey(index) for index in range(1, indexed.Extent() + 1)]


def _copy_shape(shape: TopoDS_Shape) -> TopoDS_Shape:
    operation = BRepBuilderAPI_Copy(shape, True, False)
    if not operation.IsDone():
        raise BRepEntityError("OpenCascade could not copy a Boolean operand")
    return operation.Shape()


def _material_shape(model: BRepModel) -> TopoDS_Shape:
    if not model.bodies:
        raise BRepEntityError(
            f"Model has no solid bodies; material operations are unavailable: "
            f"{model.source or '<memory>'}"
        )
    return model._material_union()


def _selected_faces(
    model: BRepModel,
    face_ids: Sequence[str] | None,
) -> list[Any]:
    if face_ids is None:
        source = _material_shape(model) if model.bodies else model.root
        return [TopoDS.Face_s(face) for face in _mapped_shapes(source, TopAbs_FACE)]
    result = []
    seen = set()
    for entity_id in face_ids:
        kind, index, shape = model.resolve_entity(entity_id)
        if kind != "face":
            raise BRepEntityError(f"Boundary scope requires face ids, got {entity_id}")
        canonical = f"face:{index}"
        if canonical not in seen:
            seen.add(canonical)
            result.append(TopoDS.Face_s(shape))
    if not result:
        raise ValueError("face id scopes must not be empty")
    return result


def _boundary_shape(
    model: BRepModel,
    face_ids: Sequence[str] | None = None,
) -> TopoDS_Shape:
    faces = _selected_faces(model, face_ids)
    if not faces:
        raise BRepEntityError("Model has no faces to use as a boundary")
    return faces[0] if len(faces) == 1 else _make_compound(faces)


def _bbox_gap(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    left_minimum = np.asarray(left["min"], dtype=float)
    left_maximum = np.asarray(left["max"], dtype=float)
    right_minimum = np.asarray(right["min"], dtype=float)
    right_maximum = np.asarray(right["max"], dtype=float)
    separation = np.maximum(
        np.maximum(left_minimum - right_maximum, right_minimum - left_maximum),
        0.0,
    )
    return float(np.linalg.norm(separation))


def _merge_bboxes(boxes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    minimum = np.min([np.asarray(box["min"], dtype=float) for box in boxes], axis=0)
    maximum = np.max([np.asarray(box["max"], dtype=float) for box in boxes], axis=0)
    size = maximum - minimum
    return {
        "min": minimum.tolist(),
        "max": maximum.tolist(),
        "size": size.tolist(),
        "diagonal": float(np.linalg.norm(size)),
        "center": ((minimum + maximum) * 0.5).tolist(),
    }


def _expand_bbox(box: Mapping[str, Any], amount: float) -> dict[str, Any]:
    minimum = np.asarray(box["min"], dtype=float) - amount
    maximum = np.asarray(box["max"], dtype=float) + amount
    return _merge_bboxes(
        [
            {"min": minimum, "max": minimum},
            {"min": maximum, "max": maximum},
        ]
    )


def _exact_distance(
    first: TopoDS_Shape,
    second: TopoDS_Shape,
) -> dict[str, Any]:
    operation = BRepExtrema_DistShapeShape(first, second)
    operation.Perform()
    if not operation.IsDone():
        raise BRepEntityError("OpenCascade exact-distance calculation failed")
    solutions = [
        {
            "first": xyz(operation.PointOnShape1(index)),
            "second": xyz(operation.PointOnShape2(index)),
        }
        for index in range(1, operation.NbSolution() + 1)
    ]
    solutions.sort(key=lambda item: tuple(item["first"] + item["second"]))
    return {
        "distance": float(operation.Value()),
        "closest_points": solutions,
    }


def compare_global_properties(
    target: ModelInput,
    current: ModelInput,
) -> dict[str, Any]:
    """Compare material counts, mass properties, bounds, and raw topology."""

    target_model = _model(target)
    current_model = _model(current)
    target_summary = target_model.summary()
    current_summary = current_model.summary()

    def delta(name: str) -> dict[str, float]:
        target_value = float(target_summary[name])
        current_value = float(current_summary[name])
        absolute = current_value - target_value
        return {
            "target": target_value,
            "current": current_value,
            "absolute_delta": absolute,
            "relative_delta": absolute / max(abs(target_value), 1.0e-12),
        }

    target_box = target_summary["bounding_box"]
    current_box = current_summary["bounding_box"]
    minimum_delta = (
        np.asarray(current_box["min"]) - np.asarray(target_box["min"])
    ).tolist()
    maximum_delta = (
        np.asarray(current_box["max"]) - np.asarray(target_box["max"])
    ).tolist()
    size_delta = (
        np.asarray(current_box["size"]) - np.asarray(target_box["size"])
    ).tolist()
    centroid_delta = np.asarray(current_summary["centroid"]) - np.asarray(
        target_summary["centroid"]
    )

    return {
        "target_model_path": target_model.source,
        "current_model_path": current_model.source,
        "body_count": {
            "target": target_summary["body_count"],
            "current": current_summary["body_count"],
            "delta": current_summary["body_count"] - target_summary["body_count"],
        },
        "material_body_count": {
            "target": target_summary["material_body_count"],
            "current": current_summary["material_body_count"],
            "delta": (
                current_summary["material_body_count"]
                - target_summary["material_body_count"]
            ),
        },
        "volume": delta("volume"),
        "surface_area": delta("surface_area"),
        "centroid": {
            "target": target_summary["centroid"],
            "current": current_summary["centroid"],
            "delta": centroid_delta.tolist(),
            "distance": float(np.linalg.norm(centroid_delta)),
        },
        "bounding_box": {
            "target": target_box,
            "current": current_box,
            "min_delta": minimum_delta,
            "max_delta": maximum_delta,
            "size_delta": size_delta,
            "max_absolute_coordinate_delta": float(
                np.max(np.abs(np.asarray(minimum_delta + maximum_delta)))
            ),
        },
        "root_bounding_box": {
            "target": target_summary["root_bounding_box"],
            "current": current_summary["root_bounding_box"],
        },
        "topology_counts": {
            name: {
                "target": target_summary[name],
                "current": current_summary[name],
                "delta": current_summary[name] - target_summary[name],
            }
            for name in ("face_count", "edge_count", "vertex_count")
        },
    }


def _face_samples(face, linear_deflection: float) -> np.ndarray:
    vertices, triangles = tessellate_face(
        face,
        tolerance=linear_deflection,
        angular_tolerance=0.2,
    )
    if not vertices:
        raise BRepEntityError("OpenCascade generated no tessellation for a face")
    vertex_array = np.asarray(vertices, dtype=float)
    candidates = [vertex_array]
    if triangles:
        triangle_array = vertex_array[np.asarray(triangles, dtype=int)]
        candidates.append(np.mean(triangle_array, axis=1))

    surface = BRep_Tool.Surface_s(face)
    projected = []
    for point in np.vstack(candidates):
        projector = GeomAPI_ProjectPointOnSurf(gp_Pnt(*point), surface)
        if projector.NbPoints() <= 0:
            continue
        u_value, v_value = projector.LowerDistanceParameters()
        projected.append(xyz(surface.Value(u_value, v_value)))

    # Some singular carriers reject triangle-center projections. Keep valid
    # samples and fall back to tessellation vertices only if all projections fail.
    values = np.asarray(projected or vertex_array.tolist(), dtype=float)
    quantization = max(linear_deflection * 0.05, 1.0e-9)
    quantized = np.round(values / quantization).astype(np.int64)
    _, indices = np.unique(quantized, axis=0, return_index=True)
    return values[np.sort(indices)]


def _farthest_indices(
    points: np.ndarray,
    count: int,
    *,
    initial: Sequence[int] = (),
) -> list[int]:
    if count >= len(points):
        return list(range(len(points)))
    selected = list(dict.fromkeys(int(index) for index in initial))[:count]
    if not selected:
        centroid = np.mean(points, axis=0)
        selected.append(int(np.argmax(np.linalg.norm(points - centroid, axis=1))))
    minimum_distances = np.min(
        np.stack(
            [np.linalg.norm(points - points[index], axis=1) for index in selected]
        ),
        axis=0,
    )
    minimum_distances[selected] = -1.0
    while len(selected) < count:
        next_index = int(np.argmax(minimum_distances))
        selected.append(next_index)
        minimum_distances = np.minimum(
            minimum_distances,
            np.linalg.norm(points - points[next_index], axis=1),
        )
        minimum_distances[selected] = -1.0
    return selected


def _bounded_boundary_faces(
    model: BRepModel,
    max_faces: int,
    face_ids: Sequence[str] | None = None,
) -> list[Any]:
    faces = _selected_faces(model, face_ids)
    if not faces:
        raise BRepEntityError("Model has no faces to sample")
    if len(faces) <= max_faces:
        return faces

    properties = [shape_mass(face, "area") for face in faces]
    areas = [item[0] for item in properties]
    centers = np.asarray([item[1] for item in properties], dtype=float)
    mandatory: list[int] = []

    if len(mandatory) > max_faces:
        local = _farthest_indices(
            centers[np.asarray(mandatory, dtype=int)],
            max_faces,
        )
        selected = [mandatory[index] for index in local]
    else:
        selected = _farthest_indices(
            centers,
            max_faces,
            initial=mandatory,
        )
    return [faces[index] for index in sorted(selected)]


def _surface_samples(
    model: BRepModel,
    linear_deflection: float,
    max_samples: int,
    face_ids: Sequence[str] | None = None,
) -> np.ndarray:
    _require_positive(linear_deflection, "linear_deflection")
    if max_samples < 16:
        raise ValueError("max_samples must be at least 16")

    faces = _bounded_boundary_faces(model, max_samples, face_ids)
    samples_by_face = [_face_samples(face, linear_deflection) for face in faces]
    representatives = np.asarray(
        [
            samples[
                int(
                    np.argmin(
                        np.linalg.norm(samples - np.mean(samples, axis=0), axis=1)
                    )
                )
            ]
            for samples in samples_by_face
        ],
        dtype=float,
    )
    if len(samples_by_face) >= max_samples:
        return representatives

    allocation = np.ones(len(samples_by_face), dtype=int)
    remaining = max_samples - len(samples_by_face)
    capacities = np.asarray(
        [max(len(samples) - 1, 0) for samples in samples_by_face],
        dtype=int,
    )
    while remaining > 0 and np.any(capacities > 0):
        for index in np.where(capacities > 0)[0]:
            if remaining == 0:
                break
            allocation[index] += 1
            capacities[index] -= 1
            remaining -= 1

    selected = []
    for samples, count in zip(samples_by_face, allocation):
        if count >= len(samples):
            selected.append(samples)
        else:
            selected.append(samples[np.linspace(0, len(samples) - 1, count, dtype=int)])
    return np.vstack(selected)


def _distance_statistics(values: np.ndarray) -> dict[str, float]:
    if not len(values):
        return {
            "minimum": 0.0,
            "maximum": 0.0,
            "mean": 0.0,
            "rms": 0.0,
            "median": 0.0,
            "p95": 0.0,
        }
    return {
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
        "mean": float(np.mean(values)),
        "rms": float(np.sqrt(np.mean(np.square(values)))),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95)),
    }


def _directed_boundary_distances(
    source_samples: np.ndarray,
    destination: TopoDS_Shape,
    *,
    include_records: bool,
) -> dict[str, Any]:
    distances = np.empty(len(source_samples), dtype=float)
    closest_points = np.empty_like(source_samples)
    for index, point in enumerate(source_samples):
        vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex()
        measurement = _exact_distance(vertex, destination)
        distances[index] = measurement["distance"]
        closest_points[index] = measurement["closest_points"][0]["second"]
    maximum_index = int(np.argmax(distances)) if len(distances) else 0
    result: dict[str, Any] = {
        "sample_count": len(source_samples),
        "statistics": _distance_statistics(distances),
        "maximum_sample": {
            "source_point": (
                source_samples[maximum_index].tolist() if len(source_samples) else None
            ),
            "closest_destination_point": (
                closest_points[maximum_index].tolist() if len(source_samples) else None
            ),
            "distance": (
                float(distances[maximum_index]) if len(source_samples) else 0.0
            ),
        },
    }
    if include_records:
        result["records"] = [
            {
                "source_point": source_samples[index].tolist(),
                "closest_destination_point": closest_points[index].tolist(),
                "distance": float(distances[index]),
            }
            for index in range(len(source_samples))
        ]
    return result


def compare_boundary_distance(
    target: ModelInput,
    current: ModelInput,
    *,
    linear_deflection: float = 0.5,
    max_samples: int = 200,
    target_face_ids: Sequence[str] | None = None,
    current_face_ids: Sequence[str] | None = None,
    include_records: bool = False,
) -> dict[str, Any]:
    """Compute bidirectional sampled-boundary to exact-boundary distances."""

    target_model = _model(target)
    current_model = _model(current)
    target_samples = _surface_samples(
        target_model,
        linear_deflection,
        max_samples,
        target_face_ids,
    )
    current_samples = _surface_samples(
        current_model,
        linear_deflection,
        max_samples,
        current_face_ids,
    )
    target_to_current = _directed_boundary_distances(
        target_samples,
        _boundary_shape(current_model, current_face_ids),
        include_records=include_records,
    )
    current_to_target = _directed_boundary_distances(
        current_samples,
        _boundary_shape(target_model, target_face_ids),
        include_records=include_records,
    )
    return {
        "target_model_path": target_model.source,
        "current_model_path": current_model.source,
        "method": "tessellated boundary samples to exact OCP boundary faces",
        "linear_deflection": linear_deflection,
        "scope": {
            "target_face_ids": (
                list(target_face_ids) if target_face_ids is not None else None
            ),
            "current_face_ids": (
                list(current_face_ids) if current_face_ids is not None else None
            ),
        },
        "target_to_current": target_to_current,
        "current_to_target": current_to_target,
        "symmetric": {
            "hausdorff_approximation": max(
                target_to_current["statistics"]["maximum"],
                current_to_target["statistics"]["maximum"],
            ),
            "mean_bidirectional_distance": (
                target_to_current["statistics"]["mean"]
                + current_to_target["statistics"]["mean"]
            )
            * 0.5,
            "rms_bidirectional_distance": math.sqrt(
                (
                    target_to_current["statistics"]["rms"] ** 2
                    + current_to_target["statistics"]["rms"] ** 2
                )
                * 0.5
            ),
        },
    }


def _cut_shape(
    first: TopoDS_Shape,
    second: TopoDS_Shape,
    fuzzy_tolerance: float | None,
) -> TopoDS_Shape:
    operation = BRepAlgoAPI_Cut(_copy_shape(first), _copy_shape(second))
    if fuzzy_tolerance is not None:
        operation.SetFuzzyValue(float(fuzzy_tolerance))
    operation.Build()
    if not operation.IsDone():
        raise BRepEntityError("OpenCascade material difference failed")
    return operation.Shape()


def _component_summary(
    shape: TopoDS_Shape,
    component_id: str,
    category: str,
) -> dict[str, Any]:
    volume, centroid = shape_mass(shape, "volume")
    area, _ = shape_mass(shape, "area")
    return {
        "component_id": component_id,
        "category": category,
        "volume": volume,
        "surface_area": area,
        "centroid": centroid.tolist(),
        "bounding_box": _bounding_box(shape),
        "valid": bool(BRepCheck_Analyzer(shape).IsValid()),
    }


def compute_material_difference(
    target: ModelInput,
    current: ModelInput,
    *,
    boolean_tolerance: float | None = None,
    output_directory: str | Path | None = None,
) -> dict[str, Any]:
    """Compute missing material (Target-Current) and excess material."""

    if boolean_tolerance is not None:
        _require_positive(boolean_tolerance, "boolean_tolerance")
    target_model = _model(target)
    current_model = _model(current)
    target_material = _material_shape(target_model)
    current_material = _material_shape(current_model)

    if target_material.IsSame(current_material):
        missing_shape = _make_compound([])
        excess_shape = _make_compound([])
    else:
        missing_shape = _cut_shape(
            target_material,
            current_material,
            boolean_tolerance,
        )
        excess_shape = _cut_shape(
            current_material,
            target_material,
            boolean_tolerance,
        )

    missing_solids = [
        TopoDS.Solid_s(shape) for shape in _mapped_shapes(missing_shape, TopAbs_SOLID)
    ]
    excess_solids = [
        TopoDS.Solid_s(shape) for shape in _mapped_shapes(excess_shape, TopAbs_SOLID)
    ]
    missing_components = [
        _component_summary(shape, f"missing:{index}", "missing_material")
        for index, shape in enumerate(missing_solids)
    ]
    excess_components = [
        _component_summary(shape, f"excess:{index}", "excess_material")
        for index, shape in enumerate(excess_solids)
    ]
    boolean_result_valid = (
        bool(BRepCheck_Analyzer(missing_shape).IsValid())
        and bool(BRepCheck_Analyzer(excess_shape).IsValid())
        and all(
            component["valid"]
            for component in [*missing_components, *excess_components]
        )
    )

    exported_files: dict[str, str] = {}
    if output_directory is not None:
        output = Path(output_directory).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        if missing_solids:
            missing_path = output / "missing_material.step"
            export_step_shapes(missing_solids, str(missing_path))
            exported_files["missing_material"] = str(missing_path)
        if excess_solids:
            excess_path = output / "excess_material.step"
            export_step_shapes(excess_solids, str(excess_path))
            exported_files["excess_material"] = str(excess_path)

    return {
        "target_model_path": target_model.source,
        "current_model_path": current_model.source,
        "missing_material": {
            "operation": "Target - Current",
            "volume": float(sum(item["volume"] for item in missing_components)),
            "component_count": len(missing_components),
            "components": missing_components,
        },
        "excess_material": {
            "operation": "Current - Target",
            "volume": float(sum(item["volume"] for item in excess_components)),
            "component_count": len(excess_components),
            "components": excess_components,
        },
        "boolean_result_valid": boolean_result_valid,
        "exported_files": exported_files,
    }


def _section_shape(
    model: BRepModel,
    origin: Sequence[float],
    normal: Sequence[float],
    tolerance: float,
) -> TopoDS_Shape:
    plane = gp_Pln(gp_Pnt(*origin), gp_Dir(*normal))
    source = _material_shape(model) if model.bodies else model.root
    operation = BRepAlgoAPI_Section(source, plane, False)
    operation.SetFuzzyValue(tolerance)
    operation.Build()
    if not operation.IsDone():
        raise BRepEntityError("OpenCascade section operation failed")
    return operation.Shape()


def _flatten_section_samples(section: Mapping[str, Any]) -> np.ndarray:
    points = [point for edge in section["edges"] for point in edge["samples_3d"]]
    return np.asarray(points, dtype=float) if points else np.empty((0, 3))


def _directed_section_distance(
    source: np.ndarray,
    destination: TopoDS_Shape,
) -> dict[str, Any]:
    if not len(source) or not _mapped_shapes(destination, TopAbs_EDGE):
        return {
            "available": not len(source),
            "statistics": _distance_statistics(np.empty(0)),
        }
    distances = []
    for point in source:
        measurement = _exact_distance(
            BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex(),
            destination,
        )
        distances.append(measurement["distance"])
    return {
        "available": True,
        "statistics": _distance_statistics(np.asarray(distances)),
    }


def compare_sections(
    target: ModelInput,
    current: ModelInput,
    plane_origin: Sequence[float],
    plane_normal: Sequence[float],
    *,
    tolerance: float = 1.0e-7,
    samples_per_edge: int = 32,
) -> dict[str, Any]:
    """Compare target and current contour geometry on one physical plane."""

    from .queries import make_section

    target_model = _model(target)
    current_model = _model(current)
    target_section = make_section(
        target_model,
        plane_origin,
        plane_normal,
        tolerance=tolerance,
        samples_per_edge=samples_per_edge,
    )
    current_section = make_section(
        current_model,
        plane_origin,
        plane_normal,
        tolerance=tolerance,
        samples_per_edge=samples_per_edge,
    )
    target_shape = _section_shape(
        target_model,
        plane_origin,
        plane_normal,
        tolerance,
    )
    current_shape = _section_shape(
        current_model,
        plane_origin,
        plane_normal,
        tolerance,
    )
    target_points = _flatten_section_samples(target_section)
    current_points = _flatten_section_samples(current_section)

    if target_section["edge_count"] and current_section["edge_count"]:
        target_to_current = _directed_section_distance(
            target_points,
            current_shape,
        )
        current_to_target = _directed_section_distance(
            current_points,
            target_shape,
        )
        hausdorff = max(
            target_to_current["statistics"]["maximum"],
            current_to_target["statistics"]["maximum"],
        )
    elif not target_section["edge_count"] and not current_section["edge_count"]:
        target_to_current = current_to_target = {
            "available": True,
            "statistics": _distance_statistics(np.empty(0)),
        }
        hausdorff = 0.0
    else:
        target_to_current = current_to_target = {
            "available": False,
            "statistics": None,
        }
        hausdorff = None

    target_area = float(
        target_section.get(
            "material_area",
            sum(contour["area"] or 0.0 for contour in target_section["contours"]),
        )
    )
    current_area = float(
        current_section.get(
            "material_area",
            sum(contour["area"] or 0.0 for contour in current_section["contours"]),
        )
    )
    target_perimeter = float(
        sum(contour["length_exact"] for contour in target_section["contours"])
    )
    current_perimeter = float(
        sum(contour["length_exact"] for contour in current_section["contours"])
    )
    return {
        "target_model_path": target_model.source,
        "current_model_path": current_model.source,
        "plane": target_section["plane"],
        "target": {
            "edge_count": target_section["edge_count"],
            "closed_contour_count": target_section["closed_contour_count"],
            "material_area": target_area,
            "perimeter": target_perimeter,
            "section": target_section,
        },
        "current": {
            "edge_count": current_section["edge_count"],
            "closed_contour_count": current_section["closed_contour_count"],
            "material_area": current_area,
            "perimeter": current_perimeter,
            "section": current_section,
        },
        "comparison": {
            "target_to_current": target_to_current,
            "current_to_target": current_to_target,
            "hausdorff_approximation": hausdorff,
            "area_delta": current_area - target_area,
            "perimeter_delta": current_perimeter - target_perimeter,
            "empty_section_mismatch": bool(
                target_section["edge_count"] != current_section["edge_count"]
                and (
                    not target_section["edge_count"]
                    or not current_section["edge_count"]
                )
            ),
        },
    }


def _cluster_anomalies(
    records: Sequence[Mapping[str, Any]],
    *,
    threshold: float,
    cluster_radius: float,
    category: str,
) -> list[dict[str, Any]]:
    anomalies = [record for record in records if record["distance"] > threshold]
    if not anomalies:
        return []
    points = np.asarray([record["source_point"] for record in anomalies])
    visited = np.zeros(len(points), dtype=bool)
    clusters = []
    for seed in range(len(points)):
        if visited[seed]:
            continue
        queue = deque([seed])
        visited[seed] = True
        members = []
        while queue:
            current = queue.popleft()
            members.append(current)
            distances = np.linalg.norm(points - points[current], axis=1)
            for neighbor in np.where((distances <= cluster_radius) & ~visited)[0]:
                visited[neighbor] = True
                queue.append(int(neighbor))
        member_points = points[members]
        member_distances = [anomalies[index]["distance"] for index in members]
        minimum = np.min(member_points, axis=0) - threshold
        maximum = np.max(member_points, axis=0) + threshold
        clusters.append(
            {
                "category": category,
                "sample_count": len(members),
                "max_distance": float(max(member_distances)),
                "mean_distance": float(np.mean(member_distances)),
                "centroid": np.mean(member_points, axis=0).tolist(),
                "bounding_box": _merge_bboxes(
                    [
                        {"min": minimum, "max": minimum},
                        {"min": maximum, "max": maximum},
                    ]
                ),
            }
        )
    return clusters


def _merge_regions(
    regions: Sequence[Mapping[str, Any]],
    merge_radius: float,
) -> list[dict[str, Any]]:
    if not regions:
        return []
    parent = list(range(len(regions)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left in range(len(regions)):
        for right in range(left + 1, len(regions)):
            if (
                _bbox_gap(
                    regions[left]["bounding_box"],
                    regions[right]["bounding_box"],
                )
                <= merge_radius
            ):
                union(left, right)

    groups: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for index, region in enumerate(regions):
        groups[find(index)].append(region)

    merged = []
    for members in groups.values():
        box = _merge_bboxes([member["bounding_box"] for member in members])
        merged.append(
            {
                "categories": sorted({member["category"] for member in members}),
                "bounding_box": box,
                "centroid": box["center"],
                "missing_volume": float(
                    sum(
                        member.get("volume", 0.0)
                        for member in members
                        if member["category"] == "missing_material"
                    )
                ),
                "excess_volume": float(
                    sum(
                        member.get("volume", 0.0)
                        for member in members
                        if member["category"] == "excess_material"
                    )
                ),
                "max_boundary_distance": float(
                    max(
                        (member.get("max_distance", 0.0) for member in members),
                        default=0.0,
                    )
                ),
                "sample_count": int(
                    sum(member.get("sample_count", 0) for member in members)
                ),
                "sources": list(members),
            }
        )
    merged.sort(
        key=lambda item: (
            -max(item["missing_volume"], item["excess_volume"]),
            -item["max_boundary_distance"],
            item["centroid"],
        )
    )
    for index, region in enumerate(merged):
        region["region_id"] = f"region:{index}"
    return merged


def build_difference_regions(
    target: ModelInput,
    current: ModelInput,
    *,
    distance_threshold: float = 0.1,
    linear_deflection: float = 0.5,
    max_samples: int = 600,
    cluster_radius: float | None = None,
    merge_radius: float | None = None,
    boolean_tolerance: float | None = None,
    include_boundary: bool = False,
    boundary_result: Mapping[str, Any] | None = None,
    material_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate material components and optional precomputed boundary anomalies."""

    _require_positive(distance_threshold, "distance_threshold")
    target_model = _model(target)
    current_model = _model(current)
    if boundary_result is not None and not include_boundary:
        raise ValueError("boundary_result requires include_boundary=True")
    boundary = None
    if include_boundary:
        boundary = (
            dict(boundary_result)
            if boundary_result is not None
            else compare_boundary_distance(
                target_model,
                current_model,
                linear_deflection=linear_deflection,
                max_samples=max_samples,
                include_records=True,
            )
        )
        for direction in ("target_to_current", "current_to_target"):
            if not isinstance(boundary.get(direction, {}).get("records"), list):
                raise ValueError(
                    "boundary_result must include directed records; call "
                    "compare_boundary_distance(..., include_records=True)"
                )
    material = (
        dict(material_result)
        if material_result is not None
        else compute_material_difference(
            target_model,
            current_model,
            boolean_tolerance=boolean_tolerance,
        )
    )
    if not all(
        isinstance(material.get(category, {}).get("components"), list)
        for category in ("missing_material", "excess_material")
    ):
        raise ValueError("material_result must be a compute_material_difference result")
    scale = max(
        target_model.summary()["bounding_box"]["diagonal"],
        current_model.summary()["bounding_box"]["diagonal"],
        1.0,
    )
    effective_cluster_radius = (
        cluster_radius
        if cluster_radius is not None
        else max(distance_threshold * 3.0, scale * 0.02)
    )
    effective_merge_radius = (
        merge_radius
        if merge_radius is not None
        else max(distance_threshold * 2.0, scale * 0.01)
    )
    _require_positive(effective_cluster_radius, "cluster_radius")
    _require_positive(effective_merge_radius, "merge_radius")

    raw_regions: list[dict[str, Any]] = []
    for category in ("missing_material", "excess_material"):
        for component in material[category]["components"]:
            raw_regions.append(
                {
                    "category": category,
                    "volume": component["volume"],
                    "centroid": component["centroid"],
                    "bounding_box": component["bounding_box"],
                    "component_id": component["component_id"],
                }
            )
    if boundary is not None:
        raw_regions.extend(
            _cluster_anomalies(
                boundary["target_to_current"]["records"],
                threshold=distance_threshold,
                cluster_radius=effective_cluster_radius,
                category="missing_boundary",
            )
        )
        raw_regions.extend(
            _cluster_anomalies(
                boundary["current_to_target"]["records"],
                threshold=distance_threshold,
                cluster_radius=effective_cluster_radius,
                category="excess_boundary",
            )
        )
    regions = _merge_regions(raw_regions, effective_merge_radius)
    if boundary is not None:
        boundary = {
            **boundary,
            "target_to_current": {
                **boundary["target_to_current"],
                "records": None,
            },
            "current_to_target": {
                **boundary["current_to_target"],
                "records": None,
            },
        }
    return {
        "target_model_path": target_model.source,
        "current_model_path": current_model.source,
        "distance_threshold": distance_threshold,
        "cluster_radius": effective_cluster_radius,
        "merge_radius": effective_merge_radius,
        "region_count": len(regions),
        "regions": regions,
        "boundary_included": include_boundary,
        "boundary_summary": boundary,
        "material_summary": material,
    }


def _query_shape_from_region(region: Mapping[str, Any]) -> tuple[TopoDS_Shape, dict]:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    if "bounding_box" in region:
        box = region["bounding_box"]
    elif "centroid" in region:
        box = {"min": region["centroid"], "max": region["centroid"]}
    else:
        raise ValueError("region must contain bounding_box or centroid")
    minimum = np.asarray(box["min"], dtype=float)
    maximum = np.asarray(box["max"], dtype=float)
    size = np.maximum(maximum - minimum, 0.0)
    if np.all(size <= 1.0e-12):
        shape = BRepBuilderAPI_MakeVertex(gp_Pnt(*minimum)).Vertex()
    else:
        size = np.maximum(size, 1.0e-12)
        shape = BRepPrimAPI_MakeBox(
            gp_Pnt(*minimum),
            float(size[0]),
            float(size[1]),
            float(size[2]),
        ).Shape()
    return shape, {
        "min": minimum.tolist(),
        "max": maximum.tolist(),
    }


def find_nearby_entities(
    model: ModelInput,
    *,
    location: Sequence[float] | None = None,
    region: Mapping[str, Any] | str | None = None,
    radius: float = 1.0,
    entity_types: Sequence[str] = ("face", "edge", "vertex"),
    max_results: int = 30,
) -> dict[str, Any]:
    """Find stable entities whose exact geometry lies near a point or region."""

    if radius < 0.0:
        raise ValueError("radius must be non-negative")
    if max_results < 1:
        raise ValueError("max_results must be at least one")
    if (location is None) == (region is None):
        raise ValueError("Provide exactly one of location or region")
    brep_model = _model(model)

    kinds = []
    for kind in entity_types:
        normalized = kind.lower()
        if normalized not in {"face", "edge", "vertex"}:
            raise ValueError("entity_types may contain face, edge, or vertex")
        if normalized not in kinds:
            kinds.append(normalized)

    if location is not None:
        point = np.asarray(location, dtype=float)
        if point.shape != (3,) or not np.all(np.isfinite(point)):
            raise ValueError("location must contain three finite coordinates")
        query_shape = BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex()
        query_box = {
            "min": point.tolist(),
            "max": point.tolist(),
            "size": [0.0, 0.0, 0.0],
            "diagonal": 0.0,
            "center": point.tolist(),
        }
        query = {"location": point.tolist()}
    else:
        parsed = json.loads(region) if isinstance(region, str) else dict(region or {})
        if not isinstance(parsed, dict):
            raise ValueError("region JSON must encode one object")
        query_shape, compact_box = _query_shape_from_region(parsed)
        query_box = _merge_bboxes([compact_box])
        query = {"region": parsed}

    results = []
    for kind in kinds:
        for index, entity in enumerate(brep_model.entity_list(kind)):
            entity_box = _bounding_box(entity)
            bbox_distance = _bbox_gap(query_box, entity_box)
            if bbox_distance > radius:
                continue
            distance = _exact_distance(entity, query_shape)["distance"]
            if distance > radius:
                continue
            geometry = _describe_geometry(kind, entity)
            center = geometry.get(
                "centroid",
                geometry.get("coordinates", entity_box["center"]),
            )
            results.append(
                {
                    "entity_id": f"{kind}:{index}",
                    "kind": kind,
                    "geometry_type": geometry["type"],
                    "distance": distance,
                    "bounding_box_distance": bbox_distance,
                    "center": center,
                    "bounding_box": entity_box,
                }
            )
    results.sort(
        key=lambda item: (
            item["distance"],
            _entity_sort_key(item["entity_id"]),
        )
    )
    return {
        "model_path": brep_model.source,
        "query": query,
        "radius": radius,
        "search_bounding_box": _expand_bbox(query_box, radius),
        "entity_count": min(len(results), max_results),
        "truncated": len(results) > max_results,
        "entities": results[:max_results],
    }


def _adjacency_signature(model: BRepModel, entity_id: str) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    geometry: Counter[str] = Counter()
    for neighbor_id in model.direct_neighbors(entity_id):
        kind, _, shape = model.resolve_entity(neighbor_id)
        counts[kind] += 1
        geometry[f"{kind}:{_describe_geometry(kind, shape)['type']}"] += 1
    return {
        "direct_neighbor_counts": dict(sorted(counts.items())),
        "neighbor_geometry_types": dict(sorted(geometry.items())),
    }


def _scalar_parameter_deltas(
    target_value: Any,
    current_value: Any,
    prefix: str = "",
) -> dict[str, dict[str, float]]:
    deltas: dict[str, dict[str, float]] = {}
    if isinstance(target_value, Mapping) and isinstance(current_value, Mapping):
        for key in sorted(set(target_value) & set(current_value)):
            child = f"{prefix}.{key}" if prefix else key
            deltas.update(
                _scalar_parameter_deltas(
                    target_value[key],
                    current_value[key],
                    child,
                )
            )
    elif (
        isinstance(target_value, (int, float))
        and not isinstance(target_value, bool)
        and isinstance(current_value, (int, float))
        and not isinstance(current_value, bool)
    ):
        target_number = float(target_value)
        current_number = float(current_value)
        absolute = current_number - target_number
        deltas[prefix] = {
            "target": target_number,
            "current": current_number,
            "absolute_delta": absolute,
            "relative_delta": absolute / max(abs(target_number), 1.0e-12),
        }
    return deltas


def compare_entities(
    target: ModelInput,
    target_entity_id: str,
    current: ModelInput,
    current_entity_id: str,
) -> dict[str, Any]:
    """Compare entity geometry, scalar parameters, distance, and adjacency."""

    target_model = _model(target)
    current_model = _model(current)
    target_kind, _, target_shape = target_model.resolve_entity(target_entity_id)
    current_kind, _, current_shape = current_model.resolve_entity(current_entity_id)
    target_descriptor = target_model.describe_entity(target_entity_id)
    current_descriptor = current_model.describe_entity(current_entity_id)
    target_signature = _adjacency_signature(
        target_model,
        target_descriptor["entity_id"],
    )
    current_signature = _adjacency_signature(
        current_model,
        current_descriptor["entity_id"],
    )
    from .queries import measure_relation

    return {
        "target": target_descriptor,
        "current": current_descriptor,
        "kind_match": target_kind == current_kind,
        "geometry_type_match": (
            target_descriptor["geometry"]["type"]
            == current_descriptor["geometry"]["type"]
        ),
        "parameter_deltas": _scalar_parameter_deltas(
            target_descriptor["geometry"],
            current_descriptor["geometry"],
        ),
        "distance": _exact_distance(target_shape, current_shape),
        "relation": measure_relation(
            target_model,
            target_descriptor["entity_id"],
            current_descriptor["entity_id"],
            second_model_or_path=current_model,
        ),
        "adjacency": {
            "target_signature": target_signature,
            "current_signature": current_signature,
            "signature_match": target_signature == current_signature,
        },
    }


def evaluate_result(
    target: ModelInput,
    current: ModelInput,
    *,
    replay_succeeded: bool,
    boundary_tolerance: float = 0.1,
    bounding_box_tolerance: float = 0.1,
    relative_volume_tolerance: float = 1.0e-3,
    relative_area_tolerance: float = 1.0e-3,
    relative_material_tolerance: float = 1.0e-3,
    linear_deflection: float = 0.5,
    max_samples: int = 600,
    boolean_tolerance: float | None = None,
    strict_geometric_tolerance: float = 1.0e-6,
    strict_material_tolerance: float = 1.0e-6,
    require_strict_brep: bool = False,
) -> dict[str, Any]:
    """Apply replay, validity, material, boundary, and optional strict gates."""

    tolerances = {
        "boundary": boundary_tolerance,
        "bounding_box": bounding_box_tolerance,
        "relative_volume": relative_volume_tolerance,
        "relative_area": relative_area_tolerance,
        "relative_material": relative_material_tolerance,
        "strict_geometric": strict_geometric_tolerance,
        "strict_material": strict_material_tolerance,
    }
    if any(value < 0.0 for value in tolerances.values()):
        raise ValueError("Evaluation tolerances cannot be negative")
    _require_positive(strict_geometric_tolerance, "strict_geometric_tolerance")
    target_model = _model(target)
    current_model = _model(current)

    global_properties = compare_global_properties(target_model, current_model)
    boundary = compare_boundary_distance(
        target_model,
        current_model,
        linear_deflection=linear_deflection,
        max_samples=max_samples,
    )
    material = compute_material_difference(
        target_model,
        current_model,
        boolean_tolerance=boolean_tolerance,
    )
    target_volume = max(float(global_properties["volume"]["target"]), 1.0e-12)
    relative_material = (
        material["missing_material"]["volume"] + material["excess_material"]["volume"]
    ) / target_volume
    strict = None
    if require_strict_brep:
        strict = compare_shapes(
            target_model.root,
            current_model.root,
            target_name=target_model.source,
            candidate_name=current_model.source,
            geometric_tolerance=strict_geometric_tolerance,
            boolean_volume_tolerance=strict_material_tolerance,
            boolean_fuzzy_tolerance=boolean_tolerance or 1.0e-9,
        ).to_dict()

    checks = {
        "replay_succeeded": bool(replay_succeeded),
        "target_valid": bool(BRepCheck_Analyzer(target_model.root).IsValid()),
        "current_valid": bool(BRepCheck_Analyzer(current_model.root).IsValid()),
        "material_body_count_matches": (
            global_properties["material_body_count"]["delta"] == 0
        ),
        "volume_within_tolerance": (
            abs(global_properties["volume"]["relative_delta"])
            <= relative_volume_tolerance
        ),
        "area_within_tolerance": (
            abs(global_properties["surface_area"]["relative_delta"])
            <= relative_area_tolerance
        ),
        "bounding_box_within_tolerance": (
            global_properties["bounding_box"]["max_absolute_coordinate_delta"]
            <= bounding_box_tolerance
        ),
        "boundary_within_tolerance": (
            boundary["symmetric"]["hausdorff_approximation"] <= boundary_tolerance
        ),
        "material_difference_valid": bool(material["boolean_result_valid"]),
        "material_within_tolerance": (relative_material <= relative_material_tolerance),
    }
    if require_strict_brep:
        checks["raw_body_count_matches"] = global_properties["body_count"]["delta"] == 0
        assert strict is not None
        checks["strict_brep_hard_gate"] = bool(strict["hard_gate_passed"])
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not failed,
        "failed_checks": failed,
        "checks": checks,
        "strict_brep_required": bool(require_strict_brep),
        "strict_brep_executed": strict is not None,
        "tolerances": tolerances,
        "metrics": {
            "global_properties": global_properties,
            "boundary_distance": boundary,
            "material_difference": material,
            "relative_total_material_difference": relative_material,
            "strict_brep": strict,
        },
    }


__all__ = [
    "build_difference_regions",
    "compare_boundary_distance",
    "compare_entities",
    "compare_global_properties",
    "compare_sections",
    "compute_material_difference",
    "evaluate_result",
    "find_nearby_entities",
]
