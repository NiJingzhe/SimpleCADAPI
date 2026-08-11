# read_product_package

## API Definition

```python
def read_product_package(data: bytes | bytearray | memoryview | str | Path, *, limits: ArtifactLimits = DEFAULT_ARTIFACT_LIMITS) -> ProductPackage
```

*Source: product_packages.py*

## Import Surface

- top-level: `from simplecadapi import read_product_package`

## Description

Read and validate one self-contained product package.
