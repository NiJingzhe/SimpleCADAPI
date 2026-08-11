from copy import deepcopy

import pytest

import simplecadapi as scad
from simplecadapi.artifacts.brep import read_brep_solid, write_brep_bytes
from simplecadapi.artifacts.canonical import ArtifactValidationError
from simplecadapi.artifacts.topology_snapshot import (
    capture_topology_snapshot,
    encode_topology_snapshot,
    restore_topology_snapshot,
)


def _tagged_box():
    return scad.apply_tag(scad.make_box_rsolid(2.0, 3.0, 4.0), "role.body")


def test_topology_snapshot_is_deterministic_across_independent_builds():
    assert encode_topology_snapshot(_tagged_box()) == encode_topology_snapshot(_tagged_box())


def test_topology_snapshot_restores_exact_semantic_state_after_brep_roundtrip():
    source = _tagged_box()
    snapshot = encode_topology_snapshot(source)
    restored = read_brep_solid(write_brep_bytes(source))

    restore_topology_snapshot(restored, snapshot)

    assert encode_topology_snapshot(restored) == snapshot
    assert scad.list_tags(restored) == scad.list_tags(source)


def test_topology_snapshot_restores_fused_bearing_with_symmetric_wires():
    bearing = scad.std.bearing.make_ball_bearing_rassembly(
        bore_diameter=16.0,
        outer_diameter=24.0,
        bearing_width=5.0,
        ball_diameter=2.5,
        ball_count=12,
        raceway_clearance=0.0,
        edge_chamfer=0.0,
        assembly_id="snapshot_bearing",
        drive_angle_degrees=None,
        fuse_rolling_elements=True,
        rolling_element_fuse_overlap=0.03,
        material=None,
    )
    source = bearing.get_component("outer_ring").item.body
    snapshot = encode_topology_snapshot(source)
    restored = read_brep_solid(write_brep_bytes(source))

    restore_topology_snapshot(restored, snapshot)

    assert encode_topology_snapshot(restored) == snapshot


def test_topology_snapshot_rejects_geometry_mismatch_without_partial_restore():
    source = _tagged_box()
    target = scad.make_box_rsolid(2.0, 3.0, 5.0)
    before = encode_topology_snapshot(target)

    with pytest.raises(ArtifactValidationError) as error:
        restore_topology_snapshot(target, capture_topology_snapshot(source))

    assert error.value.reason == "geometry_mismatch"
    assert encode_topology_snapshot(target) == before


def test_topology_snapshot_rejects_duplicate_restored_ids():
    source = _tagged_box()
    target = read_brep_solid(write_brep_bytes(source))
    snapshot = deepcopy(capture_topology_snapshot(source))
    snapshot["entities"][1]["topo_id"] = snapshot["entities"][0]["topo_id"]

    with pytest.raises(ArtifactValidationError) as error:
        restore_topology_snapshot(target, snapshot)

    assert error.value.reason == "topology_snapshot_invalid"
