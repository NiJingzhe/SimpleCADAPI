from __future__ import annotations

import subprocess
import sys
import unittest

import simplecadapi as scad


class TestErrorHarness(unittest.TestCase):
    def test_simplecad_error_is_public(self):
        self.assertTrue(hasattr(scad, "SimpleCADError"))

    def test_make_box_raises_llm_friendly_english_error(self):
        with self.assertRaises(scad.SimpleCADError) as ctx:
            scad.make_box_rsolid(0.0, 1.0, 1.0)

        message = str(ctx.exception)
        self.assertIn("Operation: make_box_rsolid", message)
        self.assertIn("Signature: make_box_rsolid(", message)
        self.assertIn(
            "Documentation: For full usage details, run help(simplecadapi.make_box_rsolid).",
            message,
        )
        self.assertIn("What happened:", message)
        self.assertIn("Possible causes:", message)
        self.assertIn("How to fix:", message)
        self.assertIn("Technical details:", message)
        self.assertIn("Failed to create a box solid.", message)
        self.assertIn("Use width, height, and depth values greater than zero.", message)

    def test_extrude_raises_actionable_closed_wire_guidance(self):
        wire = scad.make_segment_rwire((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))

        with self.assertRaises(scad.SimpleCADError) as ctx:
            scad.extrude_rsolid(wire, (0.0, 0.0, 1.0), 2.0)

        message = str(ctx.exception)
        self.assertIn("Operation: extrude_rsolid", message)
        self.assertIn("Signature: extrude_rsolid(", message)
        self.assertIn("A wire profile was provided but it is not closed.", message)
        self.assertIn(
            "If you extrude a wire, make sure the wire is closed or convert it to a face first.",
            message,
        )

    def test_import_graph_json_reports_signature_and_help(self):
        with self.assertRaises(scad.SimpleCADError) as ctx:
            scad.import_graph_json('{"schema_version":"2.0","nodes":[],"edges":[]}')

        message = str(ctx.exception)
        self.assertIn("Operation: import_graph_json", message)
        self.assertIn("Signature: import_graph_json(", message)
        self.assertIn(
            "Documentation: For full usage details, run help(simplecadapi.import_graph_json).",
            message,
        )

    def test_add_part_rassembly_reports_signature_and_help(self):
        asm = scad.make_assembly_rassembly([])

        with self.assertRaises(scad.SimpleCADError) as ctx:
            scad.add_part_rassembly(asm, "p1", "not-a-solid")

        message = str(ctx.exception)
        self.assertIn("Operation: add_part_rassembly", message)
        self.assertIn("Signature: add_part_rassembly(", message)
        self.assertIn(
            "Documentation: For full usage details, run help(simplecadapi.add_part_rassembly).",
            message,
        )

    def test_vendor_swig_deprecation_warnings_are_suppressed_on_import(self):
        result = subprocess.run(
            [
                sys.executable,
                "-W",
                "default",
                "-c",
                "import simplecadapi",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        stderr = result.stderr
        self.assertNotIn("SwigPyPacked", stderr)
        self.assertNotIn("SwigPyObject", stderr)
        self.assertNotIn("swigvarlink", stderr)


if __name__ == "__main__":
    unittest.main()
