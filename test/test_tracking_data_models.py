"""Tests for tracking data models: TopoRef, TopoEvent, TopoDelta, OperationNode, OperationGraph."""

import unittest

from simplecadapi.topology import (
    TopoKind,
    TopoEvent,
    TopoRef,
    TopoEntry,
    TopoDelta,
    OperationNode,
    OperationGraph,
)


class TestTopoRef(unittest.TestCase):
    def test_fields(self):
        ref = TopoRef("g1", "n1", 0, TopoKind.FACE, "f42")
        self.assertEqual(ref.graph_id, "g1")
        self.assertEqual(ref.node_id, "n1")
        self.assertEqual(ref.output_slot, 0)
        self.assertEqual(ref.kind, TopoKind.FACE)
        self.assertEqual(ref.topo_id, "f42")

    def test_equality(self):
        a = TopoRef("g1", "n1", 0, TopoKind.FACE, "f1")
        b = TopoRef("g1", "n1", 0, TopoKind.FACE, "f1")
        self.assertEqual(a, b)

    def test_inequality_different_topo_id(self):
        a = TopoRef("g1", "n1", 0, TopoKind.FACE, "f1")
        b = TopoRef("g1", "n1", 0, TopoKind.FACE, "f2")
        self.assertNotEqual(a, b)

    def test_inequality_different_node(self):
        a = TopoRef("g1", "n1", 0, TopoKind.FACE, "f1")
        b = TopoRef("g1", "n2", 0, TopoKind.FACE, "f1")
        self.assertNotEqual(a, b)

    def test_hashable(self):
        a = TopoRef("g1", "n1", 0, TopoKind.FACE, "f1")
        b = TopoRef("g1", "n1", 0, TopoKind.FACE, "f1")
        s = {a, b}
        self.assertEqual(len(s), 1)

    def test_hash_unequal(self):
        a = TopoRef("g1", "n1", 0, TopoKind.FACE, "f1")
        b = TopoRef("g1", "n1", 0, TopoKind.FACE, "f2")
        s = {a, b}
        self.assertEqual(len(s), 2)


class TestTopoEntry(unittest.TestCase):
    def test_preserved(self):
        ref = TopoRef("g1", "n1", 0, TopoKind.FACE, "f1")
        entry = TopoEntry(ref, TopoEvent.PRESERVED, origin_role="body")
        self.assertEqual(entry.event, TopoEvent.PRESERVED)
        self.assertEqual(entry.origin_role, "body")
        self.assertEqual(entry.parent_refs, ())

    def test_generated_with_parents(self):
        ref = TopoRef("g1", "n2", 0, TopoKind.FACE, "f_new")
        parent = TopoRef("g1", "n1", 0, TopoKind.FACE, "f1")
        entry = TopoEntry(
            ref, TopoEvent.GENERATED, origin_role="body", parent_refs=(parent,)
        )
        self.assertEqual(entry.event, TopoEvent.GENERATED)
        self.assertEqual(len(entry.parent_refs), 1)
        self.assertEqual(entry.parent_refs[0], parent)

    def test_deleted(self):
        ref = TopoRef("g1", "n1", 0, TopoKind.FACE, "f_gone")
        entry = TopoEntry(ref, TopoEvent.DELETED)
        self.assertEqual(entry.event, TopoEvent.DELETED)
        self.assertIsNone(entry.origin_role)


