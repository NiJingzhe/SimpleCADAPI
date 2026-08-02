# translate_model_json_to_fcstd

## API Definition

```python
def translate_model_json_to_fcstd(json_str: str, output_path: str, *, document_name: str = 'SimpleCADModel', freecad_cmd: Optional[str] = None) -> str
```

*Source: translator/freecad_translator/api.py*

## Import Surface

- translator backend: `from simplecadapi.translator.freecad_translator import translate_model_json_to_fcstd`

## Description

Translate canonical model JSON to `.FCStd` via FreeCADCmd/FreeCAD.

Functional sketch promotions are written as visible `Sketcher::SketchObject`
nodes with mapped/skipped constraint evidence. Exact B-spline edges are
exported to FreeCAD using `Part.BSplineCurve().buildFromPolesMultsKnots(...)`.
Safe single-use profile transforms such as section rotate/translate chains are
folded into the section object's placement so downstream `Part::Loft` receives
already-positioned sections instead of placement-bearing `App::Link` proxies.
Geometry is presented as a native FreeCAD occurrence tree. Serialized assignment
targets name design objects, repeated low-level nodes from one source callsite are
folded, and shared profiles or boolean inputs are copied per consuming result.
FreeCAD `Base`, `Tool`, `Sections`, and related links preserve recomputing
dependencies. Stable node IDs remain available in SimpleCAD metadata instead of
appearing as primary user-facing names.

`apply_tag_rselection` does not create a FreeCAD tree object. Its canonical
bindings are exposed on the traceable native geometry occurrences through
`SimpleCADAppliedTags`, `SimpleCADTagBindings`, and `SimpleCADTagNodeIds`.

Part/Assembly product nodes are written as editable FreeCAD assembly structure:
parts use `App::Part`, assemblies use native `Assembly::AssemblyObject`, part
components use `App::Link`, and nested assembly components use
`Assembly::AssemblyLink`. Explicit assembly-to-compound projections remain
available for geometry workflows without creating a second user-facing root.
Link source definitions remain in the document for recomputation, but no
product-library group or loose graph steps appear as top-level Tree View items.
