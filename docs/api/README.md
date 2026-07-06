# SimpleCAD API Index

This index includes generated docs for the public SimpleCAD API surface, including geometry operations, graph/model JSON workflows, expressions, QL, and export helpers.

## Import Surfaces

- Entries marked `top-level` are exported from `simplecadapi` and can be imported with `from simplecadapi import <name>`.
- Entries marked `submodule` are public through the listed submodule, such as `simplecadapi.ql`.
- Entries marked `translator backend` are public only through `simplecadapi.translator.<backend>`.

## Basic Creation

- [make_2d_cut_rface](make_2d_cut_rface.md) *(from operations.py)* `top-level`
- [make_2d_intersect_rface](make_2d_intersect_rface.md) *(from operations.py)* `top-level`
- [make_2d_union_rface](make_2d_union_rface.md) *(from operations.py)* `top-level`
- [make_angle_arc_redge](make_angle_arc_redge.md) *(from operations.py)* `top-level`
- [make_angle_arc_rwire](make_angle_arc_rwire.md) *(from operations.py)* `top-level`
- [make_assembly_rassembly](make_assembly_rassembly.md) *(from operations.py)* `top-level`
- [make_box_rsolid](make_box_rsolid.md) *(from operations.py)* `top-level`
- [make_circle_redge](make_circle_redge.md) *(from operations.py)* `top-level`
- [make_circle_rface](make_circle_rface.md) *(from operations.py)* `top-level`
- [make_circle_rwire](make_circle_rwire.md) *(from operations.py)* `top-level`
- [make_compound_from_assembly_rcompound](make_compound_from_assembly_rcompound.md) *(from operations.py)* `top-level`
- [make_cone_rsolid](make_cone_rsolid.md) *(from operations.py)* `top-level`
- [make_connector_ref_rconnectorref](make_connector_ref_rconnectorref.md) *(from operations.py)* `top-level`
- [make_cylinder_rsolid](make_cylinder_rsolid.md) *(from operations.py)* `top-level`
- [make_edge_connector_rconnector](make_edge_connector_rconnector.md) *(from operations.py)* `top-level`
- [make_face_connector_rconnector](make_face_connector_rconnector.md) *(from operations.py)* `top-level`
- [make_face_from_sketch_rface](make_face_from_sketch_rface.md) *(from operations.py)* `top-level`
- [make_face_from_wire_rface](make_face_from_wire_rface.md) *(from operations.py)* `top-level`
- [make_face_from_wires_rface](make_face_from_wires_rface.md) *(from operations.py)* `top-level`
- [make_helix_redge](make_helix_redge.md) *(from operations.py)* `top-level`
- [make_helix_rwire](make_helix_rwire.md) *(from operations.py)* `top-level`
- [make_line_redge](make_line_redge.md) *(from operations.py)* `top-level`
- [make_material_rmaterial](make_material_rmaterial.md) *(from operations.py)* `top-level`
- [make_part_rpart](make_part_rpart.md) *(from operations.py)* `top-level`
- [make_placement_connector_rconnector](make_placement_connector_rconnector.md) *(from operations.py)* `top-level`
- [make_placement_rplacement](make_placement_rplacement.md) *(from operations.py)* `top-level`
- [make_point_rvertex](make_point_rvertex.md) *(from operations.py)* `top-level`
- [make_polyline_rwire](make_polyline_rwire.md) *(from operations.py)* `top-level`
- [make_rectangle_rface](make_rectangle_rface.md) *(from operations.py)* `top-level`
- [make_rectangle_rwire](make_rectangle_rwire.md) *(from operations.py)* `top-level`
- [make_scalar_limit_rscalarlimit](make_scalar_limit_rscalarlimit.md) *(from operations.py)* `top-level`
- [make_segment_redge](make_segment_redge.md) *(from operations.py)* `top-level`
- [make_segment_rwire](make_segment_rwire.md) *(from operations.py)* `top-level`
- [make_sketch_rsketch](make_sketch_rsketch.md) *(from operations.py)* `top-level`
- [make_sphere_rsolid](make_sphere_rsolid.md) *(from operations.py)* `top-level`
- [make_spline_redge](make_spline_redge.md) *(from operations.py)* `top-level`
- [make_spline_rwire](make_spline_rwire.md) *(from operations.py)* `top-level`
- [make_three_point_arc_redge](make_three_point_arc_redge.md) *(from operations.py)* `top-level`
- [make_three_point_arc_rwire](make_three_point_arc_rwire.md) *(from operations.py)* `top-level`
- [make_vertex_connector_rconnector](make_vertex_connector_rconnector.md) *(from operations.py)* `top-level`
- [make_wire_from_edges_rwire](make_wire_from_edges_rwire.md) *(from operations.py)* `top-level`
- [make_wire_from_sketch_rwire](make_wire_from_sketch_rwire.md) *(from operations.py)* `top-level`

