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
                'ELLIPSE': 'ELLIPSE',
                'BSPLINECURVE': 'BSPLINE',
                'BEZIERCURVE': 'BEZIER',
            }
            result = mapping.get(type_name, type_name)
            if result == 'BSPLINE' and _edge_is_geometrically_linear(candidate):
                return 'LINE'
            return result
    except Exception:
        pass
    return None


def _canonical_geom_type(value):
    text = str(value or '').upper().replace('_TYPE', '').replace('_', '')
    aliases = (
        ('B-SPLINE', 'BSPLINE'),
        ('BSPLINE', 'BSPLINE'),
        ('NURBS', 'BSPLINE'),
        ('BEZIER', 'BEZIER'),
        ('ELLIPTICALARC', 'ELLIPSE'),
        ('ELLIPSE', 'ELLIPSE'),
        ('CYLINDER', 'CYLINDER'),
        ('CIRCLE', 'CIRCLE'),
        ('PLANE', 'PLANE'),
        ('LINE', 'LINE'),
        ('CONE', 'CONE'),
        ('SPHERE', 'SPHERE'),
        ('TORUS', 'TORUS'),
    )
    for token, canonical in aliases:
        if token in text:
            return canonical
    return text


def _edge_endpoints(candidate):
    vertices = list(getattr(candidate, 'Vertexes', []) or [])
    if len(vertices) >= 2:
        return _point_tuple(vertices[0].Point), _point_tuple(vertices[-1].Point)
    try:
        return (
            _point_tuple(candidate.valueAt(float(candidate.FirstParameter))),
            _point_tuple(candidate.valueAt(float(candidate.LastParameter))),
        )
    except Exception:
        return None


def _edge_is_geometrically_linear(candidate):
    endpoints = _edge_endpoints(candidate)
    if endpoints is None:
        return False
    start, end = endpoints
    chord = App.Vector(
        end[0] - start[0], end[1] - start[1], end[2] - start[2]
    )
    chord_length = float(getattr(chord, 'Length', 0.0))
    edge_length = float(getattr(candidate, 'Length', 0.0))
    scale = max(1.0, chord_length, edge_length)
    if chord_length <= scale * 1e-10:
        return False
    if abs(edge_length - chord_length) > scale * 1e-7:
        return False
    try:
        first = float(candidate.FirstParameter)
        last = float(candidate.LastParameter)
        samples = [
            candidate.valueAt(first + (last - first) * index / 8.0)
            for index in range(9)
        ]
    except Exception:
        return False
    origin = App.Vector(*start)
    return all(
        float(getattr((point - origin).cross(chord), 'Length', 0.0))
        / chord_length
        <= scale * 1e-7
        for point in samples
    )


def _selector_geom_type(selector):
    geom_type = _canonical_geom_type(selector.get('geom_type'))
    if geom_type != 'BSPLINE' or str(selector.get('kind', '')).lower() != 'edge':
        return geom_type
    start = _tuple3(selector.get('start'))
    end = _tuple3(selector.get('end'))
    expected_length = selector.get('length')
    if start is None or end is None or expected_length is None:
        return geom_type
    chord_length = _dist3(start, end)
    scale = max(1.0, chord_length, abs(float(expected_length)))
    if abs(float(expected_length) - chord_length) <= scale * 1e-7:
        return 'LINE'
    return geom_type


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
    expected_geom_type = _selector_geom_type(selector)
    actual_geom_type = _canonical_geom_type(_candidate_geom_type(candidate))
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


def _selection_index_for_selector(source_shape, selector, context=None):
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
    second_score = (
        _geo_selector_score(ranked[1][1], selector, ranked[1][0])
        if len(ranked) > 1
        else float('inf')
    )
    if best_score <= 1e-4 and second_score <= 1e-4:
        raise RuntimeError(
            f'Geo selector is ambiguous for {kind}; context={context!r}, '
            f'best score={best_score:.6g}, second score={second_score:.6g}'
        )
    if best_score > 1e-2:
        suffix = '' if second_score == float('inf') else f', second score={second_score:.6g}'
        raise RuntimeError(
            f'Geo selector did not match a stable {kind} candidate; '
            f'context={context!r}, best score={best_score:.6g}{suffix}'
        )
    return int(best_index)


