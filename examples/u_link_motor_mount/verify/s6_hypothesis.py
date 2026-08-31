"""S6 hypothesis: parameter-variant mechanism + missing-guard load-bearing proofs.

Probes:
  H1 variant override mechanism: assign plain floats to u_link vars ->
     params() reflects them; build_stage('s1') bbox follows (no @part cache trap:
     sweep uses build_stage, never the cached decorated builder).
  H2 missing guard A (fillet_r >= pocket radius rp): params that pass ALL current
     guards (rod_d=30, thickness=20 -> rp=5, thickness/2=10, fr=7) -> build s4
     and observe kernel behavior. If it fails/corrupts, guard is load-bearing.
  H3 missing guard B (fillet_r >= pocket depth): rod_d=40, thickness=10 (rp=15,
     thickness/2=5), D=30, d_motor=54 (depth=3), fr=4.9 (<5 passes old guard,
     >= depth=3) -> build s4 and observe.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import u_link  # noqa: E402

from s1_hypothesis import bbox_of  # noqa: E402


def set_params(**kw):
    defaults = dict(L=80.0, D=20.0, rod_d=30.0, thickness=6.0,
                    d_motor=30.0, r_corner=17.0, fillet_r=1.2)
    defaults.update(kw)
    u_link.L, u_link.D, u_link.ROD_D = defaults["L"], defaults["D"], defaults["rod_d"]
    u_link.THICKNESS, u_link.D_MOTOR = defaults["thickness"], defaults["d_motor"]
    u_link.R_CORNER, u_link.FILLET_R = defaults["r_corner"], defaults["fillet_r"]
    return defaults


# H1: override mechanism + length adaptation
set_params(L=120.0)
p = u_link.params()
rod = u_link.build_stage("s1")
xs = bbox_of(rod)
want = 120.0 / 2.0 + 30.0 / 2.0
print(f"H1 params L={p['L']} bbox_x[{xs[0]:.2f},{xs[3]:.2f}] want ±{want}")
assert p["L"] == 120.0 and abs(xs[3] - want) < 0.05 and abs(xs[0] + want) < 0.05

# H2: guard A probe — fr=7 >= rp=5, passes every current guard
set_params(thickness=20.0, fillet_r=7.0)
try:
    u_link.assert_params()  # current guards (before adding new ones)
    print("H2 current guards: PASS (as expected — guard A absent)")
    s4 = u_link.build_stage("s4")
    v = s4.get_volume()
    v3 = u_link.build_stage("s3").get_volume()
    print(f"H2 built anyway: v4={v:.3f} v3={v3:.3f} ratio={v / v3:.4f}")
    if not (0.9 < v / v3 < 1.0):
        print("H2 FINDING: volume ratio out of band -> geometry degraded, guard A load-bearing")
    else:
        from simplecadapi import ql
        floors = ql.faces().where(ql.and_(
            ql.prop("geom.type", "==", "PLANE"),
            ql.prop("geom.normal.y", ">=", 0.999),
            ql.prop("geom.center.y", ">=", 14.9), ql.prop("geom.center.y", "<=", 15.1),
        )).resolve(s4)
        print(f"H2 floors after fillet: n={len(floors)} areas={[f'{f.get_area():.2f}' for f in floors]} "
              f"(pre-fillet pi*rp^2={math.pi * 25:.2f})")
except AssertionError as exc:
    print(f"H2 current guards REJECTED: {exc} (variant mis-designed)")
except Exception as exc:  # noqa: BLE001
    print(f"H2 kernel failure: {type(exc).__name__}: {str(exc)[:120]}")

# H3: guard B probe — fr=4.9 >= depth=3, passes every current guard
set_params(rod_d=40.0, thickness=10.0, D=30.0, d_motor=54.0, r_corner=25.0, fillet_r=4.9)
try:
    u_link.assert_params()
    print("H3 current guards: PASS (as expected — guard B absent)")
    s4 = u_link.build_stage("s4")
    v3 = u_link.build_stage("s3").get_volume()
    print(f"H3 built anyway: v4={s4.get_volume():.3f} v3={v3:.3f} ratio={s4.get_volume() / v3:.4f}")
except AssertionError as exc:
    print(f"H3 current guards REJECTED: {exc}")
except Exception as exc:  # noqa: BLE001
    print(f"H3 kernel failure: {type(exc).__name__}: {str(exc)[:120]}")

# restore defaults
set_params()
print("S6 hypothesis: probes done (defaults restored)")
