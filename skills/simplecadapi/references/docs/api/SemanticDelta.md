# SemanticDelta

## Class Definition

```python
class SemanticDelta(created: Tuple[SemanticRef, ...] = (), modified: Tuple[SemanticRef, ...] = (), deleted: Tuple[SemanticRef, ...] = (), metadata: Dict[str, Any] = field(default_factory=dict))
```

*Source: topology.py*

## Import Surface

- top-level: `from simplecadapi import SemanticDelta`

## Description

Semantic entity change set attached to a single recorded operation.
