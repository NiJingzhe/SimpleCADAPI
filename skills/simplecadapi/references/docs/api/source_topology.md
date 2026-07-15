# source_topology

## API Definition

```python
def source_topology(topo_id: str) -> SerializablePredicate
```

*Source: ql.py*

## Import Surface

- submodule: `from simplecadapi import ql`

## Description

Match a local projected `TagBinding` by the exact source topology identity stored
in its kernel-history evidence. This predicate queries source-preserving evidence;
it does not infer ancestry from geometry.
