# add_circle_rsketch

## API Definition

```python
def add_circle_rsketch(sketch: Sketch, entity_id: str, center: Union[SketchRef, str], radius: ScalarLike, *, construction: bool = False) -> Sketch
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import add_circle_rsketch`

## Description

Add a named circle entity and return an updated sketch document.
