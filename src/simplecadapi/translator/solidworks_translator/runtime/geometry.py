"""SolidWorks runtime fragment: geometry helpers."""

MM_TO_M = 0.001
M_TO_MM = 1000.0
M2_TO_MM2 = 1000000.0
TOL = 1.0e-7
MODEL_SCALE = 1.0
SW_DOC_PART = 1
SW_SOLID_BODY = 0
SW_OPEN_DOC_OPTIONS_SILENT = 1
SW_SAVE_AS_CURRENT_VERSION = 0
SW_SAVE_AS_OPTIONS_SILENT = 1
SWBODYINTERSECT = 15901
SWBODYCUT = 15902
SWBODYADD = 15903
SW_TWIST_CONTROL_NORMAL_CONSTANT_TWIST = 9
SW_FM_SWEEP = 17
SW_FEATURE_FILLET_OPTIONS = 194


def _native_part_output_path(output_path):
    step_path = os.path.abspath(output_path)
    step_directory = os.path.dirname(step_path)
    if os.path.basename(step_directory).lower() == 'steps':
        native_directory = os.path.join(
            os.path.dirname(step_directory), 'sldprt'
        )
    else:
        native_directory = step_directory
    stem = os.path.splitext(os.path.basename(step_path))[0]
    return os.path.join(native_directory, stem + '.sldprt')


def _native_assembly_output_path(output_path):
    step_path = os.path.abspath(output_path)
    step_directory = os.path.dirname(step_path)
    if os.path.basename(step_directory).lower() == 'steps':
        native_directory = os.path.join(
            os.path.dirname(step_directory), 'sldasm'
        )
    else:
        native_directory = step_directory
    stem = os.path.splitext(os.path.basename(step_path))[0]
    return os.path.join(native_directory, stem + '.sldasm')


def _empty_dispatch():
    return win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)


def _byref_i4(value=0):
    return win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, int(value))


def _maybe_call(value):
    # pywin32 dispatch objects are callable too; calling one invokes its
    # default COM member, not the getter that already returned this object.
    if hasattr(value, '_oleobj_'):
        return value
    return value() if callable(value) else value


def _feature_error_status(feature):
    """Normalize GetErrorCode2's return value and out IsWarning on both versions."""
    try:
        getter = feature.GetErrorCode2
        try:
            result = _maybe_call(getter)
        except Exception:
            warning = win32com.client.VARIANT(
                pythoncom.VT_BYREF | pythoncom.VT_BOOL, False
            )
            result = getter(warning)
            if not isinstance(result, (tuple, list)):
                return int(result), bool(warning.value)
        if isinstance(result, (tuple, list)):
            if len(result) != 2:
                raise ValueError('Unexpected GetErrorCode2 return values')
            return int(result[0]), bool(result[1])
        # A scalar carries no warning flag. Keep nonzero codes fatal.
        return int(result), False
    except Exception:
        try:
            return int(_maybe_call(feature.GetErrorCode)), False
        except Exception:
            return None, False


def _v3(value, default=(0.0, 0.0, 0.0)):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        value = default
    return (float(value[0]), float(value[1]), float(value[2]))


def _add(a, b):
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


def _sub(a, b):
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _mul(a, scalar):
    return (float(a[0]) * scalar, float(a[1]) * scalar, float(a[2]) * scalar)


def _dot(a, b):
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _cross(a, b):
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a, fallback=(0.0, 0.0, 1.0)):
    length = _norm(_v3(a, fallback))
    if length <= 1.0e-12:
        return _v3(fallback)
    x, y, z = _v3(a, fallback)
    return (x / length, y / length, z / length)


def _distance(a, b):
    return _norm(_sub(_v3(a), _v3(b)))


def _point_line_distance(point, origin, direction):
    direction = _unit(direction)
    return _norm(_cross(_sub(_v3(point), _v3(origin)), direction))


def _rotate_point_payload(point, axis, angle_degrees, origin):
    axis = _unit(axis)
    relative = _sub(_v3(point), _v3(origin))
    angle = math.radians(float(angle_degrees))
    rotated = _add(
        _add(
            _mul(relative, math.cos(angle)),
            _mul(_cross(axis, relative), math.sin(angle)),
        ),
        _mul(axis, _dot(axis, relative) * (1.0 - math.cos(angle))),
    )
    return _add(_v3(origin), rotated)


