# compare_sections_batch_rdescriptor

## API Definition

```python
def compare_sections_batch_rdescriptor(target: ModelInput, current: ModelInput, *, sections: Sequence[Mapping[str, Any]], tolerance: float = 1e-07, samples_per_edge: int = 32) -> dict[str, Any]
```

*Source: inspect/brep/diagnostics.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.compare_sections_batch_rdescriptor(...)`; unavailable inside GraphSession

## Description

Compare an ordered batch of sections after loading each model once.
