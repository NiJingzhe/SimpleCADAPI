# Scene 1.0 OCP GLB Profile 2 Pseudocode

This normative profile defines the bytes produced by the Scene compiler. Every
OCP symbol below exists in cadquery-ocp 7.9.3.1. The meshing, edge sampling, and
GLB surfaces are grounded in `simplecadapi.kernel.ocp_mesh`,
`simplecadapi.scene.render_mesh`, and `simplecadapi.scene.glb`.

## Registered toolchain descriptor

The `toolchain_hash` input is the SHA-256 of RFC 8785 JCS bytes for one closed
object with exactly `build_identity`, `native_libraries`, `profile_hashes`,
`python_executable`, `python_modules`, and `schema_version`. `schema_version` is
`1.0`. Each file record has exactly `content_hash` and `logical_name`, where the
hash is `sha256:` plus lowercase SHA-256 hex over the exact file bytes.
`build_identity` is a closed object; `profile_hashes`, `python_modules`, and
`native_libraries` are record arrays; `python_executable` is one record.
`profile_hashes` contains exactly the two packaged profile file records. Python module
records contain the registered complete output-affecting transitive source
closure rooted at the modules listed in the profile. Native records contain the
registered complete OCP binding and transitive native-kernel library closure.
`python_executable` hashes the regular file reached by resolving
`sys.executable`. Record arrays are unique and sorted by logical name in
unsigned UTF-8 order.

Registration consumes a trusted build manifest mapping logical names to files.
Resolve symlinks and require every input to be a readable regular file. An
incomplete output-affecting source or native closure is not a registered
toolchain. `simplecadapi.scene.compiler` is an exact required Phase B target
root; it is explicitly absent during Phase A and therefore is not falsely
claimed as an existing implementation.

`build_identity` is closed and contains exactly `ocp_bindings_version`,
`ocp_version`, `platform_tag`, `python_abi`, and `simplecadapi_version`; each
value matches `[A-Za-z0-9][A-Za-z0-9._+-]{0,127}`. Absolute paths, mtimes, and
host names are forbidden. Display versions do not replace the descriptor hash,
and reproducibility may be claimed only for an exact registered hash match.

## Definition-local shapes

```text
bake_location(shape, requested_orientation):
  located = shape.Oriented(requested_orientation) when requested_orientation is not null
            otherwise shape
  location = located.Location()
  unlocated = located.Located(TopLoc_Location(), False)
  builder = BRepBuilderAPI_Transform(
      unlocated, location.Transformation(), True, False)
  builder.Build()
  return builder.Shape(); fail unless builder.IsDone()

For a face, requested_orientation is null and its TopAbs orientation is retained.
For an edge, requested_orientation is TopAbs_FORWARD before location is baked.
The prepared shape, not the located input, is used for meshing, discretization,
properties, classification, selectors, and frames.
```

## Numeric primitives

```text
f64(x):
  evaluate x as IEEE-754 binary64 round-to-nearest-ties-to-even
  reject a non-finite result
  return result

f32(x):
  result = IEEE-754 binary32 round-to-nearest-ties-to-even(x)
  reject overflow or a non-finite result
  if bits(result) == 0x80000000: return bits(0x00000000)
  return result

cross(a, b):
  x = f64(f64(a.y * b.z) - f64(a.z * b.y))
  y = f64(f64(a.z * b.x) - f64(a.x * b.z))
  z = f64(f64(a.x * b.y) - f64(a.y * b.x))
  FMA is forbidden
  return (x, y, z)

normalize(v):
  squared = f64(f64(v.x * v.x) + f64(v.y * v.y))
  squared = f64(squared + f64(v.z * v.z))
  length = correctly_rounded_binary64_sqrt(squared)
  reject length == 0 or non-finite
  result = (f32(v.x / length), f32(v.y / length), f32(v.z / length))
  reject binary64 norm(result) outside [0.999999, 1.000001]
  return result
```

## Face triangulation

```text
for each prepared definition-local face:
  BRepTools.Clean_s(face, False)
  mesher = BRepMesh_IncrementalMesh(
      face,
      float(compile_options.linear_tolerance),
      False,
      float(compile_options.angular_tolerance),
      False)
  mesher.Perform()

  tri_location = TopLoc_Location()
  tri = BRep_Tool.Triangulation_s(face, tri_location, 0)
  fail the face if tri is null
  trsf = tri_location.Transformation()

  for node_index in 1..tri.NbNodes():
    cad_point = tri.Node(node_index).Transformed(trsf)

  for triangle_index in 1..tri.NbTriangles():
    (a, b, c) = tri.Triangle(triangle_index).Get()
    oriented = (a, c, b) if face.Orientation() == TopAbs_REVERSED
               else (a, b, c)

    positions = [f32_components(cad_to_gltf(cad_point[node_index]))
                 for node_index in oriented]
    drop the triangle if two position bit triples are equal
    collapsed_cross = cross(positions[1] - positions[0],
                            positions[2] - positions[0])
    drop when all three collapsed_cross components are signed zero

    for each corner node_index in oriented:
      position = positions[corner ordinal]
      if tri.HasNormals():
        direction = tri.Normal(node_index).Transformed(trsf)
        if face.Orientation() == TopAbs_REVERSED:
          direction = direction.Reversed()
        normal = normalize(cad_to_gltf_direction(direction))
      else:
        normal = normalize(collapsed_cross)
      append vertex_key = little_endian(position f32 bits || normal f32 bits)
    append the oriented triangle of its three vertex_keys

  reject the face if no triangle remains
  remove unreferenced vertices and sort unique vertices by vertex_key bytes
  remap each triangle to local indices
  rotate each oriented triple cyclically to its lexicographically least value;
  reversal is forbidden
  sort triples lexicographically
  encode each local index as little-endian u16 when this block has at most 65536
  vertices, otherwise as little-endian u32
  block = sorted vertex_key bytes followed by the encoded local triangle indices
  render_key = SHA-256(0x01 || block)
```

