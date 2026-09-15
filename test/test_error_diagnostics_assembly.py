"""Assembly solve-failure diagnosis (P1 family 7).

The solver's strict-mode raise sites previously discarded the residual and
connectivity data already in hand.  These tests pin the structured channel:
residual failures carry measured translation/angular errors with a
worst-first repair; structural failures carry the connectivity verdict
(grounded / reachable / unsolved) as inventory.
"""

from __future__ import annotations

import pytest

import simplecadapi as scad
from simplecadapi.errors import SimpleCADError


def _part_with_origin(part_id: str) -> scad.Part:
    body = scad.make_box_rsolid(20.0, 10.0, 2.0)
    part = scad.make_part_rpart(part_id=part_id, body=body)
    origin = scad.make_placement_connector_rconnector(
        connector_id="origin",
        placement=scad.make_placement_rplacement(origin=(0.0, 0.0, 0.0)),
    )
    return scad.add_connector_rpart(part=part, connector=origin)


def _part_with_shifted_mark(part_id: str, shift: float) -> scad.Part:
    body = scad.make_box_rsolid(4.0, 4.0, 4.0)
    part = scad.make_part_rpart(part_id=part_id, body=body)
    mark = scad.make_placement_connector_rconnector(
        connector_id="mark",
        placement=scad.make_placement_rplacement(origin=(shift, 0.0, 0.0)),
    )
    return scad.add_connector_rpart(part=part, connector=mark)


def test_residual_failure_measures_translation_error():
    # base.origin == moving.mark AND base.far == moving.mark cannot both
    # hold: the second fixed constraint lands 15 mm off after the first
    # solves — the structured error must carry that number.
    base = _part_with_origin("base_part")
    base = scad.add_connector_rpart(
        part=base,
        connector=scad.make_placement_connector_rconnector(
            connector_id="far",
            placement=scad.make_placement_rplacement(origin=(15.0, 0.0, 0.0)),
        ),
    )
    moving = _part_with_shifted_mark("moving_part", shift=5.0)
    assembly = scad.make_assembly_rassembly(assembly_id="residual_fixture")
    assembly = scad.add_component_rassembly(
        assembly=assembly, item=base, component_id="base",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly=assembly, item=moving, component_id="moving",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.ground_component_rassembly(
        assembly=assembly, component_id="base")
    assembly = scad.add_fixed_constraint_rassembly(
        assembly=assembly, constraint_id="hold",
        connector_a=scad.make_connector_ref_rconnectorref("base", "origin"),
        connector_b=scad.make_connector_ref_rconnectorref("moving", "mark"),
    )
    assembly = scad.add_fixed_constraint_rassembly(
        assembly=assembly, constraint_id="hold2",
        connector_a=scad.make_connector_ref_rconnectorref("base", "far"),
        connector_b=scad.make_connector_ref_rconnectorref("moving", "mark"),
    )

    with pytest.raises(SimpleCADError) as ctx:
        scad.solve_assembly_constraints_rassembly(assembly=assembly)
    payload = ctx.value.to_dict()
    measurements = {m["name"]: m["value"] for m in payload["measurements"]}
    assert measurements["hold2 translation error"] == pytest.approx(15.0)
    assert measurements["placement tolerance"] == pytest.approx(1e-7)
    inventory = {(entry.symbol, entry.status) for entry in ctx.value.guidance.inventory}
    assert ("hold2", "exceeded") in inventory
    # The repair targets the connector frames, not the placements — moving
    # a component cannot fix an inconsistent constraint pair.
    assert any("connector" in line for line in ctx.value.guidance.repair)
    assert any("hold2" in line for line in ctx.value.guidance.repair)
    # Text axiom: the measured error appears in the error text itself.
    assert "hold2 translation error: 15" in str(ctx.value)


def test_structural_failure_lists_connectivity_verdict():
    # 'island' has no constraint path from the grounded component: the
    # inventory is the connectivity verdict, not a bare component list.
    part = _part_with_origin("p")
    assembly = scad.make_assembly_rassembly(assembly_id="structural_fixture")
    assembly = scad.add_component_rassembly(
        assembly=assembly, item=part, component_id="base",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly=assembly, item=part, component_id="floating",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly=assembly, item=part, component_id="island",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.ground_component_rassembly(
        assembly=assembly, component_id="base")
    assembly = scad.add_revolute_constraint_rassembly(
        assembly=assembly, constraint_id="link",
        connector_a=scad.make_connector_ref_rconnectorref("base", "origin"),
        connector_b=scad.make_connector_ref_rconnectorref("floating", "origin"),
    )

    with pytest.raises(SimpleCADError) as ctx:
        scad.solve_assembly_constraints_rassembly(assembly=assembly)
    guidance = ctx.value.guidance
    assert "island" in guidance.what_happened
    statuses = {entry.symbol: entry.status for entry in guidance.inventory}
    assert statuses["base"] == "grounded"
    assert statuses["floating"] == "reachable"
    assert statuses["island"] == "unsolved"
    assert any("ground" in line for line in guidance.repair)


def test_solve_error_passes_through_public_wrapper():
    # The public wrapper must surface the solver's structured payload
    # unchanged (raise_harness_error SimpleCADError passthrough) — the
    # operation stays the solver's, not the generic wrapper's.
    part = _part_with_origin("p")
    assembly = scad.make_assembly_rassembly(assembly_id="passthrough_fixture")
    assembly = scad.add_component_rassembly(
        assembly=assembly, item=part, component_id="base",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly=assembly, item=part, component_id="floating",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly=assembly, item=part, component_id="island",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.ground_component_rassembly(
        assembly=assembly, component_id="base")
    # The constraint gives the solver work to do; the island stays
    # disconnected from it, which is the failure being surfaced.
    assembly = scad.add_revolute_constraint_rassembly(
        assembly=assembly, constraint_id="link",
        connector_a=scad.make_connector_ref_rconnectorref("base", "origin"),
        connector_b=scad.make_connector_ref_rconnectorref("floating", "origin"),
    )
    with pytest.raises(SimpleCADError) as ctx:
        scad.solve_assembly_constraints_rassembly(assembly=assembly)
    assert ctx.value.operation == "solve_assembly_constraints"
