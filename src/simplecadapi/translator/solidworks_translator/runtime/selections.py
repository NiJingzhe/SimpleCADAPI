"""SolidWorks runtime fragment: selections helpers."""

def _selector_geometry(selector):
    params = selector.get('params') if isinstance(selector, dict) else None
    if isinstance(params, dict):
        selector = params
    if not isinstance(selector, dict):
        return {}
    geo_selector = selector.get('geo_selector')
    if isinstance(geo_selector, dict):
        return dict(selector, **geo_selector)
    return selector


def _tuple3_or_none(value):
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    return None


def _canonical_geom_type(value):
    text = str(value or '').upper().replace('_TYPE', '').replace('_', '')
    aliases = {
        'B-SPLINE': 'BSPLINE',
        'BSPLINE': 'BSPLINE',
        'BCURVE': 'BSPLINE',
        'BSURF': 'BSPLINE',
        'NURBS': 'BSPLINE',
        'BEZIERCURVE': 'BEZIER',
        'BEZIER': 'BEZIER',
        'ELLIPTICALARC': 'ELLIPSE',
        'PLANESURFACE': 'PLANE',
        'CYLINDERSURFACE': 'CYLINDER',
        'CONESURFACE': 'CONE',
        'SPHERESURFACE': 'SPHERE',
        'TORUSSURFACE': 'TORUS',
    }
    return aliases.get(text, text)


def _selector_geom_type(selector):
    selector = _selector_geometry(selector)
    geom_type = _canonical_geom_type(
        selector.get('geom_type') or selector.get('surface_type')
    )
    kind = str(selector.get('kind') or selector.get('target_kind') or '').lower()
    if geom_type not in {'BSPLINE', 'BEZIER'} or kind != 'edge':
        return geom_type
    start = _tuple3_or_none(selector.get('start'))
    end = _tuple3_or_none(selector.get('end'))
    expected_length = selector.get('length')
    if start is None or end is None or expected_length is None:
        return geom_type
    chord_length = _distance(start, end)
    edge_length = float(expected_length)
    scale = max(1.0, chord_length, edge_length)
    if (
        chord_length > scale * 1.0e-10
        and abs(edge_length - chord_length) <= scale * 1.0e-7
    ):
        return 'LINE'
    return geom_type


def _signature_geom_type(sig, selector):
    geom_type = _canonical_geom_type(sig.get('geom_type'))
    kind = _selector_kind(selector, sig)
    if geom_type not in {'BSPLINE', 'BEZIER'} or kind != 'edge':
        return geom_type
    start = _tuple3_or_none(sig.get('start'))
    end = _tuple3_or_none(sig.get('end'))
    edge_length = sig.get('length')
    if start is None or end is None or edge_length is None:
        return geom_type
    chord_length = _distance(start, end)
    edge_length = float(edge_length)
    scale = max(1.0, chord_length, edge_length)
    if (
        chord_length > scale * 1.0e-10
        and abs(edge_length - chord_length) <= scale * 1.0e-7
    ):
        return 'LINE'
    return geom_type


def _geom_type_mismatch(sig, selector):
    selector = _selector_geometry(selector)
    target = _selector_geom_type(selector)
    actual = _signature_geom_type(sig, selector)
    return int(bool(target and actual and target != actual))


def _selector_length_scale(selector):
    selector = _selector_geometry(selector)
    bbox = selector.get('bbox')
    if isinstance(bbox, dict):
        minimum = _tuple3_or_none(bbox.get('min'))
        maximum = _tuple3_or_none(bbox.get('max'))
        if minimum is not None and maximum is not None:
            return max(1.0, _distance(minimum, maximum))
    return 1.0


def _relative_error(actual, expected, floor=1.0):
    return abs(float(actual) - float(expected)) / max(float(floor), abs(float(expected)))


def _bbox_selector_score(sig, selector):
    selector = _selector_geometry(selector)
    candidate_bbox = sig.get('bbox')
    expected_bbox = selector.get('bbox')
    if not isinstance(candidate_bbox, dict) or not isinstance(expected_bbox, dict):
        return 0.0
    actual_min = _tuple3_or_none(candidate_bbox.get('min'))
    actual_max = _tuple3_or_none(candidate_bbox.get('max'))
    expected_min = _tuple3_or_none(expected_bbox.get('min'))
    expected_max = _tuple3_or_none(expected_bbox.get('max'))
    if any(value is None for value in (actual_min, actual_max, expected_min, expected_max)):
        return 1.0e6
    scale = _selector_length_scale(selector)
    return (
        _distance(actual_min, expected_min) + _distance(actual_max, expected_max)
    ) / scale


def _selector_kind(selector, sig):
    selector = _selector_geometry(selector)
    kind = str(selector.get('kind') or selector.get('target_kind') or '').lower()
    if kind:
        return kind
    if 'length' in selector or 'length' in sig:
        return 'edge'
    if 'area' in selector or 'area' in sig:
        return 'face'
    return ''


def _geom_score(sig, selector):
    selector = _selector_geometry(selector)
    selector = dict(selector, kind=_selector_kind(selector, sig), geom_type=_selector_geom_type(selector))
    signature = dict(sig, geom_type=_signature_geom_type(sig, selector))
    return _gsm_score(signature, selector)


def _best_by_geometry(signatures, selector, label, topology_match=None):
    selector = _selector_geometry(selector)
    selector = dict(selector, kind=_selector_kind(selector, signatures[0][1] if signatures else {}), geom_type=_selector_geom_type(selector))
    normalized = [(candidate, dict(signature, geom_type=_signature_geom_type(signature, selector))) for candidate, signature in signatures]
    return _gsm_select(normalized, selector, label)


def _directions_parallel(left, right, tolerance=1.0e-6):
    left = _tuple3_or_none(left)
    right = _tuple3_or_none(right)
    if left is None or right is None:
        return False
    left = _unit(left)
    right = _unit(right)
    return abs(_dot(left, right)) >= 1.0 - tolerance


def _selector_endpoints_on_circle_support(selector, support, tolerance):
    if not isinstance(support, dict):
        return False
    center = _tuple3_or_none(support.get('center'))
    axis = _tuple3_or_none(support.get('axis'))
    radius = support.get('radius')
    selector = _selector_geometry(selector)
    endpoints = (
        _tuple3_or_none(selector.get('start')),
        _tuple3_or_none(selector.get('end')),
    )
    if (
        center is None
        or axis is None
        or radius is None
        or any(point is None for point in endpoints)
    ):
        return False
    axis = _unit(axis)
    radius = abs(float(radius))
    for point in endpoints:
        offset = _sub(point, center)
        if abs(_dot(offset, axis)) > tolerance:
            return False
        radial = _sub(offset, _mul(axis, _dot(offset, axis)))
        if abs(_norm(radial) - radius) > tolerance:
            return False
    return True


def _same_edge_signature_support(first, second, selector, scale):
    geom_type = _signature_geom_type(first, selector)
    second_geom_type = _signature_geom_type(second, selector)
    selector_geom_type = _selector_geom_type(selector)
    parametric_ellipse_fragments = (
        selector_geom_type == 'ELLIPSE'
        and geom_type in {'BSPLINE', 'BEZIER'}
        and second_geom_type in {'BSPLINE', 'BEZIER'}
    )
    if geom_type != second_geom_type and not parametric_ellipse_fragments:
        return False
    tolerance = max(1.0e-7, float(scale) * 1.0e-5)
    if parametric_ellipse_fragments:
        connections = []
        for first_key, first_tangent_key in (
            ('start', 'start_tangent'),
            ('end', 'end_tangent'),
        ):
            first_point = _tuple3_or_none(first.get(first_key))
            first_tangent = _tuple3_or_none(first.get(first_tangent_key))
            for second_key, second_tangent_key in (
                ('start', 'start_tangent'),
                ('end', 'end_tangent'),
            ):
                second_point = _tuple3_or_none(second.get(second_key))
                second_tangent = _tuple3_or_none(second.get(second_tangent_key))
                if (
                    first_point is not None
                    and second_point is not None
                    and first_tangent is not None
                    and second_tangent is not None
                    and _distance(first_point, second_point) <= tolerance
                ):
                    connections.append((first_tangent, second_tangent))
        if len(connections) != 1 or not _directions_parallel(
            connections[0][0], connections[0][1], tolerance=1.0e-4
        ):
            return False
        first_samples = [
            _tuple3_or_none(point) for point in first.get('samples') or ()
        ]
        second_samples = [
            _tuple3_or_none(point) for point in second.get('samples') or ()
        ]
        if (
            len(first_samples) < 3
            or len(second_samples) < 3
            or any(point is None for point in first_samples + second_samples)
        ):
            return False
        origin = first_samples[0]
        offsets = [_sub(point, origin) for point in first_samples[1:]]
        plane_normal = None
        plane_normal_length = 0.0
        for left_index, left in enumerate(offsets):
            for right in offsets[left_index + 1:]:
                normal = _cross(left, right)
                length = _norm(normal)
                if length > plane_normal_length:
                    plane_normal = normal
                    plane_normal_length = length
        if (
            plane_normal is None
            or plane_normal_length
            <= max(1.0e-12, float(scale) * float(scale) * 1.0e-10)
        ):
            return False
        return all(
            abs(_dot(_sub(point, origin), plane_normal))
            / plane_normal_length
            <= tolerance
            for point in second_samples
        )
    if geom_type == 'LINE':
        first_start = _tuple3_or_none(first.get('start'))
        first_end = _tuple3_or_none(first.get('end'))
        second_start = _tuple3_or_none(second.get('start'))
        second_end = _tuple3_or_none(second.get('end'))
        if any(
            point is None
            for point in (first_start, first_end, second_start, second_end)
        ):
            return False
        first_direction = _sub(first_end, first_start)
        second_direction = _sub(second_end, second_start)
        if not _directions_parallel(first_direction, second_direction):
            return False
        direction_length = _norm(first_direction)
        if direction_length <= 1.0e-12:
            return False
        return all(
            _norm(_cross(_sub(point, first_start), first_direction))
            / direction_length
            <= tolerance
            for point in (second_start, second_end)
        )
    if geom_type not in {'CIRCLE', 'ELLIPSE'}:
        return False
    first_support = first.get('support')
    second_support = second.get('support')
    if not isinstance(first_support, dict) or not isinstance(second_support, dict):
        return False
    first_center = _tuple3_or_none(first_support.get('center'))
    second_center = _tuple3_or_none(second_support.get('center'))
    if (
        first_center is None
        or second_center is None
        or _distance(first_center, second_center) > tolerance
        or not _directions_parallel(
            first_support.get('axis'), second_support.get('axis')
        )
    ):
        return False
    radius_keys = ('radius',) if geom_type == 'CIRCLE' else ('major_radius', 'minor_radius')
    return all(
        first_support.get(key) is not None
        and second_support.get(key) is not None
        and abs(float(first_support[key]) - float(second_support[key])) <= tolerance
        for key in radius_keys
    )


