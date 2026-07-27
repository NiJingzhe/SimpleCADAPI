"""Tests for stable public API surface.

The package may add a small number of necessary new APIs for graph/session and
serialization, but internal implementation modules should not be advertised from
the top-level namespace.
"""

import json
import subprocess
import sys
import unittest


class TestPublicApiSurface(unittest.TestCase):
    def test_internal_modules_not_in___all__(self):
        import simplecadapi as scad

        self.assertNotIn("tracking", scad.__all__)
        self.assertNotIn("autotag", scad.__all__)
        self.assertNotIn("topology", scad.__all__)
        self.assertNotIn("graph", scad.__all__)
        self.assertNotIn("serializer", scad.__all__)

    def test_only_necessary_new_top_level_apis_are_present(self):
        code = """
import json
import simplecadapi as scad
print(json.dumps({
  'has_tracking': hasattr(scad, 'tracking'),
  'has_autotag': hasattr(scad, 'autotag'),
  'has_topology': hasattr(scad, 'topology'),
  'has_graph_module': hasattr(scad, 'graph'),
  'has_serializer_module': hasattr(scad, 'serializer'),
  'has_graph_session': hasattr(scad, 'GraphSession'),
  'has_export_graph_json': hasattr(scad, 'export_graph_json'),
  'has_import_graph_json': hasattr(scad, 'import_graph_json'),
  'has_replay_graph': hasattr(scad, 'replay_graph'),
  'has_apply_tag': hasattr(scad, 'apply_tag'),
  'has_list_tags': hasattr(scad, 'list_tags'),
  'has_set_tag': hasattr(scad, 'set_tag'),
}))
"""
        proc = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(proc.stdout)

        self.assertFalse(payload["has_tracking"])
        self.assertFalse(payload["has_autotag"])
        self.assertFalse(payload["has_topology"])
        self.assertFalse(payload["has_graph_module"])
        self.assertFalse(payload["has_serializer_module"])
        self.assertTrue(payload["has_graph_session"])
        self.assertTrue(payload["has_export_graph_json"])
        self.assertTrue(payload["has_import_graph_json"])
        self.assertTrue(payload["has_replay_graph"])
        self.assertTrue(payload["has_apply_tag"])
        self.assertTrue(payload["has_list_tags"])
        self.assertFalse(payload["has_set_tag"])

    def test_canonical_tagging_exports(self):
        import simplecadapi as scad
        from simplecadapi import operations, tagging

        expected = {
            "apply_tag_rselection": operations.apply_tag_rselection,
            "explain_tag": operations.explain_tag,
            "LineageDerivation": tagging.LineageDerivation,
            "LineagePolicy": tagging.LineagePolicy,
            "TagAttachment": tagging.TagAttachment,
            "TagBinding": tagging.TagBinding,
            "TagBindingScope": tagging.TagBindingScope,
            "TagCertainty": tagging.TagCertainty,
            "TagEvidence": tagging.TagEvidence,
            "TagEvidenceKind": tagging.TagEvidenceKind,
            "TagLifecycle": tagging.TagLifecycle,
            "TagLineageWitness": tagging.TagLineageWitness,
            "TagProducer": tagging.TagProducer,
            "TagProducerKind": tagging.TagProducerKind,
            "TagPropagation": tagging.TagPropagation,
            "TagScope": tagging.TagScope,
            "TagTarget": tagging.TagTarget,
            "TagTargetKind": tagging.TagTargetKind,
            "TopologyPropagation": tagging.TopologyPropagation,
        }

        for name, implementation in expected.items():
            with self.subTest(name=name):
                self.assertIn(name, scad.__all__)
                self.assertIs(getattr(scad, name), implementation)

    def test_tracking_policy_is_public(self):
        import simplecadapi as scad
        from simplecadapi.tracking import TrackingPolicy

        self.assertIn("TrackingPolicy", scad.__all__)
        self.assertIs(scad.TrackingPolicy, TrackingPolicy)
