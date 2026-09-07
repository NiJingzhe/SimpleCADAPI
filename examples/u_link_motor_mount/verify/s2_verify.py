"""S2 verifier: back-face cut (back_cut_frac=0.75) vs BUILD_PLAN S2 contract.

Criteria:
  C1 single Solid, volume within analytic bounds around removed lower segment
  C2 exactly 1 planar -Y face at y=back_y (back face), area >= 0.9*(L-2rc)*chord_w
  C3 bbox y == [back_y, D] within 0.05 (strong datum check)
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402
from simplecadapi import ql  # noqa: E402

P = u_link.params()
r = P["rod_d"] / 2.0
by = u_link.back_y(P)
failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


body = u_link.build_flat_bottom()

v = body.get_volume()
v_s1 = u_link.build_u_rod().get_volume()
a_below = math.pi * r * r - (r * r * math.acos(by / r) - by * math.sqrt(r * r - by * by))
lo = (P["L"] - 2.0 * P["r_corner"]) * a_below
hi = lo + 2.0 * (math.pi * P["r_corner"] / 2.0) * a_below
check("C1 volume bounds", type(body).__name__ == "Solid" and lo < v_s1 - v < hi,
      f"volume={v:.3f} removed={v_s1 - v:.3f} in ({lo:.3f},{hi:.3f})")

backs = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.normal.y", "<=", -0.999),
    ql.prop("geom.center.y", ">=", by - 0.05),
    ql.prop("geom.center.y", "<=", by + 0.05),
)).resolve(body)
chord_w = 2.0 * math.sqrt(r * r - by * by)
check("C2 back face", len(backs) == 1
      and backs[0].get_area() >= 0.9 * (P["L"] - 2.0 * P["r_corner"]) * chord_w
      and len(ql.faces().where(ql.tag(u_link.TAG_BACK)).resolve(body)) == 1,
      f"n={len(backs)} area={backs[0].get_area():.1f} chord_bound={0.9 * (P['L'] - 2 * P['r_corner']) * chord_w:.1f}")

from OCP.Bnd import Bnd_Box  # noqa: E402
from OCP.BRepBndLib import BRepBndLib  # noqa: E402

box = Bnd_Box()
box.SetGap(0.0)
BRepBndLib.AddOptimal_s(body.wrapped, box, useTriangulation=False)
_, ymin, _, _, ymax, _ = box.Get()
check("C3 bbox y", abs(ymin - by) < 0.05 and abs(ymax - P["D"]) < 0.05,
      f"y[{ymin:.3f},{ymax:.3f}] want [{by},{P['D']}]")

print(f"S2 verifier: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
