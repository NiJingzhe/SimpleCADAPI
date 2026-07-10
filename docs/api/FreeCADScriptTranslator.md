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
- Preserve exported assembly constraints as document metadata objects
- Keep assembly metadata from the full model payload alongside the IR-driven
geometry translation

The generated script focuses on `Part`-workbench-style objects and shape
construction, which is a better first target for the current canonical graph
than a full `Sketcher/PartDesign` mapping.
