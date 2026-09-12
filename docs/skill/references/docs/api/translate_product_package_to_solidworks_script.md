# translate_product_package_to_solidworks_script

## API Definition

```python
def translate_product_package_to_solidworks_script(data: ProductPackageInput, document_name: str = 'SimpleCADProduct', *, output_path: str | None = None, visible: bool = False, solidworks_version: str = '2025') -> str
```

*Source: translator/solidworks_translator/api.py*

## Import Surface

- translator backend: `from simplecadapi.translator.solidworks_translator import translate_product_package_to_solidworks_script`

## Description

Translate one validated `.scadpkg` closure into SolidWorks automation.

`solidworks_version` accepts `"2023"` or `"2025"`; the default is `"2025"`.
The generated script starts an isolated instance of the requested release,
checks its actual revision and binds its COM type library. `visible=True`
shows that instance during translation; the script closes its own instance
when it finishes. An existing interactive session is not reused.

```python
from pathlib import Path
from simplecadapi.translator.solidworks_translator import (
    translate_product_package_to_solidworks_script,
)

script = translate_product_package_to_solidworks_script(
    data="product.scadpkg",
    output_path="out/model.step",
    solidworks_version="2023",
    visible=True,
)
Path("translate_sw.py").write_text(script, encoding="utf-8")
```

Run `translate_sw.py` with a Windows Python interpreter that has `pywin32`
and the requested SolidWorks release installed. The script saves a native
`.sldprt` alongside the STEP output; assemblies also produce `.sldasm` and
component documents. Creating the script does not start SolidWorks.

Translation retains native operation failure checks and geometric-signature
selection. Source-versus-SolidWorks volume or bounding-box acceptance belongs
in independent diagnostic scripts, not in this translation path.