def _edge_signature_within_selector_bbox(signature, selector, tolerance):
    candidate_bbox = signature.get('bbox')
    expected_bbox = selector.get('bbox') if isinstance(selector, dict) else None
    if not isinstance(candidate_bbox, dict) or not isinstance(expected_bbox, dict):
        return False
    actual_min = _tuple3_or_none(candidate_bbox.get('min'))
    actual_max = _tuple3_or_none(candidate_bbox.get('max'))
    expected_min = _tuple3_or_none(expected_bbox.get('min'))
    expected_max = _tuple3_or_none(expected_bbox.get('max'))
    if any(
        value is None
        for value in (actual_min, actual_max, expected_min, expected_max)
    ):
        return False
    return all(
        expected_min[index] - tolerance <= actual_min[index]
        and actual_max[index] <= expected_max[index] + tolerance
        for index in range(3)
    )


def _fragment_signature_group_bbox_score(group, selector):
    expected_bbox = selector.get('bbox') if isinstance(selector, dict) else None
    if not isinstance(expected_bbox, dict):
        return 1.0e6
    expected_min = _tuple3_or_none(expected_bbox.get('min'))
    expected_max = _tuple3_or_none(expected_bbox.get('max'))
    if expected_min is None or expected_max is None:
        return 1.0e6
    actual_min = tuple(
        min(float(signature['bbox']['min'][index]) for _candidate, signature in group)
        for index in range(3)
    )
    actual_max = tuple(
        max(float(signature['bbox']['max'][index]) for _candidate, signature in group)
        for index in range(3)
    )
    scale = _selector_length_scale(selector)
    return (
        _distance(actual_min, expected_min) + _distance(actual_max, expected_max)
    ) / scale


def _fragment_signature_group_matches(group, selector):
    if len(group) < 2:
        return False
    expected_length = selector.get('length')
    expected_center = _tuple3_or_none(selector.get('center'))
    if expected_length is None or expected_center is None:
        return False
    total_length = sum(float(signature['length']) for _candidate, signature in group)
    if _relative_error(total_length, expected_length) > 1.0e-4:
        return False
    if _fragment_signature_group_bbox_score(group, selector) > 1.0e-4:
        return False
    if total_length <= 1.0e-12:
        return False
    weighted_center = [0.0, 0.0, 0.0]
    for _candidate, signature in group:
        center = _tuple3_or_none(signature.get('center'))
        if center is None:
            return False
        weight = float(signature['length'])
        for index in range(3):
            weighted_center[index] += center[index] * weight
    weighted_center = tuple(value / total_length for value in weighted_center)
    return (
        _distance(weighted_center, expected_center) / _selector_length_scale(selector)
        <= 1.0e-4
    )


def _fragmented_edge_group(signatures, selector, label):
    selector = _selector_geometry(selector)
    if _selector_kind(selector, {}) != 'edge':
        return None
    expected_type = _selector_geom_type(selector)
    expected_start = _tuple3_or_none(selector.get('start'))
    expected_end = _tuple3_or_none(selector.get('end'))
    expected_length = selector.get('length')
    if (
        not expected_type
        or expected_start is None
        or expected_end is None
        or expected_length is None
    ):
        return None
    scale = _selector_length_scale(selector)
    connection_tolerance = max(1.0e-7, scale * 1.0e-5)
    if _distance(expected_start, expected_end) <= connection_tolerance:
        return None
    ranked = sorted(signatures, key=lambda item: _geom_score(item[1], selector))
    if len(ranked) < 2:
        return None
    eligible = []
    for candidate_index, (candidate, signature) in enumerate(ranked):
        signature_type = _signature_geom_type(signature, selector)
        type_matches = signature_type == expected_type or (
            expected_type == 'ELLIPSE'
            and signature_type in {'BSPLINE', 'BEZIER'}
        )
        if not type_matches:
            continue
        if float(signature.get('length', 0.0)) >= float(expected_length) * (1.0 - 1.0e-6):
            continue
        if not _edge_signature_within_selector_bbox(
            signature, selector, connection_tolerance
        ):
            continue
        start = _tuple3_or_none(signature.get('start'))
        end = _tuple3_or_none(signature.get('end'))
        if start is not None and end is not None:
            eligible.append((candidate_index, candidate, signature, (start, end)))
    if len(eligible) < 2:
        return None
    valid_groups = {}
    for start_index, start_candidate, start_signature, endpoints in eligible:
        starts = []
        if _distance(endpoints[0], expected_start) <= connection_tolerance:
            starts.append(endpoints[1])
        if _distance(endpoints[1], expected_start) <= connection_tolerance:
            starts.append(endpoints[0])
        for current_point in starts:
            stack = [(
                [start_index],
                [(start_candidate, start_signature)],
                current_point,
            )]
            while stack:
                path_indices, path_group, point = stack.pop()
                if _distance(point, expected_end) <= connection_tolerance:
                    if _fragment_signature_group_matches(path_group, selector):
                        key = tuple(sorted(path_indices))
                        valid_groups[key] = [candidate for candidate, _signature in path_group]
                    continue
                if len(path_indices) >= min(12, len(eligible)):
                    continue
                for candidate_index, candidate, signature, candidate_endpoints in eligible:
                    if candidate_index in path_indices:
                        continue
                    if not _same_edge_signature_support(
                        path_group[-1][1], signature, selector, scale
                    ):
                        continue
                    next_points = []
                    if _distance(candidate_endpoints[0], point) <= connection_tolerance:
                        next_points.append(candidate_endpoints[1])
                    if _distance(candidate_endpoints[1], point) <= connection_tolerance:
                        next_points.append(candidate_endpoints[0])
                    for next_point in next_points:
                        stack.append((
                            path_indices + [candidate_index],
                            path_group + [(candidate, signature)],
                            next_point,
                        ))
    if len(valid_groups) == 1:
        return next(iter(valid_groups.values()))
    if len(valid_groups) > 1:
        raise RuntimeError(
            f'Fragmented edge selector is ambiguous; label={label!r}, '
            f'selector={selector!r}, groups={sorted(valid_groups)!r}'
        )
    return None


def _selection_candidates_by_geometry(
    signatures, selector, label, topology_match=None
):
    try:
        return [
            _best_by_geometry(
                signatures,
                selector,
                label,
                topology_match=topology_match,
            )
        ]
    except RuntimeError as single_error:
        fragmented = _fragmented_edge_group(signatures, selector, label)
        if fragmented is None:
            raise single_error
        return list(fragmented)


def _selector_edge_components(selectors):
    normalized = [_selector_geometry(selector) for selector in selectors]
    endpoints = [
        (
            _tuple3_or_none(selector.get('start')),
            _tuple3_or_none(selector.get('end')),
        )
        for selector in normalized
    ]
    if any(start is None or end is None for start, end in endpoints):
        return [list(selectors)]
    tolerance = max(
        1.0e-7,
        max(_selector_length_scale(selector) for selector in normalized) * 1.0e-5,
    )
    neighbors = {index: set() for index in range(len(selectors))}
    for right in range(len(selectors)):
        for left in range(right):
            if min(
                _distance(left_point, right_point)
                for left_point in endpoints[left]
                for right_point in endpoints[right]
            ) <= tolerance:
                neighbors[left].add(right)
                neighbors[right].add(left)
    components = []
    visited = set()
    for start_index in range(len(selectors)):
        if start_index in visited:
            continue
        pending = [start_index]
        visited.add(start_index)
        indices = []
        while pending:
            index = pending.pop()
            indices.append(index)
            for neighbor in sorted(neighbors[index], reverse=True):
                if neighbor not in visited:
                    visited.add(neighbor)
                    pending.append(neighbor)
        components.append([selectors[index] for index in sorted(indices)])
    return components


