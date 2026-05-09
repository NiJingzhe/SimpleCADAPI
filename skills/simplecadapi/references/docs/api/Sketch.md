# Sketch

## Class Definition

```python
class Sketch(curves: Iterable[Edge | Wire] | None = None)
```

*Source: sketch.py*

## Description

A lightweight first-class sketch container.

Phase 1 scope:
- hold 2D-ish curve inputs represented by Edge/Wire
- expose them as stable children
- optionally provide closed wires as profile candidates
