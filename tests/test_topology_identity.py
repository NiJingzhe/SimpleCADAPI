from __future__ import annotations

from collections import defaultdict

import simplecadapi as scad


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

    edge_a.add_tag("shared.edge")
    edge_a.set_metadata("name", "same-topological-edge")

    assert edge_b.has_tag("shared.edge")
    assert edge_b.get_metadata("name") == "same-topological-edge"


def test_solid_get_edges_returns_unique_topological_edges():
    box, _ = _box_edge_occurrences()

    edges = box.get_edges()

    assert len(edges) == 12
    assert len({edge.topo_id for edge in edges}) == 12


def test_edge_incident_faces_and_face_adjacency_are_available():
    box, _ = _box_edge_occurrences()

    edge = box.get_edges()[0]
    incident_faces = edge.get_incident_faces()

    assert len(incident_faces) == 2
    assert len({face.topo_id for face in incident_faces}) == 2

    face = box.get_faces()[0]
    adjacent_faces = face.get_adjacent_faces()

    assert len(adjacent_faces) == 4
    assert face.topo_id not in {adjacent.topo_id for adjacent in adjacent_faces}
