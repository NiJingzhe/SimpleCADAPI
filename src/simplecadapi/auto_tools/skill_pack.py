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
DEFAULT_LICENSE = "AGPL-3.0"
DOCS_PATH = Path("docs")
LICENSE_PATH = Path("LICENSE")
SKILL_SOURCE_PATH = Path("docs/skill")

SKILL_DOMAINS = (
    "requirement-refinement",
    "part-modeling",
    "sketch-and-features",
    "assembly-and-product",
    "standard-parts",
    "step-inspection",
    "export-and-translation",
)
SKILL_WORKFLOWS = (
    "single-part-modeling",
    "sketch-feature-modeling",
    "assembly-product-build",
    "step-reconstruction",
    "standard-part-assembly",
    "export-and-translation",
)
SKILL_DISCIPLINES = (
    "mechanical-modeling",
    "requirement-and-cad-brief",
    "datums-and-coordinate-systems",
    "feature-ordering",
    "assembly-positioning",
    "geometric-validation",
    "failure-and-repair",
    "manufacturing-boundaries",
)

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


def _skill_source_dir_for(project_root: Path) -> Path:
    return project_root / SKILL_SOURCE_PATH


def _has_skill_layer(project_root: Path) -> bool:
    skill_dir = _skill_source_dir_for(project_root)
    return skill_dir.is_dir() and all(
        (skill_dir / sub).is_dir() for sub in ("domains", "workflows", "discipline")
    )


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
            continue
        # Keep the skill bundle English-only and reference-focused: drop
        # deliberate Chinese release-note twins and internal design/history
        # docs (the repo keeps them; the bundle does not ship them).
        if name.endswith(".zh-CN.md"):
            ignored.append(name)
            continue
        # docs/skill/ is copied separately into references/ top level by
        # _copy_skill_layer; do not duplicate it under references/docs/.
        if name == "skill":
            ignored.append(name)
            continue
        if name in {
            "architecture",
            "rearchitecture_2_0.md",
            "rearchitecture_2_0_requirements.md",
            "operation_graph_json_spec.md",
            "part_assembly_development_plan.md",
        }:
            ignored.append(name)
            continue
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
            self.source_docs / "stdlib",
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

        self.log("Refreshing generated docs before packaging...")
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
        self._copy_skill_layer()
        inspection_reference = (
            self.source_docs / "guides" / "step-brep-reverse-engineering.md"
        )
        destination = self.references_dir / "inspect" / "brep-reverse-engineering.md"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if inspection_reference.exists():
            shutil.copy2(inspection_reference, destination)
        else:
            destination.write_text(
                "# STEP/BREP Inspection\n\n"
                "Use `simplecadapi.inspect.brep` outside GraphSession. "
                "Select inspection primitives according to the case; do not "
                "apply a fixed reverse-engineering pipeline.\n",
                encoding="utf-8",
            )

    def _copy_skill_layer(self) -> None:
        skill_source = _skill_source_dir_for(self.project_root)
        if not _has_skill_layer(self.project_root):
            raise FileNotFoundError(
                "Task-routed skill layer is missing under docs/skill/ "
                "(domains/, workflows/, discipline/)"
            )
        self.log("Copying task-routed skill layer...")
        shutil.copytree(
            skill_source,
            self.references_dir,
            dirs_exist_ok=True,
            ignore=_ignore_common_noise,
        )
        (self.references_dir / "README.md").write_text(
            self._build_skill_layer_readme(),
            encoding="utf-8",
        )

    def _validate_generated_skill(self) -> None:
        self.log("Validating generated skill...")
        required = [
            self.skill_root / "SKILL.md",
            self.references_dir / "SDK_OVERVIEW.md",
            self.references_dir / "inspect" / "brep-reverse-engineering.md",
            self.references_dir / "LICENSE.txt",
            self.docs_dir / "api" / "README.md",
            self.docs_dir / "core" / "README.md",
            self.docs_dir / "stdlib" / "README.md",
        ]
        for name in SKILL_DOMAINS:
            required.append(self.references_dir / "domains" / f"{name}.md")
        for name in SKILL_WORKFLOWS:
            required.append(self.references_dir / "workflows" / f"{name}.md")
        for name in SKILL_DISCIPLINES:
            required.append(self.references_dir / "discipline" / f"{name}.md")

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
        guide_references = ""
        if self._has_reconstruction_guides():
            guide_references = (
                "            - `references/docs/guides/"
                "reconstruction-agent-test-prompt.md`\n"
                "            - `references/docs/guides/"
                "reconstruction-agent-strategy.md`\n"
            )
        body = textwrap.dedent(
            f"""\
            ---
            name: {self.skill_name}
            description: Build, assemble, inspect, reconstruct, and export parametric CAD models with the SimpleCADAPI Python SDK. Use for SimpleCAD geometry modeling, constrained sketches, parts and assemblies, standard gears and bearings, STEP/BREP inspection and reconstruction, durable product packages, model JSON replay, and CAD backend translation.
            license: {self.license_name}
            metadata:
              project: {self.metadata.name}
              version: {self.metadata.version}
              package-name: {self.package_name}
              package-version: {self.metadata.version}
            ---

            # SimpleCAD SDK Skill

            Plan and route CAD tasks with the SimpleCADAPI SDK: classify the
            request, load the workflow that owns it, follow its task-domain and
            discipline references, and read exact API pages only for the APIs a
            step names.

            ## Task routing

            Read exactly one workflow first, per the user's goal:

            | User goal | Workflow |
            | --- | --- |
            | Model one physical part | `references/workflows/single-part-modeling.md` |
            | Constraint-driven profile as design intent | `references/workflows/sketch-feature-modeling.md` |
            | Multi-part product, connectors, constraints, package | `references/workflows/assembly-product-build.md` |
            | Rebuild an editable model from a STEP file | `references/workflows/step-reconstruction.md` |
            | Mechanism from stdlib gears/bearings | `references/workflows/standard-part-assembly.md` |
            | Export/translate a validated package | `references/workflows/export-and-translation.md` |

            Read-only questions about an existing STEP file do not need a
            workflow: `references/domains/step-inspection.md` covers them
            directly.

            ## Global rules (every task)

            1. Refine the requirement into a brief before modeling
               (`references/domains/requirement-refinement.md`).
            2. Use keyword arguments for every documented public API and
               stdlib function, except the canonical durable export call
               `capture(result, path)`, whose two required arguments are
               positional.
            3. One part per file; one assembly file per product; parameters
               live in the file that consumes them; exposed tunable parameters
               are `var()`/`Var` declarations (optionally with `unit`,
               `tolerance`).
            4. Booleans (`union_rsolid`, `cut_rsolid`, `intersect_rsolid`)
               accept mixed inputs and return exactly one `Solid`; union
               defaults to `glue=False` with a conservative scale-relative
               tolerance and fails explicitly when it cannot produce one
               merged solid.
            5. Build and validate incrementally: each major step prints small
               QL-derived facts; grounding uses QL wherever possible; never
               print whole solids or full model objects.
            6. Tags: attach with `apply_tag(shape=..., tag=...)` (LOCAL scope —
               it never propagates downward); inspect with
               `list_tags(shape=...)`; keep numeric facts in metadata, never in
               tags.
            7. `@scad.part` for one physical single-solid product;
               `@scad.assemble` for assemblies with explicit definitions.
               Neither nests inside an active `GraphSession`. Durable delivery
               is `capture(result, "out/product.scadpkg")` in one call.
            8. `simplecadapi.inspect.brep` is diagnostic-only and rejected
               inside `GraphSession`; obtain/export geometry first, inspect
               outside.
            9. Standard parts first: before hand-modeling a gear, ring gear,
               rack, cycloidal disc, or bearing, check `scad.std.gear` /
               `scad.std.bearing`.
            10. Read `references/docs/guides/cache-build-workflow.md` in full
                before configuring persistent cache, durable builds, or cache
                maintenance; cache mutation requires explicit confirmation.

            ## Boundaries

            - `.scadpkg` is the canonical durable product; STL/OBJ/MJCF are
              point-in-time exports, never editable sources.
            - Model JSON is the replay/interchange contract for explicit
              `GraphSession` flows; never hand-author payloads.
            - No claims of strength, fatigue, thermal, vibration, tolerance
              compliance, or regulatory fitness without the corresponding
              analysis actually run.

            ## Reading order

            ```text
            SKILL.md (this router)
            -> references/workflows/<scenario>.md
            -> the domains/ and discipline/ files the workflow names
            -> references/docs/api|stdlib|core/<exact page>.md for each API a step uses
            ```

            Do not read the full API index or stdlib index up front; the
            workflow names what to load. Every API used still gets its exact
            page read (`references/docs/api/<name>.md`,
            `references/docs/stdlib/<name>.md`,
            `references/docs/core/<type>.md`).

            ## Example SDK usage

            ```python
            import simplecadapi as scad
            from simplecadapi import GraphSession, export_model_json, replay_model_json

            with GraphSession(graph_id="box") as session:
                shape = scad.make_box_rsolid(width=10.0, height=20.0, depth=30.0)
                session.capture_result(value=shape)
                payload = export_model_json(session=session)

            rebuilt = replay_model_json(json_str=payload)
            print(len(rebuilt))
            ```

            ## References

            - `references/README.md` — skill layer structure
            - `references/workflows/` — six goal-oriented workflows
            - `references/domains/` — seven capability domains
            - `references/discipline/` — modeling knowledge and invariants
            - `references/SDK_OVERVIEW.md` — package-level map
            - `references/inspect/brep-reverse-engineering.md`
{guide_references}            - `references/docs/guides/cache-build-workflow.md`
            - `references/docs/api/`, `references/docs/stdlib/`, `references/docs/core/`
            """
        )
        return body.rstrip() + "\n"

    def _build_skill_layer_readme(self) -> str:
        source = _skill_source_dir_for(self.project_root) / "README.md"
        if source.is_file():
            return source.read_text(encoding="utf-8")
        return (
            "# Skill Documentation Structure\n\n"
            "domains/ workflows/ discipline/ layer; see SKILL.md for routing.\n"
        )

    def _has_reconstruction_guides(self) -> bool:
        guides = self.source_docs / "guides"
        return all(
            (guides / name).is_file()
            for name in (
                "reconstruction-agent-test-prompt.md",
                "reconstruction-agent-strategy.md",
            )
        )

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
            "- Task router (`SKILL.md`) with six workflows",
            "- Capability domains (`references/domains/`)",
            "- Modeling discipline (`references/discipline/`)",
            "- Generated API/stdlib/core references (`references/docs/`)",
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
            "- Standard parts library in `docs/stdlib/`, including `scad.std.gear` gear, ring gear, rack, and cycloidal disc factories plus `scad.std.bearing` bearing assembly factories.",
            "- Core shape/type semantics in `docs/core/`.",
            "- Graph/model serialization and replay APIs.",
            "- Expression, parameter, and semantic reference types.",
            "- Functional tagging with `apply_tag(shape=..., tag=...)`, `list_tags(shape=...)`, and QL tag predicates.",
            "",
            "## Preferred replayable workflow",
            "",
            "- Record modeling steps inside `GraphSession` when you need replayable outputs.",
            "- Export session/model payloads with `export_session_json()` and `export_model_json()`.",
            "- Re-import or replay with `import_model_json()` and `replay_model_json()`.",
        ]
        return "\n".join(lines).rstrip() + "\n"

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
        help="Refresh docs/api and docs/stdlib via auto_docs_gen.py before packaging",
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
