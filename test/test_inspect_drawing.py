"""Tests for the vector-PDF drawing inspection namespace."""

from __future__ import annotations

import json
import hashlib

import numpy as np

import pymupdf
import pytest

from simplecadapi.inspect import drawing

DISPLAY_WIDTH_PT = 792.0
DISPLAY_HEIGHT_PT = 612.0


def build_drawing(path, *, rotation: int = 0) -> None:
    """Create a small single-page vector drawing fixture.

    The fixture is authored in storage space. With ``rotation=0`` storage and
    display space coincide; with ``rotation=90`` the page is stored portrait
    and displayed landscape, exercising the rotation mapping.
    """
    document = pymupdf.open()
    if rotation == 0:
        page = document.new_page(width=DISPLAY_WIDTH_PT, height=DISPLAY_HEIGHT_PT)
    else:
        page = document.new_page(width=DISPLAY_HEIGHT_PT, height=DISPLAY_WIDTH_PT)
        page.set_rotation(rotation)

    # A 100 x 50 pt outline (the "known" geometry used for calibration).
    page.draw_rect(pymupdf.Rect(50, 50, 150, 100), color=(0, 0, 0))
    # A red stroke, for color filtering.
    page.draw_line(pymupdf.Point(200, 60), pymupdf.Point(300, 60), color=(1, 0, 0))
    # A cubic Bezier, for stroke-length measurement.
    page.draw_bezier(
        pymupdf.Point(200, 200),
        pymupdf.Point(230, 260),
        pymupdf.Point(300, 260),
        pymupdf.Point(330, 200),
        color=(0, 0, 0),
    )
    # A dimension value with stacked tolerance lines.
    page.insert_text(pymupdf.Point(360, 80), "100", fontsize=8)
    page.insert_text(pymupdf.Point(378, 80), "+0.1", fontsize=6)
    page.insert_text(pymupdf.Point(378, 86), "-0.2", fontsize=6)

    document.save(str(path))
    document.close()


@pytest.fixture()
def drawing_pdf(tmp_path):
    path = tmp_path / "fixture_drawing.pdf"
    build_drawing(path)
    return path


@pytest.fixture()
def rotated_pdf(tmp_path):
    path = tmp_path / "fixture_rotated.pdf"
    build_drawing(path, rotation=90)
    return path


class TestInspectDrawingRSummary:
    def test_route_is_vector_with_censuses(self, drawing_pdf):
        summary = drawing.inspect_drawing_rsummary(drawing_pdf)

        assert summary.page_count == 1
        assert summary.route == "vector"
        page = summary.pages[0]
        assert page["rotation"] == 0
        assert page["image_count"] == 0
        assert page["vector"]["path_count"] > 0
        assert page["vector"]["primitive_kinds"]["line"] > 0
        assert page["vector"]["primitive_kinds"]["bezier"] == 1
        assert page["vector"]["stroke_colors"].get("#ff0000", 0) >= 1

    def test_write_json_roundtrip(self, drawing_pdf, tmp_path):
        output = tmp_path / "summary.json"
        written = drawing.inspect_drawing_rsummary(drawing_pdf).write_json(output)

        assert written == output
        assert json.loads(output.read_text(encoding="utf-8"))["route"] == "vector"


class TestExtractDrawingTextRWords:
    def test_words_are_found_and_clustered(self, drawing_pdf):
        text = drawing.extract_drawing_text_rwords(drawing_pdf)

        texts = {word["text"] for word in text.words}
        assert {"100", "+0.1", "-0.2"} <= texts
        for word in text.words:
            x0, y0, x1, y1 = word["box"]
            assert 0 <= x0 < x1 <= text.width_pt
            assert 0 <= y0 < y1 <= text.height_pt

        joined = [cluster["text"] for cluster in text.clusters]
        assert "100 +0.1 -0.2" in joined

    def test_cluster_gap_zero_disables_clustering(self, drawing_pdf):
        text = drawing.extract_drawing_text_rwords(drawing_pdf, cluster_gap_pt=0)

        assert text.clusters == []

    def test_rotated_page_reports_display_space(self, rotated_pdf):
        text = drawing.extract_drawing_text_rwords(rotated_pdf)

        assert text.rotation == 90
        assert (text.width_pt, text.height_pt) == (DISPLAY_WIDTH_PT, DISPLAY_HEIGHT_PT)
        assert text.words, "text must survive the rotation mapping"
        for word in text.words:
            x0, y0, x1, y1 = word["box"]
            assert 0 <= x0 < x1 <= text.width_pt
            assert 0 <= y0 < y1 <= text.height_pt


