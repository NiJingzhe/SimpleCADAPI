# load_product_package

## API Definition

```python
def load_product_package(data: bytes | bytearray | memoryview | str | Path, *, limits: ArtifactLimits = DEFAULT_ARTIFACT_LIMITS) -> Definition
```

*Source: product_packages.py*

## Import Surface

- top-level: `from simplecadapi import load_product_package`

## Description

Load the durable root definition from one self-contained package.
