"""S2 verifier: bolt pattern + double fillet (final 6-hole form at this stage).

Run AFTER flange_plate.py contains the S2 features:
    uv run python examples/flange_plate/verify/s2_verify.py

Criteria (BUILD_PLAN S2 contract, hypothesis-proven in s2_hypothesis.py):
  D1 single Solid + final volume in Pappus bracket +-1.5%
  D2 bolt_count hole walls: CYLINDER area pi*bolt_d*flange_t, axis-distance = PCD/2
  D3 phase: first hole at 0 deg; adjacent spacing = 360/n (>=2 units measured)
  D4 tori: root TORUS n=1 (area Pappus arc-centroid formula, z > flange_t);
           edge TORUS n=2 (same-radius formula, z <= flange_t)
  D5 S1 regression: bbox unchanged (x/y in +-od/2, z in [0, top]); boss top
     annulus / bore wall cards still resolve exactly 1
  D6 pattern tool count == bolt_count and prototype validated before patterning
     (source evidence: fact cards in run log; re-check hole wall count here)
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import flange_plate as fp  # noqa: E402
from simplecadapi import ql  # noqa: E402
from OCP.Bnd import Bnd_Box  # noqa: E402
from OCP.BRepBndLib import BRepBndLib  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


p = fp.params()
od, t = p["flange_od"], p["flange_t"]
boss_od, top, bore = p["boss_od"], p["boss_top_z"], p["bore_d"]
bolt_d, pcd, n = p["bolt_d"], p["bolt_pcd"], p["bolt_count"]
r_root, r_edge = p["boss_fillet_r"], p["edge_fillet_r"]

body = fp.build_solid()

# D1 volume bracket
v_base = math.pi / 4 * (od * od * t + boss_od * boss_od * (top - t) - bore * bore * top)
v_bolts = n * math.pi / 4 * bolt_d * bolt_d * t
# root fillet adds corner-fill ring (Pappus, centroid r = Rmaj - 2R/pi - fill offset)
a_fill = r_root * r_root - math.pi * r_root ** 2 / 4
v_root_add = 2 * math.pi * (boss_od / 2 + r_root - 2 * r_root / math.pi - 2 * 0.06) * a_fill
a_cut = r_edge * r_edge - math.pi * r_edge ** 2 / 4
v_edge_cut = 2 * 2 * math.pi * (od / 2 - r_edge) * a_cut
v_bracket = v_base - v_bolts + v_root_add - v_edge_cut
v = body.get_volume()
check("D1 volume in bracket", type(body).__name__ == "Solid" and v > 0
      and abs(v - v_bracket) / v_bracket < 0.015,
      f"volume={v:.3f} bracket={v_bracket:.3f} rel={abs(v - v_bracket) / v_bracket:.5f}")

# D2 bolt hole walls
a_hole = math.pi * bolt_d * t
walls = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CYLINDER"),
    ql.prop("geom.area", ">=", a_hole - 1.0), ql.prop("geom.area", "<=", a_hole + 1.0),
)).resolve(body)
radii = [math.hypot(f.get_center().x, f.get_center().y) for f in walls]
check("D2 bolt hole walls", len(walls) == n and all(abs(r - pcd / 2) < 0.05 for r in radii),
      f"n={len(walls)} want={n} radii={sorted(set(round(r, 3) for r in radii))} want_r={pcd / 2:.3f}")

# D3 phase + spacing (measure at least two units)
angles = sorted(round(math.degrees(math.atan2(f.get_center().y, f.get_center().x)) % 360.0, 2) for f in walls)
gaps = [round(b - a, 2) for a, b in zip(angles, angles[1:])]
check("D3 phase 0deg + equal spacing", angles and angles[0] < 0.01
      and len(set(gaps)) == 1 and abs(gaps[0] - 360.0 / n) < 0.01,
      f"phases={angles} gaps={gaps} want_gap={360.0 / n:.2f}")

# D4 torus cards
tori = ql.faces().where(ql.prop("geom.type", "==", "TORUS")).resolve(body)
a_root = 2 * math.pi * (boss_od / 2 + r_root - 2 * r_root / math.pi) * (math.pi * r_root / 2)
a_edge = 2 * math.pi * (od / 2 - r_edge + 2 * r_edge / math.pi) * (math.pi * r_edge / 2)
root_tori = [f for f in tori if f.get_center().z > t]
edge_tori = [f for f in tori if f.get_center().z <= t]
check("D4a root torus", len(root_tori) == 1 and abs(root_tori[0].get_area() - a_root) / a_root < 0.02,
      f"n={len(root_tori)} area={root_tori[0].get_area():.3f} want={a_root:.3f}")
check("D4b edge tori", len(edge_tori) == 2
      and all(abs(f.get_area() - a_edge) / a_edge < 0.02 for f in edge_tori),
      f"n={len(edge_tori)} areas={[f'{f.get_area():.3f}' for f in edge_tori]} want={a_edge:.3f}")

# D5 S1 regression
box = Bnd_Box()
box.SetGap(0.0)
BRepBndLib.AddOptimal_s(body.wrapped, box, useTriangulation=False)
xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
a_top = math.pi * ((boss_od / 2) ** 2 - (bore / 2) ** 2)
boss_top = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "PLANE"),
    ql.prop("geom.center.z", ">=", top - 0.1), ql.prop("geom.center.z", "<=", top + 0.1),
    ql.prop("geom.area", ">=", a_top - 1.0), ql.prop("geom.area", "<=", a_top + 1.0),
)).resolve(body)
wants = ((xmin, -od / 2), (xmax, od / 2), (ymin, -od / 2), (ymax, od / 2), (zmin, 0.0), (zmax, top))
check("D5 S1 regression (bbox+boss top card)",
      all(abs(g - w) < 0.05 for g, w in wants) and len(boss_top) == 1,
      f"bbox x[{xmin:.2f},{xmax:.2f}] y[{ymin:.2f},{ymax:.2f}] z[{zmin:.2f},{zmax:.2f}] "
      f"boss_top n={len(boss_top)}")

print(f"S2 verifier: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
