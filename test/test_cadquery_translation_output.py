"""Tests for the CadQuery → FTC translator (tools/research/cadqueryftc).

The fixtures are real traces captured with cadquery 2.8 (see
``cadquery_traces/*.cq.py`` for the source programs); the translator itself is
pure Python, so these tests run in the ordinary repo environment with no
cadquery installed.

Two layers:

- format pins: the generated source follows the Feature Tree Convention
  (parseable block headers, closed role vocabulary, sketch API for planar
  profiles, list-form booleans, QL selections, no in-script verification);
- geometry reconciliation: each fixture builds through simplecadapi and its
  ``BODIES`` volume matches the ground-truth ``cq_volume`` recorded in the
  trace.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOLS_DIR = _REPO_ROOT / "tools" / "research" / "cadqueryftc"
_FIXTURES = _REPO_ROOT / "test" / "cadquery_traces"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from cqftc.replay import replay_trace_to_ftc  # noqa: E402
from cqftc.tracer.trace_schema import OperationTrace  # noqa: E402

_HEADER_RE = re.compile(r"^    # ---- feature: ([a-z0-9-]+) \((.+?)\) ----$", re.MULTILINE)
_ROLES = frozenset({"build", "add", "subtract", "intersect", "modify", "pattern", "annotate"})
_TIERS = frozenset({"profile=sketch", "profile=geometry", "path=sketch", "path=geometry"})

# APIs banned in generated FTC source (translator discipline):
#  - direct-geometry profile construction (sketch API carries planar profiles)
#  - no-arg topology enumeration (plural getters are index-only)
#  - in-script verification (checks live in the external validator)
_BANNED_PATTERNS = [
    ("make_circle_rface(", "direct-geometry circle profile"),
    ("make_rectangle_rface(", "direct-geometry rectangle profile"),
    ("make_polyline_rwire(", "direct-geometry polyline profile"),
    ("make_circle_rwire(", "direct-geometry circle wire"),
    (".get_edges()", "no-arg edge enumeration"),
    (".get_faces()", "no-arg face enumeration"),
    ("print(", "in-script verification print"),
    ("assert ", "in-script verification assert"),
    ("result_tag=", "training-channel artifact tag"),
    ("scad.var(", "invented parameter registry"),
]


def _load_trace(name: str) -> OperationTrace:
    payload = json.loads((_FIXTURES / f"{name}.trace.json").read_text(encoding="utf-8"))
    payload.pop("stem", None)
    payload.pop("family", None)
    return OperationTrace.from_dict(payload)


def _translate(name: str):
    trace = _load_trace(name)
    source, meta, _snapshots = replay_trace_to_ftc(trace, stem=name)
    return source, meta


class TestCadQueryFtcFormat(unittest.TestCase):
    def test_fixture_set_translates_clean(self) -> None:
        names = sorted(p.name.removesuffix(".trace.json") for p in _FIXTURES.glob("*.trace.json"))
        self.assertGreaterEqual(len(names), 4)
        for name in names:
            with self.subTest(stem=name):
                source, meta = _translate(name)
                self.assertEqual(meta["status"], "ok", msg=json.dumps(meta.get("unsupported")))
                self.assertEqual(meta["unsupported"], [])
                self.assertGreater(meta["feature_count"], 0)
                self.assertIn("@scad.part(id='cq-", source)

    def test_block_headers_parseable_with_closed_roles(self) -> None:
        for name in ("washer", "hexnut", "rarray_plate", "revolve_ring"):
            with self.subTest(stem=name):
                source, _meta = _translate(name)
                headers = _HEADER_RE.findall(source)
                self.assertTrue(headers, "no FTC block headers found")
                roles = set()
                for _slug, annotation in headers:
                    parts = [p.strip() for p in annotation.split(",")]
                    self.assertIn(parts[0], _ROLES, msg=f"role {parts[0]!r} outside closed vocabulary")
                    roles.update(parts[0] for _ in [0])
                    for tier in parts[1:]:
                        self.assertIn(tier, _TIERS, msg=f"unknown tier annotation {tier!r}")
                self.assertIn("build", {annotation.split(",")[0].strip() for _slug, annotation in headers})

    def test_slugs_carry_no_sequence_numbers(self) -> None:
        source, _meta = _translate("washer")
        slugs = [slug for slug, _annotation in _HEADER_RE.findall(source)]
        for slug in slugs:
            self.assertFalse(re.fullmatch(r"[a-z]+[-_]?0*[0-9]+", slug), msg=f"slug {slug!r} looks positional")

    def test_translated_profiles_use_sketch_api(self) -> None:
        for name in ("washer", "hexnut", "rarray_plate", "revolve_ring"):
            with self.subTest(stem=name):
                source, _meta = _translate(name)
                self.assertIn("scad.make_sketch_rsketch(", source)
                self.assertIn("scad.make_face_from_sketch_rface(", source)
                for pattern, label in _BANNED_PATTERNS:
                    self.assertNotIn(pattern, source, msg=f"{label}: {pattern!r} leaked into output")

    def test_planar_profiles_annotate_geometry_tier(self) -> None:
        source, _meta = _translate("hexnut")
        headers = _HEADER_RE.findall(source)
        annotated = [annotation for _slug, annotation in headers if "profile=geometry" in annotation]
        self.assertTrue(annotated, "transcribed profiles must annotate profile=geometry")

    def test_booleans_use_list_form_and_bodies_dataflow(self) -> None:
        source, _meta = _translate("hexnut")
        self.assertIn("bodies = list([", source)
        self.assertIn("bodies = [scad.cut_rsolid(_b, [", source)
        self.assertNotIn("scad.cut_rsolid(_b, _", source)  # single-tool form banned
        self.assertIn("return _merge_bodies(bodies)", source)

    def test_modifier_selections_are_ql_predicates_with_cardinality(self) -> None:
        source, _meta = _translate("washer")  # washer ends with edges(">Y").chamfer(...)
        self.assertIn("ql.edges()", source)
        self.assertIn("ql.prop('geom.type'", source)
        self.assertRegex(source, r"\.take\(\d+\)\.exactly\(\d+\)")
        self.assertIn("from simplecadapi import ql", source)

    def test_pattern_block_role(self) -> None:
        source, _meta = _translate("rarray_plate")
        headers = _HEADER_RE.findall(source)
        roles = {annotation.split(",")[0].strip() for _slug, annotation in headers}
        self.assertIn("pattern", roles)
        self.assertIn("for _c in [", source)

    def test_unsupported_ops_become_notes_not_drops(self) -> None:
        trace = _load_trace("hexnut")
        trace.steps.append(
            type(trace.steps[0])(op="totallyUnknown", args=[1.0], kwargs={}, selections=[])
        )
        source, meta, _snapshots = replay_trace_to_ftc(trace, stem="hexnut_x")
        self.assertIn("unsupported op: totallyUnknown", source)
        self.assertEqual(meta["status"], "partial")
        self.assertTrue(any("totallyUnknown" in note for note in meta["unsupported"]))
        self.assertNotIn("totallyUnknown()", source.replace("unsupported op: totallyUnknown", ""))


class TestCadQueryFtcGeometry(unittest.TestCase):
    """Reconciliation against ground-truth volumes recorded by the tracer."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._staged: list[Path] = []
        cls._counter = 0

    def _build_and_compare(self, name: str) -> None:
        source, meta = _translate(name)
        self.assertEqual(meta["status"], "ok")
        # @scad.part needs a real file under a project root; stage uniquely so
        # the content-addressed part cache never short-circuits the body.
        cases_dir = _TOOLS_DIR / "out" / "_test_cases"
        cases_dir.mkdir(parents=True, exist_ok=True)
        self._counter += 1
        staged = cases_dir / f"{name}_{id(self)}_{self._counter}.ftc.py"
        staged.write_text(source, encoding="utf-8")
        self._staged.append(staged)
        spec = importlib.util.spec_from_file_location(staged.stem, staged)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.build()
        self.assertTrue(module.BODIES, "BODIES channel empty after build")
        volume = sum(float(body.get_volume()) for body in module.BODIES)
        expected = json.loads((_FIXTURES / f"{name}.trace.json").read_text(encoding="utf-8"))["cq_volume"]
        rel_err = abs(volume - expected) / abs(expected)
        self.assertLess(rel_err, 1e-6, msg=f"volume drift: ftc={volume} cq={expected}")

    def test_washer_volume_reconciles(self) -> None:
        self._build_and_compare("washer")

    def test_hexnut_volume_reconciles(self) -> None:
        self._build_and_compare("hexnut")

    def test_rarray_plate_volume_reconciles(self) -> None:
        self._build_and_compare("rarray_plate")

    def test_revolve_ring_volume_reconciles(self) -> None:
        self._build_and_compare("revolve_ring")

    @classmethod
    def tearDownClass(cls) -> None:
        for staged in cls._staged:
            staged.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