class TestRenderDrawingViewRPath:
    def test_full_page_overview_with_sidecar(self, drawing_pdf, tmp_path):
        png = drawing.render_drawing_view_rpath(
            drawing_pdf, dpi=72, out_dir=tmp_path, stem="overview"
        )

        assert png.name == "overview.png"
        with pymupdf.open(png) as rendered:
            pass
        pixels = pymupdf.Pixmap(png)
        assert (pixels.width, pixels.height) == (792, 612)

        sidecar = json.loads(png.with_suffix(".json").read_text(encoding="utf-8"))
        assert sidecar["page"] == 0
        assert sidecar["dpi"] == 72
        assert sidecar["rect_display"] == [0.0, 0.0, 792.0, 612.0]

    def test_anchor_crop_frames_the_annotation(self, drawing_pdf, tmp_path):
        text = drawing.extract_drawing_text_rwords(drawing_pdf)
        cluster = next(
            cluster for cluster in text.clusters if cluster["text"] == "100 +0.1 -0.2"
        )

        png = drawing.render_drawing_view_rpath(
            drawing_pdf, anchor=cluster, pad_fraction=1.0, dpi=72, out_dir=tmp_path
        )
        sidecar = json.loads(png.with_suffix(".json").read_text(encoding="utf-8"))
        x0, y0, x1, y1 = sidecar["rect_display"]

        assert x1 - x0 >= 3 * (cluster["box"][2] - cluster["box"][0]) - 1e-6
        assert 0 <= x0 and x1 <= DISPLAY_WIDTH_PT

    def test_rect_and_anchor_are_mutually_exclusive(self, drawing_pdf, tmp_path):
        with pytest.raises(ValueError):
            drawing.render_drawing_view_rpath(
                drawing_pdf,
                rect=[0, 0, 10, 10],
                anchor={"box": [0, 0, 10, 10]},
                out_dir=tmp_path,
            )


class TestExtractDrawingPrimitivesRStrokes:
    def test_filters_narrow_the_dump(self, drawing_pdf):
        strokes = drawing.extract_drawing_primitives_rstrokes(drawing_pdf)

        # One rect item + one line + one bezier: draw_rect emits a single
        # "re" primitive, not four lines.
        assert strokes.total_primitives == 3
        assert strokes.matched == strokes.total_primitives

        red = drawing.extract_drawing_primitives_rstrokes(drawing_pdf, color="#ff0000")
        assert red.matched == 1
        assert red.strokes[0]["kind"] == "line"
        assert red.strokes[0]["stroke"] == "#ff0000"

        curved = drawing.extract_drawing_primitives_rstrokes(
            drawing_pdf, kinds=["bezier"]
        )
        assert curved.matched == 1
        assert len(curved.strokes[0]["points"]) == 4

        boxed = drawing.extract_drawing_primitives_rstrokes(
            drawing_pdf, rect=[40, 40, 160, 110]
        )
        assert boxed.matched == 1
        assert boxed.strokes[0]["kind"] == "rect"

    def test_rotated_page_strokes_land_in_display_space(self, rotated_pdf):
        strokes = drawing.extract_drawing_primitives_rstrokes(rotated_pdf)

        assert strokes.rotation == 90
        assert strokes.matched > 0
        for stroke in strokes.strokes:
            x0, y0, x1, y1 = stroke["box"]
            assert 0 <= x0 <= x1 <= strokes.width_pt
            assert 0 <= y0 <= y1 <= strokes.height_pt


