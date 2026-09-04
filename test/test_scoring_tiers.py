"""Tests for layered scoring and feature-semantic coverage."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "cadquery_converter"))

from cadquery_converter.scoring.feature_semantics import (  # noqa: E402
    identify_feature_units,
)
from cadquery_converter.scoring.tiers import assign_training_tier  # noqa: E402
from cadquery_converter.scoring.geometry import GeometryMetrics, ValidationResult  # noqa: E402
from cadquery_converter.scoring.feature_semantics import FeatureSemanticsScore  # noqa: E402
from cadquery_converter.scoring.parameters import ParameterScore  # noqa: E402
from cadquery_converter.tracer.trace_schema import TraceStep  # noqa: E402
from cadquery_converter.traced_convert import convert_cadquery_traced_source  # noqa: E402
from cadquery_converter.replay.trace_replay import filter_meaningful_steps, replay_trace_to_sftc  # noqa: E402
from cadquery_converter.tracer.cq_runner import run_cadquery_traced  # noqa: E402


HEX_NUT_CQ = """
import cadquery as cq

result = (
    cq.Workplane("XY")
    .moveTo(10.39, 0.0)
    .lineTo(5.195, 8.998)
    .lineTo(-5.195, 8.998)
    .lineTo(-10.39, 0.0)
    .lineTo(-5.195, -8.998)
    .lineTo(5.195, -8.998)
    .close()
    .extrude(10.8)
    .faces(">Z")
    .workplane()
    .circle(6.0)
    .cutThruAll()
)

show_object(result)
"""

WASHER_CQ = """
import cadquery as cq

result = (
    cq.Workplane("XZ")
    .circle(32.4)
    .extrude(5.0)
    .faces(">Y").workplane()
    .hole(37.0)
    .edges(">Y")
    .chamfer(0.4)
)

show_object(result)
"""


class TestFeatureSemantics(unittest.TestCase):
    def test_hex_nut_profile_folds_into_one_extrude(self) -> None:
        steps = [
            TraceStep(op="Workplane", plane_name="XY"),
            TraceStep(op="moveTo"),
            TraceStep(op="lineTo"),
            TraceStep(op="lineTo"),
            TraceStep(op="lineTo"),
            TraceStep(op="lineTo"),
            TraceStep(op="lineTo"),
            TraceStep(op="lineTo"),
            TraceStep(op="close"),
            TraceStep(op="extrude", args=[10.8]),
            TraceStep(op="faces"),
            TraceStep(op="workplane"),
            TraceStep(op="circle", args=[6.0]),
            TraceStep(op="cutThruAll"),
        ]
        units = identify_feature_units(steps)
        self.assertEqual(len(units), 2)
        self.assertEqual(units[0].kind, "Extrude")
        self.assertEqual(units[0].cq_trace_kinds.count("lineTo"), 6)
        self.assertIn("extrude", units[0].cq_trace_kinds)
        self.assertEqual(units[1].kind, "Cut")

    def test_replay_hex_nut_manifest_coverage(self) -> None:
        trace = run_cadquery_traced(HEX_NUT_CQ)
        code, meta = replay_trace_to_sftc(trace, graph_id="hex_nut")
        manifest = meta["feature_manifest"]
        self.assertGreaterEqual(manifest["feature_coverage"], 0.9)
        self.assertEqual(manifest["identified_count"], 2)
        kinds = [unit["kind"] for unit in manifest["feature_units"]]
        self.assertIn("Extrude", kinds)
        self.assertIn("Cut", kinds)
        # Six line segments in SFTC, but one Extrude semantic unit
        self.assertEqual(code.count("make_segment_redge"), 6)


class TestTrainingTier(unittest.TestCase):
    def test_tier_a_requires_coverage_and_geometry(self) -> None:
        metrics = GeometryMetrics(valid=True, volume=100.0, bbox=(0, 0, 0, 1, 1, 1))
        validation = ValidationResult(
            cq=metrics,
            scad=metrics,
            json_replay=metrics,
            volume_rel_error=0.01,
            bbox_rel_error=0.01,
            quality="accepted",
        )
        structure = FeatureSemanticsScore(identified_count=3, emitted_count=3, feature_coverage=1.0)
        parameters = ParameterScore(declared_count=2, referenced_count=2, param_match_rate=1.0)
        tier = assign_training_tier(
            quality="accepted",
            conversion_status="ok",
            validation=validation,
            structure=structure,
            parameters=parameters,
            replay_ok=True,
        )
        self.assertEqual(tier.training_tier, "A")

    def test_traced_washer_gets_tier(self) -> None:
        _, _, report = convert_cadquery_traced_source(
            WASHER_CQ,
            graph_id="washer",
            validate=True,
        )
        self.assertEqual(report.quality, "accepted")
        self.assertIn(report.training_tier, {"A", "B"})
        self.assertIsNotNone(report.feature_manifest)
        self.assertGreaterEqual(report.structure["feature_coverage"], 0.9)
        kinds = [unit["kind"] for unit in report.feature_manifest["feature_units"]]
        self.assertEqual(kinds, ["Extrude", "Hole", "Chamfer"])


PULLEY_REVOLVE_CQ = """
import cadquery as cq

