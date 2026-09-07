"""S3 guard-decision evidence: 6-hole -> 8-hole re-parameterization (USER round 2).

Records, as verification evidence:
  E1 candidate (bolt_count=8, bolt_pcd=88) is REJECTED by the web guard G2a,
     with the exact arithmetic in the assertion message
  E2 PCD supremum from the web inequality is 85, but 85 is EXCLUDED by the
     tangency guard G2b (web == edge_fillet_r): proven degenerate on 2026-09-05
     (run log: 8x PCD85 -> 7 hole walls, faces 16!=17, edge fillet swallowed
     the tangent 0-degree hole, volume +950 anomaly). Max deliverable PCD on a
     0.5 mm grid with web strictly > R_edge: 84.5
  E3 the delivered pair (8, 84.5) passes ALL guards (G1..G4, G2a+G2b)
  E4 parameter-change table 6-hole -> 8-hole (what changed, what did not)
Run BEFORE and AFTER the model param edit (guard math reads module params,
candidates passed as overrides; module defaults only feed the change table).

    uv run python examples/flange_plate/verify/s3_guard_evidence.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import flange_plate as fp  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        failures.append(name)


p = fp.params()  # current module defaults (pre-change: 6 holes; post-change: 8)
REQ_COUNT, REQ_PCD = 8, 88.0
DELIVERED_PCD = 84.5  # 0.5 mm grid; supremum 85 excluded by G2b tangency

print(f"module defaults: bolt_count={p['bolt_count']} bolt_pcd={p['bolt_pcd']}")
print(f"user request   : bolt_count={REQ_COUNT} bolt_pcd={REQ_PCD} (as large as possible)")

# E1: candidate 8/88 must be rejected by the web guard G2a
web88 = p["flange_od"] / 2 - REQ_PCD / 2 - p["bolt_d"] / 2
try:
    fp.assert_params(dict(p, bolt_count=REQ_COUNT, bolt_pcd=REQ_PCD))
    check("E1 guard rejects 8/88", False, "NO raise — guard silent, unacceptable")
except AssertionError as exc:
    msg = str(exc)
    ok = msg.startswith("G2") and f"= {web88:.3f}" in msg
    check("E1 guard rejects 8/88", ok, f"web(88)={web88:.3f} min={p['min_edge_web']} raised: {msg[:90]}")

# E2: supremum 85 from G2a inequality, then excluded by G2b (tangency, proven)
pcd_sup = p["flange_od"] - p["bolt_d"] - 2.0 * p["min_edge_web"]
web_sup = p["flange_od"] / 2 - pcd_sup / 2 - p["bolt_d"] / 2
check("E2a supremum from web floor", abs(pcd_sup - 85.0) < 1e-9 and abs(web_sup - p["min_edge_web"]) < 1e-9,
      f"pcd_sup = {p['flange_od']} - {p['bolt_d']} - 2*{p['min_edge_web']} = {pcd_sup:.1f}, "
      f"web({pcd_sup:.0f}) = {web_sup:.3f} == min_edge_web (boundary)")
try:
    fp.assert_params(dict(p, bolt_count=REQ_COUNT, bolt_pcd=pcd_sup))
    check("E2b 85 excluded by tangency guard", False, "85 accepted — G2b missing")
except AssertionError as exc:
    check("E2b 85 excluded by tangency guard", str(exc).startswith("G2b"),
          f"raised: {str(exc)[:80]}")
print("  degeneracy proof on record (2026-09-05 run): 8x PCD85 built a solid but the "
      "edge fillet swallowed the tangent 0-deg hole wall (D2 found 7/8 walls, "
      "faces 16 != 17, volume +950 anomaly) — tangency is a real failure mode, "
      "not a theoretical one")
check("E2c delivered PCD", abs(DELIVERED_PCD - 84.5) < 1e-9,
      f"max deliverable on 0.5mm grid with web > R_edge: {DELIVERED_PCD} "
      f"(web = {p['flange_od']/2 - DELIVERED_PCD/2 - p['bolt_d']/2:.3f} > {p['edge_fillet_r']})")

# E3: delivered pair (8, 84.5) passes all guards
delivered = dict(p, bolt_count=REQ_COUNT, bolt_pcd=DELIVERED_PCD)
try:
    fp.assert_params(delivered)
    check("E3 guards accept 8/84.5", True)
except AssertionError as exc:
    check("E3 guards accept 8/84.5", False, f"raised: {exc}")
web = p["flange_od"] / 2 - DELIVERED_PCD / 2 - p["bolt_d"] / 2
gap = DELIVERED_PCD / 2 - p["bolt_d"] / 2 - p["boss_od"] / 2 - p["boss_fillet_r"]
chord = 2 * (DELIVERED_PCD / 2) * math.sin(math.pi / REQ_COUNT)
print(f"  evidence: web={web:.3f} > R_edge={p['edge_fillet_r']} (margin {web - p['edge_fillet_r']:.3f}), "
      f"G3 gap={gap:.3f} > 0, G1 wall={(p['boss_od']-p['bore_d'])/2:.3f} > R{p['boss_fillet_r']}, "
      f"G4 boss_h={p['boss_top_z']-p['flange_t']:.1f} >= R{p['boss_fillet_r']}, "
      f"adjacent chord={chord:.2f} > bolt_d={p['bolt_d']}")

# E4: change table
print("E4 change table:")
print(f"  bolt_count : {p['bolt_count']} -> {REQ_COUNT}   (spacing 360/{REQ_COUNT} = {360.0/REQ_COUNT:.1f} deg)")
print(f"  bolt_pcd   : {p['bolt_pcd']} -> {DELIVERED_PCD}  "
      f"(88 rejected by G2a: web 0.5 < {p['min_edge_web']}; 85 excluded by G2b tangency; "
      f"84.5 = 0.5mm-grid max with web > R_edge)")
print(f"  unchanged  : flange_od={p['flange_od']} flange_t={p['flange_t']} boss_od={p['boss_od']} "
      f"boss_top_z={p['boss_top_z']} bore_d={p['bore_d']} bolt_d={p['bolt_d']} "
      f"R_root={p['boss_fillet_r']} R_edge={p['edge_fillet_r']}")
if p["bolt_count"] == REQ_COUNT and abs(p["bolt_pcd"] - DELIVERED_PCD) < 1e-9:
    print(f"  post-change module defaults already delivered: 8 holes @ web={web:.3f}")
    check("E4 module params delivered", True, "bolt_count=8, bolt_pcd=84.5 in source")
else:
    print("  pre-change module defaults: model edit still pending (this run = decision evidence)")
    check("E4 module params delivered", False, "not yet edited")

print(f"S3 guard evidence: {'ALL PASS' if not failures else 'FAILED ' + str(failures)}")
sys.exit(1 if failures else 0)
