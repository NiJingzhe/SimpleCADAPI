import base64
import hashlib
import json
import math
import re
import struct
import subprocess
import sys
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, is_dataclass, replace
from pathlib import Path
from types import MappingProxyType
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
import simplecadapi.scene.archive as scene_archive

from simplecadapi.scene import (
    BASE_LIMITS,
    ConnectorBindingDocument,
    EntityDocument,
    NormalizedProductDocument,
    PresentationDocument,
    SCHEMA_FILES,
    SceneContractError,
    SceneDocument,
    SceneResourceLimits,
    canonical_json_bytes,
    canonical_zip_bytes,
    parse_canonical_json,
    parse_strict_json,
    preflight_aggregate_compression_ratio,
    preflight_archive_member_sizes,
    preflight_glb,
    preflight_glb_counts,
    preflight_input_archive_size,
    preflight_member_compression_ratio,
    preflight_zip_bytes,
    profile_cross,
    profile_f32_bits,
    profile_normalize,
    validate_entity_asset,
    validate_connector_binding,
    validate_normalized_product,
    validate_presentation,
    validate_scene_manifest,
    validate_scene_package,
    json_resource_issues,
    resource_count_issues,
    with_scene_revision,
)
from simplecadapi.scene.validation import (
    _compute_package_budget_totals,
    _issue,
    _package_budget_issues,
    _report,
    _validate_rule_registry,
    load_contract_artifact,
)
from scene_contract_corpus_support import (
    apply_scene_field_case,
    corpus_blobs,
    scene_shape_facts,
)


IDENTITY = {
    "origin": [0, 0, 0],
    "x_axis": [1, 0, 0],
    "y_axis": [0, 1, 0],
    "z_axis": [0, 0, 1],
}
ASSET_TO_SCENE = [1000, 0, 0, 0, 0, 0, -1000, 0, 0, 1000, 0, 0, 0, 0, 0, 1]


def _f32(value):
    result = struct.unpack("<f", struct.pack("<f", value))[0]
    return 0.0 if result == 0 else result


def _normalize(vector):
    length = math.sqrt(sum(component * component for component in vector))
    return tuple(component / length for component in vector)


def _cross(left, right):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _frame(origin, x_axis):
    x_axis = _normalize(x_axis)
    seed = (0.0, 0.0, 1.0) if abs(x_axis[2]) < 0.9 else (0.0, 1.0, 0.0)
    projection = sum(left * right for left, right in zip(seed, x_axis))
    y_axis = _normalize(tuple(seed[index] - projection * x_axis[index] for index in range(3)))
    z_axis = _normalize(_cross(x_axis, y_axis))
    return {
        "origin": list(origin),
        "x_axis": list(x_axis),
        "y_axis": list(y_axis),
        "z_axis": list(z_axis),
    }


def _glb(kind, positions, indices, normals=None):
    positions = [tuple(_f32(component) for component in point) for point in positions]
    position_bytes = b"".join(struct.pack("<fff", *point) for point in positions)
    chunks = [position_bytes]
    views = [
        {"buffer": 0, "byteLength": len(position_bytes), "byteOffset": 0, "target": 34962}
    ]
    accessors = [
        {
            "bufferView": 0,
            "componentType": 5126,
            "count": len(positions),
            "max": [max(point[axis] for point in positions) for axis in range(3)],
            "min": [min(point[axis] for point in positions) for axis in range(3)],
            "type": "VEC3",
        }
    ]
    if kind == "triangle":
        assert normals is not None
        normals = [tuple(_f32(component) for component in vector) for vector in normals]
        normal_bytes = b"".join(struct.pack("<fff", *vector) for vector in normals)
        views.append(
            {
                "buffer": 0,
                "byteLength": len(normal_bytes),
                "byteOffset": len(position_bytes),
                "target": 34962,
            }
        )
        accessors.append(
            {
                "bufferView": 1,
                "componentType": 5126,
                "count": len(normals),
                "type": "VEC3",
            }
        )
        chunks.append(normal_bytes)
        index_view = 2
        attributes = {"NORMAL": 1, "POSITION": 0}
        mode = 4
    else:
        index_view = 1
        attributes = {"POSITION": 0}
        mode = 1
    prefix = b"".join(chunks)
    prefix += b"\0" * ((-len(prefix)) % 4)
    component_type = 5123 if len(positions) <= 65536 else 5125
    index_format = "H" if component_type == 5123 else "I"
    index_bytes = struct.pack("<" + index_format * len(indices), *indices)
    views.append(
        {
            "buffer": 0,
            "byteLength": len(index_bytes),
            "byteOffset": len(prefix),
            "target": 34963,
        }
    )
    accessors.append(
        {
            "bufferView": index_view,
            "componentType": component_type,
            "count": len(indices),
            "type": "SCALAR",
        }
    )
    unpadded_bin = prefix + index_bytes
    document = {
        "accessors": accessors,
        "asset": {"generator": "SimpleCAD Scene GLB Profile 1", "version": "2.0"},
        "bufferViews": views,
        "buffers": [{"byteLength": len(unpadded_bin)}],
        "meshes": [
            {"primitives": [{"attributes": attributes, "indices": index_view, "mode": mode}]}
        ],
        "nodes": [{"mesh": 0}],
        "scene": 0,
        "scenes": [{"nodes": [0]}],
    }
    json_bytes = canonical_json_bytes(document)
    json_chunk = json_bytes + b" " * ((-len(json_bytes)) % 4)
    bin_chunk = unpadded_bin + b"\0" * ((-len(unpadded_bin)) % 4)
    total_length = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    return b"".join(
        (
            struct.pack("<III", 0x46546C67, 2, total_length),
            struct.pack("<II", len(json_chunk), 0x4E4F534A),
            json_chunk,
            struct.pack("<II", len(bin_chunk), 0x004E4942),
            bin_chunk,
        )
    )


def _canonical_triangle_asset():
    points = {
        "a": (0.0, 0.0, 0.0),
        "b": (1.0, 0.0, 0.0),
        "c": (0.0, 1.0, 0.0),
        "d": (0.0, 0.0, 1.0),
    }
    oriented_faces = {
        "abc": ("a", "c", "b"),
        "abd": ("a", "b", "d"),
        "acd": ("a", "d", "c"),
        "bcd": ("b", "c", "d"),
    }
    blocks = []
    for name, corners in oriented_faces.items():
        a, b, c = (points[corner] for corner in corners)
        normal = _normalize(_cross(tuple(b[i] - a[i] for i in range(3)), tuple(c[i] - a[i] for i in range(3))))
        local_positions = sorted(
            (points[corner] for corner in corners), key=lambda point: struct.pack("<fff", *point)
        )
        remap = {point: index for index, point in enumerate(local_positions)}
        triple = tuple(remap[points[corner]] for corner in corners)
        rotations = (triple, triple[1:] + triple[:1], triple[2:] + triple[:2])
        triple = min(rotations)
        block = b"".join(
            struct.pack("<ffffff", *point, *normal) for point in local_positions
        ) + struct.pack("<HHH", *triple)
        blocks.append((hashlib.sha256(b"\x01" + block).digest(), block, name, local_positions, normal, triple))
    blocks.sort(key=lambda item: (item[0], item[1]))
    positions = []
    normals = []
    indices = []
    group_names = []
    for _render_key, _block, name, local_positions, normal, triple in blocks:
        offset = len(positions)
        positions.extend(local_positions)
        normals.extend([normal] * len(local_positions))
        indices.extend(offset + index for index in triple)
        group_names.append(name)
    return _glb("triangle", positions, indices, normals), group_names


def _canonical_line_asset():
    points = {
        "a": (0.0, 0.0, 0.0),
        "b": (1.0, 0.0, 0.0),
        "c": (0.0, 1.0, 0.0),
        "d": (0.0, 0.0, 1.0),
    }
    blocks = []
    for name in ("ab", "ac", "ad", "bc", "bd", "cd"):
        local_positions = sorted(
            (points[name[0]], points[name[1]]), key=lambda point: struct.pack("<fff", *point)
        )
        block = b"".join(struct.pack("<fff", *point) for point in local_positions)
        block += struct.pack("<HH", 0, 1)
        blocks.append((hashlib.sha256(b"\x02" + block).digest(), block, name, local_positions))
    blocks.sort(key=lambda item: (item[0], item[1]))
    positions = []
    indices = []
    group_names = []
    for _render_key, _block, name, local_positions in blocks:
        offset = len(positions)
        positions.extend(local_positions)
        indices.extend((offset, offset + 1))
        group_names.append(name)
    return _glb("line", positions, indices), group_names


