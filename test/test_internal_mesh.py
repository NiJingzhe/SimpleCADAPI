import simplecadapi as scad
import simplecadapi._mesh as _mesh


def _write_cached_mesh_as_obj(solid, path):
    mesh = _mesh.cached_mesh(solid)
    assert mesh is not None

    lines = ["# SimpleCAD internal cached mesh OBJ"]
    for x, y, z in mesh.vertices:
        lines.append(f"v {x:.9g} {y:.9g} {z:.9g}")
    for a, b, c in mesh.triangles:
        lines.append(f"f {int(a) + 1} {int(b) + 1} {int(c) + 1}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return mesh


def test_solid_creation_attaches_internal_mesh_cache():
    solid = scad.make_box_rsolid(width=10.0, height=20.0, depth=30.0)

    mesh = _mesh.cached_mesh(solid)

    assert mesh is not None
    assert _mesh.mesh_error(solid) is None
    assert mesh.vertex_count > 0
    assert mesh.triangle_count > 0
    assert mesh.vertices.shape[1] == 3
    assert mesh.triangles.shape[1] == 3
    assert int(mesh.triangles.min()) >= 0
    assert int(mesh.triangles.max()) < mesh.vertex_count


def test_internal_mesh_preserves_face_triangle_ranges():
    solid = scad.make_box_rsolid(width=10.0, height=20.0, depth=30.0)

    mesh = _mesh.cached_mesh(solid)

    assert mesh is not None

    ranges = mesh.face_triangle_ranges
    assert len(ranges) == len(solid.get_faces())
    assert sum(item.count for item in ranges) == mesh.triangle_count
    assert [item.face_index for item in ranges] == list(range(len(ranges)))
    assert all(item.source_topo_id for item in ranges)


def test_internal_mesh_bounds_track_solid_extent():
    solid = scad.make_box_rsolid(width=10.0, height=20.0, depth=30.0)

    mesh = _mesh.cached_mesh(solid)
    assert mesh is not None

    lower, upper = mesh.bounds
    assert lower == (-5.0, -10.0, 0.0)
    assert upper == (5.0, 10.0, 30.0)


def test_transformed_solid_keeps_mesh_cache_on_transformed_geometry():
    solid = scad.make_box_rsolid(width=10.0, height=20.0, depth=30.0)

    translated = scad.translate_shape(shape=solid, vector=(1.0, 2.0, 3.0))
    mesh = _mesh.cached_mesh(translated)

    assert mesh is not None
    lower, upper = mesh.bounds
    assert lower == (-4.0, -8.0, 3.0)
    assert upper == (6.0, 12.0, 33.0)


def test_mesh_internals_are_not_top_level_public_api():
    assert not hasattr(scad, "tessellate_rmesh")
    assert "tessellate_rmesh" not in scad.__all__
    assert "TriMesh" not in scad.__all__


def test_cached_mesh_can_export_obj_without_public_stl_api(tmp_path):
    solid = scad.make_cylinder_rsolid(radius=3.0, height=5.0)
    output_path = tmp_path / "cached_mesh.obj"

    mesh = _write_cached_mesh_as_obj(solid, output_path)

    content = output_path.read_text(encoding="utf-8")
    vertex_lines = [line for line in content.splitlines() if line.startswith("v ")]
    face_lines = [line for line in content.splitlines() if line.startswith("f ")]
    assert len(vertex_lines) == mesh.vertex_count
    assert len(face_lines) == mesh.triangle_count
    assert content.startswith("# SimpleCAD internal cached mesh OBJ\n")
