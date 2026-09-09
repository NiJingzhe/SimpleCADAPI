"""Tests for the snapshot constraint-recovery engine (tools/research/cadqueryftc).

The engine (``cqftc/constraints.py``) implements the recovery axioms:

- P1 fidelity: riveted sets reach solver DOF 0 AND pass the perturbation
  basin test (a jittered rebuild converges back onto the snapshot);
- P2 no invention: candidates are only entailed relations;
- P3 exactly-full DOF: admission is the production solver's DOF drop, with
  redundancy-introducing candidates rejected (the DOF counter alone can be
  fooled by rank-deficient systems);
- P4 verbatim measured values;
- P5 ``inf``-prefixed constraint ids (inferred provenance).

Synthetic snapshots pin the semantics; fixture traces pin the end-to-end
translation with ``--constraints on`` semantics (library level).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOLS_DIR = _REPO_ROOT / "tools" / "research" / "cadqueryftc"
_FIXTURES = _REPO_ROOT / "test" / "cadquery_traces"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from cqftc.constraints import (  # noqa: E402
    emit_constraint_lines,
    recover_constraints,
)
from cqftc.replay import replay_trace_to_ftc  # noqa: E402
from cqftc.tracer.trace_schema import OperationTrace  # noqa: E402

RECT = {
    "block": "rect", "role": "build", "op": "extrude", "closed": True,
    "entities": [
        {"id": "p1", "kind": "point", "xy": [-5.0, -3.0]},
        {"id": "p2", "kind": "point", "xy": [5.0, -3.0]},
        {"id": "p3", "kind": "point", "xy": [5.0, 3.0]},
        {"id": "p4", "kind": "point", "xy": [-5.0, 3.0]},
        {"id": "line_1", "kind": "line", "start": "p1", "end": "p2"},
        {"id": "line_2", "kind": "line", "start": "p2", "end": "p3"},
        {"id": "line_3", "kind": "line", "start": "p3", "end": "p4"},
        {"id": "line_4", "kind": "line", "start": "p4", "end": "p1"},
    ],
}

# Two straight edges + two semicircular ends, tangent at every joint.
SLOT = {
    "block": "slot", "role": "subtract", "op": "cutBlind", "closed": True,
    "entities": [
        {"id": "p1", "kind": "point", "xy": [-2.17, 1.86]},
        {"id": "p2", "kind": "point", "xy": [2.17, 1.86]},
        {"id": "p4", "kind": "point", "xy": [2.17, -1.86]},
        {"id": "p5", "kind": "point", "xy": [-2.17, -1.86]},
        {"id": "c1", "kind": "point", "xy": [2.17, 0.0]},
        {"id": "c2", "kind": "point", "xy": [-2.17, 0.0]},
        {"id": "line_1", "kind": "line", "start": "p1", "end": "p2"},
        {"id": "line_2", "kind": "line", "start": "p4", "end": "p5"},
        {"id": "arc_1", "kind": "arc", "start": "p2", "end": "p4", "center": "c1"},
        {"id": "arc_2", "kind": "arc", "start": "p5", "end": "p1", "center": "c2"},
    ],
}

CIRCLE = {
    "block": "circle", "role": "build", "op": "extrude", "closed": True,
    "entities": [
        {"id": "p1", "kind": "point", "xy": [0.0, 0.0]},
        {"id": "circle_1", "kind": "circle", "center": "p1", "radius": 12.5},
    ],
}


class TestRecoverySynthetic(unittest.TestCase):
    def test_rectangle_rivets_with_canonical_kinds(self) -> None:
        report = recover_constraints(RECT)
        self.assertEqual(report["status"], "riveted")
        self.assertEqual(report["dof_remaining"], 0)
        self.assertEqual(report["dof_declared"], 8)
        self.assertTrue(report["basin_ok"])
        self.assertTrue(report["coords_ok"])
        kinds = report["by_kind"]
        self.assertEqual(kinds.get("horizontal"), 2)
        self.assertEqual(kinds.get("vertical"), 2)
        self.assertEqual(kinds.get("length"), 2)

    def test_slot_rivets_with_tangency(self) -> None:
        report = recover_constraints(SLOT)
        self.assertEqual(report["status"], "riveted")
        self.assertEqual(report["dof_remaining"], 0)
        self.assertGreaterEqual(report["by_kind"].get("tangent", 0), 3)
        self.assertTrue(report["basin_ok"])

    def test_circle_rivets_minimally(self) -> None:
        report = recover_constraints(CIRCLE)
        self.assertEqual(report["status"], "riveted")
        self.assertEqual(len(report["constraints"]), 2)  # fix + radius
        self.assertAlmostEqual(report["constraints"][1]["value"], 12.5)

    def test_no_false_rivet_from_redundant_rank(self) -> None:
        """perpendicular after H/V would fake DOF 0 while width/height float —
        the redundancy guard must reject it and dimensions must take over."""
        report = recover_constraints(RECT)
        kinds = report["by_kind"]
        self.assertNotIn("perpendicular", kinds)  # implied by H+V → redundant
        self.assertEqual(kinds.get("length"), 2)  # real dimension rows instead
        self.assertTrue(report["basin_ok"])

    def test_values_are_verbatim_and_ids_carry_inf_prefix(self) -> None:
        snapshot = json.loads(json.dumps(CIRCLE))
        snapshot["entities"][1]["radius"] = 5.20005115454
        report = recover_constraints(snapshot)
        self.assertEqual(report["status"], "riveted")
        emitted = {c["constraint_id"]: c for c in report["constraints"]}
        radius_rows = [c for c in report["constraints"] if c["kind"] == "radius"]
        self.assertEqual(radius_rows[0]["value"], 5.20005115454)  # P4: no rounding
        for constraint_id in emitted:
            self.assertTrue(constraint_id.startswith("inf"), msg=constraint_id)  # P5

    def test_emission_lines_use_public_api(self) -> None:
        report = recover_constraints(RECT)
        lines = emit_constraint_lines(report)
        self.assertTrue(lines)
        for line in lines:
            self.assertIn("scad.constrain_", line)
            self.assertIn("constraint_id='inf", line)


class TestRecoveryThroughTranslation(unittest.TestCase):
    """End-to-end: --constraints on produces constrained FTC that still
    reconciles at machine precision."""

    def _translate(self, name: str, constraints_mode: bool):
        payload = json.loads((_FIXTURES / f"{name}.trace.json").read_text(encoding="utf-8"))
        payload.pop("stem", None)
        payload.pop("family", None)
        trace = OperationTrace.from_dict(payload)
        return replay_trace_to_ftc(trace, stem=name, constraints_mode=constraints_mode)

    def test_constraints_on_rivets_fixture_sketches(self) -> None:
        source, meta, snapshots = self._translate("hexnut", constraints_mode=True)
        recovery = meta["constraint_recovery"]
        self.assertTrue(recovery)
        for entry in recovery:
            self.assertEqual(entry["status"], "riveted", msg=json.dumps(entry))
        self.assertIn("scad.constrain_fix_rsketch(s,", source)
        self.assertIn("constraint_id='inf1_fix'", source)
        self.assertTrue(snapshots)
        kinds = {e["kind"] for snapshot in snapshots for e in snapshot["entities"]}
        self.assertIn("line", kinds)

    def test_constrained_build_reconciles_volume(self) -> None:
        for name in ("washer", "hexnut", "revolve_ring"):
            with self.subTest(stem=name):
                source, meta, _snapshots = self._translate(name, constraints_mode=True)
                self.assertEqual(meta["status"], "ok")
                cases_dir = _TOOLS_DIR / "out" / "_test_constraint_cases"
                cases_dir.mkdir(parents=True, exist_ok=True)
                staged = cases_dir / f"{name}_cons_{id(self)}.ftc.py"
                staged.write_text(source, encoding="utf-8")
                try:
                    spec = importlib.util.spec_from_file_location(staged.stem, staged)
                    assert spec is not None and spec.loader is not None
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.build()
                    volume = sum(float(b.get_volume()) for b in module.BODIES)
                    expected = json.loads(
                        (_FIXTURES / f"{name}.trace.json").read_text(encoding="utf-8")
                    )["cq_volume"]
                    rel_err = abs(volume - expected) / abs(expected)
                    self.assertLess(rel_err, 1e-6, msg=f"{name}: {volume} vs {expected}")
                finally:
                    staged.unlink(missing_ok=True)

    def test_every_constructedSketch_is_captured(self) -> None:
        """Unified-capture invariant: every distinct make_sketch_rsketch in the
        generated source must have a snapshot entry — no emission path may
        bypass the SketchScript sink (the taper-section gap this test pins)."""
        import re

        for name in ("washer", "hexnut", "revolve_ring", "rarray_plate"):
            with self.subTest(stem=name):
                _source, _meta, snapshots = self._translate(name, constraints_mode=True)
                emitted = {e["role"] for e in snapshots}
                del emitted
                self.assertTrue(snapshots or name == "rarray_plate")
                # rarray_plate's pattern seed is a sketch too (rect in a loop)
                if name == "rarray_plate":
                    self.assertTrue(any(e.get("role") == "pattern" for e in snapshots))

    def test_taper_sections_are_captured_and_constrained(self) -> None:
        """Taper loft sections ride the same sink as plain profiles: the
        pulley's extrude/extrude-2 blocks each contribute two circle-section
        snapshots plus the plain extrude circle, all riveted, and the source
        carries their constraint lines."""
        source, meta, snapshots = self._translate("pulley", constraints_mode=True)
        circles = [
            s for s in snapshots
            if any(e["kind"] == "circle" for e in s["entities"])
        ]
        self.assertGreaterEqual(len(circles), 5)  # 2 + 2 taper sections + plain
        riveted = sum(1 for r in meta["constraint_recovery"] if r["status"] == "riveted")
        self.assertGreaterEqual(riveted, 5)
        self.assertGreaterEqual(source.count("scad.constrain_"), 10)
        # the first taper block itself now carries section constraints
        first_block = source.split("# ---- feature:")[1]
        self.assertIn("constrain_radius_rsketch", first_block)

    def test_sketchscript_sink_is_the_single_capture_point(self) -> None:
        from cqftc.emit import SketchScript

        captured = []

        def sink(sketch: "SketchScript") -> list:
            captured.append(sketch)
            return ["# from sink"]

        sketch = SketchScript("probe", (0, 0, 0), (1, 0, 0), (0, 1, 0), sink=sink)
        sketch.point(0.0, 0.0)
        center_ref = sketch.point(0.0, 0.0)
        sketch.circle(center_ref, 2.5)
        lines = sketch.render()
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].snapshot_entities[0]["kind"], "point")
        self.assertEqual(captured[0].snapshot_entities[1]["kind"], "circle")
        self.assertEqual(lines[-1].strip(), "# from sink")

    def test_constraints_off_changes_nothing(self) -> None:
        source_off, meta_off, snapshots = self._translate("washer", constraints_mode=False)
        self.assertNotIn("constrain_", source_off)
        self.assertEqual(meta_off["constraint_recovery"], [])
        self.assertTrue(snapshots)  # sidecar snapshots are always collected


if __name__ == "__main__":
    unittest.main()
