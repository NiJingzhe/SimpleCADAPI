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
        assert result is not None
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


class TestSerializableGeometrySelectors(unittest.TestCase):
    def test_generic_property_predicate_matches_geometry_type(self):
        edge = scad.make_circle_redge((0, 0, 0), 1.0)
        pred = Q.prop("geom.type", "==", "CIRCLE")
        self.assertTrue(pred(edge))

    def test_generic_property_key_reads_center_axis(self):
        face = scad.make_rectangle_rface(2.0, 2.0, center=(0, 0, 3.0))
        key = Q.key("geom.center.z")
        self.assertAlmostEqual(key(face), 3.0, places=6)

    def test_custom_property_resolver_extends_ql_without_core_changes(self):
        obj = object()

        def resolver(target, path):
            if target is obj and path == "custom.answer":
                return 42
            return Q.MISSING

        Q.register_property_resolver("custom.", resolver)
        try:
            self.assertTrue(Q.prop("custom.answer", "==", 42)(obj))
            self.assertEqual(Q.key("custom.answer")(obj), 42)
        finally:
            Q.unregister_property_resolver("custom.")

    def test_edge_selector_serializes_and_roundtrips(self):
        selector = (
            Q.edges()
            .where(Q.prop("geom.type", "==", "CIRCLE"))
            .order_by(Q.key("geom.center.z"))
            .take(1)
            .exactly(1)
        )

        payload = selector.to_dict()
        restored = Q.selector_from_dict(payload)

        self.assertEqual(payload["target_kind"], "edge")
        self.assertEqual(payload["limit"], 1)
        self.assertEqual(payload["cardinality"]["exactly"], 1)
        self.assertEqual(restored.to_dict(), payload)

    def test_wire_selector_reads_loop_role_property(self):
        face = scad.make_rectangle_rface(2.0, 2.0)

        wires = (
            Q.wires()
            .where(Q.prop("topo.loop_role", "==", "outer"))
            .take(1)
            .exactly(1)
            .resolve(face)
        )

        self.assertEqual(len(wires), 1)
        self.assertTrue(Q.prop("topo.loop_role", "==", "outer")(wires[0]))

    def test_face_selector_resolves_geometry_predicates(self):
        box = scad.make_box_rsolid(2.0, 3.0, 4.0)
        selector = (
            Q.faces()
            .where(Q.prop("geom.type", "==", "PLANE"))
            .order_by(Q.key("geom.center.z"), desc=True)
            .take(1)
            .exactly(1)
        )

        faces = selector.resolve(box)
        self.assertEqual(len(faces), 1)
        top_face = faces[0]
        self.assertGreater(top_face.get_normal_at().z, 0.9)

    def test_edge_selector_resolves_circular_bottom_edge(self):
        with scad.GraphSession():
            rod = scad.make_cylinder_rsolid(1.0, 5.0, bottom_face_center=(0, 0, 0))
        selector = (
            Q.edges()
            .where(Q.prop("geom.type", "==", "CIRCLE"))
            .order_by(Q.key("geom.center.z"))
            .take(1)
            .exactly(1)
        )

        edges = selector.resolve(rod)
        self.assertEqual(len(edges), 1)
        meta = edges[0].get_metadata("topo_ref")
        self.assertIsNotNone(meta)
        self.assertEqual(meta["kind"], "EDGE")

    def test_boundary_traversal_selects_top_face_outer_edges(self):
        box = scad.make_box_rsolid(2.0, 3.0, 4.0)
        selector = (
            Q.faces()
            .where(Q.prop("geom.normal.z", ">", 0.9))
            .order_by(Q.key("geom.center.z"), desc=True)
            .take(1)
            .exactly(1)
            .boundary("wire")
            .where(Q.prop("topo.loop_role", "==", "outer"))
            .take(1)
            .exactly(1)
            .boundary("edge")
            .exactly(4)
        )

        edges = selector.resolve(box)
        self.assertEqual(len(edges), 4)

        payload = selector.to_dict()
        restored = Q.selector_from_dict(payload)
        self.assertEqual(len(restored.resolve(box)), 4)
        self.assertEqual(payload["traversal"]["relation"], "boundary")
        self.assertEqual(payload["source"]["traversal"]["relation"], "boundary")

    def test_boundary_traversal_selects_cut_top_edges_from_field_surface(self):
        field = scad.field.make_ellipsoid_rscalarfield((0.0, 0.0, 0.0), (1.6, 1.1, 2.0))
        field_solid = scad.make_field_surface_rsolid(
            field,
            bounds=((-2.0, -2.0, -2.0), (2.0, 2.0, 2.0)),
            resolution=(12, 12, 12),
            iso=0.0,
        )
        tool = scad.make_box_rsolid(
            4.0, 4.0, 4.0, bottom_face_center=(-2.0, -2.0, 0.25)
        )
        result = scad.cut_rsolidlist(field_solid, tool)

        selector = (
            Q.faces()
            .where(Q.prop("geom.type", "==", "PLANE"))
            .where(Q.prop("geom.normal.z", ">", 0.9))
            .order_by(Q.key("geom.center.z"), desc=True)
            .take(1)
            .exactly(1)
            .boundary("wire")
            .where(Q.prop("topo.loop_role", "==", "outer"))
            .take(1)
            .exactly(1)
            .boundary("edge")
        )

        edges = selector.resolve(result)
        self.assertGreater(len(edges), 0)

    def test_selector_exactly_enforces_cardinality(self):
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        selector = (
            Q.faces().where(Q.prop("geom.type", "==", "PLANE")).take(2).exactly(1)
        )
        with self.assertRaises(ValueError):
            selector.resolve(box)


if __name__ == "__main__":
    unittest.main()
