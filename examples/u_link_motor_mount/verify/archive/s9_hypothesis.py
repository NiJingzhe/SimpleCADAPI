"""
[ARCHIVED 2026-08-31, feat/ftc] Historical evidence of an abandoned/superseded stage — NOT a runnable verifier contract. See archive/README.md.
S9 hypothesis (final, chain-integrated): verify build_stage('s4').

  H1 4 boss cylinder walls at (±boss_x, ±boss_z), area >= 60% full
  H2 4 boss hole walls r=1.35 depth=boss_hole_depth
  H3 ribs present (volume band: cavity+boss+ribs-holes)
  H4 boss top chamfer: 4 annulus top faces at y=back_y, area ~= pi((br-ch)^2-hr^2)
  H5 named faces (mount/back) resolve
  H6 boss avoids motor pc holes (analytic, mirrors guard)
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402
from simplecadapi import ql  # noqa: E402

P = u_link.params()
by = u_link.back_y(P)
floor_y = by + P["cavity_h"]
br = P["boss_d"] / 2.0
hr = P["boss_hole_d"] / 2.0
failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


body = u_link.build_stage("s4")

# H1: boss cylinder walls (split into segments by ribs/fillets; sum by boss position)
full_wall = 2 * math.pi * br * P["cavity_h"]
seg_walls = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CYLINDER"),
    ql.prop("geom.area", ">=", 3.0),
    ql.prop("geom.area", "<=", 40.0),   # 排除整柱/孔壁（分段柱面 ~35.6）
    ql.prop("geom.center.y", ">=", by + 1.5),  # 柱面段 y心≈9.2; 孔壁 8.75 排除
    ql.prop("geom.center.y", "<=", floor_y + 0.3),
)).resolve(body)
per_boss = {pos: 0.0 for pos in pos_list} if (pos_list := u_link._boss_positions(P)) else {}
for f in seg_walls:
    c = f.get_center()
    for bx, bz in pos_list:
        if abs(c.x - bx) < 0.1 and abs(c.z - bz) < 0.1:
            per_boss[(bx, bz)] += f.get_area()
ok1 = all(0.55 * full_wall <= a <= 1.05 * full_wall for a in per_boss.values())
check("H1 boss walls", ok1,
      f"n_seg={len(seg_walls)} per_boss={{{', '.join(f'{a:.1f}' for a in per_boss.values())}}} full={full_wall:.1f}")

# H2
hole_walls = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CYLINDER"),
    ql.prop("geom.area", ">=", 2 * math.pi * hr * P["boss_hole_depth"] * 0.98),
    ql.prop("geom.area", "<=", 2 * math.pi * hr * P["boss_hole_depth"] * 1.02),
)).resolve(body)
check("H2 boss hole walls", len(hole_walls) == 4, f"n={len(hole_walls)} areas={[f'{f.get_area():.1f}' for f in hole_walls]}")

# H3 volume band: v4 = v3 - cavity + bosses + ribs - fillet/chamfer
v4 = body.get_volume()
v3 = u_link.build_stage("s3").get_volume()
cavity_v = (2 * P["waist_x"] * 2 * P["waist_z"] + 2 * (P["pocket_x2"] - P["waist_x"]) * 2 * P["pocket_z"]) * P["cavity_h"]
boss_net = 4 * (math.pi * br ** 2 * P["cavity_h"] - math.pi * hr ** 2 * P["boss_hole_depth"])
rib_max = 8 * (br + P["rib_len"] - hr - 0.5) * P["rib_h"] * P["rib_t"]
lo = v3 - cavity_v + boss_net - 400.0  # 含全局倒角+chamfer 材料损失余量
hi = v3 - cavity_v + boss_net + rib_max + 50.0
check("H3 volume band", lo < v4 < hi,
      f"v4={v4:.1f} band=({lo:.1f},{hi:.1f}) cavity_v={cavity_v:.1f} boss_net={boss_net:.1f}")

# H4 boss top faces
tops = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.normal.y", "<=", -0.999),
    ql.prop("geom.center.y", ">=", by - 0.05),
    ql.prop("geom.center.y", "<=", by + 0.05),
    ql.prop("geom.area", ">=", 2.0), ql.prop("geom.area", "<=", 30.0),
)).resolve(body)
annulus = math.pi * ((br - P["boss_chamfer"]) ** 2 - hr ** 2)
check("H4 boss tops chamfered", len(tops) == 4 and all(abs(f.get_area() - annulus) < 1.5 for f in tops),
      f"n={len(tops)} areas={[f'{f.get_area():.2f}' for f in tops]} annulus~{annulus:.2f}")

# H5
ok5 = all(len(ql.faces().where(ql.tag(t)).resolve(body)) == 1
          for t in (u_link.TAG_MOUNT_LEFT, u_link.TAG_MOUNT_RIGHT, u_link.TAG_BACK))
check("H5 named faces", ok5)

# H6 motor-hole clearance (analytic)
worst = 99.0
for cx in (-P["L"] / 2.0, P["L"] / 2.0):
    for ang in (45.0, 135.0, 225.0, 315.0):
        a = math.radians(ang)
        px, pz = cx + P["motor_pc"] * math.cos(a), P["motor_pc"] * math.sin(a)
        for bx, bz in pos_list:
            worst = min(worst, math.hypot(px - bx, pz - bz))
check("H6 boss-pc clearance", worst >= br + 1.5 + 1.0, f"worst={worst:.2f} need>={br + 2.5:.2f}")

print(f"S9 hypothesis: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
