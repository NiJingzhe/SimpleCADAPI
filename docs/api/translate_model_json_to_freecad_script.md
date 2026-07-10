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

Part/Assembly product nodes are emitted as editable FreeCAD document
structure: parts use `App::Part`, assemblies use native
`Assembly::AssemblyObject`, part components use `App::Link`, and
subassembly components use `Assembly::AssemblyLink` when the Assembly
workbench module is available.
