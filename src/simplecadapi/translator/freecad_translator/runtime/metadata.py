class SimpleCADUnsupportedOpError(RuntimeError):
    pass


def _ensure_string_property(obj, prop_name, group='SimpleCAD'):
    if prop_name not in list(getattr(obj, 'PropertiesList', []) or []):
        obj.addProperty('App::PropertyString', prop_name, group)


def _ensure_string_list_property(obj, prop_name, group='SimpleCAD'):
    if prop_name not in list(getattr(obj, 'PropertiesList', []) or []):
        obj.addProperty('App::PropertyStringList', prop_name, group)


def _ensure_string_map_property(obj, prop_name, group='SimpleCAD'):
    if prop_name not in list(getattr(obj, 'PropertiesList', []) or []):
        obj.addProperty('App::PropertyMap', prop_name, group)


def _ensure_float_property(obj, prop_name, group='SimpleCAD'):
    if prop_name not in list(getattr(obj, 'PropertiesList', []) or []):
        obj.addProperty('App::PropertyFloat', prop_name, group)


def _ensure_color_property(obj, prop_name, group='SimpleCAD'):
    if prop_name not in list(getattr(obj, 'PropertiesList', []) or []):
        obj.addProperty('App::PropertyColor', prop_name, group)


def _ensure_link_property(obj, prop_name, group='SimpleCAD'):
    if prop_name not in list(getattr(obj, 'PropertiesList', []) or []):
        obj.addProperty('App::PropertyLink', prop_name, group)


def _ensure_placement_property(obj, prop_name='Placement', group='SimpleCAD'):
    if prop_name not in list(getattr(obj, 'PropertiesList', []) or []):
        obj.addProperty('App::PropertyPlacement', prop_name, group)


