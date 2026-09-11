# SolidWorksTranslator

## Class Definition

```python
class SolidWorksTranslator(document_name: str = 'SimpleCADProduct', *, output_path: str | None = None, visible: bool = False, solidworks_version: str = '2025')
```

*Source: translator/solidworks_translator/translator.py*

## Import Surface

- translator backend: `from simplecadapi.translator.solidworks_translator import SolidWorksTranslator`

## Description

Translate one validated `.scadpkg` closure into SolidWorks automation.

Supported SolidWorks versions are `"2023"` and `"2025"`; `"2025"` remains the
default. The version and output path also apply to the model JSON/payload
entrypoints and to native document reopening. See
[translate_product_package_to_solidworks_script](translate_product_package_to_solidworks_script.md)
for session behavior and an executable-script example.
