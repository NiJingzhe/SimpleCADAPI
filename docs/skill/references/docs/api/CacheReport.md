# CacheReport

## Class Definition

```python
class CacheReport(mode: str, build_key: str, part_lookups: int, part_hits: int, part_misses: int, corrupt_entries: int = 0, miss_reason: str | None = None, bytes_read: int = 0, bytes_written: int = 0)
```

*Source: build/results.py*

## Import Surface

- top-level: `from simplecadapi import CacheReport`

## Description

Per-build whole-part cache outcome.
