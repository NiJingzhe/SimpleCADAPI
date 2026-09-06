import json
from copy import deepcopy
from pathlib import Path

import pytest

import simplecadapi as scad
from simplecadapi.artifacts.assembly_definition import AssemblyDefinition
from simplecadapi.artifacts.canonical import (
    ArtifactValidationError,
    canonical_bytes,
    content_hash,
    sha256_bytes,
    validate_relative_path,
)
from simplecadapi.artifacts.feature_graph import (
    capture_feature_graph,
    encode_feature_graph_artifact,
)
from simplecadapi.artifacts.part_definition import PartDefinition
from simplecadapi.artifacts.references import BlobRef, ConnectorInterface, InterfaceHashes
from simplecadapi.artifacts.validation import (
    parse_artifact_json,
    validate_artifact_blobs,
    validate_manifest,
)


GENERATOR = {
    "simplecadapi_version": "2.0.4b1",
    "ocp_version": "7.9.3.1",
    "python_abi": "cp313",
    "platform_tag": "darwin-arm64",
    "semantic_registry_version": "1.0",
}
EMPTY_HASH = content_hash({}, omit=())


def _blob(path, payload, media_type):
    return BlobRef(path, sha256_bytes(payload), len(payload), media_type)

def _feature_graph_blob(definition_id: str, definition_kind: str):
    with scad.GraphSession(graph_id=definition_id) as session:
        body = scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)
        session.capture_result(value=body)
    artifact = capture_feature_graph(
        session=session,
        owner_definition_kind=definition_kind,
        owner_definition_id=definition_id,
        owner_revision="r1",
        project_root=Path(__file__).resolve().parents[1],
    )
    payload = encode_feature_graph_artifact(artifact)
    path = (
        "features/"
        + artifact.content_hash.removeprefix("sha256:")
        + ".feature-graph.zip"
    )
    return _blob(
        path,
        payload,
        "application/vnd.simplecad.feature-graph+zip",
    ), payload


def _part_definition():
    feature_ref, feature_payload = _feature_graph_blob(
        "fixture_part", "single_solid"
    )
    body = b"fixture-brep"
    topology = canonical_bytes({"topology": "fixture"})
    body_ref = _blob("body/body.brep", body, "application/vnd.opencascade.brep")
    topology_ref = _blob("topology/snapshot.json", topology, "application/json")
    return PartDefinition(
        definition_id="fixture_part",
        revision="r1",
        tolerance_profile="simplecad-default",
        generator=GENERATOR,
        feature_graph_ref=feature_ref,
        solid_cache_ref=body_ref,
        topology_snapshot_ref=topology_ref,
        connectors=(),
        material_ref=None,
        file_inputs=(),
        interface_hashes=InterfaceHashes(
            geometry=sha256_bytes(body),
            connectors={},
            bindings={},
            material=None,
        ),
        blobs={
            feature_ref.path: feature_payload,
            body_ref.path: body,
            topology_ref.path: topology,
        },
    )


def _assembly_definition():
    feature_ref, feature_payload = _feature_graph_blob(
        "fixture_assembly", "assembly"
    )
    return AssemblyDefinition(
        definition_id="fixture_assembly",
        revision="r1",
        tolerance_profile="simplecad-default",
        generator=GENERATOR,
        definition_refs=(),
        instances=(),
        relations=(),
        grounded_instance_ids=(),
        public_connectors=(),
        interface_hashes=InterfaceHashes(
            geometry=EMPTY_HASH,
            connectors={},
            bindings={},
            material=None,
        ),
        feature_graph_ref=feature_ref,
        solved_snapshot={"component_placements": []},
        blobs={feature_ref.path: feature_payload},
    )


def test_connector_interface_hash_includes_public_name() -> None:
    common = {
        "connector_id": "output_axis",
        "anchor_kind": "public",
        "local_frame": scad.identity_placement_rplacement().to_dict(),
        "binding": None,
        "source_component_id": "rotor",
        "source_connector_id": "axis",
    }

    unnamed = ConnectorInterface(name=None, **common)
    named = ConnectorInterface(name="Output axis", **common)

    assert named.interface_hash != unnamed.interface_hash


