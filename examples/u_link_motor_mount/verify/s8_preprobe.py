"""S8 pre-probe: material thickness map above the back face.

Question the design depends on: for points (x, z) on the back-face plane
(y = back_y), how much material lies above (y_top - back_y)? A uniform-inset
pocket of depth `d` requires y_top >= back_y + d everywhere inside its outline
(plus fillet margin). Samples the REAL solid via ray-ish membership probing
instead of trusting analytic guesses.

Method: mesh-free point-in-solid test using BRepClass3d_SolidClassifier on the
S2 body (back-cut rod), sampling a grid on the back-face plane.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402

from OCP.BRepClass3d import BRepClass3d_SolidClassifier  # noqa: E402
from OCP.gp import gp_Pnt  # noqa: E402
from OCP.TopAbs import TopAbs_IN, TopAbs_ON  # noqa: E402

P = u_link.params()
by = u_link.back_y(P)
r = P["rod_d"] / 2.0

body = u_link.build_stage("s2")
cls = BRepClass3d_SolidClassifier(body.wrapped)


def inside(x, y, z, tol=1e-7):
    cls.Perform(gp_Pnt(x, y, z), tol)
    return cls.State() in (TopAbs_IN, TopAbs_ON)


def y_top(x, z, y_start=None):
    """Highest y with material at (x, z), binary search above back_y."""
    if not inside(x, by + 0.01, z):
        return None
    lo = by + 0.01
    hi = y = max(P["D"], r) + 5.0
    # find first y where material ends
    while inside(x, y, z):
        lo = y
        y = (y + hi) / 2 if y < hi - 1e-6 else y
        if hi - lo < 1e-4:
            break
    # bisect boundary between lo (in) and hi (out)
    a, b = lo, y if y > lo else hi
    for _ in range(60):
        m = 0.5 * (a + b)
        if inside(x, m, z):
            a = m
        else:
            b = m
    return a


print(f"back_y={by}  grid: thickness = y_top - back_y")
print("x\\z    0      4      7      9      11     12.5")
for x in (0.0, 15.0, 23.0, 28.0, 34.0, 40.0, 44.0, 47.0, 50.0, 51.0):
    row = []
    for z in (0.0, 4.0, 7.0, 9.0, 11.0, 12.5):
        t = y_top(x, z)
        row.append(f"{t - by:5.2f}" if t is not None else "  ---")
    print(f"{x:4.0f} " + " ".join(row))

zw = (r * r - by * by) ** 0.5
print(f"\nstraight-span chord half-width zw={zw:.2f}; analytic y_top(z)=sqrt(r^2-z^2)-by:")
for z in (0.0, 4.0, 7.0, 9.0, 11.0, 12.5):
    print(f"  z={z:4.1f} -> {(r * r - z * z) ** 0.5 - by:5.2f}")
