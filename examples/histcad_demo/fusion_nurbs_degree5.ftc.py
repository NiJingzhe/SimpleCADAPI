"""FTC source generated from HistCAD 0100/01000035."""

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


@scad.part(id='histcad-0100-01000035', revision='1.0.0')
def build() -> scad.Part:
    # ---- feature: newbody-1 (build, profile=sketch) ----
    s = scad.make_sketch_rsketch(name='f0', plane={'origin': (0.0, 0.0, 86.0), 'x_axis': (-1.0, 0.0, 0.0), 'y_axis': (-0.0, -1.0, 0.0)})
    s = scad.add_point_rsketch(s, 'f0_p1', 0.30010942, -1.89989058)
    s = scad.add_point_rsketch(s, 'f0_p2', 0.0, -1.9)
    s = scad.add_point_rsketch(s, 'f0_p3', 0.3, -2.2)
    s = scad.add_arc_rsketch(s, 'arc_1', 'f0_p2', 'f0_p3', 'f0_p1')
    s = scad.add_point_rsketch(s, 'f0_p4', 2.0, -2.2)
    s = scad.add_line_rsketch(s, 'line_1', 'f0_p3', 'f0_p4')
    s = scad.add_point_rsketch(s, 'f0_p5', 1.99989058, -1.89989058)
    s = scad.add_point_rsketch(s, 'f0_p6', 2.3, -1.9)
    s = scad.add_arc_rsketch(s, 'arc_2', 'f0_p4', 'f0_p6', 'f0_p5')
    s = scad.add_point_rsketch(s, 'f0_p7', 2.3, -1.5311)
    s = scad.add_line_rsketch(s, 'line_2', 'f0_p6', 'f0_p7')
    s = scad.add_point_rsketch(s, 'f0_p8', 2.3, -0.428)
    s = scad.add_bspline_rsketch(s, 'nurbs_1', 'f0_p7', 'f0_p8',
    control_points=[(2.3, -1.5311), (2.292, -1.5317), (2.2758, -1.5327), (2.2508, -1.5339), (2.2161, -1.5349), (2.1704, -1.5348), (2.123, -1.5328), (2.0746, -1.5276), (2.0269, -1.517), (1.9818, -1.4985), (1.9413, -1.4696), (1.907, -1.4286), (1.8798, -1.3751), (1.8599, -1.3104), (1.8467, -1.2367), (1.8391, -1.1573), (1.8361, -1.0753), (1.8362, -0.9941), (1.8385, -0.9164), (1.8421, -0.844), (1.8468, -0.7781), (1.8525, -0.7191), (1.8597, -0.6672), (1.8692, -0.6221), (1.8823, -0.5832), (1.9009, -0.55), (1.9268, -0.5216), (1.9616, -0.4975), (2.0065, -0.4771), (2.0622, -0.46), (2.1292, -0.4461), (2.1918, -0.4374), (2.2439, -0.4322), (2.2809, -0.4293), (2.3, -0.428)],
    degree=5, knots=[0.0, 0.0333, 0.0667, 0.1, 0.1333, 0.1667, 0.2, 0.2333, 0.2667, 0.3, 0.3333, 0.3667, 0.4, 0.4333, 0.4667, 0.5, 0.5333, 0.5667, 0.6, 0.6333, 0.6667, 0.7, 0.7333, 0.7667, 0.8, 0.8333, 0.8667, 0.9, 0.9333, 0.9667, 1.0],
    multiplicities=[6, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 6], weights=None,
    periodic=False)
    s = scad.add_point_rsketch(s, 'f0_p9', 2.3, 0.0)
    s = scad.add_line_rsketch(s, 'line_3', 'f0_p8', 'f0_p9')
    s = scad.add_point_rsketch(s, 'f0_p10', 0.0, 0.0)
    s = scad.add_line_rsketch(s, 'line_4', 'f0_p9', 'f0_p10')
    s = scad.add_point_rsketch(s, 'f0_p11', 0.0, -0.428)
    s = scad.add_line_rsketch(s, 'line_5', 'f0_p10', 'f0_p11')
    s = scad.add_point_rsketch(s, 'f0_p12', 0.0, -1.5311)
    s = scad.add_bspline_rsketch(s, 'nurbs_2', 'f0_p11', 'f0_p12',
    control_points=[(0.0, -0.428), (0.0191, -0.4293), (0.0561, -0.4322), (0.1082, -0.4374), (0.1708, -0.4461), (0.2378, -0.46), (0.2935, -0.4771), (0.3384, -0.4975), (0.3732, -0.5216), (0.3991, -0.55), (0.4177, -0.5832), (0.4308, -0.6221), (0.4403, -0.6672), (0.4475, -0.7191), (0.4532, -0.7781), (0.4579, -0.844), (0.4615, -0.9164), (0.4638, -0.9941), (0.4639, -1.0753), (0.4609, -1.1573), (0.4533, -1.2367), (0.4401, -1.3104), (0.4202, -1.3751), (0.393, -1.4286), (0.3587, -1.4696), (0.3182, -1.4985), (0.2731, -1.517), (0.2254, -1.5276), (0.177, -1.5328), (0.1296, -1.5348), (0.0839, -1.5349), (0.0492, -1.5339), (0.0242, -1.5327), (0.008, -1.5317), (0.0, -1.5311)],
    degree=5, knots=[0.0, 0.0333, 0.0667, 0.1, 0.1333, 0.1667, 0.2, 0.2333, 0.2667, 0.3, 0.3333, 0.3667, 0.4, 0.4333, 0.4667, 0.5, 0.5333, 0.5667, 0.6, 0.6333, 0.6667, 0.7, 0.7333, 0.7667, 0.8, 0.8333, 0.8667, 0.9, 0.9333, 0.9667, 1.0],
    multiplicities=[6, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 6], weights=None,
    periodic=False)
    s = scad.add_line_rsketch(s, 'line_6', 'f0_p12', 'f0_p2')
    s = scad.constrain_parallel_rsketch(s, 'line_2', 'line_3', constraint_id='h11_Parallel-2')
    s = scad.constrain_parallel_rsketch(s, 'line_5', 'line_6', constraint_id='h12_Parallel-2')
    f0_face0 = scad.make_face_from_sketch_rface(s, profile=0)
    f0_tool0 = scad.extrude_rsolid(profile=f0_face0, direction=(0.0, 0.0, 1.0), distance=100.0)
    bodies = list([f0_tool0])
    global BODIES
    BODIES = list(bodies)
    return _merge_bodies(bodies)
