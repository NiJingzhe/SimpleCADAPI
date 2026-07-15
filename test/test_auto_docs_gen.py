import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src/simplecadapi/auto_tools/auto_docs_gen.py"
)
MODULE_SPEC = importlib.util.spec_from_file_location(
    "simplecadapi_auto_docs_gen",
    MODULE_PATH,
)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load module spec for {MODULE_PATH}")

auto_docs_gen = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = auto_docs_gen
MODULE_SPEC.loader.exec_module(auto_docs_gen)


class TestAutoDocsGenPathResolution(unittest.TestCase):
    def test_resolve_source_files_from_source_checkout(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            (project_root / "pyproject.toml").write_text(
                "[project]\nname = 'demo'\n",
                encoding="utf-8",
            )

            module_file = project_root / "src/simplecadapi/auto_tools/auto_docs_gen.py"
            module_file.parent.mkdir(parents=True, exist_ok=True)
            module_file.write_text("", encoding="utf-8")

            resolved = auto_docs_gen._resolve_source_files(
                None, module_file=module_file
            )
            package_root = project_root / "src/simplecadapi"
            expected = [
                (package_root / name).resolve()
                for name in auto_docs_gen.DEFAULT_SOURCE_FILENAMES
            ]

            self.assertEqual(resolved, expected)

    def test_resolve_source_files_from_site_packages_install(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            venv_root = Path(tmp_dir) / ".venv/lib/python3.12/site-packages"
            module_file = venv_root / "simplecadapi/auto_tools/auto_docs_gen.py"
            module_file.parent.mkdir(parents=True, exist_ok=True)
            module_file.write_text("", encoding="utf-8")

            resolved = auto_docs_gen._resolve_source_files(
                None, module_file=module_file
            )
            package_root = venv_root / "simplecadapi"
            expected = [
                (package_root / name).resolve()
                for name in auto_docs_gen.DEFAULT_SOURCE_FILENAMES
            ]

            self.assertEqual(resolved, expected)

    def test_resolve_output_dirs_from_source_checkout_uses_repo_docs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            (project_root / "pyproject.toml").write_text(
                "[project]\nname = 'demo'\n",
                encoding="utf-8",
            )

            module_file = project_root / "src/simplecadapi/auto_tools/auto_docs_gen.py"
            module_file.parent.mkdir(parents=True, exist_ok=True)
            module_file.write_text("", encoding="utf-8")

            resolved = auto_docs_gen._resolve_output_dirs(None, module_file=module_file)

            self.assertEqual(resolved, [(project_root / "docs/api").resolve()])

    def test_resolve_output_dirs_from_site_packages_install_uses_cwd(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            workspace_root = tmp_path / "workspace"
            workspace_root.mkdir()

            venv_root = tmp_path / ".venv/lib/python3.12/site-packages"
            module_file = venv_root / "simplecadapi/auto_tools/auto_docs_gen.py"
            module_file.parent.mkdir(parents=True, exist_ok=True)
            module_file.write_text("", encoding="utf-8")

            resolved = auto_docs_gen._resolve_output_dirs(
                None,
                module_file=module_file,
                cwd=workspace_root,
            )

            self.assertEqual(resolved, [(workspace_root / "docs/api").resolve()])

    def test_default_source_files_include_v2_public_modules(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            package_root = Path(tmp_dir) / "src/simplecadapi"
            package_root.mkdir(parents=True, exist_ok=True)

            resolved = auto_docs_gen._default_source_files(package_root)

            resolved_names = [path.relative_to(package_root).as_posix() for path in resolved]
            self.assertIn("serializer.py", resolved_names)
            self.assertIn("graph.py", resolved_names)
            self.assertIn("expr.py", resolved_names)
            self.assertIn("tolerance.py", resolved_names)
            self.assertIn("sketch.py", resolved_names)
            self.assertIn("math.py", resolved_names)
            self.assertIn("translator/freecad_translator/api.py", resolved_names)
            self.assertIn(
                "translator/freecad_translator/script_translator.py",
                resolved_names,
            )

    def test_default_stdlib_source_files_include_standard_modules(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            package_root = Path(tmp_dir) / "src/simplecadapi"
            package_root.mkdir(parents=True, exist_ok=True)

            resolved = auto_docs_gen._default_stdlib_source_files(package_root)

            self.assertEqual(
                resolved,
                [
                    package_root / "std/bearing.py",
                    package_root / "std/gear.py",
                ],
            )

    def test_resolve_stdlib_output_dirs_from_source_checkout_uses_repo_docs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            (project_root / "pyproject.toml").write_text(
                "[project]\nname = 'demo'\n",
                encoding="utf-8",
            )

            module_file = project_root / "src/simplecadapi/auto_tools/auto_docs_gen.py"
            module_file.parent.mkdir(parents=True, exist_ok=True)
            module_file.write_text("", encoding="utf-8")

            resolved = auto_docs_gen._resolve_stdlib_output_dirs(
                None,
                module_file=module_file,
            )

            self.assertEqual(resolved, [(project_root / "docs/stdlib").resolve()])


class TestAutoDocsGenExtraction(unittest.TestCase):
    def test_extract_apis_from_v2_public_modules(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_file = tmp_path / "serializer.py"
            source_file.write_text(
                """
def export_model_json(session, indent=2):
    \"\"\"Export the canonical 2.0 model seed JSON.\"\"\"
    return \"{}\"


def _internal_helper():
    \"\"\"Should not be documented.\"\"\"
    return None
""".strip()
                + "\n",
                encoding="utf-8",
            )
            output_dir = tmp_path / "docs/api"

            generator = auto_docs_gen.APIDocumentGenerator(
                source_files=[source_file],
                output_dirs=[output_dir],
                quiet=True,
            )

            apis = generator.extract_apis()

            self.assertEqual([api.name for api in apis], ["export_model_json"])

    def test_generate_markdown_includes_v2_model_api_entry(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_file = tmp_path / "serializer.py"
            source_file.write_text(
                """
def export_model_json(session, indent=2):
    \"\"\"Export the canonical 2.0 model seed JSON.

    Args:
        session: Recorded graph session.
        indent: JSON indentation level.

    Returns:
        JSON string representation.
    \"\"\"
    return \"{}\"
""".strip()
                + "\n",
                encoding="utf-8",
            )
            output_dir = tmp_path / "docs/api"

            generator = auto_docs_gen.APIDocumentGenerator(
                source_files=[source_file],
                output_dirs=[output_dir],
                quiet=True,
            )
            generator.extract_apis()
            generator.generate_markdown_docs()

            readme = (output_dir / "README.md").read_text(encoding="utf-8")
            page = (output_dir / "export_model_json.md").read_text(encoding="utf-8")

            self.assertIn("[export_model_json](export_model_json.md)", readme)
            self.assertIn("def export_model_json(session, indent = 2)", page)
            self.assertIn("Export the canonical 2.0 model seed JSON.", page)

    def test_generate_markdown_avoids_case_insensitive_filename_collisions(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_file = tmp_path / "expr.py"
            source_file.write_text(
                """
class Const:
    \"\"\"Constant node.\"\"\"


def const(value):
    \"\"\"Constant constructor.\"\"\"
    return value
""".strip()
                + "\n",
                encoding="utf-8",
            )
            output_dir = tmp_path / "docs/api"

            generator = auto_docs_gen.APIDocumentGenerator(
                source_files=[source_file],
                output_dirs=[output_dir],
                quiet=True,
            )
            generator.extract_apis()
            generator.generate_markdown_docs()

            readme = (output_dir / "README.md").read_text(encoding="utf-8")

            self.assertTrue((output_dir / "Const.md").exists())
            self.assertTrue((output_dir / "const_function.md").exists())
            self.assertIn("[Const](Const.md)", readme)
            self.assertIn("[const](const_function.md)", readme)

    def test_generate_markdown_includes_math_helper_category(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            init_file = tmp_path / "__init__.py"
            init_file.write_text(
                "__all__ = ['BSplineFitResult', 'fit_cubic_bspline_control_points']\n",
                encoding="utf-8",
            )
            source_file = tmp_path / "math.py"
            source_file.write_text(
                '''
class BSplineFitResult:
    """B-spline fitting result."""


def fit_cubic_bspline_control_points(sample_points, *, tolerance=1e-3):
    """Fit sampled points to cubic B-spline controls."""
    return BSplineFitResult()
'''.strip()
                + "\n",
                encoding="utf-8",
            )
            output_dir = tmp_path / "docs/api"

            generator = auto_docs_gen.APIDocumentGenerator(
                source_files=[source_file],
                output_dirs=[output_dir],
                quiet=True,
            )
            generator.extract_apis()
            generator.generate_markdown_docs()

            readme = (output_dir / "README.md").read_text(encoding="utf-8")

            self.assertIn("## Math Helpers", readme)
            self.assertIn("[BSplineFitResult](BSplineFitResult.md)", readme)
            self.assertIn(
                "[fit_cubic_bspline_control_points](fit_cubic_bspline_control_points.md)",
                readme,
            )

    def test_generate_markdown_includes_physical_units_category(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            init_file = tmp_path / "__init__.py"
            init_file.write_text(
                "__all__ = ['Dimension', 'convert_value']\n", encoding="utf-8"
            )
            source_file = tmp_path / "units.py"
            source_file.write_text(
                '''
class Dimension:
    """Physical dimension."""


def convert_value(value, from_unit, to_unit):
    """Convert compatible units."""
    return value
'''.strip()
                + "\n",
                encoding="utf-8",
            )
            output_dir = tmp_path / "docs/api"

            generator = auto_docs_gen.APIDocumentGenerator(
                source_files=[source_file], output_dirs=[output_dir], quiet=True
            )
            generator.extract_apis()
            generator.generate_markdown_docs()

            readme = (output_dir / "README.md").read_text(encoding="utf-8")

            self.assertIn("## Physical Units", readme)
            self.assertIn("[Dimension](Dimension.md)", readme)
            self.assertIn("[convert_value](convert_value.md)", readme)

    def test_generate_stdlib_markdown_uses_stdlib_index_and_import_surface(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source_dir = tmp_path / "std"
            source_dir.mkdir()
            source_file = source_dir / "gear.py"
            source_file.write_text(
                '''
def make_spur_gear_rsolid(n_teeth: int, module: float):
    """Create a test spur gear.

    Parameters
    ----------
    n_teeth : int
        Number of teeth.
    module : float
        Gear module.
    """
    return None


def _private_helper():
    """Should not be documented."""
    return None
'''.strip()
                + "\n",
                encoding="utf-8",
            )
            output_dir = tmp_path / "docs/stdlib"

            generator = auto_docs_gen.StdlibDocumentGenerator(
                source_files=[source_file],
                output_dirs=[output_dir],
                quiet=True,
            )
            generator.extract_apis()
            generator.generate_markdown_docs()

            readme = (output_dir / "README.md").read_text(encoding="utf-8")
            page = (output_dir / "make_spur_gear_rsolid.md").read_text(
                encoding="utf-8"
            )

            self.assertIn("# SimpleCAD Standard Library Index", readme)
            self.assertIn("[make_spur_gear_rsolid](make_spur_gear_rsolid.md)", readme)
            self.assertIn("scad.std.gear.make_spur_gear_rsolid", page)
            self.assertIn("**Type**: `int`", page)
            self.assertNotIn("_private_helper", readme)


if __name__ == "__main__":
    unittest.main()
