"""Tests for public math helper APIs."""

from __future__ import annotations

import math
import json

import pytest

import simplecadapi as scad
import simplecadapi.math as scmath


def _distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def test_fit_line_returns_minimal_cubic_controls() -> None:
    samples = [(float(i), 0.0, 0.0) for i in range(8)]

    result = scmath.fit_cubic_bspline_control_points(samples, tolerance=1e-10)

    assert result.converged
    assert result.control_count == 4
    assert result.dimension == 3
    assert result.max_error <= 1e-10
    assert result.unique_knots == (0.0, 1.0)
    assert result.multiplicities == (4, 4)
    assert result.evaluate(0.0) == pytest.approx(samples[0])
    assert result.evaluate(1.0) == pytest.approx(samples[-1])
    assert result.evaluate(0.5) == pytest.approx((3.5, 0.0, 0.0))


def test_fit_semicircle_adaptively_inserts_simple_knots() -> None:
    sample_parameters = [i * math.pi / 20.0 for i in range(21)]
    samples = [(math.cos(t), math.sin(t), 0.0) for t in sample_parameters]

    result = scad.fit_cubic_bspline_control_points(samples, tolerance=0.002)

    assert result.converged
    assert 4 < result.control_count < len(samples)
    assert result.max_error <= result.tolerance
    assert result.multiplicities[0] == 4
    assert result.multiplicities[-1] == 4
    assert all(multiplicity == 1 for multiplicity in result.multiplicities[1:-1])

    sample_errors = [
        _distance(result.evaluate(parameter), sample)
        for parameter, sample in zip(result.sample_parameters, samples)
    ]
    assert max(sample_errors) <= result.tolerance


def test_fit_accepts_2d_samples_and_serializes_result() -> None:
    samples = [(0.0, 0.0), (0.25, 0.2), (0.5, -0.1), (0.75, 0.2), (1.0, 0.0)]

    result = scmath.fit_cubic_bspline_control_points(
        samples,
        tolerance=0.05,
        fairing=1e-3,
    )
    payload = result.to_dict()

    assert result.converged
    assert result.dimension == 2
    assert payload["degree"] == 3
    assert payload["control_points"] == [list(point) for point in result.control_points]
    assert payload["unique_knots"] == list(result.unique_knots)
    assert payload["multiplicities"] == list(result.multiplicities)
    assert payload["converged"] is True


def test_fit_removes_consecutive_duplicate_samples() -> None:
    samples = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]

    result = scmath.fit_cubic_bspline_control_points(samples, tolerance=1e-10)

    assert result.converged
    assert len(result.sample_parameters) == 3
    assert result.max_error <= 1e-10


def test_fit_returns_best_result_when_failure_is_allowed() -> None:
    sample_parameters = [i * math.pi / 20.0 for i in range(21)]
    samples = [(math.cos(t), math.sin(t), 0.0) for t in sample_parameters]

    result = scmath.fit_cubic_bspline_control_points(
        samples,
        tolerance=1e-6,
        max_control_points=4,
        raise_on_failure=False,
    )

    assert not result.converged
    assert result.control_count == 4
    assert result.max_error > result.tolerance


def test_fit_raises_when_tolerance_cannot_be_met() -> None:
    sample_parameters = [i * math.pi / 20.0 for i in range(21)]
    samples = [(math.cos(t), math.sin(t), 0.0) for t in sample_parameters]

    with pytest.raises(ValueError, match="failed to fit a cubic B-spline"):
        scmath.fit_cubic_bspline_control_points(
            samples,
            tolerance=1e-6,
            max_control_points=4,
        )


