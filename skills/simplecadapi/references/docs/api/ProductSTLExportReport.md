# ProductSTLExportReport

## Class Definition

```python
class ProductSTLExportReport(output_path: Path, root_definition_id: str, solid_count: int, definition_count: int, vertex_count: int, triangle_count: int, linear_deflection: float, angular_deflection_degrees: float, relative: bool, tessellation_backend: str = 'opencascade-brep-tessellation')
```

*Source: exporter/stl.py*

## Import Surface

- exporter namespace: `from simplecadapi import exporter` then `exporter.stl.ProductSTLExportReport(...)`

## Description

Evidence from direct BREP tessellation and binary STL export.
