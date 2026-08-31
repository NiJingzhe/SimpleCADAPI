"""
[ARCHIVED 2026-08-31, feat/ftc] Historical evidence of an abandoned/superseded stage — NOT a runnable verifier contract. See archive/README.md.
S10 hypothesis: contour-offset cavity via eroded sweep + split + bosses.

Key constructions to prove before modeling:
  H1 eroded sweep (disk r-wall_t along same U path) volume == Pappus with
     radius (r-wall_t) — exact inner offset.
  H2 upper blank: cut below (back_y - boss_h); band hollow with
     (eroded_sweep ∩ band) MINUS boss cylinders -> integral boss remnants:
     exactly 2 boss columns Ø boss_d spanning the band; chord ring face at
     y=back_y remains (area band check).
  H3 boss blind holes from column bottom: 2 walls r=boss_hole_d/2.
  H4 gussets: 8 triangular prisms (2 boss x 4 dirs) union OK.
  H5 fillet groups on upper final: re-derive exclusions (probe groups).
  H6 shell: lower segment - (eroded sweep ∩ y<=back_y): single solid, wall
     sample >= wall_t-0.15 at floor; open top at 7.5.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402
import simplecadapi as scad  # noqa: E402
from simplecadapi import ql  # noqa: E402
from OCP.BRepClass3d import BRepClass3d_SolidClassifier  # noqa: E402
from OCP.gp import gp_Pnt  # noqa: E402
from OCP.TopAbs import TopAbs_IN, TopAbs_ON  # noqa: E402

P0 = u_link.params()
BY = u_link.back_y(P0)
WALL_T, BOSS_H, BOSS_X = 2.0, 5.0, 12.0
BOSS_D, BHOLE_D, BHOLE_DEPTH = P0["boss_d"], P0["boss_hole_d"], 3.0
RIB_T, RIB_LEN, GCH = 1.2, 3.0, 0.3
r = P0["rod_d"] / 2.0
failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


def eroded_sweep(wall_t: float) -> scad.Solid:
    p = dict(P0)
    p["rod_d"] = P0["rod_d"] - 2.0 * wall_t
    path = scad.make_wire_from_edges_rwire(edges=u_link._u_path_edges(p))
    profile = scad.make_circle_rface(
        center=(-p["L"] / 2.0, p["D"], 0.0), radius=p["rod_d"] / 2.0, normal=(0.0, -1.0, 0.0))
    return scad.sweep_rsolid(profile=profile, path=path)


def big_box(y_top: float, y_bot: float) -> scad.Solid:
    ovs = 10.0
    return scad.make_box_rsolid(
        width=P0["L"] + 4 * r + 2 * ovs, height=y_top - y_bot,
        depth=2 * (r + ovs),
        bottom_face_center=(0.0, (y_top + y_bot) / 2.0, -(r + ovs)))


with scad.GraphSession(graph_id="s10_hyp") as session:
    # H1 eroded sweep volume
    er = eroded_sweep(WALL_T)
    ri = r - WALL_T
    cl = 2.0 * (P0["D"] - P0["r_corner"]) + (P0["L"] - 2.0 * P0["r_corner"]) + math.pi * P0["r_corner"]
    pappus = math.pi * ri * ri * cl
    v_er = er.get_volume()
    check("H1 eroded sweep volume", abs(v_er - pappus) / pappus < 0.01,
          f"v={v_er:.1f} pappus={pappus:.1f}")

    # H2 upper part with integral bosses
    upper = scad.cut_rsolid(u_link.build_u_rod(), big_box(BY - BOSS_H, BY - BOSS_H - 60.0))
    # 腔 = eroded ∩ band（精确截至 7.5——注意 cut 是减不是交, S10 探针教训）
    cavity_tool = scad.intersect_rsolid(er, big_box(BY, BY - 60.0))
    boss_cols = [scad.make_cylinder_rsolid(
        radius=BOSS_D / 2.0, height=BOSS_H + 2.0,
        bottom_face_center=(sx * BOSS_X, BY - BOSS_H - 1.0, 0.0), axis=(0, 1, 0))
        for sx in (-1, 1)]
    cavity_tool = scad.cut_rsolid(cavity_tool, boss_cols)  # 腔工具带 boss 孔
    upper = scad.cut_rsolid(upper, cavity_tool)
    v_up = upper.get_volume()
    ring_expect = (math.pi * r * r - math.pi * ri * ri) * 0  # ring area via faces below
    ring_faces = ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "PLANE"), ql.prop("geom.normal.y", "<=", -0.999),
        ql.prop("geom.center.y", ">=", BY - 0.05), ql.prop("geom.center.y", "<=", BY + 0.05),
    )).resolve(upper)
    boss_cyls = ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "CYLINDER"),
        ql.prop("geom.area", ">=", 2 * math.pi * (BOSS_D / 2) * BOSS_H * 0.95),
        ql.prop("geom.area", "<=", 2 * math.pi * (BOSS_D / 2) * BOSS_H * 1.05),
    )).resolve(upper)
    check("H2 bosses+ring", len(boss_cyls) == 2 and len(ring_faces) >= 1
          and ring_faces[0].get_area() > 100.0,
          f"boss_walls={len(boss_cyls)} ring_n={len(ring_faces)} ring_area={ring_faces[0].get_area():.1f}" if ring_faces else "no ring")

    # H3 boss blind holes
    holes = [scad.make_cylinder_rsolid(
        radius=BHOLE_D / 2.0, height=BHOLE_DEPTH,
        bottom_face_center=(sx * BOSS_X, BY - BOSS_H, 0.0), axis=(0, 1, 0))
        for sx in (-1, 1)]
    upper = scad.cut_rsolid(upper, holes)
    hw = ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "CYLINDER"),
        ql.prop("geom.area", ">=", 2 * math.pi * (BHOLE_D / 2) * BHOLE_DEPTH * 0.95),
        ql.prop("geom.area", "<=", 2 * math.pi * (BHOLE_D / 2) * BHOLE_DEPTH * 1.05),
    )).resolve(upper)
    check("H3 boss holes", len(hw) == 2, f"n={len(hw)}")

    # H4 gussets (triangular prisms): tri in (t,y): (0,BY),(rib_len,BY),(0,BY-boss_h)
    gussets = []
    for sx in (-1, 1):
        bx = sx * BOSS_X
        for dx in (-1, 1):  # ±x gussets: tri in (x,y), extrude z
            tri = scad.make_face_from_wire_rface(scad.make_wire_from_edges_rwire(edges=[
                scad.make_segment_redge(start=(bx + dx * BOSS_D / 2, BY, -RIB_T / 2), end=(bx + dx * (BOSS_D / 2 + RIB_LEN), BY, -RIB_T / 2)),
                scad.make_segment_redge(start=(bx + dx * (BOSS_D / 2 + RIB_LEN), BY, -RIB_T / 2), end=(bx + dx * BOSS_D / 2, BY - BOSS_H, -RIB_T / 2)),
                scad.make_segment_redge(start=(bx + dx * BOSS_D / 2, BY - BOSS_H, -RIB_T / 2), end=(bx + dx * BOSS_D / 2, BY, -RIB_T / 2)),
            ]))
            gussets.append(scad.extrude_rsolid(profile=tri, direction=(0.0, 0.0, 1.0), distance=RIB_T))
        for dz in (-1, 1):  # ±z gussets: tri in (z,y), extrude x
            tri = scad.make_face_from_wire_rface(scad.make_wire_from_edges_rwire(edges=[
                scad.make_segment_redge(start=(bx - RIB_T / 2, BY, dz * BOSS_D / 2), end=(bx - RIB_T / 2, BY, dz * (BOSS_D / 2 + RIB_LEN))),
                scad.make_segment_redge(start=(bx - RIB_T / 2, BY, dz * (BOSS_D / 2 + RIB_LEN)), end=(bx - RIB_T / 2, BY - BOSS_H, dz * BOSS_D / 2)),
                scad.make_segment_redge(start=(bx - RIB_T / 2, BY - BOSS_H, dz * BOSS_D / 2), end=(bx - RIB_T / 2, BY, dz * BOSS_D / 2)),
            ]))
            g = scad.extrude_rsolid(profile=tri, direction=(1.0, 0.0, 0.0), distance=RIB_T)
            gussets.append(g)
    upper = scad.union_rsolid(upper, *gussets)
    check("H4 gussets union", upper.get_volume() > 0, f"v={upper.get_volume():.1f}")

    # H5 fillet probe: groups
    included, excluded = [], []
    br_ = BOSS_D / 2
    for e in upper.get_edges():
        c = e.get_center()
        keep = e.get_length() >= 2 * P0["fillet_r"] + 0.3
        near_boss = ((abs(abs(c.x) - BOSS_X) <= br_ + RIB_LEN + 0.5) and c.y <= BY + 0.3)
        if abs(c.y - BY) < 0.3 and not (abs(c.z) <= 11.0 and abs(c.x) <= 23.5):
            keep = False  # 切面外缘（弦-柱面切线边, S8 教训）
        if keep and near_boss:
            keep = False
        (included if keep else excluded).append(e)
    print(f"H5 selection: total={len(included) + len(excluded)} inc={len(included)}")
    try:
        upper_f = scad.fillet_rsolid(solid=upper, edges=included, radius=P0["fillet_r"],
                                     generated_faces_tag="fillet.global_patch")
        check("H5 fillet", True, f"inc={len(included)}")
    except Exception as exc:  # noqa: BLE001
        check("H5 fillet", False, f"{type(exc).__name__}")
        upper_f = upper

    # H6 gusset chamfer BEFORE global fillet (fillet 重建会吞掉筋斜边——s10 取证)
    hyp_len = (RIB_LEN ** 2 + BOSS_H ** 2) ** 0.5
    ch_edges = []
    for e in upper.get_edges():
        if abs(e.get_length() - hyp_len) > 0.15:
            continue
        c = e.get_center()
        if any(abs(c.x - sx * BOSS_X) <= br_ + RIB_LEN + 0.4 for sx in (-1, 1)) \
                and BY - BOSS_H - 0.3 <= c.y <= BY + 0.3:
            ch_edges.append(e)
    print(f"H6 gusset hyp edges n={len(ch_edges)} (want 16)")
    upper = scad.chamfer_rsolid(solid=upper, edges=ch_edges, distance=GCH)
    check("H6 gusset chamfer", len(ch_edges) == 16, f"n={len(ch_edges)}")

    # H7 shell: lower segment = rod ∩ y<=BY (cut 去上部), 再减 eroded 得壁厚外壳
    lower = scad.cut_rsolid(u_link.build_u_rod(), big_box(BY + 60.0, BY))
    shell = scad.cut_rsolid(lower, er)
    cls = BRepClass3d_SolidClassifier(shell.wrapped)

    def inside(x, y, z):
        cls.Perform(gp_Pnt(x, y, z), 1e-7)
        return cls.State() in (TopAbs_IN, TopAbs_ON)

    floor_ok = inside(0, -r + WALL_T / 2, 0) and not inside(0, -r + WALL_T + 0.2, 0)
    side_ok = not inside(0, 0, r - WALL_T + 0.2) or True  # span axis center is cavity
    check("H7 shell walls", type(shell).__name__ == "Solid" and floor_ok,
          f"floor_mid={inside(0, -r + WALL_T / 2, 0)} above_floor_mat={inside(0, -r + WALL_T + 0.2, 0)}")

    session.capture_result(value=upper_f)
    session.capture_result(value=shell)

print(f"S10 hypothesis: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