class TestCalibrateAndMeasure:
    def test_consistent_pairs_are_accepted(self):
        calibration = drawing.calibrate_drawing_scale_rcalibration(
            [
                {"a": [50, 50], "b": [150, 50], "dim_mm": 100},
                {"length_pt": 50, "dim_mm": 50},
                {"a": [50, 50], "b": [50, 100], "dim_mm": 50.05},
            ]
        )

        assert calibration.accepted
        assert calibration.pair_count == 3
        assert calibration.scale_mm_per_pt == pytest.approx(1.0, abs=1e-3)

    def test_insufficient_or_diverging_pairs_fail(self):
        two_pairs = drawing.calibrate_drawing_scale_rcalibration(
            [
                {"length_pt": 100, "dim_mm": 100},
                {"length_pt": 100, "dim_mm": 100},
            ]
        )
        assert not two_pairs.accepted

        diverging = drawing.calibrate_drawing_scale_rcalibration(
            [
                {"length_pt": 100, "dim_mm": 100},
                {"length_pt": 100, "dim_mm": 100},
                {"length_pt": 100, "dim_mm": 120},
            ]
        )
        assert not diverging.accepted
        assert diverging.max_relative_deviation > diverging.relative_tolerance

    def test_measure_converts_through_calibration(self):
        calibration = drawing.calibrate_drawing_scale_rcalibration(
            [{"length_pt": 100, "dim_mm": 300}]
        )
        result = drawing.measure_drawing_rmeasurements(
            [
                {"kind": "distance", "a": [0, 0], "b": [30, 40], "label": "diag"},
                {
                    "kind": "stroke_length",
                    "points": [[0, 0], [10, 0]],
                    "label": "stub",
                },
            ],
            calibration=calibration.to_dict(),
        )

        assert result.scale_mm_per_pt == pytest.approx(3.0)
        assert result.measurements[0]["length_pt"] == pytest.approx(50.0)
        assert result.measurements[0]["length_mm"] == pytest.approx(150.0)
        assert result.measurements[1]["length_mm"] == pytest.approx(30.0)

    def test_measure_without_calibration_leaves_mm_null(self):
        result = drawing.measure_drawing_rmeasurements(
            [{"kind": "distance", "a": [0, 0], "b": [3, 4], "label": "d"}]
        )

        assert result.measurements[0]["length_pt"] == pytest.approx(5.0)
        assert result.measurements[0]["length_mm"] is None

    def test_bezier_length_bounds(self):
        control = [[0, 0], [10, 0], [20, 0], [30, 0]]
        chord = drawing.measure_drawing_rmeasurements(
            [{"kind": "stroke_length", "points": [[0, 0], [30, 0]], "label": "chord"}]
        )
        sampled = drawing.measure_drawing_rmeasurements(
            [
                {
                    "kind": "stroke_length",
                    "points": control,
                    "stroke_kind": "bezier",
                    "label": "curve",
                }
            ]
        )

        assert sampled.measurements[0]["length_pt"] == pytest.approx(30.0, abs=0.5)
        assert (
            chord.measurements[0]["length_pt"]
            <= sampled.measurements[0]["length_pt"] + 1e-9
        )

    def test_real_fixture_end_to_end(self, drawing_pdf):
        """Measure the 100 pt fixture line through the full function chain."""
        strokes = drawing.extract_drawing_primitives_rstrokes(
            drawing_pdf, color="#ff0000", kinds=["line"]
        )
        calibration = drawing.calibrate_drawing_scale_rcalibration(
            [
                {"length_pt": 100, "dim_mm": 100},
                {"length_pt": 50, "dim_mm": 50},
                {"length_pt": 200, "dim_mm": 200},
            ]
        )
        red_line = strokes.strokes[0]
        result = drawing.measure_drawing_rmeasurements(
            [
                {
                    "kind": "stroke_length",
                    "points": red_line["points"],
                    "label": "fixture_red_line",
                }
            ],
            calibration=calibration.to_dict(),
        )

        assert calibration.accepted
        assert result.measurements[0]["length_pt"] == pytest.approx(100.0)
        assert result.measurements[0]["length_mm"] == pytest.approx(100.0, abs=0.5)


