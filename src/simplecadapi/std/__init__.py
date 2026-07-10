"""SimpleCAD standard parts library.

Each sub-module provides parameterised standard mechanical components
built entirely from the public SimpleCAD modelling API surface.

Modules:
    gear    — involute spur / helical / herringbone gears
    bearing — ball bearing standard assemblies
    screw   — (future) threaded fasteners
    pin     — (future) dowel pins, flat keys, split pins
"""

from . import bearing, gear

__all__ = ["bearing", "gear"]
