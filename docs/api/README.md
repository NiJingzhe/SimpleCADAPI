# SimpleCAD API Index

This index includes API docs generated from `operations.py`, `evolve.py`, `constraints.py`, and `ql.py`.

## Basic Creation

- [make_angle_arc_redge](make_angle_arc_redge.md) *(来自 operations.py)*
- [make_angle_arc_rwire](make_angle_arc_rwire.md) *(来自 operations.py)*
- [make_box_rscalarfield](make_box_rscalarfield.md) *(来自 field.py)*
- [make_box_rsolid](make_box_rsolid.md) *(来自 operations.py)*
- [make_capsule_rscalarfield](make_capsule_rscalarfield.md) *(来自 field.py)*
- [make_circle_redge](make_circle_redge.md) *(来自 operations.py)*
- [make_circle_rface](make_circle_rface.md) *(来自 operations.py)*
- [make_circle_rwire](make_circle_rwire.md) *(来自 operations.py)*
- [make_cone_rsolid](make_cone_rsolid.md) *(来自 operations.py)*
- [make_cylinder_rsolid](make_cylinder_rsolid.md) *(来自 operations.py)*
- [make_ellipsoid_rscalarfield](make_ellipsoid_rscalarfield.md) *(来自 field.py)*
- [make_face_from_wire_rface](make_face_from_wire_rface.md) *(来自 operations.py)*
- [make_field_surface_rsolid](make_field_surface_rsolid.md) *(来自 operations.py)*
- [make_helix_redge](make_helix_redge.md) *(来自 operations.py)*
- [make_helix_rwire](make_helix_rwire.md) *(来自 operations.py)*
- [make_line_redge](make_line_redge.md) *(来自 operations.py)*
- [make_point_rvertex](make_point_rvertex.md) *(来自 operations.py)*
- [make_polyline_rwire](make_polyline_rwire.md) *(来自 operations.py)*
- [make_rectangle_rface](make_rectangle_rface.md) *(来自 operations.py)*
- [make_rectangle_rwire](make_rectangle_rwire.md) *(来自 operations.py)*
- [make_segment_redge](make_segment_redge.md) *(来自 operations.py)*
- [make_segment_rwire](make_segment_rwire.md) *(来自 operations.py)*
- [make_sphere_rscalarfield](make_sphere_rscalarfield.md) *(来自 field.py)*
- [make_sphere_rsolid](make_sphere_rsolid.md) *(来自 operations.py)*
- [make_spline_redge](make_spline_redge.md) *(来自 operations.py)*
- [make_spline_rwire](make_spline_rwire.md) *(来自 operations.py)*
- [make_three_point_arc_redge](make_three_point_arc_redge.md) *(来自 operations.py)*
- [make_three_point_arc_rwire](make_three_point_arc_rwire.md) *(来自 operations.py)*
- [make_wire_from_edges_rwire](make_wire_from_edges_rwire.md) *(来自 operations.py)*

## Transforms

- [mirror_shape](mirror_shape.md) *(来自 operations.py)*
- [rotate_rscalarfield](rotate_rscalarfield.md) *(来自 field.py)*
- [rotate_shape](rotate_shape.md) *(来自 operations.py)*
- [translate_rscalarfield](translate_rscalarfield.md) *(来自 field.py)*
- [translate_shape](translate_shape.md) *(来自 operations.py)*

## 3D Operations

- [extrude_rsolid](extrude_rsolid.md) *(来自 operations.py)*
- [loft_rsolid](loft_rsolid.md) *(来自 operations.py)*
- [revolve_rsolid](revolve_rsolid.md) *(来自 operations.py)*
- [sweep_rsolid](sweep_rsolid.md) *(来自 operations.py)*

## Tagging and Selection

- [select_edges_by_tag](select_edges_by_tag.md) *(来自 operations.py)*
- [select_faces_by_tag](select_faces_by_tag.md) *(来自 operations.py)*
- [set_tag](set_tag.md) *(来自 operations.py)*

## Boolean Operations

