# CacheRecord

## Class Definition

```python
class CacheRecord(namespace: str, key: str, object_hash: str, byte_length: int, media_type: str, metadata: Mapping[str, Any] = field(default_factory=dict), schema_version: str = field(default=_RECORD_SCHEMA_VERSION, init=False))
```

*Source: cache/records.py*

## Import Surface

- top-level: `from simplecadapi import CacheRecord`

## Description

Canonical mapping from one namespace/key to a content-addressed object.
