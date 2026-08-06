# Shell

## Overview

`Shell` is the public wrapper for one connected set of faces. A shell may be open, such as a lofted side wall, or closed, such as a sewn surface boundary. It wraps an OCP `TopoDS_Shell` and participates in SimpleCAD tags, metadata, QL selection, transforms, and graph replay.

## Topology and Properties

- `get_faces(index=None)` returns all faces or one indexed face.
- `get_wires(index=None)` returns the Shell's free boundary wires.
- `get_edges(index=None)` returns unique edges across the shell faces.
- `get_area()` returns total face area.
- `is_closed()` reports whether the shell has no free boundary.
- `free_boundaries_rwirelist(shell)` returns the open boundary loops.
- `ql.shells()` selects shells from a shell or compatible topology scope.

## Construction

Use the public surface operations rather than constructing `Shell` from an OCP object directly:

- [`loft_rshell`](../api/loft_rshell.md) lofts through Wire sections with optional Vertex endpoints and can name the start/end boundary Wires and side Faces.
- [`sew_faces_rshell`](../api/sew_faces_rshell.md) sews connected faces into one shell.
- [`fill_holes_rshell`](../api/fill_holes_rshell.md) fills every free boundary loop.

```python
import simplecadapi as scad

lower = scad.make_circle_rwire((0, 0, 0), 2.0)
upper = scad.make_circle_rwire((0, 0, 5), 1.0)

open_shell = scad.loft_rshell(
    [lower, upper],
    start_wire_tag="anchor.inlet",
    end_wire_tag="anchor.outlet",
    side_faces_tag="group.skin",
)
assert not open_shell.is_closed()
assert len(open_shell.get_wires()) == 2
assert len(scad.ql.wires().where(scad.ql.tag("anchor.inlet")).resolve(open_shell)) == 1

closed_shell = scad.fill_holes_rshell(open_shell)
assert closed_shell.is_closed()
```

Use [`shell_rsolid`](../api/shell_rsolid.md) for the different operation that hollows a `Solid` by offsetting walls and removing selected faces.
