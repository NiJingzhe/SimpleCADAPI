"""Features operator implementations."""

from __future__ import annotations

from ._support import *
from .geometry import (
    _default_plane_x_direction,
    _validated_loft_sections,
    make_face_from_wire_rface,
    make_helix_rwire,
)

def extrude_rsolid(
    profile: Union[Wire, Face],
    direction: Tuple[float, float, float],
    distance: ScalarLike,
    *,
    tag_prefix: Optional[str] = None,
    result_tag: Optional[str] = None,
    start_face_tag: Optional[str] = None,
    end_face_tag: Optional[str] = None,
    side_faces_tag: Optional[str] = None,
) -> Solid:
    """Create a solid by extruding a profile, with optional role-based tags."""
    try:
        assignments = _normalize_operation_role_tags(
            _OP_MAKE_EXTRUDE_RSOLID,
            (
                ("extrusion.start", start_face_tag),
                ("extrusion.end", end_face_tag),
                ("extrusion.side", side_faces_tag),
            ),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        distance_value = evaluate_scalar(distance)
        if distance_value <= 0:
            raise ValueError("拉伸距离必须大于0")

        cs = get_current_cs()
        direction_value = cast(Tuple[float, float, float], evaluate_value(direction))
        global_direction = cs.transform_vector(np.array(direction_value))

        direction_norm = float(np.linalg.norm(global_direction))
        if direction_norm <= 1e-15:
            raise ValueError("拉伸方向不能是零向量")
        direction_vec = tuple(
            (global_direction / direction_norm * distance_value).tolist()
        )

        if isinstance(profile, Wire):
            # 如果是线，先转换为面
            if profile.is_closed():
                face = Face(make_face_from_wire_ocp(profile.wrapped))
            else:
                raise ValueError(
                    "如果传入线框作为拉伸对象，那么线框必须是闭合的, 而你的线框没有闭合，请检查构成线框的点是否正确"
                )
        elif isinstance(profile, Face):
            face = profile
        else:
            raise ValueError("只能拉伸线或面")  # type: ignore[unreachable]

        resolved_direction = tuple(float(value) for value in global_direction)
        tracked = tracked_extrude(
                face,
                resolved_direction,
                distance_value,
            )
        solid = cast(Solid, tracked.shape)

        solid._apply_tag("solid.extrusion", propagate=False)
        solid._metadata = profile._metadata.copy()

        target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
        finalized = _finalize_tracked_solid(
            solid,
            op=_OP_MAKE_EXTRUDE_RSOLID,
            params={
                "direction": direction,
                "distance": distance,
            },
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[profile],
        )
        tagged = _apply_operation_role_tags(
            finalized,
            op=_OP_MAKE_EXTRUDE_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
        return _apply_feature_tag_prefix(
            tagged,
            tag_prefix=tag_prefix,
            op=_OP_MAKE_EXTRUDE_RSOLID,
            delta=tracked.delta,
            start_role="extrusion.start",
            end_role="extrusion.end",
            side_role="extrusion.side",
            source_shapes=[profile],
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="extrude_rsolid",
            what_happened="Failed to extrude the profile into a solid.",
            possible_causes=[
                "The distance is not a positive finite scalar.",
                "The direction vector is invalid.",
                "A wire profile was provided but it is not closed.",
                "The kernel rejected the profile or the extrusion direction.",
            ],
            how_to_fix=[
                "Use a distance greater than zero.",
                "Pass a valid finite direction vector.",
                "If you extrude a wire, make sure the wire is closed or convert it to a face first.",
                "Inspect the evaluated profile and direction before retrying.",
            ],
            error=e,
        )

def revolve_rsolid(
    profile: Union[Wire, Face],
    axis: Tuple[float, float, float] = (0, 0, 1),
    angle: ScalarLike = 360,
    origin: Tuple[float, float, float] = (0, 0, 0),
    *,
    tag_prefix: Optional[str] = None,
    result_tag: Optional[str] = None,
    start_face_tag: Optional[str] = None,
    end_face_tag: Optional[str] = None,
    side_faces_tag: Optional[str] = None,
) -> Solid:
    """Create a revolved solid, with optional kernel-role-based tags."""
    try:
        assignments = _normalize_operation_role_tags(
            _OP_MAKE_REVOLVE_RSOLID,
            (
                ("revolution.start", start_face_tag),
                ("revolution.end", end_face_tag),
                ("revolution.side", side_faces_tag),
            ),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        angle_value = evaluate_scalar(angle)
        if angle_value <= 0:
            raise ValueError("旋转角度必须大于0")

        cs = get_current_cs()
        axis_value = cast(Tuple[float, float, float], evaluate_value(axis))
        origin_value = cast(Tuple[float, float, float], evaluate_value(origin))
        global_axis = cs.transform_vector(np.array(axis_value))
        global_origin = cs.transform_point(np.array(origin_value))

        # 获取轮廓对应的面
        if isinstance(profile, Wire):
            # 如果是线，先转换为面
            if profile.is_closed():
                face = Face(make_face_from_wire_ocp(profile.wrapped))
            else:
                raise ValueError("旋转的线必须是闭合的")
        elif isinstance(profile, Face):
            face = profile
        else:
            raise ValueError("只能旋转线或面")

        resolved_axis = tuple(float(value) for value in global_axis)
        resolved_origin = tuple(float(value) for value in global_origin)
        tracked = tracked_revolve(
                face,
                resolved_axis,
                resolved_origin,
                angle_value,
            )
        solid = cast(Solid, tracked.shape)

        solid._metadata = profile._metadata.copy()

        target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
        finalized = _finalize_tracked_solid(
            solid,
            op=_OP_MAKE_REVOLVE_RSOLID,
            params={
                "axis": axis,
                "angle": angle,
                "origin": origin,
            },
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[profile],
        )
        tagged = _apply_operation_role_tags(
            finalized,
            op=_OP_MAKE_REVOLVE_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
        return _apply_feature_tag_prefix(
            tagged,
            tag_prefix=tag_prefix,
            op=_OP_MAKE_REVOLVE_RSOLID,
            delta=tracked.delta,
            start_role="revolution.start" if angle_value < 360.0 else None,
            end_role="revolution.end" if angle_value < 360.0 else None,
            side_role="revolution.side",
            source_shapes=[profile],
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="revolve_rsolid",
            what_happened="Failed to revolve the profile into a solid.",
            possible_causes=[
                "The angle is not a positive finite scalar.",
                "The axis or origin is invalid.",
                "A wire profile was provided but it is not closed.",
                "The kernel rejected the revolve definition.",
            ],
            how_to_fix=[
                "Use an angle greater than zero.",
                "Pass a valid non-zero axis vector and a valid origin point.",
                "If you revolve a wire, ensure it is closed or convert it to a face first.",
                "Inspect the evaluated axis, origin, and profile before retrying.",
            ],
            error=e,
        )

def _normalize_shape_input(
    shapes: Union[AnyShape, Sequence[AnyShape]],
) -> List[AnyShape]:
    """Normalize rendering input into a flat list of shapes."""

    if isinstance(shapes, _EXPORTABLE_TYPES):
        return [shapes]

    if isinstance(shapes, Sequence) and not isinstance(shapes, (str, bytes)):
        normalized: List[AnyShape] = []
        for item in shapes:
            normalized.extend(_normalize_shape_input(item))
        return normalized

    raise ValueError(
        "rendering accepts Compound, Solid, Shell, Face, Wire, Edge, Vertex, or nested sequences of those types"
    )

SCREENSHOT_VIEWS: Tuple[Tuple[float, float, str], ...] = (
    (28.0, -45.0, "isometric"),
    (90.0, -90.0, "top / X-Y"),
    (0.0, -90.0, "front / X-Z"),
    (0.0, 0.0, "side / Y-Z"),
)
"""Default multi-view set used by render_screenshot_rpath."""


def render_screenshot_rpath(
    shapes: Union[Solid, Sequence[Solid]],
    output_path: str,
    highlight_tags: Optional[Sequence[str]] = None,
    tag_labels: Optional[Dict[str, str]] = None,
    image_size: Tuple[int, int] = (1400, 900),
    view: Union[Tuple[float, float], str] = "auto",
    views: Optional[Sequence[Tuple[float, float, str]]] = None,
    show_axes: bool = True,
    show_legend: bool = True,
    zoom: float = 4.0,
    show_callouts: bool = True,
    linear_deflection: Optional[float] = None,
    angular_deflection: Optional[float] = None,
    style: str = "standard",
    edge_width_scale: Optional[float] = None,
    view_up: Optional[Sequence[float]] = None,
) -> str:
    """Render SDK solids through the shared OCCT/VTK BREP renderer.

    By default every render is a multi-view grid (SCREENSHOT_VIEWS: isometric,
    top, front, side) carrying highlight-tag color groups, callout labels with
    leader lines, a legend and per-panel axis triads. Pass an explicit
    ``view`` (preset name or ``(elevation, azimuth)``) for the legacy
    single-view image, or ``views`` to choose a custom view set.

    ``style="studio"`` turns the single-view path into a product shot
    (gradient backdrop, three-point lighting, bold tubed BRep edges);
    ``linear_deflection``/``angular_deflection`` tighten the tessellation
    for high-resolution exports. ``edge_width_scale`` tunes the studio edge
    tube radius as a fraction of model span (default 0.0026; use ~0.001 for
    exploded stacks so the ink does not swamp small parts).
    """
    try:
        from ..inspect.brep.render import _render_sdk_screenshot_rpath

        shape_list = _normalize_shape_input(shapes)
        solids = [shape for shape in shape_list if isinstance(shape, Solid)]
        if len(solids) != len(shape_list) or not solids:
            raise ValueError("render_screenshot_rpath only supports Solid inputs")
        resolved_views = views
        if resolved_views is None and (view is None or view == "auto"):
            resolved_views = SCREENSHOT_VIEWS
        return str(
            _render_sdk_screenshot_rpath(
                solids,
                output_path,
                highlight_tags=tuple(highlight_tags or ()),
                tag_labels=tag_labels,
                image_size=image_size,
                view=view,
                show_axes=show_axes,
                show_legend=show_legend,
                zoom=zoom,
                show_callouts=show_callouts,
                linear_deflection=linear_deflection,
                angular_deflection=angular_deflection,
                views=resolved_views,
                style=style,
                edge_width_scale=edge_width_scale,
                view_up=tuple(float(value) for value in view_up) if view_up is not None else None,
            )
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="render_screenshot_rpath",
            what_happened="Failed to render the screenshot.",
            possible_causes=[
                "The input does not contain any valid Solid objects.",
                "The rendering view or zoom configuration is invalid.",
                "The output path is invalid or not writable.",
            ],
            how_to_fix=[
                "Pass a Solid or a sequence of Solid objects.",
                "Use a supported view preset or a valid (elev, azim) tuple.",
                "Check that the output path is writable.",
            ],
            error=e,
        )

def fillet_rsolid(
    solid: Solid,
    edges: Union[Sequence[Edge], ShapeSelector],
    radius: ScalarLike,
    *,
    result_tag: Optional[str] = None,
    generated_faces_tag: Optional[str] = None,
) -> Solid:
    """Apply fillets, with optional tagging of kernel-proven patch faces."""
    try:
        assignments = _normalize_operation_role_tags(
            _OP_MAKE_FILLET_RSOLID,
            (("fillet.patch", generated_faces_tag),),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        radius_value = evaluate_scalar(radius)
        if radius_value <= 0:
            raise ValueError("圆角半径必须大于0")

        selected_edges = cast(List[Edge], _resolve_selector_or_shapes(solid, edges))
        if not selected_edges:
            raise ValueError("圆角操作至少需要一条边")

        tracked = tracked_fillet(solid, selected_edges, radius_value)
        result = cast(Solid, tracked.shape)

        result._metadata = solid._metadata.copy()

        selected_edge_refs = _serialize_shape_refs(selected_edges)
        selected_edge_node_ids = _ensure_geo_selection_node_ids(solid, selected_edges)

        selection_params: Dict[str, object] = {
            "radius": radius,
            "edge_count": len(selected_edges),
            "selected_edges": selected_edge_refs,
        }
        if selected_edge_node_ids:
            selection_params["selected_edge_node_ids"] = selected_edge_node_ids
        else:
            selection_params["selected_edge_indices"] = _serialize_selection_indices(
                selected_edges, solid._iter_edges()
            )

        target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
        finalized = _finalize_tracked_solid(
            result,
            op=_OP_MAKE_FILLET_RSOLID,
            params=selection_params,
            source_solid=solid,
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[solid, *selected_edges],
        )
        return _apply_operation_role_tags(
            finalized,
            op=_OP_MAKE_FILLET_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="fillet_rsolid",
            what_happened="Failed to apply the fillet operation.",
            possible_causes=[
                "The radius is not a positive finite scalar.",
                "No valid edges were selected.",
                "The selected edges are incompatible with the requested fillet radius.",
            ],
            how_to_fix=[
                "Use a positive fillet radius.",
                "Select at least one valid edge or use a selector that resolves to edges.",
                "If the kernel rejects the fillet, try a smaller radius or a simpler edge set.",
            ],
            error=e,
        )

def _chamfer_reference_face_pairs(
    edges: Sequence[Edge],
    reference_direction: Tuple[float, float, float],
) -> List[Tuple[Edge, Edge]]:
    """Order each edge's adjacent faces as (reference, other).

    The reference face is the adjacent face whose outward normal has the
    largest dot product with ``reference_direction``.
    """
    direction = np.array(reference_direction, dtype=float)
    norm = float(np.linalg.norm(direction))
    if norm <= 1e-12:
        raise ValueError("chamfer reference_direction must be non-zero")
    direction = direction / norm
    pairs: List[Tuple[Edge, Edge]] = []
    for edge in edges:
        faces = edge.get_incident_faces()
        if len(faces) < 2:
            raise ValueError(
                "An angled chamfer needs two adjacent faces per selected edge"
            )
        def alignment(face: Edge) -> float:
            normal = face.get_normal_at()
            return float(
                normal.x * direction[0]
                + normal.y * direction[1]
                + normal.z * direction[2]
            )

        ranked = sorted(faces, key=alignment, reverse=True)
        pairs.append((ranked[0], ranked[1]))
    return pairs


def chamfer_rsolid(
    solid: Solid,
    edges: Union[Sequence[Edge], ShapeSelector],
    distance: ScalarLike,
    *,
    angle: Optional[float] = None,
    reference_direction: Optional[Tuple[float, float, float]] = None,
    result_tag: Optional[str] = None,
    generated_faces_tag: Optional[str] = None,
) -> Solid:
    """Apply chamfers, with optional tagging of kernel-proven patch faces.

    Without ``angle`` the chamfer is symmetric (both legs equal
    ``distance``). With ``angle`` — measured in degrees between the chamfer
    face and the reference face — the chamfer is asymmetric with the second
    leg at ``distance * tan(angle)`` on the non-reference side;
    ``reference_direction`` picks, per edge, the adjacent face whose outward
    normal best matches it as the reference face.
    """
    try:
        assignments = _normalize_operation_role_tags(
            _OP_MAKE_CHAMFER_RSOLID,
            (("chamfer.patch", generated_faces_tag),),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        distance_value = evaluate_scalar(distance)
        if distance_value <= 0:
            raise ValueError("倒角距离必须大于0")

        selected_edges = cast(List[Edge], _resolve_selector_or_shapes(solid, edges))
        if not selected_edges:
            raise ValueError("倒角操作至少需要一条边")

        chamfer_distance2: Optional[float] = None
        edge_face_pairs: Optional[List[Tuple[Edge, Edge]]] = None
        if angle is not None:
            if reference_direction is None:
                raise ValueError(
                    "An angled chamfer requires reference_direction to pick "
                    "the face anchoring the distance"
                )
            angle_radians = math.radians(float(angle))
            if not (0.0 < angle_radians < 0.5 * math.pi):
                raise ValueError("Chamfer angle must be between 0 and 90 degrees")
            chamfer_distance2 = distance_value * math.tan(angle_radians)
            edge_face_pairs = _chamfer_reference_face_pairs(
                selected_edges, reference_direction
            )

        tracked = tracked_chamfer(
            solid,
            selected_edges,
            distance_value,
            distance2=chamfer_distance2,
            edge_face_pairs=edge_face_pairs,
        )
        result = cast(Solid, tracked.shape)

        result._metadata = solid._metadata.copy()

        selected_edge_refs = _serialize_shape_refs(selected_edges)
        selected_edge_node_ids = _ensure_geo_selection_node_ids(solid, selected_edges)

        selection_params: Dict[str, object] = {
            "distance": distance,
            "edge_count": len(selected_edges),
            "selected_edges": selected_edge_refs,
            "angle": angle,
            "reference_direction": reference_direction,
        }
        if chamfer_distance2 is not None:
            selection_params["distance2"] = chamfer_distance2
        if selected_edge_node_ids:
            selection_params["selected_edge_node_ids"] = selected_edge_node_ids
        else:
            selection_params["selected_edge_indices"] = _serialize_selection_indices(
                selected_edges, solid._iter_edges()
            )

        target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
        finalized = _finalize_tracked_solid(
            result,
            op=_OP_MAKE_CHAMFER_RSOLID,
            params=selection_params,
            source_solid=solid,
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[solid, *selected_edges],
        )
        return _apply_operation_role_tags(
            finalized,
            op=_OP_MAKE_CHAMFER_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="chamfer_rsolid",
            what_happened="Failed to apply the chamfer operation.",
            possible_causes=[
                "The distance is not a positive finite scalar.",
                "No valid edges were selected.",
                "The selected edges are incompatible with the requested chamfer size.",
            ],
            how_to_fix=[
                "Use a positive chamfer distance.",
                "Select at least one valid edge or use a selector that resolves to edges.",
                "If the kernel rejects the chamfer, try a smaller distance or fewer edges.",
            ],
            error=e,
        )

def shell_rsolid(
    solid: Solid,
    faces_to_remove: Union[Sequence[Face], ShapeSelector],
    thickness: ScalarLike,
    *,
    result_tag: Optional[str] = None,
    body_faces_tag: Optional[str] = None,
    offset_faces_tag: Optional[str] = None,
    closing_faces_tag: Optional[str] = None,
    wall_edges_tag: Optional[str] = None,
) -> Solid:
    """Shell a solid, with optional kernel-role-based face tags."""
    try:
        assignments = _normalize_operation_role_tags(
            _OP_MAKE_SHELL_RSOLID,
            (
                ("shell.body_face", body_faces_tag),
                ("shell.offset_face", offset_faces_tag),
                ("shell.closing_descendant", closing_faces_tag),
                ("shell.wall", wall_edges_tag),
            ),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        thickness_value = evaluate_scalar(thickness)
        if thickness_value <= 0:
            raise ValueError("壁厚必须大于0")

        selected_faces = cast(
            List[Face], _resolve_selector_or_shapes(solid, faces_to_remove)
        )
        if not selected_faces:
            raise ValueError("抽壳操作至少需要一个待移除面")

        tracked = tracked_shell(solid, selected_faces, thickness_value)
        result = cast(Solid, tracked.shape)

        result._metadata = solid._metadata.copy()

        selected_face_refs = _serialize_shape_refs(selected_faces)
        selected_face_node_ids = _ensure_geo_selection_node_ids(solid, selected_faces)

        selection_params: Dict[str, object] = {
            "thickness": thickness,
            "removed_face_count": len(selected_faces),
            "selected_faces": selected_face_refs,
        }
        if selected_face_node_ids:
            selection_params["selected_face_node_ids"] = selected_face_node_ids
        else:
            selection_params["selected_face_indices"] = _serialize_selection_indices(
                selected_faces, solid._iter_faces()
            )

        target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
        finalized = _finalize_tracked_solid(
            result,
            op=_OP_MAKE_SHELL_RSOLID,
            params=selection_params,
            source_solid=solid,
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[solid, *selected_faces],
        )
        return _apply_operation_role_tags(
            finalized,
            op=_OP_MAKE_SHELL_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="shell_rsolid",
            what_happened="Failed to apply the shell operation.",
            possible_causes=[
                "The thickness is not a positive finite scalar.",
                "No valid faces were selected for removal.",
                "The requested shell thickness is incompatible with the current solid.",
            ],
            how_to_fix=[
                "Use a positive shell thickness.",
                "Select at least one valid face to remove.",
                "If the shell fails, try a smaller thickness or a different face selection.",
            ],
            error=e,
        )

def loft_rsolid(
    profiles: Sequence[Union[Wire, Vertex]],
    ruled: bool = False,
    *,
    tracking_policy: TrackingPolicy | str = TrackingPolicy.FULL,
    tag_prefix: Optional[str] = None,
    result_tag: Optional[str] = None,
    start_face_tag: Optional[str] = None,
    end_face_tag: Optional[str] = None,
    side_faces_tag: Optional[str] = None,
) -> Solid:
    """Create a lofted solid, with optional kernel-role-based tags."""
    try:
        profile_list = _validated_loft_sections(profiles, operation="loft_rsolid")
        if start_face_tag is not None and isinstance(profile_list[0], Vertex):
            raise ValueError("start_face_tag requires a Wire start section")
        if end_face_tag is not None and isinstance(profile_list[-1], Vertex):
            raise ValueError("end_face_tag requires a Wire end section")
        policy = (
            TrackingPolicy.GRAPH
            if current_tracking_policy() == TrackingPolicy.GRAPH
            else TrackingPolicy(tracking_policy)
        )
        assignments = _normalize_operation_role_tags(
            _OP_MAKE_LOFT_RSOLID,
            (
                ("loft.start", start_face_tag),
                ("loft.end", end_face_tag),
                ("loft.side", side_faces_tag),
            ),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        profiles = profile_list

        if policy == TrackingPolicy.GRAPH and (assignments or tag_prefix is not None):
            raise ValueError(
                "GRAPH tracking does not provide loft face-role evidence; "
                "use FULL tracking for tag_prefix, start_face_tag, end_face_tag, "
                "or side_faces_tag"
            )

        tracked = (
            tracked_loft(profiles, ruled=ruled)
            if policy == TrackingPolicy.FULL
            else None
        )
        result = (
            cast(Solid, tracked.shape)
            if tracked is not None
            else Solid(
                make_loft_solid((profile.wrapped for profile in profiles), ruled=ruled)
            )
        )

        all_metadata = {}
        for profile in profiles:
            all_metadata.update(profile._metadata)

        result._metadata = all_metadata

        params: Dict[str, object] = {
            "profile_count": len(profiles),
            "ruled": ruled,
            "tracking_policy": policy.value,
        }
        if tracked is not None:
            target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
            finalized = _finalize_tracked_solid(
                result,
                op=_OP_MAKE_LOFT_RSOLID,
                params=params,
                delta=tracked.delta,
                delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
                input_shapes=profiles,
            )
        else:
            target_kinds = {}
            finalized = cast(
                Solid,
                _finalize_derived_shape(
                    result,
                    op=_OP_MAKE_LOFT_RSOLID,
                    params=params,
                    input_shapes=profiles,
                ),
            )
        tagged = _apply_operation_role_tags(
            finalized,
            op=_OP_MAKE_LOFT_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
        if tracked is None:
            return tagged
        return _apply_feature_tag_prefix(
            tagged,
            tag_prefix=tag_prefix,
            op=_OP_MAKE_LOFT_RSOLID,
            delta=tracked.delta,
            start_role=("loft.start" if isinstance(profiles[0], Wire) else None),
            end_role=("loft.end" if isinstance(profiles[-1], Wire) else None),
            side_role="loft.side",
            source_shapes=profiles,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="loft_rsolid",
            what_happened="Failed to loft the input profiles into a solid.",
            possible_causes=[
                "Fewer than two sections were provided.",
                "A Vertex section was used away from the start or end.",
                "One or more Wire/Vertex sections are invalid or incompatible.",
                "The kernel rejected the loft because the section geometry is inconsistent.",
            ],
            how_to_fix=[
                "Pass at least two Wire or endpoint Vertex sections.",
                "Keep Wire topology compatible across sections.",
                "If loft fails, inspect each section individually and simplify its geometry.",
            ],
            error=e,
        )

def sweep_rsolid(
    profile: Face,
    path: Wire,
    is_frenet: bool = False,
    *,
    tag_prefix: Optional[str] = None,
    result_tag: Optional[str] = None,
    start_face_tag: Optional[str] = None,
    end_face_tag: Optional[str] = None,
    side_faces_tag: Optional[str] = None,
) -> Solid:
    """Create a swept solid, with optional kernel-role-based tags."""
    make_solid = True  # 默认创建实体
    try:
        assignments = _normalize_operation_role_tags(
            _OP_MAKE_SWEEP_RSOLID,
            (
                ("sweep.start", start_face_tag),
                ("sweep.end", end_face_tag),
                ("sweep.side", side_faces_tag),
            ),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        tracked = tracked_sweep(profile, path, is_frenet=is_frenet)
        result = cast(Solid, tracked.shape)

        result._metadata = {**profile._metadata, **path._metadata}

        target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
        finalized = _finalize_tracked_solid(
            result,
            op=_OP_MAKE_SWEEP_RSOLID,
            params={"is_frenet": bool(is_frenet)},
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[profile, path],
        )
        tagged = _apply_operation_role_tags(
            finalized,
            op=_OP_MAKE_SWEEP_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
        return _apply_feature_tag_prefix(
            tagged,
            tag_prefix=tag_prefix,
            op=_OP_MAKE_SWEEP_RSOLID,
            delta=tracked.delta,
            start_role="sweep.start",
            end_role="sweep.end",
            side_role="sweep.side",
            source_shapes=[profile],
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="sweep_rsolid",
            what_happened="Failed to sweep the profile along the path.",
            possible_causes=[
                "The profile face is invalid.",
                "The path wire is invalid or unsuitable for sweep.",
                "The kernel rejected the sweep orientation or geometry.",
            ],
            how_to_fix=[
                "Pass a valid Face profile and a valid Wire path.",
                "Check that the path wire is continuous and geometrically reasonable.",
                "If sweep fails, simplify the profile or path before retrying.",
            ],
            error=e,
        )

def twisted_sweep_rsolid(
    profile: Face,
    distance: ScalarLike,
    twist_angle: ScalarLike,
    axis: Tuple[float, float, float] = (0.0, 0.0, 1.0),
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    *,
    guide_radius: ScalarLike = 1.0,
    tag_prefix: Optional[str] = None,
    result_tag: Optional[str] = None,
    start_face_tag: Optional[str] = None,
    end_face_tag: Optional[str] = None,
    side_faces_tag: Optional[str] = None,
) -> Solid:
    """Sweep a planar profile along a straight axis with linear rotation.

    ``twist_angle`` is the signed total rotation in degrees. The operation uses
    a cylindrical auxiliary spine to define a continuous rotation law, yielding
    one continuous side face per profile edge instead of a segmented ruled loft.
    """
    try:
        if not isinstance(profile, Face):
            raise TypeError("profile must be a Face")
        distance_value = float(evaluate_scalar(distance))
        twist_value = float(evaluate_scalar(twist_angle))
        guide_radius_value = float(evaluate_scalar(guide_radius))
        if not math.isfinite(distance_value) or distance_value <= 0.0:
            raise ValueError("distance must be a finite positive number")
        if not math.isfinite(twist_value):
            raise ValueError("twist_angle must be finite")
        if not math.isfinite(guide_radius_value) or guide_radius_value <= 0.0:
            raise ValueError("guide_radius must be a finite positive number")

        axis_value = cast(Tuple[float, float, float], evaluate_value(axis))
        origin_value = cast(Tuple[float, float, float], evaluate_value(origin))
        if len(axis_value) != 3 or len(origin_value) != 3:
            raise ValueError("axis and origin must each contain three values")
        cs = get_current_cs()
        global_axis = cs.transform_vector(np.asarray(axis_value, dtype=float))
        global_origin = cs.transform_point(np.asarray(origin_value, dtype=float))
        axis_norm = float(np.linalg.norm(global_axis))
        if not math.isfinite(axis_norm) or axis_norm <= 1.0e-15:
            raise ValueError("axis must be a finite non-zero vector")
        global_axis /= axis_norm
        resolved_axis = tuple(float(value) for value in global_axis)
        resolved_origin = tuple(float(value) for value in global_origin)

        assignments = _normalize_operation_role_tags(
            _OP_MAKE_TWISTED_SWEEP_RSOLID,
            (
                ("twisted_sweep.start", start_face_tag),
                ("twisted_sweep.end", end_face_tag),
                ("twisted_sweep.side", side_faces_tag),
            ),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        tracked = tracked_twisted_sweep(
                profile,
                axis=resolved_axis,
                origin=resolved_origin,
                distance=distance_value,
                twist_angle=twist_value,
                guide_radius=guide_radius_value,
            )
        result = cast(Solid, tracked.shape)
        kernel_metadata = result.get_metadata("twisted_sweep.kernel", {})
        result._metadata = profile._metadata.copy()
        result.set_metadata("twisted_sweep.kernel", kernel_metadata)

        target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
        finalized = _finalize_tracked_solid(
            result,
            op=_OP_MAKE_TWISTED_SWEEP_RSOLID,
            params={
                "axis": axis,
                "origin": origin,
                "distance": distance,
                "twist_angle": twist_angle,
                "guide_radius": guide_radius,
            },
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[profile],
        )
        tagged = _apply_operation_role_tags(
            finalized,
            op=_OP_MAKE_TWISTED_SWEEP_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
        return _apply_feature_tag_prefix(
            tagged,
            tag_prefix=tag_prefix,
            op=_OP_MAKE_TWISTED_SWEEP_RSOLID,
            delta=tracked.delta,
            start_role="twisted_sweep.start",
            end_role="twisted_sweep.end",
            side_role="twisted_sweep.side",
            source_shapes=[profile],
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="twisted_sweep_rsolid",
            what_happened="Failed to sweep the profile with a linear axial rotation.",
            possible_causes=[
                "The profile is invalid or contains inner wires.",
                "The distance, twist angle, axis, or guide radius is invalid.",
                "The requested twist causes self-intersection or kernel failure.",
            ],
            how_to_fix=[
                "Pass a valid planar Face without inner wires.",
                "Use a positive distance and guide radius with a non-zero axis.",
                "Reduce the twist angle or simplify the profile.",
            ],
            error=e,
        )

def helical_sweep_rsolid(
    profile: Wire,
    pitch: float,
    height: float,
    radius: float,
    center: Tuple[float, float, float] = (0, 0, 0),
    dir: Tuple[float, float, float] = (0, 0, 1),
    *,
    handedness: str = "Right",
) -> Solid:
    """Create a solid by sweeping a profile along a helical path."""
    try:
        if get_active_session() is not None:
            helix = make_helix_rwire(
                pitch, height, radius, center=center, dir=dir,
                handedness=handedness,
            )
            return sweep_rsolid(
                make_face_from_wire_rface(profile), helix, is_frenet=True
            )

        if pitch <= 0:
            raise ValueError("螺距必须大于0")
        if height <= 0:
            raise ValueError("高度必须大于0")
        if radius <= 0:
            raise ValueError("半径必须大于0")

        cs = get_current_cs()
        global_center = cs.transform_point(np.array(center))
        global_dir = cs.transform_vector(np.array(dir))
        global_x_direction = cs.transform_vector(_default_plane_x_direction(dir))

        result_shape = make_helical_sweep_solid(
            profile.wrapped,
            pitch,
            height,
            radius,
            global_center,
            global_dir,
            x_direction=global_x_direction,
        )
        result = Solid(result_shape)

        result._metadata = profile._metadata.copy()
        result._apply_tag("solid.feature.helical_sweep", propagate=False)

        return result
    except Exception as e:
        _wrap_public_api_error(
            operation="helical_sweep_rsolid",
            what_happened="Failed to create the helical sweep solid.",
            possible_causes=[
                "Pitch, height, or radius is not positive.",
                "The input profile wire is invalid or cannot form a face.",
                "The center or direction vector is invalid.",
                "The underlying helix or sweep construction failed.",
            ],
            how_to_fix=[
                "Use positive pitch, height, and radius values.",
                "Pass a valid profile wire that can be turned into a face.",
                "Validate the center and direction inputs before retrying.",
                "If the sweep still fails, try the explicit macro path: helix wire -> face from profile -> sweep.",
            ],
            error=e,
        )

__all__ = tuple(name for name in globals() if not name.startswith("__"))
