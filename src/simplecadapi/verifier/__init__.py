"""Static verification helpers for SimpleCAD assemblies.

The verifier namespace exposes high-level structural checks. The first checker
uses the internal cached solid meshes plus python-fcl to report current-pose mesh
contact penetrations deeper than the configured tolerance. It intentionally does
not attempt complete solid containment detection yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Iterable, Sequence, Tuple

import numpy as np

from .. import _mesh
from ..product import Assembly, Part, Placement, compose_placements, identity_placement


ComponentPath = Tuple[str, ...]


@dataclass(frozen=True)
class ComponentPair:
    """Unordered pair of component paths used by verifier scopes."""

    component_a: str | Sequence[str]
    component_b: str | Sequence[str]

    def normalized(self) -> tuple[ComponentPath, ComponentPath]:
        a = _component_path(self.component_a)
        b = _component_path(self.component_b)
        ordered = sorted((a, b))
        return ordered[0], ordered[1]


@dataclass(frozen=True)
class CollisionScope:
    """Select which component pairs a static collision check should inspect.

    Args:
        component_paths: Optional component path filter. When non-empty, only
            pairs where both components are in this set are considered.
        include_pairs: Optional explicit unordered pair set. When non-empty,
            only these pairs are considered.
        exclude_pairs: Unordered pairs to skip. This is a strict skip, not a
            joint-aware mating-region rule.
    """

    component_paths: tuple[str | Sequence[str], ...] = ()
    include_pairs: tuple[ComponentPair, ...] = ()
    exclude_pairs: tuple[ComponentPair, ...] = ()


@dataclass(frozen=True)
class CollisionCheckConfig:
    """Configuration for current-pose static mesh penetration checks.

    Args:
        max_allowed_penetration: Maximum accepted FCL contact penetration depth
            in model units. Contact or shallower penetration passes; deeper
            penetration fails.
        scope: Optional component pair scope.
        max_contacts_per_pair: Maximum FCL contacts requested per checked pair.
    """

    max_allowed_penetration: float = 0.01
    scope: CollisionScope = field(default_factory=CollisionScope)
    max_contacts_per_pair: int = 64

    def __post_init__(self) -> None:
        if self.max_allowed_penetration < 0:
            raise ValueError("max_allowed_penetration must be non-negative")
        if self.max_contacts_per_pair <= 0:
            raise ValueError("max_contacts_per_pair must be positive")


@dataclass(frozen=True)
class VerificationWarning:
    """Non-fatal verifier diagnostic."""

    code: str
    message: str
    component_path: ComponentPath | None = None


@dataclass(frozen=True)
class CollisionContact:
    """One FCL contact returned for a component pair."""

    position: tuple[float, float, float]
    normal: tuple[float, float, float]
    penetration_depth: float


@dataclass(frozen=True)
class CollisionFailure:
    """A component pair with over-tolerance mesh contact penetration."""

    component_a: ComponentPath
    component_b: ComponentPath
    penetration_depth: float
    allowed_penetration: float
    contacts: tuple[CollisionContact, ...] = ()
    kind: str = "contact_penetration"


@dataclass(frozen=True)
class CollisionReport:
    """Result of a static collision verification pass."""

    completed: bool
    passed: bool
    checked_pair_count: int
    failed_pair_count: int
    failures: tuple[CollisionFailure, ...] = ()
    warnings: tuple[VerificationWarning, ...] = ()


@dataclass(frozen=True)
class _PlacedSolid:
    path: ComponentPath
    part: Part
    placement: Placement
    mesh: _mesh.TriMesh | None
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]] | None


def check_collision_rcollisionreport(
    assembly: Assembly,
    config: CollisionCheckConfig | None = None,
) -> CollisionReport:
    """Check current assembly pose for FCL-reported over-tolerance mesh penetration.

    This first verifier version checks only FCL contact penetration between
    leaf Part component meshes at their current placements. It does not solve
    constraints, does not sample motion, and does not detect complete containment
    cases where two closed solids overlap without surface contact.
    """

    if not isinstance(assembly, Assembly):
        raise TypeError("assembly must be an Assembly")
    cfg = config or CollisionCheckConfig()
    warnings: list[VerificationWarning] = []

    fcl = _import_fcl()
    if fcl is None:
        return CollisionReport(
            completed=False,
            passed=False,
            checked_pair_count=0,
            failed_pair_count=0,
            warnings=(
                VerificationWarning(
                    code="backend_unavailable",
                    message="python-fcl is required for collision verification; install simplecadapi[collision].",
                ),
            ),
        )

    placed = _collect_placed_solids(assembly, warnings=warnings)
    selected = _apply_scope(placed, cfg.scope)
    checked_count = 0
    failures: list[CollisionFailure] = []
    models = {
        item.path: _make_fcl_model(fcl, item.mesh)
        for item in selected
        if item.mesh is not None
    }

    for solid_a, solid_b in combinations(selected, 2):
        if not _scoped_pair_allowed(solid_a.path, solid_b.path, cfg.scope):
            continue
        if solid_a.mesh is None or solid_b.mesh is None:
            continue
        checked_count += 1
        if solid_a.bounds is not None and solid_b.bounds is not None:
            if not _aabb_overlaps(solid_a.bounds, solid_b.bounds):
                continue
        failure = _check_pair_with_fcl(
            fcl=fcl,
            solid_a=solid_a,
            solid_b=solid_b,
            model_a=models[solid_a.path],
            model_b=models[solid_b.path],
            max_allowed_penetration=cfg.max_allowed_penetration,
            max_contacts_per_pair=cfg.max_contacts_per_pair,
        )
        if failure is not None:
            failures.append(failure)

    return CollisionReport(
        completed=True,
        passed=not failures,
        checked_pair_count=checked_count,
        failed_pair_count=len(failures),
        failures=tuple(failures),
        warnings=tuple(warnings),
    )


def _import_fcl() -> Any | None:
    try:
        import fcl  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return None
    return fcl


def _collect_placed_solids(
    assembly: Assembly,
    *,
    warnings: list[VerificationWarning],
    prefix: ComponentPath = (),
    parent_placement: Placement | None = None,
) -> list[_PlacedSolid]:
    base_placement = parent_placement or identity_placement()
    placed: list[_PlacedSolid] = []

    for component in assembly.components:
        path = (*prefix, component.component_id)
        placement = compose_placements(base_placement, component.placement)
        if isinstance(component.item, Part):
            mesh = _mesh.cached_mesh(component.item.body)
            if mesh is None:
                detail = _mesh.mesh_error(component.item.body) or "no cached mesh"
                warnings.append(
                    VerificationWarning(
                        code="mesh_missing",
                        message=detail,
                        component_path=path,
                    )
                )
            elif mesh.triangle_count == 0:
                warnings.append(
                    VerificationWarning(
                        code="mesh_empty",
                        message="component mesh has no triangles",
                        component_path=path,
                    )
                )
                mesh = None
            placed.append(
                _PlacedSolid(
                    path=path,
                    part=component.item,
                    placement=placement,
                    mesh=mesh,
                    bounds=_world_bounds(mesh, placement) if mesh is not None else None,
                )
            )
        elif isinstance(component.item, Assembly):
            placed.extend(
                _collect_placed_solids(
                    component.item,
                    warnings=warnings,
                    prefix=path,
                    parent_placement=placement,
                )
            )
    return placed


def _apply_scope(placed: list[_PlacedSolid], scope: CollisionScope) -> list[_PlacedSolid]:
    if not scope.component_paths and not scope.include_pairs and not scope.exclude_pairs:
        return placed

    allowed_paths = {_component_path(path) for path in scope.component_paths}
    if allowed_paths:
        placed = [item for item in placed if item.path in allowed_paths]
    if not scope.include_pairs:
        return placed

    include_pairs = {pair.normalized() for pair in scope.include_pairs}
    paths_with_pairs: set[ComponentPath] = set()
    for a, b in include_pairs:
        paths_with_pairs.add(a)
        paths_with_pairs.add(b)
    return [item for item in placed if item.path in paths_with_pairs]


def _scoped_pair_allowed(
    path_a: ComponentPath,
    path_b: ComponentPath,
    scope: CollisionScope,
) -> bool:
    pair = tuple(sorted((path_a, path_b)))
    include_pairs = {item.normalized() for item in scope.include_pairs}
    exclude_pairs = {item.normalized() for item in scope.exclude_pairs}
    if include_pairs and pair not in include_pairs:
        return False
    return pair not in exclude_pairs


def _check_pair_with_fcl(
    *,
    fcl: Any,
    solid_a: _PlacedSolid,
    solid_b: _PlacedSolid,
    model_a: Any,
    model_b: Any,
    max_allowed_penetration: float,
    max_contacts_per_pair: int,
) -> CollisionFailure | None:
    assert solid_a.mesh is not None
    assert solid_b.mesh is not None

    obj_a = fcl.CollisionObject(
        model_a,
        _fcl_transform(fcl, solid_a.placement),
    )
    obj_b = fcl.CollisionObject(
        model_b,
        _fcl_transform(fcl, solid_b.placement),
    )
    request = fcl.CollisionRequest(
        num_max_contacts=int(max_contacts_per_pair),
        enable_contact=True,
    )
    result = fcl.CollisionResult()
    fcl.collide(obj_a, obj_b, request, result)

    contacts = tuple(
        _contact_from_fcl(contact)
        for contact in result.contacts
        if float(contact.penetration_depth) > 0.0
    )
    max_depth = max((contact.penetration_depth for contact in contacts), default=0.0)
    if max_depth <= max_allowed_penetration:
        return None

    return CollisionFailure(
        component_a=solid_a.path,
        component_b=solid_b.path,
        penetration_depth=max_depth,
        allowed_penetration=float(max_allowed_penetration),
        contacts=tuple(sorted(contacts, key=lambda item: item.penetration_depth, reverse=True)),
    )


def _make_fcl_model(fcl: Any, mesh: _mesh.TriMesh) -> Any:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    triangles = np.asarray(mesh.triangles, dtype=np.int32)
    model = fcl.BVHModel()
    model.beginModel(int(mesh.vertex_count), int(mesh.triangle_count))
    model.addSubModel(vertices, triangles)
    model.endModel()
    return model


def _world_bounds(
    mesh: _mesh.TriMesh,
    placement: Placement,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    lower, upper = mesh.bounds
    corners = np.asarray(
        [
            (lower[0], lower[1], lower[2]),
            (lower[0], lower[1], upper[2]),
            (lower[0], upper[1], lower[2]),
            (lower[0], upper[1], upper[2]),
            (upper[0], lower[1], lower[2]),
            (upper[0], lower[1], upper[2]),
            (upper[0], upper[1], lower[2]),
            (upper[0], upper[1], upper[2]),
        ],
        dtype=np.float64,
    )
    rotation = np.asarray(
        [
            [placement.x_axis[0], placement.y_axis[0], placement.z_axis[0]],
            [placement.x_axis[1], placement.y_axis[1], placement.z_axis[1]],
            [placement.x_axis[2], placement.y_axis[2], placement.z_axis[2]],
        ],
        dtype=np.float64,
    )
    transformed = corners @ rotation.T + np.asarray(placement.origin, dtype=np.float64)
    world_lower = transformed.min(axis=0)
    world_upper = transformed.max(axis=0)
    return tuple(float(v) for v in world_lower), tuple(float(v) for v in world_upper)


def _aabb_overlaps(
    bounds_a: tuple[tuple[float, float, float], tuple[float, float, float]],
    bounds_b: tuple[tuple[float, float, float], tuple[float, float, float]],
) -> bool:
    lower_a, upper_a = bounds_a
    lower_b, upper_b = bounds_b
    return all(
        upper_a[index] >= lower_b[index] and upper_b[index] >= lower_a[index]
        for index in range(3)
    )


def _fcl_transform(fcl: Any, placement: Placement) -> Any:
    rotation = np.asarray(
        [
            [placement.x_axis[0], placement.y_axis[0], placement.z_axis[0]],
            [placement.x_axis[1], placement.y_axis[1], placement.z_axis[1]],
            [placement.x_axis[2], placement.y_axis[2], placement.z_axis[2]],
        ],
        dtype=np.float64,
    )
    translation = np.asarray(placement.origin, dtype=np.float64)
    return fcl.Transform(rotation, translation)


def _contact_from_fcl(contact: Any) -> CollisionContact:
    return CollisionContact(
        position=_float3(contact.pos),
        normal=_float3(contact.normal),
        penetration_depth=float(contact.penetration_depth),
    )


def _float3(value: Iterable[float]) -> tuple[float, float, float]:
    items = tuple(float(v) for v in value)
    if len(items) != 3:
        raise ValueError("expected 3D vector")
    return items  # type: ignore[return-value]


def _component_path(value: str | Sequence[str]) -> ComponentPath:
    if isinstance(value, str):
        return (value,)
    path = tuple(str(item) for item in value)
    if not path or any(not item for item in path):
        raise ValueError("component path must not be empty")
    return path


__all__ = [
    "CollisionCheckConfig",
    "CollisionContact",
    "CollisionFailure",
    "CollisionReport",
    "CollisionScope",
    "ComponentPair",
    "VerificationWarning",
    "check_collision_rcollisionreport",
]
