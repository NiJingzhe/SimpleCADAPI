# SimpleWorkplane

`SimpleWorkplane` is a context manager for modeling in a temporary local coordinate frame.

## Public constructor

```python
SimpleWorkplane(origin=(0, 0, 0), normal=(0, 0, 1))
```

## Main capabilities

- Push a local coordinate frame for nested modeling operations.
- Automatically restore the previous frame when the context exits.
- Keep the public API shape-first: functions still return `Vertex`, `Edge`, `Wire`, `Face`, and `Solid` objects.

## Example

```python
import simplecadapi as scad

with scad.SimpleWorkplane((0, 0, 10), normal=(0, 0, 1)):
    box = scad.make_box_rsolid(2, 2, 2)

print(box.get_volume())
```
