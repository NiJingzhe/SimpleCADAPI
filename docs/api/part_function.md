# part

## API Definition

```python
def part(func: Callable[_P, _R] | None = None, *, id: str | None = None, revision: str = '1.0.0', inputs: Sequence[FileInput] = (), cache: CachePolicy | Mapping[str, Any] | str | None = None, project_root: str | Path | None = None, tolerance_profile: str = 'simplecad-default') -> Callable[[Callable[_P, _R]], Callable[_P, PartBuildResult]] | Callable[_P, PartBuildResult]
```

*Source: build/part_builder.py*

## Import Surface

- top-level: `from simplecadapi import part`

## Description

Decorate one synchronous builder as a cached single-solid product part.
