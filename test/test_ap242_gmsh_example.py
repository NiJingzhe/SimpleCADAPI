"""Contract tests for the optional AP242-to-Gmsh volume mesh example."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "12_ap242_gmsh_volume_mesh.py"


def _load_example():
    spec = importlib.util.spec_from_file_location("ap242_gmsh_example", EXAMPLE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Option:
    def __init__(self):
        self.strings = []
        self.numbers = []

    def setString(self, name, value):
        self.strings.append((name, value))

    def setNumber(self, name, value):
        self.numbers.append((name, value))


class _Occ:
    def __init__(self):
        self.imported = []
        self.synchronized = False

    def importShapes(self, path):
        self.imported.append(path)
        return [(3, 9)]

    def synchronize(self):
        self.synchronized = True


class _Mesh:
    def __init__(self, *, fail=False):
        self.generated = []
        self.fail = fail

    def generate(self, dimension):
        self.generated.append(dimension)
        if self.fail:
            raise RuntimeError("mesh failure")

    def getNodes(self):
        return [1, 2, 3, 4], [0.0] * 12, []

    def getElements(self, dimension):
        return [4], [[20, 21]], [[1, 2, 3, 4, 1, 2, 3, 4]]


class _Model:
    def __init__(self, *, fail=False):
        self.occ = _Occ()
        self.mesh = _Mesh(fail=fail)
        self.models = []
        self.physical_groups = []
        self.physical_names = []

    def add(self, name):
        self.models.append(name)

    def getEntities(self, dimension):
        return [(3, 9)] if dimension == 3 else []

    def addPhysicalGroup(self, dimension, tags):
        self.physical_groups.append((dimension, tags))
        return 7

    def setPhysicalName(self, dimension, tag, name):
        self.physical_names.append((dimension, tag, name))


class _Gmsh:
    def __init__(self, *, fail=False):
        self.option = _Option()
        self.model = _Model(fail=fail)
        self.initialized = 0
        self.finalized = 0
        self.written = []

    def initialize(self):
        self.initialized += 1

    def finalize(self):
        self.finalized += 1

    def write(self, path):
        self.written.append(path)
        Path(path).write_text(
            "$MeshFormat\n4.1 0 8\n$EndMeshFormat\n", encoding="ascii"
        )


class TestAP242GmshExample(unittest.TestCase):
    def test_example_import_does_not_require_gmsh(self):
        module = _load_example()

        self.assertTrue(callable(module.build_bracket))
        self.assertTrue(callable(module.mesh_step_with_gmsh))
        self.assertEqual(module.OUT_DIR.name, "ap242_gmsh_volume_mesh")

    def test_mesh_step_uses_occ_volume_mesh_and_reports_counts(self):
        module = _load_example()
        gmsh = _Gmsh()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            step = root / "part.step"
            step.write_text("STEP", encoding="ascii")
            mesh = root / "part.msh"
            report = module.mesh_step_with_gmsh(
                step,
                mesh,
                mesh_size=1.25,
                gmsh_module=gmsh,
            )

        self.assertEqual(gmsh.initialized, 1)
        self.assertEqual(gmsh.finalized, 1)
        self.assertEqual(gmsh.option.strings, [("Geometry.OCCTargetUnit", "MM")])
        self.assertEqual(
            gmsh.option.numbers,
            [("Mesh.MeshSizeMin", 1.25), ("Mesh.MeshSizeMax", 1.25)],
        )
        self.assertEqual(gmsh.model.mesh.generated, [3])
        self.assertEqual(gmsh.model.physical_groups, [(3, [9])])
        self.assertEqual(report.volume_count, 1)
        self.assertEqual(report.node_count, 4)
        self.assertEqual(report.element_count, 2)

    def test_gmsh_is_finalized_when_meshing_fails(self):
        module = _load_example()
        gmsh = _Gmsh(fail=True)
        with tempfile.TemporaryDirectory() as tmp_dir:
            step = Path(tmp_dir) / "part.step"
            step.write_text("STEP", encoding="ascii")
            with self.assertRaisesRegex(RuntimeError, "mesh failure"):
                module.mesh_step_with_gmsh(
                    step,
                    Path(tmp_dir) / "part.msh",
                    gmsh_module=gmsh,
                )

        self.assertEqual(gmsh.initialized, 1)
        self.assertEqual(gmsh.finalized, 1)


if __name__ == "__main__":
    unittest.main()