class TestTopoDelta(unittest.TestCase):
    def test_preserved_and_generated(self):
        preserved_ref = TopoRef("g1", "n2", 0, TopoKind.FACE, "f_keep")
        generated_ref = TopoRef("g1", "n2", 0, TopoKind.FACE, "f_new")
        delta = TopoDelta(
            preserved=[preserved_ref],
            generated=[generated_ref],
        )
        self.assertEqual(len(delta.preserved), 1)
        self.assertEqual(len(delta.modified), 0)
        self.assertEqual(len(delta.generated), 1)
        self.assertEqual(len(delta.deleted), 0)

    def test_modified_and_deleted(self):
        mod_ref = TopoRef("g1", "n2", 0, TopoKind.FACE, "f_mod")
        del_ref = TopoRef("g1", "n1", 0, TopoKind.FACE, "f_del")
        delta = TopoDelta(
            modified=[mod_ref],
            deleted=[del_ref],
        )
        self.assertEqual(len(delta.modified), 1)
        self.assertEqual(len(delta.deleted), 1)

    def test_section_edges(self):
        edge_ref = TopoRef("g1", "n2", 0, TopoKind.EDGE, "e_section")
        delta = TopoDelta(section_edges=[edge_ref])
        self.assertEqual(len(delta.section_edges), 1)
        self.assertEqual(delta.section_edges[0].kind, TopoKind.EDGE)

    def test_empty(self):
        delta = TopoDelta()
        self.assertEqual(delta.preserved, ())
        self.assertEqual(delta.modified, ())
        self.assertEqual(delta.generated, ())
        self.assertEqual(delta.deleted, ())
        self.assertEqual(delta.section_edges, ())


class TestOperationNode(unittest.TestCase):
    def test_creation(self):
        node = OperationNode(
            node_id="n1",
            op="make_line_redge",
            params={"start": (0, 0, 0), "end": (10, 0, 0)},
        )
        self.assertEqual(node.node_id, "n1")
        self.assertEqual(node.op, "make_line_redge")
        self.assertEqual(node.params["end"], (10, 0, 0))
        self.assertEqual(node.inputs, ())
        self.assertIsNone(node.topo_delta)

    def test_with_inputs(self):
        node1 = OperationNode("n1", "make_line_redge", {})
        node2 = OperationNode("n2", "make_wire_from_edges_rwire", {}, inputs=(node1,))
        self.assertEqual(len(node2.inputs), 1)
        self.assertEqual(node2.inputs[0].node_id, "n1")

    def test_with_topo_delta(self):
        delta = TopoDelta(generated=[TopoRef("g1", "n1", 0, TopoKind.FACE, "f_new")])
        node = OperationNode("n1", "make_extrude_rsolid", {}, topo_delta=delta)
        self.assertIsNotNone(node.topo_delta)
        self.assertEqual(len(node.topo_delta.generated), 1)

    def test_output_count(self):
        node = OperationNode("n1", "make_translate_rshape", {}, output_count=2)
        self.assertEqual(node.output_count, 2)


