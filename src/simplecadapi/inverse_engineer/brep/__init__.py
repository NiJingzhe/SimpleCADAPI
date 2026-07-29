"""STEP BREP inspection, comparison, rendering, and slice diagnostics.

This subpackage is intentionally imported as a namespace instead of adding its
specialized OCP utilities to the top-level SimpleCAD modeling API.
"""

from .agent_tools import (
    AGENT_TOOL_NAMES,
    AgentTool,
    BRepToolError,
    agent_tool_schemas,
    call_agent_tool,
)
from .compare import (
    BRepComparison,
    InspectionSummaryComparison,
    compare_inspections,
    compare_shapes,
    compare_steps,
)
from .diagnostics import (
    build_difference_regions,
    compare_boundary_distance,
    compare_entities,
    compare_global_properties,
    compare_sections,
    compute_material_difference,
    evaluate_result,
    find_nearby_entities,
)
from .inspect import BRepInspection, inspect_shape, inspect_step
from .io import load_step, shape_mass
from .model import (
    BRepEntityError,
    BRepModel,
    clear_step_model_cache,
    get_model_summary,
    index_shape,
    inspect_entity,
    load_step_model,
)
from .parity import (
    EntityInspectionParity,
    compare_model_to_inspection,
    compare_step_to_inspection,
)
from .queries import (
    extract_face_boundaries,
    get_topology_neighborhood,
    make_section,
    measure_relation,
    probe_point,
    select_region_entities,
)
from .render import (
    DEFAULT_VIEWS,
    render_region,
    render_shape_views,
    render_step_views,
)
from .slices import (
    SliceComparison,
    SlicePanelResult,
    SliceSpec,
    center_slice_specs,
    compare_shape_slices,
    compare_step_slices,
)

__all__ = [
    "AGENT_TOOL_NAMES",
    "AgentTool",
    "BRepComparison",
    "BRepEntityError",
    "BRepInspection",
    "BRepModel",
    "BRepToolError",
    "DEFAULT_VIEWS",
    "InspectionSummaryComparison",
    "EntityInspectionParity",
    "SliceComparison",
    "SlicePanelResult",
    "SliceSpec",
    "agent_tool_schemas",
    "build_difference_regions",
    "center_slice_specs",
    "compare_boundary_distance",
    "compare_entities",
    "compare_global_properties",
    "compare_inspections",
    "compare_model_to_inspection",
    "compare_sections",
    "compare_shape_slices",
    "compare_shapes",
    "compare_step_slices",
    "compare_steps",
    "compare_step_to_inspection",
    "clear_step_model_cache",
    "call_agent_tool",
    "compute_material_difference",
    "evaluate_result",
    "extract_face_boundaries",
    "find_nearby_entities",
    "get_model_summary",
    "get_topology_neighborhood",
    "index_shape",
    "inspect_entity",
    "inspect_shape",
    "inspect_step",
    "load_step",
    "load_step_model",
    "make_section",
    "measure_relation",
    "probe_point",
    "render_region",
    "render_shape_views",
    "render_step_views",
    "select_region_entities",
    "shape_mass",
]
