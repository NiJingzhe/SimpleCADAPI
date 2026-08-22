# CachePolicy

## Class Definition

```python
class CachePolicy(mode: CacheMode = CacheMode.READ_WRITE, root: Path = Path('.simplecad/cache'), verify_reads: bool = True, quarantine_corrupt: bool = True, lock_timeout_seconds: float = 30.0, stale_lock_seconds: float = 300.0)
```

*Source: cache/policy.py*

## Import Surface

- top-level: `from simplecadapi import CachePolicy`

## Description

Resolved persistent cache location, integrity, and locking policy.
