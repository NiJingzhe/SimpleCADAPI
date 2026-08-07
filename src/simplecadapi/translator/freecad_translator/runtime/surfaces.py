def _surface_context_point(value, context):
    point = _vec(value)
    if not isinstance(context, dict):
        return point
    origin = context.get("origin")
    x_axis = context.get("x_axis")
    y_axis = context.get("y_axis")
    z_axis = context.get("z_axis")
    if not all(
        isinstance(axis, (list, tuple)) and len(axis) == 3
        for axis in (origin, x_axis, y_axis, z_axis)
    ):
        return point
    return App.Vector(
        float(origin[0])
        + point.x * float(x_axis[0])
        + point.y * float(y_axis[0])
        + point.z * float(z_axis[0]),
        float(origin[1])
        + point.x * float(x_axis[1])
        + point.y * float(y_axis[1])
        + point.z * float(z_axis[1]),
        float(origin[2])
        + point.x * float(x_axis[2])
        + point.y * float(y_axis[2])
        + point.z * float(z_axis[2]),
    )


def _surface_point_grid(params, key, context):
    rows = list(params.get(key) or [])
    if len(rows) < 2 or any(len(row) < 2 for row in rows):
        raise RuntimeError(f"{key} must contain at least a 2x2 point grid")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise RuntimeError(f"{key} must be rectangular")
    return [[_surface_context_point(point, context) for point in row] for row in rows]


def _surface_single_face(shape, operation):
    if hasattr(shape, "Shape"):
        shape = shape.Shape
    if shape is None or shape.isNull():
        raise RuntimeError(f"{operation} produced a null shape")
    if getattr(shape, "ShapeType", "") == "Face":
        face = shape
    else:
        faces = list(getattr(shape, "Faces", []) or [])
        if len(faces) != 1:
            raise RuntimeError(
                f"{operation} expected exactly one face, got {len(faces)}"
            )
        face = faces[0]
    if not face.isValid():
        raise RuntimeError(f"{operation} produced an invalid face")
    return face


def _surface_single_shell(shape, operation):
    if hasattr(shape, "Shape"):
        shape = shape.Shape
    if shape is None or shape.isNull():
        raise RuntimeError(f"{operation} produced a null shape")
    if getattr(shape, "ShapeType", "") == "Shell":
        shell = shape
    elif getattr(shape, "ShapeType", "") == "Face":
        shell = Part.makeShell([shape])
    else:
        shells = list(getattr(shape, "Shells", []) or [])
        if len(shells) != 1:
            raise RuntimeError(
                f"{operation} expected exactly one shell, got {len(shells)}"
            )
        shell = shells[0]
    if not shell.isValid():
        raise RuntimeError(f"{operation} produced an invalid shell")
    return shell


def _surface_single_edge(shape, operation):
    if hasattr(shape, "Shape"):
        shape = shape.Shape
    if shape is None or shape.isNull():
        raise RuntimeError(f"{operation} received a null edge input")
    if getattr(shape, "ShapeType", "") == "Edge":
        return shape
    edges = list(getattr(shape, "Edges", []) or [])
    if len(edges) != 1:
        raise RuntimeError(f"{operation} expected exactly one edge, got {len(edges)}")
    return edges[0]


def _surface_single_wire_or_vertex(shape, operation):
    if hasattr(shape, "Shape"):
        shape = shape.Shape
    shape_type = getattr(shape, "ShapeType", "")
    if shape_type in {"Wire", "Vertex"}:
        return shape
    if shape_type == "Edge":
        return Part.Wire(shape)
    wires = list(getattr(shape, "Wires", []) or [])
    if len(wires) == 1:
        return wires[0]
    vertices = list(getattr(shape, "Vertexes", []) or [])
    if len(vertices) == 1:
        return vertices[0]
    raise RuntimeError(f"{operation} expected one wire or endpoint vertex")


def _surface_shape_for_ref(ref):
    node_id = str(ref.get("node_id", ""))
    slot = int(ref.get("output_slot", 0))
    outputs = list(GRAPH_OUTPUTS.get(node_id, []) or [])
    if outputs:
        if slot < 0 or slot >= len(outputs):
            raise RuntimeError(
                f"Input reference {node_id}:{slot} has no FreeCAD output"
            )
        return _shape_from_object_value(outputs[slot])
    if slot != 0:
        raise RuntimeError(f"Value input reference {node_id}:{slot} must use slot zero")
    return _shape_from_graph_node(node_id)


def _surface_input_shapes(params, inputs):
    refs = params.get("input_refs") if isinstance(params, dict) else None
    if isinstance(refs, list):
        return [_surface_shape_for_ref(ref) for ref in refs]
    return [_shape_from_graph_node(node_id) for node_id in inputs]


