"""Tests for auto-tagging based on TopoDelta."""

import unittest

import simplecadapi as scad
from simplecadapi.topology import TopoKind, TopoEvent
from simplecadapi.tracking import tracked_cut, tracked_union, tracked_extrude
from simplecadapi.autotag import apply_tracking_tags, apply_tracking_tags_to_delta


class TestAutoTagCut(unittest.TestCase):
    def setUp(self):
        self.body = scad.make_box_rsolid(10, 10, 10)
        self.tool = scad.make_cylinder_rsolid(
            2.0, 15.0, bottom_face_center=(3, 3, -2.5)
        )

    def test_cut_result_faces_get_operation_tags(self):
        result = tracked_cut(self.body, self.tool)
        tagged_solid = apply_tracking_tags_to_delta(
            result.solid, result.delta, result.delta_entries, op="cut"
        )
        faces = tagged_solid.get_faces()
        # At least some faces should have operation event tags
        has_op_tag = any(
            f.has_tag("op.cut.modified") or f.has_tag("op.cut.generated") for f in faces
        )
        self.assertTrue(has_op_tag)

    def test_cut_preserved_faces_tagged(self):
        result = tracked_cut(self.body, self.tool)
        tagged_solid = apply_tracking_tags_to_delta(
            result.solid, result.delta, result.delta_entries, op="cut"
        )
        faces = tagged_solid.get_faces()
        preserved = [f for f in faces if f.has_tag("op.cut.preserved")]
        self.assertGreater(len(preserved), 0)

    def test_cut_all_faces_tagged(self):
        result = tracked_cut(self.body, self.tool)
        tagged_solid = apply_tracking_tags_to_delta(
            result.solid, result.delta, result.delta_entries, op="cut"
        )
        faces = tagged_solid.get_faces()
        # All result faces should have some operation event tag
        all_tagged = all(
            f.has_tag("op.cut.modified")
            or f.has_tag("op.cut.preserved")
            or f.has_tag("op.cut.generated")
            for f in faces
        )
        self.assertTrue(all_tagged)

    def test_cut_origin_role_tags(self):
        result = tracked_cut(self.body, self.tool)
        tagged_solid = apply_tracking_tags_to_delta(
            result.solid, result.delta, result.delta_entries, op="cut"
        )
        faces = tagged_solid.get_faces()
        has_body = any(f.has_tag("origin.body") for f in faces)
        has_tool = any(f.has_tag("origin.tool") for f in faces)
        self.assertTrue(has_body)
        self.assertTrue(has_tool)


class TestAutoTagUnion(unittest.TestCase):
    def setUp(self):
        self.body = scad.make_box_rsolid(10, 10, 10)
        self.tool = scad.make_cylinder_rsolid(4.0, 10.0, bottom_face_center=(3, 3, 0))

    def test_union_section_faces_tagged(self):
        result = tracked_union(self.body, self.tool)
        tagged_solid = apply_tracking_tags_to_delta(
            result.solid, result.delta, result.delta_entries, op="union"
        )
        faces = tagged_solid.get_faces()
        # Union creates modified faces at the intersection
        has_union_tag = any(
            f.has_tag("op.union.modified") or f.has_tag("op.union.preserved")
            for f in faces
        )
        self.assertTrue(has_union_tag)


class TestAutoTagExtrude(unittest.TestCase):
    def setUp(self):
        self.profile = scad.make_rectangle_rface(5.0, 3.0)

    def test_extrude_faces_tagged(self):
        result = tracked_extrude(self.profile, (0, 0, 1), 10.0)
        tagged_solid = apply_tracking_tags_to_delta(
            result.shape, result.delta, result.delta_entries, op="extrude"
        )
        faces = tagged_solid.get_faces()
        # Extrude produces new faces; any operation tag is sufficient
        has_tag = any(
            f.has_tag("op.extrude.generated") or f.has_tag("op.extrude.modified")
            for f in faces
        )
        self.assertTrue(has_tag)


class TestAutoTagPreservesExisting(unittest.TestCase):
    def test_existing_tags_carried_to_result(self):
        """Tags from the original body should be carried to preserved/modified faces."""
        body = scad.make_box_rsolid(10, 10, 10)
        body.auto_tag_faces("box")
        tool = scad.make_cylinder_rsolid(2.0, 15.0, bottom_face_center=(3, 3, -2.5))
        result = tracked_cut(body, tool)
        tagged_solid = apply_tracking_tags_to_delta(
            result.solid,
            result.delta,
            result.delta_entries,
            op="cut",
            source_solid=body,
        )
        faces = tagged_solid.get_faces()
        # Preserved and modified faces from body should carry body's tags
        has_original = any(
            f.has_tag("face.top") or f.has_tag("face.bottom") for f in faces
        )
        self.assertTrue(has_original)


if __name__ == "__main__":
    unittest.main()
