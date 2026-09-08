"""Constraint recovery from planar sketch snapshots.

Implements the recovery axioms agreed for the CadQuery translator:

- P1 fidelity — the accepted set rivets the snapshot: the solver reaches
  DOF 0 and a perturbed rebuild converges back onto the declared geometry
  (basin test).
- P2 no invention — every candidate is *entailed* by the snapshot: its
  residual against the declared coordinates is verified before it can be
  offered, and admission itself is decided by the production solver
  (SolveSpace) as the DOF oracle.
- P3 exactly-full DOF — a candidate is accepted only if the solver's DOF
  strictly drops; dependents and conflicts are rejected, never forced.
- P4 no beautified numbers — measured values are emitted verbatim.
- P5 provenance — emitted ids carry the ``inf`` prefix (inferred), never
  pretending to be native dataset constraints.

The engine is source-agnostic: it consumes the snapshot schema
(``{stem}.sketches.json`` entries) and could serve any front-end that can
produce planar loops / open chains in that schema.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .emit import fmt_num

TAU_GEOM = 1e-7  # entailment tolerance (mm / dimensionless) for exact relations
TAU_MEAS = 1e-6  # tolerance for measured-value candidates
JITTER_SCALE = 1e-3  # basin-test perturbation, relative to sketch span
COORDS_TOL = 1e-6  # solved-vs-declared reconciliation (relative to span)
BASIN_TOL = 1e-4  # basin convergence (relative to span)
MAX_SOLVE_CALLS = 1200  # solver-oracle budget (each trial rebuilds + solves)
# Per-tier tested-candidate caps: cheap exact relations run in full; the
# combinatorial pair tiers (relations, plausibility distances) are bounded so
# large freeform outlines (60+ point chains) degrade to honest "partial"
# reports instead of unbounded greedy runs.
TIER_TEST_CAPS = {30: 240, 40: 240, 80: 300}


@dataclass
class Candidate:
    priority: int
    kind: str  # constraint kind matching the constrain_*_rsketch API
    targets: Tuple[str, ...]
    value: Optional[float] = None
    kwargs: Dict[str, Any] = field(default_factory=dict)
    note: str = ""


class _Geometry:
    """Typed view over a snapshot's entities (declared = ground truth G)."""

    def __init__(self, snapshot: Dict[str, Any]) -> None:
        self.snapshot = snapshot
        self.points: Dict[str, Tuple[float, float]] = {}
        self.lines: Dict[str, Tuple[str, str]] = {}
        self.circles: Dict[str, Tuple[str, float]] = {}
        self.arcs: Dict[str, Tuple[str, str, str]] = {}
        self.order: List[str] = []
        for entity in snapshot.get("entities", []):
            eid = entity["id"]
            self.order.append(eid)
            if entity["kind"] == "point":
                self.points[eid] = (float(entity["xy"][0]), float(entity["xy"][1]))
            elif entity["kind"] == "line":
                self.lines[eid] = (entity["start"], entity["end"])
            elif entity["kind"] == "circle":
                self.circles[eid] = (entity["center"], float(entity["radius"]))
            elif entity["kind"] == "arc":
                self.arcs[eid] = (entity["start"], entity["end"], entity["center"])
        self.span = self._span()

    def _span(self) -> float:
        if not self.points:
            return 1.0
        xs = [p[0] for p in self.points.values()]
        ys = [p[1] for p in self.points.values()]
        return max(1e-9, max(xs) - min(xs), max(ys) - min(ys))

    def line_dir(self, eid: str) -> Tuple[float, float]:
        start, end = self.points[self.lines[eid][0]], self.points[self.lines[eid][1]]
        dx, dy = end[0] - start[0], end[1] - start[1]
        norm = math.hypot(dx, dy) or 1.0
        return (dx / norm, dy / norm)

    def line_len(self, eid: str) -> float:
        start, end = self.points[self.lines[eid][0]], self.points[self.lines[eid][1]]
        return math.hypot(end[0] - start[0], end[1] - start[1])

    def radius_of(self, eid: str) -> float:
        if eid in self.circles:
            return self.circles[eid][1]
        start, _end, center = self.arcs[eid]
        c, s = self.points[center], self.points[start]
        return math.hypot(s[0] - c[0], s[1] - c[1])

    def center_id_of(self, eid: str) -> str:
        return self.circles[eid][0] if eid in self.circles else self.arcs[eid][2]

    def curve_ids(self) -> List[str]:
        return [*self.circles.keys(), *self.arcs.keys()]

    def consecutive_line_pairs(self) -> List[Tuple[str, str]]:
        """Line pairs adjacent through a shared endpoint, in entity order."""
        result: List[Tuple[str, str]] = []
        ordered_lines = [eid for eid in self.order if eid in self.lines]
        for index, eid in enumerate(ordered_lines):
            for other in ordered_lines[index + 1 :]:
                if set(self.lines[eid]) & set(self.lines[other]):
                    result.append((eid, other))
        return result


