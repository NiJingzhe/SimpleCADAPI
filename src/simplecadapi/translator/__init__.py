"""Translator backends for exporting SimpleCAD model JSON to external CAD systems."""

from importlib import import_module
from importlib.util import find_spec

from . import freecad_translator

__all__ = ["freecad_translator"]

# Contributed backends are optional so a FreeCAD-only cherry-pick remains usable.
for _backend_name in ("fusion360_translator", "solidworks_translator"):
    _qualified_name = f"{__name__}.{_backend_name}"
    if find_spec(_qualified_name) is None:
        continue
    globals()[_backend_name] = import_module(_qualified_name)
    __all__.append(_backend_name)

del _backend_name, _qualified_name