def _bezier_surface_shape(params, context):
    grid = _surface_point_grid(params, "control_points", context)
    surface = Part.BezierSurface()
    surface.increase(len(grid) - 1, len(grid[0]) - 1)
    weights = params.get("weights")
    for u_index, row in enumerate(grid, start=1):
        for v_index, point in enumerate(row, start=1):
            surface.setPole(u_index, v_index, point)
            if weights is not None:
                surface.setWeight(
                    u_index, v_index, float(weights[u_index - 1][v_index - 1])
                )
    return _surface_single_face(surface.toShape(), "make_bezier_surface_rface")


def _fit_point_grid_surface_shape(params, context):
    grid = _surface_point_grid(params, "points", context)
    surface = Part.BSplineSurface()
    tolerance = float(params.get("tolerance", 1.0e-3))
    degree_min = int(params.get("degree_min", 3))
    degree_max = int(params.get("degree_max", 8))
    smoothing = params.get("smoothing")
    try:
        kwargs = {
            "Points": grid,
            "DegMax": degree_max,
            "Continuity": 2,
            "Tolerance": tolerance,
        }
        if smoothing is None:
            kwargs["DegMin"] = degree_min
        else:
            kwargs["LengthWeight"] = float(smoothing[0])
            kwargs["CurvatureWeight"] = float(smoothing[1])
            kwargs["TorsionWeight"] = float(smoothing[2])
        surface.approximate(**kwargs)
    except Exception:
        surface = Part.BSplineSurface()
        surface.interpolate(grid)
    return _surface_single_face(surface.toShape(), "fit_point_grid_rface")


def _ruled_surface_shape(params, inputs):
    shapes = _surface_input_shapes(params, inputs)
    if len(shapes) != 2:
        raise RuntimeError("make_ruled_surface_rface requires two edge inputs")
    result = Part.makeRuledSurface(
        _surface_single_edge(shapes[0], "make_ruled_surface_rface"),
        _surface_single_edge(shapes[1], "make_ruled_surface_rface"),
    )
    return _surface_single_face(result, "make_ruled_surface_rface")


def _gordon_surface_shape(params, inputs):
    shapes = _surface_input_shapes(params, inputs)
    profile_count = int(params.get("profile_count", 0))
    guide_count = int(params.get("guide_count", 0))
    if (
        profile_count < 2
        or guide_count < 2
        or len(shapes) != profile_count + guide_count
    ):
        raise RuntimeError(
            "make_gordon_surface_rface received an invalid curve network"
        )
    profiles = [
        _surface_single_edge(shape, "make_gordon_surface_rface")
        for shape in shapes[:profile_count]
    ]
    guides = [
        _surface_single_edge(shape, "make_gordon_surface_rface")
        for shape in shapes[profile_count:]
    ]
    tolerance = float(params.get("tolerance", 1.0e-3))
    grid = []
    for profile in profiles:
        row = []
        for guide in guides:
            distance, point_pairs, _info = profile.distToShape(guide)
            if float(distance) > tolerance or len(point_pairs) != 1:
                raise RuntimeError(
                    "Gordon emulation requires one unambiguous intersection per profile-guide pair"
                )
            first, second = point_pairs[0]
            row.append(
                App.Vector(
                    0.5 * (first.x + second.x),
                    0.5 * (first.y + second.y),
                    0.5 * (first.z + second.z),
                )
            )
        grid.append(row)
    surface = Part.BSplineSurface()
    surface.interpolate(grid)
    return _surface_single_face(surface.toShape(), "make_gordon_surface_rface")


def _surface_patch_shape(params, inputs, context):
    shapes = _surface_input_shapes(params, inputs)
    boundaries = list(params.get("boundaries") or [])
    boundary_count = int(params.get("boundary_count", len(boundaries)))
    hole_count = int(params.get("hole_count", 0))
    if len(boundaries) != boundary_count:
        raise RuntimeError("make_surface_patch_rface boundary metadata is inconsistent")
    cursor = 0
    edges = []
    for boundary in boundaries:
        if cursor >= len(shapes):
            raise RuntimeError("make_surface_patch_rface is missing a boundary edge")
        edges.append(_surface_single_edge(shapes[cursor], "make_surface_patch_rface"))
        cursor += 1
        if bool(boundary.get("has_support", False)):
            if cursor >= len(shapes):
                raise RuntimeError("make_surface_patch_rface is missing a support face")
            cursor += 1
    hole_shapes = shapes[cursor : cursor + hole_count]
    boundary_wire = Part.Wire(edges)
    if not boundary_wire.isClosed() or not boundary_wire.isValid():
        raise RuntimeError(
            "make_surface_patch_rface boundary edges must form one valid closed wire"
        )
    face = _surface_single_face(
        Part.makeFilledFace(boundary_wire.Edges), "make_surface_patch_rface"
    )
    if hole_shapes:
        holes = [
            _surface_single_wire_or_vertex(shape, "make_surface_patch_rface")
            for shape in hole_shapes
        ]
        if any(getattr(hole, "ShapeType", "") != "Wire" for hole in holes):
            raise RuntimeError("make_surface_patch_rface holes must be wires")
        try:
            face = _surface_single_face(
                Part.Face(face.Surface, [face.OuterWire] + holes),
                "make_surface_patch_rface",
            )
        except Exception as error:
            raise RuntimeError(
                "FreeCAD could not trim the emulated surface patch with hole wires"
            ) from error
    return face


