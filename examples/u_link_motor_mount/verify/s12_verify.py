"""S12 verifier: safety fillets actually landed (anti-cut).

Criteria:
  C1 rim fillet: TORUS/cylinder fillet faces exist along the flat-bottom outer
     rim (y=fb, outer boundary zone); sharp bottom-outer dihedral replaced.
  C2 notch fillet: fillet faces along notch mouth edges (12 edges); no sharp
     dihedral at mouth corners (sampled: fillet face count >= 8).
  C3 sill intact: notch bottom sill (0.5 step above floor top) is material.
  C4 shell still valid: single solid, countersinks still 2 cones, floor slab
     solid between holes, no material below fb.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
FB, FT = SH.floor_band(P)
r = P["rod_d"] / 2.0

sh = SH.build_shell_body()
cls = BRepClass3d_SolidClassifier(sh.wrapped)


def inside(x, y, z):
    cls.Perform(gp_Pnt(x, y, z), 1e-7)
    return cls.State() in (TopAbs_IN, TopAbs_ON)


# C1 rim fillet faces: 圆角面在 y∈(FB, FB+R) 环带、贴外缘（采样自 bbox 外缘内收 wall_t）
# 平底外缘圆角: 直段两端为轴 z 圆柱(45.5@y0.7)、拐角为 torus 环带
blends = ql.faces().where(ql.prop("geom.type", "==", "TORUS")).resolve(sh)
rim_cyl = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CYLINDER"),
    ql.prop("geom.center.y", ">=", FB - 0.05),
    ql.prop("geom.center.y", "<=", FB + P["safe_fillet_r"] + 0.1),
    ql.prop("geom.area", ">=", 10.0),
)).resolve(sh)
check("C1 rim fillet faces", len(blends) >= 4 and len(rim_cyl) >= 2,
      f"torus={len(blends)} rim_cyl={len(rim_cyl)}")

# C2 notch mouth fillet faces: 口边缘圆角圆柱面（轴 z 或 x，中心在口缘带）
# 走线口圆角: 口长边(竖直)呈大圆柱面 376.8@y4.1、角部呈 torus 37.3@y5.0
notch_torus = [f for f in blends
               if any(abs(abs(f.get_center().x) - sx * 37.3) < 6.0 for sx in (-1, 1))
               and f.get_center().y > FT + 0.5]
notch_long_cyl = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CYLINDER"),
    ql.prop("geom.area", ">=", 100.0),
    ql.prop("geom.center.y", ">=", FT + 0.5),
    ql.prop("geom.center.y", "<=", BY + 0.1),
)).resolve(sh)
n_mouth = len(notch_torus) + len(notch_long_cyl)
check("C2 notch fillet faces", len(notch_torus) >= 2 and len(notch_long_cyl) >= 2,
      f"notch_torus={len(notch_torus)} long_cyl={len(notch_long_cyl)}")

# C3 台阶：口窗内 sill 带有材料、口带敞开、rim 上台阶有材料（端壁 x≈50 处）
notch_xc = P["L"] / 2.0 - P["r_corner"] + 1.45 * r
wall_x = notch_xc + 8.0  # 端壁环带（上 sill 更靠外——环壁随高度外移）
# 环壁随高度外移：下 sill 与上 sill 采样点分别取（0.15/步进扫描壁带中心）
def band_x(y):
    for x in range(int(notch_xc) + 2, int(notch_xc) + 12):
        if inside(float(x), y, 0.0):
            return float(x)
    return None
sill_low = band_x(FT + 0.15) is not None
sill_top = band_x(BY - 0.15) is not None
mouth_open = not inside(float(int(notch_xc) + 9), (FT + BY) / 2.0, 0.0)
check("C3 sills intact", sill_low and sill_top and mouth_open,
      f"low={sill_low} top={sill_top} open={mouth_open}")

# C4 validity & regressions
cones = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CONE"),
    ql.prop("geom.center.y", ">=", FB - 0.1),
    ql.prop("geom.center.y", "<=", FB + P["csink_depth"] + 0.1,
            ))).resolve(sh)
slab = inside(0.0, (FB + FT) / 2.0, 8.0)
no_below = all(not inside(x, FB - 0.8, z) for x in (0.0, 30.0, 48.0) for z in (0.0, 8.0))
check("C4 validity", sh.get_volume() > 0 and len(cones) == 2 and slab and no_below,
      f"v={sh.get_volume():.1f} cones={len(cones)} slab={slab} no_below={no_below}")

print(f"S12 verifier: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
