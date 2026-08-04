# add_line_rsketch

## API Definition

```python
def add_line_rsketch(sketch: Sketch, entity_id: str, start: Union[SketchRef, str], end: Union[SketchRef, str], *, construction: bool = False) -> Sketch
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import add_line_rsketch`

## Description

Add a named line entity and return an updated sketch document.
