from __future__ import annotations

import json

import pytest
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from simplecadapi.inspect import brep


def _open_face():
    wire = BRepBuilderAPI_MakeWire()
    points = (
        gp_Pnt(0.0, 0.0, 0.0),
        gp_Pnt(2.0, 0.0, 0.0),
        gp_Pnt(2.0, 1.0, 0.0),
        gp_Pnt(0.0, 1.0, 0.0),
    )
    for first, last in zip(points, (*points[1:], points[0])):
        wire.Add(BRepBuilderAPI_MakeEdge(first, last).Edge())
    return BRepBuilderAPI_MakeFace(wire.Wire(), True).Face()


def test_validate_step_roundtrip_reports_persistence_and_topology(tmp_path):
    output = tmp_path / "box.step"
    result = brep.validate_step_roundtrip_rdescriptor(
        BRepPrimAPI_MakeBox(2.0, 3.0, 4.0).Shape(), output
    )

    assert result["passed"] is True
    assert result["output_path"] == str(output.resolve())
    assert result["file_size"] > 0
    assert result["sha256"].startswith("sha256:")
    assert result["before"]["volume"] == pytest.approx(24.0)
    assert result["after"]["volume"] == pytest.approx(24.0)
    assert result["property_deltas"]["relative_volume"] == pytest.approx(0.0)
    assert result["topology_after"]["closed_manifold"] is True
    json.dumps(result, allow_nan=False)


def test_validate_step_roundtrip_preserves_open_face_semantics(tmp_path):
    result = brep.validate_step_roundtrip_rdescriptor(
        _open_face(), tmp_path / "face.step"
    )
    assert result["passed"] is True
    assert result["before"]["root_shape_type"] == "Face"
    assert result["after"]["root_shape_type"] == "Shell"
    assert result["topology_before"]["edge_classification_counts"]["free"] == 4
    assert result["topology_after"]["edge_classification_counts"]["free"] == 4


def test_validate_step_roundtrip_rejects_input_output_alias(tmp_path):
    source = tmp_path / "source.step"
    brep.validate_step_roundtrip_rdescriptor(
        BRepPrimAPI_MakeBox(1.0, 1.0, 1.0).Shape(), source
    )
    with pytest.raises(ValueError, match="must differ from the input STEP path"):
        brep.validate_step_roundtrip_rdescriptor(source, source)
    model = brep.load_step_rbrepmodel(source)
    with pytest.raises(ValueError, match="protected input STEP path"):
        brep.validate_step_roundtrip_rdescriptor(model, source)


def test_failed_roundtrip_does_not_replace_existing_output(tmp_path, monkeypatch):
    from simplecadapi.inspect.brep import persistence

    output = tmp_path / "existing.step"
    sentinel = b"do-not-replace"
    output.write_bytes(sentinel)
    monkeypatch.setattr(persistence, "_relative_delta", lambda before, after: 1.0)

    result = persistence.validate_step_roundtrip_rdescriptor(
        BRepPrimAPI_MakeBox(1.0, 1.0, 1.0).Shape(), output
    )
    assert result["passed"] is False
    assert result["output_replaced"] is False
    assert output.read_bytes() == sentinel


@pytest.mark.parametrize("count_name", ["edge_count", "vertex_count"])
def test_roundtrip_does_not_publish_topology_count_drift(
    tmp_path, monkeypatch, count_name
):
    from simplecadapi.inspect.brep import persistence

    output = tmp_path / f"{count_name}.step"
    sentinel = b"do-not-replace"
    output.write_bytes(sentinel)
    original_index = persistence.index_shape_rbrepmodel
    index_calls = 0

    def drifting_index(*args, **kwargs):
        nonlocal index_calls
        index_calls += 1
        model = original_index(*args, **kwargs)
        if index_calls == 1:
            return model
        original_summary = model.summary

        def summary():
            result = original_summary()
            result[count_name] += 1
            return result

        model.summary = summary
        return model

    monkeypatch.setattr(persistence, "index_shape_rbrepmodel", drifting_index)

    result = persistence.validate_step_roundtrip_rdescriptor(
        BRepPrimAPI_MakeBox(1.0, 1.0, 1.0).Shape(), output
    )

    assert result["passed"] is False
    assert result["output_replaced"] is False
    assert output.read_bytes() == sentinel
