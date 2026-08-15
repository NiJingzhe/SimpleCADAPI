# translate_product_package_to_fcstd

## API Definition

```python
def translate_product_package_to_fcstd(data: ProductPackageInput, output_path: str, *, document_name: str = 'SimpleCADProduct', freecad_cmd: Optional[str] = None) -> str
```

*Source: translator/freecad_translator/api.py*

## Import Surface

- translator backend: `from simplecadapi.translator.freecad_translator import translate_product_package_to_fcstd`

## Description

Translate one validated `.scadpkg` closure into an editable `.FCStd`.
