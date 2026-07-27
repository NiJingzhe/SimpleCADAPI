"""Presentation, connector binding, and normalized product corpus cases."""

from __future__ import annotations

from copy import deepcopy

from simplecadapi.scene import (
    validate_connector_binding,
    validate_normalized_product,
    validate_presentation,
)

from .common import JsonObject, validation_case


def build_presentation_matrix_cases(
    presentation: JsonObject,
) -> list[dict[str, object]]:
    orthographic = deepcopy(presentation)
    orthographic["cameras"][0].pop("vertical_fov_degrees")
    orthographic["cameras"][0].update(
        {"projection": "orthographic", "vertical_span": 1000}
    )
    visible_only = deepcopy(presentation)
    visible_only["node_overrides"][0].pop("appearance_name")
    appearance_only = deepcopy(presentation)
    appearance_only["node_overrides"][0].pop("visible")
    neither = deepcopy(presentation)
    neither["node_overrides"][0] = {"node_id": "instance/root"}
    unknown_projection = deepcopy(presentation)
    unknown_projection["cameras"][0]["projection"] = "unknown"
    return [
        validation_case("valid_orthographic_camera", orthographic, validate_presentation),
        validation_case("valid_visible_only_override", visible_only, validate_presentation),
        validation_case(
            "valid_appearance_only_override", appearance_only, validate_presentation
        ),
        validation_case("empty_node_override", neither, validate_presentation),
        validation_case(
            "unknown_camera_projection", unknown_projection, validate_presentation
        ),
    ]


def build_connector_binding_matrix_cases(
    binding: JsonObject,
) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for topology_kind, entity_id, flip in (
        ("FACE", "entity/face/0", True),
        ("EDGE", "entity/edge/0", True),
        ("VERTEX", "entity/vertex/0", False),
    ):
        value = deepcopy(binding)
        value["target"]["entity_id"] = entity_id
        value["target"]["flip"] = flip
        value["target"]["expected_source"] = {
            "graph_id": "fixture_graph",
            "kind": "model_topology",
            "node_id": "fixture_body",
            "output_slot": 0,
            "topo_id": f"topo-{topology_kind.lower()}",
            "topology_kind": topology_kind,
        }
        cases.append(
            validation_case(
                f"valid_binding_model_topology_{topology_kind.lower()}",
                value,
                validate_connector_binding,
            )
        )
    named = deepcopy(binding)
    named["name"] = "Fixture connector"
    cases.append(validation_case("valid_binding_named", named, validate_connector_binding))
    missing_name = deepcopy(binding)
    del missing_name["name"]
    cases.append(
        validation_case("missing_binding_name", missing_name, validate_connector_binding)
    )
    unsupported_version = deepcopy(binding)
    unsupported_version["source_model"]["model_schema_version"] = "3.0"
    cases.append(
        validation_case(
            "unsupported_binding_model_schema_version",
            unsupported_version,
            validate_connector_binding,
        )
    )
    return cases


def build_normalized_product_matrix_cases(
    part: JsonObject, assembly: JsonObject
) -> list[dict[str, object]]:
    material_part = deepcopy(part)
    material_part["material"] = {
        "color": [0.2, 0.3, 0.4],
        "density": 7.85,
        "density_unit": "g/cm3",
        "material_id": "steel",
        "metadata": {},
        "name": "Steel",
    }
    model_part = deepcopy(part)
    model_part["body_source"] = {
        "graph_id": "graph",
        "kind": "model_output",
        "node_id": "body",
        "output_slot": 0,
    }
    placement = deepcopy(part)
    placement["connectors"] = [
        {
            "anchor": {
                "anchor_kind": "placement",
                "placement": {
                    "origin": [0, 0, 0],
                    "x_axis": [1, 0, 0],
                    "y_axis": [0, 1, 0],
                    "z_axis": [0, 0, 1],
                },
            },
            "connector_id": "placement",
            "name": None,
        }
    ]
    forwarded = deepcopy(assembly)
    forwarded["connectors"] = [
        {
            "anchor": {
                "anchor_kind": "forwarded",
                "offset": None,
                "source_component_id": "component_a",
                "source_connector_id": "placement",
            },
            "connector_id": "forwarded",
            "name": None,
        }
    ]
    forwarded_offset = deepcopy(forwarded)
    forwarded_offset["connectors"][0]["anchor"]["offset"] = {
        "origin": [0, 0, 5],
        "x_axis": [1, 0, 0],
        "y_axis": [0, 1, 0],
        "z_axis": [0, 0, 1],
    }
    return [
        validation_case(
            "valid_complete_material", material_part, validate_normalized_product
        ),
        validation_case(
            "valid_model_body_source", model_part, validate_normalized_product
        ),
        validation_case(
            "valid_placement_connector", placement, validate_normalized_product
        ),
        validation_case(
            "valid_forwarded_connector_null_offset",
            forwarded,
            validate_normalized_product,
        ),
        validation_case(
            "valid_forwarded_connector_offset",
            forwarded_offset,
            validate_normalized_product,
        ),
    ]