def _coalesced_edge_selector_pairs(signatures, selectors):
    normalized = [_selector_geometry(selector) for selector in selectors]
    matches = []
    for left_index in range(len(normalized)):
        left = normalized[left_index]
        if _selector_kind(left, {}) != 'edge':
            continue
        left_start = _tuple3_or_none(left.get('start'))
        left_end = _tuple3_or_none(left.get('end'))
        left_length = left.get('length')
        if left_start is None or left_end is None or left_length is None:
            continue
        for right_index in range(left_index + 1, len(normalized)):
            right = normalized[right_index]
            if _selector_geom_type(left) != _selector_geom_type(right):
                continue
            right_start = _tuple3_or_none(right.get('start'))
            right_end = _tuple3_or_none(right.get('end'))
            right_length = right.get('length')
            if right_start is None or right_end is None or right_length is None:
                continue
            scale = max(
                _selector_length_scale(left),
                _selector_length_scale(right),
            )
            tolerance = max(1.0e-7, scale * 1.0e-5)
            endpoint_pairs = [
                (left_key, right_key)
                for left_key, left_point in enumerate((left_start, left_end))
                for right_key, right_point in enumerate((right_start, right_end))
                if _distance(left_point, right_point) <= tolerance
            ]
            closes_loop = len(endpoint_pairs) == 2
            joins_path = len(endpoint_pairs) == 1
            if not (closes_loop or joins_path):
                continue
            external_endpoints = None
            if joins_path:
                left_shared, right_shared = endpoint_pairs[0]
                external_endpoints = (
                    (left_start, left_end)[1 - left_shared],
                    (right_start, right_end)[1 - right_shared],
                )
            left_bbox = left.get('bbox')
            right_bbox = right.get('bbox')
            if not isinstance(left_bbox, dict) or not isinstance(right_bbox, dict):
                continue
            expected_min = tuple(
                min(
                    float(left_bbox['min'][axis]),
                    float(right_bbox['min'][axis]),
                )
                for axis in range(3)
            )
            expected_max = tuple(
                max(
                    float(left_bbox['max'][axis]),
                    float(right_bbox['max'][axis]),
                )
                for axis in range(3)
            )
            total_length = float(left_length) + float(right_length)
            left_center = _tuple3_or_none(left.get('center'))
            right_center = _tuple3_or_none(right.get('center'))
            if left_center is None or right_center is None:
                continue
            expected_center = tuple(
                (
                    left_center[axis] * float(left_length)
                    + right_center[axis] * float(right_length)
                ) / total_length
                for axis in range(3)
            )
            candidates = []
            for candidate_index, (_candidate, signature) in enumerate(signatures):
                candidate_type = _canonical_geom_type(signature.get('geom_type'))
                expected_type = _selector_geom_type(left)
                if closes_loop:
                    if candidate_type != 'INTERSECTION':
                        continue
                elif candidate_type != expected_type:
                    continue
                candidate_start = _tuple3_or_none(signature.get('start'))
                candidate_end = _tuple3_or_none(signature.get('end'))
                candidate_center = _tuple3_or_none(signature.get('center'))
                candidate_length = signature.get('length')
                if (
                    candidate_start is None
                    or candidate_end is None
                    or candidate_center is None
                    or candidate_length is None
                ):
                    continue
                if closes_loop:
                    if _distance(candidate_start, candidate_end) > tolerance:
                        continue
                else:
                    matches_external_endpoints = (
                        _distance(candidate_start, external_endpoints[0]) <= tolerance
                        and _distance(candidate_end, external_endpoints[1]) <= tolerance
                    ) or (
                        _distance(candidate_start, external_endpoints[1]) <= tolerance
                        and _distance(candidate_end, external_endpoints[0]) <= tolerance
                    )
                    if not matches_external_endpoints:
                        continue
                    if (
                        expected_type == 'CIRCLE'
                        and not all(
                            _selector_endpoints_on_circle_support(
                                source_selector,
                                signature.get('support'),
                                tolerance,
                            )
                            for source_selector in (left, right)
                        )
                    ):
                        continue
                if _relative_error(candidate_length, total_length) > 1.0e-4:
                    continue
                combined_selector = {
                    'bbox': {'min': expected_min, 'max': expected_max},
                    'kind': 'edge',
                }
                # Edge bboxes are reconstructed from 65 curve samples. Keep
                # the tolerance below one sampling interval while relying on
                # exact outer endpoints, total length, and weighted center.
                if _bbox_selector_score(signature, combined_selector) > 5.0e-4:
                    continue
                if _distance(candidate_center, expected_center) / scale > 1.0e-4:
                    continue
                candidates.append(candidate_index)
            if len(candidates) == 1:
                matches.append((left_index, right_index, candidates[0]))
            elif len(candidates) > 1:
                raise RuntimeError(
                    'Coalesced edge selector is ambiguous; '
                    f'selectors=({left_index}, {right_index}), '
                    f'candidates={candidates!r}'
                )
    used_selectors = set()
    used_candidates = set()
    result = []
    for left_index, right_index, candidate_index in matches:
        if (
            left_index in used_selectors
            or right_index in used_selectors
            or candidate_index in used_candidates
        ):
            raise RuntimeError(
                'Coalesced edge selector groups overlap and are ambiguous; '
                f'matches={matches!r}'
            )
        used_selectors.update((left_index, right_index))
        used_candidates.add(candidate_index)
        result.append((left_index, right_index, candidate_index))
    return result


def _closed_intersection_candidate(ranked, selector):
    selector = _selector_geometry(selector)
    if _selector_kind(selector, {}) != 'edge':
        return None
    if _selector_geom_type(selector) not in {'BSPLINE', 'BEZIER'}:
        return None
    expected_start = _tuple3_or_none(selector.get('start'))
    expected_end = _tuple3_or_none(selector.get('end'))
    expected_center = _tuple3_or_none(selector.get('center'))
    expected_length = selector.get('length')
    scale = _selector_length_scale(selector)
    tolerance = max(1.0e-7, scale * 1.0e-5)
    if (
        expected_start is None
        or expected_end is None
        or expected_center is None
        or expected_length is None
        or _distance(expected_start, expected_end) > tolerance
    ):
        return None
    matches = []
    for candidate, signature in ranked:
        if _canonical_geom_type(signature.get('geom_type')) != 'INTERSECTION':
            continue
        candidate_start = _tuple3_or_none(signature.get('start'))
        candidate_end = _tuple3_or_none(signature.get('end'))
        candidate_center = _tuple3_or_none(signature.get('center'))
        candidate_length = signature.get('length')
        if (
            candidate_start is None
            or candidate_end is None
            or candidate_center is None
            or candidate_length is None
            or _distance(candidate_start, candidate_end) > tolerance
        ):
            continue
        if _bbox_selector_score(signature, selector) > 1.0e-4:
            continue
        if _relative_error(candidate_length, expected_length) > 1.0e-4:
            continue
        if _distance(candidate_center, expected_center) / scale > 1.0e-4:
            continue
        matches.append(candidate)
    return matches[0] if len(matches) == 1 else None


def _is_missing_revolution_seam(ranked, selector):
    selector = _selector_geometry(selector)
    if _selector_kind(selector, {}) != 'edge' or _selector_geom_type(selector) != 'LINE':
        return False
    expected_start = _tuple3_or_none(selector.get('start'))
    expected_end = _tuple3_or_none(selector.get('end'))
    expected_length = selector.get('length')
    scale = _selector_length_scale(selector)
    tolerance = max(1.0e-7, scale * 1.0e-5)
    if (
        expected_start is None
        or expected_end is None
        or expected_length is None
        or _relative_error(_distance(expected_start, expected_end), expected_length)
        > 1.0e-4
    ):
        return False

    def circle_support(signature, point):
        if _canonical_geom_type(signature.get('geom_type')) != 'CIRCLE':
            return None
        start = _tuple3_or_none(signature.get('start'))
        end = _tuple3_or_none(signature.get('end'))
        bbox = signature.get('bbox')
        if (
            start is None
            or end is None
            or _distance(start, end) > tolerance
            or _distance(start, point) > tolerance
            or not isinstance(bbox, dict)
        ):
            return None
        minimum = _tuple3_or_none(bbox.get('min'))
        maximum = _tuple3_or_none(bbox.get('max'))
        if minimum is None or maximum is None:
            return None
        spans = [maximum[index] - minimum[index] for index in range(3)]
        axis = min(range(3), key=lambda index: abs(spans[index]))
        if abs(spans[axis]) > tolerance:
            return None
        center = tuple((minimum[index] + maximum[index]) * 0.5 for index in range(3))
        radial = tuple(
            point[index] - center[index] if index != axis else 0.0
            for index in range(3)
        )
        if _norm(radial) <= tolerance:
            return None
        return axis, center, _unit(radial)

    start_matches = []
    end_matches = []
    for candidate, signature in ranked:
        start_support = circle_support(signature, expected_start)
        if start_support is not None:
            start_matches.append((candidate, start_support))
        end_support = circle_support(signature, expected_end)
        if end_support is not None:
            end_matches.append((candidate, end_support))
    valid_pairs = []
    for start_candidate, start_support in start_matches:
        for end_candidate, end_support in end_matches:
            if start_candidate is end_candidate:
                continue
            start_axis, start_center, start_radial = start_support
            end_axis, end_center, end_radial = end_support
            if start_axis != end_axis:
                continue
            if any(
                abs(start_center[index] - end_center[index]) > tolerance
                for index in range(3)
                if index != start_axis
            ):
                continue
            if _dot(start_radial, end_radial) < 1.0 - 1.0e-6:
                continue
            valid_pairs.append((start_candidate, end_candidate))
    return len(valid_pairs) == 1