def _rotate_direction_payload(direction, axis, angle_degrees):
    return _sub(
        _rotate_point_payload(direction, axis, angle_degrees, (0.0, 0.0, 0.0)),
        _rotate_point_payload((0.0, 0.0, 0.0), axis, angle_degrees, (0.0, 0.0, 0.0)),
    )


def _mirror_point_payload(point, plane_origin, plane_normal):
    normal = _unit(plane_normal)
    offset = _sub(_v3(point), _v3(plane_origin))
    return _sub(_v3(point), _mul(normal, 2.0 * _dot(offset, normal)))


def _mirror_direction_payload(direction, plane_normal):
    normal = _unit(plane_normal)
    direction = _v3(direction)
    return _sub(direction, _mul(normal, 2.0 * _dot(direction, normal)))


def _transform_geometry_value(value, point_transform, direction_transform):
    if not isinstance(value, dict):
        raise RuntimeError(
            f'Expected transformable SimpleCAD geometry, got {type(value).__name__}'
        )
    kind = value.get('kind')
    transformed = dict(value)
    if kind == 'wire':
        transformed['edges'] = [
            _transform_geometry_value(edge, point_transform, direction_transform)
            for edge in value.get('edges') or []
        ]
        return transformed
    if kind == 'face':
        transformed['outer'] = _transform_geometry_value(
            value.get('outer'), point_transform, direction_transform
        )
        transformed['inners'] = [
            _transform_geometry_value(wire, point_transform, direction_transform)
            for wire in value.get('inners') or []
        ]
        if value.get('normal') is not None:
            transformed['normal'] = _unit(direction_transform(value.get('normal')))
        return transformed
    if kind != 'edge':
        raise RuntimeError(f'Unsupported non-body transform value kind: {kind!r}')

    edge_type = value.get('type')
    for key in ('start', 'middle', 'end', 'center'):
        if value.get(key) is not None:
            transformed[key] = point_transform(value.get(key))
    if edge_type == 'spline':
        transformed['controls'] = [
            point_transform(point) for point in value.get('controls') or []
        ]
    for key in ('normal', '_kernel_x_axis', '_kernel_y_axis'):
        if value.get(key) is not None:
            transformed[key] = _unit(direction_transform(value.get(key)))
    if edge_type == 'helix':
        helix_params = dict(value.get('params') or {})
        for key in ('center', 'origin'):
            if helix_params.get(key) is not None:
                helix_params[key] = point_transform(helix_params.get(key))
        for key in ('dir', 'axis', 'normal'):
            if helix_params.get(key) is not None:
                helix_params[key] = _unit(direction_transform(helix_params.get(key)))
        transformed['params'] = helix_params
    return transformed


def _plane_axes(normal):
    normal = _unit(normal)
    reference = (1.0, 0.0, 0.0)
    if abs(_dot(normal, reference)) > 0.9:
        reference = (0.0, 1.0, 0.0)
    x_axis = _sub(reference, _mul(normal, _dot(reference, normal)))
    x_axis = _unit(x_axis)
    y_axis = _unit(_cross(normal, x_axis))
    return x_axis, y_axis


def _angle_arc_axes(normal):
    normal = _unit(normal)
    reference = (1.0, 0.0, 0.0) if abs(normal[2]) > 0.9 else (0.0, 0.0, 1.0)
    x_axis = _cross(normal, reference)
    if _norm(x_axis) <= 1.0e-12:
        x_axis = _cross(normal, (0.0, 1.0, 0.0))
    x_axis = _unit(x_axis)
    y_axis = _unit(_cross(normal, x_axis))
    return x_axis, y_axis


def _angle_arc_world_point(
    center,
    radius,
    angle,
    normal,
    x_axis=None,
    y_axis=None,
):
    if x_axis is None or y_axis is None:
        x_axis, y_axis = _angle_arc_axes(normal)
    else:
        x_axis = _unit(x_axis)
        y_axis = _unit(y_axis)
    radial = _add(
        _mul(x_axis, float(radius) * math.cos(float(angle))),
        _mul(y_axis, float(radius) * math.sin(float(angle))),
    )
    return _add(_v3(center), radial)


