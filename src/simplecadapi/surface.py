"""Public surface modeling namespace.

The constructors are implemented in :mod:`simplecadapi.operations` so they
participate in the same graph, coordinate-system, tagging, and error contracts
as the rest of the SDK. This module provides the focused namespace requested by
surface-heavy clients.
"""

from .operations import (
    SurfaceBoundary,
    SurfaceFillingSettings,
    fill_holes_rshell,
    fit_point_grid_rface,
    free_boundaries_rwirelist,
    make_bezier_surface_rface,
    make_gordon_surface_rface,
    make_loft_rshell,
    make_ruled_surface_rface,
    make_surface_patch_rface,
    sew_faces_rshell,
)

__all__ = [
    "SurfaceBoundary",
    "SurfaceFillingSettings",
    "make_bezier_surface_rface",
    "fit_point_grid_rface",
    "make_ruled_surface_rface",
    "make_gordon_surface_rface",
    "make_surface_patch_rface",
    "make_loft_rshell",
    "sew_faces_rshell",
    "free_boundaries_rwirelist",
    "fill_holes_rshell",
]
