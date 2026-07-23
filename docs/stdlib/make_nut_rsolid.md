# make_nut_rsolid

## API Definition

```python
def make_nut_rsolid(
    diameter: float,
    width: float,
    height: float,
    nut_style: str = "hex",
    hole_style: str = "through",
    thread_detail: str = "modeled",
    thread_form: str = "v",
    thread_pitch: Optional[float] = None,
    thread_depth: Optional[float] = None,
    hole_depth: Optional[float] = None,
    knurl_count: int = 24,
) -> Solid
```

*Source: std/fastener.py*

## Import Surface

- standard library: `import simplecadapi as scad` then `scad.std.fastener.make_nut_rsolid(...)`; direct submodule import: `from simplecadapi.std.fastener import make_nut_rsolid`

## Description

Create a parameterized nut along `+Z`, with its bottom face on `Z=0`. Nut styles are `hex`, `square`, `round`, and `knurled`. Hole styles are `through` and `blind`; a blind hole opens from the top face and uses `hole_depth` as its axial depth.

The default `thread_detail="modeled"` creates replayable internal `v` or `trapezoidal` helical teeth. Set `thread_detail="cosmetic"` explicitly for a smooth major-diameter hole with thread intent only in metadata. For metric coarse-series diameters, the factory derives the default pitch and records `d2 = d - 0.6495P` and `d1 = d - 1.0825P` in metadata. `knurl_count` controls the lobe count of the printable knurled approximation.

Modeled threads may rotate the helical seam to an equivalent kernel-stable phase. The selected phase is recorded as `thread_phase_degrees` in `std.fastener.nut` metadata and does not change thread dimensions or handedness.

Default thread proportions are useful for parametric models, not a substitute for catalog tolerances, thread class, lead-in, prevailing-torque features, or manufacturing checks.
