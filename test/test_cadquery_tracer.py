"""Tests for CadQuery runtime tracer → SFTC replay pipeline."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "cadquery_converter"))

from cadquery_converter.traced_convert import convert_cadquery_traced_source  # noqa: E402
from cadquery_converter.tracer.cq_runner import run_cadquery_traced  # noqa: E402
from cadquery_converter.replay.trace_replay import replay_trace_to_sftc  # noqa: E402


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


class TestCadQueryTracer(unittest.TestCase):
    def test_trace_washer_records_meaningful_ops(self) -> None:
        trace = run_cadquery_traced(WASHER_CQ)
        self.assertEqual(trace.cq_status, "ok")
        ops = [step.op for step in trace.steps]
        self.assertIn("circle", ops)
        self.assertIn("extrude", ops)
        self.assertIn("hole", ops)
        self.assertIn("chamfer", ops)
        self.assertGreater(trace.cq_volume or 0.0, 0.0)

    def test_replay_washer_emits_executable_sftc(self) -> None:
        trace = run_cadquery_traced(WASHER_CQ)
        code, meta = replay_trace_to_sftc(trace, graph_id="washer")
        self.assertEqual(meta.get("status"), "ok")
        self.assertIn("@scad.model(graph_id='washer')", code)
        self.assertIn("make_circle_rface", code)
        self.assertIn("extrude_rsolid", code)
        self.assertIn("cut_rsolid", code)
        self.assertIn("chamfer_rsolid", code)
        self.assertIn("capture_result", code)

    def test_traced_washer_validates_accepted(self) -> None:
        code, model_json, report = convert_cadquery_traced_source(
            WASHER_CQ,
            graph_id="washer",
            validate=True,
        )
        self.assertEqual(report.status, "ok")
        self.assertEqual(report.quality, "accepted")
        self.assertTrue(report.replay_ok)
        self.assertIsNotNone(model_json)
        self.assertIsNotNone(report.validation)
        self.assertLess(report.validation["volume_rel_error"], 0.02)
        self.assertTrue(report.validation["json_replay"]["valid"])
        self.assertLess(report.validation["json_volume_rel_error"], 0.02)
        self.assertIn("make_circle_rface", code)

    def test_benchcad_traced_sample_if_available(self) -> None:
        dataset = Path("/mnt/c/Users/zhuxi/Documents/data/BenchCAD")
        parquet = dataset / "code_gen/data/code_gen-00000-of-00018.parquet"
        if not parquet.is_file():
            self.skipTest("BenchCAD dataset not mounted")

        try:
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow not installed")

        table = pq.read_table(parquet, columns=["stem", "family", "code"])
        code, _, report = convert_cadquery_traced_source(
            table["code"][0].as_py(),
            graph_id=table["stem"][0].as_py(),
            stem=table["stem"][0].as_py(),
            family=table["family"][0].as_py(),
            validate=True,
        )
        self.assertIn("@scad.model", code)
        json.dumps(report.to_dict())


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


L_BRACKET_CQ = """
import cadquery as cq

result = (
    cq.Workplane("XZ")
    .box(39.17, 39.17, 242.16)
    .faces(">Y").workplane()
    .center(1.78, 1.78)
    .rect(35.61, 35.61)
    .cutThruAll()
)

show_object(result)
"""

from cadquery_converter.validate import (  # noqa: E402
    GeometryMetrics,
    ValidationResult,
    classify_traced_quality,
)


class TestTracedValidationTiers(unittest.TestCase):
    def test_unsupported_ops_downgrade_to_partial(self) -> None:
        metrics = GeometryMetrics(
            valid=True,
            volume=100.0,
            bbox=(0.0, 0.0, 0.0, 1.0, 1.0, 1.0),
        )
        validation = ValidationResult(cq=metrics, scad=metrics, json_replay=metrics)
        result = classify_traced_quality(
            conversion_status="partial",
            unsupported=["revolve without pending profile"],
            replay_ok=True,
            validation=validation,
            has_model_json=True,
        )
        self.assertEqual(result.quality, "partial")
        self.assertIn("unsupported_ops", result.reasons)


class TestCadQueryTracerFixes(unittest.TestCase):
    def test_replay_hex_nut_closed_wire_has_six_edges(self) -> None:
        trace = run_cadquery_traced(HEX_NUT_CQ)
        code, meta = replay_trace_to_sftc(trace, graph_id="hex_nut")
        self.assertEqual(meta.get("status"), "ok")
        self.assertEqual(code.count("make_segment_redge"), 6)
        self.assertIn("make_face_from_wire_rface", code)

    def test_traced_hex_nut_validates_accepted(self) -> None:
        _, _, report = convert_cadquery_traced_source(
            HEX_NUT_CQ,
            graph_id="hex_nut",
            validate=True,
        )
        self.assertEqual(report.quality, "accepted")
        self.assertLess(report.validation["volume_rel_error"], 0.02)

    def test_traced_l_bracket_validates_accepted(self) -> None:
        _, _, report = convert_cadquery_traced_source(
            L_BRACKET_CQ,
            graph_id="l_bracket",
            validate=True,
        )
        self.assertEqual(report.quality, "accepted")
        self.assertLess(report.validation["volume_rel_error"], 0.02)


if __name__ == "__main__":
    unittest.main()
