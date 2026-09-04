"""HistCAD translator output contracts.

Translated HistCAD sources are training data: they must contain the model and
nothing else. These tests pin that purity — no solver checks, no runtime
fallback, no diagnostics in the generated code — plus the dialect corrections
(signed axis distances, full-axis ellipse radii, tangency selectors) and the
translation-time tier gates (solve preflight, drift gate).
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

_DRIFT_STEP: Dict[str, Any] = {
    "coordinate_system": {"Euler Angles": [0.0, 0.0, 0.0], "Translation Vector": [0.0, 0.0, 0.0]},
    "sketch": {"line_1": {"start": [0.0, 0.0], "end": [10.0, 0.0]}},
    "constraints": {"Length": [["line_1", 15.0]]},
    "towards": 1.0,
    "opposite": 0.0,
    "operation": "NewBody",
}


def test_generated_source_carries_no_checks(translator):
    case = translator.translate_case([_RECTANGLE_STEP], "t/rect", constraints_mode="on")
    source = case["source"]
    assert "inspect_sketch" not in source
    assert "SKETCH_CONFLICTS" not in source
    assert "SKETCH_TIER_FALLBACKS" not in source
    # the only sanctioned runtime adaptation is the multi-body merge policy
    body = source.split("def build", 1)[1]
    assert "try:" not in body and "except" not in body


def test_feature_headers_are_parseable_ftc(translator):
    case = translator.translate_case([_RECTANGLE_STEP], "t/rect", constraints_mode="on")
    headers = re.findall(r"# ---- feature: (.+) ----", case["source"])
    assert headers, "feature header missing"
    for header in headers:
        assert re.fullmatch(r"\S+ \(\w+, profile=(sketch|geometry)\)", header), header


def test_horizontal_vertical_list_form_maps_each_line(translator):
    case = translator.translate_case([_RECTANGLE_STEP], "t/rect", constraints_mode="on")
    source = case["source"]
    assert source.count("constrain_horizontal_rsketch") == 2
    assert source.count("constrain_vertical_rsketch") == 2


def test_axis_distance_takes_sign_from_coordinates(translator):
    case = translator.translate_case([_RECTANGLE_STEP], "t/rect", constraints_mode="on")
    source = case["source"]
    # line_3.start=(8.89, 3.81) -> line_3.end=(0, 3.81): directed dx = -8.89
    assert "constrain_distance_x_rsketch(s, 'line_3.start', 'line_3.end', -8.89" in source
    # line_3.end=(0, 3.81) -> line_1.start=(0, 0): directed dy = -3.81
    assert "constrain_distance_y_rsketch(s, 'line_3.end', 'line_1.start', -3.81" in source


def test_major_minor_radius_are_half_axis_lengths(translator):
    case = translator.translate_case([_ELLIPSE_STEP], "t/ell", constraints_mode="on")
    source = case["source"]
    assert "constrain_major_radius_rsketch(s, 'ellipse_1', 1.1112" in source
    assert "constrain_minor_radius_rsketch(s, 'ellipse_1', 0.635" in source


def test_auto_mode_keeps_solving_features_on_sketch_tier(translator):
    case = translator.translate_case([_RECTANGLE_STEP], "t/rect", constraints_mode="auto")
    assert case["features"][0]["tier"] == "sketch"
    # pooled coincidents are elided, so the rectangle keeps 2 translational DOF
    assert case["features"][0]["status"] in {"solved", "underconstrained"}
    assert case["conflicts"] == []
    assert case["features"][0]["max_move"] == pytest.approx(0.0, abs=1e-9)


def test_auto_mode_gates_drifting_solves_to_geometry_tier(translator):
    case = translator.translate_case([_DRIFT_STEP], "t/drift", constraints_mode="auto")
    assert case["features"][0]["tier"] == "geometry"
    conflict = case["conflicts"][0]
    assert conflict["status"] == "diverged"
    assert conflict["feature"] == 0


def test_off_mode_transcribes_without_constraints(translator):
    case = translator.translate_case([_RECTANGLE_STEP], "t/rect", constraints_mode="off")
    source = case["source"]
    assert "constrain_" not in source
    assert case["features"][0]["tier"] == "geometry"


def test_sidecar_report_names_conflicting_constraint_ids(translator):
    # an over-determined rectangle (Fix pins every corner) whose stated
    # length contradicts the coordinates: auto mode must fall back and NAME
    # the offending entry
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
    case = translator.translate_case([step], "t/bad", constraints_mode="auto")
    assert case["features"][0]["tier"] == "geometry"
    conflict = case["conflicts"][0]
    assert conflict["status"] in {"conflicting", "failed"}
    assert any(cid.startswith("h") and "_Distance" in cid for cid in conflict["failed_constraints"])
    assert "inspect_sketch" not in case["source"]
