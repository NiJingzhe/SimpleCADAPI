"""SimpleCAD standard parts library.

Each sub-module provides parameterised standard mechanical components
built entirely from the public SimpleCAD modelling API surface.

Modules:
    gear    — involute spur / helical / herringbone gears
    screw   — (future) threaded fasteners
    bearing — (future) ball / thrust bearings
    pin     — (future) dowel pins, flat keys, split pins
"""

from . import gear

__all__ = ["gear"]
