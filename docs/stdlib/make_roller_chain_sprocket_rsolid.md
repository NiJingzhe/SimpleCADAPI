# make_roller_chain_sprocket_rsolid

## API Definition

```python
def make_roller_chain_sprocket_rsolid(n_teeth: int, chain_pitch: float, roller_diameter: float, sprocket_thickness: float, *, bore_radius: float = 0.0, roller_clearance: float = 0.15) -> Solid
```

*Source: std/chain.py*

## Import Surface

- standard library: `import simplecadapi as scad` then `scad.std.chain.make_roller_chain_sprocket_rsolid(...)`; direct submodule import: `from simplecadapi.std.chain import make_roller_chain_sprocket_rsolid`

## Description

Create a roller-chain sprocket from tooth count, chain pitch, roller diameter, and tooth-plate thickness. The pitch radius follows the regular pitch polygon. Circular roller seats are cut at every pitch point and opened through the engineering outside-diameter envelope.

The result preserves assembly-level engagement dimensions. Manufacturing release still requires the selected chain standard's permitted tooth-form range, tooth width, hub, material, heat treatment, runout, and supplier checks.
