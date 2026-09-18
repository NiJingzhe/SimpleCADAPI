"""Build the bundled skill into a user-selected destination."""
from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from .compiler import (
    SkillBuildError, SkillProject, _frontmatter_name, _validate_output_paths,
    build_target, collect_source_files, load_project,
)


def bundled_project() -> SkillProject:
    root = Path(__file__).parent / "resources"
    if not (root / "skillproj.toml").is_file():
        # Editable installs keep resources at their canonical checkout location.
        root = Path(__file__).resolve().parents[3]
    return load_project(root)


def _check_destination(output: Path, name: str, force: bool) -> None:
    if output.is_symlink():
        raise SkillBuildError(f"refusing symlink destination: {output}")
    if not output.exists():
        return
    if not force:
        raise SkillBuildError(f"destination exists: {output}; use --force to replace this skill")
    marker = output / "SKILL.md"
    if not output.is_dir() or not marker.is_file() or marker.is_symlink():
        raise SkillBuildError(f"refusing to replace non-skill destination: {output}")
    if _frontmatter_name(marker.read_text(encoding="utf-8")) != name:
        raise SkillBuildError(f"refusing to replace destination with a different skill name: {output}")


def build_skill(*, project: SkillProject, target: str, output: Path,
                force: bool = False) -> dict[str, Any]:
    if target not in project.targets:
        raise SkillBuildError(f"unknown target {target!r}; choose from: {', '.join(project.targets)}")
    output = output.expanduser().absolute()
    _check_destination(output, project.name, force)
    output = output.resolve()
    _validate_output_paths(project.root, project.source, {target: output})
    source_files = collect_source_files(project.source, frozenset(project.targets), project.root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".sca-skill-", dir=output.parent) as temporary:
        stage = Path(temporary) / "build"
        build_target(replace(project, outputs={target: stage}), source_files, target, quiet=True)
        marker = stage / "SKILL.md"
        if not marker.is_file() or _frontmatter_name(marker.read_text(encoding="utf-8")) != project.name:
            raise SkillBuildError(f"source must contain SKILL.md declaring name: {project.name}")
        _check_destination(output, project.name, force)
        backup = Path(temporary) / "previous"
        if output.exists():
            output.rename(backup)
        try:
            stage.rename(output)
        except OSError:
            if backup.exists():
                backup.rename(output)
            raise
    return {"name": project.name, "target": target, "output": str(output), "files": len(source_files)}
