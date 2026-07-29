from __future__ import annotations

import pytest
from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Trsf, gp_Vec

from simplecadapi.inverse_engineer.brep.diagnostics import (
    build_difference_regions,
    compare_boundary_distance,
    compare_entities,
    compare_global_properties,
    compare_sections,
    compute_material_difference,
    evaluate_result,
    find_nearby_entities,
)
from simplecadapi.inverse_engineer.brep.model import index_shape
import simplecadapi.inverse_engineer.brep.diagnostics as diagnostics


def _box(x: float = 10.0, y: float = 20.0, z: float = 30.0):
    return BRepPrimAPI_MakeBox(x, y, z).Shape()


def _translated(shape, x: float, y: float, z: float):
    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(x, y, z))
    operation = BRepBuilderAPI_Transform(shape, transform, True)
    operation.Build()
    assert operation.IsDone()
    return operation.Shape()


def test_global_boundary_and_material_diagnostics():
    target = index_shape(_box())
    current = index_shape(_box(9.0, 20.0, 30.0))

    global_properties = compare_global_properties(target, current)
    boundary = compare_boundary_distance(
        target,
        current,
        linear_deflection=3.0,
        max_samples=64,
    )
    material = compute_material_difference(target, current)

    assert global_properties["volume"]["absolute_delta"] == pytest.approx(-600.0)
    assert boundary["symmetric"]["hausdorff_approximation"] == pytest.approx(1.0)
    assert material["missing_material"]["volume"] == pytest.approx(600.0)
    assert material["excess_material"]["volume"] == pytest.approx(0.0)
    assert material["boolean_result_valid"] is True


def test_boundary_identity_and_section_comparison():
    target = index_shape(_box())

    boundary = compare_boundary_distance(
        target,
        target,
        linear_deflection=3.0,
        max_samples=32,
    )
    section = compare_sections(
        target,
        target,
        (0.0, 0.0, 15.0),
        (0.0, 0.0, 1.0),
        samples_per_edge=4,
    )

    assert boundary["symmetric"]["hausdorff_approximation"] < 1.0e-9
    assert section["comparison"]["hausdorff_approximation"] < 1.0e-9
    assert section["comparison"]["area_delta"] == pytest.approx(0.0)


def test_boundary_distance_can_scope_each_model_to_selected_faces():
    target = index_shape(_box())
    result = compare_boundary_distance(
        target,
        target,
        linear_deflection=3.0,
        max_samples=16,
        target_face_ids=["face:0"],
        current_face_ids=["face:0"],
    )

    assert result["scope"] == {
        "target_face_ids": ["face:0"],
        "current_face_ids": ["face:0"],
    }
    assert result["target_to_current"]["sample_count"] <= 16
    assert result["symmetric"]["hausdorff_approximation"] < 1.0e-9


def test_difference_regions_and_nearby_entities():
    target = index_shape(_box())
    current = index_shape(_translated(_box(), 2.0, 0.0, 0.0))

    regions = build_difference_regions(
        target,
        current,
        distance_threshold=0.5,
        linear_deflection=4.0,
        max_samples=48,
    )
    nearby = find_nearby_entities(
        target,
        region=regions["regions"][0],
        radius=1.0,
        max_results=10,
    )

    assert regions["region_count"] >= 1
    assert nearby["entity_count"] >= 1
    assert nearby["entities"][0]["distance"] <= 1.0


def test_difference_regions_reuses_precomputed_results(monkeypatch):
    target = index_shape(_box())
    current = index_shape(_translated(_box(), 2.0, 0.0, 0.0))
    boundary = compare_boundary_distance(
        target,
        current,
        linear_deflection=4.0,
        max_samples=32,
        include_records=True,
    )
    material = compute_material_difference(target, current)

    monkeypatch.setattr(
        diagnostics,
        "compare_boundary_distance",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("recomputed boundary")
        ),
    )
    monkeypatch.setattr(
        diagnostics,
        "compute_material_difference",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("recomputed material")
        ),
    )
    regions = build_difference_regions(
        target,
        current,
        distance_threshold=0.5,
        include_boundary=True,
        boundary_result=boundary,
        material_result=material,
    )

    assert regions["boundary_included"] is True
    assert regions["region_count"] >= 1


def test_difference_regions_default_skips_boundary_sampling(monkeypatch):
    target = index_shape(_box())
    current = index_shape(_translated(_box(), 2.0, 0.0, 0.0))
    monkeypatch.setattr(
        diagnostics,
        "compare_boundary_distance",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("boundary sampled")
        ),
    )

    regions = build_difference_regions(target, current)

    assert regions["boundary_included"] is False
    assert regions["boundary_summary"] is None
    assert regions["region_count"] >= 1


def test_entity_comparison_and_evaluation_gates():
    target = index_shape(_box())
    identical = index_shape(_box())
    different = index_shape(_box(9.0, 20.0, 30.0))

    entity = compare_entities(target, "face:0", identical, "face:0")
    passed = evaluate_result(
        target,
        identical,
        replay_succeeded=True,
        linear_deflection=3.0,
        max_samples=32,
        require_strict_brep=True,
    )
    failed = evaluate_result(
        target,
        different,
        replay_succeeded=True,
        linear_deflection=3.0,
        max_samples=32,
    )

    assert entity["kind_match"] is True
    assert entity["geometry_type_match"] is True
    assert entity["distance"]["distance"] == pytest.approx(0.0)
    assert passed["passed"] is True
    assert passed["strict_brep_executed"] is True
    assert failed["passed"] is False
    assert failed["strict_brep_executed"] is False
    assert failed["metrics"]["strict_brep"] is None


def test_evaluation_does_not_run_strict_comparison_unless_requested(monkeypatch):
    def unexpected_strict_comparison(*args, **kwargs):
        raise AssertionError("strict comparison must not execute")

    monkeypatch.setattr(diagnostics, "compare_shapes", unexpected_strict_comparison)
    result = evaluate_result(
        index_shape(_box()),
        index_shape(_box()),
        replay_succeeded=True,
        linear_deflection=3.0,
        max_samples=32,
        require_strict_brep=False,
    )

    assert result["passed"] is True
    assert result["strict_brep_executed"] is False
    assert result["metrics"]["strict_brep"] is None


def test_boundary_sample_budget_limits_face_tessellation(monkeypatch):
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    for index in range(4):
        builder.Add(compound, _translated(_box(), index * 20.0, 0.0, 0.0))
    model = index_shape(compound)
    sampled = []

    def fake_face_samples(face, linear_deflection):
        del linear_deflection
        sampled.append(face)
        return diagnostics.shape_mass(face, "area")[1][None, :]

    monkeypatch.setattr(diagnostics, "_face_samples", fake_face_samples)

    points = diagnostics._surface_samples(
        model,
        linear_deflection=1.0,
        max_samples=16,
    )

    assert len(sampled) <= 16
    assert len(points) <= 16
