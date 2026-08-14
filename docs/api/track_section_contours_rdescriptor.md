# track_section_contours_rdescriptor

## API Definition

```python
def track_section_contours_rdescriptor(*, sections: Sequence[Mapping[str, Any]], maximum_match_cost: float = 1.5, topology_area_tolerance: float = 0.2) -> dict[str, Any]
```

*Source: inspect/brep/section_tracking.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.track_section_contours_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Track contours across ordered stations without forcing one global loft.

The output distinguishes continuation, birth, death, split and merge
events. Its summary reports whether topology changes make one global loft
unsafe. It is hypothesis evidence and must not be copied into the raw BREP
summary.
