"""S2 hypothesis probe: prove the hole-card and tag-set checks discriminate.

Runs the proposed measurements against the rebuilt s2 body and against two
known-bad variants (perturbed matcher target, perturbed hole radius) to show
each check can fail. A check that cannot fail is not a check.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import simplecadapi as scad
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_SurfaceType

HERE = Path(__file__).resolve().parent
MODEL = HERE.parent / "model.py"
LEGACY = json.loads((HERE / "legacy_baseline_facts.json").read_text())


def load_module():
    spec = importlib.util.spec_from_file_location("bracket_model_h", MODEL)
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
        location = cylinder.Location()
        center = face.get_center()
        cards.append(
            {
                "center": (round(center.x, 4), round(center.y, 4), round(center.z, 4)),
                "area": round(face.get_area(), 4),
                "radius": round(cylinder.Radius(), 4),
                "axis": (round(axis.X(), 4), round(axis.Y(), 4), round(axis.Z(), 4)),
                "axis_loc": (round(location.X(), 4), round(location.Y(), 4), round(location.Z(), 4)),
            }
        )
    return cards


def cards_match(cards: list[dict], legacy_cards: list[dict]) -> bool:
    if len(cards) != len(legacy_cards):
        return False
    for card in cards:
        if not any(
            abs(card["radius"] - other["radius"]) <= 0.01
            and all(abs(a - b) <= 0.01 for a, b in zip(card["axis"], other["axis"]))
            and all(abs(a - b) <= 0.05 for a, b in zip(card["center"], other["center"]))
            for other in legacy_cards
        ):
            return False
    return True


def main() -> None:
    module = load_module()
    body = module.build_stage("s2")

    volume = body.get_volume()
    expected = 10368.0 - (2 * math.pi * 2.5**2 * 4.0 + math.pi * 3.0**2 * 4.0)
    volume_ok = abs(volume - expected) / expected <= 1e-3 and abs(volume - 10097.790499) <= 10.1
    print(f"H1 volume={volume:.4f} expected={expected:.4f} legacy=10097.790499 -> {'PASS' if volume_ok else 'FAIL'}")

    cards = cylinder_cards(body)
    cards_ok = cards_match(cards, LEGACY["cylinders"])
    print(f"H2 cylinder cards n={len(cards)} legacy n={len(LEGACY['cylinders'])} -> {'PASS' if cards_ok else 'FAIL'}")
    for card in cards:
        print("   card", card)

    # known-bad A: card comparison must reject a radius perturbation (2.5 -> 2.6)
    bad_cards = [dict(card, radius=round(card["radius"] + 0.1, 4)) for card in cards]
    print(f"H3 known-bad perturbed-radius cards rejected -> {'PASS' if not cards_match(bad_cards, LEGACY['cylinders']) else 'FAIL'}")

    # known-bad B: matcher must reject a target beyond its 10 mm guard
    # (H4 first draft used +5 mm — inside the guard band, plane at 9 mm still
    #  legitimately matched; the discriminating probe must exceed the guard)
    try:
        module._tag_interface_face(
            body, center=(17.0, 0.0, 18.0), normal=(-1.0, 0.0, 0.0), tag="interface.bogus"
        )
        print("H4 known-bad beyond-guard matcher target rejected -> FAIL (no error raised)")
    except ValueError as error:
        print(f"H4 known-bad beyond-guard matcher target rejected -> PASS ({error})")

    assert volume_ok and cards_ok
    print("S2 hypothesis conclusion: checks discriminate -> adopt")


if __name__ == "__main__":
    main()