def _loft_shell_shape(params, inputs):
    shapes = _surface_input_shapes(params, inputs)
    sections = [
        _surface_single_wire_or_vertex(shape, "make_loft_rshell") for shape in shapes
    ]
    result = Part.makeLoft(
        sections,
        False,
        bool(params.get("ruled", False)),
        False,
        5,
    )
    return _surface_single_shell(result, "make_loft_rshell")


def _sew_face_shapes(faces, tolerance, operation):
    if not faces:
        raise RuntimeError(f"{operation} requires at least one face")
    if len(faces) == 1:
        return _surface_single_shell(Part.makeShell(faces), operation)
    result = Part.makeCompound(faces)
    result.sewShape(float(tolerance))
    return _surface_single_shell(result, operation)


def _sew_faces_shell_shape(params, inputs):
    shapes = _surface_input_shapes(params, inputs)
    faces = [_surface_single_face(shape, "sew_faces_rshell") for shape in shapes]
    return _sew_face_shapes(
        faces, float(params.get("tolerance", 1.0e-6)), "sew_faces_rshell"
    )


def _free_boundary_wires(shell, tolerance):
    shell = _surface_single_shell(shell, "free_boundaries_rwirelist")
    free_shape = shell.getFreeEdges()
    free_edges = list(getattr(free_shape, "Edges", []) or [])
    groups = Part.sortEdges(free_edges, float(tolerance)) if free_edges else []
    wires = [Part.Wire(group) for group in groups if group]
    if any(not wire.isValid() for wire in wires):
        raise RuntimeError("free_boundaries_rwirelist produced an invalid wire")
    return wires


def _free_boundary_shapes(params, inputs):
    shapes = _surface_input_shapes(params, inputs)
    if len(shapes) != 1:
        raise RuntimeError("free_boundaries_rwirelist requires one shell input")
    return _free_boundary_wires(shapes[0], float(params.get("tolerance", 1.0e-6)))


def _fill_holes_shell_shape(params, inputs):
    shapes = _surface_input_shapes(params, inputs)
    if len(shapes) != 1:
        raise RuntimeError("fill_holes_rshell requires one shell input")
    shell = _surface_single_shell(shapes[0], "fill_holes_rshell")
    tolerance = float(params.get("tolerance", 1.0e-6))
    boundaries = _free_boundary_wires(shell, tolerance)
    raw_indices = params.get("hole_indices")
    indices = (
        list(range(len(boundaries)))
        if raw_indices is None
        else [int(index) for index in raw_indices]
    )
    patches = []
    for index in indices:
        if index < 0 or index >= len(boundaries):
            raise RuntimeError(
                f"fill_holes_rshell boundary index {index} is out of range"
            )
        wire = boundaries[index]
        if not wire.isClosed():
            raise RuntimeError(f"fill_holes_rshell boundary {index} is open")
        patches.append(
            _surface_single_face(Part.makeFilledFace(wire.Edges), "fill_holes_rshell")
        )
    return _sew_face_shapes([*shell.Faces, *patches], tolerance, "fill_holes_rshell")


def _register_shape_list_features(
    name,
    shapes,
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
    shapes = list(shapes)
    if len(shapes) != int(output_count):
        raise RuntimeError(
            f"{op} produced {len(shapes)} FreeCAD outputs; canonical graph requires {int(output_count)}"
        )
    if not shapes:
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
    objects = []
    for index, shape in enumerate(shapes):
        obj = _make_feature(
            f"{name}_{index}",
            shape,
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
        _ensure_string_property(obj, "SimpleCADOutputSlot")
        obj.SimpleCADOutputSlot = str(index)
        obj.Label = f"{obj.Label} [{index}]"
        objects.append(obj)
    GRAPH_NODES[node_id] = objects[0]
    return objects[0]
