"""S11 probe: two-cut architecture functional checks (flat-bottom revision).

  P1 flat bottom: ONE big planar -Y face at y=fb(0.5) (chord section of first
     cut); NO material below fb; bbox ymin == fb.
  P1b floor/cavity: floor [fb,ft] solid between holes; cavity [ft,by] hollow
     away from boss columns; boss tip plane == floor top == ft.
  P2 countersink: 2 CONE faces at boss positions (mouth at fb); through-hole
     walls spanning the floor.
  P3 notches: no material along notch windows at both ends; wall intact
     just outside the notch z-window.
  P4 non-interference upper/shell (sampled off contact planes).
  P5 deep slot: mount floor − back face == wall_t exactly.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import shell as SH  # noqa: E402
import u_link  # noqa: E402
from simplecadapi import ql  # noqa: E402
from OCP.BRepClass3d import BRepClass3d_SolidClassifier  # noqa: E402
from OCP.gp import gp_Pnt  # noqa: E402
from OCP.TopAbs import TopAbs_IN, TopAbs_ON  # noqa: E402

from s1_hypothesis import bbox_of  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


P = dict(u_link.params(), **SH.shell_params())
BY = u_link.back_y(P)
FB, FT = SH.floor_band(P)
r = P["rod_d"] / 2.0

upper = u_link.build_stage("s4")
sh = SH.build_shell_body()


def mk(solid):
    c = BRepClass3d_SolidClassifier(solid.wrapped)

    def inside(x, y, z):
        c.Perform(gp_Pnt(x, y, z), 1e-7)
        return c.State() in (TopAbs_IN, TopAbs_ON)
    return inside


in_up, in_sh = mk(upper), mk(sh)

# P1 flat bottom
bottoms = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.normal.y", "<=", -0.999),
    ql.prop("geom.center.y", ">=", FB - 0.1),
    ql.prop("geom.center.y", "<=", FB + 0.1),
    ql.prop("geom.area", ">=", 500.0),
)).resolve(sh)
xs = bbox_of(sh)
below_ok = all(not in_sh(x, FB - 0.8, z) for x in (0.0, 30.0, 48.0) for z in (0.0, 8.0))
check("P1 flat bottom face", len(bottoms) == 1 and bottoms[0].get_area() > 1000.0
      and abs(xs[1] - FB) < 0.05 and below_ok,
      f"n={len(bottoms)} area={bottoms[0].get_area():.1f}" if bottoms else "n=0"
      + f" ymin={xs[1]:.2f} want {FB}")

# P1b floor slab / cavity / boss-tip plane
slab_ok = in_sh(0.0, (FB + FT) / 2.0, 8.0) and in_sh(-20.0, (FB + FT) / 2.0, 0.0)
cav_ok = not in_sh(0.0, FT + 1.5, 8.0) and not in_sh(20.0, (FT + BY) / 2.0, 0.0)
check("P1b floor+ cavity", slab_ok and cav_ok and abs(FT - (BY - P["boss_h"])) < 1e-9,
      f"slab={slab_ok} cavity={cav_ok} ft={FT} boss_tip={BY - P['boss_h']}")

# P2 countersink + through walls
cones = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CONE"),
    ql.prop("geom.center.y", ">=", FB - 0.1), ql.prop("geom.center.y", "<=", FB + P["csink_depth"] + 0.1),
)).resolve(sh)
hole_r = P["boss_hole_d"] / 2.0
hole_w = [f for f in ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CYLINDER"),
    ql.prop("geom.area", ">=", 2 * math.pi * hole_r * (P["wall_t"] - P["csink_depth"]) * 0.7),
    ql.prop("geom.area", "<=", 2 * math.pi * hole_r * P["wall_t"] * 1.1),
)).resolve(sh) if abs(abs(f.get_center().x) - P["boss_x"]) < 0.3 and abs(f.get_center().z) < 0.3]
check("P2 countersink+through", len(cones) == 2 and len(hole_w) == 2,
      f"cones={len(cones)} hole_walls={len(hole_w)}")

# P3 notches
notch_xc = P["L"] / 2.0 - P["r_corner"] + 1.45 * r
notch_h = BY - FT
open_ok = all(not in_sh(sx * notch_xc, FT + notch_h / 2.0, 0.0) for sx in (-1, 1))
side_ok = all(in_sh(sx * 49.5, FT + notch_h / 2.0, P["notch_w"] / 2 + 3.5) for sx in (-1, 1))  # 环形壁带上（z 增大壁带内移）
check("P3 notches", open_ok and side_ok, f"open={open_ok} side_material={side_ok}")

# P4 interference
bad = []
for x in [x * 1.0 for x in range(-52, 53, 4)]:
    for z in [z * 0.5 for z in range(-29, 30, 3)]:
        for y in (FB - 0.4, FT + 0.4, BY - 0.4, 4.0):
            if in_sh(x, y, z) and in_up(x, y, z):
                bad.append((x, y, round(z, 1)))
check("P4 non-interference", not bad, f"bad={bad[:3]} n={len(bad)}")

# P5 deep slot wall
FY = P["d_motor"] / 2.0
check("P5 deep slot wall", abs(FY - BY - P["wall_t"]) < 1e-9,
      f"floor={FY} back={BY} wall={FY - BY:.2f} = wall_t {P['wall_t']}")

print(f"S11 probe: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
