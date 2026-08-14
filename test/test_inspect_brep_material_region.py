from __future__ import annotations

import math
import pytest
from OCP.BRep import BRep_Builder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Pnt

from simplecadapi.inspect import brep


def _candidate_with_two_notches():
    target = BRepPrimAPI_MakeBox(10.0, 4.0, 4.0).Shape()
    first = BRepPrimAPI_MakeBox(gp_Pnt(1.0, 1.0, 1.0), 1.0, 1.0, 1.0).Shape()
    second = BRepPrimAPI_MakeBox(gp_Pnt(8.0, 1.0, 1.0), 1.0, 1.0, 1.0).Shape()
    cut = BRepAlgoAPI_Cut(target, first)
    cut.Build()
    cut2 = BRepAlgoAPI_Cut(cut.Shape(), second)
    cut2.Build()
    return target, cut2.Shape()


def _compound(*shapes):
    result = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(result)
    for shape in shapes:
        builder.Add(result, shape)
    return result


def test_compare_material_region_limits_evidence_to_roi(tmp_path):
    target, candidate = _candidate_with_two_notches()

    report = brep.compare_material_region_rdescriptor(
        target,
        candidate,
        region_min=(0.0, 0.0, 0.0),
        region_max=(5.0, 4.0, 4.0),
        output_directory=tmp_path,
    )

    assert report["missing_material"]["volume"] == pytest.approx(1.0)
    assert report["excess_material"]["volume"] == pytest.approx(0.0)
    assert report["missing_material"]["component_count"] == 1
    assert report["local_equality_supported"] is True
    assert report["global_equality_supported"] is False
    assert (tmp_path / "missing_material.step").is_file()


def test_compare_material_region_reports_empty_local_difference():
    target, candidate = _candidate_with_two_notches()

    report = brep.compare_material_region_rdescriptor(
        target,
        candidate,
        region_min=(4.0, 0.0, 0.0),
        region_max=(7.0, 4.0, 4.0),
    )

    assert report["missing_material"]["volume"] == pytest.approx(0.0)
    assert report["excess_material"]["volume"] == pytest.approx(0.0)
    assert report["locally_equal"] is True
    assert report["global_equality_supported"] is False


def test_compare_material_region_handles_empty_roi_crop():
    target, candidate = _candidate_with_two_notches()

    report = brep.compare_material_region_rdescriptor(
        target,
        candidate,
        region_min=(20.0, 20.0, 20.0),
        region_max=(21.0, 21.0, 21.0),
    )

    assert report["localized_target_volume"] == pytest.approx(0.0)
    assert report["localized_current_volume"] == pytest.approx(0.0)
    assert report["locally_equal"] is True


def test_compare_material_region_handles_one_empty_crop_side():
    target = BRepPrimAPI_MakeBox(2.0, 2.0, 2.0).Shape()
    current = BRepPrimAPI_MakeBox(gp_Pnt(5.0, 0.0, 0.0), 2.0, 2.0, 2.0).Shape()

    report = brep.compare_material_region_rdescriptor(
        target,
        current,
        region_min=(0.0, 0.0, 0.0),
        region_max=(2.0, 2.0, 2.0),
    )

    assert report["missing_material"]["volume"] == pytest.approx(8.0)
    assert report["excess_material"]["volume"] == pytest.approx(0.0)
    assert report["boolean_result_valid"] is True


def test_compare_material_region_supports_multi_body_material_unions():
    first = BRepPrimAPI_MakeBox(2.0, 2.0, 2.0).Shape()
    second = BRepPrimAPI_MakeBox(gp_Pnt(5.0, 0.0, 0.0), 2.0, 2.0, 2.0).Shape()
    target = _compound(first, second)
    current = _compound(first, second)

    report = brep.compare_material_region_rdescriptor(
        target,
        current,
        region_min=(-1.0, -1.0, -1.0),
        region_max=(8.0, 3.0, 3.0),
    )

    assert report["localized_target_volume"] == pytest.approx(16.0)
    assert report["localized_current_volume"] == pytest.approx(16.0)
    assert report["locally_equal"] is True


def test_compare_material_region_large_roi_does_not_hide_difference():
    target = BRepPrimAPI_MakeBox(0.5, 0.5, 0.5).Shape()
    current = BRepPrimAPI_MakeBox(gp_Pnt(10.0, 0.0, 0.0), 0.5, 0.5, 0.5).Shape()

    report = brep.compare_material_region_rdescriptor(
        target,
        current,
        region_min=(-1000.0, -1000.0, -1000.0),
        region_max=(1000.0, 1000.0, 1000.0),
    )

    assert report["missing_material"]["volume"] == pytest.approx(0.125)
    assert report["locally_equal"] is False


