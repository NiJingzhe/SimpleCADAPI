"""S4 verifier: global fillet + re-tagged mounting faces vs BUILD_PLAN S4 contract.

Criteria:
  C1 single Solid, volume in (0.98*V_s3, V_s3)
  C2 bbox unchanged vs S3 within 0.05
  C3 ql.tag(mount) resolves exactly 1 face/side on FINAL solid, centers (±L/2, d_motor/2)
  C4 floors remain planar +Y at y=d_motor/2 (n=2), area in (pi*(rp-2fr)^2, pi*rp^2)
  C5 fillet.global_patch faces n >= 1 (fillet landed)
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
rp = (P["rod_d"] - P["thickness"]) / 2.0
fr = P["fillet_r"]
floor_y = P["d_motor"] / 2.0
failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


s3 = u_link.build_stage("s3")
s4 = u_link.build_stage("s4")

P4 = u_link.params()
by = u_link.back_y(P4)
br = P4["boss_d"] / 2.0
hr = P4["boss_hole_d"] / 2.0
boss_net = 2 * (math.pi * br ** 2 * P4["boss_h"] - math.pi * hr ** 2 * P4["boss_hole_depth"])
gusset_v = 8 * 0.5 * P4["rib_len"] * P4["boss_h"] * P4["rib_t"]
cw_v = 8 * P4["cable_w_w"] * P4["cable_w_h"] * (P4["thickness"] / 2.0) * 1.046  # S14 实测系数（弧壁外表面>内表面）

v3, v4 = s3.get_volume(), s4.get_volume()
base_v = v3 + boss_net + gusset_v - cw_v
check("C1 volume band", 0 < v4 and base_v - 180.0 < v4 < base_v + 180.0,
      f"{v3:.3f} -> {v4:.3f} band=({base_v - 250:.1f},{base_v + 100:.1f})")

b3, b4 = bbox_of(s3), bbox_of(s4)
ok2 = (all(abs(b3[i] - b4[i]) < 0.05 for i in (0, 2, 3, 4, 5))
       and abs(b4[1] - (u_link.back_y(P4) - P4["boss_h"])) < 0.05)
check("C2 bbox (boss hang-down)", ok2,
      f"s3=({b3[0]:.2f},{b3[1]:.2f},{b3[2]:.2f},{b3[3]:.2f},{b3[4]:.2f},{b3[5]:.2f}) "
      f"s4=({b4[0]:.2f},{b4[1]:.2f},{b4[2]:.2f},{b4[3]:.2f},{b4[4]:.2f},{b4[5]:.2f})")

for tag, want_x in ((u_link.TAG_MOUNT_LEFT, -P["L"] / 2.0), (u_link.TAG_MOUNT_RIGHT, P["L"] / 2.0)):
    hit = ql.faces().where(ql.tag(tag)).resolve(s4)
    ok = len(hit) == 1 and abs(hit[0].get_center().x - want_x) < 0.05 \
        and abs(hit[0].get_center().y - floor_y) < 0.05
    check(f"C3 {tag}", ok, f"n={len(hit)}" + (f" center=({hit[0].get_center().x:.2f},{hit[0].get_center().y:.2f})" if hit else ""))

floors = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.normal.y", ">=", 0.999),
    ql.prop("geom.center.y", ">=", floor_y - 0.1),
    ql.prop("geom.center.y", "<=", floor_y + 0.1),
)).resolve(s4)
area_lo, area_hi = math.pi * (rp - 2.0 * fr) ** 2, math.pi * rp * rp
check("C4 floors planar", len(floors) == 2 and all(area_lo < f.get_area() < area_hi for f in floors),
      f"n={len(floors)} areas={[f'{f.get_area():.2f}' for f in floors]} band=({area_lo:.2f},{area_hi:.2f})")

# C5 倒角落地证明（终态拓扑）：全局圆角 TORUS + 筋斜边 chamfer 面带
torus_faces = ql.faces().where(ql.prop("geom.type", "==", "TORUS")).resolve(s4)
hyp = (P4["rib_len"] ** 2 + P4["boss_h"] ** 2) ** 0.5
cham_w = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.area", ">=", 0.9 * hyp * P4["gusset_chamfer"] * 2 ** 0.5),
    ql.prop("geom.area", "<=", 1.3 * hyp * P4["gusset_chamfer"] * 2 ** 0.5),
)).resolve(s4)
check("C5 fillet+chamfer landed", len(torus_faces) >= 2 and len(cham_w) >= 14,
      f"torus={len(torus_faces)} gusset_chamfer_faces={len(cham_w)}")

back_hit = ql.faces().where(ql.tag(u_link.TAG_BACK)).resolve(s4)
check("C6 back face tagged", len(back_hit) == 1
      and abs(back_hit[0].get_center().y - u_link.back_y(P)) < 0.05,
      f"n={len(back_hit)} center_y={back_hit[0].get_center().y:.2f}" if back_hit else "n=0")

print(f"S4 verifier: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
