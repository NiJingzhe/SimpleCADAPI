"""Regenerate immutable cross-language Scene 1.0 contract vectors."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from simplecadapi.scene import (
    BASE_LIMITS,
    canonical_json_bytes,
    validate_connector_binding,
    validate_entity_asset,
    validate_normalized_product,
    validate_presentation,
    validate_scene_manifest,
    validate_scene_package,
    with_scene_revision,
)
from scene_contract_fixtures.authored_cases import (
    build_connector_binding_matrix_cases,
    build_normalized_product_matrix_cases,
    build_presentation_matrix_cases,
)
from scene_contract_fixtures.base_scene import build_scene_package
from scene_contract_fixtures.binary_cases import build_binary_cases
from scene_contract_fixtures.common import b64, content_hash, first_issue, report_case
from scene_contract_fixtures.entity_cases import build_entity_matrix_cases
from scene_contract_fixtures.numeric_cases import build_numeric_vectors
from scene_contract_fixtures.package_cases import build_package_matrix_cases
from scene_contract_fixtures.resource_cases import build_resource_cases
from scene_contract_fixtures.schema_field_matrix import build_schema_field_matrices
from scene_contract_fixtures.scene_corpus import (
    build_revision_vectors,
    build_scene_field_cases,
    build_scene_shape_cases,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "test" / "fixtures" / "scene-contract" / "corpus.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if output is stale")
    args = parser.parse_args()

    scene, scene_bytes, entity, entity_bytes, blobs = build_scene_package()
    blob_pool = {uri: b64(payload) for uri, payload in blobs.items()}
    scene_shape_cases, scene_packages = build_scene_shape_cases(
        scene, entity, blobs, blob_pool
    )
    scene_field_cases = build_scene_field_cases(scene)
    geometry_uri = next(uri for uri in blobs if uri.startswith("geometry/"))
    edge_uri = next(uri for uri in blobs if uri.startswith("edges/"))
    entity_uri = next(uri for uri in blobs if uri.startswith("entities/"))
    triangle_glb = blobs[geometry_uri]
    line_glb = blobs[edge_uri]
    canonical_zip, deflate_zip, glb_cases, zip_cases = build_binary_cases(
        triangle_glb,
        line_glb,
        {"scene.json": scene_bytes, **blobs},
    )

    missing_nodes = deepcopy(scene)
    del missing_nodes["nodes"]
    missing_nodes_bytes = canonical_json_bytes(missing_nodes)
    empty_nodes = with_scene_revision({**scene, "nodes": []})
    empty_nodes_bytes = canonical_json_bytes(empty_nodes)
    revision_mismatch = deepcopy(scene)
    revision_mismatch["revision"] = "sha256:" + "0" * 64
    revision_mismatch_bytes = canonical_json_bytes(revision_mismatch)
    transform_invalid = deepcopy(scene)
    transform_invalid["nodes"][0]["transform"]["x_axis"] = [2, 0, 0]
    transform_invalid = with_scene_revision(transform_invalid)
    transform_invalid_bytes = canonical_json_bytes(transform_invalid)

    nonunit_entity = deepcopy(entity)
    next(item for item in nonunit_entity["entities"] if item["kind"] == "edge")[
        "geometry"
    ]["direction"] = [2, 0, 0]
    nonunit_entity_bytes = canonical_json_bytes(nonunit_entity)
    unordered_entity = deepcopy(entity)
    shared_edge = next(
        item
        for item in unordered_entity["entities"]
        if item["kind"] == "edge" and len(item["parent_entity_ids"]) == 2
    )
    shared_edge["parent_entity_ids"].reverse()
    unordered_entity_bytes = canonical_json_bytes(unordered_entity)

    presentation = {
        "appearances": [
            {
                "alpha_mode": "opaque",
                "base_color": [0.2, 0.3, 0.4, 1],
                "double_sided": False,
                "edge_color": [0.05, 0.05, 0.05, 1],
                "metallic": 0.1,
                "name": "fixture",
                "roughness": 0.7,
            }
        ],
        "cameras": [
            {
                "far": 10000,
                "name": "overview",
                "near": 1,
                "parent_node_id": None,
                "projection": "perspective",
                "transform": {
                    "origin": [2000, -2000, 2000],
                    "x_axis": [1, 0, 0],
                    "y_axis": [0, 1, 0],
                    "z_axis": [0, 0, 1],
                },
                "vertical_fov_degrees": 45,
            }
        ],
        "node_overrides": [
            {
                "appearance_name": "fixture",
                "node_id": "instance/root",
                "visible": True,
            }
        ],
        "presentation_id": "fixture",
        "schema_version": "1.0",
        "source_scene_id": "fixture",
    }
    presentation_bytes = canonical_json_bytes(presentation)
    missing_appearance = deepcopy(presentation)
    missing_appearance["node_overrides"][0]["appearance_name"] = "missing"
    missing_appearance_bytes = canonical_json_bytes(missing_appearance)
    bad_camera = deepcopy(presentation)
    bad_camera["cameras"][0]["far"] = 1
    bad_camera_bytes = canonical_json_bytes(bad_camera)

    connector_binding = {
        "binding_id": "fixture",
        "connector_id": "fixture_connector",
        "name": None,
        "owner_definition_id": "definition/root/part/fixture",
        "schema_version": "1.0",
        "selected_occurrence_node_id": "instance/root",
        "source_model": {
            "artifact_hash": "sha256:" + "1" * 64,
            "graph_id": "fixture_graph",
            "model_schema_version": "2.0",
        },
        "source_scene": {"revision": scene["revision"], "scene_id": "fixture"},
        "target": {
            "entity_asset_id": entity["geometry_asset_id"],
            "entity_id": "entity/face/0",
            "expected_source": {
                "graph_id": "fixture_graph",
                "kind": "model_output",
                "node_id": "fixture_body",
                "output_slot": 0,
            },
            "flip": True,
            "kind": "topology_entity",
        },
    }
    connector_binding_bytes = canonical_json_bytes(connector_binding)
    wrong_binding_graph = deepcopy(connector_binding)
    wrong_binding_graph["target"]["expected_source"]["graph_id"] = "other_graph"
    wrong_binding_graph_bytes = canonical_json_bytes(wrong_binding_graph)
    vertex_flip = deepcopy(connector_binding)
    vertex_flip["target"]["entity_id"] = "entity/vertex/0"
    vertex_flip_bytes = canonical_json_bytes(vertex_flip)

    normalized_part = {
        "body_source": {"kind": "manual", "source_id": "fixture_body"},
        "connectors": [],
        "kind": "part",
        "material": None,
        "metadata": {},
        "name": None,
        "part_id": "fixture_part",
    }
    normalized_part_bytes = canonical_json_bytes(normalized_part)
    normalized_assembly = {
        "assembly_id": "fixture_assembly",
        "components": [
            {
                "component_id": "component_a",
                "definition_ref": "definition/root/part/fixture",
                "local_placement": {
                    "origin": [0, 0, 0],
                    "x_axis": [1, 0, 0],
                    "y_axis": [0, 1, 0],
                    "z_axis": [0, 0, 1],
                },
                "name": None,
            }
        ],
        "connectors": [],
        "constraints": [],
        "grounded_component_ids": ["component_a"],
        "kind": "assembly",
        "metadata": {},
        "name": None,
    }
    normalized_assembly_bytes = canonical_json_bytes(normalized_assembly)
    missing_grounded_component = deepcopy(normalized_assembly)
    missing_grounded_component["grounded_component_ids"] = ["missing"]
    missing_grounded_component_bytes = canonical_json_bytes(missing_grounded_component)
    duplicate_components = deepcopy(normalized_assembly)
    duplicate_components["components"].append(
        deepcopy(duplicate_components["components"][0])
    )
    duplicate_components_bytes = canonical_json_bytes(duplicate_components)

    bad_bounds = deepcopy(scene)
    bad_bounds["geometry_assets"][0]["scene_local_bounds"]["max"][0] = 999
    bad_bounds = with_scene_revision(bad_bounds)
    bad_bounds_bytes = canonical_json_bytes(bad_bounds)
    missing_blob = dict(blobs)
    del missing_blob[edge_uri]
    mutated_blobs = dict(blobs)
    mutated_blobs[geometry_uri] = bytes([triangle_glb[0] ^ 1]) + triangle_glb[1:]

    resource_cases = build_resource_cases(
        scene,
        normalized_part,
    )
    manifest_cases = [
        report_case("valid_scene", scene_bytes, validate_scene_manifest(scene_bytes)),
        report_case(
            "missing_nodes",
            missing_nodes_bytes,
            validate_scene_manifest(missing_nodes_bytes),
        ),
        report_case(
            "empty_nodes",
            empty_nodes_bytes,
            validate_scene_manifest(empty_nodes_bytes),
        ),
        report_case(
            "revision_mismatch",
            revision_mismatch_bytes,
            validate_scene_manifest(revision_mismatch_bytes),
        ),
        report_case(
            "transform_invalid",
            transform_invalid_bytes,
            validate_scene_manifest(transform_invalid_bytes),
        ),
        report_case(
            "noncanonical_json",
            scene_bytes + b"\n",
            validate_scene_manifest(scene_bytes + b"\n"),
        ),
        report_case(
            "duplicate_json_key",
            b'{"schema_version":"1.0","schema_version":"1.0"}',
            validate_scene_manifest(
                b'{"schema_version":"1.0","schema_version":"1.0"}'
            ),
        ),
        report_case(
            "bom",
            b"\xef\xbb\xbf" + scene_bytes,
            validate_scene_manifest(b"\xef\xbb\xbf" + scene_bytes),
        ),
    ]
    entity_cases = [
        report_case(
            "valid_entities", entity_bytes, validate_entity_asset(entity_bytes)
        ),
        report_case(
            "nonunit_analytic_direction",
            nonunit_entity_bytes,
            validate_entity_asset(nonunit_entity_bytes),
        ),
        report_case(
            "unordered_adjacency",
            unordered_entity_bytes,
            validate_entity_asset(unordered_entity_bytes),
        ),
    ]
    entity_cases.extend(build_entity_matrix_cases(entity))
    presentation_cases = [
        report_case(
            "valid_presentation",
            presentation_bytes,
            validate_presentation(presentation_bytes),
        ),
        report_case(
            "missing_presentation_appearance",
            missing_appearance_bytes,
            validate_presentation(missing_appearance_bytes),
        ),
        report_case(
            "invalid_presentation_camera",
            bad_camera_bytes,
            validate_presentation(bad_camera_bytes),
        ),
    ]
    presentation_cases.extend(build_presentation_matrix_cases(presentation))
    connector_binding_cases = [
        report_case(
            "valid_connector_binding",
            connector_binding_bytes,
            validate_connector_binding(connector_binding_bytes),
        ),
        report_case(
            "connector_binding_graph_mismatch",
            wrong_binding_graph_bytes,
            validate_connector_binding(wrong_binding_graph_bytes),
        ),
        report_case(
            "connector_binding_vertex_flip",
            vertex_flip_bytes,
            validate_connector_binding(vertex_flip_bytes),
        ),
    ]
    connector_binding_cases.extend(
        build_connector_binding_matrix_cases(connector_binding)
    )
    normalized_product_cases = [
        report_case(
            "valid_normalized_part",
            normalized_part_bytes,
            validate_normalized_product(normalized_part_bytes),
        ),
        report_case(
            "valid_normalized_assembly",
            normalized_assembly_bytes,
            validate_normalized_product(normalized_assembly_bytes),
        ),
        report_case(
            "missing_grounded_component",
            missing_grounded_component_bytes,
            validate_normalized_product(missing_grounded_component_bytes),
        ),
        report_case(
            "duplicate_components",
            duplicate_components_bytes,
            validate_normalized_product(duplicate_components_bytes),
        ),
    ]
    normalized_product_cases.extend(
        build_normalized_product_matrix_cases(normalized_part, normalized_assembly)
    )
    package_cases = [
        {
            "blob_uris": sorted(blobs),
            "expected": first_issue(validate_scene_package(scene_bytes, blobs)),
            "manifest_base64": b64(scene_bytes),
            "name": "valid_package",
            "valid": True,
        },
        {
            "blob_uris": sorted(blobs),
            "expected": first_issue(validate_scene_package(bad_bounds_bytes, blobs)),
            "manifest_base64": b64(bad_bounds_bytes),
            "name": "glb_bounds_mismatch",
            "valid": False,
        },
        {
            "blob_uris": sorted(missing_blob),
            "expected": first_issue(validate_scene_package(scene_bytes, missing_blob)),
            "manifest_base64": b64(scene_bytes),
            "name": "missing_blob",
            "valid": False,
        },
        {
            "blob_mutations": {geometry_uri: b64(mutated_blobs[geometry_uri])},
            "blob_uris": sorted(mutated_blobs),
            "expected": first_issue(validate_scene_package(scene_bytes, mutated_blobs)),
            "manifest_base64": b64(scene_bytes),
            "name": "blob_hash_mismatch",
            "valid": False,
        },
    ]
    package_cases.extend(
        build_package_matrix_cases(
            scene, entity, blobs, scene_packages, blob_pool
        )
    )

    jcs_input = {
        "literals": [None, True, False],
        "numbers": [333333333.33333329, 1e30, 4.50, 2e-3, 1e-27],
        "string": "€$\u000f\nA'B\"\\\\\"/",
    }
    jcs_bytes = canonical_json_bytes(jcs_input)
    corpus = {
        "artifacts": {
            "canonical_zip": {
                "base64": b64(canonical_zip),
                "sha256": content_hash(canonical_zip),
            },
            "deflate_zip": {
                "base64": b64(deflate_zip),
                "sha256": content_hash(deflate_zip),
            },
            "edge_glb": {
                "base64": b64(line_glb),
                "sha256": content_hash(line_glb),
                "uri": edge_uri,
            },
            "entities": {
                "base64": b64(entity_bytes),
                "sha256": content_hash(entity_bytes),
                "uri": entity_uri,
            },
            "geometry_glb": {
                "base64": b64(triangle_glb),
                "sha256": content_hash(triangle_glb),
                "uri": geometry_uri,
            },
            "scene": {
                "base64": b64(scene_bytes),
                "revision": scene["revision"],
                "sha256": content_hash(scene_bytes),
            },
        },
        "blobs": dict(sorted(blob_pool.items())),
        "entity_cases": entity_cases,
        "connector_binding_cases": connector_binding_cases,
        "format_version": "1.0",
        "glb_cases": glb_cases,
        "jcs_vectors": [
            {
                "canonical_base64": b64(jcs_bytes),
                "input": jcs_input,
                "name": "rfc8785_number_and_string_sample",
                "sha256": content_hash(jcs_bytes),
            }
        ],
        "manifest_cases": manifest_cases,
        "numeric_vectors": build_numeric_vectors(),
        "normalized_product_cases": normalized_product_cases,
        "package_cases": package_cases,
        "presentation_cases": presentation_cases,
        "resource_cases": resource_cases,
        "resource_limits": asdict(BASE_LIMITS),
        "revision_vectors": build_revision_vectors(scene_packages),
        "scene_field_cases": scene_field_cases,
        "scene_shape_cases": scene_shape_cases,
        "schema_field_matrices": build_schema_field_matrices(
            ROOT / "src/simplecadapi/scene/contracts/schemas"
        ),
        "zip_cases": zip_cases,
    }
    for collection in (
        manifest_cases,
        entity_cases,
        presentation_cases,
        connector_binding_cases,
        normalized_product_cases,
        package_cases,
    ):
        for case in collection:
            assert case["valid"] == (case["expected"] is None), case["name"]
    payload = (
        json.dumps(corpus, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    relative_output = OUTPUT.relative_to(ROOT)
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_bytes() != payload:
            print(f"stale generated fixture: {relative_output}", file=sys.stderr)
            return 1
        print(f"{relative_output} is current ({len(payload)} bytes)")
        return 0

    OUTPUT.write_bytes(payload)
    print(f"wrote {relative_output} ({len(payload)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
