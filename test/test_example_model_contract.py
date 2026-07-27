"""Structural checks for the example model/session contract."""

import ast
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _model_files() -> tuple[Path, ...]:
    return (
        EXAMPLES / "04_dimension_tolerance_chain.py",
        EXAMPLES / "08_constrained_sketch.py",
        EXAMPLES / "09_naca0016_blade_freecad.py",
        EXAMPLES / "10_part_assembly.py",
        EXAMPLES / "16_compact_two_stage_planetary_reducer" / "main.py",
        EXAMPLES / "20_integrated_bldc_joint_actuator" / "main.py",
    )


def _source_files() -> tuple[Path, ...]:
    return tuple(
        path
        for path in EXAMPLES.rglob("*.py")
        if "out" not in path.relative_to(EXAMPLES).parts
    )


def _is_decorator(node: ast.expr, name: str) -> bool:
    if isinstance(node, ast.Call):
        node = node.func
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "scad"
        and node.attr == name
    ) or (isinstance(node, ast.Name) and node.id == name)


class TestExampleModelContract(unittest.TestCase):
    def test_example_10_output_dir_is_anchored_to_the_example_file(self):
        path = EXAMPLES / "10_part_assembly.py"
        spec = importlib.util.spec_from_file_location("example_10_path_contract", path)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertTrue(module.OUT_DIR.is_absolute())
        self.assertEqual(
            module.OUT_DIR,
            EXAMPLES / "out" / "hydraulic_rod_assembly",
        )

    def test_each_current_model_entry_has_one_explicit_result(self):
        for path in _model_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            model_functions = [
                node
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and any(_is_decorator(decorator, "model") for decorator in node.decorator_list)
            ]
            self.assertEqual(len(model_functions), 1, path)
            self.assertFalse(
                isinstance(model_functions[0], ast.AsyncFunctionDef),
                f"async model entry is unsupported: {path}",
            )
            capture_calls = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "scad"
                and node.func.attr == "capture_result"
            ]
            self.assertEqual(len(capture_calls), 1, path)

    def test_examples_do_not_own_manual_sessions_or_serialization(self):
        for path in _source_files():
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("GraphSession(", source, path)
            self.assertNotIn("export_model_json(", source, path)
            self.assertNotIn("export_session_json(", source, path)

    def test_make_builders_require_the_active_session(self):
        for path in _source_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not (node.name.startswith("make_") or node.name.startswith("_make_")):
                    continue
                decorators = node.decorator_list
                has_session_contract = any(
                    _is_decorator(decorator, "requires_session")
                    or _is_decorator(decorator, "model")
                    for decorator in decorators
                )
                self.assertTrue(has_session_contract, f"{path}:{node.lineno}:{node.name}")


if __name__ == "__main__":
    unittest.main()
