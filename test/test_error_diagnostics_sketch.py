"""Sketch-solve failure diagnosis (P0 family 4).

The solver backend already names failing constraints; the structured channel
must surface them as measurements / inventory / parameterized repair, plus a
2D schematic evidence render following the diag_png pattern.  Every test
asserts against the error *text* (text axiom); the render test additionally
verifies pixels so a broken highlight channel cannot hide behind a written
file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import simplecadapi as scad
from simplecadapi.errors import SimpleCADError


@pytest.fixture(autouse=True)
def _no_render(monkeypatch):
    monkeypatch.setenv("SCA_NO_DIAGNOSTIC_RENDER", "1")


def _conflicting_sketch() -> scad.Sketch:
    """Two incompatible distances on the same point pair (5 vs 20)."""

    sketch = scad.make_sketch_rsketch("conflict fixture")
    sketch = scad.add_point_rsketch(sketch, "p1", 0.0, 0.0)
    sketch = scad.add_point_rsketch(sketch, "p2", 10.0, 0.0)
    sketch = scad.add_line_rsketch(sketch, "l1", "p1", "p2")
    sketch = scad.constrain_distance_rsketch(
        sketch, "p1", "p2", 20.0, constraint_id="c_far")
    sketch = scad.constrain_distance_rsketch(
        sketch, "p1", "p2", 5.0, constraint_id="c_near")
    return sketch


def _loose_sketch() -> scad.Sketch:
    """A solvable sketch with unconstrained entities (4 DOF)."""

    sketch = scad.make_sketch_rsketch("loose fixture")
    sketch = scad.add_point_rsketch(sketch, "a", 0.0, 0.0)
    sketch = scad.add_point_rsketch(sketch, "b", 8.0, 0.0)
    sketch = scad.add_line_rsketch(sketch, "seg", "a", "b")
    return sketch


def test_conflicting_constraints_raise_structured_diagnosis():
    with pytest.raises(SimpleCADError) as ctx:
        scad.inspect_sketch_rsketchresult(_conflicting_sketch())
    guidance = ctx.value.guidance
    # The solver names the failing constraint; our related-set logic names
    # its direct conflict partner (shares the same target entities).
    inventory = {(entry.symbol, entry.status) for entry in guidance.inventory}
    assert ("c_near", "failed") in inventory
    assert ("c_far", "near miss") in inventory
    measurements = {m.name: m.value for m in guidance.measurements}
    assert measurements["conflicting constraints"] == 1
    assert measurements["constraint c_near value"] == 5.0


def test_conflict_repair_names_the_conflicting_pair():
    with pytest.raises(SimpleCADError) as ctx:
        scad.inspect_sketch_rsketchresult(_conflicting_sketch())
    text = str(ctx.value)
    # Text axiom: the conflicting pair, their kinds, values, and the shared
    # entities all appear as text, not only in the render.
    assert "c_near" in text and "c_far" in text
    assert "distance(p1, p2 = 5)" in text
    assert "p1" in text and "p2" in text
    assert any("删除或放宽 c_near" in line for line in ctx.value.guidance.repair)


def test_solve_error_still_a_value_error_for_legacy_callers():
    # SimpleCADError subclasses ValueError: existing except clauses in
    # downstream scripts keep working after the structured upgrade.
    with pytest.raises(ValueError):
        _conflicting_sketch().solve()


def test_inspect_passes_structured_error_through_unchanged():
    # The public wrapper must re-raise the sketch diagnosis as-is instead
    # of burying it in a generic "failed to inspect" message.
    with pytest.raises(SimpleCADError) as ctx:
        scad.inspect_sketch_rsketchresult(_conflicting_sketch())
    assert ctx.value.operation == "sketch_solve"
    assert ctx.value.guidance.measurements


def test_wire_promotion_surfaces_solve_diagnosis():
    # Promotion paths (wire/face/extrude) solve internally; the diagnosis
    # must reach the caller with its payload intact.
    with pytest.raises(SimpleCADError) as ctx:
        scad.make_wire_from_sketch_rwire(_conflicting_sketch())
    assert ctx.value.operation == "sketch_solve"
    inventory = {entry.symbol for entry in ctx.value.guidance.inventory}
    assert "c_near" in inventory


def test_underconstrained_reports_dof_and_free_entities():
    with pytest.raises(SimpleCADError) as ctx:
        scad.inspect_sketch_rsketchresult(
            _loose_sketch(), require_fully_constrained=True)
    guidance = ctx.value.guidance
    measurements = {m.name: m.value for m in guidance.measurements}
    assert measurements["remaining DOF"] == 4
    inventory = {(entry.symbol, entry.status) for entry in guidance.inventory}
    assert ("a", "unconstrained") in inventory
    assert ("b", "unconstrained") in inventory
    assert ("seg", "unconstrained") in inventory
    # The repair lists the free entities concretely, with the API to use.
    assert any("constrain_fix_rsketch" in line for line in guidance.repair)


def test_conflict_evidence_render_highlights_implicated_entities(tmp_path, monkeypatch):
    monkeypatch.delenv("SCA_NO_DIAGNOSTIC_RENDER", raising=False)
    with pytest.raises(SimpleCADError) as ctx:
        scad.inspect_sketch_rsketchresult(_conflicting_sketch())
    evidence = ctx.value.guidance.evidence
    assert evidence, "evidence render expected with diagnostics enabled"
    assert evidence[0].kind == "sketch_render"
    assert Path(evidence[0].path).exists()
    # The implicated entities (p1, p2) and only they carry the symbol table.
    assert set(sym for sym, _ in evidence[0].symbols) == {"p1", "p2"}
    # Pixel verification: orange ink must actually be on the canvas.
    from PIL import Image

    with Image.open(evidence[0].path) as image:
        pixels = image.convert("RGB")
        counts = pixels.getcolors(maxcolors=1 << 24) or []
    orange = sum(
        count for count, rgb in counts
        if abs(rgb[0] - 243) < 40 and abs(rgb[1] - 156) < 40 and abs(rgb[2] - 18) < 40
    )
    assert orange > 50, f"expected visible orange ink, found {orange} px"


def test_render_disabled_by_default_in_suite(monkeypatch):
    # The suite-wide opt-out must keep text-only errors (no half-written
    # files, no render cost) — the text is complete on its own.
    monkeypatch.setenv("SCA_NO_DIAGNOSTIC_RENDER", "1")
    with pytest.raises(SimpleCADError) as ctx:
        scad.inspect_sketch_rsketchresult(_conflicting_sketch())
    assert ctx.value.guidance.evidence == ()
