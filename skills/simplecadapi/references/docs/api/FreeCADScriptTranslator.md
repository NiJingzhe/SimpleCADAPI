# FreeCADScriptTranslator

## Class Definition

```python
class FreeCADScriptTranslator(document_name: str = 'SimpleCADModel')
```

*Source: translator/freecad_translator/script_translator.py*

## Import Surface

- translator backend: `from simplecadapi.translator.freecad_translator import FreeCADScriptTranslator`

## Description

Compile a SimpleCAD model payload into a FreeCAD Python script.

Current design goals:

- Translate only from the canonical low-level `graph` IR
- Preserve node metadata and graph lineage as FreeCAD custom properties
- Preserve `expression_graph` as explicit translator metadata
- Preserve dimension tolerances and tolerance-chain requirements as metadata
- Preserve exported assembly constraints as document metadata objects
- Present geometry as variable-named native FreeCAD occurrence trees instead of
  a flat node-id tree or a separate presentation copy
- Expose only resolved product or standalone-geometry roots in FreeCAD Tree View;
  assembly projection compounds and link source definitions remain internal
- Lower `apply_tag_rselection` to custom properties on traceable geometry and
  visible results instead of creating a FreeCAD feature or history step
- Keep assembly metadata from the full model payload alongside the IR-driven
  geometry translation

The generated script uses native FreeCAD geometry objects for both computation
and the document tree. Serialized assignment targets label the native objects;
shared DAG inputs are copied per consuming result so every result has a complete,
recomputing dependency subtree. Stable node IDs remain available through
SimpleCAD custom properties rather than appearing as user-facing names.
