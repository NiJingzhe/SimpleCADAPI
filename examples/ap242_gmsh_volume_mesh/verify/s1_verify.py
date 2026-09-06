"""S1 verifier: L-base + twin ribs stage gate against model.py.

Criteria (BUILD_PLAN S1):
  C1 single Solid, volume = analytic 10368 +/- 0.1%
  C2 bbox = [-2,-20,0] x [26,20,36] +/- 0.05
  C3 topology enumerable via QL (face count reported, > 0)
Exits non-zero on any failure; prints small evidence facts only.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import simplecadapi as scad
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box

MODEL = Path(__file__).resolve().parents[1] / "model.py"

EXPECTED_VOLUME = 10368.0  # 4*40*36 + 28*40*4 - 4*40*4 + 2*(0.5*18*18*3) - 2*102
EXPECTED_BBOX = ((-2.0, -20.0, 0.0), (26.0, 20.0, 36.0))
VOL_TOL = 1e-3
BBOX_TOL = 0.05


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("bracket_model", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bbox_of(solid: scad.Solid):
    box = Bnd_Box()
    box.SetGap(0.0)
    BRepBndLib.AddOptimal_s(solid.wrapped, box, True, False)
    values = box.Get()
    return tuple(values[:3]), tuple(values[3:])


def main() -> None:
    module = load_module(MODEL)
    body = module.build_stage("s1")
    assert isinstance(body, scad.Solid), f"C1 type: expected Solid, got {type(body)}"

    volume = body.get_volume()
    volume_error = abs(volume - EXPECTED_VOLUME) / EXPECTED_VOLUME
    assert volume > 0.0, "C1 positive volume"
    assert volume_error <= VOL_TOL, f"C1 volume {volume:.4f} vs {EXPECTED_VOLUME} (rel {volume_error:.5f})"

    lo, hi = bbox_of(body)
    for index, (measured, expected) in enumerate(zip(lo + hi, EXPECTED_BBOX[0] + EXPECTED_BBOX[1])):
        assert abs(measured - expected) <= BBOX_TOL, (
            f"C2 bbox[{index}] {measured:.4f} vs {expected} (tol {BBOX_TOL})"
        )

    face_count = len(scad.ql.faces().resolve(body))
    edge_count = len(scad.ql.edges().resolve(body))
    assert face_count > 0, "C3 QL face enumeration"

    print(f"C1 PASS single Solid volume={volume:.3f} expected={EXPECTED_VOLUME} rel_err={volume_error:.6f}")
    print(f"C2 PASS bbox lo=({lo[0]:.4f},{lo[1]:.4f},{lo[2]:.4f}) hi=({hi[0]:.4f},{hi[1]:.4f},{hi[2]:.4f})")
    print(f"C3 PASS ql faces={face_count} edges={edge_count}")
    print("S1 VERIFY: ALL PASS")


if __name__ == "__main__":
    main()
