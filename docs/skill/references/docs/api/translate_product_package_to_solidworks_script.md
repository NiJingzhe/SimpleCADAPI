# translate_product_package_to_solidworks_script

## API Definition

```python
def translate_product_package_to_solidworks_script(data, document_name: str = 'SimpleCADProduct', *, output_path: Optional[str] = None, visible: bool = False, solidworks_version: str = '2025') -> str
```

*Source: translator/solidworks_translator/api.py*

## Import Surface

- translator backend: `from simplecadapi.translator.solidworks_translator import translate_product_package_to_solidworks_script`

## Description

Translate one validated `.scadpkg` closure into SolidWorks automation.
