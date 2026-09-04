"""FTC source generated from HistCAD 0100/01003954."""

import simplecadapi as scad

BODIES = None  # all solid bodies before single-solid merge


def _merge_bodies(bodies):
    result = bodies[0]
    for extra in bodies[1:]:
        try:
            result = scad.union_rsolid(result, [extra])
        except Exception:
            pass  # disjoint bodies stay outside the single-solid contract
    return result


@scad.part(id='histcad-0100-01003954', revision='1.0.0')
def build() -> scad.Part:
    # ---- feature: newbody-1 (build, profile=sketch) ----
    s = scad.make_sketch_rsketch(name='f0', plane={'origin': (0.0, 0.0, 0.0), 'x_axis': (1.0, 0.0, 0.0), 'y_axis': (0.0, 1.0, 0.0)})
    s = scad.add_point_rsketch(s, 'f0_p1', -5.0, -1.5)
    s = scad.add_point_rsketch(s, 'f0_p2', -3.0, -1.5)
    s = scad.add_line_rsketch(s, 'line_1', 'f0_p1', 'f0_p2')
    s = scad.add_point_rsketch(s, 'f0_p3', -3.0, 0.0)
    s = scad.add_line_rsketch(s, 'line_2', 'f0_p2', 'f0_p3')
    s = scad.add_point_rsketch(s, 'f0_p4', 3.5, 0.0)
    s = scad.add_line_rsketch(s, 'line_3', 'f0_p3', 'f0_p4')
    s = scad.add_point_rsketch(s, 'f0_p5', 3.5, -1.5)
    s = scad.add_line_rsketch(s, 'line_4', 'f0_p4', 'f0_p5')
    s = scad.add_point_rsketch(s, 'f0_p6', 5.5, -1.5)
    s = scad.add_line_rsketch(s, 'line_5', 'f0_p5', 'f0_p6')
    s = scad.add_point_rsketch(s, 'f0_p7', 5.5, 2.5)
    s = scad.add_line_rsketch(s, 'line_6', 'f0_p6', 'f0_p7')
    s = scad.add_point_rsketch(s, 'f0_p8', -5.0, 2.5)
    s = scad.add_line_rsketch(s, 'line_7', 'f0_p7', 'f0_p8')
    s = scad.add_line_rsketch(s, 'line_8', 'f0_p8', 'f0_p1')
    s = scad.constrain_horizontal_rsketch(s, 'line_7', constraint_id='h9_Horizontal')
    s = scad.constrain_perpendicular_rsketch(s, 'line_6', 'line_7', constraint_id='h10_Perpendicular')
    s = scad.constrain_perpendicular_rsketch(s, 'line_5', 'line_6', constraint_id='h11_Perpendicular')
    s = scad.constrain_perpendicular_rsketch(s, 'line_4', 'line_5', constraint_id='h12_Perpendicular')
    s = scad.constrain_perpendicular_rsketch(s, 'line_3', 'line_4', constraint_id='h13_Perpendicular')
    s = scad.constrain_perpendicular_rsketch(s, 'line_2', 'line_3', constraint_id='h14_Perpendicular')
    s = scad.constrain_perpendicular_rsketch(s, 'line_1', 'line_2', constraint_id='h15_Perpendicular')
    s = scad.constrain_perpendicular_rsketch(s, 'line_8', 'line_7', constraint_id='h16_Perpendicular')
    f0_face0 = scad.make_face_from_sketch_rface(s, profile=0)
    f0_tool0 = scad.extrude_rsolid(profile=f0_face0, direction=(0.0, 0.0, 1.0), distance=10.0)
    bodies = list([f0_tool0])
    # ---- feature: join-2 (add, profile=geometry) ----
    s = scad.make_sketch_rsketch(name='f1', plane={'origin': (0.0, 2.5, 0.0), 'x_axis': (-1.0, 0.0, -0.0), 'y_axis': (-0.0, -0.0, 1.0)})
    s = scad.add_point_rsketch(s, 'f1_p1', 0.0, 5.0)
    s = scad.add_circle_rsketch(s, 'circle_1', 'f1_p1', 3.1623)
    f1_face0 = scad.make_face_from_sketch_rface(s, profile=0)
    f1_tool0 = scad.extrude_rsolid(profile=f1_face0, direction=(0.0, 1.0, 0.0), distance=0.5)
    _merged = False
    _next = []
    for _b in bodies:
        try:
            _next.append(scad.union_rsolid(_b, [f1_tool0]))
            _merged = True
        except Exception:
            _next.append(_b)
    bodies = _next
    if not _merged:
        bodies.extend([f1_tool0])
    # ---- feature: join-3 (add, profile=geometry) ----
    s = scad.make_sketch_rsketch(name='f2', plane={'origin': (0.0, 3.0, 0.0), 'x_axis': (-1.0, 0.0, -0.0), 'y_axis': (-0.0, -0.0, 1.0)})
    s = scad.add_point_rsketch(s, 'f2_p1', 0.0, 5.0)
    s = scad.add_circle_rsketch(s, 'circle_1', 'f2_p1', 2.0)
    f2_face0 = scad.make_face_from_sketch_rface(s, profile=0)
    f2_tool0 = scad.extrude_rsolid(profile=f2_face0, direction=(0.0, 1.0, 0.0), distance=0.5)
    _merged = False
    _next = []
    for _b in bodies:
        try:
            _next.append(scad.union_rsolid(_b, [f2_tool0]))
            _merged = True
        except Exception:
            _next.append(_b)
    bodies = _next
    if not _merged:
        bodies.extend([f2_tool0])
    # ---- feature: join-4 (add, profile=geometry) ----
    s = scad.make_sketch_rsketch(name='f3', plane={'origin': (0.0, 3.5, 0.0), 'x_axis': (-1.0, 0.0, -0.0), 'y_axis': (-0.0, -0.0, 1.0)})
    s = scad.add_point_rsketch(s, 'f3_p1', 0.0, 5.0)
    s = scad.add_circle_rsketch(s, 'circle_1', 'f3_p1', 0.9327)
    f3_face0 = scad.make_face_from_sketch_rface(s, profile=0)
    f3_tool0 = scad.extrude_rsolid(profile=f3_face0, direction=(0.0, 1.0, 0.0), distance=0.25)
    _merged = False
    _next = []
    for _b in bodies:
        try:
            _next.append(scad.union_rsolid(_b, [f3_tool0]))
            _merged = True
        except Exception:
            _next.append(_b)
    bodies = _next
    if not _merged:
        bodies.extend([f3_tool0])
    # ---- feature: join-5 (add, profile=geometry) ----
    s = scad.make_sketch_rsketch(name='f4', plane={'origin': (0.0, 3.75, 0.0), 'x_axis': (-1.0, 0.0, -0.0), 'y_axis': (-0.0, -0.0, 1.0)})
    s = scad.add_point_rsketch(s, 'f4_p1', 0.0, 5.0)
    s = scad.add_circle_rsketch(s, 'circle_1', 'f4_p1', 0.2916)
    f4_face0 = scad.make_face_from_sketch_rface(s, profile=0)
    f4_tool0 = scad.extrude_rsolid(profile=f4_face0, direction=(0.0, 1.0, 0.0), distance=3.5)
    _merged = False
    _next = []
    for _b in bodies:
        try:
            _next.append(scad.union_rsolid(_b, [f4_tool0]))
            _merged = True
        except Exception:
            _next.append(_b)
    bodies = _next
    if not _merged:
        bodies.extend([f4_tool0])
    # ---- feature: cut-6 (subtract, profile=geometry) ----
    s = scad.make_sketch_rsketch(name='f5', plane={'origin': (0.0, 3.0, 0.0), 'x_axis': (-1.0, 0.0, -0.0), 'y_axis': (-0.0, -0.0, 1.0)})
    s = scad.add_point_rsketch(s, 'f5_p1', 2.7, 5.0)
    s = scad.add_circle_rsketch(s, 'circle_1', 'f5_p1', 0.2828)
    f5_face0 = scad.make_face_from_sketch_rface(s, profile=0)
    f5_tool0 = scad.extrude_rsolid(profile=f5_face0, direction=(-0.0, -1.0, -0.0), distance=4.6)
    bodies = [scad.cut_rsolid(_b, [f5_tool0]) for _b in bodies]
    # ---- feature: join-7 (add, profile=geometry) ----
    s = scad.make_sketch_rsketch(name='f6', plane={'origin': (0.0, 2.5, 0.0), 'x_axis': (-1.0, 0.0, -0.0), 'y_axis': (-0.0, -0.0, 1.0)})
    s = scad.add_point_rsketch(s, 'f6_p1', -3.2, 3.1)
    s = scad.add_point_rsketch(s, 'f6_p2', -2.6, 2.4)
    s = scad.add_line_rsketch(s, 'line_1', 'f6_p1', 'f6_p2')
    s = scad.add_point_rsketch(s, 'f6_p3', -2.3, 2.6)
    s = scad.add_line_rsketch(s, 'line_2', 'f6_p2', 'f6_p3')
    s = scad.add_point_rsketch(s, 'f6_p4', -2.9, 3.3571)
    s = scad.add_line_rsketch(s, 'line_3', 'f6_p3', 'f6_p4')
    s = scad.add_line_rsketch(s, 'line_4', 'f6_p4', 'f6_p1')
    f6_face0 = scad.make_face_from_sketch_rface(s, profile=0)
    f6_tool0 = scad.extrude_rsolid(profile=f6_face0, direction=(0.0, 1.0, 0.0), distance=1.0)
    _merged = False
    _next = []
    for _b in bodies:
        try:
            _next.append(scad.union_rsolid(_b, [f6_tool0]))
            _merged = True
        except Exception:
            _next.append(_b)
    bodies = _next
    if not _merged:
        bodies.extend([f6_tool0])
    # ---- feature: join-8 (add, profile=sketch) ----
    s = scad.make_sketch_rsketch(name='f7', plane={'origin': (5.5, 0.0, 0.0), 'x_axis': (0.0, 0.0, -1.0), 'y_axis': (0.0, 1.0, 0.0)})
    s = scad.add_point_rsketch(s, 'f7_p1', -8.0, -0.546)
    s = scad.add_point_rsketch(s, 'f7_p2', -2.0, -0.546)
    s = scad.add_line_rsketch(s, 'line_1', 'f7_p1', 'f7_p2')
    s = scad.add_point_rsketch(s, 'f7_p3', -2.0, 0.0)
    s = scad.add_point_rsketch(s, 'f7_p4', -2.0, 0.546)
    s = scad.add_arc_rsketch(s, 'arc_1', 'f7_p2', 'f7_p4', 'f7_p3')
    s = scad.add_point_rsketch(s, 'f7_p5', -8.0, 0.546)
    s = scad.add_line_rsketch(s, 'line_2', 'f7_p4', 'f7_p5')
    s = scad.add_point_rsketch(s, 'f7_p6', -8.0, 0.0)
    s = scad.add_arc_rsketch(s, 'arc_2', 'f7_p5', 'f7_p1', 'f7_p6')
    s = scad.constrain_parallel_rsketch(s, 'line_1', 'line_2', constraint_id='h5_Parallel-2')
    s = scad.constrain_tangent_rsketch(s, 'arc_1', 'line_1', at_a='start', constraint_id='h6_Tangent')
    s = scad.constrain_tangent_rsketch(s, 'arc_1', 'line_2', at_a='end', constraint_id='h7_Tangent')
    s = scad.constrain_tangent_rsketch(s, 'arc_2', 'line_1', at_a='end', constraint_id='h8_Tangent')
    s = scad.constrain_tangent_rsketch(s, 'arc_2', 'line_2', at_a='start', constraint_id='h9_Tangent')
    f7_face0 = scad.make_face_from_sketch_rface(s, profile=0)
    f7_tool0 = scad.extrude_rsolid(profile=f7_face0, direction=(1.0, -0.0, 0.0), distance=0.5)
    _merged = False
    _next = []
    for _b in bodies:
        try:
            _next.append(scad.union_rsolid(_b, [f7_tool0]))
            _merged = True
        except Exception:
            _next.append(_b)
    bodies = _next
    if not _merged:
        bodies.extend([f7_tool0])
    global BODIES
    BODIES = list(bodies)
    return _merge_bodies(bodies)
