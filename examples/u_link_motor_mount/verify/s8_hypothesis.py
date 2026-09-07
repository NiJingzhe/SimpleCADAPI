"""S8 hypothesis: cavity+snap holes live in the chain (single session).

H1 cavity floor: ONE planar +Y face at y=back_y+cavity_h, area ~= outline.
H2 snap holes: 4 cylindrical walls r=1.25 len=4.
H3 fillet excluding 8 hole rims succeeds; rim edges correctly identified (8).
H4 membrane grid on final solid: floor+fillet+1.0 material above floor.
H5 named faces (mount/back) resolve on final solid.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402
from simplecadapi import ql  # noqa: E402
from OCP.BRepClass3d import BRepClass3d_SolidClassifier  # noqa: E402
from OCP.gp import gp_Pnt  # noqa: E402
from OCP.TopAbs import TopAbs_IN, TopAbs_ON  # noqa: E402

P = u_link.params()
by = u_link.back_y(P)
floor_y = by + P["cavity_h"]
failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


body = u_link.build_stage("s4")

# H1
floors = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.normal.y", ">=", 0.999),
    ql.prop("geom.center.y", ">=", floor_y - 0.05),
    ql.prop("geom.center.y", "<=", floor_y + 0.05),
)).resolve(body)
area_expect = 2 * P["waist_x"] * 2 * P["waist_z"] + 2 * (P["pocket_x2"] - P["waist_x"]) * 2 * P["pocket_z"]
check("H1 cavity floor", len(floors) == 1 and floors[0].get_area() > 0.9 * area_expect,
      f"n={len(floors)} area={floors[0].get_area():.1f} expect~{area_expect:.1f}" if floors else "n=0")

# H2
walls = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CYLINDER"),
    ql.prop("geom.area", ">=", 2 * math.pi * (P["snap_hole_d"] / 2) * P["snap_hole_len"] * 0.9),
    ql.prop("geom.area", "<=", 2 * math.pi * (P["snap_hole_d"] / 2) * P["snap_hole_len"] * 1.1),
)).resolve(body)
check("H2 snap hole walls", len(walls) == 4, f"n={len(walls)} areas={[f'{w.get_area():.2f}' for w in walls]}")

# H3 (rim identification already asserted inside chain; verify fillet landed)
patch = ql.faces().where(ql.tag("fillet.global_patch")).resolve(body)
check("H3 fillet landed", len(patch) >= 1, f"patch faces n={len(patch)}")

# H4 membrane grid
cls = BRepClass3d_SolidClassifier(body.wrapped)


def inside(x, y, z):
    cls.Perform(gp_Pnt(x, y, z), 1e-7)
    return cls.State() in (TopAbs_IN, TopAbs_ON)


def in_outline(x, z):
    return abs(z) <= P["waist_z"] + 0.01 or (
        P["waist_x"] <= abs(x) <= P["pocket_x2"] + 0.01 and abs(z) <= P["pocket_z"] + 0.01)


bad = 0
n = 0
for xi in range(-33, 34, 2):
    x = xi * 1.5
    for zi in range(-15, 16, 2):
        z = zi * 0.5
        if in_outline(x, z):
            n += 1
            if not inside(x, floor_y + P["fillet_r"] + 1.0, z):
                bad += 1
check("H4 membrane above floor", bad == 0, f"grid n={n} bad={bad}")

# H5
ok5 = True
for tag in (u_link.TAG_MOUNT_LEFT, u_link.TAG_MOUNT_RIGHT, u_link.TAG_BACK):
    hit = ql.faces().where(ql.tag(tag)).resolve(body)
    ok5 = ok5 and len(hit) == 1
check("H5 named faces", ok5)

# H6 pc=8 coverage (2D analytic)
pc = 8.0
hole_r = 1.5
pts = []
for deg in (45, 135, 225, 315):
    a = math.radians(deg)
    for cx in (-P["L"] / 2.0, P["L"] / 2.0):
        pts.append((cx + pc * math.cos(a), pc * math.sin(a)))
bad_pts = [(x, z) for x, z in pts if not in_outline(x, z)]
# hole edge worst point: center + r towards +x and +z diag already included by r
edge_bad = []
for x, z in pts:
    for dx, dz in ((hole_r, 0), (0, hole_r), (hole_r / math.sqrt(2), hole_r / math.sqrt(2))):
        if not in_outline(x + dx * math.copysign(1, x), z + dz):
            edge_bad.append((round(x + dx, 2), round(z + dz, 2)))
check("H6 pc=8 coverage", not bad_pts and not edge_bad,
      f"centers_bad={bad_pts} edges_bad={edge_bad}")

print(f"S8 hypothesis: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