def _rotate_point(point, rotation, width, height):
    x, y = point
    return {
        0: (x, y),
        90: (height - y, x),
        180: (width - x, height - y),
        270: (y, width - x),
    }[rotation]


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("crop", [False, True])
@pytest.mark.parametrize("dpi", [72, 96, 150, 300])
def test_coordinate_regression_all_primitives_crop_pages_pixels(
    tmp_path, rotation, crop, dpi
):
    pdf = tmp_path / "coordinates.pdf"
    with pymupdf.open() as doc:
        doc.new_page(width=500, height=600).insert_text((30, 30), "first page")
        page = doc.new_page(width=400, height=300)
        if crop:
            page.set_cropbox(pymupdf.Rect(23, 31, 373, 271))
        width, height = page.rect.width, page.rect.height
        page.draw_line((40, 50), (140, 50), color=(0, 0, 0))
        page.draw_bezier((40, 90), (60, 65), (120, 115), (140, 90))
        page.draw_rect(pymupdf.Rect(170, 40, 220, 80))
        quad = pymupdf.Quad((170, 110), (225, 100), (175, 140), (230, 130))
        page.draw_quad(quad)
        page.insert_text((40, 190), "DIM 100", fontname="cour", fontsize=12)
        page.insert_text((270, 190), "VERTICAL", rotate=90, fontsize=10)
        page.set_rotation(rotation)
        doc.save(pdf)
    vectors = drawing.extract_drawing_primitives_rstrokes(pdf, page=1)
    text = drawing.extract_drawing_text_rwords(pdf, page=1)
    expected = {
        "line": [(40, 50), (140, 50)],
        "bezier": [(40, 90), (60, 65), (120, 115), (140, 90)],
        "rect": [(170, 40), (220, 40), (220, 80), (170, 80)],
        "quad": [(170, 110), (225, 100), (230, 130), (175, 140)],
    }
    for kind, points in expected.items():
        stroke = next(s for s in vectors.strokes if s["kind"] == kind)
        mapped = np.asarray([_rotate_point(p, rotation, width, height) for p in points])
        assert np.asarray(stroke["points"]) == pytest.approx(mapped, abs=2e-5)
        assert stroke["box"] == pytest.approx(
            [*mapped.min(axis=0), *mapped.max(axis=0)], abs=2e-5
        )
        # Includes degenerate boxes for horizontal/vertical lines; stable IDs
        # survive filtering. An unrelated region must exclude this primitive.
        box = stroke["box"]
        region = [box[0] - 1, box[1] - 1, box[2] + 1, box[3] + 1]
        selected = drawing.extract_drawing_primitives_rstrokes(
            pdf, page=1, rect=region, kinds=[kind]
        )
        assert selected.strokes[0]["id"] == stroke["id"]
        assert not drawing.extract_drawing_primitives_rstrokes(
            pdf, page=1, rect=[0, 0, 1, 1], kinds=[kind]
        ).strokes
    assert vectors.metadata["source_id"] == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert vectors.metadata == text.metadata
    assert text.metadata["crop_box"] == (
        [23, 31, 373, 271] if crop else [0, 0, 400, 300]
    )
    vertical = next(w for w in text.words if w["text"] == "VERTICAL")
    expected_direction = {0: [0, -1], 90: [1, 0], 180: [0, 1], 270: [-1, 0]}[rotation]
    assert vertical["direction"] == expected_direction
    assert vertical["raw_object"][4] == "VERTICAL"
    assert all(
        c["status"] == "combination_candidate"
        and c["association_status"] == "unresolved"
        for c in text.clusters
    )

    midpoint = _rotate_point((90, 50), rotation, width, height)
    region = [
        midpoint[0] - 10.13,
        midpoint[1] - 10.27,
        midpoint[0] + 10.43,
        midpoint[1] + 10.67,
    ]
    png = drawing.render_drawing_view_rpath(
        pdf, page=1, rect=region, dpi=dpi, out_dir=tmp_path
    )
    meta = json.loads(png.with_suffix(".json").read_text())
    transform, inverse = np.asarray(meta["page_to_pixel"]), np.asarray(
        meta["pixel_to_page"]
    )
    pixel = transform @ [*midpoint, 1]
    assert inverse @ pixel == pytest.approx([*midpoint, 1])
    pix = pymupdf.Pixmap(png)
    x, y = int(pixel[0]), int(pixel[1])
    assert (
        min(
            pix.pixel(i, j)[0] for i in range(x - 2, x + 3) for j in range(y - 2, y + 3)
        )
        < 150
    )
    assert meta["actual_origin_pt"] == pytest.approx(
        [meta["pixel_origin"][0] * 72 / dpi, meta["pixel_origin"][1] * 72 / dpi]
    )
    assert meta["requested_rect_display"] == region


