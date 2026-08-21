"""Selection operators for the SimpleCAD public API."""

from __future__ import annotations

from ._operation_support import *

def _semantic_view_target(view: AnyShape, target: AnyShape) -> AnyShape:
    candidates = [
        wrapper
        for entity in view._topology_cache.entities()
        if entity.kind == target._entity.kind
        for wrapper in entity.wrappers
        if isinstance(wrapper, type(target))
    ]
    matches = []
    for candidate in candidates:
        try:
            if _same_semantic_topology(
                target._entity.kind,
                candidate.wrapped,
                target.wrapped,
            ):
                matches.append(candidate)
        except Exception:
            continue
    unique = {candidate.topo_id: candidate for candidate in matches}
    if not unique:
        raise ValueError("tag target does not belong to the assignment scope")
    if len(unique) != 1:
        raise ValueError("tag target resolves ambiguously inside the assignment scope")
    return cast(AnyShape, next(iter(unique.values())))

def apply_tag_rselection(
    scope: AnyShape,
    targets: Union[ShapeSelector, Sequence[AnyShape]],
    tag: str,
    topology_propagation: str | TopologyPropagation = TopologyPropagation.LOCAL,
    lineage_policy: str | LineagePolicy = LineagePolicy.CONTINUATION_FRAGMENT,
) -> AnyShape:
    """Return a semantic shape view with a canonical tag assignment."""

    try:
        return _apply_tag_rselection(
            scope,
            targets,
            tag,
            topology_propagation,
            lineage_policy,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="apply_tag_rselection",
            what_happened="Failed to attach the tag to the selected shapes.",
            possible_causes=[
                "The assignment scope or target selection is invalid.",
                "The tag value is empty or malformed.",
                "The selector resolved no targets or references foreign topology.",
            ],
            how_to_fix=[
                "Pass a valid scope and a non-empty ShapeSelector or shape sequence.",
                "Use a normalized tag string such as 'role.mounting_surface' or 'group.fasteners'.",
                "Ensure every explicit target belongs to the assignment scope.",
            ],
            error=e,
        )

def _apply_tag_rselection(
    scope: AnyShape,
    targets: Union[ShapeSelector, Sequence[AnyShape]],
    tag: str,
    topology_propagation: str | TopologyPropagation,
    lineage_policy: str | LineagePolicy,
    *,
    authoring_source: str = "simplecadapi.apply_tag_rselection",
    extra_evidence: Optional[Dict[str, Any]] = None,
    clone_scope: bool = True,
) -> AnyShape:
    normalized_tag = normalize_tag(tag, strict=True)
    topology = TopologyPropagation(topology_propagation)
    lineage = LineagePolicy(lineage_policy)
    session = get_active_session()
    source_node = _active_graph_node_for_shape(scope)
    source_output_slot = int(scope._get_runtime("graph.output_slot", 0))
    if session is not None and source_node is None:
        raise ValueError("assignment scope is not produced by the active GraphSession")

    view = clone_semantic_shape_view(scope) if clone_scope else scope
    if isinstance(targets, ShapeSelector):
        selector = targets
        if source_node is not None:
            if selector.source_node_id is None:
                selector = selector.from_source(source_node.node_id, source_output_slot)
            elif (
                selector.source_node_id != source_node.node_id
                or int(selector.source_output_slot or 0) != source_output_slot
            ):
                raise ValueError(
                    "tag selector source does not match the assignment scope"
                )
        selected = cast(List[AnyShape], selector.resolve(view))
        target = TagTarget("selection_query", selector=selector.to_dict())
    else:
        if isinstance(targets, (str, bytes)):
            raise TypeError("targets must be a ShapeSelector or shape sequence")
        target_shapes = list(targets)
        if not target_shapes:
            raise ValueError("tag assignment targets cannot be empty")
        if not all(
            isinstance(item, (Vertex, Edge, Wire, Face, Shell, Solid, Compound))
            for item in target_shapes
        ):
            raise TypeError("tag assignment targets must contain only shapes")
        selected = [
            _semantic_view_target(view, cast(AnyShape, item)) for item in target_shapes
        ]
        refs = tuple(
            ref for ref in _serialize_shape_refs(target_shapes) if isinstance(ref, dict)
        )
        if len(refs) != len(target_shapes):
            refs = tuple(
                {"kind": _shape_kind_token(item), "topo_id": item.topo_id}
                for item in target_shapes
            )
        target = TagTarget("explicit_refs", refs=refs)

    selected_by_topo_id = {item.topo_id: item for item in selected}
    if len(selected_by_topo_id) != len(selected):
        raise ValueError("tag assignment targets contain ambiguous duplicate entities")
    selected = list(selected_by_topo_id.values())
    if not selected:
        raise ValueError("tag assignment resolved no targets")

    selected_refs = _serialize_shape_refs(selected)
    if len(selected_refs) != len(selected):
        selected_refs = [
            {"kind": _shape_kind_token(item), "topo_id": item.topo_id}
            for item in selected
        ]

    assignment_node_id = (
        session.graph.allocate_node_id("n")
        if source_node is not None and session is not None
        else None
    )
    evidence_data = {
        "authoring_source": authoring_source,
        "selected_count": len(selected),
        "selected_refs": selected_refs,
        **dict(extra_evidence or {}),
    }
    binding = TagBinding(
        tag=normalized_tag,
        producer=TagProducer("user_operation", node_id=assignment_node_id),
        scope=TagBindingScope(
            node_id=(source_node.node_id if source_node is not None else None),
            output_slot=source_output_slot,
        ),
        target=target,
        propagation=TagPropagation(topology=topology, lineage=lineage),
        evidence=TagEvidence("query_execution", evidence_data),
        certainty=TagCertainty.ASSERTED,
        lifecycle=TagLifecycle.ASSERTION,
        binding_id=(
            f"tag_binding_{uuid.uuid5(uuid.NAMESPACE_URL, f'simplecad:user-tag:{session.graph.graph_id}:{assignment_node_id}:{normalized_tag}').hex}"
            if assignment_node_id is not None and session is not None
            else f"tag_binding_{uuid.uuid4().hex}"
        ),
    )

    for selected_shape in selected:
        selected_shape._add_tag_binding(binding)

    if source_node is not None and session is not None:
        node = record_operation(
            op=_OP_APPLY_TAG_RSELECTION,
            params={"tag_binding": binding.to_dict()},
            inputs=[source_node],
            node_id=assignment_node_id,
            output_count=1,
            context=_current_context_metadata(),
        )
        attach_semantic_graph_node(
            view,
            node,
            output_slot=0,
            graph_id=session.graph.graph_id,
        )
    return view

