OCCURRENCE_LABEL_COUNTS = {}

OCCURRENCE_ROOT_OBJECTS = {}
OCCURRENCE_OBJECTS = []
OCCURRENCE_SOURCE_NAMES_BY_ROOT = {}
OCCURRENCE_SOURCE_OBJECTS = []

_OCCURRENCE_PRODUCT_TYPES = {
    "App::Part",
    "Assembly::AssemblyObject",
    "Assembly::AssemblyLink",
    "App::MaterialObjectPython",
    "Spreadsheet::Sheet",
}


def _occurrence_is_object(value):
    return value is not None and hasattr(value, "Name") and hasattr(value, "TypeId")


def _occurrence_object_key(value):
    try:
        return str(value.Name)
    except Exception:
        return ""


def _occurrence_is_geometry(value):
    if not _occurrence_is_object(value) or not hasattr(value, "Shape"):
        return False
    if str(getattr(value, "TypeId", "")) in _OCCURRENCE_PRODUCT_TYPES:
        return False
    return not any(
        hasattr(value, prop_name)
        for prop_name in (
            "SimpleCADAssemblyId",
            "SimpleCADPartId",
            "SimpleCADComponentId",
            "SimpleCADConnectorId",
            "SimpleCADMaterialId",
        )
    )


def _occurrence_slug(value):
    token = "".join(ch if str(ch).isalnum() else "_" for ch in str(value or ""))
    token = token.strip("_") or "occurrence"
    if token[0].isdigit():
        token = "occurrence_" + token
    return token[:120]


def _occurrence_label(source, labels):
    node_id = str(getattr(source, "SimpleCADNodeId", "") or "")
    base = str(
        labels.get(node_id)
        or getattr(source, "Label", "")
        or getattr(source, "SimpleCADOp", "")
        or "Operation"
    )
    count = OCCURRENCE_LABEL_COUNTS.get(base, 0) + 1
    OCCURRENCE_LABEL_COUNTS[base] = count
    return base if count == 1 else f"{base} ({count})"


def _occurrence_copy_link(source, clone, attribute, root_token, path, labels):
    value = getattr(source, attribute, None)
    if not _occurrence_is_object(value) or value is source:
        return
    child = _copy_occurrence(
        value,
        root_token=root_token,
        path=path + (attribute,),
        labels=labels,
    )
    if child is None:
        return
    try:
        setattr(clone, attribute, child)
    except Exception:
        pass


def _occurrence_copy_link_list(source, clone, attribute, root_token, path, labels):
    values = getattr(source, attribute, None)
    if not isinstance(values, (list, tuple)):
        return
    if not values or not all(_occurrence_is_object(value) for value in values):
        return
    children = [
        _copy_occurrence(
            value,
            root_token=root_token,
            path=path + (attribute, str(index)),
            labels=labels,
        )
        for index, value in enumerate(values)
    ]
    if any(child is None for child in children):
        return
    try:
        setattr(clone, attribute, children)
    except Exception:
        pass


def _occurrence_copy_faces(source, clone, root_token, path, labels):
    value = getattr(source, "Faces", None)
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return
    base, names = value
    if not _occurrence_is_object(base):
        return
    copied_base = _copy_occurrence(
        base,
        root_token=root_token,
        path=path + ("Faces",),
        labels=labels,
    )
    if copied_base is None:
        return
    try:
        clone.Faces = (copied_base, names)
    except Exception:
        pass


def _occurrence_copy_support(source, clone, root_token, path, labels):
    value = getattr(source, "Support", None)
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return
    base, subelements = value
    if not _occurrence_is_object(base):
        return
    copied_base = _copy_occurrence(
        base,
        root_token=root_token,
        path=path + ("Support",),
        labels=labels,
    )
    if copied_base is None:
        return
    try:
        clone.Support = (copied_base, subelements)
    except Exception:
        pass


def _occurrence_copy_link_sub(source, clone, attribute, root_token, path, labels):
    value = getattr(source, attribute, None)
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return
    linked, subelements = value
    if not _occurrence_is_object(linked):
        return
    copied = _copy_occurrence(
        linked,
        root_token=root_token,
        path=path + (attribute,),
        labels=labels,
    )
    if copied is None:
        return
    try:
        setattr(clone, attribute, (copied, subelements))
    except Exception:
        pass


