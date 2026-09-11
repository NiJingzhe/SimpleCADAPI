"""Fillet/chamfer degeneration taxonomy and QL selection-trust diagnosis.

One case per failure family from the accumulated degeneration catalog
(repo history + OCC ecosystem): size vs face room, tangent adjacency,
tangency-critical interaction, bore curvature, and the QL cardinality
inventory with logical-surface grouping.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import simplecadapi as scad
from simplecadapi.operators._diagnostics import _RENDER_DEDUP


@pytest.fixture(autouse=True)
def _no_render(monkeypatch):
    monkeypatch.setenv("SCA_NO_DIAGNOSTIC_RENDER", "1")


def _box() -> scad.Solid:
    return scad.make_box_rsolid(10, 10, 10)


def _box_edges(solid):
    return scad.ql.edges().resolve(solid)


def _payload(error) -> dict:
    return error.to_dict()


def test_chamfer_distance_exceeds_face_room():
    box = _box()
    edges = _box_edges(box)
    with pytest.raises(scad.SimpleCADError) as ctx:
        scad.chamfer_rsolid(box, [edges[0]], 12)

    payload = _payload(ctx.value)
    assert "distance 12 mm meets or exceeds the 10 mm" in payload["what_happened"]
    measurements = {m["name"]: m["value"] for m in payload["measurements"]}
    assert measurements["available_face_room"] == pytest.approx(10.0)
    assert any("below 10 mm" in step for step in payload["repair"])


def test_fillet_radius_exceeds_face_room():
    box = _box()
    edges = _box_edges(box)
    with pytest.raises(scad.SimpleCADError) as ctx:
        scad.fillet_rsolid(box, [edges[0]], 12)

    payload = _payload(ctx.value)
    assert "radius 12 mm meets or exceeds the 10 mm" in payload["what_happened"]
    measurements = {m["name"]: m["value"] for m in payload["measurements"]}
    assert measurements["radius"] == pytest.approx(12.0)


def _slot_solid() -> scad.Solid:
    arc_left = scad.make_three_point_arc_redge((0, 5, 0), (-5, 0, 0), (0, -5, 0))
    line_bottom = scad.make_segment_redge((0, -5, 0), (20, -5, 0))
    arc_right = scad.make_three_point_arc_redge((20, -5, 0), (25, 0, 0), (20, 5, 0))
    line_top = scad.make_segment_redge((20, 5, 0), (0, 5, 0))
    wire = scad.make_wire_from_edges_rwire([arc_left, line_bottom, arc_right, line_top])
    return scad.extrude_rsolid(scad.make_face_from_wire_rface(wire), (0, 0, 1), 8)


def test_fillet_tangent_adjacent_faces_degenerates():
    solid = _slot_solid()
    junction = None
    for edge in scad.ql.edges().resolve(solid):
        p1 = edge.get_start_vertex().get_coordinates()
        p2 = edge.get_end_vertex().get_coordinates()
        mid = tuple((a + b) / 2 for a, b in zip(p1, p2))
        if abs(mid[0]) < 1e-6 and abs(mid[1] - 5) < 1e-6:
            junction = edge
            break
    assert junction is not None

    with pytest.raises(scad.SimpleCADError) as ctx:
        scad.fillet_rsolid(solid, [junction], 1.0)

    payload = _payload(ctx.value)
    assert "already tangent" in payload["what_happened"]
    measurements = {m["name"]: m["value"] for m in payload["measurements"]}
    assert measurements["dihedral_angle"] == pytest.approx(180.0, abs=0.5)
    assert any("no corner to blend" in step for step in payload["repair"])


def test_fillet_tangency_critical_all_edges():
    box = _box()
    edges = _box_edges(box)
    with pytest.raises(scad.SimpleCADError) as ctx:
        scad.fillet_rsolid(box, edges, 5)

    payload = _payload(ctx.value)
    assert "meet tangentially" in payload["what_happened"]
    measurements = {m["name"]: m["value"] for m in payload["measurements"]}
    assert measurements["combined_blend_width"] == pytest.approx(10.0)
    assert measurements["available_face_room"] == pytest.approx(10.0)
    assert any("below 5 mm" in step for step in payload["repair"])


def test_fillet_bore_mouth_boundary_room():
    # Tube: outer r=10 with a bore r=4 leaves a 6 mm annulus. Empirically
    # OCC accepts r=5 but fails at r=6 == annulus width: the boundary case
    # degenerates the top-face strip, and the room probe must say so.
    outer = scad.make_cylinder_rsolid(10, 10)
    bore = scad.make_cylinder_rsolid(4, 20, bottom_face_center=(0, 0, -5))
    tube = scad.cut_rsolid(outer, bore)
    mouth_edges = [
        edge
        for edge in scad.ql.edges().resolve(tube)
        if abs(edge.get_start_vertex().get_coordinates()[2]
               - edge.get_end_vertex().get_coordinates()[2]) < 1e-6
        and edge.get_start_vertex().get_coordinates()[2] > 9.0
    ]
    assert mouth_edges

    with pytest.raises(scad.SimpleCADError) as ctx:
        scad.fillet_rsolid(tube, mouth_edges, 6)

    payload = _payload(ctx.value)
    assert "meets or exceeds" in payload["what_happened"]
    measurements = {m["name"]: m["value"] for m in payload["measurements"]}
    assert measurements["available_face_room"] == pytest.approx(6.0)
    assert any("below 6 mm" in step for step in payload["repair"])


def _split_band_solid() -> scad.Solid:
    cylinder = scad.make_cylinder_rsolid(10, 20)
    ring = scad.make_cylinder_rsolid(12, 6, bottom_face_center=(0, 0, 7))
    inner = scad.make_cylinder_rsolid(9, 10, bottom_face_center=(0, 0, 5))
    return scad.cut_rsolid(cylinder, scad.cut_rsolid(ring, inner))


def test_ql_ambiguity_reports_split_surface_group():
    part = _split_band_solid()
    with pytest.raises(scad.SimpleCADError) as ctx:
        scad.ql.faces().where(scad.ql.surface_type("CYLINDER")).exactly(1).resolve(part)

    payload = _payload(ctx.value)
    assert "expected exactly 1 face(s), got 3" in payload["what_happened"]
    assert "logical surface group" in payload["what_happened"]
    # The two r=10 bands are named as one logical group in the repair.
    assert any(
        "lie on one logical surface" in step and "F1+F6" in step
        for step in payload["repair"]
    )
    inventory = payload["inventory"]
    hits = [entry for entry in inventory if entry["status"] == "hit"]
    assert len(hits) == 3
    # Split pieces of one surface are distinguishable by their axial span.
    spans = [entry["description"] for entry in hits if "r=10" in entry["description"]]
    assert len(spans) == 2
    assert spans[0] != spans[1]
    assert any("z=[" in text for text in spans)
    # Near-misses describe what else exists (the planes).
    assert any("plane" in entry["description"] for entry in inventory)


def test_ql_zero_hit_lists_near_miss_inventory():
    part = _split_band_solid()
    with pytest.raises(scad.SimpleCADError) as ctx:
        scad.ql.faces().where(scad.ql.surface_type("SPHERE")).at_least(1).resolve(part)

    payload = _payload(ctx.value)
    assert "expected at least 1 face(s), got 0" in payload["what_happened"]
    inventory = payload["inventory"]
    assert all(entry["status"] == "near_miss" for entry in inventory)
    assert any("cylinder r=10" in entry["description"] for entry in inventory)
    assert any("align predicate values" in step for step in payload["repair"])


def test_ql_evidence_render_writes_image(tmp_path, monkeypatch):
    monkeypatch.delenv("SCA_NO_DIAGNOSTIC_RENDER", raising=False)
    monkeypatch.chdir(tmp_path)
    _RENDER_DEDUP.clear()
    part = _split_band_solid()
    with pytest.raises(scad.SimpleCADError) as ctx:
        scad.ql.faces().where(scad.ql.surface_type("CYLINDER")).exactly(1).resolve(part)
    evidence = ctx.value.to_dict()["evidence"]
    assert len(evidence) == 1
    assert Path(evidence[0]["path"]).exists()
    assert Path(evidence[0]["path"]).stat().st_size > 10_000
    assert evidence[0]["path"] in str(ctx.value)
