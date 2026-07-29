from __future__ import annotations

import math

import numpy as np
import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from simplecadapi.inverse_engineer.brep.model import BRepEntityError, index_shape
from simplecadapi.inverse_engineer.brep.queries import (
    _section_contours,
    extract_face_boundaries,
    get_topology_neighborhood,
    make_section,
    measure_relation,
    probe_point,
    select_region_entities,
)
from simplecadapi.inverse_engineer.brep.render import render_region


def _box():
    return BRepPrimAPI_MakeBox(4.0, 3.0, 2.0).Shape()


def _model():
    return index_shape(_box())


def _plane_faces(model):
    return [
        f"face:{index}"
        for index in range(len(model.faces))
        if model.describe_entity(f"face:{index}")["geometry"]["type"] == "PLANE"
    ]


def test_topology_neighborhood_is_bounded_and_rejects_invalid_ids():
    model = _model()

    neighborhood = get_topology_neighborhood(model, "face:0", depth=2, max_entities=3)

    assert neighborhood["root"] == "face:0"
    assert neighborhood["returned_entity_count"] == 3
    assert neighborhood["truncated"] is True
    assert [item["entity_id"] for item in neighborhood["entities"]] == sorted(
        (item["entity_id"] for item in neighborhood["entities"]),
        key=lambda value: (
            ("body", "face", "edge", "vertex").index(value.split(":")[0]),
            int(value.split(":")[1]),
        ),
    )
    with pytest.raises(BRepEntityError, match="out of range"):
        get_topology_neighborhood(model, "face:99")


def test_measure_relation_reports_exact_distance_and_parallel_planes():
    model = _model()
    faces = _plane_faces(model)
    best = None
    for first in faces:
        for second in faces:
            if first >= second:
                continue
            result = measure_relation(model, first, second)
            if result["relations"]["parallel"]["value"] and result["distance"] > 0.0:
                best = result
                break
        if best:
            break

    assert best is not None
    assert best["distance"] == pytest.approx(4.0)
    assert best["closest_points"]
    assert best["relations"]["parallel"]["supported"] is True
    assert best["relations"]["parallel"]["value"] is True
    assert best["relations"]["coplanar"]["value"] is False


def test_cross_model_face_coincidence_is_not_inferred_from_zero_distance():
    first = _model()
    second = _model()

    relation = measure_relation(
        first,
        "face:0",
        "face:0",
        second_model_or_path=second,
    )

    assert relation["distance"] == pytest.approx(0.0)
    assert relation["relations"]["coincident"]["supported"] is False
    assert relation["relations"]["coincident"]["value"] is None
    assert relation["relations"]["touching"]["value"] is True


def test_section_of_box_returns_one_closed_contour_with_area():
    section = make_section(_model(), origin=(0.0, 0.0, 1.0), normal=(0.0, 0.0, 1.0))

    assert section["edge_count"] == 4
    assert section["closed_contour_count"] == 1
    contour = section["contours"][0]
    assert contour["closed"] is True
    assert contour["length_exact"] == pytest.approx(14.0)
    assert contour["area"] == pytest.approx(12.0)
    assert contour["role"] == "material"
    assert section["material_area"] == pytest.approx(12.0)
    assert len(contour["samples_3d"][0]) == 3
    assert len(contour["samples_2d"][0]) == 2


def test_section_connection_tolerance_heals_small_endpoint_gap():
    gap = 5.0e-6
    points = [
        ([0.0, 0.0, 0.0], [2.0, 0.0, 0.0]),
        ([2.0, 0.0, 0.0], [2.0, 1.0, 0.0]),
        ([2.0, 1.0, 0.0], [0.0, 1.0, 0.0]),
        ([0.0, 1.0, 0.0], [0.0, gap, 0.0]),
    ]
    edges = [
        {
            "index": index,
            "samples_3d": [start, end],
            "length_exact": math.dist(start, end),
        }
        for index, (start, end) in enumerate(points)
    ]
    origin = np.asarray((0.0, 0.0, 0.0))
    x_axis = np.asarray((1.0, 0.0, 0.0))
    y_axis = np.asarray((0.0, 1.0, 0.0))

    strict = _section_contours(
        edges,
        1.0e-7,
        origin,
        x_axis,
        y_axis,
    )
    healed = _section_contours(
        edges,
        1.0e-5,
        origin,
        x_axis,
        y_axis,
    )

    assert strict[0]["closed"] is False
    assert healed[0]["closed"] is True


