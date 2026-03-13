import unittest

import simplecadapi as scad
from simplecadapi import ql as Q


class TestQLTagPredicates(unittest.TestCase):
    def test_tag_exact_and_wildcard(self):
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        box.apply_tag("role.mounting_surface")

        self.assertTrue(Q.tag("role.mounting_surface")(box))
        self.assertTrue(Q.tag("role.*")(box))
        self.assertFalse(Q.tag("role.other")(box))

    def test_tag_face_prefix(self):
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        box.auto_tag_faces("box")
        top_faces = [face for face in box.get_faces() if face.has_tag("face.top")]
        self.assertTrue(top_faces)

        top_face = top_faces[0]
        self.assertTrue(Q.tag("face.top")(top_face))
        self.assertTrue(Q.tag("face.*")(top_face))


class TestQLMetadataPredicates(unittest.TestCase):
    def test_meta_eq_and_compare(self):
        box = scad.make_box_rsolid(2.0, 3.0, 4.0)

        self.assertTrue(Q.meta("geo.type", "==", "box")(box))
        self.assertTrue(Q.meta("geo.size.x", ">", 1.0)(box))

    def test_select_where_order_first(self):
        c1 = scad.make_cylinder_rsolid(1.0, 1.0)
        c2 = scad.make_cylinder_rsolid(1.0, 3.0)
        c3 = scad.make_cylinder_rsolid(1.0, 2.0)

        result = (
            Q.select([c1, c2, c3]).order_by(Q.value("geo.height"), desc=True).first()
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.get_metadata("geo")["height"], 3.0)

    def test_where_and_not(self):
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        cyl = scad.make_cylinder_rsolid(1.0, 1.0)
        box.apply_tag("role.mounting_surface")
        box.apply_tag("state.debug", propagate=False)

        predicate = Q.and_(
            Q.meta("geo.type", "==", "box"),
            Q.tag("role.mounting_surface"),
            Q.not_(Q.tag("state.*")),
        )

        result = Q.select([box, cyl]).where(predicate).all()
        self.assertEqual(result, [])

        predicate = Q.and_(
            Q.meta("geo.type", "==", "box"),
            Q.tag("role.mounting_surface"),
        )

        result = Q.select([box, cyl]).where(predicate).all()
        self.assertEqual(result, [box])

    def test_first_empty(self):
        self.assertIsNone(Q.select([]).first())


if __name__ == "__main__":
    unittest.main()