def _fold_angle_deg(dir_a: Tuple[float, float], dir_b: Tuple[float, float]) -> float:
    """Undirected angle in degrees, folded to the smaller magnitude (the
    solver's own convention for the angle constraint)."""
    cross = dir_a[0] * dir_b[1] - dir_a[1] * dir_b[0]
    dot = dir_a[0] * dir_b[0] + dir_a[1] * dir_b[1]
    magnitude = math.degrees(math.atan2(abs(cross), dot)) % 360.0
    return min(magnitude, 360.0 - magnitude)


def enumerate_candidates(snapshot: Dict[str, Any]) -> List[Candidate]:
    """All snapshot-entailed candidates in priority order (P2: every relation
    below is verified against the declared coordinates before being offered)."""
    g = _Geometry(snapshot)
    candidates: List[Candidate] = []

    # T1 anchor: fix the first point (kills 2 rigid translations).
    if g.points:
        first_point = next(iter(g.points))
        candidates.append(Candidate(10, "fix", (first_point,), note="anchor"))

    # T2 orientation + exact line relations.
    for eid in g.lines:
        d = g.line_dir(eid)
        if abs(d[1]) < TAU_GEOM:
            candidates.append(Candidate(20, "horizontal", (eid,)))
        if abs(d[0]) < TAU_GEOM:
            candidates.append(Candidate(20, "vertical", (eid,)))

    # T3 pairwise exact relations (true relations only — the predicate is the
    # entailment filter; unrelated pairs are never offered).
    line_ids = list(g.lines)
    for i, a in enumerate(line_ids):
        for b in line_ids[i + 1 :]:
            da, db = g.line_dir(a), g.line_dir(b)
            cross = abs(da[0] * db[1] - da[1] * db[0])
            dot = da[0] * db[0] + da[1] * db[1]
            if cross < TAU_GEOM:
                candidates.append(Candidate(30, "parallel", (a, b)))
            if abs(dot) < TAU_GEOM:
                candidates.append(Candidate(30, "perpendicular", (a, b)))

    curves = g.curve_ids()
    for i, a in enumerate(curves):
        for b in curves[i + 1 :]:
            ca = g.points[g.center_id_of(a)]
            cb = g.points[g.center_id_of(b)]
            center_gap = math.hypot(ca[0] - cb[0], ca[1] - cb[1])
            if center_gap < TAU_GEOM:
                candidates.append(Candidate(40, "concentric", (a, b)))
            if abs(g.radius_of(a) - g.radius_of(b)) < TAU_MEAS * max(1.0, g.span):
                candidates.append(Candidate(40, "equal_radius", (a, b)))
            gap = center_gap - (g.radius_of(a) + g.radius_of(b))
            if abs(gap) < TAU_MEAS * max(1.0, g.span):
                candidates.append(Candidate(40, "tangent", (a, b), kwargs={"mode": "external"}))
            gap = center_gap - abs(g.radius_of(a) - g.radius_of(b))
            if abs(gap) < TAU_MEAS * max(1.0, g.span):
                candidates.append(Candidate(40, "tangent", (a, b), kwargs={"mode": "internal"}))
    line_lens = list(g.lines)
    for i, a in enumerate(line_lens):
        for b in line_lens[i + 1 :]:
            if abs(g.line_len(a) - g.line_len(b)) < TAU_MEAS * max(1.0, g.span):
                candidates.append(Candidate(40, "equal_length", (a, b)))

    # Line-circle tangency (distance from center to the infinite line == r).
    for line in g.lines:
        s_pt = g.points[g.lines[line][0]]
        d = g.line_dir(line)
        for circle in g.circles:
            center = g.points[g.circles[circle][0]]
            radius = g.circles[circle][1]
            dist = abs((center[0] - s_pt[0]) * d[1] - (center[1] - s_pt[1]) * d[0])
            if abs(dist - radius) < TAU_MEAS * max(1.0, g.span):
                candidates.append(Candidate(40, "tangent", (line, circle)))

    # Arc-line endpoint tangency: shared endpoint + line direction ⊥ radius.
    for line in g.lines:
        line_endpoints = set(g.lines[line])
        d = g.line_dir(line)
        for arc in g.arcs:
            start, _end, center = g.arcs[arc]
            c = g.points[center]
            for selector, point_id in (("start", start), ("end", _end)):
                if point_id not in line_endpoints:
                    continue
                coord = g.points[point_id]
                radius_vec = (coord[0] - c[0], coord[1] - c[1])
                rn = math.hypot(*radius_vec) or 1.0
                along = abs(radius_vec[0] * d[0] + radius_vec[1] * d[1]) / rn
                if along < TAU_GEOM:
                    candidates.append(
                        Candidate(40, "tangent", (line, arc), kwargs={"at_b": selector})
                    )

    # T5 measured dimensions (verbatim, P4).
    for eid in g.lines:
        candidates.append(Candidate(50, "length", (eid,), value=g.line_len(eid)))
    for eid in curves:
        candidates.append(Candidate(50, "radius", (eid,), value=g.radius_of(eid)))

    # T6 orientation fallback: signed dx of the first line (the distance_x
    # convention is value = point_b - point_a).
    ordered_lines = [eid for eid in g.order if eid in g.lines]
    if ordered_lines:
        first = ordered_lines[0]
        p0, p1 = g.points[g.lines[first][0]], g.points[g.lines[first][1]]
        candidates.append(Candidate(60, "distance_x", (g.lines[first][0], g.lines[first][1]), value=p1[0] - p0[0]))

    # T7 measured angles between endpoint-adjacent lines (degrees, folded).
    for a, b in g.consecutive_line_pairs():
        angle = _fold_angle_deg(g.line_dir(a), g.line_dir(b))
        if angle > TAU_GEOM and abs(angle - 180.0) > 1e-6:
            candidates.append(Candidate(70, "angle", (a, b), value=angle))

    # T8 plausibility-triggered clean distances: the *trigger* is that the
    # measured value sits on a half-unit grid (intent-plausible dimension);
    # the emitted value is still the verbatim measurement (P4).
    point_ids = list(g.points)
    for i, a in enumerate(point_ids):
        for b in point_ids[i + 1 :]:
            pa, pb = g.points[a], g.points[b]
            dist = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
            if dist < TAU_GEOM:
                continue
            if abs(dist - round(dist * 2.0) / 2.0) < TAU_MEAS:
                candidates.append(Candidate(80, "distance", (a, b), value=dist))

    candidates.sort(key=lambda c: c.priority)
    return candidates


