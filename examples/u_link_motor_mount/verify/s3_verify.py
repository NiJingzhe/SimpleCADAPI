"""S3 verifier: motor pockets + named mounting faces vs BUILD_PLAN S3 contract.

Criteria:
  C1 volume: V_s3 == V_s2 - 2*pi*rp^2*depth (exact pocket removal), single Solid
  C2 floors: exactly 2 planar +Y faces at y=d_motor/2, centers (±L/2, y, 0),
             area pi*rp^2 (rp = (rod_d-thickness)/2)
  C3 rims/walls: 2 annulus rims at y=D (pi*(r^2-rp^2)); 2 CYLINDER walls
             (2*pi*rp*depth, depth = D - d_motor/2)
  C4 NAMING: ql.tag(feature.motor_mount_floor_left/right) resolves exactly 1 face
             each, centers identical to C2 geometric selection  <- 用户核心需求
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402
from simplecadapi import ql  # noqa: E402

P = u_link.params()
r = P["rod_d"] / 2.0
rp = (P["rod_d"] - P["thickness"]) / 2.0
floor_y = P["d_motor"] / 2.0
depth = P["D"] - floor_y
failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


body = u_link.build_stage("s3")

# C1
v3 = body.get_volume()
v2 = u_link.build_stage("s2").get_volume()
expect = v2 - 2.0 * math.pi * rp * rp * depth
check("C1 pocket volume", type(body).__name__ == "Solid" and abs(v3 - expect) / expect < 0.001,
      f"v3={v3:.3f} expect={expect:.3f}")

# C2
floors = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.normal.y", ">=", 0.999),
    ql.prop("geom.center.y", ">=", floor_y - 0.1),
    ql.prop("geom.center.y", "<=", floor_y + 0.1),
)).resolve(body)
ok2 = len(floors) == 2 and all(abs(f.get_area() - math.pi * rp * rp) < 0.5 for f in floors) \
    and all(abs(f.get_center().x - s * P["L"] / 2.0) < 0.05
            for f, s in zip(sorted(floors, key=lambda f: f.get_center().x), (-1, 1)))
check("C2 floors", ok2, f"n={len(floors)} centers={[(round(f.get_center().x, 2), round(f.get_center().y, 2)) for f in floors]}")

# C3
rims = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.normal.y", ">=", 0.999),
    ql.prop("geom.center.y", ">=", P["D"] - 0.1),
    ql.prop("geom.center.y", "<=", P["D"] + 0.1),
)).resolve(body)
walls = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CYLINDER"),
    ql.prop("geom.area", ">=", 2.0 * math.pi * rp * depth * 0.98),
    ql.prop("geom.area", "<=", 2.0 * math.pi * rp * depth * 1.02),
)).resolve(body)
annulus = math.pi * (r * r - rp * rp)
check("C3 rims+walls", len(rims) == 2 and all(abs(f.get_area() - annulus) < 0.5 for f in rims)
      and len(walls) == 2,
      f"rims={len(rims)}@{[f'{f.get_area():.2f}' for f in rims]} walls={len(walls)}@{[f'{f.get_area():.2f}' for f in walls]}")

# C4
geo_centers = {}
for f in floors:
    geo_centers[round(f.get_center().x, 3)] = f.get_center()
for tag, want_x in ((u_link.TAG_MOUNT_LEFT, -P["L"] / 2.0), (u_link.TAG_MOUNT_RIGHT, P["L"] / 2.0)):
    hit = ql.faces().where(ql.tag(tag)).resolve(body)
    ok = len(hit) == 1 and abs(hit[0].get_center().x - want_x) < 0.05 \
        and abs(hit[0].get_center().y - floor_y) < 0.05 and abs(hit[0].get_area() - math.pi * rp * rp) < 0.5
    check(f"C4 {tag}", ok, f"n={len(hit)}" + (f" center=({hit[0].get_center().x:.2f},{hit[0].get_center().y:.2f})" if hit else ""))

print(f"S3 verifier: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
