"""AP242 STEP export for validated product packages."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from OCP.BRep import BRep_Builder
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.StepBasic import StepBasic_ProductDefinition
from OCP.StepRepr import (
    StepRepr_CharacterizedDefinition,
    StepRepr_DescriptiveRepresentationItem,
    StepRepr_HArray1OfRepresentationItem,
    StepRepr_ProductDefinitionShape,
    StepRepr_PropertyDefinition,
    StepRepr_PropertyDefinitionRepresentation,
    StepRepr_Representation,
    StepRepr_RepresentedDefinition,
)
from OCP.StepShape import StepShape_ShapeDefinitionRepresentation
from OCP.TCollection import TCollection_ExtendedString, TCollection_HAsciiString
from OCP.TDataStd import TDataStd_Comment, TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS_Compound
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_ColorSurf, XCAFDoc_DocumentTool
from OCP.gp import gp_Trsf

from ..artifacts import materialize_definition
from ..assembly import Assembly
from ..material import Material
from ..part import Part
from ..placement import Placement
from ..translator.package_units import (
    ProductPackageInput,
    read_product_package_translation_units,
)


@dataclass(frozen=True, slots=True)
class ProductSTEPExportReport:
    """Observed AP242 export facts and explicit semantic limitations."""

    output_path: Path
    schema: str
    definition_ids: tuple[str, ...]
    occurrence_count: int
    material_ids: tuple[str, ...]
    metadata_item_count: int
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_path": str(self.output_path),
            "schema": self.schema,
            "definition_ids": list(self.definition_ids),
            "occurrence_count": self.occurrence_count,
            "material_ids": list(self.material_ids),
            "metadata_item_count": self.metadata_item_count,
            "limitations": list(self.limitations),
        }


def _extended(value: str) -> TCollection_ExtendedString:
    return TCollection_ExtendedString(str(value))


def _ascii(value: str) -> TCollection_HAsciiString:
    return TCollection_HAsciiString(str(value))


def _set_name(label: Any, value: str) -> None:
    TDataStd_Name.Set_s(label, _extended(value))


def _set_comment(label: Any, payload: dict[str, Any]) -> None:
    TDataStd_Comment.Set_s(
        label,
        _extended(json.dumps(payload, ensure_ascii=True, sort_keys=True)),
    )


def _placement_location(placement: Placement) -> TopLoc_Location:
    transform = gp_Trsf()
    transform.SetValues(
        placement.x_axis[0],
        placement.y_axis[0],
        placement.z_axis[0],
        placement.origin[0],
        placement.x_axis[1],
        placement.y_axis[1],
        placement.z_axis[1],
        placement.origin[1],
        placement.x_axis[2],
        placement.y_axis[2],
        placement.z_axis[2],
        placement.origin[2],
    )
    return TopLoc_Location(transform)


def _empty_compound() -> TopoDS_Compound:
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    return compound


def _material_density(material: Material) -> tuple[float, str, str]:
    if material.density is None:
        return 0.0, "", ""
    return float(material.density), str(material.density_unit or ""), "mass density"


def _inject_metadata_properties(
    writer: STEPCAFControl_Writer,
    records: list[tuple[str, dict[str, Any]]],
) -> None:
    if not records:
        return
    model = writer.ChangeWriter().WS().Model()
    root_definition = None
    context = None
    for index in range(1, model.NbEntities() + 1):
        entity = model.Entity(index)
        if not isinstance(entity, StepShape_ShapeDefinitionRepresentation):
            continue
        represented = entity.Definition().Value()
        if not isinstance(represented, StepRepr_ProductDefinitionShape):
            continue
        characterized = represented.Definition().Value()
        if not isinstance(characterized, StepBasic_ProductDefinition):
            continue
        root_definition = characterized
        context = entity.UsedRepresentation().ContextOfItems()
        break
    if root_definition is None or context is None:
        raise RuntimeError("STEPCAF transfer did not create a root product definition")

    items = StepRepr_HArray1OfRepresentationItem(1, len(records))
    for index, (name, payload) in enumerate(records, start=1):
        item = StepRepr_DescriptiveRepresentationItem()
        item.Init(
            _ascii(name),
            _ascii(json.dumps(payload, ensure_ascii=True, sort_keys=True)),
        )
        items.SetValue(index, item)
    representation = StepRepr_Representation()
    representation.Init(_ascii("SimpleCAD metadata"), items, context)
    characterized_definition = StepRepr_CharacterizedDefinition()
    characterized_definition.SetValue(root_definition)
    property_definition = StepRepr_PropertyDefinition()
    property_definition.Init(
        _ascii("SimpleCAD metadata"),
        True,
        _ascii("Canonical product definition and occurrence metadata"),
        characterized_definition,
    )
    represented_definition = StepRepr_RepresentedDefinition()
    represented_definition.SetValue(property_definition)
    property_representation = StepRepr_PropertyDefinitionRepresentation()
    property_representation.Init(represented_definition, representation)
    model.AddWithRefs(property_representation)


def export_product_package_to_step(
    data: ProductPackageInput,
    output_path: str | Path,
) -> ProductSTEPExportReport:
    """Export a validated `.scadpkg` closure as XCAF-backed AP242 STEP."""

    package, units = read_product_package_translation_units(data)
    root_value = materialize_definition(package.root_definition)
    destination = Path(output_path).expanduser().resolve()
    if destination.suffix.lower() not in {".step", ".stp"}:
        raise ValueError("output_path must end in .step or .stp")
    destination.parent.mkdir(parents=True, exist_ok=True)

    XCAFApp_Application.GetApplication_s()
    document = TDocStd_Document(_extended("BinXCAF"))
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool_s(document.Main())
    material_tool = XCAFDoc_DocumentTool.MaterialTool_s(document.Main())
    labels_by_identity: dict[tuple[str, str], Any] = {}
    material_labels: dict[str, Any] = {}
    units_by_identity = {
        (unit.definition_kind, unit.definition_id): unit for unit in units
    }
    metadata_records: list[tuple[str, dict[str, Any]]] = []
    occurrence_count = 0

    def material_label(material: Material) -> Any:
        existing = material_labels.get(material.material_id)
        if existing is not None:
            return existing
        density, density_name, density_value_type = _material_density(material)
        label = material_tool.AddMaterial(
            _ascii(material.name or material.material_id),
            _ascii(json.dumps(material.to_dict(), ensure_ascii=True, sort_keys=True)),
            density,
            _ascii(density_name),
            _ascii(density_value_type),
        )
        material_labels[material.material_id] = label
        return label

    def definition_label(value: Part | Assembly) -> Any:
        nonlocal occurrence_count
        kind = "assembly" if isinstance(value, Assembly) else "single_solid"
        definition_id = (
            value.assembly_id if isinstance(value, Assembly) else value.part_id
        )
        identity = (kind, definition_id)
        existing = labels_by_identity.get(identity)
        unit = units_by_identity.get(identity)
        if unit is None:
            raise RuntimeError(
                f"materialized definition {kind}:{definition_id} is absent from package units"
            )
        if existing is not None:
            return existing
        if isinstance(value, Part):
            label = shape_tool.AddShape(value.body.wrapped, False, False)
            labels_by_identity[identity] = label
            _set_name(label, value.name or value.part_id)
            metadata = {
                "record_kind": "definition",
                "definition_id": value.part_id,
                "definition_kind": kind,
                "revision": unit.revision,
                "content_hash": unit.content_hash,
                "connectors": [connector.to_dict() for connector in value.connectors],
            }
            _set_comment(label, metadata)
            metadata_records.append(
                (f"SimpleCAD:definition:{kind}:{definition_id}", metadata)
            )
            if value.material is not None:
                material_tool.SetMaterial(label, material_label(value.material))
                if value.material.color is not None:
                    color_tool.SetColor(
                        label,
                        Quantity_Color(*value.material.color, Quantity_TOC_RGB),
                        XCAFDoc_ColorSurf,
                    )
            return label

        label = shape_tool.AddShape(_empty_compound(), False, False)
        labels_by_identity[identity] = label
        _set_name(label, value.name or value.assembly_id)
        metadata = {
            "record_kind": "definition",
            "definition_id": value.assembly_id,
            "definition_kind": kind,
            "revision": unit.revision,
            "content_hash": unit.content_hash,
            "connectors": [connector.to_dict() for connector in value.connectors],
            "constraints": [constraint.to_dict() for constraint in value.constraints],
            "grounded_component_ids": list(value.grounded_component_ids),
        }
        _set_comment(label, metadata)
        metadata_records.append(
            (f"SimpleCAD:definition:{kind}:{definition_id}", metadata)
        )
        for component in value.components:
            child_label = definition_label(component.item)
            component_label = shape_tool.AddComponent(
                label,
                child_label,
                _placement_location(component.placement),
            )
            _set_name(component_label, component.name or component.component_id)
            child_kind = (
                "assembly" if isinstance(component.item, Assembly) else "single_solid"
            )
            child_id = (
                component.item.assembly_id
                if isinstance(component.item, Assembly)
                else component.item.part_id
            )
            occurrence_metadata = {
                "record_kind": "occurrence",
                "parent_definition_id": definition_id,
                "component_id": component.component_id,
                "definition_id": child_id,
                "definition_kind": child_kind,
                "name": component.name,
                "placement": component.placement.to_dict(),
            }
            _set_comment(component_label, occurrence_metadata)
            metadata_records.append(
                (
                    f"SimpleCAD:occurrence:{definition_id}:{component.component_id}",
                    occurrence_metadata,
                )
            )
            occurrence_count += 1
        shape_tool.UpdateAssemblies()
        shape_tool.ComputeShapes(label)
        return label

    root_label = definition_label(root_value)
    shape_tool.UpdateAssemblies()
    shape_tool.ComputeShapes(root_label)

    writer = STEPCAFControl_Writer()
    writer.SetNameMode(True)
    writer.SetColorMode(True)
    writer.SetMaterialMode(True)
    writer.SetPropsMode(True)
    schema_key = "write.step.schema"
    prior_schema = Interface_Static.CVal_s(schema_key)
    if not Interface_Static.SetCVal_s(schema_key, "AP242DIS"):
        raise RuntimeError("OCCT STEP writer does not expose AP242DIS schema selection")
    try:
        if not writer.Transfer(root_label):
            raise RuntimeError("STEPCAF transfer failed")
        _inject_metadata_properties(writer, metadata_records)
        status = writer.Write(str(destination))
        if status != IFSelect_RetDone and int(status) != int(IFSelect_RetDone):
            raise RuntimeError(f"STEPCAF write failed: {status}")
    finally:
        Interface_Static.SetCVal_s(schema_key, prior_schema)

    if not destination.is_file() or destination.stat().st_size <= 0:
        raise RuntimeError("STEPCAF export did not create a non-empty STEP file")
    limitations = (
        "Connector, constraint, grounding, revision, content-hash, and placement semantics are encoded as named AP242 descriptive property items containing deterministically sorted JSON.",
        "The evaluated BREP and product structure are transferred through STEPCAF; canonical feature history is not reconstructed as AP242 features.",
    )
    return ProductSTEPExportReport(
        output_path=destination,
        schema="AP242DIS",
        definition_ids=tuple(unit.definition_id for unit in units),
        occurrence_count=occurrence_count,
        material_ids=tuple(sorted(material_labels)),
        metadata_item_count=len(metadata_records),
        limitations=limitations,
    )


__all__ = ["ProductSTEPExportReport", "export_product_package_to_step"]
