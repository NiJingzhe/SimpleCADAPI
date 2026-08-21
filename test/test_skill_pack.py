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


def _make_skill_layer(project_root: Path) -> None:
    """Create a minimal docs/skill tree so packager validation passes."""
    skill_dir = project_root / "docs/skill"
    for sub, names in (
        ("domains", skill_pack.SKILL_DOMAINS),
        ("workflows", skill_pack.SKILL_WORKFLOWS),
        ("discipline", skill_pack.SKILL_DISCIPLINES),
    ):
        (skill_dir / sub).mkdir(parents=True, exist_ok=True)
        for name in names:
            (skill_dir / sub / f"{name}.md").write_text(
                f"# {name}\n",
                encoding="utf-8",
            )


class TestSkillPackPathResolution(unittest.TestCase):
    def test_checked_in_skill_markdown_matches_generator(self):
        project_root = MODULE_PATH.parents[3]
        packager = skill_pack.SkillPackager(
            project_root=project_root,
            output_root=project_root / "unused-skill-output",
            skill_name="simplecadapi",
            license_name=skill_pack.DEFAULT_LICENSE,
            quiet=True,
        )

        generated = packager._build_skill_markdown()
        checked_in = (project_root / "skills/simplecadapi/SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(checked_in, generated)

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
            docs_stdlib = site_packages / "docs/stdlib"
            docs_api.mkdir(parents=True, exist_ok=True)
            docs_core.mkdir(parents=True, exist_ok=True)
            docs_stdlib.mkdir(parents=True, exist_ok=True)
            (docs_api / "README.md").write_text("# API Docs\n", encoding="utf-8")
            (docs_core / "README.md").write_text("# Core Docs\n", encoding="utf-8")
            (docs_stdlib / "README.md").write_text(
                "# Standard Library Docs\n",
                encoding="utf-8",
            )
            _make_skill_layer(site_packages)
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
                skill_name="simplecadapi",
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
            self.assertTrue(
                (result.skill_root / "references/docs/stdlib/README.md").exists()
            )
            self.assertTrue(
                (
                    result.skill_root / "references/inspect/brep-reverse-engineering.md"
                ).exists()
            )
            overview = (
                result.skill_root / "references/SDK_OVERVIEW.md"
            ).read_text(encoding="utf-8")
            self.assertIn("# SDK Overview", overview)
            self.assertIn("references/docs/", overview)
            self.assertTrue(
                (result.skill_root / "references/domains/part-modeling.md").exists()
            )
            self.assertEqual(
                (result.skill_root / "references/LICENSE.txt").read_text(
                    encoding="utf-8"
                ),
                "MIT License\n",
            )
            self.assertFalse((result.skill_root / "scripts").exists())

    def test_build_skill_markdown_routes_tasks_to_workflows(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            project_root = tmp_path / "project"
            docs_api = project_root / "docs/api"
            docs_core = project_root / "docs/core"
            docs_stdlib = project_root / "docs/stdlib"
            docs_guides = project_root / "docs/guides"
            docs_api.mkdir(parents=True, exist_ok=True)
            docs_core.mkdir(parents=True, exist_ok=True)
            docs_stdlib.mkdir(parents=True, exist_ok=True)
            docs_guides.mkdir(parents=True, exist_ok=True)
            (docs_api / "README.md").write_text("# API Docs\n", encoding="utf-8")
            (docs_core / "README.md").write_text("# Core Docs\n", encoding="utf-8")
            (docs_stdlib / "README.md").write_text(
                "# Standard Library Docs\n",
                encoding="utf-8",
            )
            (docs_guides / "reconstruction-agent-test-prompt.md").write_text(
                "# Reconstruction Contract\n",
                encoding="utf-8",
            )
            (docs_guides / "reconstruction-agent-strategy.md").write_text(
                "# Reconstruction Strategy\n",
                encoding="utf-8",
            )
            (project_root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (project_root / "LICENSE").write_text("MIT\n", encoding="utf-8")
            (project_root / "pyproject.toml").write_text(
                "[project]\nname = 'simplecadapi'\nversion = '2.0.9'\ndescription = 'Demo package'\n",
                encoding="utf-8",
            )
            (project_root / "src/simplecadapi").mkdir(parents=True, exist_ok=True)

            packager = skill_pack.SkillPackager(
                project_root=project_root,
                output_root=tmp_path / "skills",
                skill_name="simplecadapi",
                license_name="MIT",
                quiet=True,
            )

            content = packager._build_skill_markdown()

            # Routing table maps every workflow file.
            for workflow in skill_pack.SKILL_WORKFLOWS:
                self.assertIn(f"workflows/{workflow}.md", content)
            # Router must not force-read full API indexes up front.
            self.assertIn("Do not read the full API index", content)
            self.assertIn("Task routing", content)
            self.assertIn("Global rules", content)
            # Global rules keep the load-bearing contracts.
            self.assertIn("capture(result, path)", content)
            self.assertIn("positional", content)
            self.assertIn("@scad.part", content)
            self.assertIn("@scad.assemble", content)
            self.assertIn("scad.std.gear", content)
            self.assertIn("scad.std.bearing", content)
            self.assertIn("simplecadapi.inspect.brep", content)
            self.assertIn("cache-build-workflow.md", content)
            self.assertIn("GraphSession", content)
            self.assertIn("export_model_json", content)
            self.assertIn("replay_model_json", content)
            # Verified behavior: union glue default and tag scope.
            self.assertIn("glue=False", content)
            self.assertIn("never propagates downward", content)
            # Replaced legacy generated files are gone from the router.
            self.assertNotIn("SDK_SURFACES.md", content)
            self.assertNotIn("MODELING_WORKFLOWS.md", content)
            self.assertNotIn("SDK_PACKAGE_SUMMARY.md", content)
            self.assertNotIn("ModelResult", content)
            self.assertNotIn("@model", content)
            self.assertNotIn("scripts/", content)

    def test_build_copies_skill_layer_and_validates_all_pages(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            project_root = tmp_path / "project"
            docs_api = project_root / "docs/api"
            docs_core = project_root / "docs/core"
            docs_stdlib = project_root / "docs/stdlib"
            docs_api.mkdir(parents=True, exist_ok=True)
            docs_core.mkdir(parents=True, exist_ok=True)
            docs_stdlib.mkdir(parents=True, exist_ok=True)
            (docs_api / "README.md").write_text("# API Docs\n", encoding="utf-8")
            (docs_core / "README.md").write_text("# Core Docs\n", encoding="utf-8")
            (docs_stdlib / "README.md").write_text(
                "# Standard Library Docs\n",
                encoding="utf-8",
            )
            skill_dir = project_root / "docs/skill"
            for sub, names in (
                ("domains", skill_pack.SKILL_DOMAINS),
                ("workflows", skill_pack.SKILL_WORKFLOWS),
                ("discipline", skill_pack.SKILL_DISCIPLINES),
            ):
                (skill_dir / sub).mkdir(parents=True, exist_ok=True)
                for name in names:
                    (skill_dir / sub / f"{name}.md").write_text(
                        f"# {name}\n",
                        encoding="utf-8",
                    )
            (project_root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (project_root / "LICENSE").write_text("MIT\n", encoding="utf-8")
            (project_root / "pyproject.toml").write_text(
                "[project]\nname = 'simplecadapi'\nversion = '2.0.9'\ndescription = 'Demo package'\n",
                encoding="utf-8",
            )
            (project_root / "src/simplecadapi").mkdir(parents=True, exist_ok=True)

            packager = skill_pack.SkillPackager(
                project_root=project_root,
                output_root=tmp_path / "skills",
                skill_name="simplecadapi",
                license_name="MIT",
                quiet=True,
            )

            result = packager.build()

            refs = result.skill_root / "references"
            for name in skill_pack.SKILL_DOMAINS:
                self.assertTrue((refs / "domains" / f"{name}.md").is_file())
            for name in skill_pack.SKILL_WORKFLOWS:
                self.assertTrue((refs / "workflows" / f"{name}.md").is_file())
            for name in skill_pack.SKILL_DISCIPLINES:
                self.assertTrue((refs / "discipline" / f"{name}.md").is_file())
            # The skill layer is copied to references/ top level, not duplicated
            # under references/docs/.
            self.assertFalse((refs / "docs" / "skill").exists())
            self.assertTrue((refs / "README.md").is_file())

    def test_build_fails_when_skill_layer_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            project_root = tmp_path / "project"
            docs_api = project_root / "docs/api"
            docs_core = project_root / "docs/core"
            docs_stdlib = project_root / "docs/stdlib"
            docs_api.mkdir(parents=True, exist_ok=True)
            docs_core.mkdir(parents=True, exist_ok=True)
            docs_stdlib.mkdir(parents=True, exist_ok=True)
            (docs_api / "README.md").write_text("# API Docs\n", encoding="utf-8")
            (docs_core / "README.md").write_text("# Core Docs\n", encoding="utf-8")
            (docs_stdlib / "README.md").write_text(
                "# Standard Library Docs\n",
                encoding="utf-8",
            )
            (project_root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (project_root / "LICENSE").write_text("MIT\n", encoding="utf-8")
            (project_root / "pyproject.toml").write_text(
                "[project]\nname = 'simplecadapi'\nversion = '2.0.9'\ndescription = 'Demo package'\n",
                encoding="utf-8",
            )
            (project_root / "src/simplecadapi").mkdir(parents=True, exist_ok=True)

            packager = skill_pack.SkillPackager(
                project_root=project_root,
                output_root=tmp_path / "skills",
                skill_name="simplecadapi",
                license_name="MIT",
                quiet=True,
            )

            with self.assertRaises(FileNotFoundError):
                packager.build()


if __name__ == "__main__":
    unittest.main()