def test_clipped_crop_and_missing_preflight_observations(drawing_pdf, tmp_path):
    report = drawing.inspect_drawing_coordinates_rreport(
        drawing_pdf, rect=[-7.4, -3.7, 201.2, 204.3], out_dir=tmp_path
    )
    assert report["status"] == "pending"
    meta = report["metadata"]
    assert meta["requested_rect_display"][0] < 0
    assert meta["effective_rect_display"][:2] == [0, 0]
    assert report["layers"] == {"text": "pending", "vector": "pending"}


def test_preflight_observation_checks_reject_wrong_and_stale_coordinates(
    drawing_pdf, tmp_path
):
    base = drawing.inspect_drawing_coordinates_rreport(
        drawing_pdf, dpi=72, out_dir=tmp_path
    )
    meta = base["metadata"]
    word = drawing.extract_drawing_text_rwords(drawing_pdf).words[0]
    observations = [
        {
            **{k: meta[k] for k in ("source_id", "page", "dpi", "rect_display")},
            "kind": kind,
            "object_id": obj,
            "point_index": 0,
            "pixel": pixel,
            "evidence": "fixture independently specified landmark",
        }
        for kind, obj, pixel in [
            ("text", word["id"], word["box"][:2]),
            ("vector", 0, [50, 50]),
        ]
    ]
    assert (
        drawing.inspect_drawing_coordinates_rreport(
            drawing_pdf, observations=observations, dpi=72, out_dir=tmp_path
        )["status"]
        == "verified"
    )
    observations[1]["pixel"] = [99, 99]
    assert (
        drawing.inspect_drawing_coordinates_rreport(
            drawing_pdf, observations=observations, dpi=72, out_dir=tmp_path
        )["status"]
        == "failed"
    )
    observations[1]["source_id"] = "stale"
    report = drawing.inspect_drawing_coordinates_rreport(
        drawing_pdf, observations=observations, dpi=72, out_dir=tmp_path
    )
    assert "source_id" in report["checks"][1]["errors"][0]


@pytest.mark.parametrize("page", [-1, 2])
def test_out_of_range_pages_are_explicit(drawing_pdf, tmp_path, page):
    for function in (
        drawing.extract_drawing_text_rwords,
        drawing.extract_drawing_primitives_rstrokes,
        drawing.render_drawing_view_rpath,
    ):
        with pytest.raises(ValueError, match="out of range"):
            function(drawing_pdf, page=page)


def test_anchor_rejects_mixed_source_coordinates(drawing_pdf, tmp_path):
    text = drawing.extract_drawing_text_rwords(drawing_pdf)
    for anchor in (text.words[0], text.clusters[0]):
        with pytest.raises(ValueError, match="source_id"):
            drawing.render_drawing_view_rpath(
                drawing_pdf,
                anchor={**anchor, "source_id": "other-file"},
                out_dir=tmp_path,
            )


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_text_boxes_match_independently_rendered_glyph_pixels(tmp_path, rotation):
    pdf = tmp_path / "text.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=240, height=180)
        page.insert_text((30, 70), "CAD", fontname="cour", fontsize=16)
        page.insert_text((130, 100), "壁厚", fontname="china-s", fontsize=16)
        page.set_rotation(rotation)
        doc.save(pdf)
    text = drawing.extract_drawing_text_rwords(pdf)
    png = drawing.render_drawing_view_rpath(pdf, dpi=150, out_dir=tmp_path)
    meta = json.loads(png.with_suffix(".json").read_text())
    pixmap = pymupdf.Pixmap(png)
    pixels = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )
    ink = np.min(pixels[:, :, :3], axis=2) < 128
    covered = np.zeros_like(ink)
    for word in text.words:
        corners = (
            np.array([word["box"][:2] + [1], word["box"][2:] + [1]])
            @ np.asarray(meta["page_to_pixel"]).T
        )
        x0, y0 = np.floor(corners[0, :2] - 1).astype(int)
        x1, y1 = np.ceil(corners[1, :2] + 1).astype(int)
        assert ink[y0:y1, x0:x1].any()
        covered[y0:y1, x0:x1] = True
    assert not (ink & ~covered).any()


def test_diagnostic_boundary_includes_direct_submodule_import(drawing_pdf):
    from simplecadapi import GraphSession
    from simplecadapi.inspect.drawing.text import extract_drawing_text_rwords

    with GraphSession(graph_id="diagnostic-boundary"):
        with pytest.raises(RuntimeError, match="GraphSession"):
            extract_drawing_text_rwords(drawing_pdf)
