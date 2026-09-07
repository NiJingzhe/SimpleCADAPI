"""S2 hypothesis: flat-bottom cut (remove y<0, keep upper half of bottom tube).

Probes:
  H1 cut builds; volume lands in analytic bounds (straight half-cylinder removed
     at minimum, + at most both corner-tube lower halves).
  H2 exactly 1 planar -Y face at y=0 (flat bottom).
  H3 bbox y == [0, D].
  H4 known-bad: same checks on the UNCUT u_rod must fail (y_min = -r).
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402
from simplecadapi import ql  # noqa: E402

from s1_hypothesis import bbox_of  # noqa: E402

P = u_link.params()
r = P["rod_d"] / 2.0


def flat_bottom_cut(rod):
    ovs = 5.0
    tool = u_link.scad.make_box_rsolid(
        width=P["L"] + 2.0 * r + 2.0 * ovs,
        height=r + ovs,
        depth=2.0 * (r + ovs),
        bottom_face_center=(0.0, -(r + ovs) / 2.0, -(r + ovs)),
    )
    return u_link.scad.cut_rsolid(rod, tool)


def run_checks(solid, label):
    v = solid.get_volume()
    v_s1 = u_link.build_u_rod().get_volume()
    straight_half = (P["L"] - 2.0 * P["r_corner"]) * math.pi * r * r / 2.0
    corner_max = (math.pi * P["r_corner"] / 2.0) * (math.pi * r * r / 2.0)
    lo, hi = v_s1 - straight_half - 2.0 * corner_max, v_s1 - straight_half
    print(f"[{label}] volume={v:.3f} bounds=({lo:.3f},{hi:.3f}) in_bounds={lo < v < hi}")
    bottoms = ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "PLANE"),
        ql.prop("geom.normal.y", "<=", -0.999),
        ql.prop("geom.center.y", ">=", -0.05),
        ql.prop("geom.center.y", "<=", 0.05),
    )).resolve(solid)
    print(f"[{label}] flat-bottom faces n={len(bottoms)} areas={[f'{f.get_area():.1f}' for f in bottoms]}")
    xmin, ymin, zmin, xmax, ymax, zmax = bbox_of(solid)
    print(f"[{label}] bbox y[{ymin:.3f},{ymax:.3f}] (want [0,{P['D']}])")
    return lo < v < hi, len(bottoms) == 1 and bottoms[0].get_area() > math.pi * r * r / 2.0, \
        abs(ymin) < 0.05 and abs(ymax - P["D"]) < 0.05


# H1-H3 on cut solid
cut = flat_bottom_cut(u_link.build_u_rod())
c1, c2, c3 = run_checks(cut, "cut")
assert c1 and c2 and c3, "H1-H3 failed on cut solid"

# H4 known-bad: uncut rod must fail the bbox criterion
_, _, c3_bad = run_checks(u_link.build_u_rod(), "uncut")
assert not c3_bad, "H4 FAIL: bbox check accepted the uncut rod"

print("S2 hypothesis: all probes done")
