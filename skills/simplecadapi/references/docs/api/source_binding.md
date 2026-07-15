# source_binding

## API Definition

```python
def source_binding(binding_id: str) -> SerializablePredicate
```

*Source: ql.py*

## Import Surface

- submodule: `from simplecadapi import ql`

## Description

Match a local projected `TagBinding` whose topology-change evidence preserves the
exact source `binding_id`. Objects without canonical local binding evidence raise
an unsupported-query capability error instead of consulting flat tags.
