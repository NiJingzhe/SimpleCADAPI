"""S1 hypothesis probe: prove the S1 measurement set discriminates pass/fail.

Runs BEFORE the model source exists (verifier-first). Builds a hand replica of
the S1 substructure with nominal dims and exercises every planned check:
  H1 volume formula  V = pi/4*(od^2*t + boss_od^2*(top-t) - bore^2*top)
  H2 QL face cards   (boss top plane / bore wall cylinder / flange bottom annulus)
  H3 bbox            via BRepBndLib.AddOptimal_s (u_link lesson: Add_s bloats)
  H4 known-bad       replica WITHOUT boss must fail the volume gate (proof the
                     gate discriminates, not just passes)
"""
import math
import sys

import simplecadapi as scad
from simplecadapi import ql
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

OD, T, BOSS_OD, TOP, BORE = 100.0, 10.0, 55.0, 30.0, 30.0


def bbox_of(solid):
    box = Bnd_Box()
    box.SetGap(0.0)
    BRepBndLib.AddOptimal_s(solid.wrapped, box, useTriangulation=False)
    return box.Get()


def analytic_volume(with_boss=True, with_bore=True):
    v = math.pi / 4.0 * OD * OD * T
    if with_boss:
        v += math.pi / 4.0 * BOSS_OD * BOSS_OD * (TOP - T)
    if with_bore:
        v -= math.pi / 4.0 * BORE * BORE * TOP
    return v


def build_replica(with_boss=True, with_bore=True):
    body = scad.make_cylinder_rsolid(radius=OD / 2.0, height=T,
                                     bottom_face_center=(0.0, 0.0, 0.0), axis=(0.0, 0.0, 1.0))
    if with_boss:
        boss = scad.make_cylinder_rsolid(radius=BOSS_OD / 2.0, height=TOP - T,
                                         bottom_face_center=(0.0, 0.0, T), axis=(0.0, 0.0, 1.0))
        body = scad.union_rsolid(body, boss)
    if with_bore:
        bore = scad.make_cylinder_rsolid(radius=BORE / 2.0, height=TOP + 10.0,
                                         bottom_face_center=(0.0, 0.0, -5.0), axis=(0.0, 0.0, 1.0))
        body = scad.cut_rsolid(body, bore)
    return body


results = []


def h(name, ok, detail):
    print(f"{'PASS' if ok else 'FAIL'} {name}  {detail}")
    results.append((name, ok))


# H1 + H2 + H3 on the good replica
good = build_replica()
v = good.get_volume()
want_v = analytic_volume()
h("H1 volume formula", abs(v - want_v) / want_v < 0.005,
  f"measured={v:.3f} analytic={want_v:.3f} rel={abs(v-want_v)/want_v:.6f}")

faces = ql.faces().resolve(good)
print(f"face card: n={len(faces)}")
for f in faces:
    c = f.get_center()
    print(f"  type=? area={f.get_area():.3f} center=({c.x:.2f},{c.y:.2f},{c.z:.2f})")

# bore wall: the only CYLINDER face with area pi*30*30
bore_wall = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CYLINDER"),
    ql.prop("geom.area", ">=", math.pi * BORE * TOP - 1.0),
    ql.prop("geom.area", "<=", math.pi * BORE * TOP + 1.0),
)).resolve(good)
h("H2a bore wall card", len(bore_wall) == 1, f"n={len(bore_wall)} want_area={math.pi*BORE*TOP:.3f}")

# boss top plane: PLANE, z=30, annulus area pi*(27.5^2 - 15^2)  (bore pierces it)
boss_top = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.center.z", ">=", TOP - 0.1), ql.prop("geom.center.z", "<=", TOP + 0.1),
    ql.prop("geom.area", ">=", math.pi * ((BOSS_OD / 2.0) ** 2 - (BORE / 2.0) ** 2) - 1.0),
    ql.prop("geom.area", "<=", math.pi * ((BOSS_OD / 2.0) ** 2 - (BORE / 2.0) ** 2) + 1.0),
)).resolve(good)
h("H2b boss top annulus card", len(boss_top) == 1,
  f"n={len(boss_top)} want_area={math.pi*((BOSS_OD/2.0)**2-(BORE/2.0)**2):.3f}")

# flange bottom annulus: PLANE z=0, area pi*(50^2-15^2)
bottom = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.center.z", ">=", -0.1), ql.prop("geom.center.z", "<=", 0.1),
    ql.prop("geom.area", ">=", math.pi * ((OD / 2.0) ** 2 - (BORE / 2.0) ** 2) - 1.0),
    ql.prop("geom.area", "<=", math.pi * ((OD / 2.0) ** 2 - (BORE / 2.0) ** 2) + 1.0),
)).resolve(good)
h("H2c bottom annulus card", len(bottom) == 1,
  f"n={len(bottom)} want_area={math.pi*((OD/2.0)**2-(BORE/2.0)**2):.3f}")

xmin, ymin, zmin, xmax, ymax, zmax = bbox_of(good)
h("H3 bbox", abs(xmin + 50) < 0.05 and abs(xmax - 50) < 0.05 and abs(ymin + 50) < 0.05
  and abs(ymax - 50) < 0.05 and abs(zmin) < 0.05 and abs(zmax - TOP) < 0.05,
  f"x[{xmin:.2f},{xmax:.2f}] y[{ymin:.2f},{ymax:.2f}] z[{zmin:.2f},{zmax:.2f}]")

# H4 known-bad: replica without boss must FAIL the volume gate
bad = build_replica(with_boss=False)
vb = bad.get_volume()
want_bad = analytic_volume(with_boss=False)
h("H4 known-bad (no boss) fails volume gate", abs(vb - want_v) / want_v >= 0.005,
  f"no-boss volume={vb:.3f} vs good analytic={want_v:.3f} "
  f"(deviation {abs(vb-want_v)/want_v:.4%} must exceed 0.5%)")

ok_all = all(r for _, r in results)
print(f"S1 hypothesis: {'ALL PASS' if ok_all else 'FAILED'}")
sys.exit(0 if ok_all else 1)
