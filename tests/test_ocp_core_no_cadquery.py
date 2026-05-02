from pathlib import Path

import pytest

from simplecadapi import make_box_rsolid, make_line_redge, make_rectangle_rface, extrude_rsolid
from simplecadapi.core import Edge, Face, Solid, Vertex, Wire


def test_core_public_shapes_do_not_expose_cq_accessors():
    box = make_box_rsolid(1, 2, 3)
    face = box.get_faces()[0]
    edge = face.get_outer_wire().get_edges()[0]
    vertex = edge.get_start_vertex()
    wire = face.get_outer_wire()

    for shape in (box, face, edge, vertex, wire):
        assert hasattr(shape, "wrapped")
        for forbidden in ("cq_solid", "cq_face", "cq_edge", "cq_vertex", "cq_wire"):
            assert not hasattr(shape, forbidden), f"{type(shape).__name__} exposes {forbidden}"


def test_ocp_native_basic_properties():
    line = make_line_redge((0, 0, 0), (3, 4, 0))
    assert isinstance(line, Edge)
    assert line.get_length() == pytest.approx(5.0)
    assert line.get_start_vertex().get_coordinates() == pytest.approx((0, 0, 0))
    assert line.get_end_vertex().get_coordinates() == pytest.approx((3, 4, 0))

    box = make_box_rsolid(1, 2, 3)
    assert isinstance(box, Solid)
    assert box.get_volume() == pytest.approx(6.0)
    assert len(box.get_faces()) == 6


def test_ocp_native_face_wire_topology_and_extrude():
    face = make_rectangle_rface(2, 3)
    assert isinstance(face, Face)
    assert face.get_area() == pytest.approx(6.0)
    assert isinstance(face.get_outer_wire(), Wire)
    assert face.get_outer_wire().is_closed()

    solid = extrude_rsolid(face, (0, 0, 1), 4)
    assert solid.get_volume() == pytest.approx(24.0)


def test_runtime_source_has_no_cadquery_imports_in_runtime_package():
    runtime_files = [p for p in Path("src/simplecadapi").rglob("*.py") if "auto_tools" not in p.parts]
    forbidden = ("import cadquery", "from cadquery", "cadquery.occ_impl", ".cq_solid", ".cq_face", ".cq_edge", ".cq_wire", ".cq_vertex")
    for path in runtime_files:
        text = path.read_text()
        for token in forbidden:
            assert token not in text, f"{path} contains forbidden CadQuery token {token!r}"
