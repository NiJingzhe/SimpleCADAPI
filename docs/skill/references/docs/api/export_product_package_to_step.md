# export_product_package_to_step

## API Definition

```python
def export_product_package_to_step(data: ProductPackageInput, output_path: str | Path) -> ProductSTEPExportReport
```

*Source: exporter/step.py*

## Import Surface

- exporter namespace: `from simplecadapi import exporter` then `exporter.step.export_product_package_to_step(...)`

## Description

Export a validated `.scadpkg` closure as XCAF-backed AP242 STEP.
