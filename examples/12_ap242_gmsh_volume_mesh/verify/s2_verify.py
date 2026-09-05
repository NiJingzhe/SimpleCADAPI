"""S2 verifier: hole pattern + interface tags stage gate against model.py.

Criteria (BUILD_PLAN S2):
  C1 volume = 10368 - 270.177 (+/-0.1%) AND |V - legacy 10097.790499| < 0.1%
  C2 cylindrical faces: exactly 3, radius/axis/center match legacy facts
  C3 body carries role.structural_l_bracket
  C4 captured package scene: interface tag set == legacy 5-tag set, each face
     area rel diff <= 1e-4 and centroid delta <= 1e-3 mm
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import simplecadapi as scad
from OCP.BRepAdaptor import BRepAdaptor_Surface
from simplecadapi.scene import parse_canonical_json, read_scene_package
from OCP.GeomAbs import GeomAbs_SurfaceType

HERE = Path(__file__).resolve().parent
MODEL = HERE.parent / "model.py"
OUT_DIR = HERE.parents[1] / "out" / "ap242_gmsh_volume_mesh"
PACKAGE_PATH = OUT_DIR / "ap242_gmsh_bracket.scadpkg"
LEGACY = json.loads((HERE / "legacy_baseline_facts.json").read_text())
LEGACY_INTERFACES = json.loads((HERE / "legacy_interface_facts.json").read_text())

ANALYTIC_S2 = 10368.0 - (2 * math.pi * 2.5**2 * 4.0 + math.pi * 3.0**2 * 4.0)


def load_module():
    spec = importlib.util.spec_from_file_location("bracket_model_v", MODEL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cylinder_cards(body: scad.Solid) -> list[dict]:
    cards = []
    for face in scad.ql.faces().where(scad.ql.prop("geom.type", "==", "CYLINDER")).resolve(body):
        adaptor = BRepAdaptor_Surface(face.wrapped)
        if adaptor.GetType() != GeomAbs_SurfaceType.GeomAbs_Cylinder:
            continue
        cylinder = adaptor.Cylinder()
        axis = cylinder.Axis().Direction()
        center = face.get_center()
        cards.append(
            {
                "center": (center.x, center.y, center.z),
                "area": face.get_area(),
                "radius": cylinder.Radius(),
                "axis": (axis.X(), axis.Y(), axis.Z()),
            }
        )
    return cards


def scene_interfaces(package_path: Path) -> dict[str, dict]:
    package = scad.read_product_package(package_path)
    scene = read_scene_package(package.scene_bytes)
    interfaces: dict[str, dict] = {}
    for record in scene.manifest["entity_assets"]:
        document = parse_canonical_json(scene.blobs[record["uri"]])
        for entity in document["entities"]:
            if entity["kind"] != "face":
                continue
            for tag in (str(t) for t in entity["tags"]):
                if tag.startswith("interface."):
                    assert tag not in interfaces, f"duplicate interface tag {tag}"
                    interfaces[tag] = {
                        "area": float(entity["properties"]["area"]),
                        "centroid": [float(v) for v in entity["properties"]["centroid"]],
                    }
    return interfaces


def main() -> None:
    module = load_module()
    body = module.build_stage("s2")

    volume = body.get_volume()
    assert abs(volume - ANALYTIC_S2) / ANALYTIC_S2 <= 1e-3, f"C1 analytic {volume} vs {ANALYTIC_S2}"
    legacy_volume = LEGACY["volume"]
    assert abs(volume - legacy_volume) / legacy_volume <= 1e-3, f"C1 legacy {volume} vs {legacy_volume}"
    print(f"C1 PASS volume={volume:.6f} analytic={ANALYTIC_S2:.4f} legacy={legacy_volume} rel={(volume - legacy_volume) / legacy_volume:+.6e}")

    cards = cylinder_cards(body)
    legacy_cards = LEGACY["cylinders"]
    assert len(cards) == 3, f"C2 expected 3 cylinder faces, got {len(cards)}"
    for card in cards:
        assert any(
            abs(card["radius"] - other["radius"]) <= 0.01
            and all(abs(a - b) <= 0.01 for a, b in zip(card["axis"], other["axis"]))
            and all(abs(a - b) <= 0.05 for a, b in zip(card["center"], other["center"]))
            for other in legacy_cards
        ), f"C2 no legacy match for {card}"
    radii = sorted(round(c["radius"], 3) for c in cards)
    print(f"C2 PASS 3 cylinder faces r={radii} match legacy cards")

    tags = scad.list_tags(shape=body)
    assert "role.structural_l_bracket" in tags, f"C3 role tag missing: {tags}"
    print(f"C3 PASS body tags {tags}")

    interfaces = scene_interfaces(PACKAGE_PATH)
    assert set(interfaces) == set(LEGACY_INTERFACES), (
        f"C4 tag set mismatch: {sorted(interfaces)} vs {sorted(LEGACY_INTERFACES)}"
    )
    for tag, facts in sorted(interfaces.items()):
        legacy_facts = LEGACY_INTERFACES[tag]
        area_rel = abs(facts["area"] - legacy_facts["area"]) / legacy_facts["area"]
        centroid_delta = max(
            abs(a - b) for a, b in zip(facts["centroid"], legacy_facts["centroid"])
        )
        assert area_rel <= 1e-4, f"C4 {tag} area rel {area_rel}"
        assert centroid_delta <= 1e-3, f"C4 {tag} centroid delta {centroid_delta}"
        print(
            f"C4 PASS {tag} area={facts['area']:.4f} (rel {area_rel:.2e}) "
            f"centroid=({facts['centroid'][0]:.4f},{facts['centroid'][1]:.4f},{facts['centroid'][2]:.4f}) d={centroid_delta:.2e}"
        )
    print("S2 VERIFY: ALL PASS")


if __name__ == "__main__":
    main()