def apply_tag(shape: AnyShape, tag: str) -> AnyShape:
    """Attach a local user tag with continuation/fragment lineage policy."""

    try:
        _ensure_source_shape_has_own_selection_node(shape)
        selector = ShapeSelector(_shape_kind_token(shape)).exactly(1)
        return _apply_tag_rselection(
            shape,
            selector,
            tag,
            TopologyPropagation.LOCAL,
            LineagePolicy.CONTINUATION_FRAGMENT,
            clone_scope=False,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="apply_tag",
            what_happened="Failed to attach the tag to the shape.",
            possible_causes=[
                "The shape is invalid.",
                "The tag value is empty or malformed.",
            ],
            how_to_fix=[
                "Pass a valid shape object.",
                "Use a normalized tag string such as 'role.mounting_surface' or 'group.fasteners'.",
            ],
            error=e,
        )

def list_tags(
    shape: AnyShape,
    scope: str | TagScope = TagScope.EFFECTIVE,
) -> List[str]:
    """Return shape tags in deterministic sorted order for one scope."""
    try:
        return shape._list_tags(normalize_tag_scope(scope))
    except Exception as e:
        _wrap_public_api_error(
            operation="list_tags",
            what_happened="Failed to list tags on the shape.",
            possible_causes=[
                "The shape is invalid.",
                "The object is not a SimpleCAD shape.",
            ],
            how_to_fix=[
                "Pass a valid Vertex, Edge, Wire, Face, or Solid object.",
            ],
            error=e,
        )

def explain_tag(
    shape: AnyShape,
    tag: str,
    scope: str | TagScope = TagScope.EFFECTIVE,
) -> List[Dict[str, Any]]:
    """Explain every visible binding that produces a tag token."""

    try:
        return shape._explain_tag(
            normalize_tag(tag, strict=True), normalize_tag_scope(scope)
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="explain_tag",
            what_happened="Failed to explain the tag on the shape.",
            possible_causes=[
                "The shape or tag is invalid.",
                "The requested scope requires unavailable semantic evidence.",
            ],
            how_to_fix=[
                "Pass a valid shape and normalized tag token.",
                "Request a supported scope or provide complete topology history.",
            ],
            error=e,
        )

def select_faces_by_tag(
    solid: Solid,
    tag: str,
    scope: str | TagScope = TagScope.EFFECTIVE,
) -> List[Face]:
    """Select faces by tag."""
    try:
        normalized = normalize_tag(tag, strict=True)
        resolved_scope = normalize_tag_scope(scope)
        faces = solid.get_faces()
        return [face for face in faces if face._has_tag(normalized, resolved_scope)]
    except Exception as e:
        _wrap_public_api_error(
            operation="select_faces_by_tag",
            what_happened="Failed to select faces by tag.",
            possible_causes=[
                "The solid is invalid.",
                "The tag string is invalid.",
            ],
            how_to_fix=[
                "Pass a valid Solid object.",
                "Use the exact face tag that was previously assigned.",
            ],
            error=e,
        )

def select_edges_by_tag(
    shape: Union[Face, Solid],
    tag: str,
    scope: str | TagScope = TagScope.EFFECTIVE,
) -> List[Edge]:
    """Select edges by tag."""
    try:
        normalized = normalize_tag(tag, strict=True)
        resolved_scope = normalize_tag_scope(scope)
        if isinstance(shape, Face):
            edges = shape.get_edges()
        elif isinstance(shape, Solid):
            edges = shape.get_edges()
        else:
            raise ValueError("只能从面或实体中选择边")

        return [edge for edge in edges if edge._has_tag(normalized, resolved_scope)]
    except Exception as e:
        _wrap_public_api_error(
            operation="select_edges_by_tag",
            what_happened="Failed to select edges by tag.",
            possible_causes=[
                "The input shape is neither a Face nor a Solid.",
                "The shape is invalid.",
                "The tag string is invalid.",
            ],
            how_to_fix=[
                "Pass a Face or Solid object.",
                "Use the exact edge tag that was previously assigned.",
                "If selection is empty unexpectedly, inspect the available edge tags first.",
            ],
            error=e,
        )

__all__ = tuple(name for name in globals() if not name.startswith("__"))
