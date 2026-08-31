"""S8 diag3: per-group fillet test, one subprocess per group (crash-safe).

Usage: uv run python verify/s8_diag3.py <group>
Groups partition the non-rim edges; each subprocess builds the chain fresh
and attempts to fillet exactly one group. Exit 0 = OK, 3 = FAIL(exc), 139 =
kernel segfault (reported by shell).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402
import simplecadapi as scad  # noqa: E402

P = u_link.params()
FR = P["fillet_r"]
BY = u_link.back_y(P)
FY = BY + P["cavity_h"]


def group_of(e):
    c = e.get_center()
    in_cavity_xy = (abs(c.z) <= P["pocket_z"] + 0.3 and abs(c.x) <= P["pocket_x2"] + 0.3)
    if abs(c.y - FY) < 0.3 and in_cavity_xy:
        return "cavity_floor_rim"     # 槽底-腔壁交线
    if abs(c.y - BY) < 0.3 and in_cavity_xy:
        return "cavity_back_rim"      # 腔壁-back face 交线
    if abs(c.y - BY) < 0.3:
        return "backface_outer"       # back face 外缘
    if c.y > 14.0:
        return "mount_area"           # 电机槽/端面
    if abs(abs(c.x) - P["waist_x"]) < 0.3 and P["waist_z"] < abs(c.z) <= P["pocket_z"] + 0.3:
        return "cavity_step"          # 腰-腔台阶竖边
    return "rest"


GROUPS = ("cavity_floor_rim", "cavity_back_rim", "backface_outer", "mount_area", "cavity_step", "rest")

group = " ".join(sys.argv[1:]).replace("+", " ").split()
want = set(group)
two_step = "TWO_STEP" in want
want.discard("TWO_STEP")
with scad.GraphSession(graph_id=f"s8_diag3_{'_'.join(sorted(want))}") as session:
    body = u_link._build_chain_ops("s3")
    body = scad.cut_rsolid(body, u_link._cavity_tools(P))
    body = scad.cut_rsolid(body, u_link._snap_hole_tools(P))
    rims, others = u_link._fillet_excluded_edges(body, P)
    first = [e for e in others if group_of(e) in ({"cavity_back_rim", "mount_area"} if two_step else want)]
    print(f"groups={sorted(want)} two_step={two_step} n_first={len(first)}")
    body = scad.fillet_rsolid(solid=body, edges=first, radius=FR, generated_faces_tag="diag.patch1")
    print(f"step1 OK (n={len(first)})")
    if two_step:
        rims2, others2 = u_link._fillet_excluded_edges(body, P)
        second = [e for e in others2 if group_of(e) in want]
        print(f"n_second={len(second)}")
        body = scad.fillet_rsolid(solid=body, edges=second, radius=FR, generated_faces_tag="diag.patch2")
        print(f"step2 OK (n={len(second)})")
    if not picked:
        sys.exit(0)
    scad.fillet_rsolid(solid=body, edges=picked, radius=FR, generated_faces_tag="diag.patch")
    print(f"groups={sorted(want)} FILLET OK")
    session.capture_result(value=body)
sys.exit(0)
