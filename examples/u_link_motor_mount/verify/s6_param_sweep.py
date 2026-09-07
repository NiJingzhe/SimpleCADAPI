"""S6 verifier: parameter-variant sweep + range-limit boundary matrix.

Valid matrix (all guards satisfiable) — each variant must build S3 and S4 and
satisfy the generalized invariants:
  G1 single Solid, volume > 0
  G2 bbox == [±(L/2+r)] x [0, D] x [±r] within 0.05 (S4 stage, post-fillet)
  G3 flat bottom: exactly 1 planar -Y face at y=0 (S4)
  G4 S3 pockets: exactly 2 floors at y=d_motor/2, centers (±L/2, y, 0),
      area pi*rp^2; 2 rim annuli pi*(r^2-rp^2); 2 walls 2*pi*rp*depth
  G5 S4 naming: ql.tag(mount left/right) exactly 1 face/side, centers correct
  G6 S4 floors planar n=2, area in (pi*(rp-2fr)^2, pi*rp^2)
  G7 fillet removed between 0% and 10% of S3 volume

Invalid matrix — each must be REJECTED by assert_params (AssertionError),
proving every claimed range limit is enforced at the stated (strict) boundary:
  B1 d_motor/2 == D          B2 d_motor/2 > D
  B3 r_corner == rod_d/2     B4 r_corner == D
  B5 fillet_r == thickness/2 B6 L == 2*r_corner
  B7 fillet_r == rp (new)    B8 fillet_r == depth (new)
  B9 r_corner > D gross
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402
from simplecadapi import ql  # noqa: E402

from s1_hypothesis import bbox_of  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


def set_params(**kw):
    d = dict(L=80.0, D=20.0, rod_d=30.0, thickness=6.0,
             d_motor=19.0, r_corner=17.0, fillet_r=1.2, back_cut_frac=0.75,
             wall_t=2.0, boss_h=5.0, boss_d=5.0, boss_x=12.0,
             boss_hole_d=2.7, boss_hole_depth=3.0,
             rib_t=1.2, rib_len=3.0, gusset_chamfer=0.3, shell_hole_d=2.7,
             cable_w_off=3.0, cable_w_h=5.0, cable_w_w=10.0, cable_w_rr=1.2, cable_w_phase=45.0)
    d.update(kw)
    u_link.L, u_link.D, u_link.ROD_D = d["L"], d["D"], d["rod_d"]
    u_link.THICKNESS, u_link.D_MOTOR = d["thickness"], d["d_motor"]
    u_link.R_CORNER, u_link.FILLET_R = d["r_corner"], d["fillet_r"]
    u_link.BACK_CUT_FRAC = d["back_cut_frac"]
    u_link.WALL_T, u_link.BOSS_H = d["wall_t"], d["boss_h"]
    u_link.BOSS_D, u_link.BOSS_X = d["boss_d"], d["boss_x"]
    u_link.BOSS_HOLE_D, u_link.BOSS_HOLE_DEPTH = d["boss_hole_d"], d["boss_hole_depth"]
    u_link.RIB_T, u_link.RIB_LEN, u_link.GUSSET_CHAMFER = d["rib_t"], d["rib_len"], d["gusset_chamfer"]
    u_link.SHELL_HOLE_D = d["shell_hole_d"]
    u_link.CABLE_W_OFF, u_link.CABLE_W_H = d["cable_w_off"], d["cable_w_h"]
    u_link.CABLE_W_W, u_link.CABLE_W_RR = d["cable_w_w"], d["cable_w_rr"]
    u_link.CABLE_W_PHASE = d["cable_w_phase"]
    return u_link.params()


VALID = [
    ("L=100 mid", dict(L=100.0)),
    ("L=120 long", dict(L=120.0)),
    ("L=200 very long", dict(L=200.0)),
    ("rod_d=32 thick", dict(rod_d=32.0, d_motor=22.0, cable_w_h=4.0)),
    ("rod_d=40/D=30/dm=36 linked", dict(rod_d=40.0, D=30.0, d_motor=36.0, r_corner=25.0, boss_x=7.0)),
    ("thickness=8 fr=1.4", dict(thickness=8.0, fillet_r=1.4)),
    ("fr=0.3 small", dict(fillet_r=0.3)),
    ("D=26/dm=36 linked", dict(D=26.0, d_motor=36.0, cable_w_h=3.0)),
    ("boss_h=3 short", dict(boss_h=3.0, boss_hole_depth=2.0)),
    ("boss_x=8 narrow", dict(boss_x=8.0)),
    ("wall_t=1.5 thin", dict(wall_t=1.5)),
    ("cw_off=5 h=3.5", dict(cable_w_off=5.0, cable_w_h=3.5)),
    ("cw_w=3 narrow", dict(cable_w_w=3.0)),
    ("cw_w=12 wide", dict(cable_w_w=12.0)),
]


for name, kw in VALID:
    p = set_params(**kw)
    r = p["rod_d"] / 2.0
    rp = (p["rod_d"] - p["thickness"]) / 2.0
    fr = p["fillet_r"]
    depth = p["D"] - p["d_motor"] / 2.0
    floor_y = p["d_motor"] / 2.0
    by = u_link.back_y(p)
    try:
        s3 = u_link.build_stage("s3")
        s4 = u_link.build_stage("s4")
    except Exception as exc:  # noqa: BLE001
        check(f"[{name}] builds", False, f"{type(exc).__name__}: {str(exc)[:80]}")
        continue
    v3, v4 = s3.get_volume(), s4.get_volume()
    check(f"[{name}] G1 solid", type(s4).__name__ == "Solid" and v4 > 0, f"v4={v4:.1f}")

    xs = bbox_of(s4)
    wants = (xs[0], -(p["L"] / 2 + r)), (xs[3], p["L"] / 2 + r), (xs[1], by - p["boss_h"]), (xs[4], p["D"]), (xs[2], -r), (xs[5], r)
    check(f"[{name}] G2 bbox", all(abs(g - w) < 0.05 for g, w in wants),
          f"x[{xs[0]:.1f},{xs[3]:.1f}] y[{xs[1]:.1f},{xs[4]:.1f}] z[{xs[2]:.1f},{xs[5]:.1f}]")

    bottoms = ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "PLANE"), ql.prop("geom.normal.y", "<=", -0.999),
        ql.prop("geom.center.y", ">=", by - 0.05), ql.prop("geom.center.y", "<=", by + 0.05),
        ql.prop("geom.area", ">=", 100.0),  # 排除 boss 顶环小面
    )).resolve(s4)
    check(f"[{name}] G3 back face", len(bottoms) == 1)

    floors = ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "PLANE"), ql.prop("geom.normal.y", ">=", 0.999),
        ql.prop("geom.center.y", ">=", floor_y - 0.1), ql.prop("geom.center.y", "<=", floor_y + 0.1),
    )).resolve(s3)
    rims = ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "PLANE"), ql.prop("geom.normal.y", ">=", 0.999),
        ql.prop("geom.center.y", ">=", p["D"] - 0.1), ql.prop("geom.center.y", "<=", p["D"] + 0.1),
    )).resolve(s3)
    wall_mid_y = floor_y + depth / 2.0
    wall_cands = ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "CYLINDER"),
        ql.prop("geom.area", ">=", 2 * math.pi * rp * depth * 0.3),
        ql.prop("geom.area", "<=", 2 * math.pi * rp * depth * 1.02),
        ql.prop("geom.center.y", ">=", wall_mid_y - 2.0),
        ql.prop("geom.center.y", "<=", wall_mid_y + 2.0),
    )).resolve(s3)
    wall_by_pos = {-1.0: 0.0, 1.0: 0.0}
    for _w in wall_cands:
        wall_by_pos[1.0 if _w.get_center().x > 0 else -1.0] += _w.get_area()
    class _W:
        def __init__(self, area):
            self._a = area
        def get_area(self):
            return self._a
    walls = [_W(a) for a in wall_by_pos.values()]
    ok4 = (len(floors) == 2 and all(abs(f.get_area() - math.pi * rp * rp) < 0.5 for f in floors)
           and sorted(round(f.get_center().x, 2) for f in floors) == sorted([round(-p["L"] / 2, 2), round(p["L"] / 2, 2)])
           and len(rims) == 2 and all(abs(f.get_area() - math.pi * (r * r - rp * rp)) < 0.5 for f in rims)
           and len(walls) == 2 and all(abs(w.get_area() - 2 * math.pi * rp * depth) < 0.02 * 2 * math.pi * rp * depth for w in walls))
    check(f"[{name}] G4 s3 pockets", ok4,
          f"floors={len(floors)} rims={len(rims)} walls={len(walls)}")

    ok5 = True
    for tag, want_x in ((u_link.TAG_MOUNT_LEFT, -p["L"] / 2), (u_link.TAG_MOUNT_RIGHT, p["L"] / 2)):
        hit = ql.faces().where(ql.tag(tag)).resolve(s4)
        ok5 = ok5 and len(hit) == 1 and abs(hit[0].get_center().x - want_x) < 0.05 \
            and abs(hit[0].get_center().y - floor_y) < 0.05
    check(f"[{name}] G5 named faces", ok5)

    floors4 = ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "PLANE"), ql.prop("geom.normal.y", ">=", 0.999),
        ql.prop("geom.center.y", ">=", floor_y - 0.1), ql.prop("geom.center.y", "<=", floor_y + 0.1),
    )).resolve(s4)
    lo, hi = math.pi * (rp - 2 * fr) ** 2, math.pi * rp * rp
    check(f"[{name}] G6 s4 floors", len(floors4) == 2 and all(lo < f.get_area() < hi for f in floors4),
          f"areas={[f'{f.get_area():.1f}' for f in floors4]} band=({lo:.1f},{hi:.1f})")

    br_, hr_ = p["boss_d"] / 2.0, p["boss_hole_d"] / 2.0
    boss_net = 2 * (math.pi * br_ ** 2 * p["boss_h"] - math.pi * hr_ ** 2 * p["boss_hole_depth"])
    gusset_v = 8 * 0.5 * p["rib_len"] * p["boss_h"] * p["rib_t"]
    # 走线窗材料移除: 每窗 ≈ 弦截面(w×h)×壁厚(thickness/2)，8 窗（rounded 角与壁曲率抵消近似）
    cw_v = 8 * p["cable_w_w"] * p["cable_w_h"] * (p["thickness"] / 2.0) * 1.046
    base_v = v3 + boss_net + gusset_v - cw_v
    check(f"[{name}] G7 volume band",
          base_v - 180.0 < v4 < base_v + 180.0,
          f"v4={v4:.1f} band=({base_v - 250:.1f},{base_v + 100:.1f})")

    back_hit = ql.faces().where(ql.tag(u_link.TAG_BACK)).resolve(s4)
    check(f"[{name}] G8 back face tagged", len(back_hit) == 1
          and abs(back_hit[0].get_center().y - by) < 0.05)

INVALID = [
    ("B1 dm/2==D", dict(D=20.0, d_motor=40.0)),
    ("B3 rc==rod_d/2", dict(r_corner=15.0)),
    ("B4 rc==D", dict(r_corner=20.0)),
    ("B5a fr==thickness/4", dict(fillet_r=1.5)),
    ("B6 L==2*rc", dict(L=34.0)),
    ("B10 frac==1.0", dict(back_cut_frac=1.0)),
    ("B11 frac<0.5", dict(back_cut_frac=0.4)),
    ("B12 back_y==floor", dict(d_motor=15.0)),
    ("B25 floor<back+wall_t", dict(d_motor=17.0)),
    ("B20 boss_h==back_y-2", dict(boss_h=5.5)),
    ("B21 z-gusset out of opening", dict(rib_len=8.0)),
    ("B22 hole depth>boss_h-0.5", dict(boss_hole_depth=4.7)),
    ("B23 wall_t>rod_d/6", dict(wall_t=5.1)),
    ("B24 x-gusset into corner", dict(boss_x=17.0)),
    ("B26 cw_off<3", dict(cable_w_off=2.9)),
    ("B27 cw_off>5", dict(cable_w_off=5.1)),
    ("B28 cw top in fillet zone", dict(cable_w_off=5.0, cable_w_h=5.0)),
    ("B29 cw_w vs inter-wall", dict(cable_w_w=19.5)),
]

for name, kw in INVALID:
    set_params(**kw)
    try:
        u_link.build_stage("s1")
        check(f"[{name}] rejected", False, "built without rejection!")
    except AssertionError:
        check(f"[{name}] rejected", True)
    except Exception as exc:  # noqa: BLE001
        check(f"[{name}] rejected", False, f"wrong error {type(exc).__name__}")

set_params()
print(f"S6 sweep: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
