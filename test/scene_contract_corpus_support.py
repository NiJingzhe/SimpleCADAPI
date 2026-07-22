"""Shared-corpus replay and characterization helpers for Python tests."""

from __future__ import annotations

import base64
from collections import Counter
from copy import deepcopy
from typing import Any, Mapping

from simplecadapi.scene import with_scene_revision


def decode_base64(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


def corpus_blobs(
    corpus: Mapping[str, Any], case: Mapping[str, Any]
) -> dict[str, bytes]:
    pool = {
        uri: decode_base64(payload) for uri, payload in corpus["blobs"].items()
    }
    blobs = {uri: pool[uri] for uri in case["blob_uris"]}
    blobs.update(
        {
            uri: decode_base64(payload)
            for uri, payload in case.get("blob_mutations", {}).items()
        }
    )
    return blobs


def apply_scene_field_case(
    scene: Mapping[str, Any], case: Mapping[str, Any]
) -> dict[str, Any]:
    result = deepcopy(dict(scene))
    for mutation in case["mutations"]:
        current: Any = result
        path = mutation["path"]
        for part in path[:-1]:
            current = current[part]
        if mutation["operation"] == "delete":
            del current[path[-1]]
        else:
            current[path[-1]] = deepcopy(mutation.get("value"))
    return with_scene_revision(result) if case["recompute_revision"] else result


def scene_shape_facts(scene: Mapping[str, Any]) -> dict[str, Any]:
    nodes = scene["nodes"]
    occurrence_counts = Counter(node["definition_id"] for node in nodes)
    return {
        "definition_count": len(scene["definitions"]),
        "definition_occurrence_counts": dict(sorted(occurrence_counts.items())),
        "edge_asset_count": len(scene["edge_assets"]),
        "entity_asset_count": len(scene["entity_assets"]),
        "geometry_asset_count": len(scene["geometry_assets"]),
        "maximum_depth": max(
            len(node["source"].get("component_path", [])) for node in nodes
        ),
        "node_count": len(nodes),
        "root_node_ids": [
            node["node_id"] for node in nodes if node["parent_node_id"] is None
        ],
    }
