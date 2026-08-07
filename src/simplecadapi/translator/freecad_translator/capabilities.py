"""Static capability declaration for the FreeCAD translator backend."""

from __future__ import annotations

from typing import Dict
from ...serializer import CANONICAL_OP_SET

from ..types import (
    BackendCapabilities,
    OperationCapability,
    SupportLevel,
    TranslationOutputKind,
    TranslationTarget,
)

BACKEND_NAME = "freecad"

_CANONICAL_OPS = (
    "make_point_rvertex",
    "make_line_redge",
    "make_circle_redge",
    "make_three_point_arc_redge",
    "make_angle_arc_redge",
    "make_spline_redge",
    "make_interpolated_spline_redge",
    "make_bezier_surface_rface",
    "fit_point_grid_rface",
    "make_ruled_surface_rface",
    "make_gordon_surface_rface",
    "make_surface_patch_rface",
    "make_loft_rshell",
    "sew_faces_rshell",
    "free_boundaries_rwirelist",
    "fill_holes_rshell",
    "make_helix_redge",
    "make_wire_from_edges_rwire",
    "make_face_from_wire_rface",
    "make_face_from_wires_rface",
    "make_sketch_rsketch",
    "add_point_rsketch",
    "add_line_rsketch",
    "add_circle_rsketch",
    "add_arc_rsketch",
    "add_bspline_rsketch",
    "make_constrain_coincident_rsketch",
    "make_constrain_point_on_rsketch",
    "make_constrain_horizontal_rsketch",
    "make_constrain_vertical_rsketch",
    "make_constrain_parallel_rsketch",
    "make_constrain_perpendicular_rsketch",
    "make_constrain_collinear_rsketch",
    "make_constrain_tangent_rsketch",
    "make_constrain_concentric_rsketch",
    "make_constrain_midpoint_rsketch",
    "make_constrain_symmetric_rsketch",
    "make_constrain_equal_length_rsketch",
    "make_constrain_equal_radius_rsketch",
    "make_constrain_distance_rsketch",
    "make_constrain_distance_x_rsketch",
    "make_constrain_distance_y_rsketch",
    "make_constrain_length_rsketch",
    "make_constrain_angle_rsketch",
    "make_constrain_radius_rsketch",
    "make_constrain_diameter_rsketch",
    "make_constrain_fix_rsketch",
    "make_wire_from_sketch_rwire",
    "make_face_from_sketch_rface",
    "make_box_rsolid",
    "make_cylinder_rsolid",
    "make_cone_rsolid",
    "make_sphere_rsolid",
    "make_material_rmaterial",
    "make_placement_rplacement",
    "make_identity_placement_rplacement",
    "make_part_rpart",
    "make_assign_material_rpart",
    "make_assembly_rassembly",
    "make_add_component_rassembly",
    "make_place_component_rassembly",
    "make_compound_from_assembly_rcompound",
    "make_face_connector_rconnector",
    "make_edge_connector_rconnector",
    "make_vertex_connector_rconnector",
    "make_placement_connector_rconnector",
    "make_add_connector_rpart",
    "make_add_connector_rassembly",
    "make_forward_connector_rassembly",
    "make_connector_ref_rconnectorref",
    "make_scalar_limit_rscalarlimit",
    "make_ground_component_rassembly",
    "make_unground_component_rassembly",
    "make_fixed_constraint_rassembly",
    "make_revolute_constraint_rassembly",
    "make_prismatic_constraint_rassembly",
    "make_gear_constraint_rassembly",
    "make_belt_constraint_rassembly",
    "make_rack_pinion_constraint_rassembly",
    "make_solve_assembly_constraints_rassembly",
    "make_extrude_rsolid",
    "make_revolve_rsolid",
    "make_loft_rsolid",
    "make_sweep_rsolid",
    "make_twisted_sweep_rsolid",
    "make_translate_rshape",
    "make_rotate_rshape",
    "make_mirror_rshape",
    "make_cut_rsolid",
    "make_union_rsolid",
    "make_intersect_rsolid",
    "make_2d_cut_rface",
    "make_2d_union_rface",
    "make_2d_intersect_rface",
    "make_fillet_rsolid",
    "make_chamfer_rsolid",
    "make_shell_rsolid",
    "make_select_rvertex",
    "make_select_redge",
    "make_select_rwire",
    "make_select_rface",
    "make_select_rshell",
    "make_select_rsolid",
    "apply_tag_rselection",
)

