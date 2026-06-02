# translate_model_json_to_fcstd

## API Definition

```python
def translate_model_json_to_fcstd(json_str: str, output_path: str, *, document_name: str = 'SimpleCADModel', freecad_cmd: Optional[str] = None) -> str
```

*Source: freecad_translator.py*

## Import Surface

- top-level: `from simplecadapi import translate_model_json_to_fcstd`

## Description

Translate canonical model JSON to `.FCStd` via FreeCADCmd/FreeCAD.