## Transforms

- [mirror_shape](mirror_shape.md) *(from operations.py)* `top-level`
- [rotate_shape](rotate_shape.md) *(from operations.py)* `top-level`
- [translate_shape](translate_shape.md) *(from operations.py)* `top-level`

## 3D Operations

- [extrude_rsolid](extrude_rsolid.md) *(from operations.py)* `top-level`
- [loft_rsolid](loft_rsolid.md) *(from operations.py)* `top-level`
- [revolve_rsolid](revolve_rsolid.md) *(from operations.py)* `top-level`
- [sweep_rsolid](sweep_rsolid.md) *(from operations.py)* `top-level`

## Tagging and Selection

- [apply_tag](apply_tag.md) *(from operations.py)* `top-level`
- [list_tags](list_tags.md) *(from operations.py)* `top-level`
- [select_edges_by_tag](select_edges_by_tag.md) *(from operations.py)* `top-level`
- [select_faces_by_tag](select_faces_by_tag.md) *(from operations.py)* `top-level`

## Boolean Operations

- [cut_rsolid](cut_rsolid.md) *(from operations.py)* `top-level`
- [intersect_rsolid](intersect_rsolid.md) *(from operations.py)* `top-level`
- [union_rsolid](union_rsolid.md) *(from operations.py)* `top-level`

## Export

- [export_step](export_step.md) *(from operations.py)* `top-level`
- [export_stl](export_stl.md) *(from operations.py)* `top-level`

## FreeCAD Translation

- [FreeCADScriptTranslator](FreeCADScriptTranslator.md) *(from translator/freecad_translator/script_translator.py)* `translator backend`
- [translate_model_json_to_fcstd](translate_model_json_to_fcstd.md) *(from translator/freecad_translator/api.py)* `translator backend`
- [translate_model_json_to_freecad_script](translate_model_json_to_freecad_script.md) *(from translator/freecad_translator/api.py)* `translator backend`

## Math Helpers

- [BSplineFitResult](BSplineFitResult.md) *(from math.py)* `top-level`
- [fit_cubic_bspline_control_points](fit_cubic_bspline_control_points.md) *(from math.py)* `top-level`

## Modeling Graph and Replay

- [GraphSession](GraphSession.md) *(from graph.py)* `top-level`
- [export_graph_json](export_graph_json.md) *(from serializer.py)* `top-level`
- [export_model_json](export_model_json.md) *(from serializer.py)* `top-level`
- [export_session_json](export_session_json.md) *(from serializer.py)* `top-level`
- [import_graph_json](import_graph_json.md) *(from serializer.py)* `top-level`
- [import_model_json](import_model_json.md) *(from serializer.py)* `top-level`
- [import_session_json](import_session_json.md) *(from serializer.py)* `top-level`
- [replay_graph](replay_graph.md) *(from serializer.py)* `top-level`
- [replay_model_json](replay_model_json.md) *(from serializer.py)* `top-level`
- [suspend_graph_recording](suspend_graph_recording.md) *(from graph.py)* `top-level`

## Expressions and Parameters

- [Const](Const.md) *(from expr.py)* `top-level`
- [Expr](Expr.md) *(from expr.py)* `top-level`
- [ExpressionGraph](ExpressionGraph.md) *(from expr.py)* `top-level`
- [Var](Var.md) *(from expr.py)* `top-level`
- [const](const_function.md) *(from expr.py)* `top-level`
- [var](var_function.md) *(from expr.py)* `top-level`

## Types and Errors

