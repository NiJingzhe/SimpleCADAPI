# Example 22: City Block Diorama

## 1. Top-Down Intent

This example reconstructs the architectural/static content of the reference
image as a small city-block diorama. It is a visual product assembly, not a
mechanical assembly. Vehicles are intentionally excluded.

The scene is designed to read from an isometric/top-down view while remaining
useful as a CAD model: every major architectural, interior, and street element
is a separate colored `Part` or nested `Assembly`. Building exteriors are fully
closed; a CAD user can inspect rooms by selecting or hiding facade components
in the assembly tree rather than relying on a permanently removed wall.

### Scope

- Include the raised layered city platform, four-sided street edge, sidewalks,
  crosswalks, street lamps, trees, planters, benches, bollards, and fountain.
- Include ten static buildings corresponding to the labeled reference blocks:
  glass tower, brick apartments, two noodle bars, corner retail, office blocks,
  a game cafe, a mid-rise cafe, and smaller mixed-use buildings.
- Include visible interiors: floor slabs, stairs, partitions, kitchens,
  counters, shelves, desks, beds, sofas, dining tables, plants, and rooftop
  equipment where the building type supports them. Interiors remain inside the
  closed building shells.
- Omit vehicles, people, moving mechanisms, and hidden structural details that
  cannot be seen at the intended diorama scale.

## 2. Coordinate System And Scene Grammar

All dimensions are millimeters. The city uses a single right-handed coordinate
system:

- `X` runs east-west across the block.
- `Y` runs south-north across the block.
- `Z` is vertical; the terrain top is near `Z=0` and building placement is at
  `Z=6.8`, exactly on the sidewalk top datum.
- The platform is `260 x 220`; its raised base, trim bands, and top slab create
  the illustrated boxed-in shelf appearance.
- Main Street runs east-west through `Y=100..124`.
- East Avenue runs north-south through `X=118..142`.
- The intersection becomes a small paved civic plaza with a circular fountain.

The composition is deliberately asymmetric. The northwest and northeast
quadrants carry the tall silhouettes; the south quadrants carry lower retail
and office buildings so interiors remain visible in an isometric view.

## 3. Building Inventory

| Label | Type | Approx. footprint | Height intent | Interior intent |
| --- | --- | --- | --- | --- |
| A | glass tower | 44 x 50 | 6 floors | open-plan desks, elevator core, stairs |
| B | brick residential | 44 x 46 | 5 floors | corridor, bedrooms, living rooms, balconies |
| C | noodle bar | 42 x 24 | 1 floor | counter, kitchen, dining tables, stools |
| D | noodle bar | 44 x 24 | 1 floor | counter, kitchen, dining tables, stools |
| E | corner retail | 44 x 42 | 2 floors | shop floor, shelves, checkout, upstairs office |
| F | office block | 46 x 42 | 3 floors | desks, meeting rooms, server/equipment room |
| G | game cafe | 38 x 24 | 1 floor | counter, game tables, lounge seating, sign |
| H | mid-rise cafe | 40 x 38 | 3 floors | cafe ground floor, apartments above, balconies |
| I | blue mixed-use | 34 x 36 | 2 floors | studio/workshop, showroom, rooftop plant |
| J | small corner shop | 38 x 32 | 2 floors | retail ground floor, compact upper room |

The building factories use local coordinates and are placed only by
`assembly.py`. This keeps building geometry reusable and makes the city layout
the single owner of global positions.

## 4. Visual Language

The palette separates structural, architectural, interior, and public-realm
objects without relying on a texture pipeline:

- warm brick/red-brown for residential and noodle-bar masonry;
- cyan/blue glass with dark steel mullions for the tower and blue mixed-use
  building;
- cream concrete and tan plaster for lower buildings;
- dark charcoal roads and roofs, pale warm sidewalks, and green landscaping;
- orange wood, red upholstery, yellow signage, and blue water as high-contrast
  interior accents.

Materials are assigned to `Part` objects, not manually painted topology. Semantic
tags on solids record roles such as `role.road`, `role.interior`,
`role.facade`, and `role.landscape` for later QL inspection.

## 5. File And Dependency Plan

```text
22_city_block_diorama/
├── DESIGN.md                 # this top-down plan and acceptance contract
├── dimensions.py             # coordinates, specs, and dimension validation
├── materials.py              # palette and SimpleCAD Material values
├── common.py                 # tagged parts, placements, QL grounding helpers
├── props.py                  # trees, lamps, benches, planters, fountain
├── terrain.py                # platform, roads, sidewalks, plaza, markings
├── buildings.py              # ten building factories and visible interiors
├── assembly.py               # one global city assembly and placement map
└── main.py                   # GraphSession, replay, STEP/STL/FCStd/render output
```

Dependency direction is one-way:

```text
dimensions/materials -> common -> props/terrain/buildings -> assembly -> main
```

`assembly.py` is intentionally a composition file. It does not contain
building geometry or repeated street-prop geometry.

## 6. Bottom-Up Build Order

1. Validate scene dimensions, building envelopes, and material palette.
2. Build and QL-ground individual primitive parts through `common.py`.
3. Build reusable street props and verify their solid/face counts.
4. Build the terrain assembly: layered base, road slabs, sidewalks, plaza,
   markings, and curb details.
5. Build each building family from its floor slabs and shell pieces outward,
   adding enclosed interior partitions and connected furniture before facade
   signage.
6. Place all buildings and repeated props in the city assembly.
7. Project the assembly to a compound and print concise scene statistics.
8. Export canonical model/session JSON plus STEP, STL, FCStd, and an isometric
   screenshot. Import and strict-replay the model JSON as the final gate.

## 7. Acceptance Checks

- `example 22` runs from the repository root with `uv run python .../main.py`.
- The model has ten named building subassemblies and no vehicle components.
- The preview contains separate colored solids for architecture, interiors,
  roads, landscaping, and street furniture.
- Every building has at least one interior part; tall buildings have multiple
  floor slabs and visible room/furniture elements.
- `export_model_json` succeeds and `replay_model_json(strict=True)` returns
  outputs without an exception.
- STEP, STL, FCStd, and screenshot outputs are written under
  `examples/out/city_block_diorama/` when the local FreeCAD executable is
  available.
- The script prints only compact QL-backed grounding facts rather than dumping
  full solids or model objects.
