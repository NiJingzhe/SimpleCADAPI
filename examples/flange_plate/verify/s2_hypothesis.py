"""S2 hypothesis probe: bolt pattern + double fillet measurement set.

Proves on a hand replica (model source not yet extended to S2):
  P1 radial_pattern semantics (count includes prototype? angle coverage?)
  P2 bolt hole wall card (n, radius-from-axis, phase, area)
  P3 boss-root edge selection card (CIRCLE @ z=t, len 2*pi*27.5) -> fillet R3
  P4 flange-edge selection card (2 CIRCLEs len 2*pi*50) -> fillet R2
  P5 torus cards after fillets (n=3, areas, center.z windows)
  P6 volume after bolts = exact analytic; after fillets within Pappus bracket
  P7 known-bad: no-fillet replica fails torus card (discrimination proof)
"""
import math
import sys

import simplecadapi as scad
from simplecadapi import ql

OD, T, BOSS_OD, TOP, BORE = 100.0, 10.0, 55.0, 30.0, 30.0
BOLT_D, PCD, N, R_ROOT, R_EDGE = 11.0, 78.0, 6, 3.0, 2.0
OV = 5.0

results = []


def h(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}  {detail}")
    results.append(ok)


def base_body():
    body = scad.make_cylinder_rsolid(radius=OD / 2, height=T, bottom_face_center=(0, 0, 0), axis=(0, 0, 1))
    boss = scad.make_cylinder_rsolid(radius=BOSS_OD / 2, height=TOP - T, bottom_face_center=(0, 0, T), axis=(0, 0, 1))
    body = scad.union_rsolid(body, boss)
    bore = scad.make_cylinder_rsolid(radius=BORE / 2, height=TOP + 2 * OV, bottom_face_center=(0, 0, -OV), axis=(0, 0, 1))
    return scad.cut_rsolid(body, bore)


def edge_card(name, sel, body):
    card = sel.resolve(body)
    print(f"selection card [{name}]: n={len(card)}")
    for e in card:
        c = e.get_center()
        print(f"  len={e.get_length():.3f} center=({c.x:.2f},{c.y:.2f},{c.z:.2f})")
    return card


body = base_body()

# ---- bolt prototype + pattern (P1/P2) ----
proto = scad.make_cylinder_rsolid(radius=BOLT_D / 2, height=T + 2 * OV,
                                  bottom_face_center=(PCD / 2, 0.0, -OV), axis=(0, 0, 1))
tools = scad.radial_pattern_rsolidlist(shape=proto, center=(0.0, 0.0, 0.0), axis=(0.0, 0.0, 1.0),
                                       count=N, total_rotation_angle=360.0)
print(f"P1 pattern returns {len(tools)} tools (count={N})")
h("P1 pattern count", len(tools) == N, f"got {len(tools)}")

holed = scad.cut_rsolid(body, tools)
v_bolts = holed.get_volume()
v_expect = math.pi / 4 * (OD * OD * T + BOSS_OD * BOSS_OD * (TOP - T) - BORE * BORE * TOP) \
    - N * math.pi / 4 * BOLT_D * BOLT_D * T
h("P6a volume after bolts", abs(v_bolts - v_expect) / v_expect < 0.005,
  f"measured={v_bolts:.3f} analytic={v_expect:.3f}")

a_hole = math.pi * BOLT_D * T
hole_walls = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CYLINDER"),
    ql.prop("geom.area", ">=", a_hole - 1.0), ql.prop("geom.area", "<=", a_hole + 1.0),
)).resolve(holed)
print(f"P2 hole wall card: n={len(hole_walls)}")
radii, angles = [], []
for f in hole_walls:
    c = f.get_center()
    r = math.hypot(c.x, c.y)
    radii.append(r)
    angles.append(round(math.degrees(math.atan2(c.y, c.x)) % 360.0, 2))
    print(f"  center=({c.x:.3f},{c.y:.3f},{c.z:.3f}) r={r:.3f} area={f.get_area():.3f}")
h("P2 hole walls", len(hole_walls) == N
  and all(abs(r - PCD / 2) < 0.05 for r in radii), f"radii={sorted(set(round(r,3) for r in radii))}")
angles_sorted = sorted(angles)
print(f"  phases={angles_sorted}")
h("P2b phase + spacing", angles_sorted[0] < 1e-6 or abs(angles_sorted[0] - 360.0) < 1e-6,
  f"first hole at {angles_sorted[0]} deg (want 0)")
gaps = [round(b - a, 2) for a, b in zip(angles_sorted, angles_sorted[1:])]
h("P2c equal spacing (2+ units)", len(set(gaps)) <= 1 and abs(gaps[0] - 360.0 / N) < 0.01,
  f"gaps={gaps}")

