"""
SimpleCAD API - 简化的CAD建模Python API
基于CADQuery实现，提供直观的几何建模接口
"""

from .core import (
    # 核心类
    CoordinateSystem,
    SimpleWorkplane,
    Vertex,
    Edge,
    Wire,
    Face,
    Solid,
    AnyShape,
    TaggedMixin,

    # 坐标系函数
    get_current_cs,
    WORLD_CS,
)

from .operations import (
    # 基础几何创建
    make_angle_arc_redge,
    make_angle_arc_rwire,
    make_box_rsolid,
    make_circle_redge,
    make_circle_rface,
    make_circle_rwire,
    make_cylinder_rsolid,
    make_face_from_wire_rface,
    make_helix_redge,
    make_helix_rwire,
    make_line_redge,
    make_point_rvertex,
    make_polyline_rwire,
    make_rectangle_rface,
    make_rectangle_rwire,
    make_segment_redge,
    make_segment_rwire,
    make_sphere_rsolid,
    make_spline_redge,
    make_spline_rwire,
    make_three_point_arc_redge,
    make_three_point_arc_rwire,
    make_wire_from_edges_rwire,

    # 变换操作
    mirror_shape,
    rotate_shape,
    translate_shape,

    # 3D操作
    extrude_rsolid,
    helical_sweep_rsolid,
    loft_rsolid,
    revolve_rsolid,
    sweep_rsolid,

    # 标签和选择
    select_edges_by_tag,
    select_faces_by_tag,
    set_tag,

    # 布尔运算
    cut_rsolid,
    intersect_rsolid,
    union_rsolid,

    # 导出
    export_step,
    export_stl,

    # 高级特征操作
    chamfer_rsolid,
    fillet_rsolid,
    shell_rsolid,

    # 其他
    linear_pattern_rsolidlist,
    radial_pattern_rsolidlist,
)

__version__ = "0.1.0"
__author__ = "SimpleCAD API Team"
__description__ = "Simplified CAD modeling Python API based on CADQuery"

# 便于使用的别名
Workplane = SimpleWorkplane

# 布尔运算别名
cut = cut_rsolid
intersect = intersect_rsolid
union = union_rsolid

# 导出别名
to_step = export_step
to_stl = export_stl

# 3D操作别名
extrude = extrude_rsolid
revolve = revolve_rsolid

# 创建函数别名
create_angle_arc = make_angle_arc_redge
create_angle_arc_wire = make_angle_arc_rwire
create_box = make_box_rsolid
create_circle_edge = make_circle_redge
create_circle_face = make_circle_rface
create_circle_wire = make_circle_rwire
create_cylinder = make_cylinder_rsolid
create_face_from_wire = make_face_from_wire_rface
create_helix = make_helix_redge
create_helix_wire = make_helix_rwire
create_line = make_line_redge
create_point = make_point_rvertex
create_polyline_wire = make_polyline_rwire
create_rectangle_face = make_rectangle_rface
create_rectangle_wire = make_rectangle_rwire
create_segment = make_segment_redge
create_segment_wire = make_segment_rwire
create_sphere = make_sphere_rsolid
create_spline = make_spline_redge
create_spline_wire = make_spline_rwire
create_arc = make_three_point_arc_redge
create_arc_wire = make_three_point_arc_rwire
create_wire_from_edges = make_wire_from_edges_rwire

# 变换操作别名
rotate = rotate_shape
translate = translate_shape


__all__ = [
    # 核心类
    "CoordinateSystem",
    "SimpleWorkplane",
    "Workplane",
    "Vertex",
    "Edge",
    "Wire",
    "Face",
    "Solid",
    "AnyShape",
    "TaggedMixin",

    # 坐标系
    "get_current_cs",
    "WORLD_CS",

    # 基础几何创建
    "make_angle_arc_redge",
    "make_angle_arc_rwire",
    "make_box_rsolid",
    "make_circle_redge",
    "make_circle_rface",
    "make_circle_rwire",
    "make_cylinder_rsolid",
    "make_face_from_wire_rface",
    "make_helix_redge",
    "make_helix_rwire",
    "make_line_redge",
    "make_point_rvertex",
    "make_polyline_rwire",
    "make_rectangle_rface",
    "make_rectangle_rwire",
    "make_segment_redge",
    "make_segment_rwire",
    "make_sphere_rsolid",
    "make_spline_redge",
    "make_spline_rwire",
    "make_three_point_arc_redge",
    "make_three_point_arc_rwire",
    "make_wire_from_edges_rwire",

    # 变换操作
    "mirror_shape",
    "rotate_shape",
    "translate_shape",

    # 3D操作
    "extrude_rsolid",
    "helical_sweep_rsolid",
    "loft_rsolid",
    "revolve_rsolid",
    "sweep_rsolid",

    # 标签和选择
    "select_edges_by_tag",
    "select_faces_by_tag",
    "set_tag",

    # 布尔运算
    "cut_rsolid",
    "intersect_rsolid",
    "union_rsolid",

    # 导出
    "export_step",
    "export_stl",

    # 高级特征操作
    "chamfer_rsolid",
    "fillet_rsolid",
    "shell_rsolid",

    # 其他
    "linear_pattern_rsolidlist",
    "radial_pattern_rsolidlist",

    # 别名
    "create_angle_arc",
    "create_angle_arc_wire",
    "create_arc",
    "create_arc_wire",
    "create_box",
    "create_circle_edge",
    "create_circle_face",
    "create_circle_wire",
    "create_cylinder",
    "create_face_from_wire",
    "create_helix",
    "create_helix_wire",
    "create_line",
    "create_point",
    "create_polyline_wire",
    "create_rectangle_face",
    "create_rectangle_wire",
    "create_segment",
    "create_segment_wire",
    "create_sphere",
    "create_spline",
    "create_spline_wire",
    "create_wire_from_edges",
    "cut",
    "extrude",
    "intersect",
    "revolve",
    "rotate",
    "to_step",
    "to_stl",
    "translate",
    "union",
]
