"""FreeCAD runtime tests for geometric signature topology matching."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from simplecadapi.translator.freecad_translator.runtime import (
    assemble_runtime_source,
)


class TestFreeCADTranslatorGSM(unittest.TestCase):
    def _discover_freecadcmd(self) -> str | None:
        return (
            shutil.which("FreeCADCmd")
            or shutil.which("freecadcmd")
            or (
                "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
                if os.path.exists(
                    "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
                )
                else None
            )
        )

    def _run_runtime_probe(self, probe: str) -> dict:
        freecad_cmd = self._discover_freecadcmd()
        if not freecad_cmd:
            self.skipTest("freecadcmd not available")

        with tempfile.TemporaryDirectory() as tmp_dir:
            script_path = os.path.join(tmp_dir, "probe.py")
            result_path = os.path.join(tmp_dir, "result.json")
            script = "\n".join(
                [
                    "import json",
                    "import math",
                    "import FreeCAD as App",
                    "import Part",
                    "doc = App.newDocument('SimpleCADGSMProbe')",
                    "GRAPH_NODES = {}",
                    "GRAPH_OUTPUTS = {}",
                    "GRAPH_METADATA = {}",
                    "GRAPH_SELECTIONS = {}",
                    "GRAPH_SPINE_OBJECTS = {}",
                    "GRAPH_LIMITATIONS = {}",
                    "GRAPH_TRANSLATION_LIMITATIONS = {}",
                    "PRODUCT_VALUES = {}",
                    "ASSEMBLY_PROJECTION_INPUTS = {}",
                    "GUI_VISIBILITY_BY_NAME = {}",
                    "GUI_EXPANDED_BY_NAME = {}",
                    "GUI_SHAPE_COLOR_BY_NAME = {}",
                    "GUI_MATERIAL_OVERRIDE_BY_NAME = {}",
                    "MATERIAL_OBJECTS_BY_ID = {}",
                    "SIMPLECAD_JOINT_OBJECTS = {}",
                    "SKETCH_REGISTRY = []",
                    "OP_EXPRESSION_BINDINGS = {}",
                    "OP_EXPRESSION_LIMITATIONS = {}",
                    "EXPRESSION_GRAPH = {}",
                    f"RESULT_PATH = {json.dumps(result_path)}",
                    assemble_runtime_source(),
                    probe,
                ]
            )
            with open(script_path, "w", encoding="utf-8") as handle:
                handle.write(script)
            completed = subprocess.run(
                [freecad_cmd, script_path],
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=f"stdout={completed.stdout!r}\nstderr={completed.stderr!r}",
            )
            with open(result_path, "r", encoding="utf-8") as handle:
                return json.load(handle)

    def test_split_line_selector_resolves_unique_fragment_chain(self):
        result = self._run_runtime_probe(
            """
shape = Part.makeCompound([
    Part.makeLine(App.Vector(0, 0, 0), App.Vector(1, 0, 0)),
    Part.makeLine(App.Vector(1, 0, 0), App.Vector(2, 0, 0)),
])
selector = {
    'kind': 'edge',
    'geom_type': 'LINE',
    'start': [0, 0, 0],
    'end': [2, 0, 0],
    'center': [1, 0, 0],
    'length': 2,
    'bbox': {'min': [0, 0, 0], 'max': [2, 0, 0]},
}
indices = _selection_indices_for_selector(shape, selector, context='split test')
with open(RESULT_PATH, 'w', encoding='utf-8') as handle:
    json.dump({'indices': indices}, handle)
"""
        )

        self.assertEqual(result["indices"], [0, 1])

    def test_two_source_selectors_resolve_one_merged_edge(self):
        result = self._run_runtime_probe(
            """
shape = Part.makeCompound([
    Part.makeLine(App.Vector(0, 0, 0), App.Vector(2, 0, 0)),
])
selectors = [
    {
        'kind': 'edge', 'geom_type': 'LINE',
        'start': [0, 0, 0], 'end': [1, 0, 0],
        'center': [0.5, 0, 0], 'length': 1,
        'bbox': {'min': [0, 0, 0], 'max': [1, 0, 0]},
    },
    {
        'kind': 'edge', 'geom_type': 'LINE',
        'start': [1, 0, 0], 'end': [2, 0, 0],
        'center': [1.5, 0, 0], 'length': 1,
        'bbox': {'min': [1, 0, 0], 'max': [2, 0, 0]},
    },
]
indices = _selection_indices_for_selectors(shape, selectors, context='merge test')
with open(RESULT_PATH, 'w', encoding='utf-8') as handle:
    json.dump({'indices': indices}, handle)
