CONSTRUCTION_GROUP = None
MATERIAL_LIBRARY_GROUP = None


def _named_document_group(name, label):
    existing = doc.getObject(name)
    if existing is not None:
        return existing
    group = doc.addObject("App::DocumentObjectGroup", name)
    group.Label = label
    _set_visibility(group, False)
    _set_tree_visibility(group, False)
    return group


def _construction_group():
    global CONSTRUCTION_GROUP
    if CONSTRUCTION_GROUP is None:
        CONSTRUCTION_GROUP = _named_document_group(
            "SimpleCADConstruction", "SimpleCAD Construction"
        )
    return CONSTRUCTION_GROUP


def _material_library_group():
    global MATERIAL_LIBRARY_GROUP
    if MATERIAL_LIBRARY_GROUP is None:
        MATERIAL_LIBRARY_GROUP = _named_document_group(
            "SimpleCADMaterials", "SimpleCAD Materials"
        )
    return MATERIAL_LIBRARY_GROUP


def _group_contains(group, obj):
    return obj in list(getattr(group, "Group", []) or [])


def _add_to_group(group, obj):
    if obj is None or obj is group:
        return
    if not _group_contains(group, obj):
        try:
            group.addObject(obj)
        except Exception:
            pass


def _material_from_assignment_params(params):
    params = dict(params or {})
    material = params.get("material")
    if isinstance(material, dict):
        return dict(material)
    return {
        "material_id": str(params.get("material_id", "")),
        "name": params.get("name"),
        "density": params.get("density"),
        "density_unit": params.get("density_unit"),
        "color": params.get("color"),
    }


def _material_color(material):
    color = (material or {}).get("color")
    if not isinstance(color, (list, tuple)) or len(color) != 3:
        return None
    try:
        result = tuple(float(component) for component in color)
    except Exception:
        return None
    if any(component < 0.0 or component > 1.0 for component in result):
        return None
    return result


def _packed_rgba(color):
    channels = [
        max(0, min(255, int(float(component) * 255.0 + 0.5))) for component in color
    ]
    return (channels[0] << 24) | (channels[1] << 16) | (channels[2] << 8) | 255


def _ensure_material_object(material):
    material = dict(material or {})
    material_id = str(material.get("material_id") or "")
    if not material_id:
        raise RuntimeError("Material assignment is missing material_id")
    existing = MATERIAL_OBJECTS_BY_ID.get(material_id)
    if existing is not None:
        return existing
    obj = doc.addObject(
        "App::MaterialObjectPython",
        "Material_" + _simplecad_slug(material_id, prefix="material"),
    )
    obj.Label = str(material.get("name") or material_id)
    _ensure_string_property(obj, "SimpleCADMaterialId", "Material")
    _ensure_string_property(obj, "SimpleCADMaterialName", "Material")
    _ensure_string_property(obj, "SimpleCADMaterial", "Material")
    obj.SimpleCADMaterialId = material_id
    obj.SimpleCADMaterialName = str(material.get("name") or "")
    obj.SimpleCADMaterial = json.dumps(material, ensure_ascii=True, sort_keys=True)
    if material.get("density") is not None:
        _ensure_float_property(obj, "SimpleCADDensity", "Material")
        _ensure_string_property(obj, "SimpleCADDensityUnit", "Material")
        obj.SimpleCADDensity = float(material.get("density"))
        obj.SimpleCADDensityUnit = str(material.get("density_unit") or "")
    color = _material_color(material)
    if color is not None:
        _ensure_color_property(obj, "SimpleCADColor", "Material")
        obj.SimpleCADColor = color
    native_map = {
        "SimpleCAD.MaterialId": material_id,
        "General.Name": str(material.get("name") or material_id),
    }
    if material.get("density") is not None:
        native_map["General.Density"] = (
            str(material.get("density")) + " " + str(material.get("density_unit") or "")
        )
    if color is not None:
        native_map["General.Color"] = ",".join(str(component) for component in color)
    obj.Material = native_map
    _add_to_group(_material_library_group(), obj)
    _set_visibility(obj, False)
    _set_tree_visibility(obj, False)
    MATERIAL_OBJECTS_BY_ID[material_id] = obj
    return obj


def _apply_material_to_object(obj, material, *, override=False, visual=True):
    if obj is None:
        return None
    material = dict(material or {})
    material_obj = _ensure_material_object(material)
    _ensure_string_property(obj, "SimpleCADMaterial")
    _ensure_link_property(obj, "SimpleCADMaterialObject")
    obj.SimpleCADMaterial = json.dumps(material, ensure_ascii=True, sort_keys=True)
    obj.SimpleCADMaterialObject = material_obj
    color = _material_color(material)
    if color is None or not visual:
        return material_obj
    name = str(getattr(obj, "Name", ""))
    if name:
        GUI_SHAPE_COLOR_BY_NAME[name] = _packed_rgba(color)
        if override:
            GUI_MATERIAL_OVERRIDE_BY_NAME[name] = True
    try:
        view = getattr(obj, "ViewObject", None)
        if view is not None:
            if hasattr(view, "ShapeColor"):
                view.ShapeColor = color
            if override and hasattr(view, "OverrideMaterial"):
                view.OverrideMaterial = True
    except Exception:
        pass
    return material_obj


