"""S3 hypothesis probe: prove the equivalence gates can fail.

Feeds deliberately corrupted facts (volume +0.2%, bbox +0.3 mm, renamed tag,
area +1%) into the exact gate functions used by s3_equivalence.py. Every gate
must reject its corrupted input; the honest pair must pass everything.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_equivalence():
    spec = importlib.util.spec_from_file_location("s3_equivalence", HERE / "s3_equivalence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    eq = load_equivalence()
    interfaces = json.loads((HERE / "legacy_interface_facts.json").read_text())

    # H1 volume gate: +0.2% corruption must fail, honest pair passes
    ok, rel = eq.gate_volume(10097.79 * 1.002, 10097.79)
    print(f"H1 volume gate rejects +0.2% -> {'PASS' if not ok else 'FAIL'} (rel {rel:.2e})")
    assert not ok
    ok, rel = eq.gate_volume(10097.790499, 10097.790499)
    assert ok

    # H2 bbox gate: 0.3 mm axis corruption must fail
    new_bbox = (-2.0035, -20.0, -0.0044, 26.3, 20.0, 36.0)
    old_bbox = (-2.0035, -20.0, -0.0044, 26.0, 20.0, 36.0)
    ok, delta = eq.gate_bbox(new_bbox, old_bbox)
    print(f"H2 bbox gate rejects +0.3mm -> {'PASS' if not ok else 'FAIL'} (delta {delta})")
    assert not ok

    # H3 interface set gate: renamed tag must fail
    renamed = copy.deepcopy(interfaces)
    renamed["interface.mount_hole_2x"] = renamed.pop("interface.mount_hole_2")
    ok, problems = eq.gate_interfaces(renamed, interfaces)
    print(f"H3 set gate rejects renamed tag -> {'PASS' if not ok else 'FAIL'} ({problems[0][:44]}...)")
    assert not ok

    # H4 interface area gate: +1% area corruption must fail
    inflated = copy.deepcopy(interfaces)
    inflated["interface.load_surface"]["area"] *= 1.01
    ok, problems = eq.gate_interfaces(inflated, interfaces)
    print(f"H4 area gate rejects +1% -> {'PASS' if not ok else 'FAIL'} ({problems[0]})")
    assert not ok

    print("S3 hypothesis conclusion: all four equivalence gates discriminate -> adopt")


if __name__ == "__main__":
    main()
