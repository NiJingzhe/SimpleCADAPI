def _make_native_assembly(name, *, node_id, op, params, inputs, tags, context, output_count, param_exprs=None, semantic_delta=None, topo_delta=None):
    if Assembly is None:
        raise RuntimeError('FreeCAD Assembly workbench module is required for SimpleCAD Assembly translation')
    obj = doc.addObject('Assembly::AssemblyObject', name)
    obj.Type = 'Assembly'
    try:
        obj.newObject('Assembly::JointGroup', 'Joints')
    except Exception:
        pass
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


def _joint_group_for(assembly_container):
    for child in list(getattr(assembly_container, 'OutList', []) or []):
        if getattr(child, 'TypeId', '') == 'Assembly::JointGroup':
            return child
    return assembly_container.newObject('Assembly::JointGroup', 'Joints')


def _find_component_entry(assembly_value, component_id):
    for component in list(assembly_value.get('components', []) or []):
        if str(component.get('component_id')) == str(component_id):
            return component
    raise RuntimeError(f'Missing assembly component {component_id!r}')


def _connector_payload_for(component_entry, connector_id):
    item = component_entry.get('item') or {}
    try:
        return _connector_payload_for_item(item, connector_id)
    except Exception as exc:
        raise RuntimeError(f'Missing connector {connector_id!r} on component {component_entry.get("component_id")!r}') from exc


def _freecad_subname_for_kind(kind, index):
    # Convert a 0-based index into a FreeCAD sub-element name string.
    kind_lower = str(kind).lower()
    prefix_map = {'vertex': 'Vertex', 'edge': 'Edge', 'wire': 'Wire', 'face': 'Face', 'solid': 'Solid'}
    prefix = prefix_map.get(kind_lower, 'Face')
    return f'{prefix}{index + 1}'


def _resolve_connector_subname(component_entry, connector_payload):
    # Resolve the FreeCAD sub-element name (e.g. Face3) for a connector geometry_ref.
    # Uses the geo_selector to match against the component link shape.
    # Returns a tuple (subname1, subname2) suitable for FreeCAD Reference1/Reference2.
    geometry_ref = connector_payload.get('geometry_ref') or {}
    geo_selector = geometry_ref.get('geo_selector') or {}
    kind = str(geometry_ref.get('kind') or geo_selector.get('kind') or '').lower()
    if not kind:
        return '', ''
    link = component_entry.get('link')
    if link is None:
        return '', ''
    linked_obj = getattr(link, 'LinkedObject', None) or link
    shape = getattr(linked_obj, 'Shape', None)
    if shape is None:
        return '', ''
    try:
        index = _selection_index_for_selector(shape, geo_selector)
        subname = _freecad_subname_for_kind(kind, index)
        return subname, subname
    except Exception:
        return '', ''


def _connector_reference_for_component(assembly_value, component_entry, connector_payload):
    link = component_entry.get('link')
    if link is None:
        raise RuntimeError(f'Missing component link for component {component_entry.get("component_id")!r}')
    anchor = _connector_anchor_payload(connector_payload or {})
    if (
        getattr(link, 'TypeId', '') == 'Assembly::AssemblyLink'
        and not bool(getattr(link, 'Rigid', True))
        and str(anchor.get('anchor_kind') or '').lower() == 'forwarded'
    ):
        source_component = _find_component_entry(
            component_entry.get('item') or {}, anchor.get('source_component_id')
        )
        source_link = source_component.get('link')
        local_link = next(
            child
            for child in list(getattr(link, 'Group', []) or [])
            if getattr(child, 'LinkedObject', None) is source_link
        )
        source_item = source_component.get('item') or {}
        source_connector = _connector_payload_for_item(
            source_item, anchor.get('source_connector_id')
        )
        placement = _connector_local_placement(source_item, source_connector)
        if isinstance(anchor.get('offset'), dict):
            placement = placement.multiply(_placement_from_axes_payload(anchor.get('offset')))
        return local_link, ['', ''], placement, True
    datum = (connector_payload or {}).get('datum')
    datum_name = str(getattr(datum, 'Name', '') or '')
    if datum_name:
        subname = datum_name + '.'
        return link, [subname, subname], App.Placement(), False
    anchor = _connector_anchor_payload(connector_payload or {})
    if str(anchor.get('anchor_kind') or '').lower() == 'geometry':
        sub_a, sub_b = _resolve_connector_subname(component_entry, connector_payload)
        if sub_a and sub_b:
            return link, [sub_a, sub_b], App.Placement(), False
    return link, ['', ''], _connector_local_placement(component_entry.get('item') or {}, connector_payload), True


