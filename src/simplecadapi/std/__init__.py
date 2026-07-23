"""SimpleCAD standard parts library.

Each sub-module provides parameterised standard mechanical components
built entirely from the public SimpleCAD modelling API surface.

Modules:
    gear    — involute spur / straight-bevel / helical / herringbone gears
    bearing — ball bearing standard assemblies
    chain   — roller-chain sprockets
    fastener — parameterized bolts and nuts
    pin     — (future) dowel pins, flat keys, split pins
"""

from . import bearing, chain, fastener, gear

__all__ = ["bearing", "chain", "fastener", "gear"]
