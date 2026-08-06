# loft_rshell

## API Definition

```python
def loft_rshell(sections: Sequence[Union[Wire, Vertex]], *, ruled: bool = False, tag_prefix: Optional[str] = None, result_tag: Optional[str] = None, start_wire_tag: Optional[str] = None, end_wire_tag: Optional[str] = None, side_faces_tag: Optional[str] = None) -> Shell
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import loft_rshell`

## Description

Create an open loft Shell with endpoint-Wire and side-Face naming.
