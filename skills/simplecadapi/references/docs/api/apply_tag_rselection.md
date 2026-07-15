# apply_tag_rselection

## API Definition

```python
def apply_tag_rselection(
    scope: AnyShape,
    targets: Union[ShapeSelector, Sequence[AnyShape]],
    tag: str,
    topology_propagation: str | TopologyPropagation = TopologyPropagation.LOCAL,
    lineage_policy: str | LineagePolicy = LineagePolicy.CONTINUATION_FRAGMENT,
) -> AnyShape
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import apply_tag_rselection`

## Description

Return an independent semantic view over the same geometry with one canonical
`TagBinding` attached to the selected entities. `targets` may be a serializable
QL `ShapeSelector` or a non-empty sequence of topology objects belonging to
`scope`.

Topology propagation defaults to `local`. Set `topology_propagation="downward"`
only when descendants should inherit the binding. Lineage defaults to proven
continuation and fragment derivations; it never makes lineage part of the
`effective` scope.

Inside `GraphSession`, the operation records the complete binding, target intent,
and selected-reference evidence. Replay re-resolves the target and checks that
the evidence has not drifted. The semantic node does not replace geometry-owned
topology references.
