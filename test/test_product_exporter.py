"""End-to-end tests for product-package STEP and STL exporters."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import trimesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.StepRepr import StepRepr_DescriptiveRepresentationItem
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFPrs import XCAFPrs_DocumentExplorer

import simplecadapi as scad
from simplecadapi.inspect.brep.render import _load_step_xcaf


def _label_name(label) -> str:
    attribute = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), attribute):
        return attribute.Get().ToExtString()
    return ""


def _read_occurrences(path: Path) -> list[dict[str, object]]:
    XCAFApp_Application.GetApplication_s()
    document = TDocStd_Document(TCollection_ExtendedString("BinXCAF"))
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    reader.SetColorMode(True)
    reader.SetPropsMode(True)
    if reader.ReadFile(str(path)) != IFSelect_RetDone or not reader.Transfer(document):
        raise AssertionError(f"could not read exported STEP file {path}")
    explorer = XCAFPrs_DocumentExplorer(document, 0)
    records: list[dict[str, object]] = []
    while explorer.More():
        node = explorer.Current()
        translation = node.Location.Transformation().TranslationPart()
        records.append(
            {
                "depth": int(explorer.CurrentDepth()),
                "name": _label_name(node.Label) or _label_name(node.RefLabel),
                "ref_name": _label_name(node.RefLabel),
                "assembly": bool(node.IsAssembly),
                "xyz": [
                    round(float(translation.X()), 3),
                    round(float(translation.Y()), 3),
                    round(float(translation.Z()), 3),
                ],
            }
        )
        explorer.Next()
    return records


def _read_simplecad_metadata(path: Path) -> dict[str, dict[str, object]]:
    reader = STEPCAFControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise AssertionError(f"could not read exported STEP file {path}")
    model = reader.ChangeReader().WS().Model()
    records: dict[str, dict[str, object]] = {}
    for index in range(1, model.NbEntities() + 1):
        entity = model.Entity(index)
        if not isinstance(entity, StepRepr_DescriptiveRepresentationItem):
            continue
        name = entity.Name().ToCString()
        if not name.startswith("SimpleCAD:"):
            continue
        records[name] = json.loads(entity.Description().ToCString())
    return records


def _build_nested_package(root: Path):
    cache = scad.CachePolicy(root=root / "cache")

    @scad.part(id="linked", cache=cache, project_root=Path(__file__).parent)
    def build_part() -> scad.Part:
        body = scad.make_box_rsolid(1.0, 2.0, 3.0)
        face = scad.apply_tag(body.get_faces()[0], "interface.mount_face")
        part = scad.make_part_rpart("linked", body, name="Part linked")
        return scad.add_connector_rpart(
            part,
            scad.make_face_connector_rconnector("mount", face),
        )

    part = build_part()

    @scad.assemble(
        id="child",
        definitions=(part,),
        cache=cache,
        project_root=Path(__file__).parent,
    )
    def build_child() -> scad.Assembly:
        assembly = scad.make_assembly_rassembly("child", name="Child assembly")
        for component_id, name in (
            ("inner_a", "Inner linked part A"),
            ("inner_b", "Inner linked part B"),
        ):
            assembly = scad.add_component_rassembly(
                assembly,
                part.value,
                component_id=component_id,
                placement=scad.identity_placement_rplacement(),
                name=name,
            )
        assembly = scad.ground_component_rassembly(assembly, "inner_a")
        assembly = scad.add_revolute_constraint_rassembly(
            assembly,
            "joint",
            scad.make_connector_ref_rconnectorref("inner_a", "mount"),
            scad.make_connector_ref_rconnectorref("inner_b", "mount"),
            drive_angle_degrees=15.0,
        )
        return scad.solve_assembly_constraints_rassembly(assembly)

    child = build_child()

    @scad.assemble(
        id="root",
        definitions=(child, part),
        cache=cache,
        project_root=Path(__file__).parent,
    )
    def build_root() -> scad.Assembly:
        assembly = scad.make_assembly_rassembly("root", name="Root assembly")
        assembly = scad.add_component_rassembly(
            assembly,
            child.value,
            component_id="nested",
            placement=scad.make_placement_rplacement(origin=(10.0, 0.0, 0.0)),
            name="Nested child assembly",
        )
        return scad.add_component_rassembly(
            assembly,
            part.value,
            component_id="direct",
            placement=scad.make_placement_rplacement(origin=(0.0, 5.0, 0.0)),
            name="Direct linked part",
        )

    return scad.build_product_package(build_root())


class TestProductExporter(unittest.TestCase):
    def test_exporters_are_available_only_from_exporter_namespace(self):
        self.assertIs(
            scad.exporter.export_product_package_to_step,
            scad.exporter.step.export_product_package_to_step,
        )
        self.assertIs(
            scad.exporter.export_product_package_to_stl,
            scad.exporter.stl.export_product_package_to_stl,
        )
        self.assertFalse(hasattr(scad, "export_step"))
        self.assertFalse(hasattr(scad, "export_stl"))
        self.assertFalse(hasattr(scad.translator, "ap242_translator"))

    def test_nested_package_preserves_ap242_product_structure_and_placements(self):

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            package = _build_nested_package(root)
            step_path = root / "nested.step"
            report = scad.exporter.export_product_package_to_step(package, step_path)
            records = _read_occurrences(step_path)
            content = step_path.read_text(encoding="utf-8")
            metadata = _read_simplecad_metadata(step_path)

        self.assertIn("AP242_MANAGED_MODEL_BASED_3D_ENGINEERING", content)
        self.assertEqual(report.schema, "AP242DIS")
        self.assertEqual(report.definition_ids, ("linked", "child", "root"))
        self.assertEqual(report.occurrence_count, 4)
        self.assertEqual(report.metadata_item_count, 7)
        self.assertEqual(
            set(metadata),
            {
                "SimpleCAD:definition:single_solid:linked",
                "SimpleCAD:definition:assembly:child",
                "SimpleCAD:definition:assembly:root",
                "SimpleCAD:occurrence:child:inner_a",
                "SimpleCAD:occurrence:child:inner_b",
                "SimpleCAD:occurrence:root:nested",
                "SimpleCAD:occurrence:root:direct",
            },
        )
        linked = metadata["SimpleCAD:definition:single_solid:linked"]
        self.assertEqual(linked["revision"], "1.0.0")
        self.assertRegex(str(linked["content_hash"]), r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(linked["connectors"][0]["connector_id"], "mount")
        child = metadata["SimpleCAD:definition:assembly:child"]
        self.assertEqual(child["grounded_component_ids"], ["inner_a"])
        self.assertEqual(child["constraints"][0]["constraint_id"], "joint")
        self.assertEqual(child["constraints"][0]["drive_angle_degrees"], 15.0)
        nested = metadata["SimpleCAD:occurrence:root:nested"]
        self.assertEqual(nested["definition_id"], "child")
        self.assertEqual(nested["placement"]["origin"], [10.0, 0.0, 0.0])
        self.assertEqual(
            records,
            [
                {
                    "depth": 0,
                    "name": "Root assembly",
                    "ref_name": "Root assembly",
                    "assembly": True,
                    "xyz": [0.0, 0.0, 0.0],
                },
                {
                    "depth": 1,
                    "name": "Direct linked part",
                    "ref_name": "Part linked",
                    "assembly": False,
                    "xyz": [0.0, 5.0, 0.0],
                },
                {
                    "depth": 1,
                    "name": "Nested child assembly",
                    "ref_name": "Child assembly",
                    "assembly": True,
                    "xyz": [10.0, 0.0, 0.0],
                },
                {
                    "depth": 2,
                    "name": "Inner linked part A",
                    "ref_name": "Part linked",
                    "assembly": False,
                    "xyz": [10.0, 0.0, 0.0],
                },
                {
                    "depth": 2,
                    "name": "Inner linked part B",
                    "ref_name": "Part linked",
                    "assembly": False,
                    "xyz": [10.0, -0.388, 0.051],
                },
            ],
        )
        self.assertTrue(any("feature history" in item for item in report.limitations))
        self.assertFalse(any("OCAF comments" in item for item in report.limitations))

    def test_part_material_and_color_enter_stepcaf_payload(self):

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cache = scad.CachePolicy(root=root / "cache")

            @scad.part(
                id="colored",
                cache=cache,
                project_root=Path(__file__).parent,
            )
            def build_colored() -> scad.Part:
                body = scad.make_box_rsolid(1.0, 2.0, 3.0)
                part = scad.make_part_rpart("colored", body, name="Colored part")
                material = scad.make_material_rmaterial(
                    "blue_aluminum",
                    name="Blue aluminum",
                    density=2.7e-6,
                    density_unit="kg/mm^3",
                    color=(0.2, 0.4, 0.6),
                )
                return scad.assign_material_rpart(part, material)

            package = scad.build_product_package(build_colored())
            step_path = root / "colored.step"
            report = scad.exporter.export_product_package_to_step(package, step_path)
            content = step_path.read_text(encoding="utf-8")
            _shape, face_colors = _load_step_xcaf(step_path)

        self.assertEqual(report.material_ids, ("blue_aluminum",))
        self.assertIn(
            "PROPERTY_DEFINITION('material property','material name'", content
        )
        self.assertIn("MEASURE_REPRESENTATION_ITEM('kg/mm^3',2.7E-06", content)
        self.assertIn('"material_id": "blue_aluminum"', content)
        self.assertTrue(face_colors)
        self.assertEqual(
            {
                tuple(round(value, 3) for value in color[:3])
                for color in face_colors.values()
            },
            {(0.2, 0.4, 0.6)},
        )

    def test_nested_package_exports_quad_dominant_stl(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            package = _build_nested_package(root)
            stl_path = root / "nested.stl"
            report = scad.exporter.export_product_package_to_stl(
                package,
                stl_path,
                mesh_size=0.75,
            )
            mesh = trimesh.load_mesh(stl_path, force="mesh", process=False)

        self.assertEqual(report.root_definition_id, "root")
        self.assertEqual(report.definition_count, 3)
        self.assertEqual(report.solid_count, 3)
        self.assertGreater(report.quadrilateral_count, 0)
        self.assertGreater(report.quad_fraction, 0.5)
        self.assertEqual(len(mesh.faces), report.stl_triangle_count)
        self.assertTrue(
            np.allclose(
                mesh.bounds,
                [[-0.5, -1.35415439394285, -0.2077077845361233], [10.5, 6.0, 3.207707784536123]],
            )
        )


if __name__ == "__main__":
    unittest.main()