result = (
    cq.Workplane("YZ")
    .polyline([
        [17.5, -12.6], [31.5, -12.6], [62.4, -12.6], [62.4, -5.0], [70.0, -5.0],
        [70.0, 5.0], [62.4, 5.0], [62.4, 12.6], [31.5, 12.6], [17.5, 12.6],
    ])
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
)

show_object(result)
"""

LOFT_CQ = """
import cadquery as cq

result = cq.Workplane("XY").circle(7).workplane(offset=8).circle(6.272).loft()
show_object(result)
"""

MIRROR_Y_CQ = """
import cadquery as cq

result = (
    cq.Workplane("XY")
    .moveTo(0, 0)
    .lineTo(10, 0)
    .lineTo(10, 4)
    .lineTo(2, 4)
    .lineTo(2, 20)
    .lineTo(10, 20)
    .lineTo(10, 24)
    .lineTo(0, 24)
    .mirrorY()
    .extrude(5)
)

show_object(result)
"""

SPACER_NESTED_CUT_CQ = """
import cadquery as cq

result = (
    cq.Workplane("XY").circle(12).extrude(0.8)
    .faces(">Z").workplane().hole(15)
    .cut(cq.Workplane("XY").transformed(offset=(0, 0, 0)).box(10, 2.25, 1.8))
)

show_object(result)
"""


class TestKernelEmitFixes(unittest.TestCase):
    def test_revolve_axis_is_workplane_local(self) -> None:
        code, _, report = convert_cadquery_traced_source(
            PULLEY_REVOLVE_CQ, graph_id="pulley", validate=True
        )
        self.assertEqual(report.quality, "accepted")
        self.assertIn("axis=(0, 0, 1)", code)

    def test_loft_emits_wires(self) -> None:
        code, _, report = convert_cadquery_traced_source(LOFT_CQ, graph_id="loft", validate=True)
        self.assertEqual(report.quality, "accepted")
        self.assertIn("make_circle_rwire", code)
        self.assertNotIn("make_circle_rface", code)

    def test_mirror_y_closes_profile(self) -> None:
        code, _, report = convert_cadquery_traced_source(
            MIRROR_Y_CQ, graph_id="i_beam_like", validate=True
        )
        self.assertEqual(report.quality, "accepted")
        self.assertEqual(code.count("make_segment_redge"), 14)

    def test_nested_cut_tool_not_extra_feature(self) -> None:
        _, _, report = convert_cadquery_traced_source(
            SPACER_NESTED_CUT_CQ, graph_id="spacer", validate=True
        )
        self.assertEqual(report.quality, "accepted")
        self.assertEqual(report.feature_manifest["identified_count"], 3)
        self.assertGreaterEqual(report.feature_manifest["feature_coverage"], 0.99)
        kinds = [unit["kind"] for unit in report.feature_manifest["feature_units"]]
        self.assertEqual(kinds, ["Extrude", "Hole", "Cut"])

    def test_both_extrude_uses_full_distance_each_way(self) -> None:
        code = """
