def _node_object(node_id, index=0):
    outputs = GRAPH_OUTPUTS.get(node_id, [])
    if not outputs:
        raise RuntimeError(f'Missing graph output object for node {node_id!r}')
    idx = int(index)
    if idx < 0 or idx >= len(outputs):
        raise RuntimeError(f'Output object slot {idx} missing for node {node_id!r}')
    return outputs[idx]


def _set_visibility(obj, visible):
    if obj is not None:
        try:
            GUI_VISIBILITY_BY_NAME[str(obj.Name)] = bool(visible)
        except Exception:
            pass
    try:
        view = getattr(obj, 'ViewObject', None)
        if view is not None and hasattr(view, 'Visibility'):
            view.Visibility = bool(visible)
    except Exception:
        pass
    try:
        if hasattr(obj, 'Visibility'):
            obj.Visibility = bool(visible)
    except Exception:
        pass


def _set_expanded(obj, expanded=True):
    try:
        GUI_EXPANDED_BY_NAME[str(obj.Name)] = bool(expanded)
    except Exception:
        pass


def _xml_attr(value):
    return str(value).replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def _visibility_for_gui(obj):
    try:
        name = str(obj.Name)
    except Exception:
        return False
    if name in GUI_VISIBILITY_BY_NAME:
        return bool(GUI_VISIBILITY_BY_NAME[name])
    try:
        return bool(obj.Visibility)
    except Exception:
        return False


def _write_gui_document_xml(fcstd_path):
    object_rows = []
    for obj in list(getattr(doc, 'Objects', []) or []):
        try:
            name = str(obj.Name)
        except Exception:
            continue
        object_rows.append((
            name,
            _visibility_for_gui(obj),
            bool(GUI_EXPANDED_BY_NAME.get(name, False)),
            GUI_SHAPE_COLOR_BY_NAME.get(name),
            bool(GUI_MATERIAL_OVERRIDE_BY_NAME.get(name, False)),
        ))
    lines = [
        "<?xml version='1.0' encoding='utf-8'?>",
        '<!--',
        ' FreeCAD Document, see https://www.freecad.org for more information...',
        '-->',
        '<Document SchemaVersion="1">',
        f'    <ViewProviderData Count="{len(object_rows)}">',
    ]
    for name, visible, expanded, packed_color, override_material in object_rows:
        joint_type = SIMPLECAD_JOINT_OBJECTS.get(name)
        properties = [
            ('Visibility', 'App::PropertyBool', f'<Bool value="{str(bool(visible)).lower()}"/>'),
        ]
        if packed_color is not None and override_material:
            properties.extend([
                ('OverrideMaterial', 'App::PropertyBool', '<Bool value="true"/>'),
                (
                    'ShapeMaterial',
                    'App::PropertyMaterial',
                    '<PropertyMaterial ambientColor="858993663" '
                    f'diffuseColor="{int(packed_color)}" '
                    'specularColor="858993663" emissiveColor="255" '
                    'shininess="0.2" transparency="0" image="" imagePath="" uuid=""/>',
                ),
            ])
        elif packed_color is not None:
            properties.append(
                ('ShapeColor', 'App::PropertyColor', f'<PropertyColor value="{int(packed_color)}"/>')
            )
        if joint_type is not None:
            vp_class = 'ViewProviderGroundedJoint' if joint_type == 'Grounded' else 'ViewProviderJoint'
            properties.append(
                ('Proxy', 'App::PropertyPythonObject', f'<Python value="bnVsbA==" encoded="yes" module="JointObject" class="{vp_class}"/>')
            )
        lines.extend([
            f'        <ViewProvider name="{_xml_attr(name)}" expanded="{1 if expanded else 0}">',
            f'            <Properties Count="{len(properties)}">',
        ])
        for prop_name, prop_type, prop_value in properties:
            status = ' status="67108864"' if prop_name == 'Proxy' else ''
            lines.extend([
                f'                <Property name="{prop_name}" type="{prop_type}"{status}>',
                f'                    {prop_value}',
                '                </Property>',
            ])
        lines.extend([
            '            </Properties>',
            '        </ViewProvider>',
        ])
    lines.extend([
        '    </ViewProviderData>',
        '    <Camera settings="  OrthographicCamera { viewportMapping ADJUST_CAMERA position 0 -0 20000 orientation 0 0 1 0 nearDistance 1 farDistance 100000 aspectRatio 1 focalDistance 20000 height 1000 } "/>',
        '</Document>',
        '',
    ])
    gui_document = '\n'.join(lines).encode('utf-8')
    tmp_path = str(fcstd_path) + '.simplecad_tmp'
    with zipfile.ZipFile(fcstd_path, 'r') as source:
        infos = source.infolist()
        with zipfile.ZipFile(tmp_path, 'w', compression=zipfile.ZIP_DEFLATED) as target:
            wrote_gui = False
            for info in infos:
                if info.filename == 'GuiDocument.xml':
                    target.writestr(info, gui_document)
                    wrote_gui = True
                else:
                    target.writestr(info, source.read(info.filename))
            if not wrote_gui:
                target.writestr('GuiDocument.xml', gui_document)
    os.replace(tmp_path, fcstd_path)