def test_connector_interface_hash_uses_normalized_frame() -> None:
    raw_frame = {
        "origin": [41.7193000900063, -14.849242404917511, 0.0],
        "x_axis": [0.7071067811865474, -0.7071067811865477, 0.0],
        "y_axis": [0.5000000000000001, 0.49999999999999983, -0.7071067811865475],
        "z_axis": [0.5000000000000002, 0.4999999999999999, 0.7071067811865476],
    }
    connector = ConnectorInterface(
        connector_id="roller_axis",
        name=None,
        anchor_kind="placement",
        local_frame=raw_frame,
        binding=None,
    )
    payload = canonical_bytes(connector.to_dict())
    for _ in range(10):
        connector = ConnectorInterface.from_dict(json.loads(payload))
        assert canonical_bytes(connector.to_dict()) == payload
    nearby = deepcopy(raw_frame)
    nearby["origin"][0] += 1e-10
    nearby["y_axis"][0] += 1e-15
    same_chunk = ConnectorInterface(
        connector_id="roller_axis", name=None, anchor_kind="placement",
        local_frame=nearby, binding=None,
    )
    assert same_chunk.interface_hash == connector.interface_hash
    changed = json.loads(payload)
    changed["local_frame"]["origin"][0] += 2_000_000  # 0.002 mm in 1e-9 mm ticks
    with pytest.raises(ArtifactValidationError) as caught:
        ConnectorInterface.from_dict(changed)
    assert caught.value.reason == "hash_invalid"


def test_part_definition_canonical_roundtrip_and_blob_validation():
    definition = _part_definition()
    parsed = parse_artifact_json(definition.canonical_bytes, kind="part_definition")
    rebuilt = PartDefinition.from_dict(parsed, blobs=definition.blobs)

    validate_artifact_blobs(rebuilt.to_dict(), rebuilt.blobs)
    assert rebuilt.canonical_bytes == definition.canonical_bytes
    assert rebuilt.content_hash == definition.content_hash
    assert rebuilt.units == "mm"


def test_assembly_solved_snapshot_does_not_change_definition_identity():
    first = _assembly_definition()
    payload = first.to_dict()
    payload["solved_snapshot"] = {"component_placements": [], "solver": "replacement"}
    second = AssemblyDefinition.from_dict(payload)

    assert second.content_hash == first.content_hash
    assert second.canonical_bytes != first.canonical_bytes


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda value: value.update(unexpected=True), "schema_invalid"),
        (lambda value: value.update(units="inch"), "schema_invalid"),
        (lambda value: value.update(content_hash="sha256:" + "0" * 64), "hash_invalid"),
    ],
)
def test_part_manifest_rejects_closed_schema_and_identity_violations(mutate, reason):
    payload = deepcopy(_part_definition().to_dict())
    mutate(payload)

    with pytest.raises(ArtifactValidationError) as error:
        validate_manifest(payload, "part_definition")

    assert error.value.reason == reason


def test_artifact_json_rejects_noncanonical_bytes():
    payload = _part_definition().to_dict()
    noncanonical = json.dumps(payload, indent=2).encode("utf-8")

    with pytest.raises(ArtifactValidationError) as error:
        parse_artifact_json(noncanonical, kind="part_definition")

    assert error.value.reason == "noncanonical_json"


def test_blob_validation_rejects_size_hash_and_unreferenced_payloads():
    definition = _part_definition()
    blobs = dict(definition.blobs)
    blobs[definition.solid_cache_ref.path] = b"corrupt"

    with pytest.raises(ArtifactValidationError) as error:
        validate_artifact_blobs(definition.to_dict(), blobs)
    assert error.value.reason == "blob_size_mismatch"

    blobs = dict(definition.blobs)
    blobs["extra.bin"] = b"extra"
    with pytest.raises(ArtifactValidationError) as error:
        validate_artifact_blobs(definition.to_dict(), blobs)
    assert error.value.reason == "blob_unreferenced"


def test_artifact_paths_are_normalized_project_relative_ascii():
    assert validate_relative_path("inputs/model.step", "/path") == "inputs/model.step"
    for invalid in ("../model.step", "/tmp/model.step", "inputs//model.step", "inputs\\model.step", "输入.step"):
        with pytest.raises(ArtifactValidationError):
            validate_relative_path(invalid, "/path")
