"""Parity checks between stable entity models and legacy inspection reports."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .io import shape_mass
from .model import BRepModel, _describe_geometry, load_step_model


_SURFACE_TYPES = {
    "Plane": "PLANE",
    "Cylinder": "CYLINDER",
    "Cone": "CONE",
    "Sphere": "SPHERE",
    "Torus": "TORUS",
    "BezierSurface": "BEZIER",
    "BSplineSurface": "BSPLINE",
    "SurfaceOfRevolution": "REVOLUTION",
    "SurfaceOfExtrusion": "EXTRUSION",
    "OffsetSurface": "OFFSET",
    "OtherSurface": "OTHER",
}
_CURVE_TYPES = {
    "Line": "LINE",
    "Circle": "CIRCLE",
    "Ellipse": "ELLIPSE",
    "Hyperbola": "HYPERBOLA",
    "Parabola": "PARABOLA",
    "BezierCurve": "BEZIER",
    "BSplineCurve": "BSPLINE",
    "OffsetCurve": "OFFSET",
    "OtherCurve": "OTHER",
}


@dataclass(frozen=True)
class EntityInspectionParity:
    """Result of checking stable entity output against a BRepInspection report."""

    source: str | None
    valid: bool
    issues: tuple[str, ...]
    checked_faces: int
    checked_edges: int
    degenerate_edges: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _close(
    actual: float,
    expected: float,
    *,
    relative_tolerance: float,
    absolute_tolerance: float,
) -> bool:
    return math.isclose(
        float(actual),
        float(expected),
        rel_tol=relative_tolerance,
        abs_tol=absolute_tolerance,
    )


def _expected_type(value: str, mapping: Mapping[str, str]) -> str:
    return mapping.get(value, value.upper())


def compare_model_to_inspection(
    model: BRepModel,
    report: Mapping[str, Any],
    *,
    relative_tolerance: float = 1.0e-8,
    absolute_tolerance: float = 1.0e-8,
) -> EntityInspectionParity:
    """Check summary, geometry labels, measurements, and incidence parity."""

    if relative_tolerance < 0.0 or absolute_tolerance < 0.0:
        raise ValueError("Parity tolerances must be non-negative")

    issues: list[str] = []
    summary = model.summary()
    counts = report["counts"]
    expected_counts = {
        "body_count": int(counts["solid"]),
        "face_count": int(counts["unique_faces"]),
        "edge_count": int(counts["unique_edges"]),
        "vertex_count": int(counts["unique_vertices"]),
    }
    for key, expected in expected_counts.items():
        actual = int(summary[key])
        if actual != expected:
            issues.append(f"{key}: expected {expected}, got {actual}")

    root_properties = {
        "volume": shape_mass(model.root, "volume")[0],
        "surface_area": shape_mass(model.root, "area")[0],
    }
    for key, actual in root_properties.items():
        expected = float(report[key])
        if not _close(
            actual,
            expected,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        ):
            issues.append(f"{key}: expected {expected}, got {actual}")

    expected_bounds = [float(value) for value in report["bounding_box"]]
    actual_bounds = [
        *summary["root_bounding_box"]["min"],
        *summary["root_bounding_box"]["max"],
    ]
    for index, (actual, expected) in enumerate(
        zip(actual_bounds, expected_bounds, strict=True)
    ):
        if not _close(
            actual,
            expected,
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        ):
            issues.append(f"bounding_box[{index}]: expected {expected}, got {actual}")

    expected_surface_counts = {
        _expected_type(kind, _SURFACE_TYPES): int(count)
        for kind, count in report["surface_type_counts"].items()
    }
    if summary["surface_type_statistics"] != expected_surface_counts:
        issues.append(
            "surface_type_statistics: expected "
            f"{expected_surface_counts}, got {summary['surface_type_statistics']}"
        )

    actual_curve_counts: Counter[str] = Counter()
    degenerate_edges = 0
    for edge in model.edges:
        geometry = _describe_geometry("edge", edge)
        curve_type = geometry["type"]
        if curve_type == "DEGENERATE":
            degenerate_edges += 1
            curve_type = geometry["underlying_curve_type"] or "OTHER"
        actual_curve_counts[curve_type] += 1
    expected_curve_counts = {
        _expected_type(kind, _CURVE_TYPES): int(count)
        for kind, count in report["edge_type_counts"].items()
    }
    if dict(actual_curve_counts) != expected_curve_counts:
        issues.append(
            "underlying_curve_type_statistics: expected "
            f"{expected_curve_counts}, got {dict(actual_curve_counts)}"
        )

    report_faces = report["faces"]
    checked_face_count = min(len(report_faces), len(model.faces))
    if len(report_faces) != len(model.faces):
        issues.append(
            f"face_records: report has {len(report_faces)}, "
            f"model has {len(model.faces)}"
        )
    for index, face_report in enumerate(report_faces[:checked_face_count]):
        entity_id = f"face:{index}"
        geometry = _describe_geometry("face", model.faces[index])
        expected_type = _expected_type(
            face_report["surface"]["type"],
            _SURFACE_TYPES,
        )
        if geometry["type"] != expected_type:
            issues.append(
                f"{entity_id}.type: expected {expected_type}, got {geometry['type']}"
            )
        if not _close(
            geometry["area"],
            face_report["area"],
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        ):
            issues.append(
                f"{entity_id}.area: expected {face_report['area']}, "
                f"got {geometry['area']}"
            )
        actual_edges = set(model.adjacency_details(entity_id)["edges"])
        expected_edges = {
            f"edge:{int(edge_index) - 1}" for edge_index in face_report["edge_indices"]
        }
        if actual_edges != expected_edges:
            issues.append(
                f"{entity_id}.edges: expected {sorted(expected_edges)}, "
                f"got {sorted(actual_edges)}"
            )

    report_edges = report["edges"]
    checked_edge_count = min(len(report_edges), len(model.edges))
    if len(report_edges) != len(model.edges):
        issues.append(
            f"edge_records: report has {len(report_edges)}, "
            f"model has {len(model.edges)}"
        )
    for index, edge_report in enumerate(report_edges[:checked_edge_count]):
        entity_id = f"edge:{index}"
        geometry = _describe_geometry("edge", model.edges[index])
        actual_type = geometry["type"]
        if actual_type == "DEGENERATE":
            actual_type = geometry["underlying_curve_type"] or "OTHER"
        expected_type = _expected_type(edge_report["type"], _CURVE_TYPES)
        if actual_type != expected_type:
            issues.append(
                f"{entity_id}.underlying_type: expected {expected_type}, "
                f"got {actual_type}"
            )
        if not _close(
            geometry["length"],
            edge_report["length"],
            relative_tolerance=relative_tolerance,
            absolute_tolerance=absolute_tolerance,
        ):
            issues.append(
                f"{entity_id}.length: expected {edge_report['length']}, "
                f"got {geometry['length']}"
            )
        actual_faces = set(model.adjacency_details(entity_id)["faces"])
        expected_faces = {
            f"face:{int(face_index) - 1}" for face_index in edge_report["face_indices"]
        }
        if actual_faces != expected_faces:
            issues.append(
                f"{entity_id}.faces: expected {sorted(expected_faces)}, "
                f"got {sorted(actual_faces)}"
            )

    return EntityInspectionParity(
        source=model.source,
        valid=not issues,
        issues=tuple(issues),
        checked_faces=checked_face_count,
        checked_edges=checked_edge_count,
        degenerate_edges=degenerate_edges,
    )


def compare_step_to_inspection(
    step_path: str | Path,
    report_path: str | Path,
    *,
    relative_tolerance: float = 1.0e-8,
    absolute_tolerance: float = 1.0e-8,
) -> EntityInspectionParity:
    """Load a STEP file and compare it with a serialized BRepInspection report."""

    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    return compare_model_to_inspection(
        load_step_model(step_path),
        report,
        relative_tolerance=relative_tolerance,
        absolute_tolerance=absolute_tolerance,
    )


__all__ = [
    "EntityInspectionParity",
    "compare_model_to_inspection",
    "compare_step_to_inspection",
]
