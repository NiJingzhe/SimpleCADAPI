# export_product_package_to_stl

## API Definition

```python
def export_product_package_to_stl(data: ProductPackageInput, output_path: str | Path, *, mesh_size: float = 1.0, recombination_angle_degrees: float = 45.0) -> ProductSTLExportReport
```

*Source: exporter/stl.py*

## Import Surface

- exporter namespace: `from simplecadapi import exporter` then `exporter.stl.export_product_package_to_stl(...)`

## Description

Export one validated `.scadpkg` as a quad-dominant remeshed STL.

Gmsh recombines each CAD surface into quadrilaterals before its STL writer
splits every quad into two triangles, as required by the STL file format.
