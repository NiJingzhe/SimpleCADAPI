"""Evidence-gated semantic projections from topology tracking data."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from .core import AnyShape, Solid
from .topology import TopoDelta, TopoKind
from .tracking import _topo_id

try:
    from .tagging import (
        LineageDerivation,
        TagEvidence,
        TagProducerKind,
        lineage_policy_allows,
        operation_role_tag_binding,
        projected_tag_binding,
    )
except ImportError:  # The binding layer can be integrated independently.
    TagEvidence = None  # type: ignore[assignment,misc]
    LineageDerivation = None  # type: ignore[assignment,misc]
    lineage_policy_allows = None  # type: ignore[assignment]
    operation_role_tag_binding = None  # type: ignore[assignment]
    projected_tag_binding = None  # type: ignore[assignment]


def _event_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    token = getattr(value, "name", value)
    token = str(token).strip().lower()
    return token or None


def _operation_alias(op: str) -> str:
    token = str(op).strip().lower()
    if token.startswith("op."):
        token = token[3:]
    if token.startswith("make_"):
        token = token[5:]
    for suffix in ("_rsolid", "_rshape", "_rface", "_rwire", "_redge"):
        if token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _entries_from_delta(delta: TopoDelta) -> Dict[str, Dict[str, Any]]:
    """Build the compatibility lookup without dropping canonical witnesses."""

    result: Dict[str, Dict[str, Any]] = {}
    for entry in delta.entries:
        parent_refs = [
            {
                "graph_id": ref.graph_id,
                "node_id": ref.node_id,
                "output_slot": ref.output_slot,
                "kind": ref.kind.name,
                "topo_id": ref.topo_id,
            }
            for ref in entry.parent_refs
        ]
        witness = {
            "topo_id": entry.ref.topo_id,
            "kind": entry.ref.kind.name,
            "event": entry.event.name.lower(),
            "origin_role": entry.origin_role,
            "input_topo_id": (
                entry.parent_refs[0].topo_id if entry.parent_refs else None
            ),
            "parent_refs": parent_refs,
            "derivation": entry.metadata.get("derivation", "unknown"),
            "coverage": entry.metadata.get("coverage", "complete"),
            "status": entry.metadata.get("status", "proven"),
            "evidence_kind": entry.metadata.get(
                "evidence_kind", "kernel_history"
            ),
            "source_kind": entry.metadata.get("source_kind"),
        }
        aggregate = result.setdefault(
            entry.ref.topo_id,
            {
                "topo_id": entry.ref.topo_id,
                "kind": entry.ref.kind.name,
                "event": witness["event"],
                "origin_role": entry.origin_role,
                "input_topo_id": witness["input_topo_id"],
                "derivation": witness["derivation"],
                "coverage": witness["coverage"],
                "status": witness["status"],
                "witnesses": [],
            },
        )
        aggregate["witnesses"].append(witness)
    return result


def _normalized_witnesses(entry: Dict[str, Any]) -> list[Dict[str, Any]]:
    raw = entry.get("witnesses")
    if isinstance(raw, (list, tuple)) and raw:
        return [dict(item) for item in raw if isinstance(item, dict)]
    return [dict(entry)]


def _matching_entry(
    entries: Dict[str, Dict[str, Any]], topo_id: str, kind: TopoKind
) -> Optional[Dict[str, Any]]:
    entry = entries.get(topo_id)
    if not isinstance(entry, dict):
        return None

    witnesses = [
        witness
        for witness in _normalized_witnesses(entry)
        if str(witness.get("kind", entry.get("kind", kind.name))).upper()
        == kind.name
    ]
    if not witnesses:
        return None
    matched = dict(entry)
    matched["kind"] = kind.name
    matched["witnesses"] = witnesses
    return matched


def _normalized_tracking_witness(
    witness: Dict[str, Any], *, default_kind: TopoKind
) -> Dict[str, Any]:
    result = {
        "kind": "topology_change",
        "topo_kind": str(witness.get("kind", default_kind.name)).upper(),
        "source_kind": (
            str(witness["source_kind"]).upper()
            if witness.get("source_kind") is not None
            else None
        ),
        "event": _event_name(witness.get("event")),
        "origin_role": witness.get("origin_role"),
        "input_topo_id": witness.get("input_topo_id"),
        "derivation": str(witness.get("derivation", "unknown")).lower(),
        "coverage": str(witness.get("coverage", "complete")).lower(),
        "status": str(witness.get("status", "proven")).lower(),
        "evidence_kind": str(
            witness.get("evidence_kind", "kernel_history")
        ).lower(),
    }
    for key in ("result_role", "evidence_method", "project_source_tags"):
        if witness.get(key) is not None:
            result[key] = witness[key]
    if witness.get("parent_refs") is not None:
        result["parent_refs"] = list(witness["parent_refs"])
    if witness.get("section"):
        result["section"] = True
    return result


def _tracking_payload(
    entry: Dict[str, Any], *, op: str, topo_id: str, kind: TopoKind
) -> Dict[str, Any]:
    witnesses = [
        _normalized_tracking_witness(item, default_kind=kind)
        for item in _normalized_witnesses(entry)
    ]
    events = sorted(
        {
            str(item["event"])
            for item in witnesses
            if item.get("event") is not None
        }
    )
    origin_roles = sorted(
        {
            str(item["origin_role"])
            for item in witnesses
            if item.get("origin_role") is not None
        }
    )
    result_roles = sorted(
        {
            str(item["result_role"])
            for item in witnesses
            if item.get("result_role") is not None
        }
    )
    coverage = (
        "complete"
        if witnesses and all(item["coverage"] == "complete" for item in witnesses)
        else "partial"
    )
    status = (
        "proven"
        if witnesses and all(item["status"] == "proven" for item in witnesses)
        else "unknown"
    )
    payload: Dict[str, Any] = {
        "schema_version": "1.0",
        "kind": "topology_change",
        "op": str(op),
        "operation": _operation_alias(op),
        "topo_id": topo_id,
        "topo_kind": kind.name,
        "coverage": coverage,
        "status": status,
        "events": events,
        "origin_roles": origin_roles,
        "result_roles": result_roles,
        "witnesses": witnesses,
    }
    if len(events) == 1:
        payload["event"] = events[0]
    if len(origin_roles) == 1:
        payload["origin_role"] = origin_roles[0]
    if len(result_roles) == 1:
        payload["result_role"] = result_roles[0]
    return payload


def _unknown_tracking_payload(
    *, op: str, topo_id: str, kind: TopoKind
) -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "kind": "topology_change",
        "op": str(op),
        "operation": _operation_alias(op),
        "topo_id": topo_id,
        "topo_kind": kind.name,
        "coverage": "partial",
        "status": "unknown",
        "events": [],
        "origin_roles": [],
        "result_roles": [],
        "witnesses": [],
    }


def _carry_source_lineage(
    target: AnyShape,
    entry: Dict[str, Any],
    source_entities: Dict[str, AnyShape],
    *,
    op: str,
) -> None:
    """Attach source bindings only through policy-allowed kernel witnesses."""

    add_lineage = getattr(target, "_add_tag_lineage", None)
    if not callable(add_lineage):
        return

    for witness in _normalized_witnesses(entry):
        derivation = str(witness.get("derivation", "unknown")).lower()
        if LineageDerivation is None:
            continue
        try:
            LineageDerivation(derivation)
        except ValueError:
            # An operation role can be complete without proving tag lineage.
            continue
        input_id = witness.get("input_topo_id")
        source = source_entities.get(str(input_id)) if input_id is not None else None
        if source is None:
            continue
        local_bindings = getattr(source, "_local_tag_bindings", None)
        if not callable(local_bindings) or lineage_policy_allows is None:
            continue
        evidence_data = {
            "op": str(op),
            "event": _event_name(witness.get("event")),
            "origin_role": witness.get("origin_role"),
            "coverage": str(witness.get("coverage", "complete")),
            "derivation": derivation,
        }
        evidence = (
            TagEvidence("topology_change", evidence_data)
            if TagEvidence is not None
            else {"kind": "topology_change", **evidence_data}
        )
        bindings = list(local_bindings())
        bindings.extend(
            item.binding
            for item in getattr(source, "_tag_lineage", ())
            if item.coverage == "complete"
            and lineage_policy_allows(
                item.binding.propagation, item.derivation
            )
        )
        unique_bindings = {binding.binding_id: binding for binding in bindings}
        for binding in unique_bindings.values():
            if not lineage_policy_allows(binding.propagation, derivation):
                continue
            add_lineage(
                binding,
                derivation=derivation,
                source_topo_id=source.topo_id,
                evidence=evidence,
                coverage=str(witness.get("coverage", "complete")),
            )


def _apply_operation_role_bindings(target: AnyShape, track: Dict[str, Any], *, op: str) -> None:
    if operation_role_tag_binding is None:
        return
    add_binding = getattr(target, "_add_tag_binding", None)
    if not callable(add_binding):
        return
    for witness in track.get("witnesses", []):
        role = witness.get("result_role")
        if (
            role is None
            or witness.get("status") != "proven"
            or witness.get("coverage") != "complete"
        ):
            continue
        role = str(role)
        kind = target.__class__.__name__.lower()
        tag = f"{kind}.{role}"
        add_binding(
            operation_role_tag_binding(
                tag,
                operation=op,
                role=role,
                target_topo_id=target.topo_id,
                evidence_method=str(witness.get("evidence_method", "unknown")),
            )
        )


def _project_source_bindings(
    target: AnyShape,
    entry: Dict[str, Any],
    source_entities: Dict[str, AnyShape],
    *,
    op: str,
) -> None:
    if projected_tag_binding is None:
        return
    add_binding = getattr(target, "_add_tag_binding", None)
    if not callable(add_binding):
        return
    for witness in _normalized_witnesses(entry):
        if not witness.get("project_source_tags"):
            continue
        if (
            str(witness.get("coverage", "partial")).lower() != "complete"
            or str(witness.get("status", "unknown")).lower() != "proven"
        ):
            continue
        input_id = witness.get("input_topo_id")
        source = source_entities.get(str(input_id)) if input_id is not None else None
        if source is None:
            continue
        local_bindings = getattr(source, "_local_tag_bindings", None)
        if not callable(local_bindings):
            continue
        role = str(witness.get("result_role", "generated"))
        for binding in local_bindings():
            if binding.producer.kind != TagProducerKind.USER_OPERATION:
                continue
            add_binding(
                projected_tag_binding(
                    binding,
                    operation=op,
                    role=role,
                    source_topo_id=source.topo_id,
                    target_topo_id=target.topo_id,
                    evidence_method=str(witness.get("evidence_method", "Generated")),
                )
            )


def _lineage_coverage(
    entry: Dict[str, Any], source_entities: Dict[str, AnyShape]
) -> str:
    for witness in _normalized_witnesses(entry):
        if str(witness.get("coverage", "partial")).lower() != "complete":
            return "partial"
        input_id = witness.get("input_topo_id")
        if input_id is not None and str(input_id) not in source_entities:
            return "partial"
    return "complete"


def apply_tracking_tags(
    solid: Solid,
    delta: TopoDelta,
    delta_entries: Optional[Dict[str, Dict[str, Any]]] = None,
    op_prefix: str = "unknown",
    *,
    source_solid: Optional[Solid] = None,
    source_solids: Optional[Sequence[Solid]] = None,
    source_shapes: Optional[Sequence[AnyShape]] = None,
) -> Solid:
    """Project proven tracking facts to typed metadata and lineage witnesses.

    Missing evidence remains unknown. Operation names, origin roles, and change
    events are not materialized as semantic tags.
    """

    entries = dict(delta_entries) if delta_entries else _entries_from_delta(delta)
    sources = list(source_solids or ())
    if source_solid is not None and all(
        source_solid is not source for source in sources
    ):
        sources.insert(0, source_solid)
    all_sources: list[AnyShape] = list(sources)
    for source in source_shapes or ():
        if all(source is not existing for existing in all_sources):
            all_sources.append(source)
    source_faces = {
        _topo_id(face.wrapped): face
        for source in all_sources
        for face in (
            source.get_faces()
            if hasattr(source, "get_faces")
            else ([source] if source.__class__.__name__ == "Face" else [])
        )
    }
    source_edges = {
        _topo_id(edge.wrapped): edge
        for source in all_sources
        for edge in (
            source.get_edges()
            if hasattr(source, "get_edges")
            else ([source] if source.__class__.__name__ == "Edge" else [])
        )
    }

    for face in solid.get_faces():
        topo_id = _topo_id(face.wrapped)
        entry = _matching_entry(entries, topo_id, TopoKind.FACE)
        if entry is None:
            face.set_metadata(
                "track",
                _unknown_tracking_payload(
                    op=op_prefix, topo_id=topo_id, kind=TopoKind.FACE
                ),
            )
            face._set_runtime("semantic.lineage.coverage", "partial")
            continue

        track = _tracking_payload(
            entry,
            op=op_prefix,
            topo_id=topo_id,
            kind=TopoKind.FACE,
        )
        face.set_metadata("track", track)
        _apply_operation_role_bindings(face, track, op=op_prefix)
        face._set_runtime(
            "semantic.lineage.coverage",
            _lineage_coverage(entry, source_faces),
        )
        if source_faces and track["status"] == "proven":
            _carry_source_lineage(face, entry, source_faces, op=op_prefix)
        if source_edges and track["status"] == "proven":
            _project_source_bindings(face, entry, source_edges, op=op_prefix)

    section_ids = {
        ref.topo_id for ref in delta.section_edges if ref.kind == TopoKind.EDGE
    }
    for edge in solid.get_edges():
        topo_id = _topo_id(edge.wrapped)
        entry = _matching_entry(entries, topo_id, TopoKind.EDGE)
        if entry is None:
            track = _unknown_tracking_payload(
                op=op_prefix, topo_id=topo_id, kind=TopoKind.EDGE
            )
        else:
            track = _tracking_payload(
                entry,
                op=op_prefix,
                topo_id=topo_id,
                kind=TopoKind.EDGE,
            )

        if topo_id in section_ids:
            track["section"] = True
            track["derivation"] = "intersection"
            if entry is None:
                section_witness = {
                    "kind": "topology_change",
                    "topo_kind": TopoKind.EDGE.name,
                    "source_kind": None,
                    "event": "generated",
                    "origin_role": None,
                    "input_topo_id": None,
                    "derivation": "intersection",
                    "coverage": "complete",
                    "status": "proven",
                    "evidence_kind": "kernel_section_edges",
                    "section": True,
                }
                track.update(
                    {
                        "coverage": "complete",
                        "status": "proven",
                        "event": "generated",
                        "events": ["generated"],
                        "witnesses": [section_witness],
                    }
                )
        edge.set_metadata("track", track)
        _apply_operation_role_bindings(edge, track, op=op_prefix)
        edge._set_runtime(
            "semantic.lineage.coverage",
            _lineage_coverage(entry, source_edges) if entry is not None else "partial",
        )
        if entry is not None and source_edges and track["status"] == "proven":
            _carry_source_lineage(edge, entry, source_edges, op=op_prefix)

    return solid


def apply_tracking_tags_to_delta(
    solid: Solid,
    delta: TopoDelta,
    delta_entries: Optional[Dict[str, Dict[str, Any]]] = None,
    op: str = "unknown",
    source_solid: Optional[Solid] = None,
    source_solids: Optional[Sequence[Solid]] = None,
    source_shapes: Optional[Sequence[AnyShape]] = None,
) -> Solid:
    """Apply evidence-gated tracking projections for one operation result."""

    return apply_tracking_tags(
        solid,
        delta,
        delta_entries,
        op_prefix=op,
        source_solid=source_solid,
        source_solids=source_solids,
        source_shapes=source_shapes,
    )
