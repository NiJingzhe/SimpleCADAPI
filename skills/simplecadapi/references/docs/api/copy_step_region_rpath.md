# copy_step_region_rpath

## API Definition

```python
def copy_step_region_rpath(path: str | Path, output_path: str | Path, *, face_ids: Sequence[str] | None = None) -> Path
```

*Source: inspect/brep/snapshots.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.copy_step_region_rpath(...)`; unavailable inside GraphSession

## Description

Copy one STEP solid or one connected face Shell into a BREP snapshot.

``face_ids`` copies the selected target faces with their existing carriers,
trims, pcurves, shared edges/vertices, orientations, and tolerances. The
selection must form one connected valid Shell. Omitting ``face_ids`` copies
the complete single Solid. The operation runs outside GraphSession and writes
atomically to ``.scadbrep``.
