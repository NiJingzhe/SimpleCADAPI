"""Kernel-independent geometric selection, embedded in both CAD runtimes.

The weights and acceptance rules are the FreeCAD translator's GSM contract.
Adapters supply measurements in millimetres; enumeration order is never an ID.
"""

import math


def _gsm_point(value):
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return tuple(float(v) for v in value)
    return None


def _gsm_distance(first, second):
    if first is None or second is None:
        return 1e6
    return math.dist(first, second)


def _gsm_relative(actual, expected):
    return abs(float(actual) - float(expected)) / max(abs(float(actual)), abs(float(expected)), 1.0)


def _gsm_scale(selector):
    bbox = selector.get('bbox')
    if not isinstance(bbox, dict):
        return 1.0
    minimum, maximum = _gsm_point(bbox.get('min')), _gsm_point(bbox.get('max'))
    return max(math.dist(minimum, maximum), 1.0) if minimum is not None and maximum is not None else 1.0


def _gsm_type(value):
    value = str(value or '').upper().replace('_TYPE', '').replace('_', '')
    for token, canonical in (
        ('B-SPLINE', 'BSPLINE'), ('BSPLINE', 'BSPLINE'), ('BCURVE', 'BSPLINE'),
        ('BSURF', 'BSPLINE'), ('NURBS', 'BSPLINE'), ('BEZIER', 'BEZIER'),
        ('ELLIPTICALARC', 'ELLIPSE'), ('ELLIPSE', 'ELLIPSE'),
        ('CYLINDER', 'CYLINDER'), ('CIRCLE', 'CIRCLE'), ('PLANE', 'PLANE'),
        ('LINE', 'LINE'), ('CONE', 'CONE'), ('SPHERE', 'SPHERE'), ('TORUS', 'TORUS'),
    ):
        if token in value:
            return canonical
    return value


def _gsm_bbox_score(signature, selector):
    actual, expected = signature.get('bbox'), selector.get('bbox')
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return 0.0
    return sum(_gsm_distance(_gsm_point(actual.get(key)), _gsm_point(expected.get(key))) for key in ('min', 'max')) / _gsm_scale(selector)


def _gsm_score(signature, selector):
    score = 10.0 * _gsm_bbox_score(signature, selector)
    actual_type, expected_type = _gsm_type(signature.get('geom_type')), _gsm_type(selector.get('geom_type'))
    if actual_type and expected_type and actual_type != expected_type:
        score += 10.0
    kind = str(selector.get('kind') or selector.get('target_kind') or '').lower()
    scale = _gsm_scale(selector)
    if kind in ('edge', 'face'):
        measure = 'length' if kind == 'edge' else 'area'
        if selector.get(measure) is not None and signature.get(measure) is not None:
            score += 10.0 * _gsm_relative(signature[measure], selector[measure])
        score += 10.0 * _gsm_distance(_gsm_point(signature.get('center')), _gsm_point(selector.get('center'))) / scale
    if kind == 'edge':
        points = [_gsm_point(value.get(key)) for value in (signature, selector) for key in ('start', 'end')]
        if all(point is not None for point in points):
            start, end, expected_start, expected_end = points
            direct = math.dist(start, expected_start) + math.dist(end, expected_end)
            reverse = math.dist(start, expected_end) + math.dist(end, expected_start)
            score += min(direct, reverse) / max(float(signature.get('length', 1.0)), float(selector.get('length', 1.0)), 1.0)
    elif kind == 'face':
        actual_normal, expected_normal = _gsm_point(signature.get('normal')), _gsm_point(selector.get('normal'))
        if actual_normal is not None and expected_normal is not None:
            la = math.sqrt(sum(v*v for v in actual_normal))
            le = math.sqrt(sum(v*v for v in expected_normal))
            if la > 1e-12 and le > 1e-12:
                actual_normal = tuple(v/la for v in actual_normal)
                expected_normal = tuple(v/le for v in expected_normal)
                score += min(math.dist(actual_normal, expected_normal), math.dist(actual_normal, tuple(-v for v in expected_normal)))
        for key in ('edge_count', 'inner_wire_count'):
            if key in selector and key in signature:
                score += abs(int(signature[key]) - int(selector[key])) * 0.001
    elif kind == 'vertex' and 'coordinates' in signature:
        score += 10.0 * _gsm_distance(_gsm_point(signature['coordinates']), _gsm_point(selector.get('coordinates'))) / scale
    elif kind == 'wire' and 'edge_count' in selector:
        score += abs(int(signature.get('edge_count', 0)) - int(selector['edge_count'])) * 10.0
    elif kind == 'solid' and 'volume' in selector and 'volume' in signature:
        score += 10.0 * _gsm_relative(signature['volume'], selector['volume'])
    return score


def _gsm_select(signatures, selector, context=None):
    if not signatures:
        raise RuntimeError(f'No candidates available for geo selection; context={context!r}')
    ranked = sorted(((_gsm_score(signature, selector), candidate) for candidate, signature in signatures), key=lambda item: item[0])
    best_score, best = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else float('inf')
    if best_score <= 1e-4 and second_score <= 1e-4:
        raise RuntimeError(f'Geo selector is ambiguous; context={context!r}, best score={best_score:.6g}, second score={second_score:.6g}')
    if best_score > 1e-2 and not (best_score <= 0.5 and second_score >= best_score * 10.0 + 0.5):
        raise RuntimeError(f'Geo selector did not match a stable candidate; context={context!r}, best score={best_score:.6g}, second score={second_score:.6g}')
    return best
