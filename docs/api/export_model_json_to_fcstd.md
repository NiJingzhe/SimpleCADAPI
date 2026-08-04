# export_model_json_to_fcstd

## API Definition

```python
def export_model_json_to_fcstd(json_str: str, output_path: str, *, document_name: str = 'SimpleCADModel', freecad_cmd: Optional[str] = None) -> str
```

*Source: translator/freecad_translator/api.py*

## Import Surface

- translator backend: `from simplecadapi.translator.freecad_translator import export_model_json_to_fcstd`

## Description

Export canonical model JSON to `.FCStd` via FreeCADCmd/FreeCAD.