- [cut_rsolidlist](cut_rsolidlist.md) *(来自 operations.py)*
- [intersect_rscalarfield](intersect_rscalarfield.md) *(来自 field.py)*
- [intersect_rsolidlist](intersect_rsolidlist.md) *(来自 operations.py)*
- [union_rscalarfield](union_rscalarfield.md) *(来自 field.py)*
- [union_rsolidlist](union_rsolidlist.md) *(来自 operations.py)*

## Export

- [export_step](export_step.md) *(来自 operations.py)*
- [export_stl](export_stl.md) *(来自 operations.py)*

## Advanced Features

- [chamfer_rsolid](chamfer_rsolid.md) *(来自 operations.py)*
- [fillet_rsolid](fillet_rsolid.md) *(来自 operations.py)*
- [helical_sweep_rsolid](helical_sweep_rsolid.md) *(来自 operations.py)*
- [shell_rsolid](shell_rsolid.md) *(来自 operations.py)*

## Evolve

- [make_n_hole_flange_rsolid](make_n_hole_flange_rsolid.md) *(来自 evolve.py)*
- [make_naca_propeller_blade_rsolid](make_naca_propeller_blade_rsolid.md) *(来自 evolve.py)*
- [make_threaded_rod_rsolid](make_threaded_rod_rsolid.md) *(来自 evolve.py)*

## Assembly Constraints

- [add_part_rassembly](add_part_rassembly.md) *(来自 constraints.py)*
- [clear_constraints_rassembly](clear_constraints_rassembly.md) *(来自 constraints.py)*
- [clone_assembly_rassembly](clone_assembly_rassembly.md) *(来自 constraints.py)*
- [constrain_coincident_rassembly](constrain_coincident_rassembly.md) *(来自 constraints.py)*
- [constrain_concentric_rassembly](constrain_concentric_rassembly.md) *(来自 constraints.py)*
- [constrain_distance_rassembly](constrain_distance_rassembly.md) *(来自 constraints.py)*
- [constrain_offset_rassembly](constrain_offset_rassembly.md) *(来自 constraints.py)*
- [make_assembly_rassembly](make_assembly_rassembly.md) *(来自 constraints.py)*
- [rotate_part_rassembly](rotate_part_rassembly.md) *(来自 constraints.py)*
- [solve_assembly_rresult](solve_assembly_rresult.md) *(来自 constraints.py)*
- [stack](stack.md) *(来自 constraints.py)*
- [stack_rassembly](stack_rassembly.md) *(来自 constraints.py)*
- [translate_part_rassembly](translate_part_rassembly.md) *(来自 constraints.py)*

## Other

- [and_](and_.md) *(来自 ql.py)*
- [bounds_rbbox](bounds_rbbox.md) *(来自 field.py)*
- [eval_rarray](eval_rarray.md) *(来自 field.py)*
- [eval_rscalar](eval_rscalar.md) *(来自 field.py)*
- [geo](geo.md) *(来自 ql.py)*
- [linear_pattern_rsolidlist](linear_pattern_rsolidlist.md) *(来自 operations.py)*
- [meta](meta.md) *(来自 ql.py)*
- [not_](not_.md) *(来自 ql.py)*
- [or_](or_.md) *(来自 ql.py)*
- [radial_pattern_rsolidlist](radial_pattern_rsolidlist.md) *(来自 operations.py)*
- [render_screenshot_rpath](render_screenshot_rpath.md) *(来自 operations.py)*
- [scale_rscalarfield](scale_rscalarfield.md) *(来自 field.py)*
- [select](select.md) *(来自 ql.py)*
- [smooth_subtract_rscalarfield](smooth_subtract_rscalarfield.md) *(来自 field.py)*
- [smooth_union_rscalarfield](smooth_union_rscalarfield.md) *(来自 field.py)*
- [subtract_rscalarfield](subtract_rscalarfield.md) *(来自 field.py)*
- [tag](tag.md) *(来自 ql.py)*
- [value](value.md) *(来自 ql.py)*
