import json
from copy import deepcopy

import pytest

from simplecadapi.artifacts.assembly_definition import AssemblyDefinition
from simplecadapi.artifacts.canonical import (
    ArtifactValidationError,
    canonical_bytes,
    content_hash,
    sha256_bytes,
    validate_relative_path,
)
from simplecadapi.artifacts.part_definition import PartDefinition
from simplecadapi.artifacts.references import BlobRef, InterfaceHashes
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


def _part_definition():
    model = canonical_bytes({"model": "fixture"})
    body = b"fixture-brep"
    topology = canonical_bytes({"topology": "fixture"})
    model_ref = _blob("model/model.json", model, "application/json")
    body_ref = _blob("body/body.brep", body, "application/vnd.opencascade.brep")
    topology_ref = _blob("topology/snapshot.json", topology, "application/json")
    return PartDefinition(
        definition_id="fixture_part",
        revision="r1",
        tolerance_profile="simplecad-default",
        generator=GENERATOR,
        model_ref=model_ref,
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
        blobs={model_ref.path: model, body_ref.path: body, topology_ref.path: topology},
    )


def _assembly_definition():
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
        solved_snapshot={"component_placements": []},
    )


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
