def _sanitize_expr_alias(expr_id, prefix='expr'):
    alias = ''.join(ch if str(ch).isalnum() else '_' for ch in str(expr_id)).strip('_')
    if not alias:
        alias = prefix
    if alias[0].isdigit():
        alias = prefix + '_' + alias
    return alias[:64]


def _expr_alias(expr_id):
    alias = EXPR_ALIAS_BY_ID.get(expr_id)
    if alias:
        return alias
    return _sanitize_expr_alias(expr_id)


def _resolve_expr_ref(expr_ref):
    if not isinstance(expr_ref, dict):
        return None
    expr_id = expr_ref.get('expr_id')
    if not expr_id or 'expr_sheet' not in globals() or expr_sheet is None:
        return None
    alias = _expr_alias(expr_id)
    try:
        return float(expr_sheet.get(alias))
    except Exception:
        cell = EXPR_CELL_BY_ID.get(expr_id)
        if not cell:
            return None
        try:
            return float(expr_sheet.get(cell))
        except Exception:
            return None


def _expr_ref_to_freecad_expr(expr_ref):
    if not isinstance(expr_ref, dict):
        return None
    expr_id = expr_ref.get('expr_id')
    if not expr_id or 'expr_sheet' not in globals() or expr_sheet is None:
        return None
    if expr_id not in EXPR_CELL_BY_ID:
        return None
    return f"<<SimpleCADExpressions>>.{_expr_alias(expr_id)}"


def _nested_expr_ref(expr_meta, *path):
    value = expr_meta
    for key in path:
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and isinstance(key, int) and 0 <= key < len(value):
            value = value[key]
        else:
            return None
    return value


def _bind_expression(obj, prop_name, expr_ref):
    if isinstance(expr_ref, str):
        expr = expr_ref
    else:
        expr = _expr_ref_to_freecad_expr(expr_ref)
    if not expr or not hasattr(obj, 'setExpression'):
        return False
    try:
        obj.setExpression(prop_name, expr)
        return True
    except Exception:
        return False


def _bind_expression_from_param(obj, prop_name, param_exprs, *path):
    return _bind_expression(obj, prop_name, _nested_expr_ref(param_exprs, *path))


def _apply_op_expression_bindings(obj, op_name, param_exprs):
    for prop_name, path in OP_EXPRESSION_BINDINGS.get(str(op_name), ()):
        _bind_expression_from_param(obj, prop_name, param_exprs, *path)


def _apply_sketch_expression_bindings(obj, bindings):
    for prop_name, expr_ref in bindings or []:
        _bind_expression(obj, prop_name, expr_ref)


def _expr_formula_from_ref(expr_ref):
    expr = _expr_ref_to_freecad_expr(expr_ref)
    return expr if expr else None


def _formula_nested_value(params, param_exprs, *path):
    expr = _expr_formula_from_ref(_nested_expr_ref(param_exprs, *path))
    if expr is not None:
        return expr
    try:
        value = params
        for key in path:
            value = value[key]
        return repr(float(value))
    except Exception:
        return None


def _formula_scale(expr, coeff):
    coeff_value = float(coeff)
    if abs(coeff_value) <= 1e-12:
        return None
    if abs(coeff_value - 1.0) <= 1e-12:
        return expr
    if abs(coeff_value + 1.0) <= 1e-12:
        return f'-({expr})'
    return f'({expr}) * ({repr(coeff_value)})'


def _formula_mul(left, right):
    if left is None or right is None:
        return None
    return f'({left}) * ({right})'


def _formula_join_terms(*terms):
    filtered = [term for term in terms if term is not None]
    if not filtered:
        return None
    return ' + '.join(filtered)


def _formula_centered(expr, offset):
    offset_value = float(offset)
    if abs(offset_value) <= 1e-12:
        return expr
    return f'({expr}) - ({repr(offset_value)})'


def _formula_square(expr):
    return f'pow(({expr}); 2)'


def _formula_cos_radians(expr):
    return f'cos(({expr}) * 180 / pi)'


def _formula_sin_radians(expr):
    return f'sin(({expr}) * 180 / pi)'


def _local_point_component_formula(params, param_exprs, point_path, origin, axis_vec):
    path = tuple(point_path) if isinstance(point_path, (list, tuple)) else (point_path,)
    offsets = (float(origin.x), float(origin.y), float(origin.z))
    axis = (float(axis_vec.x), float(axis_vec.y), float(axis_vec.z))
    terms = []
    for idx, (offset, coeff) in enumerate(zip(offsets, axis)):
        value = _formula_nested_value(params, param_exprs, *(path + (idx,)))
        if value is None:
            return None
        term = _formula_scale(_formula_centered(value, offset), coeff)
        if term is not None:
            terms.append(term)
    if not terms:
        return '0.0'
    return ' + '.join(terms)


