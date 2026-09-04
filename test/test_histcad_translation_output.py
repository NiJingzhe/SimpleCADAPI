"""HistCAD translator output contracts.

Translated HistCAD sources are training data: they contain the model and
nothing else. These tests pin that purity — no solver checks, no runtime
fallback, no diagnostics in the generated code — plus the dialect corrections
(signed axis distances, full-axis ellipse radii, tangency selectors, pooled
coincident elision). The translator ONLY translates: constraints are emitted
unconditionally; whether they solve is a question for the external audit
tools (histcad_conflicts.py / histcad_validate.py).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

_TOOLS = Path(__file__).resolve().parent.parent / "tools" / "research" / "histjson"


def _load_translator():
    spec = importlib.util.spec_from_file_location(
        "histcad_to_ftc", _TOOLS / "histcad_to_ftc.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("histcad_to_ftc", module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def translator():
    return _load_translator()


_RECTANGLE_STEP: Dict[str, Any] = {
    "coordinate_system": {"Euler Angles": [0.0, 0.0, 0.0], "Translation Vector": [0.0, 0.0, 0.0]},
    "sketch": {
        "line_1": {"start": [0.0, 0.0], "end": [8.89, 0.0]},
        "line_2": {"start": [8.89, 0.0], "end": [8.89, 3.81]},
        "line_3": {"start": [8.89, 3.81], "end": [0.0, 3.81]},
        "line_4": {"start": [0.0, 3.81], "end": [0.0, 0.0]},
    },
    "constraints": {
        "Coincident": [
            ["line_1.end", "line_2.start"],
            ["line_1.start", "line_4.end"],
            ["line_2.end", "line_3.start"],
            ["line_3.end", "line_4.start"],
        ],
        "Distance": [
            ["line_3.start", "line_3.end", {"length": 8.89, "direction": "HORIZONTAL"}],
            ["line_3.end", "line_1.start", {"length": 3.81, "direction": "VERTICAL"}],
        ],
        "Horizontal": ["line_1", "line_3"],
        "Vertical": ["line_2", "line_4"],
    },
    "towards": 0.0,
    "opposite": 1.905,
    "operation": "NewBody",
}

_ELLIPSE_STEP: Dict[str, Any] = {
    "coordinate_system": {"Euler Angles": [0.0, 0.0, 0.0], "Translation Vector": [0.0, 0.0, 0.0]},
    "sketch": {
        "ellipse_1": {"center": [-5.08, -1.905], "major": 1.1112, "minor": 0.635, "angle": 270.0},
    },
    "constraints": {
        # dataset stores the FULL axis length; the sketch fields are semi-axes
        "MajorRadius": [["ellipse_1", 2.2224]],
        "MinorRadius": [["ellipse_1", 1.27]],
    },
    "towards": 1.0,
    "opposite": 0.0,
    "operation": "NewBody",
}


def test_generated_source_carries_no_checks(translator):
    source = translator.translate_steps([_RECTANGLE_STEP], "t/rect", constraints_mode="on")
    assert "inspect_sketch" not in source
    assert "SKETCH_CONFLICTS" not in source
    assert "SKETCH_TIER_FALLBACKS" not in source
    # the only sanctioned runtime adaptation is the multi-body merge policy
    body = source.split("def build", 1)[1]
    assert "try:" not in body and "except" not in body


def test_feature_headers_are_parseable_ftc(translator):
    source = translator.translate_steps([_RECTANGLE_STEP], "t/rect", constraints_mode="on")
    headers = re.findall(r"# ---- feature: (.+) ----", source)
    assert headers, "feature header missing"
    for header in headers:
        assert re.fullmatch(r"\S+ \(\w+, profile=(sketch|geometry)\)", header), header


def test_constraints_are_translated_unconditionally(translator):
    # default mode: every mappable constraint lands in the source even when
    # the stated values contradict the coordinates — auditing is external
    step: Dict[str, Any] = {
        **_RECTANGLE_STEP,
        "constraints": {
            **_RECTANGLE_STEP["constraints"],
            "Distance": [
                ["line_3.start", "line_3.end", {"length": 8.90, "direction": "HORIZONTAL"}],
            ],
            "Fix": [["line_1.start"], ["line_2.start"], ["line_3.start"], ["line_4.start"]],
        },
    }
    source = translator.translate_steps([step], "t/bad", constraints_mode="on")
    assert "constrain_distance_x_rsketch(s, 'line_3.start', 'line_3.end', -8.9" in source
    assert source.count("constrain_fix_rsketch") == 4
    assert "profile=sketch" in source


def test_pooled_coincidents_are_elided(translator):
    # coincident refs that pooled onto the same point are vacuous; emitting
    # them creates degenerate equations that break the solver's Jacobian
    source = translator.translate_steps([_RECTANGLE_STEP], "t/rect", constraints_mode="on")
    assert "constrain_coincident_rsketch" not in source
    # the non-vacuous constraints still translate
    assert source.count("constrain_horizontal_rsketch") == 2
    assert source.count("constrain_vertical_rsketch") == 2


def test_horizontal_vertical_list_form_maps_each_line(translator):
    source = translator.translate_steps([_RECTANGLE_STEP], "t/rect", constraints_mode="on")
    assert source.count("constrain_horizontal_rsketch") == 2
    assert source.count("constrain_vertical_rsketch") == 2


def test_axis_distance_takes_sign_from_coordinates(translator):
    source = translator.translate_steps([_RECTANGLE_STEP], "t/rect", constraints_mode="on")
    # line_3.start=(8.89, 3.81) -> line_3.end=(0, 3.81): directed dx = -8.89
    assert "constrain_distance_x_rsketch(s, 'line_3.start', 'line_3.end', -8.89" in source
    # line_3.end=(0, 3.81) -> line_1.start=(0, 0): directed dy = -3.81
    assert "constrain_distance_y_rsketch(s, 'line_3.end', 'line_1.start', -3.81" in source


def test_major_minor_radius_are_half_axis_lengths(translator):
    source = translator.translate_steps([_ELLIPSE_STEP], "t/ell", constraints_mode="on")
    assert "constrain_major_radius_rsketch(s, 'ellipse_1', 1.1112" in source
    assert "constrain_minor_radius_rsketch(s, 'ellipse_1', 0.635" in source


def test_off_mode_transcribes_without_constraints(translator):
    source = translator.translate_steps([_RECTANGLE_STEP], "t/rect", constraints_mode="off")
    assert "constrain_" not in source
    assert "profile=geometry" in source


def test_translator_never_imports_the_sdk(translator):
    # translation is pure text generation; solving lives in the audit tools.
    # (the generated source's own import line appears only inside a string)
    module_text = Path(_TOOLS / "histcad_to_ftc.py").read_text()
    assert not re.search(r"^\s*(import|from)\s+simplecadapi", module_text, re.MULTILINE)
