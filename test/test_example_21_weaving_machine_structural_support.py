from __future__ import annotations

import importlib

import pytest
import simplecadapi as scad


support_module = importlib.import_module(
    "examples.21_weaving_machine.structural_support"
)


def _part(part_id: str) -> scad.Part:
    return scad.make_part_rpart(
        part_id=part_id,
        body=scad.make_box_rsolid(
            width=10.0,
            height=10.0,
            depth=10.0,
            bottom_face_center=(0.0, 0.0, 0.0),
        ),
    )


def _assembly(
    assembly_id: str,
    components: tuple[
        tuple[str, scad.Part | scad.Assembly, tuple[float, float, float]], ...
    ],
) -> scad.Assembly:
    assembly = scad.make_assembly_rassembly(assembly_id=assembly_id)
    for component_id, item, origin in components:
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=item,
            component_id=component_id,
            placement=scad.make_placement_rplacement(origin=origin),
        )
    return assembly


def _machine(
    *subsystems: tuple[str, scad.Assembly],
    left_rail_origin: tuple[float, float, float] = (0.0, -20.0, 0.0),
) -> scad.Assembly:
    frame = _assembly(
        "support_test_frame",
        (
            ("datum_rail_left", _part("support_test_rail_left"), left_rail_origin),
            (
                "datum_rail_right",
                _part("support_test_rail_right"),
                (0.0, 20.0, 0.0),
            ),
        ),
    )
    top_level = (("a10_main_frame", frame), *subsystems)
    return _assembly(
        "support_test_machine",
        tuple(
            (component_id, item, (0.0, 0.0, 0.0)) for component_id, item in top_level
        ),
    )


def test_support_audit_reports_a_detached_part():
    detached = _assembly(
        "support_test_detached",
        (("detached", _part("support_test_detached_part"), (100.0, 0.0, 0.0)),),
    )

    report = support_module.audit_structural_support(
        machine=_machine(("a20_warp_supply", detached))
    )

    assert not report.passed
    assert report.supported_parts == 2
    assert report.total_parts == 3
    assert tuple(item.path for item in report.unsupported) == (
        ("a20_warp_supply", "detached"),
    )


def test_support_audit_rejects_cross_subsystem_accidental_contact():
    supported = _assembly(
        "support_test_supported",
        (("frame_mount", _part("support_test_frame_mount"), (10.0, -20.0, 0.0)),),
    )
    incidental = _assembly(
        "support_test_incidental",
        (("incidental", _part("support_test_incidental_part"), (20.0, -20.0, 0.0)),),
    )

    report = support_module.audit_structural_support(
        machine=_machine(
            ("a20_warp_supply", supported),
            ("a30_upper_bias_supply", incidental),
        )
    )

    assert report.supported_parts == 3
    assert tuple(item.path for item in report.unsupported) == (
        ("a30_upper_bias_supply", "incidental"),
    )


@pytest.mark.parametrize(
    ("gap", "passed"),
    ((0.25, True), (0.251, False)),
)
def test_support_audit_enforces_contact_tolerance(gap: float, passed: bool):
    near_frame = _assembly(
        "support_test_tolerance",
        (
            (
                "near_frame",
                _part("support_test_near_frame_part"),
                (10.0 + gap, -20.0, 0.0),
            ),
        ),
    )

    report = support_module.audit_structural_support(
        machine=_machine(("a20_warp_supply", near_frame))
    )

    assert report.passed is passed
    assert report.supported_parts == (3 if passed else 2)


def test_support_audit_rejects_invalid_contact_tolerance():
    machine = _machine()

    with pytest.raises(ValueError, match="finite and non-negative"):
        support_module.audit_structural_support(
            machine=machine,
            contact_tolerance=float("nan"),
        )
