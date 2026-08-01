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

Geometry is emitted as a human-readable native occurrence tree. Serialized
`source.assignment_targets` name native design objects; low-level graph nodes
produced by one source callsite are folded into one operation. Shared profiles
and boolean inputs are copied per consuming result, while stable node IDs remain
available as internal SimpleCAD metadata rather than user-facing labels.

Tag application is metadata-only in FreeCAD. `apply_tag_rselection` creates no
feature or history step; its canonical bindings and graph node IDs are attached
to traceable geometry and visible result objects through
`SimpleCADAppliedTags`, `SimpleCADTagBindings`, and `SimpleCADTagNodeIds`.

Standalone geometry results use their native FreeCAD feature as the visible
result and retain native dependency links for recomputation. No separate result
proxy or duplicate history tree is created. Product nodes retain their native
structure: parts use `App::Part`, assemblies use `Assembly::AssemblyObject`, part
components use `App::Link`, and subassembly components use
`Assembly::AssemblyLink` when the Assembly workbench module is available.

The user-facing Tree View contains only resolved product roots or standalone
geometry roots. Assembly projection compounds do not create preview-model roots,
and `App::Link` source definitions remain internal rather than appearing in a
product-library group or as loose top-level steps.
