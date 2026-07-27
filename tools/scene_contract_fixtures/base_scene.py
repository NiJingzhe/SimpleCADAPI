"""Base Scene package and canonical tetrahedron asset construction."""

from __future__ import annotations

import hashlib
import math
import struct

from simplecadapi.scene import canonical_json_bytes, with_scene_revision

from .binary_cases import glb
from .common import content_hash, sha256_hex


IDENTITY = {
    "origin": [0, 0, 0],
    "x_axis": [1, 0, 0],
    "y_axis": [0, 1, 0],
    "z_axis": [0, 0, 1],
}
ASSET_TO_SCENE = [1000, 0, 0, 0, 0, 0, -1000, 0, 0, 1000, 0, 0, 0, 0, 0, 1]


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
    y_axis = _normalize(
        tuple(seed[index] - projection * x_axis[index] for index in range(3))
    )
    z_axis = _normalize(_cross(x_axis, y_axis))
    return {
        "origin": list(origin),
        "x_axis": list(x_axis),
        "y_axis": list(y_axis),
        "z_axis": list(z_axis),
    }


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
        normal = _normalize(
            _cross(
                tuple(b[i] - a[i] for i in range(3)),
                tuple(c[i] - a[i] for i in range(3)),
            )
        )
        local_positions = sorted(
            (points[corner] for corner in corners),
            key=lambda point: struct.pack("<fff", *point),
        )
        remap = {point: index for index, point in enumerate(local_positions)}
        triple = tuple(remap[points[corner]] for corner in corners)
        rotations = (triple, triple[1:] + triple[:1], triple[2:] + triple[:2])
        triple = min(rotations)
        block = b"".join(
            struct.pack("<ffffff", *point, *normal) for point in local_positions
        ) + struct.pack("<HHH", *triple)
        blocks.append(
            (
                hashlib.sha256(b"\x01" + block).digest(),
                block,
                name,
                local_positions,
                normal,
                triple,
            )
        )
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
    return glb("triangle", positions, indices, normals), group_names


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
            (points[name[0]], points[name[1]]),
            key=lambda point: struct.pack("<fff", *point),
        )
        block = b"".join(struct.pack("<fff", *point) for point in local_positions)
        block += struct.pack("<HH", 0, 1)
        blocks.append(
            (
                hashlib.sha256(b"\x02" + block).digest(),
                block,
                name,
                local_positions,
            )
        )
    blocks.sort(key=lambda item: (item[0], item[1]))
    positions = []
    indices = []
    group_names = []
    for _render_key, _block, name, local_positions in blocks:
        offset = len(positions)
        positions.extend(local_positions)
        indices.extend((offset, offset + 1))
        group_names.append(name)
    return glb("line", positions, indices), group_names


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


def build_scene_package():
    triangle_glb, face_order = _canonical_triangle_asset()
    line_glb, edge_order = _canonical_line_asset()
    geometry_hash = content_hash(triangle_glb)
    edge_hash = content_hash(line_glb)
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
                {
                    "direction": list(_normalize(direction)),
                    "origin": list(start),
                    "type": "line",
                },
                {
                    "bounds": {"max": maximum, "min": minimum},
                    "centroid": midpoint,
                    "length": math.sqrt(
                        sum(component * component for component in direction)
                    ),
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
    entity_asset["entities"].sort(
        key=lambda entity: entity["entity_id"].encode("utf-8")
    )
    entity_bytes = canonical_json_bytes(entity_asset)
    entity_hash = content_hash(entity_bytes)
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
    appearance_id = "appearance/evaluated/" + sha256_hex(
        canonical_json_bytes(appearance_draft)
    )
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
            "coordinate_system": {
                "handedness": "right",
                "length_unit": "mm",
                "up_axis": "+Z",
            },
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
                    "source": {
                        "kind": "manual",
                        "root_id": "root",
                        "source_id": "fixture",
                    },
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
                    "tessellation": {
                        "angular_tolerance": 0.22,
                        "linear_tolerance": 0.35,
                    },
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
    blobs = {
        geometry_uri: triangle_glb,
        edge_uri: line_glb,
        entity_uri: entity_bytes,
    }
    return scene, scene_bytes, entity_asset, entity_bytes, blobs
