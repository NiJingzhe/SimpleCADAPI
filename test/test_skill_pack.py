import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src/simplecadapi/auto_tools/skill_pack.py"
)
MODULE_SPEC = importlib.util.spec_from_file_location(
    "simplecadapi_skill_pack",
    MODULE_PATH,
)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load module spec for {MODULE_PATH}")

skill_pack = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = skill_pack
MODULE_SPEC.loader.exec_module(skill_pack)


class TestSkillPackPathResolution(unittest.TestCase):
    def test_default_project_root_from_source_checkout(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            (project_root / "pyproject.toml").write_text(
                "[project]\nname = 'simplecadapi'\n",
                encoding="utf-8",
            )
            package_root = project_root / "src/simplecadapi"
            module_file = package_root / "auto_tools/skill_pack.py"
            module_file.parent.mkdir(parents=True, exist_ok=True)
            module_file.write_text("", encoding="utf-8")

            resolved = skill_pack._default_project_root(module_file)

            self.assertEqual(resolved, project_root.resolve())

    def test_default_project_root_from_site_packages_install(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            site_packages = Path(tmp_dir) / ".venv/lib/python3.12/site-packages"
            module_file = site_packages / "simplecadapi/auto_tools/skill_pack.py"
            module_file.parent.mkdir(parents=True, exist_ok=True)
            module_file.write_text("", encoding="utf-8")

            resolved = skill_pack._default_project_root(module_file)

            self.assertEqual(resolved, site_packages.resolve())

    def test_default_output_root_from_source_checkout(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            (project_root / "pyproject.toml").write_text(
                "[project]\nname = 'simplecadapi'\n",
                encoding="utf-8",
            )
            (project_root / "src/simplecadapi").mkdir(parents=True, exist_ok=True)

            resolved = skill_pack._default_output_root(project_root)

            self.assertEqual(resolved, (project_root / "skills").resolve())

    def test_default_output_root_from_site_packages_install(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            site_packages = tmp_path / ".venv/lib/python3.12/site-packages"
            site_packages.mkdir(parents=True, exist_ok=True)
            workspace_root = tmp_path / "workspace"
            workspace_root.mkdir()

            resolved = skill_pack._default_output_root(
                site_packages,
                cwd=workspace_root,
            )

            self.assertEqual(resolved, (workspace_root / "skills").resolve())

    def test_build_from_site_packages_layout_uses_metadata_readme(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            site_packages = tmp_path / ".venv/lib/python3.12/site-packages"
            docs_api = site_packages / "docs/api"
            docs_core = site_packages / "docs/core"
            docs_api.mkdir(parents=True, exist_ok=True)
            docs_core.mkdir(parents=True, exist_ok=True)
            (docs_api / "README.md").write_text("# API Docs\n", encoding="utf-8")
            (docs_core / "README.md").write_text("# Core Docs\n", encoding="utf-8")

            dist_info = site_packages / "simplecadapi-2.0.2.dist-info"
            (dist_info / "licenses").mkdir(parents=True, exist_ok=True)
            (dist_info / "METADATA").write_text(
                "Metadata-Version: 2.1\n"
                "Name: simplecadapi\n"
                "Version: 2.0.2\n"
                "Summary: Demo package\n"
                "\n"
                "# Demo README\n"
                "\n"
                "Installed package readme body.\n",
                encoding="utf-8",
            )
            (dist_info / "licenses/LICENSE").write_text(
                "MIT License\n",
                encoding="utf-8",
            )

            output_root = tmp_path / "workspace/skills"
            packager = skill_pack.SkillPackager(
                project_root=site_packages,
                output_root=output_root,
                skill_name="simplecad-self-evolve",
                license_name="MIT",
                package_name="simplecadapi",
                package_version="2.0.2",
                refresh_docs=True,
                quiet=True,
            )

            result = packager.build()

            self.assertTrue((result.skill_root / "SKILL.md").exists())
            self.assertTrue(
                (result.skill_root / "references/docs/api/README.md").exists()
            )
            self.assertEqual(
                (result.skill_root / "references/PROJECT_README.md").read_text(
                    encoding="utf-8"
                ),
                "# Demo README\n\nInstalled package readme body.",
            )
            self.assertEqual(
                (result.skill_root / "references/LICENSE.txt").read_text(
                    encoding="utf-8"
                ),
                "MIT License\n",
            )


if __name__ == "__main__":
    unittest.main()
