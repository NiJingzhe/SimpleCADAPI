"""S1 hypothesis: circular-profile sweep along U-path (down -> right -> up).

Probes:
  H1 sweep builds with R_corner > profile radius; Pappus volume cross-check.
  H2 QL selects exactly the 2 planar end caps at y=D (type PLANE, center window).
  H3 bbox measurable (OCP Bnd_Box on wrapped) matches analytic extremes.
  H4 known-bad A: volume gate rejects +5% perturbed expectation.
  H5 known-bad B: degenerate corner R_corner == r signature (recorded, not used).
"""
import math

import simplecadapi as scad
from simplecadapi import ql

L, D, ROD_D, R_CORNER = 80.0, 40.0, 30.0, 20.0
r = ROD_D / 2.0
R = R_CORNER


def build_u_rod(L=L, D=D, r=r, R=R):
    xl, xr = -L / 2.0, L / 2.0
    s2 = math.sqrt(2.0) / 2.0
    cl, cr = (xl + R, R), (xr - R, R)
    path = scad.make_wire_from_edges_rwire(edges=[
        scad.make_segment_redge(start=(xl, D, 0.0), end=(xl, R, 0.0)),
        scad.make_three_point_arc_redge(
            start=(xl, R, 0.0),
            middle=(cl[0] - R * s2, cl[1] - R * s2, 0.0),
            end=(cl[0], 0.0, 0.0),
        ),
        scad.make_segment_redge(start=(cl[0], 0.0, 0.0), end=(cr[0], 0.0, 0.0)),
        scad.make_three_point_arc_redge(
            start=(cr[0], 0.0, 0.0),
            middle=(cr[0] + R * s2, cr[1] - R * s2, 0.0),
            end=(xr, R, 0.0),
        ),
        scad.make_segment_redge(start=(xr, R, 0.0), end=(xr, D, 0.0)),
    ])
    profile = scad.make_circle_rface(
        center=(xl, D, 0.0), radius=r, normal=(0.0, -1.0, 0.0)
    )
    return scad.sweep_rsolid(profile=profile, path=path)


def bbox_of(solid):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    box.SetGap(0.0)
    BRepBndLib.AddOptimal_s(solid.wrapped, box, useTriangulation=False)
    return box.Get()


# H1: build + Pappus volume
rod = build_u_rod()
volume = rod.get_volume()
centerline = 2.0 * (D - R) + (L - 2.0 * R) + math.pi * R
pappus = math.pi * r * r * centerline
print(f"H1 volume={volume:.3f} pappus={pappus:.3f} rel_err={abs(volume - pappus) / pappus:.5f}")
assert volume > 0
assert abs(volume - pappus) / pappus < 0.005, "volume off Pappus by >0.5%"

# H2: QL end caps
caps = ql.faces().where(
    ql.and_(
        ql.prop("geom.type", "==", "PLANE"),
        ql.prop("geom.center.y", ">=", D - 0.1),
        ql.prop("geom.center.y", "<=", D + 0.1),
    )
)
card = caps.resolve(rod)
print(f"H2 cap card: n={len(card)}")
for f in card:
    c = f.get_center()
    n = f.get_normal_at()
    print(
        f"  center=({c.x:.2f},{c.y:.2f},{c.z:.2f}) area={f.get_area():.3f} "
        f"normal=({n.x:.2f},{n.y:.2f},{n.z:.2f})"
    )
assert len(card) == 2, f"expected 2 end caps, got {len(card)}"
assert all(abs(f.get_area() - math.pi * r * r) < 1.0 for f in card)

# H3: bbox
xmin, ymin, zmin, xmax, ymax, zmax = bbox_of(rod)
print(f"H3 bbox x[{xmin:.2f},{xmax:.2f}] y[{ymin:.2f},{ymax:.2f}] z[{zmin:.2f},{zmax:.2f}]")
for got, want in (
    (xmin, -(L / 2 + r)), (xmax, L / 2 + r),
    (ymin, -r), (ymax, D),
    (zmin, -r), (zmax, r),
):
    assert abs(got - want) < 0.05, f"bbox {got} != {want}"

# H4: known-bad — volume gate rejects perturbed expectation
try:
    assert abs(volume - pappus * 1.05) / (pappus * 1.05) < 0.005
    raise SystemExit("H4 FAIL: gate accepted a 5%-wrong expectation")
except AssertionError:
    print("H4 volume gate rejected +5% perturbation (as designed)")

# H5: known-bad — degenerate corner R == r signature
try:
    bad = build_u_rod(R=r)
    v_bad = bad.get_volume()
    print(f"H5 degenerate R=r built: volume={v_bad:.3f} (recorded signature, NOT adopted)")
except Exception as exc:  # noqa: BLE001
    print(f"H5 degenerate R=r failed as expected: {type(exc).__name__}: {exc}")

print("S1 hypothesis: all probes done")