def _contains_expr_refs(value):
    if isinstance(value, dict):
        if isinstance(value.get('expr_id'), str) and value['expr_id']:
            return True
        return any(_contains_expr_refs(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_expr_refs(v) for v in value)
    return False


def _expression_limitation_payload(op, param_exprs):
    if not _contains_expr_refs(param_exprs or {}):
        return None
    reason = OP_EXPRESSION_LIMITATIONS.get(str(op))
    if not reason:
        return None
    return {'op': str(op), 'reason': str(reason)}


def _record_graph_limitation(node_id, op, param_exprs):
    limitation = _expression_limitation_payload(op, param_exprs)
    if limitation:
        GRAPH_LIMITATIONS[str(node_id)] = limitation
    return limitation


def _simplecad_slug(value, prefix='obj'):
    token = ''.join(ch if str(ch).isalnum() else '_' for ch in str(value or ''))
    token = token.strip('_')
    if not token:
        token = str(prefix)
    if token[0].isdigit():
        token = str(prefix) + '_' + token
    return token[:120]


def _semantic_label_token(tags):
    normalized = sorted(str(tag) for tag in (tags or []))
    for prefix in ('role.', 'anchor.', 'group.'):
        for tag in normalized:
            if tag.startswith(prefix) and len(tag) > len(prefix):
                return tag[len(prefix):].replace('.', '_')
    for tag in normalized:
        if tag not in {'primitive', 'derived', 'solid', 'face', 'wire', 'edge', 'vertex'}:
            return tag.replace('.', '_')
    return ''


def _op_label_token(op):
    token = str(op or '')
    if token.startswith('make_'):
        token = token[len('make_'):]
    for suffix in ('_rsolid', '_rface', '_rwire', '_redge', '_rvertex', '_rassembly', '_rpart'):
        if token.endswith(suffix):
            token = token[:-len(suffix)]
            break
    return token or str(op or 'node')


def _simplecad_display_name(*, node_id, op, params, tags, semantic_delta):
    params = params or {}
    for key in ('name', 'component_id', 'part_id', 'assembly_id', 'constraint_id', 'connector_id', 'material_id'):
        value = params.get(key)
        if value:
            return f"{value} ({_op_label_token(op)})"
    tag_token = _semantic_label_token(tags)
    if tag_token:
        return f"{tag_token} ({_op_label_token(op)})"
    created = (semantic_delta or {}).get('created', []) if isinstance(semantic_delta, dict) else []
    if created:
        first = created[0]
        if isinstance(first, dict):
            entity_type = first.get('entity_type')
            entity_id = first.get('entity_id')
            if entity_type and entity_id:
                return f"{entity_type} {entity_id}"
    return f"{_op_label_token(op)} {node_id}"


def _attach_simplecad_metadata(obj, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    _ensure_string_property(obj, 'SimpleCADNodeId')
    _ensure_string_property(obj, 'SimpleCADOp')
    _ensure_string_property(obj, 'SimpleCADDisplayName')
    _ensure_string_property(obj, 'SimpleCADParams')
    _ensure_string_property(obj, 'SimpleCADInputs')
    _ensure_string_property(obj, 'SimpleCADContext')
    _ensure_string_property(obj, 'SimpleCADParamExprs')
    _ensure_string_property(obj, 'SimpleCADSemanticDelta')
    _ensure_string_property(obj, 'SimpleCADTopoDelta')
    _ensure_string_property(obj, 'SimpleCADOutputCount')
    _ensure_string_property(obj, 'SimpleCADExprSupport')
    _ensure_string_property(obj, 'SimpleCADExprLimitation')
    _ensure_string_list_property(obj, 'SimpleCADTags')
    obj.SimpleCADNodeId = str(node_id)
    obj.SimpleCADOp = str(op)
    display_name = _simplecad_display_name(node_id=node_id, op=op, params=params, tags=tags, semantic_delta=semantic_delta)
    obj.SimpleCADDisplayName = str(display_name)
    try:
        obj.Label = str(display_name)
    except Exception:
        pass
    obj.SimpleCADParams = json.dumps(params, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADInputs = json.dumps(inputs, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADContext = json.dumps(context or {}, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADParamExprs = json.dumps(param_exprs or {}, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADSemanticDelta = json.dumps(semantic_delta or {}, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADTopoDelta = json.dumps(topo_delta or {}, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADOutputCount = str(int(output_count))
    limitation = _expression_limitation_payload(op, param_exprs)
    obj.SimpleCADExprSupport = 'limited' if limitation else 'mapped_or_not_requested'
    obj.SimpleCADExprLimitation = limitation['reason'] if limitation else ''
    obj.SimpleCADTags = [str(tag) for tag in (tags or [])]


def _append_folded_op_metadata(obj, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    _ensure_string_property(obj, 'SimpleCADFoldedOps')
    try:
        folded = json.loads(obj.SimpleCADFoldedOps) if obj.SimpleCADFoldedOps else []
    except Exception:
        folded = []
    if not isinstance(folded, list):
        folded = []
    folded.append({
        'node_id': str(node_id),
        'op': str(op),
        'params': params or {},
        'inputs': list(inputs or []),
        'tags': list(tags or []),
        'context': context or {},
        'output_count': int(output_count),
        'param_exprs': param_exprs or {},
        'semantic_delta': semantic_delta or {},
        'topo_delta': topo_delta or {},
    })
    obj.SimpleCADFoldedOps = json.dumps(folded, ensure_ascii=True, sort_keys=True)
    existing_tags = list(getattr(obj, 'SimpleCADTags', []) or [])
    merged_tags = sorted({str(tag) for tag in existing_tags + list(tags or [])})
    try:
        obj.SimpleCADTags = merged_tags
    except Exception:
        pass


def _record_graph_output(node_id, obj):
    GRAPH_OUTPUTS.setdefault(node_id, []).append(obj)


def _register_graph_object(obj, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
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
    GRAPH_NODES[node_id] = obj
    GRAPH_METADATA[node_id] = {
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
    }
    _record_graph_limitation(node_id, op, param_exprs)
    _record_graph_output(node_id, obj)
    return obj


def _register_graph_metadata_only(*, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    GRAPH_NODES[node_id] = {
        'node_id': node_id,
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
        'output_count': int(output_count),
        'param_exprs': param_exprs or {},
        'semantic_delta': semantic_delta or {},
        'topo_delta': topo_delta or {},
    }
    GRAPH_METADATA[node_id] = {
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
    }
    _record_graph_limitation(node_id, op, param_exprs)
    GRAPH_OUTPUTS.setdefault(node_id, [])
    return GRAPH_NODES[node_id]


def _register_graph_alias(*, node_id, source_node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    source_obj = _node_object(source_node_id)
    GRAPH_NODES[node_id] = source_obj
    GRAPH_METADATA[node_id] = {
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
    }
    GRAPH_OUTPUTS[node_id] = list(GRAPH_OUTPUTS.get(source_node_id, []))
    return source_obj


def _register_graph_folded_alias(*, node_id, source_node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    source_obj = _node_object(source_node_id)
    _append_folded_op_metadata(
        source_obj,
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
    GRAPH_NODES[node_id] = source_obj
    GRAPH_METADATA[node_id] = {
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
        'folded_into': str(source_node_id),
    }
    _record_graph_limitation(node_id, op, param_exprs)
    GRAPH_OUTPUTS[node_id] = [source_obj]
    return source_obj


def _register_graph_value(value, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    GRAPH_NODES[node_id] = value
    GRAPH_METADATA[node_id] = {
        'op': op,
        'params': params,
        'inputs': list(inputs),
        'context': context or {},
        'tags': list(tags or []),
    }
    _record_graph_limitation(node_id, op, param_exprs)
    GRAPH_OUTPUTS[node_id] = []
    return value


def _make_feature(name, shape, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    obj = doc.addObject('Part::Feature', name)
    obj.Shape = shape
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
def _single_face_shape(shape, operation):
    if hasattr(shape, 'Shape'):
        shape = shape.Shape
    if shape is None or shape.isNull():
        raise RuntimeError(f'{operation} produced no valid shape')
    if getattr(shape, 'ShapeType', '') == 'Face':
        return shape
    faces = list(getattr(shape, 'Faces', []) or [])
    if len(faces) == 1:
        return faces[0]
    raise RuntimeError(f'{operation} expected exactly one face, got {len(faces)}')


def _face_shape_from_wire_shape(shape, operation='make_face_from_wire_rface'):
    source_obj = shape
    if hasattr(shape, 'Shape'):
        shape = shape.Shape
    try:
        shape_invalid = shape is None or shape.isNull()
    except Exception:
        shape_invalid = shape is None
    if shape_invalid and hasattr(source_obj, 'Shape'):
        try:
            doc.recompute()
        except Exception:
            pass
        shape = getattr(source_obj, 'Shape', None)
    try:
        shape_invalid = shape is None or shape.isNull()
    except Exception:
        shape_invalid = shape is None
    if shape_invalid:
        raise RuntimeError(f'{operation} source has no valid shape')
    if getattr(shape, 'ShapeType', '') == 'Face':
        return shape
    if getattr(shape, 'ShapeType', '') == 'Wire':
        return Part.Face(shape)
    wires = list(getattr(shape, 'Wires', []) or [])
    if len(wires) == 1:
        return Part.Face(wires[0])
    return _single_face_shape(shape, operation)


def _wire_shape_from_object(obj, operation):
    source_obj = obj
    shape = getattr(obj, 'Shape', obj)
    try:
        shape_invalid = shape is None or shape.isNull()
    except Exception:
        shape_invalid = shape is None
    if shape_invalid and hasattr(source_obj, 'Shape'):
        try:
            doc.recompute()
        except Exception:
            pass
        shape = getattr(source_obj, 'Shape', None)
    try:
        shape_invalid = shape is None or shape.isNull()
    except Exception:
        shape_invalid = shape is None
    if shape_invalid:
        raise RuntimeError(f'{operation} source has no valid shape')
    if getattr(shape, 'ShapeType', '') == 'Wire':
        return shape
    wires = list(getattr(shape, 'Wires', []) or [])
    if len(wires) == 1:
        return wires[0]
    raise RuntimeError(f'{operation} expected exactly one wire, got {len(wires)}')


def _face_shape_from_wire_shapes(outer_obj, inner_objs, operation='make_face_from_wires_rface'):
    outer_wire = _wire_shape_from_object(outer_obj, operation + ' outer')
    inner_wires = [_wire_shape_from_object(inner_obj, operation + ' inner') for inner_obj in inner_objs]
    attempts = [
        [outer_wire] + [wire.reversed() for wire in inner_wires],
        [outer_wire] + inner_wires,
    ]
    for wires in attempts:
        try:
            face = Part.Face(wires)
        except Exception:
            continue
        if face is not None and not face.isNull() and face.isValid():
            return face
    raise RuntimeError(f'{operation} produced an invalid multi-loop face')


def _face_boolean_shape(operation, base_obj, tool_obj):
    base_shape = _face_shape_from_wire_shape(base_obj, operation + ' base')
    tool_shape = _face_shape_from_wire_shape(tool_obj, operation + ' tool')
    if operation == 'make_2d_cut_rface':
        result = base_shape.cut(tool_shape)
    elif operation == 'make_2d_union_rface':
        result = base_shape.fuse(tool_shape)
    elif operation == 'make_2d_intersect_rface':
        result = base_shape.common(tool_shape)
    else:
        raise RuntimeError(f'Unsupported 2D face boolean {operation!r}')
    return _single_face_shape(result, operation)


def _make_native_object(type_id, name, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    obj = doc.addObject(type_id, name)
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