Normals are per triangle corner. There is no averaging within a CAD face or
across CAD faces.

## Edge discretization

```text
for each edge prepared with TopAbs_FORWARD orientation:
  adaptor = BRepAdaptor_Curve(edge)
  sampler = GCPnts_TangentialDeflection(
      adaptor,
      adaptor.FirstParameter(),
      adaptor.LastParameter(),
      float(compile_options.angular_tolerance),
      float(compile_options.linear_tolerance),
      2,
      1e-9,
      1e-7)
  fail compilation if sampler construction raises
  points = [sampler.Value(i) for i in 1..sampler.NbPoints()]
  convert each point through cad_to_gltf and f32

  for each adjacent pair:
    drop it when endpoint bit triples are equal
  sort unique position bit triples and remap endpoints
  replace each pair with (min(local_a, local_b), max(local_a, local_b))
  sort and deduplicate pairs
  if no pair remains, retain a degenerate entity and emit no render block
  otherwise:
    encode local indices as little-endian u16 when this block has at most 65536
    vertices, otherwise as little-endian u32
    block = sorted position bits followed by the encoded local segment indices
    render_key = SHA-256(0x02 || block)
```

## Block and range order

```text
Sort all emitted face blocks and all emitted edge blocks independently by
(render_key bytes, block bytes). Keep one block per rendered entity. Within an
equal-block cell, assign otherwise indistinguishable range slots by canonical
entity ID in unsigned UTF-8 order. Concatenate vertices in block order and add
the number of prior vertices to each block-local index. Metadata, source,
bindings, and tags never enter a block or render_key.

Emit one positive face group per face and one positive edge group per rendered
edge; a degenerate edge has no group. Each array is ordered by `first_index`,
has contiguous zero-based `group_id` values, and exactly partitions its primitive
index accessor without overlap. Face counts are multiples of three and edge
counts are multiples of two. `mesh_index` and `primitive_index` are zero;
`first_index` and `index_count` count accessor elements, not bytes.
```

## Exact GLB writer

```text
writer identity = simplecadapi.scene.glb.scene-1.0-ocp-glb-1
asset = {"generator":"SimpleCAD Scene GLB Profile 1","version":"2.0"}
root fields = accessors, asset, bufferViews, buffers, meshes, nodes, scene, scenes
scene = 0; nodes = [{"mesh":0}]; scenes = [{"nodes":[0]}]
meshes = [{"primitives":[primitive]}]

triangle primitive = {
  "attributes":{"NORMAL":1,"POSITION":0}, "indices":2, "mode":4}
triangle BIN = POSITION float32x3, NORMAL float32x3, zero alignment, INDICES

line primitive = {
  "attributes":{"POSITION":0}, "indices":1, "mode":1}
line BIN = POSITION float32x3, zero alignment, INDICES

POSITION accessor fields = bufferView, componentType=5126, count, max, min,
                           type="VEC3"
NORMAL accessor fields = bufferView, componentType=5126, count, type="VEC3"
index accessor fields = bufferView, componentType, count, type="SCALAR"
array bufferView target = 34962; index bufferView target = 34963
bufferView fields = buffer=0, byteLength, byteOffset, target
buffer fields = byteLength, equal to the unpadded BIN length

Use componentType 5123 when total vertex count <= 65536, otherwise 5125.
All integer and float buffer values are little-endian. Buffer views are
contiguous in the stated order and each next offset is aligned to four bytes
with zeroes. POSITION min/max are exact decoded binary32 extrema.

JSON bytes are RFC 8785 JCS UTF-8 followed by minimal 0x20 padding to a multiple
of four. BIN bytes use minimal 0x00 final padding to a multiple of four. Emit a
12-byte little-endian GLB header (magic 0x46546c67, version 2, total length),
then JSON chunk type 0x4e4f534a, then BIN chunk type 0x004e4942.

Empty accessors, URI buffers, extras, extensions, and every JSON field not named
above are forbidden.
```

## Default appearance and Product equivalence

The exact default appearance is:

```json
{"alpha_mode":"opaque","base_color":[0.72,0.75,0.78,1],"double_sided":false,"edge_color":[0.08,0.09,0.1,1],"metallic":0,"name":null,"roughness":0.55,"sdk_metadata":{},"source":null}
```

Definition equivalence validates against `normalized-product-1.schema.json` and
compares exact RFC 8785 JCS bytes. Part connectors and Assembly components,
connectors, and constraints retain declaration order. Grounded component IDs
are sorted by unsigned UTF-8 bytes. A component contains exactly
`component_id`, nullable `name`, `definition_ref`, and `local_placement`.
Material is the complete normalized JSON-safe record; Product metadata uses the
evaluated profile projection; runtime connector `_metadata` is forbidden. Any
record difference is a typed semantic-ID collision. Mesh equality and subset or
"at least same" heuristics are forbidden.

Any normative profile change requires a new profile ID and a mandatory cache
miss. Characterization must cover every case in `required_characterization_cases`.
