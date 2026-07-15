# output_role

## API Definition

```python
def output_role(role_name: str) -> SerializablePredicate
```

*Source: ql.py*

## Import Surface

- submodule: `from simplecadapi import ql`

## Description

Return a serializable predicate matching a kernel-proven operation output role
in `metadata["track"]`. Role matching never falls back to face order, geometry,
or flat tags. Use it with a typed selector, for example:

```python
end = ql.faces().where(ql.output_role(role_name="extrusion.end")).exactly(1)
```