def _formula_value(params, param_exprs, key, index):
    return _formula_nested_value(params, param_exprs, key, index)


def _line_length_formula(params, param_exprs):
    sx = _formula_value(params, param_exprs, 'start', 0)
    sy = _formula_value(params, param_exprs, 'start', 1)
    sz = _formula_value(params, param_exprs, 'start', 2)
    ex = _formula_value(params, param_exprs, 'end', 0)
    ey = _formula_value(params, param_exprs, 'end', 1)
    ez = _formula_value(params, param_exprs, 'end', 2)
    terms = []
    for a, b in ((ex, sx), (ey, sy), (ez, sz)):
        if a is None or b is None:
            return None
        terms.append(f"pow(({a}) - ({b}); 2)")
    return f"sqrt({' + '.join(terms)})"


def _build_line_sketch_bindings(param_exprs, geom_index=0, use_local_line=False):
    bindings = []
    for point_name, point_index in (("start", 1), ("end", 2)):
        expr_ref = _nested_expr_ref(param_exprs, point_name)
        if not isinstance(expr_ref, list):
            continue
        for axis_name, axis_index in (("x", 0), ("y", 1), ("z", 2)):
            axis_expr = _nested_expr_ref(param_exprs, point_name, axis_index)
            if axis_expr is None:
                continue
            prop = f"Geometry[{int(geom_index)}].{'StartPoint' if point_name == 'start' else 'EndPoint'}.{axis_name}"
            if use_local_line and axis_name in {'x', 'y', 'z'}:
                continue
            bindings.append((prop, axis_expr))
    return bindings


def _build_circle_sketch_bindings(param_exprs, geom_index=0, local=False):
    bindings = []
    for axis_name, axis_index in (("x", 0), ("y", 1), ("z", 2)):
        axis_expr = _nested_expr_ref(param_exprs, 'center', axis_index)
        if axis_expr is None:
            continue
        if local and axis_name == 'z':
            continue
        bindings.append((f"Geometry[{int(geom_index)}].Center.{axis_name}", axis_expr))
    radius_expr = _nested_expr_ref(param_exprs, 'radius')
    if radius_expr is not None:
        bindings.append((f"Geometry[{int(geom_index)}].Radius", radius_expr))
    return bindings


def _build_local_point_sketch_bindings(params, param_exprs, point_path, prop_prefix, geom_index=0, origin=None, x_axis=None, y_axis=None):
    bindings = []
    if origin is None or x_axis is None or y_axis is None:
        return bindings
    x_expr = _local_point_component_formula(params, param_exprs, point_path, origin, x_axis)
    if x_expr is not None:
        bindings.append((f"Geometry[{int(geom_index)}].{prop_prefix}.x", x_expr))
    y_expr = _local_point_component_formula(params, param_exprs, point_path, origin, y_axis)
    if y_expr is not None:
        bindings.append((f"Geometry[{int(geom_index)}].{prop_prefix}.y", y_expr))
    return bindings


def _build_local_line_sketch_bindings(params, param_exprs, geom_index=0, origin=None, x_axis=None, y_axis=None):
    bindings = []
    bindings.extend(
        _build_local_point_sketch_bindings(
            params,
            param_exprs,
            'start',
            'StartPoint',
            geom_index=geom_index,
            origin=origin,
            x_axis=x_axis,
            y_axis=y_axis,
        )
    )
    bindings.extend(
        _build_local_point_sketch_bindings(
            params,
            param_exprs,
            'end',
            'EndPoint',
            geom_index=geom_index,
            origin=origin,
            x_axis=x_axis,
            y_axis=y_axis,
        )
    )
    return bindings


def _build_local_circle_sketch_bindings(params, param_exprs, geom_index=0, origin=None, x_axis=None, y_axis=None):
    bindings = []
    bindings.extend(
        _build_local_point_sketch_bindings(
            params,
            param_exprs,
            'center',
            'Center',
            geom_index=geom_index,
            origin=origin,
            x_axis=x_axis,
            y_axis=y_axis,
        )
    )
    radius_expr = _nested_expr_ref(param_exprs, 'radius')
    if radius_expr is not None:
        bindings.append((f"Geometry[{int(geom_index)}].Radius", radius_expr))
    return bindings


