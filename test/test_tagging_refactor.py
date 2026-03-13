import unittest

import simplecadapi as scad
from simplecadapi import tagging


class TestTaggingRefactor(unittest.TestCase):
    def test_tag_validation(self):
        self.assertTrue(tagging.is_normalized_tag("geom.primitive.box"))
        self.assertTrue(tagging.is_normalized_tag("face.top"))
        self.assertFalse(tagging.is_normalized_tag("Face.Top"))
        self.assertFalse(tagging.is_normalized_tag("size: 2x3x4"))

    def test_tag_policy_propagation(self):
        policy = tagging.DEFAULT_TAG_POLICY
        self.assertTrue(policy.should_propagate("role.mounting_surface"))
        self.assertTrue(policy.should_propagate("anchor.datum.primary"))
        self.assertTrue(policy.should_propagate("group.fasteners"))
        self.assertFalse(policy.should_propagate("feature.extrude.start_face"))
        self.assertFalse(policy.should_propagate("state.debug"))
        self.assertFalse(policy.should_propagate("face.top"))
        self.assertFalse(policy.should_propagate("legacy.top"))

    def test_apply_tag_propagates_role(self):
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        box.apply_tag("role.mounting_surface")

        faces = box.get_faces()
        self.assertTrue(any(face.has_tag("role.mounting_surface") for face in faces))

        edges = box.get_edges()
        self.assertTrue(any(edge.has_tag("role.mounting_surface") for edge in edges))

    def test_anchor_resolution_role_tag(self):
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        box.auto_tag_faces("box")
        top_faces = [face for face in box.get_faces() if face.has_tag("top")]
        self.assertTrue(top_faces)
        top_face = top_faces[0]
        top_face.apply_tag("role.mounting_surface")

        asm = scad.make_assembly_rassembly([("box", box)])
        anchor = asm.part("box").face_center("mounting_surface")

        self.assertEqual(anchor.part, "box")
        self.assertEqual(anchor.label, "face:mounting_surface")


class TestAutoTagFacesNamespaces(unittest.TestCase):
    def test_box_faces_have_new_tags(self):
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        box.auto_tag_faces("box")
        faces = box.get_faces()
        self.assertTrue(any(face.has_tag("face.top") for face in faces))
        self.assertTrue(any(face.has_tag("face.bottom") for face in faces))

    def test_cylinder_faces_have_new_tags(self):
        cylinder = scad.make_cylinder_rsolid(1.0, 2.0)
        cylinder.auto_tag_faces("cylinder")
        faces = cylinder.get_faces()
        self.assertTrue(any(face.has_tag("face.top") for face in faces))
        self.assertTrue(any(face.has_tag("face.bottom") for face in faces))
        self.assertTrue(any(face.has_tag("face.side") for face in faces))

    def test_sphere_faces_have_new_tags(self):
        sphere = scad.make_sphere_rsolid(1.0)
        sphere.auto_tag_faces("sphere")
        faces = sphere.get_faces()
        self.assertEqual(len(faces), 1)
        self.assertTrue(faces[0].has_tag("face.surface"))


if __name__ == "__main__":
    unittest.main()