- [SimpleCADError](SimpleCADError.md) *(from errors.py)* `top-level`
- [Sketch](Sketch.md) *(from sketch.py)* `top-level`
- [SketchConstraint](SketchConstraint.md) *(from sketch.py)* `top-level`
- [SketchConstraintDiagnostic](SketchConstraintDiagnostic.md) *(from sketch.py)* `top-level`
- [SketchRef](SketchRef.md) *(from sketch.py)* `top-level`
- [SketchSolveResult](SketchSolveResult.md) *(from sketch.py)* `top-level`

## Advanced Features

- [chamfer_rsolid](chamfer_rsolid.md) *(from operations.py)* `top-level`
- [fillet_rsolid](fillet_rsolid.md) *(from operations.py)* `top-level`
- [helical_sweep_rsolid](helical_sweep_rsolid.md) *(from operations.py)* `top-level`
- [shell_rsolid](shell_rsolid.md) *(from operations.py)* `top-level`

## Evolve

- [make_n_hole_flange_rsolid](make_n_hole_flange_rsolid.md) *(from evolve.py)* `top-level`
- [make_naca_propeller_blade_rsolid](make_naca_propeller_blade_rsolid.md) *(from evolve.py)* `top-level`
- [make_threaded_rod_rsolid](make_threaded_rod_rsolid.md) *(from evolve.py)* `top-level`

## Other

