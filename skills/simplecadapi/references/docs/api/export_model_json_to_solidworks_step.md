# export_model_json_to_solidworks_step

## API Definition

```python
def export_model_json_to_solidworks_step(json_str: str, output_path: str, *, document_name: str = 'SimpleCADModel', visible: bool = False, python_exe: Optional[str] = None, source_kernel_fallback: bool = False) -> str
```

*Source: translator/solidworks_translator/api.py*

## Import Surface

- translator backend: `from simplecadapi.translator.solidworks_translator import export_model_json_to_solidworks_step`

## Description

Execute SolidWorks COM automation and export a STEP file.