"""
        )

        self.assertEqual(result["indices"], [0])

    def test_identical_candidates_are_rejected_as_ambiguous(self):
        result = self._run_runtime_probe(
            """
shape = Part.makeCompound([
    Part.makeLine(App.Vector(0, 0, 0), App.Vector(2, 0, 0)),
    Part.makeLine(App.Vector(0, 0, 0), App.Vector(2, 0, 0)),
])
selector = {
    'kind': 'edge', 'geom_type': 'LINE',
    'start': [0, 0, 0], 'end': [2, 0, 0],
    'center': [1, 0, 0], 'length': 2,
    'bbox': {'min': [0, 0, 0], 'max': [2, 0, 0]},
}
try:
    _selection_indices_for_selector(shape, selector, context='ambiguity test')
except RuntimeError as error:
    message = str(error)
else:
    message = ''
with open(RESULT_PATH, 'w', encoding='utf-8') as handle:
    json.dump({'message': message}, handle)
"""
        )

        self.assertIn("ambiguous", result["message"].lower())

    def test_second_candidate_inside_match_threshold_is_ambiguous(self):
        result = self._run_runtime_probe(
            """
shape = Part.makeCompound([
    Part.makeLine(App.Vector(0, 0, 0), App.Vector(2, 0, 0)),
    Part.makeLine(App.Vector(0, 0.000005, 0), App.Vector(2, 0.000005, 0)),
])
selector = {
    'kind': 'edge', 'geom_type': 'LINE',
    'start': [0, 0, 0], 'end': [2, 0, 0],
    'center': [1, 0, 0], 'length': 2,
    'bbox': {'min': [0, 0, 0], 'max': [2, 0, 0]},
}
scores = [
    _geo_selector_score(candidate, selector, index)
    for index, candidate in enumerate(shape.Edges)
]
try:
    _selection_indices_for_selector(shape, selector, context='near ambiguity test')
except RuntimeError as error:
    message = str(error)
else:
    message = ''
with open(RESULT_PATH, 'w', encoding='utf-8') as handle:
    json.dump({'message': message, 'scores': scores}, handle)
"""
        )

        self.assertLessEqual(result["scores"][1], 1e-4)
        self.assertIn("ambiguous", result["message"].lower())

    def test_split_full_circle_selector_resolves_unique_closed_chain(self):
        result = self._run_runtime_probe(
            """
shape = Part.makeCompound([
    Part.Arc(App.Vector(1, 0, 0), App.Vector(0, 1, 0), App.Vector(-1, 0, 0)).toShape(),
    Part.Arc(App.Vector(-1, 0, 0), App.Vector(0, -1, 0), App.Vector(1, 0, 0)).toShape(),
])
selector = {
    'kind': 'edge', 'geom_type': 'CIRCLE',
    'start': [1, 0, 0], 'end': [1, 0, 0],
    'center': [0, 0, 0], 'length': 2 * math.pi,
    'bbox': {'min': [-1, -1, 0], 'max': [1, 1, 0]},
}
indices = _selection_indices_for_selector(shape, selector, context='circle split test')
with open(RESULT_PATH, 'w', encoding='utf-8') as handle:
    json.dump({'indices': indices}, handle)
"""
        )

        self.assertEqual(result["indices"], [0, 1])

    def test_three_source_selectors_resolve_one_merged_edge(self):
        result = self._run_runtime_probe(
            """
shape = Part.makeCompound([
    Part.makeLine(App.Vector(0, 0, 0), App.Vector(3, 0, 0)),
])
selectors = [
    {
        'kind': 'edge', 'geom_type': 'LINE',
        'start': [index, 0, 0], 'end': [index + 1, 0, 0],
        'center': [index + 0.5, 0, 0], 'length': 1,
        'bbox': {'min': [index, 0, 0], 'max': [index + 1, 0, 0]},
    }
    for index in range(3)
]
indices = _selection_indices_for_selectors(shape, selectors, context='three-way merge test')
with open(RESULT_PATH, 'w', encoding='utf-8') as handle:
    json.dump({'indices': indices}, handle)
"""
        )

        self.assertEqual(result["indices"], [0])


if __name__ == "__main__":
    unittest.main()
