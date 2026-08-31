"""S1 verifier: U-rod sweep against REQUIREMENTS/BUILD_PLAN S1 contract.

Run AFTER u_link.py exists (fresh process, re-materializes from source):
    uv run python verify/s1_verify.py

Criteria:
  C1 single Solid, volume > 0, equals Pappus (A * centerline) within 0.5%
  C2 exactly 2 planar end caps at y=D, each area pi*r^2, centers (±L/2, D, 0)
  C3 bbox == [±(L/2+r)] x [-r, D] x [±r] within 0.05
  C4 parameter guard present in source: R_corner > r (H5 proved build alone won't fail)
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402
from simplecadapi import ql  # noqa: E402

P = u_link.params()
r = P["rod_d"] / 2.0
failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


rod = u_link.build_u_rod()

# C1
volume = rod.get_volume()
centerline = 2.0 * (P["D"] - P["r_corner"]) + (P["L"] - 2.0 * P["r_corner"]) + math.pi * P["r_corner"]
pappus = math.pi * r * r * centerline
check("C1 solid+volume", type(rod).__name__ == "Solid" and volume > 0
      and abs(volume - pappus) / pappus < 0.005,
      f"volume={volume:.3f} pappus={pappus:.3f}")

# C2
caps = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.center.y", ">=", P["D"] - 0.1),
    ql.prop("geom.center.y", "<=", P["D"] + 0.1),
)).resolve(rod)
ok2 = len(caps) == 2 and all(abs(f.get_area() - math.pi * r * r) < 1.0 for f in caps) \
    and all(abs(f.get_center().x - s * P["L"] / 2.0) < 0.05 for f, s in zip(sorted(caps, key=lambda f: f.get_center().x), (-1, 1)))
check("C2 end caps", ok2, f"n={len(caps)} areas={[f'{f.get_area():.2f}' for f in caps]}")

# C3
from OCP.Bnd import Bnd_Box  # noqa: E402
from OCP.BRepBndLib import BRepBndLib  # noqa: E402

box = Bnd_Box()
box.SetGap(0.0)
BRepBndLib.AddOptimal_s(rod.wrapped, box, useTriangulation=False)
xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
wants = (xmin, -(P["L"] / 2 + r)), (xmax, P["L"] / 2 + r), (ymin, -r), (ymax, P["D"]), (zmin, -r), (zmax, r)
check("C3 bbox", all(abs(g - w) < 0.05 for g, w in wants),
      f"x[{xmin:.2f},{xmax:.2f}] y[{ymin:.2f},{ymax:.2f}] z[{zmin:.2f},{zmax:.2f}]")

# C4
src = Path(u_link.__file__).read_text()
check("C4 R_corner>r guard", "R_CORNER" in src and P["r_corner"] > r,
      f"R={P['r_corner']} r={r}")

print(f"S1 verifier: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