def _model_work_scale(payload):
    lengths = []

    def add_length(value):
        try:
            value = abs(float(value))
        except (TypeError, ValueError):
            return
        if math.isfinite(value) and value > 1.0e-9:
            lengths.append(value)

    for node in ((payload.get('graph') or {}).get('nodes') or []):
        op = str(node.get('op') or '')
        params = node.get('params') or {}
        if op == 'make_line_redge':
            add_length(_distance(params.get('start'), params.get('end')))
        elif op in {'make_circle_redge', 'make_angle_arc_redge'}:
            add_length(params.get('radius'))
        elif op == 'make_three_point_arc_redge':
            points = [params.get('start'), params.get('middle'), params.get('end')]
            for first, second in zip(points, points[1:]):
                add_length(_distance(first, second))
        elif op in {'make_spline_redge', 'make_interpolated_spline_redge'}:
            points = params.get('control_points') or params.get('controls') or params.get('points') or []
            for first, second in zip(points, points[1:]):
                add_length(_distance(first, second))
        elif op == 'make_helix_redge':
            for key in ('radius', 'pitch', 'height'):
                add_length(params.get(key))
        elif op in {
            'make_extrude_rsolid', 'make_fillet_rsolid', 'make_chamfer_rsolid',
            'make_shell_rsolid', 'make_box_rsolid', 'make_cylinder_rsolid',
            'make_cone_rsolid', 'make_sphere_rsolid',
        }:
            for key in (
                'distance', 'radius', 'radius1', 'radius2', 'thickness',
                'length', 'width', 'height',
            ):
                add_length(params.get(key))

    minimum = min(lengths, default=5.0)
    # SolidWorks rejects sketch entities below roughly one millimetre. Build at
    # a stable working size, then restore the canonical model size before export.
    scale = min(1000000.0, max(1.0, 5.0 / minimum))
    # Scaling a tiny profile far from the origin can make its reference plane
    # uncreatable. Bound coordinate amplification using the recorded points;
    # this requires no source-body construction or output-shape measurement.
    maximum_coordinate = 0.0
    for node in ((payload.get('graph') or {}).get('nodes') or []):
        params = node.get('params') or {}
        points = []
        for key in ('start', 'middle', 'end', 'center', 'origin'):
            point = params.get(key)
            if isinstance(point, (list, tuple)) and len(point) == 3:
                points.append(point)
        for key in ('points', 'control_points', 'controls'):
            points.extend(params.get(key) or [])
        for point in points:
            if isinstance(point, (list, tuple)) and len(point) == 3:
                maximum_coordinate = max(maximum_coordinate, *(abs(float(v)) for v in point))
    if maximum_coordinate:
        scale = min(scale, max(1.0, 200000.0 / maximum_coordinate))
    return scale


def _as_m(value):
    return float(value) * MODEL_SCALE * MM_TO_M


def _pt_m(value):
    x, y, z = _v3(value)
    return (
        x * MODEL_SCALE * MM_TO_M,
        y * MODEL_SCALE * MM_TO_M,
        z * MODEL_SCALE * MM_TO_M,
    )


def _identity_matrix():
    return [
        1.0, 0.0, 0.0,
        0.0, 1.0, 0.0,
        0.0, 0.0, 1.0,
        0.0, 0.0, 0.0,
        1.0,
        0.0, 0.0, 0.0,
    ]


def _translation_matrix(vector_mm):
    tx, ty, tz = _pt_m(vector_mm)
    data = _identity_matrix()
    data[9] = tx
    data[10] = ty
    data[11] = tz
    return data


def _solidworks_rotation_angle_index(principal_index):
    principal_index = int(principal_index)
    if principal_index not in (0, 1, 2):
        raise ValueError(
            f'Invalid principal rotation axis index: {principal_index}'
        )
    return 2 - principal_index


def _scale_about_bbox_matrix(bbox, factor):
    center = _bbox_center(bbox)
    cx, cy, cz = _pt_m(center)
    factor = float(factor)
    data = _identity_matrix()
    data[9] = (1.0 - factor) * cx
    data[10] = (1.0 - factor) * cy
    data[11] = (1.0 - factor) * cz
    data[12] = factor
    return data


