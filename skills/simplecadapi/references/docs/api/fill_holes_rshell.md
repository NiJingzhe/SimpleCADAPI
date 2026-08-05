# fill_holes_rshell

## API Definition

```python
def fill_holes_rshell(shell: Shell, hole_indices: Optional[Sequence[int]] = None, *, tolerance: float = 1e-06, settings: Optional[SurfaceFillingSettings] = None, tag_prefix: Optional[str] = None) -> Shell
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import fill_holes_rshell`

## Description

Fill selected closed free boundaries and return a sewn Shell.
