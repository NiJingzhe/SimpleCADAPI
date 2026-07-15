from __future__ import annotations

import importlib
import math
from dataclasses import fields, replace

import pytest


parameters_module = importlib.import_module("examples.21_weaving_machine.parameters")
inventory_module = importlib.import_module("examples.21_weaving_machine.inventory")


def test_default_parameters_preserve_derived_relations_and_concept_gate():
    parameters = parameters_module.default_machine_parameters()

    parameters_module.validate_concept_parameters(parameters)

    assert math.isclose(parameters.takeup_step, 12.0)
    assert parameters.guide_center_span == 288.0
    assert parameters.edge_allowance_total == 12.0
    assert parameters.guide_centers_y[0] == -144.0
    assert parameters.guide_centers_y[-1] == 144.0
    assert parameters.filling_planes_z == (24.0, 0.0, -24.0)
    assert parameters.minimum_rapier_travel == 500.0


@pytest.mark.parametrize(
    ("field_name", "bad_value", "message"),
    (
        ("guide_pitch", 0.0, "guide_pitch"),
        ("guide_positions", 1, "guide_positions"),
        ("bias_angle_degrees", 90.0, "bias_angle_degrees"),
        ("dynamic_clearance", 4.99, "at least 5 mm"),
        ("fill_half_height", 10.0, "shed-height"),
        ("x_needle", -400.0, "X stations"),
        ("effective_width", 280.0, "guide center span"),
    ),
)
def test_concept_gate_rejects_invalid_boundaries(field_name, bad_value, message):
    parameters = parameters_module.default_machine_parameters()
    bad_design_value = replace(getattr(parameters, field_name), value=bad_value)
    parameters = replace(parameters, **{field_name: bad_design_value})

    with pytest.raises(parameters_module.ParameterValidationError, match=message):
        parameters_module.validate_concept_parameters(parameters)


def test_non_finite_design_values_and_unproven_validation_are_rejected():
    with pytest.raises(TypeError, match="int or float"):
        parameters_module.DesignValue(
            value=True,
            unit="count",
            evidence=parameters_module.EvidenceLevel.PDF_EXPLICIT,
            status=parameters_module.ValidationStatus.PROPOSAL,
            source="test",
        )
    with pytest.raises(ValueError, match="finite"):
        parameters_module.DesignValue(
            value=float("nan"),
            unit="mm",
            evidence=parameters_module.EvidenceLevel.ENGINEERING_COMPLETION,
            status=parameters_module.ValidationStatus.PROPOSAL,
            source="test",
        )
    with pytest.raises(ValueError, match="must not be empty"):
        parameters_module.DesignValue(
            value=1.0,
            unit="",
            evidence=parameters_module.EvidenceLevel.ENGINEERING_COMPLETION,
            status=parameters_module.ValidationStatus.PROPOSAL,
            source="test",
        )
    with pytest.raises(ValueError, match="external_evidence_id"):
        parameters_module.DesignValue(
            value=1.0,
            unit="mm",
            evidence=parameters_module.EvidenceLevel.ENGINEERING_COMPLETION,
            status=parameters_module.ValidationStatus.VALIDATED,
            source="test",
        )


def test_manufacturing_and_full_detail_fail_closed():
    parameters = parameters_module.default_machine_parameters()

    with pytest.raises(
        parameters_module.ParameterValidationError, match="not validated"
    ):
        parameters_module.validate_manufacturing_release(parameters)
    with pytest.raises(
        parameters_module.ParameterValidationError, match="closed_with_evidence"
    ):
        parameters_module.validate_detail_level(
            detail=parameters_module.DetailLevel.FULL,
            topology_closed=False,
            inventory_complete=False,
        )
    with pytest.raises(
        parameters_module.ParameterValidationError, match="resolved authoritative"
    ):
        parameters_module.validate_detail_level(
            detail=parameters_module.DetailLevel.FULL,
            topology_closed=True,
            inventory_complete=False,
        )
    parameters_module.validate_detail_level(
        detail=parameters_module.DetailLevel.FULL,
        topology_closed=True,
        inventory_complete=True,
    )


def test_manufacturing_gate_accepts_a_fully_evidenced_parameter_set():
    parameters = parameters_module.default_machine_parameters()
    validated = {
        item.name: replace(
            getattr(parameters, item.name),
            status=parameters_module.ValidationStatus.VALIDATED,
            external_evidence_id=f"test:{item.name}",
        )
        for item in fields(parameters)
    }

    parameters_module.validate_manufacturing_release(replace(parameters, **validated))


def test_concept_gate_collects_clearance_and_source_architecture_errors():
    parameters = parameters_module.default_machine_parameters()
    parameters = replace(
        parameters,
        yarn_height_allowance=replace(parameters.yarn_height_allowance, value=-1.0),
        bias_layers=replace(parameters.bias_layers, value=2),
        filling_channels=replace(parameters.filling_channels, value=2),
        fillings_per_cycle=replace(parameters.fillings_per_cycle, value=1),
    )

    with pytest.raises(parameters_module.ParameterValidationError) as error:
        parameters_module.validate_concept_parameters(parameters)

    assert any("must not be negative" in item for item in error.value.issues)
    assert any("four bias layers" in item for item in error.value.issues)
    assert any("three filling channels" in item for item in error.value.issues)
    assert any("two fillings" in item for item in error.value.issues)


def test_authoritative_inventory_keeps_unknown_counts_unresolved():
    inventory = inventory_module.default_inventory()

    assert not inventory.complete
    assert "G-BLOCK" in inventory.unresolved_ids
    assert len(inventory_module.TOP_LEVEL_COMPONENT_IDS) == 14
    with pytest.raises(ValueError, match="unresolved inventory"):
        inventory.require_complete()


def test_inventory_validation_and_complete_path():
    status = inventory_module.QuantityStatus
    with pytest.raises(ValueError, match="must not be empty"):
        inventory_module.InventoryItem("", "item", 1, status.RESOLVED, "test")
    with pytest.raises(ValueError, match="positive quantity"):
        inventory_module.InventoryItem("item", "item", 0, status.RESOLVED, "test")
    with pytest.raises(ValueError, match="must be None"):
        inventory_module.InventoryItem("item", "item", 1, status.UNRESOLVED, "test")

    item = inventory_module.InventoryItem("item", "item", 1, status.RESOLVED, "test")
    inventory = inventory_module.Inventory((item,))
    assert inventory.complete
    inventory.require_complete()
    with pytest.raises(ValueError, match="unique"):
        inventory_module.Inventory((item, item))
