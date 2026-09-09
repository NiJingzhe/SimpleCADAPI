"""Extract geometry fingerprints from CadQuery shapes."""

from __future__ import annotations

from typing import Any, List, Optional

from .trace_schema import GeoFingerprint


def _vec3(value: Any) -> List[float]:
    if hasattr(value, "x"):
        return [float(value.x), float(value.y), float(value.z)]
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return [float(value[0]), float(value[1]), float(value[2])]
    raise TypeError(f"cannot convert {value!r} to vec3")


def _bbox_dict(shape: Any) -> dict[str, list[float]]:
    box = shape.BoundingBox()
    return {
        "min": [float(box.xmin), float(box.ymin), float(box.zmin)],
        "max": [float(box.xmax), float(box.ymax), float(box.zmax)],
    }


def _index_in_parent(parent: Any, child: Any, collection_name: str) -> Optional[int]:
    if parent is None:
        return None
    getter = getattr(parent, collection_name, None)
    if getter is None:
        return None
    child_wrapped = getattr(child, "wrapped", child)
    for index, item in enumerate(getter()):
        item_wrapped = getattr(item, "wrapped", item)
        try:
            if item_wrapped.IsSame(child_wrapped):
                return index
        except Exception:
            if item is child:
                return index
    return None


def fingerprint_cq_shape(shape: Any, *, parent_solid: Any = None) -> GeoFingerprint:
    type_name = type(shape).__name__.lower()
    if "face" in type_name:
        return GeoFingerprint(
            kind="face",
            index=_index_in_parent(parent_solid, shape, "Faces"),
            geom_type=str(getattr(shape, "geomType", lambda: None)() or ""),
            center=_vec3(shape.Center()),
            normal=_vec3(shape.normalAt()),
            area=float(shape.Area()),
            bbox=_bbox_dict(shape),
        )

    if "edge" in type_name:
        center = _vec3(shape.Center()) if hasattr(shape, "Center") else None
        return GeoFingerprint(
            kind="edge",
            index=_index_in_parent(parent_solid, shape, "Edges"),
            geom_type=str(getattr(shape, "geomType", lambda: None)() or ""),
            center=center,
            length=float(shape.Length()),
            start=_vec3(shape.startPoint()),
            end=_vec3(shape.endPoint()),
            bbox=_bbox_dict(shape),
        )

    raise TypeError(f"unsupported CadQuery shape type: {type_name}")


def fingerprint_cq_objects(objects: list[Any], *, parent_solid: Any = None) -> list[GeoFingerprint]:
    fingerprints: list[GeoFingerprint] = []
    for obj in objects:
        try:
            fingerprints.append(fingerprint_cq_shape(obj, parent_solid=parent_solid))
        except Exception:
            continue
    return fingerprints