def _same_fragment_support(first, second, expected_type, scale):
    first_type = _canonical_geom_type(_candidate_geom_type(first))
    second_type = _canonical_geom_type(_candidate_geom_type(second))
    if first_type != expected_type or second_type != expected_type:
        return False
    first_endpoints = _edge_endpoints(first)
    second_endpoints = _edge_endpoints(second)
    if first_endpoints is None or second_endpoints is None:
        return False
    tolerance = max(1e-7, scale * 1e-5)
    if expected_type == 'LINE':
        left = App.Vector(
            *(first_endpoints[1][axis] - first_endpoints[0][axis] for axis in range(3))
        )
        right = App.Vector(
            *(second_endpoints[1][axis] - second_endpoints[0][axis] for axis in range(3))
        )
        if float(left.Length) <= 1e-12 or float(right.Length) <= 1e-12:
            return False
        if abs(float(left.dot(right))) / (float(left.Length) * float(right.Length)) < 1.0 - 1e-6:
            return False
        origin = App.Vector(*first_endpoints[0])
        return all(
            float(getattr((App.Vector(*point) - origin).cross(left), 'Length', 0.0))
            / float(left.Length)
            <= tolerance
            for point in second_endpoints
        )
    if expected_type == 'CIRCLE':
        first_curve = getattr(first, 'Curve', None)
        second_curve = getattr(second, 'Curve', None)
        if first_curve is None or second_curve is None:
            return False
        try:
            centers_match = _dist3(
                _point_tuple(first_curve.Center), _point_tuple(second_curve.Center)
            ) <= tolerance
            radii_match = abs(float(first_curve.Radius) - float(second_curve.Radius)) <= tolerance
            axes_match = abs(float(first_curve.Axis.dot(second_curve.Axis))) >= 1.0 - 1e-6
            return centers_match and radii_match and axes_match
        except Exception:
            return False
    return False


def _combined_edge_matches(candidates, selector):
    if len(candidates) < 2:
        return False
    expected_length = selector.get('length')
    expected_center = _tuple3(selector.get('center'))
    expected_bbox = selector.get('bbox')
    if expected_length is None or expected_center is None or not isinstance(expected_bbox, dict):
        return False
    total_length = sum(float(candidate.Length) for candidate in candidates)
    scale = _selector_bbox_diagonal(selector)
    if abs(total_length - float(expected_length)) / max(1.0, abs(float(expected_length))) > 1e-4:
        return False
    weighted_center = tuple(
        sum(_candidate_center(candidate)[axis] * float(candidate.Length) for candidate in candidates)
        / total_length
        for axis in range(3)
    )
    if _dist3(weighted_center, expected_center) / scale > 1e-4:
        return False
    expected_min = _tuple3(expected_bbox.get('min'))
    expected_max = _tuple3(expected_bbox.get('max'))
    actual_min = (
        min(float(candidate.BoundBox.XMin) for candidate in candidates),
        min(float(candidate.BoundBox.YMin) for candidate in candidates),
        min(float(candidate.BoundBox.ZMin) for candidate in candidates),
    )
    actual_max = (
        max(float(candidate.BoundBox.XMax) for candidate in candidates),
        max(float(candidate.BoundBox.YMax) for candidate in candidates),
        max(float(candidate.BoundBox.ZMax) for candidate in candidates),
    )
    return (
        expected_min is not None
        and expected_max is not None
        and (_dist3(actual_min, expected_min) + _dist3(actual_max, expected_max)) / scale <= 1e-4
    )