def _entity(kind, index, parents, children, geometry, properties, frame, status):
    return {
        "child_entity_ids": sorted(children),
        "connector_binding_status": status,
        "entity_id": f"entity/{kind}/{index}",
        "evaluated_tags": [],
        "geometry": geometry,
        "kind": kind,
        "parent_entity_ids": sorted(parents),
        "properties": properties,
        "render_status": "rendered",
        "sdk_connector_frame": frame,
        "sdk_metadata": {},
        "semantic_binding_ids": [],
        "source": {"kind": "unbound"},
    }


def _build_scene_package():
    triangle_glb, face_order = _canonical_triangle_asset()
    line_glb, edge_order = _canonical_line_asset()
    geometry_hash = "sha256:" + hashlib.sha256(triangle_glb).hexdigest()
    edge_hash = "sha256:" + hashlib.sha256(line_glb).hexdigest()
    face_ids = {name: f"entity/face/{index}" for index, name in enumerate(face_order)}
    edge_ids = {name: f"entity/edge/{index}" for index, name in enumerate(edge_order)}
    vertex_ids = {name: f"entity/vertex/{index}" for index, name in enumerate("abcd")}
    cad_points = {
        "a": (0.0, 0.0, 0.0),
        "b": (1000.0, 0.0, 0.0),
        "c": (0.0, 0.0, 1000.0),
        "d": (0.0, -1000.0, 0.0),
    }
    face_vertices = {
        "abc": "abc",
        "abd": "abd",
        "acd": "acd",
        "bcd": "bcd",
    }
    face_edges = {
        "abc": ("ab", "ac", "bc"),
        "abd": ("ab", "ad", "bd"),
        "acd": ("ac", "ad", "cd"),
        "bcd": ("bc", "bd", "cd"),
    }
    edge_faces = {
        edge: tuple(name for name, edges in face_edges.items() if edge in edges)
        for edge in edge_order
    }
    vertex_edges = {
        vertex: tuple(edge for edge in edge_order if vertex in edge)
        for vertex in "abcd"
    }
    entities = []
    entities.append(
        _entity(
            "solid",
            0,
            [],
            list(face_ids.values()),
            {"type": "brep_solid"},
            {
                "bounds": {"max": [1000, 0, 1000], "min": [0, -1000, 0]},
                "centroid": [250, -250, 250],
                "quality": "kernel_evaluated",
                "surface_area": 1_500_000 + 500_000 * math.sqrt(3),
                "volume": 1_000_000_000 / 6,
            },
            None,
            "not_applicable",
        )
    )
    face_normals = {
        "abc": (0.0, 1.0, 0.0),
        "abd": (0.0, 0.0, -1.0),
        "acd": (-1.0, 0.0, 0.0),
        "bcd": _normalize((1.0, -1.0, 1.0)),
    }
    for name in face_order:
        vertices = [cad_points[vertex] for vertex in face_vertices[name]]
        minimum = [min(point[axis] for point in vertices) for axis in range(3)]
        maximum = [max(point[axis] for point in vertices) for axis in range(3)]
        centroid = [sum(point[axis] for point in vertices) / 3 for axis in range(3)]
        edge_vector = tuple(vertices[1][axis] - vertices[0][axis] for axis in range(3))
        frame = _frame(centroid, edge_vector)
        frame["z_axis"] = list(face_normals[name])
        frame["y_axis"] = list(_normalize(_cross(face_normals[name], frame["x_axis"])))
        entities.append(
            _entity(
                "face",
                int(face_ids[name].rsplit("/", 1)[1]),
                ["entity/solid/0"],
                [edge_ids[edge] for edge in face_edges[name]],
                {
                    "normal": list(face_normals[name]),
                    "origin": centroid,
                    "type": "plane",
                    "x_direction": frame["x_axis"],
                },
                {
                    "area": 500_000 * (math.sqrt(3) if name == "bcd" else 1),
                    "bounds": {"max": maximum, "min": minimum},
                    "centroid": centroid,
                    "orientation": "forward",
                    "quality": "kernel_evaluated",
                },
                frame,
                "owner_not_part",
            )
        )
    for name in edge_order:
        start, end = (cad_points[vertex] for vertex in name)
        direction = tuple(end[axis] - start[axis] for axis in range(3))
        midpoint = [(start[axis] + end[axis]) / 2 for axis in range(3)]
        minimum = [min(start[axis], end[axis]) for axis in range(3)]
        maximum = [max(start[axis], end[axis]) for axis in range(3)]
        entities.append(
            _entity(
                "edge",
                int(edge_ids[name].rsplit("/", 1)[1]),
                [face_ids[face] for face in edge_faces[name]],
                [vertex_ids[vertex] for vertex in name],
                {"direction": list(_normalize(direction)), "origin": list(start), "type": "line"},
                {
                    "bounds": {"max": maximum, "min": minimum},
                    "centroid": midpoint,
                    "length": math.sqrt(sum(component * component for component in direction)),
                    "quality": "kernel_evaluated",
                },
                _frame(midpoint, direction),
                "owner_not_part",
            )
        )
    for name in "abcd":
        point = cad_points[name]
        entities.append(
            _entity(
                "vertex",
                int(vertex_ids[name].rsplit("/", 1)[1]),
                [edge_ids[edge] for edge in vertex_edges[name]],
                [],
                {"position": list(point), "type": "point"},
                {
                    "bounds": {"max": list(point), "min": list(point)},
                    "position": list(point),
                    "quality": "kernel_evaluated",
                },
                {**IDENTITY, "origin": list(point)},
                "owner_not_part",
            )
        )
    definition_id = "definition/root/shape/manual/fixture"
    entity_asset = {
        "definition_id": definition_id,
        "edge_asset_id": edge_hash,
        "edge_groups": [
            {
                "entity_id": edge_ids[name],
                "first_index": 2 * index,
                "group_id": index,
                "index_count": 2,
                "mesh_index": 0,
                "primitive_index": 0,
            }
            for index, name in enumerate(edge_order)
        ],
        "entities": entities,
        "face_groups": [
            {
                "entity_id": face_ids[name],
                "first_index": 3 * index,
                "group_id": index,
                "index_count": 3,
                "mesh_index": 0,
                "primitive_index": 0,
            }
            for index, name in enumerate(face_order)
        ],
        "geometry_asset_id": geometry_hash,
        "geometry_engine": {
            "name": "OpenCascade",
            "profile": "ocp-evaluated-properties-1",
            "version": "fixture",
        },
        "schema_version": "1.0",
    }
    entity_asset["entities"].sort(key=lambda entity: entity["entity_id"].encode("utf-8"))
    entity_bytes = canonical_json_bytes(entity_asset)
    entity_hash = "sha256:" + hashlib.sha256(entity_bytes).hexdigest()
    appearance_draft = {
        "alpha_mode": "opaque",
        "base_color": [0.72, 0.75, 0.78, 1],
        "double_sided": False,
        "edge_color": [0.08, 0.09, 0.1, 1],
        "metallic": 0,
        "name": None,
        "roughness": 0.55,
        "sdk_metadata": {},
        "source": None,
    }
    appearance_id = "appearance/evaluated/" + hashlib.sha256(
        canonical_json_bytes(appearance_draft)
    ).hexdigest()
    appearance = {"appearance_id": appearance_id, **appearance_draft}
    geometry_uri = f"geometry/sha256-{geometry_hash.removeprefix('sha256:')}.glb"
    edge_uri = f"edges/sha256-{edge_hash.removeprefix('sha256:')}.glb"
    entity_uri = f"entities/sha256-{entity_hash.removeprefix('sha256:')}.json"
    bounds = {"max": [1000, 0, 1000], "min": [0, -1000, 0]}
    scene = with_scene_revision(
        {
            "annotations": [],
            "appearances": [appearance],
            "cameras": [],
            "compile_options": {
                "angular_tolerance": 0.22,
                "embed_presentation": False,
                "embed_source": False,
                "linear_tolerance": 0.35,
            },
            "connectors": [],
            "coordinate_system": {"handedness": "right", "length_unit": "mm", "up_axis": "+Z"},
            "definitions": [
                {
                    "appearance_id": appearance_id,
                    "definition_id": definition_id,
                    "edge_asset_id": edge_hash,
                    "entity_asset_id": entity_hash,
                    "geometry_asset_id": geometry_hash,
                    "kind": "shape",
                    "name": None,
                    "sdk_metadata": {},
                    "source": {"kind": "manual", "root_id": "root", "source_id": "fixture"},
                }
            ],
            "diagnostics": [],
            "edge_assets": [
                {
                    "asset_id": edge_hash,
                    "asset_to_scene": ASSET_TO_SCENE,
                    "byte_length": len(line_glb),
                    "content_hash": edge_hash,
                    "media_type": "model/gltf-binary",
                    "scene_local_bounds": bounds,
                    "tessellation": {"linear_tolerance": 0.35},
                    "uri": edge_uri,
                }
            ],
            "entity_assets": [
                {
                    "byte_length": len(entity_bytes),
                    "content_hash": entity_hash,
                    "entity_asset_id": entity_hash,
                    "media_type": "application/vnd.simplecad.entities+json",
                    "uri": entity_uri,
                }
            ],
            "extensions": {},
            "extensions_required": [],
            "extensions_used": [],
            "generator": {
                "name": "simplecadapi",
                "ocp_bindings_version": "fixture",
                "ocp_version": "fixture",
                "platform_tag": "fixture",
                "profile": "scene-1.0-ocp-glb-2",
                "python_abi": "fixture",
                "simplecadapi_version": "fixture",
                "toolchain_hash": "sha256:" + "0" * 64,
            },
            "geometry_assets": [
                {
                    "asset_id": geometry_hash,
                    "asset_to_scene": ASSET_TO_SCENE,
                    "byte_length": len(triangle_glb),
                    "content_hash": geometry_hash,
                    "media_type": "model/gltf-binary",
                    "scene_local_bounds": bounds,
                    "tessellation": {"angular_tolerance": 0.22, "linear_tolerance": 0.35},
                    "uri": geometry_uri,
                }
            ],
            "lights": [],
            "nodes": [
                {
                    "appearance_override_id": None,
                    "definition_id": definition_id,
                    "name": None,
                    "node_id": "instance/root",
                    "order": 0,
                    "parent_node_id": None,
                    "sdk_metadata": {},
                    "selectable": True,
                    "source": {"kind": "shape_root", "root_id": "root"},
                    "transform": IDENTITY,
                    "visible": True,
                }
            ],
            "scene_id": "fixture",
            "schema_version": "1.0",
            "source": {"kind": "manual", "source_id": "fixture"},
        }
    )
    scene_bytes = canonical_json_bytes(scene)
    blobs = {geometry_uri: triangle_glb, edge_uri: line_glb, entity_uri: entity_bytes}
    return scene, scene_bytes, entity_asset, entity_bytes, blobs


