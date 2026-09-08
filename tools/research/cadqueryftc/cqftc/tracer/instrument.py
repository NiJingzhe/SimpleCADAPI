"""Instrument CadQuery Workplane to record operation traces."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional

from .fingerprint import fingerprint_cq_objects
from .trace_schema import OperationTrace, TraceStep

_TRACE: Optional[OperationTrace] = None
_ORIGINALS: Dict[str, Callable[..., Any]] = {}
_HELIX_REGISTRY: Dict[int, Dict[str, Any]] = {}


def _is_named_workplane(step_plane_name: Optional[str]) -> bool:
    if not step_plane_name:
        return False
    text = str(step_plane_name)
    return text in {"XY", "XZ", "YZ"} or text.startswith("Plane(")


def _serialize_path_arg(value: Any) -> Any:
    type_name = type(value).__name__
    if type_name == "Workplane":
        return {"__workplane_path__": True}
    if type_name == "Wire":
        helix = _HELIX_REGISTRY.get(id(value))
        if helix is not None:
            return {"__helix__": helix}
    return _serialize_value(value)


def get_active_trace() -> OperationTrace:
    global _TRACE
    if _TRACE is None:
        _TRACE = OperationTrace()
    return _TRACE


def reset_trace() -> OperationTrace:
    global _TRACE
    _TRACE = OperationTrace()
    return _TRACE


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        return [float(value.x), float(value.y), float(value.z)]
    type_name = type(value).__name__
    if type_name == "Location":
        origin = None
        wrapped = getattr(value, "wrapped", None)
        if wrapped is not None and hasattr(wrapped, "Transformation"):
            try:
                trsf = wrapped.Transformation()
                trans = trsf.TranslationPart()
                origin = [float(trans.X()), float(trans.Y()), float(trans.Z())]
            except Exception:
                origin = None
        if origin is None:
            for attr in ("toTuple", "toNdtuple"):
                fn = getattr(value, attr, None)
                if callable(fn):
                    raw = fn()
                    if isinstance(raw, (list, tuple)) and raw:
                        first = raw[0] if isinstance(raw[0], (list, tuple)) else raw
                        if isinstance(first, (list, tuple)) and len(first) >= 3:
                            origin = [float(first[0]), float(first[1]), float(first[2])]
                            break
        if origin is not None:
            return origin
    if type_name == "Workplane":
        return {"__workplane_ref__": True}
    return repr(value)


def _plane_state(wp: Any) -> dict[str, Any]:
    plane = getattr(wp, "plane", None)
    if plane is None:
        return {}
    origin = plane.origin
    normal = plane.zDir if hasattr(plane, "zDir") else getattr(plane, "normal", None)
    x_dir = plane.xDir if hasattr(plane, "xDir") else None
    payload: dict[str, Any] = {}
    if origin is not None:
        payload["plane_origin"] = _serialize_value(origin)
    if normal is not None:
        payload["plane_normal"] = _serialize_value(normal)
    if x_dir is not None:
        payload["plane_x_dir"] = _serialize_value(x_dir)
    return payload


def _parent_solid(wp: Any) -> Any:
    try:
        if wp.objects:
            first = wp.objects[0]
            type_name = type(first).__name__.lower()
            if "solid" in type_name or "compound" in type_name:
                return first
            parent = wp.parent
            if parent is not None and hasattr(parent, "val"):
                return parent.val()
    except Exception:
        pass
    try:
        return wp.val()
    except Exception:
        return None


def _record_step(
    wp: Any,
    op: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    selector: Optional[str] = None,
    selection_objects: Optional[list[Any]] = None,
) -> None:
    trace = get_active_trace()
    parent = _parent_solid(wp)
    selections = fingerprint_cq_objects(
        selection_objects or list(getattr(wp, "objects", []) or []),
        parent_solid=parent,
    )
    if op in {"fillet", "chamfer", "hole", "cskHole", "cutBlind", "cutThruAll"} and not selections:
        selections = fingerprint_cq_objects(list(getattr(wp, "objects", []) or []), parent_solid=parent)

    plane_name = str(args[0]) if op == "Workplane" and args else None
    trace.steps.append(
        TraceStep(
            op=op,
            args=[_serialize_value(arg) for arg in args],
            kwargs={key: _serialize_value(value) for key, value in kwargs.items()},
            plane_name=plane_name,
            selector=selector,
            selections=selections,
            **_plane_state(wp),
        )
    )


def _wrap_method(name: str, *, selector: bool = False) -> None:
    import cadquery as cq

    original = getattr(cq.Workplane, name)
    _ORIGINALS[name] = original

    def wrapped(self, *args, **kwargs):
        if name in {"fillet", "chamfer"}:
            _record_step(
                self,
                name,
                args,
                kwargs,
                selection_objects=list(getattr(self, "objects", []) or []),
            )
        elif name == "sweep":
            serialized_args = [_serialize_path_arg(args[0])] if args else []
            _record_step(self, name, tuple(serialized_args), kwargs)
        else:
            _record_step(self, name, args, kwargs, selector=str(args[0]) if selector and args else None)

        result = original(self, *args, **kwargs)

        trace = get_active_trace()
        if not trace.steps:
            return result

        step = trace.steps[-1]
        if name in {
            "box",
            "cylinder",
            "sphere",
            "extrude",
            "revolve",
            "loft",
            "cut",
            "union",
            "intersect",
            "fillet",
            "chamfer",
            "hole",
            "cutBlind",
            "cutThruAll",
            "sweep",
            "shell",
            "cskHole",
        }:
            step.produced_solid = True

        if name in {"faces", "edges"} and args:
            step.selector = str(args[0])
            parent = _parent_solid(result)
            step.selections = fingerprint_cq_objects(
                list(getattr(result, "objects", []) or []),
                parent_solid=parent,
            )
        elif name in {"workplane", "transformed"}:
            plane_state = _plane_state(result)
            for key, value in plane_state.items():
                setattr(step, key, value)

        return result

    setattr(cq.Workplane, name, wrapped)


def _wrap_init() -> None:
    import cadquery as cq

    original_init = cq.Workplane.__init__
    _ORIGINALS["__init__"] = original_init

    def wrapped_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        plane_name = str(args[0]) if args else None
        trace = get_active_trace()
        trace.steps.append(
            TraceStep(
                op="Workplane",
                args=[_serialize_value(arg) for arg in args],
                kwargs={key: _serialize_value(value) for key, value in kwargs.items()},
                plane_name=plane_name,
                **_plane_state(self),
            )
        )

    cq.Workplane.__init__ = wrapped_init


def _wrap_make_helix() -> None:
    import cadquery as cq

    original = cq.Wire.makeHelix
    _ORIGINALS["Wire.makeHelix"] = original

    def wrapped_make_helix(
        pitch: float,
        height: float,
        radius: float,
        center=(0.0, 0.0, 0.0),
        dir=(0.0, 0.0, 1.0),
        **kwargs: Any,
    ):
        wire = original(pitch, height, radius, center=center, dir=dir, **kwargs)
        _HELIX_REGISTRY[id(wire)] = {
            "pitch": float(pitch),
            "height": float(height),
            "radius": float(radius),
            "center": _serialize_value(center),
            "dir": _serialize_value(dir),
        }
        return wire

    cq.Wire.makeHelix = wrapped_make_helix


def install_instrumentation() -> None:
    if _ORIGINALS:
        return
    _HELIX_REGISTRY.clear()
    _wrap_init()
    _wrap_make_helix()
    methods = [
        "box",
        "cylinder",
        "sphere",
        "circle",
        "rect",
        "polygon",
        "polyline",
        "slot2D",
        "spline",
        "shell",
        "moveTo",
        "lineTo",
        "threePointArc",
        "close",
        "mirrorX",
        "mirrorY",
        "extrude",
        "cutBlind",
        "cutThruAll",
        "revolve",
        "loft",
        "hole",
        "cskHole",
        "cut",
        "union",
        "intersect",
        "fillet",
        "chamfer",
        "sweep",
        "faces",
        "edges",
        "workplane",
        "transformed",
        "center",
        "rarray",
        "polarArray",
        "pushPoints",
    ]
    import cadquery as cq

    for method in methods:
        if hasattr(cq.Workplane, method):
            _wrap_method(method, selector=method in {"faces", "edges"})


def remove_instrumentation() -> None:
    import cadquery as cq

    if "Wire.makeHelix" in _ORIGINALS:
        cq.Wire.makeHelix = _ORIGINALS["Wire.makeHelix"]
    if "__init__" in _ORIGINALS:
        cq.Workplane.__init__ = _ORIGINALS["__init__"]
    for name, original in _ORIGINALS.items():
        if name == "__init__":
            continue
        if hasattr(cq.Workplane, name):
            setattr(cq.Workplane, name, original)
    _ORIGINALS.clear()
    _HELIX_REGISTRY.clear()


def trace_to_json(trace: OperationTrace) -> str:
    return json.dumps(trace.to_dict(), ensure_ascii=False, indent=2)