import cadquery as cq
result = (
    cq.Workplane("XZ")
    .rect(10, 4)
    .extrude(1.0, both=True)
)
show_object(result)
"""
        sftc, _, report = convert_cadquery_traced_source(code, graph_id="both", validate=True)
        self.assertEqual(report.quality, "accepted")
        self.assertIn("distance=(extrude_distance) * 2.0", sftc)
        self.assertIn("scad.translate", sftc)

    def test_slot2d_shell_spline_and_move_to_revolve(self) -> None:
        slot_cq = """
import cadquery as cq
result = cq.Workplane("XY").slot2D(40, 20, 0).extrude(5)
show_object(result)
"""
        _, _, slot_report = convert_cadquery_traced_source(slot_cq, graph_id="slot", validate=True)
        self.assertEqual(slot_report.quality, "accepted")

        shell_cq = """
import cadquery as cq
result = cq.Workplane("XZ").box(20, 20, 10).faces(">Y").shell(-1)
show_object(result)
"""
        _, _, shell_report = convert_cadquery_traced_source(shell_cq, graph_id="shell", validate=True)
        self.assertEqual(shell_report.quality, "accepted")

        spline_cq = """
import cadquery as cq
result = (
    cq.Workplane("XY")
    .circle(1)
    .sweep(cq.Workplane("XY").spline([(0, 0, 0), (10, 0, 0), (10, 10, 0)]), isFrenet=True)
)
show_object(result)
"""
        spline_code, _, spline_report = convert_cadquery_traced_source(
            spline_cq, graph_id="spline_sweep", validate=False
        )
        self.assertIn("make_interpolated_spline_rwire", spline_code)
        self.assertFalse(spline_report.unsupported)

        revolve_cq = """
import cadquery as cq
result = (
    cq.Workplane("XY")
    .moveTo(10, 0)
    .circle(2)
    .revolve(180, (0, 0, 0), (0, -1, 0))
)
show_object(result)
"""
        revolve_code, _, revolve_report = convert_cadquery_traced_source(
            revolve_cq, graph_id="half_revolve", validate=True
        )
        self.assertEqual(revolve_report.quality, "accepted")
        self.assertIn("center=(10, 0, 0)", revolve_code)

    def test_deferred_union_and_polar_holes(self) -> None:
        u_bolt_like = """
import cadquery as cq
result = (
    cq.Workplane("XY")
    .transformed(offset=cq.Vector(-20, 0, 20))
    .cylinder(40, 5)
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(20, 0, 20))
            .cylinder(40, 5)
    )
    .union(
        cq.Workplane("XY")
            .transformed(offset=cq.Vector(0, 0, 40))
            .moveTo(20, 0)
            .circle(5)
            .revolve(180, (0, 0, 0), (0, -1, 0))
    )
)
show_object(result)
"""
        code, _, report = convert_cadquery_traced_source(
            u_bolt_like, graph_id="u_bolt_like", validate=True
        )
        self.assertEqual(report.quality, "accepted")
        self.assertGreaterEqual(code.count("tool_"), 2)
        self.assertTrue(
            "union_rsolid(*_body_union_parts)" in code or "_body_smart_fuse" in code
        )

        polar = """
import cadquery as cq
result = (
    cq.Workplane("XY")
    .cylinder(10, 20)
    .faces(">Z").workplane()
    .polarArray(10, 0, 360, 6)
    .hole(3)
)
show_object(result)
"""
        _, _, polar_report = convert_cadquery_traced_source(
            polar, graph_id="polar_holes", validate=True
        )
        self.assertEqual(polar_report.quality, "accepted")


if __name__ == "__main__":
    unittest.main()
