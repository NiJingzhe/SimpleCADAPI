import math
import cadquery as cq
import simplecadapi as scad

part_1 = None
edges_1 = []
edges_1.append(scad.make_three_point_arc_redge((20, 62, 0), (0, 12, 0), (53, 4, 0)))
edges_1.append(scad.make_three_point_arc_redge((53, 4, 0), (49, 7, 0), (46, 10, 0)))
edges_1.append(scad.make_three_point_arc_redge((46, 10, 0), (8, 17, 0), (21, 53, 0)))
edges_1.append(scad.make_three_point_arc_redge((21, 53, 0), (20, 58, 0), (20, 62, 0)))
wire_1 = cq.Wire.combine([e.cq_edge for e in edges_1])[0]
face_1_grp = scad.Face(cq.Face.makeFromWires(wire_1))
solid_extr_1 = scad.extrude_rsolid(face_1_grp, (0, 0, 1), 17)  # along +Z
solid_extr_1 = scad.translate_shape(solid_extr_1, (-95, -86, -8))
part_1 = (
    solid_extr_1 if part_1 is None else scad.union_rsolidlist(part_1, solid_extr_1)[0]
)
edges_2 = []
edges_2.append(scad.make_segment_redge((20, 71, 0), (20, 62, 0)))
edges_2.append(scad.make_three_point_arc_redge((20, 62, 0), (60, 47, 0), (53, 4, 0)))
edges_2.append(scad.make_segment_redge((53, 4, 0), (61, 0, 0)))
edges_2.append(scad.make_three_point_arc_redge((61, 0, 0), (95, 27, 0), (130, 0, 0)))
edges_2.append(scad.make_segment_redge((130, 0, 0), (138, 4, 0)))
edges_2.append(scad.make_three_point_arc_redge((138, 4, 0), (131, 47, 0), (171, 62, 0)))
edges_2.append(scad.make_segment_redge((171, 62, 0), (171, 71, 0)))
edges_2.append(
    scad.make_three_point_arc_redge((171, 71, 0), (130, 87, 0), (136, 131, 0))
)
edges_2.append(
    scad.make_three_point_arc_redge((136, 131, 0), (133, 133, 0), (129, 135, 0))
)
edges_2.append(
    scad.make_three_point_arc_redge((129, 135, 0), (95, 109, 0), (62, 135, 0))
)
edges_2.append(scad.make_segment_redge((62, 135, 0), (54, 131, 0)))
edges_2.append(scad.make_three_point_arc_redge((54, 131, 0), (61, 87, 0), (20, 71, 0)))
wire_2 = cq.Wire.combine([e.cq_edge for e in edges_2])[0]
edges_3 = []
wire_3 = cq.Wire.assembleEdges([cq.Edge.makeCircle(25, cq.Vector(95, 67, 0))])
face_3_grp = scad.Face(cq.Face.makeFromWires(wire_2, [wire_3]))
solid_extr_3 = scad.extrude_rsolid(face_3_grp, (0, 0, 1), 17)  # along +Z
solid_extr_3 = scad.translate_shape(solid_extr_3, (-95, -86, -8))
part_1 = (
    solid_extr_3 if part_1 is None else scad.union_rsolidlist(part_1, solid_extr_3)[0]
)
edges_4 = []
edges_4.append(scad.make_three_point_arc_redge((20, 62, 0), (20, 58, 0), (21, 53, 0)))
edges_4.append(scad.make_three_point_arc_redge((21, 53, 0), (51, 42, 0), (46, 10, 0)))
edges_4.append(scad.make_three_point_arc_redge((46, 10, 0), (49, 7, 0), (53, 4, 0)))
edges_4.append(scad.make_three_point_arc_redge((53, 4, 0), (60, 47, 0), (20, 62, 0)))
wire_4 = cq.Wire.combine([e.cq_edge for e in edges_4])[0]
face_4_grp = scad.Face(cq.Face.makeFromWires(wire_4))
solid_extr_4 = scad.extrude_rsolid(face_4_grp, (0, 0, 1), 17)  # along +Z
solid_extr_4 = scad.translate_shape(solid_extr_4, (-95, -86, -8))
part_1 = (
    solid_extr_4 if part_1 is None else scad.union_rsolidlist(part_1, solid_extr_4)[0]
)
edges_5 = []
edges_5.append(
    scad.make_three_point_arc_redge((62, 135, 0), (95, 109, 0), (129, 135, 0))
)
edges_5.append(
    scad.make_three_point_arc_redge((129, 135, 0), (125, 137, 0), (120, 139, 0))
)
edges_5.append(
    scad.make_three_point_arc_redge((120, 139, 0), (95, 118, 0), (71, 139, 0))
)
edges_5.append(
    scad.make_three_point_arc_redge((71, 139, 0), (66, 137, 0), (62, 135, 0))
)
wire_5 = cq.Wire.combine([e.cq_edge for e in edges_5])[0]
face_5_grp = scad.Face(cq.Face.makeFromWires(wire_5))
solid_extr_5 = scad.extrude_rsolid(face_5_grp, (0, 0, 1), 17)  # along +Z
solid_extr_5 = scad.translate_shape(solid_extr_5, (-95, -86, -8))
part_1 = (
    solid_extr_5 if part_1 is None else scad.union_rsolidlist(part_1, solid_extr_5)[0]
)
edges_6 = []
edges_6.append(
    scad.make_three_point_arc_redge((62, 135, 0), (66, 137, 0), (71, 139, 0))
)
edges_6.append(
    scad.make_three_point_arc_redge((71, 139, 0), (95, 168, 0), (120, 139, 0))
)
edges_6.append(
    scad.make_three_point_arc_redge((120, 139, 0), (125, 137, 0), (129, 135, 0))
)
edges_6.append(
    scad.make_three_point_arc_redge((129, 135, 0), (95, 178, 0), (62, 135, 0))
)
wire_6 = cq.Wire.combine([e.cq_edge for e in edges_6])[0]
face_6_grp = scad.Face(cq.Face.makeFromWires(wire_6))
solid_extr_6 = scad.extrude_rsolid(face_6_grp, (0, 0, 1), 17)  # along +Z
solid_extr_6 = scad.translate_shape(solid_extr_6, (-95, -86, -8))
part_1 = (
    solid_extr_6 if part_1 is None else scad.union_rsolidlist(part_1, solid_extr_6)[0]
)
edges_7 = []
edges_7.append(scad.make_three_point_arc_redge((138, 4, 0), (141, 7, 0), (145, 10, 0)))
edges_7.append(
    scad.make_three_point_arc_redge((145, 10, 0), (139, 42, 0), (170, 53, 0))
)
edges_7.append(
    scad.make_three_point_arc_redge((170, 53, 0), (171, 58, 0), (171, 62, 0))
)
edges_7.append(scad.make_three_point_arc_redge((171, 62, 0), (131, 47, 0), (138, 4, 0)))
wire_7 = cq.Wire.combine([e.cq_edge for e in edges_7])[0]
face_7_grp = scad.Face(cq.Face.makeFromWires(wire_7))
solid_extr_7 = scad.extrude_rsolid(face_7_grp, (0, 0, 1), 17)  # along +Z
solid_extr_7 = scad.translate_shape(solid_extr_7, (-95, -86, -8))
part_1 = (
    solid_extr_7 if part_1 is None else scad.union_rsolidlist(part_1, solid_extr_7)[0]
)
edges_8 = []
edges_8.append(scad.make_three_point_arc_redge((138, 4, 0), (191, 12, 0), (171, 62, 0)))
edges_8.append(
    scad.make_three_point_arc_redge((171, 62, 0), (171, 58, 0), (170, 53, 0))
)
edges_8.append(
    scad.make_three_point_arc_redge((170, 53, 0), (183, 17, 0), (145, 10, 0))
)
edges_8.append(scad.make_three_point_arc_redge((145, 10, 0), (141, 7, 0), (138, 4, 0)))
wire_8 = cq.Wire.combine([e.cq_edge for e in edges_8])[0]
face_8_grp = scad.Face(cq.Face.makeFromWires(wire_8))
solid_extr_8 = scad.extrude_rsolid(face_8_grp, (0, 0, 1), 17)  # along +Z
solid_extr_8 = scad.translate_shape(solid_extr_8, (-95, -86, -8))
part_1 = (
    solid_extr_8 if part_1 is None else scad.union_rsolidlist(part_1, solid_extr_8)[0]
)
result = part_1


# 导出 STEP（可选）
scad.export_step(result, "result_simplecad.step")
print("OK: simplecadapi inline 版本完成")
