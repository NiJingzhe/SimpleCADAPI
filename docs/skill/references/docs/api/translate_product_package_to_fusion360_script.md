# translate_product_package_to_fusion360_script

## API Definition

```python
def translate_product_package_to_fusion360_script(data: ProductPackageInput, document_name: str = 'SimpleCADProduct', *, selection_mode: str = 'gsm', source_kernel_fallback: bool = False) -> str
```

*Source: translator/fusion360_translator/api.py*

## Import Surface

- translator backend: `from simplecadapi.translator.fusion360_translator import translate_product_package_to_fusion360_script`

## Description

Translate one validated `.scadpkg` closure into a Fusion 360 script.
