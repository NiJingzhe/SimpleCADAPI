# SimpleCAD API Index

This index includes API docs generated from `operations.py`, `evolve.py`, `constraints.py`, and `ql.py`.

## Basic Creation

- [make_angle_arc_redge](make_angle_arc_redge.md) *(from operations.py)*
- [make_angle_arc_rwire](make_angle_arc_rwire.md) *(from operations.py)*
- [make_box_rscalarfield](make_box_rscalarfield.md) *(from field.py)*
- [make_box_rsolid](make_box_rsolid.md) *(from operations.py)*
- [make_capsule_rscalarfield](make_capsule_rscalarfield.md) *(from field.py)*
- [make_circle_redge](make_circle_redge.md) *(from operations.py)*
- [make_circle_rface](make_circle_rface.md) *(from operations.py)*
- [make_circle_rwire](make_circle_rwire.md) *(from operations.py)*
- [make_cone_rsolid](make_cone_rsolid.md) *(from operations.py)*
- [make_cylinder_rsolid](make_cylinder_rsolid.md) *(from operations.py)*
- [make_ellipsoid_rscalarfield](make_ellipsoid_rscalarfield.md) *(from field.py)*
- [make_face_from_wire_rface](make_face_from_wire_rface.md) *(from operations.py)*
- [make_field_surface_rsolid](make_field_surface_rsolid.md) *(from operations.py)*
- [make_helix_redge](make_helix_redge.md) *(from operations.py)*
- [make_helix_rwire](make_helix_rwire.md) *(from operations.py)*
- [make_line_redge](make_line_redge.md) *(from operations.py)*
- [make_point_rvertex](make_point_rvertex.md) *(from operations.py)*
- [make_polyline_rwire](make_polyline_rwire.md) *(from operations.py)*
- [make_rectangle_rface](make_rectangle_rface.md) *(from operations.py)*
- [make_rectangle_rwire](make_rectangle_rwire.md) *(from operations.py)*
- [make_segment_redge](make_segment_redge.md) *(from operations.py)*
- [make_segment_rwire](make_segment_rwire.md) *(from operations.py)*
- [make_sphere_rscalarfield](make_sphere_rscalarfield.md) *(from field.py)*
- [make_sphere_rsolid](make_sphere_rsolid.md) *(from operations.py)*
- [make_spline_redge](make_spline_redge.md) *(from operations.py)*
- [make_spline_rwire](make_spline_rwire.md) *(from operations.py)*
- [make_three_point_arc_redge](make_three_point_arc_redge.md) *(from operations.py)*
- [make_three_point_arc_rwire](make_three_point_arc_rwire.md) *(from operations.py)*
- [make_wire_from_edges_rwire](make_wire_from_edges_rwire.md) *(from operations.py)*

## Transforms

- [mirror_shape](mirror_shape.md) *(from operations.py)*
- [rotate_rscalarfield](rotate_rscalarfield.md) *(from field.py)*
- [rotate_shape](rotate_shape.md) *(from operations.py)*
- [translate_rscalarfield](translate_rscalarfield.md) *(from field.py)*
- [translate_shape](translate_shape.md) *(from operations.py)*

## 3D Operations

- [extrude_rsolid](extrude_rsolid.md) *(from operations.py)*
- [loft_rsolid](loft_rsolid.md) *(from operations.py)*
- [revolve_rsolid](revolve_rsolid.md) *(from operations.py)*
- [sweep_rsolid](sweep_rsolid.md) *(from operations.py)*

## Tagging and Selection

- [select_edges_by_tag](select_edges_by_tag.md) *(from operations.py)*
- [select_faces_by_tag](select_faces_by_tag.md) *(from operations.py)*
- [set_tag](set_tag.md) *(from operations.py)*

## Boolean Operations

- [cut_rsolidlist](cut_rsolidlist.md) *(from operations.py)*
- [intersect_rscalarfield](intersect_rscalarfield.md) *(from field.py)*
- [intersect_rsolidlist](intersect_rsolidlist.md) *(from operations.py)*
- [union_rscalarfield](union_rscalarfield.md) *(from field.py)*
- [union_rsolidlist](union_rsolidlist.md) *(from operations.py)*

## Export

- [export_step](export_step.md) *(from operations.py)*
- [export_stl](export_stl.md) *(from operations.py)*

## Advanced Features

- [chamfer_rsolid](chamfer_rsolid.md) *(from operations.py)*
- [fillet_rsolid](fillet_rsolid.md) *(from operations.py)*
- [helical_sweep_rsolid](helical_sweep_rsolid.md) *(from operations.py)*
- [shell_rsolid](shell_rsolid.md) *(from operations.py)*

## Evolve

- [make_n_hole_flange_rsolid](make_n_hole_flange_rsolid.md) *(from evolve.py)*
- [make_naca_propeller_blade_rsolid](make_naca_propeller_blade_rsolid.md) *(from evolve.py)*
- [make_threaded_rod_rsolid](make_threaded_rod_rsolid.md) *(from evolve.py)*

## Assembly Constraints

- [add_part_rassembly](add_part_rassembly.md) *(from constraints.py)*
- [clear_constraints_rassembly](clear_constraints_rassembly.md) *(from constraints.py)*
- [clone_assembly_rassembly](clone_assembly_rassembly.md) *(from constraints.py)*
- [constrain_coincident_rassembly](constrain_coincident_rassembly.md) *(from constraints.py)*
- [constrain_concentric_rassembly](constrain_concentric_rassembly.md) *(from constraints.py)*
- [constrain_distance_rassembly](constrain_distance_rassembly.md) *(from constraints.py)*
- [constrain_offset_rassembly](constrain_offset_rassembly.md) *(from constraints.py)*
- [make_assembly_rassembly](make_assembly_rassembly.md) *(from constraints.py)*
- [rotate_part_rassembly](rotate_part_rassembly.md) *(from constraints.py)*
- [solve_assembly_rresult](solve_assembly_rresult.md) *(from constraints.py)*
- [stack](stack.md) *(from constraints.py)*
- [stack_rassembly](stack_rassembly.md) *(from constraints.py)*
- [translate_part_rassembly](translate_part_rassembly.md) *(from constraints.py)*

## Other

- [and_](and_.md) *(from ql.py)*
- [bounds_rbbox](bounds_rbbox.md) *(from field.py)*
- [eval_rarray](eval_rarray.md) *(from field.py)*
- [eval_rscalar](eval_rscalar.md) *(from field.py)*
- [geo](geo.md) *(from ql.py)*
- [linear_pattern_rsolidlist](linear_pattern_rsolidlist.md) *(from operations.py)*
- [meta](meta.md) *(from ql.py)*
- [not_](not_.md) *(from ql.py)*
- [or_](or_.md) *(from ql.py)*
- [radial_pattern_rsolidlist](radial_pattern_rsolidlist.md) *(from operations.py)*
- [render_screenshot_rpath](render_screenshot_rpath.md) *(from operations.py)*
- [scale_rscalarfield](scale_rscalarfield.md) *(from field.py)*
- [select](select.md) *(from ql.py)*
- [smooth_subtract_rscalarfield](smooth_subtract_rscalarfield.md) *(from field.py)*
- [smooth_union_rscalarfield](smooth_union_rscalarfield.md) *(from field.py)*
- [subtract_rscalarfield](subtract_rscalarfield.md) *(from field.py)*
- [tag](tag.md) *(from ql.py)*
- [value](value.md) *(from ql.py)*
