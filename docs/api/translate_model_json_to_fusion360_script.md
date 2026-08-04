# translate_model_json_to_fusion360_script

## API Definition

```python
def translate_model_json_to_fusion360_script(json_str: str, document_name: str = 'SimpleCADModel', result_node_ids: Optional[Sequence[str]] = None, *, selection_mode: str = 'gsm', source_kernel_fallback: bool = False) -> str
```

*Source: translator/fusion360_translator/api.py*

## Import Surface

- translator backend: `from simplecadapi.translator.fusion360_translator import translate_model_json_to_fusion360_script`

## Description

Translate canonical model JSON into a Fusion 360 Python script.
