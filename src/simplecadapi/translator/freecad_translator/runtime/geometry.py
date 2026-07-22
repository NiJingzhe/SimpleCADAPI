def _vec(v):
    return App.Vector(float(v[0]), float(v[1]), float(v[2]))


def _placement_from_axes_payload(payload):
    origin = payload.get('origin', (0.0, 0.0, 0.0))
    x_axis = payload.get('x_axis', (1.0, 0.0, 0.0))
    y_axis = payload.get('y_axis', (0.0, 1.0, 0.0))
    z_axis = payload.get('z_axis')
    if z_axis is None:
        x = _vec(x_axis)
        y = _vec(y_axis)
        z = x.cross(y)
        length = float(getattr(z, 'Length', 0.0))
        if length == 0.0:
            raise RuntimeError('Placement axes do not form a frame')
        z_axis = (z.x / length, z.y / length, z.z / length)
    matrix = App.Matrix()
    matrix.A11 = float(x_axis[0]); matrix.A12 = float(y_axis[0]); matrix.A13 = float(z_axis[0]); matrix.A14 = float(origin[0])
    matrix.A21 = float(x_axis[1]); matrix.A22 = float(y_axis[1]); matrix.A23 = float(z_axis[1]); matrix.A24 = float(origin[1])
    matrix.A31 = float(x_axis[2]); matrix.A32 = float(y_axis[2]); matrix.A33 = float(z_axis[2]); matrix.A34 = float(origin[2])
    return App.Placement(matrix)


def _connector_tuple3(value, default=(0.0, 0.0, 0.0)):
    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except Exception:
            pass
    return (float(default[0]), float(default[1]), float(default[2]))