def _attach_presentation(scene, blobs):
    presentation = {
        "appearances": [
            {
                "alpha_mode": "opaque",
                "base_color": [1, 0.5, 0.1, 1],
                "double_sided": False,
                "edge_color": [0.1, 0.05, 0, 1],
                "metallic": 0,
                "name": "Highlight",
                "roughness": 0.4,
            }
        ],
        "cameras": [
            {
                "far": 10000,
                "name": "Overview",
                "near": 1,
                "parent_node_id": "instance/root",
                "projection": "perspective",
                "transform": IDENTITY,
                "vertical_fov_degrees": 45,
            }
        ],
        "node_overrides": [
            {
                "appearance_name": "Highlight",
                "node_id": "instance/root",
                "visible": False,
            }
        ],
        "presentation_id": "fixture-presentation",
        "schema_version": "1.0",
        "source_scene_id": scene["scene_id"],
    }
    authored = presentation["appearances"][0]
    evaluated_draft = {
        "alpha_mode": authored["alpha_mode"],
        "base_color": authored["base_color"],
        "double_sided": authored["double_sided"],
        "edge_color": authored["edge_color"],
        "metallic": authored["metallic"],
        "name": authored["name"],
        "roughness": authored["roughness"],
        "sdk_metadata": {},
        "source": {
            "appearance_name": authored["name"],
            "kind": "presentation",
            "presentation_id": presentation["presentation_id"],
        },
    }
    appearance_id = "appearance/evaluated/" + hashlib.sha256(
        canonical_json_bytes(evaluated_draft)
    ).hexdigest()
    scene["appearances"].append({"appearance_id": appearance_id, **evaluated_draft})
    scene["appearances"].sort(key=lambda appearance: appearance["appearance_id"].encode("utf-8"))
    scene["nodes"][0]["visible"] = False
    scene["nodes"][0]["appearance_override_id"] = appearance_id
    scene["cameras"] = [
        {"camera_id": "camera/fixture-presentation/Overview", **presentation["cameras"][0]}
    ]
    presentation_bytes = canonical_json_bytes(presentation)
    scene["compile_options"]["embed_presentation"] = True
    scene["presentation_source"] = {
        "artifact_hash": "sha256:" + hashlib.sha256(presentation_bytes).hexdigest(),
        "embedded_artifact_byte_length": len(presentation_bytes),
        "embedded_artifact_uri": "presentation/presentation.json",
        "presentation_id": presentation["presentation_id"],
        "schema_version": "1.0",
    }
    scene = with_scene_revision(scene)
    blobs = dict(blobs)
    blobs["presentation/presentation.json"] = presentation_bytes
    return scene, presentation, blobs


def _replace_embedded_presentation(scene, blobs, payload):
    scene["presentation_source"]["artifact_hash"] = (
        "sha256:" + hashlib.sha256(payload).hexdigest()
    )
    scene["presentation_source"]["embedded_artifact_byte_length"] = len(payload)
    scene = with_scene_revision(scene)
    blobs = dict(blobs)
    blobs["presentation/presentation.json"] = payload
    return scene, blobs


def _codes(report):
    return [issue.code for issue in report.issues]


def _load_shared_corpus():
    path = Path(__file__).parent / "fixtures" / "scene-contract" / "corpus.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_generated_python_scene_contract_types_are_current():
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[1] / "tools/generate_scene_contract_types.py"),
            "--check",
            "--language",
            "python",
        ],
        cwd=Path(__file__).parents[1],
        check=True,
    )


def _decode_base64(value):
    return base64.b64decode(value, validate=True)


def _f64_from_hex(value):
    return struct.unpack(">d", bytes.fromhex(value))[0]


def _f64_hex(value):
    return struct.pack(">d", value).hex()


def _first_report_issue(report):
    issue = report.first_error
    return None if issue is None else {"code": issue.code, "path": issue.path}


def _replace_glb_json(glb, mutate):
    json_length = struct.unpack_from("<I", glb, 12)[0]
    document = parse_strict_json(glb[20 : 20 + json_length].rstrip(b" "))
    mutate(document)
    replacement = canonical_json_bytes(document)
    replacement += b" " * ((-len(replacement)) % 4)
    bin_header = 20 + json_length
    bin_chunk = glb[bin_header:]
    result = b"".join(
        (
            struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(replacement) + len(bin_chunk)),
            struct.pack("<II", len(replacement), 0x4E4F534A),
            replacement,
            bin_chunk,
        )
    )
    return result


def _declared_deflate_zip(compressed, uncompressed_size, *, local_uncompressed_size=None):
    name = b"scene.json"
    if local_uncompressed_size is None:
        local_uncompressed_size = uncompressed_size
    local = struct.pack(
        "<IHHHHHIIIHH",
        0x04034B50,
        20,
        0x0800,
        8,
        0,
        0x0021,
        0,
        len(compressed),
        local_uncompressed_size,
        len(name),
        0,
    )
    central_offset = len(local) + len(name) + len(compressed)
    central = struct.pack(
        "<IHHHHHHIIIHHHHHII",
        0x02014B50,
        0x0314,
        20,
        0x0800,
        8,
        0,
        0x0021,
        0,
        len(compressed),
        uncompressed_size,
        len(name),
        0,
        0,
        0,
        0,
        0x81A40000,
        0,
    ) + name
    eocd = struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        1,
        1,
        len(central),
        central_offset,
        0,
    )
    return local + name + compressed + central + eocd