def _occurrence_copy_simplecad_properties(source, clone):
    for prop_name in list(getattr(source, "PropertiesList", []) or []):
        if not str(prop_name).startswith("SimpleCAD"):
            continue
        try:
            if prop_name not in list(getattr(clone, "PropertiesList", []) or []):
                clone.addProperty(
                    source.getTypeIdOfProperty(prop_name),
                    prop_name,
                    source.getGroupOfProperty(prop_name),
                )
            setattr(clone, prop_name, getattr(source, prop_name))
        except Exception:
            pass


def _occurrence_copy_expressions(source, clone):
    if not hasattr(clone, "setExpression"):
        return
    for prop_name, expression in list(getattr(source, "ExpressionEngine", []) or []):
        try:
            clone.setExpression(str(prop_name), str(expression))
        except Exception:
            pass


def _copy_occurrence(source, *, root_token, path, labels):
    if not _occurrence_is_object(source):
        return None
    is_product_link = bool(
        getattr(source, "SimpleCADComponentId", "")
        or str(getattr(source, "TypeId", "")) == "Assembly::AssemblyLink"
    )
    try:
        clone = doc.copyObject(source, False)
    except Exception as exc:
        raise RuntimeError(
            f'FreeCAD cannot copy occurrence {getattr(source, "Name", "<unknown>")!r}'
        ) from exc
    OCCURRENCE_SOURCE_NAMES_BY_ROOT.setdefault(root_token, set()).add(
        _occurrence_object_key(source)
    )
    OCCURRENCE_OBJECTS.append(clone)
    OCCURRENCE_SOURCE_OBJECTS.append(source)
    _occurrence_copy_simplecad_properties(source, clone)
    _occurrence_copy_expressions(source, clone)
    try:
        clone.Label = _occurrence_label(source, labels)
    except Exception:
        pass

    attributes = (
        "Base",
        "Tool",
        "Source",
        "Spine",
        "BaseFeature",
        "Profile",
        "Path",
    )
    if not is_product_link:
        attributes = attributes + ("LinkedObject",)
    for attribute in attributes:
        _occurrence_copy_link(source, clone, attribute, root_token, path, labels)
    for attribute in ("Sections", "Shapes", "Sources", "Tools"):
        _occurrence_copy_link_list(source, clone, attribute, root_token, path, labels)
    _occurrence_copy_faces(source, clone, root_token, path, labels)
    _occurrence_copy_support(source, clone, root_token, path, labels)
    _occurrence_copy_link_sub(source, clone, "Spine", root_token, path, labels)
    return clone


def _occurrence_remove_object(obj):
    if not _occurrence_is_object(obj):
        return
    try:
        doc.removeObject(str(obj.Name))
    except Exception:
        pass


def _occurrence_protected_objects():
    protected = {
        id(root) for root in OCCURRENCE_ROOT_OBJECTS.values() if root is not None
    }
    for value in list(PRODUCT_VALUES.values()):
        if not isinstance(value, dict):
            continue
        for key in ("container", "body", "material_object"):
            obj = value.get(key)
            if _occurrence_is_object(obj):
                protected.add(id(obj))
        for component in list(value.get("components", []) or []):
            if not isinstance(component, dict):
                continue
            link = component.get("link")
            if _occurrence_is_object(link):
                protected.add(id(link))
    return protected