class SelectionRuntimeMixin:
    def _restore_circular_partitions(self, source, selectors, node_id):
        """Restore merged half-circle boundaries using a native silhouette split.

        This changes topology only. The requested edges are subsequently picked
        by the shared FreeCAD GSM contract, never by widening a half-circle pick.
        """
        for raw in selectors:
            selector = _selector_geometry(raw)
            if _selector_geom_type(selector) != 'CIRCLE':
                continue
            signatures = [(edge, self._edge_signature(edge)) for edge in self._body_edges(source)]
            try:
                _best_by_geometry(signatures, selector, 'edge')
                continue
            except RuntimeError:
                pass
            start, end = _tuple3_or_none(selector.get('start')), _tuple3_or_none(selector.get('end'))
            length = selector.get('length')
            if start is None or end is None or length is None:
                continue
            center = _mul(_add(start, end), .5)
            radius = _distance(start, end) * .5
            if radius <= 1e-9 or abs(float(length)-math.pi*radius) > radius*1e-5:
                continue
            matches = []
            for edge, signature in signatures:
                support = signature.get('support') or {}
                if (_canonical_geom_type(signature.get('geom_type')) == 'CIRCLE'
                    and _tuple3_or_none(support.get('center')) is not None
                    and _distance(support.get('center'), center) <= max(1., radius)*1e-6
                    and abs(float(support.get('radius',0))-radius) <= max(1.,radius)*1e-6
                    and abs(float(signature.get('length',0))-2*math.pi*radius) <= radius*1e-5):
                    matches.append((edge, support))
            if len(matches) != 1:
                continue
            edge, support = matches[0]
            faces = list(_maybe_call(edge.GetTwoAdjacentFaces2) or [])
            cylinders = [face for face in faces if face is not None and self._cylinder_surface_params(face) is not None]
            if len(cylinders) != 1:
                continue
            axis = _unit(support['axis'])
            radial = _unit(_sub(start, center))
            def point_variant(point):
                return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, list(_pt_m(point)))
            before = self._body_names()
            descriptor = {'bbox': self._box_from_entity(source), 'volume': self._body_volume(source)}
            self._clear_selection()
            plane = self.model.CreatePlaneFixed2(point_variant(center), point_variant(_add(center, _mul(radial, radius))), point_variant(_add(center, _mul(axis, radius))), False)
            if plane is None:
                raise RuntimeError('Could not create plane for native circular partition')
            self._clear_selection()
            if not self._select_entity(plane, append=False, mark=2) or not self._select_entity(cylinders[0], append=True, mark=1):
                raise RuntimeError('Could not select native circular partition geometry')
            old_features = {self._feature_identity(item) for item in self._features()}
            _maybe_call(self.model.InsertSplitLineSil)
            new_features = [item for item in self._features() if self._feature_identity(item) not in old_features]
            if len(new_features) != 1:
                raise RuntimeError('Native circular partition did not create one split feature')
            feature = new_features[0]
            feature.Name = f'SimpleCAD_{node_id}_circular_partition'
            source = self._capture_new_body(before, feature, expected_bbox=descriptor['bbox'])
            if not self._body_matches_native_snapshot(source, descriptor, volume_relative_tolerance=1e-8):
                raise RuntimeError('Native circular partition changed solid geometry')
            self.logs.append(f'{node_id} restored half-circle topology with native Split Line')
        return source

    def _select_entity(self, entity, append=False, mark=0):
        for call in (
            lambda: entity.Select2(bool(append), mark),
            lambda: entity.Select2(bool(append), None),
            lambda: entity.Select2(bool(append), _empty_dispatch()),
            lambda: entity.Select4(bool(append), _empty_dispatch()),
            lambda: entity.Select(bool(append), mark),
            lambda: entity.Select(bool(append)),
        ):
            try:
                if call():
                    return True
            except Exception:
                pass
        return False

    def _select_solid_body(self, body, *, append=False, mark=1):
        body_name = self._body_name(body)
        if body_name:
            try:
                if self.model.Extension.SelectByID2(
                    body_name,
                    'SOLIDBODY',
                    0.0,
                    0.0,
                    0.0,
                    bool(append),
                    int(mark),
                    _empty_dispatch(),
                    0,
                ):
                    return True
            except Exception:
                pass
        return self._select_entity(body, append=append, mark=mark)

    def _group_sweep_path_selection(self):
        try:
            return bool(self.model.Extension.SelectByID2(
                'Unknown', 'SELOBJGROUP',
                0.0, 0.0, 0.0,
                True, 4, _empty_dispatch(), 0,
            ))
        except Exception as exc:
            self.logs.append(f'could not group sweep path segments: {exc}')
            return False

    def _clear_selection(self):
        try:
            self.model.ClearSelection2(True)
        except Exception:
            pass

    def _selection_state(self):
        state = []
        try:
            raw_manager = self.model._oleobj_.InvokeTypes(
                65537,
                0,
                pythoncom.DISPATCH_PROPERTYGET,
                (pythoncom.VT_DISPATCH, 0),
                (),
            )
            manager = win32com.client.Dispatch(raw_manager)
            count = int(manager._oleobj_.InvokeTypes(
                1, 0, pythoncom.DISPATCH_METHOD, (pythoncom.VT_I4, 0), ()
            ))
        except Exception:
            return state
        for index in range(1, count + 1):
            try:
                object_type = int(manager._oleobj_.InvokeTypes(
                    14,
                    0,
                    pythoncom.DISPATCH_METHOD,
                    (pythoncom.VT_I4, 0),
                    ((pythoncom.VT_I4, pythoncom.PARAMFLAG_FIN),),
                    index,
                ))
            except Exception:
                object_type = None
            try:
                mark = int(manager._oleobj_.InvokeTypes(
                    17,
                    0,
                    pythoncom.DISPATCH_METHOD,
                    (pythoncom.VT_I4, 0),
                    ((pythoncom.VT_I4, pythoncom.PARAMFLAG_FIN),),
                    index,
                ))
            except Exception:
                mark = None
            state.append({'type': object_type, 'mark': mark})
        return state

    def _edge_signature(self, edge):
        def array3(value):
            try:
                value = _maybe_call(value)
                if value is not None and len(value) >= 3:
                    return tuple(float(value[index]) for index in range(3))
            except Exception:
                pass
            return None

        curve = None
        for call in (
            lambda: _maybe_call(edge.GetCurve),
            lambda: win32com.client.Dispatch(edge._oleobj_.InvokeTypes(
                1, 0, pythoncom.DISPATCH_METHOD, (pythoncom.VT_DISPATCH, 0), ()
            )),
        ):
            try:
                curve = call()
                if curve is not None:
                    break
            except Exception:
                curve = None

        # GetCurveParams3 is the documented source for an edge's geometric
        # endpoints, parameter range, and curve type. GetCurve must be called
        # first so SolidWorks materializes the underlying curve information.
        start_m = end_m = None
        u_min = u_max = None
        curve_type = None
        try:
            curve_data = _maybe_call(edge.GetCurveParams3)
            if curve_data is not None:
                start_m = array3(getattr(curve_data, 'StartPoint', None))
                end_m = array3(getattr(curve_data, 'EndPoint', None))
                u_min = float(_maybe_call(getattr(curve_data, 'UMinValue')))
                u_max = float(_maybe_call(getattr(curve_data, 'UMaxValue')))
                curve_type = int(_maybe_call(getattr(curve_data, 'CurveType')))
        except Exception:
            start_m = end_m = None
            u_min = u_max = None
            curve_type = None

        params = None
        if start_m is None or end_m is None or u_min is None or u_max is None:
            for call in (
                lambda: _maybe_call(edge.GetCurveParams2),
                lambda: edge._oleobj_.InvokeTypes(
                    24, 0, pythoncom.DISPATCH_METHOD,
                    (pythoncom.VT_VARIANT, 0), (),
                ),
            ):
                try:
                    values = call()
                    params = tuple(float(value) for value in values)
                    if len(params) >= 8:
                        start_m = tuple(params[index] for index in range(3))
                        end_m = tuple(params[index] for index in range(3, 6))
                        u_min, u_max = float(params[6]), float(params[7])
                        break
                except Exception:
                    params = None

        def vertex_point(getter_name):
            try:
                vertex = _maybe_call(getattr(edge, getter_name))
                if vertex is None:
                    return None
                return array3(getattr(vertex, 'GetPoint'))
            except Exception:
                return None

        points_m = []
        curve_samples_m = []
        if start_m is not None and end_m is not None and u_min is not None and u_max is not None:
            for step in range(65):
                parameter = u_min + (u_max - u_min) * (step / 64.0)
                evaluated = None
                for call in (
                    lambda: edge.Evaluate2(parameter, 1),
                    lambda: curve.Evaluate2(parameter, 1) if curve is not None else None,
                ):
                    try:
                        evaluated = call()
                        if evaluated is not None and len(evaluated) >= 3:
                            break
                    except Exception:
                        evaluated = None
                if evaluated is None or len(evaluated) < 3:
                    curve_samples_m = []
                    break
                point = tuple(float(evaluated[index]) for index in range(3))
                tangent = (
                    tuple(float(evaluated[index]) for index in range(3, 6))
                    if len(evaluated) >= 6
                    else None
                )
                curve_samples_m.append((point, tangent))
            if len(curve_samples_m) == 65:
                points_m.extend(point for point, _tangent in curve_samples_m)
            else:
                points_m.extend((start_m, end_m))
        else:
            start_m = vertex_point('GetStartVertex')
            end_m = vertex_point('GetEndVertex')
            if start_m is not None:
                points_m.append(start_m)
            if end_m is not None:
                points_m.append(end_m)

        if not points_m:
            bbox = self._box_from_entity(edge)
            start = end = _bbox_center(bbox)
        else:
            converted = [
                tuple(value * M_TO_MM / MODEL_SCALE for value in point)
                for point in points_m
            ]
            bbox = {
                'min': tuple(min(point[index] for point in converted) for index in range(3)),
                'max': tuple(max(point[index] for point in converted) for index in range(3)),
            }
            start = tuple(value * M_TO_MM / MODEL_SCALE for value in start_m)
            end = tuple(value * M_TO_MM / MODEL_SCALE for value in end_m)

        center = _bbox_center(bbox)
        length = _distance(start, end)
        for call in (
            lambda: curve.GetLength3(u_min, u_max),
            lambda: curve._oleobj_.InvokeTypes(
                63, 0, pythoncom.DISPATCH_METHOD, (pythoncom.VT_R8, 0),
                ((pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN), (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN)),
                u_min, u_max,
            ),
            lambda: curve._oleobj_.InvokeTypes(
                21, 0, pythoncom.DISPATCH_METHOD, (pythoncom.VT_R8, 0),
                ((pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN), (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN)),
                u_min, u_max,
            ),
        ):
            try:
                length_value = call()
                if length_value is not None:
                    length = float(length_value) * M_TO_MM / MODEL_SCALE
                    break
            except Exception:
                pass
        curve_types = {
            3001: 'LINE',
            3002: 'CIRCLE',
            3003: 'ELLIPSE',
            3004: 'INTERSECTION',
            3005: 'BSPLINE',
            3006: 'SPCURVE',
            3008: 'CONSTPARAM',
            3009: 'TRIMMED',
        }
        geom_type = ''
        if curve_type is not None:
            geom_type = curve_types.get(int(curve_type), '')
        if not geom_type:
            try:
                geom_type = curve_types.get(int(_maybe_call(curve.Identity)), '')
            except Exception:
                if start_m is not None and end_m is not None:
                    geom_type = 'LINE' if abs(_distance(start, end) - length) <= 1.0e-7 else ''
        if geom_type in {'BSPLINE', 'INTERSECTION'} and len(curve_samples_m) == 65:
            sample_points = [
                tuple(value * M_TO_MM / MODEL_SCALE for value in point)
                for point, _tangent in curve_samples_m
            ]
            chord = _sub(end, start)
            chord_length = _norm(chord)
            scale = max(1.0, chord_length, length)
            if (
                chord_length > scale * 1.0e-10
                and abs(length - chord_length) <= scale * 1.0e-7
                and all(
                    _norm(_cross(_sub(point, start), chord)) / chord_length
                    <= scale * 1.0e-7
                    for point in sample_points
                )
            ):
                geom_type = 'LINE'
        if (
            geom_type == 'INTERSECTION'
            and _distance(start, end) > max(1.0, length) * 1.0e-7
        ):
            # SolidWorks reports open surface-intersection splines with the
            # generic INTERSECTION identity. OCC exposes the same support as a
            # BSplineCurve, so normalize the backend signature before GSM.
            geom_type = 'BSPLINE'
        if geom_type == 'LINE':
            center = tuple((start[index] + end[index]) * 0.5 for index in range(3))
        elif len(curve_samples_m) == 65 and all(
            tangent is not None for _point, tangent in curve_samples_m
        ):
            weighted = [0.0, 0.0, 0.0]
            total = 0.0
            for index, (point, tangent) in enumerate(curve_samples_m):
                coefficient = 1.0 if index in {0, 64} else (4.0 if index % 2 else 2.0)
                weight = coefficient * _norm(tangent)
                total += weight
                for axis in range(3):
                    weighted[axis] += weight * point[axis]
            if total > 1.0e-18:
                center = tuple(
                    value / total * M_TO_MM / MODEL_SCALE
                    for value in weighted
                )
        start_tangent = end_tangent = None
        if len(curve_samples_m) == 65:
            first_tangent = curve_samples_m[0][1]
            last_tangent = curve_samples_m[-1][1]
            if first_tangent is not None:
                start_tangent = _unit(first_tangent)
            if last_tangent is not None:
                end_tangent = _unit(last_tangent)
        support = None
        if geom_type == 'CIRCLE' and curve is not None:
            for attribute_name in ('CircleParams', 'ICircleParams'):
                try:
                    values = _maybe_call(getattr(curve, attribute_name))
                    if values is not None and len(values) >= 7:
                        support = {
                            'center': tuple(
                                float(values[index]) * M_TO_MM / MODEL_SCALE
                                for index in range(3)
                            ),
                            'axis': _unit(tuple(
                                float(values[index]) for index in range(3, 6)
                            )),
                            'radius': (
                                abs(float(values[6])) * M_TO_MM / MODEL_SCALE
                            ),
                        }
                        break
                except Exception:
                    support = None
        return {
            'bbox': bbox,
            'center': center,
            'start': start,
            'end': end,
            'start_tangent': start_tangent,
            'end_tangent': end_tangent,
            'samples': [
                tuple(value * M_TO_MM / MODEL_SCALE for value in point)
                for point, _tangent in curve_samples_m
            ],
            'length': length,
            'geom_type': geom_type,
            'support': support,
        }

    def _face_signature(self, face):
        bbox = self._box_from_entity(face)
        center = None
        # FreeCAD uses surface centre of mass, not the bounding-box midpoint.
        # A temporary single-face sheet gives the same geometric quantity.
        try:
            sheet = _maybe_call(face.CreateSheetBody)
            sheet = win32com.client.Dispatch(sheet)
            properties = sheet.GetMassProperties(1.0)
            center = tuple(float(properties[i]) * M_TO_MM / MODEL_SCALE for i in range(3))
            bbox = self._box_from_entity(sheet)
        except Exception as exc:
            raise RuntimeError(f'Could not measure face centre of mass for geometric selection: {exc}') from exc
        area = 0.0
        try:
            area = float(face.GetArea()) * M2_TO_MM2 / (MODEL_SCALE * MODEL_SCALE)
        except Exception:
            pass
        geom_type = ''
        surface_types = {
            4001: 'PLANE',
            4002: 'CYLINDER',
            4003: 'CONE',
            4004: 'SPHERE',
            4005: 'TORUS',
            4006: 'BSPLINE',
            4007: 'BLEND',
            4008: 'OFFSET',
            4009: 'EXTRU',
            4010: 'SREV',
        }
        try:
            surface = _maybe_call(face.GetSurface)
            identity = int(_maybe_call(surface.Identity))
            geom_type = surface_types.get(identity, str(identity))
        except Exception:
            surface = None
        normal = None
        try:
            values = _maybe_call(getattr(face, 'Normal'))
            if values is not None and len(values) >= 3:
                normal = _unit(tuple(float(values[index]) for index in range(3)))
        except Exception:
            pass
        if normal is None and geom_type == 'PLANE' and surface is not None:
            try:
                values = _maybe_call(getattr(surface, 'PlaneParams'))
                if values is not None and len(values) >= 6:
                    normal = _unit(tuple(float(values[index]) for index in range(3, 6)))
            except Exception:
                pass
        signature = {
            'bbox': bbox,
            'center': center,
            'area': area,
            'geom_type': geom_type,
            'normal': normal,
        }
        try:
            signature['edge_count'] = len(_maybe_call(face.GetEdges) or [])
            signature['inner_wire_count'] = max(0, int(_maybe_call(face.GetLoopCount)) - 1)
        except Exception:
            pass
        return signature

    def _cylinder_surface_params(self, face):
        surface = None
        for call in (
            lambda: _maybe_call(face.GetSurface),
            lambda: win32com.client.Dispatch(face._oleobj_.InvokeTypes(
                3,
                0,
                pythoncom.DISPATCH_METHOD,
                (pythoncom.VT_DISPATCH, 0),
                (),
            )),
        ):
            try:
                surface = call()
                if surface is not None:
                    break
            except Exception:
                surface = None
        if surface is None:
            return None
        is_cylinder = False
        for call in (
            lambda: bool(_maybe_call(surface.IsCylinder)),
            lambda: bool(surface._oleobj_.InvokeTypes(
                7,
                0,
                pythoncom.DISPATCH_METHOD,
                (pythoncom.VT_BOOL, 0),
                (),
            )),
        ):
            try:
                is_cylinder = call()
                break
            except Exception:
                pass
        if not is_cylinder:
            return None
        values = None
        for call in (
            lambda: _maybe_call(surface.CylinderParams),
            lambda: surface._oleobj_.InvokeTypes(
                2,
                0,
                pythoncom.DISPATCH_PROPERTYGET,
                (pythoncom.VT_VARIANT, 0),
                (),
            ),
        ):
            try:
                values = tuple(float(value) for value in call())
                if len(values) >= 7:
                    break
            except Exception:
                values = None
        if values is None or len(values) < 7:
            return None
        scale = M_TO_MM / MODEL_SCALE
        return {
            'origin': tuple(values[index] * scale for index in range(3)),
            'axis': _unit(values[3:6]),
            'radius': abs(float(values[6]) * scale),
            'bbox': self._box_from_entity(face),
        }

    def _is_missing_cylinder_seam(self, body, selector):
        selector = _selector_geometry(selector)
        if _selector_kind(selector, {}) != 'edge':
            return False
        if _selector_geom_type(selector) != 'LINE':
            return False
        start = _tuple3_or_none(selector.get('start'))
        end = _tuple3_or_none(selector.get('end'))
        expected_length = selector.get('length')
        if start is None or end is None or expected_length is None:
            return False
        direction = _sub(end, start)
        chord_length = _norm(direction)
        scale = max(1.0, chord_length, abs(float(expected_length)))
        if chord_length <= scale * 1.0e-10:
            return False
        if _relative_error(chord_length, expected_length) > 1.0e-4:
            return False
        unit_direction = _unit(direction)
        body_bbox = self._box_from_entity(body)
        for face in self._body_faces(body):
            cylinder = self._cylinder_surface_params(face)
            if cylinder is None:
                continue
            if abs(_dot(unit_direction, cylinder['axis'])) < 1.0 - 1.0e-6:
                continue
            radius = float(cylinder['radius'])
            radius_scale = max(1.0, radius)
            if (
                abs(_point_line_distance(start, cylinder['origin'], cylinder['axis']) - radius)
                > radius_scale * 1.0e-5
                or abs(_point_line_distance(end, cylinder['origin'], cylinder['axis']) - radius)
                > radius_scale * 1.0e-5
            ):
                continue
            bbox = cylinder.get('bbox')
            if (
                not isinstance(bbox, dict)
                or _distance(bbox.get('min'), bbox.get('max')) <= 1.0e-12
            ):
                bbox = body_bbox
            tolerance = scale * 1.0e-5
            if not isinstance(bbox, dict):
                continue
            if not all(
                float(bbox['min'][index]) - tolerance <= point[index]
                <= float(bbox['max'][index]) + tolerance
                for point in (start, end)
                for index in range(3)
            ):
                continue
            return True
        return False

    def _detail_edge_topology_match(
        self, ranked, selector, source, missing_seam
    ):
        closed_intersection = _closed_intersection_candidate(ranked, selector)
        if closed_intersection is not None:
            return closed_intersection
        if _is_missing_revolution_seam(ranked, selector):
            return missing_seam
        if self._is_missing_cylinder_seam(source, selector):
            return missing_seam
        return None

    def _body_edges(self, body):
        try:
            edges = _maybe_call(body.GetEdges)
        except Exception:
            edges = None
        if not edges:
            return []
        return list(edges) if isinstance(edges, (list, tuple)) else [edges]

    def _body_faces(self, body):
        try:
            faces = _maybe_call(body.GetFaces)
        except Exception:
            faces = None
        if not faces:
            return []
        return list(faces) if isinstance(faces, (list, tuple)) else [faces]

    def _feature_detail_edges(self, params, inputs, kind, node_id):
        upstream_bodies = self._bodies_from_value(
            self._first_output(inputs[0])
        )
        if upstream_bodies:
            self._capture_detail_source_topology(
                inputs[0], upstream_bodies
            )
        # Keep detail features attached to their live input body even when a
        # downstream transform/boolean consumes the result. Copying the input
        # first creates a static BaseBody/MoveCopy snapshot and severs native
        # parameter propagation after the document is reopened.
        selectors = []
        for selector_id in params.get('selected_edge_node_ids') or []:
            payload = self.selection_payloads.get(str(selector_id))
            if payload:
                selectors.append(payload.get('params') or {})
        if not selectors:
            for item in params.get('selected_edges') or []:
                if isinstance(item, dict):
                    selectors.append(item.get('selector_hint') or item)
        if not selectors:
            raise RuntimeError(f'{kind} requires at least one geometrically selected edge')
        if len(upstream_bodies) > 1:
            # Match against the same complete edge pool represented by the
            # canonical compound, then require every selector (including a
            # fragmented path) to belong to exactly one native body. This
            # preserves unaffected live bodies instead of silently dropping
            # them when SolidWorks reports only the feature's changed body.
            edge_signatures = []
            body_edge_signatures = []
            edge_owners = {}
            for body_index, body in enumerate(upstream_bodies):
                signatures = [
                    (edge, self._edge_signature(edge))
                    for edge in self._body_edges(body)
                ]
                body_edge_signatures.append(signatures)
                for edge, signature in signatures:
                    edge_signatures.append((edge, signature))
                    edge_owners[id(edge)] = body_index
            selectors_by_body = {
                index: [] for index in range(len(upstream_bodies))
            }
            missing_seam = object()

            def compound_topology_match(ranked, selector):
                closed_intersection = _closed_intersection_candidate(
                    ranked, selector
                )
                if closed_intersection is not None:
                    return closed_intersection
                seam_owners = []
                for body_index, body in enumerate(upstream_bodies):
                    local_ranked = sorted(
                        body_edge_signatures[body_index],
                        key=lambda item: _geom_score(item[1], selector),
                    )
                    if (
                        _is_missing_revolution_seam(local_ranked, selector)
                        or self._is_missing_cylinder_seam(body, selector)
                    ):
                        seam_owners.append(body_index)
                if len(seam_owners) == 1:
                    return missing_seam
                if len(seam_owners) > 1:
                    raise RuntimeError(
                        f'{kind} {node_id} seam selector is ambiguous across '
                        f'live bodies {seam_owners!r}'
                    )
                return None

            skipped_seams = 0
            individual_candidates = {}
            individual_errors = {}
            for selector_index, selector in enumerate(selectors):
                try:
                    individual_candidates[selector_index] = (
                        _selection_candidates_by_geometry(
                            edge_signatures,
                            selector,
                            'edge',
                            topology_match=compound_topology_match,
                        )
                    )
                except RuntimeError as exc:
                    individual_errors[selector_index] = exc
            coalesced_pairs = _coalesced_edge_selector_pairs(
                edge_signatures,
                selectors,
            )
            coalesced_pairs = [
                pair for pair in coalesced_pairs
                if pair[0] in individual_errors or pair[1] in individual_errors
            ]
            coalesced_candidates = {}
            for left_index, right_index, candidate_index in coalesced_pairs:
                candidate = edge_signatures[candidate_index][0]
                coalesced_candidates[left_index] = candidate
                coalesced_candidates[right_index] = candidate
            covered_errors = set(individual_errors) & set(coalesced_candidates)
            unresolved_errors = sorted(set(individual_errors) - covered_errors)
            if unresolved_errors:
                raise individual_errors[unresolved_errors[0]]
            for selector_index, selector in enumerate(selectors):
                candidates = (
                    [coalesced_candidates[selector_index]]
                    if selector_index in coalesced_candidates
                    else individual_candidates[selector_index]
                )
                if len(candidates) == 1 and candidates[0] is missing_seam:
                    skipped_seams += 1
                    continue
                owners = {
                    edge_owners.get(id(candidate)) for candidate in candidates
                }
                owners.discard(None)
                if len(owners) != 1:
                    raise RuntimeError(
                        f'{kind} {node_id} selector {selector_index} '
                        f'matched edges on {len(owners)} live bodies; refusing '
                        'an ambiguous multi-body detail feature'
                    )
                selectors_by_body[next(iter(owners))].append(selector)
            if skipped_seams:
                self.logs.append(
                    f'{kind} {node_id} omitted {skipped_seams} seam '
                    'selection(s) absent from the SolidWorks body set'
                )
            results = []
            for body_index, body in enumerate(upstream_bodies):
                body_selectors = selectors_by_body[body_index]
                if not body_selectors:
                    results.append(body)
                    continue
                results.append(
                    self._apply_detail_feature_to_body(
                        body,
                        body_selectors,
                        params,
                        kind,
                        f'{node_id}_body_{body_index + 1}',
                        allow_component_fallback=True,
                    )
                )
            self.logs.append(
                f'{kind} {node_id} preserved {len(results)} live bodies; '
                f'{sum(bool(value) for value in selectors_by_body.values())} '
                'body/bodies were affected'
            )
            self._validate_detail_result(
                results, kind, node_id
            )
            return results
        source = upstream_bodies[0]
        self.logs.append(f'{kind} {node_id} consumes the live input body')
        result = self._apply_detail_feature_to_body(
            source,
            selectors,
            params,
            kind,
            node_id,
            allow_component_fallback=True,
            topology_source_node_id=inputs[0],
            topology_target_node_id=node_id,
        )
        self._validate_detail_result(
            result, kind, node_id
        )
        return result

    def _detail_selected_edges(self, source, selectors, kind, node_id):
        edge_signatures = [
            (edge, self._edge_signature(edge))
            for edge in self._body_edges(source)
        ]
        selected = []
        skipped_seams = 0
        missing_seam = object()
        individual_candidates = {}
        individual_errors = {}
        for selector_index, selector in enumerate(selectors):
            try:
                individual_candidates[selector_index] = (
                    _selection_candidates_by_geometry(
                        edge_signatures,
                        selector,
                        'edge',
                        topology_match=lambda _ranked, normalized_selector: self._detail_edge_topology_match(
                            _ranked,
                            normalized_selector,
                            source,
                            missing_seam,
                        ),
                    )
                )
            except RuntimeError as exc:
                individual_errors[selector_index] = exc
        coalesced_pairs = _coalesced_edge_selector_pairs(
            edge_signatures,
            selectors,
        )
        coalesced_pairs = [
            pair for pair in coalesced_pairs
            if pair[0] in individual_errors or pair[1] in individual_errors
        ]
        coalesced_by_selector = {}
        for left_index, right_index, candidate_index in coalesced_pairs:
            coalesced_by_selector[left_index] = (
                right_index, edge_signatures[candidate_index][0]
            )
        consumed_selectors = {
            right_index
            for _left_index, right_index, _candidate_index in coalesced_pairs
        }
        covered_errors = {
            index
            for left_index, right_index, _candidate_index in coalesced_pairs
            for index in (left_index, right_index)
            if index in individual_errors
        }
        unresolved_errors = sorted(set(individual_errors) - covered_errors)
        if unresolved_errors:
            raise individual_errors[unresolved_errors[0]]
        for selector_index, selector in enumerate(selectors):
            if selector_index in consumed_selectors:
                continue
            if selector_index in coalesced_by_selector:
                right_index, candidate = coalesced_by_selector[selector_index]
                selected.append(candidate)
                self.logs.append(
                    f'{kind} {node_id} coalesced selector pair '
                    f'{selector_index}/{right_index} onto one complete '
                    'SolidWorks edge'
                )
                continue
            candidates = individual_candidates[selector_index]
            if len(candidates) == 1 and candidates[0] is missing_seam:
                skipped_seams += 1
            else:
                selected.extend(candidates)
        return selected, skipped_seams

    def _validate_detail_result(self, bodies, kind, node_id):
        if not self._bodies_from_value(bodies):
            raise RuntimeError(f'SolidWorks {kind} feature {node_id} produced no body')

    def _capture_detail_source_topology(self, source_node_id, sources):
        source_node_id = str(source_node_id)
        if source_node_id in self.captured_topology_source_ids:
            return
        self.captured_topology_source_ids.add(source_node_id)
        catalog = self.detail_edge_catalog.get(source_node_id)
        if not isinstance(catalog, dict):
            return
        edge_catalog = catalog.get('edges') or []
        targets = dict(catalog.get('targets') or {})
        source_bodies = (
            list(sources)
            if isinstance(sources, (list, tuple))
            else [sources]
        )
        native_signatures = [
            (edge, self._edge_signature(edge))
            for source in source_bodies
            if source is not None
            for edge in self._body_edges(source)
        ]
        references_to_indices = {}
        failed = 0
        failure_details = []
        for entry in edge_catalog:
            if not isinstance(entry, dict):
                failed += 1
                failure_details.append({'index': None, 'reason': 'invalid_entry'})
                continue
            canonical_index = entry.get('canonical_index')
            try:
                canonical_index = int(canonical_index)
                selector = dict(entry.get('selector') or {})
                candidates = _selection_candidates_by_geometry(
                    native_signatures,
                    selector,
                    f'persisted edge {source_node_id}:{canonical_index}',
                )
                if len(candidates) != 1:
                    failed += 1
                    failure_details.append({
                        'index': canonical_index,
                        'reason': f'native_candidate_count={len(candidates)}',
                    })
                    continue
                reference = self._persistent_reference_bytes(candidates[0])
                if not reference:
                    failed += 1
                    failure_details.append({
                        'index': canonical_index,
                        'reason': 'empty_persistent_reference',
                    })
                    continue
                encoded = base64.b64encode(reference).decode('ascii')
                references_to_indices.setdefault(encoded, []).append(
                    canonical_index
                )
            except Exception as exc:
                failed += 1
                failure_details.append({
                    'index': canonical_index,
                    'reason': f'{type(exc).__name__}: {exc}',
                })
        mappings = {
            str(indices[0]): [reference]
            for reference, indices in references_to_indices.items()
            if len(indices) == 1
        }
        collapsed = sum(
            len(indices)
            for indices in references_to_indices.values()
            if len(indices) > 1
        )
        self.persisted_topology_maps[source_node_id] = {
            'source_node_id': source_node_id,
            'mappings': mappings,
            'targets': targets,
        }
        self.logs.append(
            f'persisted GSM topology map prepared for {source_node_id}: '
            f'bodies={len(source_bodies)} mapped={len(mappings)} '
            f'failed={failed} collapsed={collapsed}'
        )
        if failure_details:
            self.logs.append(
                f'persisted GSM topology failures for {source_node_id}: '
                f'{failure_details[:12]!r}'
            )

    def _capture_detail_feature_topology(
        self, feature, result_body, source_node_id, detail_node_id
    ):
        stage = 'resolve_feature'
        source_map = self.persisted_topology_maps.get(str(source_node_id))
        if not isinstance(source_map, dict):
            return
        target = (source_map.get('targets') or {}).get(str(detail_node_id))
        if not isinstance(target, dict):
            return
        canonical_indices = [
            int(value) for value in target.get('selected_indices') or []
        ]
        if not canonical_indices:
            return
        definition = None
        accessed = False
        try:
            feature_name = (
                str(feature)
                if isinstance(feature, str)
                else str(_maybe_call(feature.Name) or '')
            )
            persistent_features = [
                candidate
                for candidate in self._features({'Fillet', 'Chamfer'})
                if str(_maybe_call(candidate.Name) or '') == feature_name
            ]
            if len(persistent_features) == 1:
                feature = persistent_features[0]
                self.logs.append(
                    f'rebound persistent detail feature {feature_name}'
                )
            if result_body is None:
                reopened_bodies = self._solid_bodies()
                if len(reopened_bodies) == 1:
                    result_body = reopened_bodies[0]
            stage = 'get_definition'
            definition_value = feature.GetDefinition
            definition = (
                definition_value
                if hasattr(definition_value, '_oleobj_')
                else _maybe_call(definition_value)
            )
            if definition is None:
                return
            stage = 'access_selections'
            for call in (
                lambda: definition.AccessSelections(
                    self.model, _empty_dispatch()
                ),
                lambda: definition.AccessSelections(self.model, None),
            ):
                try:
                    accessed = bool(call())
                    if accessed:
                        break
                except Exception:
                    pass
            stage = 'query_detail_interface'
            edge_definition = definition
            edge_dispids = (21, 17)
            for interface_iid, edges_dispid in (
                ('{9FE7C8DB-8A4C-41BB-8E3B-7600692DBC92}', 21),
                ('{8427D092-A1FC-49C9-B1ED-EC52D2389E9A}', 17),
            ):
                try:
                    interface = definition._oleobj_.QueryInterface(
                        pythoncom.MakeIID(interface_iid),
                        pythoncom.IID_IDispatch,
                    )
                    edge_definition = win32com.client.Dispatch(interface)
                    edge_dispids = (edges_dispid,)
                    break
                except Exception:
                    pass
            stage = 'read_feature_edges'
            try:
                edges = _maybe_call(edge_definition.Edges)
            except Exception:
                edges = None
                for dispid in edge_dispids:
                    try:
                        edges = edge_definition._oleobj_.InvokeTypes(
                            dispid,
                            0,
                            pythoncom.DISPATCH_PROPERTYGET,
                            (pythoncom.VT_VARIANT, 0),
                            (),
                        )
                        break
                    except Exception:
                        pass
            edges = (
                list(edges)
                if isinstance(edges, (list, tuple))
                else ([edges] if edges is not None else [])
            )
            source_catalog = self.detail_edge_catalog.get(
                str(source_node_id)
            ) or {}
            edge_catalog = source_catalog.get('edges') or []
            feature_mappings = {}
            if len(edges) == len(canonical_indices):
                stage = 'persist_feature_edges'
                for canonical_index, edge in zip(canonical_indices, edges):
                    reference = self._persistent_reference_bytes(edge)
                    if not reference:
                        raise RuntimeError(
                            f'empty FeatureData reference for canonical edge '
                            f'{canonical_index}'
                        )
                    feature_mappings[str(canonical_index)] = [
                        base64.b64encode(reference).decode('ascii')
                    ]
            else:
                self.logs.append(
                    f'native detail seed count differs for '
                    f'{detail_node_id}: FeatureData edges={len(edges)} '
                    f'canonical={len(canonical_indices)}; applying strict '
                    'reconstruction-stage geometry mapping'
                )
                entries_by_index = {
                    int(entry.get('canonical_index')): entry
                    for entry in edge_catalog
                    if isinstance(entry, dict)
                    and entry.get('canonical_index') is not None
                }
                selected_entries = [
                    entries_by_index.get(canonical_index)
                    for canonical_index in canonical_indices
                ]
                if any(entry is None for entry in selected_entries):
                    raise RuntimeError(
                        'canonical detail seed catalog is incomplete'
                    )
                selectors = [
                    dict(entry.get('selector') or {})
                    for entry in selected_entries
                ]
                feature_signatures = [
                    (edge, self._edge_signature(edge)) for edge in edges
                ]
                individual_candidates = {}
                individual_errors = {}
                for selector_index, selector in enumerate(selectors):
                    try:
                        individual_candidates[selector_index] = (
                            _selection_candidates_by_geometry(
                                feature_signatures,
                                selector,
                                f'FeatureData edge {detail_node_id}:'
                                f'{canonical_indices[selector_index]}',
                            )
                        )
                    except RuntimeError as exc:
                        individual_errors[selector_index] = exc
                coalesced_pairs = _coalesced_edge_selector_pairs(
                    feature_signatures, selectors
                )
                coalesced_pairs = [
                    pair for pair in coalesced_pairs
                    if pair[0] in individual_errors
                    or pair[1] in individual_errors
                ]
                coalesced_candidates = {}
                for left_index, right_index, candidate_index in coalesced_pairs:
                    candidate = feature_signatures[candidate_index][0]
                    coalesced_candidates[left_index] = [candidate]
                    coalesced_candidates[right_index] = [candidate]
                for selector_index, canonical_index in enumerate(
                    canonical_indices
                ):
                    candidates = coalesced_candidates.get(selector_index)
                    if candidates is None:
                        candidates = individual_candidates.get(selector_index)
                    if not candidates:
                        continue
                    references = []
                    for edge in candidates:
                        reference = self._persistent_reference_bytes(edge)
                        if not reference:
                            references = []
                            break
                        encoded = base64.b64encode(reference).decode('ascii')
                        if encoded not in references:
                            references.append(encoded)
                    if references:
                        feature_mappings[str(canonical_index)] = references
            target['feature_mappings'] = feature_mappings
            feature_reference_owners = {}
            for canonical_index, references in feature_mappings.items():
                for reference in references:
                    feature_reference_owners.setdefault(reference, []).append(
                        int(canonical_index)
                    )
            target['feature_reference_owners'] = {
                reference: sorted(indices)
                for reference, indices in feature_reference_owners.items()
            }
            target['feature_seed_count'] = len(edges)
            self.logs.append(
                f'persisted native detail seed mapping for {detail_node_id}: '
                f'entries={len(feature_mappings)} '
                f'canonical={len(canonical_indices)}'
            )

            stage = 'persist_post_feature_edges'
            selected_set = set(canonical_indices)
            result_signatures = [
                (edge, self._edge_signature(edge))
                for edge in self._body_edges(result_body)
            ]
            post_references_to_indices = {}
            post_failures = 0
            for entry in edge_catalog:
                try:
                    canonical_index = int(entry.get('canonical_index'))
                    if canonical_index in selected_set:
                        continue
                    candidates = _selection_candidates_by_geometry(
                        result_signatures,
                        dict(entry.get('selector') or {}),
                        f'post-detail edge {detail_node_id}:'
                        f'{canonical_index}',
                    )
                    if len(candidates) != 1:
                        post_failures += 1
                        continue
                    reference = self._persistent_reference_bytes(
                        candidates[0]
                    )
                    if not reference:
                        post_failures += 1
                        continue
                    encoded = base64.b64encode(reference).decode('ascii')
                    post_references_to_indices.setdefault(
                        encoded, []
                    ).append(canonical_index)
                except Exception:
                    post_failures += 1
            post_feature_mappings = {
                str(indices[0]): [reference]
                for reference, indices in post_references_to_indices.items()
                if len(indices) == 1
            }
            target['post_feature_mappings'] = post_feature_mappings
            self.logs.append(
                f'persisted post-detail replacement mapping for '
                f'{detail_node_id}: entries={len(post_feature_mappings)} '
                f'failed={post_failures}'
            )
        except Exception as exc:
            self.logs.append(
                f'could not persist native detail seed mapping for '
                f'{detail_node_id} at {stage}: {exc}'
            )
        finally:
            if definition is not None and accessed:
                try:
                    definition.ReleaseSelectionAccess()
                except Exception:
                    pass

    def _retry_pending_detail_topology(self):
        for record in self.pending_detail_topology:
            source_id = str(record.get('source_node_id') or '')
            target_id = str(record.get('detail_node_id') or '')
            source_map = self.persisted_topology_maps.get(source_id) or {}
            target = (source_map.get('targets') or {}).get(target_id) or {}
            if target.get('feature_mappings'):
                continue
            self._capture_detail_feature_topology(
                record.get('feature_name') or record.get('feature'),
                None,
                source_id,
                target_id,
            )

    def _delete_retry_feature(self, feature, kind, node_id):
        self._clear_selection()
        try:
            selected = bool(feature.Select2(False, 0))
        except Exception:
            selected = False
        deleted = False
        if selected:
            try:
                deleted = bool(self.model.Extension.DeleteSelection2(0))
            except Exception:
                deleted = False
        if not deleted:
            raise RuntimeError(
                f'Could not delete rejected SolidWorks {kind} candidate '
                f'for {node_id}'
            )
        try:
            self.model.ForceRebuild3(False)
        except Exception:
            pass

    def _apply_detail_feature_to_body(
        self,
        source,
        selectors,
        params,
        kind,
        node_id,
        *,
        allow_component_fallback,
        topology_source_node_id=None,
        topology_target_node_id=None,
        require_geometry_change=False,
    ):
        source_bbox = self._box_from_entity(source)
        source_descriptor = {
            'bbox': source_bbox,
            'volume': self._body_volume(source),
        }
        source_name = self._body_name(source)
        source_reference = self._persistent_reference_bytes(source)
        source = self._restore_circular_partitions(source, selectors, node_id)
        selected, skipped_seams = self._detail_selected_edges(
            source, selectors, kind, node_id
        )
        if skipped_seams:
            self.logs.append(
                f'{kind} {node_id} omitted {skipped_seams} cylindrical seam '
                'selection(s) absent from SolidWorks native topology'
            )
        if not selected:
            return source
        self._clear_selection()
        for index, edge in enumerate(selected):
            if not self._select_entity(edge, append=index > 0):
                raise RuntimeError(f'Could not select SolidWorks edge for {kind}')
        before = self._body_names()
        result = None
        feature_error = None
        candidate_rebuilt = False
        if kind == 'fillet':
            radius = _as_m(params.get('radius', 0.0))
            feature = None

            def create_fillet_from_definition(propagate):
                self._clear_selection()
                for edge_index, edge in enumerate(selected):
                    if not self._select_entity(
                        edge, append=edge_index > 0, mark=1
                    ):
                        return None
                definition = self.model.FeatureManager.CreateDefinition(1)
                if definition is None or not bool(definition.Initialize(0)):
                    return None
                definition.ConicTypeForCrossSectionProfile = 0
                definition.DefaultRadius = radius
                definition.OverflowType = 0
                definition.PropagateToTangentFaces = bool(propagate)
                definition.Edges = win32com.client.VARIANT(
                    pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH,
                    tuple(selected),
                )
                return self.model.FeatureManager.CreateFeature(definition)

            for call in (
                # FeatureData preserves the explicit seed-edge set and avoids
                # the legacy FeatureFillet option-bit expansion that can make
                # large disconnected selections invalid in SolidWorks.
                lambda: create_fillet_from_definition(False),
                lambda: create_fillet_from_definition(True),
                lambda: self.model.FeatureManager.FeatureFillet(
                    2,
                    radius,
                    0,
                    0,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.FeatureFillet(
                    66,
                    radius,
                    0,
                    0,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.FeatureFillet(
                    34,
                    radius,
                    0,
                    0,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.FeatureFillet(
                    98,
                    radius,
                    0,
                    0,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.FeatureFillet(
                    226,
                    radius,
                    0,
                    0,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.FeatureFillet(
                    SW_FEATURE_FILLET_OPTIONS,
                    radius,
                    0,
                    0,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.FeatureFillet3(
                    SW_FEATURE_FILLET_OPTIONS,
                    radius,
                    0.0,
                    0.0,
                    0,
                    0,
                    0,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.FeatureFillet2(
                    SW_FEATURE_FILLET_OPTIONS,
                    radius,
                    0.0,
                    0,
                    0,
                    0,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
                lambda: self.model.FeatureManager.InsertFeatureFillet(radius),
            ):
                try:
                    feature = call()
                    if feature is not None:
                        break
                except Exception as exc:
                    self.logs.append(f'fillet attempt failed for {node_id}: {exc}')
        else:
            distance = _as_m(params.get('distance', params.get('radius', 0.0)))
            feature = None

            def select_chamfer_edges(mark):
                self._clear_selection()
                for edge_index, edge in enumerate(selected):
                    if not self._select_entity(
                        edge, append=edge_index > 0, mark=mark
                    ):
                        return False
                return True

            def create_chamfer_from_definition():
                # CreateDefinition supports simple chamfers through
                # swFmFillet=1. The chamfer is the rho-zero profile
                # specialization of ISimpleFilletFeatureData2, not a
                # swFmChamfer definition. Tangent propagation stays disabled
                # so CADIR's explicit seed-edge set survives save/reopen.
                if not select_chamfer_edges(1):
                    return None
                definition = self.model.FeatureManager.CreateDefinition(1)
                if definition is None or not bool(definition.Initialize(0)):
                    return None
                definition.ConicTypeForCrossSectionProfile = 3
                definition.AsymmetricFillet = False
                definition.IsMultipleRadius = False
                definition.DefaultRadius = distance
                definition.OverflowType = 0
                definition.PropagateToTangentFaces = False
                definition.Edges = win32com.client.VARIANT(
                    pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH,
                    tuple(selected),
                )
                return self.model.FeatureManager.CreateFeature(definition)

            def insert_equal_distance_chamfer():
                if not select_chamfer_edges(0):
                    return None
                return self.model.FeatureManager.InsertFeatureChamfer(
                    0, 16, 0.0, 0.0, distance, 0.0, 0.0, 0.0
                )

            def insert_angle_distance_chamfer():
                if not select_chamfer_edges(0):
                    return None
                return self.model.FeatureManager.InsertFeatureChamfer(
                    0, 1, distance, math.pi / 4.0, 0.0, 0.0, 0.0, 0.0
                )

            for attempt_name, call in (
                # CADIR serializes the complete seed-edge set. Keep tangent
                # propagation disabled (option bit 4) so SolidWorks does not
                # silently expand those seeds and destabilize the persisted
                # FeatureData references after reopen.
                ('equal_distance', insert_equal_distance_chamfer),
                # Equal legs are also representable by a 45-degree
                # angle-distance chamfer. This is an API compatibility retry,
                # still with the exact explicit seed set and no propagation.
                ('angle_distance_45', insert_angle_distance_chamfer),
                # Some SolidWorks releases reject InsertFeatureChamfer for
                # large disconnected seed sets. The rho-zero simple-fillet
                # definition is the documented offset-face chamfer fallback,
                # but it is not the first choice because its distance
                # convention can differ from an equal-distance edge chamfer
                # on non-orthogonal faces.
                ('rho_zero_feature_data', create_chamfer_from_definition),
            ):
                candidate_feature = None
                try:
                    candidate_feature = call()
                    if candidate_feature is None:
                        continue
                    try:
                        candidate_feature.Name = (
                            f'SimpleCAD_{node_id}_{kind}_{attempt_name}'
                        )
                    except Exception:
                        pass
                    try:
                        self.model.ForceRebuild3(False)
                    except Exception as exc:
                        self.logs.append(
                            f'{kind} rebuild call failed for {node_id} '
                            f'candidate {attempt_name}: {exc}'
                        )
                    candidate_error, candidate_warning = _feature_error_status(
                        candidate_feature
                    )
                    if candidate_error and candidate_warning:
                        self.logs.append(
                            f'{kind} candidate {attempt_name} reported warning '
                            f'{candidate_error}'
                        )
                        candidate_error = 0
                    candidate_result = self._capture_new_body(
                        before,
                        candidate_feature,
                        expected_bbox=source_bbox,
                        fallback_body=source,
                    )
                    candidate_volume = self._body_volume(candidate_result)
                    candidate_bbox = self._box_from_entity(candidate_result)
                    candidate_matches = True
                    source_volume = source_descriptor.get('volume')
                    candidate_changed = (
                        source_volume is None
                        or candidate_volume is None
                        or _relative_error(
                            candidate_volume,
                            source_volume,
                            floor=1.0e-12,
                        ) > 1.0e-10
                        or _bbox_score(
                            candidate_bbox,
                            source_descriptor.get('bbox'),
                        ) > 1.0e-9
                    )
                    if require_geometry_change and not candidate_changed:
                        candidate_matches = False
                    self.logs.append(
                        f'chamfer {node_id} candidate {attempt_name} '
                        f'volume={candidate_volume!r} bbox={candidate_bbox!r} '
                        f'feature_error={candidate_error!r} '
                        f'geometry_changed={candidate_changed!r}'
                    )
                    if candidate_error in (None, 0) and candidate_matches:
                        feature = candidate_feature
                        result = candidate_result
                        feature_error = candidate_error
                        candidate_rebuilt = True
                        break
                    self._delete_retry_feature(
                        candidate_feature, kind, node_id
                    )
                    candidate_feature = None
                    persistent_source = (
                        self._resolve_persistent_reference_bytes(
                            source_reference
                        )
                    )
                    if (
                        persistent_source is not None
                        and self._body_matches_native_snapshot(
                            persistent_source, source_descriptor
                        )
                    ):
                        rebound_sources = [persistent_source]
                    else:
                        rebound_sources = [
                            body for body in self._solid_bodies()
                            if self._body_matches_native_snapshot(
                                body, source_descriptor
                            )
                        ]
                        named_sources = [
                            body for body in rebound_sources
                            if self._body_name(body) == source_name
                        ]
                        if len(named_sources) == 1:
                            rebound_sources = named_sources
                    if len(rebound_sources) != 1:
                        raise RuntimeError(
                            f'{kind} {node_id} could not uniquely rebind the '
                            f'live input body after rejecting {attempt_name}; '
                            f'candidates={len(rebound_sources)}'
                        )
                    source = rebound_sources[0]
                    source_bbox = self._box_from_entity(source)
                    selected, retry_skipped = self._detail_selected_edges(
                        source, selectors, kind, node_id
                    )
                    if retry_skipped != skipped_seams:
                        raise RuntimeError(
                            f'{kind} {node_id} seam classification changed '
                            'while retrying native candidates'
                        )
                    before = self._body_names()
                except Exception as exc:
                    self.logs.append(
                        f'chamfer attempt {attempt_name} failed for '
                        f'{node_id}: {exc}'
                    )
                    if 'Could not delete rejected' in str(exc):
                        raise
                    # A feature may have consumed the input before result
                    # capture fails. Roll it back before trying another API.
                    if candidate_feature is not None:
                        self._delete_retry_feature(candidate_feature, kind, node_id)
                        rebound = [body for body in self._solid_bodies() if self._body_matches_native_snapshot(body, source_descriptor)]
                        if len(rebound) != 1:
                            raise RuntimeError(f'{kind} {node_id} could not restore its input after failed feature capture') from exc
                        source = rebound[0]
                        selected, skipped_seams = self._detail_selected_edges(source, selectors, kind, node_id)
                        before = self._body_names()
        if feature is None:
            components = _selector_edge_components(selectors)
            if allow_component_fallback and len(components) > 1:
                self.logs.append(
                    f'{kind} {node_id} retrying {len(selectors)} selected edges '
                    f'as {len(components)} disconnected components'
                )
                current = source
                for component_index, component in enumerate(components):
                    current = self._apply_detail_feature_to_body(
                        current,
                        component,
                        params,
                        kind,
                        f'{node_id}_component_{component_index + 1}',
                        allow_component_fallback=False,
                        require_geometry_change=True,
                    )
                return current
            raise RuntimeError(
                f'SolidWorks {kind} feature creation failed; '
                f'selections={self._selection_state()!r}; logs={self.logs[-3:]!r}'
            )
        try:
            feature.Name = f'SimpleCAD_{node_id}_{kind}'
        except Exception:
            pass
        if not candidate_rebuilt:
            try:
                self.model.ForceRebuild3(False)
            except Exception as exc:
                self.logs.append(
                    f'{kind} rebuild call failed for {node_id}: {exc}'
                )
        if feature_error is None:
            feature_error, feature_warning = _feature_error_status(feature)
            if feature_error and feature_warning:
                self.logs.append(
                    f'{kind} feature {node_id} reported warning {feature_error}'
                )
                feature_error = 0
        if feature_error not in (None, 0):
            raise RuntimeError(
                f'SolidWorks {kind} feature {node_id} reports native '
                f'error code {feature_error}'
            )
        if result is None:
            result = self._capture_new_body(
                before,
                feature,
                expected_bbox=source_bbox,
                fallback_body=source,
            )
        if topology_source_node_id and topology_target_node_id:
            self.pending_detail_topology.append({
                'feature': feature,
                'feature_name': str(
                    _maybe_call(feature.Name) or ''
                ),
                'result_body': result,
                'source_node_id': str(topology_source_node_id),
                'detail_node_id': str(topology_target_node_id),
            })
            self._capture_detail_feature_topology(
                feature,
                result,
                topology_source_node_id,
                topology_target_node_id,
            )
        return result


__all__ = ["SelectionRuntimeMixin"]