def _dot3(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross3(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _unit3(value, default=(0.0, 0.0, 1.0)):
    vec = _connector_tuple3(value, default)
    length = math.sqrt(_dot3(vec, vec))
    if length <= 1.0e-12:
        vec = _connector_tuple3(default, (0.0, 0.0, 1.0))
        length = math.sqrt(_dot3(vec, vec))
    return (vec[0] / length, vec[1] / length, vec[2] / length)


def _orthogonal_axis3(z_axis):
    candidates = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    best = min(candidates, key=lambda candidate: abs(_dot3(z_axis, candidate)))
    projected = (
        best[0] - z_axis[0] * _dot3(z_axis, best),
        best[1] - z_axis[1] * _dot3(z_axis, best),
        best[2] - z_axis[2] * _dot3(z_axis, best),
    )
    return _unit3(projected, (1.0, 0.0, 0.0))


def _placement_from_geometry_ref_payload(geometry_ref):
    geometry_ref = geometry_ref or {}
    selector = geometry_ref.get('geo_selector') or {}
    kind = str(geometry_ref.get('kind') or selector.get('kind') or '').lower()
    flip = bool(geometry_ref.get('flip', False))
    if kind == 'face':
        origin = _connector_tuple3(selector.get('center'), (0.0, 0.0, 0.0))
        z_axis = _unit3(selector.get('normal'), (0.0, 0.0, 1.0))
        if flip:
            z_axis = (-z_axis[0], -z_axis[1], -z_axis[2])
        x_axis = _orthogonal_axis3(z_axis)
        y_axis = _unit3(_cross3(z_axis, x_axis), (0.0, 1.0, 0.0))
        return _placement_from_axes_payload({'origin': origin, 'x_axis': x_axis, 'y_axis': y_axis})
    if kind == 'edge':
        origin = _connector_tuple3(selector.get('center'), (0.0, 0.0, 0.0))
        start = selector.get('start')
        end = selector.get('end')
        if isinstance(start, (list, tuple)) and isinstance(end, (list, tuple)):
            s = _connector_tuple3(start)
            e = _connector_tuple3(end)
            direction = (e[0] - s[0], e[1] - s[1], e[2] - s[2])
        else:
            direction = (1.0, 0.0, 0.0)
        z_axis = _unit3(direction, (1.0, 0.0, 0.0))
        if flip:
            z_axis = (-z_axis[0], -z_axis[1], -z_axis[2])
        x_axis = _orthogonal_axis3(z_axis)
        y_axis = _unit3(_cross3(z_axis, x_axis), (0.0, 1.0, 0.0))
        return _placement_from_axes_payload({'origin': origin, 'x_axis': x_axis, 'y_axis': y_axis})
    if kind == 'vertex':
        return _placement_from_axes_payload({'origin': _connector_tuple3(selector.get('coordinates'), (0.0, 0.0, 0.0))})
    return _placement_from_axes_payload({'origin': _connector_tuple3(selector.get('center'), (0.0, 0.0, 0.0))})


def _connector_anchor_payload(connector_payload):
    anchor = connector_payload.get('anchor') if isinstance(connector_payload, dict) else None
    if isinstance(anchor, dict):
        return anchor
    geometry_ref = connector_payload.get('geometry_ref') if isinstance(connector_payload, dict) else None
    if isinstance(geometry_ref, dict):
        return {'anchor_kind': 'geometry', 'geometry_ref': geometry_ref}
    return {'anchor_kind': 'placement', 'placement': {'origin': (0.0, 0.0, 0.0)}}


def _connector_payload_for_item(item, connector_id):
    for connector in list((item or {}).get('connectors', []) or []):
        if str(connector.get('connector_id')) == str(connector_id):
            return connector
    raise RuntimeError(f'Missing connector {connector_id!r} on product item')


def _connector_metadata_payload(connector_payload):
    payload = dict(connector_payload or {})
    payload.pop('datum', None)
    payload.pop('placement', None)
    return payload


def _connector_local_placement(item, connector_payload, seen=None):
    seen = set(seen or set())
    connector_id = str((connector_payload or {}).get('connector_id', ''))
    key = (id(item), connector_id)
    if key in seen:
        raise RuntimeError(f'forwarded connector cycle detected at {connector_id!r}')
    seen.add(key)
    anchor = _connector_anchor_payload(connector_payload or {})
    kind = str(anchor.get('anchor_kind') or '').lower()
    if kind == 'geometry':
        return _placement_from_geometry_ref_payload(anchor.get('geometry_ref') or (connector_payload or {}).get('geometry_ref'))
    if kind == 'placement':
        return _placement_from_axes_payload(anchor.get('placement') or {})
    if kind == 'forwarded':
        source_component = _find_component_entry(item or {}, anchor.get('source_component_id'))
        source_item = source_component.get('item') or {}
        source_connector = _connector_payload_for_item(source_item, anchor.get('source_connector_id'))
        source_placement = _placement_from_axes_payload(source_component.get('placement') or {})
        result = source_placement.multiply(_connector_local_placement(source_item, source_connector, seen))
        if isinstance(anchor.get('offset'), dict):
            result = result.multiply(_placement_from_axes_payload(anchor.get('offset')))
        return result
    return App.Placement()


def _make_connector_datum(container, connector_payload, placement):
    connector_id = str((connector_payload or {}).get('connector_id') or 'connector')
    metadata_payload = _connector_metadata_payload(connector_payload)
    object_name = 'connector_' + _simplecad_slug(connector_id, prefix='connector')
    datum = None
    try:
        datum = container.newObject('PartDesign::CoordinateSystem', object_name)
    except Exception:
        datum = container.newObject('App::FeaturePython', object_name)
    datum.Label = 'connector.' + connector_id
    _ensure_placement_property(datum)
    datum.Placement = placement
    _ensure_string_property(datum, 'SimpleCADConnectorId')
    _ensure_string_property(datum, 'SimpleCADConnector')
    datum.SimpleCADConnectorId = connector_id
    datum.SimpleCADConnector = json.dumps(metadata_payload, ensure_ascii=True, sort_keys=True)
    _set_visibility(datum, True)
    return datum


def _materialize_product_connector_datums(product_value):
    container = (product_value or {}).get('container')
    if container is None:
        return product_value
    resolved = []
    for connector in list((product_value or {}).get('connectors', []) or []):
        connector = dict(connector)
        try:
            placement = _connector_local_placement(product_value, connector)
            connector['datum'] = _make_connector_datum(container, connector, placement)
            connector['placement'] = placement
        except Exception:
            pass
        resolved.append(connector)
    product_value['connectors'] = resolved
    return product_value


def _component_connector_proxy(assembly_value, component_entry, connector_payload):
    assembly_container = assembly_value.get('container')
    if assembly_container is None:
        raise RuntimeError('Assembly value has no container for connector proxy')
    link = component_entry.get('link')
    link_placement = getattr(link, 'Placement', App.Placement()) if link is not None else _placement_from_axes_payload(component_entry.get('placement') or {})
    local_placement = _connector_local_placement(component_entry.get('item') or {}, connector_payload)
    proxy_payload = dict(connector_payload or {})
    proxy_payload['connector_id'] = str(component_entry.get('component_id')) + '.' + str(proxy_payload.get('connector_id', 'connector'))
    return _make_connector_datum(assembly_container, proxy_payload, link_placement.multiply(local_placement))


def _shape_from_component_link(link):
    source = getattr(link, 'LinkedObject', None)
    if source is None or not hasattr(source, 'Shape'):
        raise RuntimeError('Component link has no shape-bearing linked object')
    shape = source.Shape.copy()
    try:
        shape.Placement = link.Placement.multiply(shape.Placement)
    except Exception:
        pass
    return shape
def _materialize_boolean_operand(obj, name):
    if getattr(obj, 'TypeId', '') != 'App::Link':
        return obj
    shape = _shape_from_component_link(obj)
    wrapper = doc.addObject('Part::Feature', name)
    wrapper.Label = str(name)
    wrapper.Shape = shape
    _ensure_string_property(wrapper, 'SimpleCADMaterializedFromLink')
    wrapper.SimpleCADMaterializedFromLink = str(getattr(obj, 'Name', ''))
    _set_visibility(wrapper, False)
    return wrapper


def _placed_shape_from_body(body, placement):
    if body is None or not hasattr(body, 'Shape'):
        raise RuntimeError('Part product value has no shape-bearing body')
    shape = body.Shape.copy()
    try:
        shape.Placement = placement.multiply(shape.Placement)
    except Exception:
        pass
    return shape


def _shapes_from_product_value(value, placement=None):
    placement = placement or App.Placement()
    if value.get('kind') == 'part':
        return [_placed_shape_from_body(value.get('body'), placement)]
    if value.get('kind') == 'assembly':
        shapes = []
        for component in value.get('components', []):
            component_placement = component.get('link').Placement if component.get('link') is not None else _placement_from_axes_payload(component.get('placement') or {})
            shapes.extend(_shapes_from_product_value(component.get('item'), placement.multiply(component_placement)))
        return shapes
    raise RuntimeError('Unsupported product value for shape projection')


def _normalized_vec(v):
    vec = _vec(v)
    length = float(getattr(vec, 'Length', 0.0))
    if length == 0.0:
        raise RuntimeError('Expected a non-zero vector')
    return App.Vector(vec.x / length, vec.y / length, vec.z / length)


def _scaled_direction(direction, distance):
    unit = _normalized_vec(direction)
    dist = float(distance)
    return App.Vector(unit.x * dist, unit.y * dist, unit.z * dist)


def _twisted_sweep_loft_shape(profile_obj, *, axis, origin, distance, twist_angle):
    operation = 'make_twisted_sweep_rsolid'
    face = _face_shape_from_wire_shape(profile_obj, operation)
    wires = list(getattr(face, 'Wires', []) or [])
    if len(wires) != 1:
        raise RuntimeError(f'{operation} emulation requires a face with one outer wire')

    axis_vec = _normalized_vec(axis)
    origin_vec = _vec(origin)
    distance_value = float(distance)
    twist_value = float(twist_angle)
    if not math.isfinite(distance_value) or distance_value <= 0.0:
        raise RuntimeError(f'{operation} distance must be finite and positive')
    if not math.isfinite(twist_value):
        raise RuntimeError(f'{operation} twist angle must be finite')

    section_count = max(3, int(math.ceil(abs(twist_value) / 30.0)) + 1)
    sections = []
    for index in range(section_count):
        fraction = float(index) / float(section_count - 1)
        section = wires[0].copy()
        angle = twist_value * fraction
        if abs(angle) > 1.0e-12:
            section.rotate(origin_vec, axis_vec, angle)
        offset = distance_value * fraction
        if abs(offset) > 1.0e-12:
            section.translate(App.Vector(axis_vec.x * offset, axis_vec.y * offset, axis_vec.z * offset))
        sections.append(section)

    result = Part.makeLoft(sections, True, False, False, 5)
    if result is None or result.isNull() or not result.isValid():
        raise RuntimeError(f'{operation} loft emulation produced an invalid shape')
    if len(list(getattr(result, 'Solids', []) or [])) != 1:
        raise RuntimeError(f'{operation} loft emulation did not produce one solid')
    return result


def _placement_from_context(context):
    origin = context.get('origin') if isinstance(context, dict) else None
    if isinstance(origin, (list, tuple)) and len(origin) == 3:
        return App.Placement(_vec(origin), App.Rotation())
    return App.Placement()


def _rotation_from_context_axes(context):
    if not isinstance(context, dict):
        return App.Rotation()
    x_axis = context.get('x_axis')
    y_axis = context.get('y_axis')
    z_axis = context.get('z_axis')
    if not (
        isinstance(x_axis, (list, tuple)) and len(x_axis) == 3 and
        isinstance(y_axis, (list, tuple)) and len(y_axis) == 3 and
        isinstance(z_axis, (list, tuple)) and len(z_axis) == 3
    ):
        return App.Rotation()
    m = App.Matrix()
    m.A11, m.A21, m.A31 = float(x_axis[0]), float(x_axis[1]), float(x_axis[2])
    m.A12, m.A22, m.A32 = float(y_axis[0]), float(y_axis[1]), float(y_axis[2])
    m.A13, m.A23, m.A33 = float(z_axis[0]), float(z_axis[1]), float(z_axis[2])
    return App.Rotation(m)


def _sketch_placement_from_context(context):
    origin = context.get('origin') if isinstance(context, dict) else None
    base = _vec(origin) if isinstance(origin, (list, tuple)) and len(origin) == 3 else App.Vector(0.0, 0.0, 0.0)
    return App.Placement(base, _rotation_from_context_axes(context))


def _line_sketch_placement(start, end):
    start_v = _vec(start)
    end_v = _vec(end)
    delta = App.Vector(end_v.x - start_v.x, end_v.y - start_v.y, end_v.z - start_v.z)
    x_axis = _normalized_vec((delta.x, delta.y, delta.z))
    ref = App.Vector(0.0, 0.0, 1.0)
    dot = abs(float(x_axis.x * ref.x + x_axis.y * ref.y + x_axis.z * ref.z))
    if dot > 0.95:
        ref = App.Vector(0.0, 1.0, 0.0)
    z_axis = x_axis.cross(ref)
    z_len = float(getattr(z_axis, 'Length', 0.0))
    if z_len == 0.0:
        ref = App.Vector(1.0, 0.0, 0.0)
        z_axis = x_axis.cross(ref)
        z_len = float(getattr(z_axis, 'Length', 0.0))
    z_axis = App.Vector(z_axis.x / z_len, z_axis.y / z_len, z_axis.z / z_len)
    y_axis = z_axis.cross(x_axis)
    y_len = float(getattr(y_axis, 'Length', 0.0))
    y_axis = App.Vector(y_axis.x / y_len, y_axis.y / y_len, y_axis.z / y_len)
    m = App.Matrix()
    m.A11, m.A21, m.A31 = x_axis.x, x_axis.y, x_axis.z
    m.A12, m.A22, m.A32 = y_axis.x, y_axis.y, y_axis.z
    m.A13, m.A23, m.A33 = z_axis.x, z_axis.y, z_axis.z
    rotation = App.Rotation(m)
    return App.Placement(start_v, rotation), float(getattr(delta, 'Length', 0.0))


def _pick_perpendicular_axis(vec):
    ref = App.Vector(0.0, 0.0, 1.0)
    dot = abs(float(vec.x * ref.x + vec.y * ref.y + vec.z * ref.z))
    if dot > 0.95:
        ref = App.Vector(0.0, 1.0, 0.0)
    perp = vec.cross(ref)
    length = float(getattr(perp, 'Length', 0.0))
    if length == 0.0:
        ref = App.Vector(1.0, 0.0, 0.0)
        perp = vec.cross(ref)
        length = float(getattr(perp, 'Length', 0.0))
    return App.Vector(perp.x / length, perp.y / length, perp.z / length)


def _frame_from_points(points, fallback_context=None):
    if not points:
        raise RuntimeError('Expected at least one point for sketch frame')
    origin = _vec(points[0])
    fallback_x = None
    fallback_y = None
    fallback_z = None
    if isinstance(fallback_context, dict):
        raw_x = fallback_context.get('x_axis')
        raw_y = fallback_context.get('y_axis')
        raw_z = fallback_context.get('z_axis')
        if isinstance(raw_x, (list, tuple)) and len(raw_x) == 3:
            try:
                fallback_x = _normalized_vec(raw_x)
            except Exception:
                fallback_x = None
        if isinstance(raw_y, (list, tuple)) and len(raw_y) == 3:
            try:
                fallback_y = _normalized_vec(raw_y)
            except Exception:
                fallback_y = None
        if isinstance(raw_z, (list, tuple)) and len(raw_z) == 3:
            try:
                fallback_z = _normalized_vec(raw_z)
            except Exception:
                fallback_z = None

    if fallback_x is not None and fallback_y is not None and fallback_z is not None:
        scale = 1.0
        on_fallback_plane = True
        for point in points[1:]:
            delta = App.Vector(float(point[0]) - origin.x, float(point[1]) - origin.y, float(point[2]) - origin.z)
            scale = max(scale, float(getattr(delta, 'Length', 0.0)))
            offset = abs(float(delta.x * fallback_z.x + delta.y * fallback_z.y + delta.z * fallback_z.z))
            if offset > max(1e-7, scale * 1e-7):
                on_fallback_plane = False
                break
        if on_fallback_plane:
            m = App.Matrix()
            m.A11, m.A21, m.A31 = fallback_x.x, fallback_x.y, fallback_x.z
            m.A12, m.A22, m.A32 = fallback_y.x, fallback_y.y, fallback_y.z
            m.A13, m.A23, m.A33 = fallback_z.x, fallback_z.y, fallback_z.z
            placement = App.Placement(origin, App.Rotation(m))
            return placement, origin, fallback_x, fallback_y

    x_axis = None
    for point in points[1:]:
        delta = App.Vector(float(point[0]) - origin.x, float(point[1]) - origin.y, float(point[2]) - origin.z)
        length = float(getattr(delta, 'Length', 0.0))
        if length > 1e-9:
            x_axis = App.Vector(delta.x / length, delta.y / length, delta.z / length)
            break
    if x_axis is None:
        x_axis = fallback_x if fallback_x is not None else App.Vector(1.0, 0.0, 0.0)

    z_axis = None
    for point in points[1:]:
        delta = App.Vector(float(point[0]) - origin.x, float(point[1]) - origin.y, float(point[2]) - origin.z)
        candidate = x_axis.cross(delta)
        length = float(getattr(candidate, 'Length', 0.0))
        if length > 1e-9:
            z_axis = App.Vector(candidate.x / length, candidate.y / length, candidate.z / length)
            break

    if z_axis is None and fallback_z is not None:
        dot = abs(float(x_axis.x * fallback_z.x + x_axis.y * fallback_z.y + x_axis.z * fallback_z.z))
        if dot < 0.95:
            z_axis = fallback_z

    if z_axis is None:
        z_axis = _pick_perpendicular_axis(x_axis)

    y_axis = z_axis.cross(x_axis)
    y_len = float(getattr(y_axis, 'Length', 0.0))
    if y_len == 0.0:
        y_axis = _pick_perpendicular_axis(z_axis)
        y_len = float(getattr(y_axis, 'Length', 0.0))
    y_axis = App.Vector(y_axis.x / y_len, y_axis.y / y_len, y_axis.z / y_len)

    m = App.Matrix()
    m.A11, m.A21, m.A31 = x_axis.x, x_axis.y, x_axis.z
    m.A12, m.A22, m.A32 = y_axis.x, y_axis.y, y_axis.z
    m.A13, m.A23, m.A33 = z_axis.x, z_axis.y, z_axis.z
    placement = App.Placement(origin, App.Rotation(m))
    return placement, origin, x_axis, y_axis


def _local_point_on_frame(point, origin, x_axis, y_axis):
    p = _vec(point)
    dx = p.x - origin.x
    dy = p.y - origin.y
    dz = p.z - origin.z
    return App.Vector(
        dx * x_axis.x + dy * x_axis.y + dz * x_axis.z,
        dx * y_axis.x + dy * y_axis.y + dz * y_axis.z,
        0.0,
    )


def _vec_tuple(vec):
    return (float(vec.x), float(vec.y), float(vec.z))


def _first_edge(obj):
    shape = getattr(obj, 'Shape', None) if hasattr(obj, 'Shape') else obj
    if shape is None or shape.isNull():
        raise RuntimeError(f'Object {getattr(obj, "Name", "<unknown>")} has no valid shape')
    edges = list(getattr(shape, 'Edges', []))
    if not edges:
        raise RuntimeError(f'Object {getattr(obj, "Name", "<unknown>")} has no edges')
    return edges[0]


def _edge_start_point(obj):
    edge = _first_edge(obj)
    return _vec_tuple(edge.Vertexes[0].Point)


def _edge_end_point(obj):
    edge = _first_edge(obj)
    return _vec_tuple(edge.Vertexes[-1].Point)


def _edge_mid_point(obj):
    edge = _first_edge(obj)
    point = edge.valueAt(0.5 * (float(edge.FirstParameter) + float(edge.LastParameter)))
    return _vec_tuple(point)


def _arc_from_edge(obj):
    return Part.Arc(_vec(_edge_start_point(obj)), _vec(_edge_mid_point(obj)), _vec(_edge_end_point(obj)))


def _shape_from_graph_node(node_id):
    value = GRAPH_NODES.get(node_id)
    if value is None:
        raise RuntimeError(f'Missing graph node {node_id!r}')
    if isinstance(value, dict) and 'shape' in value:
        return value['shape']
    if hasattr(value, 'Shape'):
        shape = getattr(value, 'Shape', None)
    else:
        shape = value
    try:
        shape_invalid = shape is None or shape.isNull()
    except Exception:
        shape_invalid = shape is None
    if shape_invalid:
        try:
            doc.recompute()
        except Exception:
            pass
        if hasattr(value, 'Shape'):
            shape = getattr(value, 'Shape', None)
    if shape is None or shape.isNull():
        raise RuntimeError(f'Graph node {node_id!r} has no valid shape')
    return shape