def _angle_arc_local_point_formula(params, param_exprs, angle_key, origin, sketch_axis):
    if origin is None or sketch_axis is None:
        return None
    center_component = _local_point_component_formula(params, param_exprs, 'center', origin, sketch_axis)
    radius_expr = _formula_nested_value(params, param_exprs, 'radius')
    angle_expr = _formula_nested_value(params, param_exprs, angle_key)
    if center_component is None or radius_expr is None or angle_expr is None:
        return None
    normal = params.get('normal', (0.0, 0.0, 1.0))
    try:
        arc_x, arc_y = _angle_arc_axes(normal)
    except Exception:
        return None
    cos_term = _formula_scale(
        _formula_mul(radius_expr, _formula_cos_radians(angle_expr)),
        float(arc_x.x * sketch_axis.x + arc_x.y * sketch_axis.y + arc_x.z * sketch_axis.z),
    )
    sin_term = _formula_scale(
        _formula_mul(radius_expr, _formula_sin_radians(angle_expr)),
        float(arc_y.x * sketch_axis.x + arc_y.y * sketch_axis.y + arc_y.z * sketch_axis.z),
    )
    return _formula_join_terms(center_component, cos_term, sin_term)


def _build_local_angle_arc_sketch_bindings(params, param_exprs, geom_index=0, origin=None, x_axis=None, y_axis=None):
    bindings = []
    bindings.extend(
        _build_local_circle_sketch_bindings(
            params,
            param_exprs,
            geom_index=geom_index,
            origin=origin,
            x_axis=x_axis,
            y_axis=y_axis,
        )
    )
    start_x = _angle_arc_local_point_formula(params, param_exprs, 'start_angle', origin, x_axis)
    start_y = _angle_arc_local_point_formula(params, param_exprs, 'start_angle', origin, y_axis)
    end_x = _angle_arc_local_point_formula(params, param_exprs, 'end_angle', origin, x_axis)
    end_y = _angle_arc_local_point_formula(params, param_exprs, 'end_angle', origin, y_axis)
    if start_x is not None:
        bindings.append((f"Geometry[{int(geom_index)}].StartPoint.x", start_x))
    if start_y is not None:
        bindings.append((f"Geometry[{int(geom_index)}].StartPoint.y", start_y))
    if end_x is not None:
        bindings.append((f"Geometry[{int(geom_index)}].EndPoint.x", end_x))
    if end_y is not None:
        bindings.append((f"Geometry[{int(geom_index)}].EndPoint.y", end_y))
    return bindings


def _three_point_arc_local_coordinate_formulas(params, param_exprs, origin, x_axis, y_axis):
    return {
        'sx': _local_point_component_formula(params, param_exprs, 'start', origin, x_axis),
        'sy': _local_point_component_formula(params, param_exprs, 'start', origin, y_axis),
        'mx': _local_point_component_formula(params, param_exprs, 'middle', origin, x_axis),
        'my': _local_point_component_formula(params, param_exprs, 'middle', origin, y_axis),
        'ex': _local_point_component_formula(params, param_exprs, 'end', origin, x_axis),
        'ey': _local_point_component_formula(params, param_exprs, 'end', origin, y_axis),
    }


def _three_point_arc_center_formula(params, param_exprs, origin, x_axis, y_axis, axis_name):
    coords = _three_point_arc_local_coordinate_formulas(params, param_exprs, origin, x_axis, y_axis)
    if any(value is None for value in coords.values()):
        return None
    sx = coords['sx']
    sy = coords['sy']
    mx = coords['mx']
    my = coords['my']
    ex = coords['ex']
    ey = coords['ey']
    denom = (
        f"2 * ((({sx}) * (({my}) - ({ey}))) + (({mx}) * (({ey}) - ({sy}))) + (({ex}) * (({sy}) - ({my}))))"
    )
    start_sq = f"({_formula_square(sx)} + {_formula_square(sy)})"
    mid_sq = f"({_formula_square(mx)} + {_formula_square(my)})"
    end_sq = f"({_formula_square(ex)} + {_formula_square(ey)})"
    if axis_name == 'x':
        numer = (
            f"(({start_sq}) * (({my}) - ({ey}))) + (({mid_sq}) * (({ey}) - ({sy}))) + (({end_sq}) * (({sy}) - ({my})))"
        )
    elif axis_name == 'y':
        numer = (
            f"(({start_sq}) * (({ex}) - ({mx}))) + (({mid_sq}) * (({sx}) - ({ex}))) + (({end_sq}) * (({mx}) - ({sx})))"
        )
    else:
        return None
    return f"(({numer})) / ({denom})"


def _three_point_arc_radius_formula(params, param_exprs, origin, x_axis, y_axis):
    coords = _three_point_arc_local_coordinate_formulas(params, param_exprs, origin, x_axis, y_axis)
    sx = coords.get('sx')
    sy = coords.get('sy')
    cx = _three_point_arc_center_formula(params, param_exprs, origin, x_axis, y_axis, 'x')
    cy = _three_point_arc_center_formula(params, param_exprs, origin, x_axis, y_axis, 'y')
    if sx is None or sy is None or cx is None or cy is None:
        return None
    return f"sqrt({_formula_square(f'({cx}) - ({sx})')} + {_formula_square(f'({cy}) - ({sy})')})"


