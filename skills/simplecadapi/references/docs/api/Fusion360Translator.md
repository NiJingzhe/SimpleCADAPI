# Fusion360Translator

## Class Definition

```python
class Fusion360Translator(document_name: str = 'SimpleCADModel', result_node_ids: Optional[Sequence[str]] = None, *, selection_mode: str = 'gsm', source_kernel_fallback: bool = False)
```

*Source: translator/fusion360_translator/translator.py*

## Import Surface

- translator backend: `from simplecadapi.translator.fusion360_translator import Fusion360Translator`

## Description

Translate canonical model JSON into a Fusion 360 Python script.