def test_strict_and_canonical_json_reject_ambiguous_encodings():
    with pytest.raises(ValueError, match="duplicate"):
        parse_strict_json(b'{"a":1,"a":2}')
    with pytest.raises(ValueError, match="BOM"):
        parse_strict_json(b"\xef\xbb\xbf{}")
    with pytest.raises(ValueError, match="canonical"):
        parse_canonical_json(b'{"b":1, "a":2}')
    with pytest.raises(ValueError, match="surrogate"):
        parse_strict_json(b'{"value":"\\ud800"}')
    with pytest.raises(ValueError, match="surrogate"):
        parse_strict_json(b'{"\\ud800":0}')


def test_packaged_contract_artifacts_validate_and_link_exact_pseudocode_hashes():
    schema_paths = [
        "schemas/scene-1.0.schema.json",
        "schemas/entities-1.0.schema.json",
        "schemas/presentation-1.0.schema.json",
        "schemas/connector-binding-1.0.schema.json",
        "schemas/normalized-product-1.schema.json",
        "schemas/rules-1.schema.json",
        "schemas/profile-1.schema.json",
        "schemas/render-profile-2.schema.json",
        "schemas/evaluated-properties-profile-1.schema.json",
    ]
    schemas = {
        path: parse_strict_json(load_contract_artifact(path)) for path in schema_paths
    }
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    rules_schema = parse_strict_json(load_contract_artifact("schemas/rules-1.schema.json"))
    Draft202012Validator(rules_schema).validate(
        parse_strict_json(load_contract_artifact("rules/scene-1.0-rules.json"))
    )
    profile_schemas = {
        "render_asset": schemas["schemas/render-profile-2.schema.json"],
        "evaluated_properties": schemas[
            "schemas/evaluated-properties-profile-1.schema.json"
        ],
    }
    registry = Registry().with_resources(
        (
            schema["$id"],
            Resource.from_contents(schema, default_specification=DRAFT202012),
        )
        for schema in profile_schemas.values()
    )
    dispatcher = Draft202012Validator(
        schemas["schemas/profile-1.schema.json"], registry=registry
    )
    profile_cases = (
        (
            "profiles/scene-1.0-ocp-glb-2.profile.json",
            "scene-1.0-ocp-glb-2",
            "render_asset",
        ),
        (
            "profiles/ocp-evaluated-properties-1.profile.json",
            "ocp-evaluated-properties-1",
            "evaluated_properties",
        ),
    )
    for path, profile_id, profile_kind in profile_cases:
        profile = parse_strict_json(load_contract_artifact(path))
        applicable = Draft202012Validator(profile_schemas[profile_kind])
        other_kind = next(kind for kind in profile_schemas if kind != profile_kind)

        assert profile["profile_id"] == profile_id
        assert profile["profile_kind"] == profile_kind
        applicable.validate(profile)
        dispatcher.validate(profile)
        assert not Draft202012Validator(profile_schemas[other_kind]).is_valid(profile)

        unknown_nested = deepcopy(profile)
        unknown_nested["rules"]["implementation_status"]["unknown"] = True
        assert not applicable.is_valid(unknown_nested)
        assert not dispatcher.is_valid(unknown_nested)

        deeply_unknown = deepcopy(profile)
        if profile_kind == "render_asset":
            deeply_unknown["rules"]["default_appearance"]["unknown"] = True
        else:
            deeply_unknown["rules"]["canonical_labeling"]["unknown"] = True
        assert not applicable.is_valid(deeply_unknown)
        assert not dispatcher.is_valid(deeply_unknown)

        wrong_id = deepcopy(profile)
        wrong_id["profile_id"] = "wrong-profile"
        assert not applicable.is_valid(wrong_id)
        assert not dispatcher.is_valid(wrong_id)

        wrong_kind = deepcopy(profile)
        wrong_kind["profile_kind"] = other_kind
        assert not applicable.is_valid(wrong_kind)
        assert not dispatcher.is_valid(wrong_kind)

        pseudocode = load_contract_artifact(profile["pseudocode_uri"])
        assert profile["pseudocode_hash"] == "sha256:" + hashlib.sha256(pseudocode).hexdigest()


def test_rule_registry_rejects_schema_and_ordering_invariant_violations():
    schema = parse_strict_json(load_contract_artifact("schemas/rules-1.schema.json"))
    registry = parse_strict_json(load_contract_artifact("rules/scene-1.0-rules.json"))
    assert set(_validate_rule_registry(registry, schema)) == {
        rule["id"] for rule in registry["rules"]
    }

    missing_precedence = deepcopy(registry)
    missing_precedence["rules"][0].pop("precedence")
    with pytest.raises(ValueError, match="precedence"):
        _validate_rule_registry(missing_precedence, schema)

    duplicate_id = deepcopy(registry)
    duplicate_id["rules"][1]["id"] = duplicate_id["rules"][0]["id"]
    with pytest.raises(ValueError, match="duplicate rule ID"):
        _validate_rule_registry(duplicate_id, schema)

    duplicate_precedence = deepcopy(registry)
    duplicate_precedence["rules"][1]["precedence"] = 0
    with pytest.raises(ValueError, match="duplicate precedence"):
        _validate_rule_registry(duplicate_precedence, schema)

    wrong_order = deepcopy(registry)
    wrong_order["rules"][0], wrong_order["rules"][1] = (
        wrong_order["rules"][1],
        wrong_order["rules"][0],
    )
    with pytest.raises(ValueError, match="ordered by phase and precedence"):
        _validate_rule_registry(wrong_order, schema)

    wrong_id_order = deepcopy(registry)
    wrong_id_order["rules"][0]["id"], wrong_id_order["rules"][1]["id"] = (
        wrong_id_order["rules"][1]["id"],
        wrong_id_order["rules"][0]["id"],
    )
    with pytest.raises(ValueError, match="unsigned UTF-8 rule-ID order"):
        _validate_rule_registry(wrong_id_order, schema)


def test_rule_registry_controls_reports_and_closes_issue_authority():
    report = _report(
        [
            _issue("transform_invalid", "/z", "later registered rule"),
            _issue("bounds_invalid", "/z", "z message"),
            _issue("bounds_invalid", "/z", "a message"),
            _issue("bounds_invalid", "/a", "earlier pointer"),
        ],
        artifact="scene",
    )
    assert [(issue.code, issue.path, issue.message) for issue in report.issues] == [
        ("bounds_invalid", "/a", "earlier pointer"),
        ("bounds_invalid", "/z", "a message"),
        ("bounds_invalid", "/z", "z message"),
        ("transform_invalid", "/z", "later registered rule"),
    ]

    with pytest.raises(ValueError, match="unregistered"):
        _report([_issue("not_registered", "", "no authority")], artifact="scene")
    with pytest.raises(ValueError, match="registered phase"):
        _report(
            [_issue("bounds_invalid", "", "wrong phase", "package")],
            artifact="scene",
        )
    with pytest.raises(ValueError, match="does not apply"):
        _report(
            [_issue("presentation_reference_invalid", "", "wrong artifact")],
            artifact="scene",
        )
    with pytest.raises(ValueError, match="root pointer"):
        _report(
            [_issue("duplicate_json_key", "/value", "wrong pointer", "parse")],
            artifact="scene",
        )


