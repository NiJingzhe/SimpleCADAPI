# track_section_contours_rdescriptor

```python
track_section_contours_rdescriptor(
    *,
    sections: Sequence[Mapping[str, Any]],
    maximum_match_cost: float = 1.5,
    topology_area_tolerance: float = 0.2,
) -> dict[str, Any]
```

Inspection namespace. Matches closed contours across ordered section stations
and reports continuation, birth, death, split, and merge events. A false
`single_loft_safe` value means a non-initial topology event requires separate
local features or surface regions rather than one global loft.
