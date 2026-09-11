"""Failure-time geometric diagnosis and evidence rendering.

Diagnosis runs only on failure paths, computes the geometric facts behind the
failure (measurements), and optionally renders one evidence image next to the
part-cache root. Everything here is best-effort: a diagnosis crash must never
replace the real error, so public entries swallow their own failures.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from ..errors import ErrorEvidence, ErrorMeasurement
from ..kernel.ocp_booleans import common_shapes
from ..kernel.ocp_properties import volume

_DISABLE_ENV = "SCA_NO_DIAGNOSTIC_RENDER"
_TRUTHY = {"1", "true", "yes", "on"}

# Cap on pairwise probes: boolean inputs are small in practice; guard the
# quadratic blow-up for pathological operand counts instead of hanging the
# failure path.
_MAX_PAIR_PROBES = 256


def diagnostics_enabled() -> bool:
    return os.environ.get(_DISABLE_ENV, "").strip().lower() not in _TRUTHY


def diagnostics_dir() -> Path:
    """Diagnostics directory anchored next to the part-cache root.

    Follows the ``@part`` cache resolution (project config and SCA_CACHE_ROOT
    environment overrides included): cache root ``<anchor>/.simplecad/cache``
    yields ``<anchor>/.simplecad/diagnostics``.
    """

    # Lazy import: cache.__init__ pulls artifacts, which would cycle through
    # operators at module import time.
    from ..cache.policy import resolve_cache_policy

    policy = resolve_cache_policy(None, project_root=".")
    return policy.root.parent / "diagnostics"


def render_failure_evidence(
    shapes: Sequence[Any],
    *,
    operation: str,
    view: str = "default",
    caption: str = "",
) -> Optional[ErrorEvidence]:
    """Render one diagnostic image; never raises, returns None when disabled/failed."""

    if not diagnostics_enabled():
        return None
    try:
        root = diagnostics_dir()
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = root / f"{operation}-{stamp}.png"
        from .features import render_screenshot_rpath

        render_screenshot_rpath(shapes, str(path))
        return ErrorEvidence(
            kind="render",
            path=str(path),
            view=view,
            caption=caption,
        )
    except Exception:
        return None


@dataclass(frozen=True)
class ClosestApproach:
    """Exact minimum distance between two shapes with the supporting points."""

    gap: float
    point_a: Tuple[float, float, float]
    point_b: Tuple[float, float, float]


def closest_approach(shape_a: Any, shape_b: Any) -> Optional[ClosestApproach]:
    try:
        tool = BRepExtrema_DistShapeShape(shape_a, shape_b)
        tool.Perform()
        if not tool.IsDone() or tool.NbSolution() < 1:
            return None
        pa: gp_Pnt = tool.PointOnShape1(1)
        pb: gp_Pnt = tool.PointOnShape2(1)
        return ClosestApproach(
            gap=float(tool.Value()),
            point_a=(float(pa.X()), float(pa.Y()), float(pa.Z())),
            point_b=(float(pb.X()), float(pb.Y()), float(pb.Z())),
        )
    except Exception:
        return None


@dataclass
class BooleanDiagnosis:
    """Classified boolean failure with measurements, repair steps, and evidence."""

    failure_kind: str  # "disjoint" | "non_manifold_contact" | "unknown"
    what_happened: Optional[str] = None
    possible_causes: Optional[List[str]] = None
    measurements: List[ErrorMeasurement] = field(default_factory=list)
    repair: List[str] = field(default_factory=list)
    evidence_shapes: List[Any] = field(default_factory=list)
    evidence_caption: str = ""


def _vector_display(vector: Sequence[float]) -> str:
    return "(" + ", ".join(f"{float(v):.4g}" for v in vector) + ")"


def _overlap_volume(shape_a: Any, shape_b: Any) -> float:
    """Positive-volume intersection of two shapes; 0.0 when disjoint or touching only."""

    try:
        common = common_shapes([shape_a, shape_b])
        total = 0.0
        explorer = TopExp_Explorer(common, TopAbs_SOLID)
        while explorer.More():
            total += volume(TopoDS.Solid_s(explorer.Current()))
            explorer.Next()
        return total
    except Exception:
        return 0.0


def _diagnose_pair(
    index_a: int,
    index_b: int,
    solid_a: Any,
    solid_b: Any,
    effective_tol: float,
    operation_kind: str = "union",
) -> Optional[BooleanDiagnosis]:
    approach = closest_approach(solid_a.wrapped, solid_b.wrapped)
    if approach is None:
        return None
    label_a = f"operand {index_a + 1}"
    label_b = f"operand {index_b + 1}"
    move_vector = tuple(pb - pa for pa, pb in zip(approach.point_a, approach.point_b))
    if approach.gap > effective_tol:
        disjoint_causes = {
            "union": [
                "The operands are separated in space, so the union cannot produce exactly one solid.",
                "A placement/translation moved one operand away from the other.",
            ],
            "cut": [
                "The tool never reaches the base solid, so the cut removes nothing.",
                "A placement/translation moved the tool away from the base solid.",
            ],
            "intersect": [
                "The operands are separated in space, so the intersection is empty.",
                "A placement/translation moved one operand away from the other.",
            ],
        }
        disjoint_repair = {
            "union": [
                (
                    f"Move {label_b} by {_vector_display(move_vector)} "
                    f"(≥ {approach.gap:.4g} mm) so the operands touch, "
                    "or extend one operand across the gap."
                ),
                "If the pieces are meant to stay separate, build an assembly "
                "(make_assembly_rassembly) instead of a single-solid union.",
            ],
            "cut": [
                (
                    f"Move the tool {label_b} by {_vector_display(move_vector)} "
                    f"(≥ {approach.gap:.4g} mm) so it reaches inside the base solid, "
                    "or extend the tool across the gap."
                ),
                "Check the intended removal region: with this gap the cut is a no-op on the base solid.",
            ],
            "intersect": [
                (
                    f"Move {label_b} by {_vector_display(move_vector)} "
                    f"(≥ {approach.gap:.4g} mm) so the operands share a positive-volume overlap."
                ),
            ],
        }
        return BooleanDiagnosis(
            failure_kind="disjoint",
            what_happened=(
                f"separated solids: {label_a} and {label_b} never touch; "
                f"nearest detected gap is {approach.gap:.4g} mm "
                f"(tolerance {effective_tol:.4g})"
            ),
            possible_causes=disjoint_causes.get(operation_kind, disjoint_causes["union"]),
            measurements=[
                ErrorMeasurement("min_gap", approach.gap, "mm"),
                ErrorMeasurement("closest_point_a", approach.point_a, "mm"),
                ErrorMeasurement("closest_point_b", approach.point_b, "mm"),
                ErrorMeasurement("closure_vector_a_to_b", move_vector, "mm"),
            ],
            repair=disjoint_repair.get(operation_kind, disjoint_repair["union"]),
            evidence_shapes=[solid_a, solid_b],
            evidence_caption=(
                f"{label_a} and {label_b}; nearest gap {approach.gap:.4g} mm "
                "between the two closest points (see measurements)"
            ),
        )
    if approach.gap <= effective_tol and _overlap_volume(solid_a.wrapped, solid_b.wrapped) < 1e-12:
        contact_repair = {
            "cut": [
                (
                    "The tool only grazes the base solid; translate the tool "
                    f"along {_vector_display(move_vector)} by a working depth "
                    "(e.g. 0.5 mm beyond touch) so it removes real volume."
                ),
            ],
            "intersect": [
                (
                    "The operands only graze each other; translate one along "
                    f"{_vector_display(move_vector)} by a working depth "
                    "(e.g. 0.5 mm beyond touch) to create a positive-volume overlap."
                ),
            ],
        }
        default_contact_repair = [
            (
                "Give the contact a positive-volume overlap: translate one operand "
                f"along {_vector_display(move_vector)} by a working overlap "
                "(e.g. 0.5 mm beyond touch) and retry."
            ),
            "For intended face contact, make the shared face finite in area and "
            "coincident; no artificial overlap is required.",
        ]
        return BooleanDiagnosis(
            failure_kind="non_manifold_contact",
            what_happened=(
                f"operands meet only along an edge, vertex, or tangent "
                f"(measured gap {approach.gap:.4g} mm ≤ tol {effective_tol:.4g}), "
                "which is not one manifold solid"
            ),
            possible_causes=[
                "The operands touch without a finite-area face or positive-volume overlap.",
            ],
            measurements=[
                ErrorMeasurement("min_gap", approach.gap, "mm"),
                ErrorMeasurement("closest_point_a", approach.point_a, "mm"),
                ErrorMeasurement("closest_point_b", approach.point_b, "mm"),
            ],
            repair=contact_repair.get(operation_kind, default_contact_repair),
            evidence_shapes=[solid_a, solid_b],
            evidence_caption=f"{label_a} and {label_b} in edge/vertex/tangent-only contact",
        )
    return None


def diagnose_boolean_failure(
    operands: Optional[Sequence[Any]],
    *,
    effective_tol: Optional[float],
    operation_kind: str = "union",
) -> Optional[BooleanDiagnosis]:
    """Classify a boolean failure from its operands; never raises.

    Probes operand pairs for the nearest separated pair (disjoint) or the
    touching-but-not-merged pair (non-manifold contact). Returns None when the
    operands are unavailable or no pair explains the failure.
    """

    try:
        if not operands or len(operands) < 2:
            return None
        tol = float(effective_tol or 0.0)
        probes = 0
        best_disjoint: Optional[BooleanDiagnosis] = None
        best_contact: Optional[BooleanDiagnosis] = None
        for i in range(len(operands)):
            for j in range(i + 1, len(operands)):
                if probes >= _MAX_PAIR_PROBES:
                    break
                probes += 1
                candidate = _diagnose_pair(
                    i, j, operands[i], operands[j], tol, operation_kind
                )
                if candidate is None:
                    continue
                if candidate.failure_kind == "disjoint":
                    gap = candidate.measurements[0].value
                    if best_disjoint is None or gap < best_disjoint.measurements[0].value:
                        best_disjoint = candidate
                elif candidate.failure_kind == "non_manifold_contact":
                    if best_contact is None:
                        best_contact = candidate
        if best_disjoint is not None:
            return best_disjoint
        return best_contact
    except Exception:
        return None
