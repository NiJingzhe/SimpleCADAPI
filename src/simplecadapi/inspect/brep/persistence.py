"""Atomic STEP persistence with explicit round-trip evidence."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import tempfile
from typing import Any

from OCP.TopoDS import TopoDS_Shape

from ...kernel.ocp_export import export_step_shapes
from .io import load_step_rshape
from .model import (
    BRepModel,
    clear_step_model_cache_rnone,
    index_shape_rbrepmodel,
    load_step_rbrepmodel,
)
from .topology_inspection import inspect_topology_rdescriptor


ModelInput = BRepModel | TopoDS_Shape | str | Path


def _model(value: ModelInput) -> BRepModel:
    if isinstance(value, BRepModel):
        return value
    if isinstance(value, TopoDS_Shape):
        return index_shape_rbrepmodel(value)
    if isinstance(value, (str, Path)):
        return load_step_rbrepmodel(value)
    raise TypeError("Expected a BRepModel, TopoDS_Shape, or STEP path")


def _relative_delta(before: float, after: float) -> float:
    return (after - before) / max(abs(before), 1.0e-12)


def _topology_count(report: dict[str, Any], name: str) -> int:
    return int(report["edge_classification_counts"].get(name, 0))


def _compact_summary(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result.pop("bodies", None)
    return result


def _compact_topology(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    for key in (
        "problem_edges",
        "small_faces",
        "shells",
        "internal_face_ids",
        "external_face_ids",
    ):
        result.pop(key, None)
    return result


def validate_step_roundtrip_rdescriptor(
    model_or_shape: ModelInput,
    output_path: str | Path,
    *,
    relative_property_tolerance: float = 1.0e-7,
    protected_input_paths: tuple[str | Path, ...] = (),
    compact: bool = True,
) -> dict[str, Any]:
    """Atomically write and reload STEP, publishing only a verified result."""

    if (
        not math.isfinite(relative_property_tolerance)
        or relative_property_tolerance < 0.0
    ):
        raise ValueError("relative_property_tolerance must be finite and non-negative")
    destination = Path(output_path).expanduser().resolve()
    if destination.suffix.lower() not in {".step", ".stp"}:
        raise ValueError("output_path must end in .step or .stp")
    if not destination.parent.is_dir():
        raise ValueError(f"output_path parent does not exist: {destination.parent}")
    protected = {Path(path).expanduser().resolve() for path in protected_input_paths}
    if isinstance(model_or_shape, BRepModel) and model_or_shape.source is not None:
        protected.add(Path(model_or_shape.source).expanduser().resolve())
    if isinstance(model_or_shape, (str, Path)):
        protected.add(Path(model_or_shape).expanduser().resolve())
    if destination in protected:
        raise ValueError(
            "output_path must differ from the input STEP path and every protected "
            "input STEP path"
        )

    before_model = _model(model_or_shape)
    before = before_model.summary()
    topology_before = inspect_topology_rdescriptor(before_model)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f".{destination.stem}-",
            suffix=destination.suffix,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        export_step_shapes([before_model.root], str(temporary_path))
        reloaded = load_step_rshape(
            temporary_path,
            require_single_root=False,
            require_valid=False,
        )
        after_model = index_shape_rbrepmodel(reloaded, source=destination)
        after = after_model.summary()
        topology_after = inspect_topology_rdescriptor(after_model)
        payload = temporary_path.read_bytes()
        volume_delta = float(after["volume"] - before["volume"])
        area_delta = float(after["surface_area"] - before["surface_area"])
        relative_volume = _relative_delta(
            float(before["volume"]), float(after["volume"])
        )
        relative_area = _relative_delta(
            float(before["surface_area"]), float(after["surface_area"])
        )
        property_deltas = {
            "volume": volume_delta,
            "relative_volume": relative_volume,
            "surface_area": area_delta,
            "relative_surface_area": relative_area,
            "centroid_distance": float(math.dist(before["centroid"], after["centroid"])),
        }
        topology_deltas = {
            "faces": int(after["face_count"] - before["face_count"]),
            "edges": int(after["edge_count"] - before["edge_count"]),
            "vertices": int(after["vertex_count"] - before["vertex_count"]),
            "free_edges": _topology_count(topology_after, "free")
            - _topology_count(topology_before, "free"),
            "non_manifold_edges": _topology_count(topology_after, "non_manifold")
            - _topology_count(topology_before, "non_manifold"),
            "degenerate_edges": _topology_count(topology_after, "degenerate")
            - _topology_count(topology_before, "degenerate"),
        }
        passed = (
            bool(before["valid"])
            and bool(after["valid"])
            and before["body_count"] == after["body_count"]
            and (
                before["body_count"] == 0
                or (float(before["volume"]) > 0.0 and float(after["volume"]) > 0.0)
            )
            and before["face_count"] == after["face_count"]
            and abs(relative_volume) <= relative_property_tolerance
            and abs(relative_area) <= relative_property_tolerance
            and topology_deltas["free_edges"] == 0
            and topology_deltas["non_manifold_edges"] == 0
            and topology_deltas["degenerate_edges"] == 0
        )
        output_replaced = False
        if passed:
            temporary_path.replace(destination)
            temporary_path = None
            output_replaced = True
            clear_step_model_cache_rnone()
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    return {
        "report_version": 1,
        "tool": "validate_step_roundtrip_rdescriptor",
        "passed": passed,
        "output_path": str(destination),
        "file_size": len(payload),
        "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "before": _compact_summary(before) if compact else before,
        "after": _compact_summary(after) if compact else after,
        "topology_before": (
            _compact_topology(topology_before) if compact else topology_before
        ),
        "topology_after": (
            _compact_topology(topology_after) if compact else topology_after
        ),
        "property_deltas": property_deltas,
        "topology_deltas": topology_deltas,
        "output_replaced": output_replaced,
        "strict_material_equality_checked": False,
        "strict_brep_equality_checked": False,
        "preserved_metadata_claimed": False,
    }


__all__ = ["validate_step_roundtrip_rdescriptor"]