def _make_simplecad_joint(assembly_value, constraint_payload, object_name, label):
    assembly_container = assembly_value.get('container')
    if assembly_container is None:
        raise RuntimeError('Assembly value has no container for constraint translation')
    connector_a = constraint_payload.get('connector_a') or {}
    connector_b = constraint_payload.get('connector_b') or {}
    component_a = _find_component_entry(assembly_value, connector_a.get('component_id'))
    component_b = _find_component_entry(assembly_value, connector_b.get('component_id'))
    connector_a_payload = _connector_payload_for(component_a, connector_a.get('connector_id'))
    connector_b_payload = _connector_payload_for(component_b, connector_b.get('connector_id'))
    joint_type = {'fixed': 'Fixed', 'revolute': 'Revolute', 'prismatic': 'Slider', 'gear': 'Gears', 'belt': 'Belt', 'rack_pinion': 'RackPinion'}.get(str(constraint_payload.get('constraint_kind')))
    if not joint_type:
        raise RuntimeError(f"Unsupported SimpleCAD constraint kind {constraint_payload.get('constraint_kind')!r}")
    joint_group = _joint_group_for(assembly_container)
    joint = joint_group.newObject('App::FeaturePython', object_name)
    joint.Label = str(label or constraint_payload.get('constraint_id') or object_name)
    type_index = {'Fixed': 0, 'Revolute': 1, 'Slider': 3, 'RackPinion': 9, 'Gears': 11, 'Belt': 12}[joint_type]
    native_status = 'metadata_only'
    if JointObject is not None:
        JointObject.Joint(joint, type_index)
        native_status = 'native_equivalent'
        if getattr(App, 'GuiUp', False) and hasattr(joint, 'ViewObject') and joint.ViewObject is not None:
            try:
                JointObject.ViewProviderJoint(joint.ViewObject)
            except Exception:
                pass
    else:
        _ensure_string_property(joint, 'JointType')
        joint.JointType = joint_type
    try:
        ref_a_obj, ref_a_subs, ref_a_placement, ref_a_detached = _connector_reference_for_component(assembly_value, component_a, connector_a_payload)
        ref_b_obj, ref_b_subs, ref_b_placement, ref_b_detached = _connector_reference_for_component(assembly_value, component_b, connector_b_payload)
        if hasattr(joint, 'Reference1'):
            if hasattr(joint, 'Detach1'):
                joint.Detach1 = bool(ref_a_detached)
            if hasattr(joint, 'Detach2'):
                joint.Detach2 = bool(ref_b_detached)
            joint.Reference1 = [ref_a_obj, list(ref_a_subs)]
            joint.Reference2 = [ref_b_obj, list(ref_b_subs)]
            if hasattr(joint, 'Placement1'):
                joint.Placement1 = ref_a_placement
            if hasattr(joint, 'Placement2'):
                joint.Placement2 = ref_b_placement
    except Exception:
        native_status = 'native_partial'
    if joint_type == 'Revolute' and constraint_payload.get('drive_angle_degrees') is not None:
        try:
            joint.Angle = float(constraint_payload.get('drive_angle_degrees'))
        except Exception:
            native_status = 'native_partial'
    if joint_type == 'Slider' and constraint_payload.get('drive_distance') is not None:
        try:
            joint.Distance = float(constraint_payload.get('drive_distance'))
        except Exception:
            native_status = 'native_partial'
    if joint_type == 'Gears':
        try:
            joint.Distance = float(constraint_payload.get('pitch_radius_a'))
            joint.Distance2 = float(constraint_payload.get('pitch_radius_b'))
        except Exception:
            native_status = 'native_partial'
    if joint_type == 'Belt':
        try:
            joint.Distance = float(constraint_payload.get('pulley_radius_a'))
            joint.Distance2 = float(constraint_payload.get('pulley_radius_b'))
        except Exception:
            native_status = 'native_partial'
    if joint_type == 'RackPinion':
        try:
            joint.Distance = float(constraint_payload.get('pitch_radius'))
        except Exception:
            native_status = 'native_partial'
    angle_limit = constraint_payload.get('angle_limit')
    if angle_limit:
        try:
            joint.EnableAngleMin = True
            joint.EnableAngleMax = True
            joint.AngleMin = float(angle_limit.get('lower_value'))
            joint.AngleMax = float(angle_limit.get('upper_value'))
        except Exception:
            native_status = 'native_partial'
    distance_limit = constraint_payload.get('distance_limit')
    if distance_limit:
        try:
            joint.EnableLengthMin = True
            joint.EnableLengthMax = True
            joint.LengthMin = float(distance_limit.get('lower_value'))
            joint.LengthMax = float(distance_limit.get('upper_value'))
        except Exception:
            native_status = 'native_partial'
    _ensure_string_property(joint, 'SimpleCADConstraint')
    _ensure_string_property(joint, 'SimpleCADConstraintTranslationStatus')
    joint.SimpleCADConstraint = json.dumps(constraint_payload, ensure_ascii=True, sort_keys=True)
    joint.SimpleCADConstraintTranslationStatus = native_status
    _set_visibility(joint, False)
    try:
        SIMPLECAD_JOINT_OBJECTS[str(joint.Name)] = joint_type
    except Exception:
        pass
    return joint


def _make_simplecad_grounded_joint(assembly_value, component_id):
    assembly_container = assembly_value.get('container')
    if assembly_container is None:
        raise RuntimeError('Assembly value has no container for grounded joint translation')
    component_entry = _find_component_entry(assembly_value, component_id)
    link = component_entry.get('link')
    if link is None:
        raise RuntimeError(f'Missing component link for grounded component {component_id!r}')
    joint_group = _joint_group_for(assembly_container)
    ground = joint_group.newObject('App::FeaturePython', 'GroundedJoint_' + str(component_id))
    ground.Label = 'GroundedJoint_' + str(component_id)
    native_status = 'metadata_only'
    if JointObject is not None:
        JointObject.GroundedJoint(ground, link)
        native_status = 'native_equivalent'
    else:
        _ensure_string_property(ground, 'ObjectToGround')
    _ensure_string_property(ground, 'SimpleCADGroundedComponent')
    ground.SimpleCADGroundedComponent = str(component_id)
    _set_visibility(ground, False)
    try:
        SIMPLECAD_JOINT_OBJECTS[str(ground.Name)] = 'Grounded'
    except Exception:
        pass
    return ground
