def _subshape_candidates_for_kind(shape, kind):
    kind = str(kind).lower()
    if kind == 'solid':
        return list(getattr(shape, 'Solids', []) or [shape])
    if kind == 'face':
        return list(getattr(shape, 'Faces', []) or [])
    if kind == 'edge':
        return list(getattr(shape, 'Edges', []) or [])
    if kind == 'wire':
        return list(getattr(shape, 'Wires', []) or [])
    if kind == 'vertex':
        return list(getattr(shape, 'Vertexes', []) or [])
    return []


def _point_tuple(point):
    return (float(point.x), float(point.y), float(point.z))


def _candidate_center(candidate):
    center = getattr(candidate, 'CenterOfMass', None)
    if center is not None:
        return _point_tuple(center)
    bound_box = getattr(candidate, 'BoundBox', None)
    if bound_box is not None:
        return (
            (float(bound_box.XMin) + float(bound_box.XMax)) / 2.0,
            (float(bound_box.YMin) + float(bound_box.YMax)) / 2.0,
            (float(bound_box.ZMin) + float(bound_box.ZMax)) / 2.0,
        )
    return None


def _tuple3(value):
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    return None


def _dist3(a, b):
    if a is None or b is None:
        return 1e6
    return math.dist(a, b)


def _relative_scalar_delta(actual, expected, floor=1.0):
    try:
        actual_f = float(actual)
        expected_f = float(expected)
    except Exception:
        return 1e6
    return abs(actual_f - expected_f) / max(abs(actual_f), abs(expected_f), float(floor))


def _unit_tuple(value):
    if value is None:
        return None
    length = math.sqrt(sum(float(v) * float(v) for v in value))
    if length <= 1e-12:
        return None
    return tuple(float(v) / length for v in value)


def _selector_bbox_diagonal(selector):
    bbox = selector.get('bbox') if isinstance(selector, dict) else None
    if not isinstance(bbox, dict):
        return 1.0
    expected_min = _tuple3(bbox.get('min'))
    expected_max = _tuple3(bbox.get('max'))
    if expected_min is None or expected_max is None:
        return 1.0
    return max(_dist3(expected_min, expected_max), 1.0)


def _candidate_face_normal(candidate):
    try:
        u_min, u_max, v_min, v_max = candidate.ParameterRange
        normal = candidate.normalAt(0.5 * (float(u_min) + float(u_max)), 0.5 * (float(v_min) + float(v_max)))
        return _unit_tuple(_point_tuple(normal))
    except Exception:
        try:
            normal = candidate.normalAt(0.0, 0.0)
            return _unit_tuple(_point_tuple(normal))
        except Exception:
            return None


def _candidate_geom_type(candidate):
    try:
        surface = getattr(candidate, 'Surface', None)
        if surface is not None:
            type_name = type(surface).__name__.replace('Part.', '').upper()
            mapping = {
                'PLANE': 'PLANE',
                'CYLINDER': 'CYLINDER',
                'CONE': 'CONE',
                'SPHERE': 'SPHERE',
                'TORUS': 'TORUS',
                'BSPLINESURFACE': 'BSPLINE',
                'BEZIERSURFACE': 'BEZIER',
            }
            return mapping.get(type_name, type_name)
    except Exception:
        pass
    try:
        curve = getattr(candidate, 'Curve', None)
        if curve is not None:
            type_name = type(curve).__name__.replace('Part.', '').upper()
            mapping = {
                'LINE': 'LINE',
                'LINESEGMENT': 'LINE',
                'CIRCLE': 'CIRCLE',
                'BSPLINECURVE': 'BSPLINE',
                'BEZIERCURVE': 'BEZIER',
            }
            return mapping.get(type_name, type_name)
    except Exception:
        pass
    return None


def _bbox_selector_score(candidate, selector):
    bbox = selector.get('bbox') if isinstance(selector, dict) else None
    bound_box = getattr(candidate, 'BoundBox', None)
    if not isinstance(bbox, dict) or bound_box is None:
        return 0.0
    expected_min = _tuple3(bbox.get('min'))
    expected_max = _tuple3(bbox.get('max'))
    if expected_min is None or expected_max is None:
        return 1e6
    actual_min = (float(bound_box.XMin), float(bound_box.YMin), float(bound_box.ZMin))
    actual_max = (float(bound_box.XMax), float(bound_box.YMax), float(bound_box.ZMax))
    return (_dist3(actual_min, expected_min) + _dist3(actual_max, expected_max)) / _selector_bbox_diagonal(selector)


