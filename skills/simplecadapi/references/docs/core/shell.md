# Shell

## Overview

`Shell` is the public wrapper for one connected set of faces. A shell may be open, such as a lofted side wall, or closed, such as a sewn surface boundary. It wraps an OCP `TopoDS_Shell` and participates in SimpleCAD tags, metadata, QL selection, transforms, and graph replay.

## Topology and Properties

- `get_faces(index=None)` returns all faces or one indexed face.
- `get_edges(index=None)` returns unique edges across the shell faces.
- `get_area()` returns total face area.
- `is_closed()` reports whether the shell has no free boundary.
- `free_boundaries_rwirelist(shell)` returns the open boundary loops.
- `ql.shells()` selects shells from a shell or compatible topology scope.

## Construction

Use the public surface operations rather than constructing `Shell` from an OCP object directly:

- [`make_loft_rshell`](../api/make_loft_rshell.md) lofts through wire or vertex sections.
- [`sew_faces_rshell`](../api/sew_faces_rshell.md) sews connected faces into one shell.
- [`fill_holes_rshell`](../api/fill_holes_rshell.md) fills every free boundary loop.

```python
import simplecadapi as scad

lower = scad.make_circle_rwire((0, 0, 0), 2.0)
upper = scad.make_circle_rwire((0, 0, 5), 1.0)

open_shell = scad.make_loft_rshell([lower, upper])
assert not open_shell.is_closed()
assert len(scad.free_boundaries_rwirelist(open_shell)) == 2

closed_shell = scad.fill_holes_rshell(open_shell)
assert closed_shell.is_closed()
```

Use [`shell_rsolid`](../api/shell_rsolid.md) for the different operation that hollows a `Solid` by offsetting walls and removing selected faces.
