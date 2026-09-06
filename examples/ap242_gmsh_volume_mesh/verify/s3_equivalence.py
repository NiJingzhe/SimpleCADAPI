"""S3 verifier: legacy-vs-rebuilt package equivalence + delivery gates.

Criteria (BUILD_PLAN S3):
  E1 volume(new pkg) vs volume(legacy pkg): rel diff < 0.1%
  E2 bounding box per axis: |delta| <= 0.05 mm
  E3 interface tag sets equal; per-tag area rel <= 1e-4, centroid <= 1e-3 mm
  E4 BREP inspection of materialized new body: valid, 1 solid, volume > 0
  E5 both packages re-opened + validated in THIS fresh process
  E6 export_step/obj/stl artifacts exist and are non-empty
Gate functions are importable so s3_hypothesis.py can prove they fail on
corrupted inputs (a gate that cannot fail is not a gate).
"""

from __future__ import annotations

import json
from pathlib import Path

import simplecadapi as scad
from simplecadapi.inspect import brep
from simplecadapi.scene import parse_canonical_json, read_scene_package
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parents[1] / "out"
NEW_PACKAGE = OUT_DIR / "ap242_gmsh_bracket.scadpkg"
LEGACY_PACKAGE = OUT_DIR / "legacy_baseline" / "ap242_gmsh_bracket.scadpkg"
EXPORTS = {
    "step": OUT_DIR / "ap242_gmsh_bracket.step",
    "obj": OUT_DIR / "ap242_gmsh_bracket.obj",
    "stl": OUT_DIR / "ap242_gmsh_bracket.stl",
}

VOLUME_TOL = 1e-3
BBOX_TOL = 0.05
AREA_TOL = 1e-4
CENTROID_TOL = 1e-3


def bbox_of(shape) -> tuple[float, ...]:
    box = Bnd_Box()
    box.SetGap(0.0)
    BRepBndLib.AddOptimal_s(shape, box, True, False)
    return box.Get()


def gate_volume(new: float, old: float) -> tuple[bool, float]:
    rel = abs(new - old) / abs(old)
    return rel <= VOLUME_TOL, rel


def gate_bbox(new: tuple[float, ...], old: tuple[float, ...]) -> tuple[bool, float]:
    delta = max(abs(a - b) for a, b in zip(new, old))
    return delta <= BBOX_TOL, delta


def gate_interfaces(
    new: dict[str, dict], old: dict[str, dict]
) -> tuple[bool, list[str]]:
    problems: list[str] = []
    if set(new) != set(old):
        problems.append(f"tag set {sorted(new)} != {sorted(old)}")
        return False, problems
    for tag in sorted(old):
        area_rel = abs(new[tag]["area"] - old[tag]["area"]) / old[tag]["area"]
        centroid_delta = max(
            abs(a - b) for a, b in zip(new[tag]["centroid"], old[tag]["centroid"])
        )
        if area_rel > AREA_TOL:
            problems.append(f"{tag} area rel {area_rel:.2e}")
        if centroid_delta > CENTROID_TOL:
            problems.append(f"{tag} centroid {centroid_delta:.2e}")
    return not problems, problems


def package_facts(package_path: Path) -> dict:
    """Re-open + validate one package, extract equivalence facts."""
    package = scad.read_product_package(package_path)
    scad.validate_product_package(package)
    part = scad.materialize_definition(package.root_definition)
    body = part.body
    inspection = brep.inspect_shape_rbrepinspection(body.wrapped, source=str(package_path))

    scene = read_scene_package(package.scene_bytes)
    interfaces: dict[str, dict] = {}
    for record in scene.manifest["entity_assets"]:
        document = parse_canonical_json(scene.blobs[record["uri"]])
        for entity in document["entities"]:
            if entity["kind"] != "face":
                continue
            for tag in (str(t) for t in entity["tags"]):
                if tag.startswith("interface."):
                    interfaces[tag] = {
                        "area": float(entity["properties"]["area"]),
                        "centroid": [float(v) for v in entity["properties"]["centroid"]],
                    }
    return {
        "definition_id": package.root_definition.definition_id,
        "revision": package.root_definition.revision,
        "part": part,
        "body": body,
        "volume": body.get_volume(),
        "bbox": bbox_of(body.wrapped),
        "inspection": inspection,
        "interfaces": interfaces,
    }


def main() -> None:
    new = package_facts(NEW_PACKAGE)
    old = package_facts(LEGACY_PACKAGE)

    print(f"E5 PASS packages re-opened: {new['definition_id']}@{new['revision']} (new) "
          f"vs {old['definition_id']}@{old['revision']} (legacy)")
    assert new["definition_id"] == old["definition_id"] == "ap242_gmsh_bracket"

    ok, rel = gate_volume(new["volume"], old["volume"])
    assert ok, f"E1 volume rel {rel}"
    print(f"E1 PASS volume new={new['volume']:.6f} legacy={old['volume']:.6f} rel={rel:.2e}")

    ok, delta = gate_bbox(new["bbox"], old["bbox"])
    assert ok, f"E2 bbox delta {delta}"
    print(
        "E2 PASS bbox new=(" + ",".join(f"{v:.4f}" for v in new["bbox"]) + ")"
        " legacy=(" + ",".join(f"{v:.4f}" for v in old["bbox"]) + f") max_delta={delta:.4f}"
    )

    ok, problems = gate_interfaces(new["interfaces"], old["interfaces"])
    assert ok, f"E3 interface problems: {problems}"
    print(f"E3 PASS interface sets equal ({len(new['interfaces'])} tags), areas/centroids within tolerance")

    inspection = new["inspection"]
    assert inspection.valid, f"E4 brep invalid: {inspection.counts}"
    counts = inspection.counts
    assert counts.get("solid", 0) == 1, f"E4 solid count {counts}"
    assert counts.get("closed_shell", 0) == 1 and counts.get("open_shell", 0) == 0, (
        f"E4 shell closure {counts}"
    )
    assert inspection.volume > 0.0, "E4 positive volume"
    assert abs(inspection.volume - new["volume"]) < 1e-3, "E4 volume agreement"
    print(
        f"E4 PASS brep valid solids=1 volume={inspection.volume:.3f} "
        f"counts={ {k: v for k, v in sorted(inspection.counts.items())} }"
    )

    for name, path in sorted(EXPORTS.items()):
        assert path.is_file() and path.stat().st_size > 0, f"E6 missing {name}: {path}"
        print(f"E6 PASS {name} {path.stat().st_size} bytes")

    print("S3 VERIFY: ALL PASS")


if __name__ == "__main__":
    main()
