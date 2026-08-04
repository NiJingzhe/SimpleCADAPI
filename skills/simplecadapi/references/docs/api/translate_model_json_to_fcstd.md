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
Geometry results use native FreeCAD objects directly: assignment targets name
design objects, shared inputs receive independent occurrences per consumer,
and native feature links preserve recomputing dependencies. No presentation
proxy, duplicate history tree, or hidden graph-object archive is created.
`apply_tag_rselection` remains graph metadata rather than a FreeCAD feature;
traceable geometry and visible result objects expose `SimpleCADAppliedTags`,
`SimpleCADTagBindings`, and `SimpleCADTagNodeIds`.
Part/Assembly product nodes are written as editable FreeCAD assembly structure:
parts use `App::Part`, assemblies use native `Assembly::AssemblyObject`, part
components use `App::Link`, and nested assembly components use
`Assembly::AssemblyLink`. Explicit assembly-to-compound projections remain
available for geometry workflows without creating a second user-facing root.
Link source definitions remain in the document for recomputation, but the
Tree View exposes only the resolved product or standalone-geometry roots.
