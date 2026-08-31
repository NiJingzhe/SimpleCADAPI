"""
[ARCHIVED 2026-08-31, feat/ftc] Historical evidence of an abandoned/superseded stage — NOT a runnable verifier contract. See archive/README.md.
S9 verifier: cover geometry + fit + assembly vs S9 contract.

Criteria:
  C1 cover: single solid, bbox x[±(pocket_x2-clr)] y[back_y, back_y+cover_t] z[±(pocket_z-clr)]
  C2 cover holes: 4 walls r=cover_hole_d/2 len=cover_t at boss positions
  C3 fit (analytic): cover outline inside cavity outline by cover_clr on outer bounds
  C4 body-cover non-intersection: common volume == 0 (except boss-through-hole
     clearance >0: min radial gap = cover_hole_d/2 - boss_d/2)
  C5 assembly: solve residuals within tolerance; 2 components
  C6 named faces on body part still resolve (mount x2 + back)
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import assembly as ASM  # noqa: E402
import cover as CV  # noqa: E402
import u_link  # noqa: E402
from simplecadapi import ql  # noqa: E402

from s1_hypothesis import bbox_of  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


P = dict(u_link.params(), **CV.cover_params())
by = u_link.back_y(P)
clr, t = P["cover_clr"], P["cover_t"]

# C1
cbody = CV.build_cover_body()
xs = bbox_of(cbody)
wants = (xs[0], -(P["pocket_x2"] - clr)), (xs[3], P["pocket_x2"] - clr), \
    (xs[1], by), (xs[4], by + t), (xs[2], -(P["pocket_z"] - clr)), (xs[5], P["pocket_z"] - clr)
check("C1 cover bbox", type(cbody).__name__ == "Solid" and cbody.get_volume() > 0
      and all(abs(g - w) < 0.05 for g, w in wants),
      f"x[{xs[0]:.2f},{xs[3]:.2f}] y[{xs[1]:.2f},{xs[4]:.2f}] z[{xs[2]:.2f},{xs[5]:.2f}]")

# C2
cr = P["cover_hole_d"] / 2.0
walls = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CYLINDER"),
    ql.prop("geom.area", ">=", 2 * math.pi * cr * t * 0.95),
    ql.prop("geom.area", "<=", 2 * math.pi * cr * t * 1.05),
)).resolve(cbody)
pos = u_link._boss_positions(P)
ok2 = len(walls) == 4 and all(
    any(abs(w.get_center().x - bx) < 0.1 and abs(w.get_center().z - bz) < 0.1 for bx, bz in pos)
    for w in walls)
check("C2 cover holes at boss positions", ok2, f"n={len(walls)}")

# C3 analytic outline containment (outer bounds inset by clr)
ok3 = (P["waist_z"] - clr > 0 and P["pocket_z"] - clr > 0
       and P["pocket_x2"] - clr > P["waist_x"]
       and cr + 0.3 <= P["pocket_z"] - clr - P["boss_z"] + cr  # hole fits in pocket half-width
       and all(P["boss_x"] + cr + 0.3 <= P["pocket_x2"] - clr for _ in (0,))
       and all(P["boss_z"] + cr + 0.3 <= P["pocket_z"] - clr for _ in (0,)))
check("C3 outline containment", ok3,
      f"gap_z={P['pocket_z'] - clr - (P['boss_z'] + cr):.2f} gap_x={P['pocket_x2'] - clr - (P['boss_x'] + cr):.2f}")

# C4 interference: sample cover interior points, none may lie inside body
# (boolean common on disjoint solids is rejected by validation -> classifier probe)
from OCP.BRepClass3d import BRepClass3d_SolidClassifier  # noqa: E402
from OCP.gp import gp_Pnt  # noqa: E402
from OCP.TopAbs import TopAbs_IN, TopAbs_ON  # noqa: E402

bbody = u_link.build_stage("s4")
cls = BRepClass3d_SolidClassifier(bbody.wrapped)
bad = []
ymid = by + t / 2.0
for xi in range(-47, 48, 2):
    x = xi * 1.0
    for zi in range(-7, 8, 1):
        z = zi * 1.0
        in_cover = (abs(z) <= P["waist_z"] - clr - 0.3 and abs(x) <= P["waist_x"] + clr - 0.3) or (
            P["waist_x"] + 0.3 <= abs(x) <= P["pocket_x2"] - clr - 0.3
            and abs(z) <= P["pocket_z"] - clr - 0.3)
        if not in_cover:
            continue
        if any((x - bx) ** 2 + (z - bz) ** 2 <= (cr + 0.3) ** 2 for bx, bz in pos):
            continue  # hole zone
        cls.Perform(gp_Pnt(x, ymid, z), 1e-7)
        if cls.State() in (TopAbs_IN, TopAbs_ON):
            bad.append((x, round(z, 1)))
radial_gap = cr - P["boss_d"] / 2.0
check("C4 zero interference", not bad and radial_gap > 0,
      f"bad_samples={bad[:4]} n_bad={len(bad)} radial_gap={radial_gap:.2f}")

# C5 assembly
result = ASM.build_u_link_assembly()
asm = result.value
report = asm._get_runtime("constraint_report")
ok5 = len(asm.component_ids()) == 2 and all(r["within_tolerance"] for r in report["residuals"])
check("C5 assembly solve", ok5,
      f"components={asm.component_ids()} residuals={report['residuals']}")

# C6 named faces on body part (fresh @part build)
body_part = u_link.build_u_link_part().value.body
ok6 = all(len(ql.faces().where(ql.tag(t)).resolve(body_part)) == 1
          for t in (u_link.TAG_MOUNT_LEFT, u_link.TAG_MOUNT_RIGHT, u_link.TAG_BACK))
check("C6 named faces on part", ok6)

print(f"S9 verifier: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