def _apply_candidate(sketch: Any, candidate: Candidate, constraint_id: str) -> Any:
    """Apply one candidate through the public constrain_* API."""
    import simplecadapi as scad

    kind = candidate.kind
    t = candidate.targets
    value = candidate.value
    measured = 0.0
    if kind in {"length", "radius", "distance", "distance_x", "angle"}:
        assert value is not None, f"candidate kind {kind} requires a measured value"
        measured = value
    if kind == "fix":
        return scad.constrain_fix_rsketch(sketch, t[0], constraint_id=constraint_id)
    if kind == "horizontal":
        return scad.constrain_horizontal_rsketch(sketch, t[0], constraint_id=constraint_id)
    if kind == "vertical":
        return scad.constrain_vertical_rsketch(sketch, t[0], constraint_id=constraint_id)
    if kind == "parallel":
        return scad.constrain_parallel_rsketch(sketch, t[0], t[1], constraint_id=constraint_id)
    if kind == "perpendicular":
        return scad.constrain_perpendicular_rsketch(sketch, t[0], t[1], constraint_id=constraint_id)
    if kind == "concentric":
        return scad.constrain_concentric_rsketch(sketch, t[0], t[1], constraint_id=constraint_id)
    if kind == "equal_radius":
        return scad.constrain_equal_radius_rsketch(sketch, t[0], t[1], constraint_id=constraint_id)
    if kind == "equal_length":
        return scad.constrain_equal_length_rsketch(sketch, t[0], t[1], constraint_id=constraint_id)
    if kind == "tangent":
        kwargs = dict(candidate.kwargs)
        return scad.constrain_tangent_rsketch(
            sketch, t[0], t[1], constraint_id=constraint_id, **kwargs
        )
    if kind == "length":
        return scad.constrain_length_rsketch(sketch, t[0], measured, constraint_id=constraint_id)
    if kind == "radius":
        return scad.constrain_radius_rsketch(sketch, t[0], measured, constraint_id=constraint_id)
    if kind == "distance":
        return scad.constrain_distance_rsketch(sketch, t[0], t[1], measured, constraint_id=constraint_id)
    if kind == "distance_x":
        return scad.constrain_distance_x_rsketch(sketch, t[0], t[1], measured, constraint_id=constraint_id)
    if kind == "angle":
        return scad.constrain_angle_rsketch(sketch, t[0], t[1], measured, constraint_id=constraint_id)
    raise ValueError(f"unsupported candidate kind: {kind}")


