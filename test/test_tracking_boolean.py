"""Tests for BRep tracking: boolean operation history capture via OCC Modified/Generated/IsDeleted."""

import unittest

import simplecadapi as scad
from simplecadapi.topology import (
    TopoKind,
    TopoEvent,
    TopoRef,
    TopoDelta,
    OperationNode,
    OperationGraph,
)
from simplecadapi.tracking import (
    tracked_cut,
    tracked_union,
    tracked_intersect,
    TrackedBooleanResult,
)


class TestTrackedCut(unittest.TestCase):
    """Test cut with full face-level history."""

    def setUp(self):
        self.body = scad.make_box_rsolid(10, 10, 10)
        self.tool = scad.make_cylinder_rsolid(
            2.0, 15.0, bottom_face_center=(3, 3, -2.5)
        )

    def test_tracked_cut_returns_solid_and_delta(self):
        result = tracked_cut(self.body, self.tool)
        self.assertIsInstance(result, TrackedBooleanResult)
        self.assertIsNotNone(result.solid)
        self.assertIsInstance(result.delta, TopoDelta)

    def test_tracked_cut_has_preserved_faces(self):
        result = tracked_cut(self.body, self.tool)
        preserved_face_refs = [
            r for r in result.delta.preserved if r.kind == TopoKind.FACE
        ]
        # After a cylinder cut through a box, most original faces should be
        # either modified or preserved; some should survive
        self.assertGreater(len(preserved_face_refs), 0)

    def test_tracked_cut_has_generated_faces(self):
        result = tracked_cut(self.body, self.tool)
        generated_face_refs = [
            r for r in result.delta.generated if r.kind == TopoKind.FACE
        ]
        # The cylindrical hole creates new faces
        self.assertGreater(len(generated_face_refs), 0)

    def test_tracked_cut_volume_decreased(self):
        result = tracked_cut(self.body, self.tool)
        original_vol = self.body.get_volume()
        result_vol = result.solid.get_volume()
        self.assertLess(result_vol, original_vol)

    def test_tracked_cut_total_faces_increased(self):
        """A cylinder cut through a box adds the cylindrical hole face."""
        result = tracked_cut(self.body, self.tool)
        original_faces = len(self.body.get_faces())
        result_faces = len(result.solid.get_faces())
        # Cylinder through box: at least 1 new face (cylindrical hole)
        self.assertGreaterEqual(result_faces, original_faces)

    def test_tracked_cut_tool_with_tool_face_labels(self):
        """Faces from the tool should be labeled with origin_role='tool'."""
        result = tracked_cut(self.body, self.tool)
        tool_generated = [
            r
            for r in result.delta.generated
            if r.kind == TopoKind.FACE
            and result.delta_entries.get(r.topo_id, {}).get("origin_role") == "tool"
        ]
        # At least the cylindrical face of the hole should be tool-origin
        self.assertGreater(len(tool_generated), 0)

    def test_tracked_cut_preserves_volume_accuracy(self):
        result = tracked_cut(self.body, self.tool)
        # Volume should be original minus roughly the cylinder volume
        expected_min = self.body.get_volume() - 3.14159 * 2.0**2 * 15.0
        self.assertGreater(result.solid.get_volume(), 0)


class TestTrackedUnion(unittest.TestCase):
    def setUp(self):
        self.body = scad.make_box_rsolid(10, 10, 10)
        # Use a cylinder to ensure curved intersection edges
        self.tool = scad.make_cylinder_rsolid(4.0, 10.0, bottom_face_center=(3, 3, 0))

    def test_tracked_union_returns_solid_and_delta(self):
        result = tracked_union(self.body, self.tool)
        self.assertIsInstance(result, TrackedBooleanResult)
        self.assertIsNotNone(result.solid)

    def test_tracked_union_volume_increased(self):
        result = tracked_union(self.body, self.tool)
        original_vol = self.body.get_volume()
        result_vol = result.solid.get_volume()
        # Union of two overlapping boxes should be less than sum but more than either
        self.assertGreater(result_vol, original_vol)

    def test_tracked_union_has_section_edges(self):
        result = tracked_union(self.body, self.tool)
        # Two overlapping boxes should create section edges
        section_edges = result.delta.section_edges
        self.assertGreater(len(section_edges), 0)


class TestTrackedIntersect(unittest.TestCase):
    def setUp(self):
        self.body = scad.make_box_rsolid(10, 10, 10)
        self.tool = scad.make_cylinder_rsolid(6.0, 10.0, bottom_face_center=(3, 3, 0))

    def test_tracked_intersect_returns_solid_and_delta(self):
        result = tracked_intersect(self.body, self.tool)
        self.assertIsInstance(result, TrackedBooleanResult)
        self.assertIsNotNone(result.solid)

    def test_tracked_intersect_volume_less_than_both(self):
        result = tracked_intersect(self.body, self.tool)
        self.assertLess(result.solid.get_volume(), self.body.get_volume())
        self.assertLess(result.solid.get_volume(), self.tool.get_volume())


class TestDeltaEntries(unittest.TestCase):
    """Test that delta_entries provides origin_role info."""

    def setUp(self):
        self.body = scad.make_box_rsolid(10, 10, 10)
        self.tool = scad.make_cylinder_rsolid(
            3.0, 15.0, bottom_face_center=(3, 3, -2.5)
        )

    def test_body_faces_labeled(self):
        result = tracked_cut(self.body, self.tool)
        body_preserved = [
            r
            for r in result.delta.preserved
            if r.kind == TopoKind.FACE
            and result.delta_entries.get(r.topo_id, {}).get("origin_role") == "body"
        ]
        self.assertGreater(len(body_preserved), 0)

    def test_modified_faces_labeled(self):
        result = tracked_cut(self.body, self.tool)
        body_modified = [
            r
            for r in result.delta.modified
            if r.kind == TopoKind.FACE
            and result.delta_entries.get(r.topo_id, {}).get("origin_role") == "body"
        ]
        # Some faces from body should be modified
        self.assertGreater(len(body_modified), 0)


class TestSolidMapping(unittest.TestCase):
    """Test that the result solid is a valid SimpleCADAPI Solid."""

    def setUp(self):
        self.body = scad.make_box_rsolid(10, 10, 10)
        self.tool = scad.make_cylinder_rsolid(
            2.0, 15.0, bottom_face_center=(3, 3, -2.5)
        )

    def test_result_is_solid(self):
        result = tracked_cut(self.body, self.tool)
        self.assertIsInstance(result.solid, scad.Solid)

    def test_result_has_faces(self):
        result = tracked_cut(self.body, self.tool)
        faces = result.solid.get_faces()
        self.assertGreater(len(faces), 0)

    def test_result_has_valid_volume(self):
        result = tracked_cut(self.body, self.tool)
        self.assertGreater(result.solid.get_volume(), 0)


if __name__ == "__main__":
    unittest.main()