def test_valid_tetrahedron_scene_package_and_canonical_zip_round_trip():
    scene, scene_bytes, entity_asset, entity_bytes, blobs = _build_scene_package()

    assert validate_scene_manifest(scene).valid
    assert validate_scene_manifest(scene_bytes).valid
    assert validate_entity_asset(entity_asset).valid
    assert validate_entity_asset(entity_bytes).valid
    assert validate_scene_package(scene_bytes, blobs).valid
    assert {preflight_glb(payload).kind for uri, payload in blobs.items() if uri.endswith(".glb")} == {
        "triangle",
        "line",
    }

    archive_bytes = canonical_zip_bytes({"scene.json": scene_bytes, **blobs})
    archive = preflight_zip_bytes(archive_bytes)
    assert archive.input_size == archive.canonical_size == len(archive_bytes)
    assert not archive.used_deflate
    assert dict(archive.members) == {"scene.json": scene_bytes, **blobs}
    assert canonical_zip_bytes(archive.members) == archive_bytes
    assert validate_scene_package(
        archive.members["scene.json"],
        {name: payload for name, payload in archive.members.items() if name != "scene.json"},
    ).valid


def test_embedded_presentation_is_canonical_and_resolves_exactly_against_scene():
    scene, _scene_bytes, _entity_asset, _entity_bytes, blobs = _build_scene_package()
    scene, presentation, blobs = _attach_presentation(scene, blobs)

    assert validate_scene_package(canonical_json_bytes(scene), blobs).valid

    noncanonical = json.dumps(presentation, indent=2, sort_keys=True).encode("utf-8")
    scene, blobs = _replace_embedded_presentation(scene, blobs, noncanonical)
    report = validate_scene_package(canonical_json_bytes(scene), blobs)
    assert report.first_error is not None
    assert (report.first_error.code, report.first_error.path) == (
        "noncanonical_json",
        "",
    )


@pytest.mark.parametrize(
    ("mutate", "code", "path"),
    [
        (
            lambda presentation: presentation.__setitem__("presentation_id", "other"),
            "source_matrix_invalid",
            "/presentation/presentation.json/presentation_id",
        ),
        (
            lambda presentation: presentation.__setitem__("source_scene_id", "other"),
            "source_matrix_invalid",
            "/presentation/presentation.json/source_scene_id",
        ),
        (
            lambda presentation: presentation["node_overrides"][0].__setitem__(
                "node_id", "instance/missing"
            ),
            "source_matrix_invalid",
            "/presentation/presentation.json/node_overrides/0/node_id",
        ),
        (
            lambda presentation: presentation["cameras"][0].__setitem__(
                "parent_node_id", "instance/missing"
            ),
            "source_matrix_invalid",
            "/presentation/presentation.json/cameras/0/parent_node_id",
        ),
    ],
)
def test_embedded_presentation_ids_and_scene_references_are_contextual(
    mutate, code, path
):
    scene, _scene_bytes, _entity_asset, _entity_bytes, blobs = _build_scene_package()
    scene, presentation, blobs = _attach_presentation(scene, blobs)
    mutate(presentation)
    scene, blobs = _replace_embedded_presentation(
        scene, blobs, canonical_json_bytes(presentation)
    )

    report = validate_scene_package(canonical_json_bytes(scene), blobs)

    assert any(issue.code == code and issue.path == path for issue in report.issues)


def test_embedded_presentation_appearance_and_camera_resolution_is_exact():
    scene, _scene_bytes, _entity_asset, _entity_bytes, blobs = _build_scene_package()
    scene, _presentation, blobs = _attach_presentation(scene, blobs)
    presentation_appearance = next(
        appearance
        for appearance in scene["appearances"]
        if isinstance(appearance["source"], dict)
    )
    presentation_appearance["source"]["appearance_name"] = "Other"
    draft = dict(presentation_appearance)
    draft.pop("appearance_id")
    new_id = "appearance/evaluated/" + hashlib.sha256(
        canonical_json_bytes(draft)
    ).hexdigest()
    presentation_appearance["appearance_id"] = new_id
    scene["nodes"][0]["appearance_override_id"] = new_id
    scene["appearances"].sort(key=lambda appearance: appearance["appearance_id"].encode("utf-8"))
    scene["cameras"] = []
    scene = with_scene_revision(scene)

    report = validate_scene_package(canonical_json_bytes(scene), blobs)

    appearance_index = scene["appearances"].index(presentation_appearance)
    assert any(
        issue.code == "source_matrix_invalid"
        and issue.path == f"/appearances/{appearance_index}/source/appearance_name"
        for issue in report.issues
    )
    assert any(
        issue.code == "source_matrix_invalid"
        and issue.path == "/presentation/presentation.json/cameras/0"
        for issue in report.issues
    )


def test_product_material_appearance_provenance_must_match_a_part_root():
    scene, _scene_bytes, _entity_asset, _entity_bytes, _blobs = _build_scene_package()
    appearance = scene["appearances"][0]
    appearance["source"] = {
        "kind": "product_material",
        "material_id": "steel",
        "root_id": "other",
    }
    draft = dict(appearance)
    draft.pop("appearance_id")
    appearance_id = "appearance/evaluated/" + hashlib.sha256(
        canonical_json_bytes(draft)
    ).hexdigest()
    appearance["appearance_id"] = appearance_id
    scene["definitions"][0]["appearance_id"] = appearance_id
    scene = with_scene_revision(scene)

    report = validate_scene_manifest(scene)

    assert any(
        issue.code == "source_matrix_invalid"
        and issue.path == "/appearances/0/source/root_id"
        for issue in report.issues
    )


def test_package_rejects_conflicting_records_for_one_uri_and_dispatches_by_role():
    scene, _scene_bytes, _entity_asset, _entity_bytes, blobs = _build_scene_package()
    edge_uri = scene["edge_assets"][0]["uri"]
    scene["edge_assets"][0]["uri"] = scene["geometry_assets"][0]["uri"]
    scene = with_scene_revision(scene)
    blobs = dict(blobs)
    blobs.pop(edge_uri)

    report = validate_scene_package(canonical_json_bytes(scene), blobs)

    assert any(issue.code == "package_member_set_invalid" for issue in report.issues)
    assert any(
        issue.code == "source_matrix_invalid" and issue.path == "/edge_assets/0/uri"
        for issue in report.issues
    )


def test_package_budget_formula_and_first_error_use_declarative_limits():
    totals = _compute_package_budget_totals(
        scene_json_bytes=7,
        glb_decoded_buffer_bytes=11,
        entity_json_bytes=13,
        other_immutable_json_bytes=17,
        entity_count=23,
        entity_vertex_count=19,
        triangle_vertex_count=29,
        triangle_count=31,
        line_vertex_count=37,
        line_segment_count=41,
    )
    assert totals == {
        "static_decoded_buffer_bytes": 656,
        "entity_count": 23,
        "triangle_vertex_total": 29,
        "triangle_total": 31,
        "line_vertex_total": 37,
        "line_segment_total": 41,
    }
    exact = SimpleNamespace(
        static_decoded_buffer_bytes=656,
        entities_total=23,
        triangle_vertices_total=29,
        triangles_total=31,
        line_vertices_total=37,
        line_segments_total=41,
    )
    assert not _package_budget_issues(totals, limits=exact)

    over_every_limit = SimpleNamespace(
        static_decoded_buffer_bytes=655,
        entities_total=22,
        triangle_vertices_total=28,
        triangles_total=30,
        line_vertices_total=36,
        line_segments_total=40,
    )
    report = _report(
        _package_budget_issues(totals, limits=over_every_limit), artifact="package"
    )
    assert report.first_error is not None
    assert (
        report.first_error.code,
        report.first_error.path,
        report.first_error.message,
    ) == (
        "resource_limit_exceeded",
        "",
        "total line GLB vertex count exceeds resource limit",
    )


@pytest.mark.parametrize("value", [None, [], {"definitions": 1}, {"nodes": 1}, {"entities": 1}])
def test_structurally_invalid_values_return_reports_instead_of_raising(value):
    assert not validate_scene_manifest(value).valid
    assert not validate_entity_asset(value).valid


def test_asset_bearing_scene_requires_a_root_occurrence():
    scene, _scene_bytes, _entity_asset, _entity_bytes, _blobs = _build_scene_package()
    scene["nodes"] = []
    scene = with_scene_revision(scene)

    report = validate_scene_manifest(scene)

    assert "hierarchy_invalid" in _codes(report)


def test_package_rejects_manifest_bounds_that_differ_from_glb():
    scene, _scene_bytes, _entity_asset, _entity_bytes, blobs = _build_scene_package()
    scene["geometry_assets"][0]["scene_local_bounds"]["max"][0] = 999
    scene = with_scene_revision(scene)

    report = validate_scene_package(canonical_json_bytes(scene), blobs)

    assert "bounds_invalid" in _codes(report)