def _rotation_matrix(axis, angle_degrees, origin):
    ax, ay, az = _unit(axis)
    angle = math.radians(float(angle_degrees))
    c = math.cos(angle)
    s = math.sin(angle)
    t = 1.0 - c
    r00 = t * ax * ax + c
    r01 = t * ax * ay - s * az
    r02 = t * ax * az + s * ay
    r10 = t * ax * ay + s * az
    r11 = t * ay * ay + c
    r12 = t * ay * az - s * ax
    r20 = t * ax * az - s * ay
    r21 = t * ay * az + s * ax
    r22 = t * az * az + c
    ox, oy, oz = _pt_m(origin)
    tx = ox - (r00 * ox + r01 * oy + r02 * oz)
    ty = oy - (r10 * ox + r11 * oy + r12 * oz)
    tz = oz - (r20 * ox + r21 * oy + r22 * oz)
    # IMathTransform stores the rotation basis for row-vector multiplication.
    # Transpose the conventional column-vector Rodrigues matrix while keeping
    # the world-space pivot translation unchanged.
    return [r00, r10, r20, r01, r11, r21, r02, r12, r22, tx, ty, tz, 1.0, 0.0, 0.0, 0.0]


def _mirror_matrix(plane_origin, plane_normal):
    nx, ny, nz = _unit(plane_normal)
    px, py, pz = _pt_m(plane_origin)
    d = -(nx * px + ny * py + nz * pz)
    r00 = 1.0 - 2.0 * nx * nx
    r01 = -2.0 * nx * ny
    r02 = -2.0 * nx * nz
    r10 = -2.0 * ny * nx
    r11 = 1.0 - 2.0 * ny * ny
    r12 = -2.0 * ny * nz
    r20 = -2.0 * nz * nx
    r21 = -2.0 * nz * ny
    r22 = 1.0 - 2.0 * nz * nz
    tx = -2.0 * d * nx
    ty = -2.0 * d * ny
    tz = -2.0 * d * nz
    return [r00, r01, r02, r10, r11, r12, r20, r21, r22, tx, ty, tz, 1.0, 0.0, 0.0, 0.0]


def _placement_matrix(placement):
    if isinstance(placement, dict) and placement.get('kind') == 'placement':
        placement = placement.get('params') or {}
    if not isinstance(placement, dict):
        placement = {}
    origin = _v3(placement.get('origin') or (0.0, 0.0, 0.0))
    x_axis = _unit(placement.get('x_axis') or (1.0, 0.0, 0.0))
    y_axis = _unit(placement.get('y_axis') or (0.0, 1.0, 0.0))
    z_axis = _unit(placement.get('z_axis') or _cross(x_axis, y_axis))
    tx, ty, tz = _pt_m(origin)
    # SimpleCAD axes are columns of the local-to-world transform. SolidWorks
    # multiplies row vectors, so write the transposed basis just as in
    # _rotation_matrix.
    return [
        x_axis[0], x_axis[1], x_axis[2],
        y_axis[0], y_axis[1], y_axis[2],
        z_axis[0], z_axis[1], z_axis[2],
        tx, ty, tz,
        1.0,
        0.0, 0.0, 0.0,
    ]


def _multiply_transform_matrices(first, second):
    """Compose two SolidWorks row-vector affine transforms."""
    if len(first) < 13 or len(second) < 13:
        raise ValueError('SolidWorks transforms require at least 13 values')
    first_scale = float(first[12])
    second_scale = float(second[12])
    first_rotation = [float(value) for value in first[:9]]
    second_rotation = [float(value) for value in second[:9]]
    rotation = [
        sum(
            first_rotation[row * 3 + inner]
            * second_rotation[inner * 3 + column]
            for inner in range(3)
        )
        for row in range(3)
        for column in range(3)
    ]
    first_translation = [float(value) for value in first[9:12]]
    second_translation = [float(value) for value in second[9:12]]
    translation = [
        sum(
            first_translation[inner]
            * second_rotation[inner * 3 + column]
            * second_scale
            for inner in range(3)
        )
        + second_translation[column]
        for column in range(3)
    ]
    return rotation + translation + [
        first_scale * second_scale, 0.0, 0.0, 0.0
    ]


