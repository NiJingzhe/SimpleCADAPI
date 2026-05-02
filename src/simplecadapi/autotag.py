"""Auto-tagging based on TopoDelta: applies operation semantic tags to result shapes.

After a tracked operation (cut, union, fillet, etc.), this module can match
result faces to their delta entries and apply semantic tags like:
- ``op.cut.modified`` / ``op.cut.generated`` / ``op.cut.preserved``
- ``origin.body`` / ``origin.tool``
- ``role.section.face``

These tags can then be queried via the QL (``Q.tag("op.cut.generated")``).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .core import Solid, Face
from .topology import TopoKind, TopoEvent, TopoDelta
from .tracking import _topo_id


def apply_tracking_tags(
    solid: Solid,
    delta: TopoDelta,
    delta_entries: Optional[Dict[str, Dict[str, Any]]] = None,
    op_prefix: str = "op",
) -> Solid:
    """Apply operation semantic tags to a result solid based on TopoDelta.

    For each face in the result solid, checks whether it matches a face in the
    delta's modified/generated/preserved/deleted lists by topo_id, and applies
    corresponding tags.

    Faces in the result that don't match any delta entry are tagged as
    ``{op_prefix}.generated`` (inferred new faces).

    Args:
        solid: The result solid to tag.
        delta: The TopoDelta from the tracked operation.
        delta_entries: Per-entity metadata dict (optional, used for origin_role).
        op_prefix: Tag prefix for the operation (default ``"op"``).

    Returns:
        The same ``solid`` (mutated in place) for convenience.
    """
    entries = delta_entries or {}

    # Build a lookup: topo_id -> event
    id_to_event: Dict[str, str] = {}
    for ref in delta.modified:
        id_to_event[ref.topo_id] = "modified"
    for ref in delta.generated:
        id_to_event[ref.topo_id] = "generated"
    for ref in delta.preserved:
        id_to_event[ref.topo_id] = "preserved"
    for ref in delta.deleted:
        id_to_event[ref.topo_id] = "deleted"

    # Section edges
    section_ids = {ref.topo_id for ref in delta.section_edges}
    delta_is_pure_preserve = (
        len(delta.preserved) > 0
        and len(delta.modified) == 0
        and len(delta.generated) == 0
        and len(delta.deleted) == 0
    )

    for face in solid.get_faces():
        fid = _topo_id(face.wrapped)
        event = id_to_event.get(fid)

        if event is None:
            # Check delta_entries by input_topo_id
            entry = entries.get(fid)
            if entry:
                event = entry.get("event", "")

        if event is None:
            if delta_is_pure_preserve:
                event = "preserved"
            else:
                # Face not found in delta -> it's a generated face
                event = "generated"

        tag = f"{op_prefix}.{event}"
        face.add_tag(tag)
        face.apply_tag(f"face.{tag}", propagate=False)
        face.set_metadata(
            "track",
            {
                "event": event,
                "topo_id": fid,
                "op": op_prefix,
            },
        )

        # Origin role tagging from entries
        entry = entries.get(fid, {})
        origin_role = entry.get("origin_role")
        if origin_role:
            face.add_tag(f"origin.{origin_role}")
            face.apply_tag(f"face.origin.{origin_role}", propagate=False)
            face.get_metadata("track", {})["origin_role"] = origin_role

        # Section face tagging (faces at boolean intersection)
        if fid in section_ids:
            face.add_tag("role.section.face")
            face.apply_tag(f"face.role.section", propagate=False)

    return solid


def apply_tracking_tags_to_delta(
    solid: Solid,
    delta: TopoDelta,
    delta_entries: Optional[Dict[str, Dict[str, Any]]] = None,
    op: str = "unknown",
    source_solid: Optional[Solid] = None,
) -> Solid:
    """Convenience wrapper that prefixes the operation name.

    Args:
        solid: The result solid.
        delta: The TopoDelta.
        delta_entries: Per-entity metadata.
        op: Operation name (e.g. ``"cut"``, ``"union"``, ``"extrude"``).
        source_solid: If provided, carry over tags from this solid's faces
            to the result faces that originated from them.

    Returns:
        The tagged solid.
    """
    result = apply_tracking_tags(solid, delta, delta_entries, op_prefix=f"op.{op}")

    if source_solid is not None:
        _carry_source_tags(result, delta_entries or {}, source_solid)

    return result


def _carry_source_tags(
    result_solid: Solid,
    delta_entries: Dict[str, Dict[str, Any]],
    source_solid: Solid,
) -> None:
    """Carry over tags from source solid faces to result faces.

    For each face in the result, looks up its delta entry to find the
    ``input_topo_id`` of the source face, then copies propagatable tags.
    """
    # Build source face lookup by topo_id
    source_face_tags: Dict[str, set] = {}
    for face in source_solid.get_faces():
        fid = _topo_id(face.wrapped)
        source_face_tags[fid] = set(face._tags)

    # For each result face, find its source and copy tags
    for face in result_solid.get_faces():
        fid = _topo_id(face.wrapped)
        entry = delta_entries.get(fid, {})
        input_id = entry.get("input_topo_id")
        if input_id and input_id in source_face_tags:
            for tag in source_face_tags[input_id]:
                # Don't overwrite operation tags
                if not tag.startswith("op.") and not tag.startswith("origin."):
                    face.add_tag(tag)
