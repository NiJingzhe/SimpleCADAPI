# translate_product_package_to_solidworks_script

## API Definition

```python
def translate_product_package_to_solidworks_script(data: ProductPackageInput, document_name: str = 'SimpleCADProduct', *, output_path: str | None = None, visible: bool = False, source_kernel_fallback: bool = False) -> str
```

*Source: translator/solidworks_translator/api.py*

## Import Surface

- translator backend: `from simplecadapi.translator.solidworks_translator import translate_product_package_to_solidworks_script`

## Description

Translate one validated `.scadpkg` closure into SolidWorks automation.
