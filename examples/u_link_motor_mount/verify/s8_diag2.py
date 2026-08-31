"""S8 diag2: recursive bisection to find the edge(s) that kill the fillet."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402
import simplecadapi as scad  # noqa: E402

P = u_link.params()
FR = P["fillet_r"]

with scad.GraphSession(graph_id="s8_diag2") as session:
    body = u_link._build_chain_ops("s3")
    body = scad.cut_rsolid(body, u_link._cavity_tools(P))
    body = scad.cut_rsolid(body, u_link._snap_hole_tools(P))
    rims, others = u_link._split_snap_rims(body, P)

    def ok(edges):
        try:
            scad.fillet_rsolid(solid=body, edges=edges, radius=FR)
            return True
        except Exception:  # noqa: BLE001
            return False

    def bisect(edges, depth=0):
        if ok(edges):
            print(f"{'  '*depth}OK n={len(edges)}")
            return []
        if len(edges) == 1:
            e = edges[0]
            c = e.get_center()
            print(f"{'  '*depth}POISON len={e.get_length():.3f} c=({c.x:.2f},{c.y:.2f},{c.z:.2f})")
            return edges
        h = len(edges) // 2
        print(f"{'  '*depth}split {len(edges)} -> {h}+{len(edges)-h}")
        return bisect(edges[:h], depth + 1) + bisect(edges[h:], depth + 1)

    poison = bisect(others)
    print(f"poison edges: {len(poison)}")
    for e in poison:
        c = e.get_center()
        print(f"  len={e.get_length():.3f} c=({c.x:.3f},{c.y:.3f},{c.z:.3f})")
    session.capture_result(value=body)
print("diag2 done")
