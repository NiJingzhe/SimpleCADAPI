#!/usr/bin/env python3
"""Build a thin Agent Skills bundle for SimpleCAD API.

This packager intentionally does not bundle SDK source code.
The generated skill contains SDK reference documents and generated API/core docs.
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
DEFAULT_SKILL_NAME = "simplecadapi"
DEFAULT_LICENSE = "MIT"
DOCS_PATH = Path("docs")
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
    default_desc = "SimpleCAD SDK reference skill"

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
        description=message.get("Summary", "SimpleCAD SDK reference skill"),
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
    """Build thin SDK skill bundle: SKILL.md plus reference docs."""

    def __init__(
        self,
        project_root: Path,
        output_root: Path,
        skill_name: str,
        license_name: str,
        package_name: str | None = None,
        package_version: str | None = None,
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
        self.references_dir = self.skill_root / "references"
        self.docs_dir = self.references_dir / "docs"

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
        self.source_docs = _docs_root_for(self.project_root)
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

        self.references_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir.mkdir(parents=True, exist_ok=True)
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
        (self.references_dir / "SDK_OVERVIEW.md").write_text(
            self._build_project_overview(),
            encoding="utf-8",
        )
        (self.references_dir / "SDK_SURFACES.md").write_text(
            self._build_runtime_install_reference(),
            encoding="utf-8",
        )
        (self.references_dir / "V2_MODELING_WORKFLOWS.md").write_text(
            self._build_evolve_workflow_reference(),
            encoding="utf-8",
        )
        (self.references_dir / "SDK_PACKAGE_SUMMARY.md").write_text(
            self._build_sdk_package_summary(),
            encoding="utf-8",
        )

    def _validate_generated_skill(self) -> None:
        self.log("Validating generated skill...")
        required = (
            self.skill_root / "SKILL.md",
            self.references_dir / "SDK_OVERVIEW.md",
            self.references_dir / "SDK_SURFACES.md",
            self.references_dir / "V2_MODELING_WORKFLOWS.md",
            self.references_dir / "SDK_PACKAGE_SUMMARY.md",
            self.references_dir / "LICENSE.txt",
            self.docs_dir / "api" / "README.md",
            self.docs_dir / "core" / "README.md",
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

    def _create_archive(self) -> Path:
        archive_path = self.output_root / f"{self.skill_name}.tar.gz"
        self.log(f"Creating archive: {archive_path}")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(self.skill_root, arcname=self.skill_name)
        return archive_path

    def _build_skill_markdown(self) -> str:
        package_spec = self._package_spec()
        body = textwrap.dedent(
            f"""\
            ---
            name: {self.skill_name}
            description: Thin SimpleCAD SDK reference skill focused on the public API surface, core types, and v2 modeling workflows.
            license: {self.license_name}
            compatibility: Documentation/reference bundle for SimpleCADAPI v2 surfaces.
            metadata:
              project: {self.metadata.name}
              version: {self.metadata.version}
              package-name: {self.package_name}
              package-version: {self.metadata.version}
            ---

            # SimpleCAD SDK Skill

            ## Philosophy
            - This is a thin SDK reference skill: docs only.
            - SDK source code is not bundled in this skill.

            ## Working From Repo Root
            - Tool calls run from the repo root.
            - Use one explicit skill root: `./skills/{self.skill_name}/` or `./workspace/skills/{self.skill_name}/`.
            - Main doc paths:
              - `<skill_root>/SKILL.md`
              - `<skill_root>/references/docs/api/README.md`
              - `<skill_root>/references/docs/api/<api_name>.md`
              - `<skill_root>/references/docs/core/<type_name>.md`
              - `<skill_root>/references/SDK_OVERVIEW.md`
              - `<skill_root>/references/SDK_SURFACES.md`
              - `<skill_root>/references/V2_MODELING_WORKFLOWS.md`

            ## MUST Requirements
            1. Read `SKILL.md` and `references/docs/api/README.md` before choosing APIs.
            2. Read the exact API Markdown page for every API you use.
            3. Read the needed `core/` docs when an API needs `Edge`, `Face`, `Wire`, `Solid`, `Assembly`, `GraphSession`, `Sketch`, or expression types.
            4. Follow the documented API signatures exactly.
            5. Use the graph/model JSON workflow for v2 tasks: `GraphSession`, `export_session_json`, `export_model_json`, `import_model_json`, and `replay_model_json`.
            6. Use geometry APIs for integrated parts and declarative constraints for final assemblies.
            7. Use tags consistently.
            8. Build and validate incrementally. Each step MUST include a small grounding `print`, and grounding MUST use QL where possible.
            9. For inspection/debugging, query geometry with QL and print only the queried facts you need; do not print whole solids, assemblies, or full model objects.
            10. Boolean operations always return `List[Solid]`. You MUST check `len(results)` before using `results[0]`.
            11. `union_rsolidlist(...)` already uses SimpleCAD's tuned default boolean settings internally. Do not add manual boolean tuning unless you are debugging a stubborn edge case.
            12. If tangent-only contact leaves multiple solids after `union_rsolidlist(...)`, that is often acceptable. Keep the list and continue operating on the list or iterate over its solids.
            13. If the design explicitly requires exactly one merged solid and `len(results) != 1`, you MUST NOT silently pick one item. Instead, slightly adjust part placement so the intended bodies overlap/embed, run the union again, and only then unwrap the single result.
            14. If a task depends on model replay or interchange, prefer `export_model_json()` output over hand-written payloads.

            ## Boolean result discipline
            - `union_rsolidlist(...)`, `cut_rsolidlist(...)`, and `intersect_rsolidlist(...)` accept mixed inputs: standalone `Solid`, lists of `Solid`, and nested sequences.
            - They always return `List[Solid]`.
            - `union_rsolidlist(...)` already applies the package's default glue mode and a conservative internal tolerance.
            - If a union still returns multiple solids that remain separated beyond tolerance, the API prints a stdout warning automatically.
            - Default behavior: keep the list result and pass it forward or iterate over it.
            - Only unwrap to a single solid after an explicit `len(results) == 1` check.
            - If a single merged solid is required but a union still returns multiple solids, slightly move the parts so they overlap instead of merely touching, then recompute the union.

            ## SDK Focus
            - This skill is intended to describe the public CAD Python SDK surface.
            - Prefer the generated API and core docs over environment/bootstrap instructions.
            - Use `references/SDK_OVERVIEW.md` for the package-level map.
            - Use `references/SDK_SURFACES.md` for the main public surfaces.
            - Use `references/V2_MODELING_WORKFLOWS.md` for graph/model-oriented patterns.

            ## Example SDK usage

            ```python
            import simplecadapi as scad
            from simplecadapi import GraphSession, export_model_json, make_box_rsolid
            ```

            Typical v2 usage in a Python script:

            ```python
            import simplecadapi as scad
            from simplecadapi import GraphSession, export_model_json, replay_model_json

            with GraphSession() as session:
                shape = scad.make_box_rsolid(10.0, 20.0, 30.0)

            model_json = export_model_json(session)
            rebuilt = replay_model_json(model_json)
            print(len(rebuilt))
            ```

            Use the graph/model JSON workflow when the task needs reproducibility, interchange, or replayable v2 outputs.

            ## References
            - `references/SDK_OVERVIEW.md`
            - `references/SDK_SURFACES.md`
            - `references/V2_MODELING_WORKFLOWS.md`
            - `references/SDK_PACKAGE_SUMMARY.md`
            - `references/docs/api/`
            - `references/docs/core/`
            """
        )
        return body.rstrip() + "\n"

    def _build_project_overview(self) -> str:
        package_spec = self._package_spec()
        lines = [
            "# SDK Overview",
            "",
            f"- Project: `{self.metadata.name}`",
            f"- Version: `{self.metadata.version}`",
            f"- Package distribution: `{package_spec}`",
            "",
            "## What this skill bundles",
            "",
            "- Skill instructions (`SKILL.md`)",
            "- Documentation references (`references/docs/`)",
            "- High-level SDK summaries (`references/*.md`)",
            "",
            "## What this skill does not bundle",
            "",
            "- SDK source code (`src/simplecadapi`) is intentionally excluded.",
            "- Environment/bootstrap workflows are intentionally not the focus here.",
            "- Self-evolving or skill-local case packaging is intentionally excluded.",
            "",
            "## Main SDK surfaces",
            "",
            "- Geometry and modeling operations in `docs/api/`.",
            "- Core shape/type semantics in `docs/core/`.",
            "- v2 graph/model serialization and replay APIs.",
            "- Expression, parameter, and semantic reference types.",
            "",
            "## Preferred v2 workflow",
            "",
            "- Record modeling steps inside `GraphSession` when you need replayable outputs.",
            "- Export session/model payloads with `export_session_json()` and `export_model_json()`.",
            "- Re-import or replay with `import_model_json()` and `replay_model_json()`.",
        ]
        return "\n".join(lines).rstrip() + "\n"

    def _build_runtime_install_reference(self) -> str:
        body = textwrap.dedent(
            f"""\
            # SDK Surfaces

            ## Public API groups

            - Primitive and sketch construction functions
            - Transform, feature, boolean, and export functions
            - Assembly and constraint entry points
            - Graph/model serialization and replay entry points
            - Expression and semantic reference data types

            ## Recommended reading order

            1. `references/docs/api/README.md`
            2. `references/SDK_OVERVIEW.md`
            3. `references/V2_MODELING_WORKFLOWS.md`
            4. Specific pages under `references/docs/api/`
            5. Supporting pages under `references/docs/core/`

            ## Typical v2 surface

            ```python
            from simplecadapi import GraphSession, export_model_json, replay_model_json

            with GraphSession() as session:
                ...

            model_json = export_model_json(session)
            rebuilt = replay_model_json(model_json)
            print(len(rebuilt))
            ```
            """
        )
        return body.rstrip() + "\n"

    def _build_evolve_workflow_reference(self) -> str:
        body = textwrap.dedent(
            f"""\
            # V2 Modeling Workflows

            ## 1) Capture a replayable v2 modeling flow

            ```python
            from simplecadapi import GraphSession, export_model_json

            with GraphSession() as session:
                ...

            payload = export_model_json(session)
            ```

            ## 2) Import and use in Python

            ```python
            import simplecadapi as scad
            from simplecadapi import GraphSession, export_model_json
            ```

            ## 3) Keep replay payloads as the interchange boundary

            - Prefer `export_model_json()` output instead of hand-written payloads.
            - Use `replay_model_json()` when you need deterministic reconstruction.
            - Use `import_model_json()` when consuming previously exported payloads.
            """
        )
        return body.rstrip() + "\n"

    def _build_sdk_package_summary(self) -> str:
        summary = self.metadata.description or self.package_name
        readme_excerpt = (self.metadata.readme_text or "").strip()
        excerpt_lines = [
            line.strip() for line in readme_excerpt.splitlines() if line.strip()
        ]
        excerpt = "\n".join(excerpt_lines[:6])

        body = textwrap.dedent(
            f"""\
            # SDK Package Summary

            - Project: `{self.metadata.name}`
            - Version: `{self.metadata.version}`
            - Summary: {summary}

            ## Scope

            - Public CAD Python SDK for geometry, assemblies, and v2 replayable modeling.
            - Includes generated API and core type references under `references/docs/`.
            - Emphasizes public surfaces rather than repository operations.

            ## Main reference entry points

            - `references/docs/api/README.md`
            - `references/docs/core/README.md`
            - `references/SDK_OVERVIEW.md`
            - `references/SDK_SURFACES.md`
            - `references/V2_MODELING_WORKFLOWS.md`
            """
        )

        if excerpt:
            body += "\n## Package excerpt\n\n" + excerpt + "\n"

        return body.rstrip() + "\n"

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
