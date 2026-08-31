"""S7 hypothesis: back-face cut at 75% of bottom-tube height + naming.

Cut plane moves from centerline (y=0, 50%) to y = r*(2f-1), f=0.75 -> y=7.5.
Probes:
  H1 geometry: exactly ONE planar -Y face at y=back_y (straight-span chord strip
     continuous with corner chord regions); bbox y == [back_y, D]; single solid.
  H2 chord math: face area >= (L-2rc)*2*sqrt(r^2-h^2)*0.9; volume removal band
     [(L-2rc)*A_below, + 2*(pi*rc/2)*A_below] with A_below = pi*r^2 - segment.
  H3 naming + lineage: apply_tag_rselection on S2 output -> ql.tag n=1;
     then does the tag survive the S3 pocket cut? the S4 fillet?
     (S4 lesson says fillet breaks lineage; S3 unknown -> probe.)
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402
from simplecadapi import ql  # noqa: E402
from simplecadapi import GraphSession  # noqa: E402

from s1_hypothesis import bbox_of  # noqa: E402

P = dict(L=80.0, D=20.0, rod_d=30.0, thickness=6.0, d_motor=30.0, r_corner=17.0, fillet_r=1.2)
FRAC = 0.75
r = P["rod_d"] / 2.0
back_y = r * (2.0 * FRAC - 1.0)
rp = (P["rod_d"] - P["thickness"]) / 2.0
floor_y = P["d_motor"] / 2.0


def cut_back(rod):
    ovs = 5.0
    tool = u_link.scad.make_box_rsolid(
        width=P["L"] + 2.0 * r + 2.0 * ovs,
        height=back_y + r + ovs,
        depth=2.0 * (r + ovs),
        bottom_face_center=(0.0, back_y - (back_y + r + ovs) / 2.0, -(r + ovs)),
    )
    return u_link.scad.cut_rsolid(rod, tool)


def back_selector():
    return ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "PLANE"),
        ql.prop("geom.normal.y", "<=", -0.999),
        ql.prop("geom.center.y", ">=", back_y - 0.1),
        ql.prop("geom.center.y", "<=", back_y + 0.1),
    )).exactly(1)


with GraphSession(graph_id="s7_hyp") as session:
    body = cut_back(u_link.build_u_rod())

    # H1
    backs = ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "PLANE"),
        ql.prop("geom.normal.y", "<=", -0.999),
        ql.prop("geom.center.y", ">=", back_y - 0.1),
        ql.prop("geom.center.y", "<=", back_y + 0.1),
    )).resolve(body)
    xs = bbox_of(body)
    v = body.get_volume()
    v1 = u_link.build_u_rod().get_volume()
    print(f"H1 back faces n={len(backs)} area={backs[0].get_area():.1f}" if backs else "H1 back faces n=0")
    print(f"H1 bbox y[{xs[1]:.3f},{xs[4]:.3f}] (want [{back_y},{P['D']}]) volume={v:.1f}")
    assert len(backs) == 1
    assert abs(xs[1] - back_y) < 0.05 and abs(xs[4] - P["D"]) < 0.05

    # H2 chord/volume math
    h = back_y
    chord_w = 2.0 * math.sqrt(r * r - h * h)
    a_below = math.pi * r * r - (r * r * math.acos(h / r) - h * math.sqrt(r * r - h * h))
    lo = (P["L"] - 2.0 * P["r_corner"]) * a_below
    hi = lo + 2.0 * (math.pi * P["r_corner"] / 2.0) * a_below
    removed = v1 - v
    print(f"H2 area={backs[0].get_area():.1f} >= {(P['L'] - 2 * P['r_corner']) * chord_w * 0.9:.1f}; "
          f"removed={removed:.1f} in ({lo:.1f},{hi:.1f})")
    assert backs[0].get_area() >= (P["L"] - 2.0 * P["r_corner"]) * chord_w * 0.9
    assert lo < removed < hi

    # H3 tag + lineage through S3 pocket cut
    body = u_link.scad.apply_tag_rselection(scope=body, targets=back_selector(), tag="feature.back_face")
    pocket_depth = P["D"] - floor_y
    tools = [u_link.scad.make_cylinder_rsolid(
        radius=rp, height=pocket_depth + 5.0,
        bottom_face_center=(x, floor_y, 0.0), axis=(0.0, 1.0, 0.0)) for x in (-P["L"] / 2, P["L"] / 2)]
    body = u_link.scad.cut_rsolid(body, tools)
    n_after_cut = len(ql.faces().where(ql.tag("feature.back_face")).resolve(body))
    print(f"H3 back tag after S3 pocket cut: n={n_after_cut}")

    body = u_link.scad.fillet_rsolid(solid=body, edges=list(body.get_edges()),
                                     radius=P["fillet_r"], generated_faces_tag="fillet.global_patch")
    n_after_fillet = len(ql.faces().where(ql.tag("feature.back_face")).resolve(body))
    backs4 = ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "PLANE"),
        ql.prop("geom.normal.y", "<=", -0.999),
        ql.prop("geom.center.y", ">=", back_y - 0.1),
        ql.prop("geom.center.y", "<=", back_y + 0.1),
    )).resolve(body)
    print(f"H3 back tag after fillet: n={n_after_fillet}; geometric back face still n={len(backs4)}"
          + (f" area={backs4[0].get_area():.1f}" if backs4 else ""))
    session.capture_result(value=body)

print("S7 hypothesis: probes done")