OP_SUPPORT: Dict[str, OperationCapability] = {
    op: OperationCapability(
        SupportLevel.UNSUPPORTED,
        reason="The FreeCAD runtime has no implementation for this canonical operation.",
    )
    for op in CANONICAL_OP_SET
}
for _op in _CANONICAL_OPS:
    OP_SUPPORT[_op] = OperationCapability(SupportLevel.NATIVE)
OP_SUPPORT["make_point_rvertex"] = OperationCapability(
    SupportLevel.UNSUPPORTED,
    reason="The FreeCAD point emitter has not been implemented yet.",
)
for _op, _reason in {
    "fit_point_grid_rface": (
        "FreeCAD approximates the point grid with its native BSplineSurface fitter; "
        "small rejected grids fall back to exact grid interpolation."
    ),
    "make_gordon_surface_rface": (
        "FreeCAD interpolates a BSpline surface through the profile-guide "
        "intersection grid because it has no native Gordon network builder."
    ),
    "make_surface_patch_rface": (
        "FreeCAD fills and trims the boundary because it cannot map the full "
        "support continuity and interior constraint contract parametrically."
    ),
    "free_boundaries_rwirelist": (
        "FreeCAD reconstructs free boundaries from shell edges referenced by one face."
    ),
    "fill_holes_rshell": (
        "FreeCAD fills selected closed boundary wires and sews them back to the shell."
    ),
}.items():
    OP_SUPPORT[_op] = OperationCapability(SupportLevel.EMULATED, reason=_reason)
OP_SUPPORT["make_twisted_sweep_rsolid"] = OperationCapability(
    SupportLevel.EMULATED,
    reason=(
        "FreeCAD has no equivalent auxiliary-spine feature; the backend emits "
        "a smooth solid loft through rotated and translated profile sections."
    ),
)
for _op in (
    "make_sketch_rsketch",
    "add_point_rsketch",
    "add_line_rsketch",
    "add_circle_rsketch",
    "add_arc_rsketch",
    "add_bspline_rsketch",
    "make_constrain_coincident_rsketch",
    "make_constrain_point_on_rsketch",
    "make_constrain_horizontal_rsketch",
    "make_constrain_vertical_rsketch",
    "make_constrain_parallel_rsketch",
    "make_constrain_perpendicular_rsketch",
    "make_constrain_collinear_rsketch",
    "make_constrain_tangent_rsketch",
    "make_constrain_concentric_rsketch",
    "make_constrain_midpoint_rsketch",
    "make_constrain_symmetric_rsketch",
    "make_constrain_equal_length_rsketch",
    "make_constrain_equal_radius_rsketch",
    "make_constrain_distance_rsketch",
    "make_constrain_distance_x_rsketch",
    "make_constrain_distance_y_rsketch",
    "make_constrain_length_rsketch",
    "make_constrain_angle_rsketch",
    "make_constrain_radius_rsketch",
    "make_constrain_diameter_rsketch",
    "make_constrain_fix_rsketch",
):
    OP_SUPPORT[_op] = OperationCapability(
        SupportLevel.METADATA_ONLY,
        reason="The graph node is preserved until a sketch promotion materializes it.",
    )
OP_SUPPORT["apply_tag_rselection"] = OperationCapability(
    SupportLevel.METADATA_ONLY,
    reason="Canonical TagBinding metadata is attached to the traceable geometry and visible result objects without creating a FreeCAD feature.",
)

CAPABILITIES = BackendCapabilities(
    backend_id=BACKEND_NAME,
    display_name="FreeCAD",
    input_schema_versions=("2.0",),
    targets=(
        TranslationTarget(
            target_id="freecad_script",
            output_kind=TranslationOutputKind.TEXT,
            media_type="text/x-python",
            extensions=(".py",),
            option_names=("document_name",),
        ),
        TranslationTarget(
            target_id="fcstd",
            output_kind=TranslationOutputKind.FILE,
            media_type="application/octet-stream",
            extensions=(".FCStd",),
            requires_external_runtime=True,
            option_names=("document_name", "freecad_cmd"),
        ),
    ),
    operations=OP_SUPPORT,
)

__all__ = ["BACKEND_NAME", "CAPABILITIES", "OP_SUPPORT"]
