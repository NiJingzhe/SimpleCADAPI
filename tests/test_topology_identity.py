from __future__ import annotations

from collections import defaultdict

import simplecadapi as scad
from simplecadapi.core import clone_semantic_shape_view
from simplecadapi.sketch import Sketch, SketchRef, SketchSolveResult


def _box_edge_occurrences():
    box = scad.make_box_rsolid(1.0, 1.0, 1.0)
    occurrences = []
    for face in box.get_faces():
        occurrences.extend(face.get_outer_wire().get_edges())
    return box, occurrences


def test_box_edge_occurrences_share_canonical_topo_ids():
    _, occurrences = _box_edge_occurrences()

    assert len(occurrences) == 24
    assert len({edge.topo_id for edge in occurrences}) == 12


def test_shared_edge_occurrences_share_tags_and_metadata():
    _, occurrences = _box_edge_occurrences()
    groups = defaultdict(list)
    for edge in occurrences:
        groups[edge.topo_id].append(edge)

    shared = next(group for group in groups.values() if len(group) >= 2)
    edge_a, edge_b = shared[0], shared[1]

    scad.apply_tag(edge_a, "shared.edge")
    edge_a.set_metadata("name", "same-topological-edge")

    assert "shared.edge" in scad.list_tags(edge_b)
    assert edge_b.get_metadata("name") == "same-topological-edge"


def test_shared_edge_occurrences_keep_entity_state_after_whole_assignment():
    _, occurrences = _box_edge_occurrences()
    groups = defaultdict(list)
    for edge in occurrences:
        groups[edge.topo_id].append(edge)

    edge_a, edge_b = next(group[:2] for group in groups.values() if len(group) >= 2)
    scad.apply_tag(edge_a, "shared.edge")
    entity = edge_a._entity
    containers = (
        entity.tags,
        entity.tag_bindings,
        entity.tag_lineage,
        entity.metadata,
        entity.runtime,
    )

    edge_a._tag_cache = set(edge_a._tag_cache)
    edge_a._tag_bindings = list(edge_a._tag_bindings)
    edge_a._tag_lineage = list(edge_a._tag_lineage)
    edge_a._metadata = {"name": "reassigned"}
    edge_a._runtime = {"cached": True}

    assert edge_b._entity is entity
    assert containers == (
        edge_b._tag_cache,
        edge_b._tag_bindings,
        edge_b._tag_lineage,
        edge_b._metadata,
        edge_b._runtime,
    )
    assert all(
        before is after
        for before, after in zip(
            containers,
            (
                entity.tags,
                entity.tag_bindings,
                entity.tag_lineage,
                entity.metadata,
                entity.runtime,
            ),
        )
    )
    assert edge_b.get_metadata("name") == "reassigned"
    assert edge_b._get_runtime("cached") is True


def test_non_topology_tagged_objects_keep_standalone_state():
    objects = [
        Sketch(name="standalone"),
        SketchRef("sketch", "point", kind="point"),
        SketchSolveResult(
            sketch_id="sketch",
            status="solved",
            dof=0,
            residual_norm=0.0,
            iterations=0,
            solved_points={},
            solved_scalars={},
        ),
    ]

    for obj in objects:
        containers = (obj._tag_cache, obj._metadata, obj._runtime)
        obj._tag_cache = {"standalone.state"}
        obj._metadata = {"owner": type(obj).__name__}
        obj._runtime = {"ready": True}

        assert obj._entity is None
        assert obj._tag_cache is containers[0]
        assert obj._metadata is containers[1]
        assert obj._runtime is containers[2]
        assert obj._tag_cache == {"standalone.state"}
        assert obj.get_metadata("owner") == type(obj).__name__
        assert obj._get_runtime("ready") is True


def test_semantic_shape_clone_keeps_independent_entity_state():
    box = scad.make_box_rsolid(1.0, 1.0, 1.0)
    box.set_metadata("view", "source")

    clone = clone_semantic_shape_view(box)
    clone._metadata = {"view": "clone"}

    assert clone.topo_id == box.topo_id
    assert clone._entity is not box._entity
    assert clone.get_metadata("view") == "clone"
    assert box.get_metadata("view") == "source"


def test_solid_get_edges_returns_unique_topological_edges():
    box, _ = _box_edge_occurrences()

    edges = box.get_edges()

    assert len(edges) == 12
    assert len({edge.topo_id for edge in edges}) == 12


def test_edge_incident_faces_and_face_adjacency_are_available():
    box, _ = _box_edge_occurrences()

    edge = box.get_edges(0)
    incident_faces = edge.get_incident_faces()

    assert len(incident_faces) == 2
    assert len({face.topo_id for face in incident_faces}) == 2

    face = box.get_faces(0)
    adjacent_faces = face.get_adjacent_faces()

    assert len(adjacent_faces) == 4
    assert face.topo_id not in {adjacent.topo_id for adjacent in adjacent_faces}
