"""Bind pywin32 wrappers to the running application's actual type library."""


def _solidworks_wrapper_class(module, clsid):
    candidate = getattr(module, 'CLSIDToClassMap', {}).get(clsid)
    if candidate is not None:
        return candidate
    # Demand-generated child modules register individual classes and do not
    # expose the root module's CLSIDToClassMap.
    for candidate in vars(module).values():
        if isinstance(candidate, type) and str(getattr(candidate, 'CLSID', '')) == clsid:
            return candidate
    return None


def _bind_solidworks_dispatch(sw, version):
    from win32com.client import CLSIDToClass, gencache

    expected = SOLIDWORKS_API_MAJOR_BY_VERSION[normalize_solidworks_version(version)]
    type_library_source = 'application'
    try:
        type_info = sw._oleobj_.GetTypeInfo()
        type_library, _ = type_info.GetContainingTypeLib()
        dispatch_clsid = str(type_info.GetTypeAttr()[0])
    except (AttributeError, pythoncom.com_error):
        # Some SolidWorks automation proxies expose no type information.
        # Startup has already verified RevisionNumber; resolve that release's
        # registered library explicitly instead of accepting another year.
        type_library = pythoncom.LoadRegTypeLib(
            pythoncom.MakeIID('{83A33D31-27C5-11CE-BFD4-00400513BB57}'), expected, 0, 0
        )
        dispatch_clsid = '{83A33D22-27C5-11CE-BFD4-00400513BB57}'
        type_library_source = 'registered'
    attributes = type_library.GetLibAttr()
    library_id, lcid, major, minor = (
        attributes[0], attributes[1], attributes[3], attributes[4]
    )
    if major != expected:
        raise RuntimeError(
            'SolidWorks %s exposes unexpected type library major %s (expected %s)'
            % (version, major, expected)
        )
    module = gencache.EnsureModule(library_id, lcid, major, minor, bForDemand=True)
    if module is None:
        raise RuntimeError('Could not load the SolidWorks %s COM type library' % version)

    # Both releases share interface GUIDs. DispatchEx isolates the application,
    # but pywin32 can still select an already-loaded wrapper for the other year.
    # Rebind only this library's entries in this process; retain other libraries
    # and do not delete or reset the user's generated-wrapper cache.
    gencache.AddModuleToCache(library_id, lcid, major, minor, bFlushNow=False)
    CLSIDToClass.RegisterCLSIDsFromDict(module.CLSIDToClassMap)
    for clsid in module.CLSIDToPackageMap:
        if not CLSIDToClass.HasClass(clsid):
            continue
        existing = CLSIDToClass.GetClass(clsid)
        if existing.__module__.startswith(module.__name__ + '.'):
            continue
        actual_module = gencache.GetModuleForCLSID(clsid)
        if actual_module is not None:
            actual_class = _solidworks_wrapper_class(actual_module, clsid)
            if actual_class is not None:
                CLSIDToClass.RegisterCLSID(clsid, actual_class)

    actual_module = gencache.GetModuleForCLSID(dispatch_clsid)
    if actual_module is not None:
        actual_class = _solidworks_wrapper_class(actual_module, dispatch_clsid)
        if actual_class is not None:
            CLSIDToClass.RegisterCLSID(dispatch_clsid, actual_class)
    if not CLSIDToClass.HasClass(dispatch_clsid):
        raise RuntimeError('Could not bind the SolidWorks %s application COM interface' % version)
    wrapper = CLSIDToClass.GetClass(dispatch_clsid)
    if not (
        wrapper.__module__ == module.__name__
        or wrapper.__module__.startswith(module.__name__ + '.')
    ):
        raise RuntimeError('The SolidWorks application COM wrapper belongs to another version')
    return wrapper(sw._oleobj_), {
        'guid': str(library_id), 'lcid': lcid, 'major': major, 'minor': minor,
        'source': type_library_source,
    }