def test_glb_rejects_json_strings_and_booleans_in_numeric_fields():
    _scene, _scene_bytes, _entity_asset, _entity_bytes, blobs = _build_scene_package()
    triangle = next(payload for uri, payload in blobs.items() if uri.startswith("geometry/"))
    string_bounds = _replace_glb_json(
        triangle, lambda document: document["accessors"][0]["min"].__setitem__(0, "0")
    )
    boolean_scene = _replace_glb_json(triangle, lambda document: document.__setitem__("scene", False))

    with pytest.raises(ValueError, match="three-number"):
        preflight_glb(string_bounds)
    with pytest.raises(ValueError, match="non-negative safe integer"):
        preflight_glb(boolean_scene)


def test_entity_asset_rejects_sparse_ids_and_non_unit_analytic_directions():
    _scene, _scene_bytes, entity_asset, _entity_bytes, _blobs = _build_scene_package()
    sparse = deepcopy(entity_asset)
    sparse["entities"][0]["entity_id"] = "entity/edge/99"
    non_unit = deepcopy(entity_asset)
    edge = next(entity for entity in non_unit["entities"] if entity["kind"] == "edge")
    edge["geometry"]["direction"] = [2, 0, 0]

    assert "entity_topology_invalid" in _codes(validate_entity_asset(sparse))
    assert "analytic_geometry_invalid" in _codes(validate_entity_asset(non_unit))


def test_package_enforces_contextual_entity_binding_status():
    scene, _scene_bytes, entity_asset, _entity_bytes, blobs = _build_scene_package()
    face = next(entity for entity in entity_asset["entities"] if entity["kind"] == "face")
    face["connector_binding_status"] = "supported"
    entity_bytes = canonical_json_bytes(entity_asset)
    old_uri = scene["entity_assets"][0]["uri"]
    entity_hash = "sha256:" + hashlib.sha256(entity_bytes).hexdigest()
    entity_uri = f"entities/sha256-{entity_hash.removeprefix('sha256:')}.json"
    scene["entity_assets"][0].update(
        {
            "byte_length": len(entity_bytes),
            "content_hash": entity_hash,
            "entity_asset_id": entity_hash,
            "uri": entity_uri,
        }
    )
    scene["definitions"][0]["entity_asset_id"] = entity_hash
    scene = with_scene_revision(scene)
    blobs = {uri: payload for uri, payload in blobs.items() if uri != old_uri}
    blobs[entity_uri] = entity_bytes

    report = validate_scene_package(canonical_json_bytes(scene), blobs)

    assert "connector_invalid" in _codes(report)


def test_deep_python_value_returns_a_budget_report_without_recursion_error():
    value = {}
    current = value
    for _index in range(1000):
        child = {}
        current["x"] = child
        current = child

    report = validate_scene_manifest(value)

    assert report.first_error is not None
    assert report.first_error.code == "resource_limit_exceeded"


def test_public_validator_resource_overflows_remain_budget_issues():
    scene, scene_bytes, _entity_asset, _entity_bytes, _blobs = _build_scene_package()
    collection_report = validate_scene_manifest(
        scene, limits=replace(BASE_LIMITS, definitions=0)
    )
    serialized_report = validate_scene_manifest(
        scene, limits=replace(BASE_LIMITS, scene_json_bytes=len(scene_bytes) - 1)
    )

    assert collection_report.first_error is not None
    assert (
        collection_report.first_error.code,
        collection_report.first_error.phase,
        collection_report.first_error.path,
    ) == ("resource_limit_exceeded", "budget", "/definitions")
    assert serialized_report.first_error is not None
    assert (
        serialized_report.first_error.code,
        serialized_report.first_error.phase,
        serialized_report.first_error.path,
    ) == ("resource_limit_exceeded", "budget", "")


def test_zip_preflight_rejects_crc_mutation_and_trailing_data():
    _scene, scene_bytes, _entity_asset, _entity_bytes, blobs = _build_scene_package()
    archive = canonical_zip_bytes({"scene.json": scene_bytes, **blobs})
    corrupted = bytearray(archive)
    first_payload = 30 + struct.unpack_from("<H", archive, 26)[0]
    corrupted[first_payload] ^= 1

    with pytest.raises(ValueError, match="CRC"):
        preflight_zip_bytes(corrupted)
    with pytest.raises(ValueError, match="EOCD"):
        preflight_zip_bytes(archive + b"x")


def test_zip_preflight_checks_aggregate_ratio_boundary_before_inflate(monkeypatch):
    compressed = b"\0"
    template = _declared_deflate_zip(compressed, 0)
    exact_size = len(template) * BASE_LIMITS.compression_ratio

    def fail_inflate(*_args, **_kwargs):
        raise AssertionError("inflate must not run before ratio preflight")

    monkeypatch.setattr(scene_archive.zlib, "decompressobj", fail_inflate)
    with pytest.raises(
        ValueError,
        match=r'^member compression ratio exceeds limit: "scene\.json"$',
    ):
        preflight_zip_bytes(_declared_deflate_zip(compressed, exact_size))
    with pytest.raises(ValueError, match="^aggregate compression ratio exceeds limit$"):
        preflight_zip_bytes(_declared_deflate_zip(compressed, exact_size + 1))
    with pytest.raises(ValueError, match="^ZIP central/local header mismatch$"):
        preflight_zip_bytes(
            _declared_deflate_zip(
                compressed,
                exact_size + 1,
                local_uncompressed_size=exact_size,
            )
        )


def test_zip_preflight_zero_compressed_size_uses_one_for_member_ratio():
    with pytest.raises(ValueError, match=r'^invalid deflate stream: "scene\.json"$'):
        preflight_zip_bytes(
            _declared_deflate_zip(b"", BASE_LIMITS.compression_ratio)
        )
    with pytest.raises(
        ValueError,
        match=r'^member compression ratio exceeds limit: "scene\.json"$',
    ):
        preflight_zip_bytes(
            _declared_deflate_zip(b"", BASE_LIMITS.compression_ratio + 1)
        )


def test_python_matches_all_shared_manifest_and_entity_cases():
    corpus = _load_shared_corpus()
    validators = (
        (corpus["manifest_cases"], validate_scene_manifest),
        (corpus["entity_cases"], validate_entity_asset),
        (corpus["presentation_cases"], validate_presentation),
        (corpus["connector_binding_cases"], validate_connector_binding),
        (corpus["normalized_product_cases"], validate_normalized_product),
    )
    for cases, validator in validators:
        for case in cases:
            report = validator(_decode_base64(case["payload_base64"]))
            assert report.valid is case["valid"], case["name"]
            if case["expected"] is not None:
                assert report.first_error is not None
                assert {
                    "code": report.first_error.code,
                    "path": report.first_error.path,
                } == case["expected"], case["name"]


def test_shared_positive_case_names_cannot_drift_to_negative_expectations():
    corpus = _load_shared_corpus()
    positive_names = []
    for section_name, cases in corpus.items():
        if not isinstance(cases, list):
            continue
        for case in cases:
            if not isinstance(case, dict):
                continue
            name = case.get("name")
            if not isinstance(name, str) or not (
                name.startswith("valid_") or name == "nullable_fields_nonnull"
            ):
                continue
            positive_names.append(f"{section_name}:{name}")
            assert case["valid"] is True, positive_names[-1]
            if "expected" in case:
                assert case["expected"] is None, positive_names[-1]
            if "error" in case:
                assert case["error"] is None, positive_names[-1]
    assert len(positive_names) == 30


def test_accepted_package_fixtures_cover_every_connector_binding_status():
    corpus = _load_shared_corpus()
    statuses = set()
    for case in (*corpus["package_cases"], *corpus["scene_shape_cases"]):
        if not case["valid"]:
            continue
        for uri, payload in corpus_blobs(corpus, case).items():
            if not uri.startswith("entities/"):
                continue
            sidecar = parse_canonical_json(payload)
            statuses.update(
                entity["connector_binding_status"]
                for entity in sidecar["entities"]
            )
    assert statuses == {
        "not_applicable",
        "owner_not_part",
        "source_not_model",
        "frame_undefined",
        "selector_ambiguous",
        "selector_unstable",
        "supported",
    }


