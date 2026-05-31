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
        scad.apply_tag(box, "role.mounting_surface")

        faces = box.get_faces()
        self.assertTrue(any("role.mounting_surface" in scad.list_tags(face) for face in faces))

        edges = box.get_edges()
        self.assertTrue(any("role.mounting_surface" in scad.list_tags(edge) for edge in edges))

    def test_tagging_public_surface_is_functional_and_sorted(self):
        vertex = scad.make_point_rvertex(0.0, 0.0, 0.0)

        scad.apply_tag(vertex, "role.zeta")
        scad.apply_tag(vertex, "role.alpha")

        self.assertEqual(scad.list_tags(vertex), ["role.alpha", "role.zeta"])
        for member_name in ("add_tag", "apply_tag", "get_tags", "has_tag", "remove_tag"):
            self.assertFalse(hasattr(vertex, member_name))
        self.assertFalse(hasattr(scad, "set_tag"))

    def test_anchor_resolution_candidate_priority(self):
        candidates = tagging.resolve_anchor_tag_candidates("mounting_surface")

        self.assertEqual(candidates[0], "role.mounting_surface")
        self.assertEqual(candidates[1], "anchor.mounting_surface")
        self.assertIn("face.mounting_surface", candidates)
        self.assertEqual(candidates[-1], "mounting_surface")

    def test_new_primitive_tags_are_normalized_and_geo_metadata_carries_values(self):
        box = scad.make_box_rsolid(1.0, 2.0, 3.0)

        box_tags = scad.list_tags(box)
        self.assertEqual(box_tags, sorted(box_tags))
        self.assertTrue(all(tagging.is_normalized_tag(tag) for tag in box_tags))
        self.assertFalse(any(tag.isdigit() for tag in box_tags))
        self.assertFalse(any(":" in tag or " " in tag for tag in box_tags))
        self.assertEqual(box.get_metadata("geo")["size"], {"x": 1.0, "y": 2.0, "z": 3.0})

    def test_wire_edge_indices_live_in_geo_metadata_not_tags(self):
        wire = scad.make_rectangle_rwire(1.0, 1.0)
        edges = wire.get_edges()

        self.assertTrue(edges)
        self.assertFalse(any(tag.isdigit() for edge in edges for tag in scad.list_tags(edge)))
        self.assertTrue(all(edge.get_metadata("geo")["edge_index"] >= 0 for edge in edges))

    def test_anchor_resolution_prefers_role_over_anchor_and_topology_tags(self):
        candidates = tagging.resolve_anchor_tag_candidates("datum")

        self.assertLess(candidates.index("role.datum"), candidates.index("anchor.datum"))
        self.assertLess(candidates.index("anchor.datum"), candidates.index("face.datum"))


class TestAutoTagFacesNamespaces(unittest.TestCase):
    def test_box_faces_have_new_tags(self):
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        box.auto_tag_faces("box")
        faces = box.get_faces()
        self.assertTrue(any("face.top" in scad.list_tags(face) for face in faces))
        self.assertTrue(any("face.bottom" in scad.list_tags(face) for face in faces))

    def test_cylinder_faces_have_new_tags(self):
        cylinder = scad.make_cylinder_rsolid(1.0, 2.0)
        cylinder.auto_tag_faces("cylinder")
        faces = cylinder.get_faces()
        self.assertTrue(any("face.top" in scad.list_tags(face) for face in faces))
        self.assertTrue(any("face.bottom" in scad.list_tags(face) for face in faces))
        self.assertTrue(any("face.side" in scad.list_tags(face) for face in faces))

    def test_sphere_faces_have_new_tags(self):
        sphere = scad.make_sphere_rsolid(1.0)
        sphere.auto_tag_faces("sphere")
        faces = sphere.get_faces()
        self.assertEqual(len(faces), 1)
        self.assertIn("face.surface", scad.list_tags(faces[0]))


if __name__ == "__main__":
    unittest.main()
