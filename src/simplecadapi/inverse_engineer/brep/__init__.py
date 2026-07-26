"""STEP BREP inspection, comparison, rendering, and slice diagnostics.

This subpackage is intentionally imported as a namespace instead of adding its
specialized OCP utilities to the top-level SimpleCAD modeling API.
"""

from .compare import (
    BRepComparison,
    InspectionSummaryComparison,
    compare_inspections,
    compare_shapes,
    compare_steps,
)
from .inspect import BRepInspection, inspect_shape, inspect_step
from .io import load_step, shape_mass
from .render import DEFAULT_VIEWS, render_shape_views, render_step_views
from .slices import (
    SliceComparison,
    SlicePanelResult,
    SliceSpec,
    center_slice_specs,
    compare_shape_slices,
    compare_step_slices,
)

__all__ = [
    "BRepComparison",
    "BRepInspection",
    "DEFAULT_VIEWS",
    "InspectionSummaryComparison",
    "SliceComparison",
    "SlicePanelResult",
    "SliceSpec",
    "center_slice_specs",
    "compare_inspections",
    "compare_shape_slices",
    "compare_shapes",
    "compare_step_slices",
    "compare_steps",
    "inspect_shape",
    "inspect_step",
    "load_step",
    "render_shape_views",
    "render_step_views",
    "shape_mass",
]