def test_python_matches_all_shared_package_cases():
    corpus = _load_shared_corpus()
    precedence_statuses = {
        "solid_status_precedence": "not_applicable",
        "owner_not_part_status_precedence": "owner_not_part",
        "source_not_model_status_precedence": "source_not_model",
        "frame_undefined_status_precedence": "frame_undefined",
    }
    for case in corpus["package_cases"]:
        blobs = corpus_blobs(corpus, case)
        report = validate_scene_package(_decode_base64(case["manifest_base64"]), blobs)
        assert report.valid is case["valid"], case["name"]
        if case["expected"] is not None:
            assert report.first_error is not None
            assert {
                "code": report.first_error.code,
                "path": report.first_error.path,
            } == case["expected"], case["name"]
        expected_status = precedence_statuses.get(case["name"])
        if expected_status is not None:
            assert report.first_error is not None
            assert report.first_error.message == (
                f"connector binding status must be {expected_status}"
            )


def test_python_replays_shared_scene_field_matrix():
    corpus = _load_shared_corpus()
    scene = parse_canonical_json(_decode_base64(corpus["artifacts"]["scene"]["base64"]))
    for case in corpus["scene_field_cases"]:
        value = apply_scene_field_case(scene, case)
        report = validate_scene_manifest(canonical_json_bytes(value))
        assert report.valid is case["valid"], case["name"]
        assert _first_report_issue(report) == case["expected"], case["name"]


def test_python_characterizes_shared_scene_shapes_and_asset_reuse():
    corpus = _load_shared_corpus()
    for case in corpus["scene_shape_cases"]:
        manifest = _decode_base64(case["manifest_base64"])
        scene = parse_canonical_json(manifest)
        report = validate_scene_package(manifest, corpus_blobs(corpus, case))
        assert report.valid is case["valid"], case["name"]
        assert _first_report_issue(report) == case["expected"], case["name"]
        assert canonical_json_bytes(scene) == manifest, case["name"]
        assert scene_shape_facts(scene) == case["expected_shape"], case["name"]

        definitions = {item["definition_id"]: item for item in scene["definitions"]}
        for definition_id, count in case["expected_shape"][
            "definition_occurrence_counts"
        ].items():
            if count > 1:
                occurrences = [
                    node for node in scene["nodes"] if node["definition_id"] == definition_id
                ]
                assert len(occurrences) == count
                assert len({node["definition_id"] for node in occurrences}) == 1
                assert definitions[definition_id]["geometry_asset_id"] is not None


def test_python_matches_shared_two_pass_revision_vectors():
    for vector in _load_shared_corpus()["revision_vectors"]:
        draft_bytes = _decode_base64(vector["draft_base64"])
        draft = parse_canonical_json(draft_bytes)
        scene_bytes = _decode_base64(vector["canonical_base64"])
        scene = with_scene_revision(draft)

        assert canonical_json_bytes(draft) == draft_bytes, vector["name"]
        assert scene["revision"] == vector["revision"], vector["name"]
        assert canonical_json_bytes(scene) == scene_bytes, vector["name"]
        assert "sha256:" + hashlib.sha256(scene_bytes).hexdigest() == vector["sha256"]


def test_python_matches_all_shared_glb_and_zip_cases():
    corpus = _load_shared_corpus()
    for case in corpus["glb_cases"]:
        payload = _decode_base64(case["payload_base64"])
        if case["valid"]:
            assert preflight_glb(payload, expected_kind=case["expected_kind"]).kind == case["kind"]
        else:
            with pytest.raises(ValueError, match="^" + re.escape(case["error"]) + "$"):
                preflight_glb(payload, expected_kind=case["expected_kind"])
    for case in corpus["zip_cases"]:
        payload = _decode_base64(case["payload_base64"])
        if case["valid"]:
            assert preflight_zip_bytes(payload).used_deflate is case["used_deflate"]
        else:
            with pytest.raises(ValueError, match="^" + re.escape(case["error"]) + "$"):
                preflight_zip_bytes(payload)


def test_python_matches_shared_numeric_profile_vectors():
    for vector in _load_shared_corpus()["numeric_vectors"]:
        try:
            if vector["operation"] == "f32":
                actual = f"{profile_f32_bits(_f64_from_hex(vector['input_bits'][0])):08x}"
            elif vector["operation"] == "cross":
                left, right = (
                    tuple(_f64_from_hex(component) for component in value)
                    for value in vector["input_bits"]
                )
                actual = [_f64_hex(component) for component in profile_cross(left, right)]
            elif vector["operation"] == "normalize":
                value = tuple(
                    _f64_from_hex(component) for component in vector["input_bits"][0]
                )
                actual = [
                    f"{profile_f32_bits(component):08x}"
                    for component in profile_normalize(value)
                ]
            else:
                raise AssertionError(vector["operation"])
        except ValueError as exc:
            assert not vector["valid"], vector["name"]
            assert str(exc) == vector["error"], vector["name"]
        else:
            assert vector["valid"], vector["name"]
            assert actual == vector["expected_bits"], vector["name"]


def test_python_matches_shared_resource_boundaries():
    corpus = _load_shared_corpus()
    assert asdict(BASE_LIMITS) == corpus["resource_limits"]
    valid_scene = parse_canonical_json(
        _decode_base64(corpus["artifacts"]["scene"]["base64"])
    )

    for case in corpus["resource_cases"]:
        operation = case["operation"]
        parameters = case["parameters"]
        limits = replace(BASE_LIMITS, **parameters.get("limits", {}))
        try:
            if operation == "input_archive_size":
                preflight_input_archive_size(parameters["size"], limits=limits)
                valid, error, first = True, None, None
            elif operation in {"archive_member_sizes", "archive_member_count"}:
                if operation == "archive_member_sizes":
                    sizes = parameters["sizes"]
                else:
                    sizes = {"scene.json": 0}
                    sizes.update(
                        {
                            f"x/{index:05d}": 0
                            for index in range(parameters["count"] - 1)
                        }
                    )
                preflight_archive_member_sizes(sizes, limits=limits)
                valid, error, first = True, None, None
            elif operation in {
                "aggregate_compression_ratio",
                "member_compression_ratio",
            }:
                callback = (
                    preflight_aggregate_compression_ratio
                    if operation == "aggregate_compression_ratio"
                    else preflight_member_compression_ratio
                )
                callback(
                    parameters["uncompressed_size"],
                    parameters["compressed_size"],
                    limits=limits,
                )
                valid, error, first = True, None, None
            elif operation == "json_depth":
                value = {}
                current = value
                for _index in range(parameters["depth"]):
                    current["x"] = {}
                    current = current["x"]
                issues = json_resource_issues(value, limits=limits)
                valid = not issues
                error = None
                first = (
                    None
                    if not issues
                    else {"code": issues[0].code, "path": issues[0].path}
                )
            elif operation == "json_domain":
                text = parameters["text"]
                kind = parameters["kind"]
                field = parameters.get("field")
                if kind == "value":
                    value = {"value": text}
                elif kind == "object_key":
                    value = {text: 0}
                elif kind == "metadata_key":
                    value = {"metadata": {text: 0}}
                elif kind == "sdk_metadata_key":
                    value = {"sdk_metadata": {text: 0}}
                elif kind == "identifier":
                    value = {field or "node_id": text}
                elif kind == "identifier_array":
                    value = {field or "component_path": [text]}
                elif kind == "uri":
                    value = {"uri": text}
                else:
                    raise AssertionError(kind)
                issues = json_resource_issues(value, limits=limits)
                valid = not issues
                error = None
                first = (
                    None
                    if not issues
                    else {"code": issues[0].code, "path": issues[0].path}
                )
            elif operation == "resource_count":
                count = parameters["count"]
                kind = parameters["kind"]
                field = parameters.get("field")
                if kind == "collection":
                    value = {field: [None] * count}
                elif kind == "hierarchy":
                    value = {
                        "nodes": [
                            {"source": {"component_path": ["x"] * count}}
                        ]
                    }
                elif kind == "forwarded":
                    value = {
                        "connectors": [
                            {
                                "anchor_kind": "forwarded",
                                "connector_snapshot_id": f"c{index}",
                                "forwarded_from": {
                                    "source_connector_snapshot_id": f"c{index + 1}"
                                },
                            }
                            for index in range(count)
                        ]
                    }
                else:
                    raise AssertionError(kind)
                issues = resource_count_issues(
                    value, parameters["artifact"], limits=limits
                )
                valid = not issues
                error = None
                first = (
                    None
                    if not issues
                    else {"code": issues[0].code, "path": issues[0].path}
                )
            elif operation == "glb_counts":
                preflight_glb_counts(
                    parameters["kind"],
                    parameters["vertex_count"],
                    parameters["index_count"],
                    limits=limits,
                )
                valid, error, first = True, None, None
            elif operation == "package_budget":
                contributions = parameters["contributions"]
                totals = _compute_package_budget_totals(**contributions)
                result = _report(
                    _package_budget_issues(totals, limits=limits),
                    artifact="package",
                )
                valid, error, first = result.valid, None, _first_report_issue(result)
            elif operation == "scene_geometry_byte_length":
                value = deepcopy(valid_scene)
                byte_length = int(parameters["value"])
                value["geometry_assets"][0]["byte_length"] = byte_length
                if byte_length <= 9_007_199_254_740_991:
                    value = with_scene_revision(value)
                result = validate_scene_manifest(value)
                valid, error, first = result.valid, None, _first_report_issue(result)
            elif operation == "scene_compile_option":
                value = deepcopy(valid_scene)
                field, number = parameters["field"], parameters["value"]
                value["compile_options"][field] = number
                value["geometry_assets"][0]["tessellation"][field] = number
                if field == "linear_tolerance":
                    value["edge_assets"][0]["tessellation"][field] = number
                result = validate_scene_manifest(with_scene_revision(value))
                valid, error, first = result.valid, None, _first_report_issue(result)
            else:
                raise AssertionError(operation)
        except ValueError as exc:
            valid, error, first = False, str(exc), None

        assert valid == case["valid"], case["name"]
        if "error" in case:
            assert error == case["error"], case["name"]
        if case.get("expected") is not None:
            assert first == case["expected"], case["name"]


