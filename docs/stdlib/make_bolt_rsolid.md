# make_bolt_rsolid

## API Definition

```python
def make_bolt_rsolid(
    diameter: float,
    length: float,
    head_style: str = "hex",
    thread_style: str = "auto",
    thread_detail: str = "modeled",
    thread_form: str = "v",
    thread_pitch: Optional[float] = None,
    thread_depth: Optional[float] = None,
    thread_length: Optional[float] = None,
    head_width: Optional[float] = None,
    head_height: Optional[float] = None,
    drive_style: str = "none",
    drive_size: Optional[float] = None,
    drive_depth: Optional[float] = None,
    underhead_fillet_radius: Optional[float] = None,
) -> Solid
```

*Source: std/fastener.py*

## Import Surface

- standard library: `import simplecadapi as scad` then `scad.std.fastener.make_bolt_rsolid(...)`; direct submodule import: `from simplecadapi.std.fastener import make_bolt_rsolid`

## Description

Create a parameterized bolt along `+Z`, with the head underside on `Z=0`. Head styles are `hex`, `square`, `cylindrical`, `button`, and `countersunk`. Drive styles are `none`, `slot`, `cross`, and `hex_socket`.

Thread styles are `auto`, `full`, `partial`, and `none`. `auto` selects full thread for `length <= 3 * diameter`; otherwise it uses the ISO-style piecewise partial-thread length. The default `thread_detail="modeled"` creates a visible replayable helical `v` or `trapezoidal` thread. Set `thread_detail="cosmetic"` explicitly for a smooth shank with thread intent only in metadata. For partial threads, `thread_length` is measured back from the tip at `Z=length`.

For metric coarse-series diameters, the factory derives the default pitch from the standard series and records `d2 = d - 0.6495P` and `d1 = d - 1.0825P` in metadata. Hex-head defaults use catalog-like `S` and `k` values where available. The default underhead fillet is `0.06d`; `underhead_fillet_radius` can override it. The metadata also reports a minimum recommended mating-hole chamfer equal to the fillet radius.

Modeled threads may rotate the helical seam to an equivalent kernel-stable phase. The selected phase is recorded as `thread_phase_degrees` in `std.fastener.bolt` metadata and does not change thread dimensions or handedness.

Default dimensions are useful parametric proportions, not a claim of compliance with a specific ISO, DIN, ASME, or supplier catalog. Set catalog dimensions explicitly for released hardware.
