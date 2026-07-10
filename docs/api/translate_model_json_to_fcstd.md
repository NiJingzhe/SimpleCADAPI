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
Part/Assembly product nodes are written as editable FreeCAD assembly structure:
parts use `App::Part`, assemblies use native `Assembly::AssemblyObject`, part
components use `App::Link`, and nested assembly components use
`Assembly::AssemblyLink`. Explicit assembly-to-compound projections remain in
the document for geometry workflows but do not replace the visible assembly
tree.
