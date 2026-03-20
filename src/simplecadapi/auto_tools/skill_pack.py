#!/usr/bin/env python3
"""Build a thin Agent Skills bundle for SimpleCAD API.

This packager intentionally does not bundle SDK source code.
The generated skill contains docs, SKILL.md, and helper scripts. Runtime code is
installed from PyPI into the active virtual environment site-packages.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tarfile
import textwrap
from dataclasses import dataclass
from email import message_from_string
from pathlib import Path
from typing import Sequence, cast

try:
    import tomllib  # Python 3.11+  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

DEFAULT_PACKAGE_NAME = "simplecadapi"
DEFAULT_SKILL_NAME = "simplecad-self-evolve"
DEFAULT_LICENSE = "MIT"
DEFAULT_JUPYTER_DEPS: tuple[str, ...] = (
    "jupyterlab>=4.5.5",
    "ipykernel>=6.29.5",
)

DOCS_PATH = Path("docs")
README_PATH = Path("README.md")
LICENSE_PATH = Path("LICENSE")

SKILL_NAME_PATTERN = re.compile(r"^(?!-)(?!.*--)[a-z0-9]+(?:-[a-z0-9]+)*$")


def _package_root_from(module_file: Path | str | None = None) -> Path:
    target = Path(module_file) if module_file is not None else Path(__file__)
    return target.resolve().parents[1]


def _is_source_checkout_root(project_root: Path) -> bool:
    return (project_root / "pyproject.toml").exists() and (
        project_root / "src" / DEFAULT_PACKAGE_NAME
    ).exists()


def _source_checkout_root(package_root: Path) -> Path | None:
    src_dir = package_root.parent
    project_root = src_dir.parent

    if src_dir.name != "src":
        return None
    if not _is_source_checkout_root(project_root):
        return None
    return project_root


def _default_project_root(module_file: Path | str | None = None) -> Path:
    package_root = _package_root_from(module_file)
    return _source_checkout_root(package_root) or package_root.parent


def _default_output_root(project_root: Path, cwd: Path | None = None) -> Path:
    if _is_source_checkout_root(project_root):
        return (project_root / "skills").resolve()
    return ((cwd if cwd is not None else Path.cwd()) / "skills").resolve()


def _first_existing_path(candidates: Sequence[Path]) -> Path | None:
    for path in candidates:
        if path.exists():
            return path
    return None


def _docs_root_for(project_root: Path) -> Path:
    docs_root = _first_existing_path(
        (
            project_root / DOCS_PATH,
            project_root / "src" / DOCS_PATH,
        )
    )
    return docs_root or (project_root / DOCS_PATH)


def _readme_path_for(project_root: Path) -> Path | None:
    return _first_existing_path(
        (
            project_root / README_PATH,
            project_root / "src" / README_PATH,
        )
    )


def _normalize_dist_name(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()


def _dist_info_dir(project_root: Path, package_name: str) -> Path | None:
    candidates: list[Path] = []
    patterns = (
        f"{package_name}-*.dist-info",
        f"{package_name.replace('-', '_')}-*.dist-info",
        f"{_normalize_dist_name(package_name)}-*.dist-info",
    )

    for pattern in patterns:
        for path in sorted(project_root.glob(pattern)):
            if path not in candidates:
                candidates.append(path)

    return candidates[0] if candidates else None


def _license_path_for(project_root: Path, package_name: str) -> Path | None:
    dist_info_dir = _dist_info_dir(project_root, package_name)
    candidates = [project_root / LICENSE_PATH]
    if dist_info_dir is not None:
        candidates.extend(
            [
                dist_info_dir / "licenses" / LICENSE_PATH.name,
                dist_info_dir / LICENSE_PATH.name,
            ]
        )
    return _first_existing_path(tuple(candidates))


def _auto_docs_script_path_for(project_root: Path) -> Path | None:
    return _first_existing_path(
        (
            project_root
            / "src"
            / DEFAULT_PACKAGE_NAME
            / "auto_tools"
            / "auto_docs_gen.py",
            project_root / DEFAULT_PACKAGE_NAME / "auto_tools" / "auto_docs_gen.py",
        )
    )


@dataclass(frozen=True)
class ProjectMetadata:
    """Project metadata used for skill rendering."""

    name: str
    version: str
    description: str
    readme_text: str | None = None


@dataclass(frozen=True)
class BuildResult:
    """Result object for completed build."""

    skill_root: Path
    archive_path: Path | None


def _load_project_metadata(
    project_root: Path,
    default_name: str = DEFAULT_PACKAGE_NAME,
) -> ProjectMetadata:
    pyproject_path = project_root / "pyproject.toml"

    default_version = "0.0.0"
    default_desc = "SimpleCAD skill runtime installer and docs"

    if not pyproject_path.exists():
        return ProjectMetadata(default_name, default_version, default_desc)

    if tomllib is not None:
        try:
            data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            project = data.get("project", {})
            return ProjectMetadata(
                name=str(project.get("name") or default_name),
                version=str(project.get("version") or default_version),
                description=str(project.get("description") or default_desc),
                readme_text=None,
            )
        except Exception:
            pass

    content = pyproject_path.read_text(encoding="utf-8")
    name_match = re.search(
        r'^\s*name\s*=\s*"(?P<name>[^"]+)"\s*$',
        content,
        flags=re.MULTILINE,
    )
    version_match = re.search(
        r'^\s*version\s*=\s*"(?P<version>[^"]+)"\s*$',
        content,
        flags=re.MULTILINE,
    )
    description_match = re.search(
        r'^\s*description\s*=\s*"(?P<description>[^"]+)"\s*$',
        content,
        flags=re.MULTILINE,
    )

    return ProjectMetadata(
        name=name_match.group("name") if name_match else default_name,
        version=version_match.group("version") if version_match else default_version,
        description=(
            description_match.group("description")
            if description_match
            else default_desc
        ),
        readme_text=None,
    )


def _load_installed_metadata(
    project_root: Path,
    package_name: str = DEFAULT_PACKAGE_NAME,
) -> ProjectMetadata | None:
    dist_info_dir = _dist_info_dir(project_root, package_name)
    if dist_info_dir is None:
        return None

    metadata_path = dist_info_dir / "METADATA"
    if not metadata_path.exists():
        return None

    message = message_from_string(metadata_path.read_text(encoding="utf-8"))
    payload = cast(str, message.get_payload())
    readme_text = payload.strip() or None
    return ProjectMetadata(
        name=message.get("Name", package_name),
        version=message.get("Version", "0.0.0"),
        description=message.get(
            "Summary", "SimpleCAD skill runtime installer and docs"
        ),
        readme_text=readme_text,
    )


def _ignore_common_noise(_: str, names: list[str]) -> list[str]:
    ignored: list[str] = []
    for name in names:
        if name in {"__pycache__", ".DS_Store"}:
            ignored.append(name)
            continue
        if name.endswith(".pyc"):
            ignored.append(name)
    return ignored


class SkillPackager:
    """Build thin skill bundle: docs + SKILL.md + scripts."""

    def __init__(
        self,
        project_root: Path,
        output_root: Path,
        skill_name: str,
        license_name: str,
        package_name: str | None = None,
        package_version: str | None = None,
        jupyter_deps: tuple[str, ...] = DEFAULT_JUPYTER_DEPS,
        clean: bool = True,
        refresh_docs: bool = False,
        archive: bool = False,
        quiet: bool = False,
    ):
        self.project_root = project_root.resolve()
        self.output_root = output_root.resolve()
        self.skill_name = skill_name
        self.license_name = license_name
        self.clean = clean
        self.refresh_docs = refresh_docs
        self.archive = archive
        self.quiet = quiet

        self.skill_root = self.output_root / self.skill_name
        self.scripts_dir = self.skill_root / "scripts"
        self.references_dir = self.skill_root / "references"
        self.docs_dir = self.references_dir / "docs"
        self.cases_root = self.skill_root / "cases"
        self.cases_module = self._cases_module_name()
        self.cases_module_dir = self.cases_root / self.cases_module

        self.source_checkout = _is_source_checkout_root(self.project_root)
        default_package_name = package_name or DEFAULT_PACKAGE_NAME
        self.metadata = _load_project_metadata(
            self.project_root,
            default_name=default_package_name,
        )
        if self.metadata.version == "0.0.0":
            installed_metadata = _load_installed_metadata(
                self.project_root,
                package_name=default_package_name,
            )
            if installed_metadata is not None:
                self.metadata = installed_metadata

        self.package_name = package_name or self.metadata.name
        self.package_version = package_version or self.metadata.version
        self.jupyter_deps = jupyter_deps
        self.source_docs = _docs_root_for(self.project_root)
        self.source_readme = _readme_path_for(self.project_root)
        self.source_license = _license_path_for(self.project_root, self.package_name)

    def log(self, message: str) -> None:
        if not self.quiet:
            print(message)

    def build(self) -> BuildResult:
        self._validate_inputs()

        if self.refresh_docs:
            self._refresh_api_docs()

        self._prepare_output_directory()
        self._copy_reference_docs()
        self._write_skill_markdown()
        self._write_reference_files()
        self._write_case_package()
        self._write_scripts()
        self._validate_generated_skill()

        archive_path = self._create_archive() if self.archive else None
        return BuildResult(self.skill_root, archive_path)

    def _validate_inputs(self) -> None:
        if len(self.skill_name) > 64:
            raise ValueError("skill_name must be <= 64 characters")
        if not SKILL_NAME_PATTERN.fullmatch(self.skill_name):
            raise ValueError(
                "skill_name must use lowercase letters, numbers, and single hyphens"
            )

        required = (
            self.source_docs,
            self.source_docs / "api",
            self.source_docs / "core",
        )
        for path in required:
            if not path.exists():
                raise FileNotFoundError(f"Missing required path: {path}")

        if self.source_readme is None and not self.metadata.readme_text:
            raise FileNotFoundError(
                "Missing required project README content in both project files and dist-info metadata"
            )

        if self.source_license is None:
            raise FileNotFoundError(
                "Missing required license file in both project files and dist-info metadata"
            )

    def _refresh_api_docs(self) -> None:
        if not self.source_checkout:
            self.log(
                "Using packaged docs from installed simplecadapi; skipped --refresh-docs outside source checkout."
            )
            return

        script_path = _auto_docs_script_path_for(self.project_root)
        if script_path is None:
            raise FileNotFoundError(f"Cannot refresh docs, missing: {script_path}")

        self.log("Refreshing API docs before packaging...")
        try:
            subprocess.run(
                [sys.executable, str(script_path), "--quiet"],
                cwd=str(self.project_root),
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("Failed to refresh API docs") from exc

    def _prepare_output_directory(self) -> None:
        if self.skill_root.exists() and self.clean:
            self.log(f"Removing existing skill directory: {self.skill_root}")
            shutil.rmtree(self.skill_root)

        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.references_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.cases_module_dir.mkdir(parents=True, exist_ok=True)
        self.log(f"Writing skill bundle to: {self.skill_root}")

    def _copy_reference_docs(self) -> None:
        self.log("Copying reference docs...")
        target_docs = self.docs_dir
        shutil.copytree(
            self.source_docs,
            target_docs,
            dirs_exist_ok=True,
            ignore=_ignore_common_noise,
        )

        if self.source_readme is not None:
            shutil.copy2(self.source_readme, self.references_dir / "PROJECT_README.md")
        else:
            (self.references_dir / "PROJECT_README.md").write_text(
                self.metadata.readme_text or "",
                encoding="utf-8",
            )

        if self.source_license is None:
            raise FileNotFoundError(
                "Missing required license file in both project files and dist-info metadata"
            )
        shutil.copy2(self.source_license, self.references_dir / "LICENSE.txt")

    def _write_skill_markdown(self) -> None:
        self.log("Generating SKILL.md...")
        (self.skill_root / "SKILL.md").write_text(
            self._build_skill_markdown(),
            encoding="utf-8",
        )

    def _write_reference_files(self) -> None:
        self.log("Generating overview references...")
        (self.references_dir / "PROJECT_OVERVIEW.md").write_text(
            self._build_project_overview(),
            encoding="utf-8",
        )
        (self.references_dir / "RUNTIME_INSTALL.md").write_text(
            self._build_runtime_install_reference(),
            encoding="utf-8",
        )
        (self.references_dir / "EVOLVE_WORKFLOW.md").write_text(
            self._build_evolve_workflow_reference(),
            encoding="utf-8",
        )

    def _write_case_package(self) -> None:
        self.log("Generating skill-local evolve cases package...")
        (self.cases_module_dir / "__init__.py").write_text(
            self._build_cases_init(),
            encoding="utf-8",
        )
        (self.cases_module_dir / "evolve.py").write_text(
            self._build_cases_evolve_module(),
            encoding="utf-8",
        )

    def _write_scripts(self) -> None:
        self.log("Generating helper scripts...")
        scripts: dict[str, str] = {
            "install.sh": self._script_install(),
            "with_skill.sh": self._script_with_skill(),
            "jupyter_with_skill.sh": self._script_jupyter_with_skill(),
            "repl_bootstrap.py": self._script_repl_bootstrap(),
            "add_new_case.sh": self._script_add_new_case(),
            "evolve_case.py": self._script_evolve_case(),
            "validate_skill.sh": self._script_validate_skill(),
        }

        for name, content in scripts.items():
            path = self.scripts_dir / name
            path.write_text(content, encoding="utf-8")
            path.chmod(0o755)

    def _validate_generated_skill(self) -> None:
        self.log("Validating generated skill...")
        required = (
            self.skill_root / "SKILL.md",
            self.scripts_dir / "install.sh",
            self.scripts_dir / "with_skill.sh",
            self.scripts_dir / "jupyter_with_skill.sh",
            self.scripts_dir / "repl_bootstrap.py",
            self.scripts_dir / "add_new_case.sh",
            self.scripts_dir / "evolve_case.py",
            self.scripts_dir / "validate_skill.sh",
            self.references_dir / "PROJECT_OVERVIEW.md",
            self.references_dir / "RUNTIME_INSTALL.md",
            self.references_dir / "EVOLVE_WORKFLOW.md",
            self.references_dir / "PROJECT_README.md",
            self.references_dir / "LICENSE.txt",
            self.docs_dir / "api" / "README.md",
            self.docs_dir / "core" / "README.md",
            self.cases_module_dir / "__init__.py",
            self.cases_module_dir / "evolve.py",
        )

        for path in required:
            if not path.exists():
                raise FileNotFoundError(f"Generated skill is missing: {path}")

        forbidden = (
            self.skill_root / "assets" / "project_snapshot" / "src",
            self.skill_root / "src",
        )
        for path in forbidden:
            if path.exists():
                raise ValueError(f"Thin skill must not include source code: {path}")

        frontmatter = self._parse_frontmatter(
            (self.skill_root / "SKILL.md").read_text("utf-8")
        )
        if frontmatter.get("name", "") != self.skill_name:
            raise ValueError("SKILL.md frontmatter name does not match skill directory")
        if not frontmatter.get("description", ""):
            raise ValueError("SKILL.md frontmatter description is empty")

    def _cases_module_name(self) -> str:
        module_name = f"{self.skill_name.replace('-', '_')}_cases"
        if module_name and module_name[0].isdigit():
            module_name = f"skill_{module_name}"
        return module_name

    def _create_archive(self) -> Path:
        archive_path = self.output_root / f"{self.skill_name}.tar.gz"
        self.log(f"Creating archive: {archive_path}")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(self.skill_root, arcname=self.skill_name)
        return archive_path

    def _build_skill_markdown(self) -> str:
        package_spec = self._package_spec()
        deps_for_doc = ", ".join(self.jupyter_deps)
        cases_module = self.cases_module

        body = textwrap.dedent(
            f"""\
            ---
            name: {self.skill_name}
            description: Thin SimpleCAD skill that installs runtime SDK from PyPI into current venv site-packages, then provides deterministic REPL/Jupyter usage and references.
            license: {self.license_name}
            compatibility: Requires Python 3.10+, active virtual environment, and network access for package installation.
            metadata:
              project: {self.metadata.name}
              version: {self.metadata.version}
              runtime-package: {self.package_name}
              runtime-spec: {package_spec}
              cases-module: {cases_module}
            ---

            # SimpleCAD Runtime Skill

            ## Philosophy
            - This is a thin skill package: docs + scripts only.
            - SDK source code is not bundled in this skill.
            - Runtime code is installed from PyPI into active virtual environment site-packages.
            - Skill-local evolved cases are stored under `cases/{cases_module}/`.

            ## Working From Repo Root
            - Tool calls run from the repo root.
            - Use one explicit skill root: `./skills/{self.skill_name}/` or `./workspace/skills/{self.skill_name}/`.
            - Main doc paths:
              - `<skill_root>/SKILL.md`
              - `<skill_root>/references/docs/api/README.md`
              - `<skill_root>/references/docs/api/<api_name>.md`
              - `<skill_root>/references/docs/core/<type_name>.md`
            - Skill layout also includes `<skill_root>/scripts/` and `<skill_root>/cases/`.

            ## MUST Requirements
            1. Read `SKILL.md` and `references/docs/api/README.md` before choosing APIs.
            2. Read the exact API Markdown page for every API you use.
            3. Read the needed `core/` and tag/selection docs when an API needs `Edge`, `Face`, `Wire`, `Solid`, `Assembly`, or tags.
            4. Follow the documented API signatures exactly.
            5. Use geometry APIs for integrated parts and declarative constraints for final assemblies.
            6. Use tags consistently.
            7. Build and validate incrementally. Each step MUST include a small grounding `print`, and grounding MUST use QL where possible.
            8. For inspection/debugging, query geometry with QL and print only the queried facts you need; do not print whole solids, assemblies, or full model objects.
            9. After model construction, ask the user whether the result is satisfactory and whether any modifications are needed. Only after explicit user confirmation may you add the script to evolve cases.

            ## Install behavior
            - Preferred: run `scripts/install.sh` once when skill is installed/activated.
            - Runtime wrappers auto-install on demand if `simplecadapi` is missing.
            - Package installed by default: `{package_spec}`
            - Wrappers install only into a virtual environment interpreter (set `PYTHON_BIN` when needed).

            ## Interpreter selection
            Use the interpreter from your active/current venv site-packages. Example:

            ```bash
            PYTHON_BIN=.venv/bin/python scripts/install.sh
            PYTHON_BIN=.venv/bin/python scripts/with_skill.sh --check
            ```

            ## Skill path activation
            To activate this skill path in current shell:

            ```bash
            eval "$(scripts/with_skill.sh --print-env)"
            ```

            This exports `SIMPLECAD_SKILL_ROOT`, `SIMPLECAD_CASES_ROOT`, `SIMPLECAD_CASES_MODULE`, and updates `PYTHONPATH`.

            ## How to import and use
            After runtime install, import normally (no custom `sys.path` needed):

            ```python
            import simplecadapi as scad
            from simplecadapi import make_box_rsolid, export_stl
            ```

            Typical usage in a Python script:

            ```python
            import simplecadapi as scad
            from simplecadapi import make_box_rsolid, export_stl

            shape = make_box_rsolid(10.0, 20.0, 30.0)
            export_stl(shape, "example_box.stl")
            ```

            Import skill-local evolved cases:

            ```python
            from {cases_module}.evolve import my_new_case
            ```

            Run script with wrapper (auto-installs runtime when missing):

            ```bash
            PYTHON_BIN=.venv/bin/python scripts/with_skill.sh -- .venv/bin/python your_script.py
            ```

            Quick import check in current venv:

            ```bash
            PYTHON_BIN=.venv/bin/python scripts/with_skill.sh --check
            ```

            ## Self-evolve in skill directory
            Add a new case function from a local Python script:

            ```bash
            scripts/add_new_case.sh path/to/new_case.py
            ```

            By default, the first top-level function in that file is appended into:
            - `cases/{cases_module}/evolve.py`

            Then import it with:

            ```python
            from {cases_module}.evolve import your_function_name
            ```

            ## Persistent REPL / notebook kernel
            In a long-running kernel session, bootstrap once in first cell:

            ```python
            %run ./scripts/repl_bootstrap.py
            import simplecadapi as scad
            from {cases_module}.evolve import my_new_case
            ```

            If your kernel also needs notebook tools installed in this environment:

            ```python
            %run ./scripts/repl_bootstrap.py --with-jupyter
            ```

            ## Jupyter launch
            - `scripts/jupyter_with_skill.sh lab`
            - `scripts/jupyter_with_skill.sh notebook`
            - This wrapper ensures runtime package and Jupyter deps (`{deps_for_doc}`) are available.

            ## Script quick reference
            - `scripts/install.sh`: install runtime package to active venv site-packages.
            - `scripts/with_skill.sh`: ensure runtime installed and run any command.
            - `scripts/jupyter_with_skill.sh`: launch Jupyter with automatic dependency bootstrapping.
            - `scripts/repl_bootstrap.py`: one-time activation helper for persistent Python sessions.
            - `scripts/add_new_case.sh`: append new function into skill-local evolve module.
            - `scripts/evolve_case.py`: Python extractor used by `add_new_case.sh`.
            - `scripts/validate_skill.sh`: validate skill structure.

            ## References
            - `references/PROJECT_OVERVIEW.md`
            - `references/RUNTIME_INSTALL.md`
            - `references/EVOLVE_WORKFLOW.md`
            - `references/docs/api/`
            - `references/docs/core/`
            - `references/PROJECT_README.md`
            """
        )
        return body.rstrip() + "\n"

    def _build_project_overview(self) -> str:
        package_spec = self._package_spec()
        cases_module = self.cases_module
        lines = [
            "# Project Overview",
            "",
            f"- Project: `{self.metadata.name}`",
            f"- Version: `{self.metadata.version}`",
            f"- Runtime package: `{package_spec}`",
            f"- Skill cases module: `{cases_module}`",
            "",
            "## What this skill bundles",
            "",
            "- Skill instructions (`SKILL.md`)",
            "- Helper scripts (`scripts/`)",
            "- Documentation references (`references/docs/`)",
            f"- Skill-local evolve package (`cases/{cases_module}/`)",
            "",
            "## What this skill does not bundle",
            "",
            "- SDK source code (`src/simplecadapi`) is intentionally excluded.",
            "- Runtime code is always resolved from site-packages.",
            "",
            "## Runtime bootstrap strategy",
            "",
            "0. Select a virtual environment interpreter (`PYTHON_BIN` if needed).",
            "1. Try `import simplecadapi`.",
            "2. If import fails, run `scripts/install.sh`.",
            '3. Activate skill paths (`eval "$(scripts/with_skill.sh --print-env)"`).',
            f"4. Import skill-local cases from `{cases_module}.evolve`.",
            "",
            "## Optional Jupyter dependencies",
            "",
        ]

        lines.extend(f"- `{dep}`" for dep in self.jupyter_deps)
        return "\n".join(lines).rstrip() + "\n"

    def _build_runtime_install_reference(self) -> str:
        package_spec = self._package_spec()
        cases_module = self.cases_module
        body = textwrap.dedent(
            f"""\
            # Runtime Install Reference

            ## Base install

            ```bash
            PYTHON_BIN=.venv/bin/python scripts/install.sh
            ```

            This installs `{package_spec}` to the active Python environment.
            If `PYTHON_BIN` is not set, wrappers default to `python3` (fallback `python`).
            Installation is intentionally blocked for non-venv/system interpreters.

            ## Install with Jupyter support

            ```bash
            PYTHON_BIN=.venv/bin/python scripts/install.sh --with-jupyter
            ```

            ## Upgrade package

            ```bash
            PYTHON_BIN=.venv/bin/python scripts/install.sh -- --upgrade
            ```

            Everything after `--` is forwarded to `uv pip install` (or `python -m pip install` fallback).

            ## Validate runtime

            ```bash
            PYTHON_BIN=.venv/bin/python scripts/with_skill.sh --check
            .venv/bin/python scripts/repl_bootstrap.py --check
            ```

            ## Activate skill paths in current shell

            ```bash
            eval "$(scripts/with_skill.sh --print-env)"
            ```

            ## Add and import skill-local evolved case

            ```bash
            scripts/add_new_case.sh path/to/new_case.py
            ```

            ```python
            from {cases_module}.evolve import your_function_name
            ```
            """
        )
        return body.rstrip() + "\n"

    def _build_evolve_workflow_reference(self) -> str:
        cases_module = self.cases_module
        body = textwrap.dedent(
            f"""\
            # Skill-Local Evolve Workflow

            This thin skill does not modify `site-packages/simplecadapi` directly.
            New evolve cases are stored in skill-local module:

            - `cases/{cases_module}/evolve.py`

            ## 1) Add a new case from a Python file

            ```bash
            scripts/add_new_case.sh path/to/new_case.py
            ```

            By default, the first top-level function in `new_case.py` is extracted.

            ## 2) Activate skill paths

            ```bash
            eval "$(scripts/with_skill.sh --print-env)"
            ```

            ## 3) Import and use in Python

            ```python
            import simplecadapi as scad
            from {cases_module}.evolve import your_function_name
            ```

            ## 4) Persistent kernel usage

            ```python
            %run ./scripts/repl_bootstrap.py
            from {cases_module}.evolve import your_function_name
            ```
            """
        )
        return body.rstrip() + "\n"

    def _build_cases_init(self) -> str:
        return (
            f'"""Skill-local evolved cases for {self.skill_name}."""\n\n'
            "from .evolve import *\n"
        )

    def _build_cases_evolve_module(self) -> str:
        body = textwrap.dedent(
            '''\
            """Skill-local evolved case functions.

            This module is managed by `scripts/add_new_case.sh` and `scripts/evolve_case.py`.
            """

            __all__: list[str] = []
            '''
        )
        return body.rstrip() + "\n"

    def _script_install(self) -> str:
        package_name = self.package_name
        package_version = self.package_version
        package_spec = self._package_spec()
        cases_module = self.cases_module
        jupyter_items = " ".join(f'"{item}"' for item in self.jupyter_deps)

        return (
            textwrap.dedent(
                f"""\
                #!/usr/bin/env bash
                set -euo pipefail

                SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
                SKILL_ROOT="$(cd "${{SCRIPT_DIR}}/.." && pwd)"
                PYTHON_BIN="${{PYTHON_BIN:-python3}}"

                if ! command -v "${{PYTHON_BIN}}" >/dev/null 2>&1; then
                  PYTHON_BIN="python"
                fi

                if ! command -v "${{PYTHON_BIN}}" >/dev/null 2>&1; then
                  echo "Error: python interpreter not found." >&2
                  exit 1
                fi

                PYTHON_BIN="$(command -v "${{PYTHON_BIN}}")"
                export PYTHON_BIN

                if ! "${{PYTHON_BIN}}" - <<'PY' >/dev/null 2>&1
                import sys
                raise SystemExit(0 if sys.prefix != sys.base_prefix else 1)
                PY
                then
                  echo "Error: target interpreter is not inside a virtual environment." >&2
                  echo "Hint: activate a venv first, or run with PYTHON_BIN=/path/to/venv/bin/python." >&2
                  exit 1
                fi

                export SIMPLECAD_SKILL_ROOT="${{SKILL_ROOT}}"
                export SIMPLECAD_RUNTIME_PACKAGE="{package_name}"
                export SIMPLECAD_CASES_ROOT="${{SKILL_ROOT}}/cases"
                export SIMPLECAD_CASES_MODULE="{cases_module}"

                PACKAGE_SPEC="{package_spec}"
                JUPYTER_DEPS=({jupyter_items})
                INSTALL_JUPYTER=0
                INSTALL_ARGS=()

                while [[ $# -gt 0 ]]; do
                  case "$1" in
                    --with-jupyter)
                      INSTALL_JUPYTER=1
                      shift
                      ;;
                    --)
                      shift
                      INSTALL_ARGS+=("$@")
                      break
                      ;;
                    *)
                      INSTALL_ARGS+=("$1")
                      shift
                      ;;
                  esac
                done

                if command -v uv >/dev/null 2>&1; then
                  INSTALL_CMD=(uv pip install --python "${{PYTHON_BIN}}")
                else
                  INSTALL_CMD=("${{PYTHON_BIN}}" -m pip install)
                fi

                run_install() {{
                  local targets=("$@")
                  if [[ ${{#INSTALL_ARGS[@]}} -gt 0 ]]; then
                    "${{INSTALL_CMD[@]}}" "${{INSTALL_ARGS[@]}}" "${{targets[@]}}"
                  else
                    "${{INSTALL_CMD[@]}}" "${{targets[@]}}"
                  fi
                }}

                echo "Installing runtime package: ${{PACKAGE_SPEC}}"
                run_install "${{PACKAGE_SPEC}}"

                if [[ "${{INSTALL_JUPYTER}}" == "1" ]]; then
                  echo "Installing Jupyter dependencies..."
                  run_install "${{JUPYTER_DEPS[@]}}"
                fi

                "${{PYTHON_BIN}}" - <<'PY'
                import simplecadapi as scad

                print("simplecadapi import OK")
                print(getattr(scad, "__description__", ""))
                PY

                echo "Runtime install completed for {package_name} {package_version}."
                """
            ).rstrip()
            + "\n"
        )

    def _script_with_skill(self) -> str:
        script = textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail

            SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
            SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
            CASES_ROOT="${SKILL_ROOT}/cases"
            CASES_MODULE="__CASES_MODULE__"
            PYTHON_BIN="${PYTHON_BIN:-python3}"

            if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
              PYTHON_BIN="python"
            fi

            if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
              echo "Error: python interpreter not found." >&2
              exit 1
            fi

            PYTHON_BIN="$(command -v "${PYTHON_BIN}")"
            export PYTHON_BIN

            export SIMPLECAD_SKILL_ROOT="${SKILL_ROOT}"
            export SIMPLECAD_CASES_ROOT="${CASES_ROOT}"
            export SIMPLECAD_CASES_MODULE="${CASES_MODULE}"

            case ":${PYTHONPATH:-}:" in
              *":${CASES_ROOT}:"*) ;;
              *) export PYTHONPATH="${CASES_ROOT}${PYTHONPATH:+:${PYTHONPATH}}" ;;
            esac

            MODE="run"
            ENSURE_JUPYTER=0

            while [[ $# -gt 0 ]]; do
              case "$1" in
                --print-env)
                  MODE="print-env"
                  shift
                  ;;
                --check)
                  MODE="check"
                  shift
                  ;;
                --ensure-jupyter)
                  ENSURE_JUPYTER=1
                  shift
                  ;;
                --)
                  shift
                  break
                  ;;
                *)
                  break
                  ;;
              esac
            done

            ensure_runtime() {
              if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
            import simplecadapi  # noqa: F401
            PY
              then
                echo "Runtime package missing, running scripts/install.sh ..."
                "${SCRIPT_DIR}/install.sh"
              fi
            }

            ensure_jupyter() {
              if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
            import jupyterlab  # noqa: F401
            import ipykernel  # noqa: F401
            PY
              then
                echo "Jupyter dependencies missing, running scripts/install.sh --with-jupyter ..."
                "${SCRIPT_DIR}/install.sh" --with-jupyter
              fi
            }

            if [[ "${MODE}" == "print-env" ]]; then
              printf 'export SIMPLECAD_SKILL_ROOT="%s"\\n' "${SIMPLECAD_SKILL_ROOT}"
              printf 'export SIMPLECAD_CASES_ROOT="%s"\\n' "${SIMPLECAD_CASES_ROOT}"
              printf 'export SIMPLECAD_CASES_MODULE="%s"\\n' "${SIMPLECAD_CASES_MODULE}"
              printf 'export PYTHONPATH="%s"\\n' "${PYTHONPATH}"
              exit 0
            fi

            ensure_runtime

            if [[ "${ENSURE_JUPYTER}" == "1" ]]; then
              ensure_jupyter
            fi

            if [[ "${MODE}" == "check" ]]; then
              "${PYTHON_BIN}" - <<'PY'
            import os
            import simplecadapi as scad

            print("Runtime check passed.")
            print(getattr(scad, "__description__", ""))
            print(f"Skill cases module: {os.environ.get('SIMPLECAD_CASES_MODULE', '')}")
            PY
              exit 0
            fi

            if [[ $# -eq 0 ]]; then
              echo "Skill runtime is ready in current environment."
              echo "Run command via wrapper: scripts/with_skill.sh -- ${PYTHON_BIN} your_script.py"
              echo 'Add skill env vars: eval "$(scripts/with_skill.sh --print-env)"'
              echo "Or check runtime: scripts/with_skill.sh --check"
              exit 0
            fi

            exec "$@"
            """
        )
        return script.replace("__CASES_MODULE__", self.cases_module).rstrip() + "\n"

    def _script_jupyter_with_skill(self) -> str:
        return (
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail

                SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
                PYTHON_BIN="${PYTHON_BIN:-python3}"

                if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
                  PYTHON_BIN="python"
                fi

                if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
                  echo "Error: python interpreter not found." >&2
                  exit 1
                fi

                PYTHON_BIN="$(command -v "${PYTHON_BIN}")"
                export PYTHON_BIN

                if [[ $# -lt 1 ]]; then
                  echo "Usage: scripts/jupyter_with_skill.sh <lab|notebook> [-- <extra args>]" >&2
                  exit 1
                fi

                JUPYTER_APP="$1"
                shift

                case "${JUPYTER_APP}" in
                  lab|notebook) ;;
                  *)
                    echo "Error: first argument must be 'lab' or 'notebook'." >&2
                    exit 1
                    ;;
                esac

                if [[ "${1:-}" == "--" ]]; then
                  shift
                fi

                exec "${SCRIPT_DIR}/with_skill.sh" --ensure-jupyter -- "${PYTHON_BIN}" -m jupyter "${JUPYTER_APP}" "$@"
                """
            ).rstrip()
            + "\n"
        )

    def _script_repl_bootstrap(self) -> str:
        package_spec = self._package_spec()
        cases_module = self.cases_module

        return (
            textwrap.dedent(
                f"""\
                #!/usr/bin/env python3
                \"\"\"Bootstrap runtime package in a persistent Python REPL/kernel.\"\"\"

                from __future__ import annotations

                import argparse
                import os
                import subprocess
                import sys
                from pathlib import Path


                PACKAGE_SPEC = "{package_spec}"
                CASES_MODULE = "{cases_module}"


                def _script_dir() -> Path:
                    return Path(__file__).resolve().parent


                def _cases_root() -> Path:
                    return _script_dir().parent / "cases"


                def _activate_cases_path() -> None:
                    cases_root = str(_cases_root())
                    os.environ["SIMPLECAD_CASES_ROOT"] = cases_root
                    os.environ["SIMPLECAD_CASES_MODULE"] = CASES_MODULE

                    current_pythonpath = os.environ.get("PYTHONPATH", "")
                    parts = [item for item in current_pythonpath.split(os.pathsep) if item]
                    if cases_root not in parts:
                        parts.insert(0, cases_root)
                        os.environ["PYTHONPATH"] = os.pathsep.join(parts)

                    if cases_root not in sys.path:
                        sys.path.insert(0, cases_root)


                def _install(with_jupyter: bool = False) -> None:
                    cmd = [str(_script_dir() / "install.sh")]
                    if with_jupyter:
                        cmd.append("--with-jupyter")
                    env = os.environ.copy()
                    env.setdefault("PYTHON_BIN", sys.executable)
                    subprocess.run(cmd, check=True, env=env)


                def _has_simplecadapi() -> bool:
                    try:
                        import simplecadapi  # noqa: F401
                    except Exception:
                        return False
                    return True


                def _has_jupyter_deps() -> bool:
                    try:
                        import jupyterlab  # noqa: F401
                        import ipykernel  # noqa: F401
                    except Exception:
                        return False
                    return True


                def activate(check: bool = False, with_jupyter: bool = False) -> int:
                    skill_root = _script_dir().parent
                    os.environ["SIMPLECAD_SKILL_ROOT"] = str(skill_root)
                    _activate_cases_path()

                    if not _has_simplecadapi():
                        print(f"Installing runtime package {{PACKAGE_SPEC}} ...")
                        _install(with_jupyter=with_jupyter)

                    if with_jupyter and not _has_jupyter_deps():
                        print("Installing Jupyter dependencies ...")
                        _install(with_jupyter=True)

                    if check and not _has_simplecadapi():
                        print("Runtime install failed: cannot import simplecadapi", file=sys.stderr)
                        return 1

                    print(f"Skill runtime activated from site-packages: {{PACKAGE_SPEC}}")
                    print(f"Skill cases module ready: {{CASES_MODULE}}.evolve")
                    print("You can now run: import simplecadapi as scad")
                    return 0


                def main() -> None:
                    parser = argparse.ArgumentParser(
                        description="Bootstrap SimpleCAD runtime in persistent Python process"
                    )
                    parser.add_argument(
                        "--check",
                        action="store_true",
                        help="Validate that import simplecadapi succeeds after bootstrap",
                    )
                    parser.add_argument(
                        "--with-jupyter",
                        action="store_true",
                        help="Also ensure jupyterlab and ipykernel are installed",
                    )
                    args = parser.parse_args()
                    raise SystemExit(activate(check=args.check, with_jupyter=args.with_jupyter))


                if __name__ == "__main__":
                    main()
                """
            ).rstrip()
            + "\n"
        )

    def _script_add_new_case(self) -> str:
        return (
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail

                SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
                PYTHON_BIN="${PYTHON_BIN:-python3}"

                if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
                  PYTHON_BIN="python"
                fi

                if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
                  echo "Error: python interpreter not found." >&2
                  exit 1
                fi

                PYTHON_BIN="$(command -v "${PYTHON_BIN}")"
                export PYTHON_BIN

                if [[ $# -lt 1 ]]; then
                  echo "Usage: scripts/add_new_case.sh <path-to-python-file> [--function <name>] [--target <path>]" >&2
                  exit 1
                fi

                exec "${SCRIPT_DIR}/with_skill.sh" -- "${PYTHON_BIN}" "${SCRIPT_DIR}/evolve_case.py" "$@"
                """
            ).rstrip()
            + "\n"
        )

    def _script_evolve_case(self) -> str:
        script = textwrap.dedent(
            r'''
            #!/usr/bin/env python3
            """Extract and append a new case function into skill-local evolve module."""

            from __future__ import annotations

            import argparse
            import ast
            from pathlib import Path


            CASES_MODULE = "__CASES_MODULE__"
            SKILL_ROOT = Path(__file__).resolve().parent.parent
            DEFAULT_TARGET = SKILL_ROOT / "cases" / CASES_MODULE / "evolve.py"


            def _read_text(path: Path) -> str:
                return path.read_text(encoding="utf-8")


            def _node_source(lines: list[str], node: ast.AST) -> str:
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", start)
                return "\n".join(lines[start - 1 : end])


            def _extract_header_imports(tree: ast.Module, lines: list[str]) -> list[str]:
                imports: list[str] = []
                for node in tree.body:
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        imports.append(_node_source(lines, node).strip())
                        continue
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        break
                return [item for item in imports if item]


            def _find_import_insert_index(lines: list[str]) -> int:
                if len(lines) <= 1:
                    return len(lines)

                index = 1
                while index < len(lines) and not lines[index].strip():
                    index += 1

                if index >= len(lines):
                    return 1

                triple_double = '"' * 3
                triple_single = "'" * 3

                stripped = lines[index].strip()
                if not (stripped.startswith(triple_double) or stripped.startswith(triple_single)):
                    return 1

                quote = triple_double if stripped.startswith(triple_double) else triple_single
                if stripped.count(quote) >= 2 and len(stripped) > len(quote) * 2:
                    return index + 1

                index += 1
                while index < len(lines):
                    if quote in lines[index]:
                        return index + 1
                    index += 1

                return 1


            def _combine_imports(imports: list[str], function_source: str) -> str:
                if not imports:
                    return function_source

                lines = function_source.splitlines()
                if not lines:
                    return function_source

                insert_at = _find_import_insert_index(lines)
                import_lines = [f"    {item}" for item in imports]
                merged = lines[:insert_at] + [""] + import_lines + [""] + lines[insert_at:]
                return "\n".join(merged)


            def _ensure_target(path: Path) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    return

                path.write_text(
                    "\n".join(
                        [
                            '"""Skill-local evolved case functions."""',
                            "",
                            "__all__: list[str] = []",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )


            def _select_function(tree: ast.Module, name: str | None) -> ast.FunctionDef:
                functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
                if not functions:
                    raise ValueError("No top-level function found in source file")

                if name is None:
                    return functions[0]

                for node in functions:
                    if node.name == name:
                        return node

                raise ValueError(f"Function '{name}' not found in source file")


            def _append_case(target: Path, function_source: str, function_name: str, allow_duplicate: bool) -> None:
                content = _read_text(target)
                if not allow_duplicate and f"def {function_name}(" in content:
                    raise ValueError(f"Function '{function_name}' already exists in {target}")

                with target.open("a", encoding="utf-8") as stream:
                    stream.write("\n\n" + function_source.strip() + "\n")
                    if f'__all__.append("{function_name}")' not in content:
                        stream.write(f'\n__all__.append("{function_name}")\n')

                ast.parse(_read_text(target), filename=str(target))


            def _parse_args() -> argparse.Namespace:
                parser = argparse.ArgumentParser(
                    description="Add a new evolved case function into this skill package"
                )
                parser.add_argument("source_file", type=Path, help="Python file containing new function")
                parser.add_argument(
                    "--function",
                    default=None,
                    help="Specific function name to extract (default: first top-level function)",
                )
                parser.add_argument(
                    "--target",
                    type=Path,
                    default=DEFAULT_TARGET,
                    help="Target evolve module path",
                )
                parser.add_argument(
                    "--allow-duplicate",
                    action="store_true",
                    help="Allow appending function even if same name already exists",
                )
                return parser.parse_args()


            def main() -> None:
                args = _parse_args()

                if not args.source_file.exists():
                    raise SystemExit(f"Source file not found: {args.source_file}")

                source_text = _read_text(args.source_file)
                if not source_text.strip():
                    raise SystemExit(f"Source file is empty: {args.source_file}")

                try:
                    tree = ast.parse(source_text)
                except SyntaxError as exc:
                    raise SystemExit(f"Cannot parse source file: {exc}") from exc

                function_node = _select_function(tree, args.function)
                lines = source_text.splitlines()
                function_source = _node_source(lines, function_node)
                imports = _extract_header_imports(tree, lines)
                merged_source = _combine_imports(imports, function_source)

                _ensure_target(args.target)
                try:
                    _append_case(
                        target=args.target,
                        function_source=merged_source,
                        function_name=function_node.name,
                        allow_duplicate=args.allow_duplicate,
                    )
                except ValueError as exc:
                    raise SystemExit(str(exc)) from exc

                print(f"Added function '{function_node.name}' to {args.target}")
                print("Import with:")
                print(f"  from {CASES_MODULE}.evolve import {function_node.name}")


            if __name__ == "__main__":
                main()
            '''
        )
        return (
            script.replace("__CASES_MODULE__", self.cases_module).lstrip().rstrip()
            + "\n"
        )

    def _script_validate_skill(self) -> str:
        script = textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail

            SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
            SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

            missing=0
            required=(
              "SKILL.md"
              "scripts/install.sh"
              "scripts/with_skill.sh"
              "scripts/jupyter_with_skill.sh"
              "scripts/repl_bootstrap.py"
              "scripts/add_new_case.sh"
              "scripts/evolve_case.py"
              "scripts/validate_skill.sh"
              "references/PROJECT_OVERVIEW.md"
              "references/RUNTIME_INSTALL.md"
              "references/EVOLVE_WORKFLOW.md"
              "references/PROJECT_README.md"
              "references/LICENSE.txt"
              "references/docs/api/README.md"
              "references/docs/core/README.md"
              "cases/__CASES_MODULE__/__init__.py"
              "cases/__CASES_MODULE__/evolve.py"
            )

            for relative in "${required[@]}"; do
              if [[ ! -e "${SKILL_ROOT}/${relative}" ]]; then
                echo "Missing required path: ${relative}" >&2
                missing=1
              fi
            done

            if [[ -d "${SKILL_ROOT}/assets/project_snapshot/src" || -d "${SKILL_ROOT}/src" ]]; then
              echo "Unexpected bundled source code found in thin skill package." >&2
              missing=1
            fi

            if [[ "${missing}" -ne 0 ]]; then
              exit 1
            fi

            if command -v skills-ref >/dev/null 2>&1; then
              skills-ref validate "${SKILL_ROOT}"
            else
              echo "skills-ref not found, skipped external spec validation."
            fi

            echo "Skill validation succeeded: ${SKILL_ROOT}"
            """
        )
        return script.replace("__CASES_MODULE__", self.cases_module).rstrip() + "\n"

    def _package_spec(self) -> str:
        if self.package_version:
            return f"{self.package_name}=={self.package_version}"
        return self.package_name

    @staticmethod
    def _parse_frontmatter(content: str) -> dict[str, str]:
        lines = content.splitlines()
        if not lines or lines[0].strip() != "---":
            raise ValueError("SKILL.md is missing YAML frontmatter start marker")

        data: dict[str, str] = {}
        end_index = None
        for index in range(1, len(lines)):
            line = lines[index]
            if line.strip() == "---":
                end_index = index
                break
            if not line.strip() or line.startswith((" ", "\t")):
                continue
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")

        if end_index is None:
            raise ValueError("SKILL.md is missing YAML frontmatter end marker")

        return data


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package SimpleCAD API into a thin Agent Skills bundle"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root (default: source checkout root, or installed environment root)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Output directory for generated skill bundle (default: repo skills/ in source checkout, otherwise ./skills)",
    )
    parser.add_argument(
        "--skill-name",
        default=DEFAULT_SKILL_NAME,
        help="Skill directory name and SKILL.md frontmatter name",
    )
    parser.add_argument(
        "--license-name",
        default=DEFAULT_LICENSE,
        help="License value written into SKILL.md frontmatter",
    )
    parser.add_argument(
        "--package-name",
        default=None,
        help="Runtime package name to install from PyPI (default: project.name)",
    )
    parser.add_argument(
        "--package-version",
        default=None,
        help="Runtime package version to install (default: project.version)",
    )
    parser.add_argument(
        "--refresh-docs",
        action="store_true",
        help="Refresh docs/api via auto_docs_gen.py before packaging",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove existing output skill directory before packaging",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Create <skill-name>.tar.gz after generation",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce console output",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    project_root = (
        args.project_root.resolve()
        if args.project_root is not None
        else _default_project_root()
    )
    output_root = (
        args.output_root.resolve()
        if args.output_root is not None
        else _default_output_root(project_root)
    )

    packager = SkillPackager(
        project_root=project_root,
        output_root=output_root,
        skill_name=args.skill_name,
        license_name=args.license_name,
        package_name=args.package_name,
        package_version=args.package_version,
        clean=not args.no_clean,
        refresh_docs=args.refresh_docs,
        archive=args.archive,
        quiet=args.quiet,
    )

    try:
        result = packager.build()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if not args.quiet:
        print("Skill package generated successfully.")
        print(f"Skill directory: {result.skill_root}")
        if result.archive_path is not None:
            print(f"Archive path: {result.archive_path}")


if __name__ == "__main__":
    main()
