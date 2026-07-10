import simplecadapi as scad


def _two_box_assembly(offset):
    box = scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)
    part = scad.make_part_rpart(part_id="box_part", body=box)
    assembly = scad.make_assembly_rassembly(assembly_id="collision_demo")
    assembly = scad.add_component_rassembly(
        assembly=assembly,
        item=part,
        component_id="box_a",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly=assembly,
        item=part,
        component_id="box_b",
        placement=scad.make_placement_rplacement(origin=offset),
    )
    return assembly


def test_verifier_namespace_is_public():
    assert hasattr(scad, "verifier")
    assert "verifier" in scad.__all__
    assert hasattr(scad.verifier, "check_collision_rcollisionreport")


def test_collision_report_passes_for_separated_meshes():
    assembly = _two_box_assembly(offset=(2.0, 0.0, 0.0))

    report = scad.verifier.check_collision_rcollisionreport(
        assembly=assembly,
        config=scad.verifier.CollisionCheckConfig(max_allowed_penetration=0.01),
    )

    assert report.completed
    assert report.passed
    assert report.checked_pair_count == 1
    assert report.failed_pair_count == 0
    assert report.failures == ()


def test_collision_report_fails_for_over_tolerance_contact_penetration():
    assembly = _two_box_assembly(offset=(0.5, 0.0, 0.0))

    report = scad.verifier.check_collision_rcollisionreport(
        assembly=assembly,
        config=scad.verifier.CollisionCheckConfig(max_allowed_penetration=0.01),
    )

    assert report.completed
    assert not report.passed
    assert report.checked_pair_count == 1
    assert report.failed_pair_count == 1
    failure = report.failures[0]
    assert failure.component_a == ("box_a",)
    assert failure.component_b == ("box_b",)
    assert failure.penetration_depth > 0.01
    assert failure.kind == "contact_penetration"
    assert failure.contacts


def test_collision_report_respects_allowed_penetration_tolerance():
    assembly = _two_box_assembly(offset=(0.5, 0.0, 0.0))

    report = scad.verifier.check_collision_rcollisionreport(
        assembly=assembly,
        config=scad.verifier.CollisionCheckConfig(max_allowed_penetration=2.0),
    )

    assert report.completed
    assert report.passed
    assert report.checked_pair_count == 1
    assert report.failed_pair_count == 0


def test_collision_scope_can_exclude_pair():
    assembly = _two_box_assembly(offset=(0.5, 0.0, 0.0))

    report = scad.verifier.check_collision_rcollisionreport(
        assembly=assembly,
        config=scad.verifier.CollisionCheckConfig(
            max_allowed_penetration=0.01,
            scope=scad.verifier.CollisionScope(
                exclude_pairs=(scad.verifier.ComponentPair("box_a", "box_b"),),
            ),
        ),
    )

    assert report.completed
    assert report.passed
    assert report.checked_pair_count == 0
    assert report.failed_pair_count == 0
