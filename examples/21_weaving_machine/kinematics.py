"""Independent joint declarations and coverage audit; not a general DOF solver."""

from __future__ import annotations

import math
from dataclasses import dataclass

import simplecadapi as scad


@dataclass(frozen=True)
class JointContract:
    joint_id: str
    parent_component_id: str
    child_component_id: str
    joint_kind: str
    axis: tuple[float, float, float]
    lower_limit: float
    upper_limit: float
    mechanical_zero: float
    safe_hold: str

    def __post_init__(self) -> None:
        if self.joint_kind != "prismatic":
            raise ValueError("the initial fixture supports only a prismatic contract")
        if (
            self.lower_limit > self.mechanical_zero
            or self.mechanical_zero > self.upper_limit
        ):
            raise ValueError("mechanical zero must lie inside joint limits")
        magnitude = math.sqrt(sum(value * value for value in self.axis))
        if not math.isclose(magnitude, 1.0, abs_tol=1.0e-12):
            raise ValueError("joint axis must be a unit vector")
        if not self.safe_hold.strip():
            raise ValueError("safe_hold must not be empty")

    def resolve_drive(self, drive_distance: float, *, clamp: bool) -> float:
        if not math.isfinite(drive_distance):
            raise ValueError("drive_distance must be finite")
        if clamp:
            return min(max(drive_distance, self.lower_limit), self.upper_limit)
        if not self.lower_limit <= drive_distance <= self.upper_limit:
            raise ValueError(
                f"drive_distance {drive_distance} outside "
                f"[{self.lower_limit}, {self.upper_limit}]"
            )
        return drive_distance


@dataclass(frozen=True)
class JointAudit:
    passed: bool
    component_coverage: bool
    constraint_matches: bool
    axis_matches: bool
    message: str


def audit_joint_contract(
    *,
    assembly: scad.Assembly,
    contract: JointContract,
) -> JointAudit:
    component_ids = set(assembly.component_ids())
    component_coverage = (
        contract.parent_component_id in component_ids
        and contract.child_component_id in component_ids
        and contract.parent_component_id in assembly.grounded_component_ids
    )
    matching = [
        item
        for item in assembly.constraints
        if item.constraint_id == contract.joint_id
        and item.constraint_kind == contract.joint_kind
        and item.connector_a.component_id == contract.parent_component_id
        and item.connector_b.component_id == contract.child_component_id
    ]
    constraint_matches = len(matching) == 1
    axis_matches = False
    if constraint_matches:
        constraint = matching[0]
        parent = assembly.get_component(contract.parent_component_id)
        connector = parent.item.get_connector(constraint.connector_a.connector_id)
        axis_matches = all(
            math.isclose(actual, expected, abs_tol=1.0e-12)
            for actual, expected in zip(connector.placement.z_axis, contract.axis)
        )
    passed = component_coverage and constraint_matches and axis_matches
    message = (
        "joint declaration and component coverage agree; this is not a generic DOF/rank proof"
        if passed
        else "joint declaration does not match assembly coverage, constraint, or axis"
    )
    return JointAudit(
        passed, component_coverage, constraint_matches, axis_matches, message
    )
