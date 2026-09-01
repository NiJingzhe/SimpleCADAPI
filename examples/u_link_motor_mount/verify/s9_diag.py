"""S9 diag: per-group fillet test in crash-safe subprocesses.

Usage: uv run python verify/s9_diag.py <group...>
Rebuilds chain s9 (cavity+boss+ribs) then fillets only edges of named groups.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402
import simplecadapi as scad  # noqa: E402

P = u_link.params()
FR = P["fillet_r"]
BY = u_link.back_y(P)
FY = BY + P["cavity_h"]
BOSS_X, BOSS_Z = 39.0, 3.5
BR, HR = 2.5, 1.35
RIB_T, RIB_H, RIB_LEN = 1.2, 1.5, 2.5
RIB_IN, RIB_OUT = HR + 0.5, BR + RIB_LEN


def group_of(e):
    c = e.get_center()
    in_cavity_xy = abs(c.z) <= P["pocket_z"] + 0.3 and abs(c.x) <= P["pocket_x2"] + 0.3
    near_boss_axis = any(
        ((c.x - sx * BOSS_X) ** 2 + (c.z - sz * BOSS_Z) ** 2) < (BR + 1.0) ** 2
        for sx in (-1, 1) for sz in (-1, 1))
    if near_boss_axis:
        if abs(c.y - FY) < 0.3:
            return "boss_root"            # boss/筋 根部-腔底交线
        if RIB_IN - 0.3 <= min(
                (abs(c.x - sx * BOSS_X) for sx in (-1, 1))) <= RIB_OUT + 0.3 \
                and abs(c.z % (2 * BOSS_Z)) <= BOSS_Z + 0.3 and FY - RIB_H - 0.3 <= c.y <= FY + 0.3:
            return "rib_edges"
        return "boss_other"
    if abs(c.y - FY) < 0.3 and in_cavity_xy:
        return "cavity_floor_rim"
    if abs(c.y - BY) < 0.3 and in_cavity_xy:
        return "cavity_back_rim"
    if abs(c.y - BY) < 0.3:
        return "backface_outer"
    if c.y > 14.0:
        return "mount_area"
    return "rest"


GROUPS = ("boss_root", "rib_edges", "boss_other", "cavity_floor_rim",
          "cavity_back_rim", "backface_outer", "mount_area", "rest")

want = set(" ".join(sys.argv[1:]).replace("+", " ").split())
label = "_".join(sorted(want)) or "none"

with scad.GraphSession(graph_id=f"s9_diag_{label}") as session:
    body = u_link._build_chain_ops("s3")
    body = scad.cut_rsolid(body, u_link._cavity_tools(P))
    bosses = [scad.make_cylinder_rsolid(
        radius=BR, height=P["cavity_h"],
        bottom_face_center=(sx * BOSS_X, BY, sz * BOSS_Z), axis=(0, 1, 0))
        for sx in (-1, 1) for sz in (-1, 1)]
    body = scad.union_rsolid(body, *bosses)
    holes = [scad.make_cylinder_rsolid(
        radius=HR, height=2.5,
        bottom_face_center=(sx * BOSS_X, BY, sz * BOSS_Z), axis=(0, 1, 0))
        for sx in (-1, 1) for sz in (-1, 1)]
    body = scad.cut_rsolid(body, holes)
    ribs = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            for dx in (-1, 1):
                x0 = sx * BOSS_X + dx * RIB_IN
                x1 = sx * BOSS_X + dx * RIB_OUT
                ribs.append(scad.make_box_rsolid(
                    width=RIB_OUT - RIB_IN, height=RIB_H, depth=RIB_T,
                    bottom_face_center=((x0 + x1) / 2, FY - RIB_H / 2, sz * BOSS_Z - RIB_T / 2)))
    body = scad.union_rsolid(body, *ribs)

    counts = {}
    picked = []
    for e in scad.ql.edges().resolve(body):
        g = group_of(e)
        counts[g] = counts.get(g, 0) + 1
        if g in want:
            picked.append(e)
    print(f"groups={sorted(want)} n={len(picked)} all_counts={counts}")
    if picked:
        scad.fillet_rsolid(solid=body, edges=picked, radius=FR, generated_faces_tag="diag.patch")
        print(f"FILLET OK groups={sorted(want)}")
    session.capture_result(value=body)
