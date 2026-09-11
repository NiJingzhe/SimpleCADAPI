"""Plan human-readable SolidWorks feature names from the canonical DAG."""

from __future__ import annotations

from typing import Dict

_OPERATION_LABELS: Dict[str, str] = {
    "make_box_rsolid": "Box",
    "make_cylinder_rsolid": "Cylinder",
    "make_cone_rsolid": "Cone",
    "make_sphere_rsolid": "Sphere",
    "make_point_rvertex": "Point",
    "make_line_redge": "Line",
    "make_circle_redge": "Circle",
    "make_angle_arc_redge": "Arc",
    "make_three_point_arc_redge": "Three Point Arc",
    "make_spline_redge": "Spline",
    "make_interpolated_spline_redge": "Interpolated Spline",
    "make_helix_redge": "Helix",
    "make_wire_from_edges_rwire": "Profile",
    "make_face_from_wire_rface": "Profile",
    "make_face_from_wires_rface": "Profile",
    "make_sketch_rsketch": "Sketch",
    "make_wire_from_sketch_rwire": "Sketch",
    "make_face_from_sketch_rface": "Sketch",
    "make_extrude_rsolid": "Extrude",
    "make_revolve_rsolid": "Revolve",
    "make_loft_rsolid": "Loft",
    "make_sweep_rsolid": "Sweep",
    "make_twisted_sweep_rsolid": "Twisted Sweep",
    "make_cut_rsolid": "Cut",
    "make_union_rsolid": "Union",
    "make_intersect_rsolid": "Intersection",
    "make_2d_cut_rface": "Profile Cut",
    "make_2d_union_rface": "Profile Union",
    "make_2d_intersect_rface": "Profile Intersection",
    "make_fillet_rsolid": "Fillet",
    "make_chamfer_rsolid": "Chamfer",
    "make_shell_rsolid": "Shell",
    "make_mirror_rshape": "Mirror",
    "make_translate_rshape": "Move",
    "make_rotate_rshape": "Rotate",
    "make_select_rvertex": "Vertex Selection",
    "make_select_redge": "Edge Selection",
    "make_select_rwire": "Wire Selection",
    "make_select_rface": "Face Selection",
    "make_select_rshell": "Shell Selection",
    "make_select_rsolid": "Solid Selection",
    "apply_tag_rselection": "Tag",
    "make_part_rpart": "Part",
    "make_assembly_rassembly": "Assembly",
    "make_add_component_rassembly": "Component",
    "make_place_component_rassembly": "Component Placement",
    "make_material_rmaterial": "Material",
    "make_placement_rplacement": "Placement",
    "make_identity_placement_rplacement": "Placement",
    "make_compound_from_assembly_rcompound": "Assembly Result",
    "make_ground_component_rassembly": "Ground Component",
    "make_unground_component_rassembly": "Unground Component",
    "make_fixed_constraint_rassembly": "Fixed Constraint",
    "make_revolute_constraint_rassembly": "Revolute Constraint",
    "make_prismatic_constraint_rassembly": "Prismatic Constraint",
    "make_gear_constraint_rassembly": "Gear Constraint",
    "make_belt_constraint_rassembly": "Belt Constraint",
    "make_rack_pinion_constraint_rassembly": "Rack Pinion Constraint",
    "make_solve_assembly_constraints_rassembly": "Solve Assembly",
    "make_connector_ref_rconnectorref": "Connector Reference",
    "make_scalar_limit_rscalarlimit": "Scalar Limit",
}


def operation_label(op: str) -> str:
    """Return the human-readable label for one canonical operation."""

    return _OPERATION_LABELS.get(str(op), str(op))


__all__ = ["operation_label"]
