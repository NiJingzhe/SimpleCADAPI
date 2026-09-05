"""Role 1 input classification: measure the existing legacy bracket model.

Read-only inspection of the provided reference model (examples/12/.../model.py
before formalization). Produces verify/legacy_baseline_facts.json used later by
the S3 equivalence verifier. No new geometry is authored here.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import simplecadapi as scad
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.GeomAbs import GeomAbs_SurfaceType

HERE = Path(__file__).resolve().parent
MODEL = HERE.parent / "model.py"
FACTS_OUT = HERE.parent / "verify" / "legacy_baseline_facts.json"


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("legacy_bracket_model", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bbox_of(solid: scad.Solid) -> dict:
    box = Bnd_Box()
    box.SetGap(0.0)
    BRepBndLib.AddOptimal_s(solid.wrapped, box, True, False)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    return {
        "min": [round(v, 6) for v in (xmin, ymin, zmin)],
        "max": [round(v, 6) for v in (xmax, ymax, zmax)],
    }


def cylinder_cards(body: scad.Solid) -> list[dict]:
    cards = []
    sel = scad.ql.faces().where(scad.ql.prop("geom.type", "==", "CYLINDER"))
    for face in sel.resolve(body):
        adaptor = BRepAdaptor_Surface(face.wrapped)
        if adaptor.GetType() != GeomAbs_SurfaceType.GeomAbs_Cylinder:
            continue
        cylinder = adaptor.Cylinder()
        axis = cylinder.Axis().Direction()
        location = cylinder.Location()
        center = face.get_center()
        cards.append(
            {
                "center": [round(center.x, 4), round(center.y, 4), round(center.z, 4)],
                "area": round(face.get_area(), 4),
                "radius": round(cylinder.Radius(), 4),
                "axis": [round(axis.X(), 4), round(axis.Y(), 4), round(axis.Z(), 4)],
                "axis_loc": [round(location.X(), 4), round(location.Y(), 4), round(location.Z(), 4)],
            }
        )
    return cards


def main() -> None:
    module = load_module(MODEL)
    result = module.build_bracket()
    body = result.part.body

    faces = scad.ql.faces().resolve(body)
    volume = body.get_volume()
    tags = scad.list_tags(shape=body)
    facts = {
        "volume": round(volume, 6),
        "face_count": len(faces),
        "bbox": bbox_of(body),
        "tags": tags,
        "cylinders": cylinder_cards(body),
        "material": {
            "id": result.part.material.material_id if getattr(result.part, "material", None) else None,
        },
        "part_id": result.part.part_id,
        "name": result.part.name,
    }
    print("part", facts["part_id"], facts["name"])
    print("volume", facts["volume"])
    print("faces", facts["face_count"])
    print("bbox", facts["bbox"])
    print("tags", tags)
    for card in facts["cylinders"]:
        print("cyl", card)
    FACTS_OUT.parent.mkdir(parents=True, exist_ok=True)
    FACTS_OUT.write_text(json.dumps(facts, indent=2))
    print("facts_json", FACTS_OUT)


if __name__ == "__main__":
    main()
