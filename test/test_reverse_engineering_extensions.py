from __future__ import annotations

from pathlib import Path

import pytest

import simplecadapi as scad
from simplecadapi.inspect import brep
from simplecadapi.kernel.ocp_export import export_step_shapes


def _export(shape: scad.Solid, path: Path) -> Path:
    export_step_shapes([shape.wrapped], str(path))
    return path


def test_analytic_face_fit_identifies_cylindrical_carrier(tmp_path: Path):
    source = _export(
        scad.make_cylinder_rsolid(radius=3.0, height=7.0),
        tmp_path / "cylinder.step",
    )
    summary = brep.inspect_step_rsummary(source)
    fits = [
        brep.fit_face_analytic_rdescriptor(
            source,
            f"face:{index}",
            tolerance=1.0e-5,
            u_samples=9,
            v_samples=9,
        )
        for index in range(summary["face_count"])
    ]
    cylinder_fit = next(
        fit for fit in fits if fit["best_candidate"]["type"] == "cylinder"
    )
    assert cylinder_fit["accepted"] is True
    assert cylinder_fit["best_candidate"]["parameters"]["radius"] == pytest.approx(
        3.0, rel=1.0e-5
    )


def test_section_tracking_rejects_one_loft_across_contour_birth():
    sections = [
        {"contours": [{"area": 100.0, "perimeter": 40.0, "centroid_2d": [0.0, 0.0]}]},
        {
            "contours": [
                {"area": 98.0, "perimeter": 39.5, "centroid_2d": [0.0, 0.0]},
                {
                    "area": 4.0,
                    "perimeter": 8.0,
                    "centroid_2d": [2.0, 0.0],
                    "nesting_depth": 1,
                },
            ]
        },
    ]

    result = brep.track_section_contours_rdescriptor(sections=sections)

    assert result["summary"]["birth_count"] == 2
    assert result["summary"]["single_loft_safe"] is False


def test_step_comparison_render_uses_shared_views_and_writes_image(tmp_path: Path):
    source = _export(
        scad.make_box_rsolid(width=4.0, height=5.0, depth=6.0),
        tmp_path / "box.step",
    )
    output = tmp_path / "comparison.png"
    result = brep.render_step_comparison_rpath(
        source,
        source,
        output,
        image_size=(4.0, 5.0),
        dpi=40,
        linear_deflection=0.5,
        angular_deflection=0.3,
    )
    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0
