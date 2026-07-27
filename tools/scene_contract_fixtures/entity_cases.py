"""Entity provenance, topology adjacency, and range corpus cases."""

from __future__ import annotations

from copy import deepcopy

from simplecadapi.scene import validate_entity_asset

from .common import JsonObject, validation_case


def _entity_with_source(entity: JsonObject, source_kind: str) -> JsonObject:
    result = deepcopy(entity)
    topology_kind = {
        "solid": "SOLID",
        "face": "FACE",
        "edge": "EDGE",
        "vertex": "VERTEX",
    }
    for record in result["entities"]:
        if source_kind == "model_output":
            record["source"] = {
                "graph_id": "graph",
                "kind": "model_output",
                "node_id": "body",
                "output_slot": 0,
            }
        elif source_kind == "model_topology":
            record["source"] = {
                "graph_id": "graph",
                "kind": "model_topology",
                "node_id": "body",
                "output_slot": 0,
                "topo_id": record["entity_id"],
                "topology_kind": topology_kind[record["kind"]],
            }
        else:
            record["source"] = {
                "kind": "imported_primitive",
                "source_element_id": record["entity_id"],
            }
    return result


def build_entity_matrix_cases(entity: JsonObject) -> list[dict[str, object]]:
    cases = [
        validation_case(
            f"valid_entity_source_{source_kind}",
            _entity_with_source(entity, source_kind),
            validate_entity_asset,
        )
        for source_kind in ("model_output", "model_topology", "imported_primitive")
    ]
    topology_mismatch = _entity_with_source(entity, "model_topology")
    face = next(
        record for record in topology_mismatch["entities"] if record["kind"] == "face"
    )
    face["source"]["topology_kind"] = "EDGE"
    cases.append(
        validation_case(
            "model_topology_kind_mismatch", topology_mismatch, validate_entity_asset
        )
    )

    missing_reciprocal = deepcopy(entity)
    face = next(
        record for record in missing_reciprocal["entities"] if record["kind"] == "face"
    )
    edge_id = face["child_entity_ids"][0]
    edge = next(
        record
        for record in missing_reciprocal["entities"]
        if record["entity_id"] == edge_id
    )
    edge["parent_entity_ids"].remove(face["entity_id"])
    cases.append(
        validation_case(
            "missing_reciprocal_adjacency", missing_reciprocal, validate_entity_asset
        )
    )

    range_gap = deepcopy(entity)
    range_gap["face_groups"][1]["first_index"] += 3
    cases.append(
        validation_case("face_group_range_gap", range_gap, validate_entity_asset)
    )
    wrong_cardinality = deepcopy(entity)
    wrong_cardinality["edge_groups"][0]["index_count"] = 3
    cases.append(
        validation_case(
            "edge_group_wrong_cardinality", wrong_cardinality, validate_entity_asset
        )
    )
    unsupported_version = deepcopy(entity)
    unsupported_version["schema_version"] = "2.0"
    cases.append(
        validation_case(
            "unsupported_entity_schema_version",
            unsupported_version,
            validate_entity_asset,
        )
    )
    return cases
