"""Selection operator implementations."""

from __future__ import annotations

from ._support import *

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
        faces = solid._iter_faces()
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
            edges = shape._iter_edges()
        elif isinstance(shape, Solid):
            edges = shape._iter_edges()
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
