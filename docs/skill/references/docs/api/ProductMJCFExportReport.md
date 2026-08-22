# ProductMJCFExportReport

## Class Definition

```python
class ProductMJCFExportReport(output_path: Path, mapping_path: Path, mesh_directory: Path, root_definition_id: str, mesh_count: int, body_count: int, joint_count: int, equality_count: int, closure_count: int, grounded_group_count: int, site_count: int, default_density_count: int, limitations: tuple[str, ...])
```

*Source: exporter/mjcf.py*

## Import Surface

- exporter namespace: `from simplecadapi import exporter` then `exporter.mjcf.ProductMJCFExportReport(...)`

## Description

Observed facts and compiler decisions from one MJCF export.
