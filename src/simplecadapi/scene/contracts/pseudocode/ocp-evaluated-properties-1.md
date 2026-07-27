# OCP Evaluated Properties Profile 1 Pseudocode

This normative Phase A target defines the evaluated sidecar that the Phase B
Scene compiler must produce. The repository does not yet contain that compiler.
The named OCP calls exist in cadquery-ocp 7.9.3.1; SDK-derived selector and frame
algorithms name their concrete Python symbols.
The existing serializer resolver accepts a score tie and the Product edge-frame
helper falls back to +X for missing endpoints. Those helpers are not the Scene
compiler: this target instead requires unique matching and a null edge frame.

## Preparation and accepted topology

```text
First build solid/face/edge/vertex incidence from the unmodified OCP topology.
Accept one manifold solid or a compound of disjoint manifold solids. Reject a
compsolid, shared face, shell, free boundary, standalone lower-dimensional root,
or any face that does not have exactly one solid owner.

Required cardinalities:
  solid: zero parents and at least one face child
  face: exactly one solid parent and at least one edge child
  edge: at least one face parent and one or two vertex children
  vertex: at least one edge parent and zero children
Every relation is reciprocal. Deduplicate and unsigned-UTF-8-sort adjacency.

bake_location(shape, force_forward):
  oriented = shape.Oriented(TopAbs_FORWARD) if force_forward else shape
  location = oriented.Location()
  unlocated = oriented.Located(TopLoc_Location(), False)
  builder = BRepBuilderAPI_Transform(
      unlocated, location.Transformation(), True, False)
  builder.Build()
  fail unless builder.IsDone()
  return builder.Shape()

Evaluate every entity from its prepared copy. Faces retain TopAbs orientation.
Edges are forced FORWARD before location baking. Coedge orientation is not saved.
```

## Analytic classification

```text
curve = BRepAdaptor_Curve(prepared_forward_edge)
curve_symbol = curve.GetType()

GeomAbs_Line         -> line,          curve.Line()
GeomAbs_Circle       -> circle,        curve.Circle()
GeomAbs_Ellipse      -> ellipse,       curve.Ellipse()
GeomAbs_BSplineCurve -> bspline_curve, curve.BSpline()
GeomAbs_Hyperbola    -> other_curve("GeomAbs_Hyperbola")
GeomAbs_Parabola     -> other_curve("GeomAbs_Parabola")
GeomAbs_BezierCurve  -> other_curve("GeomAbs_BezierCurve")
GeomAbs_OffsetCurve  -> other_curve("GeomAbs_OffsetCurve")
GeomAbs_OtherCurve   -> other_curve("GeomAbs_OtherCurve")

surface = BRepAdaptor_Surface(prepared_face, True)
surface_symbol = surface.GetType()

GeomAbs_Plane              -> plane,           surface.Plane()
GeomAbs_Cylinder           -> cylinder,        surface.Cylinder()
GeomAbs_Cone               -> cone,            surface.Cone()
GeomAbs_Sphere             -> sphere,          surface.Sphere()
GeomAbs_Torus              -> torus,           surface.Torus()
GeomAbs_BSplineSurface     -> bspline_surface, surface.BSpline()
GeomAbs_BezierSurface      -> other_surface("GeomAbs_BezierSurface")
GeomAbs_SurfaceOfRevolution -> other_surface("GeomAbs_SurfaceOfRevolution")
GeomAbs_SurfaceOfExtrusion -> other_surface("GeomAbs_SurfaceOfExtrusion")
GeomAbs_OffsetSurface      -> other_surface("GeomAbs_OffsetSurface")
GeomAbs_OtherSurface       -> other_surface("GeomAbs_OtherSurface")
```

For line/circle/ellipse call the exact `gp_Lin`, `gp_Circ`, and `gp_Elips`
methods listed in the profile. For plane/cylinder/cone/sphere/torus call the
listed `gp_*` methods. `gp_Cone.SemiAngle()` is radians and is converted with
`math.degrees`. Normalize all serialized directions and reject non-finite data.
Map face orientation exactly from the four `TopAbs_*` symbols in the profile.
Treat a serialized normal/axis as local +Z and `x_direction` as local +X;
require `abs(dot(z,x)) <= 1e-12`, and derive +Y as
`normalize(cross(z,x))`. Circle/cylinder/sphere radii are positive;
ellipse/torus satisfy `major_radius >= minor_radius > 0`; cone reference radius
is nonnegative and `0 < semi_angle_degrees < 90`.

For a B-spline curve read `Degree`, `IsRational`, `IsPeriodic`, `NbPoles`, and
`NbKnots`, then read every one-based `Knot(i)` and `Multiplicity(i)`. For a
B-spline surface read the corresponding U and V summary calls and every
one-based `UKnot`, `UMultiplicity`, `VKnot`, and `VMultiplicity` listed in the
profile. Before emitting the summary require:

