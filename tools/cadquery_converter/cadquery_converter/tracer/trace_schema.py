"""Trace schema for CadQuery execution logging."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GeoFingerprint:
    kind: str
    index: Optional[int] = None
    geom_type: Optional[str] = None
    center: Optional[List[float]] = None
    normal: Optional[List[float]] = None
    direction: Optional[List[float]] = None
    length: Optional[float] = None
    area: Optional[float] = None
    bbox: Optional[Dict[str, List[float]]] = None
    start: Optional[List[float]] = None
    end: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass
class TraceStep:
    op: str
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    plane_name: Optional[str] = None
    plane_origin: Optional[List[float]] = None
    plane_normal: Optional[List[float]] = None
    plane_x_dir: Optional[List[float]] = None
    selector: Optional[str] = None
    selections: List[GeoFingerprint] = field(default_factory=list)
    produced_solid: bool = False

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "op": self.op,
            "args": self.args,
            "kwargs": self.kwargs,
            "plane_name": self.plane_name,
            "plane_origin": self.plane_origin,
            "plane_normal": self.plane_normal,
            "plane_x_dir": self.plane_x_dir,
            "selector": self.selector,
            "selections": [item.to_dict() for item in self.selections],
            "produced_solid": self.produced_solid,
        }
        return {key: value for key, value in payload.items() if value not in (None, [], {})}


@dataclass
class OperationTrace:
    steps: List[TraceStep] = field(default_factory=list)
    cq_status: str = "ok"
    error: str = ""
    cq_volume: Optional[float] = None
    cq_bbox: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cq_status": self.cq_status,
            "error": self.error,
            "cq_volume": self.cq_volume,
            "cq_bbox": self.cq_bbox,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OperationTrace":
        steps = []
        for raw in payload.get("steps", []):
            selections = [
                GeoFingerprint(**{key: value for key, value in item.items()})
                for item in raw.get("selections", [])
            ]
            steps.append(
                TraceStep(
                    op=str(raw["op"]),
                    args=list(raw.get("args", [])),
                    kwargs=dict(raw.get("kwargs", {})),
                    plane_name=raw.get("plane_name"),
                    plane_origin=raw.get("plane_origin"),
                    plane_normal=raw.get("plane_normal"),
                    plane_x_dir=raw.get("plane_x_dir"),
                    selector=raw.get("selector"),
                    selections=selections,
                    produced_solid=bool(raw.get("produced_solid", False)),
                )
            )
        return cls(
            steps=steps,
            cq_status=str(payload.get("cq_status", "ok")),
            error=str(payload.get("error", "")),
            cq_volume=payload.get("cq_volume"),
            cq_bbox=payload.get("cq_bbox"),
        )
