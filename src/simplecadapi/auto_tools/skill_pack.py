#!/usr/bin/env python3
"""Package SimpleCAD API into an Agent Skills compatible bundle.

This tool builds a skill directory with the following structure:

<output-root>/<skill-name>/
  SKILL.md
  scripts/
  references/
  assets/project_snapshot/

The snapshot contains selected project code and docs so that the skill can
run self-evolution workflows in a portable way.
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
from pathlib import Path
from typing import Iterable

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for Python 3.10
    tomllib = None  # type: ignore[assignment]


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "skills"
DEFAULT_SKILL_NAME = "simplecad-self-evolve"
DEFAULT_LICENSE = "MIT"

SNAPSHOT_PATHS: tuple[Path, ...] = (
    Path("src/simplecadapi"),
    Path("docs"),
    Path("README.md"),
    Path("pyproject.toml"),
    Path("LICENSE"),
)

SKILL_NAME_PATTERN = re.compile(r"^(?!-)(?!.*--)[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class ProjectMetadata:
    """Minimal project metadata used to render the skill files."""

    name: str
    version: str


@dataclass(frozen=True)
class BuildResult:
    """Result object for a completed skill package build."""

    skill_root: Path
    archive_path: Path | None


def _load_project_metadata(project_root: Path) -> ProjectMetadata:
    pyproject_path = project_root / "pyproject.toml"
    default_name = project_root.name.lower()
    default_version = "0.0.0"

    if not pyproject_path.exists():
        return ProjectMetadata(name=default_name, version=default_version)

    if tomllib is not None:
        try:
            data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            project = data.get("project", {})
            name = str(project.get("name") or default_name)
            version = str(project.get("version") or default_version)
            return ProjectMetadata(name=name, version=version)
        except Exception:
            pass

    name_match = re.search(
        r'^\s*name\s*=\s*"(?P<name>[^"]+)"\s*$',
        pyproject_path.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    version_match = re.search(
        r'^\s*version\s*=\s*"(?P<version>[^"]+)"\s*$',
        pyproject_path.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )

    name = name_match.group("name") if name_match else default_name
    version = version_match.group("version") if version_match else default_version
    return ProjectMetadata(name=name, version=version)


def _ignore_cache_files(_: str, names: list[str]) -> list[str]:
    ignored: list[str] = []
    for name in names:
        if name == "__pycache__":
            ignored.append(name)
            continue
        if name.endswith(".pyc"):
            ignored.append(name)
            continue
        if name == ".DS_Store":
            ignored.append(name)
    return ignored


class SkillPackager:
    """Build a skills-spec bundle from the SimpleCAD project files."""

    def __init__(
        self,
        project_root: Path,
        output_root: Path,
        skill_name: str,
        license_name: str,
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
        self.snapshot_root = self.skill_root / "assets" / "project_snapshot"
        self.metadata = _load_project_metadata(self.project_root)

    def log(self, message: str) -> None:
        if not self.quiet:
            print(message)

    def build(self) -> BuildResult:
        self._validate_inputs()

        if self.refresh_docs:
            self._refresh_api_docs()

        self._prepare_output_directory()
        self._copy_snapshot_files()
        self._write_skill_markdown()
        self._write_reference_files()
        self._write_scripts()
        self._validate_generated_skill()

        archive_path = self._create_archive() if self.archive else None
        return BuildResult(skill_root=self.skill_root, archive_path=archive_path)

    def _validate_inputs(self) -> None:
        if len(self.skill_name) > 64:
            raise ValueError("skill_name must be <= 64 characters")
        if not SKILL_NAME_PATTERN.fullmatch(self.skill_name):
            raise ValueError(
                "skill_name must use lowercase letters, numbers, and single hyphens"
            )

        for relative_path in SNAPSHOT_PATHS:
            source = self.project_root / relative_path
            if not source.exists():
                raise FileNotFoundError(f"Missing required path: {source}")

    def _refresh_api_docs(self) -> None:
        script_path = self.project_root / "src/simplecadapi/auto_tools/auto_docs_gen.py"
        if not script_path.exists():
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
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        self.log(f"Writing skill bundle to: {self.skill_root}")

    def _copy_snapshot_files(self) -> None:
        self.log("Copying project snapshot files...")
        for relative_path in SNAPSHOT_PATHS:
            source = self.project_root / relative_path
            destination = self.snapshot_root / relative_path

            if source.is_dir():
                shutil.copytree(
                    source,
                    destination,
                    dirs_exist_ok=True,
                    ignore=_ignore_cache_files,
                )
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def _write_skill_markdown(self) -> None:
        self.log("Generating SKILL.md...")
        content = self._build_skill_markdown()
        (self.skill_root / "SKILL.md").write_text(content, encoding="utf-8")

    def _write_reference_files(self) -> None:
        self.log("Generating reference documents...")
        project_overview = self._build_project_overview_reference()
        (self.references_dir / "PROJECT_OVERVIEW.md").write_text(
            project_overview,
            encoding="utf-8",
        )

        api_index = self._build_reference_from_snapshot(
            title="API Index",
            snapshot_relative_path=Path("docs/api/README.md"),
            fallback_body=(
                "The API index is not available in this snapshot. "
                "Run scripts/refresh_docs.sh first."
            ),
        )
        (self.references_dir / "API_INDEX.md").write_text(api_index, encoding="utf-8")

        core_index = self._build_reference_from_snapshot(
            title="Core Index",
            snapshot_relative_path=Path("docs/core/README.md"),
            fallback_body=(
                "The core index is not available in this snapshot. "
                "Check assets/project_snapshot/docs/core/."
            ),
        )
        (self.references_dir / "CORE_INDEX.md").write_text(
            core_index,
            encoding="utf-8",
        )

        evolve_workflow = self._build_evolve_workflow_reference()
        (self.references_dir / "EVOLVE_WORKFLOW.md").write_text(
            evolve_workflow,
            encoding="utf-8",
        )

    def _write_scripts(self) -> None:
        self.log("Generating helper scripts...")
        scripts: dict[str, str] = {
            "with_skill.sh": self._script_with_skill(),
            "jupyter_with_skill.sh": self._script_jupyter_with_skill(),
            "repl_bootstrap.py": self._script_repl_bootstrap_py(),
            "refresh_docs.sh": self._script_refresh_docs(),
            "rebuild_exports.sh": self._script_rebuild_exports(),
            "validate_skill.sh": self._script_validate_skill(),
            "repack_skill.sh": self._script_repack_skill(),
            "add_new_case.sh": self._script_add_new_case(),
        }

        for script_name, content in scripts.items():
            path = self.scripts_dir / script_name
            path.write_text(content, encoding="utf-8")
            path.chmod(0o755)

    def _validate_generated_skill(self) -> None:
        self.log("Validating generated skill...")

        required_paths = (
            self.skill_root / "SKILL.md",
            self.scripts_dir / "with_skill.sh",
            self.scripts_dir / "jupyter_with_skill.sh",
            self.scripts_dir / "repl_bootstrap.py",
            self.scripts_dir / "add_new_case.sh",
            self.scripts_dir / "refresh_docs.sh",
            self.scripts_dir / "rebuild_exports.sh",
            self.scripts_dir / "validate_skill.sh",
            self.scripts_dir / "repack_skill.sh",
            self.references_dir / "PROJECT_OVERVIEW.md",
            self.references_dir / "API_INDEX.md",
            self.references_dir / "CORE_INDEX.md",
            self.references_dir / "EVOLVE_WORKFLOW.md",
            self.snapshot_root / "src/simplecadapi/operations.py",
            self.snapshot_root / "src/simplecadapi/evolve.py",
            self.snapshot_root / "docs/api/README.md",
        )

        for path in required_paths:
            if not path.exists():
                raise FileNotFoundError(
                    f"Generated skill is missing required file: {path}"
                )

        frontmatter = self._parse_frontmatter(
            (self.skill_root / "SKILL.md").read_text("utf-8")
        )
        name = frontmatter.get("name", "")
        description = frontmatter.get("description", "")
        if name != self.skill_name:
            raise ValueError(
                "SKILL.md frontmatter name does not match directory name "
                f"({name!r} != {self.skill_name!r})"
            )
        if not description:
            raise ValueError("SKILL.md frontmatter description is empty")
        if len(description) > 1024:
            raise ValueError("SKILL.md frontmatter description exceeds 1024 characters")

    def _create_archive(self) -> Path:
        archive_path = self.output_root / f"{self.skill_name}.tar.gz"
        self.log(f"Creating archive: {archive_path}")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(self.skill_root, arcname=self.skill_name)
        return archive_path

    def _build_skill_markdown(self) -> str:
        description = (
            "Package SimpleCAD API as a portable Agent Skill and provide a clear "
            "add-new-case workflow that keeps source, exports, docs, and skill bundle "
            "in sync. Use when you need a self-maintained CAD SDK skill."
        )
        compatibility = (
            "Requires bash and Python 3.10+. Optional: skills-ref CLI for full spec "
            "validation."
        )

        body = textwrap.dedent(
            f"""\
            ---
            name: {self.skill_name}
            description: {description}
            license: {self.license_name}
            compatibility: {compatibility}
            metadata:
              project: {self.metadata.name}
              version: {self.metadata.version}
              snapshot: assets/project_snapshot
            ---

            # SimpleCAD Self Evolve Skill

            ## When to use this skill
            - You need a portable snapshot of SimpleCAD SDK code and docs.
            - You need one repeatable command flow to add a new SDK case/function.
            - You want source updates, exports, and docs to stay synchronized.

            ## SDK core philosophy
            - **Open/Closed design**: keep core wrapper types stable and extend capability by adding new top-level functions.
            - **Function-first API**: use explicit snake_case operation functions instead of hidden class mutation.
            - **Return-type explicit naming**: function names encode return type, for example `make_circle_rwire` or `extrude_rsolid`.
            - **Evolve by composition**: new advanced cases are added in `evolve.py` by combining existing primitives.
            - **Docs as contract**: every public function should keep signature, docstring, and generated docs aligned.

            ## Directory map
            The skill root layout:

            - `SKILL.md`: this instruction file.
            - `scripts/`: runnable automation scripts for add/update/validate workflows.
            - `references/`: readable navigation and workflow documents.
            - `assets/project_snapshot/`: portable SDK snapshot used by scripts.

            Snapshot scope in `assets/project_snapshot/`:

            - `src/simplecadapi/core.py`: core geometric wrapper types and coordinate system utilities.
            - `src/simplecadapi/operations.py`: stable public operation functions.
            - `src/simplecadapi/evolve.py`: advanced or newly extracted case functions.
            - `src/simplecadapi/__init__.py`: aggregated exports and aliases.
            - `src/simplecadapi/auto_tools/`: automation tools (`evolution.py`, `make_export.py`, `auto_docs_gen.py`, `skill_pack.py`).
            - `docs/api/`: generated per-function API docs.
            - `docs/core/`: core type documentation.
            - `README.md`: SDK design and workflow explanation.
            - `pyproject.toml`: package metadata and script entry points.
            - `LICENSE`: project license.

            ## How to import SDK functions
            Import targets by module role:

            - Public SDK APIs: `simplecadapi` (recommended) or `simplecadapi.operations`.
            - Evolved case functions: `simplecadapi.evolve`.
            - Core wrapper types: `simplecadapi.core`.

            If you already installed the package, import directly:

            ```python
            import simplecadapi as scad
            from simplecadapi import make_box_rsolid, export_stl
            from simplecadapi.evolve import make_n_hole_flange_rsolid
            ```

            If you are running against this skill snapshot without installation, set `PYTHONPATH` first:

            ```bash
            export PYTHONPATH="${{PWD}}/assets/project_snapshot/src:${{PYTHONPATH:-}}"
            python3 your_script.py
            ```

            Example usage after import:

            ```python
            import simplecadapi as scad

            box = scad.make_box_rsolid(width=10, height=6, depth=4)
            scad.export_stl(box, "box.stl")
            ```

            ## Single-skill simplified mode
            If your project uses only this one skill, you can skip registry and multi-skill lock management.
            Use `scripts/with_skill.sh` as the single activation entry.

            ```bash
            scripts/with_skill.sh -- python3 your_script.py
            scripts/jupyter_with_skill.sh lab
            # or export into current shell
            eval "$(scripts/with_skill.sh --print-env)"
            ```

            - `with_skill.sh` sets `SIMPLECAD_SKILL_ROOT` and `SIMPLECAD_SKILL_SRC`.
            - `with_skill.sh` prepends this skill's `assets/project_snapshot/src` to `PYTHONPATH`.
            - `jupyter_with_skill.sh` launches Jupyter with this skill path pre-activated.
            - This keeps imports deterministic while remaining lightweight.

            ## Persistent REPL and notebook kernel mode
            If an LLM writes code directly in a persistent REPL (IPython/Jupyter kernel), use one-time bootstrap in the session.

            ```python
            # in a notebook cell or persistent Python REPL
            %run ./skills/simplecad-self-evolve/scripts/repl_bootstrap.py
            import simplecadapi as scad
            ```

            Notes:
            - `repl_bootstrap.py` injects this skill's source path into current process `sys.path`.
            - It also sets `SIMPLECAD_SKILL_ROOT` and `SIMPLECAD_SKILL_SRC` in `os.environ`.
            - Use `--check` when running from shell to verify imports: `python scripts/repl_bootstrap.py --check`.

            ## Scripts and exact usage
            `scripts/with_skill.sh`

            ```bash
            scripts/with_skill.sh -- python3 your_script.py
            scripts/with_skill.sh --print-env
            scripts/with_skill.sh --check
            ```

            - Purpose: activate this single skill import path in a deterministic way.
            - `-- <command>` runs a command with skill-aware `PYTHONPATH`.
            - `--print-env` prints `export` commands that can be `eval` in current shell.
            - `--check` verifies runtime dependencies and `import simplecadapi` availability.

            `scripts/jupyter_with_skill.sh`

            ```bash
            scripts/jupyter_with_skill.sh lab
            scripts/jupyter_with_skill.sh notebook
            scripts/jupyter_with_skill.sh lab -- --no-browser
            ```

            - Purpose: start Jupyter Lab/Notebook with skill import path already injected.
            - Uses `with_skill.sh` internally so notebook kernels inherit deterministic `PYTHONPATH`.

            `scripts/repl_bootstrap.py`

            ```bash
            python scripts/repl_bootstrap.py
            python scripts/repl_bootstrap.py --check
            ```

            - Purpose: activate skill import path in an already-running Python process.
            - Typical use: first cell in a notebook kernel managed by LLM.

            `scripts/add_new_case.sh`

            ```bash
            scripts/add_new_case.sh <path-to-python-script>
            # optional: NO_REPACK=1 scripts/add_new_case.sh <path>
            ```

            - Purpose: end-to-end add-new-case pipeline.
            - Input: a Python file that contains a function implementation to extract.
            - Actions: validate skill -> extract function into `evolve.py` -> rebuild `__init__.py` exports -> regenerate `docs/api` -> repack skill.
            - Output: updated snapshot files (and repacked skill unless `NO_REPACK=1`).

            `scripts/rebuild_exports.sh`

            ```bash
            scripts/rebuild_exports.sh [extra make_export args]
            ```

            - Purpose: regenerate `assets/project_snapshot/src/simplecadapi/__init__.py` from current APIs.

            `scripts/refresh_docs.sh`

            ```bash
            scripts/refresh_docs.sh
            ```

            - Purpose: regenerate `assets/project_snapshot/docs/api/*.md` and the API index from function docstrings.

            `scripts/repack_skill.sh`

            ```bash
            scripts/repack_skill.sh [extra skill_pack args]
            ```

            - Purpose: rebuild this skill folder from `assets/project_snapshot` using `skill_pack.py`.

            `scripts/validate_skill.sh`

            ```bash
            scripts/validate_skill.sh
            ```

            - Purpose: verify required files and run `skills-ref validate` when available.

            ## Recommended add-new-case procedure
            1. Prepare a Python script with one well-documented new case function.
            2. Run `scripts/add_new_case.sh <script.py>`.
            3. Review changes under `assets/project_snapshot/src/simplecadapi/` and `assets/project_snapshot/docs/api/`.
            4. Run `scripts/validate_skill.sh` and then publish/share this skill.

            ## Additional references
            - `references/PROJECT_OVERVIEW.md`
            - `references/API_INDEX.md`
            - `references/CORE_INDEX.md`
            - `references/EVOLVE_WORKFLOW.md`
            """
        )
        return body.rstrip() + "\n"

    def _build_project_overview_reference(self) -> str:
        lines: list[str] = [
            "# Project Overview",
            "",
            f"- Project name: `{self.metadata.name}`",
            f"- Project version: `{self.metadata.version}`",
            f"- Skill name: `{self.skill_name}`",
            "",
            "## Snapshot contents",
            "",
        ]

        for relative_path in SNAPSHOT_PATHS:
            lines.append(f"- `assets/project_snapshot/{relative_path.as_posix()}`")

        lines.extend(
            [
                "",
                "## Notes",
                "",
                "- This snapshot is generated by `skill-pack`.",
                "- Use `scripts/repack_skill.sh` after modifying snapshot content.",
                "- Use `scripts/validate_skill.sh` before distribution.",
                "",
                "## Source readme excerpt",
                "",
            ]
        )

        readme_path = self.snapshot_root / "README.md"
        if readme_path.exists():
            excerpt = self._take_first_nonempty_lines(
                readme_path.read_text(encoding="utf-8").splitlines(),
                limit=24,
            )
            lines.extend(excerpt)
        else:
            lines.append("README.md not found in snapshot.")

        return "\n".join(lines).rstrip() + "\n"

    def _build_reference_from_snapshot(
        self,
        title: str,
        snapshot_relative_path: Path,
        fallback_body: str,
    ) -> str:
        source_path = self.snapshot_root / snapshot_relative_path
        header = [
            f"# {title}",
            "",
            "This file mirrors content from the project snapshot.",
            "",
            f"- Source: `assets/project_snapshot/{snapshot_relative_path.as_posix()}`",
            "",
        ]

        if source_path.exists():
            mirrored = source_path.read_text(encoding="utf-8").strip()
            return (
                "\n".join(header + ["## Mirrored Content", "", mirrored, ""]).rstrip()
                + "\n"
            )

        return "\n".join(header + [fallback_body, ""]).rstrip() + "\n"

    @staticmethod
    def _take_first_nonempty_lines(lines: Iterable[str], limit: int) -> list[str]:
        selected: list[str] = []
        for line in lines:
            if not line.strip() and not selected:
                continue
            selected.append(line)
            if len(selected) >= limit:
                break
        return selected

    def _build_evolve_workflow_reference(self) -> str:
        return (
            textwrap.dedent(
                """\
            # Evolve Workflow

            This reference describes the expected self-evolution sequence.

            1. Extract function implementation into `evolve.py`.
            2. Rebuild exports in `__init__.py`.
            3. Regenerate API docs from source docstrings.
            4. Repack the skill folder from the updated snapshot.

            ## Commands

            ```bash
            scripts/add_new_case.sh path/to/new_function.py
            ```

            Or run each step separately:

            ```bash
            scripts/rebuild_exports.sh
            scripts/refresh_docs.sh
            scripts/repack_skill.sh
            scripts/validate_skill.sh
            ```

            ## Environment

            - `PYTHON_BIN` can override the Python interpreter used by scripts.
            - `NO_REPACK=1` skips the repack step in `add_new_case.sh`.
            """
            ).rstrip()
            + "\n"
        )

    @staticmethod
    def _script_common_preamble() -> str:
        return textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail

            SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
            SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
            SNAPSHOT_ROOT="${SKILL_ROOT}/assets/project_snapshot"
            PYTHON_BIN="${PYTHON_BIN:-python3}"

            if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
              PYTHON_BIN="python"
            fi

            if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
              echo "Error: python interpreter not found." >&2
              exit 1
            fi
            """
        )

    def _script_with_skill(self) -> str:
        return (
            self._script_common_preamble()
            + textwrap.dedent(
                """\

if [[ ! -d "${SNAPSHOT_ROOT}/src" ]]; then
  echo "Error: missing skill source path: ${SNAPSHOT_ROOT}/src" >&2
  exit 1
fi

export SIMPLECAD_SKILL_ROOT="${SKILL_ROOT}"
export SIMPLECAD_SKILL_SRC="${SNAPSHOT_ROOT}/src"

if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${SIMPLECAD_SKILL_SRC}:${PYTHONPATH}"
else
  export PYTHONPATH="${SIMPLECAD_SKILL_SRC}"
fi

if [[ "${1:-}" == "--print-env" ]]; then
  printf 'export SIMPLECAD_SKILL_ROOT="%s"\\n' "${SIMPLECAD_SKILL_ROOT}"
  printf 'export SIMPLECAD_SKILL_SRC="%s"\\n' "${SIMPLECAD_SKILL_SRC}"
  printf 'export PYTHONPATH="%s"\\n' "${PYTHONPATH}"
  exit 0
fi

if [[ "${1:-}" == "--check" ]]; then
  "${PYTHON_BIN}" - <<'PY'
import importlib

deps = ("numpy", "cadquery")
missing = []
for dep in deps:
    try:
        importlib.import_module(dep)
    except Exception as exc:
        missing.append((dep, str(exc)))

if missing:
    print("Missing runtime dependencies:")
    for name, reason in missing:
        print(f"- {name}: {reason}")
    raise SystemExit(1)

import simplecadapi  # noqa: F401
print("Dependency check passed. simplecadapi import is available.")
PY
  exit 0
fi

if [[ "${1:-}" == "--" ]]; then
  shift
fi

if [[ $# -eq 0 ]]; then
  echo "Skill import path is ready in this shell process."
  echo "Run with wrapper: scripts/with_skill.sh -- python3 your_script.py"
  echo 'Or export vars into current shell: eval "$(scripts/with_skill.sh --print-env)"'
  echo "Check dependencies: scripts/with_skill.sh --check"
  exit 0
fi

exec "$@"
                """
            )
        ).rstrip() + "\n"

    def _script_jupyter_with_skill(self) -> str:
        return (
            self._script_common_preamble()
            + textwrap.dedent(
                """\

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

if ! "${PYTHON_BIN}" -m jupyter --version >/dev/null 2>&1; then
  echo "Error: jupyter is not available in current python environment." >&2
  echo "Install it with: ${PYTHON_BIN} -m pip install jupyterlab" >&2
  exit 1
fi

exec "${SCRIPT_DIR}/with_skill.sh" -- "${PYTHON_BIN}" -m jupyter "${JUPYTER_APP}" "$@"
                """
            )
        ).rstrip() + "\n"

    @staticmethod
    def _script_repl_bootstrap_py() -> str:
        return (
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                \"\"\"Bootstrap skill import path inside a persistent Python process.\"\"\"

                from __future__ import annotations

                import argparse
                import os
                import sys
                from pathlib import Path


                def activate(check: bool = False) -> int:
                    script_path = Path(__file__).resolve()
                    skill_root = script_path.parent.parent
                    skill_src = skill_root / "assets" / "project_snapshot" / "src"

                    if not skill_src.exists():
                        print(f"Error: missing skill source path: {skill_src}", file=sys.stderr)
                        return 1

                    skill_src_str = str(skill_src)
                    if skill_src_str not in sys.path:
                        sys.path.insert(0, skill_src_str)

                    os.environ["SIMPLECAD_SKILL_ROOT"] = str(skill_root)
                    os.environ["SIMPLECAD_SKILL_SRC"] = skill_src_str

                    current = os.environ.get("PYTHONPATH", "")
                    paths = [item for item in current.split(os.pathsep) if item] if current else []
                    if skill_src_str not in paths:
                        os.environ["PYTHONPATH"] = (
                            os.pathsep.join([skill_src_str, *paths]) if paths else skill_src_str
                        )

                    if check:
                        try:
                            import simplecadapi  # noqa: F401
                        except Exception as exc:
                            print(f"Path injected but import check failed: {exc}", file=sys.stderr)
                            return 1

                    print(f"Activated skill source: {skill_src_str}")
                    print("You can now run: import simplecadapi as scad")
                    return 0


                def main() -> None:
                    parser = argparse.ArgumentParser(
                        description="Activate SimpleCAD skill import path in current Python process"
                    )
                    parser.add_argument(
                        "--check",
                        action="store_true",
                        help="Also check that `import simplecadapi` succeeds",
                    )
                    args = parser.parse_args()
                    raise SystemExit(activate(check=args.check))


                if __name__ == "__main__":
                    main()
                """
            ).rstrip()
            + "\n"
        )

    def _script_refresh_docs(self) -> str:
        return (
            self._script_common_preamble()
            + textwrap.dedent(
                """\

                "${PYTHON_BIN}" "${SNAPSHOT_ROOT}/src/simplecadapi/auto_tools/auto_docs_gen.py" \
                  --source "${SNAPSHOT_ROOT}/src/simplecadapi/operations.py" \
                  --source "${SNAPSHOT_ROOT}/src/simplecadapi/evolve.py" \
                  --output-dir "${SNAPSHOT_ROOT}/docs/api" \
                  "$@"
                """
            )
        ).rstrip() + "\n"

    def _script_rebuild_exports(self) -> str:
        return (
            self._script_common_preamble()
            + textwrap.dedent(
                """\

                "${PYTHON_BIN}" "${SNAPSHOT_ROOT}/src/simplecadapi/auto_tools/make_export.py" --force "$@"
                """
            )
        ).rstrip() + "\n"

    def _script_validate_skill(self) -> str:
        return (
            self._script_common_preamble()
            + textwrap.dedent(
                """\

                missing=0
                required=(
                  "SKILL.md"
                  "scripts/with_skill.sh"
                  "scripts/jupyter_with_skill.sh"
                  "scripts/repl_bootstrap.py"
                  "scripts/add_new_case.sh"
                  "scripts/rebuild_exports.sh"
                  "scripts/refresh_docs.sh"
                  "scripts/repack_skill.sh"
                  "scripts/validate_skill.sh"
                  "references/PROJECT_OVERVIEW.md"
                  "references/API_INDEX.md"
                  "references/CORE_INDEX.md"
                  "references/EVOLVE_WORKFLOW.md"
                  "assets/project_snapshot/src/simplecadapi/operations.py"
                  "assets/project_snapshot/src/simplecadapi/evolve.py"
                  "assets/project_snapshot/docs/api/README.md"
                )

                for relative in "${required[@]}"; do
                  if [[ ! -e "${SKILL_ROOT}/${relative}" ]]; then
                    echo "Missing required path: ${relative}" >&2
                    missing=1
                  fi
                done

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
        ).rstrip() + "\n"

    def _script_repack_skill(self) -> str:
        return (
            self._script_common_preamble()
            + textwrap.dedent(
                """\

                SKILLS_ROOT="$(cd "${SKILL_ROOT}/.." && pwd)"
                SKILL_NAME="$(basename "${SKILL_ROOT}")"
                TEMP_ROOT="$(mktemp -d)"
                trap 'rm -rf "${TEMP_ROOT}"' EXIT

                "${PYTHON_BIN}" "${SNAPSHOT_ROOT}/src/simplecadapi/auto_tools/skill_pack.py" \
                  --project-root "${SNAPSHOT_ROOT}" \
                  --output-root "${TEMP_ROOT}" \
                  --skill-name "${SKILL_NAME}" \
                  "$@"

                GENERATED_SKILL="${TEMP_ROOT}/${SKILL_NAME}"

                "${PYTHON_BIN}" - "${GENERATED_SKILL}" "${SKILL_ROOT}" <<'PY'
                import shutil
                import sys
                from pathlib import Path

                source = Path(sys.argv[1])
                target = Path(sys.argv[2])

                if not source.exists():
                    raise SystemExit(f"Generated skill path does not exist: {source}")

                for item in list(target.iterdir()):
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()

                for item in source.iterdir():
                    destination = target / item.name
                    if item.is_dir():
                        shutil.copytree(item, destination)
                    else:
                        shutil.copy2(item, destination)
                PY

                echo "Skill repacked: ${SKILL_ROOT}"
                """
            )
        ).rstrip() + "\n"

    def _script_add_new_case(self) -> str:
        return (
            self._script_common_preamble()
            + textwrap.dedent(
                """\

                if [[ $# -lt 1 ]]; then
                  echo "Usage: scripts/add_new_case.sh <python-script-path>" >&2
                  exit 1
                fi

                INPUT_SCRIPT="$1"
                shift

                if [[ ! -f "${INPUT_SCRIPT}" ]]; then
                  echo "Input script not found: ${INPUT_SCRIPT}" >&2
                  exit 1
                fi

                "${SCRIPT_DIR}/validate_skill.sh"

                "${PYTHON_BIN}" "${SNAPSHOT_ROOT}/src/simplecadapi/auto_tools/evolution.py" \
                  "${INPUT_SCRIPT}" \
                  --evolve_file "${SNAPSHOT_ROOT}/src/simplecadapi/evolve.py"

                "${SCRIPT_DIR}/rebuild_exports.sh" --force
                "${SCRIPT_DIR}/refresh_docs.sh"

                if [[ "${NO_REPACK:-0}" != "1" ]]; then
                  "${SCRIPT_DIR}/repack_skill.sh" "$@"
                else
                  echo "NO_REPACK=1 set, skipping skill repack step."
                fi

                echo "Add-new-case pipeline completed."
                """
            )
        ).rstrip() + "\n"

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
        description="Package SimpleCAD API into an Agent Skills compatible bundle"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Project root to snapshot (default: repository root)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory where the skill folder is written (default: ./skills)",
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
        help="Create <skill-name>.tar.gz next to the generated skill directory",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce console output",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    packager = SkillPackager(
        project_root=args.project_root,
        output_root=args.output_root,
        skill_name=args.skill_name,
        license_name=args.license_name,
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
