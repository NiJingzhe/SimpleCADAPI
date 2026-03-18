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


if __name__ == "__main__":
    unittest.main()