def _occurrence_cleanup_originals(plan):
    global CONSTRUCTION_GROUP
    protected = _occurrence_protected_objects()
    clone_ids = {id(obj) for obj in OCCURRENCE_OBJECTS if obj is not None}
    node_order = {
        str(node_id): index
        for index, node_id in enumerate(
            [
                str(value)
                for root in list((plan or {}).get("roots") or [])
                for value in list(root.get("managed_node_ids") or [])
            ]
        )
    }
    candidates = []
    for root in list((plan or {}).get("roots") or []):
        if not isinstance(root, dict):
            continue
        for node_id in list(root.get("managed_node_ids") or []):
            for obj in list(GRAPH_OUTPUTS.get(str(node_id), []) or []):
                if not _occurrence_is_object(obj):
                    continue
                if id(obj) in protected or id(obj) in clone_ids:
                    continue
                candidates.append((node_order.get(str(node_id), -1), obj))
    seen = set()
    for _index, obj in sorted(candidates, key=lambda item: item[0], reverse=True):
        marker = id(obj)
        if marker in seen:
            continue
        seen.add(marker)
        _occurrence_remove_object(obj)
    for obj in list(GRAPH_SPINE_OBJECTS.values()):
        if id(obj) not in protected and id(obj) not in clone_ids:
            _occurrence_remove_object(obj)
    for obj in list(OCCURRENCE_SOURCE_OBJECTS):
        marker = id(obj)
        if marker in seen or marker in protected or marker in clone_ids:
            continue
        seen.add(marker)
        _occurrence_remove_object(obj)
    doc.recompute()
    if CONSTRUCTION_GROUP is not None:
        try:
            if not list(getattr(CONSTRUCTION_GROUP, "Group", []) or []):
                _occurrence_remove_object(CONSTRUCTION_GROUP)
                CONSTRUCTION_GROUP = None
        except Exception:
            pass


def _occurrence_complete_root(container, root, root_token, labels):
    copied_names = OCCURRENCE_SOURCE_NAMES_BY_ROOT.setdefault(root_token, set())
    for node_id in list(root.get("managed_node_ids") or []):
        for index, source in enumerate(list(GRAPH_OUTPUTS.get(str(node_id), []) or [])):
            source_name = _occurrence_object_key(source)
            if (
                not source_name
                or source_name in copied_names
                or not _occurrence_is_geometry(source)
            ):
                continue
            clone = _copy_occurrence(
                source,
                root_token=root_token,
                path=("managed", str(node_id), str(index)),
                labels=labels,
            )
            if clone is None:
                continue
            try:
                container.addObject(clone)
            except Exception as exc:
                raise RuntimeError(
                    f"FreeCAD could not attach upstream occurrence {clone.Name!r}"
                ) from exc
            _set_visibility(clone, False)


def _occurrence_make_root(root, source, labels):
    root_id = str(root.get("root_id") or "model")
    root_token = _occurrence_slug(root_id)
    container_name = "SimpleCADModel_" + root_token
    container = doc.getObject(container_name)
    if container is None:
        container = doc.addObject("App::Part", container_name)
    container.Label = str(root.get("label") or "Model")
    clone = _copy_occurrence(
        source,
        root_token=root_token,
        path=("result",),
        labels=labels,
    )
    if clone is None:
        return None
    try:
        clone.Label = str(root.get("result_label") or _occurrence_label(source, labels))
    except Exception:
        pass
    _ensure_string_property(clone, "SimpleCADSemanticRole", "SimpleCAD Semantic")
    clone.SimpleCADSemanticRole = "result"
    _attach_tag_metadata_for_node(clone, str(root.get("result_node_id") or ""))
    try:
        container.addObject(clone)
    except Exception as exc:
        raise RuntimeError(
            f"FreeCAD could not attach result occurrence {clone.Name!r} to {container.Name!r}"
        ) from exc
    _set_visibility(container, True)
    _set_expanded(container, True)
    _occurrence_complete_root(container, root, root_token, labels)
    _set_visibility(clone, True)
    _set_expanded(clone, True)
    _hide_origin_tree(container)
    return container