# ---- root fillet selection + apply (P3) ----
root_sel = ql.edges().where(ql.and_(
    ql.prop("geom.type", "==", "CIRCLE"),
    ql.prop("geom.center.z", ">=", T - 0.1), ql.prop("geom.center.z", "<=", T + 0.1),
    ql.prop("geom.length", ">=", 2 * math.pi * BOSS_OD / 2 - 0.5),
    ql.prop("geom.length", "<=", 2 * math.pi * BOSS_OD / 2 + 0.5),
))
root_card = edge_card("boss-root R3", root_sel, holed)
h("P3 root selection card", len(root_card) == 1
  and abs(root_card[0].get_length() - math.pi * BOSS_OD) < 0.5,
  f"n={len(root_card)} len={[f'{e.get_length():.3f}' for e in root_card]} want={math.pi*BOSS_OD:.3f}")

rooted = scad.fillet_rsolid(solid=holed, edges=root_sel.exactly(1), radius=R_ROOT,
                            generated_faces_tag="fillet.boss_root")

# ---- edge fillets selection + apply (P4) ----
edge_sel = ql.edges().where(ql.and_(
    ql.prop("geom.type", "==", "CIRCLE"),
    ql.prop("geom.length", ">=", 2 * math.pi * OD / 2 - 0.5),
    ql.prop("geom.length", "<=", 2 * math.pi * OD / 2 + 0.5),
    ql.or_(ql.and_(ql.prop("geom.center.z", ">=", -0.1), ql.prop("geom.center.z", "<=", 0.1)),
           ql.and_(ql.prop("geom.center.z", ">=", T - 0.1), ql.prop("geom.center.z", "<=", T + 0.1))),
))
edge_card_out = edge_card("flange-edge R2 x2", edge_sel, rooted)
h("P4 edge selection card", len(edge_card_out) == 2
  and all(abs(e.get_length() - math.pi * OD) < 0.5 for e in edge_card_out),
  f"n={len(edge_card_out)} lens={[f'{e.get_length():.3f}' for e in edge_card_out]} want={math.pi*OD:.3f}")

final = scad.fillet_rsolid(solid=rooted, edges=edge_sel.exactly(2), radius=R_EDGE,
                           generated_faces_tag="fillet.flange_edge")

# ---- torus cards (P5) ----
tori = ql.faces().where(ql.prop("geom.type", "==", "TORUS")).resolve(final)
print(f"P5 torus card: n={len(tori)}")
# Pappus surface: A = 2*pi*r_bar*arc_len; arc-centroid radial offset from arc
# center is 2R/pi along the bisector (root concave: inboard; edge convex: outboard)
a_root = 2 * math.pi * (BOSS_OD / 2 + R_ROOT - 2 * R_ROOT / math.pi) * (math.pi * R_ROOT / 2)
a_edge = 2 * math.pi * (OD / 2 - R_EDGE + 2 * R_EDGE / math.pi) * (math.pi * R_EDGE / 2)
for f in tori:
    c = f.get_center()
    print(f"  area={f.get_area():.3f} center=({c.x:.2f},{c.y:.2f},{c.z:.2f})")
root_tori = [f for f in tori if f.get_center().z > T]
edge_tori = [f for f in tori if f.get_center().z <= T]
h("P5a root torus", len(root_tori) == 1 and abs(root_tori[0].get_area() - a_root) / a_root < 0.02,
  f"n={len(root_tori)} area={root_tori[0].get_area():.3f} want={a_root:.3f}")
h("P5b edge tori", len(edge_tori) == 2 and all(abs(f.get_area() - a_edge) / a_edge < 0.02 for f in edge_tori),
  f"n={len(edge_tori)} areas={[f'{f.get_area():.3f}' for f in edge_tori]} want={a_edge:.3f}")

# ---- final volume bracket (P6b) ----
# Pappus: root fillet ADDS ring (corner square minus quarter disc) at r~28.15
a_fill = R_ROOT * R_ROOT - math.pi * R_ROOT ** 2 / 4
v_root_add = 2 * math.pi * 28.15 * a_fill
# each edge fillet REMOVES corner (square minus quarter disc) at r~49.55
a_cut = R_EDGE * R_EDGE - math.pi * R_EDGE ** 2 / 4
v_edge_cut = 2 * 2 * math.pi * 49.55 * a_cut
v_final = final.get_volume()
v_bracket = v_expect + v_root_add - v_edge_cut
h("P6b final volume in Pappus bracket", abs(v_final - v_bracket) / v_bracket < 0.015,
  f"measured={v_final:.3f} bracket={v_bracket:.3f} rel={abs(v_final-v_bracket)/v_bracket:.5f}")

# ---- known-bad: holed body without fillets must fail torus card (P7) ----
tori_bad = ql.faces().where(ql.prop("geom.type", "==", "TORUS")).resolve(holed)
h("P7 known-bad no-fillet torus=0", len(tori_bad) == 0, f"n={len(tori_bad)} != 3 -> gate discriminates")

ok = all(results)
print(f"S2 hypothesis: {'ALL PASS' if ok else 'FAILED'} ({sum(results)}/{len(results)})")
sys.exit(0 if ok else 1)
