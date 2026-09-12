"""Sweep/loft family failure diagnosis (P1 family 5).

Open-wire profiles get a measured gap (endpoints + distance + chain count)
instead of a bare closedness complaint; kernel loft failures get a section
compatibility verdict (coincident stations, edge counts, closure, ordering)
instead of the kernel's wordless "build did not complete".  Wire evidence
renders as a 2D plan schematic — the 3D pipeline cannot mesh bare wires.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import simplecadapi as scad
from simplecadapi.errors import SimpleCADError


@pytest.fixture(autouse=True)
def _no_render(monkeypatch):
    monkeypatch.setenv("SCA_NO_DIAGNOSTIC_RENDER", "1")


def _open_u_wire(gap: float = 0.8) -> scad.Wire:
    """A U-shaped wire whose two uprights stop ``gap`` short of closing."""

    return scad.make_wire_from_edges_rwire([
        scad.make_line_redge((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)),
        scad.make_line_redge((10.0, 0.0, 0.0), (10.0, 6.0, 0.0)),
        scad.make_line_redge((10.0, 6.0, 0.0), (0.0, 6.0, 0.0)),
        scad.make_line_redge((0.0, 6.0, 0.0), (0.0, gap, 0.0)),
    ])


def test_extrude_reports_measured_gap():
    with pytest.raises(SimpleCADError) as ctx:
        scad.extrude_rsolid(_open_u_wire(), (0.0, 0.0, 1.0), 2.0)
    measurements = {m.name: m.value for m in ctx.value.guidance.measurements}
    assert measurements["gap"] == pytest.approx(0.8)
    assert measurements["gap end P1"] == (0.0, 0.0, 0.0)
    assert measurements["gap end P2"] == (0.0, 0.8, 0.0)
    assert measurements["edge count"] == 4
    # Text axiom: the gap coordinates appear in the error text itself.
    assert "0.8" in str(ctx.value)
    assert any("add a segment" in line.lower() for line in ctx.value.guidance.repair)
    # SDK error-language contract: error text stays English.
    import re

    assert not re.search(r"[\u3400-\u9fff\uf900-\ufaff]", str(ctx.value))


def test_make_face_reports_measured_gap():
    with pytest.raises(SimpleCADError) as ctx:
        scad.make_face_from_wire_rface(_open_u_wire(gap=1.5))
    measurements = {m.name: m.value for m in ctx.value.guidance.measurements}
    assert measurements["gap"] == pytest.approx(1.5)
    assert ctx.value.operation == "make_face_from_wire_rface"


def test_split_wire_reports_chain_count():
    # A split wire cannot be constructed through make_wire_from_edges_rwire
    # (it rejects disconnected edges upstream), so the chain-count channel
    # is defense-in-depth for wires built by other routes.  What IS
    # contract: the upstream rejection names the assembly failure.
    box_a = [
        scad.make_line_redge((0.0, 0.0, 0.0), (4.0, 0.0, 0.0)),
        scad.make_line_redge((4.0, 0.0, 0.0), (4.0, 4.0, 0.0)),
        scad.make_line_redge((4.0, 4.0, 0.0), (0.0, 4.0, 0.0)),
        scad.make_line_redge((0.0, 4.0, 0.0), (0.0, 0.0, 0.0)),
    ]
    box_b = [
        scad.make_line_redge((10.0, 0.0, 0.0), (14.0, 0.0, 0.0)),
        scad.make_line_redge((14.0, 0.0, 0.0), (14.0, 4.0, 0.0)),
        scad.make_line_redge((14.0, 4.0, 0.0), (10.0, 4.0, 0.0)),
    ]
    with pytest.raises(SimpleCADError) as ctx:
        scad.make_wire_from_edges_rwire(box_a + box_b)
    assert "assemble" in ctx.value.guidance.what_happened


def test_loft_coincident_sections_named():
    rect = scad.make_rectangle_rwire(4.0, 4.0)
    with pytest.raises(SimpleCADError) as ctx:
        scad.loft_rsolid([rect, scad.make_rectangle_rwire(4.0, 4.0)])
    payload = ctx.value.to_dict()
    assert "S2" in payload["what_happened"] and "S1" in payload["what_happened"]
    inventory = {entry.symbol: entry.status for entry in ctx.value.guidance.inventory}
    assert inventory["S1"] == "implicated"
    assert inventory["S2"] == "implicated"
    assert any("same location" in line for line in ctx.value.guidance.repair)


def test_loft_open_section_named():
    # Closed rect -> open U wire: the open station must be named.
    rect = scad.make_rectangle_rwire(4.0, 4.0)
    with pytest.raises(SimpleCADError) as ctx:
        scad.loft_rsolid([rect, _open_u_wire()])
    inventory = {entry.symbol: entry.status for entry in ctx.value.guidance.inventory}
    assert inventory["S2"] == "implicated"
    assert any("open wire" in line for line in ctx.value.guidance.repair)


def test_open_wire_evidence_renders_plan(tmp_path, monkeypatch):
    monkeypatch.delenv("SCA_NO_DIAGNOSTIC_RENDER", raising=False)
    with pytest.raises(SimpleCADError) as ctx:
        scad.extrude_rsolid(_open_u_wire(), (0.0, 0.0, 1.0), 2.0)
    evidence = ctx.value.guidance.evidence
    assert evidence
    assert evidence[0].kind == "wire_plan_render"
    assert Path(evidence[0].path).exists()
    # Pixel verification: orange highlight ink must be on the canvas.
    from PIL import Image

    with Image.open(evidence[0].path) as image:
        pixels = image.convert("RGB")
        counts = pixels.getcolors(maxcolors=1 << 24) or []
    orange = sum(
        count for count, rgb in counts
        if abs(rgb[0] - 243) < 40 and abs(rgb[1] - 156) < 40 and abs(rgb[2] - 18) < 40
    )
    assert orange > 100, f"expected visible orange ink, found {orange} px"
