"""S13 probe: pocket-wall cable-window direction openness map + tool sanity.

P1 openness map: for each pocket axis (±L/2, ·, 0), cast radial rays at window
   heights y ∈ {13, 15, 17}; walk r from 12.3 (just outside pocket bore) to 24;
   phase OPEN if material ends by r<=16 and stays air to 24 (cable can exit);
   phase BLIND if material persists (corner blend / bottom tube).
P2 candidate cut: 45°-phased rounded-rect windows (2 through-prisms per pocket)
   on the s3 body; sample: window mid-ray open, inter-window wall intact,
   bottom offset = floor+3 material boundary.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402
import simplecadapi as scad  # noqa: E402
from OCP.BRepClass3d import BRepClass3d_SolidClassifier  # noqa: E402
from OCP.gp import gp_Pnt  # noqa: E402
from OCP.TopAbs import TopAbs_IN, TopAbs_ON  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


P = u_link.params()
BY = u_link.back_y(P)
FY = P["d_motor"] / 2.0
r = P["rod_d"] / 2.0
OFF, H, W, RR, PHASE = 3.0, 5.0, 5.0, 1.2, 45.0

body = u_link.build_stage("s3")
cls = BRepClass3d_SolidClassifier(body.wrapped)


def inside(x, y, z):
    cls.Perform(gp_Pnt(x, y, z), 1e-7)
    return cls.State() in (TopAbs_IN, TopAbs_ON)


# P1 openness map
print("P1 openness (per phase: open at y=13/15/17):")
open_phases = {}
for phi_deg in range(0, 360, 15):
    states = []
    for y in (13.0, 15.0, 17.0):
        ok_all = True
        for xc in (-P["L"] / 2, P["L"] / 2):
            a = math.radians(phi_deg)
            ray_mat = [inside(xc + rr_ * math.cos(a), y, rr_ * math.sin(a))
                       for rr_ in [12.3 + 0.25 * i for i in range(int((24 - 12.3) / 0.25))]]
            # 材料须在 r<=16 内终止且之后全空
            last_mat = max(i for i, m in enumerate(ray_mat) if m) if any(ray_mat) else -1
            end_r = 12.3 + 0.25 * last_mat
            open_dir = end_r <= 16.0 and not any(ray_mat[last_mat + 1:])
            ok_all = ok_all and open_dir
        states.append("O" if ok_all else "x")
    open_phases[phi_deg] = states
    print(f"  {phi_deg:3d}°: {''.join(states)}")

# 期望: ±Z(90/270) 与外侧(180 for left? 注意 ±L/2 对称: 0°=+X 对右槽是外侧、对左槽是内侧)
diag_ok = all(open_phases[a] == ["O", "O", "O"] for a in (45, 135, 225, 315))
inward_bad = open_phases[0] != ["O", "O", "O"] or open_phases[180] != ["O", "O", "O"]
print(f"P1 diag45 all open: {diag_ok}; inward(0/180) blocked somewhere: {inward_bad}")
check("P1 direction map", diag_ok and inward_bad,
      f"0°:{open_phases[0]} 90°:{open_phases[90]} 180°:{open_phases[180]} 45°:{open_phases[45]}")

# P2: 直接验证链成品（S13 已入链；跨 session 工具构造不可行——s8/s13 两次教训）
body4 = u_link.build_stage("s4")
cls2 = BRepClass3d_SolidClassifier(body4.wrapped)


def ins(x, y, z):
    cls2.Perform(gp_Pnt(x, y, z), 1e-7)
    return cls2.State() in (TopAbs_IN, TopAbs_ON)


y_mid = FY + OFF + H / 2.0
mid_r = 13.5
opens, walls = [], []
for xc in (-P["L"] / 2, P["L"] / 2):
    for phi in (45, 135, 225, 315):
        a = math.radians(phi)
        opens.append(not ins(xc + mid_r * math.cos(a), y_mid, mid_r * math.sin(a)))
    for phi in (0, 90, 180, 270):  # 窗间壁完好
        a = math.radians(phi)
        walls.append(ins(xc + mid_r * math.cos(a), y_mid, mid_r * math.sin(a)))
a45 = math.radians(45)
bottoms = [ins(xc + mid_r * math.cos(a45), FY + OFF - 0.3, mid_r * math.sin(a45))
           for xc in (-P["L"] / 2, P["L"] / 2)]
above = [not ins(xc + mid_r * math.cos(a45), FY + OFF + 0.3, mid_r * math.sin(a45))
         for xc in (-P["L"] / 2, P["L"] / 2)]
check("P2 windows open(8)", all(opens), f"{opens}")
check("P2 inter-window walls", all(walls), f"{walls}")
check("P2 bottom offset = 3mm", all(bottoms) and all(above), f"below={bottoms} above={above}")

print(f"S13 probe: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
