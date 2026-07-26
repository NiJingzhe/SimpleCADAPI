from __future__ import annotations

import math
from pathlib import Path

import pytest
import simplecadapi as scad
from simplecadapi.inverse_engineer import brep
from simplecadapi.inverse_engineer.brep.cli import main as brep_cli_main


def _box():
    return scad.make_box_rsolid(width=4.0, height=3.0, depth=2.0)


def _two_arc_cylinder():
    first = scad.make_angle_arc_redge(
        center=(0.0, 0.0, 0.0),
        radius=1.0,
        start_angle=0.0,
        end_angle=math.pi,
        normal=(0.0, 0.0, 1.0),
    )
    second = scad.make_angle_arc_redge(
        center=(0.0, 0.0, 0.0),
        radius=1.0,
        start_angle=math.pi,
        end_angle=2.0 * math.pi,
        normal=(0.0, 0.0, 1.0),
    )
    wire = scad.make_wire_from_edges_rwire(edges=[first, second])
    face = scad.make_face_from_wire_rface(wire=wire, normal=(0.0, 0.0, 1.0))
    return scad.extrude_rsolid(profile=face, direction=(0.0, 0.0, 1.0), distance=2.0)


def test_inspect_shape_reports_unique_and_occurrence_counts():
    report = brep.inspect_shape(_box().wrapped)

    assert report.valid is True
    assert report.counts["unique_faces"] == 6
    assert report.counts["unique_edges"] == 12
    assert report.counts["unique_vertices"] == 8
    assert report.counts["edge_occurrences"] == 24
    assert report.surface_type_counts == {"Plane": 6}
    assert report.edge_type_counts == {"Line": 12}
    assert report.volume == pytest.approx(24.0)


def test_inspect_bspline_edge_includes_reconstruction_parameters():
    wire = scad.make_spline_rwire(
        control_points=[
            (0.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (2.0, 1.0, 0.0),
            (3.0, 0.0, 0.0),
        ],
        degree=3,
    )

    report = brep.inspect_shape(wire.wrapped)
    spline = report.edges[0]

    assert spline["type"] == "BSplineCurve"
    assert spline["degree"] == 3
    assert spline["poles"] == 4
    assert len(spline["control_points"]) == 4
    assert len(spline["knot_values"]) == spline["knots"]
    assert len(spline["multiplicities"]) == spline["knots"]


def test_compare_same_shape_passes_geometry_and_topology():
    shape = _box().wrapped
    comparison = brep.compare_shapes(shape, shape)

    assert comparison.same_geometric_point_set is True
    assert comparison.geometry_labelled_incidence_graph_isomorphic is True
    assert comparison.hard_gate_passed is True
    assert comparison.target_minus_candidate_volume == 0.0
    assert comparison.candidate_minus_target_volume == 0.0


def test_compare_detects_same_geometry_with_different_topology():
    full_circle = scad.make_cylinder_rsolid(radius=1.0, height=2.0)
    two_arcs = _two_arc_cylinder()

    comparison = brep.compare_shapes(full_circle.wrapped, two_arcs.wrapped)

    assert comparison.same_geometric_point_set is True
    assert comparison.geometry_labelled_incidence_graph_isomorphic is False
    assert comparison.hard_gate_passed is False


def test_center_slice_specs_follow_shape_bounds():
    specs = brep.center_slice_specs(
        minimum=(-2.0, 4.0, 10.0),
        maximum=(6.0, 8.0, 14.0),
    )

    assert [(spec.plane, spec.value) for spec in specs] == [
        ("yz", 2.0),
        ("xz", 6.0),
        ("xy", 12.0),
    ]


def test_compare_shape_slices_has_zero_xor_for_same_shape():
    shape = _box().wrapped
    comparison = brep.compare_shape_slices(
        shape,
        shape,
        slices=(brep.SliceSpec("xy", 1.0), brep.SliceSpec("xz", 1.5)),
        samples=(11, 9),
    )

    assert comparison.total_samples == 198
    assert comparison.xor_samples == 0
    assert comparison.sampled_slices_identical is True


def test_step_round_trip_and_cli(tmp_path: Path):
    step = tmp_path / "box.step"
    report_path = tmp_path / "box-report.json"
    comparison_path = tmp_path / "comparison.json"
    scad.export_step(shapes=_box(), filename=str(step))

    report = brep.inspect_step(step)
    comparison = brep.compare_steps(step, step)

    assert report.counts["unique_faces"] == 6
    assert comparison.hard_gate_passed is True
    assert brep_cli_main(["inspect", str(step), "--output", str(report_path)]) == 0
    assert (
        brep_cli_main(
            ["compare", str(step), str(step), "--output", str(comparison_path)]
        )
        == 0
    )
    assert report_path.exists()
    assert comparison_path.exists()