```text
1 <= degree <= 25; poles >= 2; unique knots >= 2
knots are finite and strictly increasing
interior multiplicity is in [1, degree]
non-periodic endpoint multiplicity is in [1, degree+1]
non-periodic: sum(multiplicities) == poles + degree + 1
periodic: first multiplicity == last multiplicity
periodic: sum(multiplicities) - first multiplicity == poles
```

Apply those rules independently to U and V for a surface. The maximum 25 is
also checked against `Geom_BSplineCurve.MaxDegree_s()` and
`Geom_BSplineSurface.MaxDegree_s()`.

## Kernel properties

```text
bounds(shape):
  box = Bnd_Box()
  box.SetGap(0.0)
  BRepBndLib.AddOptimal_s(shape, box, False, False)
  return box.Get()

edge properties:
  props = GProp_GProps()
  BRepGProp.LinearProperties_s(edge, props, False, False)
  length = props.Mass(); centroid = props.CentreOfMass()

face properties:
  props = GProp_GProps()
  BRepGProp.SurfaceProperties_s(face, props, False, False)
  area = props.Mass(); centroid = props.CentreOfMass()

solid properties:
  volume_props = GProp_GProps()
  BRepGProp.VolumeProperties_s(solid, volume_props, False, False, False)
  volume = volume_props.Mass(); centroid = volume_props.CentreOfMass()
  surface_props = GProp_GProps()
  BRepGProp.SurfaceProperties_s(solid, surface_props, False, False)
  surface_area = surface_props.Mass()

vertex position = BRep_Tool.Pnt_s(vertex)
```

All property inputs are prepared definition-local shapes. Reject non-finite
results and a zero-mass entity for which the required centroid is undefined.
The serialized quality string is exactly `kernel_evaluated`.

## Metadata projection

```text
project(value, path, ancestors):
  reject a cycle
  accept null, boolean, and string without coercion
  accept an integer only in [-9007199254740991, 9007199254740991]
  accept a finite binary64 without coercion
  map list recursively
  map tuple recursively to a JSON array
  map an object only when every key is a string; recurse on each value
  reject bytes, set, non-string keys, non-finite numbers, and every other value

project_entity_metadata(metadata):
  require a top-level object
  omit graph, topo_ref, track, source_sketch, sketch_solve, sketch_promotion
  omit every key beginning with "_"
  retain every other key, including geo and std.* keys, through project()
  report the exact metadata path and fail compilation on rejection
```

No `repr`, stringification, integer-key conversion, or OCP-object coercion is
permitted. RFC 8785 determines object key order in canonical bytes.

## `geo_exact` score and uniqueness

The selector constructor is `simplecadapi.operations._make_geo_selector`; the
score is `simplecadapi.serializer._geo_selector_score`. `metadata_geo` has zero
score contribution. `distance` is binary64 Euclidean vec3 distance.

Build the selector after location baking and FORWARD edge orientation. Common
fields are `mode`, `kind`, JSON-normalized `metadata_geo`, `bbox`, and optional
`geom_type`; `mode`, `kind`, and `metadata_geo` are required, while `bbox` and
`geom_type` are optional. The optional `source_shape` constructor argument is
not serialized or scored. Never serialize a source traversal index. Use
`BRepBndLib.AddOptimal_s(shape, box, False, False)` after `box.SetGap(0.0)` for
the bbox. Vertex adds `coordinates`; edge adds `length`, `center`, and, only
when both wrapper calls succeed, `start` and `end`; face adds `area`, `center`,
`normal`, `edge_count`, and `inner_wire_count`; solid adds `volume` and center.
The exact wrapper calls are listed in the profile.

`metadata_geo` is normalized by
`simplecadapi.operations._jsonable_geo_value`: null/string/boolean and Python
int/float are retained; NumPy integers/floats convert to Python numbers; a
successful `to_tuple()` converts to a recursive float array; x/y/z attributes
convert to a float vec3; dict keys convert with `str` and values recurse; lists
and tuples recurse to arrays; every other value converts with `str`. The result
must be in the RFC 8785 domain or compilation fails.

`Face.get_normal_at(0.5, 0.5)` constructs `BRepAdaptor_Surface(face, True)`,
maps 0.5 to the midpoint of each first/last parameter range, constructs
`BRepLProp_SLProps(adaptor, midpoint_u, midpoint_v, 1, 1e-7)`, requires
`IsNormalDefined()`, reads `Normal()`, and reverses it for `TopAbs_REVERSED`.