def test_face_boundaries_preserve_hole_loop_and_pcurve_samples():
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 4.0).Shape()
    axis = gp_Ax2(gp_Pnt(5.0, 5.0, 0.0), gp_Dir(0.0, 0.0, 1.0))
    cut = BRepAlgoAPI_Cut(box, BRepPrimAPI_MakeCylinder(axis, 2.0, 4.0).Shape())
    cut.Build()
    assert cut.IsDone()
    model = index_shape(cut.Shape())
    top_face = next(
        f"face:{index}"
        for index in range(len(model.faces))
        if model.describe_entity(f"face:{index}")["geometry"]["parameters"]["origin"][2]
        == pytest.approx(4.0)
    )

    boundaries = extract_face_boundaries(model, top_face, samples_per_edge=8)

    assert boundaries["outer"]["closed"] is True
    assert boundaries["inner_loop_count"] == 1
    inner_edge = boundaries["inner"][0]["edges"][0]
    assert inner_edge["length_exact"] > 0.0
    assert inner_edge["uv_samples"] is not None
    assert len(inner_edge["uv_samples"]) == 8


def test_face_boundaries_compact_mode_preserves_order_without_samples():
    model = _model()
    detailed = extract_face_boundaries(model, "face:0", samples_per_edge=8)
    compact = extract_face_boundaries(
        model,
        "face:0",
        samples_per_edge=2,
        compact=True,
    )

    assert compact["compact"] is True
    assert compact["outer"]["geometry_type_counts"] == {"LINE": 4}
    assert [edge["entity_id"] for edge in compact["outer"]["edges"]] == [
        edge["entity_id"] for edge in detailed["outer"]["edges"]
    ]
    first = compact["outer"]["edges"][0]
    assert first["geometry_type"] == "LINE"
    assert first["length_exact"] > 0.0
    assert len(first["start"]) == 3
    assert len(first["end"]) == 3
    assert "samples_3d" not in first
    assert "uv_samples" not in first


def test_section_classifies_hole_and_reports_material_area():
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 4.0).Shape()
    axis = gp_Ax2(gp_Pnt(5.0, 5.0, 0.0), gp_Dir(0.0, 0.0, 1.0))
    cut = BRepAlgoAPI_Cut(box, BRepPrimAPI_MakeCylinder(axis, 2.0, 4.0).Shape())
    cut.Build()
    assert cut.IsDone()

    section = make_section(
        index_shape(cut.Shape()),
        origin=(0.0, 0.0, 2.0),
        normal=(0.0, 0.0, 1.0),
        samples_per_edge=64,
    )

    assert section["closed_contour_count"] == 2
    assert {contour["role"] for contour in section["contours"]} == {
        "material",
        "hole",
    }
    assert section["material_area"] == pytest.approx(
        100.0 - math.pi * 4.0,
        rel=2.0e-3,
    )


def test_probe_point_orders_exact_nearest_entities():
    result = probe_point(_model(), point=(8.0, 1.0, 1.0), limit=4)

    assert result["candidate_count"] == 26
    assert len(result["hits"]) == 4
    assert result["hits"][0]["distance"] == pytest.approx(4.0)
    assert result["hits"][0]["closest_point"] == pytest.approx([4.0, 1.0, 1.0])
    assert result["hits"][0]["kind"] == "face"
    assert result["exact_distance_evaluation_count"] < result["candidate_count"]
    assert result["bbox_pruned_count"] > 0


def test_select_region_entities_expands_stable_ids_and_returns_bounds():
    model = _model()
    selection = select_region_entities(model, entity_ids=["face:0"], depth=1)

    assert "face:0" in selection["entity_ids"]
    assert "body:0" in selection["entity_ids"]
    assert any(entity.startswith("edge:") for entity in selection["entity_ids"])
    assert all(
        minimum <= maximum
        for minimum, maximum in zip(
            selection["bounds"]["min"], selection["bounds"]["max"]
        )
    )


def test_render_region_writes_highlighted_image(tmp_path):
    output = tmp_path / "highlight.png"

    result = render_region(_model(), ["face:0"], output, dpi=60)

    assert result == output
    assert output.is_file()
    assert output.stat().st_size > 0
