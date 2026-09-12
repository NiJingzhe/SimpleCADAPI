"""WHUCAD translator output contracts.

Translated WHUCAD sources are training data: they contain the model and
nothing else — no solver checks, no runtime fallback, no diagnostics. These
tests pin that purity plus the dialect corrections (signed extrude span,
quantization decode, cap/wall reference convention) on hand-built vectors,
so no dataset download is needed to run them.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from typing import List

import numpy as np
import pytest

_TOOLS = Path(__file__).resolve().parent.parent / "tools" / "research" / "whucad"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _TOOLS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def wvec():
    return _load("whucad_vec")


@pytest.fixture(scope="module")
def to_ftc():
    return _load("whucad_to_ftc")


def _row(cmd: int, args: List[int]) -> np.ndarray:
    assert len(args) == 32  # N_ARGS: 5 sketch + 14 body + 9 finish + 4 select
    return np.array([cmd] + args)


def _pad(*values: int) -> List[int]:
    return list(values) + [-1] * (32 - len(values))


def _cylinder_vec() -> np.ndarray:
    """SOL, Circle, Ext — the quantized rows of a one-cylinder pad."""
    quant = lambda v: int(round((v + 1.0) / 2.0 * 256))  # noqa: E731
    size_q = 128  # sketch size → 1.0
    circle = _row(2, _pad(160, 128, -1, -1, 32))          # center (32,0), r=32
    ext = _row(7, _pad(-1, -1, -1, -1, -1,             # sketch arg pads
                       128, 128, 128,                  # plane theta/phi/gamma = 0
                       128, 128, 128,                  # sketch pos = (0,0,0)
                       size_q,                         # sketch size
                       quant(0.5), quant(0.0),         # extents
                       0, 0, -1, -1,                   # extent types, pad
                       0))                             # AddFeatureOperation
    return np.array([
        _row(6, _pad()),   # SOL
        circle,
        ext,
    ])


def test_decode_cylinder(wvec):
    features = wvec.decode_vec(_cylinder_vec(), is_numerical=True)
    assert [f.kind for f in features] == ["Ext"]
    feature = features[0]
    assert feature.operation == "AddFeatureOperation"
    assert feature.extent_one == pytest.approx(0.5)
    assert feature.extent_two == pytest.approx(0.0)
    plan = feature.sketch
    assert plan.plane_origin == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    assert plan.plane_normal == pytest.approx((0.0, 0.0, 1.0), abs=1e-9)
    (loop,) = plan.profile.loops
    (circle,) = loop.curves
    # denormalize: (p - 128) * size / 95 with size = 1.0
    assert circle.center == pytest.approx((32.0 / 95.0, 0.0), abs=1e-9)
    assert circle.radius == pytest.approx(32.0 / 95.0, abs=1e-9)


def test_translate_cylinder_emits_feature_block(to_ftc, wvec):
    features = wvec.decode_vec(_cylinder_vec(), is_numerical=True)
    source = to_ftc.translate_features(features, "0000/test")
    assert "@scad.part(id='whucad-0000-test'" in source
    assert "# ---- feature: ext-1 (build, profile=geometry) ----" in source
    assert "scad.make_sketch_rsketch(name='f0'" in source
    assert "scad.add_circle_rsketch(sketch=s, entity_id='f0_e0_0'" in source
    assert "scad.make_face_from_sketch_rface(sketch=s, profile=0)" in source
    assert "scad.extrude_rsolid(profile=f0_face, direction=(0.0, 0.0, 1.0), distance=0.5)" in source
    assert "bodies = [f0_tool]" in source


def test_translated_source_is_pure_training_data(to_ftc, wvec):
    features = wvec.decode_vec(_cylinder_vec(), is_numerical=True)
    source = to_ftc.translate_features(features, "0000/test")
    body = source.split("def build()")[1]
    assert "assert " not in body
    assert "print(" not in body
    assert "except Exception" not in body  # only _merge_bodies carries one, above build
    assert source.count("try:") <= 1


def test_unsupported_feature_annotated_not_dropped_silently(to_ftc, wvec):
    features = wvec.decode_vec(_cylinder_vec(), is_numerical=True)
    features.append(wvec.UnsupportedFeature("Mirror", ""))
    source = to_ftc.translate_features(features, "0000/test")
    assert "# step 1: unsupported Mirror (Mirror)" in source
    assert "# ---- feature: mirror-" not in source


def test_cylinder_build_volume(to_ftc, wvec, tmp_path):
    """Execute the translated source inside the repo tree; the built volume
    must match the decoded cylinder analytically."""
    features = wvec.decode_vec(_cylinder_vec(), is_numerical=True)
    source = to_ftc.translate_features(features, "0000/test")
    module_path = _TOOLS / "out" / "_cases" / "test_contract.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(source)
    try:
        spec = importlib.util.spec_from_file_location("test_contract", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.build()
        body = result.value.body
        radius = 32.0 / 95.0
        expected = math.pi * radius * radius * 0.5
        assert body.get_volume() == pytest.approx(expected, rel=1e-7)
    finally:
        module_path.unlink(missing_ok=True)
