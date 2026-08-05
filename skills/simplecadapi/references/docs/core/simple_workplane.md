# SimpleWorkplane

`SimpleWorkplane` is a context manager for modeling in a temporary local coordinate frame.

## Public constructor

```python
SimpleWorkplane(
    origin=(0, 0, 0),
    normal=(0, 0, 1),
    x_dir=(1, 0, 0),
)
```

## Main capabilities

- Push a local coordinate frame for nested modeling operations.
- Automatically restore the previous frame when the context exits.
- Keep the public API shape-first: functions still return `Vertex`, `Edge`, `Wire`, `Face`, and `Solid` objects.
- Resolve point parameters relative to the active frame and vector parameters without applying frame translation.
- Compose nested workplanes as a chain: each child `origin`, `normal`, and `x_dir` is expressed in its parent frame.
- Record the fully composed frame on each `GraphSession` node so model JSON replay reproduces the same geometry outside the original context managers.
- Keep existing shape inputs in global coordinates. Entering a workplane does not move a shape; only the operation's point and vector parameters use the active frame.
- Bind declarative sketches to their creation frame, so they can be promoted after the workplane exits without changing position.

## Example

```python
import simplecadapi as scad

with scad.SimpleWorkplane(
    origin=(10, 20, 30),
    normal=(0, 1, 0),
    x_dir=(1, 0, 0),
):
    with scad.SimpleWorkplane(
        origin=(2, 3, 4),
        normal=(1, 0, 0),
        x_dir=(0, 1, 0),
    ):
        box = scad.make_box_rsolid(2, 4, 6)
        moved = scad.translate_shape(box, (0, 0, 2))

print(moved.get_volume())
```
