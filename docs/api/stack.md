# stack

## API Definition

```python
def stack(assembly: Assembly, parts: Sequence[Union[str, PartHandle]], axis: str = 'z', gap: float = 0.0, align: Literal['center', 'start', 'end'] = 'center', justify: Literal['start', 'center', 'end', 'space-between'] = 'start', bounds: Optional[Tuple[PointAnchor, PointAnchor]] = None) -> Assembly
```

*Source: constraints.py*

## Description

Declaratively stack multiple parts along the specified axis.

Semantics:
- sequential stacking: part i is placed after part i-1 with the given gap
- cross-axis alignment: the other two axes are aligned according to `align`
- main-axis distribution: `justify` controls how the whole stack is placed
within the bounds

BBox-first note:
- This function uses axis-aligned bounding-box (AABB) anchors such as
`bbox.top` and `bbox.bottom` to approximate Flexbox-like box semantics.
- For parts with large rotations, the AABB changes with pose, so the layout
result changes as well. This is expected in the current MVP stage.

Note:
- This is container-level sugar that compiles into a set of `offset(...)`
constraints internally.
