from __future__ import annotations

from dataclasses import replace

import pytest

import simplecadapi as scad
from simplecadapi.artifacts.brep import read_brep_solid, write_brep_bytes
from simplecadapi.artifacts.interface import PartInterfaceSnapshot
from simplecadapi.artifacts.references import ConnectorInterface, InterfaceHashes


def _connector(
    connector_id: str,
    *,
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
    binding: dict | None = None,
) -> ConnectorInterface:
    return ConnectorInterface(
        connector_id=connector_id,
        name=None,
        anchor_kind="geometry" if binding is not None else "placement",
        local_frame=scad.make_placement_rplacement(origin=origin).to_dict(),
        binding=binding,
    )


def _snapshot(
    definition_id: str,
    *,
    geometry: str,
    connectors: tuple[ConnectorInterface, ...] = (),
    material: str | None = None,
    build_key: str = "sha256:" + "1" * 64,
) -> PartInterfaceSnapshot:
    return PartInterfaceSnapshot(
        definition_id=definition_id,
        definition_hash="sha256:" + "d" * 64,
        build_key=build_key,
        interface_hashes=InterfaceHashes(
            geometry=geometry,
            connectors={item.connector_id: item.interface_hash for item in connectors},
            bindings={item.connector_id: item.binding_hash for item in connectors},
            material=material,
        ),
    )


def test_geometry_interface_hash_is_independent_of_brep_bytes_and_build_identity():
    first = scad.make_box_rsolid(width=2.0, height=3.0, depth=4.0)
    independently_built = scad.make_box_rsolid(width=2.0, height=3.0, depth=4.0)
    round_tripped = read_brep_solid(write_brep_bytes(first))
    changed = scad.make_box_rsolid(width=2.1, height=3.0, depth=4.0)

    first_interface = scad.geometry_interface_fingerprint(first)

    assert first_interface == scad.geometry_interface_fingerprint(independently_built)
    assert first_interface == scad.geometry_interface_fingerprint(round_tripped)
    assert first_interface != scad.geometry_interface_fingerprint(changed)
    assert first_interface != "sha256:" + write_brep_bytes(first).hex()[:64]

    descriptor = scad.geometry_interface_descriptor(first)
    assert descriptor["body_count"] == 1
    assert descriptor["face_count"] == 6
    assert descriptor["edge_count"] == 12
    assert descriptor["vertex_count"] == 8


def test_part_interface_diff_classifies_all_downstream_scopes():
    geometry_a = "sha256:" + "a" * 64
    geometry_b = "sha256:" + "b" * 64
    material_a = "sha256:" + "c" * 64
    material_b = "sha256:" + "e" * 64
    mount_a = _connector("mount", origin=(0.0, 0.0, 0.0))
    mount_b = _connector("mount", origin=(1.0, 0.0, 0.0))
    audit_a = _connector("audit", binding={"kind": "face", "selector": {"index": 1}})
    audit_b = _connector("audit", binding={"kind": "face", "selector": {"index": 2}})
    removed = _connector("removed")
    added = _connector("added")

    before = _snapshot(
        "part_a",
        geometry=geometry_a,
        connectors=(mount_a, audit_a, removed),
        material=material_a,
    )
    after = _snapshot(
        "part_a",
        geometry=geometry_b,
        connectors=(mount_b, audit_b, added),
        material=material_b,
        build_key="sha256:" + "2" * 64,
    )

    diff = scad.diff_part_interfaces(before, after)

    assert diff.geometry_changed
    assert diff.connector_interface_changed == ("mount",)
    assert diff.connector_binding_changed == ("audit",)
    assert diff.connector_added == ("added",)
    assert diff.connector_removed == ("removed",)
    assert diff.material_changed
    assert diff.pose_dirty
    assert diff.dirty_scopes() == ("geometry", "pose", "binding_audit", "material")


def test_part_interface_diff_marks_build_only_changes_as_provenance():
    value = _snapshot("stable", geometry="sha256:" + "a" * 64)
    changed_build = replace(value, build_key="sha256:" + "2" * 64)

    diff = scad.diff_part_interfaces(value, changed_build)

    assert diff.provenance_only
    assert not diff.interface_changed
    assert diff.dirty_scopes() == ("provenance",)


def test_latest_part_state_preserves_other_definitions_and_returns_predecessor(
    tmp_path,
):
    state_path = tmp_path / "state" / "latest-parts.json"
    policy = scad.CachePolicy(root=tmp_path / "cache")

    @scad.part(id="first_part", cache=policy)
    def first(width: float = 1.0):
        return scad.make_box_rsolid(width=width, height=1.0, depth=1.0)

    @scad.part(id="second_part", cache=policy)
    def second():
        return scad.make_box_rsolid(width=2.0, height=1.0, depth=1.0)

    initial = first()
    warm = first()
    second()
    changed = first(2.0)
    parts = scad.load_latest_part_state(state_path)

    assert initial.interface_diff is None
    assert warm.interface_diff is None
    assert changed.interface_diff is not None
    assert changed.interface_diff.geometry_changed
    assert set(parts) == {"first_part", "second_part"}
    assert parts["first_part"].build_key == changed.cache_report.build_key


def test_read_only_part_diff_does_not_mutate_latest_state(tmp_path):
    cache_root = tmp_path / "cache"

    @scad.part(id="read_only_diff", cache=scad.CachePolicy(root=cache_root))
    def cached(width: float = 1.0):
        return scad.make_box_rsolid(width=width, height=1.0, depth=1.0)

    baseline = cached()
    state_path = tmp_path / "state" / "latest-parts.json"
    before = state_path.read_bytes()

    @scad.part(
        id="read_only_diff",
        cache=scad.CachePolicy(mode="read_only", root=cache_root),
    )
    def read_only(width: float = 2.0):
        return scad.make_box_rsolid(width=width, height=1.0, depth=1.0)

    result = read_only()

    assert result.interface_diff is not None
    assert result.interface_diff.geometry_changed
    assert state_path.read_bytes() == before
    assert (
        baseline.definition.interface_hashes.geometry
        != result.definition.interface_hashes.geometry
    )