def build_document(
    snapshot: Dict[str, Any],
    *,
    jitter: float = 0.0,
    seed: str = "recover",
    exclude_ids: Tuple[str, ...] = (),
) -> Any:
    """Build a Sketch document from the snapshot via the public API.

    With ``jitter > 0`` the declared point coordinates are perturbed — used
    for the basin test (P1): the constraint set must pull them back to G.
    ``exclude_ids`` keeps anchor points at their declared coordinates (a
    ``fix`` constraint anchors to *initial* coordinates, so jittering a
    fixed point would break the test by construction).
    """
    import simplecadapi as scad

    rng = random.Random(seed)
    g = _Geometry(snapshot)
    span = g.span
    excluded = set(exclude_ids)
    s = scad.make_sketch_rsketch(name=snapshot.get("block", "snapshot"), plane="XY")
    for entity in snapshot.get("entities", []):
        if entity["kind"] == "point":
            x, y = entity["xy"]
            if jitter and entity["id"] not in excluded:
                x = x + rng.uniform(-jitter, jitter) * span
                y = y + rng.uniform(-jitter, jitter) * span
            s = scad.add_point_rsketch(s, entity["id"], x, y)
        elif entity["kind"] == "line":
            s = scad.add_line_rsketch(s, entity["id"], entity["start"], entity["end"])
        elif entity["kind"] == "circle":
            s = scad.add_circle_rsketch(s, entity["id"], entity["center"], entity["radius"])
        elif entity["kind"] == "arc":
            s = scad.add_arc_rsketch(s, entity["id"], entity["start"], entity["end"], entity["center"])
        else:
            raise ValueError(f"unsupported snapshot entity kind: {entity['kind']}")
    return s


