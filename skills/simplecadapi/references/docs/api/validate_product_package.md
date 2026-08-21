# validate_product_package

## API Definition

```python
def validate_product_package(package: ProductPackage, *, limits: ArtifactLimits = DEFAULT_ARTIFACT_LIMITS) -> None
```

*Source: product_packages.py*

## Import Surface

- top-level: `from simplecadapi import validate_product_package`

## Description

Validate the manifest, every object archive, and the complete definition DAG.