def _geo_selector_score(candidate, selector, candidate_index):
    score = _bbox_selector_score(candidate, selector) * 10.0
    expected_geom_type = str(selector.get('geom_type') or '').upper()
    actual_geom_type = _candidate_geom_type(candidate)
    if expected_geom_type and actual_geom_type and expected_geom_type != actual_geom_type:
        score += 10.0
    kind = str(selector.get('kind', '')).lower()
    if kind == 'edge':
        if 'length' in selector and hasattr(candidate, 'Length'):
            score += _relative_scalar_delta(candidate.Length, selector['length']) * 10.0
        score += (_dist3(_candidate_center(candidate), _tuple3(selector.get('center'))) / _selector_bbox_diagonal(selector)) * 10.0
        vertices = list(getattr(candidate, 'Vertexes', []) or [])
        if len(vertices) >= 2:
            start = _point_tuple(vertices[0].Point)
            end = _point_tuple(vertices[-1].Point)
            expected_start = _tuple3(selector.get('start'))
            expected_end = _tuple3(selector.get('end'))
            if expected_start is not None and expected_end is not None:
                direct = _dist3(start, expected_start) + _dist3(end, expected_end)
                reverse = _dist3(start, expected_end) + _dist3(end, expected_start)
                score += min(direct, reverse) / max(float(candidate.Length), float(selector.get('length', 1.0)), 1.0)
    elif kind == 'face':
        if 'area' in selector and hasattr(candidate, 'Area'):
            score += _relative_scalar_delta(candidate.Area, selector['area']) * 10.0
        score += (_dist3(_candidate_center(candidate), _tuple3(selector.get('center'))) / _selector_bbox_diagonal(selector)) * 10.0
        expected_normal = _unit_tuple(_tuple3(selector.get('normal')))
        actual_normal = _candidate_face_normal(candidate)
        if expected_normal is not None and actual_normal is not None:
            reversed_expected = tuple(-float(v) for v in expected_normal)
            score += min(_dist3(actual_normal, expected_normal), _dist3(actual_normal, reversed_expected))
        if 'edge_count' in selector:
            score += abs(len(list(getattr(candidate, 'Edges', []) or [])) - int(selector['edge_count'])) * 0.001
        if 'inner_wire_count' in selector:
            score += abs(max(0, len(list(getattr(candidate, 'Wires', []) or [])) - 1) - int(selector['inner_wire_count'])) * 0.001
    elif kind == 'vertex':
        point = getattr(candidate, 'Point', None)
        if point is not None:
            score += (_dist3(_point_tuple(point), _tuple3(selector.get('coordinates'))) / _selector_bbox_diagonal(selector)) * 10.0
    elif kind == 'wire':
        edges = list(getattr(candidate, 'Edges', []) or [])
        if 'edge_count' in selector:
            score += abs(len(edges) - int(selector['edge_count'])) * 10.0
    elif kind == 'solid':
        if 'volume' in selector and hasattr(candidate, 'Volume'):
            score += _relative_scalar_delta(candidate.Volume, selector['volume']) * 10.0
    return score


def _selection_index_for_selector(source_shape, selector):
    kind = str(selector.get('kind') or selector.get('target_kind') or '').lower()
    candidates = _subshape_candidates_for_kind(source_shape, kind)
    if not candidates:
        raise RuntimeError(f'No {kind} candidates available for geo selection')
    ranked = sorted(
        enumerate(candidates),
        key=lambda item: _geo_selector_score(item[1], selector, item[0]),
    )
    best_index, best_candidate = ranked[0]
    best_score = _geo_selector_score(best_candidate, selector, best_index)
    if best_score > 1e-2:
        second_score = None
        if len(ranked) > 1:
            second_index, second_candidate = ranked[1]
            second_score = _geo_selector_score(second_candidate, selector, second_index)
        suffix = '' if second_score is None else f', second score={second_score:.6g}'
        raise RuntimeError(f'Geo selector did not match a stable {kind} candidate; best score={best_score:.6g}{suffix}')
    return int(best_index)


def _register_geo_selection_node(*, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    if not inputs:
        raise RuntimeError(f'Selection node {node_id!r} is missing its source input')
    selector = dict(params.get('geo_selector') or {})
    source_node_id = str(inputs[0])
    source_shape = _shape_from_graph_node(source_node_id)
    index = _selection_index_for_selector(source_shape, selector)
    candidates = _subshape_candidates_for_kind(source_shape, selector.get('kind'))
    selected_shape = candidates[index]
    payload = {
        'node_id': node_id,
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
        'output_count': int(output_count),
        'selector': selector,
        'index': int(index),
        'kind': str(selector.get('kind', '')),
        'shape': selected_shape,
    }
    obj = doc.addObject('Part::Feature', f'{str(op)}_{str(node_id)}')
    obj.Shape = selected_shape
    registered = _register_graph_object(
        obj,
        node_id=node_id,
        op=op,
        params=params,
        inputs=inputs,
        tags=tags,
        context=context,
        output_count=output_count,
        param_exprs=param_exprs,
        semantic_delta=semantic_delta,
        topo_delta=topo_delta,
    )
    GRAPH_SELECTIONS[node_id] = payload
    return registered


def _register_tag_selection_node(name, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    if len(inputs) != 1:
        raise RuntimeError(f'Tag selection node {node_id!r} requires exactly one source input')
    binding = params.get('tag_binding')
    if not isinstance(binding, dict):
        raise RuntimeError(f'Tag selection node {node_id!r} is missing its TagBinding payload')
    source_obj = _node_object(str(inputs[0]))
    link_type = 'App::Link'
    obj = doc.addObject(link_type, name)
    obj.LinkedObject = source_obj
    obj.LinkTransform = True
    _ensure_string_property(obj, 'SimpleCADTagBinding')
    obj.SimpleCADTagBinding = json.dumps(binding, ensure_ascii=True, sort_keys=True)
    return _register_graph_object(
        obj,
        node_id=node_id,
        op=op,
        params=params,
        inputs=inputs,
        tags=tags,
        context=context,
        output_count=output_count,
        param_exprs=param_exprs,
        semantic_delta=semantic_delta,
        topo_delta=topo_delta,
    )


def _selected_indices_from_nodes(node_ids, fallback_indices, base_shape=None, kind=None):
    indices = []
    for node_id in node_ids or []:
        payload = GRAPH_SELECTIONS.get(str(node_id)) or GRAPH_NODES.get(str(node_id))
        if isinstance(payload, dict) and base_shape is not None:
            selector = dict(payload.get('selector') or payload.get('params', {}).get('geo_selector') or {})
            if kind is not None:
                selector['kind'] = str(kind)
            if selector:
                indices.append(_selection_index_for_selector(base_shape, selector))
                continue
        if isinstance(payload, dict) and 'index' in payload:
            indices.append(int(payload['index']))
    if indices:
        return indices
    return [int(idx) for idx in (fallback_indices or [])]
