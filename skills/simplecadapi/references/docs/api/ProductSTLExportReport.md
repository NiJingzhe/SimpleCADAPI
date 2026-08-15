# ProductSTLExportReport

## Class Definition

```python
class ProductSTLExportReport(output_path: Path, root_definition_id: str, solid_count: int, definition_count: int, quadrilateral_count: int, residual_triangle_count: int, stl_triangle_count: int, quad_fraction: float, mesh_size: float, remesh_backend: str = 'gmsh-quad-dominant')
```

*Source: exporter/stl.py*

## Import Surface

- exporter namespace: `from simplecadapi import exporter` then `exporter.stl.ProductSTLExportReport(...)`

## Description

Evidence from quad-dominant product-surface remeshing and STL export.
