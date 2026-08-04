# apply_tag_rselection

## API Definition

```python
def apply_tag_rselection(scope: AnyShape, targets: Union[ShapeSelector, Sequence[AnyShape]], tag: str, topology_propagation: str | TopologyPropagation = TopologyPropagation.LOCAL, lineage_policy: str | LineagePolicy = LineagePolicy.CONTINUATION_FRAGMENT) -> AnyShape
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import apply_tag_rselection`

## Description

Return a semantic shape view with a canonical tag assignment.