```text
if candidate kind != selector kind: score = 1e12
otherwise:
  if selector.bbox is absent: bbox = 0
  else bbox = distance(actual_min, expected_min) +
              distance(actual_max, expected_max)
  use bbox = 1e6 when a present bbox is invalid or cannot be evaluated
  score = 10*bbox
  if expected geom_type exists and evaluated geom_type exists and differs:
    score += 1e6

  vertex: score += 10*distance(coordinates, selector.coordinates)

  edge:
    if the length key exists: score += 10*abs(length-selector.length)
    score += 10*distance(center, selector.center)
    if both selector endpoints and candidate endpoints are available:
      score += min(distance(start,selector.start)+distance(end,selector.end),
                   distance(start,selector.end)+distance(end,selector.start))

  face:
    if the area key exists: score += abs(area-selector.area)
    score += 10*distance(center,selector.center)
    score += 5*distance(normal,selector.normal)
    if edge_count exists: score += 10*abs(edge_count-selector.edge_count)
    if inner_wire_count exists:
      score += 10*abs(inner_wire_count-selector.inner_wire_count)

  solid: if volume exists: score += abs(volume-selector.volume)
```

`distance(a,b)` returns `1e6` when either vec3 is absent and otherwise returns
`math.dist(a,b)`.

Reject non-finite scores. Evaluate every same-kind candidate in the owner Part
body. A supported match requires exactly one score `<= 0.0001` and every other
score `> 0.0001`. More than one passing candidate is `selector_ambiguous`; zero
passing candidates or a clean replay that resolves to another canonical entity
is `selector_unstable`. Apply the profile's binding reason precedence.
The resolver's candidate index has zero score contribution.

## Connector frame

```text
orthogonal_x(z):
  seeds = [(1,0,0), (0,1,0), (0,0,1)]
  best = seeds[0]
  for seed in seeds[1:]:
    replace best only if abs(dot(z,seed)) < abs(dot(z,best))
  return normalize(best - z*dot(z,best))

frame(origin, z):
  z = normalize(z)
  x = orthogonal_x(z)
  y = normalize(cross(z,x))
  return Placement(origin=origin, x_axis=x, y_axis=y)

face:   frame(selector.center, selector.normal)
edge:   frame(selector.center, selector.end-selector.start)
vertex: identity axes at selector.coordinates
solid:  null
```

The strict-less-than scan makes exact seed ties choose X before Y before Z.
An edge with missing or coincident endpoints has a null frame. Store the
unflipped frame; binding `flip` is not applied to the sidecar snapshot.

## Canonical entity labeling

```text
initial_record(e) = internal closed canonicalization-only object containing:
  kind, geometry, properties, source, sdk_connector_frame, render_status,
  connector_binding_status, semantic_binding_ids, evaluated_tags,
  sdk_metadata, render_key
render_key is null for solid, vertex, and degenerate edge
initial_bytes(e) = JCS(initial_record(e))
label(e) = SHA-256(initial_bytes(e))
partition entities by label; order initial cells by label bytes

Labels are held internally as 32 raw bytes. Whenever a label occurs in JCS,
encode it as 64 lowercase hexadecimal characters without a prefix.

repeat simultaneously:
  signature(e) = JCS([
      label(e),
      unsigned-byte-sort(multiset(label(parent))),
      unsigned-byte-sort(multiset(label(child)))])
  next_label(e) = SHA-256(signature(e))
  split each existing cell by next_label and order its subcells by label bytes
  never merge cells that were already separate
until the partition no longer splits

Call search on the root partition with depth 0. If every cell is singleton,
encode that permutation. Otherwise choose the first
non-singleton cell in current partition order. For every candidate ordered by
(initial_bytes, refined label bytes), replace the cell by a candidate singleton
followed by the remainder. At depth d assign the singleton label
`SHA-256(0x49 || big_endian_u64(d) || old_label || initial_bytes(candidate))`,
refine again, and recurse depth-first. Exact candidate-order ties may use any
order because every branch is evaluated. Recurse with depth d+1. Count the root and every recursive
individualized partition as one state. If the count would exceed 1,000,000, fail with
`entity_canonicalization_budget_exceeded`.

For a complete permutation, encode JCS of an array in permutation order. Each
array item has exactly `child_indices`, `initial_record`, and `parent_indices`;
the index arrays contain the corresponding permutation indices sorted as
ascending integers. The winning
permutation has the lexicographically least complete encoding bytes. Compare all
candidates; traversal order never selects the winner by itself.

For each kind in solid, face, edge, vertex order, filter the winning permutation
to that kind and assign entity/{kind}/0, entity/{kind}/1, ... . Output entities
by unsigned UTF-8 entity ID. Sort every set-like ID/tag/binding array by unsigned
UTF-8 bytes.
```

Any normative profile change requires a new profile ID and a mandatory cache
miss.