def _build_local_three_point_arc_sketch_bindings(params, param_exprs, geom_index=0, origin=None, x_axis=None, y_axis=None):
    bindings = []
    bindings.extend(
        _build_local_point_sketch_bindings(
            params,
            param_exprs,
            'start',
            'StartPoint',
            geom_index=geom_index,
            origin=origin,
            x_axis=x_axis,
            y_axis=y_axis,
        )
    )
    bindings.extend(
        _build_local_point_sketch_bindings(
            params,
            param_exprs,
            'end',
            'EndPoint',
            geom_index=geom_index,
            origin=origin,
            x_axis=x_axis,
            y_axis=y_axis,
        )
    )
    if origin is None or x_axis is None or y_axis is None:
        return bindings
    center_x = _three_point_arc_center_formula(params, param_exprs, origin, x_axis, y_axis, 'x')
    center_y = _three_point_arc_center_formula(params, param_exprs, origin, x_axis, y_axis, 'y')
    radius = _three_point_arc_radius_formula(params, param_exprs, origin, x_axis, y_axis)
    if center_x is not None:
        bindings.append((f"Geometry[{int(geom_index)}].Center.x", center_x))
    if center_y is not None:
        bindings.append((f"Geometry[{int(geom_index)}].Center.y", center_y))
    if radius is not None:
        bindings.append((f"Geometry[{int(geom_index)}].Radius", radius))
    return bindings


def _build_arc_sketch_bindings(param_exprs, geom_index=0, *, prefer_local=False):
    bindings = []
    if prefer_local:
        for axis_name, axis_index in (("x", 0), ("y", 1)):
            start_expr = _nested_expr_ref(param_exprs, 'start', axis_index)
            if start_expr is not None:
                bindings.append((f"Geometry[{int(geom_index)}].StartPoint.{axis_name}", start_expr))
            end_expr = _nested_expr_ref(param_exprs, 'end', axis_index)
            if end_expr is not None:
                bindings.append((f"Geometry[{int(geom_index)}].EndPoint.{axis_name}", end_expr))
        return bindings
    bindings.extend(_build_circle_sketch_bindings(param_exprs, geom_index=geom_index, local=False))
    start_angle_expr = _nested_expr_ref(param_exprs, 'start_angle')
    if start_angle_expr is not None:
        bindings.append((f"Geometry[{int(geom_index)}].FirstParameter", start_angle_expr))
    end_angle_expr = _nested_expr_ref(param_exprs, 'end_angle')
    if end_angle_expr is not None:
        bindings.append((f"Geometry[{int(geom_index)}].LastParameter", end_angle_expr))
    return bindings


def _detail_edge_binding_expr(param_exprs, key):
    edge_indices = []
    radius_expr = None
    if key == 'radius':
        radius_expr = _nested_expr_ref(param_exprs, 'radius')
    elif key == 'distance':
        radius_expr = _nested_expr_ref(param_exprs, 'distance')
    if radius_expr is None:
        return None
    return radius_expr


def _apply_detail_feature_bindings(obj, param_exprs, key):
    expr_ref = _detail_edge_binding_expr(param_exprs, key)
    if expr_ref is None:
        return False
    selected = []
    if key == 'radius':
        selected = list(getattr(obj, 'Edges', []) or [])
    else:
        selected = list(getattr(obj, 'Edges', []) or [])
    applied = False
    for idx in range(len(selected)):
        applied = _bind_expression(obj, f'Edges[{idx}]', expr_ref) or applied
    return applied


def _resolve_param_value(params, param_exprs, key):
    if isinstance(param_exprs, dict) and key in param_exprs:
        value = _resolve_expr_ref(param_exprs[key])
        if value is not None:
            return value
    return params[key]


def _resolve_nested_param_value(params, param_exprs, *path):
    value = params
    expr_meta = param_exprs if isinstance(param_exprs, dict) else {}
    for key in path:
        value = value[key]
        if isinstance(expr_meta, dict) and key in expr_meta:
            expr_meta = expr_meta[key]
        elif isinstance(expr_meta, list) and isinstance(key, int) and 0 <= key < len(expr_meta):
            expr_meta = expr_meta[key]
        else:
            expr_meta = None
    expr_value = _resolve_expr_ref(expr_meta)
    if expr_value is not None:
        return expr_value
    return value


def _resolve_vec3_param(params, param_exprs, key):
    return (
        float(_resolve_nested_param_value(params, param_exprs, key, 0)),
        float(_resolve_nested_param_value(params, param_exprs, key, 1)),
        float(_resolve_nested_param_value(params, param_exprs, key, 2)),
    )