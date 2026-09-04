"""Edit-bench scoring: param diff + instruction alignment."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .parameters import extract_scad_vars

_NUM = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


@dataclass
class EditScore:
    edit_param_diff_count: int = 0
    param_diff: Dict[str, List[float]] = field(default_factory=dict)
    edit_instruction_align: bool = False
    edit_geometry_ok: Optional[bool] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_param_diff(
    orig_sftc: str,
    gt_sftc: str,
    *,
    tol: float = 1e-6,
) -> Dict[str, List[float]]:
    orig = extract_scad_vars(orig_sftc)
    gt = extract_scad_vars(gt_sftc)
    names = sorted(set(orig) | set(gt))
    diff: Dict[str, List[float]] = {}
    for name in names:
        a = orig.get(name)
        b = gt.get(name)
        if a is None or b is None:
            if a is None and b is not None:
                diff[name] = [float("nan"), b]
            elif b is None and a is not None:
                diff[name] = [a, float("nan")]
            continue
        if abs(a - b) > tol:
            diff[name] = [a, b]
    return diff


def _instruction_numeric_change(instruction: str) -> Optional[Tuple[Optional[float], float]]:
    """Return (from, to) or (None, to) when only a target value is stated."""
    nums = [float(x) for x in _NUM.findall(instruction)]
    if len(nums) >= 2:
        return nums[0], nums[1]
    if len(nums) == 1:
        return None, nums[0]
    return None


def _approx(a: float, b: float, *, tol: float = 1e-3) -> bool:
    if math.isnan(a) or math.isnan(b):
        return False
    return abs(a - b) <= tol * max(1.0, abs(b))


def _diff_pairs_aligned(
    diff: Dict[str, List[float]],
    from_v: Optional[float],
    to_v: float,
) -> bool:
    if not diff:
        return False
    for old, new in diff.values():
        if from_v is not None and not _approx(old, from_v):
            return False
        if not _approx(new, to_v):
            return False
    return True


def _feature_add_remove_align(
    instruction: str,
    diff: Dict[str, List[float]],
) -> Optional[Dict[str, Any]]:
    """T4 feature_edit: add/remove hole/cylinder often introduces radius(+height) vars."""
    q = instruction.lower()
    added = {n: pair[1] for n, pair in diff.items() if math.isnan(pair[0]) and not math.isnan(pair[1])}
    removed = {n: pair[0] for n, pair in diff.items() if math.isnan(pair[1]) and not math.isnan(pair[0])}
    changed_set = added if added else removed
    if not changed_set:
        return None

    nums = [float(x) for x in _NUM.findall(instruction)]
    diameter = None
    radius = None
    if "diameter" in q and nums:
        diameter = nums[0]
        radius = diameter / 2.0
    elif "radius" in q and nums:
        radius = nums[0]
        diameter = radius * 2.0

    radius_hits = [
        (n, v)
        for n, v in changed_set.items()
        if "radius" in n.lower() and radius is not None and _approx(v, radius)
    ]
    diameter_hits = [
        (n, v)
        for n, v in changed_set.items()
        if "diameter" in n.lower() and diameter is not None and _approx(v, diameter)
    ]
    if not radius_hits and not diameter_hits:
        # depth-only feature (e.g. hex socket depth)
        if "deep" in q or "depth" in q:
            depth_hits = [
                (n, v)
                for n, v in changed_set.items()
                if "depth" in n.lower() or "extrude" in n.lower()
            ]
            if depth_hits and nums:
                for n, v in depth_hits:
                    if any(_approx(v, num) for num in nums):
                        return {
                            "mode": "feature_depth",
                            "matched_params": [n],
                            "action": "add" if added else "remove",
                        }
        return None

    return {
        "mode": "feature_add_remove",
        "matched_params": [n for n, _ in (radius_hits or diameter_hits)],
        "action": "add" if added else "remove",
    }


def score_edit(
    *,
    orig_sftc: str,
    gt_sftc: str,
    instruction: str = "",
    edit_geometry_ok: Optional[bool] = None,
    category_label: str = "",
) -> EditScore:
    diff = compute_param_diff(orig_sftc, gt_sftc)
    align = False
    details: Dict[str, Any] = {}
    change = _instruction_numeric_change(instruction)
    label = (category_label or "").lower()

    if change is not None and diff:
        from_v, to_v = change
        finite_diff = {
            n: pair
            for n, pair in diff.items()
            if not math.isnan(pair[0]) and not math.isnan(pair[1])
        }
        if finite_diff and _diff_pairs_aligned(finite_diff, from_v, to_v):
            align = True
            details["matched_params"] = sorted(finite_diff.keys())
        elif from_v is None and finite_diff and len({round(pair[1], 6) for pair in finite_diff.values()}) == 1:
            only_new = next(iter(finite_diff.values()))[1]
            if _approx(only_new, to_v):
                align = True
                details["matched_params"] = sorted(finite_diff.keys())
                details["mode"] = "target_only"

    if not align and diff and label in {"feature_edit", ""}:
        feature = _feature_add_remove_align(instruction, diff)
        if feature:
            align = True
            details.update(feature)

    if not align:
        if change is not None and not diff:
            details["reason"] = "instruction_has_numbers_but_no_param_diff"
        elif change is not None and diff:
            details.setdefault("reason", f"param_diff_count={len(diff)}")
        elif not change and diff:
            # Still try feature add/remove without numbers (e.g. remove second leg)
            if any(math.isnan(pair[0]) or math.isnan(pair[1]) for pair in diff.values()):
                details["reason"] = "feature_diff_without_numeric_instruction"
                if label == "feature_edit" and len(diff) <= 4:
                    # Soft align: exclusive add/remove of a small param cluster
                    align = True
                    details["mode"] = "feature_cluster_add_remove"
                    details["matched_params"] = sorted(diff.keys())
            else:
                details["reason"] = "no_numeric_instruction"
        elif not diff:
            details["reason"] = "no_param_diff"

    return EditScore(
        edit_param_diff_count=len(diff),
        param_diff=diff,
        edit_instruction_align=align,
        edit_geometry_ok=edit_geometry_ok,
        details=details,
    )
