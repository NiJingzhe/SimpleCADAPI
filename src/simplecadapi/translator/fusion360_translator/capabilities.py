"""Static capability declaration for the Fusion 360 translator backend."""

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

BACKEND_NAME = "fusion360"

_GEOMETRY_OPS = {
    "make_line_redge",
    "make_circle_redge",
    "make_three_point_arc_redge",
    "make_angle_arc_redge",
    "make_spline_redge",
    "make_helix_redge",
    "make_wire_from_edges_rwire",
    "make_face_from_wire_rface",
    "make_face_from_wires_rface",
    "make_extrude_rsolid",
    "make_revolve_rsolid",
    "make_loft_rsolid",
    "make_sweep_rsolid",
    "make_translate_rshape",
    "make_rotate_rshape",
    "make_mirror_rshape",
    "make_cut_rsolid",
    "make_union_rsolid",
    "make_intersect_rsolid",
    "make_fillet_rsolid",
    "make_chamfer_rsolid",
    "make_shell_rsolid",
    "make_select_redge",
    "make_select_rface",
}

_PRODUCT_OPS = {
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
    "make_connector_ref_rconnectorref",
    "make_scalar_limit_rscalarlimit",
    "make_ground_component_rassembly",
    "make_unground_component_rassembly",
    "make_fixed_constraint_rassembly",
    "make_revolute_constraint_rassembly",
    "make_prismatic_constraint_rassembly",
    "make_solve_assembly_constraints_rassembly",
}

OP_SUPPORT: Dict[str, OperationCapability] = {
    op: OperationCapability(
        SupportLevel.UNSUPPORTED,
        reason="The Fusion 360 runtime has no implementation for this canonical operation.",
    )
    for op in CANONICAL_OP_SET
}
for _op in _GEOMETRY_OPS:
    OP_SUPPORT[_op] = OperationCapability(
        SupportLevel.EMULATED,
        reason=(
            "The generated Fusion 360 script reconstructs this operation through "
            "Fusion API geometry, TemporaryBRep, or an explicitly enabled fallback."
        ),
    )
for _op in _PRODUCT_OPS:
    OP_SUPPORT[_op] = OperationCapability(
        SupportLevel.METADATA_ONLY,
        reason=(
            "The generated script preserves or consumes the product semantic data "
            "without promising an equivalent native Fusion feature."
        ),
    )

CAPABILITIES = BackendCapabilities(
    backend_id=BACKEND_NAME,
    display_name="Fusion360",
    input_schema_versions=("2.0",),
    targets=(
        TranslationTarget(
            target_id="fusion360_script",
            output_kind=TranslationOutputKind.TEXT,
            media_type="text/x-python",
            extensions=(".py",),
            requires_external_runtime=True,
            option_names=(
                "document_name",
                "result_node_ids",
                "selection_mode",
                "source_kernel_fallback",
            ),
        ),
    ),
    operations=OP_SUPPORT,
)

__all__ = ["BACKEND_NAME", "CAPABILITIES", "OP_SUPPORT"]