def test_compare_material_region_removes_stale_exports(tmp_path):
    target = BRepPrimAPI_MakeBox(2.0, 2.0, 2.0).Shape()
    current = BRepPrimAPI_MakeBox(gp_Pnt(5.0, 0.0, 0.0), 2.0, 2.0, 2.0).Shape()
    brep.compare_material_region_rdescriptor(
        target,
        current,
        region_min=(0.0, 0.0, 0.0),
        region_max=(2.0, 2.0, 2.0),
        output_directory=tmp_path,
    )
    assert (tmp_path / "missing_material.step").is_file()

    report = brep.compare_material_region_rdescriptor(
        target,
        target,
        region_min=(0.0, 0.0, 0.0),
        region_max=(2.0, 2.0, 2.0),
        output_directory=tmp_path,
    )

    assert report["locally_equal"] is True
    assert not (tmp_path / "missing_material.step").exists()


def test_compare_material_region_exports_one_sided_crop(tmp_path):
    target = BRepPrimAPI_MakeBox(2.0, 2.0, 2.0).Shape()
    current = BRepPrimAPI_MakeBox(gp_Pnt(5.0, 0.0, 0.0), 2.0, 2.0, 2.0).Shape()

    report = brep.compare_material_region_rdescriptor(
        target,
        current,
        region_min=(0.0, 0.0, 0.0),
        region_max=(2.0, 2.0, 2.0),
        output_directory=tmp_path,
    )

    assert report["exported_files"]["missing_material"] == str(
        tmp_path / "missing_material.step"
    )
    assert (tmp_path / "missing_material.step").is_file()


def test_compare_material_region_rejects_export_alias(tmp_path):
    from simplecadapi.kernel.ocp_export import export_step_shapes

    source = tmp_path / "missing_material.step"
    export_step_shapes([BRepPrimAPI_MakeBox(1.0, 1.0, 1.0).Shape()], str(source))

    with pytest.raises(ValueError, match="would overwrite an input STEP"):
        brep.compare_material_region_rdescriptor(
            source,
            source,
            region_min=(0.0, 0.0, 0.0),
            region_max=(1.0, 1.0, 1.0),
            output_directory=tmp_path,
        )


def test_compare_material_region_bounds_component_records():
    target = BRepPrimAPI_MakeBox(10.0, 2.0, 2.0).Shape()
    first = BRepPrimAPI_MakeBox(gp_Pnt(1.0, 0.5, 0.5), 1.0, 1.0, 1.0).Shape()
    second = BRepPrimAPI_MakeBox(gp_Pnt(7.0, 0.5, 0.5), 1.0, 1.0, 1.0).Shape()
    cut = BRepAlgoAPI_Cut(target, first)
    cut.Build()
    cut2 = BRepAlgoAPI_Cut(cut.Shape(), second)
    cut2.Build()

    report = brep.compare_material_region_rdescriptor(
        target,
        cut2.Shape(),
        region_min=(0.0, 0.0, 0.0),
        region_max=(10.0, 2.0, 2.0),
        max_components=1,
    )

    assert report["missing_material"]["component_count"] == 2
    assert len(report["missing_material"]["components"]) == 1
    assert report["missing_material"]["components_truncated"] is True


def test_compare_material_region_rejects_invalid_region():
    box = BRepPrimAPI_MakeBox(1.0, 1.0, 1.0).Shape()
    with pytest.raises(ValueError, match="region_max must exceed region_min"):
        brep.compare_material_region_rdescriptor(
            box,
            box,
            region_min=(0.0, 0.0, 0.0),
            region_max=(0.0, 1.0, 1.0),
        )
    with pytest.raises(ValueError, match="boolean_tolerance must be finite"):
        brep.compare_material_region_rdescriptor(
            box,
            box,
            region_min=(0.0, 0.0, 0.0),
            region_max=(1.0, 1.0, 1.0),
            boolean_tolerance=math.nan,
        )


def test_compare_material_region_rejects_invalid_zero_volume_solid():
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
    from OCP.TopoDS import TopoDS_Shell

    shell = TopoDS_Shell()
    BRep_Builder().MakeShell(shell)
    zero_volume = BRepBuilderAPI_MakeSolid(shell).Solid()

    with pytest.raises(ValueError, match="valid positive-volume solid material"):
        brep.compare_material_region_rdescriptor(
            zero_volume,
            zero_volume,
            region_min=(0.0, 0.0, 0.0),
            region_max=(1.0, 1.0, 1.0),
        )
