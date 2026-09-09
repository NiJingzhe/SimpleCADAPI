"""CadQuery trace op → FTC block metadata (roles, slugs, registries).

Roles use the FTC closed vocabulary ``build | add | subtract | intersect |
modify | pattern | annotate``.  Build-family ops demote to ``add`` when a body
already exists (CadQuery accumulates solids into a compound; the FTC block for
that accumulation is an add block).
"""

from __future__ import annotations

# Trace ops the replayer understands.  Anything outside this set is recorded as
# an unsupported note by the translator (never silently dropped).
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

# Ops traced for context only; they never open an FTC block on their own.
CONTEXT_ONLY_OPS = frozenset({"faces", "edges", "workplane", "transformed", "center"})

# Ops that accumulate profile segments before a commit.
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

# FTC role per committing op.  Build-family ops become "add" when a solid
# already exists (see replay._ftc_role).
FTC_ROLE = {
    "box": "build",
    "cylinder": "build",
    "sphere": "build",
    "extrude": "build",
    "revolve": "build",
    "loft": "build",
    "sweep": "build",
    "cutBlind": "subtract",
    "cutThruAll": "subtract",
    "hole": "subtract",
    "cskHole": "subtract",
    "cut": "subtract",
    "union": "add",
    "intersect": "intersect",
    "fillet": "modify",
    "chamfer": "modify",
    "shell": "modify",
    "pattern_cut": "pattern",
    "pattern_extrude": "pattern",
}

# Stable slug per committing op (deduplicated with a numeric suffix on
# collision inside one program — a dedup counter, not a positional identity).
FTC_SLUG = {
    "box": "box",
    "cylinder": "cylinder",
    "sphere": "sphere",
    "extrude": "extrude",
    "revolve": "revolve",
    "loft": "loft",
    "sweep": "sweep",
    "cutBlind": "pocket-cut",
    "cutThruAll": "through-cut",
    "hole": "hole",
    "cskHole": "countersink-hole",
    "cut": "cut",
    "union": "union",
    "intersect": "intersect",
    "fillet": "fillet",
    "chamfer": "chamfer",
    "shell": "shell",
    "pattern_cut": "pattern-cut",
    "pattern_extrude": "pattern-bosses",
}
