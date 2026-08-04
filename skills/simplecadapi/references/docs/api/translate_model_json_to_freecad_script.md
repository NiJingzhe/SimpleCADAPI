# translate_model_json_to_freecad_script

## API Definition

```python
def translate_model_json_to_freecad_script(json_str: str, document_name: str = 'SimpleCADModel') -> str
```

*Source: translator/freecad_translator/api.py*

## Import Surface

- translator backend: `from simplecadapi.translator.freecad_translator import translate_model_json_to_freecad_script`

## Description

Translate exported model JSON into a FreeCAD Python script.

Geometry is emitted as native FreeCAD occurrence trees. Serialized source
assignment targets name native design objects, shared DAG inputs are copied
per consuming result, and FreeCAD feature links preserve recomputing
dependencies. Stable node ids remain available as internal metadata.
`apply_tag_rselection` nodes do not create FreeCAD features. Their canonical
bindings and source node ids are attached to traceable geometry and visible
result objects as `SimpleCADAppliedTags`, `SimpleCADTagBindings`, and
`SimpleCADTagNodeIds`.
The Tree View exposes only resolved product or standalone-geometry roots.
Assembly projection compounds and link source definitions remain available
for recomputation but are hidden from the user-facing document tree.