class TestOperationGraph(unittest.TestCase):
    def test_empty_graph(self):
        graph = OperationGraph()
        self.assertEqual(graph.node_count, 0)
        self.assertEqual(graph.edge_count, 0)
        self.assertEqual(graph.nodes, [])

    def test_add_primitive_node(self):
        graph = OperationGraph()
        node = graph.add_node(
            "make_line_redge", {"start": (0, 0, 0), "end": (10, 0, 0)}
        )
        self.assertEqual(graph.node_count, 1)
        self.assertEqual(node.op, "make_line_redge")
        self.assertEqual(node.params["end"], (10, 0, 0))

    def test_add_node_with_inputs(self):
        graph = OperationGraph()
        box_node = graph.add_node(
            "make_line_redge", {"start": (0, 0, 0), "end": (10, 0, 0)}
        )
        cyl_node = graph.add_node(
            "make_line_redge", {"start": (10, 0, 0), "end": (10, 10, 0)}
        )
        cut_node = graph.add_node(
            "make_wire_from_edges_rwire", {"edge_count": 2}, inputs=[box_node, cyl_node]
        )
        self.assertEqual(graph.node_count, 3)
        self.assertEqual(graph.edge_count, 2)
        self.assertEqual(len(cut_node.inputs), 2)

    def test_get_node(self):
        graph = OperationGraph()
        node = graph.add_node("make_line_redge", {})
        found = graph.get_node(node.node_id)
        self.assertEqual(found, node)

    def test_get_node_missing(self):
        graph = OperationGraph()
        self.assertIsNone(graph.get_node("nonexistent"))

    def test_unique_ids(self):
        graph = OperationGraph()
        n1 = graph.add_node("make_line_redge", {})
        n2 = graph.add_node("make_line_redge", {})
        self.assertNotEqual(n1.node_id, n2.node_id)

    def test_edges_are_set(self):
        graph = OperationGraph()
        box_node = graph.add_node("make_line_redge", {})
        cyl_node = graph.add_node("make_line_redge", {})
        graph.add_node("make_wire_from_edges_rwire", {}, inputs=[box_node, cyl_node])
        edges = graph.edges
        # Should not have duplicate edges
        self.assertEqual(len(edges), len(set(edges)))

    def test_upstream_nodes(self):
        graph = OperationGraph()
        n1 = graph.add_node("make_line_redge", {})
        n2 = graph.add_node("make_line_redge", {})
        n3 = graph.add_node("make_wire_from_edges_rwire", {}, inputs=[n1, n2])
        upstream = graph.upstream_nodes(n3.node_id)
        self.assertEqual(len(upstream), 2)
        self.assertIn(n1.node_id, upstream)
        self.assertIn(n2.node_id, upstream)

    def test_upstream_empty(self):
        graph = OperationGraph()
        n1 = graph.add_node("make_line_redge", {})
        self.assertEqual(graph.upstream_nodes(n1.node_id), [])

    def test_downstream_nodes(self):
        graph = OperationGraph()
        n1 = graph.add_node("make_line_redge", {})
        n2 = graph.add_node("make_line_redge", {})
        n3 = graph.add_node("make_wire_from_edges_rwire", {}, inputs=[n1, n2])
        downstream = graph.downstream_nodes(n1.node_id)
        self.assertEqual(len(downstream), 1)
        self.assertEqual(downstream[0], n3.node_id)

    def test_is_dag_valid(self):
        graph = OperationGraph()
        n1 = graph.add_node("make_line_redge", {})
        n2 = graph.add_node("make_line_redge", {})
        n3 = graph.add_node("make_wire_from_edges_rwire", {}, inputs=[n1, n2])
        self.assertTrue(graph.is_dag())

    def test_is_dag_empty(self):
        graph = OperationGraph()
        self.assertTrue(graph.is_dag())

    def test_root_nodes(self):
        graph = OperationGraph()
        n1 = graph.add_node("make_line_redge", {})
        n2 = graph.add_node("make_line_redge", {})
        n3 = graph.add_node("make_wire_from_edges_rwire", {}, inputs=[n1, n2])
        roots = graph.root_nodes()
        self.assertEqual(len(roots), 2)
        root_ids = [r.node_id for r in roots]
        self.assertIn(n1.node_id, root_ids)
        self.assertIn(n2.node_id, root_ids)

    def test_leaf_nodes(self):
        graph = OperationGraph()
        n1 = graph.add_node("make_line_redge", {})
        n2 = graph.add_node("make_line_redge", {})
        n3 = graph.add_node("make_wire_from_edges_rwire", {}, inputs=[n1, n2])
        leaves = graph.leaf_nodes()
        self.assertEqual(len(leaves), 1)
        self.assertEqual(leaves[0].node_id, n3.node_id)

    def test_topological_order(self):
        graph = OperationGraph()
        n1 = graph.add_node("make_line_redge", {})
        n2 = graph.add_node("make_line_redge", {})
        n3 = graph.add_node("make_wire_from_edges_rwire", {}, inputs=[n1, n2])
        n4 = graph.add_node("make_face_from_wire_rface", {}, inputs=[n3])
        topo = graph.topological_order()
        self.assertEqual(len(topo), 4)
        # n1 and n2 before n3, n3 before n4
        idx = {node.node_id: i for i, node in enumerate(topo)}
        self.assertLess(idx[n1.node_id], idx[n3.node_id])
        self.assertLess(idx[n2.node_id], idx[n3.node_id])
        self.assertLess(idx[n3.node_id], idx[n4.node_id])

    def test_topological_order_single(self):
        graph = OperationGraph()
        n1 = graph.add_node("make_line_redge", {})
        topo = graph.topological_order()
        self.assertEqual(len(topo), 1)
        self.assertEqual(topo[0].node_id, n1.node_id)


if __name__ == "__main__":
    unittest.main()
