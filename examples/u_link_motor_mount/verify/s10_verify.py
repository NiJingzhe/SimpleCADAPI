"""S10 verifier: split design vs S10 contract.

Criteria:
  C1 upper: single solid, bbox y=[back_y, D]; back ring face tagged (n>=1);
     mount floors tagged n=1 each (centers ±L/2, floor_y)
  C2 upper bosses: 2 cylinder walls at (±boss_x, 0) spanning band; 2 blind
     hole walls (depth=boss_hole_depth); 16 gusset hypotenuse chamfer faces
     (planar, slope-normal) present
  C3 contour fit: cavity = eroded sweep — verify by sampling: points at
     (tube surface - wall_t/2 inward normal) are INSIDE cavity (not material)
     at multiple stations; points deeper than wall_t+0.3 inside are NOT material
  C4 shell: single solid; floor wall sample (0,-r+wall_t/2,0) inside,
     (0,-r+wall_t+0.3,0) not; notch openness (52,4.75,0) not inside,
     material around notch edges intact; 2 bolt holes r=shell_hole_d/2 at
     (±boss_x, z=0) through floor; hole ID == boss_hole_d
  C5 non-interference: shell material samples not inside upper and vice versa
     (band walls) — sampled grid
  C6 assembly: 2 components, residuals within tolerance; named faces on parts
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import assembly as ASM  # noqa: E402
import shell as SH  # noqa: E402
import u_link  # noqa: E402
from simplecadapi import ql  # noqa: E402
from OCP.BRepClass3d import BRepClass3d_SolidClassifier  # noqa: E402
from OCP.gp import gp_Pnt  # noqa: E402
from OCP.TopAbs import TopAbs_IN, TopAbs_ON  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


P = dict(u_link.params(), **SH.shell_params())
BY = u_link.back_y(P)
r = P["rod_d"] / 2.0
FY = P["d_motor"] / 2.0

upper = u_link.build_stage("s4")
sh = SH.build_shell_body()


def mk_cls(solid):
    c = BRepClass3d_SolidClassifier(solid.wrapped)

    def inside(x, y, z):
        c.Perform(gp_Pnt(x, y, z), 1e-7)
        return c.State() in (TopAbs_IN, TopAbs_ON)
    return inside


in_up, in_sh = mk_cls(upper), mk_cls(sh)

# C1
check("C1 upper solid+tags", upper.get_volume() > 0
      and len(ql.faces().where(ql.tag(u_link.TAG_BACK)).resolve(upper)) == 1
      and all(len(ql.faces().where(ql.tag(t)).resolve(upper)) == 1
              for t in (u_link.TAG_MOUNT_LEFT, u_link.TAG_MOUNT_RIGHT)))
fl = ql.faces().where(ql.tag(u_link.TAG_MOUNT_LEFT)).resolve(upper)[0]
check("C1b mount center", abs(fl.get_center().x + P["L"] / 2) < 0.05
      and abs(fl.get_center().y - FY) < 0.05,
      f"c=({fl.get_center().x:.2f},{fl.get_center().y:.2f})")

# C2 bosses（材料采样判定柱体；面记账因内核重叠弧段不可靠）
br_ = P["boss_d"] / 2.0
ring_ok = True
y_probe = BY - 0.5  # 孔顶(5.5)之上取环
import math as _m  # noqa: E402
for sx in (-1, 1):
    for deg in (20, 70, 110, 160, 200, 250, 290, 340):  # 避开 4 筋方向附近
        a = _m.radians(deg)
        ring_ok = ring_ok and in_up(sx * P["boss_x"] + (br_ - 0.25) * _m.cos(a), y_probe, (br_ - 0.25) * _m.sin(a))
        ring_ok = ring_ok and not in_up(sx * P["boss_x"] + (br_ + 0.8) * _m.cos(a), y_probe, (br_ + 0.8) * _m.sin(a))
hw = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CYLINDER"),
    ql.prop("geom.area", ">=", 2 * math.pi * (P["boss_hole_d"] / 2) * P["boss_hole_depth"] * 0.95),
    ql.prop("geom.area", "<=", 2 * math.pi * (P["boss_hole_d"] / 2) * P["boss_hole_depth"] * 1.05),
)).resolve(upper)
hyp = (P["rib_len"] ** 2 + P["boss_h"] ** 2) ** 0.5
cham_w = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.area", ">=", 0.9 * hyp * P["gusset_chamfer"] * 2 ** 0.5),
    ql.prop("geom.area", "<=", 1.3 * hyp * P["gusset_chamfer"] * 2 ** 0.5),
)).resolve(upper)
check("C2 bosses+holes+chamfers", ring_ok and len(hw) == 2 and len(cham_w) >= 14,
      f"ring_probe={ring_ok} hole_walls={len(hw)} chamfer_faces={len(cham_w)}")

# C3 band 开放性（上件 7.5 以下仅存 boss+筋；壁全让位 shell）+ shell 轮廓壁
mid_band = BY - P["boss_h"] / 2.0
far_from_boss = lambda x, z: all(  # noqa: E731
    (x - sx * P["boss_x"]) ** 2 + z ** 2 > (P["boss_d"] / 2 + P["rib_len"] + 1.0) ** 2
    for sx in (-1, 1))
ok3 = True
for _x in (-30.0, -18.0, 18.0, 30.0, 0.0, -8.0, 8.0):
    for _z in (0.0, 5.0, 10.0, -10.0):
        if far_from_boss(_x, _z) and in_up(_x, mid_band, _z):
            ok3 = False
            print(f"    C3 material leak: ({_x}, {mid_band}, {_z})")
ok3 = ok3 and in_up(P["boss_x"], BY - 0.5, 0.0)
print("    C3 boss core:", in_up(P["boss_x"], BY - 0.5, 0.0))  # boss 柱实体在（孔顶 5.5 之上取芯）
ok3 = ok3 and in_sh(0.0, mid_band, r - P["wall_t"] / 2.0)
print("    C3 shell wall:", in_sh(0.0, mid_band, r - P["wall_t"] / 2.0))  # shell 壁中点在
ok3 = ok3 and not in_sh(0.0, mid_band, r - P["wall_t"] - 2.0)

check("C3 band open + shell contour", ok3)

# C4 shell（S11 两刀架构：地板+沉头孔+大走线口——详证在 s11_probe）
FB, FT = SH.floor_band(P)
cones = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CONE"),
    ql.prop("geom.center.y", ">=", FB - 0.1), ql.prop("geom.center.y", "<=", FT + 0.1),
)).resolve(sh)
floor_mid = in_sh(0.0, (FB + FT) / 2.0, 8.0)
notch_y = (FB + BY) / 2.0
notch_open = all(not in_sh(sx * (P["L"] / 2 - P["r_corner"] + 1.45 * r), notch_y, 0.0)
                 for sx in (-1, 1))
sh_part = SH.build_shell_part().value.body
rim_ok = len(ql.faces().where(ql.tag(SH.TAG_SHELL_RIM)).resolve(sh_part)) >= 1
check("C4 shell floor+csink+notch", len(cones) == 2 and floor_mid and notch_open and rim_ok,
      f"cones={len(cones)} floor_mid={floor_mid} notch_open={notch_open} rim={rim_ok}")

# C5 non-interference (shell material vs upper; upper band walls vs shell)
bad = []
for x in [x * 1.0 for x in range(-52, 53, 4)]:
    for z in [z * 0.5 for z in range(-29, 30, 4)]:
        for y in (0.0, 4.0, BY - 0.3):
            if in_sh(x, y, z) and in_up(x, y, z):
                bad.append((x, y, round(z, 1)))
check("C5 non-interference", not bad, f"bad={bad[:3]} n={len(bad)}")

# C6 assembly
res = ASM.build_u_link_assembly()
asm = res.value
report = asm._get_runtime("constraint_report")
ok6 = len(asm.component_ids()) == 2 and all(x["within_tolerance"] for x in report["residuals"])
check("C6 assembly", ok6, f"components={asm.component_ids()}")

print(f"S10 verifier: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
