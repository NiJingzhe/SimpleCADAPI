# assemble

## API Definition

```python
def assemble(func: Callable[_P, _R] | None = None, *, id: str | None = None, revision: str = '1.0.0', definitions: Sequence[Any] = (), cache: CachePolicy | Mapping[str, Any] | str | None = None, project_root: str | Path | None = None, tolerance_profile: str = 'simplecad-default') -> Callable[[Callable[_P, _R]], Callable[_P, AssemblyBuildResult]] | Callable[_P, AssemblyBuildResult]
```

*Source: build/assembly_builder.py*

## Import Surface

- top-level: `from simplecadapi import assemble`

## Description

Decorate one assembly builder with explicit external definitions.