def _assembly_component_matrix(placements):
    matrix = _identity_matrix()
    # Product traversal records placements outermost first. Body transforms are
    # applied innermost first, so preserve that same order for Component2.
    for placement in reversed(tuple(placements or ())):
        matrix = _multiply_transform_matrices(
            matrix, _placement_matrix(placement)
        )
    if MODEL_SCALE > 0.0:
        for index in (9, 10, 11):
            matrix[index] = float(matrix[index]) / MODEL_SCALE
    return matrix


def _transform_matrices_close(first, second):
    if len(first) < 13 or len(second) < 13:
        return False
    scale = max(
        1.0,
        *(abs(float(value)) for value in first[:13]),
        *(abs(float(value)) for value in second[:13]),
    )
    tolerance = scale * 1.0e-8
    return all(
        abs(float(first[index]) - float(second[index])) <= tolerance
        for index in range(13)
    )


def _is_identity_matrix(matrix_data, tolerance=1.0e-10):
    identity = _identity_matrix()
    return len(matrix_data) == len(identity) and all(
        abs(float(actual) - float(expected)) <= tolerance
        for actual, expected in zip(matrix_data, identity)
    )


def _is_translation_matrix(matrix_data, tolerance=1.0e-12):
    identity = _identity_matrix()
    return (
        len(matrix_data) >= 16
        and all(
            abs(float(matrix_data[index]) - float(identity[index]))
            <= tolerance
            for index in range(9)
        )
        and abs(float(matrix_data[12]) - 1.0) <= tolerance
        and all(
            abs(float(matrix_data[index])) <= tolerance
            for index in (13, 14, 15)
        )
    )


def _bbox_from_box(box):
    if not box or len(box) < 6:
        return None
    return {
        'min': tuple(float(box[i]) * M_TO_MM / MODEL_SCALE for i in range(3)),
        'max': tuple(float(box[i]) * M_TO_MM / MODEL_SCALE for i in range(3, 6)),
    }


def _bbox_center(bbox):
    return tuple((float(bbox['min'][i]) + float(bbox['max'][i])) * 0.5 for i in range(3))


def _bbox_score(candidate_bbox, selector_bbox):
    if not isinstance(candidate_bbox, dict) or not isinstance(selector_bbox, dict):
        return 0.0
    expected_min = selector_bbox.get('min')
    expected_max = selector_bbox.get('max')
    actual_min = candidate_bbox.get('min')
    actual_max = candidate_bbox.get('max')
    if not all(isinstance(value, (list, tuple)) and len(value) == 3 for value in (
        expected_min, expected_max, actual_min, actual_max,
    )):
        return 1.0e6
    return _distance(actual_min, expected_min) + _distance(actual_max, expected_max)


def _bbox_intersects(first, second, tolerance=1.0e-7):
    if not isinstance(first, dict) or not isinstance(second, dict):
        return False
    first_min = first.get('min')
    first_max = first.get('max')
    second_min = second.get('min')
    second_max = second.get('max')
    if not all(
        isinstance(value, (list, tuple)) and len(value) == 3
        for value in (first_min, first_max, second_min, second_max)
    ):
        return False
    return all(
        float(first_max[index]) + tolerance >= float(second_min[index])
        and float(second_max[index]) + tolerance >= float(first_min[index])
        for index in range(3)
    )


def _bbox_axis_gaps(first, second):
    if not isinstance(first, dict) or not isinstance(second, dict):
        return (float('inf'), float('inf'), float('inf'))
    first_min = first.get('min')
    first_max = first.get('max')
    second_min = second.get('min')
    second_max = second.get('max')
    if not all(
        isinstance(value, (list, tuple)) and len(value) == 3
        for value in (first_min, first_max, second_min, second_max)
    ):
        return (float('inf'), float('inf'), float('inf'))
    return tuple(
        max(
            0.0,
            float(second_min[index]) - float(first_max[index]),
            float(first_min[index]) - float(second_max[index]),
        )
        for index in range(3)
    )


def _flatten(values):
    for value in values:
        if isinstance(value, (list, tuple)):
            yield from _flatten(value)
        else:
            yield value
