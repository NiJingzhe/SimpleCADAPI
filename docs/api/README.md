# SimpleCAD API Index

This index includes generated docs for the public SimpleCAD API surface, including geometry operations, graph/model JSON workflows, expressions, QL, and export helpers.

## Import Surfaces

- Entries marked `top-level` are exported from `simplecadapi` and can be imported with `from simplecadapi import <name>`.
- Entries marked `submodule` are public through the listed submodule, such as `simplecadapi.ql`.

## Basic Creation

- [make_angle_arc_redge](make_angle_arc_redge.md) *(from operations.py)* `top-level`
- [make_angle_arc_rwire](make_angle_arc_rwire.md) *(from operations.py)* `top-level`
- [make_box_rsolid](make_box_rsolid.md) *(from operations.py)* `top-level`
- [make_circle_redge](make_circle_redge.md) *(from operations.py)* `top-level`
- [make_circle_rface](make_circle_rface.md) *(from operations.py)* `top-level`
- [make_circle_rwire](make_circle_rwire.md) *(from operations.py)* `top-level`
- [make_cone_rsolid](make_cone_rsolid.md) *(from operations.py)* `top-level`
- [make_cylinder_rsolid](make_cylinder_rsolid.md) *(from operations.py)* `top-level`
- [make_face_from_wire_rface](make_face_from_wire_rface.md) *(from operations.py)* `top-level`
- [make_helix_redge](make_helix_redge.md) *(from operations.py)* `top-level`
- [make_helix_rwire](make_helix_rwire.md) *(from operations.py)* `top-level`
- [make_line_redge](make_line_redge.md) *(from operations.py)* `top-level`
- [make_point_rvertex](make_point_rvertex.md) *(from operations.py)* `top-level`
- [make_polyline_rwire](make_polyline_rwire.md) *(from operations.py)* `top-level`
- [make_rectangle_rface](make_rectangle_rface.md) *(from operations.py)* `top-level`
- [make_rectangle_rwire](make_rectangle_rwire.md) *(from operations.py)* `top-level`
- [make_segment_redge](make_segment_redge.md) *(from operations.py)* `top-level`
- [make_segment_rwire](make_segment_rwire.md) *(from operations.py)* `top-level`
- [make_sphere_rsolid](make_sphere_rsolid.md) *(from operations.py)* `top-level`
- [make_spline_redge](make_spline_redge.md) *(from operations.py)* `top-level`
- [make_spline_rwire](make_spline_rwire.md) *(from operations.py)* `top-level`
- [make_three_point_arc_redge](make_three_point_arc_redge.md) *(from operations.py)* `top-level`
- [make_three_point_arc_rwire](make_three_point_arc_rwire.md) *(from operations.py)* `top-level`
- [make_wire_from_edges_rwire](make_wire_from_edges_rwire.md) *(from operations.py)* `top-level`

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

- [translate_model_json_to_fcstd](translate_model_json_to_fcstd.md) *(from freecad_translator.py)* `top-level`
- [translate_model_json_to_freecad_script](translate_model_json_to_freecad_script.md) *(from freecad_translator.py)* `top-level`

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

- [SemanticDelta](SemanticDelta.md) *(from topology.py)* `top-level`
- [SemanticRef](SemanticRef.md) *(from topology.py)* `top-level`
- [and_](and_.md) *(from ql.py)* `submodule:ql`
- [geo](geo.md) *(from ql.py)* `submodule:ql`
- [linear_pattern_rsolidlist](linear_pattern_rsolidlist.md) *(from operations.py)* `top-level`
- [meta](meta.md) *(from ql.py)* `submodule:ql`
- [not_](not_.md) *(from ql.py)* `submodule:ql`
- [or_](or_.md) *(from ql.py)* `submodule:ql`
- [radial_pattern_rsolidlist](radial_pattern_rsolidlist.md) *(from operations.py)* `top-level`
- [render_screenshot_rpath](render_screenshot_rpath.md) *(from operations.py)* `top-level`
- [select](select.md) *(from ql.py)* `submodule:ql`
- [tag](tag.md) *(from ql.py)* `submodule:ql`
- [value](value.md) *(from ql.py)* `submodule:ql`
