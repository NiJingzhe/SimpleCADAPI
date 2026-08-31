"""S8 diag: bisect which edge group kills the global fillet."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402
import simplecadapi as scad  # noqa: E402

P = u_link.params()
FR = P["fillet_r"]

with scad.GraphSession(graph_id="s8_diag") as session:
    body = u_link._build_chain_ops("s3")
    body = scad.cut_rsolid(body, u_link._cavity_tools(P))
    body = scad.cut_rsolid(body, u_link._snap_hole_tools(P))
    rims, others = u_link._split_snap_rims(body, P)
    print(f"total={len(rims) + len(others)} rims={len(rims)} others={len(others)}")

    def try_fillet(solid, edges, label):
        try:
            r = scad.fillet_rsolid(solid=solid, edges=edges, radius=FR)
            print(f"  {label}: OK (n={len(edges)})")
            return r
        except Exception as exc:  # noqa: BLE001
            print(f"  {label}: FAIL (n={len(edges)}) {type(exc).__name__}")
            return None

    # group others by y-band of edge center
    def band(e):
        y = e.get_center().y
        if y < P["waist_z"] - 0.5:
            return "low"
        if abs(y - (u_link.back_y(P) + P["cavity_h"])) < 1.0:
            return "cavity"
        if y > 14.0:
            return "top"
        return "mid"

    groups = {}
    for e in others:
        groups.setdefault(band(e), []).append(e)
    for k, v in sorted(groups.items()):
        print(f"group {k}: n={len(v)} lens={[round(x.get_length(), 2) for x in v[:6]]}")
        try_fillet(body, v, f"band {k}")

    # cumulative: all bands except one
    for skip in sorted(groups):
        edges = [e for k, v in groups.items() if k != skip for e in v]
        try_fillet(body, edges, f"all minus {skip}")

    session.capture_result(value=body)
print("diag done")
