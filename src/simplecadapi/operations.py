"""Compatibility facade for the SimpleCAD operator implementation modules.

Public callers should continue importing through ``simplecadapi`` or this module.
Assignments to facade symbols are mirrored into implementation modules so
existing monkeypatch-based integrations keep observing the executed binding.
"""

import sys as _sys
from types import ModuleType as _ModuleType

from . import _operation_support as _support
from . import _operators_boolean as _boolean
from . import _operators_features as _features
from . import _operators_geometry as _geometry
from . import _operators_product as _product
from . import _operators_selection as _selection
from . import _operators_sketch as _sketch
from . import _operators_transform as _transform
from ._operation_support import *
from ._operators_geometry import *
from ._operators_transform import *
from ._operators_boolean import *
from ._operators_product import *
from ._operators_sketch import *
from ._operators_selection import *
from ._operators_features import *

_IMPLEMENTATION_MODULES = (
    _support,
    _geometry,
    _transform,
    _boolean,
    _product,
    _sketch,
    _selection,
    _features,
)

__all__ = tuple(
    dict.fromkeys(
        name
        for module in _IMPLEMENTATION_MODULES
        for name in module.__all__
    )
)

_SYMBOL_MODULES = {
    name: tuple(
        module for module in _IMPLEMENTATION_MODULES if name in vars(module)
    )
    for name in __all__
}


class _OperationsFacade(_ModuleType):
    def __setattr__(self, name, value):
        for module in self.__dict__.get("_SYMBOL_MODULES", {}).get(name, ()):
            setattr(module, name, value)
        super().__setattr__(name, value)


_sys.modules[__name__].__class__ = _OperationsFacade