def _fragmented_edge_indices(source_shape, selector, context=None):
    if str(selector.get('kind', '')).lower() != 'edge':
        return None
    expected_type = _selector_geom_type(selector)
    expected_start = _tuple3(selector.get('start'))
    expected_end = _tuple3(selector.get('end'))
    if expected_type not in {'LINE', 'CIRCLE'} or expected_start is None or expected_end is None:
        return None
    scale = _selector_bbox_diagonal(selector)
    tolerance = max(1e-7, scale * 1e-5)
    if (
        _dist3(expected_start, expected_end) <= tolerance
        and expected_type != 'CIRCLE'
    ):
        return None
    candidates = list(getattr(source_shape, 'Edges', []) or [])
    eligible = [
        (index, candidate, _edge_endpoints(candidate))
        for index, candidate in enumerate(candidates)
        if _canonical_geom_type(_candidate_geom_type(candidate)) == expected_type
        and float(candidate.Length) < float(selector.get('length', candidate.Length)) * (1.0 - 1e-6)
    ]
    eligible = [item for item in eligible if item[2] is not None]
    valid = set()
    for index, candidate, endpoints in eligible:
        next_points = []
        if _dist3(endpoints[0], expected_start) <= tolerance:
            next_points.append(endpoints[1])
        if _dist3(endpoints[1], expected_start) <= tolerance:
            next_points.append(endpoints[0])
        for point in next_points:
            stack = [([index], [candidate], point)]
            while stack:
                indices, group, current = stack.pop()
                if _dist3(current, expected_end) <= tolerance:
                    if _combined_edge_matches(group, selector):
                        valid.add(tuple(sorted(indices)))
                    continue
                if len(indices) >= min(12, len(eligible)):
                    continue
                for next_index, next_candidate, next_endpoints in eligible:
                    if next_index in indices or not _same_fragment_support(
                        group[-1], next_candidate, expected_type, scale
                    ):
                        continue
                    for endpoint_index in (0, 1):
                        if _dist3(next_endpoints[endpoint_index], current) <= tolerance:
                            stack.append((
                                indices + [next_index],
                                group + [next_candidate],
                                next_endpoints[1 - endpoint_index],
                            ))
    if len(valid) == 1:
        return list(next(iter(valid)))
    if len(valid) > 1:
        raise RuntimeError(
            f'Fragmented edge selector is ambiguous; context={context!r}, groups={sorted(valid)!r}'
        )
    return None


def _selection_indices_for_selector(source_shape, selector, context=None):
    try:
        return [_selection_index_for_selector(source_shape, selector, context=context)]
    except RuntimeError as single_error:
        fragmented = _fragmented_edge_indices(source_shape, selector, context=context)
        if fragmented is None:
            raise single_error
        return fragmented


def _merged_selector_group_candidate(source_shape, selectors):
    if len(selectors) < 2:
        return None
    geom_type = _selector_geom_type(selectors[0])
    if any(_selector_geom_type(selector) != geom_type for selector in selectors[1:]):
        return None
    endpoints = [
        (_tuple3(selector.get('start')), _tuple3(selector.get('end')))
        for selector in selectors
    ]
    if any(None in pair for pair in endpoints):
        return None
    scale = max(_selector_bbox_diagonal(selector) for selector in selectors)
    tolerance = max(1e-7, scale * 1e-5)
    if geom_type == 'LINE':
        origin = App.Vector(*endpoints[0][0])
        axis = App.Vector(*endpoints[0][1]) - origin
        if float(axis.Length) <= 1e-12 or any(
            float((App.Vector(*point) - origin).cross(axis).Length)
            / float(axis.Length)
            > tolerance
            for pair in endpoints
            for point in pair
        ):
            return None
    elif geom_type == 'CIRCLE':
        centers = [_tuple3(selector.get('center')) for selector in selectors]
        if any(center is None for center in centers) or any(
            _dist3(centers[0], center) > tolerance for center in centers[1:]
        ):
            return None

    outer_pairs = set()
    for start_index, start_pair in enumerate(endpoints):
        for start_endpoint_index in (0, 1):
            stack = [(
                (start_index,),
                start_pair[start_endpoint_index],
                start_pair[1 - start_endpoint_index],
            )]
            while stack:
                used, start_point, current = stack.pop()
                if len(used) == len(selectors):
                    outer_pairs.add(tuple(sorted((start_point, current))))
                    continue
                for next_index, next_pair in enumerate(endpoints):
                    if next_index in used:
                        continue
                    for endpoint_index in (0, 1):
                        if _dist3(next_pair[endpoint_index], current) <= tolerance:
                            stack.append((
                                used + (next_index,),
                                start_point,
                                next_pair[1 - endpoint_index],
                            ))
    if len(outer_pairs) != 1:
        return None
    outer_start, outer_end = next(iter(outer_pairs))
    lengths = [float(selector.get('length', 0.0)) for selector in selectors]
    total_length = sum(lengths)
    if total_length <= 0.0:
        return None
    boxes = [selector.get('bbox') or {} for selector in selectors]
    mins = [_tuple3(box.get('min')) for box in boxes]
    maxs = [_tuple3(box.get('max')) for box in boxes]
    centers = [_tuple3(selector.get('center')) for selector in selectors]
    if any(value is None for value in mins + maxs + centers):
        return None
    combined = {
        'kind': 'edge',
        'geom_type': geom_type,
        'start': outer_start,
        'end': outer_end,
        'length': total_length,
        'center': tuple(
            sum(centers[index][axis] * lengths[index] for index in range(len(selectors)))
            / total_length
            for axis in range(3)
        ),
        'bbox': {
            'min': tuple(min(value[axis] for value in mins) for axis in range(3)),
            'max': tuple(max(value[axis] for value in maxs) for axis in range(3)),
        },
    }
    try:
        return _selection_index_for_selector(source_shape, combined, context='merged edge selectors')
    except RuntimeError:
        return None


