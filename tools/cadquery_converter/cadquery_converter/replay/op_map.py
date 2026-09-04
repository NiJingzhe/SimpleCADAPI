"""CQ trace op → SimpleCAD API mapping registry (plan Phase 2.1)."""

from __future__ import annotations

# Supported trace ops replayed by trace_replay.py.  Used for coverage reporting.
SUPPORTED_TRACE_OPS = frozenset(
    {
        "Workplane",
        "box",
        "cylinder",
        "sphere",
        "circle",
        "rect",
        "polygon",
        "polyline",
        "moveTo",
        "lineTo",
        "threePointArc",
        "close",
        "mirrorX",
        "mirrorY",
        "extrude",
        "cutBlind",
        "cutThruAll",
        "hole",
        "cskHole",
        "revolve",
        "loft",
        "sweep",
        "cut",
        "union",
        "intersect",
        "fillet",
        "chamfer",
        "shell",
        "faces",
        "edges",
        "workplane",
        "transformed",
        "center",
        "rarray",
        "polarArray",
        "pushPoints",
        "slot2D",
        "spline",
    }
)

# Ops that are traced for context but intentionally not replayed as features.
CONTEXT_ONLY_OPS = frozenset({"faces", "edges", "workplane", "transformed", "center"})

# Committing ops → CAD feature-manager kind (semantic unit, not API 1:1).
COMMITTING_KIND = {
    "box": "Box",
    "cylinder": "Cylinder",
    "sphere": "Sphere",
    "extrude": "Extrude",
    "cutBlind": "Cut",
    "cutThruAll": "Cut",
    "hole": "Hole",
    "cskHole": "Hole",
    "revolve": "Revolve",
    "loft": "Loft",
    "sweep": "Sweep",
    "cut": "Cut",
    "union": "Join",
    "intersect": "Intersect",
    "fillet": "Fillet",
    "chamfer": "Chamfer",
}

PROFILE_OPS = frozenset(
    {
        "circle",
        "rect",
        "polygon",
        "polyline",
        "moveTo",
        "lineTo",
        "threePointArc",
        "close",
        "mirrorX",
        "mirrorY",
        "slot2D",
        "spline",
    }
)

PATTERN_SETUP_OPS = frozenset({"rarray", "polarArray", "pushPoints"})

SLUG_FOR_KIND = {
    "Box": "box",
    "Cylinder": "cylinder",
    "Sphere": "sphere",
    "Extrude": "extrude",
    "Cut": "cut",
    "Hole": "hole",
    "Revolve": "revolve",
    "Loft": "loft",
    "Sweep": "sweep",
    "Join": "union",
    "Intersect": "intersect",
    "Fillet": "fillet",
    "Chamfer": "chamfer",
}
