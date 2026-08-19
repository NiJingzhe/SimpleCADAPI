"""Assembly connector resolution and constraint solving."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union, cast

from .assembly import (
    Assembly,
    _AUTHORED_PLACEMENTS_RUNTIME_KEY,
    _with_component_path_placement,
)
from .connector import (
    Connector,
    ConnectorAnchor,
    ConnectorRef,
    resolve_connector,
    resolve_connector_placement,
)
from .constraint import (
    Constraint,
    ConstraintReport,
    ConstraintResidual,
    _is_connecting_constraint,
    _is_coupling_constraint,
)
from .placement import (
    Placement,
    _norm,
    identity_placement,
    inverse_placement,
    relative_placement,
    rotate_z_placement,
    translate_z_placement,
)

_PLACEMENT_TOLERANCE = 1e-7
_ANGLE_TOLERANCE_DEGREES = 1e-6


def constraint_reports_match(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> bool:
    """Compare reports by semantic identity and solver-scale numeric tolerance."""
    report_fields = {
        "solved",
        "grounded_component_ids",
        "solved_component_ids",
        "unsolved_component_ids",
        "residuals",
    }
    residual_fields = {
        "constraint_id",
        "translation_error",
        "angular_error_degrees",
        "within_tolerance",
    }
    if set(actual) != report_fields or set(expected) != report_fields:
        return False
    if actual["solved"] != expected["solved"]:
        return False
    for field in (
        "grounded_component_ids",
        "solved_component_ids",
        "unsolved_component_ids",
    ):
        actual_ids = actual[field]
        expected_ids = expected[field]
        if not isinstance(actual_ids, list) or not isinstance(expected_ids, list):
            return False
        if len(actual_ids) != len(set(actual_ids)) or len(expected_ids) != len(
            set(expected_ids)
        ):
            return False
        if set(actual_ids) != set(expected_ids):
            return False
    actual_residuals = actual["residuals"]
    expected_residuals = expected["residuals"]
    if not isinstance(actual_residuals, list) or not isinstance(
        expected_residuals, list
    ):
        return False
    actual_by_id: Dict[str, Mapping[str, Any]] = {}
    expected_by_id: Dict[str, Mapping[str, Any]] = {}
    for residuals, target in (
        (actual_residuals, actual_by_id),
        (expected_residuals, expected_by_id),
    ):
        for item in residuals:
            if not isinstance(item, Mapping) or set(item) != residual_fields:
                return False
            constraint_id = str(item["constraint_id"])
            if constraint_id in target:
                return False
            target[constraint_id] = item
    if set(actual_by_id) != set(expected_by_id):
        return False
    for constraint_id, actual_item in actual_by_id.items():
        expected_item = expected_by_id[constraint_id]
        if actual_item["within_tolerance"] != expected_item["within_tolerance"]:
            return False
        try:
            translation_matches = math.isclose(
                float(actual_item["translation_error"]),
                float(expected_item["translation_error"]),
                rel_tol=0.0,
                abs_tol=_PLACEMENT_TOLERANCE,
            )
            angular_matches = math.isclose(
                float(actual_item["angular_error_degrees"]),
                float(expected_item["angular_error_degrees"]),
                rel_tol=0.0,
                abs_tol=_ANGLE_TOLERANCE_DEGREES,
            )
        except (TypeError, ValueError):
            return False
        if not translation_matches or not angular_matches:
            return False
    return True


CouplingEndpoint = Tuple[str, Union[Constraint, ConnectorRef]]


def solve_assembly_constraints(assembly: Assembly, strict: bool = True) -> Assembly:
    if not isinstance(assembly, Assembly):
        raise TypeError("assembly must be an Assembly")
    definition_runtime = {
        key: value
        for key, value in assembly._runtime.items()
        if key.startswith("definition.")
    }
    authored_component_placements = assembly._get_runtime(
        _AUTHORED_PLACEMENTS_RUNTIME_KEY
    )
    if authored_component_placements is None:
        authored_component_placements = {
            component.component_id: component.placement.to_dict()
            for component in assembly.components
        }
    if not assembly.constraints:
        return assembly
    if not assembly.grounded_component_ids:
        raise ValueError("assembly constraints require at least one grounded component")
    solved: Dict[str, Placement] = {
        component_id: assembly.get_component(component_id).placement
        for component_id in assembly.grounded_component_ids
    }

    pending = [
        constraint
        for constraint in assembly.constraints
        if _is_connecting_constraint(constraint)
    ]
    progressed = True
    while pending and progressed:
        progressed = False
        remaining: List[Constraint] = []
        for constraint in pending:
            a_id = constraint.connector_a.component_id
            b_id = constraint.connector_b.component_id
            if a_id in solved and b_id not in solved:
                bounds = _constraint_scalar_bounds(constraint)
                if (
                    constraint.constraint_kind == "revolute"
                    and constraint.drive_angle_degrees is not None
                ):
                    scalar = _project_scalar(constraint.drive_angle_degrees, bounds)
                elif (
                    constraint.constraint_kind == "prismatic"
                    and constraint.drive_distance is not None
                ):
                    scalar = _project_scalar(constraint.drive_distance, bounds)
                elif bounds is not None:
                    scalar = _project_scalar(
                        _constraint_current_scalar(assembly, constraint), bounds
                    )
                else:
                    scalar = None
                solved[b_id] = _solve_other_component(
                    assembly,
                    constraint,
                    known_side="a",
                    known_placement=solved[a_id],
                    scalar_override=scalar,
                )
                progressed = True
            elif b_id in solved and a_id not in solved:
                bounds = _constraint_scalar_bounds(constraint)
                if (
                    constraint.constraint_kind == "revolute"
                    and constraint.drive_angle_degrees is not None
                ):
                    scalar = _project_scalar(constraint.drive_angle_degrees, bounds)
                elif (
                    constraint.constraint_kind == "prismatic"
                    and constraint.drive_distance is not None
                ):
                    scalar = _project_scalar(constraint.drive_distance, bounds)
                elif bounds is not None:
                    scalar = _project_scalar(
                        _constraint_current_scalar(assembly, constraint), bounds
                    )
                else:
                    scalar = None
                solved[a_id] = _solve_other_component(
                    assembly,
                    constraint,
                    known_side="b",
                    known_placement=solved[b_id],
                    scalar_override=scalar,
                )
                progressed = True
            elif a_id in solved and b_id in solved:
                candidate = assembly.with_component_placement(
                    a_id, solved[a_id]
                ).with_component_placement(b_id, solved[b_id])
                residual = measure_constraint_residual(
                    candidate,
                    constraint.constraint_id,
                )
                if not residual.within_tolerance:
                    adjusted = _try_close_forwarded_constraint(candidate, constraint)
                    if adjusted is not None:
                        assembly = adjusted
                    elif strict:
                        raise ValueError(
                            f"constraint '{constraint.constraint_id}' residual exceeds tolerance"
                        )
            else:
                remaining.append(constraint)
        pending = remaining

    for constraint in pending:
        a_id = constraint.connector_a.component_id
        b_id = constraint.connector_b.component_id
        bounds = _constraint_scalar_bounds(constraint)
        if bounds is None:
            if strict:
                raise ValueError(
                    f"constraint '{constraint.constraint_id}' forms an unresolvable loop"
                )
            continue
        if a_id in solved and b_id in solved:
            known_side = "a"
            known_placement = solved[a_id]
        elif b_id in solved:
            known_side = "b"
            known_placement = solved[b_id]
        else:
            if strict:
                raise ValueError(
                    f"constraint '{constraint.constraint_id}' has no grounded path"
                )
            continue

        lo, hi = bounds
        obj = lambda s: _loop_constraint_residual_at_scalar(
            assembly, constraint, known_side, known_placement, s
        )
        optimal_scalar = _golden_section_search(obj, lo, hi)
        if known_side == "a":
            solved[b_id] = _solve_other_component(
                assembly,
                constraint,
                known_side="a",
                known_placement=known_placement,
                scalar_override=optimal_scalar,
            )
        else:
            solved[a_id] = _solve_other_component(
                assembly,
                constraint,
                known_side="b",
                known_placement=known_placement,
                scalar_override=optimal_scalar,
            )

    unsolved = tuple(
        component.component_id
        for component in assembly.components
        if component.component_id not in solved
    )
    if strict and unsolved:
        raise ValueError(
            "unsolved components in constrained assembly: " + ", ".join(unsolved)
        )
    result = assembly
    for component_id, placement in solved.items():
        result = result.with_component_placement(component_id, placement)
    result = _solve_coupling_constraints(result)
    report = inspect_assembly_constraints(result)
    if strict:
        failed = [
            residual.constraint_id
            for residual in report.residuals
            if not residual.within_tolerance
        ]
        if failed:
            raise ValueError(
                "constraint residual exceeds tolerance: " + ", ".join(failed)
            )
    result._set_runtime("constraint_report", report.to_dict())
    result._set_runtime(
        _AUTHORED_PLACEMENTS_RUNTIME_KEY,
        authored_component_placements,
    )
    for key, value in definition_runtime.items():
        result._set_runtime(key, value)
    return result


def measure_constraint_residual(
    assembly: Assembly, constraint_id: str
) -> ConstraintResidual:
    if not isinstance(assembly, Assembly):
        raise TypeError("assembly must be an Assembly")
    constraint = assembly.get_constraint(constraint_id)
    if _is_coupling_constraint(constraint):
        return _measure_coupling_constraint_residual(assembly, constraint)
    frame_a = _connector_world_frame(assembly, constraint.connector_a)
    frame_b = _connector_world_frame(assembly, constraint.connector_b)
    current_scalar = _constraint_current_scalar(assembly, constraint)
    motion = _motion_from_scalar(constraint, current_scalar)
    expected_b = frame_a.compose(motion)
    relative = relative_placement(expected_b, frame_b)
    translation_error = _norm(relative.origin)
    angular_error = _angular_error_degrees(relative)
    return ConstraintResidual(
        constraint.constraint_id,
        translation_error,
        angular_error,
        translation_error <= _PLACEMENT_TOLERANCE
        and angular_error <= _ANGLE_TOLERANCE_DEGREES,
    )


def inspect_assembly_constraints(assembly: Assembly) -> ConstraintReport:
    if not isinstance(assembly, Assembly):
        raise TypeError("assembly must be an Assembly")
    residuals = tuple(
        measure_constraint_residual(assembly, constraint.constraint_id)
        for constraint in assembly.constraints
    )
    all_ids = tuple(component.component_id for component in assembly.components)
    if assembly.constraints:
        reachable = set(assembly.grounded_component_ids)
        progressed = True
        while progressed:
            progressed = False
            for constraint in assembly.constraints:
                if not _is_connecting_constraint(constraint):
                    continue
                a_id = constraint.connector_a.component_id
                b_id = constraint.connector_b.component_id
                if a_id in reachable and b_id not in reachable:
                    reachable.add(b_id)
                    progressed = True
                if b_id in reachable and a_id not in reachable:
                    reachable.add(a_id)
                    progressed = True
        solved_ids = tuple(
            component_id for component_id in all_ids if component_id in reachable
        )
        unsolved_ids = tuple(
            component_id for component_id in all_ids if component_id not in reachable
        )
    else:
        solved_ids = all_ids
        unsolved_ids = ()
    return ConstraintReport(
        solved=not unsolved_ids
        and all(residual.within_tolerance for residual in residuals),
        grounded_component_ids=assembly.grounded_component_ids,
        solved_component_ids=solved_ids,
        unsolved_component_ids=unsolved_ids,
        residuals=residuals,
    )


def _connector_local_frame_for_ref(
    assembly: Assembly, connector_ref: ConnectorRef
) -> Placement:
    component = assembly.get_component(connector_ref.component_id)
    connector = resolve_connector(assembly, connector_ref)
    owner = component.item if isinstance(component.item, Assembly) else None
    return resolve_connector_placement(connector, owner_assembly=owner)


def _connector_world_frame(
    assembly: Assembly, connector_ref: ConnectorRef
) -> Placement:
    component = assembly.get_component(connector_ref.component_id)
    return component.placement.compose(
        _connector_local_frame_for_ref(assembly, connector_ref)
    )


@dataclass(frozen=True)
class _ForwardedSolveTarget:
    component_path: Tuple[str, ...]
    parent_world: Placement
    connector_tail: Placement


def _forwarded_solve_target(
    assembly: Assembly, connector_ref: ConnectorRef
) -> Optional[_ForwardedSolveTarget]:
    component = assembly.get_component(connector_ref.component_id)
    if not isinstance(component.item, Assembly):
        return None
    connector = component.item.get_connector(connector_ref.connector_id)
    return _descend_forwarded_solve_target(
        owner=component.item,
        connector=connector,
        owner_world=component.placement,
        component_path=(component.component_id,),
    )


def _descend_forwarded_solve_target(
    *,
    owner: Assembly,
    connector: Connector,
    owner_world: Placement,
    component_path: Tuple[str, ...],
) -> Optional[_ForwardedSolveTarget]:
    anchor = cast(ConnectorAnchor, connector.anchor)
    if anchor.anchor_kind != "forwarded":
        return None
    source_component_id = cast(str, anchor.source_component_id)
    source_connector_id = cast(str, anchor.source_connector_id)
    source_component = owner.get_component(source_component_id)
    source_connector = source_component.item.get_connector(source_connector_id)
    source_path = (*component_path, source_component_id)
    if (
        isinstance(source_component.item, Assembly)
        and source_connector.anchor_kind == "forwarded"
    ):
        nested = _descend_forwarded_solve_target(
            owner=source_component.item,
            connector=source_connector,
            owner_world=owner_world.compose(source_component.placement),
            component_path=source_path,
        )
        if nested is None:
            return None
        tail = nested.connector_tail
        if anchor.offset is not None:
            tail = tail.compose(anchor.offset)
        return _ForwardedSolveTarget(
            component_path=nested.component_path,
            parent_world=nested.parent_world,
            connector_tail=tail,
        )
    source_owner = (
        source_component.item if isinstance(source_component.item, Assembly) else None
    )
    tail = resolve_connector_placement(
        source_connector,
        owner_assembly=source_owner,
    )
    if anchor.offset is not None:
        tail = tail.compose(anchor.offset)
    return _ForwardedSolveTarget(
        component_path=source_path,
        parent_world=owner_world,
        connector_tail=tail,
    )


def _assemblies_for_component_path(
    assembly: Assembly, component_path: Tuple[str, ...]
) -> Tuple[Assembly, ...]:
    component = assembly.get_component(component_path[0])
    if not isinstance(component.item, Assembly):
        return ()
    owner = component.item
    owners = [owner]
    for component_id in component_path[1:-1]:
        component = owner.get_component(component_id)
        if not isinstance(component.item, Assembly):
            return ()
        owner = component.item
        owners.append(owner)
    return tuple(owners)


def _preserves_satisfied_constraints(before: Assembly, after: Assembly) -> bool:
    for constraint in before.constraints:
        previous = measure_constraint_residual(before, constraint.constraint_id)
        if (
            previous.within_tolerance
            and not measure_constraint_residual(
                after, constraint.constraint_id
            ).within_tolerance
        ):
            return False
    return True


def _try_close_forwarded_constraint(
    assembly: Assembly, constraint: Constraint
) -> Optional[Assembly]:
    motion = _constraint_motion_from_current(assembly, constraint)
    for moving_side in ("a", "b"):
        moving_ref = (
            constraint.connector_a if moving_side == "a" else constraint.connector_b
        )
        target = _forwarded_solve_target(assembly, moving_ref)
        if target is None:
            continue
        owners = _assemblies_for_component_path(assembly, target.component_path)
        if not owners:
            continue
        parent = owners[-1]
        if target.component_path[-1] in parent.grounded_component_ids:
            continue
        if moving_side == "b":
            fixed_frame = _connector_world_frame(assembly, constraint.connector_a)
            target_frame = fixed_frame.compose(motion)
        else:
            fixed_frame = _connector_world_frame(assembly, constraint.connector_b)
            target_frame = fixed_frame.compose(inverse_placement(motion))
        placement = (
            inverse_placement(target.parent_world)
            .compose(target_frame)
            .compose(inverse_placement(target.connector_tail))
        )
        candidate = _with_component_path_placement(
            assembly,
            target.component_path,
            placement,
        )
        if not measure_constraint_residual(
            candidate, constraint.constraint_id
        ).within_tolerance:
            continue
        if not _preserves_satisfied_constraints(assembly, candidate):
            continue
        updated_owners = _assemblies_for_component_path(
            candidate, target.component_path
        )
        if not all(
            inspect_assembly_constraints(owner).solved for owner in updated_owners
        ):
            continue
        return candidate
    return None


def _constraint_current_scalar(assembly: Assembly, constraint: Constraint) -> float:
    frame_a = _connector_world_frame(assembly, constraint.connector_a)
    frame_b = _connector_world_frame(assembly, constraint.connector_b)
    relative = relative_placement(frame_a, frame_b)
    if constraint.constraint_kind == "prismatic":
        return relative.origin[2]
    return math.degrees(math.atan2(relative.x_axis[1], relative.x_axis[0]))


def _constraint_scalar_bounds(constraint: Constraint) -> Optional[Tuple[float, float]]:
    if constraint.constraint_kind == "revolute" and constraint.angle_limit is not None:
        return (constraint.angle_limit.lower_value, constraint.angle_limit.upper_value)
    if (
        constraint.constraint_kind == "prismatic"
        and constraint.distance_limit is not None
    ):
        return (
            constraint.distance_limit.lower_value,
            constraint.distance_limit.upper_value,
        )
    return None


def _project_scalar(scalar: float, bounds: Optional[Tuple[float, float]]) -> float:
    if bounds is None:
        return scalar
    lo, hi = bounds
    return max(lo, min(hi, scalar))


def _motion_from_scalar(constraint: Constraint, scalar: float) -> Placement:
    if constraint.constraint_kind == "fixed":
        return identity_placement()
    if constraint.constraint_kind == "revolute":
        return rotate_z_placement(scalar)
    return translate_z_placement(scalar)


def _golden_section_search(
    func, a: float, b: float, tol: float = 1e-10, max_iter: int = 200
) -> float:
    _phi = (math.sqrt(5.0) - 1.0) / 2.0
    c = b - _phi * (b - a)
    d = a + _phi * (b - a)
    fc = func(c)
    fd = func(d)
    for _ in range(max_iter):
        if b - a <= tol:
            break
        if fc < fd:
            b = d
            d = c
            fd = fc
            c = b - _phi * (b - a)
            fc = func(c)
        else:
            a = c
            c = d
            fc = fd
            d = a + _phi * (b - a)
            fd = func(d)
    return (a + b) / 2.0


def _constraint_motion_from_current(
    assembly: Assembly, constraint: Constraint
) -> Placement:
    if constraint.constraint_kind == "fixed":
        return identity_placement()
    if constraint.constraint_kind == "revolute":
        angle = (
            constraint.drive_angle_degrees
            if constraint.drive_angle_degrees is not None
            else _constraint_current_scalar(assembly, constraint)
        )
        return rotate_z_placement(angle)
    distance = (
        constraint.drive_distance
        if constraint.drive_distance is not None
        else _constraint_current_scalar(assembly, constraint)
    )
    return translate_z_placement(distance)


def _loop_constraint_residual_at_scalar(
    assembly: Assembly,
    constraint: Constraint,
    known_side: str,
    known_placement: Placement,
    candidate_scalar: float,
) -> float:
    unknown_ref = (
        constraint.connector_b if known_side == "a" else constraint.connector_a
    )
    known_ref = constraint.connector_a if known_side == "a" else constraint.connector_b
    motion = _motion_from_scalar(constraint, candidate_scalar)
    if known_side == "b":
        motion = inverse_placement(motion)
    known_connector_frame = _connector_local_frame_for_ref(assembly, known_ref)
    unknown_connector_frame = _connector_local_frame_for_ref(assembly, unknown_ref)
    known_frame = known_placement.compose(known_connector_frame)
    target_unknown_frame = known_frame.compose(motion)
    target_placement = target_unknown_frame.compose(
        inverse_placement(unknown_connector_frame)
    )

    test = assembly.with_component_placement(unknown_ref.component_id, target_placement)
    residual = measure_constraint_residual(test, constraint.constraint_id)
    return residual.translation_error + math.radians(residual.angular_error_degrees)


def _solve_other_component(
    assembly: Assembly,
    constraint: Constraint,
    *,
    known_side: str,
    known_placement: Placement,
    scalar_override: Optional[float] = None,
) -> Placement:
    if constraint.constraint_kind == "fixed":
        motion = identity_placement()
    else:
        if scalar_override is not None:
            scalar = scalar_override
        elif known_side == "a":
            scalar = (
                constraint.drive_angle_degrees
                if constraint.constraint_kind == "revolute"
                else constraint.drive_distance
            )
            if scalar is None:
                scalar = _constraint_current_scalar(assembly, constraint)
        else:
            scalar = (
                constraint.drive_angle_degrees
                if constraint.constraint_kind == "revolute"
                else constraint.drive_distance
            )
            if scalar is None:
                scalar = _constraint_current_scalar(assembly, constraint)
        motion = _motion_from_scalar(constraint, scalar)
        if known_side == "b":
            motion = inverse_placement(motion)
    if known_side == "a":
        known_ref = constraint.connector_a
        unknown_ref = constraint.connector_b
    else:
        known_ref = constraint.connector_b
        unknown_ref = constraint.connector_a
    known_connector_frame = _connector_local_frame_for_ref(assembly, known_ref)
    unknown_connector_frame = _connector_local_frame_for_ref(assembly, unknown_ref)
    known_frame = known_placement.compose(known_connector_frame)
    target_unknown_frame = known_frame.compose(motion)
    return target_unknown_frame.compose(inverse_placement(unknown_connector_frame))


def _support_constraint_for_ref(
    assembly: Assembly,
    connector_ref: ConnectorRef,
    support_kind: str,
) -> Optional[Constraint]:
    for constraint in assembly.constraints:
        if constraint.constraint_kind != support_kind:
            continue
        if (
            constraint.connector_a == connector_ref
            or constraint.connector_b == connector_ref
        ):
            return constraint
    return None


def _coupling_endpoint_for_ref(
    assembly: Assembly,
    connector_ref: ConnectorRef,
    support_kind: str,
) -> Optional[CouplingEndpoint]:
    support = _support_constraint_for_ref(assembly, connector_ref, support_kind)
    if support is not None:
        return ("support", support)
    if connector_ref.component_id in assembly.grounded_component_ids:
        return ("grounded", connector_ref)
    return None


def _endpoint_scalar(assembly: Assembly, endpoint: CouplingEndpoint) -> float:
    if endpoint[0] == "grounded":
        return 0.0
    return _support_scalar(assembly, cast(Constraint, endpoint[1]))


def _endpoint_can_accept_coupled_scalar(endpoint: CouplingEndpoint) -> bool:
    if endpoint[0] == "grounded":
        return False
    return _support_can_accept_coupled_scalar(cast(Constraint, endpoint[1]))


def _set_endpoint_scalar(
    assembly: Assembly,
    endpoint: CouplingEndpoint,
    scalar: float,
) -> Assembly:
    if endpoint[0] == "grounded":
        return assembly
    return _set_support_scalar(assembly, cast(Constraint, endpoint[1]), scalar)


def _support_scalar(assembly: Assembly, support: Constraint) -> float:
    scalar = _constraint_current_scalar(assembly, support)
    bounds = _constraint_scalar_bounds(support)
    return _project_scalar(scalar, bounds)


def _component_placement_for_support_scalar(
    assembly: Assembly,
    support: Constraint,
    scalar: float,
) -> Placement:
    a_id = support.connector_a.component_id
    b_id = support.connector_b.component_id
    if (
        a_id in assembly.grounded_component_ids
        and b_id not in assembly.grounded_component_ids
    ):
        return _solve_other_component(
            assembly,
            support,
            known_side="a",
            known_placement=assembly.get_component(a_id).placement,
            scalar_override=scalar,
        )
    if (
        b_id in assembly.grounded_component_ids
        and a_id not in assembly.grounded_component_ids
    ):
        return _solve_other_component(
            assembly,
            support,
            known_side="b",
            known_placement=assembly.get_component(b_id).placement,
            scalar_override=scalar,
        )
    return _solve_other_component(
        assembly,
        support,
        known_side="a",
        known_placement=assembly.get_component(a_id).placement,
        scalar_override=scalar,
    )


def _support_can_accept_coupled_scalar(support: Constraint) -> bool:
    if support.constraint_kind == "revolute":
        return support.drive_angle_degrees is None
    if support.constraint_kind == "prismatic":
        return support.drive_distance is None
    return False


def _set_support_scalar(
    assembly: Assembly,
    support: Constraint,
    scalar: float,
) -> Assembly:
    bounds = _constraint_scalar_bounds(support)
    scalar = _project_scalar(scalar, bounds)
    moving_ref = support.connector_b
    if support.connector_b.component_id in assembly.grounded_component_ids:
        moving_ref = support.connector_a
    placement = _component_placement_for_support_scalar(assembly, support, scalar)
    return assembly.with_component_placement(moving_ref.component_id, placement)


def _coupling_supports(
    assembly: Assembly,
    coupling: Constraint,
) -> Tuple[Optional[CouplingEndpoint], Optional[CouplingEndpoint]]:
    if coupling.constraint_kind == "rack_pinion":
        rack_support = _coupling_endpoint_for_ref(
            assembly, coupling.connector_a, "prismatic"
        )
        pinion_support = _coupling_endpoint_for_ref(
            assembly, coupling.connector_b, "revolute"
        )
        return rack_support, pinion_support
    support_a = _coupling_endpoint_for_ref(assembly, coupling.connector_a, "revolute")
    support_b = _coupling_endpoint_for_ref(assembly, coupling.connector_b, "revolute")
    return support_a, support_b


def _coupling_phase_from_supports(
    assembly: Assembly,
    coupling: Constraint,
    support_a: CouplingEndpoint,
    support_b: CouplingEndpoint,
) -> float:
    scalar_a = _endpoint_scalar(assembly, support_a)
    scalar_b = _endpoint_scalar(assembly, support_b)
    if coupling.constraint_kind == "gear":
        return float(coupling.pitch_radius_a) * math.radians(scalar_a) + float(
            coupling.pitch_radius_b
        ) * math.radians(scalar_b)
    if coupling.constraint_kind == "belt":
        return float(coupling.pulley_radius_a) * math.radians(scalar_a) - float(
            coupling.pulley_radius_b
        ) * math.radians(scalar_b)
    return scalar_a + float(coupling.pitch_radius) * math.radians(scalar_b)


def coupling_phase_offset(assembly: Assembly, constraint: Constraint) -> float:
    if not isinstance(assembly, Assembly):
        raise TypeError("assembly must be an Assembly")
    if not isinstance(constraint, Constraint):
        raise TypeError("constraint must be a Constraint")
    if not _is_coupling_constraint(constraint):
        raise ValueError("constraint must be a gear, belt, or rack_pinion constraint")
    support_a, support_b = _coupling_supports(assembly, constraint)
    if support_a is None or support_b is None:
        return 0.0
    return _coupling_phase_from_supports(assembly, constraint, support_a, support_b)


def _solve_coupling_constraints(assembly: Assembly) -> Assembly:
    result = assembly
    for coupling in assembly.constraints:
        if not _is_coupling_constraint(coupling):
            continue
        support_a, support_b = _coupling_supports(result, coupling)
        if support_a is None or support_b is None:
            continue
        phase = float(coupling.phase_offset or 0.0)
        scalar_a = _endpoint_scalar(result, support_a)
        scalar_b = _endpoint_scalar(result, support_b)
        can_set_a = _endpoint_can_accept_coupled_scalar(support_a)
        can_set_b = _endpoint_can_accept_coupled_scalar(support_b)
        if coupling.constraint_kind == "gear":
            if not can_set_a and can_set_b:
                target_b = math.degrees(
                    (phase - float(coupling.pitch_radius_a) * math.radians(scalar_a))
                    / float(coupling.pitch_radius_b)
                )
                result = _set_endpoint_scalar(result, support_b, target_b)
            elif can_set_a and not can_set_b:
                target_a = math.degrees(
                    (phase - float(coupling.pitch_radius_b) * math.radians(scalar_b))
                    / float(coupling.pitch_radius_a)
                )
                result = _set_endpoint_scalar(result, support_a, target_a)
        elif coupling.constraint_kind == "belt":
            if not can_set_a and can_set_b:
                target_b = math.degrees(
                    (float(coupling.pulley_radius_a) * math.radians(scalar_a) - phase)
                    / float(coupling.pulley_radius_b)
                )
                result = _set_endpoint_scalar(result, support_b, target_b)
            elif can_set_a and not can_set_b:
                target_a = math.degrees(
                    (phase + float(coupling.pulley_radius_b) * math.radians(scalar_b))
                    / float(coupling.pulley_radius_a)
                )
                result = _set_endpoint_scalar(result, support_a, target_a)
        else:
            if not can_set_a and can_set_b:
                target_b = math.degrees(
                    (phase - scalar_a) / float(coupling.pitch_radius)
                )
                result = _set_endpoint_scalar(result, support_b, target_b)
            elif can_set_a and not can_set_b:
                target_a = phase - float(coupling.pitch_radius) * math.radians(scalar_b)
                result = _set_endpoint_scalar(result, support_a, target_a)
    return result


def _measure_coupling_constraint_residual(
    assembly: Assembly,
    constraint: Constraint,
) -> ConstraintResidual:
    support_a, support_b = _coupling_supports(assembly, constraint)
    if support_a is None or support_b is None:
        return ConstraintResidual(
            constraint.constraint_id,
            1.0e30,
            0.0,
            False,
        )
    residual = abs(
        _coupling_phase_from_supports(assembly, constraint, support_a, support_b)
        - float(constraint.phase_offset or 0.0)
    )
    angular_error = 0.0
    if constraint.constraint_kind == "gear":
        angular_error = math.degrees(residual / float(constraint.pitch_radius_b))
    elif constraint.constraint_kind == "belt":
        angular_error = math.degrees(residual / float(constraint.pulley_radius_b))
    elif constraint.constraint_kind == "rack_pinion":
        angular_error = math.degrees(residual / float(constraint.pitch_radius))
    return ConstraintResidual(
        constraint.constraint_id,
        residual,
        abs(angular_error),
        residual <= _PLACEMENT_TOLERANCE,
    )


def _angular_error_degrees(relative: Placement) -> float:
    trace = relative.x_axis[0] + relative.y_axis[1] + relative.z_axis[2]
    cos_angle = max(-1.0, min(1.0, (trace - 1.0) / 2.0))
    return abs(math.degrees(math.acos(cos_angle)))


__all__ = [
    "coupling_phase_offset",
    "inspect_assembly_constraints",
    "measure_constraint_residual",
    "solve_assembly_constraints",
]
