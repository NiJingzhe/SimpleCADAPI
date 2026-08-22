# ProductOBJExportReport

## Class Definition

```python
class ProductOBJExportReport(output_path: Path, root_definition_id: str, solid_count: int, definition_count: int, vertex_count: int, triangle_count: int, linear_deflection: float, angular_deflection_degrees: float, relative: bool, tessellation_backend: str = 'opencascade-brep-tessellation')
```

*Source: exporter/obj.py*

## Import Surface

- exporter namespace: `from simplecadapi import exporter` then `exporter.obj.ProductOBJExportReport(...)`

## Description

Evidence from direct BREP tessellation and triangle OBJ export.
