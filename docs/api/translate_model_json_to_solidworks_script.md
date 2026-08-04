# translate_model_json_to_solidworks_script

## API Definition

```python
def translate_model_json_to_solidworks_script(json_str: str, document_name: str = 'SimpleCADModel', *, output_path: Optional[str] = None, visible: bool = False, source_kernel_fallback: bool = False) -> str
```

*Source: translator/solidworks_translator/api.py*

## Import Surface

- translator backend: `from simplecadapi.translator.solidworks_translator import translate_model_json_to_solidworks_script`

## Description

Translate canonical model JSON into a SolidWorks automation script.
