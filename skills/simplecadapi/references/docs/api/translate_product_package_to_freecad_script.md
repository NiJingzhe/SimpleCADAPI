# translate_product_package_to_freecad_script

## API Definition

```python
def translate_product_package_to_freecad_script(data: ProductPackageInput, document_name: str = 'SimpleCADProduct') -> str
```

*Source: translator/freecad_translator/api.py*

## Import Surface

- translator backend: `from simplecadapi.translator.freecad_translator import translate_product_package_to_freecad_script`

## Description

Translate one validated `.scadpkg` closure into a FreeCAD script.