def _save_fcstd_with_gui_visibility(output_path):
    doc.recompute()
    _hide_all_origin_trees()
    doc.saveAs(output_path)
    _hide_all_origin_trees()
    _write_gui_document_xml(output_path)


def _placement_for_rotation(origin, axis, angle_degrees):
    center = _vec(origin)
    rotation = App.Rotation(_vec(axis), float(angle_degrees))
    to_center = App.Placement(center, rotation)
    from_center = App.Placement(App.Vector(-center.x, -center.y, -center.z), App.Rotation())
    return to_center.multiply(from_center)


def _fold_object_placement(obj, placement):
    obj.Placement = placement.multiply(obj.Placement)
    return obj


def _set_part_body_visibility(product_value, visible):
    container = product_value.get('container') if isinstance(product_value, dict) else None
    if container is None:
        return
    body = product_value.get('body')
    for child in list(getattr(container, 'Group', []) or []):
        if _is_origin_object(child):
            _set_visibility(child, False)
            continue
        if _is_connector_object(child):
            _set_visibility(child, False)
            continue
        _set_visibility(child, bool(visible and child is body))
    if body is not None:
        _set_visibility(body, visible)


def _set_product_tree_visibility(product_value, visible, *, show_source_container=True):
    if not isinstance(product_value, dict):
        return
    kind = product_value.get('kind')
    container = product_value.get('container')
    if kind == 'part':
        if container is not None:
            _set_visibility(container, visible if show_source_container else False)
            _set_expanded(container, bool(visible and show_source_container))
            _hide_origin_tree(container)
        _set_part_body_visibility(product_value, visible)
        return
    if kind == 'assembly':
        if container is not None:
            _set_visibility(container, visible if show_source_container else False)
            _set_expanded(container, bool(visible and show_source_container))
            _hide_origin_tree(container)
            for child in list(getattr(container, 'Group', []) or []):
                if _is_connector_object(child):
                    _set_visibility(child, False)
        for component in product_value.get('components', []):
            link = component.get('link')
            if link is not None:
                _set_visibility(link, visible)
                _set_expanded(link, bool(visible))
            item = component.get('item')
            _set_product_tree_visibility(item, visible, show_source_container=False)


def _apply_product_result_visibility(visible_ids):
    product_ids = set()
    product_ids.update(str(node_id) for node_id in visible_ids if str(node_id) in PRODUCT_VALUES)
    product_ids.update(
        str(source_id)
        for node_id, source_id in ASSEMBLY_PROJECTION_INPUTS.items()
        if str(node_id) in visible_ids
    )
    for node_id in product_ids:
        _set_product_tree_visibility(PRODUCT_VALUES.get(node_id), True)
    if PRODUCT_LIBRARY_GROUP is not None:
        _set_visibility(PRODUCT_LIBRARY_GROUP, False)
    if CONSTRUCTION_GROUP is not None:
        _set_visibility(CONSTRUCTION_GROUP, False)


def _result_product_container(result_node_ids):
    for node_id in result_node_ids or []:
        product_value = PRODUCT_VALUES.get(str(node_id))
        if isinstance(product_value, dict) and product_value.get('container') is not None:
            return product_value.get('container')
        source_id = ASSEMBLY_PROJECTION_INPUTS.get(str(node_id))
        product_value = PRODUCT_VALUES.get(str(source_id))
        if isinstance(product_value, dict) and product_value.get('container') is not None:
            return product_value.get('container')
    return None


def _set_active_result_object(result_node_ids):
    obj = _result_product_container(result_node_ids)
    if obj is None:
        result_objects = [candidate for node_id in (result_node_ids or []) for candidate in GRAPH_OUTPUTS.get(str(node_id), [])]
        obj = result_objects[0] if result_objects else None
    if obj is None:
        return
    try:
        doc.ActiveObject = obj
    except Exception:
        pass
    try:
        import FreeCADGui as Gui
        if getattr(App, 'GuiUp', False) and Gui.ActiveDocument is not None:
            Gui.ActiveDocument.ActiveView.setActiveObject('part', obj)
    except Exception:
        pass


def _apply_result_visibility(result_node_ids):
    visible_ids = {str(node_id) for node_id in (result_node_ids or [])}
    projection_visible_ids = {str(source_id) for node_id, source_id in ASSEMBLY_PROJECTION_INPUTS.items() if str(node_id) in visible_ids}
    for node_id, outputs in GRAPH_OUTPUTS.items():
        is_visible = str(node_id) in visible_ids or str(node_id) in projection_visible_ids
        if str(node_id) in ASSEMBLY_PROJECTION_INPUTS:
            is_visible = False
        for obj in outputs:
            _set_visibility(obj, is_visible)
    _apply_product_result_visibility(visible_ids)
    _hide_all_origin_trees()
