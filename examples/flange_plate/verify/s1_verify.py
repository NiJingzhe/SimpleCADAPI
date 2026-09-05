"""S1 verifier: axisymmetric stepped revolve (disc + boss - center bore).

Run AFTER flange_plate.py exists (fresh process, re-materializes from source):
    uv run python examples/flange_plate/verify/s1_verify.py

Criteria (BUILD_PLAN S1 contract, hypothesis-proven in s1_hypothesis.py):
  C1 single Solid, volume = pi/4*(od^2*t + boss_od^2*(top-t) - bore^2*top) +-0.5%
  C2 bbox x/y in [-od/2, od/2], z in [0, boss_top_z], tol 0.05
  C3 boss top annulus plane @ z=boss_top_z, area pi*((boss_od/2)^2-(bore/2)^2)
  C4 bore wall cylinder, area pi*bore_d*boss_top_z
  C5 flange bottom annulus plane @ z=0, area pi*((od/2)^2-(bore/2)^2)
  C6 parameter guards reject 4 known-bad dicts and accept nominal params
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import flange_plate as fp  # noqa: E402
from simplecadapi import ql  # noqa: E402
from OCP.Bnd import Bnd_Box  # noqa: E402
from OCP.BRepBndLib import BRepBndLib  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


p = fp.params()
od, t = p["flange_od"], p["flange_t"]
boss_od, top, bore = p["boss_od"], p["boss_top_z"], p["bore_d"]

body = fp.build_solid()

# C1
volume = body.get_volume()
analytic = math.pi / 4.0 * (od * od * t + boss_od * boss_od * (top - t) - bore * bore * top)
check("C1 solid+volume", type(body).__name__ == "Solid" and volume > 0
      and abs(volume - analytic) / analytic < 0.005,
      f"volume={volume:.3f} analytic={analytic:.3f}")

# C2
box = Bnd_Box()
box.SetGap(0.0)
BRepBndLib.AddOptimal_s(body.wrapped, box, useTriangulation=False)
xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
bbox_wants = ((xmin, -od / 2), (xmax, od / 2), (ymin, -od / 2),
              (ymax, od / 2), (zmin, 0.0), (zmax, top))
check("C2 bbox", all(abs(g - w) < 0.05 for g, w in bbox_wants),
      f"x[{xmin:.2f},{xmax:.2f}] y[{ymin:.2f},{ymax:.2f}] z[{zmin:.2f},{zmax:.2f}]")

# C3 boss top annulus
a_top = math.pi * ((boss_od / 2.0) ** 2 - (bore / 2.0) ** 2)
boss_top = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.center.z", ">=", top - 0.1), ql.prop("geom.center.z", "<=", top + 0.1),
    ql.prop("geom.area", ">=", a_top - 1.0), ql.prop("geom.area", "<=", a_top + 1.0),
)).resolve(body)
check("C3 boss top annulus", len(boss_top) == 1,
      f"n={len(boss_top)} area={[f'{f.get_area():.2f}' for f in boss_top]} want={a_top:.2f}")

# C4 bore wall
a_bore = math.pi * bore * top
bore_wall = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CYLINDER"),
    ql.prop("geom.area", ">=", a_bore - 1.0), ql.prop("geom.area", "<=", a_bore + 1.0),
)).resolve(body)
check("C4 bore wall cylinder", len(bore_wall) == 1,
      f"n={len(bore_wall)} area={[f'{f.get_area():.2f}' for f in bore_wall]} want={a_bore:.2f}")

# C5 flange bottom annulus
a_bot = math.pi * ((od / 2.0) ** 2 - (bore / 2.0) ** 2)
bottom = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.center.z", ">=", -0.1), ql.prop("geom.center.z", "<=", 0.1),
    ql.prop("geom.area", ">=", a_bot - 1.0), ql.prop("geom.area", "<=", a_bot + 1.0),
)).resolve(body)
check("C5 bottom annulus", len(bottom) == 1,
      f"n={len(bottom)} area={[f'{f.get_area():.2f}' for f in bottom]} want={a_bot:.2f}")

# C6 guards: nominal accepted, 4 known-bad dicts rejected
try:
    fp.assert_params(p)
    ok_nominal = True
except AssertionError:
    ok_nominal = False
check("C6a nominal params accepted", ok_nominal)

bad_cases = {
    "bore>=boss (G1)": dict(p, bore_d=boss_od),
    "web<min (G2)": dict(p, bolt_pcd=od - p["bolt_d"] - 2.0 * p["min_edge_web"] + 1.0),
    "bolt hits root fillet (G3)": dict(p, bolt_pcd=boss_od + p["bolt_d"] + 2.0 * p["boss_fillet_r"]),
    "root fillet>boss height (G4)": dict(p, boss_top_z=t + 2.0),  # boss 高 2 < R3
}
for name, bad_p in bad_cases.items():
    try:
        fp.assert_params(bad_p)
        check(f"C6 guard rejects {name}", False, "NO raise — guard is silent")
    except AssertionError as exc:
        check(f"C6 guard rejects {name}", True, f"raised: {str(exc)[:60]}")

print(f"S1 verifier: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
