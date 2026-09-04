"""CAD feature-semantic aggregation and coverage (not CQ API step 1:1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..replay.op_map import (
    COMMITTING_KIND,
    CONTEXT_ONLY_OPS,
    PATTERN_SETUP_OPS,
    PROFILE_OPS,
    SLUG_FOR_KIND,
)
from ..tracer.trace_schema import TraceStep


@dataclass
class FeatureUnit:
    index: int
    kind: str
    slug: str
    cq_trace_kinds: List[str] = field(default_factory=list)
    params: List[str] = field(default_factory=list)
    sftc_lines: Optional[List[int]] = None
    emitted: bool = False
    unsupported: bool = False

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if payload.get("sftc_lines") is None:
            payload.pop("sftc_lines", None)
        return payload


@dataclass
class FeatureSemanticsScore:
    identified_count: int = 0
    emitted_count: int = 0
    unsupported_count: int = 0
    feature_coverage: float = 0.0
    feature_units: List[Dict[str, Any]] = field(default_factory=list)
    unsupported_semantics: List[str] = field(default_factory=list)
    context_only_trace_ops: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _is_named_workplane(plane_name: Optional[str]) -> bool:
    if not plane_name:
        return False
    text = str(plane_name)
    return text in {"XY", "XZ", "YZ"} or text.startswith("Plane(")


def _is_workplane_ref(value: Any) -> bool:
    return isinstance(value, dict) and value.get("__workplane_ref__") is True


def _find_tool_chain_range(steps: Sequence[TraceStep], end_index: int) -> tuple[int, int]:
    """Match replay: nested Workplane…box/profile chains feeding a boolean tool."""
    start = end_index - 1
    while start >= 0:
        step = steps[start]
        if step.op == "Workplane" and _is_named_workplane(step.plane_name):
            candidate = start
            cursor = start - 1
            while cursor >= 0 and steps[cursor].op in {
                "circle",
                "rect",
                "polygon",
                "polyline",
                "moveTo",
                "lineTo",
                "threePointArc",
                "close",
                "mirrorX",
                "mirrorY",
                "center",
                "transformed",
            }:
                cursor -= 1
            if (
                cursor >= 0
                and steps[cursor].op == "Workplane"
                and _is_named_workplane(steps[cursor].plane_name)
            ):
                candidate = cursor
            return candidate, end_index
        start -= 1
    return end_index, end_index


def identify_feature_units(steps: Sequence[TraceStep]) -> List[FeatureUnit]:
    """Aggregate CQ trace steps into CAD feature semantic units.

    Profile ops (moveTo/lineTo/circle/…) fold into the next committing op.
    Context ops (faces/workplane/…) never form their own feature.
    Nested boolean tool chains (Workplane+box/profile before cut/union) fold into
    the boolean feature — matching replay consumption.
    """
    units: List[FeatureUnit] = []
    pending: List[str] = []
    context_seen: List[str] = []

    consumed: set[int] = set()
    for index, step in enumerate(steps):
        if step.op in {"cut", "union", "intersect"} and step.args and _is_workplane_ref(step.args[0]):
            start, end = _find_tool_chain_range(steps, index)
            for consumed_index in range(start, end):
                consumed.add(consumed_index)

    for index, step in enumerate(steps):
        if index in consumed:
            continue
        op = step.op
        if op == "Workplane":
            if _is_named_workplane(step.plane_name):
                context_seen.append(op)
            continue
        if op in CONTEXT_ONLY_OPS:
            context_seen.append(op)
            continue
        if op in PROFILE_OPS or op in PATTERN_SETUP_OPS:
            pending.append(op)
            continue
        if op in COMMITTING_KIND:
            if op in {"cut", "union", "intersect"} and step.args and _is_workplane_ref(step.args[0]):
                kinds = [op]
            else:
                kinds = pending + [op]
            pending = []
            kind = COMMITTING_KIND[op]
            units.append(
                FeatureUnit(
                    index=len(units) + 1,
                    kind=kind,
                    slug=SLUG_FOR_KIND.get(kind, op),
                    cq_trace_kinds=kinds,
                )
            )
            continue
        if pending:
            pending = []
        units.append(
            FeatureUnit(
                index=len(units) + 1,
                kind=f"Unsupported:{op}",
                slug=op,
                cq_trace_kinds=[op],
                unsupported=True,
            )
        )

    for unit in units:
        unit.__dict__["_context_hint"] = list(dict.fromkeys(context_seen))
    return units


def build_feature_manifest(
    *,
    identified: Sequence[FeatureUnit],
    emitted: Sequence[Dict[str, Any]],
    unsupported_notes: Sequence[str] = (),
    context_only_trace_ops: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Merge identified semantics with emitted Feature blocks into a sidecar."""
    identified_list = list(identified)
    emitted_list = [dict(unit) for unit in emitted]

    context_ops = list(context_only_trace_ops or [])
    if not context_ops and identified_list:
        hint = identified_list[0].__dict__.get("_context_hint")
        if hint:
            context_ops = list(hint)

    identified_count = len(identified_list)
    emitted_ok = len([unit for unit in emitted_list if not unit.get("unsupported")])

    if identified_count == 0:
        coverage = 1.0 if emitted_ok else 0.0
    else:
        matched = 0
        for index, unit in enumerate(identified_list):
            if unit.unsupported:
                continue
            if index < len(emitted_list):
                matched += 1
        coverage = matched / identified_count

    unsupported_semantics = [unit.kind for unit in identified_list if unit.unsupported]
    unsupported_semantics.extend(str(note) for note in unsupported_notes)

    if emitted_list:
        feature_units = emitted_list
        for unit in feature_units:
            unit.setdefault("emitted", True)
    else:
        feature_units = [unit.to_dict() for unit in identified_list]

    return {
        "feature_units": feature_units,
        "unsupported_semantics": list(dict.fromkeys(unsupported_semantics)),
        "context_only_trace_ops": list(dict.fromkeys(context_ops)),
        "identified_count": identified_count or len(feature_units),
        "emitted_count": emitted_ok,
        "feature_coverage": coverage,
    }


def score_feature_semantics(
    feature_manifest: Dict[str, Any],
    *,
    unsupported: Optional[Iterable[str]] = None,
) -> FeatureSemanticsScore:
    units = list(feature_manifest.get("feature_units") or [])
    identified = int(feature_manifest.get("identified_count") or len(units))
    emitted = int(
        feature_manifest.get("emitted_count")
        or sum(1 for unit in units if unit.get("emitted", True) and not unit.get("unsupported"))
    )
    coverage = float(feature_manifest.get("feature_coverage") or 0.0)
    if identified and "feature_coverage" not in feature_manifest:
        coverage = emitted / identified
    unsupported_list = list(feature_manifest.get("unsupported_semantics") or [])
    if unsupported:
        for note in unsupported:
            text = str(note)
            if text not in unsupported_list:
                unsupported_list.append(text)
    return FeatureSemanticsScore(
        identified_count=identified,
        emitted_count=emitted,
        unsupported_count=len(unsupported_list),
        feature_coverage=coverage,
        feature_units=units,
        unsupported_semantics=unsupported_list,
        context_only_trace_ops=list(feature_manifest.get("context_only_trace_ops") or []),
    )


def empty_manifest() -> Dict[str, Any]:
    return {
        "feature_units": [],
        "unsupported_semantics": [],
        "context_only_trace_ops": [],
        "identified_count": 0,
        "emitted_count": 0,
        "feature_coverage": 0.0,
    }