def _selection_indices_for_selectors(source_shape, selectors, context=None):
    resolved = []
    failures = {}
    for selector_index, selector in enumerate(selectors):
        try:
            resolved.append(_selection_indices_for_selector(
                source_shape, selector, context=f'{context} selector {selector_index}'
            ))
        except RuntimeError as error:
            resolved.append(None)
            failures[selector_index] = error
    if not failures:
        return list(dict.fromkeys(index for indices in resolved for index in indices))
    failure_indices = sorted(failures)
    if len(failure_indices) > 12:
        raise failures[failure_indices[0]]
    groups = []

    def visit_group(start_offset, indices):
        if len(indices) >= 2:
            candidate = _merged_selector_group_candidate(
                source_shape, [selectors[index] for index in indices]
            )
            if candidate is not None:
                groups.append((tuple(indices), candidate))
        if len(indices) >= len(failure_indices):
            return
        for next_offset in range(start_offset, len(failure_indices)):
            visit_group(
                next_offset + 1,
                indices + [failure_indices[next_offset]],
            )

    visit_group(0, [])
    if not groups:
        raise failures[min(failures)]
    solutions = []

    def solve(used_selectors, used_candidates, chosen):
        remaining = sorted(set(failures) - used_selectors)
        if not remaining:
            solutions.append(tuple(chosen))
            return
        first = remaining[0]
        for indices, candidate in groups:
            index_set = set(indices)
            if (
                first not in index_set
                or index_set & used_selectors
                or candidate in used_candidates
            ):
                continue
            solve(
                used_selectors | index_set,
                used_candidates | {candidate},
                chosen + [(indices, candidate)],
            )

    solve(set(), set(), [])
    if len(solutions) != 1:
        raise RuntimeError(
            f'Merged edge selector groups are ambiguous; groups={groups!r}'
        )
    chosen = solutions[0]
    used_selectors = {
        selector_index
        for indices, _candidate in chosen
        for selector_index in indices
    }
    selected = [candidate for _indices, candidate in chosen]
    for selector_index, indices in enumerate(resolved):
        if selector_index in used_selectors:
            continue
        if indices is None:
            raise failures[selector_index]
        selected.extend(indices)
    return list(dict.fromkeys(selected))


def _register_geo_selection_node(*, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None, allow_deferred=False):
    if not inputs:
        raise RuntimeError(f'Selection node {node_id!r} is missing its source input')
    selector = dict(params.get('geo_selector') or {})
    source_node_id = str(inputs[0])
    source_shape = _shape_from_graph_node(source_node_id)
    resolution_error = None
    try:
        indices = _selection_indices_for_selector(
            source_shape, selector, context=f'node {node_id}'
        )
    except RuntimeError as error:
        if not allow_deferred:
            raise
        indices = []
        resolution_error = str(error)
    candidates = _subshape_candidates_for_kind(source_shape, selector.get('kind'))
    selected_shapes = [candidates[index] for index in indices]
    selected_shape = (
        selected_shapes[0]
        if len(selected_shapes) == 1
        else Part.makeCompound(selected_shapes) if selected_shapes else Part.Shape()
    )
    payload = {
        'node_id': node_id,
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
        'output_count': int(output_count),
        'selector': selector,
        'index': int(indices[0]) if indices else None,
        'indices': [int(index) for index in indices],
        'resolution_error': resolution_error,
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
    selectors = []
    legacy_indices = []
    for node_id in node_ids or []:
        payload = GRAPH_SELECTIONS.get(str(node_id)) or GRAPH_NODES.get(str(node_id))
        if isinstance(payload, dict) and base_shape is not None:
            selector = dict(payload.get('selector') or payload.get('params', {}).get('geo_selector') or {})
            if kind is not None:
                selector['kind'] = str(kind)
            if selector:
                selectors.append(selector)
                continue
        if isinstance(payload, dict) and 'index' in payload:
            legacy_indices.append(int(payload['index']))
    if selectors and base_shape is not None:
        return _selection_indices_for_selectors(
            base_shape, selectors, context=f'{kind or "shape"} detail selector set'
        )
    if legacy_indices:
        return legacy_indices
    return [int(idx) for idx in (fallback_indices or [])]