def _apply_material_to_product(product_value, material):
    material_obj = _apply_material_to_object(
        product_value.get("container"), material, visual=False
    )
    _apply_material_to_object(product_value.get("body"), material)
    product_value["material"] = dict(material or {})
    product_value["material_object"] = material_obj
    return product_value


def _is_origin_object(obj):
    return getattr(obj, "TypeId", "") == "App::Origin" or str(
        getattr(obj, "Name", "")
    ).startswith("Origin")


def _is_connector_object(obj):
    try:
        if hasattr(obj, "SimpleCADConnectorId"):
            return True
    except Exception:
        pass
    try:
        return str(getattr(obj, "Name", "")).startswith("connector_")
    except Exception:
        return False


def _hide_origin_tree(container):
    for child in list(getattr(container, "Group", []) or []):
        if _is_origin_object(child):
            _set_visibility(child, False)
            for nested in list(getattr(child, "OutListRecursive", []) or []):
                _set_visibility(nested, False)


def _hide_all_origin_trees():
    for obj in list(getattr(doc, "Objects", []) or []):
        if not _is_origin_object(obj):
            continue
        _set_visibility(obj, False)
        for nested in list(getattr(obj, "OutListRecursive", []) or []):
            _set_visibility(nested, False)


def _move_to_construction_group(obj):
    group = _construction_group()
    for candidate in [obj] + list(getattr(obj, "OutListRecursive", []) or []):
        if candidate is None:
            continue
        if getattr(candidate, "TypeId", "") in {
            "App::Origin",
            "App::Line",
            "App::Plane",
            "App::Point",
        }:
            continue
        _add_to_group(group, candidate)
        _set_visibility(candidate, False)
        _set_tree_visibility(candidate, False)
    _set_visibility(group, False)
    _set_tree_visibility(group, False)


def _hide_product_source_definition(product_item):
    container = (
        product_item.get("container") if isinstance(product_item, dict) else None
    )
    if container is None:
        return
    _set_visibility(container, False)
    _set_tree_visibility(container, False)
    _hide_origin_tree(container)


def _make_part_body_copy(part_container, source_obj, source_node_id):
    doc.recompute()
    if source_obj is None or not hasattr(source_obj, "Shape"):
        raise RuntimeError("Part body source has no shape")
    body = part_container.newObject("Part::Feature", "Body")
    body.Label = "Body"
    body.Shape = source_obj.Shape.copy()
    _ensure_string_property(body, "SimpleCADSourceBodyNodeId")
    body.SimpleCADSourceBodyNodeId = str(source_node_id)
    _attach_tag_metadata_for_node(body, source_node_id)
    _set_visibility(body, True)
    _move_to_construction_group(source_obj)
    return body


def _make_assembly_component_link(
    assembly_container, product_item, name, label, placement
):
    link_type = (
        "Assembly::AssemblyLink"
        if product_item.get("kind") == "assembly"
        else "App::Link"
    )
    link = assembly_container.newObject(link_type, name)
    link.Label = str(label)
    _hide_product_source_definition(product_item)
    link.LinkedObject = product_item.get("container")
    if product_item.get("kind") == "part":
        link.LinkedObject = product_item.get("container") or product_item.get("body")
    if link_type == "Assembly::AssemblyLink":
        try:
            movable_kinds = {"revolute", "prismatic"}
            link.Rigid = not any(
                str(constraint.get("constraint_kind")) in movable_kinds
                for constraint in list(product_item.get("constraints", []) or [])
            )
        except Exception:
            pass
    _set_component_link_placement(link, product_item, placement)
    if product_item.get("kind") == "part" and product_item.get("material"):
        _apply_material_to_object(link, product_item.get("material"), override=True)
    return link


def _set_component_link_placement(link, product_item, placement):
    target_placement = _placement_from_axes_payload(placement)
    if not (
        getattr(link, "TypeId", "") == "Assembly::AssemblyLink"
        and not bool(getattr(link, "Rigid", True))
    ):
        link.Placement = target_placement
        return
    doc.recompute()
    link.Placement = App.Placement()
    for source_component in list(product_item.get("components", []) or []):
        source_link = source_component.get("link")
        local_link = next(
            (
                child
                for child in list(getattr(link, "Group", []) or [])
                if getattr(child, "LinkedObject", None) is source_link
            ),
            None,
        )
        if local_link is None:
            continue
        source_placement = _placement_from_axes_payload(
            source_component.get("placement") or {}
        )
        local_link.Placement = target_placement.multiply(source_placement)