def _coords_gap(solved: Dict[str, Tuple[float, float]], declared: Dict[str, Tuple[float, float]], span: float) -> float:
    worst = 0.0
    for point_id, (x, y) in declared.items():
        sx, sy = solved.get(point_id, (x, y))
        worst = max(worst, math.hypot(sx - x, sy - y))
    return worst / span


def recover_constraints(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Greedy solver-oracle recovery; returns a report with accepted candidates."""
    g = _Geometry(snapshot)
    accepted: List[Dict[str, Any]] = []
    report: Dict[str, Any] = {
        "block": snapshot.get("block"),
        "op": snapshot.get("op"),
        "entities": len(snapshot.get("entities", [])),
    }
    if len(g.points) + len(g.lines) + len(g.circles) + len(g.arcs) == 0:
        report.update({"status": "skipped", "reason": "empty snapshot"})
        return report

    sketch = build_document(snapshot)
    try:
        base = sketch.solve(strict=False)
    except Exception as exc:  # noqa: BLE001
        report.update({"status": "skipped", "reason": f"baseline solve failed: {exc}"})
        return report
    if base.status not in {"solved", "underconstrained"}:
        report.update({"status": "skipped", "reason": f"baseline status={base.status}"})
        return report

    dof = base.dof
    report["dof_declared"] = dof
    solve_calls = 1
    tested = 0
    tier_tested: Dict[int, int] = {}
    by_kind: Dict[str, int] = {}

    def _redundant(result: Any) -> bool:
        # A candidate that introduces redundancy can still *drop* the DOF
        # counter while leaving the system rank-deficient (a false rivet:
        # DOF 0, Jacobian singular, geometry still floats). The basin test
        # exists for exactly this case; refusing redundant admissions keeps
        # accepted sets minimal by construction.
        return any(d.code == "redundant_constraints" for d in result.diagnostics)

    for candidate in enumerate_candidates(snapshot):
        if dof == 0:
            break
        if solve_calls >= MAX_SOLVE_CALLS:
            report["solve_calls_capped"] = True
            break
        tier_cap = TIER_TEST_CAPS.get(candidate.priority)
        if tier_cap is not None and tier_tested.get(candidate.priority, 0) >= tier_cap:
            continue
        tested += 1
        tier_tested[candidate.priority] = tier_tested.get(candidate.priority, 0) + 1
        index = len(accepted) + 1
        constraint_id = f"inf{index}_{candidate.kind}"
        try:
            trial = _apply_candidate(sketch, candidate, constraint_id)
            result = trial.solve(strict=False)
        except Exception:  # noqa: BLE001 — inadmissible candidates roll back
            continue
        solve_calls += 1
        if (
            result.status in {"solved", "underconstrained"}
            and result.dof < dof
            and not _redundant(result)
        ):
            sketch = trial
            dof = result.dof
            accepted.append(
                {
                    "kind": candidate.kind,
                    "targets": list(candidate.targets),
                    "value": candidate.value,
                    "kwargs": candidate.kwargs or None,
                    "constraint_id": constraint_id,
                    "priority": candidate.priority,
                }
            )
            by_kind[candidate.kind] = by_kind.get(candidate.kind, 0) + 1

    # P1 verification: solve from G (trivial) + coordinate reconciliation.
    final = sketch.solve(strict=False)
    coords_rel = _coords_gap(final.solved_points, g.points, g.span)
    coords_ok = coords_rel < COORDS_TOL and final.status in {"solved", "underconstrained"}

    # P1 basin test: rebuild with jittered declarations (anchors keep their
    # declared coordinates — `fix` anchors to *initial* coordinates), then
    # the same constraints must pull the free geometry back onto G.
    basin_ok: Optional[bool] = None
    if dof == 0 and coords_ok:
        basin_ok = False
        anchors = tuple(
            target
            for item in accepted
            if item["kind"] == "fix"
            for target in item["targets"]
        )
        try:
            perturbed = build_document(
                snapshot,
                jitter=JITTER_SCALE,
                seed=f"{snapshot.get('block', 'x')}-basin",
                exclude_ids=anchors,
            )
            for item in accepted:
                trial = _apply_candidate(
                    perturbed,
                    Candidate(item["priority"], item["kind"], tuple(item["targets"]), item["value"], item.get("kwargs") or {}),
                    item["constraint_id"],
                )
                perturbed = trial
            basin_result = perturbed.solve(strict=False)
            basin_gap = _coords_gap(basin_result.solved_points, g.points, g.span)
            basin_ok = (
                basin_result.status == "solved" and basin_gap < BASIN_TOL
            )
        except Exception:  # noqa: BLE001
            basin_ok = False

    report.update(
        {
            "status": (
                "riveted"
                if dof == 0 and coords_ok and basin_ok is True
                else "partial" if accepted
                else "none"
            ),
            "dof_remaining": dof,
            "constraints": accepted,
            "by_kind": by_kind,
            "candidates_tested": tested,
            "solve_calls": solve_calls,
            "coords_relative_gap": coords_rel,
            "coords_ok": coords_ok,
            "basin_ok": basin_ok,
        }
    )
    return report


def emit_constraint_lines(report: Dict[str, Any], indent: str = "    ") -> List[str]:
    """FTC source lines for an accepted constraint set (P5: inf provenance)."""
    lines: List[str] = []
    for item in report.get("constraints", []):
        kind = item["kind"]
        targets = ", ".join(repr(t) for t in item["targets"])
        value = f", {fmt_num(item['value'])}" if item.get("value") is not None else ""
        kwargs = ""
        for key in ("at_a", "at_b", "mode"):
            if item.get("kwargs") and item["kwargs"].get(key) is not None:
                kwargs += f", {key}={item['kwargs'][key]!r}"
        lines.append(
            f"{indent}s = scad.constrain_{kind}_rsketch(s, {targets}{value}{kwargs}, "
            f"constraint_id={item['constraint_id']!r})"
        )
    return lines


# Sketches at or below this entity count recover inline; larger ones go
# through the subprocess guard (SolveSpace's redundancy analysis can explode
# combinatorially on big freeform outlines, and a C-extension call cannot be
# interrupted from Python).
FAST_PATH_MAX_ENTITIES = 24


def recover_constraints_guarded(
    snapshot: Dict[str, Any],
    *,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Recover inline for small sketches; subprocess + wall-clock timeout for
    large ones, degrading honestly to a ``timeout`` report (no constraints)."""
    import os
    import subprocess
    import sys

    entities = snapshot.get("entities", [])
    if len(entities) <= FAST_PATH_MAX_ENTITIES:
        return recover_constraints(snapshot)

    points = sum(1 for e in entities if e.get("kind") == "point")
    budget = timeout if timeout is not None else min(30.0 + 4.0 * points, 240.0)
    env = os.environ.copy()
    package_root = str(__import__("pathlib").Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = (
        package_root if not env.get("PYTHONPATH") else package_root + os.pathsep + env["PYTHONPATH"]
    )
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "cqftc._recover_worker"],
            input=json.dumps(snapshot, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=budget,
            check=False,
            env=env,
            cwd=package_root,
        )
    except subprocess.TimeoutExpired:
        return {
            "block": snapshot.get("block"),
            "status": "timeout",
            "reason": f"recovery exceeded {budget:.0f}s budget",
            "constraints": [],
        }
    if proc.returncode != 0:
        return {
            "block": snapshot.get("block"),
            "status": "error",
            "reason": (proc.stderr or "").strip()[:200] or f"worker exit {proc.returncode}",
            "constraints": [],
        }
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "block": snapshot.get("block"),
            "status": "error",
            "reason": "invalid worker report",
            "constraints": [],
        }
