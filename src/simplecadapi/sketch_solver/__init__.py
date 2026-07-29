"""Pluggable sketch constraint solver backends.

Backends consume SimpleCAD's backend-neutral ``Sketch`` document and return
``SketchSolveResult``.  Import backend implementations directly when selecting
one explicitly; the package-level registry only owns selection policy.
"""

from .backend import (
    SketchSolverBackend,
    SketchSolverOptions,
    get_default_sketch_solver_backend,
    get_sketch_solver_backend,
    register_sketch_solver_backend,
    set_default_sketch_solver_backend,
    sketch_solver_backend,
)

__all__ = [
    "SketchSolverBackend",
    "SketchSolverOptions",
    "get_default_sketch_solver_backend",
    "get_sketch_solver_backend",
    "register_sketch_solver_backend",
    "set_default_sketch_solver_backend",
    "sketch_solver_backend",
]