def test_shared_exact_byte_artifacts_and_jcs_vectors():
    corpus = _load_shared_corpus()
    for artifact in corpus["artifacts"].values():
        payload = _decode_base64(artifact["base64"])
        assert "sha256:" + hashlib.sha256(payload).hexdigest() == artifact["sha256"]
    for vector in corpus["jcs_vectors"]:
        payload = canonical_json_bytes(vector["input"])
        assert payload == _decode_base64(vector["canonical_base64"])
        assert "sha256:" + hashlib.sha256(payload).hexdigest() == vector["sha256"]
    archive = preflight_zip_bytes(_decode_base64(corpus["artifacts"]["canonical_zip"]["base64"]))
    assert canonical_zip_bytes(archive.members) == _decode_base64(
        corpus["artifacts"]["canonical_zip"]["base64"]
    )


def _apply_schema_mutations(base, mutations):
    value = deepcopy(base)
    for mutation in mutations:
        current = value
        for part in mutation["path"][:-1]:
            current = current[part]
        field = mutation["path"][-1]
        if mutation["operation"] == "delete":
            del current[field]
        else:
            current[field] = deepcopy(mutation["value"])
    return value


def test_python_replays_all_closed_schema_record_field_matrices():
    corpus = _load_shared_corpus()
    schemas = {
        artifact: parse_strict_json(load_contract_artifact(path))
        for artifact, path in SCHEMA_FILES.items()
    }
    for matrix in corpus["schema_field_matrices"]:
        root = schemas[matrix["artifact"]]
        pointer = matrix["schema_pointer"]
        schema = (
            root
            if pointer == "#"
            else {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$ref": pointer,
                "$defs": root["$defs"],
            }
        )
        validator = Draft202012Validator(schema)
        for case in matrix["cases"]:
            value = _apply_schema_mutations(matrix["base"], case["mutations"])
            assert validator.is_valid(value) is case["valid"], (
                matrix["artifact"],
                pointer,
                matrix["variant"],
                case["name"],
            )


def _valid_document_payloads():
    corpus = _load_shared_corpus()
    return (
        ("scene", SceneDocument, _decode_base64(corpus["artifacts"]["scene"]["base64"])),
        ("entities", EntityDocument, _decode_base64(corpus["artifacts"]["entities"]["base64"])),
        (
            "presentation",
            PresentationDocument,
            _decode_base64(next(case for case in corpus["presentation_cases"] if case["valid"])["payload_base64"]),
        ),
        (
            "connector_binding",
            ConnectorBindingDocument,
            _decode_base64(next(case for case in corpus["connector_binding_cases"] if case["valid"])["payload_base64"]),
        ),
        (
            "normalized_product",
            NormalizedProductDocument,
            _decode_base64(next(case for case in corpus["normalized_product_cases"] if case["valid"])["payload_base64"]),
        ),
    )


def _assert_deeply_immutable(value):
    if isinstance(value, Mapping):
        assert isinstance(value, MappingProxyType)
        for child in value.values():
            _assert_deeply_immutable(child)
    elif isinstance(value, tuple):
        for child in value:
            _assert_deeply_immutable(child)
    else:
        assert not isinstance(value, (dict, list))


def _nested_container(value):
    for child in value.values():
        if isinstance(child, (Mapping, tuple, dict, list)):
            return child
    raise AssertionError("fixture has no nested container")


def test_immutable_documents_construct_parse_validate_and_round_trip_canonically():
    for name, document_type, payload in _valid_document_payloads():
        mutable = parse_canonical_json(payload)
        constructed = document_type.from_value(mutable)
        parsed = document_type.parse(payload)

        assert is_dataclass(constructed), name
        assert constructed.canonical_bytes == payload, name
        assert parsed.canonical_bytes == payload, name
        assert constructed.canonical_hash == "sha256:" + hashlib.sha256(payload).hexdigest(), name
        assert constructed == parsed, name
        assert bytes(constructed) == payload, name
        assert document_type.from_value(constructed.value) == constructed, name
        assert document_type.from_value(constructed.to_mutable()) == constructed, name


def test_immutable_documents_resist_nested_mutation_and_isolate_mutable_exports():
    for name, document_type, payload in _valid_document_payloads():
        source = parse_canonical_json(payload)
        document = document_type.from_value(source)
        expected_bytes = document.canonical_bytes

        _assert_deeply_immutable(document.value)
        with pytest.raises(TypeError):
            document.value["mutation"] = True
        frozen_nested = _nested_container(document.value)
        with pytest.raises((TypeError, AttributeError)):
            if isinstance(frozen_nested, Mapping):
                frozen_nested["mutation"] = True
            else:
                frozen_nested.append(None)
        with pytest.raises(FrozenInstanceError):
            document._canonical_bytes = b"mutated"

        source["mutation"] = True
        first_copy = document.to_mutable()
        second_copy = document.to_mutable()
        mutable_nested = _nested_container(first_copy)
        if isinstance(mutable_nested, dict):
            mutable_nested["mutation"] = True
        else:
            mutable_nested.append(None)
        first_copy["mutation"] = True

        assert "mutation" not in document.value, name
        assert "mutation" not in second_copy, name
        assert first_copy != second_copy, name
        assert document.canonical_bytes == expected_bytes, name


def test_immutable_document_constructors_reject_invalid_values_and_stale_revisions():
    for _name, document_type, _payload in _valid_document_payloads():
        with pytest.raises(SceneContractError):
            document_type.from_value({})

    with pytest.raises(ValueError, match="canonical"):
        SceneDocument.parse(b'{ "schema_version": "1.0" }')

    corpus = _load_shared_corpus()
    scene = parse_canonical_json(_decode_base64(corpus["artifacts"]["scene"]["base64"]))
    scene["revision"] = "sha256:" + "0" * 64
    with pytest.raises(SceneContractError) as error:
        SceneDocument.from_value(scene)
    assert error.value.report.first_error.code == "revision_mismatch"