- [Assembly](Assembly.md) *(from product.py)* `top-level`
- [Component](Component.md) *(from product.py)* `top-level`
- [Connector](Connector.md) *(from product.py)* `top-level`
- [ConnectorAnchor](ConnectorAnchor.md) *(from product.py)* `top-level`
- [ConnectorRef](ConnectorRef.md) *(from product.py)* `top-level`
- [Constraint](Constraint.md) *(from product.py)* `top-level`
- [ConstraintReport](ConstraintReport.md) *(from product.py)* `top-level`
- [ConstraintResidual](ConstraintResidual.md) *(from product.py)* `top-level`
- [GeometryRef](GeometryRef.md) *(from product.py)* `top-level`
- [Material](Material.md) *(from product.py)* `top-level`
- [Part](Part.md) *(from product.py)* `top-level`
- [Placement](Placement.md) *(from product.py)* `top-level`
- [ScalarLimit](ScalarLimit.md) *(from product.py)* `top-level`
- [SemanticDelta](SemanticDelta.md) *(from topology.py)* `top-level`
- [SemanticRef](SemanticRef.md) *(from topology.py)* `top-level`
- [add_arc_rsketch](add_arc_rsketch.md) *(from operations.py)* `top-level`
- [add_belt_constraint_rassembly](add_belt_constraint_rassembly.md) *(from operations.py)* `top-level`
- [add_bspline_rsketch](add_bspline_rsketch.md) *(from operations.py)* `top-level`
- [add_circle_rsketch](add_circle_rsketch.md) *(from operations.py)* `top-level`
- [add_component_rassembly](add_component_rassembly.md) *(from operations.py)* `top-level`
- [add_connector_rassembly](add_connector_rassembly.md) *(from operations.py)* `top-level`
- [add_connector_rpart](add_connector_rpart.md) *(from operations.py)* `top-level`
- [add_fixed_constraint_rassembly](add_fixed_constraint_rassembly.md) *(from operations.py)* `top-level`
- [add_gear_constraint_rassembly](add_gear_constraint_rassembly.md) *(from operations.py)* `top-level`
- [add_line_rsketch](add_line_rsketch.md) *(from operations.py)* `top-level`
- [add_point_rsketch](add_point_rsketch.md) *(from operations.py)* `top-level`
- [add_prismatic_constraint_rassembly](add_prismatic_constraint_rassembly.md) *(from operations.py)* `top-level`
- [add_rack_pinion_constraint_rassembly](add_rack_pinion_constraint_rassembly.md) *(from operations.py)* `top-level`
- [add_revolute_constraint_rassembly](add_revolute_constraint_rassembly.md) *(from operations.py)* `top-level`
- [and_](and_.md) *(from ql.py)* `submodule:ql`
- [assign_material_rpart](assign_material_rpart.md) *(from operations.py)* `top-level`
- [constrain_angle_rsketch](constrain_angle_rsketch.md) *(from operations.py)* `top-level`
- [constrain_coincident_rsketch](constrain_coincident_rsketch.md) *(from operations.py)* `top-level`
- [constrain_collinear_rsketch](constrain_collinear_rsketch.md) *(from operations.py)* `top-level`
- [constrain_concentric_rsketch](constrain_concentric_rsketch.md) *(from operations.py)* `top-level`
- [constrain_connect_rsketch](constrain_connect_rsketch.md) *(from operations.py)* `top-level`
- [constrain_diameter_rsketch](constrain_diameter_rsketch.md) *(from operations.py)* `top-level`
- [constrain_distance_rsketch](constrain_distance_rsketch.md) *(from operations.py)* `top-level`
- [constrain_distance_x_rsketch](constrain_distance_x_rsketch.md) *(from operations.py)* `top-level`
- [constrain_distance_y_rsketch](constrain_distance_y_rsketch.md) *(from operations.py)* `top-level`
- [constrain_equal_length_rsketch](constrain_equal_length_rsketch.md) *(from operations.py)* `top-level`
- [constrain_equal_radius_rsketch](constrain_equal_radius_rsketch.md) *(from operations.py)* `top-level`
- [constrain_fix_rsketch](constrain_fix_rsketch.md) *(from operations.py)* `top-level`
- [constrain_horizontal_rsketch](constrain_horizontal_rsketch.md) *(from operations.py)* `top-level`
- [constrain_length_rsketch](constrain_length_rsketch.md) *(from operations.py)* `top-level`
- [constrain_midpoint_rsketch](constrain_midpoint_rsketch.md) *(from operations.py)* `top-level`
- [constrain_parallel_rsketch](constrain_parallel_rsketch.md) *(from operations.py)* `top-level`
- [constrain_perpendicular_rsketch](constrain_perpendicular_rsketch.md) *(from operations.py)* `top-level`
- [constrain_point_on_rsketch](constrain_point_on_rsketch.md) *(from operations.py)* `top-level`
- [constrain_radius_rsketch](constrain_radius_rsketch.md) *(from operations.py)* `top-level`
- [constrain_symmetric_rsketch](constrain_symmetric_rsketch.md) *(from operations.py)* `top-level`
- [constrain_tangent_rsketch](constrain_tangent_rsketch.md) *(from operations.py)* `top-level`
- [constrain_vertical_rsketch](constrain_vertical_rsketch.md) *(from operations.py)* `top-level`
- [forward_connector_rassembly](forward_connector_rassembly.md) *(from operations.py)* `top-level`
- [geo](geo.md) *(from ql.py)* `submodule:ql`
- [get_sketch_entity_rsketchref](get_sketch_entity_rsketchref.md) *(from operations.py)* `top-level`
- [get_sketch_point_rsketchref](get_sketch_point_rsketchref.md) *(from operations.py)* `top-level`
- [ground_component_rassembly](ground_component_rassembly.md) *(from operations.py)* `top-level`
- [identity_placement_rplacement](identity_placement_rplacement.md) *(from operations.py)* `top-level`
- [inspect_assembly_constraints_rconstraintreport](inspect_assembly_constraints_rconstraintreport.md) *(from operations.py)* `top-level`
- [inspect_sketch_rsketchresult](inspect_sketch_rsketchresult.md) *(from operations.py)* `top-level`
- [linear_pattern_rsolidlist](linear_pattern_rsolidlist.md) *(from operations.py)* `top-level`
- [measure_constraint_residual_rconstraintresidual](measure_constraint_residual_rconstraintresidual.md) *(from operations.py)* `top-level`
- [meta](meta.md) *(from ql.py)* `submodule:ql`
- [not_](not_.md) *(from ql.py)* `submodule:ql`
- [or_](or_.md) *(from ql.py)* `submodule:ql`
- [place_component_rassembly](place_component_rassembly.md) *(from operations.py)* `top-level`
- [radial_pattern_rsolidlist](radial_pattern_rsolidlist.md) *(from operations.py)* `top-level`
- [render_screenshot_rpath](render_screenshot_rpath.md) *(from operations.py)* `top-level`
- [select](select.md) *(from ql.py)* `submodule:ql`
- [solve_assembly_constraints_rassembly](solve_assembly_constraints_rassembly.md) *(from operations.py)* `top-level`
- [tag](tag.md) *(from ql.py)* `submodule:ql`
- [unground_component_rassembly](unground_component_rassembly.md) *(from operations.py)* `top-level`
- [value](value.md) *(from ql.py)* `submodule:ql`
