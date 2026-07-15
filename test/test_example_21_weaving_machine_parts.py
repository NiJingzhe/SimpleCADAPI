from __future__ import annotations

import importlib

import pytest

import simplecadapi as scad


common_module = importlib.import_module("examples.21_weaving_machine.common")
fixture_module = importlib.import_module("examples.21_weaving_machine.guide_fixture")
main_module = importlib.import_module("examples.21_weaving_machine.main")
materials_module = importlib.import_module("examples.21_weaving_machine.materials")
parameters_module = importlib.import_module("examples.21_weaving_machine.parameters")


def test_d1_fixture_has_functional_parts_y_axis_contract_and_zero_residual():
    parameters = parameters_module.default_machine_parameters()
    with scad.GraphSession(graph_id="test_d1_fixture"):
        build = fixture_module.make_guide_fixture_assembly(
            parameters=parameters,
            materials=materials_module.make_guide_materials(),
            position=6.0,
        )

    report = scad.inspect_assembly_constraints_rconstraintreport(
        assembly=build.assembly
    )
    cartridge = build.assembly.get_component("guide_cartridge")
    rail = build.assembly.get_component("wear_rail").item
    body = cartridge.item.get_component("block_body").item
    eye = cartridge.item.get_component("ceramic_eye").item

    assert report.solved
    assert all(item.within_tolerance for item in report.residuals)
    assert cartridge.placement.origin == (0.0, 6.0, 2.0)
    assert build.joint_contract.axis == (0.0, 1.0, 0.0)
    assert build.joint_audit.passed
    assert "role.bias_guide_block" in scad.list_tags(shape=body.body)
    assert "role.yarn_contact" in scad.list_tags(shape=eye.body)
    assert "role.replaceable_wear_rail" in scad.list_tags(shape=rail.body)
    assert body.body.get_volume() > 0.0
    assert eye.body.get_volume() > 0.0
    assert rail.body.get_volume() > 0.0


def test_fixture_rejects_out_of_range_drive_or_clamps_by_request():
    parameters = parameters_module.default_machine_parameters()
    with pytest.raises(ValueError, match="outside"):
        with scad.GraphSession(graph_id="test_d1_out_of_range"):
            fixture_module.make_guide_fixture_assembly(
                parameters=parameters,
                materials=materials_module.make_guide_materials(),
                position=20.0,
            )

    with scad.GraphSession(graph_id="test_d1_clamped"):
        clamped = fixture_module.make_guide_fixture_assembly(
            parameters=parameters,
            materials=materials_module.make_guide_materials(),
            position=20.0,
            clamp_position=True,
        )
    assert clamped.solved_position == parameters.guide_slide_travel.value


def test_model_json_strict_replay_preserves_product_signature():
    artifact = main_module.build_replayable_guide_fixture(
        parameters=parameters_module.default_machine_parameters(),
        position=0.0,
    )

    replayed = scad.replay_model_json(json_str=artifact.model_json, strict=True)

    assert artifact.replay_signature_equal
    assert len(replayed) == 1
    assert isinstance(replayed[0], scad.Assembly)
    assert common_module.semantic_signature(
        replayed[0]
    ) == common_module.semantic_signature(artifact.build.assembly)


def test_cli_writes_hash_bound_outputs_and_truthful_evidence(tmp_path):
    result = main_module.main(
        [
            "--target",
            "fixture",
            "--position",
            "12",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert (tmp_path / "weaving_machine_d1_guide_fixture.model.json").is_file()
    assert (tmp_path / "weaving_machine_d1_guide_fixture.session.json").is_file()
    assert (tmp_path / "weaving_machine_d1_guide_fixture.step").is_file()
    evidence = (tmp_path / "weaving_machine_d1_guide_fixture.evidence.json").read_text(
        encoding="utf-8"
    )
    assert '"functional_a40_guide_indexing": false' in evidence
    assert '"manufacturing_release": false' in evidence
    assert '"closure": "unresolved"' in evidence


def test_cli_full_and_manufacturing_gates_fail_closed(tmp_path):
    with pytest.raises(
        parameters_module.ParameterValidationError, match="closed_with_evidence"
    ):
        main_module.main(
            [
                "--target",
                "fixture",
                "--detail",
                "full",
                "--output-dir",
                str(tmp_path),
            ]
        )
    with pytest.raises(
        parameters_module.ParameterValidationError, match="not validated"
    ):
        main_module.main(
            [
                "--target",
                "fixture",
                "--manufacturing-gate",
                "--output-dir",
                str(tmp_path),
            ]
        )
