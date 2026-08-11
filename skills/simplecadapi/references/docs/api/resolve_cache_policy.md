# resolve_cache_policy

## API Definition

```python
def resolve_cache_policy(explicit: CachePolicy | Mapping[str, Any] | None = None, *, project_root: str | Path = '.', environ: Mapping[str, str] | None = None) -> CachePolicy
```

*Source: cache/policy.py*

## Import Surface

- top-level: `from simplecadapi import resolve_cache_policy`

## Description

Resolve fields using explicit > environment > project > defaults.
