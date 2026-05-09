"""Tests for canonical model export with assembly metadata."""

from __future__ import annotations

import json
import unittest

import simplecadapi as scad
from simplecadapi.graph import GraphSession


class TestAssemblyModelExport(unittest.TestCase):
    def test_export_model_json_can_include_assembly_registry(self):
        a = scad.make_box_rsolid(1.0, 1.0, 1.0)
        b = scad.make_box_rsolid(1.0, 1.0, 1.0)
        asm = scad.make_assembly_rassembly([("a", a), ("b", b)])
        gap = scad.var("gap", 2.0)
        asm = scad.constrain_offset_rassembly(
            asm,
            asm.part("a").anchor("bbox.top"),
            asm.part("b").anchor("bbox.bottom"),
            gap,
            axis="z",
        )

        with GraphSession() as session:
            scad.make_circle_rface((0, 0, 0), scad.var("r", 3.0))

        payload = json.loads(scad.export_model_json(session, assembly=asm))
        self.assertIn("assembly", payload)
        self.assertIn("parts", payload["assembly"])
        self.assertIn("constraint_param_exprs", payload["assembly"])
        self.assertEqual(len(payload["assembly"]["parts"]), 2)


if __name__ == "__main__":
    unittest.main()
