def _make_metadata_note(name, title, payload):
    obj = doc.addObject("App::FeaturePython", name)
    _ensure_string_property(obj, "Title")
    _ensure_string_property(obj, "Payload")
    obj.Title = title
    obj.Payload = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    _set_visibility(obj, False)
    _set_tree_visibility(obj, False)
    return obj


def _register_ir_node(
    name,
    *,
    node_id,
    op,
    params,
    inputs,
    tags,
    context,
    output_count,
    param_exprs=None,
    semantic_delta=None,
    topo_delta=None,
):
    return _register_graph_metadata_only(
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


def _placement_from_frame(origin, x_axis, y_axis, z_axis):
    m = App.Matrix()
    m.A11, m.A21, m.A31 = x_axis.x, x_axis.y, x_axis.z
    m.A12, m.A22, m.A32 = y_axis.x, y_axis.y, y_axis.z
    m.A13, m.A23, m.A33 = z_axis.x, z_axis.y, z_axis.z
    return App.Placement(origin, App.Rotation(m))


def _sketch_plane_frame(plane):
    if isinstance(plane, str):
        token = plane.upper()
        if token == "XY":
            origin = App.Vector(0.0, 0.0, 0.0)
            x_axis = App.Vector(1.0, 0.0, 0.0)
            y_axis = App.Vector(0.0, 1.0, 0.0)
            z_axis = App.Vector(0.0, 0.0, 1.0)
            return origin, x_axis, y_axis, z_axis
        if token == "XZ":
            origin = App.Vector(0.0, 0.0, 0.0)
            x_axis = App.Vector(1.0, 0.0, 0.0)
            y_axis = App.Vector(0.0, 0.0, 1.0)
            z_axis = App.Vector(0.0, -1.0, 0.0)
            return origin, x_axis, y_axis, z_axis
        if token == "YZ":
            origin = App.Vector(0.0, 0.0, 0.0)
            x_axis = App.Vector(0.0, 1.0, 0.0)
            y_axis = App.Vector(0.0, 0.0, 1.0)
            z_axis = App.Vector(1.0, 0.0, 0.0)
            return origin, x_axis, y_axis, z_axis
    if isinstance(plane, dict):
        origin = _vec(plane.get("origin", (0.0, 0.0, 0.0)))
        x_axis = _normalized_vec(plane.get("x_axis", (1.0, 0.0, 0.0)))
        y_axis = _normalized_vec(plane.get("y_axis", (0.0, 1.0, 0.0)))
        z_axis = x_axis.cross(y_axis)
        z_len = float(getattr(z_axis, "Length", 0.0))
        if z_len == 0.0:
            raise RuntimeError("Sketch plane x_axis and y_axis must not be parallel")
        z_axis = App.Vector(z_axis.x / z_len, z_axis.y / z_len, z_axis.z / z_len)
        y_axis = z_axis.cross(x_axis)
        y_len = float(getattr(y_axis, "Length", 0.0))
        y_axis = App.Vector(y_axis.x / y_len, y_axis.y / y_len, y_axis.z / y_len)
        return origin, x_axis, y_axis, z_axis
    raise RuntimeError(f"Unsupported sketch plane payload: {plane!r}")


def _sketch_entity_maps(sketch_payload):
    entities = (
        list(sketch_payload.get("entities") or [])
        if isinstance(sketch_payload, dict)
        else []
    )
    return entities, {
        str(entity.get("id")): entity
        for entity in entities
        if isinstance(entity, dict) and entity.get("id") is not None
    }


def _sketch_solved_point(point_id, sketch_payload, solve_snapshot):
    solved = (
        (solve_snapshot or {}).get("solved_points", {})
        if isinstance(solve_snapshot, dict)
        else {}
    )
    if point_id in solved:
        point = solved[point_id]
        return (float(point[0]), float(point[1]))
    _entities, by_id = _sketch_entity_maps(sketch_payload)
    entity = by_id.get(str(point_id))
    if isinstance(entity, dict) and entity.get("kind") == "point":
        return (float(entity.get("x", 0.0)), float(entity.get("y", 0.0)))
    raise RuntimeError(f"Missing solved sketch point {point_id!r}")


def _sketch_solved_radius(entity_id, entity, solve_snapshot):
    key = f"circle:{entity_id}:radius"
    scalars = (
        (solve_snapshot or {}).get("solved_scalars", {})
        if isinstance(solve_snapshot, dict)
        else {}
    )
    if key in scalars:
        return float(scalars[key])
    return float(entity.get("radius", 0.0))


def _sketch_profile_entity_ids(params, sketch_payload):
    promotion_map = params.get("promotion_map") if isinstance(params, dict) else None
    if isinstance(promotion_map, dict):
        loops = promotion_map.get("loops") or []
        loop_ids = [
            str(edge.get("entity_id"))
            for loop in loops
            if isinstance(loop, dict)
            for edge in (loop.get("edges") or [])
            if isinstance(edge, dict) and edge.get("entity_id") is not None
        ]
        if loop_ids:
            return loop_ids
        edges = promotion_map.get("edges") or []
        ids = [
            str(edge.get("entity_id"))
            for edge in edges
            if isinstance(edge, dict) and edge.get("entity_id") is not None
        ]
        if ids:
            return ids
    entities, _by_id = _sketch_entity_maps(sketch_payload)
    return [
        str(entity.get("id"))
        for entity in entities
        if entity.get("kind") in {"line", "circle", "arc", "bspline"}
        and not bool(entity.get("construction", False))
    ]


def _sketch_world_point(
    point_id, sketch_payload, solve_snapshot, origin, x_axis, y_axis
):
    x, y = _sketch_solved_point(point_id, sketch_payload, solve_snapshot)
    return App.Vector(
        origin.x + x * x_axis.x + y * y_axis.x,
        origin.y + x * x_axis.y + y * y_axis.y,
        origin.z + x * x_axis.z + y * y_axis.z,
    )


def _sketch_xy_to_world(x, y, origin, x_axis, y_axis):
    # Convert raw 2-D sketch coordinates to a 3-D world App.Vector.
    return App.Vector(
        origin.x + x * x_axis.x + y * y_axis.x,
        origin.y + x * x_axis.y + y * y_axis.y,
        origin.z + x * x_axis.z + y * y_axis.z,
    )


def _sketch_control_point_xy(control, sketch_payload, solve_snapshot):
    if isinstance(control, dict):
        point_id = control.get("point_id", control.get("point"))
        if point_id is None:
            raise RuntimeError(
                "Sketch B-spline control-point mapping requires point_id"
            )
        return _sketch_solved_point(str(point_id), sketch_payload, solve_snapshot)
    return float(control[0]), float(control[1])


def _sketch_local_point(point_id, sketch_payload, solve_snapshot):
    x, y = _sketch_solved_point(point_id, sketch_payload, solve_snapshot)
    return App.Vector(x, y, 0.0)


def _sketch_wire_shape_from_promotion(params):
    sketch_payload = params.get("sketch") or {}
    solve_snapshot = params.get("solve_snapshot") or {}
    origin, x_axis, y_axis, z_axis = _sketch_plane_frame(
        sketch_payload.get("plane", "XY")
    )
    _entities, by_id = _sketch_entity_maps(sketch_payload)
    edge_shapes = []
    for entity_id in _sketch_profile_entity_ids(params, sketch_payload):
        entity = by_id.get(str(entity_id))
        if not isinstance(entity, dict):
            continue
        kind = str(entity.get("kind"))
        if kind == "line":
            start = _sketch_world_point(
                str(entity.get("start")),
                sketch_payload,
                solve_snapshot,
                origin,
                x_axis,
                y_axis,
            )
            end = _sketch_world_point(
                str(entity.get("end")),
                sketch_payload,
                solve_snapshot,
                origin,
                x_axis,
                y_axis,
            )
            edge_shapes.append(Part.LineSegment(start, end).toShape())
        elif kind == "circle":
            center = _sketch_world_point(
                str(entity.get("center")),
                sketch_payload,
                solve_snapshot,
                origin,
                x_axis,
                y_axis,
            )
            edge_shapes.append(
                Part.Circle(
                    center,
                    z_axis,
                    _sketch_solved_radius(str(entity_id), entity, solve_snapshot),
                ).toShape()
            )
        elif kind == "arc":
            start = _sketch_world_point(
                str(entity.get("start")),
                sketch_payload,
                solve_snapshot,
                origin,
                x_axis,
                y_axis,
            )
            end = _sketch_world_point(
                str(entity.get("end")),
                sketch_payload,
                solve_snapshot,
                origin,
                x_axis,
                y_axis,
            )
            import math as _math

            start_xy = _sketch_solved_point(
                str(entity.get("start")), sketch_payload, solve_snapshot
            )
            end_xy = _sketch_solved_point(
                str(entity.get("end")), sketch_payload, solve_snapshot
            )
            center_xy = _sketch_solved_point(
                str(entity.get("center")), sketch_payload, solve_snapshot
            )
            radius = _math.hypot(start_xy[0] - center_xy[0], start_xy[1] - center_xy[1])
            start_angle = _math.atan2(
                start_xy[1] - center_xy[1], start_xy[0] - center_xy[0]
            )
            end_angle = _math.atan2(end_xy[1] - center_xy[1], end_xy[0] - center_xy[0])
            sweep = (end_angle - start_angle) % (2.0 * _math.pi)
            middle_angle = start_angle + 0.5 * sweep
            middle = _sketch_xy_to_world(
                center_xy[0] + radius * _math.cos(middle_angle),
                center_xy[1] + radius * _math.sin(middle_angle),
                origin,
                x_axis,
                y_axis,
            )
            edge_shapes.append(Part.Arc(start, middle, end).toShape())
        elif kind == "bspline":
            cps_data = entity.get("control_points", [])
            degree = int(entity.get("degree", 3))
            knots = entity.get("knots")
            mults = entity.get("multiplicities")
            weights = entity.get("weights")
            periodic = bool(entity.get("periodic", False))
            cps = [
                _sketch_xy_to_world(
                    *_sketch_control_point_xy(p, sketch_payload, solve_snapshot),
                    origin,
                    x_axis,
                    y_axis,
                )
                for p in cps_data
            ]
            curve = Part.BSplineCurve()
            if weights:
                curve.buildFromPolesMultsKnots(
                    cps, mults, knots, periodic, degree, weights
                )
            else:
                curve.buildFromPolesMultsKnots(cps, mults, knots, periodic, degree)
            edge_shapes.append(curve.toShape())
    if not edge_shapes:
        raise RuntimeError("Sketch promotion has no profile geometry to materialize")
    return Part.Wire(edge_shapes)


def _sketch_entity_expr(param_exprs, entity_index, *path):
    expr_meta = _nested_expr_ref(
        param_exprs or {}, "sketch", "entities", int(entity_index)
    )
    if expr_meta is None:
        return None
    return _nested_expr_ref(expr_meta, *path)


def _sketch_constraint_value_expr(param_exprs, constraint_index):
    return _nested_expr_ref(
        param_exprs or {}, "sketch", "constraints", int(constraint_index), "value"
    )


def _sketch_constraint_status_append(status, source, mapped, **payload):
    entry = {
        "id": source.get("id") if isinstance(source, dict) else None,
        "kind": source.get("kind") if isinstance(source, dict) else None,
    }
    entry.update(payload)
    status["mapped" if mapped else "skipped"].append(entry)


def _sketch_constraint_priority(item):
    _index, constraint = item
    kind = str(constraint.get("kind")) if isinstance(constraint, dict) else ""
    priorities = {
        "coincident": 0,
        "connect": 0,
        "point_on": 1,
        "fix": 2,
        "horizontal": 3,
        "vertical": 3,
        "distance": 4,
        "distance_x": 4,
        "distance_y": 4,
        "length": 4,
        "radius": 4,
        "diameter": 4,
        "angle": 4,
        "parallel": 5,
        "perpendicular": 5,
        "collinear": 5,
        "tangent": 5,
        "concentric": 5,
        "equal_length": 5,
        "equal_radius": 5,
        "midpoint": 6,
        "symmetric": 6,
    }
    return priorities.get(kind, 9), int(_index)


def _validate_sketch_constraint(sketch_obj, idx):
    try:
        result = sketch_obj.solve()
    except Exception as exc:
        return False, f"FreeCAD Sketcher solver raised {exc!r}"
    try:
        result_int = int(result)
    except Exception:
        return True, ""
    if result_int < 0:
        return (
            False,
            f"FreeCAD Sketcher solver rejected constraint with result {result_int}",
        )
    return True, ""


def _remove_sketch_constraint(sketch_obj, idx):
    try:
        if hasattr(sketch_obj, "setExpression"):
            sketch_obj.setExpression(f"Constraints[{int(idx)}]", None)
    except Exception:
        pass
    try:
        sketch_obj.delConstraint(int(idx))
    except Exception:
        pass


def _safe_add_sketch_constraint(
    sketch_obj, status, source, freecad_kind, *args, expr_ref=None, synthetic=False
):
    if Sketcher is None:
        _sketch_constraint_status_append(
            status,
            source,
            False,
            freecad_kind=freecad_kind,
            reason="Sketcher module is unavailable",
            synthetic=bool(synthetic),
        )
        return None
    try:
        idx = sketch_obj.addConstraint(Sketcher.Constraint(freecad_kind, *args))
    except Exception as exc:
        _sketch_constraint_status_append(
            status,
            source,
            False,
            freecad_kind=freecad_kind,
            reason=str(exc),
            synthetic=bool(synthetic),
        )
        return None
    if expr_ref is not None:
        _bind_expression(sketch_obj, f"Constraints[{int(idx)}]", expr_ref)
    ok, reason = _validate_sketch_constraint(sketch_obj, idx)
    if not ok:
        _remove_sketch_constraint(sketch_obj, idx)
        _sketch_constraint_status_append(
            status,
            source,
            False,
            freecad_kind=freecad_kind,
            reason=reason,
            synthetic=bool(synthetic),
        )
        return None
    serializable_args = [
        int(arg) if isinstance(arg, int) and not isinstance(arg, bool) else arg
        for arg in args
    ]
    _sketch_constraint_status_append(
        status,
        source,
        True,
        freecad_kind=freecad_kind,
        index=int(idx),
        args=serializable_args,
        synthetic=bool(synthetic),
    )
    return int(idx)


def _target_point_id(target, by_id):
    if not isinstance(target, dict):
        return None
    entity_id = str(target.get("entity_id"))
    subentity = str(target.get("subentity", "geometry"))
    entity = by_id.get(entity_id)
    if not isinstance(entity, dict):
        return None
    kind = str(entity.get("kind"))
    if kind == "point":
        return entity_id
    if kind == "line" and subentity in {"start", "end"}:
        return str(entity.get(subentity))
    if kind in {"circle", "arc"} and subentity == "center":
        return str(entity.get("center"))
    if kind in {"arc", "bspline"} and subentity in {"start", "end"}:
        return str(entity.get(subentity))
    return None


def _target_point_ref(target, by_id, point_refs):
    point_id = _target_point_id(target, by_id)
    if point_id is None:
        return None
    refs = point_refs.get(point_id) or []
    return refs[0] if refs else None


def _target_entity_ref(target, by_id, geom_by_entity):
    if not isinstance(target, dict):
        return None
    entity_id = str(target.get("entity_id"))
    entity = by_id.get(entity_id)
    if not isinstance(entity, dict):
        return None
    geom_index = geom_by_entity.get(entity_id)
    if geom_index is None:
        return None
    return int(geom_index), str(entity.get("kind"))


def _fix_point_constraint(
    sketch_obj, status, source, point_ref, x_value, y_value, x_expr=None, y_expr=None
):
    if point_ref is None:
        _sketch_constraint_status_append(
            status,
            source,
            False,
            reason="Target point is not represented by safe Sketcher geometry",
        )
        return
    geom_index, pos = point_ref
    _safe_add_sketch_constraint(
        sketch_obj,
        status,
        source,
        "DistanceX",
        int(geom_index),
        int(pos),
        float(x_value),
        expr_ref=x_expr,
    )
    _safe_add_sketch_constraint(
        sketch_obj,
        status,
        source,
        "DistanceY",
        int(geom_index),
        int(pos),
        float(y_value),
        expr_ref=y_expr,
    )


def _materialize_sketch_constraints(
    sketch_obj, sketch_payload, params, param_exprs, geom_by_entity, point_refs
):
    status = {"mapped": [], "skipped": []}
    entities, by_id = _sketch_entity_maps(sketch_payload)
    entity_index_by_id = {
        str(entity.get("id")): idx for idx, entity in enumerate(entities)
    }
    solve_snapshot = params.get("solve_snapshot") or {}

    for point_id, refs in sorted(point_refs.items()):
        if len(refs) < 2:
            continue
        first_geom, first_pos = refs[0]
        for geom_index, pos in refs[1:]:
            _safe_add_sketch_constraint(
                sketch_obj,
                status,
                {"id": f"point_identity:{point_id}", "kind": "coincident"},
                "Coincident",
                int(first_geom),
                int(first_pos),
                int(geom_index),
                int(pos),
                synthetic=True,
            )

    constraints = (
        list(sketch_payload.get("constraints") or [])
        if isinstance(sketch_payload, dict)
        else []
    )
    for constraint_index, constraint in sorted(
        enumerate(constraints), key=_sketch_constraint_priority
    ):
        if not isinstance(constraint, dict):
            continue
        kind = str(constraint.get("kind"))
        targets = list(constraint.get("targets") or [])
        value = constraint.get("value")
        value_expr = _sketch_constraint_value_expr(param_exprs, constraint_index)

        if kind in {"coincident", "connect"} and len(targets) == 2:
            a = _target_point_ref(targets[0], by_id, point_refs)
            b = _target_point_ref(targets[1], by_id, point_refs)
            if a is None or b is None:
                _sketch_constraint_status_append(
                    status,
                    constraint,
                    False,
                    reason="Coincident target is not represented by safe Sketcher geometry",
                )
                continue
            _safe_add_sketch_constraint(
                sketch_obj,
                status,
                constraint,
                "Coincident",
                int(a[0]),
                int(a[1]),
                int(b[0]),
                int(b[1]),
            )
            continue

        if kind == "point_on" and len(targets) == 2:
            point_ref = _target_point_ref(targets[0], by_id, point_refs)
            entity_ref = _target_entity_ref(targets[1], by_id, geom_by_entity)
            if point_ref is None or entity_ref is None:
                _sketch_constraint_status_append(
                    status,
                    constraint,
                    False,
                    reason="Point-on target is not represented by safe Sketcher geometry",
                )
                continue
            _safe_add_sketch_constraint(
                sketch_obj,
                status,
                constraint,
                "PointOnObject",
                int(point_ref[0]),
                int(point_ref[1]),
                int(entity_ref[0]),
            )
            continue

        if kind in {"horizontal", "vertical"} and len(targets) == 1:
            entity_ref = _target_entity_ref(targets[0], by_id, geom_by_entity)
            if entity_ref is None or entity_ref[1] != "line":
                _sketch_constraint_status_append(
                    status,
                    constraint,
                    False,
                    reason=f"{kind} requires a materialized line",
                )
                continue
            _safe_add_sketch_constraint(
                sketch_obj,
                status,
                constraint,
                "Horizontal" if kind == "horizontal" else "Vertical",
                int(entity_ref[0]),
            )
            continue

        if (
            kind in {"parallel", "perpendicular", "equal_length", "angle"}
            and len(targets) == 2
        ):
            a = _target_entity_ref(targets[0], by_id, geom_by_entity)
            b = _target_entity_ref(targets[1], by_id, geom_by_entity)
            if a is None or b is None or a[1] != "line" or b[1] != "line":
                _sketch_constraint_status_append(
                    status,
                    constraint,
                    False,
                    reason=f"{kind} requires two materialized lines",
                )
                continue
            if kind == "parallel":
                _safe_add_sketch_constraint(
                    sketch_obj, status, constraint, "Parallel", int(a[0]), int(b[0])
                )
            elif kind == "perpendicular":
                _safe_add_sketch_constraint(
                    sketch_obj,
                    status,
                    constraint,
                    "Perpendicular",
                    int(a[0]),
                    int(b[0]),
                )
            elif kind == "equal_length":
                _safe_add_sketch_constraint(
                    sketch_obj, status, constraint, "Equal", int(a[0]), int(b[0])
                )
            else:
                _safe_add_sketch_constraint(
                    sketch_obj,
                    status,
                    constraint,
                    "Angle",
                    int(a[0]),
                    int(b[0]),
                    float(value),
                    expr_ref=value_expr,
                )
            continue

        if kind == "collinear" and len(targets) == 2:
            a = _target_entity_ref(targets[0], by_id, geom_by_entity)
            b_target = targets[1]
            b = _target_entity_ref(b_target, by_id, geom_by_entity)
            if a is None or b is None or a[1] != "line" or b[1] != "line":
                _sketch_constraint_status_append(
                    status,
                    constraint,
                    False,
                    reason="collinear requires two materialized lines",
                )
                continue
            _safe_add_sketch_constraint(
                sketch_obj, status, constraint, "Parallel", int(a[0]), int(b[0])
            )
            b_entity = by_id.get(str(b_target.get("entity_id")))
            if isinstance(b_entity, dict):
                for point_id in (str(b_entity.get("start")), str(b_entity.get("end"))):
                    refs = point_refs.get(point_id) or []
                    if refs:
                        _safe_add_sketch_constraint(
                            sketch_obj,
                            status,
                            constraint,
                            "PointOnObject",
                            int(refs[0][0]),
                            int(refs[0][1]),
                            int(a[0]),
                        )
            continue

        if kind in {"equal_radius", "concentric"} and len(targets) == 2:
            a = _target_entity_ref(targets[0], by_id, geom_by_entity)
            b = _target_entity_ref(targets[1], by_id, geom_by_entity)
            if (
                a is None
                or b is None
                or a[1] not in {"circle", "arc"}
                or b[1] not in {"circle", "arc"}
            ):
                _sketch_constraint_status_append(
                    status,
                    constraint,
                    False,
                    reason=f"{kind} requires two materialized circles or arcs",
                )
                continue
            if kind == "equal_radius":
                _safe_add_sketch_constraint(
                    sketch_obj, status, constraint, "Equal", int(a[0]), int(b[0])
                )
            else:
                _safe_add_sketch_constraint(
                    sketch_obj,
                    status,
                    constraint,
                    "Coincident",
                    int(a[0]),
                    3,
                    int(b[0]),
                    3,
                )
            continue

        if kind == "tangent" and len(targets) == 2:
            a = _target_entity_ref(targets[0], by_id, geom_by_entity)
            b = _target_entity_ref(targets[1], by_id, geom_by_entity)
            if (
                a is None
                or b is None
                or a[1] not in {"line", "circle", "arc"}
                or b[1] not in {"line", "circle", "arc"}
            ):
                _sketch_constraint_status_append(
                    status,
                    constraint,
                    False,
                    reason="tangent requires two materialized line/circle/arc entities",
                )
                continue
            _safe_add_sketch_constraint(
                sketch_obj, status, constraint, "Tangent", int(a[0]), int(b[0])
            )
            continue

        if kind in {"distance", "distance_x", "distance_y"} and len(targets) == 2:
            a = _target_point_ref(targets[0], by_id, point_refs)
            b = _target_point_ref(targets[1], by_id, point_refs)
            if a is None or b is None:
                _sketch_constraint_status_append(
                    status,
                    constraint,
                    False,
                    reason=f"{kind} target is not represented by safe Sketcher geometry",
                )
                continue
            fc_kind = {
                "distance": "Distance",
                "distance_x": "DistanceX",
                "distance_y": "DistanceY",
            }[kind]
            _safe_add_sketch_constraint(
                sketch_obj,
                status,
                constraint,
                fc_kind,
                int(a[0]),
                int(a[1]),
                int(b[0]),
                int(b[1]),
                float(value),
                expr_ref=value_expr,
            )
            continue

        if kind == "length" and len(targets) == 1:
            entity_ref = _target_entity_ref(targets[0], by_id, geom_by_entity)
            if entity_ref is None or entity_ref[1] != "line":
                _sketch_constraint_status_append(
                    status,
                    constraint,
                    False,
                    reason="length requires a materialized line",
                )
                continue
            _safe_add_sketch_constraint(
                sketch_obj,
                status,
                constraint,
                "Distance",
                int(entity_ref[0]),
                float(value),
                expr_ref=value_expr,
            )
            continue

        if kind in {"radius", "diameter"} and len(targets) == 1:
            entity_ref = _target_entity_ref(targets[0], by_id, geom_by_entity)
            if entity_ref is None or entity_ref[1] not in {"circle", "arc"}:
                _sketch_constraint_status_append(
                    status,
                    constraint,
                    False,
                    reason=f"{kind} requires a materialized circle or arc",
                )
                continue
            _safe_add_sketch_constraint(
                sketch_obj,
                status,
                constraint,
                "Radius" if kind == "radius" else "Diameter",
                int(entity_ref[0]),
                float(value),
                expr_ref=value_expr,
            )
            continue

        if kind == "fix" and len(targets) == 1:
            target = targets[0]
            entity_id = str(target.get("entity_id")) if isinstance(target, dict) else ""
            entity = by_id.get(entity_id)
            if not isinstance(entity, dict):
                _sketch_constraint_status_append(
                    status, constraint, False, reason="fix target entity is missing"
                )
                continue
            entity_kind = str(entity.get("kind"))
            if entity_kind == "point":
                point_id = entity_id
                x_value, y_value = _sketch_solved_point(
                    point_id, sketch_payload, solve_snapshot
                )
                expr_meta = _sketch_entity_expr(
                    param_exprs, entity_index_by_id[point_id]
                )
                _fix_point_constraint(
                    sketch_obj,
                    status,
                    constraint,
                    _target_point_ref(target, by_id, point_refs),
                    x_value,
                    y_value,
                    _nested_expr_ref(expr_meta, "x"),
                    _nested_expr_ref(expr_meta, "y"),
                )
            elif entity_kind == "line":
                for point_key in ("start", "end"):
                    point_id = str(entity.get(point_key))
                    x_value, y_value = _sketch_solved_point(
                        point_id, sketch_payload, solve_snapshot
                    )
                    point_entity_index = entity_index_by_id.get(point_id)
                    expr_meta = (
                        _sketch_entity_expr(param_exprs, point_entity_index)
                        if point_entity_index is not None
                        else None
                    )
                    refs = point_refs.get(point_id) or []
                    _fix_point_constraint(
                        sketch_obj,
                        status,
                        constraint,
                        refs[0] if refs else None,
                        x_value,
                        y_value,
                        _nested_expr_ref(expr_meta, "x"),
                        _nested_expr_ref(expr_meta, "y"),
                    )
            elif entity_kind == "circle":
                center_id = str(entity.get("center"))
                x_value, y_value = _sketch_solved_point(
                    center_id, sketch_payload, solve_snapshot
                )
                center_entity_index = entity_index_by_id.get(center_id)
                expr_meta = (
                    _sketch_entity_expr(param_exprs, center_entity_index)
                    if center_entity_index is not None
                    else None
                )
                refs = point_refs.get(center_id) or []
                _fix_point_constraint(
                    sketch_obj,
                    status,
                    constraint,
                    refs[0] if refs else None,
                    x_value,
                    y_value,
                    _nested_expr_ref(expr_meta, "x"),
                    _nested_expr_ref(expr_meta, "y"),
                )
                entity_ref = _target_entity_ref(target, by_id, geom_by_entity)
                if entity_ref is not None:
                    circle_index = entity_index_by_id.get(entity_id)
                    radius_expr = _nested_expr_ref(
                        (
                            _sketch_entity_expr(param_exprs, circle_index)
                            if circle_index is not None
                            else None
                        ),
                        "radius",
                    )
                    _safe_add_sketch_constraint(
                        sketch_obj,
                        status,
                        constraint,
                        "Radius",
                        int(entity_ref[0]),
                        _sketch_solved_radius(entity_id, entity, solve_snapshot),
                        expr_ref=radius_expr,
                    )
            elif entity_kind == "arc":
                for point_key in ("start", "end", "center"):
                    point_id = str(entity.get(point_key))
                    x_value, y_value = _sketch_solved_point(
                        point_id, sketch_payload, solve_snapshot
                    )
                    point_entity_index = entity_index_by_id.get(point_id)
                    expr_meta = (
                        _sketch_entity_expr(param_exprs, point_entity_index)
                        if point_entity_index is not None
                        else None
                    )
                    refs = point_refs.get(point_id) or []
                    _fix_point_constraint(
                        sketch_obj,
                        status,
                        constraint,
                        refs[0] if refs else None,
                        x_value,
                        y_value,
                        _nested_expr_ref(expr_meta, "x"),
                        _nested_expr_ref(expr_meta, "y"),
                    )
            else:
                _sketch_constraint_status_append(
                    status,
                    constraint,
                    False,
                    reason=f"Cannot fix unsupported sketch entity kind {entity_kind!r}",
                )
            continue

        if kind in {"midpoint", "symmetric"}:
            _sketch_constraint_status_append(
                status,
                constraint,
                False,
                reason=f"{kind} has no crash-safe FreeCAD Sketcher mapping in this translator",
            )
            continue

        _sketch_constraint_status_append(
            status,
            constraint,
            False,
            reason=f"Unsupported sketch constraint kind {kind!r}",
        )
    return status


def _attach_sketch_promotion_metadata(obj, params, constraint_status):
    _ensure_string_property(obj, "SimpleCADSketch")
    _ensure_string_property(obj, "SimpleCADSketchSolve")
    _ensure_string_property(obj, "SimpleCADSketchPromotion")
    _ensure_string_property(obj, "SimpleCADSketchConstraints")
    obj.SimpleCADSketch = json.dumps(
        params.get("sketch") or {}, ensure_ascii=True, sort_keys=True
    )
    obj.SimpleCADSketchSolve = json.dumps(
        params.get("solve_snapshot") or {}, ensure_ascii=True, sort_keys=True
    )
    obj.SimpleCADSketchPromotion = json.dumps(
        params.get("promotion_map") or {}, ensure_ascii=True, sort_keys=True
    )
    obj.SimpleCADSketchConstraints = json.dumps(
        constraint_status or {}, ensure_ascii=True, sort_keys=True
    )


def _make_sketch_promotion_object(
    name,
    *,
    node_id,
    op,
    params,
    inputs,
    tags,
    context,
    output_count,
    param_exprs=None,
    semantic_delta=None,
    topo_delta=None,
):
    sketch_payload = params.get("sketch") or {}
    solve_snapshot = params.get("solve_snapshot") or {}
    if Sketcher is None:
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = _sketch_wire_shape_from_promotion(params)
        constraint_status = {
            "mapped": [],
            "skipped": [{"reason": "Sketcher module is unavailable"}],
        }
        _attach_sketch_promotion_metadata(obj, params, constraint_status)
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

    obj = doc.addObject("Sketcher::SketchObject", name)
    origin, x_axis, y_axis, z_axis = _sketch_plane_frame(
        sketch_payload.get("plane", "XY")
    )
    obj.Placement = _placement_from_frame(origin, x_axis, y_axis, z_axis)
    profile_ids = set(_sketch_profile_entity_ids(params, sketch_payload))
    entities, _by_id = _sketch_entity_maps(sketch_payload)
    geom_by_entity = {}
    point_refs = {}

    for entity in entities:
        entity_id = str(entity.get("id"))
        kind = str(entity.get("kind"))
        construction = bool(entity.get("construction", False)) or (
            kind in {"line", "circle", "arc", "bspline"}
            and entity_id not in profile_ids
        )
        if kind == "line":
            start_id = str(entity.get("start"))
            end_id = str(entity.get("end"))
            start = _sketch_local_point(start_id, sketch_payload, solve_snapshot)
            end = _sketch_local_point(end_id, sketch_payload, solve_snapshot)
            geom_index = int(
                obj.addGeometry(Part.LineSegment(start, end), construction)
            )
            geom_by_entity[entity_id] = geom_index
            point_refs.setdefault(start_id, []).append((geom_index, 1))
            point_refs.setdefault(end_id, []).append((geom_index, 2))
        elif kind == "circle":
            center_id = str(entity.get("center"))
            center = _sketch_local_point(center_id, sketch_payload, solve_snapshot)
            radius = _sketch_solved_radius(entity_id, entity, solve_snapshot)
            geom_index = int(
                obj.addGeometry(
                    Part.Circle(center, App.Vector(0.0, 0.0, 1.0), radius), construction
                )
            )
            geom_by_entity[entity_id] = geom_index
            point_refs.setdefault(center_id, []).append((geom_index, 3))
        elif kind == "arc":
            start_id = str(entity.get("start"))
            end_id = str(entity.get("end"))
            center_id = str(entity.get("center"))
            start = _sketch_local_point(start_id, sketch_payload, solve_snapshot)
            end = _sketch_local_point(end_id, sketch_payload, solve_snapshot)
            center = _sketch_local_point(center_id, sketch_payload, solve_snapshot)
            import math as _math

            radius = _math.hypot(start.x - center.x, start.y - center.y)
            arc = Part.ArcOfCircle(
                Part.Circle(center, App.Vector(0.0, 0.0, 1.0), radius),
                _math.atan2(start.y - center.y, start.x - center.x),
                _math.atan2(end.y - center.y, end.x - center.x),
            )
            geom_index = int(obj.addGeometry(arc, construction))
            geom_by_entity[entity_id] = geom_index
            point_refs.setdefault(start_id, []).append((geom_index, 1))
            point_refs.setdefault(end_id, []).append((geom_index, 2))
            point_refs.setdefault(center_id, []).append((geom_index, 3))
        elif kind == "bspline":
            cps_data = entity.get("control_points", [])
            degree = int(entity.get("degree", 3))
            knots = entity.get("knots")
            mults = entity.get("multiplicities")
            weights = entity.get("weights")
            periodic = bool(entity.get("periodic", False))
            cps = [
                App.Vector(
                    *_sketch_control_point_xy(p, sketch_payload, solve_snapshot), 0.0
                )
                for p in cps_data
            ]
            curve = Part.BSplineCurve()
            if weights:
                curve.buildFromPolesMultsKnots(
                    cps, mults, knots, periodic, degree, weights
                )
            else:
                curve.buildFromPolesMultsKnots(cps, mults, knots, periodic, degree)
            geom_index = int(obj.addGeometry(curve, construction))
            geom_by_entity[entity_id] = geom_index
            start_id = str(entity.get("start"))
            end_id = str(entity.get("end"))
            point_refs.setdefault(start_id, []).append((geom_index, 1))
            point_refs.setdefault(end_id, []).append((geom_index, 2))

    if not geom_by_entity:
        raise RuntimeError(
            "Sketch promotion contains no materialized line or circle geometry"
        )
    constraint_status = _materialize_sketch_constraints(
        obj, sketch_payload, params, param_exprs or {}, geom_by_entity, point_refs
    )
    try:
        obj.solve()
    except Exception:
        pass
    try:
        doc.recompute()
    except Exception:
        pass
    _attach_sketch_promotion_metadata(obj, params, constraint_status)
    _attach_simplecad_metadata(
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
    SKETCH_REGISTRY.append(
        {
            "node_id": node_id,
            "op": op,
            "object": obj.Name,
            "constraint_status": constraint_status,
        }
    )
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
    return registered
