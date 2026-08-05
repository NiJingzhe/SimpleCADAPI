# make_loft_rshell

## API Definition

```python
def make_loft_rshell(sections: Sequence[Union[Wire, Vertex]], *, ruled: bool = False, tag_prefix: Optional[str] = None) -> Shell
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_loft_rshell`

## Description

Create an open Shell loft through wire or vertex sections.
