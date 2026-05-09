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
