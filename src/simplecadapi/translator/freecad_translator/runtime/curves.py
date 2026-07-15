def _local_line_from_edge(obj, origin, x_axis, y_axis):
    start_3d = _edge_start_point(obj)
    end_3d = _edge_end_point(obj)
    start = _local_point_on_frame(start_3d, origin, x_axis, y_axis)
    end = _local_point_on_frame(end_3d, origin, x_axis, y_axis)
    projected_len = float((end - start).Length)
    source_len = float((_vec(end_3d) - _vec(start_3d)).Length)
    if source_len > 1e-9 and projected_len <= 1e-9:
        raise RuntimeError('Projected non-zero edge collapsed to zero length; sketch frame is not coplanar with the source wire')
    return Part.LineSegment(
        start,
        end,
    )


def _local_arc_from_edge(obj, origin, x_axis, y_axis):
    return Part.Arc(
        _local_point_on_frame(_edge_start_point(obj), origin, x_axis, y_axis),
        _local_point_on_frame(_edge_mid_point(obj), origin, x_axis, y_axis),
        _local_point_on_frame(_edge_end_point(obj), origin, x_axis, y_axis),
    )


def _angle_arc_axes(normal):
    normal_vec = _normalized_vec(normal)
    ref_vec = App.Vector(1.0, 0.0, 0.0) if abs(normal_vec.z) > 0.9 else App.Vector(0.0, 0.0, 1.0)
    local_x = normal_vec.cross(ref_vec)
    x_len = float(getattr(local_x, 'Length', 0.0))
    if x_len == 0.0:
        ref_vec = App.Vector(0.0, 1.0, 0.0)
        local_x = normal_vec.cross(ref_vec)
        x_len = float(getattr(local_x, 'Length', 0.0))
    local_x = App.Vector(local_x.x / x_len, local_x.y / x_len, local_x.z / x_len)
    local_y = normal_vec.cross(local_x)
    y_len = float(getattr(local_y, 'Length', 0.0))
    local_y = App.Vector(local_y.x / y_len, local_y.y / y_len, local_y.z / y_len)
    return local_x, local_y


def _angle_arc_world_point(circle_center, radius, angle, normal):
    center = _vec(circle_center)
    local_x, local_y = _angle_arc_axes(normal)
    r = float(radius)
    theta = float(angle)
    return App.Vector(
        center.x + r * math.cos(theta) * local_x.x + r * math.sin(theta) * local_y.x,
        center.y + r * math.cos(theta) * local_x.y + r * math.sin(theta) * local_y.y,
        center.z + r * math.cos(theta) * local_x.z + r * math.sin(theta) * local_y.z,
    )


def _angle_arc_curve(circle_center, radius, start_angle, end_angle, normal):
    sa = float(start_angle)
    ea = float(end_angle)
    mid_angle = 0.5 * (sa + ea)
    start_world = _angle_arc_world_point(circle_center, radius, sa, normal)
    mid_world = _angle_arc_world_point(circle_center, radius, mid_angle, normal)
    end_world = _angle_arc_world_point(circle_center, radius, ea, normal)
    return Part.Arc(start_world, mid_world, end_world)


def _local_angle_arc(circle_center, radius, start_angle, end_angle, normal, origin, x_axis, y_axis):
    sa = float(start_angle)
    ea = float(end_angle)
    mid_angle = 0.5 * (sa + ea)
    start_local = _local_point_on_frame(
        _vec_tuple(_angle_arc_world_point(circle_center, radius, sa, normal)),
        origin,
        x_axis,
        y_axis,
    )
    mid_local = _local_point_on_frame(
        _vec_tuple(_angle_arc_world_point(circle_center, radius, mid_angle, normal)),
        origin,
        x_axis,
        y_axis,
    )
    end_local = _local_point_on_frame(
        _vec_tuple(_angle_arc_world_point(circle_center, radius, ea, normal)),
        origin,
        x_axis,
        y_axis,
    )
    return Part.Arc(start_local, mid_local, end_local)


def _bspline_curve_from_params(params, transform_point=None):
    poles = []
    for point in params.get('control_points') or []:
        point3 = tuple(point) + (0.0,) if len(tuple(point)) == 2 else tuple(point)
        pole = transform_point(point3) if transform_point is not None else _vec(point3)
        poles.append(pole)
    if not poles and params.get('points'):
        for point in params.get('points') or []:
            point3 = tuple(point) + (0.0,) if len(tuple(point)) == 2 else tuple(point)
            pole = transform_point(point3) if transform_point is not None else _vec(point3)
            poles.append(pole)
        if len(poles) < 2:
            raise RuntimeError('B-spline has fewer than two points')
        curve = Part.BSplineCurve()
        curve.interpolate(poles)
        return curve
    if not poles:
        raise RuntimeError('B-spline has no control points')
    mults = tuple(int(value) for value in (params.get('multiplicities') or []))
    knots = tuple(float(value) for value in (params.get('knots') or []))
    degree = int(params.get('degree', 3))
    periodic = bool(params.get('periodic', False))
    weights = params.get('weights')
    curve = Part.BSplineCurve()
    if weights is None:
        curve.buildFromPolesMultsKnots(poles, mults, knots, periodic, degree)
    else:
        curve.buildFromPolesMultsKnots(poles, mults, knots, periodic, degree, tuple(float(value) for value in weights))
    return curve


def _wire_shape_from_edge_objects(node_ids):
    shapes = []
    for node_id in node_ids:
        shape = _shape_from_graph_node(node_id)
        shapes.append(shape)
    return Part.Wire(shapes)


def _shape_is_null(shape):
    try:
        return shape is None or shape.isNull()
    except Exception:
        return shape is None


def _spine_object(node_id):
    node_id = str(node_id)
    cached = GRAPH_SPINE_OBJECTS.get(node_id)
    if cached is not None:
        return cached
    obj = GRAPH_NODES[node_id]
    try:
        shape = getattr(obj, 'Shape', None)
    except Exception:
        shape = None
    if not _shape_is_null(shape):
        return obj
    meta = GRAPH_METADATA.get(node_id, {})
    if str(meta.get('op', '')) == 'make_wire_from_edges_rwire':
        edge_ids = list(meta.get('inputs') or [])
        if edge_ids:
            fallback = doc.addObject('Part::Feature', f'make_spine_wire_{node_id}')
            fallback.Shape = _wire_shape_from_edge_objects(edge_ids)
            _set_visibility(fallback, False)
            GRAPH_SPINE_OBJECTS[node_id] = fallback
            return fallback
    return obj


def _build_face_from_source(source_obj, name):
    face_obj = doc.addObject('Part::Face', name)
    face_obj.Sources = [source_obj]
    return face_obj
