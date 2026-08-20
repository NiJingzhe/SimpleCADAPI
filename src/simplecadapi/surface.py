"""Public surface modeling namespace.

The constructors are implemented in the focused operator module so they
participate in the same graph, coordinate-system, tagging, and error contracts.
"""

from ._operators_geometry import (
    SurfaceBoundary,
    SurfaceFillingSettings,
    fill_holes_rshell,
    fit_point_grid_rface,
    free_boundaries_rwirelist,
    make_bezier_surface_rface,
    make_cylindrical_surface_rface,
    make_gordon_surface_rface,
    loft_rshell,
    make_ruled_surface_rface,
    make_surface_patch_rface,
    make_solid_from_shell_rsolid,
    sew_faces_rshell,
    trim_surface_rface,
)

__all__ = [
    "SurfaceBoundary",
    "SurfaceFillingSettings",
    "make_bezier_surface_rface",
    "make_cylindrical_surface_rface",
    "fit_point_grid_rface",
    "make_ruled_surface_rface",
    "make_gordon_surface_rface",
    "make_surface_patch_rface",
    "loft_rshell",
    "trim_surface_rface",
    "sew_faces_rshell",
    "make_solid_from_shell_rsolid",
    "free_boundaries_rwirelist",
    "fill_holes_rshell",
]