def _occurrence_make_part_root(root, source, labels):
    product = PRODUCT_VALUES.get(str(root.get("product_node_id") or ""))
    if not isinstance(product, dict):
        return None
    container = product.get("container")
    if not _occurrence_is_object(container):
        return None
    container.Label = str(root.get("label") or container.Label)
    was_visible = bool(getattr(container, "Visibility", False))
    old_body = product.get("body")
    clone = _copy_occurrence(
        source,
        root_token=_occurrence_slug(root.get("root_id") or "part"),
        path=("body",),
        labels=labels,
    )
    if clone is None:
        return None
    try:
        clone.Label = str(root.get("result_label") or _occurrence_label(source, labels))
        _ensure_string_property(clone, "SimpleCADSourceBodyNodeId")
        clone.SimpleCADSourceBodyNodeId = str(root.get("result_node_id") or "")
        _attach_tag_metadata_for_node(clone, clone.SimpleCADSourceBodyNodeId)
        container.addObject(clone)
    except Exception as exc:
        raise RuntimeError(
            f"FreeCAD could not attach part occurrence {clone.Name!r}"
        ) from exc
    if old_body is not None and old_body is not clone:
        _occurrence_remove_object(old_body)
    material = product.get("material")
    for value in list(PRODUCT_VALUES.values()):
        if isinstance(value, dict) and value.get("container") is container:
            value["body"] = clone
            if value.get("material"):
                material = value.get("material")
    if material:
        _apply_material_to_object(clone, material)
    _set_visibility(container, was_visible)
    _set_expanded(container, True)
    _occurrence_complete_root(
        container,
        root,
        _occurrence_slug(root.get("root_id") or "part"),
        labels,
    )
    _set_visibility(clone, was_visible)
    _set_expanded(clone, True)
    _hide_origin_tree(container)
    return container


def _apply_occurrence_tree(plan):
    global OCCURRENCE_LABEL_COUNTS, OCCURRENCE_SOURCE_NAMES_BY_ROOT
    if not isinstance(plan, dict):
        return {}
    labels = dict(plan.get("node_labels") or {})
    OCCURRENCE_LABEL_COUNTS = {}
    OCCURRENCE_SOURCE_NAMES_BY_ROOT = {}
    OCCURRENCE_OBJECTS[:] = []
    OCCURRENCE_SOURCE_OBJECTS[:] = []
    created = {}
    for root in list(plan.get("roots") or []):
        if not isinstance(root, dict):
            continue
        result_node_id = str(root.get("result_node_id") or "")
        outputs = list(GRAPH_OUTPUTS.get(result_node_id, []) or [])
        source = outputs[0] if outputs else None
        if not _occurrence_is_object(source):
            continue
        if str(root.get("kind") or "") == "part":
            container = _occurrence_make_part_root(root, source, labels)
        else:
            container = _occurrence_make_root(root, source, labels)
        if container is not None:
            created[str(root.get("root_id") or container.Name)] = container
    _occurrence_cleanup_originals(plan)
    OCCURRENCE_ROOT_OBJECTS.clear()
    OCCURRENCE_ROOT_OBJECTS.update(created)
    if created:
        active = next(iter(created.values()))
        try:
            doc.ActiveObject = active
        except Exception:
            pass
    return created


def _set_user_tree_branch(obj, shown, seen=None):
    if not _occurrence_is_object(obj):
        return
    seen = seen if isinstance(seen, set) else set()
    marker = id(obj)
    if marker in seen:
        return
    seen.add(marker)
    _set_tree_visibility(obj, shown)
    for child in list(getattr(obj, "Group", []) or []):
        _set_user_tree_branch(child, shown, seen)


def _enforce_user_tree_roots():
    for obj in list(getattr(doc, "Objects", []) or []):
        _set_tree_visibility(obj, False)
    allowed = []
    for node_id in list((SEMANTIC_PLAN or {}).get("display_product_node_ids") or []):
        product = PRODUCT_VALUES.get(str(node_id))
        container = product.get("container") if isinstance(product, dict) else None
        if _occurrence_is_object(container):
            allowed.append(container)
    for root in list((SEMANTIC_PLAN or {}).get("roots") or []):
        if not isinstance(root, dict) or str(root.get("kind") or "") != "geometry":
            continue
        container = OCCURRENCE_ROOT_OBJECTS.get(str(root.get("root_id") or ""))
        if _occurrence_is_object(container):
            allowed.append(container)
    seen = set()
    for container in allowed:
        _set_user_tree_branch(container, True, seen)


def _restore_occurrence_tree_visibility():
    for container in OCCURRENCE_ROOT_OBJECTS.values():
        _set_visibility(container, bool(getattr(container, "Visibility", True)))
        _set_expanded(container, True)
        _hide_origin_tree(container)
    _enforce_user_tree_roots()
