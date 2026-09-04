"""Tests for CadQuery → SFTC converter."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "cadquery_converter"))

from cadquery_converter.convert import convert_cadquery_source  # noqa: E402


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


HEX_NUT_CQ = """
import cadquery as cq

result = (
    cq.Workplane("XY")
    .polygon(6, 6.35)
    .extrude(2.4)
    .faces(">Z").workplane()
    .circle(1.5)
    .cutThruAll()
)

show_object(result)
"""


RARRAY_CQ = """
import cadquery as cq

result = (
    cq.Workplane("YZ")
    .box(110.69, 154.26, 13.98)
    .faces(">X").workplane()
    .rarray(20.37, 75.31, 4, 2)
    .rect(11.65, 38.68)
    .cutBlind(-6.99)
)

show_object(result)
"""


REVOLVE_CQ = """
import cadquery as cq

result = (
    cq.Workplane("YZ")
    .polyline([[17.5, -12.6], [31.5, -12.6], [62.4, -12.6], [62.4, -5.0], [70.0, -5.0], [70.0, 5.0], [62.4, 5.0], [62.4, 12.6], [31.5, 12.6], [17.5, 12.6]])
    .close()
    .revolve(360, (0, 0, 0), (0, 1, 0))
)

show_object(result)
"""


class TestCadQueryConverter(unittest.TestCase):
    def test_washer_emits_sftc_sections(self) -> None:
        code, report = convert_cadquery_source(
            WASHER_CQ,
            graph_id="washer",
            stem="washer",
            family="washer",
        )
        self.assertIn("# -- Parameters --", code)
        self.assertIn("@scad.model(graph_id='washer')", code)
        self.assertIn("make_circle_rface", code)
        self.assertIn("extrude_rsolid", code)
        self.assertIn("cut_rsolid", code)
        self.assertIn("chamfer_rsolid", code)
        self.assertIn("capture_result", code)
        self.assertGreater(report.feature_count, 0)

    def test_hex_nut_polygon_extrude_and_cut(self) -> None:
        code, report = convert_cadquery_source(
            HEX_NUT_CQ,
            graph_id="hex_nut",
            stem="hex_nut",
            family="hex_nut",
        )
        self.assertIn("make_polyline_rwire", code)
        self.assertIn("cut_rsolid", code)
        self.assertGreater(report.feature_count, 0)

    def test_rarray_cutblind_emits_pattern_loop(self) -> None:
        code, report = convert_cadquery_source(RARRAY_CQ, graph_id="waffle")
        self.assertIn("for _ix in range(4)", code)
        self.assertIn("cut_rsolid", code)

    def test_revolve_emits_revolve_rsolid(self) -> None:
        code, report = convert_cadquery_source(REVOLVE_CQ, graph_id="pulley")
        self.assertIn("revolve_rsolid", code)
        self.assertGreater(report.feature_count, 0)

    def test_validation_runs_for_washer(self) -> None:
        code, report = convert_cadquery_source(
            WASHER_CQ,
            graph_id="washer",
            validate=True,
        )
        self.assertIsNotNone(report.validation)
        self.assertIn(report.quality, {"accepted", "partial", "rejected"})
        if report.quality == "accepted":
            self.assertLess(report.validation["volume_rel_error"], 0.05)

    def test_benchcad_sample_if_available(self) -> None:
        dataset = Path("/mnt/c/Users/zhuxi/Documents/data/BenchCAD")
        parquet = dataset / "code_gen/data/code_gen-00000-of-00018.parquet"
        if not parquet.is_file():
            self.skipTest("BenchCAD dataset not mounted")

        try:
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow not installed")

        table = pq.read_table(parquet, columns=["stem", "family", "code"])
        code = table["code"][0].as_py()
        converted, report = convert_cadquery_source(
            code,
            graph_id=table["stem"][0].as_py(),
            stem=table["stem"][0].as_py(),
            family=table["family"][0].as_py(),
            validate=True,
        )
        self.assertIn("@scad.model", converted)
        json.dumps(report.to_dict())


if __name__ == "__main__":
    unittest.main()