@pytest.mark.parametrize(
    ("samples", "match"),
    [
        ([], "at least two distinct points"),
        ([(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)], "at least two distinct points"),
        ([(0.0, 0.0), (1.0, 0.0, 0.0)], "same dimension"),
        ([(0.0,), (1.0,)], "2D or 3D"),
        ([(0.0, 0.0), (math.nan, 1.0)], "finite"),
    ],
)
def test_fit_validates_sample_points(samples: list[tuple[float, ...]], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        scmath.fit_cubic_bspline_control_points(samples)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"tolerance": 0.0}, "tolerance"),
        ({"fairing": -1.0}, "fairing"),
        ({"duplicate_tolerance": -1.0}, "duplicate_tolerance"),
        ({"knot_tolerance": 0.0}, "knot_tolerance"),
        ({"max_control_points": 3}, "max_control_points"),
    ],
)
def test_fit_validates_options(kwargs: dict[str, float], match: str) -> None:
    samples = [(0.0, 0.0, 0.0), (0.5, 0.1, 0.0), (1.0, 0.0, 0.0)]

    with pytest.raises(ValueError, match=match):
        scmath.fit_cubic_bspline_control_points(samples, **kwargs)


def test_math_helper_is_public_through_top_level_and_submodule() -> None:
    assert scad.fit_cubic_bspline_control_points is scmath.fit_cubic_bspline_control_points
    assert scad.BSplineFitResult is scmath.BSplineFitResult
    assert scad.math is scmath
    assert "math" in scad.__all__
    assert "fit_cubic_bspline_control_points" in scad.__all__


def test_fit_result_fields_feed_exact_spline_builder() -> None:
    samples = [(0.0, 0.0, 0.0), (1.0, 0.6, 0.0), (2.0, 0.0, 0.0)]
    fit = scmath.fit_cubic_bspline_control_points(samples, tolerance=0.01)

    edge = scad.make_spline_redge(
        control_points=fit.control_points,
        knots=fit.unique_knots,
        multiplicities=fit.multiplicities,
    )

    assert isinstance(edge, scad.Edge)
    metadata = edge.get_metadata("geo")
    assert metadata["type"] == "bspline"
    assert metadata["degree"] == fit.degree
    assert metadata["knots"] == list(fit.unique_knots)
    assert metadata["multiplicities"] == list(fit.multiplicities)


def test_exact_spline_builder_accepts_full_repeated_knot_vector() -> None:
    edge = scad.make_spline_redge(
        control_points=[
            (0.0, 0.0, 0.0),
            (0.5, 1.0, 0.0),
            (1.5, 1.0, 0.0),
            (2.0, 0.0, 0.0),
        ],
        knots=[0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0],
    )

    metadata = edge.get_metadata("geo")
    assert metadata["knots"] == [0.0, 1.0]
    assert metadata["multiplicities"] == [4, 4]


def test_exact_spline_builder_validates_exact_payload() -> None:
    with pytest.raises(ValueError, match=r"sum\(multiplicities\)"):
        scad.make_spline_redge(
            control_points=[
                (0.0, 0.0, 0.0),
                (0.5, 1.0, 0.0),
                (1.5, 1.0, 0.0),
                (2.0, 0.0, 0.0),
            ],
            knots=[0.0, 1.0],
            multiplicities=[3, 3],
        )


def test_exact_spline_graph_payload_uses_control_parameters() -> None:
    with scad.GraphSession() as session:
        scad.make_spline_redge(
            control_points=[
                (0.0, 0.0),
                (0.5, 1.0),
                (1.5, 1.0),
                (2.0, 0.0),
            ]
        )

    payload = json.loads(scad.export_model_json(session))
    node = next(node for node in payload["graph"]["nodes"] if node["op"] == "make_spline_redge")

    assert "control_points" in node["params"]
    assert "points" not in node["params"]
    assert node["params"]["degree"] == 3
    assert node["params"]["knots"] == [0.0, 1.0]
    assert node["params"]["multiplicities"] == [4, 4]
    replayed = scad.replay_model_json(json.dumps(payload))
    assert len(replayed) == 1
    assert isinstance(replayed[0], scad.Edge)
